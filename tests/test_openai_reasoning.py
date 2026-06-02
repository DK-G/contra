"""Tests for reasoning-model payload sanitization and usage accounting."""

import src.openai_client as oc
from src.openai_client import _is_reasoning_model, _sanitize_payload, get_usage, reset_usage


def test_reasoning_model_detection():
    assert _is_reasoning_model("o4-mini")
    assert _is_reasoning_model("o3-mini")
    assert _is_reasoning_model("o1")
    assert not _is_reasoning_model("gpt-4o-mini")
    assert not _is_reasoning_model("gpt-4.1")
    assert not _is_reasoning_model("")


def test_sanitize_strips_temperature_for_reasoning_models():
    payload = {"model": "o4-mini", "input": [], "temperature": 0.0, "top_p": 1}
    cleaned = _sanitize_payload(payload)
    assert "temperature" not in cleaned
    assert "top_p" not in cleaned
    assert cleaned["model"] == "o4-mini"
    # original is not mutated
    assert "temperature" in payload


def test_sanitize_keeps_temperature_for_chat_models():
    payload = {"model": "gpt-4o-mini", "input": [], "temperature": 0.4}
    cleaned = _sanitize_payload(payload)
    assert cleaned["temperature"] == 0.4
    assert cleaned is payload  # unchanged -> same object


def test_usage_accumulation_includes_reasoning_tokens():
    reset_usage()
    oc._accumulate_usage({
        "usage": {
            "input_tokens": 100,
            "output_tokens": 250,
            "output_tokens_details": {"reasoning_tokens": 200},
        }
    })
    oc._accumulate_usage({"usage": {"input_tokens": 50, "output_tokens": 30}})
    u = get_usage()
    assert u["calls"] == 2
    assert u["input_tokens"] == 150
    assert u["output_tokens"] == 280
    assert u["reasoning_tokens"] == 200
    reset_usage()
    assert get_usage()["calls"] == 0
