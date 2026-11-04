"""Resumable exports: bounded memory, checkpoints, cancellation, cleanup, worker restarts (#3282)."""

import hashlib
import json
import os
import time
import uuid
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.db import OperationalError, connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.data_exports import datasets, runner, tasks
from apps.data_exports.models import ExportJob
from apps.notifications.models import Notification

ROWS = 50
CHUNK = 7


@pytest.fixture(autouse=True)
def export_env(settings, tmp_path):
    settings.EXPORT_ROOT = str(tmp_path / "exports")
    settings.EXPORT_CHUNK_ROWS = CHUNK
    settings.EXPORT_MAX_ATTEMPTS = 3
    settings.EXPORT_LEASE_SECONDS = 300
    settings.EXPORT_TTL_HOURS = 24
    settings.EXPORT_MAX_BYTES = 50 * 1024 * 1024
    settings.EXPORT_MAX_ACTIVE_PER_USER = 2
    settings.CELERY_TASK_ALWAYS_EAGER = False


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(
        username="other-export-user", email="other@example.com", password="x"
    )


def seed(user, n=ROWS, prefix="Note"):
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=user,
                notif_type="badge",
                title=f"{prefix} {i}",
                message=f'Message number {i}, with a comma and "quotes"',
                meta={"i": i},
            )
            for i in range(n)
        ]
    )


@pytest.fixture
def rows(db, user, other_user):
    seed(user)
    seed(other_user, 20, prefix="Secret")


def make_job(user, fmt="csv", dataset="notifications", **kwargs):
    kwargs.setdefault(
        "total_rows", datasets.count_rows(datasets.get_dataset("notifications"), user)
    )
    return ExportJob.objects.create(
        user=user, dataset=dataset, file_format=fmt, **kwargs
    )


def expected(user, fmt="csv"):
    """What an uninterrupted export of the user's notifications must contain, byte for byte."""
    ds = datasets.get_dataset("notifications")
    data = list(ds.queryset(user).order_by("pk").values_list(*ds.columns))
    return datasets.encode_header(ds.columns, fmt) + datasets.encode_rows(
        data, ds.columns, fmt
    )


def output(job):
    return (runner.export_root() / job.file_name).read_bytes()


def age_heartbeat(job, seconds=3600):
    ExportJob.objects.filter(pk=job.pk).update(
        heartbeat_at=timezone.now() - timedelta(seconds=seconds)
    )


def reload(job):
    job.refresh_from_db()
    return job


# ----------------------------------------------------------------------------------- basics


@pytest.mark.django_db
class TestPipeline:
    @pytest.mark.parametrize("fmt", ["csv", "ndjson"])
    def test_the_whole_dataset_is_written_and_nothing_of_anyone_elses(
        self, user, rows, fmt
    ):
        job = make_job(user, fmt)
        assert runner.run_job(job.id) == "completed"
        job = reload(job)
        assert output(job) == expected(user, fmt)
        assert job.rows_written == ROWS and job.status == "completed"
        assert job.sha256 == hashlib.sha256(output(job)).hexdigest()
        assert job.expires_at > timezone.now() and job.lease_token is None
        assert b"Secret" not in output(job)
        assert not (runner.export_root() / f"{job.id}.part").exists()

    def test_csv_has_a_header_and_one_line_per_row(self, user, rows):
        job = make_job(user)
        runner.run_job(job.id)
        lines = output(reload(job)).decode().split("\r\n")
        assert lines[0].startswith("id,recipient_id,sender_id,notif_type,title")
        assert len([ln for ln in lines if ln]) == ROWS + 1
        assert '"Message number 0, with a comma and ""quotes"""' in lines[1]

    def test_ndjson_is_one_json_object_per_line(self, user, rows):
        job = make_job(user, "ndjson")
        runner.run_job(job.id)
        parsed = [
            json.loads(line) for line in output(reload(job)).decode().splitlines()
        ]
        assert [p["title"] for p in parsed][:2] == ["Note 0", "Note 1"]
        assert len(parsed) == ROWS and parsed[0]["meta"] == {"i": 0}

    def test_an_empty_dataset_gives_a_header_only_file(self, user):
        job = make_job(user)
        assert runner.run_job(job.id) == "completed"
        assert output(reload(job)) == datasets.encode_header(
            datasets.get_dataset("notifications").columns, "csv"
        )

    def test_spreadsheet_formulas_in_user_text_are_neutralised(self, user, db):
        Notification.objects.create(
            recipient=user,
            notif_type="badge",
            title='=HYPERLINK("http://evil")',
            message="-2+3",
            meta={},
        )
        job = make_job(user)
        runner.run_job(job.id)
        text = output(reload(job)).decode()
        assert "'=HYPERLINK" in text and "'-2+3" in text
        assert ",=HYPERLINK" not in text

    def test_a_finished_job_is_not_run_again(self, user, rows):
        job = make_job(user)
        runner.run_job(job.id)
        assert runner.run_job(job.id) is None
        assert reload(job).attempts == 1

    def test_only_integer_primary_keys_can_be_registered(self, db):
        with pytest.raises(ValueError):
            datasets.register_dataset("bad", "Bad", "data_exports.ExportJob", "user")
        with pytest.raises(datasets.UnknownDataset):
            datasets.get_dataset("bad")

    def test_the_default_datasets_are_registered(self, db):
        keys = {d.key for d in datasets.all_datasets()}
        assert {
            "notifications",
            "lesson_progress",
            "quiz_attempts",
            "code_submissions",
            "sandbox_logs",
        } <= keys


@pytest.mark.django_db
class TestBoundedMemory:
    def test_no_step_reads_or_holds_more_than_one_chunk(self, user, rows):
        job = make_job(user)
        sizes = []
        real = datasets.encode_rows

        def spy(chunk, *args):
            sizes.append(len(chunk))
            return real(chunk, *args)

        with (
            CaptureQueriesContext(connection) as queries,
            patch.object(datasets, "encode_rows", spy),
        ):
            runner.run_job(job.id)
        data_queries = [
            q["sql"]
            for q in queries
            if "notifications_notification" in q["sql"] and "SELECT" in q["sql"]
        ]
        assert max(sizes) == CHUNK and sum(sizes) == ROWS
        assert (
            len(data_queries) == -(-ROWS // CHUNK) + 1
        )  # a full pass plus the empty last read
        assert all(f"LIMIT {CHUNK}" in sql for sql in data_queries)

    def test_the_file_grows_chunk_by_chunk_in_step_with_the_checkpoint(
        self, user, rows
    ):
        job = make_job(user)
        part = runner.export_root() / f"{job.id}.part"
        seen = []
        real = runner._checkpoint

        def check(j, last_pk, nrows, nbytes):
            real(j, last_pk, nrows, nbytes)
            seen.append((nrows, part.stat().st_size == nbytes))

        with patch.object(runner, "_checkpoint", check):
            runner.run_job(job.id)
        assert [r for r, _ in seen][-1] == ROWS
        assert all(ok for _, ok in seen)
        assert len(seen) == 1 + -(-ROWS // CHUNK)

    def test_a_file_over_the_size_limit_fails_instead_of_filling_the_disk(
        self, user, rows, settings
    ):
        settings.EXPORT_MAX_BYTES = 600
        job = make_job(user)
        assert runner.run_job(job.id) == "failed"
        job = reload(job)
        assert "limit" in job.error
        assert not list(runner.export_root().glob(f"{job.id}*"))


# ---------------------------------------------------------------------- worker restarts


def crash_at_checkpoint(n, *, after):
    """Make the n-th checkpoint kill the worker, before or after it is saved."""
    real = runner._checkpoint
    calls = {"n": 0}

    def maybe_crash(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == n and not after:
            raise KeyboardInterrupt("worker killed")
        real(*args, **kwargs)
        if calls["n"] == n and after:
            raise KeyboardInterrupt("worker killed")

    return patch.object(runner, "_checkpoint", maybe_crash)


@pytest.mark.django_db
class TestWorkerRestarts:
    TOTAL_CHECKPOINTS = 1 + -(-ROWS // CHUNK)

    @pytest.mark.parametrize("fmt", ["csv", "ndjson"])
    @pytest.mark.parametrize("after", [False, True], ids=["before-save", "after-save"])
    @pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 9])
    def test_a_job_killed_at_any_checkpoint_resumes_to_the_identical_file(
        self, user, rows, n, after, fmt
    ):
        reference = make_job(user, fmt)
        runner.run_job(reference.id)
        want = output(reload(reference))

        job = make_job(user, fmt)
        with crash_at_checkpoint(n, after=after), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        killed = reload(job)
        assert killed.status == "running" and killed.attempts == 1

        age_heartbeat(job)  # the worker is gone: its lease runs out
        assert runner.run_job(job.id) == "completed"
        job = reload(job)
        assert output(job) == want == expected(user, fmt)
        assert job.attempts == 2 and job.rows_written == ROWS

    def test_the_resume_does_not_redo_the_work_already_checkpointed(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(4, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        done = reload(job).checkpoint["rows"]
        assert done == 3 * CHUNK

        age_heartbeat(job)
        read_from = []
        real = datasets.fetch_chunk

        def spy(dataset, owner, last_pk, size):
            read_from.append(last_pk)
            return real(dataset, owner, last_pk, size)

        with patch.object(datasets, "fetch_chunk", spy):
            runner.run_job(job.id)
        assert (
            read_from[0] == reload(job).checkpoint["last_pk"] - (ROWS - done)
            or read_from[0] is not None
        )
        assert len(read_from) == -(-(ROWS - done) // CHUNK) + 1

    def test_bytes_written_after_the_last_checkpoint_are_discarded(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(3, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        part = runner.part_path(job)
        with open(part, "ab") as fh:  # a chunk the dead worker half wrote
            fh.write(b"9999,torn,row-without-newline")
        age_heartbeat(job)
        runner.run_job(job.id)
        assert output(reload(job)) == expected(user)

    def test_a_file_shorter_than_its_checkpoint_starts_over(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(4, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        runner.part_path(job).write_bytes(
            b"lost"
        )  # disk trouble: the file no longer matches
        age_heartbeat(job)
        runner.run_job(job.id)
        assert output(reload(job)) == expected(user)

    def test_a_missing_part_file_starts_over(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(4, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        runner.part_path(job).unlink()
        age_heartbeat(job)
        runner.run_job(job.id)
        assert output(reload(job)) == expected(user)

    def test_a_worker_killed_while_renaming_the_finished_file(self, user, rows):
        job = make_job(user)
        with (
            patch.object(runner.os, "replace", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            runner.run_job(job.id)
        assert runner.part_path(job).exists()
        age_heartbeat(job)
        assert runner.run_job(job.id) == "completed"
        assert output(reload(job)) == expected(user)

    def test_a_worker_killed_after_renaming_but_before_saying_so(self, user, rows):
        job = make_job(user)
        with (
            patch.object(runner, "_complete", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            runner.run_job(job.id)
        assert runner.final_path(job).exists() and not runner.part_path(job).exists()
        age_heartbeat(job)
        assert runner.run_job(job.id) == "completed"
        job = reload(job)
        assert output(job) == expected(user) and job.rows_written == ROWS

    def test_a_finished_file_of_the_wrong_size_is_not_trusted(self, user, rows):
        job = make_job(user)
        with (
            patch.object(runner, "_complete", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            runner.run_job(job.id)
        runner.final_path(job).write_bytes(b"truncated")
        age_heartbeat(job)
        runner.run_job(job.id)
        assert output(reload(job)) == expected(user)

    def test_rows_added_while_the_worker_was_down_are_picked_up(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(3, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        seed(user, 3, prefix="Late")
        age_heartbeat(job)
        runner.run_job(job.id)
        assert output(reload(job)).count(b"Late") == 3

    def test_a_running_job_with_a_fresh_heartbeat_is_left_to_its_worker(
        self, user, rows
    ):
        job = make_job(user)
        with crash_at_checkpoint(3, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        assert (
            runner.run_job(job.id) is None
        )  # heartbeat is recent: someone may still be on it

    def test_a_worker_that_lost_its_lease_cannot_write_anything(self, user, rows):
        job = make_job(user)
        first = runner.claim(job.id)
        age_heartbeat(job)
        second = runner.claim(job.id)
        assert first is not None and second is not None
        assert second.lease_token != first.lease_token

        with pytest.raises(runner.LostLease):
            runner._checkpoint(first, 5, 5, 100)
        assert reload(job).checkpoint == {}
        assert (
            runner._still_mine.__name__
        )  # the stale worker also stops at its next chunk
        with pytest.raises(runner.LostLease):
            runner._still_mine(first)
        assert runner._still_mine(second) is True

    def test_a_job_that_keeps_killing_its_workers_is_eventually_failed(
        self, user, rows, settings
    ):
        settings.EXPORT_MAX_ATTEMPTS = 2
        job = make_job(user)
        for _ in range(2):
            with crash_at_checkpoint(2, after=True), pytest.raises(KeyboardInterrupt):
                runner.run_job(job.id)
            age_heartbeat(job)
        assert runner.run_job(job.id) == "failed"
        job = reload(job)
        assert "too many attempts" in job.error
        assert not runner.part_path(job).exists()


# ------------------------------------------------------------------------------ errors


@pytest.mark.django_db
class TestFailuresAndRetries:
    def fail_nth_read(self, n, exc):
        real = datasets.fetch_chunk
        calls = {"n": 0}

        def wrapper(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == n:
                raise exc
            return real(*args, **kwargs)

        return patch.object(datasets, "fetch_chunk", wrapper)

    def test_a_transient_error_requeues_the_job_and_keeps_its_progress(
        self, user, rows
    ):
        job = make_job(user)
        with self.fail_nth_read(4, OperationalError("server closed the connection")):
            assert runner.run_job(job.id) == "queued"
        job = reload(job)
        assert job.status == "queued" and job.lease_token is None
        assert "OperationalError" in job.error
        assert job.next_run_at > timezone.now()
        assert job.checkpoint["rows"] == 3 * CHUNK
        assert runner.part_path(job).exists()

        assert runner.run_job(job.id) == "completed"
        job = reload(job)
        assert output(job) == expected(user) and job.attempts == 2 and job.error == ""

    def test_a_job_that_keeps_failing_transiently_is_failed_after_its_attempts(
        self, user, rows
    ):
        job = make_job(user)
        statuses = []
        with patch.object(
            datasets, "fetch_chunk", side_effect=OperationalError("down")
        ):
            for _ in range(3):
                statuses.append(runner.run_job(job.id))
        assert statuses == ["queued", "queued", "failed"]
        job = reload(job)
        assert job.attempts == 3 and not runner.part_path(job).exists()

    def test_a_permanent_error_fails_at_once(self, user, rows):
        job = make_job(user)
        with patch.object(datasets, "fetch_chunk", side_effect=ValueError("bad data")):
            assert runner.run_job(job.id) == "failed"
        job = reload(job)
        assert job.attempts == 1 and "bad data" in job.error

    def test_an_unknown_dataset_fails_at_once(self, user, rows):
        job = make_job(user, dataset="does-not-exist", total_rows=0)
        assert runner.run_job(job.id) == "failed"
        assert "does-not-exist" in reload(job).error

    def test_the_backoff_grows(self):
        assert [int(runner.backoff(n).total_seconds()) for n in (1, 2, 3, 10)] == [
            60,
            120,
            240,
            3600,
        ]


# --------------------------------------------------------------------------- cancellation


@pytest.mark.django_db
class TestCancellation:
    def test_a_running_job_stops_at_the_next_chunk_and_leaves_no_file(self, user, rows):
        job = make_job(user)
        real = datasets.fetch_chunk
        calls = {"n": 0}

        def cancelling(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 3:
                ExportJob.objects.filter(pk=job.pk).update(cancel_requested=True)
            return real(*args, **kwargs)

        with patch.object(datasets, "fetch_chunk", cancelling):
            assert runner.run_job(job.id) == "cancelled"
        job = reload(job)
        assert job.status == "cancelled" and job.finished_at and job.lease_token is None
        assert calls["n"] == 3  # it did not read on after the request
        assert not list(runner.export_root().glob(f"{job.id}*"))

    def test_a_cancel_request_on_a_job_that_was_never_started(self, user, rows):
        job = make_job(user, cancel_requested=True)
        assert runner.run_job(job.id) == "cancelled"

    def test_a_cancelled_job_cannot_be_resumed(self, user, rows):
        job = make_job(user)
        ExportJob.objects.filter(pk=job.pk).update(status="cancelled")
        assert runner.run_job(job.id) is None


# ------------------------------------------------------------------------------ cleanup


@pytest.mark.django_db
class TestSweep:
    def stub_enqueue(self):
        queued = []
        return queued, patch.object(
            tasks, "enqueue", side_effect=lambda job_id, delay=0: queued.append(job_id)
        )

    def test_a_job_whose_worker_died_is_requeued_and_resumed(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(4, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        age_heartbeat(job)
        queued, stub = self.stub_enqueue()
        with stub:
            summary = tasks.sweep_exports()
        assert summary["requeued"] == 1 and queued == [job.id]
        assert reload(job).status == "queued"
        assert runner.run_job(job.id) == "completed"
        assert output(reload(job)) == expected(user)

    def test_a_job_out_of_attempts_is_failed_and_its_file_removed(
        self, user, rows, settings
    ):
        settings.EXPORT_MAX_ATTEMPTS = 1
        job = make_job(user)
        with crash_at_checkpoint(3, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        age_heartbeat(job)
        queued, stub = self.stub_enqueue()
        with stub:
            summary = tasks.sweep_exports()
        assert summary["failed"] == 1 and queued == []
        assert reload(job).status == "failed"
        assert not runner.part_path(job).exists()

    def test_a_job_with_a_recent_heartbeat_is_left_alone(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(3, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        queued, stub = self.stub_enqueue()
        with stub:
            assert tasks.sweep_exports()["requeued"] == 0
        assert reload(job).status == "running" and queued == []

    def test_due_and_unattended_queued_jobs_are_started_but_not_ones_waiting_to_retry(
        self, user, rows
    ):
        due = make_job(user, next_run_at=timezone.now() - timedelta(seconds=1))
        waiting = make_job(user, next_run_at=timezone.now() + timedelta(minutes=10))
        stuck = make_job(user)
        ExportJob.objects.filter(pk=stuck.pk).update(
            created_at=timezone.now() - timedelta(hours=1)
        )
        fresh = make_job(user)
        queued, stub = self.stub_enqueue()
        with stub:
            tasks.sweep_exports()
        assert set(queued) == {due.id, stuck.id}
        assert waiting.id not in queued and fresh.id not in queued

    def test_a_queued_job_with_a_cancel_request_is_cancelled_without_a_worker(
        self, user, rows
    ):
        job = make_job(
            user,
            cancel_requested=True,
            next_run_at=timezone.now() - timedelta(seconds=1),
        )
        queued, stub = self.stub_enqueue()
        with stub:
            summary = tasks.sweep_exports()
        assert summary["cancelled"] == 1 and queued == []
        assert reload(job).status == "cancelled"

    def test_finished_exports_are_deleted_when_their_window_closes(self, user, rows):
        keep = make_job(user)
        gone = make_job(user)
        runner.run_job(keep.id)
        runner.run_job(gone.id)
        ExportJob.objects.filter(pk=gone.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        gone_path = runner.export_root() / reload(gone).file_name
        keep_path = runner.export_root() / reload(keep).file_name
        assert tasks.sweep_exports()["expired"] == 1
        assert reload(gone).status == "expired" and not gone_path.exists()
        assert reload(keep).status == "completed" and keep_path.exists()

    def test_files_of_failed_and_cancelled_jobs_are_removed(self, user, rows):
        failed = make_job(user, status="failed")
        cancelled = make_job(user, status="cancelled")
        for job in (failed, cancelled):
            runner.part_path(job).write_bytes(b"leftover")
        assert tasks.sweep_exports()["files_removed"] == 2
        assert not list(runner.export_root().glob("*.part"))

    def test_files_that_belong_to_no_job_are_removed_once_they_are_old(
        self, user, rows
    ):
        root = runner.export_root()
        old = root / f"{uuid.uuid4()}.part"
        new = root / f"{uuid.uuid4()}.csv"
        old.write_bytes(b"x")
        new.write_bytes(b"x")
        two_days_ago = time.time() - 2 * 24 * 3600
        os.utime(old, (two_days_ago, two_days_ago))
        stranger = root / "notes.txt"
        stranger.write_bytes(b"not ours")
        tasks.sweep_exports()
        assert not old.exists() and new.exists() and stranger.exists()

    def test_the_file_of_a_running_job_is_never_removed(self, user, rows):
        job = make_job(user)
        with crash_at_checkpoint(3, after=True), pytest.raises(KeyboardInterrupt):
            runner.run_job(job.id)
        tasks.sweep_exports()
        assert runner.part_path(job).exists()

    def test_the_sweep_is_scheduled(self):
        from django.conf import settings

        assert (
            settings.CELERY_BEAT_SCHEDULE["sweep-data-exports"]["task"]
            == "data_exports.sweep_exports"
        )


# ------------------------------------------------------------------------------------- API


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def completed_job(user, fmt="csv"):
    job = make_job(user, fmt)
    runner.run_job(job.id)
    return reload(job)


@pytest.mark.django_db
class TestApi:
    def test_login_is_required(self, rows):
        anonymous: Any = APIClient()
        assert anonymous.get("/api/exports/").status_code == 401
        assert (
            anonymous.post("/api/exports/", {"dataset": "notifications"}).status_code
            == 401
        )

    def test_creating_an_export_runs_it_and_offers_the_download(
        self, client, user, rows
    ):
        # a worker that takes the job as soon as it is queued
        with patch(
            "apps.data_exports.views.enqueue",
            side_effect=lambda job_id, delay=0: runner.run_job(job_id),
        ):
            res = client.post(
                "/api/exports/",
                {"dataset": "notifications", "format": "ndjson"},
                format="json",
            )
        assert res.status_code == 202
        body = res.json()
        assert body["status"] == "completed" and body["progress_percent"] == 100
        assert body["rows_written"] == ROWS and body["total_rows"] == ROWS
        assert body["downloadable"] and body["download_url"].endswith(
            f"/api/exports/{body['id']}/download/"
        )
        assert body["sha256"]

    def test_a_queued_export_reports_its_state(self, client, user, rows):
        with patch("apps.data_exports.views.enqueue"):
            res = client.post(
                "/api/exports/", {"dataset": "notifications"}, format="json"
            )
        assert res.status_code == 202
        body = res.json()
        assert (
            body["status"] == "queued"
            and body["format"] == "csv"
            and not body["downloadable"]
        )

    def test_progress_is_an_estimate_against_the_size_at_creation(
        self, client, user, rows
    ):
        job = make_job(user)
        ExportJob.objects.filter(pk=job.pk).update(status="running", rows_written=25)
        assert client.get(f"/api/exports/{job.id}/").json()["progress_percent"] == 50

    def test_bad_requests(self, client, rows):
        res = client.post("/api/exports/", {"dataset": "passwords"}, format="json")
        assert res.status_code == 400 and "notifications" in res.json()["datasets"]
        res = client.post(
            "/api/exports/",
            {"dataset": "notifications", "format": "xlsx"},
            format="json",
        )
        assert res.status_code == 400 and res.json()["formats"] == ["csv", "ndjson"]
        assert client.post("/api/exports/", {}, format="json").status_code == 400

    def test_a_user_can_only_have_a_few_exports_active(self, client, user, rows):
        with patch("apps.data_exports.views.enqueue"):
            for _ in range(2):
                assert (
                    client.post(
                        "/api/exports/", {"dataset": "notifications"}, format="json"
                    ).status_code
                    == 202
                )
            res = client.post(
                "/api/exports/", {"dataset": "notifications"}, format="json"
            )
        assert (
            res.status_code == 429 and res.json()["error"] == "too_many_active_exports"
        )

    def test_the_list_shows_only_my_exports_and_what_can_be_exported(
        self, client, user, other_user, rows
    ):
        mine = make_job(user)
        theirs = make_job(other_user)
        body = client.get("/api/exports/").json()
        assert [j["id"] for j in body["results"]] == [str(mine.id)]
        assert "notifications" in [d["key"] for d in body["datasets"]] and body[
            "formats"
        ] == ["csv", "ndjson"]
        assert str(theirs.id) not in str(body)

    def test_other_peoples_exports_do_not_exist_for_me(
        self, client, user, other_user, rows
    ):
        theirs = completed_job(other_user)
        for path in ("", "cancel/", "download/"):
            method = client.post if path == "cancel/" else client.get
            assert method(f"/api/exports/{theirs.id}/{path}").status_code == 404

    def test_cancelling_a_queued_export(self, client, user, rows):
        job = make_job(user)
        res = client.post(f"/api/exports/{job.id}/cancel/")
        assert res.status_code == 202 and res.json()["status"] == "cancelled"

    def test_cancelling_a_running_export_asks_the_worker_to_stop(
        self, client, user, rows
    ):
        job = make_job(user)
        ExportJob.objects.filter(pk=job.pk).update(status="running")
        res = client.post(f"/api/exports/{job.id}/cancel/")
        assert res.status_code == 202 and res.json()["cancel_requested"] is True
        assert reload(job).status == "running"

    def test_a_finished_export_cannot_be_cancelled(self, client, user, rows):
        job = completed_job(user)
        assert client.post(f"/api/exports/{job.id}/cancel/").status_code == 409

    def test_download(self, client, user, rows):
        job = completed_job(user)
        res = client.get(f"/api/exports/{job.id}/download/")
        assert res.status_code == 200
        body = b"".join(res.streaming_content)
        assert body == expected(user)
        assert res["Content-Type"].startswith("text/csv")
        assert (
            res["Content-Disposition"].startswith("attachment;")
            and ".csv" in res["Content-Disposition"]
        )
        assert (
            res["Accept-Ranges"] == "bytes"
            and res["X-Content-Type-Options"] == "nosniff"
        )
        assert res["ETag"] == f'"{job.sha256}"' and res["Content-Length"] == str(
            len(body)
        )

    def test_download_before_it_is_ready_or_after_it_expired(self, client, user, rows):
        job = make_job(user)
        assert client.get(f"/api/exports/{job.id}/download/").status_code == 409
        done = completed_job(user)
        ExportJob.objects.filter(pk=done.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        assert client.get(f"/api/exports/{done.id}/download/").status_code == 410
        ExportJob.objects.filter(pk=done.pk).update(status="expired")
        assert client.get(f"/api/exports/{done.id}/download/").status_code == 410

    def test_a_deleted_file_reads_as_expired(self, client, user, rows):
        job = completed_job(user)
        (runner.export_root() / job.file_name).unlink()
        assert client.get(f"/api/exports/{job.id}/download/").status_code == 410

    @pytest.mark.parametrize(
        "spec,start,end",
        [
            ("bytes=10-19", 10, 19),
            ("bytes=-5", None, None),
            ("bytes=40-", 40, None),
            ("bytes=0-0", 0, 0),
        ],
    )
    def test_an_interrupted_download_can_resume_with_a_range(
        self, client, user, rows, spec, start, end
    ):
        job = completed_job(user)
        whole = expected(user)
        res = client.get(f"/api/exports/{job.id}/download/", HTTP_RANGE=spec)
        assert res.status_code == 206
        chunk = b"".join(res.streaming_content)
        if spec == "bytes=-5":
            start, end = len(whole) - 5, len(whole) - 1
        end = len(whole) - 1 if end is None else end
        assert chunk == whole[start : end + 1]
        assert res["Content-Range"] == f"bytes {start}-{end}/{len(whole)}"
        assert res["Content-Length"] == str(len(chunk))

    @pytest.mark.parametrize(
        "spec", ["bytes=99999999-", "bytes=5-2", "bytes=abc", "items=1-2", "bytes=-"]
    )
    def test_a_range_that_cannot_be_served(self, client, user, rows, spec):
        job = completed_job(user)
        res = client.get(f"/api/exports/{job.id}/download/", HTTP_RANGE=spec)
        assert res.status_code == 416
        assert res["Content-Range"] == f"bytes */{len(expected(user))}"

    def test_putting_the_pieces_of_a_ranged_download_together_gives_the_file(
        self, client, user, rows
    ):
        job = completed_job(user, "ndjson")
        whole = expected(user, "ndjson")
        got, pos = b"", 0
        while pos < len(whole):
            res = client.get(
                f"/api/exports/{job.id}/download/",
                HTTP_RANGE=f"bytes={pos}-{pos + 1499}",
            )
            piece = b"".join(res.streaming_content)
            got, pos = got + piece, pos + len(piece)
        assert got == whole
