#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch


def pick_device(explicit: str) -> str:
    if explicit != "auto":
        return explicit
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--reference-clip", required=True)
    parser.add_argument("--reference-text", required=True)
    parser.add_argument("--output-wav", required=True)
    parser.add_argument("--model-id", default="nari-labs/Dia-1.6B-0626")
    parser.add_argument("--device", default="auto", choices=["auto", "mps", "cuda", "cpu"])
    parser.add_argument("--temperature", type=float, default=1.8)
    parser.add_argument("--top-p", type=float, default=0.90)
    parser.add_argument("--cfg-scale", type=float, default=4.0)
    args = parser.parse_args()

    from dia.model import Dia

    device = pick_device(args.device)
    compute_dtype = "float16" if device in {"cuda", "mps"} else "float32"

    model = Dia.from_pretrained(args.model_id, compute_dtype=compute_dtype)

    # Dia voice-clone convention: prepend transcript of reference clip.
    prompt = f"{args.reference_text} {args.text}"

    t0 = time.perf_counter()
    output = model.generate(
        prompt,
        audio_prompt=args.reference_clip,
        use_torch_compile=False,
        verbose=False,
        cfg_scale=args.cfg_scale,
        temperature=args.temperature,
        top_p=args.top_p,
        cfg_filter_top_k=50,
    )
    infer_ms = (time.perf_counter() - t0) * 1000.0

    out = Path(args.output_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save_audio(str(out), output)

    metrics = {
        # Offline API does not expose packet-level first-token; using end-to-end latency surrogate.
        "first_token_latency_ms": infer_ms,
        "device": device,
        "model_id": args.model_id,
    }
    Path(str(out) + ".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
