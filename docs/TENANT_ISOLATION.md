# Cross-Tenant Data Isolation

This document describes the row-level security (RLS) architecture used to enforce **organization-scoped data isolation** across the CampusConnect platform.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   HTTP Request  │────▶│ TenantContext    │────▶│  Scoped Query   │
│  (JWT + org ID) │     │ Middleware       │     │  Set (Tenant)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

Every authenticated request carries an `organization_id` claim in the JWT. The `TenantContextMiddleware` extracts this value and stores it in a thread-local context. All `TenantAwareModel` queries automatically inject `WHERE organization_id = <current>`.

## Quick Start

### 1. Inherit `TenantAwareModel`

```python
# backend/apps/lessons/models.py
from apps.core.models import TenantAwareModel

class Lesson(TenantAwareModel):
    title = models.CharField(max_length=200)
    # `organization` FK is provided by the base class.

    Lesson.objects.all()        # -> only the current tenant's lessons
    Lesson.objects.unscoped()   # -> all lessons (admin/migration tooling only)
```

### 2. Register the middleware

```python
# backend/config/settings.py
MIDDLEWARE = [
    ...
    "apps.core.middleware.tenant.TenantContextMiddleware",
    ...
]
```

### 3. Include the JWT claim

```python
# backend/apps/accounts/jwt.py
def get_token(user):
    return {
        "user_id": user.id,
        "organization_id": user.organization_id,  # <-- required for RLS
        ...
    }
```

## Migrating an Existing Model

1. Add to the model:

   ```python
   organization = models.ForeignKey(
       "organizations.Organization",
       on_delete=models.CASCADE,
       null=True,
       db_index=True,
   )
   ```

2. Run the migration:

   ```bash
   python manage.py makemigrations <app>
   python manage.py migrate
   ```

3. Backfill existing rows:

   ```sql
   UPDATE <table>
   SET organization_id = (
       SELECT organization_id
       FROM accounts_userprofile
       WHERE user_id = <table>.user_id
   );
   ```

4. *(Optional)* Switch the model to inherit `TenantAwareModel` and remove the explicit `organization` field definition.

## Security Audit

Run the built-in audit command to verify no cross-tenant leaks exist:

```bash
python manage.py audit_tenant_isolation
```

The checker validates:

- [ ] Every tenant-scoped model inherits `TenantAwareModel` or declares `organization`.
- [ ] No raw SQL queries omit `organization_id` filters.
- [ ] Admin views use `organization` field list filters.
- [ ] API endpoints enforce `IsTenantMember` permission.

## Appendix: File Inventory

```
backend/apps/core/tenant.py                              # thread-local context
backend/apps/core/middleware/tenant.py                   # TenantContextMiddleware
backend/apps/core/models.py                              # TenantAwareModel + managers
backend/apps/core/mixins.py                              # OrganizationScopedQuerySetMixin
backend/apps/core/permissions.py                         # IsTenantMember
backend/apps/accounts/jwt.py                              # organization_id JWT claim
backend/config/settings.py                               # middleware registration
backend/apps/core/management/commands/audit_tenant_isolation.py
backend/apps/core/tests/test_tenant_isolation.py
docs/TENANT_ISOLATION.md                                  # this document
```
