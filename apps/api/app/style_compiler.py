from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .config import (
    FINAL_RENDER_MAX_TOKENS,
    PREVIEW_RENDER_MAX_TOKENS,
    SEGMENT_BASE_PAUSE_MS,
    SEGMENT_MAX_CHARS,
    SEGMENT_TARGET_CHARS,
    TAG_MAX_PER_SENTENCE,
    TAG_MAX_TOTAL,
)

StyleLiteral = Literal['natural', 'news', 'drama_movie', 'sad', 'happy', 'charming_attractive']

TAG_REGEX = r'\[[a-z ]+\]'
SUPPORTED_TAGS = [
    '[clear throat]',
    '[sigh]',
    '[shush]',
    '[cough]',
    '[groan]',
    '[sniff]',
    '[gasp]',
    '[chuckle]',
    '[laugh]',
]
SAFE_STYLE_TAGS = set(SUPPORTED_TAGS)
DISABLED_DEFAULT_TAGS: set[str] = set()
TAG_DETAILS: dict[str, str] = {
    '[clear throat]': 'Subtle vocal reset before a line.',
    '[sigh]': 'Breathy exhale for grief, fatigue, or relief.',
    '[shush]': 'Quieting cue for intimate or hushed delivery.',
    '[cough]': 'Brief cough effect used sparingly for realism.',
    '[groan]': 'Low emotional strain cue for heavy dramatic moments.',
    '[sniff]': 'Soft sniff cue suitable for crying-adjacent delivery.',
    '[gasp]': 'Quick inhale for surprise, tension, or emphasis.',
    '[chuckle]': 'Light playful laugh.',
    '[laugh]': 'Stronger laughter peak.',
}
STYLE_ALLOWED_TAGS: dict[StyleLiteral, list[str]] = {
    'natural': ['[clear throat]'],
    'news': ['[clear throat]', '[shush]'],
    'drama_movie': ['[gasp]', '[sigh]', '[groan]', '[shush]'],
    'sad': ['[sigh]', '[sniff]', '[groan]'],
    'happy': ['[chuckle]', '[laugh]', '[gasp]'],
    'charming_attractive': ['[chuckle]', '[sigh]', '[shush]'],
}
STYLE_CATALOG: dict[StyleLiteral, dict[str, object]] = {
    'natural': {
        'label': 'Natural',
        'description': 'Neutral and closest to the trained base voice, guided by punctuation. Supported tags are only used when written explicitly.',
        'uses_tags': True,
        'supported_tags': STYLE_ALLOWED_TAGS['natural'],
    },
    'news': {
        'label': 'News',
        'description': 'Confident, domineering, politician-anchor style delivery. Supported tags are only used when written explicitly.',
        'uses_tags': True,
        'supported_tags': STYLE_ALLOWED_TAGS['news'],
    },
    'drama_movie': {
        'label': 'Drama and Movie',
        'description': 'Hyper-cinematic with hard emotional contrast, whispers, peaks, and tension. Supported tags are only used when written explicitly.',
        'uses_tags': True,
        'supported_tags': STYLE_ALLOWED_TAGS['drama_movie'],
    },
    'sad': {
        'label': 'Sad',
        'description': 'Breaking, grief-heavy, crying-adjacent speech with breathy collapse. Supported tags are only used when written explicitly.',
        'uses_tags': True,
        'supported_tags': STYLE_ALLOWED_TAGS['sad'],
    },
    'happy': {
        'label': 'Happy',
        'description': 'Bubbly, elevated, playful, and giggly. Supported tags are only used when written explicitly.',
        'uses_tags': True,
        'supported_tags': STYLE_ALLOWED_TAGS['happy'],
    },
    'charming_attractive': {
        'label': 'Charming and Attractive',
        'description': 'Slow, teasing, sensual, breathy, and magnetically playful. Supported tags are only used when written explicitly.',
        'uses_tags': True,
        'supported_tags': STYLE_ALLOWED_TAGS['charming_attractive'],
    },
}


@dataclass
class SegmentPlan:
    index: int
    text: str
    pause_ms: int
    style_strength: float
    mode_hint: str


@dataclass
class StyleCompileResult:
    styled_text: str
    applied_tags: list[str]
    generation_params: dict[str, float | int]
    style: StyleLiteral
    warnings: list[str]
    disfluency_edits: list[str]


def clamp_qwen_speed(speed: float) -> float:
    return max(0.7, min(1.3, float(speed)))


def normalize_style(style: str | None) -> tuple[StyleLiteral, list[str]]:
    warnings: list[str] = []
    raw = (style or '').strip().lower()
    if raw in STYLE_CATALOG:
        return raw, warnings  # type: ignore[return-value]
    legacy = {
        'natural': 'natural',
        'cinematic': 'drama_movie',
        'podcast': 'natural',
        'storytelling': 'drama_movie',
        'news': 'news',
        'dramatic': 'drama_movie',
    }
    mapped = legacy.get(raw)
    if mapped:
        warnings.append(f"Mapped legacy style '{raw}' to '{mapped}'")
        return mapped, warnings  # type: ignore[return-value]
    warnings.append(f"Unknown style '{style}', defaulted to natural")
    return 'natural', warnings


def plan_tts_segments(text: str, style: str | None) -> tuple[list[SegmentPlan], StyleLiteral, list[str]]:
    style_id, warnings = normalize_style(style)
    cleaned = _normalize_base_text(text)
    sentence_candidates = [part.strip() for part in re.split(r'(?<=[.!?])\s+', cleaned) if part.strip()]
    clauses: list[str] = []
    for sentence in sentence_candidates:
        clauses.extend(_split_clause(sentence))
    segments: list[SegmentPlan] = []
    for idx, clause in enumerate(clauses):
        pause_ms = _pause_for_segment(clause, style_id)
        style_strength = _segment_style_strength(style_id, idx, len(clauses))
        mode_hint = 'normal'
        if style_id == 'drama_movie' and idx % 3 == 1:
            mode_hint = 'hushed'
        elif style_id == 'drama_movie' and idx % 3 == 2:
            mode_hint = 'peak'
        elif style_id == 'sad':
            mode_hint = 'fragile'
        elif style_id == 'happy':
            mode_hint = 'bright'
        elif style_id == 'news':
            mode_hint = 'dominant'
        elif style_id == 'charming_attractive':
            mode_hint = 'teasing'
        segments.append(
            SegmentPlan(
                index=idx,
                text=clause,
                pause_ms=pause_ms,
                style_strength=style_strength,
                mode_hint=mode_hint,
            )
        )
    return segments or [SegmentPlan(index=0, text=cleaned, pause_ms=SEGMENT_BASE_PAUSE_MS, style_strength=1.0, mode_hint='normal')], style_id, warnings


def compile_style_text(
    text: str,
    style: str | None,
    style_strength: float = 1.0,
    *,
    allow_auto_inject: bool = False,
    render_mode: str = 'final',
    segment_index: int = 0,
) -> StyleCompileResult:
    style_id, warnings = normalize_style(style)
    clean = _normalize_base_text(text)
    clean = _sanitize_tag_sequence(clean)
    clean = _sanitize_allowed_tags(clean, allowed_tags=set(STYLE_ALLOWED_TAGS[style_id]))
    strength = max(0.0, min(1.2, float(style_strength)))

    clean = _shape_punctuation(clean, style_id, segment_index)
    disfluency_edits: list[str] = []
    if allow_auto_inject:
        clean, disfluency_edits = _apply_disfluency(clean, style_id, segment_index)
        clean = _inject_style_tags(clean, style_id, strength, segment_index)

    applied_tags = _extract_tags(clean)
    params = _generation_params(style_id, strength, render_mode=render_mode)
    return StyleCompileResult(
        styled_text=clean,
        applied_tags=applied_tags,
        generation_params=params,
        style=style_id,
        warnings=warnings,
        disfluency_edits=disfluency_edits,
    )


def canonicalize_tag(raw: str) -> str:
    token = raw.strip().lower()
    if token.startswith('[') and token.endswith(']'):
        token = token[1:-1].strip()
    token = re.sub(r'\s+', ' ', token)
    return f'[{token}]'


def _normalize_base_text(text: str) -> str:
    normalized = ' '.join((text or '').split())
    if not normalized:
        return 'Hello.'
    return normalized


def _split_clause(text: str) -> list[str]:
    chunks: list[str] = []
    pending = text.strip()
    if len(pending) <= SEGMENT_MAX_CHARS:
        return [pending]
    for piece in re.split(r'(?<=[,;:])\s+|\s+(?=but\s|and\s|because\s|while\s|when\s|if\s)', pending, flags=re.IGNORECASE):
        piece = piece.strip()
        if not piece:
            continue
        if len(piece) <= SEGMENT_TARGET_CHARS:
            chunks.append(piece)
            continue
        words = piece.split()
        bucket: list[str] = []
        char_count = 0
        for word in words:
            bucket.append(word)
            char_count += len(word) + 1
            if char_count >= SEGMENT_TARGET_CHARS:
                chunks.append(' '.join(bucket).strip())
                bucket = []
                char_count = 0
        if bucket:
            chunks.append(' '.join(bucket).strip())
    return chunks or [pending]


def _pause_for_segment(text: str, style: StyleLiteral) -> int:
    pause = SEGMENT_BASE_PAUSE_MS
    if text.endswith('?'):
        pause += 70
    elif text.endswith('!'):
        pause += 45
    elif text.endswith('...'):
        pause += 140
    elif text.endswith(','):
        pause += 30
    if style == 'sad':
        pause += 120
    elif style == 'charming_attractive':
        pause += 70
    elif style == 'news':
        pause = max(90, pause - 25)
    return pause


def _segment_style_strength(style: StyleLiteral, index: int, total: int) -> float:
    if total <= 1:
        return 1.0
    if style == 'drama_movie':
        pattern = [0.85, 1.15, 0.75, 1.1]
        return pattern[index % len(pattern)]
    if style == 'sad':
        return 0.95 if index == 0 else 1.05
    if style == 'happy':
        return 1.05 if index % 2 == 0 else 0.95
    if style == 'news':
        return 0.9
    if style == 'charming_attractive':
        return 0.96 if index % 2 == 0 else 1.04
    return 1.0


def _shape_punctuation(text: str, style: StyleLiteral, segment_index: int) -> str:
    clean = text.strip()
    if style == 'news':
        clean = clean.replace('!', '.').replace('?', '.')
        clean = re.sub(r'\s*,\s*', ', ', clean)
    elif style == 'sad':
        clean = re.sub(r'!+', '...', clean)
        if ',' in clean and '...' not in clean:
            clean = clean.replace(',', ', ...', 1)
    elif style == 'happy':
        if '!' not in clean and segment_index % 2 == 0:
            clean = clean.rstrip('. ') + '!'
    elif style == 'drama_movie':
        if segment_index % 3 == 1 and ',' not in clean:
            clean = clean.replace(' ', ', ', 1)
        if segment_index % 3 == 2 and not clean.endswith('!'):
            clean = clean.rstrip('. ') + '!'
    elif style == 'charming_attractive':
        clean = re.sub(r'\s*-\s*', ', ', clean)
        if ',' not in clean and len(clean.split()) > 6:
            parts = clean.split(' ', 4)
            if len(parts) >= 5:
                clean = ' '.join(parts[:4]) + ', ' + parts[4]
    if clean and clean[-1] not in '.!?':
        clean += '.'
    return clean


def _apply_disfluency(text: str, style: StyleLiteral, segment_index: int) -> tuple[str, list[str]]:
    edits: list[str] = []
    clean = text
    lower = clean.lower()
    if style == 'sad':
        if re.search(r'\bi\b', lower) and 'i... i' not in lower:
            clean = re.sub(r'\bI\b', 'I... I', clean, count=1)
            edits.append("Expanded 'I' into a breaking-start hesitation")
        elif '...' not in clean and len(clean.split()) > 8:
            clean = clean.replace(',', ', ...', 1) if ',' in clean else clean.replace(' ', ' ... ', 1)
            edits.append('Inserted grief pause')
    elif style == 'happy' and segment_index % 2 == 0 and not lower.startswith('oh'):
        clean = f'Oh, {clean[0].lower() + clean[1:]}' if clean else clean
        edits.append("Inserted bright opener 'Oh'")
    elif style == 'drama_movie' and len(clean.split()) > 7:
        if segment_index % 3 == 1 and 'I mean' not in clean:
            clean = re.sub(r'^([A-Z][^ ]+)', r'\1... \1', clean, count=1)
            edits.append('Inserted dramatic false start')
        elif segment_index % 3 == 2 and 'listen,' not in lower:
            clean = f'Listen, {clean[0].lower() + clean[1:]}' if clean else clean
            edits.append("Inserted confrontational lead-in 'Listen'")
    elif style == 'charming_attractive' and not lower.startswith('mm'):
        clean = f'Mm, {clean[0].lower() + clean[1:]}' if clean else clean
        edits.append("Inserted breathy opener 'Mm'")
    return clean, edits


def _inject_style_tags(text: str, style: StyleLiteral, strength: float, segment_index: int) -> str:
    allowed = STYLE_ALLOWED_TAGS[style]
    out = text
    tag: str | None = None
    if style == 'natural':
        if segment_index == 0 and strength < 0.95:
            tag = '[clear throat]'
    elif style == 'news':
        tag = '[clear throat]' if segment_index == 0 else None
    elif style == 'sad':
        tag = '[sniff]' if segment_index % 2 == 0 else '[sigh]'
    elif style == 'happy':
        tag = '[chuckle]' if segment_index % 2 == 0 else '[laugh]'
    elif style == 'drama_movie':
        pattern = ['[gasp]', '[shush]', '[groan]', '[sigh]']
        tag = pattern[segment_index % len(pattern)]
    elif style == 'charming_attractive':
        pattern = ['[shush]', '[chuckle]', '[sigh]']
        tag = pattern[segment_index % len(pattern)]
    if tag and tag in allowed and tag not in out:
        out = f'{tag} {out}'
    return _sanitize_allowed_tags(_sanitize_tag_sequence(out), allowed_tags=set(allowed))


def _sanitize_tag_sequence(text: str) -> str:
    out = text
    out = re.sub(rf'({TAG_REGEX})\s+({TAG_REGEX})', r'\1 ', out)
    out = re.sub(r'\s{2,}', ' ', out).strip()
    for bad in DISABLED_DEFAULT_TAGS:
        out = out.replace(bad, '')
    return out


def _sanitize_allowed_tags(text: str, *, allowed_tags: set[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        token = canonicalize_tag(match.group(0))
        return token if token in SAFE_STYLE_TAGS and token in allowed_tags else ''

    out = re.sub(TAG_REGEX, repl, text)
    out = re.sub(r'\s{2,}', ' ', out).strip()
    out = re.sub(r'\s+([,.;!?])', r'\1', out)
    return out


def _extract_tags(text: str) -> list[str]:
    tags = [canonicalize_tag(token) for token in re.findall(TAG_REGEX, text.lower()) if canonicalize_tag(token) in SAFE_STYLE_TAGS]
    return tags[:TAG_MAX_TOTAL]


def _generation_params(style: StyleLiteral, strength: float, *, render_mode: str) -> dict[str, float | int]:
    base_max_tokens = PREVIEW_RENDER_MAX_TOKENS if render_mode == 'preview' else FINAL_RENDER_MAX_TOKENS
    if style == 'natural':
        return {'temperature': 0.46, 'top_p': 0.76, 'repetition_penalty': 1.16, 'max_tokens': base_max_tokens}
    if style == 'news':
        return {'temperature': 0.42, 'top_p': 0.74, 'repetition_penalty': 1.2, 'max_tokens': base_max_tokens}
    if style == 'sad':
        return {'temperature': min(0.72, 0.52 + (strength * 0.08)), 'top_p': 0.84, 'repetition_penalty': 1.1, 'max_tokens': base_max_tokens}
    if style == 'happy':
        return {'temperature': min(0.88, 0.66 + (strength * 0.10)), 'top_p': 0.92, 'repetition_penalty': 1.04, 'max_tokens': base_max_tokens}
    if style == 'drama_movie':
        return {'temperature': min(0.92, 0.70 + (strength * 0.12)), 'top_p': 0.94, 'repetition_penalty': 1.02, 'max_tokens': base_max_tokens}
    return {'temperature': min(0.82, 0.60 + (strength * 0.08)), 'top_p': 0.90, 'repetition_penalty': 1.05, 'max_tokens': base_max_tokens}
