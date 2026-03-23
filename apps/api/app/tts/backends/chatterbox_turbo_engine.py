from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import numpy as np

from .base import ensure_ref_audio_exists


class ChatterboxMLError(Exception):
    pass


class ChatterboxMLEngine:
    def __init__(self, name: str) -> None:
        self.name = name
        self.model_id: str | None = None
        self.model = None
        self.ready = False
        self._lock = threading.Lock()
        self._conditioning_cache: dict[tuple[str, str, int], Any] = {}
        self._conditioning_cache_limit = 16
        self.last_conditioning_cache_hit = False

    def initialize_or_raise(self, requested_model_id: str) -> str:
        if self.ready and self.model is not None and self.model_id == requested_model_id:
            return requested_model_id

        try:
            from mlx_audio.tts import load
        except Exception as exc:
            self.model = None
            self.ready = False
            self.model_id = requested_model_id
            raise ChatterboxMLError('mlx-audio is unavailable for Chatterbox backend') from exc

        try:
            self.model = load(requested_model_id)
        except Exception as exc:
            self.model = None
            self.ready = False
            self.model_id = requested_model_id
            raise ChatterboxMLError(f"Failed to load model '{requested_model_id}'") from exc

        if not hasattr(self.model, 'generate'):
            self.model = None
            self.ready = False
            self.model_id = requested_model_id
            raise ChatterboxMLError('Loaded model does not expose generate()')

        self.model_id = requested_model_id
        self.ready = True
        self._conditioning_cache.clear()
        self.last_conditioning_cache_hit = False
        return requested_model_id

    def synthesize_raw(
        self,
        *,
        text: str,
        ref_audio_path: str,
        requested_model_id: str,
        generation_options: dict[str, Any] | None = None,
        on_chunk: Callable[[int], None] | None = None,
    ) -> tuple[np.ndarray, int]:
        self.initialize_or_raise(requested_model_id)
        if not self.ready or self.model is None:
            raise ChatterboxMLError('Chatterbox engine is not initialized')

        ref_path = ensure_ref_audio_exists(ref_audio_path)
        options = dict(generation_options or {})
        options.setdefault('stream', False)
        options.setdefault('split_pattern', r'(?<=[.!?])\s+')
        options.pop('instruct', None)

        chunks: list[np.ndarray] = []
        sample_rate = int(getattr(self.model, 'sample_rate', 24000))
        cache_key = (requested_model_id, str(ref_path.resolve()), int(ref_path.stat().st_mtime_ns))
        cache_hit = False
        with self._lock:
            conds = options.get('conds')
            if conds is None and hasattr(self.model, 'prepare_conditionals'):
                conds = self._conditioning_cache.get(cache_key)
                cache_hit = conds is not None
                if conds is None:
                    conds = self.model.prepare_conditionals(
                        str(ref_path),
                        int(getattr(self.model, 'sample_rate', 24000)),
                    )
                    self._conditioning_cache[cache_key] = conds
                    while len(self._conditioning_cache) > self._conditioning_cache_limit:
                        self._conditioning_cache.pop(next(iter(self._conditioning_cache)))
                options['conds'] = conds
                options.pop('ref_audio', None)
            else:
                options['ref_audio'] = str(ref_path)
            self.last_conditioning_cache_hit = cache_hit
            results = self.model.generate(text=text, **options)
            for idx, result in enumerate(results, start=1):
                wav = np.array(result.audio, dtype=np.float32)
                if wav.ndim > 1:
                    wav = wav.reshape(-1)
                if wav.size == 0:
                    continue
                chunks.append(wav)
                sample_rate = int(getattr(result, 'sample_rate', sample_rate))
                if on_chunk:
                    on_chunk(idx)

        if not chunks:
            raise ChatterboxMLError('Model returned no audio data')

        if len(chunks) == 1:
            return chunks[0], sample_rate
        return np.concatenate(chunks, axis=0), sample_rate
