from pathlib import Path

import pytest

from scripts import app_dependency_graph as graph


def make_app(root: Path, name: str, body: str = "") -> None:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "__init__.py").write_text("", encoding="utf-8")
    (folder / "views.py").write_text(body, encoding="utf-8")


@pytest.fixture
def apps_dir(tmp_path):
    root = tmp_path / "apps"
    root.mkdir()
    make_app(
        root, "alpha", "from apps.beta.models import B\nimport apps.gamma.services\n"
    )
    make_app(root, "beta", "from django.db import models\n")
    make_app(root, "gamma", "import stripe\nfrom celery import shared_task\n")
    make_app(root, "delta", "x = models.ForeignKey('alpha.Thing', on_delete=1)\n")
    (root / "migrations").mkdir()  # tooling folder, not an app
    return root


def test_every_real_app_is_in_a_domain():
    real = set(graph.app_names())
    listed = [app for members in graph.DOMAINS.values() for app in members]
    assert (
        real - set(listed) == set()
    ), "add new apps to DOMAINS in scripts/app_dependency_graph.py"
    assert set(listed) - real == set(), "DOMAINS lists an app that no longer exists"
    assert len(listed) == len(set(listed)), "an app is listed in two domains"


def test_app_names_skips_non_app_folders(apps_dir):
    assert graph.app_names(apps_dir) == ["alpha", "beta", "delta", "gamma"]


def test_imports_and_relation_strings_become_edges(apps_dir):
    edges, _ = graph.scan(apps_dir)
    assert edges["alpha"] == {"beta", "gamma"}
    assert edges["delta"] == {"alpha"}
    assert edges["beta"] == set()


def test_external_services_come_from_imports(apps_dir):
    _, services = graph.scan(apps_dir)
    assert services["gamma"] == {"Stripe", "Celery"}
    assert services["beta"] == set()


def test_tests_and_migrations_are_ignored(apps_dir):
    (apps_dir / "beta" / "tests").mkdir()
    (apps_dir / "beta" / "tests" / "test_x.py").write_text(
        "from apps.alpha import models\n", encoding="utf-8"
    )
    (apps_dir / "beta" / "migrations").mkdir()
    (apps_dir / "beta" / "migrations" / "0001.py").write_text(
        "from apps.alpha import models\n", encoding="utf-8"
    )
    (apps_dir / "beta" / "test_helpers.py").write_text(
        "from apps.alpha import models\n", encoding="utf-8"
    )
    edges, _ = graph.scan(apps_dir)
    assert edges["beta"] == set()


def test_tiers_follow_the_number_of_importing_apps():
    assert graph.tier(0) == "Optional"
    assert graph.tier(2) == "Supporting"
    assert graph.tier(3) == "Core"


def test_render_contains_every_edge_and_every_app(apps_dir, tmp_path):
    settings = tmp_path / "settings.py"
    settings.write_text(
        'INSTALLED_APPS = ["apps.alpha", "apps.beta"]\n', encoding="utf-8"
    )
    text = graph.render(apps_dir, settings)
    assert (
        "alpha --> beta" in text
        and "alpha --> gamma" in text
        and "delta --> alpha" in text
    )
    assert "| `gamma` |" in text
    row = next(line for line in text.splitlines() if line.startswith("| `gamma`"))
    assert "Stripe, Celery" in row or "Celery, Stripe" in row
    assert "| no |" in row  # gamma is not installed
    assert "Optional" in next(
        line for line in text.splitlines() if line.startswith("| `delta`")
    )


def test_replace_section_keeps_the_rest_of_the_document():
    doc = f"before\n{graph.START}\nold\n{graph.END}\nafter\n"
    new = graph.replace_section(doc, f"{graph.START}\nnew\n{graph.END}")
    assert new == f"before\n{graph.START}\nnew\n{graph.END}\nafter\n"


def test_replace_section_needs_both_markers():
    with pytest.raises(ValueError):
        graph.replace_section("no markers here", "x")


def test_architecture_doc_is_up_to_date():
    current = graph.DOC.read_text(encoding="utf-8")
    assert (
        graph.replace_section(current, graph.section()) == current
    ), "docs/ARCHITECTURE.md is out of date. Run: python scripts/app_dependency_graph.py --write"
