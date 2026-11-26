"""
OpenAI LLM Provider Adapter.
============================
Integrates with OpenAI API (e.g. gpt-4o, gpt-4o-mini, gpt-3.5-turbo).
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


class OpenAIProvider(BaseLLMProvider):
    """Adapter for OpenAI API."""

    name = "openai"
    default_model = "gpt-3.5-turbo"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.api_key = api_key or getattr(settings, "OPENAI_API_KEY", "")
        self.model = model or getattr(
            settings, "OPENAI_MODEL", getattr(settings, "LLM_MODEL", self.default_model)
        )
        self.timeout = timeout

    def _build_messages(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
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
        messages = self._build_messages(prompt, system_prompt, history)

        try:
            import openai

            if api_key:
                openai.api_key = api_key

            response = openai.chat.completions.create(
                model=active_model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 400),
                temperature=kwargs.get("temperature", 0.6),
                timeout=self.timeout,
            )
            content = response.choices[0].message.content.strip()
            duration_ms = (time.perf_counter() - start_time) * 1000

            return LLMResponse(
                content=content,
                provider=self.name,
                model=active_model,
                latency_ms=duration_ms,
                raw_response=response,
            )
        except Exception as exc:
            self._handle_openai_exception(exc)
            raise

    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        active_model = kwargs.get("model", self.model)
        api_key = kwargs.get("api_key", self.api_key)
        messages = self._build_messages(prompt, system_prompt, history)

        try:
            import openai

            if api_key:
                openai.api_key = api_key

            stream = openai.chat.completions.create(
                model=active_model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 400),
                temperature=kwargs.get("temperature", 0.6),
                stream=True,
                timeout=self.timeout,
            )

            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", None)
                    if content:
                        yield content
        except Exception as exc:
            self._handle_openai_exception(exc)
            raise

    def _handle_openai_exception(self, exc: Exception) -> None:
        exc_str = str(exc).lower()
        exc_name = type(exc).__name__

        if "timeout" in exc_str or "apitimeouterror" in exc_name.lower():
            raise LLMTimeoutError(
                f"OpenAI API call timed out: {exc}",
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
                "internalservererror",
                "apiconnectionerror",
                "service unavailable",
            ]
        ):
            raise LLMServer5xxError(
                f"OpenAI API returned 5xx/connection failure: {exc}",
                provider=self.name,
                status_code=500,
                original_error=exc,
            ) from exc

        if any(
            term in exc_str
            for term in [
                "400",
                "401",
                "403",
                "404",
                "badrequesterror",
                "authenticationerror",
            ]
        ):
            raise LLMClientError(
                f"OpenAI API client error: {exc}",
                provider=self.name,
                status_code=400,
                original_error=exc,
            ) from exc
