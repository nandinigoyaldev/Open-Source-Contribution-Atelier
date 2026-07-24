"""
DRF mixins for cross-tenant data isolation.

:class:`OrganizationScopedQuerySetMixin` is the drop-in solution for
protecting existing viewsets without altering their models. It scopes
``get_queryset()`` to the current tenant using one of two strategies,
auto-detected from the model:

    1. If the model has an ``organization`` field, filter on it
       directly (the model is :class:`apps.core.models.TenantAwareModel`
       or has been migrated to carry the FK).
    2. Otherwise, if the model has a ``user`` field, filter on
       ``user__user_profile__organization`` — this covers user-owned
       models (``IssueReport``, ``Note``, …) that have not yet been
       migrated to carry an explicit ``organization`` FK.

``perform_create()`` stamps the resolved organization onto new records
when the model supports it (strategy 1 only).

The mixin also exposes ``get_tenant_id()`` for subclasses and an
``unscoped`` escape hatch for admin viewsets (use sparingly).
"""

from django.core.exceptions import FieldDoesNotExist
from rest_framework.exceptions import NotAuthenticated

from apps.core.tenant import get_current_tenant_id


class OrganizationScopedQuerySetMixin:
    """
    Mixin that scopes a DRF viewset's queryset to the current tenant.

    Add it BEFORE ``viewsets.ModelViewSet`` in the MRO::

        class LessonViewSet(OrganizationScopedQuerySetMixin,
                            viewsets.ModelViewSet):
            queryset = Lesson.objects.all()
            serializer_class = LessonSerializer
            permission_classes = [IsAuthenticated]
    """

    #: Set to ``True`` to bypass tenant scoping (superuser-only views).
    tenant_unscoped = False

    # -- tenant resolution ------------------------------------------------

    def get_tenant_id(self):
        """Return the org id for the current request, or ``None``."""
        return get_current_tenant_id()

    # -- queryset scoping -------------------------------------------------

    def _model_has_field(self, model, name):
        try:
            model._meta.get_field(name)
            return True
        except FieldDoesNotExist:
            return False

    def get_queryset(self):
        if not hasattr(self, "queryset") or self.queryset is None:
            # Subclass didn't set ``queryset``; defer to the default.
            return super().get_queryset()

        qs = self.queryset
        if self.tenant_unscoped:
            return qs

        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            # Anonymous access: return empty rather than leak data.
            return qs.none()

        org_id = self.get_tenant_id()
        if org_id is None:
            # Authenticated but no tenant resolved: fail closed.
            return qs.none()

        model = qs.model

        if self._model_has_field(model, "organization"):
            # Strategy 1: explicit tenant FK on the model.
            return qs.filter(organization_id=org_id)

        if self._model_has_field(model, "user"):
            # Strategy 2: derive tenant from the owning user's profile.
            return qs.filter(user__user_profile__organization_id=org_id)

        # No tenant discriminator available — fail closed.
        return qs.none()

    # -- write-side stamping ----------------------------------------------

    def perform_create(self, serializer):
        org_id = self.get_tenant_id()
        model = serializer.Meta.model if hasattr(serializer, "Meta") else None
        if (
            org_id is not None
            and model is not None
            and self._model_has_field(model, "organization")
        ):
            serializer.save(organization_id=org_id)
        else:
            serializer.save()

    def perform_update(self, serializer):
        # Prevent moving a record across tenants via a PATCH.
        validated = serializer.validated_data
        if "organization" in validated or "organization_id" in validated:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Reassigning a record to a different organization is not "
                "permitted through the API."
            )
        serializer.save()
