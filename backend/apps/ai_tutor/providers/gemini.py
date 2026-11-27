"""
Gemini LLM Provider Adapter.
============================
Integrates with Google Gemini models (e.g. gemini-1.5-flash, gemini-1.5-pro).
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
    TokenUsage,
)

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Adapter for Google Gemini API."""

    name = "gemini"
    default_model = "gemini-1.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(settings, "GEMINI_MODEL", self.default_model)
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        start_time = time.perf_counter()
        self.last_usage = None
        active_model = kwargs.get("model", self.model)
        api_key = kwargs.get("api_key", self.api_key)

        # 1. Try google.generativeai SDK if available
        try:
            import google.generativeai as genai

            if api_key:
                genai.configure(api_key=api_key)
            gmodel = genai.GenerativeModel(
                model_name=active_model,
                system_instruction=system_prompt if system_prompt else None,
            )
            chat_history = []
            if history:
                for entry in history[-6:]:
                    if entry.get("question"):
                        chat_history.append(
                            {"role": "user", "parts": [entry["question"]]}
                        )
                    if entry.get("answer"):
                        chat_history.append(
                            {"role": "model", "parts": [entry["answer"]]}
                        )

            chat = gmodel.start_chat(history=chat_history)
            response = chat.send_message(
                prompt, request_options={"timeout": self.timeout}
            )
            content = response.text.strip() if hasattr(response, "text") else ""
            meta = getattr(response, "usage_metadata", None)
            if meta is not None:
                self.last_usage = self._usage_from(
                    getattr(meta, "prompt_token_count", None),
                    getattr(meta, "candidates_token_count", None),
                    getattr(meta, "thoughts_token_count", None),
                )

            duration_ms = (time.perf_counter() - start_time) * 1000
            return LLMResponse(
                content=content,
                provider=self.name,
                model=active_model,
                latency_ms=duration_ms,
                raw_response=response,
                usage=self.last_usage,
            )
        except (ImportError, AttributeError):
            # 2. Fall back to direct Google AI REST API
            return self._call_rest_api(
                prompt, system_prompt, history, active_model, api_key, start_time
            )
        except Exception as exc:
            self._handle_gemini_exception(exc)
            raise

    def _call_rest_api(
        self,
        prompt: str,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]],
        model: str,
        api_key: str,
        start_time: float,
    ) -> LLMResponse:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        params = {"key": api_key} if api_key else {}
        contents = []

        if history:
            for entry in history[-6:]:
                if entry.get("question"):
                    contents.append(
                        {"role": "user", "parts": [{"text": entry["question"]}]}
                    )
                if entry.get("answer"):
                    contents.append(
                        {"role": "model", "parts": [{"text": entry["answer"]}]}
                    )
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        body: Dict[str, Any] = {"contents": contents}
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            resp = requests.post(url, params=params, json=body, timeout=self.timeout)
            if resp.status_code >= 500:
                raise LLMServer5xxError(
                    f"Gemini API returned server error HTTP {resp.status_code}: {resp.text}",
                    provider=self.name,
                    status_code=resp.status_code,
                )
            if resp.status_code >= 400:
                raise LLMClientError(
                    f"Gemini API returned client error HTTP {resp.status_code}: {resp.text}",
                    provider=self.name,
                    status_code=resp.status_code,
                )

            data = resp.json()
            candidates = data.get("candidates", [])
            text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "")

            meta = data.get("usageMetadata") or {}
            if isinstance(meta, dict):
                self.last_usage = self._usage_from(
                    meta.get("promptTokenCount"),
                    meta.get("candidatesTokenCount"),
                    meta.get("thoughtsTokenCount"),
                )

            duration_ms = (time.perf_counter() - start_time) * 1000
            return LLMResponse(
                content=text.strip(),
                provider=self.name,
                model=model,
                latency_ms=duration_ms,
                raw_response=data,
                usage=self.last_usage,
            )
        except requests.exceptions.Timeout as exc:
            raise LLMTimeoutError(
                f"Gemini request timed out after {self.timeout}s: {exc}",
                provider=self.name,
                timeout_seconds=self.timeout,
                original_error=exc,
            ) from exc
        except requests.exceptions.RequestException as exc:
            if (
                hasattr(exc, "response")
                and exc.response is not None
                and exc.response.status_code >= 500
            ):
                raise LLMServer5xxError(
                    f"Gemini server error: {exc}",
                    provider=self.name,
                    status_code=exc.response.status_code,
                    original_error=exc,
                ) from exc
            self._handle_gemini_exception(exc)
            raise

    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        resp = self.generate(prompt, system_prompt, history, **kwargs)
        # Yield completed response text as token chunks
        words = resp.content.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    @staticmethod
    def _usage_from(
        prompt_tokens: Any, candidate_tokens: Any, thought_tokens: Any = None
    ) -> Optional[TokenUsage]:
        # thinking models bill their thought tokens as output too
        if isinstance(thought_tokens, int) and isinstance(candidate_tokens, int):
            candidate_tokens += thought_tokens
        return TokenUsage.from_counts(prompt_tokens, candidate_tokens)

    def _handle_gemini_exception(self, exc: Exception) -> None:
        exc_str = str(exc).lower()
        exc_name = type(exc).__name__

        if (
            "timeout" in exc_str
            or "deadlineexceeded" in exc_str
            or "timeouterror" in exc_name.lower()
        ):
            raise LLMTimeoutError(
                f"Gemini API call timed out: {exc}",
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
                "serviceunavailable",
                "internalservererror",
                "overloaded",
                "resourceexhausted",
            ]
        ):
            status_code = 503 if "exhausted" in exc_str else 500
            raise LLMServer5xxError(
                f"Gemini API returned 5xx/server outage: {exc}",
                provider=self.name,
                status_code=status_code,
                original_error=exc,
            ) from exc

        if any(
            term in exc_str
            for term in [
                "400",
                "401",
                "403",
                "404",
                "invalidargument",
                "unauthenticated",
            ]
        ):
            raise LLMClientError(
                f"Gemini API client error: {exc}",
                provider=self.name,
                status_code=400,
                original_error=exc,
            ) from exc
