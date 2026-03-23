from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from .config import DEFAULT_TTS_MODEL_FINAL, DEFAULT_TTS_MODEL_PREVIEW, MODEL_ALIAS
from .tts.backends import ChatterboxMLEngine


class TTSError(Exception):
    pass


class TTSService:
    def __init__(self) -> None:
        self.model_id: str | None = None
        self.ready = False
        self.startup_state = 'booting'
        self.startup_error: str | None = None
        self.engines = {
            'preview': ChatterboxMLEngine('chatterbox_turbo'),
            'final': ChatterboxMLEngine('chatterbox_full'),
        }
        self.backend_kind = 'dual_chatterbox'

    def resolve_model_id(self, requested_model_id: str | None = None, *, render_mode: str | None = None) -> str:
        if requested_model_id:
            return MODEL_ALIAS.get(requested_model_id, requested_model_id)
        if render_mode == 'preview':
            return DEFAULT_TTS_MODEL_PREVIEW
        return self.model_id or DEFAULT_TTS_MODEL_FINAL

    def engine_label_for_model(self, requested_model_id: str) -> str:
        resolved = MODEL_ALIAS.get(requested_model_id, requested_model_id)
        if resolved == DEFAULT_TTS_MODEL_PREVIEW:
            return 'preview'
        return 'final'

    def initialize_or_raise(self, requested_model_id: str | None = None) -> str:
        final_model = MODEL_ALIAS.get(requested_model_id or DEFAULT_TTS_MODEL_FINAL, requested_model_id or DEFAULT_TTS_MODEL_FINAL)
        preview_model = DEFAULT_TTS_MODEL_PREVIEW
        self.startup_state = 'warming'
        self.startup_error = None
        try:
            self.engines['preview'].initialize_or_raise(preview_model)
            self.engines['final'].initialize_or_raise(final_model)
        except Exception as exc:
            self.ready = False
            self.model_id = final_model
            self.startup_state = 'failed'
            self.startup_error = str(exc)
            raise TTSError(f"Could not initialize TTS backends with final='{final_model}' preview='{preview_model}'") from exc
        self.model_id = final_model
        self.ready = True
        self.startup_state = 'ready'
        self.startup_error = None
        return final_model

    def load_model(self, requested_model_id: str) -> str:
        resolved = MODEL_ALIAS.get(requested_model_id, requested_model_id)
        label = self.engine_label_for_model(resolved)
        self.engines[label].initialize_or_raise(resolved)
        self.ready = True
        if self.engines['preview'].ready and self.engines['final'].ready:
            self.startup_state = 'ready'
            self.startup_error = None
        if label == 'final':
            self.model_id = resolved
        return resolved

    def synthesize_raw(
        self,
        *,
        text: str,
        ref_audio_path: str,
        requested_model_id: str,
        speed: float = 1.0,
        generation_options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, int, str]:
        model_id = self.load_model(requested_model_id)
        label = self.engine_label_for_model(model_id)
        engine = self.engines[label]
        try:
            wav, sample_rate = engine.synthesize_raw(
                text=text,
                ref_audio_path=ref_audio_path,
                requested_model_id=model_id,
                generation_options=generation_options,
            )
            wav = self._apply_speed_transform(wav, sample_rate, speed)
            return wav, sample_rate, engine.name
        except Exception as exc:
            raise TTSError(f'TTS generation failed for model {model_id}: {exc}') from exc

    def synthesize(
        self,
        text: str,
        ref_audio_path: str,
        output_path: Path,
        requested_model_id: str,
        instruct: str | None = None,
        speed: float = 1.0,
        generation_options: dict[str, Any] | None = None,
    ) -> tuple[float, str]:
        options = dict(generation_options or {})
        if instruct:
            options.setdefault('instruct', instruct)
        wav, sample_rate, engine_name = self.synthesize_raw(
            text=text,
            ref_audio_path=ref_audio_path,
            requested_model_id=requested_model_id,
            speed=speed,
            generation_options=options,
        )
        self.write_audio(output_path, wav, sample_rate)
        return float(len(wav) / max(sample_rate, 1)), engine_name

    def write_audio(self, output_path: Path, wav: np.ndarray, sample_rate: int) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), wav, sample_rate)

    def _apply_speed_transform(self, wav: np.ndarray, sample_rate: int, speed: float) -> np.ndarray:
        if abs(float(speed) - 1.0) < 0.01:
            return wav.astype(np.float32)
        try:
            with tempfile.TemporaryDirectory(prefix='omnivious_speed_') as temp_dir:
                input_path = Path(temp_dir) / 'in.wav'
                output_path = Path(temp_dir) / 'out.wav'
                sf.write(str(input_path), wav, sample_rate)
                subprocess.run(
                    [
                        'ffmpeg',
                        '-hide_banner',
                        '-loglevel',
                        'error',
                        '-y',
                        '-i',
                        str(input_path),
                        '-filter:a',
                        f'atempo={float(speed):.6f}',
                        str(output_path),
                    ],
                    check=True,
                )
                stretched, _ = sf.read(str(output_path), dtype='float32')
                return stretched.astype(np.float32)
        except Exception:
            speed = max(0.7, min(1.3, float(speed)))
            source_x = np.arange(wav.shape[0], dtype=np.float32)
            target_len = max(1, int(round(wav.shape[0] / speed)))
            target_x = np.linspace(0, wav.shape[0] - 1, target_len, dtype=np.float32)
            if wav.ndim == 1:
                return np.interp(target_x, source_x, wav).astype(np.float32)
            channels = [
                np.interp(target_x, source_x, wav[:, idx]).astype(np.float32)
                for idx in range(wav.shape[1])
            ]
            return np.stack(channels, axis=1)


tts_service = TTSService()
