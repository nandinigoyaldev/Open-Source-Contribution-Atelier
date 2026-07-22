import pytest
from django.test import RequestFactory
from django.utils import translation
from django.core.cache import cache

from apps.localization.middleware import LocaleMiddleware, resolve_locale


@pytest.fixture(autouse=True)
def clear_caches():
    resolve_locale.cache_clear()
    cache.clear()
    yield
    resolve_locale.cache_clear()
    cache.clear()


def test_resolve_locale_exact_match():
    # settings.LANGUAGES has en, es, fr, de, zh-hans
    assert resolve_locale("es") == "es"
    assert resolve_locale("fr") == "fr"
    assert resolve_locale("de") == "de"
    assert resolve_locale("zh-hans") == "zh-hans"


def test_resolve_locale_normalization_case():
    assert resolve_locale("ES") == "es"
    assert resolve_locale("Es-Es") == "es"  # Falls back to es
    assert resolve_locale("zh_HANS") == "zh-hans"


def test_resolve_locale_fallback_chain():
    # zh-hans-cn -> zh-hans
    assert resolve_locale("zh-hans-cn") == "zh-hans"
    # es-419 -> es
    assert resolve_locale("es-419") == "es"
    # fr-ch -> fr
    assert resolve_locale("fr-ch") == "fr"


def test_resolve_locale_q_factor_prioritization():
    # fr has q=0.9, es has q=0.8, fr is matched first
    assert resolve_locale("es;q=0.8, fr;q=0.9") == "fr"
    # even with fallback: zh-hans-cn (q=0.7) vs es (q=0.6) -> zh-hans
    assert resolve_locale("zh-hans-cn;q=0.7, es;q=0.6") == "zh-hans"


def test_resolve_locale_malformed_and_edge_cases():
    # Injection/weird characters should fall back to default (en-us)
    assert resolve_locale("es; DROP TABLE users;") == "en-us"
    assert resolve_locale("a" * 100) == "en-us"
    assert resolve_locale("") == "en-us"
    assert resolve_locale(None) == "en-us"
    assert (
        resolve_locale("invalid-locale-tag-with-many-subtags-that-is-too-long")
        == "en-us"
    )


def test_middleware_activates_language():
    rf = RequestFactory()
    middleware = LocaleMiddleware(lambda req: req)

    # Check ES
    request = rf.get("/", HTTP_ACCEPT_LANGUAGE="es")
    request.session = {}
    middleware(request)
    assert request.LANGUAGE_CODE == "es"

    # Check FR
    request = rf.get("/", HTTP_ACCEPT_LANGUAGE="fr")
    request.session = {}
    middleware(request)
    assert request.LANGUAGE_CODE == "fr"


def test_locale_switch_rate_limiting():
    rf = RequestFactory()
    middleware = LocaleMiddleware(lambda req: req)
    request = rf.get("/", HTTP_ACCEPT_LANGUAGE="en-us")
    session = {}
    request.session = session

    # Initially active is en-us
    middleware(request)
    assert request.LANGUAGE_CODE == "en-us"

    # Perform 10 switches: en -> es -> fr -> de -> zh-hans -> en -> es -> fr -> de -> zh-hans
    languages = ["es", "fr", "de", "zh-hans", "en", "es", "fr", "de", "zh-hans", "en"]
    for lang in languages:
        request = rf.get("/", HTTP_ACCEPT_LANGUAGE=lang)
        request.session = session
        middleware(request)

    # The 11th switch (to 'es') should be blocked due to rate-limiting
    request = rf.get("/", HTTP_ACCEPT_LANGUAGE="es")
    request.session = session
    middleware(request)

    # Since it is rate-limited, it keeps the previous active language ("zh-hans")
    assert request.LANGUAGE_CODE == "zh-hans"
