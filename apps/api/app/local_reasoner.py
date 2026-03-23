from __future__ import annotations

import json
import re
import threading
import gc
from dataclasses import dataclass
from pathlib import Path

from .config import (
    LLM_OUTPUT_GROWTH_CAP_RATIO,
    LLM_EDIT_BUDGET_RATIO,
    MLX_REASONING_MODEL,
    REASONER_DISFLUENCY_LEVEL,
    REASONER_MAX_TOKENS_LONG,
    REASONER_MAX_TOKENS_MEDIUM,
    REASONER_MAX_TOKENS_SHORT,
    REASONER_MAX_TOKENS_XLONG,
    REASONER_MODE,
    REASONER_TEMPERATURE,
    REASONER_TOP_P,
    TAG_MAX_PER_SENTENCE,
    TAG_MAX_TOTAL,
)
from .style_compiler import (
    SAFE_STYLE_TAGS,
    STYLE_ALLOWED_TAGS,
    StyleLiteral,
    canonicalize_tag,
)

TAG_REGEX = r"\[[a-z ]+\]"

STYLE_INTENT: dict[StyleLiteral, str] = {
    "natural": "Neutral and grounded. Closest to base speaker identity with restrained expression.",
    "sad": "Intense grief and heartbreak with breaking voice and breath-heavy sorrow.",
    "news": "Dominant political-news delivery: commanding, confident, sharp, slightly confrontational.",
    "happy": "Bubbly, euphoric, playful energy with lively cadence.",
    "drama_movie": "Hyper-cinematic, high contrast delivery with whispers and explosive peaks.",
    "charming_attractive": "Charming, sensual, teasing, magnetic, tasteful non-explicit intimacy.",
}


class LocalReasonerStatus:
    def __init__(self, *, ready: bool, model: str, detail: str | None = None) -> None:
        self.ready = ready
        self.model = model
        self.detail = detail


class LocalReasonerError(Exception):
    pass


@dataclass
class EnhancedTextResult:
    original_text: str
    enhanced_text: str
    analysis: str
    applied_tags: list[str]
    disfluency_edits: list[str]


class LocalReasonerClient:
    def __init__(self, model_id: str = MLX_REASONING_MODEL) -> None:
        self.model_id = model_id
        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()

    def ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        with self._lock:
            if self._model is not None and self._tokenizer is not None:
                return
            try:
                from mlx_lm import load
            except Exception as exc:
                raise LocalReasonerError("mlx_lm is unavailable for local reasoning") from exc
            try:
                model, tokenizer = load(self.model_id)
            except Exception:
                try:
                    from mlx_lm.utils import _download, load_model, load_tokenizer

                    model_path = _download(self.model_id)
                    model, config = load_model(model_path, strict=False)
                    tokenizer = load_tokenizer(
                        model_path,
                        eos_token_ids=config.get("eos_token_id", None),
                    )
                except Exception as exc:
                    raise LocalReasonerError(f"Failed to load reasoning model '{self.model_id}'") from exc
            self._model = model
            self._tokenizer = tokenizer

    def status(self) -> LocalReasonerStatus:
        if self._model is not None and self._tokenizer is not None:
            return LocalReasonerStatus(ready=True, model=self.model_id)
        try:
            import mlx_lm  # noqa: F401
        except Exception as exc:
            return LocalReasonerStatus(ready=False, model=self.model_id, detail=f"mlx_lm import failed: {exc}")
        if self._is_model_cached(self.model_id):
            return LocalReasonerStatus(ready=True, model=self.model_id, detail="Model cached; lazy-load on first use.")
        return LocalReasonerStatus(
            ready=False,
            model=self.model_id,
            detail=f"Model '{self.model_id}' not found in local HuggingFace cache.",
        )

    def single_pass_enhance(self, *, text: str, style: StyleLiteral) -> EnhancedTextResult:
        self.ensure_loaded()
        clean = " ".join((text or "").split()).strip()
        if not clean:
            raise LocalReasonerError("Input text is empty.")

        if REASONER_MODE != "single_pass":
            raise LocalReasonerError("Unsupported reasoner mode")

        allowed_tags = STYLE_ALLOWED_TAGS.get(style, STYLE_ALLOWED_TAGS["natural"])
        style_intent = STYLE_INTENT.get(style, STYLE_INTENT["natural"])
        edit_budget = max(0.03, min(0.4, float(LLM_EDIT_BUDGET_RATIO)))
        max_edits = max(2, min(16, int(round(len(clean) * edit_budget / 8))))
        prompt = (
            "Task: In one pass, enhance the script for natural speech performance.\n"
            f"Style target: {style}\n"
            f"Style intent: {style_intent}\n"
            f"Disfluency level: {REASONER_DISFLUENCY_LEVEL}\n"
            f"Allowed tags for this style: {', '.join(allowed_tags)}\n"
            f"Model supported tags (global): {', '.join(sorted(SAFE_STYLE_TAGS))}\n"
            "Requirements:\n"
            "1) Keep semantic meaning and named entities intact.\n"
            "2) Add sparse tags only from the allowed style list.\n"
            "3) Add moderate human hesitations/disfluencies (e.g. um, uh, well, you know, false starts) naturally.\n"
            "4) No sentence reordering.\n"
            f"5) Edit budget is capped; keep <= {max_edits} meaningful micro-edits.\n"
            f"6) Hard caps: <= {TAG_MAX_PER_SENTENCE} tag per sentence, <= {TAG_MAX_TOTAL} tags total.\n"
            "7) Keep output concise; do not expand exposition.\n"
            "Return strict JSON with keys: enhanced_text, applied_tags, analysis, disfluency_edits.\n"
            "applied_tags must be an array of tags; disfluency_edits must be an array of concise edit notes.\n"
            "analysis must be <= 20 words and disfluency_edits must contain <= 8 short items."
        )

        result = self._generate_json(
            prompt=prompt,
            text=clean,
            max_tokens=self._max_tokens_for_script(clean),
        )
        enhanced_raw = str(result.get("enhanced_text", clean))
        enhanced = self._sanitize_enhanced_text(enhanced_raw, allowed_tags=set(allowed_tags))
        max_growth_ratio = max(1.0, float(LLM_OUTPUT_GROWTH_CAP_RATIO))
        growth_ratio = len(enhanced) / max(1, len(clean))
        growth_cap_triggered = growth_ratio > max_growth_ratio
        if growth_cap_triggered:
            enhanced = clean
        tags = self._extract_tags(enhanced)
        analysis = str(result.get("analysis", "")).strip()
        if growth_cap_triggered:
            suffix = f"growth cap triggered ({growth_ratio:.2f}x > {max_growth_ratio:.2f}x); fallback to original text."
            analysis = f"{analysis} {suffix}".strip()
        disfluency_edits = self._sanitize_string_array(result.get("disfluency_edits"), limit=8)
        if growth_cap_triggered:
            disfluency_edits = []
        return EnhancedTextResult(
            original_text=clean,
            enhanced_text=enhanced or clean,
            analysis=analysis,
            applied_tags=tags,
            disfluency_edits=disfluency_edits,
        )

    def release_runtime_cache(self) -> None:
        gc.collect()

    def _generate_json(self, *, prompt: str, text: str, max_tokens: int) -> dict:
        if self._model is None or self._tokenizer is None:
            raise LocalReasonerError("Reasoning model is not initialized")
        request = (
            f"{prompt}\n\nSCRIPT:\n{text}\n\n"
            "Return ONLY valid JSON. No markdown, no code fences, no prose outside JSON."
        )
        try:
            from mlx_lm import generate
            from mlx_lm.sample_utils import make_sampler
        except Exception as exc:
            raise LocalReasonerError("mlx_lm.generate is unavailable") from exc

        try:
            sampler = make_sampler(temp=REASONER_TEMPERATURE, top_p=REASONER_TOP_P)
            with self._lock:
                raw = generate(
                    self._model,
                    self._tokenizer,
                    request,
                    verbose=False,
                    max_tokens=max_tokens,
                    sampler=sampler,
                )
        except Exception as exc:
            raise LocalReasonerError(f"Local reasoning request failed: {exc}") from exc

        if not isinstance(raw, str) or not raw.strip():
            raise LocalReasonerError("Invalid reasoning output payload.")
        parsed = self._parse_json_object(raw)
        if not isinstance(parsed, dict):
            raise LocalReasonerError("Reasoning model returned non-object JSON.")
        return parsed

    def _sanitize_enhanced_text(self, text: str, *, allowed_tags: set[str]) -> str:
        out = " ".join((text or "").split()).strip()
        if not out:
            return ""

        def repl(match: re.Match[str]) -> str:
            token = canonicalize_tag(match.group(0))
            if token not in SAFE_STYLE_TAGS or token not in allowed_tags:
                return ""
            return token

        out = re.sub(TAG_REGEX, repl, out)
        out = re.sub(r"\s{2,}", " ", out).strip()
        out = re.sub(r"\s+([,.;!?])", r"\1", out)

        # Enforce per-sentence and global tag caps deterministically.
        tag_count = 0
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", out) if part.strip()]
        cleaned_sentences: list[str] = []
        for sentence in sentences:
            sentence_tags = re.findall(TAG_REGEX, sentence.lower())
            kept = 0
            if sentence_tags:
                def sentence_repl(match: re.Match[str]) -> str:
                    nonlocal tag_count, kept
                    token = canonicalize_tag(match.group(0))
                    if token not in allowed_tags:
                        return ""
                    if kept >= TAG_MAX_PER_SENTENCE or tag_count >= TAG_MAX_TOTAL:
                        return ""
                    kept += 1
                    tag_count += 1
                    return token
                sentence = re.sub(TAG_REGEX, sentence_repl, sentence)
                sentence = re.sub(r"\s{2,}", " ", sentence).strip()
            cleaned_sentences.append(sentence)
        return " ".join(cleaned_sentences).strip() or out

    def _extract_tags(self, text: str) -> list[str]:
        tags = [canonicalize_tag(token) for token in re.findall(TAG_REGEX, text.lower())]
        filtered = [tag for tag in tags if tag in SAFE_STYLE_TAGS]
        return filtered[: max(1, TAG_MAX_TOTAL)]

    def _sanitize_string_array(self, raw: object, *, limit: int) -> list[str]:
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            text = str(item).strip()
            if text:
                out.append(text)
            if len(out) >= limit:
                break
        return out

    def _max_tokens_for_script(self, text: str) -> int:
        length = len(text or "")
        if length <= 240:
            return max(32, int(REASONER_MAX_TOKENS_SHORT))
        if length <= 640:
            return max(48, int(REASONER_MAX_TOKENS_MEDIUM))
        if length <= 1500:
            return max(64, int(REASONER_MAX_TOKENS_LONG))
        return max(80, int(REASONER_MAX_TOKENS_XLONG))

    def _clear_mlx_cache(self) -> None:
        try:
            import mlx.core as mx

            mx.clear_cache()
        except Exception:
            return

    def _parse_json_object(self, raw: str) -> dict:
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).replace("```", "")
        raw = raw.strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for idx, ch in enumerate(raw):
            if ch != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(raw[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise LocalReasonerError("Reasoner returned non-JSON output.")

    def _is_model_cached(self, model_id: str) -> bool:
        cache_root = Path.home() / ".cache" / "huggingface" / "hub"
        model_dir = cache_root / f"models--{model_id.replace('/', '--')}"
        snapshots = model_dir / "snapshots"
        if not snapshots.exists() or not snapshots.is_dir():
            return False
        return any(p.is_dir() for p in snapshots.iterdir())


class LocalReasonerProbe:
    def __init__(self, client: LocalReasonerClient) -> None:
        self.client = client

    def status(self) -> LocalReasonerStatus:
        return self.client.status()


local_reasoner_client = LocalReasonerClient()
local_reasoner_probe = LocalReasonerProbe(local_reasoner_client)
