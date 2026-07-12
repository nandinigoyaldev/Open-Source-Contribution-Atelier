from django.core.checks import Error, register, Tags
from django.db import connections

@register(Tags.database)
def check_sqlite_wal_mode(app_configs, **kwargs):
    errors = []
    
    for alias in connections:
        conn = connections[alias]
        if conn.vendor == 'sqlite':
            try:
                with conn.cursor() as cursor:
                    cursor.execute("PRAGMA journal_mode;")
                    journal_mode = cursor.fetchone()[0].lower()
                    
                    if journal_mode != "wal":
                        errors.append(
                            Error(
                                f"SQLite database '{alias}' is not using WAL mode (current: {journal_mode}).",
                                hint="Ensure your database settings include 'PRAGMA journal_mode=WAL;' in init_command.",
                                obj=f"Database: {alias}",
                                id="perf.E001",
                            )
                        )
            except Exception as e:
                pass
                
    return errors
