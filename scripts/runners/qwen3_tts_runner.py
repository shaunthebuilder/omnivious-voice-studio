#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import soundfile as sf
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
    parser.add_argument("--model-id", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    parser.add_argument("--language", default="English")
    parser.add_argument("--instruct", default="")
    parser.add_argument("--device", default="auto", choices=["auto", "mps", "cuda", "cpu"])
    args = parser.parse_args()

    from qwen_tts import Qwen3TTSModel

    device = pick_device(args.device)
    load_kwargs = {}
    if device in {"cuda", "mps"}:
        load_kwargs["device_map"] = device
    if device == "cuda":
        load_kwargs["dtype"] = torch.bfloat16
        load_kwargs["attn_implementation"] = "flash_attention_2"

    model = Qwen3TTSModel.from_pretrained(args.model_id, **load_kwargs)

    t0 = time.perf_counter()
    wavs, sr = model.generate_voice_clone(
        text=args.text,
        ref_audio=args.reference_clip,
        ref_text=args.reference_text,
        language=args.language,
        instruct=(args.instruct if args.instruct else None),
    )
    infer_ms = (time.perf_counter() - t0) * 1000.0

    out = Path(args.output_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
    sf.write(str(out), wav, sr)

    metrics = {
        # Offline API does not expose packet-level first-token; using end-to-end latency surrogate.
        "first_token_latency_ms": infer_ms,
        "device": device,
        "model_id": args.model_id,
    }
    Path(str(out) + ".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
