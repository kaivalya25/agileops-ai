"""Typed requests to an Ollama server."""

import json
import os
from collections.abc import Callable
from time import monotonic
from typing import Protocol, TypeVar
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import BaseModel, ValidationError

Output = TypeVar("Output", bound=BaseModel)


class ModelError(RuntimeError):
    pass


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StructuredModel(Protocol):
    def invoke(self, instructions: str, data: dict, output: type[Output]) -> Output: ...


class OllamaModel:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: float = 60,
        observe: Callable | None = None,
    ):
        endpoint = (
            url or os.getenv("AGILEOPS_OLLAMA_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        parsed = urlparse(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Configure an Ollama HTTP base URL without credentials.")
        self.url = endpoint
        self.model = model or os.getenv("AGILEOPS_OLLAMA_MODEL", "qwen2.5:1.5b")
        self.timeout = timeout
        self.observe = observe
        self.http = build_opener(ProxyHandler({}), _RejectRedirects())

    def invoke(self, instructions: str, data: dict, output: type[Output]) -> Output:
        start = monotonic()
        request = Request(
            f"{self.url}/api/chat",
            data=json.dumps(
                {
                    "model": self.model,
                    "stream": False,
                    "format": output.model_json_schema(),
                    "options": {"temperature": 0, "num_predict": 1024},
                    "messages": [
                        {"role": "system", "content": instructions},
                        {
                            "role": "user",
                            "content": json.dumps(data, ensure_ascii=False),
                        },
                    ],
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.http.open(request, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
        except (URLError, TimeoutError, OSError) as error:
            if self.observe:
                self.observe(
                    model=self.model,
                    status="failed",
                    latency_seconds=monotonic() - start,
                )
            raise ModelError(
                "Ollama is unavailable or the configured model could not run."
            ) from error
        if len(raw) > 2_000_000:
            raise ModelError("Ollama returned an oversized response.")
        try:
            envelope = json.loads(raw)
            result = output.model_validate_json(envelope["message"]["content"])
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            if self.observe:
                self.observe(
                    model=self.model,
                    status="invalid_output",
                    latency_seconds=monotonic() - start,
                )
            raise ModelError(
                "Ollama returned an invalid structured response."
            ) from error
        if self.observe:
            self.observe(
                model=self.model,
                status="completed",
                latency_seconds=monotonic() - start,
                input_tokens=envelope.get("prompt_eval_count"),
                output_tokens=envelope.get("eval_count"),
            )
        return result
