from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from .config import AUDIO_SAMPLE_RATE, JOBS_DIR, MAX_TRAIN_SECONDS, MIN_TRAIN_SECONDS


class IngestError(Exception):
    pass


def _run(cmd: list[str]) -> None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise IngestError(
            f"Executable not found: {cmd[0]}. Ensure required tools are installed and available."
        ) from exc
    if proc.returncode != 0:
        raise IngestError(f"Command failed: {' '.join(cmd)}\n{proc.stderr}")


def _resolve_yt_dlp_cmd() -> list[str]:
    # Preferred: system binary.
    from shutil import which

    binary = which("yt-dlp")
    if binary:
        return [binary]

    # Fallback: venv script next to the current interpreter.
    script = Path(sys.executable).parent / "yt-dlp"
    if script.exists():
        return [str(script)]

    # Final fallback: module invocation in the current Python environment.
    return [sys.executable, "-m", "yt_dlp"]


def probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError(f"ffprobe failed: {proc.stderr}")
    data = json.loads(proc.stdout)
    return float(data["format"]["duration"])


def save_upload_tmp(file_bytes: bytes, suffix: str) -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = JOBS_DIR / f"upload_{uuid.uuid4().hex}{suffix}"
    path.write_bytes(file_bytes)
    return path


def download_youtube_audio(url: str) -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    out_base = JOBS_DIR / f"yt_{uuid.uuid4().hex}"
    yt_dlp_cmd = _resolve_yt_dlp_cmd()
    cmd = [
        *yt_dlp_cmd,
        "-x",
        "--audio-format",
        "wav",
        "-o",
        f"{out_base}.%(ext)s",
        url,
    ]
    _run(cmd)
    matches = list(JOBS_DIR.glob(f"{out_base.name}.*"))
    if not matches:
        raise IngestError("Could not locate downloaded YouTube audio")
    return matches[0]


def normalize_and_trim(input_path: Path, output_path: Path) -> float:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        str(AUDIO_SAMPLE_RATE),
        "-t",
        str(MAX_TRAIN_SECONDS),
        str(output_path),
    ]
    _run(cmd)
    duration = probe_duration(output_path)
    if duration < MIN_TRAIN_SECONDS:
        raise IngestError(f"Audio too short ({duration:.2f}s). Minimum is {MIN_TRAIN_SECONDS}s")
    return min(duration, float(MAX_TRAIN_SECONDS))


def cleanup_tmp(path: Path | None) -> None:
    if not path:
        return
    try:
        if path.exists():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
    except OSError:
        pass
