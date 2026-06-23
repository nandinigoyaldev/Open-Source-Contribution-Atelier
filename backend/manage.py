#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    # Channels 4 removed the runserver WS override.
    # Intercept `runserver` and hand off to daphne so WebSocket works.
    if len(sys.argv) >= 2 and sys.argv[1] == "runserver":
        _run_daphne()
        return

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


def _run_daphne() -> None:
    import django

    django.setup()

    host = "127.0.0.1"
    port = "8000"

    for arg in sys.argv[2:]:
        if arg.startswith("--"):
            continue
        if ":" in arg:
            host, port = arg.split(":", 1)
        elif arg.isdigit():
            port = arg
        else:
            host = arg
        break

    no_reload = "--noreload" in sys.argv

    from channels.routing import get_default_application

    application = get_default_application()

    print(f"Daphne: serving on http://{host}:{port} (WebSocket enabled)")

    from daphne import server as daphne_server
    from daphne.endpoints import build_endpoint_description_strings

    endpoints = build_endpoint_description_strings(host=host, port=int(port))
    server = daphne_server.Server(
        application=application,
        endpoints=endpoints,
        signal_handlers=not no_reload,
        action_logger=_daphne_log,
    )
    server.run()


def _daphne_log(log_level, msg, args):
    from django.core.management.color import color_style

    style = color_style()
    fmt = msg % args if args else msg
    if log_level in ("error", "critical", "exception"):
        print(style.ERROR(f"[{log_level.upper()}] {fmt}"))
    else:
        print(fmt)


if __name__ == "__main__":
    main()
