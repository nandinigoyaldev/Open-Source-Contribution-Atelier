import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from apps.content import tasks
from apps.content.models import CurriculumImport, Lesson
from apps.content.services import curriculum_import as ci
from apps.content.services import curriculum_import_jobs as jobs

from .curriculum_import_helpers import sample_zip

pytestmark = pytest.mark.django_db

BRANCHES = "module-2/branches.md"
SAMPLE_SLUGS = {"sample-what-is-git", "sample-first-commit", "sample-branches"}


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.CURRICULUM_IMPORT_CHUNK_SIZE = 1


def new_import(data=None):
    return jobs.create_import(data or sample_zip(), name="sample.zip")


def previewed(data=None):
    imp = jobs.run_validation(new_import(data).pk)
    assert imp.status == CurriculumImport.PREVIEWED, imp.report
    return imp


# --- validation -------------------------------------------------------------


def test_clean_archive_becomes_previewed_with_plan():
    imp = previewed()
    assert imp.cursor == imp.total_lessons == 3
    assert imp.report["counts"] == {"modules": 2, "lessons": 3, "quizzes": 2}
    assert sorted(imp.report["plan"]["create"]) == sorted(SAMPLE_SLUGS)
    assert imp.report["plan"]["update"] == []
    assert not Lesson.objects.filter(slug__in=SAMPLE_SLUGS).exists()


def test_validation_never_writes_lessons_and_reports_problems():
    bad = sample_zip({BRANCHES: "[x](javascript:alert(1))"})
    imp = jobs.run_validation(new_import(bad).pk)
    assert imp.status == CurriculumImport.FAILED
    assert imp.report["problems"][0]["code"] == "unsafe_url"
    assert imp.report["problem_count"] == 1
    assert Lesson.objects.count() == 0


def test_unreadable_archive_fails_with_a_report():
    imp = jobs.run_validation(new_import(b"not a zip").pk)
    assert imp.status == CurriculumImport.FAILED
    assert imp.report["problems"][0]["code"] == "bad_archive"


def test_problem_list_is_capped(monkeypatch):
    monkeypatch.setattr(jobs, "MAX_REPORTED_PROBLEMS", 1)
    bad = sample_zip({BRANCHES: "[a](javascript:x) [b](javascript:y)"})
    imp = jobs.run_validation(new_import(bad).pk)
    assert imp.report["problem_count"] == 2
    assert len(imp.report["problems"]) == 1
    assert imp.report["problems_truncated"] is True


def test_plan_marks_existing_lessons_as_update():
    Lesson.objects.create(
        slug="sample-branches",
        title="Old",
        summary="s",
        content="c",
        difficulty="beginner",
    )
    imp = previewed()
    assert imp.report["plan"]["update"] == ["sample-branches"]
    assert len(imp.report["plan"]["create"]) == 2


# --- resume after a worker crash -------------------------------------------


class WorkerCrash(Exception):
    pass


def test_validation_resumes_from_cursor_after_worker_crash(monkeypatch):
    imp = new_import()
    real = ci.validate_lesson_file
    calls = []

    def crashing(zf, entry, slugs):
        calls.append(entry.slug)
        if len(calls) == 3:  # third lesson: the worker dies mid-chunk
            raise WorkerCrash("simulated crash")
        return real(zf, entry, slugs)

    monkeypatch.setattr(ci, "validate_lesson_file", crashing)
    with pytest.raises(WorkerCrash):
        jobs.run_validation(imp.pk)

    imp.refresh_from_db()
    assert imp.status == CurriculumImport.VALIDATING
    assert imp.cursor == 2  # two chunks of one lesson were committed
    assert len(imp.report["plan"]["create"]) == 2

    # A fresh worker picks the same row up again and only touches what is left.
    resumed = []

    def spy(zf, entry, slugs):
        resumed.append(entry.slug)
        return real(zf, entry, slugs)

    monkeypatch.setattr(ci, "validate_lesson_file", spy)
    imp = jobs.run_validation(imp.pk)
    assert resumed == ["sample-branches"]
    assert imp.status == CurriculumImport.PREVIEWED
    assert imp.cursor == 3

    fresh = previewed()
    assert imp.report == fresh.report


def test_resume_keeps_problems_found_before_the_crash(monkeypatch):
    bad = sample_zip({"module-1/what-is-git.md": "[x](javascript:alert(1))"})
    imp = new_import(bad)
    real = ci.validate_lesson_file
    state = {"n": 0}

    def crash_on_second(zf, entry, slugs):
        state["n"] += 1
        if state["n"] == 2:
            raise WorkerCrash()
        return real(zf, entry, slugs)

    monkeypatch.setattr(ci, "validate_lesson_file", crash_on_second)
    with pytest.raises(WorkerCrash):
        jobs.run_validation(imp.pk)
    monkeypatch.setattr(ci, "validate_lesson_file", real)
    imp = jobs.run_validation(imp.pk)
    assert imp.status == CurriculumImport.FAILED
    assert imp.report["problem_count"] == 1


def test_validation_task_is_idempotent_once_finished():
    imp = previewed()
    again = jobs.run_validation(imp.pk)
    assert again.status == CurriculumImport.PREVIEWED
    assert again.report == imp.report


# --- publishing -------------------------------------------------------------


def test_publish_creates_lessons_modules_and_prerequisites():
    imp = jobs.run_publish(previewed().pk)
    assert imp.status == CurriculumImport.PUBLISHED
    assert imp.report["published"] == {"created": 3, "updated": 0, "unchanged": 0}
    lessons = {lesson.slug: lesson for lesson in Lesson.objects.all()}
    assert set(lessons) == SAMPLE_SLUGS
    branches = lessons["sample-branches"]
    assert branches.category == "Branching"
    assert branches.difficulty == "intermediate"
    assert branches.order == 30
    assert list(branches.prerequisites.values_list("slug", flat=True)) == [
        "sample-first-commit"
    ]
    # front matter is stripped from the stored body
    assert not lessons["sample-what-is-git"].content.startswith("---")


def test_rerunning_the_same_archive_is_a_noop():
    jobs.run_publish(previewed().pk)
    before = (
        list(
            Lesson.objects.order_by("slug").values_list("slug", "updated_at", "content")
        )
        if hasattr(Lesson, "updated_at")
        else None
    )
    second = previewed()
    assert second.report["plan"]["unchanged"] and not second.report["plan"]["create"]
    assert len(second.report["plan"]["unchanged"]) == 3
    second = jobs.run_publish(second.pk)
    assert second.report["published"] == {"created": 0, "updated": 0, "unchanged": 3}
    assert Lesson.objects.count() == 3
    if before is not None:
        assert before == list(
            Lesson.objects.order_by("slug").values_list("slug", "updated_at", "content")
        )


def test_changed_lesson_is_updated_not_duplicated():
    jobs.run_publish(previewed().pk)
    changed = sample_zip({BRANCHES: "## Branches v2\n\nNew text."})
    imp = jobs.run_publish(previewed(changed).pk)
    assert imp.report["published"] == {"created": 0, "updated": 1, "unchanged": 2}
    assert Lesson.objects.get(slug="sample-branches").content.startswith(
        "## Branches v2"
    )
    assert Lesson.objects.count() == 3


def test_publishing_a_published_import_again_does_nothing():
    imp = jobs.run_publish(previewed().pk)
    count = Lesson.objects.count()
    assert jobs.run_publish(imp.pk).status == CurriculumImport.PUBLISHED
    assert Lesson.objects.count() == count


def test_only_previewed_imports_can_be_published():
    failed = jobs.run_validation(new_import(sample_zip({BRANCHES: "[x](data:x)"})).pk)
    with pytest.raises(jobs.ImportStateError):
        jobs.run_publish(failed.pk)
    validating = new_import()
    with pytest.raises(jobs.ImportStateError):
        jobs.run_publish(validating.pk)
    assert Lesson.objects.count() == 0


def test_failed_publish_rolls_back_and_leaves_existing_curriculum(monkeypatch):
    existing = Lesson.objects.create(
        slug="sample-first-commit",
        title="Original",
        summary="orig",
        content="original body",
        difficulty="beginner",
        order=5,
    )
    other = Lesson.objects.create(
        slug="unrelated", title="U", summary="u", content="u", difficulty="beginner"
    )
    imp = previewed()
    before = list(Lesson.objects.order_by("id").values())

    real_save = Lesson.save
    saves = []

    def flaky_save(self, *args, **kwargs):
        saves.append(self.slug)
        if len(saves) == 3:  # two lessons are already written when this blows up
            raise RuntimeError("disk full")
        return real_save(self, *args, **kwargs)

    monkeypatch.setattr(Lesson, "save", flaky_save)
    result = jobs.run_publish(imp.pk)
    monkeypatch.undo()

    assert len(saves) == 3
    assert result.status == CurriculumImport.FAILED
    assert "RuntimeError: disk full" in result.report["publish_error"]
    assert "rolled back" in result.error
    assert list(Lesson.objects.order_by("id").values()) == before
    existing.refresh_from_db()
    assert existing.content == "original body" and existing.title == "Original"
    assert Lesson.objects.filter(slug="unrelated").first().pk == other.pk
    assert not Lesson.objects.filter(
        slug__in=["sample-what-is-git", "sample-branches"]
    ).exists()


def test_failed_prerequisite_step_also_rolls_back(monkeypatch):
    imp = previewed()
    real = jobs._apply

    def apply_then_fail(*args, **kwargs):
        real(*args, **kwargs)  # every write succeeded...
        raise RuntimeError("late failure")  # ...but the transaction must not commit

    monkeypatch.setattr(jobs, "_apply", apply_then_fail)
    result = jobs.run_publish(imp.pk)
    assert result.status == CurriculumImport.FAILED
    assert Lesson.objects.count() == 0


def test_tampered_archive_is_not_published():
    imp = previewed()
    with open(imp.archive.path, "wb") as handle:
        handle.write(sample_zip({BRANCHES: "## swapped after validation"}))
    result = jobs.run_publish(imp.pk)
    assert result.status == CurriculumImport.FAILED
    assert "checksum" in result.error
    assert Lesson.objects.count() == 0


def test_interrupted_publish_can_be_retried():
    imp = previewed()
    CurriculumImport.objects.filter(pk=imp.pk).update(
        status=CurriculumImport.PUBLISHING
    )
    result = jobs.run_publish(imp.pk)
    assert result.status == CurriculumImport.PUBLISHED
    assert Lesson.objects.count() == 3


def test_oversized_upload_is_refused(settings):
    settings.CURRICULUM_IMPORT_MAX_ARCHIVE_BYTES = 10
    with pytest.raises(ci.ArchiveError):
        jobs.create_import(sample_zip())


# --- admin API --------------------------------------------------------------


@pytest.fixture(autouse=True)
def run_tasks_inline(monkeypatch):
    """No Celery app is configured in the test process, so run ``.delay`` inline
    (what CELERY_TASK_ALWAYS_EAGER would do)."""
    for task in (tasks.validate_curriculum_import, tasks.publish_curriculum_import):
        monkeypatch.setattr(task, "delay", task)


@pytest.fixture
def admin_client():
    user = get_user_model().objects.create_user(
        username="imp-admin", email="a@example.com", password="pw123456", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user)
    return client


def upload(client, data=None, name="curriculum.zip"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return client.post(
        "/api/content/curriculum-imports/",
        {"archive": SimpleUploadedFile(name, data or sample_zip())},
        format="multipart",
    )


def test_api_requires_admin(user):
    anonymous = APIClient()
    assert upload(anonymous).status_code in (401, 403)
    client = APIClient()
    client.force_authenticate(user)
    assert upload(client).status_code == 403
    assert client.get("/api/content/curriculum-imports/").status_code == 403
    assert CurriculumImport.objects.count() == 0


def test_api_upload_preview_publish(admin_client):
    response = upload(admin_client)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "previewed"
    assert body["report"]["plan"]["create"]
    assert "archive" not in body
    assert Lesson.objects.count() == 0

    detail = admin_client.get(f"/api/content/curriculum-imports/{body['id']}/")
    assert detail.json()["status"] == "previewed"

    published = admin_client.post(
        f"/api/content/curriculum-imports/{body['id']}/publish/"
    )
    assert published.status_code == 202
    assert published.json()["status"] == "published"
    assert Lesson.objects.count() == 3

    listing = admin_client.get("/api/content/curriculum-imports/")
    assert listing.status_code == 200


def test_api_invalid_archive_reports_problems_and_cannot_be_published(admin_client):
    body = upload(admin_client, sample_zip({BRANCHES: "[x](javascript:1)"})).json()
    assert body["status"] == "failed"
    assert body["report"]["problems"][0]["code"] == "unsafe_url"
    response = admin_client.post(
        f"/api/content/curriculum-imports/{body['id']}/publish/"
    )
    assert response.status_code == 409
    assert Lesson.objects.count() == 0


def test_api_rejects_missing_file(admin_client):
    response = admin_client.post(
        "/api/content/curriculum-imports/", {}, format="multipart"
    )
    assert response.status_code == 400


# --- management command -----------------------------------------------------


def run_command(*args):
    out = StringIO()
    call_command("import_curriculum", *args, stdout=out)
    return out.getvalue()


def test_command_start_preview_publish_and_rerun(tmp_path):
    archive = tmp_path / "c.zip"
    archive.write_bytes(sample_zip())

    out = run_command("start", str(archive))
    assert "previewed" in out and "3 to create" in out
    assert Lesson.objects.count() == 0
    import_id = CurriculumImport.objects.get().pk

    assert "previewed" in run_command("preview", str(import_id))
    out = run_command("publish", str(import_id))
    assert "3 created" in out
    assert Lesson.objects.count() == 3

    out = run_command("start", str(archive), "--publish")
    assert "3 unchanged" in out and "0 created" in out
    assert Lesson.objects.count() == 3


def test_command_json_output(tmp_path):
    archive = tmp_path / "c.zip"
    archive.write_bytes(sample_zip())
    payload = json.loads(run_command("--format", "json", "start", str(archive)))
    assert payload["status"] == "previewed"


def test_command_reports_problems_and_exits_nonzero(tmp_path):
    archive = tmp_path / "bad.zip"
    archive.write_bytes(sample_zip({BRANCHES: "[x](javascript:alert(1))"}))
    out = StringIO()
    with pytest.raises(CommandError, match="nothing was published"):
        call_command("import_curriculum", "start", str(archive), stdout=out)
    assert "unsafe URL scheme" in out.getvalue()
    assert Lesson.objects.count() == 0


def test_command_errors(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        run_command("start", str(tmp_path / "missing.zip"))
    with pytest.raises(CommandError, match="no import with id"):
        run_command("publish", "999")
    imp = new_import()
    with pytest.raises(CommandError, match="only a previewed import"):
        run_command("publish", str(imp.pk))


def test_enqueue_falls_back_to_django_q_when_celery_has_no_broker(monkeypatch):
    queued = []
    monkeypatch.setattr(tasks, "async_task", lambda name, pk: queued.append((name, pk)))

    def no_broker(pk):
        raise ConnectionError("broker down")

    monkeypatch.setattr(tasks.validate_curriculum_import, "delay", no_broker)
    tasks.enqueue(tasks.validate_curriculum_import, 7)
    assert queued == [("apps.content.tasks.validate_curriculum_import", 7)]
