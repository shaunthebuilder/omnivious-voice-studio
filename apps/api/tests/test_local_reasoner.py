from app.local_reasoner import LocalReasonerClient


def test_single_pass_enhance_calls_generate_once(monkeypatch) -> None:
    client = LocalReasonerClient(model_id="dummy/model")
    calls: list[int] = []

    monkeypatch.setattr(client, "ensure_loaded", lambda: None)
    monkeypatch.setattr("app.local_reasoner.LLM_OUTPUT_GROWTH_CAP_RATIO", 4.0)

    def fake_generate_json(*, prompt: str, text: str, max_tokens: int):
        calls.append(1)
        return {
            "enhanced_text": "[clear throat] Well, we should proceed. [laugh]",
            "applied_tags": ["[clear throat]", "[laugh]"],
            "analysis": "single pass ok",
            "disfluency_edits": ["Inserted 'Well' opener"],
        }

    monkeypatch.setattr(client, "_generate_json", fake_generate_json)
    result = client.single_pass_enhance(
        text="We should proceed.",
        style="news",
    )

    assert len(calls) == 1
    assert result.enhanced_text
    # news style does not allow [laugh], so sanitizer must remove it.
    assert "[laugh]" not in result.enhanced_text
    assert "[clear throat]" in result.enhanced_text
    assert result.disfluency_edits == ["Inserted 'Well' opener"]
