from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf

from app.tts_service import TTSService


class _FakeEngine:
    name = 'chatterbox_turbo'

    def __init__(self) -> None:
        self.model_id = None
        self.ready = False
        self.calls: list[dict] = []

    def initialize_or_raise(self, requested_model_id: str) -> str:
        self.model_id = requested_model_id
        self.ready = True
        return requested_model_id

    def synthesize_raw(self, **kwargs):
        self.calls.append(kwargs)
        wav = np.zeros(24000, dtype=np.float32)
        return wav, 24000


def test_tts_service_passes_generation_options_to_engine() -> None:
    service = TTSService()
    fake = _FakeEngine()
    service.engines['preview'] = fake
    service.engines['final'] = fake
    service.ready = True
    service.model_id = 'mlx-community/chatterbox-turbo-fp16'
    service._apply_speed_transform = lambda wav, _sr, _speed: wav  # type: ignore[method-assign]

    with TemporaryDirectory(prefix='omnivious_tts_test_') as temp_dir:
        ref = Path(temp_dir) / 'ref.wav'
        out = Path(temp_dir) / 'out.wav'
        sf.write(str(ref), np.zeros(24000 * 6, dtype=np.float32), 24000)

        service.synthesize(
            text='hello',
            ref_audio_path=str(ref),
            output_path=out,
            requested_model_id='mlx-community/chatterbox-turbo',
            speed=1.0,
            generation_options={'temperature': 0.81},
        )

        assert out.exists()
        assert fake.calls
        call = fake.calls[-1]
        assert call['text'] == 'hello'
        assert call['ref_audio_path'] == str(ref)
        assert call['generation_options']['temperature'] == 0.81


def test_tts_service_speed_transform_changes_duration() -> None:
    service = TTSService()
    wav = np.sin(np.linspace(0, 10 * np.pi, 24000, dtype=np.float32))
    faster = service._apply_speed_transform(wav, 24000, 1.2)
    slower = service._apply_speed_transform(wav, 24000, 0.8)
    assert faster.shape[0] < wav.shape[0]
    assert slower.shape[0] > wav.shape[0]


def test_tts_service_tracks_startup_state() -> None:
    service = TTSService()
    fake = _FakeEngine()
    service.engines['preview'] = fake
    service.engines['final'] = fake

    resolved = service.initialize_or_raise('mlx-community/chatterbox-fp16')

    assert resolved == 'mlx-community/chatterbox-fp16'
    assert service.ready is True
    assert service.startup_state == 'ready'
    assert service.startup_error is None
