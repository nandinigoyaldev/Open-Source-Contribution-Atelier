"""
TenantSchemaMiddleware
======================
Extracts organization tenant context from request headers or subdomains.
For enterprise organizations (is_enterprise=True), activates PostgreSQL
schema routing:
    SET search_path TO tenant_<org_slug>, public

Ensures default community users and standard requests remain on the 'public'
schema with ZERO performance penalty (no DB queries, no SET search_path roundtrips).
"""

from __future__ import annotations

import logging
from typing import Optional

from django.core.cache import cache

from apps.core.tenant import (
    clear_current_tenant,
    set_current_schema,
    set_current_tenant_instance,
)
from apps.organizations.models import Organization
from apps.organizations.tenancy import (
    RESERVED_SUBDOMAINS,
    TENANT_ID_HEADER,
    TENANT_SCHEMA_HEADER,
    TENANT_SLUG_HEADER,
    activate_tenant_schema,
    deactivate_tenant_schema,
)

logger = logging.getLogger(__name__)


class TenantSchemaMiddleware:
    """
    Middleware that dynamically isolates enterprise workspaces into dedicated schemas.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_identifier = self._extract_tenant_identifier(request)

        # FAST PATH: Community users (no tenant header/subdomain) remain on 'public' schema
        # with ZERO database queries or search_path churn.
        if not tenant_identifier:
            request.tenant = None
            request.tenant_schema = "public"
            return self.get_response(request)

        # SLOW PATH: Enterprise tenant identifier present. Resolve organization.
        organization = self._resolve_organization(tenant_identifier)

        if organization and organization.is_enterprise and organization.schema_name:
            schema_name = organization.schema_name
            request.tenant = organization
            request.tenant_schema = schema_name
            set_current_tenant_instance(organization)
            activate_tenant_schema(schema_name)
            try:
                response = self.get_response(request)
            finally:
                deactivate_tenant_schema()
                clear_current_tenant()
            return response
        else:
            request.tenant = organization
            request.tenant_schema = "public"
            return self.get_response(request)

    def _extract_tenant_identifier(self, request) -> Optional[str]:
        """
        Extracts tenant identifier from headers or subdomain.
        Header takes precedence over subdomain.
        """
        # 1. Check custom headers (used by APIs, SDKs, frontend proxies)
        for header_name in (
            TENANT_SCHEMA_HEADER,
            TENANT_SLUG_HEADER,
            TENANT_ID_HEADER,
            "HTTP_X_TENANT",
        ):
            val = request.META.get(header_name)
            if val and str(val).strip():
                return str(val).strip()

        # 2. Check subdomain: <tenant>.atelier.dev or <tenant>.localhost
        raw_host = (
            request.META.get("HTTP_HOST") or request.META.get("SERVER_NAME") or ""
        )
        if raw_host:
            host = raw_host.split(":")[0].lower()
            parts = host.split(".")
            if len(parts) >= 2:
                subdomain = parts[0]
                if subdomain and subdomain not in RESERVED_SUBDOMAINS:
                    return subdomain

        return None

    def _resolve_organization(self, identifier: str) -> Optional[Organization]:
        """
        Resolves an Organization by slug, schema_name, or primary key.
        Cached for 10 minutes to avoid repeated database lookups.
        """
        cache_key = f"tenant_org_meta:{identifier}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        org = None
        if identifier.isdigit():
            org = Organization.objects.filter(id=int(identifier)).first()
        if org is None:
            org = Organization.objects.filter(slug=identifier).first()
        if org is None:
            org = Organization.objects.filter(schema_name=identifier).first()

        cache.set(cache_key, org, timeout=600)
        return org
