# Django has no type stubs here: ``Model.objects`` is unknown and test client responses
# are typed as WSGIRequest, so header lookups on them are reported.
# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false
"""
Tests for the AI tutor daily token budget (token_budget.py, the ask view guard,
the ledger flush and provider usage reporting).
"""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from itertools import count
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.ai_tutor import token_budget
from apps.ai_tutor.models import (
    AITokenBudgetOverride,
    AITokenOrganizationPool,
    AITokenUsageLedger,
)
from apps.ai_tutor.providers.anthropic import AnthropicProvider
from apps.ai_tutor.providers.base import BaseLLMProvider, LLMResponse, TokenUsage
from apps.ai_tutor.providers.gemini import GeminiProvider
from apps.ai_tutor.providers.openai import OpenAIProvider
from apps.ai_tutor.providers.router import SmartFailoverRouter
from apps.ai_tutor.services import AiTutorService
from apps.ai_tutor.tasks import flush_ai_token_usage

User = get_user_model()

ASK_URL = "/api/ai/tutor/ask/"
NOW = datetime(2026, 3, 10, 12, 0, tzinfo=dt_timezone.utc)
TODAY = NOW.date()
MIDNIGHT = datetime(2026, 3, 11, 0, 0, tzinfo=dt_timezone.utc)

_usernames = count(1)


class UsageProvider(BaseLLMProvider):
    """Mock provider. Like OpenAI streaming, its usage is only known once the stream ends."""

    name = "mock"

    def __init__(self, content="Branches keep main safe.", usage=None):
        self.content = content
        self.usage = usage
        self.calls = 0

    def generate(self, prompt, system_prompt="", history=None, **kwargs):
        self.calls += 1
        self.last_usage = self.usage
        return LLMResponse(
            content=self.content, provider=self.name, model="mock", usage=self.usage
        )

    def stream(self, prompt, system_prompt="", history=None, **kwargs):
        self.calls += 1
        self.last_usage = None
        words = self.content.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
        self.last_usage = self.usage


def use_router(provider):
    return patch(
        "apps.ai_tutor.providers.router.SmartFailoverRouter",
        return_value=SmartFailoverRouter(providers=[provider]),
    )


def frozen(moment):
    return patch("django.utils.timezone.now", return_value=moment)


class BudgetTestCase(TestCase):
    # The test cache is a LocMemCache, which would switch on the ledger write-through.
    # Turning it off makes these tests run the counter + flush path that Redis uses.
    write_through = False

    def setUp(self):
        overrides = override_settings(
            AI_TUTOR_TOKEN_LEDGER_WRITE_THROUGH=self.write_through
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = self.make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def make_user(self, **extra):
        name = f"budget-user-{next(_usernames)}"
        return User.objects.create_user(
            username=name, email=f"{name}@example.com", password="pw-123456", **extra
        )

    def use(self, user, tokens, now=NOW):
        """Spend ``tokens`` (split roughly 80/20 between input and output)."""
        output_tokens = tokens // 5
        token_budget.record_usage(user, tokens - output_tokens, output_tokens, now=now)

    def ask(self, question="How do git branches work?", stream=False, **extra):
        return self.client.post(
            ASK_URL, {"question": question, "stream": stream, **extra}, format="json"
        )


class BudgetStatusTests(BudgetTestCase):
    def test_free_learner_gets_10k(self):
        budget = token_budget.get_budget_status(self.user, now=NOW)
        self.assertEqual(budget.limit, 10_000)
        self.assertEqual(budget.tier, token_budget.TIER_FREE)
        self.assertEqual(budget.used, 0)
        self.assertEqual(budget.reset_at, MIDNIGHT)

    def test_premium_subscription_gets_50k(self):
        from apps.billing.models import CustomerSubscription

        CustomerSubscription.objects.create(
            user=self.user, stripe_customer_id="cus_budget", active=True
        )
        budget = token_budget.get_budget_status(self.user, now=NOW)
        self.assertEqual(budget.limit, 50_000)
        self.assertEqual(budget.tier, token_budget.TIER_PREMIUM)

    def test_inactive_subscription_stays_free(self):
        from apps.billing.models import CustomerSubscription

        CustomerSubscription.objects.create(
            user=self.user, stripe_customer_id="cus_lapsed", active=False
        )
        self.assertEqual(
            token_budget.get_budget_status(self.user, now=NOW).limit, 10_000
        )

    @override_settings(AI_TUTOR_FREE_DAILY_TOKENS=1234)
    def test_limits_come_from_settings(self):
        self.assertEqual(token_budget.get_budget_status(self.user, now=NOW).limit, 1234)

    def test_boundaries(self):
        # (tokens used, warning expected, exhausted expected)
        cases = [
            (8_999, False, False),
            (9_000, True, False),
            (9_999, True, False),
            (10_000, True, True),
            (10_400, True, True),
        ]
        for used, warning, exhausted in cases:
            with self.subTest(used=used):
                user = self.make_user()
                self.use(user, used)
                budget = token_budget.get_budget_status(user, now=NOW)
                self.assertEqual(budget.used, used)
                self.assertEqual(budget.warning, warning)
                self.assertEqual(budget.exhausted, exhausted)
                self.assertEqual(budget.remaining, max(0, 10_000 - used))

    def test_estimator_rounds_up_four_chars_per_token(self):
        self.assertEqual(token_budget.estimate_tokens(""), 0)
        self.assertEqual(token_budget.estimate_tokens("a"), 1)
        self.assertEqual(token_budget.estimate_tokens("abcd"), 1)
        self.assertEqual(token_budget.estimate_tokens("abcde"), 2)


class AskViewBudgetTests(BudgetTestCase):
    def test_headers_at_89_90_99_percent(self):
        for used, warned in [(8_900, False), (9_000, True), (9_900, True)]:
            with self.subTest(used=used):
                user = self.make_user()
                self.client.force_authenticate(user=user)
                self.use(user, used)
                with frozen(NOW):
                    response = self.ask()
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response["X-AI-Token-Budget-Limit"], "10000")
                self.assertEqual(
                    response["X-AI-Token-Budget-Remaining"], str(10_000 - used)
                )
                self.assertEqual(
                    response["X-AI-Token-Budget-Reset"], str(int(MIDNIGHT.timestamp()))
                )
                self.assertEqual(response["X-AI-Token-Budget-Scope"], "user")
                self.assertEqual("X-AI-Token-Budget-Warning" in response, warned)
                if warned:
                    self.assertIn(
                        f"{used // 100}%", response["X-AI-Token-Budget-Warning"]
                    )

    def test_streaming_response_carries_the_headers_too(self):
        self.use(self.user, 9_500)
        with frozen(NOW):
            response = self.ask(stream=True)
            b"".join(response.streaming_content)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["X-AI-Token-Budget-Remaining"], "500")
        self.assertIn("X-AI-Token-Budget-Warning", response)

    @override_settings(OPENAI_API_KEY="sk-test")
    def test_429_at_100_percent_never_reaches_the_router(self):
        self.use(self.user, 10_000)
        # Raise instead of handing back a MagicMock: if the guard ever breaks, the
        # tutor falls back to a plain answer and this test fails. A MagicMock answer
        # would reach the JSON renderer, which recurses on it until memory runs out.
        with (
            frozen(NOW),
            patch(
                "apps.ai_tutor.providers.router.SmartFailoverRouter",
                side_effect=AssertionError("router must not be built"),
            ) as router_cls,
        ):
            response = self.ask()

        router_cls.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response["Retry-After"], str(12 * 60 * 60))
        self.assertEqual(response["X-AI-Token-Budget-Remaining"], "0")
        self.assertIn("X-AI-Token-Budget-Warning", response)
        body = response.json()
        self.assertEqual(body["code"], "ai_token_budget_exhausted")
        self.assertEqual(body["limit"], 10_000)
        self.assertEqual(body["used"], 10_000)
        self.assertEqual(body["remaining"], 0)
        self.assertEqual(body["tier"], "free")
        self.assertEqual(body["scope"], "user")
        self.assertEqual(body["reset_at"], "2026-03-11T00:00:00Z")
        self.assertEqual(body["retry_after"], 12 * 60 * 60)

    @override_settings(OPENAI_API_KEY="sk-test")
    def test_exact_exhaustion_from_real_provider_usage(self):
        self.use(self.user, 9_000)
        provider = UsageProvider(usage=TokenUsage(input_tokens=900, output_tokens=100))

        with frozen(NOW), use_router(provider):
            first = self.ask()
            second = self.ask()

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.json()["answer"], "Branches keep main safe.")
        self.assertEqual(first["X-AI-Token-Budget-Remaining"], "1000")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(second.json()["used"], 10_000)

    def test_budget_resets_at_midnight_utc(self):
        just_before = MIDNIGHT - timedelta(seconds=30)
        self.use(self.user, 10_000, now=just_before)

        with frozen(just_before):
            blocked = self.ask()
        with frozen(MIDNIGHT):
            allowed = self.ask()

        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(blocked["Retry-After"], "30")
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed["X-AI-Token-Budget-Remaining"], "10000")
        next_midnight = MIDNIGHT + timedelta(days=1)
        self.assertEqual(
            allowed["X-AI-Token-Budget-Reset"], str(int(next_midnight.timestamp()))
        )

    def test_usage_one_second_before_midnight_belongs_to_that_day(self):
        token_budget.record_usage(
            self.user, 50, 50, now=MIDNIGHT - timedelta(seconds=1)
        )
        self.assertEqual(token_budget.get_user_usage(self.user.pk, TODAY), 100)
        self.assertEqual(token_budget.get_user_usage(self.user.pk, MIDNIGHT.date()), 0)

    def test_hints_and_evaluations_do_not_need_budget(self):
        self.use(self.user, 10_000)
        with frozen(NOW):
            hint = self.ask(action="hint", question="git branches")
            evaluation = self.ask(
                action="evaluate", question="git commit", expected_command="git add ."
            )
        self.assertEqual(hint.status_code, status.HTTP_200_OK)
        self.assertEqual(evaluation.status_code, status.HTTP_200_OK)

    def test_rule_based_answers_cost_nothing(self):
        # no LLM key configured, so the tutor answers from its knowledge base
        with frozen(NOW):
            response = self.ask(stream=True)
            b"".join(response.streaming_content)
        self.assertEqual(token_budget.get_user_usage(self.user.pk, TODAY), 0)


@override_settings(GEMINI_API_KEY="test-key")
class StreamingUsageTests(BudgetTestCase):
    def test_stream_counts_the_usage_the_provider_reported(self):
        provider = UsageProvider(usage=TokenUsage(input_tokens=321, output_tokens=45))
        with frozen(NOW), use_router(provider):
            response = self.ask(stream=True)
            body = b"".join(response.streaming_content).decode()

        self.assertIn("Branches", body)
        row = AITokenUsageLedger.objects.get(user=self.user, date=TODAY)
        token_budget.flush_usage_to_ledger(now=NOW)
        row.refresh_from_db()
        self.assertEqual((row.input_tokens, row.output_tokens), (321, 45))

    def test_stream_without_usage_is_estimated(self):
        provider = UsageProvider(content="Use git switch -c to make a branch.")
        history = [{"question": "Hi", "answer": "Hello!"}]
        with frozen(NOW), use_router(provider):
            response = self.ask(stream=True, history=history)
            b"".join(response.streaming_content)

        system_prompt = AiTutorService._build_system_prompt(
            "",
            AiTutorService.build_tutor_context(current_lesson="General Open Source"),
        )
        prompt_text = "\n".join(
            [system_prompt, "Hi", "Hello!", "How do git branches work?"]
        )
        expected = token_budget.estimate_tokens(
            prompt_text
        ) + token_budget.estimate_tokens("Use git switch -c to make a branch.")
        self.assertEqual(token_budget.get_user_usage(self.user.pk, TODAY), expected)

    def test_dropped_stream_still_counts_what_was_sent(self):
        provider = UsageProvider(
            content="one two three four",
            usage=TokenUsage(input_tokens=500, output_tokens=500),
        )
        with frozen(NOW), use_router(provider):
            stream = AiTutorService.get_streaming_response(
                question="Explain rebase", user=self.user
            )
            next(stream)  # client reads one chunk, then goes away
            stream.close()

        # the provider never got to report usage, so prompt and sent text are estimated
        prompt_text = "\n".join(
            [AiTutorService._build_system_prompt("", None), "Explain rebase"]
        )
        expected = token_budget.estimate_tokens(
            prompt_text
        ) + token_budget.estimate_tokens("one ")
        self.assertEqual(token_budget.get_user_usage(self.user.pk, TODAY), expected)

    def test_failed_providers_count_nothing(self):
        provider = UsageProvider()
        provider.stream = MagicMock(side_effect=RuntimeError("503 overloaded"))
        with frozen(NOW), use_router(provider):
            response = self.ask(stream=True)
            b"".join(response.streaming_content)
        self.assertEqual(token_budget.get_user_usage(self.user.pk, TODAY), 0)


class OverrideAndPoolTests(BudgetTestCase):
    def test_override_replaces_the_tier_limit(self):
        AITokenBudgetOverride.objects.create(
            user=self.user, daily_token_limit=200_000, reason="course TA"
        )
        self.use(self.user, 60_000)
        budget = token_budget.get_budget_status(self.user, now=NOW)
        self.assertEqual(budget.limit, 200_000)
        self.assertEqual(budget.tier, token_budget.TIER_OVERRIDE)
        self.assertFalse(budget.exhausted)

    def test_expired_override_is_ignored(self):
        AITokenBudgetOverride.objects.create(
            user=self.user, daily_token_limit=200_000, expires_at=NOW
        )
        budget = token_budget.get_budget_status(self.user, now=NOW)
        self.assertEqual(budget.limit, 10_000)
        self.assertEqual(budget.tier, token_budget.TIER_FREE)

    def test_zero_override_blocks_the_user(self):
        AITokenBudgetOverride.objects.create(user=self.user, daily_token_limit=0)
        with frozen(NOW):
            response = self.ask()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.json()["tier"], "override")

    def _member(self, organization):
        from apps.accounts.models import UserProfile

        user = self.make_user()
        profile = UserProfile.objects.filter(user=user).first() or UserProfile(
            user=user
        )
        profile.organization = organization
        profile.save()
        return user

    def test_org_pool_is_shared_by_members(self):
        from apps.organizations.models import Organization

        org = Organization.objects.create(name="Budget Pool Org")
        AITokenOrganizationPool.objects.create(
            organization=org, daily_token_limit=1_000
        )
        alice, bob = self._member(org), self._member(org)
        outsider = self.make_user()

        self.use(alice, 600)
        budget = token_budget.get_budget_status(bob, now=NOW)
        self.assertEqual(budget.scope, token_budget.SCOPE_ORGANIZATION)
        self.assertEqual((budget.limit, budget.used), (1_000, 600))
        self.assertFalse(budget.exhausted)

        self.use(bob, 400)
        for member in (alice, bob):
            self.assertTrue(token_budget.get_budget_status(member, now=NOW).exhausted)
        self.assertFalse(token_budget.get_budget_status(outsider, now=NOW).exhausted)

        self.client.force_authenticate(user=bob)
        with frozen(NOW):
            response = self.ask()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.json()["scope"], "organization")
        self.assertIn("organization", response.json()["message"])

    def test_inactive_pool_falls_back_to_the_tier(self):
        from apps.organizations.models import Organization

        org = Organization.objects.create(name="Paused Pool Org")
        AITokenOrganizationPool.objects.create(
            organization=org, daily_token_limit=1_000, is_active=False
        )
        member = self._member(org)
        budget = token_budget.get_budget_status(member, now=NOW)
        self.assertEqual((budget.limit, budget.scope), (10_000, "user"))

    def test_override_wins_over_the_pool(self):
        from apps.organizations.models import Organization

        org = Organization.objects.create(name="Override Pool Org")
        AITokenOrganizationPool.objects.create(
            organization=org, daily_token_limit=1_000
        )
        member = self._member(org)
        AITokenBudgetOverride.objects.create(user=member, daily_token_limit=5_000)
        budget = token_budget.get_budget_status(member, now=NOW)
        self.assertEqual((budget.limit, budget.tier), (5_000, "override"))

    def test_models_are_in_the_admin(self):
        for model in (
            AITokenUsageLedger,
            AITokenBudgetOverride,
            AITokenOrganizationPool,
        ):
            self.assertTrue(admin.site.is_registered(model))


class LedgerFlushTests(BudgetTestCase):
    def ledger(self, user=None, day=TODAY):
        row = AITokenUsageLedger.objects.get(user=user or self.user, date=day)
        return row.input_tokens, row.output_tokens

    def test_flush_copies_counters_and_is_idempotent(self):
        token_budget.record_usage(self.user, 700, 300, now=NOW)
        self.assertEqual(self.ledger(), (0, 0))  # row exists, flush has not run yet
        # the check does not wait for the flush
        self.assertEqual(token_budget.get_budget_status(self.user, now=NOW).used, 1_000)

        self.assertEqual(token_budget.flush_usage_to_ledger(now=NOW), 1)
        self.assertEqual(self.ledger(), (700, 300))
        self.assertEqual(token_budget.flush_usage_to_ledger(now=NOW), 0)
        self.assertEqual(token_budget.flush_usage_to_ledger(now=NOW), 0)
        self.assertEqual(self.ledger(), (700, 300))

        token_budget.record_usage(self.user, 10, 5, now=NOW)
        self.assertEqual(token_budget.flush_usage_to_ledger(now=NOW), 1)
        self.assertEqual(self.ledger(), (710, 305))

    def test_scheduled_task_flushes(self):
        token_budget.record_usage(self.user, 70, 30)
        self.assertEqual(flush_ai_token_usage(), 1)
        self.assertEqual(flush_ai_token_usage(), 0)
        today = token_budget.utc_day()
        self.assertEqual(self.ledger(day=today), (70, 30))

    def test_flush_never_lowers_the_ledger(self):
        token_budget.record_usage(self.user, 700, 300, now=NOW)
        token_budget.flush_usage_to_ledger(now=NOW)
        cache.set(token_budget.counter_key(TODAY, self.user.pk, "input"), 5)
        token_budget.flush_usage_to_ledger(now=NOW)
        self.assertEqual(self.ledger(), (700, 300))

    def test_ledger_keeps_the_budget_when_the_cache_is_lost(self):
        token_budget.record_usage(self.user, 8_000, 1_500, now=NOW)
        token_budget.flush_usage_to_ledger(now=NOW)
        cache.clear()  # Redis restarted

        self.assertEqual(token_budget.get_budget_status(self.user, now=NOW).used, 9_500)
        # counting goes on from the ledger total instead of from zero
        token_budget.record_usage(self.user, 400, 100, now=NOW)
        self.assertTrue(token_budget.get_budget_status(self.user, now=NOW).exhausted)
        token_budget.flush_usage_to_ledger(now=NOW)
        self.assertEqual(self.ledger(), (8_400, 1_600))

    def test_flush_after_midnight_picks_up_the_end_of_yesterday(self):
        late = MIDNIGHT - timedelta(seconds=5)
        token_budget.record_usage(self.user, 100, 20, now=late)
        token_budget.flush_usage_to_ledger(now=late)
        token_budget.record_usage(self.user, 5, 1, now=late)  # after that flush

        token_budget.flush_usage_to_ledger(now=MIDNIGHT + timedelta(seconds=30))
        self.assertEqual(self.ledger(day=late.date()), (105, 21))

    def test_cache_failure_writes_straight_to_the_ledger(self):
        with patch.object(
            token_budget.cache, "incr", side_effect=ConnectionError("redis down")
        ):
            token_budget.record_usage(self.user, 40, 2, now=NOW)
        self.assertEqual(self.ledger(), (40, 2))

    def test_deleting_a_row_resets_the_day(self):
        token_budget.record_usage(self.user, 9_000, 1_000, now=NOW)
        AITokenUsageLedger.objects.filter(user=self.user).delete()
        self.assertEqual(token_budget.get_budget_status(self.user, now=NOW).used, 0)

        token_budget.record_usage(self.user, 10, 0, now=NOW)
        token_budget.flush_usage_to_ledger(now=NOW)
        self.assertEqual(self.ledger(), (10, 0))

    def test_flush_schedule_is_registered(self):
        from django_q.models import Schedule

        apps.get_app_config("ai_tutor").setup_schedules(sender=None)
        schedule = Schedule.objects.get(name="flush-ai-token-usage")
        self.assertEqual(schedule.func, "apps.ai_tutor.tasks.flush_ai_token_usage")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)


class WriteThroughTests(BudgetTestCase):
    """Default with a per-process LocMemCache: every request goes straight to the ledger."""

    write_through = None

    def test_on_by_default_for_locmem_and_settable(self):
        self.assertTrue(token_budget.ledger_write_through())
        with override_settings(AI_TUTOR_TOKEN_LEDGER_WRITE_THROUGH=False):
            self.assertFalse(token_budget.ledger_write_through())

    def test_usage_lands_in_the_ledger_right_away(self):
        token_budget.record_usage(self.user, 700, 300, now=NOW)
        token_budget.record_usage(self.user, 7, 3, now=NOW)

        row = AITokenUsageLedger.objects.get(user=self.user, date=TODAY)
        self.assertEqual((row.input_tokens, row.output_tokens), (707, 303))
        key = token_budget.counter_key(TODAY, self.user.pk, "input")
        self.assertIsNone(cache.get(key))
        self.assertEqual(token_budget.get_budget_status(self.user, now=NOW).used, 1_010)
        # nothing is left for the flush to do
        self.assertEqual(token_budget.flush_usage_to_ledger(now=NOW), 0)

    def test_other_workers_see_the_usage(self):
        self.use(self.user, 10_000)
        cache.clear()  # a different process, with its own empty LocMemCache
        with frozen(NOW):
            response = self.ask()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class ProviderUsageTests(TestCase):
    def test_openai_generate_reports_usage(self):
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hi"))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        )
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="sk-test")
            response = provider.generate("Explain commits")
        self.assertEqual(response.usage, TokenUsage(120, 30))
        self.assertEqual(provider.last_usage, TokenUsage(120, 30))

    def test_openai_stream_reads_the_final_usage_chunk(self):
        def chunk(text=None, usage=None):
            choices = [SimpleNamespace(delta=SimpleNamespace(content=text))]
            return SimpleNamespace(choices=choices if text else [], usage=usage)

        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = iter(
            [
                chunk("Hello "),
                chunk("there"),
                chunk(usage=SimpleNamespace(prompt_tokens=11, completion_tokens=2)),
            ]
        )
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="sk-test")
            text = "".join(provider.stream("Hi"))

        self.assertEqual(text, "Hello there")
        self.assertEqual(provider.last_usage, TokenUsage(11, 2))
        kwargs = mock_openai.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["stream_options"], {"include_usage": True})

    def test_mocked_sdk_without_usage_gives_none(self):
        mock_openai = MagicMock()  # every attribute is a MagicMock, not a number
        mock_openai.chat.completions.create.return_value.choices = [
            SimpleNamespace(message=SimpleNamespace(content="Hi"))
        ]
        with patch.dict("sys.modules", {"openai": mock_openai}):
            response = OpenAIProvider(api_key="sk-test").generate("Hi")
        self.assertIsNone(response.usage)

    def test_anthropic_reports_usage(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "content": [{"type": "text", "text": "A fork is your copy."}],
            "usage": {"input_tokens": 52, "output_tokens": 9},
        }
        with patch(
            "apps.ai_tutor.providers.anthropic.requests.post", return_value=resp
        ):
            provider = AnthropicProvider(api_key="test")
            response = provider.generate("Fork?")
            streamed = "".join(provider.stream("Fork?"))
        self.assertEqual(response.usage, TokenUsage(52, 9))
        self.assertEqual(streamed, "A fork is your copy.")
        self.assertEqual(provider.last_usage, TokenUsage(52, 9))

    def test_gemini_rest_reports_usage_with_thoughts(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Clone copies a repo."}]}}],
            "usageMetadata": {
                "promptTokenCount": 40,
                "candidatesTokenCount": 6,
                "thoughtsTokenCount": 4,
            },
        }
        with patch("apps.ai_tutor.providers.gemini.requests.post", return_value=resp):
            provider = GeminiProvider(api_key="test")
            response = provider._call_rest_api(
                "Clone?", "", None, "gemini-1.5-flash", "test", 0.0
            )
        self.assertEqual(response.usage, TokenUsage(40, 10))

    def test_router_exposes_the_serving_providers_usage(self):
        usage = TokenUsage(3, 4)
        router = SmartFailoverRouter(providers=[UsageProvider(usage=usage)])
        self.assertIsNone(router.last_usage)
        list(router.stream("Hi"))
        self.assertEqual(router.last_usage, usage)

    def test_sync_answer_counts_the_reported_usage(self):
        cache.clear()
        self.addCleanup(cache.clear)
        user = User.objects.create_user(username="sync-budget", password="pw-123456")
        provider = UsageProvider(usage=TokenUsage(input_tokens=80, output_tokens=20))
        with override_settings(OPENAI_API_KEY="sk-test"), use_router(provider):
            answer = AiTutorService.get_response(question="What is a PR?", user=user)
        self.assertEqual(answer, "Branches keep main safe.")
        today = token_budget.utc_day()
        self.assertEqual(token_budget.get_user_usage(user.pk, today), 100)
