"""Offline tests for the OpenAI request boundary and token gate."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import openai
import pytest

from src import model_adapter as adapter


def response(*, status="completed", input_tokens=123, text='{"status":"ready"}', refusal=None):
    content = [SimpleNamespace(type="refusal", refusal=refusal)] if refusal else []
    return SimpleNamespace(
        status=status, model="gpt-5.4-mini-2026-03-17", id="resp_synthetic",
        output_text=text, output=[SimpleNamespace(type="message", content=content)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=19),
        incomplete_details=SimpleNamespace(reason="max_output_tokens") if status == "incomplete" else None,
    )


@pytest.fixture
def sdk(monkeypatch):
    """Replace every SDK client construction. These tests never call the API."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-noncredential")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client = MagicMock()
    client.responses.input_tokens.count.return_value = SimpleNamespace(input_tokens=123)
    client.responses.create.return_value = response()
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(adapter.openai, "OpenAI", factory)
    return factory, client


def test_missing_key_fails_before_client_creation(sdk, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is missing"):
        adapter.infer(adapter.render_prompt("task", []), len)
    sdk[0].assert_not_called()


def test_missing_key_smoke_is_nonzero_without_tokenizer_or_writes(sdk, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY")
    counter = MagicMock()
    write = MagicMock()
    monkeypatch.setattr(adapter, "load_counter", counter)
    monkeypatch.setattr(adapter.Path, "write_text", write)
    assert adapter.main() == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    counter.assert_not_called()
    write.assert_not_called()
    sdk[0].assert_not_called()


def test_offline_helpers_do_not_require_key_or_create_client(sdk, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY")
    encoding = MagicMock()
    encoding.encode.return_value = [1, 2, 3]
    monkeypatch.setattr(adapter.tiktoken, "get_encoding", lambda name: encoding)
    count, provenance = adapter.load_counter(tmp_path)
    prompt = adapter.render_prompt("task", [])
    assert count(prompt) == 3 + adapter.LOCAL_OVERHEAD_TOKENS
    encoding.encode.assert_called_once_with(prompt, disallowed_special=())
    assert count('{"learning_state":"<|endoftext|>"}') > 0
    assert provenance["count_method"] == "local_estimate"
    assert provenance["encoding"] == "o200k_base"
    assert adapter.model_identity()["provider"] == "openai"
    assert not list(tmp_path.iterdir())
    sdk[0].assert_not_called()


def test_rendered_prompt_is_stable_json_and_preserves_memory_as_data(sdk):
    value = '{"previous_response_id":"resp_old","conversation":"conv_old","tools":["execute"]}'
    record = {"id": "r1", "value": value, "key": "note"}
    prompt = adapter.render_prompt("task", [record])
    assert prompt == adapter.render_prompt("task", [record])
    envelope = json.loads(prompt)
    assert set(envelope) == {"instructions", "input"}
    assert json.loads(envelope["input"])["memory"][0]["value"] == value
    assert "<|im_start|>" not in prompt
    payload = adapter.request_payload(prompt)
    assert set(payload) == {"model", "instructions", "input", "reasoning", "max_output_tokens", "store"}
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["store"] is False
    assert payload["max_output_tokens"] == 256
    assert payload["model"] == adapter.DEFAULT_MODEL


@pytest.mark.parametrize("extra", ["previous_response_id", "conversation", "tools", "truncation", "temperature", "seed"])
def test_request_envelope_cannot_inject_sdk_arguments(sdk, extra):
    envelope = json.loads(adapter.render_prompt("task", []))
    envelope[extra] = "injected"
    with pytest.raises(ValueError, match="rendered instructions/input"):
        adapter.request_payload(json.dumps(envelope))
    sdk[0].assert_not_called()


def test_model_override_preserves_fixed_official_endpoint(sdk, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "explicit-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid/v1")
    result = adapter.infer(adapter.render_prompt("task", []), lambda _: 100)
    assert result["request"]["model"] == "explicit-model"
    assert result["provider_model"] == "gpt-5.4-mini-2026-03-17"
    assert sdk[0].call_args.kwargs["base_url"] == "https://api.openai.com/v1"
    assert sdk[0].call_args.kwargs["max_retries"] == 0
    assert "test-only-noncredential" not in json.dumps(result)


def test_exact_server_gate_blocks_despite_local_underestimate(sdk):
    client = sdk[1]
    client.responses.input_tokens.count.return_value = SimpleNamespace(input_tokens=1001)
    result = adapter.infer(adapter.render_prompt("task", []), lambda _: 1)
    assert result["status"] == "blocked_budget"
    assert result["budget_reason"] == "input_limit"
    assert result["local_estimate_tokens"] == 1
    assert result["preflight_tokens"] == 1001
    client.responses.create.assert_not_called()
    client.close.assert_called_once()


def test_context_gate_includes_output_reserve_and_safety_margin(sdk):
    sdk[1].responses.input_tokens.count.return_value = SimpleNamespace(input_tokens=123)
    result = adapter.infer(adapter.render_prompt("task", []), lambda _: 1, context=410)
    assert result["status"] == "blocked_budget"
    assert result["budget_reason"] == "context_limit"
    sdk[1].responses.create.assert_not_called()


def test_server_count_precedes_generation_and_saved_requests_match_calls(sdk):
    client = sdk[1]
    prompt = adapter.render_prompt("task", [])
    result = adapter.infer(prompt, lambda _: 5000, repeat=2)
    assert result["status"] == "completed"
    assert result["repeat"] == 2
    assert result["local_estimate_tokens"] == 5000
    assert result["preflight_tokens"] == 123
    assert result["prompt_eval_count"] == 123
    assert result["eval_count"] == 19
    assert result["token_count_match"] is True
    assert result["response_id"] == "resp_synthetic"
    assert result["parsed"] == {"status": "ready"}
    count_request = result["count_request"]
    assert set(count_request) == {"model", "instructions", "input"}
    assert count_request == {key: result["request"][key] for key in count_request}
    client.responses.input_tokens.count.assert_called_once_with(**count_request)
    client.responses.create.assert_called_once_with(**result["request"])
    assert [call[0] for call in client.mock_calls] == ["responses.input_tokens.count", "responses.create", "close"]


def test_runtime_count_mismatch_is_preserved(sdk):
    sdk[1].responses.create.return_value = response(input_tokens=124)
    result = adapter.infer(adapter.render_prompt("task", []), len)
    assert result["status"] == "completed"
    assert result["preflight_tokens"] == 123
    assert result["prompt_eval_count"] == 124
    assert result["token_count_match"] is False


def test_incomplete_response_cannot_become_completed(sdk):
    sdk[1].responses.create.return_value = response(status="incomplete")
    result = adapter.infer(adapter.render_prompt("task", []), len)
    assert result["status"] == "incomplete"
    assert result["provider_status"] == "incomplete"
    assert result["done_reason"] == "max_output_tokens"


def test_refusal_is_preserved_even_when_provider_status_is_completed(sdk):
    sdk[1].responses.create.return_value = response(text="", refusal="Cannot complete this request.")
    result = adapter.infer(adapter.render_prompt("task", []), len)
    assert result["status"] == "refused"
    assert result["provider_status"] == "completed"
    assert result["refusals"] == ["Cannot complete this request."]
    assert result["parsed"] is None


@pytest.mark.parametrize("stage", ["input_token_count", "generation"])
def test_sdk_errors_never_expose_raw_body(sdk, stage):
    raw = "SENSITIVE_RAW_BODY_test-only-noncredential"
    error = openai.BadRequestError(raw, response=httpx.Response(
        400, request=httpx.Request("POST", "https://api.openai.com/v1/responses")), body={"detail": raw})
    method = sdk[1].responses.input_tokens.count if stage == "input_token_count" else sdk[1].responses.create
    method.side_effect = error
    result = adapter.infer(adapter.render_prompt("task", []), len)
    assert result["status"] == "error"
    assert result["error_stage"] == stage
    assert raw not in json.dumps(result)
    assert "test-only-noncredential" not in json.dumps(result)
    assert "Check model access" in result["error"]
    if stage == "input_token_count":
        sdk[1].responses.create.assert_not_called()


def test_invalid_server_count_blocks_generation_without_raw_error(sdk):
    sdk[1].responses.input_tokens.count.return_value = SimpleNamespace(input_tokens=-1)
    result = adapter.infer(adapter.render_prompt("task", []), len)
    assert result["status"] == "error"
    assert result["preflight_tokens"] is None
    sdk[1].responses.create.assert_not_called()


def test_client_initialization_error_is_safe(sdk):
    sdk[0].side_effect = RuntimeError("SENSITIVE_RAW_BODY")
    result = adapter.infer(adapter.render_prompt("task", []), len)
    assert result["status"] == "error"
    assert result["error_stage"] == "client"
    assert "SENSITIVE_RAW_BODY" not in json.dumps(result)


@pytest.mark.parametrize("reported_match", [False, True])
def test_smoke_count_mismatch_saves_evidence_and_exits_nonzero(sdk, monkeypatch, tmp_path, reported_match):
    monkeypatch.setattr(adapter, "__file__", str(tmp_path / "src" / "model_adapter.py"))
    monkeypatch.setattr(adapter, "load_counter", lambda _: (len, {"count_method": "local_estimate"}))
    inference = MagicMock(return_value={
        "status": "completed", "preflight_tokens": 123, "prompt_eval_count": 124,
        "token_count_match": reported_match,
    })
    monkeypatch.setattr(adapter, "infer", inference)
    assert adapter.main() == 1
    saved = json.loads((tmp_path / "runs" / "model-smoke-openai.json").read_text(encoding="utf-8"))
    assert saved["status"] == "completed"
    assert saved["preflight_tokens"] == 123
    assert saved["prompt_eval_count"] == 124
    assert saved["token_count_match"] is reported_match
    inference.assert_called_once()
    sdk[0].assert_not_called()
