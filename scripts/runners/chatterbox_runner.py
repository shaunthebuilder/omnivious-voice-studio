#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
import torchaudio as ta


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
    parser.add_argument("--reference-clip", required=False)
    parser.add_argument("--output-wav", required=True)
    parser.add_argument("--device", default="auto", choices=["auto", "mps", "cuda", "cpu"])
    parser.add_argument("--model", default="turbo", choices=["turbo", "base"])
    parser.add_argument("--exaggeration", type=float, default=1.2)
    parser.add_argument("--cfg-weight", type=float, default=0.5)
    args = parser.parse_args()

    device = pick_device(args.device)

    if args.model == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        model = ChatterboxTurboTTS.from_pretrained(device=device)
    else:
        from chatterbox.tts import ChatterboxTTS

        model = ChatterboxTTS.from_pretrained(device=device)

    kwargs = {}
    if args.reference_clip:
        kwargs["audio_prompt_path"] = args.reference_clip
    if args.model == "base":
        kwargs["exaggeration"] = args.exaggeration
        kwargs["cfg_weight"] = args.cfg_weight

    t0 = time.perf_counter()
    wav = model.generate(args.text, **kwargs)
    infer_ms = (time.perf_counter() - t0) * 1000.0

    out = Path(args.output_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(out), wav, model.sr)

    metrics = {
        # Offline API does not expose packet-level first-token; using end-to-end latency surrogate.
        "first_token_latency_ms": infer_ms,
        "device": device,
        "model": args.model,
    }
    Path(str(out) + ".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
