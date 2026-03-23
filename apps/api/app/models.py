from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Persona(Base):
    __tablename__ = 'personas'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditioning_long_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_embedding_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_quality_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_status: Mapped[str] = mapped_column(String(20), nullable=False, default='idle')
    training_progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    training_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    training_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_audio_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_source_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    certification_status: Mapped[str] = mapped_column(String(24), nullable=False, default='pending')
    certification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    certification_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_candidates_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    certified_profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    generations = relationship('Generation', back_populates='persona')


class Job(Base):
    __tablename__ = 'jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='queued', nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Generation(Base):
    __tablename__ = 'generations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    persona_id: Mapped[int] = mapped_column(Integer, ForeignKey('personas.id'), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    processed_text: Mapped[str] = mapped_column(Text, nullable=False)
    style: Mapped[str] = mapped_column(String(40), nullable=False, default='natural')
    engine: Mapped[str] = mapped_column(String(40), nullable=False, default='chatterbox_full')
    render_mode: Mapped[str] = mapped_column(String(20), nullable=False, default='final')
    engine_requested: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fallback_engine_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_codes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    certified_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    identity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied_tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='queued', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    persona = relationship('Persona', back_populates='generations')
