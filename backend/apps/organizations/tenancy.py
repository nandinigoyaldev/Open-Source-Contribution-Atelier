"""
Multi-tenant PostgreSQL schema isolation for enterprise organization workspaces.

Architecture:
- Organizations with is_enterprise=True get an isolated PostgreSQL schema:
  `tenant_<org_slug>`.
- Schema routing is dynamically activated via:
  `SET search_path TO tenant_<org_slug>, public`
- Default community users and non-enterprise organizations remain on `public`
  schema without overhead or search_path manipulation.
- Cross-database compatibility: on non-PostgreSQL engines (e.g. SQLite for local
  development and unit testing), search_path routing degrades gracefully without error.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Union

from django.conf import settings
from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

# Reserved subdomains that never map to tenant slugs
RESERVED_SUBDOMAINS = frozenset(
    {
        "www",
        "api",
        "app",
        "admin",
        "static",
        "media",
        "mail",
        "smtp",
        "staging",
        "prod",
        "production",
        "dev",
        "development",
        "localhost",
        "testserver",
        "127",
    }
)

TENANT_SCHEMA_HEADER = "HTTP_X_ORGANIZATION_TENANT"
TENANT_SLUG_HEADER = "HTTP_X_TENANT_SLUG"
TENANT_ID_HEADER = "HTTP_X_TENANT_ID"


def get_tenant_schema_name(slug_or_name: str) -> str:
    """
    Generate a safe PostgreSQL schema identifier for a tenant slug or name.
    PostgreSQL identifiers must be <= 63 bytes, lowercase alphanumeric + underscore.
    """
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", str(slug_or_name)).lower().strip("_")
    if not clean:
        clean = "org"
    return f"tenant_{clean}"[:63]


def is_valid_schema_name(schema_name: str) -> bool:
    """Validate that schema_name matches safe SQL identifier rules."""
    return bool(re.match(r"^[a-z][a-z0-9_]{1,62}$", schema_name))


def activate_tenant_schema(
    schema_name: Optional[str] = None, force_execute: bool = False
) -> str:
    """
    Set search_path on the current database connection.
    If schema_name is provided and not 'public', sets:
      SET search_path TO <schema_name>, public
    If schema_name is None or 'public', resets:
      SET search_path TO public

    Returns the SQL query executed (or formatted).
    """
    from apps.core.tenant import set_current_schema

    effective_schema = (
        schema_name if (schema_name and schema_name != "public") else "public"
    )
    set_current_schema(effective_schema)

    if effective_schema != "public":
        if not is_valid_schema_name(effective_schema):
            raise ValueError(f"Invalid schema name for tenancy: {effective_schema}")
        sql = f'SET search_path TO "{effective_schema}", public'
    else:
        sql = "SET search_path TO public"

    if connection.vendor == "postgresql" or force_execute:
        with connection.cursor() as cursor:
            cursor.execute(sql)

    logger.debug("Activated schema routing: %s (vendor=%s)", sql, connection.vendor)
    return sql


def deactivate_tenant_schema(force_execute: bool = False) -> str:
    """Restore search_path to default public schema."""
    return activate_tenant_schema("public", force_execute=force_execute)


def create_tenant_schema(schema_name: str, force_execute: bool = False) -> bool:
    """
    Create a new PostgreSQL schema if it does not already exist.
    """
    if not is_valid_schema_name(schema_name):
        raise ValueError(f"Invalid schema name: {schema_name}")

    if connection.vendor == "postgresql" or force_execute:
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        logger.info("Created PostgreSQL tenant schema: %s", schema_name)
        return True

    logger.debug(
        "create_tenant_schema skipped on non-PostgreSQL engine: %s", connection.vendor
    )
    return False


def drop_tenant_schema(
    schema_name: str, cascade: bool = True, force_execute: bool = False
) -> bool:
    """
    Drop a PostgreSQL schema (used for teardown/cleanup).
    """
    if not is_valid_schema_name(schema_name):
        raise ValueError(f"Invalid schema name: {schema_name}")

    if connection.vendor == "postgresql" or force_execute:
        cascade_sql = " CASCADE" if cascade else ""
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}"{cascade_sql}')
        logger.info("Dropped PostgreSQL tenant schema: %s", schema_name)
        return True

    return False


def migrate_tenant_schema(schema_name: str, force_execute: bool = False) -> bool:
    """
    Run migrations against a specific tenant schema.
    Sets search_path to the tenant schema and executes migrations,
    then restores search_path.
    """
    if not is_valid_schema_name(schema_name):
        raise ValueError(f"Invalid schema name: {schema_name}")

    if connection.vendor == "postgresql" or force_execute:
        previous_schema = get_current_schema_from_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema_name}", public')
            call_command("migrate", interactive=False, verbosity=0)
            logger.info("Migrated tenant schema: %s", schema_name)
            return True
        except Exception as exc:
            logger.warning(
                "Migration runner caught exception on schema %s: %s", schema_name, exc
            )
            return False
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SET search_path TO "{previous_schema or "public"}", public'
                )
    return False


def get_current_schema_from_db() -> Optional[str]:
    """Inspect the current primary schema from database search_path."""
    if connection.vendor != "postgresql":
        from apps.core.tenant import get_current_schema

        return get_current_schema()
    with connection.cursor() as cursor:
        cursor.execute("SHOW search_path")
        row = cursor.fetchone()
        if row and row[0]:
            parts = [p.strip().strip('"') for p in row[0].split(",")]
            return parts[0] if parts else "public"
    return "public"
