from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / 'data'
PERSONA_DIR = DATA_DIR / 'personas'
JOBS_DIR = DATA_DIR / 'jobs'
OUTPUT_DIR = DATA_DIR / 'outputs'

DATABASE_URL = os.getenv('OMNIVIOUS_DATABASE_URL', f"sqlite:///{(DATA_DIR / 'omnivious.db').as_posix()}")
API_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'OMNIVIOUS_CORS_ORIGINS',
        'http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001',
    ).split(',')
    if origin.strip()
]

DEFAULT_TTS_MODEL_PREVIEW = os.getenv('OMNIVIOUS_TTS_MODEL_PREVIEW', 'mlx-community/chatterbox-turbo-fp16')
DEFAULT_TTS_MODEL_FINAL = os.getenv('OMNIVIOUS_TTS_MODEL_FINAL', 'mlx-community/chatterbox-fp16')
DEFAULT_TTS_MODEL = DEFAULT_TTS_MODEL_FINAL
MODEL_ALIAS = {
    'mlx-community/chatterbox-turbo': DEFAULT_TTS_MODEL_PREVIEW,
    'mlx-community/chatterbox-turbo-fp16': DEFAULT_TTS_MODEL_PREVIEW,
    'mlx-community/chatterbox': DEFAULT_TTS_MODEL_FINAL,
    'mlx-community/chatterbox-fp16': DEFAULT_TTS_MODEL_FINAL,
    DEFAULT_TTS_MODEL_PREVIEW: DEFAULT_TTS_MODEL_PREVIEW,
    DEFAULT_TTS_MODEL_FINAL: DEFAULT_TTS_MODEL_FINAL,
    # Legacy aliases preserved so stale clients continue to route to the preview engine.
    'mlx-community/Qwen3-TTS-0.6B-8bit': DEFAULT_TTS_MODEL_PREVIEW,
    'mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit': DEFAULT_TTS_MODEL_PREVIEW,
    'mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16': DEFAULT_TTS_MODEL_PREVIEW,
}

MAX_TRAIN_SECONDS = int(os.getenv('OMNIVIOUS_MAX_TRAIN_SECONDS', '300'))
MIN_TRAIN_SECONDS = int(os.getenv('OMNIVIOUS_MIN_TRAIN_SECONDS', '10'))
AUDIO_SAMPLE_RATE = int(os.getenv('OMNIVIOUS_AUDIO_SAMPLE_RATE', '24000'))
CLONE_CONDITION_TARGET_SECONDS = float(os.getenv('OMNIVIOUS_CLONE_CONDITION_TARGET_SECONDS', '45'))
CLONE_CONDITION_MIN_SECONDS = float(os.getenv('OMNIVIOUS_CLONE_CONDITION_MIN_SECONDS', '20'))
CLONE_CONDITION_MAX_SECONDS = float(os.getenv('OMNIVIOUS_CLONE_CONDITION_MAX_SECONDS', '60'))
ANCHOR_MIN_SECONDS = float(os.getenv('OMNIVIOUS_ANCHOR_MIN_SECONDS', '8'))
ANCHOR_MAX_SECONDS = float(os.getenv('OMNIVIOUS_ANCHOR_MAX_SECONDS', '15'))
CERTIFICATION_MAX_ANCHORS = int(os.getenv('OMNIVIOUS_CERTIFICATION_MAX_ANCHORS', '4'))
CERTIFICATION_REQUIRED_SIMILARITY = float(os.getenv('OMNIVIOUS_CERTIFICATION_REQUIRED_SIMILARITY', '0.58'))
CERTIFICATION_MIN_OPERATIONAL_RATIO = float(os.getenv('OMNIVIOUS_CERTIFICATION_MIN_OPERATIONAL_RATIO', '0.75'))
STT_MODEL_ID = os.getenv('OMNIVIOUS_STT_MODEL_ID', 'mlx-community/Qwen3-ASR-1.7B-8bit')

# Compatibility thresholds kept for old tests and UI code.
IDENTITY_STRICT_PASS_THRESHOLD = float(os.getenv('OMNIVIOUS_IDENTITY_STRICT_PASS_THRESHOLD', '0.70'))
IDENTITY_WARNING_FLOOR = float(os.getenv('OMNIVIOUS_IDENTITY_WARNING_FLOOR', '0.50'))
IDENTITY_HARD_FAIL_FLOOR = float(os.getenv('OMNIVIOUS_IDENTITY_HARD_FAIL_FLOOR', '0.35'))

TTS_RETENTION_HOURS = int(os.getenv('OMNIVIOUS_TTS_RETENTION_HOURS', '24'))
CLEANUP_INTERVAL_SECONDS = int(os.getenv('OMNIVIOUS_CLEANUP_INTERVAL_SECONDS', '1800'))
JOB_STALE_TIMEOUT_SECONDS = float(os.getenv('OMNIVIOUS_JOB_STALE_TIMEOUT_SECONDS', '600'))
JOB_WATCHDOG_INTERVAL_SECONDS = float(os.getenv('OMNIVIOUS_JOB_WATCHDOG_INTERVAL_SECONDS', '60'))
SYNTH_TIMEOUT_SECONDS = float(os.getenv('OMNIVIOUS_SYNTH_TIMEOUT_SECONDS', '90'))
CERTIFICATION_SYNTH_TIMEOUT_SECONDS = float(os.getenv('OMNIVIOUS_CERTIFICATION_SYNTH_TIMEOUT_SECONDS', '45'))

SEGMENT_TARGET_CHARS = int(os.getenv('OMNIVIOUS_SEGMENT_TARGET_CHARS', '170'))
SEGMENT_MAX_CHARS = int(os.getenv('OMNIVIOUS_SEGMENT_MAX_CHARS', '260'))
SEGMENT_CROSSFADE_MS = int(os.getenv('OMNIVIOUS_SEGMENT_CROSSFADE_MS', '26'))
SEGMENT_BASE_PAUSE_MS = int(os.getenv('OMNIVIOUS_SEGMENT_BASE_PAUSE_MS', '120'))
PREVIEW_RENDER_MAX_TOKENS = int(os.getenv('OMNIVIOUS_PREVIEW_RENDER_MAX_TOKENS', '520'))
FINAL_RENDER_MAX_TOKENS = int(os.getenv('OMNIVIOUS_FINAL_RENDER_MAX_TOKENS', '880'))

REASONER_MODE = os.getenv('OMNIVIOUS_REASONER_MODE', 'single_pass').strip().lower()
REASONER_DISFLUENCY_LEVEL = os.getenv('OMNIVIOUS_REASONER_DISFLUENCY_LEVEL', 'moderate').strip().lower()
MLX_REASONING_MODEL = os.getenv('OMNIVIOUS_MLX_REASONING_MODEL', 'Qwen/Qwen3-4B-MLX-8bit')

TAG_MAX_PER_SENTENCE = int(os.getenv('OMNIVIOUS_TAG_MAX_PER_SENTENCE', '1'))
TAG_MAX_TOTAL = int(os.getenv('OMNIVIOUS_TAG_MAX_TOTAL', '8'))
LLM_EDIT_BUDGET_RATIO = float(os.getenv('OMNIVIOUS_LLM_EDIT_BUDGET_RATIO', '0.12'))
LLM_OUTPUT_GROWTH_CAP_RATIO = float(os.getenv('OMNIVIOUS_LLM_OUTPUT_GROWTH_CAP_RATIO', '1.15'))
REASONER_TEMPERATURE = float(os.getenv('OMNIVIOUS_REASONER_TEMPERATURE', '0.05'))
REASONER_TOP_P = float(os.getenv('OMNIVIOUS_REASONER_TOP_P', '0.6'))
REASONER_MAX_TOKENS_SHORT = int(os.getenv('OMNIVIOUS_REASONER_MAX_TOKENS_SHORT', '96'))
REASONER_MAX_TOKENS_MEDIUM = int(os.getenv('OMNIVIOUS_REASONER_MAX_TOKENS_MEDIUM', '144'))
REASONER_MAX_TOKENS_LONG = int(os.getenv('OMNIVIOUS_REASONER_MAX_TOKENS_LONG', '192'))
REASONER_MAX_TOKENS_XLONG = int(os.getenv('OMNIVIOUS_REASONER_MAX_TOKENS_XLONG', '256'))


def validate_certification_thresholds() -> None:
    if not (0.0 <= CERTIFICATION_REQUIRED_SIMILARITY <= 1.0):
        raise ValueError('OMNIVIOUS_CERTIFICATION_REQUIRED_SIMILARITY must be between 0 and 1')
    if not (0.0 <= CERTIFICATION_MIN_OPERATIONAL_RATIO <= 1.0):
        raise ValueError('OMNIVIOUS_CERTIFICATION_MIN_OPERATIONAL_RATIO must be between 0 and 1')
    if CLONE_CONDITION_MIN_SECONDS > CLONE_CONDITION_TARGET_SECONDS:
        raise ValueError('Clone conditioning min seconds must be <= target seconds')
    if CLONE_CONDITION_TARGET_SECONDS > CLONE_CONDITION_MAX_SECONDS:
        raise ValueError('Clone conditioning target seconds must be <= max seconds')
    if ANCHOR_MIN_SECONDS > ANCHOR_MAX_SECONDS:
        raise ValueError('Anchor min seconds must be <= anchor max seconds')
    if not (0.0 <= IDENTITY_HARD_FAIL_FLOOR <= IDENTITY_WARNING_FLOOR < IDENTITY_STRICT_PASS_THRESHOLD <= 1.0):
        raise ValueError('Identity compatibility thresholds must satisfy hard_fail <= warning < strict_pass <= 1')


def validate_identity_thresholds() -> None:
    if not (0.0 <= IDENTITY_HARD_FAIL_FLOOR <= IDENTITY_WARNING_FLOOR < IDENTITY_STRICT_PASS_THRESHOLD <= 1.0):
        raise ValueError('Identity compatibility thresholds must satisfy hard_fail <= warning < strict_pass <= 1')
