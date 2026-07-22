from django.http import JsonResponse
from django.db import connection
from django.core.management import call_command
from io import StringIO


def migration_health(request):
    """Check migration status."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT app, name, applied FROM django_migrations ORDER BY id DESC LIMIT 10"
            )
            migrations = cursor.fetchall()

        # Check pending migrations
        out = StringIO()
        call_command("showmigrations", stdout=out)
        output = out.getvalue()

        pending = [line for line in output.split("\n") if " [ ] " in line]

        return JsonResponse(
            {
                "status": "ok",
                "recent_migrations": [
                    {"app": m[0], "name": m[1], "applied_at": m[2]} for m in migrations
                ],
                "pending_count": len(pending),
                "pending_migrations": pending[:10],
            }
        )
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
