"""
Anthropic LLM Provider Adapter.
===============================
Integrates with Anthropic Claude models (e.g. claude-3-haiku, claude-3-5-sonnet).
Translates provider errors to LLMServer5xxError and LLMTimeoutError for transparent failover.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Generator, List, Optional

import requests
from django.conf import settings

from .base import (
    BaseLLMProvider,
    LLMClientError,
    LLMResponse,
    LLMServer5xxError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Adapter for Anthropic API."""

    name = "anthropic"
    default_model = "claude-3-haiku-20240307"
    api_url = "https://api.anthropic.com/v1/messages"
    anthropic_version = "2023-06-01"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.api_key = api_key or getattr(settings, "ANTHROPIC_API_KEY", "")
        self.model = model or getattr(settings, "ANTHROPIC_MODEL", self.default_model)
        self.timeout = timeout

    def _build_messages(
        self, prompt: str, history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        messages = []
        if history:
            for entry in history[-6:]:
                if entry.get("question"):
                    messages.append({"role": "user", "content": entry["question"]})
                if entry.get("answer"):
                    messages.append({"role": "assistant", "content": entry["answer"]})
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        start_time = time.perf_counter()
        active_model = kwargs.get("model", self.model)
        api_key = kwargs.get("api_key", self.api_key)
        messages = self._build_messages(prompt, history)

        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 400),
            "temperature": kwargs.get("temperature", 0.6),
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            # Check 5xx or Anthropic 529 overloaded error
            if resp.status_code >= 500 or resp.status_code == 529:
                raise LLMServer5xxError(
                    f"Anthropic API returned server error HTTP {resp.status_code}: {resp.text}",
                    provider=self.name,
                    status_code=resp.status_code,
                )

            if resp.status_code >= 400:
                raise LLMClientError(
                    f"Anthropic API returned client error HTTP {resp.status_code}: {resp.text}",
                    provider=self.name,
                    status_code=resp.status_code,
                )

            data = resp.json()
            content_blocks = data.get("content", [])
            text = ""
            if content_blocks and isinstance(content_blocks, list):
                for block in content_blocks:
                    if block.get("type") == "text":
                        text += block.get("text", "")

            duration_ms = (time.perf_counter() - start_time) * 1000
            return LLMResponse(
                content=text.strip(),
                provider=self.name,
                model=active_model,
                latency_ms=duration_ms,
                raw_response=data,
            )
        except requests.exceptions.Timeout as exc:
            raise LLMTimeoutError(
                f"Anthropic request timed out after {self.timeout}s: {exc}",
                provider=self.name,
                timeout_seconds=self.timeout,
                original_error=exc,
            ) from exc
        except requests.exceptions.RequestException as exc:
            if (
                hasattr(exc, "response")
                and exc.response is not None
                and exc.response.status_code in [500, 502, 503, 504, 529]
            ):
                raise LLMServer5xxError(
                    f"Anthropic server error: {exc}",
                    provider=self.name,
                    status_code=exc.response.status_code,
                    original_error=exc,
                ) from exc
            self._handle_anthropic_exception(exc)
            raise

    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        resp = self.generate(prompt, system_prompt, history, **kwargs)
        words = resp.content.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    def _handle_anthropic_exception(self, exc: Exception) -> None:
        exc_str = str(exc).lower()
        if "timeout" in exc_str:
            raise LLMTimeoutError(
                f"Anthropic API timed out: {exc}",
                provider=self.name,
                timeout_seconds=self.timeout,
                original_error=exc,
            ) from exc

        if any(
            term in exc_str
            for term in [
                "500",
                "502",
                "503",
                "504",
                "529",
                "overloaded",
                "server_error",
            ]
        ):
            raise LLMServer5xxError(
                f"Anthropic API server error: {exc}",
                provider=self.name,
                status_code=500,
                original_error=exc,
            ) from exc
