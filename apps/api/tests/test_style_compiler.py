from app.style_compiler import (
    DISABLED_DEFAULT_TAGS,
    SAFE_STYLE_TAGS,
    TAG_MAX_TOTAL,
    canonicalize_tag,
    clamp_qwen_speed,
    compile_style_text,
)


def test_style_compiler_only_emits_allowed_tags() -> None:
    result = compile_style_text(
        "The city sleeps, but this story does not. Listen closely as the night unfolds.",
        "drama_movie",
        style_strength=1.0,
    )
    assert result.style == "drama_movie"
    assert all(tag in SAFE_STYLE_TAGS for tag in result.applied_tags)
    assert all(tag not in result.styled_text for tag in DISABLED_DEFAULT_TAGS)


def test_style_compiler_does_not_auto_inject_nonverbal_cues() -> None:
    text = "I will stay with you through the night."

    for style in ["charming_attractive", "happy", "sad", "drama_movie"]:
        result = compile_style_text(text, style, style_strength=1.0)
        assert result.applied_tags == []
        assert result.disfluency_edits == []
        assert "[" not in result.styled_text
        assert "Mm," not in result.styled_text
        assert "Oh," not in result.styled_text
        assert "Listen," not in result.styled_text
        assert "I... I" not in result.styled_text


def test_style_compiler_respects_tag_density_budget() -> None:
    text = " ".join(["[laugh] hello"] * 220) + "."
    result = compile_style_text(text, "happy", style_strength=1.0)
    # hard-capped by style compiler to avoid identity drift.
    assert len(result.applied_tags) <= TAG_MAX_TOTAL


def test_style_compiler_keeps_supported_multi_word_tag_only() -> None:
    result = compile_style_text(
        "[clear throat] We begin now. [music] This should disappear.",
        "news",
        style_strength=1.0,
    )
    assert "[clear throat]" in result.styled_text
    assert "[music]" not in result.styled_text
    assert canonicalize_tag("[clear   throat]") == "[clear throat]"


def test_clamp_speed_bounds() -> None:
    assert clamp_qwen_speed(0.2) == 0.7
    assert clamp_qwen_speed(1.08) == 1.08
    assert clamp_qwen_speed(2.0) == 1.3
