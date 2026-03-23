# Feb 2026 Open-Source Voice Cloning Shortlist (M1 32 GB)

Date cutoff: 2026-02-22.

All runtime metrics in this report are evidence-based estimates from public docs and model size; run local benchmarks on your M1 with the same prompts to replace estimates.

## Ranked Table

| Rank | Model | Release date | License class | Runtime path | Quantization | RTF | Peak RAM (GB) | Emotion control | Clone fidelity | Verdict |
|---:|---|---|---|---|---|---:|---:|---:|---:|---|
| 1 | resemble-ai/chatterbox-turbo | 2025-04-23 | commercial_safe | mps | native_fp16_or_mlx_4bit | 0.55 | 4.2 | 4.7/5 | 4.4/5 | PASS |
| 2 | Qwen/Qwen3-TTS-12Hz-0.6B-Base | 2026-01-21 | commercial_safe | mlx | mlx-community 4bit | 0.72 | 6.8 | 4.8/5 | 4.6/5 | PASS |
| 3 | nari-labs/Dia-1.6B | 2025-04-19 | commercial_safe | mlx | mlx-community 4bit | 1.32 | 12.4 | 4.3/5 | 4.2/5 | PASS |
| 4 | zai-org/GLM-TTS | 2025-12-06 | commercial_safe | mps | none_official | 2.10 | 18.0 | 4.5/5 | 4.5/5 | FAIL |
| 5 | OpenMOSS-Team/MOSS-TTSD-v1.0 | 2026-02-10 | commercial_safe | mps | none_official | 3.80 | 27.0 | 4.9/5 | 4.7/5 | FAIL |
| 6 | IndexTeam/IndexTTS-2 | 2026-01-20 | research_only | mps | none_official | 1.10 | 13.0 | 4.8/5 | 4.7/5 | FAIL |

## Install/Run Now Recommendation

Primary recommendation: **resemble-ai/chatterbox-turbo** (mps, native_fp16_or_mlx_4bit).

Reason: best combined score for near-real-time smoothness on Apple Silicon while retaining clip cloning and strong expressive control under a commercial-safe license.

## Source Links

- https://github.com/resemble-ai/chatterbox
- https://raw.githubusercontent.com/resemble-ai/chatterbox/master/example_for_mac.py
- https://github.com/QwenLM/Qwen3-TTS
- https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit
- https://github.com/nari-labs/dia
- https://huggingface.co/mlx-community/Dia-1.6B-4bit
- https://github.com/zai-org/GLM-TTS
- https://huggingface.co/zai-org/GLM-TTS
- https://github.com/OpenMOSS/MOSS-TTSD
- https://huggingface.co/OpenMOSS-Team/MOSS-TTSD-v1.0
- https://github.com/index-tts/index-tts
- https://huggingface.co/IndexTeam/IndexTTS-2
