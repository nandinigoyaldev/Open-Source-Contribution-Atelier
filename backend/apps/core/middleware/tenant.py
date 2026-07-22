"""
TenantContextMiddleware
=======================

Resolves the requesting user's organization (tenant) on every
authenticated request and stores it in the thread-local
:class:`apps.core.tenant` context so that queryset managers and the
:class:`apps.core.mixins.OrganizationScopedQuerySetMixin` can scope
queries automatically.

Resolution order (first match wins):
    1. ``organization_id`` claim on the verified JWT access token
       (populated by ``apps.accounts.jwt.DynamicSaltAccessToken``).
    2. ``request.user.user_profile.organization_id`` (the user's
       default organization profile).
    3. The user's most recent ``OrganizationMembership`` (fallback for
       users without a profile org set but who belong to >=1 org).

If no organization can be resolved, the tenant id is left as ``None``
and tenant-scoped querysets will return empty results — fail-closed.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.tenant import set_current_tenant, clear_current_tenant


class TenantContextMiddleware:
    """Populate the thread-local tenant context from the authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response
        # Reuse the project's configured JWT auth so we can read verified
        # claims without re-implementing verification.
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        organization_id = None
        user_id = None

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            user_id = user.pk

            # 1. Prefer the organization_id claim from the verified JWT.
            organization_id = self._org_id_from_jwt(request)

            # 2. Fall back to the user profile's default organization.
            if organization_id is None:
                organization_id = self._org_id_from_profile(user)

            # 3. Final fallback: the user's most recent membership.
            if organization_id is None:
                organization_id = self._org_id_from_membership(user)

        set_current_tenant(organization_id, user_id)
        try:
            response = self.get_response(request)
        finally:
            # Always clear — prevents bleed between requests on the same thread.
            clear_current_tenant()
        return response

    # -- helpers -----------------------------------------------------------

    def _org_id_from_jwt(self, request):
        """Read the ``organization_id`` claim from a verified JWT, if present."""
        try:
            header = self.jwt_auth.get_header(request)
            if header is None:
                return None
            raw_token = self.jwt_auth.get_raw_token(header)
            if raw_token is None:
                return None
            validated = self.jwt_auth.get_validated_token(raw_token)
            org_id = validated.get("organization_id")
            if org_id in (None, ""):
                return None
            return int(org_id)
        except Exception:
            # Any JWT validation failure will be raised properly by the DRF
            # auth classes later in the stack; here we simply fall through.
            return None

    def _org_id_from_profile(self, user):
        profile = getattr(user, "user_profile", None)
        if profile is None:
            return None
        return getattr(profile, "organization_id", None)

    def _org_id_from_membership(self, user):
        # Imported lazily to avoid an import cycle at module load time.
        from apps.organizations.models import OrganizationMembership

        membership = (
            OrganizationMembership.objects.filter(user=user)
            .order_by("-joined_at")
            .first()
        )
        return membership.organization_id if membership else None
