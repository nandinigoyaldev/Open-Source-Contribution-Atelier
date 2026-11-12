from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from apps.search import durable
from apps.search.models import SearchDocument, SearchIndexFailure
from apps.search.tasks import index_model_for_search, remove_model_from_search


class FakeApiError(Exception):
    def __init__(self, status_code, code=None):
        super().__init__(f"api error {status_code}")
        self.status_code = status_code
        self.code = code


class FakeIndex:
    """Stands in for a Meilisearch index; `failures` are raised one per call."""

    def __init__(self, failures=()):
        self.failures = list(failures)
        self.added = []
        self.deleted = []

    def _maybe_fail(self):
        if self.failures:
            exc = self.failures.pop(0)
            if exc is not None:
                raise exc

    def add_documents(self, docs):
        self._maybe_fail()
        self.added.append(docs)

    def delete_document(self, doc_id):
        self._maybe_fail()
        self.deleted.append(doc_id)


@pytest.fixture(autouse=True)
def no_sleep():
    with patch.object(durable.time, "sleep") as sleep:
        yield sleep


def _index(fake):
    return patch("apps.search.durable.get_meili_index", return_value=fake)


def _task(object_id=1, title="Hello"):
    index_model_for_search("auth", "user", object_id, title, "body text")


@pytest.mark.django_db
def test_transient_failure_is_retried_then_succeeds(no_sleep):
    fake = FakeIndex([ConnectionError("down"), FakeApiError(503)])
    with _index(fake):
        _task()
    assert len(fake.added) == 1
    assert no_sleep.call_count == 2
    assert SearchIndexFailure.objects.count() == 0


@pytest.mark.django_db
def test_permanent_error_is_recorded_once_without_retry(no_sleep):
    fake = FakeIndex([FakeApiError(400, "invalid_document_id")])
    with _index(fake):
        _task()
    no_sleep.assert_not_called()
    failure = SearchIndexFailure.objects.get()
    assert failure.operation == SearchIndexFailure.OP_INDEX
    assert failure.attempts == 1
    assert "400" in failure.last_error
    assert failure.document_id == str(SearchDocument.objects.get().id)


@pytest.mark.django_db
def test_exhausted_retries_record_attempts_and_truncate_error():
    fake = FakeIndex([ConnectionError("x" * 2000)] * 3)
    with _index(fake):
        _task()
    failure = SearchIndexFailure.objects.get()
    assert failure.attempts == durable.MAX_ATTEMPTS
    assert len(failure.last_error) <= durable.ERROR_MAX_LENGTH


@pytest.mark.django_db
def test_repeated_failure_updates_the_same_row():
    with _index(FakeIndex([FakeApiError(400)])):
        _task()
    first = SearchIndexFailure.objects.get()
    with _index(FakeIndex([FakeApiError(422)])):
        _task(title="Hello again")
    second = SearchIndexFailure.objects.get()
    assert second.pk == first.pk
    assert second.attempts == 2
    assert second.first_failed_at == first.first_failed_at
    assert second.last_failed_at >= first.last_failed_at
    assert "422" in second.last_error


@pytest.mark.django_db
def test_successful_index_clears_open_failure():
    with _index(FakeIndex([FakeApiError(400)])):
        _task()
    assert SearchIndexFailure.objects.count() == 1
    with _index(FakeIndex()):
        _task()
    assert SearchIndexFailure.objects.count() == 0


@pytest.mark.django_db
def test_failure_row_stores_no_document_text():
    with _index(FakeIndex([FakeApiError(400)])):
        _task(title="Secret title")
    failure = SearchIndexFailure.objects.get()
    stored = " ".join(
        str(getattr(failure, f.name)) for f in SearchIndexFailure._meta.fields
    )
    assert "Secret title" not in stored
    assert "body text" not in stored


@pytest.mark.django_db
def test_replay_pushes_current_data_and_clears_row():
    with _index(FakeIndex([FakeApiError(400)])):
        _task(title="Old title")
    # Newer data lands in the DB while the failure row is still open.
    SearchDocument.objects.update(title="Newer title")
    fake = FakeIndex()
    with (
        _index(fake),
        patch(
            "apps.search.management.commands.replay_search_failures.get_meili_index",
            return_value=fake,
        ),
    ):
        call_command("replay_search_failures", stdout=StringIO())
        call_command("replay_search_failures", stdout=StringIO())  # second run: no-op
    assert SearchIndexFailure.objects.count() == 0
    assert len(fake.added) == 1
    assert fake.added[0][0]["title"] == "Newer title"


@pytest.mark.django_db
def test_replay_keeps_row_when_still_failing():
    with _index(FakeIndex([FakeApiError(400)])):
        _task()
    fake = FakeIndex([FakeApiError(400)])
    with (
        _index(fake),
        patch(
            "apps.search.management.commands.replay_search_failures.get_meili_index",
            return_value=fake,
        ),
    ):
        call_command("replay_search_failures", stdout=StringIO())
    failure = SearchIndexFailure.objects.get()
    assert failure.attempts == 2


@pytest.mark.django_db
def test_replay_dry_run_does_not_touch_meilisearch():
    with _index(FakeIndex([FakeApiError(400)])):
        _task()
    out = StringIO()
    with patch(
        "apps.search.management.commands.replay_search_failures.get_meili_index"
    ) as get_index:
        call_command("replay_search_failures", "--dry-run", stdout=out)
    get_index.assert_not_called()
    assert "1 open failure" in out.getvalue()
    assert SearchIndexFailure.objects.count() == 1


@pytest.mark.django_db
def test_delete_failure_is_recorded_and_replay_is_idempotent():
    with _index(FakeIndex()):
        _task()
    doc_id = SearchDocument.objects.get().id

    with _index(FakeIndex([FakeApiError(400)])):
        remove_model_from_search("auth", "user", 1)
    assert SearchDocument.objects.count() == 0  # DB row is gone regardless
    failure = SearchIndexFailure.objects.get()
    assert failure.operation == SearchIndexFailure.OP_DELETE
    assert failure.document_id == str(doc_id)

    # Meilisearch already lost the document: 404 must count as success.
    fake = FakeIndex([FakeApiError(404, "document_not_found")])
    with (
        patch(
            "apps.search.management.commands.replay_search_failures.get_meili_index",
            return_value=fake,
        ),
        _index(fake),
    ):
        call_command("replay_search_failures", stdout=StringIO())
        call_command("replay_search_failures", stdout=StringIO())
    assert SearchIndexFailure.objects.count() == 0


@pytest.mark.django_db
def test_replay_of_index_failure_for_removed_document_just_clears():
    with _index(FakeIndex([FakeApiError(400)])):
        _task()
    SearchDocument.objects.all().delete()
    fake = FakeIndex()
    with (
        _index(fake),
        patch(
            "apps.search.management.commands.replay_search_failures.get_meili_index",
            return_value=fake,
        ),
    ):
        call_command("replay_search_failures", stdout=StringIO())
    assert SearchIndexFailure.objects.count() == 0
    assert fake.added == []


@pytest.mark.django_db
def test_no_meilisearch_configured_records_nothing():
    with patch("apps.search.durable.get_meili_index", return_value=None):
        _task()
        remove_model_from_search("auth", "user", 1)
    assert SearchIndexFailure.objects.count() == 0
    assert ContentType.objects.filter(app_label="auth", model="user").exists()
