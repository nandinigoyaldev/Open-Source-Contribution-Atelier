import subprocess
from textwrap import dedent

from scripts.ci.check_migration_locks import inspect_migration, main


def findings(operations, *, atomic="True"):
    return inspect_migration(dedent(f"""
            from django.db import migrations as m, models
            from django.contrib.postgres.operations import AddIndexConcurrently as OnlineIndex

            class Migration(m.Migration):
                atomic = {atomic}
                operations = [
                    {operations}
                ]
            """))


def test_existing_table_requires_concurrent_index():
    (issue,) = findings(
        'm.AddIndex(model_name="account", index=models.Index(fields=["name"]))'
    )
    assert issue.severity == "error"
    assert "AddIndexConcurrently" in issue.message


def test_new_table_can_use_a_standard_index():
    assert not findings(
        'm.CreateModel(name="Account", fields=[]), '
        'm.AddIndex(model_name="account", index=models.Index(fields=["name"]))'
    )


def test_concurrent_index_requires_explicitly_non_atomic_migration():
    index = 'OnlineIndex(model_name="account", index=models.Index(fields=["name"]))'
    assert not findings(index, atomic="False")
    assert findings(index)[0].severity == "error"


def test_separate_database_and_state_only_checks_executed_operations():
    index = 'm.AddIndex(model_name="account", index=models.Index(fields=["name"]))'
    assert not findings(f"m.SeparateDatabaseAndState(state_operations=[{index}])")
    assert (
        findings(f"m.SeparateDatabaseAndState(database_operations=[{index}])")[
            0
        ].severity
        == "error"
    )


def test_non_nullable_add_and_table_rename_are_advisories():
    issues = findings(
        'm.AddField(model_name="account", name="age", field=models.IntegerField()), '
        'm.RenameModel(old_name="Account", new_name="Member")'
    )
    assert [issue.severity for issue in issues] == ["warning", "warning"]
    assert "no default" in issues[0].message
    assert "rename" in issues[1].message


def test_defaults_nullable_fields_and_indexed_foreign_keys():
    issues = findings(
        'm.AddField(model_name="account", name="age", field=models.IntegerField(default=0)), '
        'm.AddField(model_name="account", name="a", field=models.CharField(null=True)), '
        'm.AddField(model_name="account", name="org", '
        'field=models.ForeignKey("app.Org", null=True, db_index=False)), '
        'm.AddField(model_name="account", name="other", '
        'field=models.ForeignKey("app.Org", null=True))'
    )
    assert len(issues) == 1
    assert "default index" in issues[0].message


def test_cli_only_lints_added_migrations(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    git("init", "-q")
    git("config", "user.name", "CI test")
    git("config", "user.email", "ci@example.test")
    folder = tmp_path / "backend/apps/a/migrations"
    folder.mkdir(parents=True)
    content = (
        "from django.db import migrations, models\n"
        "class Migration(migrations.Migration):\n"
        "    operations = [migrations.AddIndex(model_name='account', index=models.Index(fields=['name']))]\n"
    )
    (folder / "0001_existing.py").write_text(content)
    git("add", ".")
    git("commit", "-qm", "initial")
    base = git("rev-parse", "HEAD")
    (folder / "0001_existing.py").write_text(content + "\n")
    (folder / "0002_new.py").write_text(content)
    (folder.parent / "not_a_migration.py").write_text(content)
    git("add", ".")
    git("commit", "-qm", "add files")
    assert main(["--base", base]) == 1
    output = capsys.readouterr().out
    assert "0002_new.py:3: error:" in output
    assert "0001_existing" not in output
    assert "not_a_migration" not in output


def test_positional_django_operations_are_checked():
    assert not findings(
        'm.CreateModel("Account", []), '
        'm.AddIndex("account", models.Index(fields=["name"]))'
    )
    errors = findings(
        'm.AddField("account", "age", models.IntegerField()), '
        'm.SeparateDatabaseAndState([m.AddIndex("account", models.Index(fields=["name"]))])'
    )
    assert [issue.severity for issue in errors] == ["warning", "error"]
