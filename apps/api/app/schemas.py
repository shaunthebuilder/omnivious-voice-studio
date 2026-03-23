from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CertificationStatus = Literal['pending', 'certifying', 'certified', 'rejected', 'uncertified_legacy']
StyleLiteral = Literal['natural', 'news', 'drama_movie', 'sad', 'happy', 'charming_attractive']
RenderModeLiteral = Literal['preview', 'final']
LegacyStyleLiteral = Literal['natural', 'cinematic', 'podcast', 'storytelling', 'news', 'dramatic']


class PersonaOut(BaseModel):
    id: int
    name: str
    source_type: str
    source_ref: str | None = None
    ref_audio_path: str | None = None
    anchor_audio_path: str | None = None
    conditioning_long_path: str | None = None
    speaker_embedding_path: str | None = None
    duration_sec: float | None = None
    transcript: str | None = None
    training_quality: dict | None = None
    training_status: str
    training_progress: float
    training_job_id: int | None = None
    training_error: str | None = None
    training_audio_seconds: float | None = None
    training_source_duration_seconds: float | None = None
    certification_status: CertificationStatus
    certification_error: str | None = None
    certification_report: dict | None = None
    render_profile: dict | None = None
    anchor_candidates: list[dict] = Field(default_factory=list)
    certified_profile_version: int = 1
    created_at: datetime


class JobOut(BaseModel):
    id: int
    job_type: str
    status: str
    progress: float
    result_json: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class PersonaCreateResponse(BaseModel):
    persona: PersonaOut
    job_id: int


class PersonaRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class GenerateIn(BaseModel):
    model_config = ConfigDict(extra='ignore')

    persona_id: int
    text: str = Field(min_length=1)
    style: StyleLiteral = 'natural'
    style_profile: LegacyStyleLiteral | None = None
    render_mode: RenderModeLiteral = 'final'
    speed: float = Field(default=1.0, ge=0.7, le=1.3)
    model_id: str | None = None

    @model_validator(mode='before')
    @classmethod
    def map_legacy_style_profile(cls, raw: object) -> object:
        if not isinstance(raw, dict):
            return raw
        if raw.get('style'):
            return raw
        legacy_style = raw.get('style_profile')
        if legacy_style is None:
            return raw
        mapping = {
            'natural': 'natural',
            'cinematic': 'drama_movie',
            'podcast': 'natural',
            'storytelling': 'drama_movie',
            'news': 'news',
            'dramatic': 'drama_movie',
        }
        raw['style'] = mapping.get(str(legacy_style).strip().lower(), 'natural')
        return raw


class GenerateResponse(BaseModel):
    generation_id: int
    job_id: int


class GenerationOut(BaseModel):
    id: int
    persona_id: int
    input_text: str
    processed_text: str
    style: str
    engine: str
    render_mode: RenderModeLiteral
    engine_requested: str | None = None
    engine_used: str | None = None
    fallback_engine_used: str | None = None
    segment_count: int = 0
    warning_codes: list[str] = Field(default_factory=list)
    certified_profile_version: int | None = None
    identity_score: float | None = None
    retry_count: int = 0
    fallback_applied: bool = False
    applied_tags: list[str] = Field(default_factory=list)
    attempts: list[dict] = Field(default_factory=list)
    quality_state: Literal['pass', 'warning', 'hard_fail'] = 'pass'
    quality_warnings: list[str] = Field(default_factory=list)
    llm_enhance_ms: float | None = None
    synthesis_ms: float | None = None
    identity_score_ms: float | None = None
    total_generation_ms: float | None = None
    reasoner_timeout_triggered: bool = False
    stage_timeout_triggered: bool = False
    input_chars: int | None = None
    enhanced_chars: int | None = None
    growth_ratio: float | None = None
    disfluency_edits: list[str] = Field(default_factory=list)
    audio_path: str | None
    duration_sec: float | None
    status: str
    created_at: datetime


class StyleOut(BaseModel):
    id: StyleLiteral
    label: str
    description: str
    uses_tags: bool
    supported_tags: list[str] = Field(default_factory=list)


class SpeechTagOut(BaseModel):
    tag: str
    description: str
    enabled: bool


class DeleteGenerationOut(BaseModel):
    deleted: bool
    file_deleted: bool


class DeletePersonaOut(BaseModel):
    deleted: bool
    generation_files_deleted: int
    persona_assets_deleted: bool


class HealthOut(BaseModel):
    status: str
    startup_state: Literal['booting', 'warming', 'ready', 'failed']
    startup_error: str | None = None
    model_ready: bool
    preview_ready: bool = False
    final_ready: bool = False
    preview_model_id: str
    final_model_id: str
    llm_ready: bool = False
    llm_model: str | None = None
