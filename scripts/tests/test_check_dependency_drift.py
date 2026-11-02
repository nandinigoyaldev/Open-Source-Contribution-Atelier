import json

from scripts.ci.check_dependency_drift import (
    check_npm_project,
    check_python,
    main,
    parse_requirements,
    pin_of,
    satisfies,
)


def write_npm(folder, manifest, lock_root, name="app"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "package.json").write_text(
        json.dumps({"name": name, **manifest}), encoding="utf-8"
    )
    (folder / "package-lock.json").write_text(
        json.dumps(
            {
                "name": name,
                "lockfileVersion": 3,
                "packages": {"": {"name": name, **lock_root}},
            }
        ),
        encoding="utf-8",
    )


def test_matching_manifest_and_lockfile_pass(tmp_path):
    deps = {
        "dependencies": {"react": "^19.0.0"},
        "devDependencies": {"vitest": "^3.0.5"},
    }
    write_npm(tmp_path, deps, deps)
    assert check_npm_project(tmp_path, "frontend") == []


def test_dependency_missing_from_the_lockfile_is_drift(tmp_path):
    write_npm(
        tmp_path,
        {"dependencies": {"react": "^19.0.0", "zod": "^4.0.0"}},
        {"dependencies": {"react": "^19.0.0"}},
    )
    problems = check_npm_project(tmp_path, "frontend")
    assert any(
        "`zod` (dependencies) is in package.json but not in package-lock.json" in p
        for p in problems
    )
    assert problems[-1].startswith("Fix: run `npm install` in frontend/")


def test_dependency_only_in_the_lockfile_is_drift(tmp_path):
    write_npm(tmp_path, {"dependencies": {}}, {"dependencies": {"left-pad": "^1.0.0"}})
    assert any(
        "`left-pad`" in p and "not in package.json" in p
        for p in check_npm_project(tmp_path, "frontend")
    )


def test_changed_version_range_is_drift_and_shows_both_ranges(tmp_path):
    write_npm(
        tmp_path,
        {"devDependencies": {"vite": "^7.0.0"}},
        {"devDependencies": {"vite": "^6.0.0"}},
    )
    problem = check_npm_project(tmp_path, "frontend")[0]
    assert (
        "`vite` (devDependencies)" in problem
        and "`^7.0.0`" in problem
        and "`^6.0.0`" in problem
    )


def test_moving_a_package_between_sections_is_drift(tmp_path):
    write_npm(
        tmp_path,
        {"devDependencies": {"tsx": "^4.0.0"}},
        {"dependencies": {"tsx": "^4.0.0"}},
    )
    assert (
        len([p for p in check_npm_project(tmp_path, "root") if p.startswith("root:")])
        == 2
    )


def test_optional_and_peer_sections_are_checked(tmp_path):
    write_npm(
        tmp_path,
        {
            "optionalDependencies": {"fsevents": "^2.3.0"},
            "peerDependencies": {"react": ">=18"},
        },
        {
            "optionalDependencies": {"fsevents": "^2.3.0"},
            "peerDependencies": {"react": ">=17"},
        },
    )
    problems = check_npm_project(tmp_path, "frontend")
    assert len([p for p in problems if "peerDependencies" in p]) == 1
    assert not any("fsevents" in p for p in problems)


def test_missing_lockfile_is_reported(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert "has no package-lock.json" in check_npm_project(tmp_path, "frontend")[0]


def test_folder_without_package_json_is_skipped(tmp_path):
    assert check_npm_project(tmp_path, "frontend") == []


def test_parse_requirements_ignores_comments_options_and_extras():
    text = "# comment\n\n-r other.txt\nDjango>=5.0,<5.1  # web\npsycopg[binary]>=3.2.0\nSome_Pkg==1.0\n"
    assert parse_requirements_text(text) == {
        "django": ">=5.0,<5.1",
        "psycopg": ">=3.2.0",
        "some-pkg": "==1.0",
    }


def parse_requirements_text(text, tmp=None):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "requirements.txt"
        path.write_text(text, encoding="utf-8")
        return parse_requirements(path)


def test_pin_of_only_recognises_exact_pins():
    assert pin_of("==5.5.1") == "5.5.1"
    assert pin_of(">=5.5.1") is None
    assert pin_of("") is None


def test_satisfies_checks_ranges():
    assert satisfies("5.5.1", ">=5.5.0")
    assert not satisfies("5.4.0", ">=5.5.0")
    assert satisfies("2.35.0", ">=2.35.0, <3")
    assert satisfies("1.0", "")
    assert satisfies("1.0", "not a specifier")  # cannot prove drift


def write_requirements(tmp_path, dev, prod):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "requirements.txt").write_text(dev, encoding="utf-8")
    (tmp_path / "backend" / "requirements-prod.txt").write_text(prod, encoding="utf-8")


def test_python_requirements_in_sync_pass(tmp_path):
    write_requirements(
        tmp_path, "Django>=5.0\nsimplejwt>=5.5.0\n", "Django>=4.2\nsimplejwt==5.5.1\n"
    )
    assert check_python(tmp_path) == []


def test_package_only_in_production_requirements_is_drift(tmp_path):
    write_requirements(tmp_path, "Django>=5.0\n", "Django>=5.0\ngunicorn>=21\n")
    problems = check_python(tmp_path)
    assert (
        "`gunicorn` is in requirements-prod.txt but not in requirements.txt"
        in problems[0]
    )
    assert problems[-1].startswith("Fix:")


def test_production_pin_outside_the_dev_range_is_drift(tmp_path):
    write_requirements(tmp_path, "pkg>=2.0\n", "pkg==1.9\n")
    assert "pinned to 1.9" in check_python(tmp_path)[0]


def test_name_normalisation_matches_underscores_and_case(tmp_path):
    write_requirements(tmp_path, "Django_Filter>=24\n", "django-filter>=23\n")
    assert check_python(tmp_path) == []


def test_main_exit_codes_and_message(tmp_path, capsys):
    deps = {"dependencies": {"react": "^19.0.0"}}
    write_npm(tmp_path / "frontend", deps, deps)
    write_npm(tmp_path, {}, {})
    write_requirements(tmp_path, "a>=1\n", "a>=1\n")
    assert main(["--root", str(tmp_path)]) == 0
    assert "consistent" in capsys.readouterr().out

    write_npm(
        tmp_path / "frontend", {"dependencies": {"react": "^19.0.0", "zod": "^4"}}, deps
    )
    assert main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "Dependency drift found" in out and "zod" in out and "npm install" in out
