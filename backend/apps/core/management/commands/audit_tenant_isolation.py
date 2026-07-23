"""
Management command: audit_tenant_isolation
==========================================

Probes every registered DRF viewset for cross-tenant data isolation
coverage and reports gaps. A viewset is considered "protected" if it
inherits :class:`apps.core.mixins.OrganizationScopedQuerySetMixin`
OR overrides ``get_queryset()`` with explicit organization filtering
(heuristic: the source string references ``organization`` or
``user_profile``).

Usage::

    python manage.py audit_tenant_isolation
    python manage.py audit_tenant_isolation --strict   # exit code 1 on any gap
"""

import inspect

from django.core.management.base import BaseCommand
from django.urls import get_resolver
from rest_framework.viewsets import ViewSetMixin

from apps.core.mixins import OrganizationScopedQuerySetMixin


class Command(BaseCommand):
    help = (
        "Audit all registered DRF viewsets for cross-tenant data "
        "isolation coverage and report any unprotected endpoints."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit with code 1 if any unprotected viewset is found.",
        )

    def handle(self, *args, **options):
        viewsets = self._collect_viewsets()
        protected, unprotected = [], []

        for viewset in viewsets:
            if self._is_protected(viewset):
                protected.append(viewset)
            else:
                unprotected.append(viewset)

        total = len(viewsets)
        self.stdout.write(
            self.style.NOTICE(
                f"🔍 Audited {total} DRF viewset(s): "
                f"{len(protected)} protected, {len(unprotected)} unprotected."
            )
        )

        if protected:
            self.stdout.write(self.style.SUCCESS("\n✅ Protected viewsets:"))
            for vs in sorted(protected, key=lambda c: c.__name__):
                self.stdout.write(f"   • {vs.__module__}.{vs.__name__}")

        if unprotected:
            self.stdout.write(
                self.style.WARNING("\n⚠️  Unprotected viewsets (isolation gaps):")
            )
            for vs in sorted(unprotected, key=lambda c: c.__name__):
                self.stdout.write(f"   • {vs.__module__}.{vs.__name__}")

            self.stdout.write(
                self.style.WARNING(
                    "\nFix: add `OrganizationScopedQuerySetMixin` to each "
                    "unprotected viewset, or override get_queryset() with "
                    "organization scoping. See docs/TENANT_ISOLATION.md."
                )
            )

        # Critical endpoints the issue names explicitly — verify they are covered.
        critical = {
            "OrganizationViewSet",
            "OrganizationMembershipViewSet",
            "IssueReportViewSet",
            "BountyViewSet",
            "NoteViewSet",
        }
        missing_critical = critical - {c.__name__ for c in protected}
        if missing_critical:
            self.stdout.write(
                self.style.ERROR(
                    "\n🚨 CRITICAL unprotected endpoints: "
                    + ", ".join(sorted(missing_critical))
                )
            )

        if options["strict"] and unprotected:
            raise SystemExit(1)

    # -- collection --------------------------------------------------------

    def _collect_viewsets(self):
        """Walk the URL resolver and collect all distinct viewset classes."""
        resolver = get_resolver()
        seen = set()
        viewsets = []

        def walk(pattern):
            callback = pattern.callback
            cls = getattr(callback, "cls", None) or getattr(
                callback, "view_class", None
            )
            if cls and isinstance(cls, type) and issubclass(cls, ViewSetMixin):
                if cls not in seen:
                    seen.add(cls)
                    viewsets.append(cls)
            for child in getattr(pattern, "url_patterns", []):
                walk(child)

        for p in resolver.url_patterns:
            walk(p)
        return viewsets

    def _is_protected(self, viewset):
        """A viewset is protected if it uses the mixin OR overrides get_queryset."""
        if issubclass(viewset, OrganizationScopedQuerySetMixin):
            return True
        # Heuristic: did the subclass override get_queryset with org-aware logic?
        get_queryset = getattr(viewset, "get_queryset", None)
        if get_queryset is None:
            return False
        if "get_queryset" in viewset.__dict__:
            try:
                src = inspect.getsource(viewset.__dict__["get_queryset"])
                if (
                    "organization" in src
                    or "user_profile" in src
                    or "memberships" in src
                ):
                    return True
            except (OSError, TypeError):
                pass
        return False
