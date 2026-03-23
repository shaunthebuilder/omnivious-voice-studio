from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from .config import (
    CERTIFICATION_REQUIRED_SIMILARITY,
    DEFAULT_TTS_MODEL_FINAL,
    DEFAULT_TTS_MODEL_PREVIEW,
    JOB_STALE_TIMEOUT_SECONDS,
    OUTPUT_DIR,
    SEGMENT_CROSSFADE_MS,
    SYNTH_TIMEOUT_SECONDS,
)
from .database import SessionLocal
from .models import Generation, Job, Persona
from .persona_service import certify_existing_persona, ingest_persona_audio
from .speaker_identity import identity_scorer
from .style_compiler import clamp_qwen_speed, compile_style_text, normalize_style, plan_tts_segments
from .tts_service import TTSError, tts_service

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self) -> None:
        self.tasks: dict[int, asyncio.Task[Any]] = {}
        self._generation_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='omnivious-generation')

    def shutdown(self) -> None:
        self._generation_executor.shutdown(wait=False, cancel_futures=True)

    def create_job(self, db: Session, job_type: str, payload: dict[str, Any]) -> Job:
        job = Job(job_type=job_type, payload_json=json.dumps(payload), status='queued', progress=0.05)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def enqueue_ingest(self, job_id: int) -> None:
        self._enqueue(job_id, self._run_ingest, fail_generation=False)

    def enqueue_generation(self, job_id: int) -> None:
        self._enqueue(job_id, self._run_generation, fail_generation=True)

    def enqueue_certification(self, job_id: int) -> None:
        self._enqueue(job_id, self._run_certification, fail_generation=False)

    def _enqueue(self, job_id: int, runner: Callable[[int], Any], fail_generation: bool) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._fail_enqueue(job_id, 'Could not enqueue job: no running event loop', fail_generation=fail_generation)
            return
        task = loop.create_task(runner(job_id))
        self.tasks[job_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(job_id, None))

    async def _run_worker_call(self, fn: Callable[..., Any], *args: Any, timeout: float | None = None, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._generation_executor, lambda: fn(*args, **kwargs))
        if timeout is None:
            return await future
        return await asyncio.wait_for(future, timeout=timeout)

    def _set_job_state(
        self,
        db: Session,
        job: Job,
        *,
        status: str | None = None,
        progress: float | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if result is not None:
            job.result_json = json.dumps(result)
        if error is not None:
            job.error = error
        db.add(job)
        db.commit()

    def _set_persona_training(
        self,
        db: Session,
        persona: Persona,
        *,
        status: str | None = None,
        progress: float | None = None,
        job_id: int | None = None,
        set_job_id: bool = False,
        error: str | None = None,
        set_error: bool = False,
        certification_status: str | None = None,
        certification_error: str | None = None,
    ) -> None:
        if status is not None:
            persona.training_status = status
        if progress is not None:
            persona.training_progress = progress
        if set_job_id:
            persona.training_job_id = job_id
        if set_error:
            persona.training_error = error
        if certification_status is not None:
            persona.certification_status = certification_status
        if certification_error is not None or certification_status == 'certified':
            persona.certification_error = certification_error
        db.add(persona)
        db.commit()

    def _fail_enqueue(self, job_id: int, error: str, fail_generation: bool) -> None:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            self._set_job_state(db, job, status='failed', error=error)
            payload = json.loads(job.payload_json)
            persona_id = payload.get('persona_id')
            if job.job_type in {'persona_ingest', 'persona_certify'} and persona_id is not None:
                persona = db.query(Persona).filter(Persona.id == persona_id).first()
                if persona:
                    self._set_persona_training(
                        db,
                        persona,
                        status='failed',
                        progress=job.progress,
                        job_id=job.id,
                        set_job_id=True,
                        error=error,
                        set_error=True,
                        certification_status='rejected' if job.job_type == 'persona_certify' else persona.certification_status,
                    )
            if fail_generation:
                generation_id = payload.get('generation_id')
                if generation_id is not None:
                    generation = db.query(Generation).filter(Generation.id == generation_id).first()
                    if generation:
                        generation.status = 'failed'
                        db.add(generation)
                        db.commit()
        finally:
            db.close()

    def recover_stale_running_jobs(self, *, stale_after_seconds: float, reason: str = 'worker_restarted_or_timeout') -> int:
        if stale_after_seconds <= 0:
            return 0
        cutoff = datetime.utcnow() - timedelta(seconds=float(stale_after_seconds))
        recovered = 0
        db = SessionLocal()
        try:
            stale_jobs = db.query(Job).filter(Job.status == 'running').filter(Job.updated_at < cutoff).all()
            for job in stale_jobs:
                payload: dict[str, Any] = {}
                try:
                    payload = json.loads(job.payload_json)
                    if not isinstance(payload, dict):
                        payload = {}
                except Exception:
                    payload = {}
                job.status = 'failed'
                job.error = reason
                db.add(job)
                recovered += 1

                generation_id = payload.get('generation_id')
                if generation_id is not None:
                    generation = db.query(Generation).filter(Generation.id == generation_id).first()
                    if generation and generation.status in {'queued', 'running'}:
                        generation.status = 'failed'
                        db.add(generation)

                persona_id = payload.get('persona_id')
                if job.job_type in {'persona_ingest', 'persona_certify'} and persona_id is not None:
                    persona = db.query(Persona).filter(Persona.id == persona_id).first()
                    if persona and persona.training_status in {'queued', 'running'}:
                        persona.training_status = 'failed'
                        persona.training_error = reason
                        persona.training_progress = max(float(persona.training_progress or 0.0), 0.05)
                        db.add(persona)
            if recovered > 0:
                db.commit()
        finally:
            db.close()
        return recovered

    async def _run_ingest(self, job_id: int) -> None:
        db = SessionLocal()
        persona: Persona | None = None
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            payload = json.loads(job.payload_json)
            persona = db.query(Persona).filter(Persona.id == payload['persona_id']).first()
            if not persona:
                self._set_job_state(db, job, status='failed', error='Persona not found')
                return

            self._set_job_state(db, job, status='running', progress=0.1)
            self._set_persona_training(
                db,
                persona,
                status='running',
                progress=0.1,
                job_id=job.id,
                set_job_id=True,
                error=None,
                set_error=True,
                certification_status='certifying',
                certification_error=None,
            )

            progress_ref = {'value': 0.1}

            def on_progress(value: float) -> None:
                progress_ref['value'] = value
                inner_db = SessionLocal()
                try:
                    inner_job = inner_db.query(Job).filter(Job.id == job.id).first()
                    inner_persona = inner_db.query(Persona).filter(Persona.id == persona.id).first()
                    if inner_job:
                        self._set_job_state(inner_db, inner_job, status='running', progress=value)
                    if inner_persona:
                        self._set_persona_training(
                            inner_db,
                            inner_persona,
                            status='running',
                            progress=value,
                            job_id=job.id,
                            set_job_id=True,
                            error=None,
                            set_error=True,
                            certification_status='certifying',
                            certification_error=None,
                        )
                finally:
                    inner_db.close()

            updated = await self._run_worker_call(
                ingest_persona_audio,
                persona,
                payload['source_type'],
                payload['source_ref'],
                payload.get('upload_path'),
                db,
                on_progress=on_progress,
            )
            db.refresh(updated)
            result = {
                'persona_id': updated.id,
                'ref_audio_path': updated.ref_audio_path,
                'anchor_audio_path': updated.anchor_audio_path,
                'conditioning_long_path': updated.conditioning_long_path,
                'duration_sec': updated.duration_sec,
                'training_audio_seconds': updated.training_audio_seconds,
                'training_source_duration_seconds': updated.training_source_duration_seconds,
                'certification_status': updated.certification_status,
                'certified_profile_version': updated.certified_profile_version,
            }
            self._set_job_state(db, job, status='completed', progress=1.0, result=result)
            self._set_persona_training(
                db,
                updated,
                status='completed',
                progress=1.0,
                job_id=job.id,
                set_job_id=True,
                error=None,
                set_error=True,
                certification_status='certified',
                certification_error=None,
            )
        except Exception as exc:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                logger.exception('Persona ingest job %s failed', job_id)
                self._set_job_state(db, job, status='failed', error=str(exc))
                if persona:
                    self._set_persona_training(
                        db,
                        persona,
                        status='failed',
                        progress=max(job.progress, 0.05),
                        job_id=job.id,
                        set_job_id=True,
                        error=str(exc),
                        set_error=True,
                        certification_status='rejected',
                        certification_error=str(exc),
                    )
        finally:
            db.close()

    async def _run_certification(self, job_id: int) -> None:
        db = SessionLocal()
        persona: Persona | None = None
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            payload = json.loads(job.payload_json)
            persona = db.query(Persona).filter(Persona.id == payload['persona_id']).first()
            if not persona:
                self._set_job_state(db, job, status='failed', error='Persona not found')
                return
            if not persona.ref_audio_path:
                self._set_job_state(db, job, status='failed', error='Persona reference audio missing')
                return

            self._set_job_state(db, job, status='running', progress=0.56)
            self._set_persona_training(
                db,
                persona,
                status='running',
                progress=0.56,
                job_id=job.id,
                set_job_id=True,
                error=None,
                set_error=True,
                certification_status='certifying',
                certification_error=None,
            )

            def on_progress(value: float) -> None:
                inner_db = SessionLocal()
                try:
                    inner_job = inner_db.query(Job).filter(Job.id == job.id).first()
                    inner_persona = inner_db.query(Persona).filter(Persona.id == persona.id).first()
                    if inner_job:
                        self._set_job_state(inner_db, inner_job, status='running', progress=value)
                    if inner_persona:
                        self._set_persona_training(
                            inner_db,
                            inner_persona,
                            status='running',
                            progress=value,
                            job_id=job.id,
                            set_job_id=True,
                            error=None,
                            set_error=True,
                            certification_status='certifying',
                            certification_error=None,
                        )
                finally:
                    inner_db.close()

            updated = await self._run_worker_call(certify_existing_persona, persona, db, on_progress=on_progress)
            db.refresh(updated)
            result = {
                'persona_id': updated.id,
                'certification_status': updated.certification_status,
                'certified_profile_version': updated.certified_profile_version,
            }
            self._set_job_state(db, job, status='completed', progress=1.0, result=result)
            self._set_persona_training(
                db,
                updated,
                status='completed',
                progress=1.0,
                job_id=job.id,
                set_job_id=True,
                error=None,
                set_error=True,
                certification_status='certified',
                certification_error=None,
            )
        except Exception as exc:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                logger.exception('Persona certification job %s failed', job_id)
                self._set_job_state(db, job, status='failed', error=str(exc))
                if persona:
                    self._set_persona_training(
                        db,
                        persona,
                        status='failed',
                        progress=max(job.progress, 0.56),
                        job_id=job.id,
                        set_job_id=True,
                        error=str(exc),
                        set_error=True,
                        certification_status='rejected',
                        certification_error=str(exc),
                    )
        finally:
            db.close()

    async def _run_generation(self, job_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            payload = json.loads(job.payload_json)
            generation = db.query(Generation).filter(Generation.id == payload['generation_id']).first()
            if not generation:
                self._set_job_state(db, job, status='failed', error='Generation not found')
                return
            persona = db.query(Persona).filter(Persona.id == generation.persona_id).first()
            if not persona:
                self._set_job_state(db, job, status='failed', error='Persona not found')
                generation.status = 'failed'
                db.add(generation)
                db.commit()
                return
            if persona.certification_status != 'certified':
                raise RuntimeError('Persona must be certified before generation')

            render_mode = str(payload.get('render_mode') or 'final').lower()
            normalized_style, style_warnings = normalize_style(str(payload.get('style') or 'natural'))
            speed = clamp_qwen_speed(float(payload.get('speed', 1.0)))
            primary_model = tts_service.resolve_model_id(payload.get('model_id'), render_mode=render_mode)
            fallback_model = DEFAULT_TTS_MODEL_PREVIEW
            ref_primary = persona.conditioning_long_path or persona.anchor_audio_path or persona.ref_audio_path
            ref_fallback = persona.anchor_audio_path or persona.conditioning_long_path or persona.ref_audio_path
            if not ref_primary:
                raise RuntimeError('Persona conditioning audio missing')
            speaker_embedding = self._load_or_create_speaker_embedding(persona, ref_fallback or ref_primary, db)
            render_profile = self._load_json(persona.render_profile_json)
            style_defaults = render_profile.get('style_defaults', {}) if isinstance(render_profile, dict) else {}
            profile_style_default = style_defaults.get(normalized_style, {}) if isinstance(style_defaults, dict) else {}
            profile_multiplier = float(profile_style_default.get('style_strength', 1.0)) if isinstance(profile_style_default, dict) else 1.0

            generation.status = 'running'
            generation.style = normalized_style
            generation.render_mode = render_mode
            generation.engine_requested = primary_model
            generation.certified_profile_version = persona.certified_profile_version
            db.add(generation)
            db.commit()
            self._set_job_state(db, job, status='running', progress=0.08)

            segments, _, planner_warnings = plan_tts_segments(generation.input_text, normalized_style)
            if not segments:
                raise RuntimeError('Could not build speech segments')

            rendered_segments: list[dict[str, Any]] = []
            stitched_inputs: list[tuple[np.ndarray, int, int]] = []
            applied_tags: list[str] = []
            processed_segments: list[str] = []
            warning_codes: list[str] = [*style_warnings, *planner_warnings]
            fallback_used = False
            llm_enhance_ms = 0.0
            generation_start = time.perf_counter()

            for index, segment in enumerate(segments, start=1):
                progress_base = 0.12 + ((index - 1) / max(len(segments), 1)) * 0.72
                self._set_job_state(db, job, progress=min(0.9, progress_base))
                compiled_primary = compile_style_text(
                    segment.text,
                    normalized_style,
                    style_strength=segment.style_strength * profile_multiplier,
                    render_mode=render_mode,
                    segment_index=segment.index,
                )
                segment_attempts = [
                    {
                        'label': 'primary',
                        'model_id': primary_model,
                        'ref_audio_path': ref_primary,
                        'style': normalized_style,
                        'compile': compiled_primary,
                    }
                ]
                if primary_model != fallback_model:
                    segment_attempts.append(
                        {
                            'label': 'fallback_engine',
                            'model_id': fallback_model,
                            'ref_audio_path': ref_primary,
                            'style': normalized_style,
                            'compile': compile_style_text(
                                segment.text,
                                normalized_style,
                                style_strength=min(0.92, segment.style_strength * 0.82 * profile_multiplier),
                                render_mode='preview',
                                segment_index=segment.index,
                            ),
                        }
                    )
                segment_attempts.append(
                    {
                        'label': 'natural_anchor_fallback',
                        'model_id': fallback_model,
                        'ref_audio_path': ref_fallback,
                        'style': 'natural',
                        'compile': compile_style_text(
                            segment.text,
                            'natural',
                            style_strength=0.7,
                            render_mode='preview',
                            segment_index=segment.index,
                        ),
                    }
                )

                chosen_attempt: dict[str, Any] | None = None
                last_error: str | None = None
                for attempt in segment_attempts:
                    synth_start = time.perf_counter()
                    try:
                        wav, sample_rate, engine_name = await self._run_worker_call(
                            tts_service.synthesize_raw,
                            text=attempt['compile'].styled_text,
                            ref_audio_path=str(attempt['ref_audio_path']),
                            requested_model_id=str(attempt['model_id']),
                            speed=1.0,
                            generation_options=attempt['compile'].generation_params,
                            timeout=max(5.0, float(SYNTH_TIMEOUT_SECONDS)),
                        )
                        chosen_attempt = {
                            'segment_index': segment.index,
                            'segment_text': segment.text,
                            'styled_text': attempt['compile'].styled_text,
                            'applied_tags': attempt['compile'].applied_tags,
                            'disfluency_edits': attempt['compile'].disfluency_edits,
                            'engine_used': engine_name,
                            'engine_model': attempt['model_id'],
                            'fallback_label': attempt['label'],
                            'pause_ms': segment.pause_ms,
                            'timing_ms': {'synthesis_ms': round((time.perf_counter() - synth_start) * 1000, 2)},
                            'warnings': [*attempt['compile'].warnings],
                        }
                        if attempt['label'] != 'primary':
                            fallback_used = True
                            warning_codes.append(f"segment_{segment.index}_{attempt['label']}")
                        stitched_inputs.append((wav, sample_rate, segment.pause_ms))
                        applied_tags.extend(attempt['compile'].applied_tags)
                        processed_segments.append(attempt['compile'].styled_text)
                        rendered_segments.append(chosen_attempt)
                        break
                    except Exception as exc:
                        last_error = str(exc)
                        warning_codes.append(f"segment_{segment.index}_{attempt['label']}_error")
                if chosen_attempt is None:
                    raise RuntimeError(f'Segment {segment.index} could not be rendered: {last_error or "unknown error"}')

            self._set_job_state(db, job, progress=0.92)
            final_wav, sample_rate = self._stitch_segments(stitched_inputs)
            final_wav = tts_service._apply_speed_transform(final_wav, sample_rate, speed)  # noqa: SLF001
            output_path = OUTPUT_DIR / f'gen_{generation.id}_{uuid.uuid4().hex}.wav'
            await self._run_worker_call(tts_service.write_audio, output_path, final_wav, sample_rate)
            advisory_identity = await self._run_worker_call(identity_scorer.similarity, speaker_embedding, output_path)
            if advisory_identity.score < CERTIFICATION_REQUIRED_SIMILARITY:
                warning_codes.append('identity_advisory_low')

            total_generation_ms = round((time.perf_counter() - generation_start) * 1000, 2)
            engine_used = 'mixed' if {row['engine_used'] for row in rendered_segments}.__len__() > 1 else rendered_segments[0]['engine_used']
            fallback_engine_used = DEFAULT_TTS_MODEL_PREVIEW if fallback_used else None

            generation.processed_text = ' '.join(processed_segments)
            generation.audio_path = str(output_path)
            generation.duration_sec = round(float(len(final_wav) / max(sample_rate, 1)), 3)
            generation.identity_score = round(float(advisory_identity.score), 4)
            generation.retry_count = sum(1 for row in rendered_segments if row['fallback_label'] != 'primary')
            generation.fallback_applied = 1 if fallback_used else 0
            generation.applied_tags_json = json.dumps(applied_tags)
            generation.attempts_json = json.dumps(rendered_segments)
            generation.engine = engine_used
            generation.engine_used = engine_used
            generation.fallback_engine_used = fallback_engine_used
            generation.segment_count = len(rendered_segments)
            generation.warning_codes_json = json.dumps(sorted(set(warning_codes)))
            generation.status = 'completed'
            db.add(generation)
            db.commit()

            result = {
                'generation_id': generation.id,
                'audio_path': generation.audio_path,
                'duration_sec': generation.duration_sec,
                'style': generation.style,
                'render_mode': render_mode,
                'engine_requested': primary_model,
                'engine_used': generation.engine_used,
                'fallback_engine_used': generation.fallback_engine_used,
                'segment_count': generation.segment_count,
                'applied_tags': applied_tags,
                'identity_score': generation.identity_score,
                'warning_codes': sorted(set(warning_codes)),
                'fallback_applied': bool(generation.fallback_applied),
                'llm_enhance_ms': llm_enhance_ms,
                'synthesis_ms': round(sum(row['timing_ms']['synthesis_ms'] for row in rendered_segments), 2),
                'identity_score_ms': 0.0,
                'total_generation_ms': total_generation_ms,
                'attempt_count': len(rendered_segments),
                'reasoner_timeout_triggered': False,
                'stage_timeout_triggered': False,
                'input_chars': len(generation.input_text or ''),
                'enhanced_chars': len(generation.processed_text or ''),
                'growth_ratio': round(len(generation.processed_text or '') / max(1, len(generation.input_text or '')), 3),
                'disfluency_edits': [edit for row in rendered_segments for edit in row.get('disfluency_edits', [])],
            }
            self._set_job_state(db, job, status='completed', progress=1.0, result=result)
        except Exception as exc:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                logger.exception('Generation job %s failed', job_id)
                self._set_job_state(db, job, status='failed', error=str(exc))
            if job:
                payload = json.loads(job.payload_json)
                generation_id = payload.get('generation_id')
                if generation_id:
                    generation = db.query(Generation).filter(Generation.id == generation_id).first()
                    if generation:
                        generation.status = 'failed'
                        db.add(generation)
                        db.commit()
        finally:
            db.close()

    def _load_or_create_speaker_embedding(self, persona: Persona, ref_audio_path: str, db: Session) -> np.ndarray:
        if persona.speaker_embedding_path and Path(persona.speaker_embedding_path).exists():
            return identity_scorer.load_embedding(persona.speaker_embedding_path)
        emb = identity_scorer.embedding_from_audio_path(ref_audio_path)
        persona_dir = Path(ref_audio_path).parent
        emb_path = persona_dir / 'speaker_embedding.npy'
        persona.speaker_embedding_path = identity_scorer.save_embedding(emb, emb_path)
        db.add(persona)
        db.commit()
        return emb

    def _load_json(self, raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _stitch_segments(self, parts: list[tuple[np.ndarray, int, int]]) -> tuple[np.ndarray, int]:
        if not parts:
            raise RuntimeError('No rendered segments available to stitch')
        sample_rate = parts[0][1]
        output = parts[0][0].astype(np.float32)
        for wav, sr, pause_ms in parts[1:]:
            if sr != sample_rate:
                raise RuntimeError('Segment sample rates do not match')
            pause_samples = int(sample_rate * (pause_ms / 1000.0))
            if pause_samples > 0:
                output = np.concatenate([output, np.zeros(pause_samples, dtype=np.float32)])
            output = _crossfade_concat(output, wav.astype(np.float32), sample_rate)
        return output.astype(np.float32), sample_rate


job_manager = JobManager()


def _crossfade_concat(a: np.ndarray, b: np.ndarray, sample_rate: int) -> np.ndarray:
    if a.size == 0:
        return b
    if b.size == 0:
        return a
    fade_samples = max(1, int(sample_rate * (SEGMENT_CROSSFADE_MS / 1000.0)))
    fade_samples = min(fade_samples, a.shape[0], b.shape[0])
    if fade_samples <= 1:
        return np.concatenate([a, b])
    fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
    fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
    overlap = (a[-fade_samples:] * fade_out) + (b[:fade_samples] * fade_in)
    return np.concatenate([a[:-fade_samples], overlap, b[fade_samples:]]).astype(np.float32)
