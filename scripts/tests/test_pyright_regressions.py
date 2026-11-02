import json

from scripts.ci.pyright_regressions import (
    error_counts,
    main,
    messages_for,
    regressions,
    relative_name,
)


def report(*diagnostics):
    return {"generalDiagnostics": list(diagnostics)}


def error(
    file, line=0, message="bad", rule="reportGeneralTypeIssues", severity="error"
):
    return {
        "file": file,
        "severity": severity,
        "message": message,
        "rule": rule,
        "range": {
            "start": {"line": line, "character": 0},
            "end": {"line": line, "character": 1},
        },
    }


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_relative_name_strips_root_and_normalises_separators():
    assert (
        relative_name("C:\\work\\repo\\backend\\apps\\a.py", "C:\\work\\repo")
        == "backend/apps/a.py"
    )
    assert (
        relative_name(
            "/home/runner/work/repo/backend/apps/a.py", "/home/runner/work/repo"
        )
        == "backend/apps/a.py"
    )


def test_relative_name_lines_up_reports_from_different_checkouts():
    base = relative_name("/tmp/base-checkout/backend/apps/a.py")
    head = relative_name("/home/runner/work/repo/backend/apps/a.py")
    assert base == head == "backend/apps/a.py"


def test_only_errors_are_counted():
    counts = error_counts(
        report(
            error("/r/backend/a.py"),
            error("/r/backend/a.py"),
            error("/r/backend/b.py", severity="warning"),
        )
    )
    assert counts == {"backend/a.py": 2}


def test_no_regression_when_counts_are_equal_or_lower():
    base = error_counts(
        report(
            error("/r/backend/a.py"), error("/r/backend/a.py"), error("/r/backend/b.py")
        )
    )
    head = error_counts(report(error("/r/backend/a.py"), error("/r/backend/b.py")))
    assert regressions(base, head) == []


def test_an_extra_error_in_an_existing_file_is_a_regression():
    base = error_counts(report(error("/r/backend/a.py")))
    head = error_counts(
        report(error("/r/backend/a.py"), error("/r/backend/a.py", line=9))
    )
    assert regressions(base, head) == [("backend/a.py", 1, 2)]


def test_errors_in_a_new_file_are_a_regression():
    base = error_counts(report())
    head = error_counts(report(error("/r/backend/new.py")))
    assert regressions(base, head) == [("backend/new.py", 0, 1)]


def test_moving_an_existing_error_to_another_line_is_not_a_regression():
    base = error_counts(report(error("/r/backend/a.py", line=3)))
    head = error_counts(report(error("/r/backend/a.py", line=120)))
    assert regressions(base, head) == []


def test_worst_file_is_listed_first():
    base = error_counts(report(error("/r/backend/a.py")))
    head = error_counts(
        report(*([error("/r/backend/a.py")] * 2), *([error("/r/backend/b.py")] * 5))
    )
    assert [name for name, _, _ in regressions(base, head)] == [
        "backend/b.py",
        "backend/a.py",
    ]


def test_messages_include_file_line_text_and_rule_and_are_limited():
    head = report(
        *[error("/r/backend/a.py", line=i, message="x  is\nbad") for i in range(10)]
    )
    lines = messages_for(head, ["backend/a.py"], limit=3)["backend/a.py"]
    assert len(lines) == 3
    assert lines[0] == "backend/a.py:1: x is bad (reportGeneralTypeIssues)"


def test_cli_passes_when_nothing_got_worse(tmp_path, capsys):
    base = write(tmp_path, "base.json", report(error("/b/backend/a.py")))
    head = write(tmp_path, "head.json", report(error("/h/backend/a.py")))
    assert main([base, head]) == 0
    assert "No file has more Pyright errors" in capsys.readouterr().out


def test_cli_fails_with_an_actionable_message_for_a_new_type_error(tmp_path, capsys):
    base = write(tmp_path, "base.json", report(error("/b/backend/a.py")))
    head = write(
        tmp_path,
        "head.json",
        report(
            error("/h/backend/a.py"),
            error(
                "/h/backend/a.py", line=41, message='"int" is not assignable to "str"'
            ),
        ),
    )
    assert main([base, head]) == 1
    out = capsys.readouterr().out
    assert "backend/a.py: 1 -> 2" in out
    assert "backend/a.py:42:" in out
    assert "npx pyright backend" in out


def test_cli_reports_an_unreadable_report_with_exit_code_2(tmp_path, capsys):
    good = write(tmp_path, "good.json", report())
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert main([good, str(bad)]) == 2
    assert "Could not read the Pyright report" in capsys.readouterr().err
    assert main([good, str(tmp_path / "missing.json")]) == 2
    other = write(tmp_path, "other.json", {"something": "else"})
    assert main([good, other]) == 2
