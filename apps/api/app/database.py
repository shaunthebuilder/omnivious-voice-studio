from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_startup_migrations() -> None:
    if not DATABASE_URL.startswith('sqlite'):
        return

    expected_persona_columns = {
        'training_status': "TEXT DEFAULT 'idle'",
        'training_progress': 'REAL DEFAULT 0.0',
        'training_job_id': 'INTEGER',
        'training_error': 'TEXT',
        'training_audio_seconds': 'REAL',
        'training_source_duration_seconds': 'REAL',
        'anchor_audio_path': 'TEXT',
        'conditioning_long_path': 'TEXT',
        'speaker_embedding_path': 'TEXT',
        'training_quality_json': 'TEXT',
        'certification_status': "TEXT DEFAULT 'pending'",
        'certification_error': 'TEXT',
        'certification_report_json': 'TEXT',
        'render_profile_json': 'TEXT',
        'anchor_candidates_json': 'TEXT',
        'certified_profile_version': 'INTEGER DEFAULT 1',
    }
    expected_generation_columns = {
        'style': "TEXT DEFAULT 'natural'",
        'engine': "TEXT DEFAULT 'chatterbox_full'",
        'render_mode': "TEXT DEFAULT 'final'",
        'engine_requested': 'TEXT',
        'engine_used': 'TEXT',
        'fallback_engine_used': 'TEXT',
        'segment_count': 'INTEGER DEFAULT 0',
        'warning_codes_json': 'TEXT',
        'certified_profile_version': 'INTEGER',
        'identity_score': 'REAL',
        'retry_count': 'INTEGER DEFAULT 0',
        'fallback_applied': 'INTEGER DEFAULT 0',
        'applied_tags_json': 'TEXT',
        'attempts_json': 'TEXT',
    }

    with engine.begin() as conn:
        persona_rows = conn.exec_driver_sql('PRAGMA table_info(personas)').fetchall()
        persona_existing = {row[1] for row in persona_rows}
        for column, ddl in expected_persona_columns.items():
            if column not in persona_existing:
                conn.exec_driver_sql(f'ALTER TABLE personas ADD COLUMN {column} {ddl}')

        generation_rows = conn.exec_driver_sql('PRAGMA table_info(generations)').fetchall()
        generation_existing = {row[1] for row in generation_rows}
        for column, ddl in expected_generation_columns.items():
            if column not in generation_existing:
                conn.exec_driver_sql(f'ALTER TABLE generations ADD COLUMN {column} {ddl}')

        conn.exec_driver_sql("UPDATE personas SET training_status = 'idle' WHERE training_status IS NULL")
        conn.exec_driver_sql("UPDATE personas SET training_progress = 0.0 WHERE training_progress IS NULL")
        conn.exec_driver_sql("UPDATE personas SET certified_profile_version = 1 WHERE certified_profile_version IS NULL")
        conn.exec_driver_sql(
            "UPDATE personas SET certification_status = 'uncertified_legacy' "
            "WHERE certification_status IS NULL OR certification_status = ''"
        )
        conn.exec_driver_sql(
            "UPDATE personas SET certification_status = 'uncertified_legacy' "
            "WHERE certification_status = 'pending' AND ref_audio_path IS NOT NULL AND training_status = 'completed'"
        )
        conn.exec_driver_sql("UPDATE generations SET style = 'natural' WHERE style IS NULL")
        conn.exec_driver_sql("UPDATE generations SET engine = 'chatterbox_full' WHERE engine IS NULL")
        conn.exec_driver_sql("UPDATE generations SET render_mode = 'final' WHERE render_mode IS NULL")
        conn.exec_driver_sql("UPDATE generations SET retry_count = 0 WHERE retry_count IS NULL")
        conn.exec_driver_sql("UPDATE generations SET fallback_applied = 0 WHERE fallback_applied IS NULL")
        conn.exec_driver_sql("UPDATE generations SET segment_count = 0 WHERE segment_count IS NULL")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
