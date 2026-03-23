from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from statistics import mean

import librosa
import numpy as np
import soundfile as sf
from sqlalchemy.orm import Session

from .config import (
    ANCHOR_MAX_SECONDS,
    ANCHOR_MIN_SECONDS,
    AUDIO_SAMPLE_RATE,
    CERTIFICATION_MAX_ANCHORS,
    CERTIFICATION_MIN_OPERATIONAL_RATIO,
    CERTIFICATION_REQUIRED_SIMILARITY,
    CERTIFICATION_SYNTH_TIMEOUT_SECONDS,
    CLONE_CONDITION_MAX_SECONDS,
    CLONE_CONDITION_MIN_SECONDS,
    CLONE_CONDITION_TARGET_SECONDS,
    DEFAULT_TTS_MODEL_FINAL,
    DEFAULT_TTS_MODEL_PREVIEW,
    MAX_TRAIN_SECONDS,
    PERSONA_DIR,
)
from .ingest import cleanup_tmp, download_youtube_audio, normalize_and_trim, probe_duration
from .models import Persona
from .speaker_identity import identity_scorer
from .style_compiler import compile_style_text
from .tts_service import TTSError, tts_service


class PersonaError(Exception):
    pass


CERTIFICATION_PROMPTS = [
    ('natural', 'The weather is calm now. Stay with me and speak clearly.'),
    ('news', 'Tonight, we deliver a direct statement with confidence and control.'),
    ('drama_movie', 'No. Listen to me. This changes everything, and it changes now.'),
]


def resolve_unique_persona_name(db: Session, requested_name: str, exclude_persona_id: int | None = None) -> str:
    base = requested_name.strip()
    if not base:
        raise PersonaError('Persona name is required')

    if _name_available(db, base, exclude_persona_id):
        return base

    version = 2
    while True:
        candidate = f'{base} v{version}'
        if _name_available(db, candidate, exclude_persona_id):
            return candidate
        version += 1


def _name_available(db: Session, name: str, exclude_persona_id: int | None) -> bool:
    q = db.query(Persona).filter(Persona.name == name)
    if exclude_persona_id is not None:
        q = q.filter(Persona.id != exclude_persona_id)
    return q.first() is None


def ingest_persona_audio(
    persona: Persona,
    source_type: str,
    source_ref: str,
    upload_path: str | None,
    db: Session,
    on_progress: Callable[[float], None] | None = None,
) -> Persona:
    tmp_path: Path | None = None
    try:
        if on_progress:
            on_progress(0.18)
        if source_type == 'youtube':
            tmp_path = download_youtube_audio(source_ref)
        elif source_type == 'upload':
            if not upload_path:
                raise PersonaError('Missing upload file path')
            tmp_path = Path(upload_path)
        else:
            raise PersonaError(f'Unsupported source_type: {source_type}')

        source_duration = probe_duration(tmp_path)
        consumed_duration = min(source_duration, float(MAX_TRAIN_SECONDS))

        persona_dir = PERSONA_DIR / str(persona.id)
        persona_dir.mkdir(parents=True, exist_ok=True)
        full_path = persona_dir / 'reference_full.wav'

        if on_progress:
            on_progress(0.42)
        duration = normalize_and_trim(tmp_path, full_path)

        persona.source_type = source_type
        persona.source_ref = source_ref
        persona.ref_audio_path = str(full_path)
        persona.duration_sec = duration
        persona.training_audio_seconds = consumed_duration
        persona.training_source_duration_seconds = source_duration
        db.add(persona)
        db.commit()
        db.refresh(persona)

        certified = certify_existing_persona(persona, db, on_progress=on_progress, full_audio_path=full_path)
        certified.duration_sec = duration
        certified.training_audio_seconds = consumed_duration
        certified.training_source_duration_seconds = source_duration
        db.add(certified)
        db.commit()
        db.refresh(certified)
        return certified
    finally:
        if source_type == 'youtube':
            cleanup_tmp(tmp_path)
        elif source_type == 'upload' and tmp_path and tmp_path.exists():
            _safe_unlink(tmp_path)


def certify_existing_persona(
    persona: Persona,
    db: Session,
    on_progress: Callable[[float], None] | None = None,
    *,
    full_audio_path: Path | None = None,
) -> Persona:
    full_path = Path(full_audio_path or persona.ref_audio_path or '')
    if not full_path.exists():
        raise PersonaError('Reference audio missing; cannot certify persona')

    persona_dir = PERSONA_DIR / str(persona.id)
    persona_dir.mkdir(parents=True, exist_ok=True)
    conditioning_path = persona_dir / 'conditioning_long.wav'

    if on_progress:
        on_progress(0.58)
    quality = _analyze_audio_quality(full_path)
    conditioning_seconds = _build_conditioning_clip(full_path, conditioning_path)
    anchors = _extract_anchor_candidates(full_path, persona_dir)
    if not anchors:
        raise PersonaError('Could not extract a stable speech anchor from the training audio')

    if on_progress:
        on_progress(0.72)
    selected_anchor = anchors[0]
    selected_anchor_path = Path(selected_anchor['path'])
    reference_embedding = identity_scorer.embedding_from_audio_path(selected_anchor_path)
    embedding_path = persona_dir / 'speaker_embedding.npy'
    identity_scorer.save_embedding(reference_embedding, embedding_path)

    if on_progress:
        on_progress(0.86)
    certification = _run_certification_suite(
        conditioning_path=conditioning_path,
        reference_embedding=reference_embedding,
        timeout_seconds=CERTIFICATION_SYNTH_TIMEOUT_SECONDS,
    )

    transcript = persona.transcript
    certification_status = 'certified'
    certification_error = None
    if certification['avg_similarity'] < CERTIFICATION_REQUIRED_SIMILARITY:
        certification_status = 'rejected'
        certification_error = (
            f"Certification similarity {certification['avg_similarity']:.3f} below required "
            f"{CERTIFICATION_REQUIRED_SIMILARITY:.2f}. Retrain with cleaner single-speaker audio."
        )
    elif certification['operational_ratio'] < CERTIFICATION_MIN_OPERATIONAL_RATIO:
        certification_status = 'rejected'
        certification_error = (
            f"Certification render success ratio {certification['operational_ratio']:.2f} below required "
            f"{CERTIFICATION_MIN_OPERATIONAL_RATIO:.2f}. Retrain with cleaner reference audio."
        )

    quality.update({'conditioning_seconds': round(conditioning_seconds, 3)})
    persona.anchor_audio_path = str(selected_anchor_path)
    persona.conditioning_long_path = str(conditioning_path)
    persona.speaker_embedding_path = str(embedding_path)
    persona.training_quality_json = json.dumps(quality)
    persona.transcript = transcript
    persona.anchor_candidates_json = json.dumps(anchors)
    persona.render_profile_json = json.dumps(
        {
            'profile_version': int(persona.certified_profile_version or 1) + (1 if certification_status == 'certified' else 0),
            'conditioning_seconds': round(conditioning_seconds, 3),
            'preview_model': DEFAULT_TTS_MODEL_PREVIEW,
            'final_model': DEFAULT_TTS_MODEL_FINAL,
            'preferred_anchor': str(selected_anchor_path),
            'style_defaults': {
                'natural': {'style_strength': 0.92},
                'news': {'style_strength': 0.88},
                'sad': {'style_strength': 1.05},
                'happy': {'style_strength': 1.04},
                'drama_movie': {'style_strength': 1.12},
                'charming_attractive': {'style_strength': 1.0},
            },
        }
    )
    persona.certification_report_json = json.dumps(
        {
            'quality': quality,
            'conditioning_seconds': round(conditioning_seconds, 3),
            'anchors_considered': anchors,
            'selected_anchor': str(selected_anchor_path),
            'certification': certification,
            'stt_available': False,
        }
    )
    persona.certification_status = certification_status
    persona.certification_error = certification_error
    if certification_status == 'certified':
        persona.certified_profile_version = int(persona.certified_profile_version or 0) + 1
    db.add(persona)
    db.commit()
    db.refresh(persona)

    if certification_status != 'certified':
        raise PersonaError(certification_error or 'Persona certification failed')
    return persona


def _run_certification_suite(
    *,
    conditioning_path: Path,
    reference_embedding: np.ndarray,
    timeout_seconds: float,
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    similarities: list[float] = []
    operational_successes = 0
    total = 0
    with tempfile.TemporaryDirectory(prefix='omnivious_cert_') as temp_dir:
        temp_root = Path(temp_dir)
        for model_id in (DEFAULT_TTS_MODEL_PREVIEW, DEFAULT_TTS_MODEL_FINAL):
            for style, prompt in CERTIFICATION_PROMPTS[:2 if model_id == DEFAULT_TTS_MODEL_FINAL else 3]:
                total += 1
                out_path = temp_root / f'{Path(model_id).name}_{style}_{total}.wav'
                compile_result = compile_style_text(
                    prompt,
                    style,
                    render_mode='preview' if model_id == DEFAULT_TTS_MODEL_PREVIEW else 'final',
                )
                try:
                    duration, engine_name = tts_service.synthesize(
                        text=compile_result.styled_text,
                        ref_audio_path=str(conditioning_path),
                        output_path=out_path,
                        requested_model_id=model_id,
                        speed=1.0,
                        generation_options=compile_result.generation_params,
                    )
                    score = identity_scorer.similarity(reference_embedding, out_path).score
                    audio_quality = identity_scorer.speech_quality(out_path)
                    operational_successes += 1
                    similarities.append(score)
                    results.append(
                        {
                            'model_id': model_id,
                            'engine': engine_name,
                            'style': style,
                            'duration_sec': round(duration, 3),
                            'similarity': round(score, 4),
                            'speech_ratio': audio_quality['speech_ratio'],
                            'clipping_ratio': audio_quality['clipping_ratio'],
                            'status': 'ok',
                        }
                    )
                except TTSError as exc:
                    results.append(
                        {
                            'model_id': model_id,
                            'style': style,
                            'status': 'error',
                            'error': str(exc),
                        }
                    )
    operational_ratio = operational_successes / max(total, 1)
    return {
        'results': results,
        'avg_similarity': round(mean(similarities), 4) if similarities else 0.0,
        'max_similarity': round(max(similarities), 4) if similarities else 0.0,
        'operational_ratio': round(operational_ratio, 4),
    }


def _build_conditioning_clip(full_path: Path, out_path: Path) -> float:
    wav, sr = sf.read(str(full_path), always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    wav = wav.astype(np.float32)
    if wav.size == 0:
        raise PersonaError('Training source audio is empty after normalization')

    segments = _speech_segments(wav, sr, min_sec=2.5)
    if not segments:
        clip = _crop_center(wav, sr, CLONE_CONDITION_TARGET_SECONDS)
        sf.write(str(out_path), clip, sr)
        return float(clip.shape[0] / sr)

    target_samples = int(sr * max(CLONE_CONDITION_MIN_SECONDS, min(CLONE_CONDITION_TARGET_SECONDS, CLONE_CONDITION_MAX_SECONDS)))
    chunks: list[np.ndarray] = []
    collected = 0
    for start_s, end_s, _score in segments:
        part = wav[int(start_s * sr) : int(end_s * sr)]
        remaining = target_samples - collected
        if remaining <= 0:
            break
        piece = part[:remaining]
        chunks.append(piece)
        collected += piece.shape[0]
    if not chunks:
        clip = _crop_center(wav, sr, CLONE_CONDITION_TARGET_SECONDS)
    else:
        clip = np.concatenate(chunks)
    sf.write(str(out_path), clip.astype(np.float32), sr)
    return float(clip.shape[0] / sr)


def _extract_anchor_candidates(full_path: Path, persona_dir: Path) -> list[dict[str, object]]:
    wav, sr = sf.read(str(full_path), always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    wav = wav.astype(np.float32)
    segments = _speech_segments(wav, sr, min_sec=ANCHOR_MIN_SECONDS)
    candidates: list[dict[str, object]] = []
    for index, (start_s, end_s, score) in enumerate(segments[: CERTIFICATION_MAX_ANCHORS * 2]):
        s = int(start_s * sr)
        e = int(end_s * sr)
        clip = wav[s:e]
        max_samples = int(sr * ANCHOR_MAX_SECONDS)
        if clip.shape[0] > max_samples:
            clip = clip[:max_samples]
        if clip.shape[0] < int(sr * ANCHOR_MIN_SECONDS):
            continue
        path = persona_dir / f'anchor_short_{index + 1}.wav'
        sf.write(str(path), clip.astype(np.float32), sr)
        candidates.append(
            {
                'path': str(path),
                'duration_sec': round(float(clip.shape[0] / sr), 3),
                'score': round(float(score), 4),
            }
        )
    candidates.sort(key=lambda item: float(item['score']), reverse=True)
    trimmed = candidates[:CERTIFICATION_MAX_ANCHORS]
    if trimmed:
        return trimmed

    # Fallback for legacy/reference clips that do not survive the VAD threshold cleanly.
    fallback_duration = min(max(ANCHOR_MIN_SECONDS, 10.0), ANCHOR_MAX_SECONDS)
    fallback_clip = _crop_center(wav, sr, fallback_duration)
    fallback_path = persona_dir / 'anchor_short_fallback.wav'
    sf.write(str(fallback_path), fallback_clip.astype(np.float32), sr)
    return [
        {
            'path': str(fallback_path),
            'duration_sec': round(float(fallback_clip.shape[0] / sr), 3),
            'score': 0.0,
            'fallback': True,
        }
    ]


def _speech_segments(wav: np.ndarray, sr: int, min_sec: float) -> list[tuple[float, float, float]]:
    frame_len = int(sr * 0.032)
    hop_len = int(sr * 0.016)
    rms = librosa.feature.rms(y=wav, frame_length=frame_len, hop_length=hop_len)[0]
    max_rms = float(np.max(rms) + 1e-9)
    speech_mask = rms > (max_rms * 0.12)
    ranges: list[tuple[float, float, float]] = []
    start = None
    for idx, flag in enumerate(speech_mask.tolist()):
        if flag and start is None:
            start = idx
        if not flag and start is not None:
            end = idx
            s = (start * hop_len) / sr
            e = (end * hop_len) / sr
            duration = e - s
            if duration >= min_sec:
                clip = wav[int(s * sr) : int(e * sr)]
                clip_db = float(20 * np.log10(np.sqrt(np.mean(np.square(clip)) + 1e-9) + 1e-9))
                clipping_ratio = float(np.mean(np.abs(clip) > 0.98))
                score = (clip_db + 35.0) - (clipping_ratio * 8.0) - (abs(duration - CLONE_CONDITION_TARGET_SECONDS) * 0.05)
                ranges.append((s, e, score))
            start = None
    if start is not None:
        s = (start * hop_len) / sr
        e = (len(speech_mask) * hop_len) / sr
        duration = e - s
        if duration >= min_sec:
            clip = wav[int(s * sr) : int(e * sr)]
            clip_db = float(20 * np.log10(np.sqrt(np.mean(np.square(clip)) + 1e-9) + 1e-9))
            clipping_ratio = float(np.mean(np.abs(clip) > 0.98))
            score = (clip_db + 35.0) - (clipping_ratio * 8.0) - (abs(duration - CLONE_CONDITION_TARGET_SECONDS) * 0.05)
            ranges.append((s, e, score))
    ranges.sort(key=lambda item: item[2], reverse=True)
    return ranges


def _crop_center(wav: np.ndarray, sr: int, sec: float) -> np.ndarray:
    length = int(sr * sec)
    if wav.shape[0] <= length:
        return wav
    start = max(0, (wav.shape[0] - length) // 2)
    return wav[start : start + length]


def _analyze_audio_quality(path: Path) -> dict[str, float | int]:
    wav, sr = sf.read(str(path), always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    wav = wav.astype(np.float32)
    duration = float(wav.shape[0] / max(sr, 1))
    if wav.size == 0:
        return {'duration_sec': duration, 'speech_ratio': 0.0, 'clipping_ratio': 1.0, 'rms_db': -120.0}
    quality = identity_scorer.speech_quality(path)
    quality.update({'duration_sec': round(duration, 3), 'sample_rate': int(sr)})
    return quality


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def list_personas(db: Session) -> list[Persona]:
    return db.query(Persona).order_by(Persona.created_at.desc()).all()


def get_persona(db: Session, persona_id: int) -> Persona | None:
    return db.query(Persona).filter(Persona.id == persona_id).first()
