#!/usr/bin/env python3
"""Builds a Feb-2026 voice-cloning shortlist for Apple Silicon M1 32GB.

The script encodes verified public facts (license, release date, capabilities,
Apple-local runtime paths) and computes a weighted ranking. Runtime metrics are
estimate placeholders until measured on the target machine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Any

AS_OF_DATE = date(2026, 2, 22)


@dataclass
class ModelEval:
    # Required schema fields
    model_id: str
    release_date: str  # YYYY-MM-DD
    license_class: str  # commercial_safe|research_only|unclear_license
    runtime_backend: str  # mps|mlx
    quantization: str
    rtf: float
    first_token_latency_ms: float
    peak_ram_gb: float
    emotion_control_score: float  # 1-5
    voice_similarity_score: float  # 1-5
    overall_score: float  # 0-100
    notes: str

    # Extra fields used for gating/ranking traceability
    gate_release_ok: bool
    gate_clip_clone_ok: bool
    gate_expression_ok: bool
    gate_apple_path_ok: bool
    gate_commercial_ok: bool
    operational_simplicity_score: float  # 1-5


def parse_yyyy_mm_dd(d: str) -> date:
    yyyy, mm, dd = d.split("-")
    return date(int(yyyy), int(mm), int(dd))


def score_speed_smoothness(rtf: float, latency_ms: float, peak_ram_gb: float) -> float:
    # RTF: prioritize <= 1.0; acceptable up to 1.5; heavily penalize above 1.5.
    if rtf <= 1.0:
        rtf_score = 100.0 - max(0.0, (rtf - 0.4) * 25.0)
    elif rtf <= 1.5:
        rtf_score = 80.0 - (rtf - 1.0) * 60.0
    else:
        rtf_score = max(5.0, 50.0 - (rtf - 1.5) * 15.0)

    # Latency: soft threshold for interactive UX.
    if latency_ms <= 250:
        lat_score = 100.0
    elif latency_ms <= 500:
        lat_score = 85.0 - (latency_ms - 250.0) * 0.08
    elif latency_ms <= 1000:
        lat_score = 65.0 - (latency_ms - 500.0) * 0.06
    else:
        lat_score = max(10.0, 35.0 - (latency_ms - 1000.0) * 0.02)

    # Memory: prefer <= 12 GB peak for 32 GB system smoothness.
    if peak_ram_gb <= 8.0:
        ram_score = 100.0
    elif peak_ram_gb <= 12.0:
        ram_score = 85.0 - (peak_ram_gb - 8.0) * 6.25
    elif peak_ram_gb <= 20.0:
        ram_score = 60.0 - (peak_ram_gb - 12.0) * 5.0
    else:
        ram_score = max(5.0, 20.0 - (peak_ram_gb - 20.0) * 2.5)

    return max(0.0, min(100.0, 0.6 * rtf_score + 0.25 * lat_score + 0.15 * ram_score))


def compute_overall(model: ModelEval) -> float:
    speed = score_speed_smoothness(model.rtf, model.first_token_latency_ms, model.peak_ram_gb)
    expressive = model.emotion_control_score * 20.0
    cloning = model.voice_similarity_score * 20.0
    ops = model.operational_simplicity_score * 20.0

    overall = 0.35 * speed + 0.30 * expressive + 0.20 * cloning + 0.15 * ops

    # Required down-rank for models above acceptable near-real-time.
    if model.rtf > 1.5:
        overall -= 12.0

    # Enforce commercial-safe preference in the main rank.
    if model.license_class != "commercial_safe":
        overall -= 15.0

    # Penalize unclear Apple-local path.
    if not model.gate_apple_path_ok:
        overall -= 20.0

    return round(max(0.0, min(100.0, overall)), 2)


def build_candidates() -> List[ModelEval]:
    # Metrics below are evidence-based estimates from public docs and model size,
    # not measured on this host. Replace with measured values from the benchmark
    # harness when executed on the target M1 machine.
    rows: List[ModelEval] = [
        ModelEval(
            model_id="resemble-ai/chatterbox-turbo",
            release_date="2025-04-23",
            license_class="commercial_safe",
            runtime_backend="mps",
            quantization="native_fp16_or_mlx_4bit",
            rtf=0.55,
            first_token_latency_ms=240.0,
            peak_ram_gb=4.2,
            emotion_control_score=4.7,
            voice_similarity_score=4.4,
            overall_score=0.0,
            notes=(
                "MIT. Official Apple example exists (example_for_mac.py). "
                "Zero-shot voice cloning + expressive controls (exaggeration/cfg). "
                "MLX quantized variants available on HF. Metrics estimated."
            ),
            gate_release_ok=True,
            gate_clip_clone_ok=True,
            gate_expression_ok=True,
            gate_apple_path_ok=True,
            gate_commercial_ok=True,
            operational_simplicity_score=4.9,
        ),
        ModelEval(
            model_id="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
            release_date="2026-01-21",
            license_class="commercial_safe",
            runtime_backend="mlx",
            quantization="mlx-community 4bit",
            rtf=0.72,
            first_token_latency_ms=320.0,
            peak_ram_gb=6.8,
            emotion_control_score=4.8,
            voice_similarity_score=4.6,
            overall_score=0.0,
            notes=(
                "Apache-2.0 on repo and HF model card. Supports 3-second rapid voice clone "
                "and instruction-driven emotion/prosody control. Official examples are CUDA-leaning; "
                "Apple-local path is via mlx-community quantized conversions. Metrics estimated."
            ),
            gate_release_ok=True,
            gate_clip_clone_ok=True,
            gate_expression_ok=True,
            gate_apple_path_ok=True,
            gate_commercial_ok=True,
            operational_simplicity_score=4.2,
        ),
        ModelEval(
            model_id="nari-labs/Dia-1.6B",
            release_date="2025-04-19",
            license_class="commercial_safe",
            runtime_backend="mlx",
            quantization="mlx-community 4bit",
            rtf=1.32,
            first_token_latency_ms=650.0,
            peak_ram_gb=12.4,
            emotion_control_score=4.3,
            voice_similarity_score=4.2,
            overall_score=0.0,
            notes=(
                "Apache-2.0. Voice-cloning via 5-10s prompt + transcript and strong paralinguistics. "
                "Official repo says GPU-tested; Apple path is through mlx-community conversion, "
                "so operational risk is moderate. Metrics estimated."
            ),
            gate_release_ok=True,
            gate_clip_clone_ok=True,
            gate_expression_ok=True,
            gate_apple_path_ok=True,
            gate_commercial_ok=True,
            operational_simplicity_score=3.6,
        ),
        ModelEval(
            model_id="zai-org/GLM-TTS",
            release_date="2025-12-06",
            license_class="commercial_safe",
            runtime_backend="mps",
            quantization="none_official",
            rtf=2.10,
            first_token_latency_ms=1200.0,
            peak_ram_gb=18.0,
            emotion_control_score=4.5,
            voice_similarity_score=4.5,
            overall_score=0.0,
            notes=(
                "Repo Apache-2.0; HF model card tags MIT. Strong zero-shot cloning and RL emotion control. "
                "No explicit Apple/MLX path in official docs, so near-real-time on M1 is unlikely. "
                "Metrics estimated."
            ),
            gate_release_ok=True,
            gate_clip_clone_ok=True,
            gate_expression_ok=True,
            gate_apple_path_ok=False,
            gate_commercial_ok=True,
            operational_simplicity_score=2.6,
        ),
        ModelEval(
            model_id="OpenMOSS-Team/MOSS-TTSD-v1.0",
            release_date="2026-02-10",
            license_class="commercial_safe",
            runtime_backend="mps",
            quantization="none_official",
            rtf=3.80,
            first_token_latency_ms=2200.0,
            peak_ram_gb=27.0,
            emotion_control_score=4.9,
            voice_similarity_score=4.7,
            overall_score=0.0,
            notes=(
                "Apache-2.0. Latest (2026-02-10) and highly expressive with short-reference cloning, "
                "but model family is 8B and official docs are CUDA-oriented; no clear Apple/MLX local path. "
                "Likely not smooth on M1 32GB for near-real-time. Metrics estimated."
            ),
            gate_release_ok=True,
            gate_clip_clone_ok=True,
            gate_expression_ok=True,
            gate_apple_path_ok=False,
            gate_commercial_ok=True,
            operational_simplicity_score=2.1,
        ),
        ModelEval(
            model_id="IndexTeam/IndexTTS-2",
            release_date="2026-01-20",
            license_class="research_only",
            runtime_backend="mps",
            quantization="none_official",
            rtf=1.10,
            first_token_latency_ms=560.0,
            peak_ram_gb=13.0,
            emotion_control_score=4.8,
            voice_similarity_score=4.7,
            overall_score=0.0,
            notes=(
                "Technically strong for expressive cloning, but license is bilibili Model Use License with "
                "commercial constraints. Excluded for strict commercial-safe preference. Metrics estimated."
            ),
            gate_release_ok=True,
            gate_clip_clone_ok=True,
            gate_expression_ok=True,
            gate_apple_path_ok=False,
            gate_commercial_ok=False,
            operational_simplicity_score=3.4,
        ),
    ]

    for row in rows:
        # Guard release cut-off.
        row.gate_release_ok = row.gate_release_ok and parse_yyyy_mm_dd(row.release_date) <= AS_OF_DATE
        row.overall_score = compute_overall(row)

    return rows


def apply_metric_overrides(rows: List[ModelEval], override_path: Path) -> List[ModelEval]:
    if not override_path.exists():
        return rows

    payload: Dict[str, Dict[str, Any]] = json.loads(override_path.read_text(encoding="utf-8"))
    for row in rows:
        override = payload.get(row.model_id)
        if not override:
            continue
        for field in [
            "rtf",
            "first_token_latency_ms",
            "peak_ram_gb",
            "emotion_control_score",
            "voice_similarity_score",
            "operational_simplicity_score",
        ]:
            if field in override:
                setattr(row, field, float(override[field]))
        row.notes = row.notes + " Metrics overridden from benchmark_measurements.json."
        row.overall_score = compute_overall(row)
    return rows


def build_ranked_table(rows: List[ModelEval]) -> str:
    def pass_all(row: ModelEval) -> bool:
        return all(
            [
                row.gate_release_ok,
                row.gate_clip_clone_ok,
                row.gate_expression_ok,
                row.gate_apple_path_ok,
                row.gate_commercial_ok,
            ]
        )

    ranked = sorted(
        rows,
        key=lambda x: (pass_all(x), x.gate_commercial_ok, x.overall_score),
        reverse=True,
    )
    lines = []
    lines.append("| Rank | Model | Release date | License class | Runtime path | Quantization | RTF | Peak RAM (GB) | Emotion control | Clone fidelity | Verdict |")
    lines.append("|---:|---|---|---|---|---|---:|---:|---:|---:|---|")
    for i, r in enumerate(ranked, start=1):
        passes_all = pass_all(r)
        verdict = "PASS" if passes_all else "FAIL"
        runtime_path = f"{r.runtime_backend}"
        lines.append(
            f"| {i} | {r.model_id} | {r.release_date} | {r.license_class} | {runtime_path} | {r.quantization} | {r.rtf:.2f} | {r.peak_ram_gb:.1f} | {r.emotion_control_score:.1f}/5 | {r.voice_similarity_score:.1f}/5 | {verdict} |"
        )
    return "\n".join(lines)


def main() -> None:
    out_json = Path("model_eval_results.json")
    out_report = Path("reports/voice_cloning_shortlist_feb2026.md")

    rows = build_candidates()
    rows = apply_metric_overrides(rows, Path("benchmark_measurements.json"))

    def pass_all(row: ModelEval) -> bool:
        return all(
            [
                row.gate_release_ok,
                row.gate_clip_clone_ok,
                row.gate_expression_ok,
                row.gate_apple_path_ok,
                row.gate_commercial_ok,
            ]
        )

    ranked = sorted(
        rows,
        key=lambda x: (pass_all(x), x.gate_commercial_ok, x.overall_score),
        reverse=True,
    )

    # Write JSON artifact in ranked order.
    json_rows = []
    for r in ranked:
        row = asdict(r)
        # Keep required schema fields at top-level; keep extra fields too for transparency.
        json_rows.append(row)

    out_json.write_text(json.dumps(json_rows, indent=2), encoding="utf-8")

    # Build ranked report.
    passing = [
        r
        for r in ranked
        if pass_all(r)
    ]

    top_reco = passing[0] if passing else ranked[0]

    report_lines = [
        "# Feb 2026 Open-Source Voice Cloning Shortlist (M1 32 GB)",
        "",
        "Date cutoff: 2026-02-22.",
        "",
        "All runtime metrics in this report are evidence-based estimates from public docs and model size; run local benchmarks on your M1 with the same prompts to replace estimates.",
        "",
        "## Ranked Table",
        "",
        build_ranked_table(rows),
        "",
        "## Install/Run Now Recommendation",
        "",
        f"Primary recommendation: **{top_reco.model_id}** ({top_reco.runtime_backend}, {top_reco.quantization}).",
        "",
        "Reason: best combined score for near-real-time smoothness on Apple Silicon while retaining clip cloning and strong expressive control under a commercial-safe license.",
        "",
        "## Source Links",
        "",
        "- https://github.com/resemble-ai/chatterbox",
        "- https://raw.githubusercontent.com/resemble-ai/chatterbox/master/example_for_mac.py",
        "- https://github.com/QwenLM/Qwen3-TTS",
        "- https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "- https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit",
        "- https://github.com/nari-labs/dia",
        "- https://huggingface.co/mlx-community/Dia-1.6B-4bit",
        "- https://github.com/zai-org/GLM-TTS",
        "- https://huggingface.co/zai-org/GLM-TTS",
        "- https://github.com/OpenMOSS/MOSS-TTSD",
        "- https://huggingface.co/OpenMOSS-Team/MOSS-TTSD-v1.0",
        "- https://github.com/index-tts/index-tts",
        "- https://huggingface.co/IndexTeam/IndexTTS-2",
        "",
    ]

    out_report.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"Wrote {out_report}")
    print()
    print("Top recommendation:", top_reco.model_id)


if __name__ == "__main__":
    main()
