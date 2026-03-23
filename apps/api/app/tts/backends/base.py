from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class TTSEngine(Protocol):
    name: str
    model_id: str | None
    ready: bool

    def initialize_or_raise(self, requested_model_id: str) -> str:
        ...

    def synthesize_raw(
        self,
        *,
        text: str,
        ref_audio_path: str,
        requested_model_id: str,
        generation_options: dict[str, Any] | None = None,
        on_chunk: Callable[[int], None] | None = None,
    ) -> tuple[np.ndarray, int]:
        ...


def ensure_ref_audio_exists(ref_audio_path: str) -> Path:
    path = Path(ref_audio_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")
    return path
