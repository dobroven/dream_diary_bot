from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from openai import BadRequestError

import ai


def test_parse_patterns_plain_array():
    raw = '[{"pattern": "полёт", "count": 2, "examples": []}]'
    assert ai._parse_patterns(raw) == [
        {"pattern": "полёт", "count": 2, "examples": []}
    ]


def test_parse_patterns_fenced_json():
    raw = '```json\n[{"pattern": "вода", "count": 3}]\n```'
    assert ai._parse_patterns(raw) == [{"pattern": "вода", "count": 3}]


def test_parse_patterns_with_explanation_around_json():
    raw = 'Вот результат анализа:\n[{"pattern": "дом", "count": 2}]\nГотово.'
    assert ai._parse_patterns(raw) == [{"pattern": "дом", "count": 2}]


def test_parse_patterns_accepts_object_with_patterns():
    raw = '{"patterns": [{"pattern": "погоня", "count": 4}]}'
    assert ai._parse_patterns(raw) == [{"pattern": "погоня", "count": 4}]


def test_parse_patterns_rejects_invalid_json():
    assert ai._parse_patterns("это не JSON") == []


def test_parse_patterns_rejects_non_list():
    assert ai._parse_patterns('{"result": "ok"}') == []


def test_validate_dream_map_filters_sorts_and_limits():
    patterns = [
        {"pattern": f"p{i}", "count": i, "examples": [], "description": ""}
        for i in range(20)
    ]

    result = ai.validate_dream_map(patterns)

    assert len(result) == 15
    assert result[0]["count"] == 19
    assert all(p["count"] >= 2 for p in result)


def test_validate_dream_map_trims_long_examples():
    patterns = [
        {
            "pattern": "тест",
            "count": 2,
            "examples": [" ".join(["слово"] * 15)],
            "description": "описание",
        }
    ]

    result = ai.validate_dream_map(patterns)

    assert result[0]["examples"][0].endswith("…")
    assert len(result[0]["examples"][0].split()) == 10


def test_validate_dream_map_handles_bad_fields():
    patterns = [
        {"pattern": "норма", "count": "3", "examples": ["пример"], "description": None},
        {"pattern": "плохой count", "count": "много", "examples": []},
        {"pattern": "мало", "count": 1, "examples": []},
    ]

    result = ai.validate_dream_map(patterns)

    assert len(result) == 1
    assert result[0]["count"] == 3
    assert result[0]["description"] == ""


def test_generate_dream_map_uses_parser():
    dreams = [
        {
            "date": "2026-01-01",
            "title": "Первый",
            "description": "Я летал над городом.",
        },
        {
            "date": "2026-01-02",
            "title": "Второй",
            "description": "Снова летал над морем.",
        },
    ]
    raw = '```json\n[{"pattern": "полёт", "count": 2, "examples": ["летал"]}]\n```'

    with patch("ai.db.list_dreams_for_map", return_value=dreams), \
         patch("ai._call_llm", return_value=raw):
        patterns, analyzed = ai.generate_dream_map(1)

    assert analyzed == 2
    assert len(patterns) == 1
    assert patterns[0]["pattern"] == "полёт"


def test_get_client_requires_api_key(monkeypatch):
    monkeypatch.setattr(ai, "_client", None)
    monkeypatch.delenv("ZVENOAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ZVENOAI_API_KEY"):
        ai._get_client()


class _FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=response))]
        )


def _fake_client(responses):
    completions = _FakeCompletions(responses)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    return client, completions


def _bad_request(message: str) -> BadRequestError:
    request = httpx.Request("POST", "https://api.zveno.ai/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return BadRequestError(message, response=response, body=None)


def test_call_llm_sends_reasoning_and_returns_content():
    client, completions = _fake_client(["ответ"])

    with patch("ai._get_client", return_value=client):
        result = ai._call_llm("system", "user", ai.DREAM_MAP_MODEL)

    assert result == "ответ"
    call = completions.calls[0]
    assert call["model"] == ai.DREAM_MAP_MODEL
    assert call["temperature"] == 0.2
    assert call["extra_body"] == {"reasoning": {"effort": "low"}}


def test_call_llm_retries_without_reasoning_on_bad_request():
    client, completions = _fake_client([
        _bad_request("reasoning is not supported for this model"),
        "ответ без reasoning",
    ])

    with patch("ai._get_client", return_value=client):
        result = ai._call_llm("system", "user", ai.DREAM_MAP_MODEL)

    assert result == "ответ без reasoning"
    assert len(completions.calls) == 2
    assert "extra_body" not in completions.calls[1]

