"""Guards the settings that let Django-Q workers drain on SIGTERM."""

import re
from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from config.settings import _parse_task_timeout

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = [
    REPO_ROOT / "docker-compose.yml",
    REPO_ROOT / "infra" / "deploy" / "docker-compose.prod.yml",
]


def _seconds(value: str) -> int:
    match = re.fullmatch(r"(\d+)([sm])", str(value).strip())
    assert match, f"unsupported duration {value!r}, use Ns or Nm"
    return int(match.group(1)) * (60 if match.group(2) == "m" else 1)


def test_seconds_helper_parses_supported_formats():
    assert _seconds("120s") == 120
    assert _seconds("2m") == 120
    with pytest.raises(AssertionError, match="unsupported duration"):
        _seconds("1h")


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=lambda p: p.name)
def test_worker_grace_period_exceeds_task_timeout(path):
    # Custom tags such as !reset are not plain YAML, so ignore them.
    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    compose = yaml.load(path.read_text("utf-8"), Loader=Loader)
    worker = compose["services"]["worker"]
    assert _seconds(worker["stop_grace_period"]) > settings.Q_TASK_TIMEOUT


def test_base_worker_runs_qcluster_without_shell():
    compose = yaml.safe_load(COMPOSE_FILES[0].read_text("utf-8"))
    command = compose["services"]["worker"]["command"]
    assert command.startswith("python manage.py qcluster")
    assert "sh -c" not in command


def test_task_timeout_accepts_positive_integer():
    assert _parse_task_timeout("45") == 45


@pytest.mark.parametrize("raw", ["abc", "", "1.5", "0", "-5"])
def test_task_timeout_rejects_invalid_values(raw):
    with pytest.raises(ImproperlyConfigured, match="Q_TASK_TIMEOUT"):
        _parse_task_timeout(raw)
