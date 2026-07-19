Tenant Isolation
This document describes the cross-tenant data isolation pattern used acrossthe platform to prevent a user in Organization A from accessing data owned byOrganization B through API endpoints.

Overview
Every authenticated request is associated with a tenant — theorganization the requesting user belongs to. Tenant context is resolvedby TenantContextMiddleware and stored in a thread-local(apps.core.tenant) so that model managers and DRF viewsets can scopequeries automatically.

The isolation layer has four cooperating pieces:

Piece	Location	Role
TenantContext (thread-local)	apps/core/tenant.py	Holds the current request's organization_id
TenantContextMiddleware	apps/core/middleware/tenant.py	Resolves organization_id from JWT claim or user profile
TenantAwareModel + TenantManager	apps/core/models.py	Auto-scopes models that carry an organization FK
OrganizationScopedQuerySetMixin	apps/core/mixins.py	Drop-in DRF viewset mixin for tenant scoping
Resolution Order
TenantContextMiddleware resolves the tenant id in this order (first hit wins):

The organization_id claim on the verified JWT access token.
request.user.user_profile.organization_id (the user's default org).
The user's most recent OrganizationMembership.
If none resolve, the tenant id is None and tenant-scoped querysetsreturn empty results — the system fails closed.

Protecting a Viewset
Option A — Drop-in mixin (recommended for existing views)
from apps.core.mixins import OrganizationScopedQuerySetMixinfrom rest_framework import viewsetsclass LessonViewSet(OrganizationScopedQuerySetMixin, viewsets.ModelViewSet):    queryset = Lesson.objects.all()    serializer_class = LessonSerializer    permission_classes = [IsAuthenticated]
The mixin auto-detects the tenant discriminator on the model:

If the model has an organization field → filters on it directly.
Else if the model has a user field → filters on
user__user_profile__organization.
Otherwise → returns an empty queryset (fail closed).
perform_create() stamps the current tenant onto new records when the
model supports it. perform_update() blocks moving a record across
tenants via a PATCH.

Option B — Explicit object-level 403
For endpoints that should return 403 Forbidden (rather than the
secure 404 default) when a cross-tenant object is requested, add
IsTenantMember:
from apps.core.permissions import IsTenantMember

class LessonViewSet(OrganizationScopedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]

Protecting a New Model
For new tenant-scoped models, inherit TenantAwareModel:
from apps.core.models import TenantAwareModel

class Lesson(TenantAwareModel):
    title = models.CharField(max_length=200)
    # `organization` FK is provided by the base class.

Lesson.objects.all()  # -> only the current tenant's lessons
Lesson.objects.unscoped()  # -> all lessons (admin/migration tooling only)

Adding organization to an existing model requires a migration.

Migrating an Existing Model
Add organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, null=True, db_index=True) to the model.
Run python manage.py makemigrations <app> and python manage.py migrate.
Backfill: UPDATE <table> SET organization_id = (SELECT organization_id FROM accounts_userprofile WHERE user_id = <table>.user_id).
(Optional) switch the model to inherit TenantAwareModel and remove the explicit organization field definition.
Security Audit
Run the audit command to surface unprotected viewsets:

python manage.py audit_tenant_isolation
python manage.py audit_tenant_isolation --strict  # exit 1 on any gap

The command inspects every registered DRF viewset and reports which ones
lack tenant scoping. CI should run with --strict.

Testing
Integration tests live in apps/core/tests/test_tenant_isolation.py.
They verify that:

An Org A user cannot list Org B resources.
An Org A user cannot retrieve Org B detail URLs (404 by default, 403
when IsTenantMember is applied).
The thread-local tenant context is set and cleared correctly.
The audit command runs and produces a report.
Guidelines for Extending
Never bypass TenantManager / OrganizationScopedQuerySetMixin
in request-handling code. Use .unscoped() only in management
commands and migrations.
Always insert new tenant-scoped models as TenantAwareModel
subclasses; do not re-implement the FK manually.
Always run audit_tenant_isolation --strict in CI for PRs that
touch apps/*/views.py.
New DRF viewsets over tenant-scoped data MUST inherit
OrganizationScopedQuerySetMixin.
Threat Model
Threat
Mitigation
User guesses another org's resource id and GETs it	Mixin scopes queryset → 404; IsTenantMember → 403
User POSTs a resource with a foreign-org organization_id	perform_create() ignores client organization_id and stamps the request's tenant
User PATCHes a resource to reassign it to another org	perform_update() raises PermissionDenied if organization is in validated_data
Anonymous request scrapes tenant data	IsAuthenticated + fail-closed empty queryset
Background task / management command runs without a request	get_current_tenant_id() returns None → .unscoped() must be called explicitly
JWT is stolen and replayed in another org's context	Tenant is bound to the token's organization_id claim, set at login from the user's profile — cannot be forged client-side

Failure Modes
No tenant resolved on an authenticated request → tenant-scoped
querysets return empty. Endpoint returns 200 [] / 404. No data
leaks; the user sees an empty result set.
Tenant context not cleared → the thread-local is cleared in a
finally block in TenantContextMiddleware.__call__, so a context
cannot bleed to the next request on the same worker thread.
audit_tenant_isolation reports a gap → a viewset is missing the
mixin AND has no get_queryset() override referencing organization
or user_profile. Fix by adding the mixin or overriding
get_queryset().
Appendix: File Inventory
backend/apps/core/tenant.py                              # thread-local context
backend/apps/core/middleware/tenant.py                   # TenantContextMiddleware
backend/apps/core/models.py                              # TenantAwareModel + managers
backend/apps/core/mixins.py                              # OrganizationScopedQuerySetMixin
backend/apps/core/permissions.py                         # IsTenantMember
backend/apps/accounts/jwt.py                             # organization_id JWT claim
backend/config/settings.py                               # middleware registration
backend/apps/core/management/commands/audit_tenant_isolation.py
backend/apps/core/tests/test_tenant_isolation.py
docs/TENANT_ISOLATION.md                                 # this document
---
