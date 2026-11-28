import logging
from typing import Any, Dict

import pytest
import requests

from apps.audit.models import AuditChainHead, AuditEvent
from apps.audit.tasks import publish_audit_checkpoints

pytestmark = pytest.mark.django_db

URL = "https://ledger.example.test/append?token=s3cret"


@pytest.fixture(autouse=True)
def empty_chains(settings):
    settings.AUDIT_CHECKPOINT_URL = ""
    AuditEvent._base_manager.all().delete()
    AuditChainHead._default_manager.filter(chain="audit").delete()


@pytest.fixture
def receiver(settings, monkeypatch):
    settings.AUDIT_CHECKPOINT_URL = URL
    calls = []
    answer: Dict[str, Any] = {"status": 201}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if "error" in answer:
            raise answer["error"]
        response = requests.Response()
        response.status_code = answer["status"]
        return response

    monkeypatch.setattr("apps.audit.tasks.requests.post", post)
    return calls, answer


def make_event(number=1):
    return AuditEvent._default_manager.create(
        action="created", resource_type="test.checkpoint", resource_id=str(number)
    )


def test_head_is_logged_and_sent(receiver, caplog):
    calls, _ = receiver
    make_event(1)
    head = make_event(2)
    expected = [f"audit:2:{head.hash}"]

    with caplog.at_level(logging.INFO, logger="apps.audit.tasks"):
        assert publish_audit_checkpoints() == expected

    assert f"Audit chain checkpoint {expected[0]}" in caplog.text
    ((url, sent),) = calls
    assert url == URL
    assert sent["json"] == {"checkpoints": expected, "failed": []}
    assert sent["timeout"] and sent["allow_redirects"] is False


def test_without_a_url_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(
        "apps.audit.tasks.requests.post",
        lambda *args, **kwargs: pytest.fail("no request expected"),
    )
    event = make_event()

    assert publish_audit_checkpoints() == [f"audit:1:{event.hash}"]


def test_empty_chains_send_nothing(receiver):
    calls, _ = receiver

    assert publish_audit_checkpoints() == []
    assert calls == []


def test_tampered_chain_is_reported_not_published(receiver):
    calls, _ = receiver
    event = make_event()
    AuditEvent._base_manager.filter(pk=event.pk).update(resource_id="forged")

    with pytest.raises(RuntimeError, match="verification failed: audit"):
        publish_audit_checkpoints()

    ((_, sent),) = calls
    assert sent["json"] == {"checkpoints": [], "failed": ["audit"]}


@pytest.mark.parametrize(
    "answer",
    [
        {"status": 302},
        {"status": 500},
        {"error": requests.ConnectionError(f"cannot reach {URL}")},
    ],
)
def test_undelivered_checkpoints_fail_without_leaking_the_url(receiver, caplog, answer):
    receiver[1].update(answer)
    make_event()

    with pytest.raises(RuntimeError, match="not delivered") as failure:
        publish_audit_checkpoints()

    assert "s3cret" not in str(failure.value) + caplog.text
