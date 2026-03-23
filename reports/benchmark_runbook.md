# Benchmark Runbook (Mac M1 32 GB)

## Purpose
Run a consistent local benchmark for clip-based voice cloning + emotion/modulation control and feed measured metrics into `model_eval_results.json`.

## Inputs
- Reference clip: `benchmarks/reference_clip.wav` (5-10 seconds, clean speech)
- Prompt set: embedded in `benchmarks/benchmark_config.example.json`
- Repeats: 3 per prompt per model

## 1) Prepare environment
Install model dependencies you plan to benchmark:
- Chatterbox: `pip install chatterbox-tts`
- Qwen3-TTS: follow [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- Dia: follow [nari-labs/dia](https://github.com/nari-labs/dia)

Required tools:
- Python 3.10+
- `/usr/bin/time` (built into macOS)

## 2) Configure benchmark
1. Put your real reference clip at `benchmarks/reference_clip.wav`.
2. Copy config and adjust commands if needed:
```bash
cp benchmarks/benchmark_config.example.json benchmarks/benchmark_config.json
```
3. Ensure each command in the config produces a WAV file at `{output_wav}`.

## 3) Run benchmark harness
```bash
python3 scripts/run_voice_benchmark.py \
  --config benchmarks/benchmark_config.json \
  --output benchmark_measurements.json
```

Outputs:
- `benchmark_measurements.json`
- `benchmark_measurements_raw_runs.json`

## 4) Fill subjective scores
Edit `benchmark_measurements.json` and set:
- `emotion_control_score` (1-5)
- `voice_similarity_score` (1-5)
- `operational_simplicity_score` (1-5)

## 5) Rebuild final ranking
```bash
python3 scripts/build_voice_model_shortlist.py
```

This updates:
- `model_eval_results.json`
- `reports/voice_cloning_shortlist_feb2026.md`

## Notes
- Current repo outputs are seeded with evidence-based estimates until measured metrics are provided.
- For first-token latency, runner scripts currently use end-to-end latency as a surrogate for offline APIs.
