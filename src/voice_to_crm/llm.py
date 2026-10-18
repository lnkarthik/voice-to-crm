import json
import subprocess
import time
from typing import Protocol


class LLMError(Exception):
    """The LLM step failed (CLI error, timeout, or unparseable output)."""


class LLMBackend(Protocol):
    """A backend for the LLM step."""

    def complete_json(self, prompt: str, schema: dict) -> dict:
        """Complete a prompt and return a JSON object matching the schema."""
        ...


class ClaudeCLIBackend:
    """A backend that calls the Claude CLI."""

    def __init__(
        self,
        model: str = "sonnet",
        timeout_s: float = 180,
        retries: int = 2,
        runner=subprocess.run,
        sleep=time.sleep,
    ):
        self.model = model
        self.timeout_s = timeout_s
        self.retries = retries
        self.runner = runner
        self.sleep = sleep

    def complete_json(self, prompt: str, schema: dict) -> dict:
        argv = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema),
            "--model",
            self.model,
        ]
        attempts = 1 + self.retries
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                proc = self.runner(
                    argv, capture_output=True, text=True, timeout=self.timeout_s
                )
                if proc.returncode != 0:
                    raise LLMError(
                        f"claude exited {proc.returncode}: {proc.stderr.strip()[:200]}"
                    )
                return parse_cli_output(proc.stdout)
            except (subprocess.TimeoutExpired, LLMError) as e:
                last_error = e
                if attempt < attempts - 1:
                    self.sleep(2**attempt)
        raise LLMError(f"LLM failed after {attempts} attempts: {last_error}")


def parse_cli_output(stdout: str) -> dict:
    """Extract the model's JSON object from `claude -p --output-format json` stdout."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"CLI output is not JSON: {e}") from e

    if envelope.get("is_error"):
        raise LLMError(f"CLI reported an error: {envelope.get('result')}")

    if envelope.get("structured_output") is not None:
        return envelope["structured_output"]

    text = envelope.get("result") or ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMError(f"No JSON object in CLI result: {text[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"Unparseable JSON in CLI result: {e}") from e


class FakeLLM:
    """A scripted backend for tests: returns canned responses in order."""

    def __init__(self, responses: list[dict | str]):
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.schemas: list[dict] = []

    def complete_json(self, prompt: str, schema: dict) -> dict:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        if not self.responses:
            raise LLMError("FakeLLM has no responses left")
        response = self.responses.pop(0)
        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError as e:
                raise LLMError(f"FakeLLM response is not JSON: {e}") from e
        return response
