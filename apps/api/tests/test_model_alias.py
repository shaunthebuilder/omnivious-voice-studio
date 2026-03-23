from app.config import DEFAULT_TTS_MODEL_PREVIEW, MODEL_ALIAS


def test_alias_resolution_exists():
    assert MODEL_ALIAS['mlx-community/chatterbox-turbo'] == DEFAULT_TTS_MODEL_PREVIEW
    assert MODEL_ALIAS['mlx-community/Qwen3-TTS-0.6B-8bit'] == DEFAULT_TTS_MODEL_PREVIEW
    assert MODEL_ALIAS['mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit'] == DEFAULT_TTS_MODEL_PREVIEW
