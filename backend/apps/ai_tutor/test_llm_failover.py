"""
Unit Tests for Fallback LLM Provider Failover Pipeline.
======================================================
Verifies:
- SmartFailoverRouter transparent failover on 5xx and timeout.
- Prometheus counter logging: llm_provider_failovers_total{from, to}.
- Multi-hop failover across Gemini -> OpenAI -> Anthropic.
- Exhaustion handling (LLMAllProvidersFailedError).
- Transparent integration with AiTutorService.
- Provider exception mapping (5xx, timeout, client error).
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.ai_tutor.providers.anthropic import AnthropicProvider
from apps.ai_tutor.providers.base import (
    BaseLLMProvider,
    LLMAllProvidersFailedError,
    LLMClientError,
    LLMResponse,
    LLMServer5xxError,
    LLMTimeoutError,
)
from apps.ai_tutor.providers.gemini import GeminiProvider
from apps.ai_tutor.providers.metrics import (
    LLM_PROVIDER_FAILOVERS_TOTAL,
    record_llm_provider_failover,
)
from apps.ai_tutor.providers.openai import OpenAIProvider
from apps.ai_tutor.providers.router import SmartFailoverRouter
from apps.ai_tutor.services import AiTutorService


class MockProvider(BaseLLMProvider):
    """Configurable mock provider for deterministic unit testing."""

    def __init__(self, name: str, behavior="success", content="Default mock content"):
        self.name = name
        self.behavior = behavior
        self.content = content
        self.call_count = 0

    def generate(self, prompt, system_prompt="", history=None, **kwargs):
        self.call_count += 1
        if self.behavior == "5xx":
            raise LLMServer5xxError(
                f"{self.name} simulated 500 Internal Server Error",
                provider=self.name,
                status_code=500,
            )
        elif self.behavior == "timeout":
            raise LLMTimeoutError(
                f"{self.name} connection timed out after 10s",
                provider=self.name,
                timeout_seconds=10.0,
            )
        elif self.behavior == "client_error":
            raise LLMClientError(
                f"{self.name} bad request 400",
                provider=self.name,
                status_code=400,
            )
        elif callable(self.behavior):
            return self.behavior(prompt, system_prompt, history, **kwargs)

        return LLMResponse(
            content=self.content,
            provider=self.name,
            model=f"mock-{self.name}-model",
            latency_ms=12.5,
        )

    def stream(self, prompt, system_prompt="", history=None, **kwargs):
        self.call_count += 1
        if self.behavior == "5xx":
            raise LLMServer5xxError(
                f"{self.name} stream 503 Service Unavailable",
                provider=self.name,
                status_code=503,
            )
        elif self.behavior == "timeout":
            raise LLMTimeoutError(
                f"{self.name} stream timeout",
                provider=self.name,
                timeout_seconds=10.0,
            )
        for token in self.content.split():
            yield token + " "


class LLMFailoverPipelineTests(TestCase):
    def setUp(self):
        self.gemini = MockProvider("gemini", content="Response from Gemini")
        self.openai = MockProvider("openai", content="Response from OpenAI")
        self.anthropic = MockProvider("anthropic", content="Response from Anthropic")

    def test_primary_provider_success_no_failover(self):
        """
        When primary provider succeeds, router returns immediately without
        contacting secondary providers, and no failover metric is incremented.
        """
        router = SmartFailoverRouter(
            providers=[self.gemini, self.openai, self.anthropic]
        )
        response = router.generate("Explain git rebase")

        self.assertEqual(response.provider, "gemini")
        self.assertEqual(response.content, "Response from Gemini")
        self.assertEqual(self.gemini.call_count, 1)
        self.assertEqual(self.openai.call_count, 0)
        self.assertEqual(self.anthropic.call_count, 0)

    def test_primary_5xx_triggers_transparent_failover_to_openai(self):
        """
        When Gemini encounters 500 error, router transparently fails over to OpenAI
        within the same request, and records metric llm_provider_failovers_total{from="gemini", to="openai"}.
        """
        self.gemini.behavior = "5xx"
        router = SmartFailoverRouter(
            providers=[self.gemini, self.openai, self.anthropic]
        )

        with patch(
            "apps.ai_tutor.providers.router.record_llm_provider_failover"
        ) as mock_record:
            response = router.generate("What is a commit?")

            self.assertEqual(response.provider, "openai")
            self.assertEqual(response.content, "Response from OpenAI")
            self.assertEqual(self.gemini.call_count, 1)
            self.assertEqual(self.openai.call_count, 1)
            self.assertEqual(self.anthropic.call_count, 0)

            mock_record.assert_called_once_with(
                from_provider="gemini", to_provider="openai"
            )

    def test_primary_timeout_triggers_transparent_failover(self):
        """
        When primary provider times out, router transparently fails over to secondary.
        """
        self.gemini.behavior = "timeout"
        router = SmartFailoverRouter(
            providers=[self.gemini, self.openai, self.anthropic]
        )

        with patch(
            "apps.ai_tutor.providers.router.record_llm_provider_failover"
        ) as mock_record:
            response = router.generate("How to resolve merge conflicts?")

            self.assertEqual(response.provider, "openai")
            self.assertEqual(self.gemini.call_count, 1)
            self.assertEqual(self.openai.call_count, 1)
            mock_record.assert_called_once_with(
                from_provider="gemini", to_provider="openai"
            )

    def test_multi_hop_failover_gemini_to_openai_to_anthropic(self):
        """
        Multi-hop failover: Gemini fails (500) -> OpenAI fails (timeout) -> Anthropic succeeds.
        Both provider switch events are recorded.
        """
        self.gemini.behavior = "5xx"
        self.openai.behavior = "timeout"
        router = SmartFailoverRouter(
            providers=[self.gemini, self.openai, self.anthropic]
        )

        with patch(
            "apps.ai_tutor.providers.router.record_llm_provider_failover"
        ) as mock_record:
            response = router.generate("Explain pull request etiquette")

            self.assertEqual(response.provider, "anthropic")
            self.assertEqual(response.content, "Response from Anthropic")
            self.assertEqual(self.gemini.call_count, 1)
            self.assertEqual(self.openai.call_count, 1)
            self.assertEqual(self.anthropic.call_count, 1)

            self.assertEqual(mock_record.call_count, 2)
            mock_record.assert_any_call(from_provider="gemini", to_provider="openai")
            mock_record.assert_any_call(from_provider="openai", to_provider="anthropic")

    def test_all_providers_failed_raises_unified_exception(self):
        """
        When every provider in the failover chain fails, router raises LLMAllProvidersFailedError.
        """
        self.gemini.behavior = "5xx"
        self.openai.behavior = "timeout"
        self.anthropic.behavior = "5xx"
        router = SmartFailoverRouter(
            providers=[self.gemini, self.openai, self.anthropic]
        )

        with self.assertRaises(LLMAllProvidersFailedError) as ctx:
            router.generate("What is git cherry-pick?")

        self.assertIn("All LLM providers failed", str(ctx.exception))
        self.assertEqual(len(ctx.exception.errors), 3)

    def test_streaming_failover_on_provider_outage(self):
        """
        When streaming completion from primary fails with 5xx/timeout before token emission,
        router transparently fails over to secondary provider.
        """
        self.gemini.behavior = "5xx"
        router = SmartFailoverRouter(
            providers=[self.gemini, self.openai, self.anthropic]
        )

        tokens = list(router.stream("Explain Git staging"))
        streamed_text = "".join(tokens).strip()

        self.assertEqual(streamed_text, "Response from OpenAI")
        self.assertEqual(self.gemini.call_count, 1)
        self.assertEqual(self.openai.call_count, 1)

    def test_prometheus_metric_label_recording(self):
        """
        Verifies that Prometheus Counter metric is correctly called with from/to labels.
        """
        if LLM_PROVIDER_FAILOVERS_TOTAL is not None:
            before_val = LLM_PROVIDER_FAILOVERS_TOTAL.labels(
                **{"from": "gemini", "to": "openai"}
            )._value.get()

            record_llm_provider_failover(from_provider="gemini", to_provider="openai")

            after_val = LLM_PROVIDER_FAILOVERS_TOTAL.labels(
                **{"from": "gemini", "to": "openai"}
            )._value.get()
            self.assertEqual(after_val, before_val + 1)

    def test_ai_tutor_service_integration_with_failover(self):
        """
        AiTutorService._llm_response uses SmartFailoverRouter to seamlessly
        return the fallback provider's response when primary fails.
        """
        self.gemini.behavior = "5xx"
        test_router = SmartFailoverRouter(providers=[self.gemini, self.openai])

        with patch(
            "apps.ai_tutor.providers.router.SmartFailoverRouter",
            return_value=test_router,
        ):
            answer = AiTutorService._llm_response(
                question="What is open source?",
                lesson_context="Open Source Basics",
                history=[],
            )
            self.assertEqual(answer, "Response from OpenAI")

    def test_ai_tutor_service_falls_back_to_socratic_when_all_fail(self):
        """
        If all LLM providers fail, AiTutorService gracefully degrades to the
        deterministic Socratic knowledge base rather than crashing or showing an error.
        """
        self.gemini.behavior = "5xx"
        self.openai.behavior = "5xx"
        test_router = SmartFailoverRouter(providers=[self.gemini, self.openai])

        with patch(
            "apps.ai_tutor.providers.router.SmartFailoverRouter",
            return_value=test_router,
        ):
            answer = AiTutorService._llm_response(
                question="What is a commit?",
                lesson_context="",
                history=[],
            )
            self.assertIn("snapshot", answer.lower())

    def test_provider_retriable_error_heuristic(self):
        """
        Verifies is_retriable_error properly identifies 5xx status codes, timeouts,
        and connection failures.
        """
        provider = GeminiProvider()

        self.assertTrue(provider.is_retriable_error(LLMServer5xxError("500 error")))
        self.assertTrue(provider.is_retriable_error(LLMTimeoutError("Read timed out")))
        self.assertTrue(
            provider.is_retriable_error(Exception("503 Service Unavailable"))
        )
        self.assertTrue(provider.is_retriable_error(Exception("Connection timed out")))
        self.assertFalse(provider.is_retriable_error(LLMClientError("400 Bad Request")))
