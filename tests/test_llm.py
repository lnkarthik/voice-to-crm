import json
import subprocess

import pytest

from voice_to_crm.llm import ClaudeCLIBackend, FakeLLM, LLMError, parse_cli_output


def test_parse_structured_output():
    stdout = '{"is_error": false, "structured_output": {"a": 1}, "result": ""}'
    assert parse_cli_output(stdout) == {"a": 1}


def test_parse_fenced_result_string():
    result = 'Here you go:\n```json\n{"a": 1}\n```'
    stdout = json.dumps({"is_error": False, "result": result})
    assert parse_cli_output(stdout) == {"a": 1}


def test_parse_error_flag_raises():
    stdout = '{"is_error": true, "result": "rate limited"}'
    with pytest.raises(LLMError):
        parse_cli_output(stdout)


def test_cli_argv_and_retry():
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        if len(calls) < 3:
            raise subprocess.TimeoutExpired(argv, 1)
        return subprocess.CompletedProcess(
            argv, 0, stdout='{"structured_output": {"a": 1}}', stderr=""
        )

    backend = ClaudeCLIBackend(runner=runner, sleep=lambda s: None)
    assert backend.complete_json("hi", {"type": "object"}) == {"a": 1}
    assert calls[0][:2] == ["claude", "-p"]
    assert "--json-schema" in calls[0]
    assert "--model" in calls[0]
    assert len(calls) == 3


def test_cli_gives_up_after_retries():
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="boom")

    backend = ClaudeCLIBackend(runner=runner, sleep=lambda s: None)
    with pytest.raises(LLMError):
        backend.complete_json("hi", {})
    assert len(calls) == 3


def test_fake_llm_returns_responses_in_order_and_records_calls():
    fake = FakeLLM([{"a": 1}, '{"b": 2}'])
    assert fake.complete_json("p1", {"s": 1}) == {"a": 1}
    assert fake.complete_json("p2", {"s": 2}) == {"b": 2}
    assert fake.prompts == ["p1", "p2"]
    assert fake.schemas == [{"s": 1}, {"s": 2}]


def test_fake_llm_bad_json_string_raises():
    with pytest.raises(LLMError):
        FakeLLM(["not json"]).complete_json("p", {})


@pytest.mark.live
def test_live_claude_cli():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    assert ClaudeCLIBackend().complete_json("Return name=Ada", schema) == {
        "name": "Ada"
    }
