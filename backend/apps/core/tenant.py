"""
Thread-local tenant context for cross-tenant data isolation.

This module is intentionally kept separate from the middleware that
populates it (``apps.core.middleware.tenant``) so that model managers
and querysets can read the current tenant without importing the
middleware (which would create a circular import in some code paths).

The context is populated by :class:`TenantContextMiddleware` on every
authenticated request and cleared in a ``finally`` block to prevent
bleed-through between requests served by the same worker thread.
"""

import threading

_tenant_local = threading.local()


def get_current_tenant_id():
    """
    Return the organization id of the current request's tenant, or
    ``None`` if no tenant context is active (e.g. management commands,
    background tasks, unauthenticated requests).
    """
    return getattr(_tenant_local, "organization_id", None)


def get_current_user_id():
    """Return the user id of the current request, or ``None``."""
    return getattr(_tenant_local, "user_id", None)


def set_current_tenant(organization_id, user_id=None):
    """Populate the thread-local tenant context."""
    _tenant_local.organization_id = organization_id
    _tenant_local.user_id = user_id


def clear_current_tenant():
    """Clear the thread-local tenant context (always call in ``finally``)."""
    _tenant_local.organization_id = None
    _tenant_local.user_id = None
