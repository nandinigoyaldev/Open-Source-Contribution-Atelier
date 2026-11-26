"""Flag locking operations in newly added Django migrations without importing them."""

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    line: int
    severity: str
    message: str


def qualified_name(node, imports):
    if isinstance(node, ast.Name):
        return imports.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{qualified_name(node.value, imports)}.{node.attr}"
    return ""


def arguments(call):
    return {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}


def argument(call, name, position):
    keyword = arguments(call).get(name)
    if keyword is not None:
        return keyword
    return call.args[position] if len(call.args) > position else None


def literal(node, fallback=None):
    return node.value if isinstance(node, ast.Constant) else fallback


def class_attribute(cls, name):
    for statement in reversed(cls.body):
        if isinstance(statement, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in statement.targets
            ):
                return statement.value
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == name
        ):
            return statement.value
    return None


def check_operations(operations, imports, non_atomic, created_models):
    if not isinstance(operations, (ast.List, ast.Tuple)):
        return []
    findings = []
    for operation in operations.elts:
        if not isinstance(operation, ast.Call):
            continue
        name = qualified_name(operation.func, imports)
        model = literal(argument(operation, "model_name", 0))
        created_here = isinstance(model, str) and model.lower() in created_models

        def report(severity, message):
            findings.append(Finding(operation.lineno, severity, message))

        if name == "django.db.migrations.CreateModel":
            model_name = literal(argument(operation, "name", 0))
            if isinstance(model_name, str):
                created_models.add(model_name.lower())
        elif name == "django.db.migrations.AddIndex" and not created_here:
            report(
                "error",
                "AddIndex on an existing table can block writes. Use "
                "AddIndexConcurrently in a migration with atomic = False.",
            )
        elif name == "django.contrib.postgres.operations.AddIndexConcurrently":
            if not non_atomic:
                report("error", "AddIndexConcurrently requires atomic = False.")
        elif name == "django.db.migrations.AddField" and not created_here:
            field = argument(operation, "field", 2)
            if not isinstance(field, ast.Call):
                continue
            field_args = arguments(field)
            if (
                literal(field_args.get("null"), False) is False
                and "default" not in field_args
                and "db_default" not in field_args
            ):
                report(
                    "warning",
                    "Non-nullable column has no default. Review a staged backfill "
                    "and constraint rollout before applying it to existing rows.",
                )
            if (
                qualified_name(field.func, imports) == "django.db.models.ForeignKey"
                and literal(field_args.get("db_index")) is False
            ):
                report(
                    "warning",
                    "Foreign key disables Django's default index. Confirm that a "
                    "separate index covers the referencing column.",
                )
        elif name in {
            "django.db.migrations.RenameModel",
            "django.db.migrations.AlterModelTable",
        }:
            report(
                "warning", "Table rename can acquire an exclusive lock. Review rollout."
            )
        elif name == "django.db.migrations.SeparateDatabaseAndState":
            findings.extend(
                check_operations(
                    argument(operation, "database_operations", 0),
                    imports,
                    non_atomic,
                    created_models,
                )
            )
    return findings


def inspect_migration(source):
    tree = ast.parse(source)
    imports = {}
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and statement.module:
            imports.update(
                (alias.asname or alias.name, f"{statement.module}.{alias.name}")
                for alias in statement.names
            )
        elif isinstance(statement, ast.Import):
            imports.update(
                (alias.asname, alias.name) for alias in statement.names if alias.asname
            )

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Migration":
            return check_operations(
                class_attribute(node, "operations"),
                imports,
                literal(class_attribute(node, "atomic")) is False,
                set(),
            )
    return []


def new_migrations(base, head):
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "-z",
            "--diff-filter=A",
            f"{base}...{head}",
            "--",
            "backend",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    for filename in result.stdout.split("\0"):
        file = Path(filename)
        if (
            file.parent.name == "migrations"
            and file.suffix == ".py"
            and file.stem != "__init__"
        ):
            yield file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Pull request base revision")
    parser.add_argument("--head", default="HEAD", help="Revision to inspect")
    args = parser.parse_args(argv)
    failed = False
    for file in new_migrations(args.base, args.head):
        try:
            source = subprocess.check_output(
                ["git", "show", f"{args.head}:{file.as_posix()}"], text=True
            )
            findings = inspect_migration(source)
        except SyntaxError as error:
            findings = [
                Finding(error.lineno or 1, "error", f"Invalid Python: {error.msg}")
            ]
        for finding in findings:
            print(f"{file}:{finding.line}: {finding.severity}: {finding.message}")
            failed |= finding.severity == "error"
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
