import os
import yaml
from django.conf import settings


def test_migration_workflow_syntax():
    workflow_path = os.path.normpath(
        os.path.join(
            settings.BASE_DIR, "..", ".github", "workflows", "migration-check.yml"
        )
    )
    assert os.path.exists(workflow_path), f"Workflow file not found at {workflow_path}"

    with open(workflow_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)

    assert content is not None, "Workflow file is empty or invalid YAML"
    assert content.get("name") == "Migration Safety Check", "Workflow name mismatch"

    on_triggers = content.get("on") or content.get(True) or {}
    if isinstance(on_triggers, dict):
        assert "pull_request" in on_triggers, "Missing pull_request trigger"
        assert "workflow_dispatch" in on_triggers, "Missing workflow_dispatch trigger"
    else:
        assert (
            on_triggers in ["pull_request", "workflow_dispatch"]
            or "pull_request" in on_triggers
            or "workflow_dispatch" in on_triggers
        )

    jobs = content.get("jobs", {})
    assert "migration-check" in jobs, "Missing migration-check job"

    steps = jobs["migration-check"].get("steps", [])
    assert len(steps) > 0, "No steps defined in migration-check job"

    filter_step = next((s for s in steps if s.get("id") == "filter"), None)
    assert filter_step is not None, "Missing filter step with id 'filter'"
    assert "GITHUB_OUTPUT" in filter_step.get(
        "run", ""
    ), "Should use GITHUB_OUTPUT instead of deprecated set-output"
    assert "set-output" not in filter_step.get(
        "run", ""
    ), "Should not use deprecated ::set-output syntax"

    check_step = next((s for s in steps if s.get("id") == "check"), None)
    assert check_step is not None, "Missing check step with id 'check'"
    assert "timeout-minutes" in check_step, "Missing timeout-minutes in check step"
