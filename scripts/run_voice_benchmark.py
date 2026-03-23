#!/usr/bin/env python3
"""Generic benchmark harness for local TTS voice-cloning model evaluation.

It executes per-model generation commands against a shared reference clip and
shared prompt set, then produces benchmark_measurements.json for the ranking
script.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shlex
import statistics
import subprocess
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class RunResult:
    elapsed_s: float
    audio_duration_s: float
    rtf: float
    peak_ram_gb: Optional[float]
    first_token_latency_ms: Optional[float]
    output_wav: str


def safe_slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", text)


def read_wav_duration_s(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            raise ValueError(f"Invalid WAV sample rate in {path}")
        return frames / float(rate)


def parse_time_l_peak_ram_gb(stderr_text: str) -> Optional[float]:
    # macOS /usr/bin/time -l output example:
    # "12345678  maximum resident set size"
    m = re.search(r"(\d+)\s+maximum resident set size", stderr_text)
    if not m:
        return None
    # macOS reports bytes for -l on modern versions.
    value = float(m.group(1))
    gb = value / (1024.0 ** 3)
    # If value is unexpectedly small, fallback to KB assumption.
    if gb < 0.05:
        gb = value / (1024.0 ** 2)
    return gb


def load_first_token_latency(path: Optional[Path]) -> Optional[float]:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for key in ["first_token_latency_ms", "first_token_ms", "ttfa_ms"]:
        if key in payload:
            try:
                return float(payload[key])
            except Exception:
                return None
    return None


def run_one(command: str) -> Tuple[float, str, str]:
    wrapped = f"/usr/bin/time -l sh -lc {shlex.quote(command)}"
    t0 = time.perf_counter()
    proc = subprocess.run(
        wrapped,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(
            "Benchmark command failed.\n"
            f"Command: {command}\n"
            f"Exit: {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )
    return elapsed, proc.stdout, proc.stderr


def cv(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    return statistics.stdev(values) / mean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="benchmarks/benchmark_config.example.json")
    parser.add_argument("--output", default="benchmark_measurements.json")
    parser.add_argument("--runs-dir", default="benchmarks/runs")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    out_path = Path(args.output)
    runs_dir = Path(args.runs_dir)

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    reference_clip = Path(cfg["reference_clip"]).expanduser().resolve()
    if not reference_clip.exists():
        raise FileNotFoundError(f"reference_clip not found: {reference_clip}")

    prompts = cfg["prompts"]
    repeats = int(cfg.get("repeats", 3))
    models = cfg["models"]

    runs_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Dict[str, float]] = {}
    raw_results: Dict[str, Dict[str, object]] = {}

    for model in models:
        model_id = model["model_id"]
        command_tmpl = model["command"]
        model_slug = safe_slug(model_id)
        model_dir = runs_dir / model_slug
        model_dir.mkdir(parents=True, exist_ok=True)

        model_runs: List[RunResult] = []

        print(f"[model] {model_id}")

        for p in prompts:
            prompt_id = p["id"]
            text = p["text"]
            for i in range(1, repeats + 1):
                out_wav = model_dir / f"{prompt_id}_r{i}.wav"
                sidecar = Path(str(out_wav) + ".metrics.json")

                command = command_tmpl.format(
                    text=text,
                    reference_clip=str(reference_clip),
                    output_wav=str(out_wav),
                    prompt_id=prompt_id,
                    repeat=i,
                )

                elapsed_s, _stdout, stderr = run_one(command)

                if not out_wav.exists():
                    raise FileNotFoundError(f"Expected output not found: {out_wav}")

                duration_s = read_wav_duration_s(out_wav)
                rtf = elapsed_s / duration_s if duration_s > 0 else math.inf

                run = RunResult(
                    elapsed_s=elapsed_s,
                    audio_duration_s=duration_s,
                    rtf=rtf,
                    peak_ram_gb=parse_time_l_peak_ram_gb(stderr),
                    first_token_latency_ms=load_first_token_latency(sidecar),
                    output_wav=str(out_wav),
                )
                model_runs.append(run)

                print(
                    f"  - {prompt_id} r{i}: elapsed={elapsed_s:.2f}s "
                    f"dur={duration_s:.2f}s rtf={rtf:.3f}"
                )

        rtf_vals = [r.rtf for r in model_runs if math.isfinite(r.rtf)]
        lat_vals = [r.first_token_latency_ms for r in model_runs if r.first_token_latency_ms is not None]
        ram_vals = [r.peak_ram_gb for r in model_runs if r.peak_ram_gb is not None]

        # Subjective scores: provide either in config or fill later.
        manual = cfg.get("manual_scores", {}).get(model_id, {})

        summary[model_id] = {
            "rtf": round(statistics.mean(rtf_vals), 3),
            "first_token_latency_ms": round(statistics.mean(lat_vals), 2) if lat_vals else 0.0,
            "peak_ram_gb": round(max(ram_vals), 3) if ram_vals else 0.0,
            "emotion_control_score": float(manual.get("emotion_control_score", 0.0)),
            "voice_similarity_score": float(manual.get("voice_similarity_score", 0.0)),
            "operational_simplicity_score": float(manual.get("operational_simplicity_score", 0.0)),
            "stability_cv_rtf": round(cv(rtf_vals), 4),
        }

        raw_results[model_id] = {
            "runs": [r.__dict__ for r in model_runs],
        }

    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    raw_path = out_path.with_name(out_path.stem + "_raw_runs.json")
    raw_path.write_text(json.dumps(raw_results, indent=2), encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"Wrote {raw_path}")


if __name__ == "__main__":
    main()
