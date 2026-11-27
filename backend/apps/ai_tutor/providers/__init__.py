"""
AI Tutor LLM Provider Subsystem.
================================
Provides multi-provider failover pipeline across Gemini, OpenAI, and Anthropic.
"""

from .anthropic import AnthropicProvider
from .base import (
    BaseLLMProvider,
    LLMAllProvidersFailedError,
    LLMClientError,
    LLMProviderError,
    LLMResponse,
    LLMServer5xxError,
    LLMTimeoutError,
    TokenUsage,
)
from .gemini import GeminiProvider
from .metrics import LLM_PROVIDER_FAILOVERS_TOTAL, record_llm_provider_failover
from .openai import OpenAIProvider
from .router import SmartFailoverRouter

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "LLMProviderError",
    "LLMServer5xxError",
    "LLMTimeoutError",
    "LLMClientError",
    "LLMAllProvidersFailedError",
    "TokenUsage",
    "GeminiProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "SmartFailoverRouter",
    "LLM_PROVIDER_FAILOVERS_TOTAL",
    "record_llm_provider_failover",
]
