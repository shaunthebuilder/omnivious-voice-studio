from __future__ import annotations

STYLE_INSTRUCTS = {
    "natural": (
        "Natural conversational delivery, balanced emotion, clear and relaxed phrasing. "
        "Avoid anchor-like, theatrical, melancholic, overly bubbly, or flirtatious tone."
    ),
    "news": (
        "Professional broadcast news anchor delivery: authoritative, precise, neutral, steady cadence, crisp articulation. "
        "Avoid dramatic, playful, or intimate tone."
    ),
    "drama_movie": (
        "Perform like a cinematic movie scene with high emotional contrast, pronounced emphasis, wider pitch movement, "
        "strategic pauses, and bold theatrical intensity. "
        "Avoid flat anchor tone and avoid monotone delivery."
    ),
    "sad": (
        "Melancholic and reflective delivery: softer projection, lower energy, gentle pacing, emotionally subdued expression. "
        "Avoid cheerful or energetic tone."
    ),
    "happy": (
        "Cheerful and upbeat delivery: bright tone, lively rhythm, positive energy, smiling resonance. "
        "Avoid solemn or melancholic tone."
    ),
    "charming_attractive": (
        "Charming and magnetic delivery: warm, confident, playful, smooth phrasing, inviting but tasteful intimacy. "
        "Avoid explicit sexualized tone."
    ),
}

LEGACY_STYLE_MAP = {
    "natural": "natural",
    "cinematic": "drama_movie",
    "podcast": "natural",
    "storytelling": "drama_movie",
    "news": "news",
    "dramatic": "drama_movie",
}


def clamp_qwen_speed(speed: float) -> float:
    return max(0.7, min(1.3, float(speed)))


def normalize_style(style: str | None) -> tuple[str, list[str]]:
    warnings: list[str] = []
    raw = (style or "").strip().lower()
    if not raw:
        return "natural", warnings
    mapped = LEGACY_STYLE_MAP.get(raw, raw)
    if mapped not in STYLE_INSTRUCTS:
        warnings.append(f"Unknown style '{style}', defaulted to natural")
        return "natural", warnings
    if mapped != raw:
        warnings.append(f"Mapped legacy style '{raw}' to '{mapped}'")
    return mapped, warnings


def build_qwen_instruct_from_style(style: str | None) -> tuple[str, list[str], list[str]]:
    style_key, warnings = normalize_style(style)
    instruct = STYLE_INSTRUCTS[style_key]
    tags = [f"style:{style_key}"]
    return instruct, tags, warnings


def build_qwen_generation_options(style: str | None) -> tuple[dict[str, float], list[str], list[str]]:
    style_key, warnings = normalize_style(style)
    style_options: dict[str, dict[str, float]] = {
        "natural": {"temperature": 0.68, "top_p": 0.88, "repetition_penalty": 1.08},
        "news": {"temperature": 0.45, "top_p": 0.76, "repetition_penalty": 1.12},
        "drama_movie": {"temperature": 0.96, "top_p": 0.98, "repetition_penalty": 1.02},
        "sad": {"temperature": 0.58, "top_p": 0.82, "repetition_penalty": 1.10},
        "happy": {"temperature": 0.84, "top_p": 0.93, "repetition_penalty": 1.06},
        "charming_attractive": {"temperature": 0.78, "top_p": 0.91, "repetition_penalty": 1.05},
    }
    options = style_options[style_key]
    tags = [
        f"gen_temperature:{options['temperature']:.2f}",
        f"gen_top_p:{options['top_p']:.2f}",
        f"gen_repetition_penalty:{options['repetition_penalty']:.2f}",
    ]
    return options, tags, warnings
