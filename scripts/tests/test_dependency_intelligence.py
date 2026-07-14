from scripts.dependency_intelligence import Update, classify, markdown_report, overall_classification


def test_semver_classification():
    assert classify("1.2.3", "1.2.4") == "patch"
    assert classify("1.2.3", "1.3.0") == "minor"
    assert classify("1.2.3", "2.0.0") == "major"


def test_range_versions_are_classified():
    assert classify("^18.2.0", "^19.0.0") == "major"
    assert classify(">=5.0", ">=5.0.14") == "patch"


def test_overall_classification_uses_highest_risk():
    updates = [
        Update("npm", "a", "1.0.0", "1.0.1", "patch", [], [], []),
        Update("npm", "b", "1.0.0", "2.0.0", "major", [], [], []),
    ]
    assert overall_classification(updates) == "major"


def test_report_flags_breaking_updates():
    update = Update(
        ecosystem="npm",
        package="react",
        old="18.2.0",
        new="19.0.0",
        classification="major",
        release_notes=["Upstream repository: react"],
        peer_dependency_changes=["react-dom: ^18 → ^19"],
        breaking_changes=["Major version change"],
    )
    report = markdown_report([update])
    assert "BREAKING" in report
    assert "react-dom" in report
    assert "Closes #1643" in report
