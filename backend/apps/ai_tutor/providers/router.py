"""
Smart Failover Router for LLM Providers.
========================================
Coordinates resilient failover across multiple LLM providers:
  Primary Provider -> on 5xx or timeout -> Secondary Provider -> Tertiary Provider

Tracks provider failover transitions with Prometheus counter:
  llm_provider_failovers_total{from="gemini", to="openai"}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Optional

from django.conf import settings

from .anthropic import AnthropicProvider
from .base import (
    BaseLLMProvider,
    LLMAllProvidersFailedError,
    LLMClientError,
    LLMResponse,
    LLMServer5xxError,
    LLMTimeoutError,
    TokenUsage,
)
from .gemini import GeminiProvider
from .metrics import record_llm_provider_failover
from .openai import OpenAIProvider

logger = logging.getLogger(__name__)


class SmartFailoverRouter:
    """
    Intelligent LLM router that attempts primary provider, and on 5xx or timeout,
    transparently fails over to secondary/tertiary providers within the same request.
    """

    PROVIDER_CLASSES = {
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }

    def __init__(
        self,
        providers: Optional[List[BaseLLMProvider]] = None,
        provider_names: Optional[List[str]] = None,
    ):
        if providers:
            self.providers = list(providers)
        else:
            names = provider_names or getattr(
                settings,
                "AI_TUTOR_PROVIDER_ORDER",
                None,
            )
            if not names:
                has_gemini = bool(getattr(settings, "GEMINI_API_KEY", None))
                has_openai = bool(getattr(settings, "OPENAI_API_KEY", None))
                has_anthropic = bool(getattr(settings, "ANTHROPIC_API_KEY", None))

                if has_gemini:
                    names = ["gemini", "openai", "anthropic"]
                elif has_openai:
                    names = ["openai", "gemini", "anthropic"]
                elif has_anthropic:
                    names = ["anthropic", "gemini", "openai"]
                else:
                    names = ["gemini", "openai", "anthropic"]

            self.providers = []
            for name in names:
                cls = self.PROVIDER_CLASSES.get(name.lower())
                if cls:
                    self.providers.append(cls())

        if not self.providers:
            # Fallback default order: Gemini -> OpenAI -> Anthropic
            self.providers = [GeminiProvider(), OpenAIProvider(), AnthropicProvider()]

        # The provider that served the last generate()/stream() call.
        self.active_provider: Optional[BaseLLMProvider] = None

    @property
    def last_usage(self) -> Optional[TokenUsage]:
        """Token usage the serving provider reported, None when it reported none."""
        if self.active_provider is None:
            return None
        return getattr(self.active_provider, "last_usage", None)

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Attempt generation across the provider chain.
        If a provider encounters 5xx or timeout, transparently failover to the next.
        """
        errors: List[tuple[str, Exception]] = []
        self.active_provider = None

        for idx, provider in enumerate(self.providers):
            has_next = idx + 1 < len(self.providers)
            next_provider = self.providers[idx + 1] if has_next else None

            try:
                logger.debug(
                    "Attempting LLM completion with provider '%s' (step %d/%d)",
                    provider.name,
                    idx + 1,
                    len(self.providers),
                )
                response = provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history=history,
                    **kwargs,
                )
                self.active_provider = provider
                return response

            except (LLMServer5xxError, LLMTimeoutError) as exc:
                errors.append((provider.name, exc))
                if has_next and next_provider is not None:
                    record_llm_provider_failover(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                    )
                    logger.warning(
                        "LLM provider '%s' failed with %s (%s). Transparently failing over to '%s'.",
                        provider.name,
                        type(exc).__name__,
                        exc,
                        next_provider.name,
                    )
                    continue
                else:
                    logger.error(
                        "All LLM providers in failover chain exhausted after '%s' failed with %s: %s",
                        provider.name,
                        type(exc).__name__,
                        exc,
                    )

            except Exception as exc:
                # Check if retriable under provider logic
                if (
                    provider.is_retriable_error(exc)
                    and has_next
                    and next_provider is not None
                ):
                    errors.append((provider.name, exc))
                    record_llm_provider_failover(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                    )
                    logger.warning(
                        "LLM provider '%s' encountered retriable exception (%s). Transparently failing over to '%s'.",
                        provider.name,
                        exc,
                        next_provider.name,
                    )
                    continue

                errors.append((provider.name, exc))
                if has_next and next_provider is not None:
                    # Also failover on unexpected non-client errors
                    record_llm_provider_failover(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                    )
                    logger.warning(
                        "LLM provider '%s' failed with error (%s). Transparently failing over to '%s'.",
                        provider.name,
                        exc,
                        next_provider.name,
                    )
                    continue

        # If all providers failed, raise unified error with history
        error_summary = "; ".join(f"{name}: {err}" for name, err in errors)
        raise LLMAllProvidersFailedError(
            f"All LLM providers failed to complete request: [{error_summary}]",
            errors=errors,
        )

    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """
        Stream completion with transparent failover before the first token is emitted.
        """
        errors: List[tuple[str, Exception]] = []
        self.active_provider = None

        for idx, provider in enumerate(self.providers):
            has_next = idx + 1 < len(self.providers)
            next_provider = self.providers[idx + 1] if has_next else None

            try:
                gen = provider.stream(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history=history,
                    **kwargs,
                )
                # Attempt to peek or fetch first token to ensure provider connection is healthy
                try:
                    first_token = next(gen)
                except StopIteration:
                    self.active_provider = provider
                    return

                # set before yielding so a stream the client drops early still
                # knows which provider (and so which usage) it came from
                self.active_provider = provider
                yield first_token
                for token in gen:
                    yield token
                return

            except (LLMServer5xxError, LLMTimeoutError) as exc:
                errors.append((provider.name, exc))
                if has_next and next_provider is not None:
                    record_llm_provider_failover(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                    )
                    logger.warning(
                        "LLM stream from provider '%s' failed with %s. Failing over to '%s'.",
                        provider.name,
                        type(exc).__name__,
                        next_provider.name,
                    )
                    continue

            except Exception as exc:
                errors.append((provider.name, exc))
                if has_next and next_provider is not None:
                    record_llm_provider_failover(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                    )
                    logger.warning(
                        "LLM stream from provider '%s' failed (%s). Failing over to '%s'.",
                        provider.name,
                        exc,
                        next_provider.name,
                    )
                    continue

        error_summary = "; ".join(f"{name}: {err}" for name, err in errors)
        raise LLMAllProvidersFailedError(
            f"All LLM providers failed to initiate stream: [{error_summary}]",
            errors=errors,
        )
