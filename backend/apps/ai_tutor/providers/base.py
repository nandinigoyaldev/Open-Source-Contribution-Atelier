"""
Provider-Agnostic LLM Interface & Exception Hierarchy.
======================================================
Defines common response structures, exceptions, and abstract provider interface
for the multi-provider failover pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized provider-agnostic response object."""

    content: str
    provider: str
    model: str
    latency_ms: float = 0.0
    raw_response: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.content


class LLMProviderError(Exception):
    """Base exception for all LLM provider failures."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error


class LLMServer5xxError(LLMProviderError):
    """
    Raised when an LLM provider returns an HTTP 5xx error, service unavailable,
    internal server error, or rate-limited service failure.
    Eligible for transparent failover.
    """

    def __init__(
        self,
        message: str,
        provider: str = "",
        status_code: int = 500,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, provider=provider, original_error=original_error)
        self.status_code = status_code


class LLMTimeoutError(LLMProviderError):
    """
    Raised when an LLM provider connection or read operation times out.
    Eligible for transparent failover.
    """

    def __init__(
        self,
        message: str,
        provider: str = "",
        timeout_seconds: float = 0.0,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, provider=provider, original_error=original_error)
        self.timeout_seconds = timeout_seconds


class LLMClientError(LLMProviderError):
    """
    Raised on 4xx client errors (e.g. invalid arguments, authentication failure).
    """

    def __init__(
        self,
        message: str,
        provider: str = "",
        status_code: int = 400,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, provider=provider, original_error=original_error)
        self.status_code = status_code


class LLMAllProvidersFailedError(LLMProviderError):
    """
    Raised when all providers in the configured failover chain fail.
    """

    def __init__(
        self, message: str, errors: Optional[List[tuple[str, Exception]]] = None
    ):
        super().__init__(message)
        self.errors = errors or []


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM provider adapters (Gemini, OpenAI, Anthropic).
    """

    name: str = "base"
    default_model: str = "default"
    timeout: float = 10.0

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Execute forward completion call to provider.

        Raises:
            LLMServer5xxError: On 5xx provider error (triggers failover).
            LLMTimeoutError: On provider timeout (triggers failover).
            LLMClientError: On client-side 4xx error.
        """
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """
        Stream completion chunks from provider.
        """
        raise NotImplementedError

    def is_retriable_error(self, exc: Exception) -> bool:
        """
        Determines whether an exception is considered a 5xx or timeout failure
        warranting transparent failover.
        """
        if isinstance(exc, (LLMServer5xxError, LLMTimeoutError)):
            return True

        # Check standard exception names and messages for 5xx/timeout indicators
        msg = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        if "timeout" in exc_type or "timeouterror" in exc_type or "timed out" in msg:
            return True

        if any(
            code in msg
            for code in [
                "500",
                "502",
                "503",
                "504",
                "server error",
                "service unavailable",
                "overloaded",
                "bad gateway",
            ]
        ):
            return True

        return False
