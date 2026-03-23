from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .cleanup import prune_expired_generations
from .config import (
    API_CORS_ORIGINS,
    CLEANUP_INTERVAL_SECONDS,
    DATA_DIR,
    DEFAULT_TTS_MODEL_FINAL,
    DEFAULT_TTS_MODEL_PREVIEW,
    IDENTITY_HARD_FAIL_FLOOR,
    IDENTITY_STRICT_PASS_THRESHOLD,
    JOB_STALE_TIMEOUT_SECONDS,
    JOB_WATCHDOG_INTERVAL_SECONDS,
    JOBS_DIR,
    OUTPUT_DIR,
    PERSONA_DIR,
    TTS_RETENTION_HOURS,
    validate_certification_thresholds,
)
from .database import Base, engine, get_db, run_startup_migrations
from .ingest import save_upload_tmp
from .jobs import job_manager
from .models import Generation, Job, Persona
from .persona_service import PersonaError, get_persona, list_personas, resolve_unique_persona_name
from .style_compiler import DISABLED_DEFAULT_TAGS, STYLE_CATALOG, TAG_DETAILS
from .schemas import (
    DeleteGenerationOut,
    DeletePersonaOut,
    GenerateIn,
    GenerateResponse,
    GenerationOut,
    HealthOut,
    JobOut,
    PersonaCreateResponse,
    PersonaOut,
    PersonaRenameIn,
    SpeechTagOut,
    StyleOut,
)
from .tts_service import tts_service

app = FastAPI(title='Omnivious Voice Studio API', version='0.3.0')
cleanup_task: asyncio.Task | None = None
watchdog_task: asyncio.Task | None = None
warmup_task: asyncio.Task | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

for p in [DATA_DIR, PERSONA_DIR, JOBS_DIR, OUTPUT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)
run_startup_migrations()
app.mount('/media', StaticFiles(directory=DATA_DIR), name='media')


@app.on_event('startup')
async def on_startup() -> None:
    validate_certification_thresholds()
    job_manager.recover_stale_running_jobs(stale_after_seconds=JOB_STALE_TIMEOUT_SECONDS)

    global cleanup_task, watchdog_task, warmup_task
    tts_service.startup_state = 'warming'
    tts_service.startup_error = None
    warmup_task = asyncio.create_task(_warm_tts_models())
    cleanup_task = asyncio.create_task(_cleanup_loop())
    watchdog_task = asyncio.create_task(_job_watchdog_loop())


@app.on_event('shutdown')
async def on_shutdown() -> None:
    global cleanup_task, watchdog_task, warmup_task
    job_manager.shutdown()
    if warmup_task:
        warmup_task.cancel()
        warmup_task = None
    if cleanup_task:
        cleanup_task.cancel()
        cleanup_task = None
    if watchdog_task:
        watchdog_task.cancel()
        watchdog_task = None


@app.get('/api/health', response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(
        status='ok',
        startup_state=tts_service.startup_state,
        startup_error=tts_service.startup_error,
        model_ready=tts_service.ready,
        preview_ready=tts_service.engines['preview'].ready,
        final_ready=tts_service.engines['final'].ready,
        preview_model_id=DEFAULT_TTS_MODEL_PREVIEW,
        final_model_id=tts_service.model_id or DEFAULT_TTS_MODEL_FINAL,
        llm_ready=False,
        llm_model=None,
    )


@app.post('/api/personas', response_model=PersonaCreateResponse)
async def create_persona(
    persona_name: str = Form(...),
    source_type: str = Form(...),
    youtube_url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> PersonaCreateResponse:
    resolved_name = _resolve_persona_name_or_400(db, persona_name)
    source_ref, upload_path = await _resolve_training_source(source_type, youtube_url, file)

    persona = Persona(
        name=resolved_name,
        source_type=source_type,
        source_ref=source_ref,
        training_status='queued',
        training_progress=0.05,
        training_error=None,
        certification_status='pending',
        certification_error=None,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)

    payload = {
        'persona_id': persona.id,
        'source_type': source_type,
        'source_ref': source_ref,
        'upload_path': upload_path,
    }
    job = job_manager.create_job(db, 'persona_ingest', payload)
    persona.training_job_id = job.id
    db.add(persona)
    db.commit()
    db.refresh(persona)
    job_manager.enqueue_ingest(job.id)
    return PersonaCreateResponse(persona=_persona_out(persona), job_id=job.id)


@app.get('/api/personas', response_model=list[PersonaOut])
def personas(db: Session = Depends(get_db)) -> list[PersonaOut]:
    return [_persona_out(p) for p in list_personas(db)]


@app.get('/api/personas/{persona_id}', response_model=PersonaOut)
def persona_by_id(persona_id: int, db: Session = Depends(get_db)) -> PersonaOut:
    persona = get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    return _persona_out(persona)


@app.get('/api/styles', response_model=list[StyleOut])
def list_styles() -> list[StyleOut]:
    return [
        StyleOut(
            id=style_id,  # type: ignore[arg-type]
            label=str(meta['label']),
            description=str(meta['description']),
            uses_tags=bool(meta['uses_tags']),
            supported_tags=list(meta.get('supported_tags', [])),  # type: ignore[arg-type]
        )
        for style_id, meta in STYLE_CATALOG.items()
    ]


@app.get('/api/tags', response_model=list[SpeechTagOut])
def list_speech_tags() -> list[SpeechTagOut]:
    return [
        SpeechTagOut(tag=tag, description=description, enabled=tag not in DISABLED_DEFAULT_TAGS)
        for tag, description in TAG_DETAILS.items()
    ]


@app.patch('/api/personas/{persona_id}', response_model=PersonaOut)
def rename_persona(persona_id: int, payload: PersonaRenameIn, db: Session = Depends(get_db)) -> PersonaOut:
    persona = get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    persona.name = _resolve_persona_name_or_400(db, payload.name, exclude_persona_id=persona_id)
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return _persona_out(persona)


@app.delete('/api/personas/{persona_id}', response_model=DeletePersonaOut)
def delete_persona(persona_id: int, db: Session = Depends(get_db)) -> DeletePersonaOut:
    persona = get_persona(db, persona_id)
    if not persona:
        return DeletePersonaOut(deleted=True, generation_files_deleted=0, persona_assets_deleted=False)

    generations = db.query(Generation).filter(Generation.persona_id == persona.id).all()
    generation_files_deleted = 0
    for generation in generations:
        if generation.audio_path:
            p = Path(generation.audio_path)
            if p.exists() and p.is_file():
                try:
                    p.unlink()
                    generation_files_deleted += 1
                except OSError:
                    pass
        db.delete(generation)

    persona_dir = PERSONA_DIR / str(persona.id)
    persona_assets_deleted = False
    if persona_dir.exists() and persona_dir.is_dir():
        try:
            shutil.rmtree(persona_dir)
            persona_assets_deleted = True
        except OSError:
            persona_assets_deleted = False

    db.delete(persona)
    db.commit()
    return DeletePersonaOut(deleted=True, generation_files_deleted=generation_files_deleted, persona_assets_deleted=persona_assets_deleted)


@app.post('/api/personas/{persona_id}/retrain', response_model=PersonaCreateResponse)
async def retrain_persona(
    persona_id: int,
    source_type: str = Form(...),
    youtube_url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> PersonaCreateResponse:
    persona = get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    source_ref, upload_path = await _resolve_training_source(source_type, youtube_url, file)
    persona.source_type = source_type
    persona.source_ref = source_ref
    persona.training_status = 'queued'
    persona.training_progress = 0.05
    persona.training_error = None
    persona.certification_status = 'pending'
    persona.certification_error = None
    db.add(persona)
    db.commit()
    db.refresh(persona)

    job = job_manager.create_job(
        db,
        'persona_ingest',
        {
            'persona_id': persona.id,
            'source_type': source_type,
            'source_ref': source_ref,
            'upload_path': upload_path,
        },
    )
    persona.training_job_id = job.id
    db.add(persona)
    db.commit()
    db.refresh(persona)
    job_manager.enqueue_ingest(job.id)
    return PersonaCreateResponse(persona=_persona_out(persona), job_id=job.id)


@app.post('/api/personas/{persona_id}/recertify', response_model=PersonaCreateResponse)
async def recertify_persona(persona_id: int, db: Session = Depends(get_db)) -> PersonaCreateResponse:
    persona = get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    if not persona.ref_audio_path:
        raise HTTPException(status_code=409, detail='Persona reference audio missing')
    persona.training_status = 'queued'
    persona.training_progress = 0.56
    persona.training_error = None
    persona.certification_status = 'pending'
    persona.certification_error = None
    db.add(persona)
    db.commit()
    db.refresh(persona)
    job = job_manager.create_job(db, 'persona_certify', {'persona_id': persona.id})
    persona.training_job_id = job.id
    db.add(persona)
    db.commit()
    db.refresh(persona)
    job_manager.enqueue_certification(job.id)
    return PersonaCreateResponse(persona=_persona_out(persona), job_id=job.id)


@app.get('/api/jobs/{job_id}', response_model=JobOut)
def job_by_id(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    return _job_out(job)


@app.post('/api/generate', response_model=GenerateResponse)
async def generate(payload: GenerateIn, db: Session = Depends(get_db)) -> GenerateResponse:
    if tts_service.startup_state != 'ready' or not tts_service.ready:
        detail = tts_service.startup_error or 'TTS models are still warming'
        raise HTTPException(status_code=503, detail=detail)
    persona = get_persona(db, payload.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    if persona.certification_status != 'certified':
        raise HTTPException(status_code=409, detail='Persona must be certified before generation')

    generation = Generation(
        persona_id=payload.persona_id,
        input_text=payload.text,
        processed_text=payload.text,
        style=payload.style,
        engine='chatterbox_full' if payload.render_mode == 'final' else 'chatterbox_turbo',
        render_mode=payload.render_mode,
        engine_requested=payload.model_id,
        engine_used=None,
        fallback_engine_used=None,
        segment_count=0,
        warning_codes_json='[]',
        certified_profile_version=persona.certified_profile_version,
        identity_score=None,
        retry_count=0,
        fallback_applied=0,
        applied_tags_json='[]',
        attempts_json='[]',
        audio_path=None,
        duration_sec=None,
        status='queued',
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)

    job = job_manager.create_job(
        db,
        'tts_generation',
        {
            'generation_id': generation.id,
            'persona_id': payload.persona_id,
            'model_id': payload.model_id,
            'style': payload.style,
            'speed': payload.speed,
            'render_mode': payload.render_mode,
        },
    )
    job_manager.enqueue_generation(job.id)
    return GenerateResponse(generation_id=generation.id, job_id=job.id)


@app.get('/api/generations/{generation_id}', response_model=GenerationOut)
def generation_by_id(generation_id: int, db: Session = Depends(get_db)) -> GenerationOut:
    generation = db.query(Generation).filter(Generation.id == generation_id).first()
    if not generation:
        raise HTTPException(status_code=404, detail='Generation not found')
    return _generation_out(generation)


@app.get('/api/generations', response_model=list[GenerationOut])
def list_generations(persona_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)) -> list[GenerationOut]:
    q = db.query(Generation).filter(Generation.status == 'completed')
    if persona_id is not None:
        q = q.filter(Generation.persona_id == persona_id)
    rows = q.order_by(Generation.created_at.desc()).limit(max(1, min(limit, 500))).all()
    return [_generation_out(row) for row in rows]


@app.delete('/api/generations/{generation_id}', response_model=DeleteGenerationOut)
def delete_generation(generation_id: int, db: Session = Depends(get_db)) -> DeleteGenerationOut:
    generation = db.query(Generation).filter(Generation.id == generation_id).first()
    if not generation:
        return DeleteGenerationOut(deleted=True, file_deleted=False)

    file_deleted = False
    if generation.audio_path:
        p = Path(generation.audio_path)
        if p.exists() and p.is_file():
            try:
                p.unlink()
                file_deleted = True
            except OSError:
                file_deleted = False

    db.delete(generation)
    db.commit()
    return DeleteGenerationOut(deleted=True, file_deleted=file_deleted)


async def _resolve_training_source(source_type: str, youtube_url: str | None, file: UploadFile | None) -> tuple[str, str | None]:
    if source_type not in {'upload', 'youtube'}:
        raise HTTPException(status_code=400, detail='source_type must be upload or youtube')
    if source_type == 'youtube':
        if not youtube_url or not youtube_url.strip():
            raise HTTPException(status_code=400, detail='youtube_url required for source_type=youtube')
        return youtube_url.strip(), None
    if file is None:
        raise HTTPException(status_code=400, detail='file required for source_type=upload')
    raw = await file.read()
    ext = Path(file.filename or 'sample.wav').suffix or '.wav'
    temp = save_upload_tmp(raw, ext)
    return (file.filename or temp.name), str(temp)


def _resolve_persona_name_or_400(db: Session, requested_name: str, exclude_persona_id: int | None = None) -> str:
    try:
        return resolve_unique_persona_name(db, requested_name, exclude_persona_id=exclude_persona_id)
    except PersonaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _cleanup_loop() -> None:
    while True:
        try:
            from .database import SessionLocal

            db = SessionLocal()
            try:
                prune_expired_generations(db, TTS_RETENTION_HOURS)
            finally:
                db.close()
        except Exception:
            pass
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


async def _job_watchdog_loop() -> None:
    interval = max(5.0, float(JOB_WATCHDOG_INTERVAL_SECONDS))
    while True:
        try:
            job_manager.recover_stale_running_jobs(stale_after_seconds=JOB_STALE_TIMEOUT_SECONDS, reason='worker_restarted_or_timeout')
        except Exception:
            pass
        await asyncio.sleep(interval)


async def _warm_tts_models() -> None:
    try:
        await asyncio.to_thread(tts_service.initialize_or_raise, DEFAULT_TTS_MODEL_FINAL)
    except Exception as exc:
        tts_service.ready = False
        tts_service.startup_state = 'failed'
        tts_service.startup_error = str(exc)


def _persona_out(persona: Persona) -> PersonaOut:
    training_quality = _load_json(persona.training_quality_json)
    certification_report = _load_json(persona.certification_report_json)
    render_profile = _load_json(persona.render_profile_json)
    anchor_candidates = _load_json_array(persona.anchor_candidates_json)
    return PersonaOut(
        id=persona.id,
        name=persona.name,
        source_type=persona.source_type,
        source_ref=persona.source_ref,
        ref_audio_path=_media_path(persona.ref_audio_path),
        anchor_audio_path=_media_path(persona.anchor_audio_path),
        conditioning_long_path=_media_path(persona.conditioning_long_path),
        speaker_embedding_path=persona.speaker_embedding_path,
        duration_sec=persona.duration_sec,
        transcript=persona.transcript,
        training_quality=training_quality,
        training_status=persona.training_status or 'idle',
        training_progress=persona.training_progress if persona.training_progress is not None else 0.0,
        training_job_id=persona.training_job_id,
        training_error=persona.training_error,
        training_audio_seconds=persona.training_audio_seconds,
        training_source_duration_seconds=persona.training_source_duration_seconds,
        certification_status=persona.certification_status or 'pending',
        certification_error=persona.certification_error,
        certification_report=certification_report,
        render_profile=render_profile,
        anchor_candidates=anchor_candidates,
        certified_profile_version=persona.certified_profile_version or 1,
        created_at=persona.created_at,
    )


def _job_out(job: Job) -> JobOut:
    result = _load_json(job.result_json)
    if isinstance(result, dict) and result.get('audio_path'):
        result['audio_path'] = _media_path(result['audio_path'])
    return JobOut(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        result_json=result if result else None,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _generation_out(generation: Generation) -> GenerationOut:
    applied_tags = _load_json_array(generation.applied_tags_json)
    attempts = _load_json_array(generation.attempts_json)
    warning_codes = [str(item) for item in _load_json_array(generation.warning_codes_json)]
    llm_enhance_ms = 0.0
    synthesis_ms = None
    total_generation_ms = None
    disfluency_edits: list[str] = []
    if attempts:
        synthesis_ms = round(sum(float(row.get('timing_ms', {}).get('synthesis_ms', 0.0)) for row in attempts if isinstance(row, dict)), 2)
        disfluency_edits = [str(edit) for row in attempts if isinstance(row, dict) for edit in row.get('disfluency_edits', [])]
        total_generation_ms = synthesis_ms
    input_chars = len(generation.input_text or '')
    enhanced_chars = len(generation.processed_text or '')
    growth_ratio = round(enhanced_chars / max(1, input_chars), 3)
    quality_state = _compute_quality_state(generation.status, warning_codes)
    quality_warnings = warning_codes.copy()
    if generation.identity_score is not None and generation.identity_score < 0.5:
        quality_warnings.append(f'Advisory identity drift: {generation.identity_score:.3f}')
    return GenerationOut(
        id=generation.id,
        persona_id=generation.persona_id,
        input_text=generation.input_text,
        processed_text=generation.processed_text,
        style=generation.style or 'natural',
        engine=generation.engine or 'chatterbox_full',
        render_mode=generation.render_mode or 'final',
        engine_requested=generation.engine_requested,
        engine_used=generation.engine_used,
        fallback_engine_used=generation.fallback_engine_used,
        segment_count=generation.segment_count or 0,
        warning_codes=warning_codes,
        certified_profile_version=generation.certified_profile_version,
        identity_score=generation.identity_score,
        retry_count=generation.retry_count or 0,
        fallback_applied=bool(generation.fallback_applied),
        applied_tags=applied_tags,
        attempts=attempts,
        quality_state=quality_state,
        quality_warnings=quality_warnings,
        llm_enhance_ms=llm_enhance_ms,
        synthesis_ms=synthesis_ms,
        identity_score_ms=0.0,
        total_generation_ms=total_generation_ms,
        reasoner_timeout_triggered=False,
        stage_timeout_triggered=False,
        input_chars=input_chars,
        enhanced_chars=enhanced_chars,
        growth_ratio=growth_ratio,
        disfluency_edits=disfluency_edits,
        audio_path=_media_path(generation.audio_path),
        duration_sec=generation.duration_sec,
        status=generation.status,
        created_at=generation.created_at,
    )


def _compute_quality_state(status: str, warning_codes: list[str] | float | int | None) -> str:
    if status != 'completed':
        return 'hard_fail'
    if isinstance(warning_codes, (int, float)):
        score = float(warning_codes)
        if score >= IDENTITY_STRICT_PASS_THRESHOLD:
            return 'pass'
        if score >= IDENTITY_HARD_FAIL_FLOOR:
            return 'warning'
        return 'hard_fail'
    return 'warning' if warning_codes else 'pass'


def _media_path(raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    p = Path(raw_path)
    if not p.exists():
        return None
    return f"/media/{p.relative_to(DATA_DIR)}"


def _load_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _load_json_array(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []
