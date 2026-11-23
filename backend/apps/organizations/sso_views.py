# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false, reportOptionalMemberAccess=false, reportCallIssue=false
"""
HTTP endpoints for organization OIDC single sign-on.

Admin (JWT):   GET/PUT/PATCH/DELETE /api/organizations/<id>/sso/
               POST /api/organizations/<id>/sso/link/
               POST /api/organizations/<id>/sso/link/confirm/
Public flow:   POST /api/auth/sso/discover/
               GET  /api/auth/sso/oidc/start/
               GET  /api/auth/sso/oidc/callback/
               POST /api/auth/sso/exchange/

The browser parts are redirects. A failed login always ends on the frontend with
``?sso_error=<code>`` where ``code`` is one of a fixed set of identifiers. Nothing
the provider sent (error descriptions, claims, tokens) is echoed back.
"""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib.auth.models import update_last_login
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.http import HttpResponseRedirect
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.jwt import DynamicSaltRefreshToken
from apps.accounts.throttles import OAuthThrottle, _get_real_ip
from apps.accounts.views import frontend_url
from apps.audit.security_events import record_security_event
from apps.core.permissions import get_cached_organization_role

from . import oidc_client, sso_service
from .models import (
    Organization,
    OrganizationAuditLog,
    OrganizationMembership,
    OrganizationOIDCProvider,
)
from .sso_serializers import OIDCProviderSerializer
from .sso_service import SSOError

logger = logging.getLogger(__name__)

# The URL conf mounts every API route twice (/ and /api/v1/), so reverse() is
# ambiguous. The redirect URI registered at the provider has to be one fixed path.
START_PATH = "/api/auth/sso/oidc/start/"
CALLBACK_PATH = "/api/auth/sso/oidc/callback/"
SESSION_KEY = "org_sso_attempts"
ATTEMPT_TTL_SECONDS = 600
MAX_OPEN_ATTEMPTS = 5
LOGIN_CODE_TTL = 60
LINK_TOKEN_TTL = 300
LINK_CONFIRM_TTL = 300

ERROR_CODES = {
    "sso_not_available",
    "invalid_state",
    "invalid_request",
    "provider_denied",
    "provider_unavailable",
    "provider_misconfigured",
    "token_exchange_failed",
    "id_token_invalid",
    "nonce_mismatch",
    "email_not_verified",
    "domain_not_allowed",
    "account_exists",
    "provisioning_disabled",
    "provisioning_failed",
    "account_disabled",
    "privileged_account",
    "not_a_member",
    "identity_already_linked",
    "user_already_linked",
    "link_expired",
    "sso_failed",
}


# --------------------------------------------------------------------- helpers


def safe_next_path(value: Optional[str]) -> str:
    """Only a plain path on the frontend. Anything else becomes ``/``."""
    if not isinstance(value, str) or not value or len(value) > 200:
        return "/"
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return "/"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return "/"
    return value


def _frontend_next_url(path: str, extra: dict) -> str:
    """
    Frontend URL for ``path`` (which may already carry a query and a fragment)
    with ``extra`` merged into its query, so ``/dashboard?tab=1`` becomes
    ``/dashboard?tab=1&sso=linked#...`` and not ``tab=1?sso=linked``.
    """
    parts = urlsplit(path)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    query = [(k, v) for k, v in query if k not in extra] + list(extra.items())
    return frontend_url(
        urlunsplit(("", "", parts.path or "/", urlencode(query), parts.fragment))
    )


def _error_redirect(code: str):
    if code not in ERROR_CODES:
        code = "sso_failed"
    return HttpResponseRedirect(frontend_url("/login", {"sso_error": code}))


def _audit(request, operation: str, organization_id, **payload) -> None:
    record_security_event(
        operation=operation,
        target_type="organizations.organization",
        target_id=organization_id,
        payload=payload,
        ip_address=_get_real_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        request_id=request.META.get("HTTP_X_REQUEST_ID", ""),
    )


def _redirect_uri(request) -> str:
    from django.conf import settings

    configured = getattr(settings, "OIDC_SSO_REDIRECT_URI", "")
    return configured or request.build_absolute_uri(CALLBACK_PATH)


def _store_attempt(request, state: str, attempt: dict) -> None:
    now = time.time()
    attempts = request.session.get(SESSION_KEY, {})
    attempts = {
        s: a for s, a in attempts.items() if now - a.get("ts", 0) < ATTEMPT_TTL_SECONDS
    }
    # Keep only the newest few so the session can not grow without bound.
    newest = sorted(attempts.items(), key=lambda kv: kv[1]["ts"])[
        -(MAX_OPEN_ATTEMPTS - 1) :
    ]
    attempts = dict(newest)
    attempts[state] = {**attempt, "ts": now}
    request.session[SESSION_KEY] = attempts
    # The session copy of an attempt is only written back when the response goes
    # out, so two overlapping callbacks can both read it. This marker is what is
    # actually claimed (see _pop_attempt).
    cache.set(f"org-sso-state:{state}", 1, ATTEMPT_TTL_SECONDS)


def _pop_attempt(request, state: str) -> Optional[dict]:
    attempts = request.session.get(SESSION_KEY, {})
    attempt = attempts.pop(state, None)
    request.session[SESSION_KEY] = attempts
    if not attempt or time.time() - attempt.get("ts", 0) > ATTEMPT_TTL_SECONDS:
        return None
    # Delete-as-claim: only one of several concurrent callbacks gets True, and it
    # happens before any call to the provider, so a state is redeemed once.
    if not cache.delete(f"org-sso-state:{state}"):
        return None
    return attempt


# ------------------------------------------------------------- admin settings


class _OrgSSOMixin:
    permission_classes = [permissions.IsAuthenticated]

    def _org_and_role(self, request, organization_pk):
        org = Organization.objects.filter(pk=organization_pk).first()
        role = (
            get_cached_organization_role(request.user.id, organization_pk)
            if org
            else None
        )
        return org, role


class OrganizationSSOConfigView(_OrgSSOMixin, APIView):
    """Read and change the OIDC provider of one organization (owners and admins)."""

    def _check(self, request, organization_pk):
        org, role = self._org_and_role(request, organization_pk)
        if org is None or role is None:
            return None, Response(status=status.HTTP_404_NOT_FOUND)
        if role not in (
            OrganizationMembership.ROLE_OWNER,
            OrganizationMembership.ROLE_ADMIN,
        ):
            return None, Response(
                {"detail": "Only organization owners and admins can manage SSO."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return org, None

    def get(self, request, organization_pk):
        org, denied = self._check(request, organization_pk)
        if denied:
            return denied
        provider = OrganizationOIDCProvider.objects.filter(organization=org).first()
        if provider is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(OIDCProviderSerializer(provider).data)

    def _write(self, request, organization_pk, partial):
        org, denied = self._check(request, organization_pk)
        if denied:
            return denied
        provider = OrganizationOIDCProvider.objects.filter(organization=org).first()
        serializer = OIDCProviderSerializer(
            provider, data=request.data, partial=partial and provider is not None
        )
        serializer.is_valid(raise_exception=True)
        # Only field names and flags go to the audit log, never the secret.
        changed = sorted(serializer.validated_data.keys())
        created = provider is None
        provider = serializer.save(organization=org)
        OrganizationAuditLog.objects.create(
            organization_id=org.id,
            organization_name=org.name,
            actor=request.user,
            action=OrganizationAuditLog.ACTION_UPDATED,
            changes={
                "sso": {"fields": changed, "is_enabled": provider.is_enabled},
            },
        )
        return Response(
            OIDCProviderSerializer(provider).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def put(self, request, organization_pk):
        return self._write(request, organization_pk, partial=False)

    def patch(self, request, organization_pk):
        return self._write(request, organization_pk, partial=True)

    def delete(self, request, organization_pk):
        org, denied = self._check(request, organization_pk)
        if denied:
            return denied
        provider = OrganizationOIDCProvider.objects.filter(organization=org).first()
        if provider is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        provider.delete()
        OrganizationAuditLog.objects.create(
            organization_id=org.id,
            organization_name=org.name,
            actor=request.user,
            action=OrganizationAuditLog.ACTION_UPDATED,
            changes={"sso": {"removed": True}},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationSSOLinkView(_OrgSSOMixin, APIView):
    """
    Start linking the signed-in account to the organization's provider. Returns a
    one-time URL for the browser. The link is only made after the same signed-in
    account confirms it (``OrganizationSSOLinkConfirmView``), so a leaked URL can
    not attach somebody else's provider identity to this account.
    """

    throttle_classes = [OAuthThrottle]

    def post(self, request, organization_pk):
        org, role = self._org_and_role(request, organization_pk)
        if org is None or role is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if sso_service.enabled_provider_for_org(org.id) is None:
            return Response(
                {"detail": "SSO is not enabled for this organization."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = oidc_client.new_token()
        cache.set(
            f"org-sso-link:{token}",
            {"user_id": request.user.id, "organization_id": org.id},
            LINK_TOKEN_TTL,
        )
        url = request.build_absolute_uri(START_PATH)
        return Response(
            {"start_url": f"{url}?organization={org.id}&link_token={token}"}
        )


class OrganizationSSOLinkConfirmView(_OrgSSOMixin, APIView):
    """
    Second half of linking. The provider callback only stages the link and sends
    the browser to the frontend with ``sso_link=<code>``. The signed-in account that
    started the link posts that code here, so the link is made by the same account
    and not by whoever happened to hold the start URL.
    """

    throttle_classes = [OAuthThrottle]

    def post(self, request, organization_pk):
        org, role = self._org_and_role(request, organization_pk)
        if org is None or role is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        code = request.data.get("code") if hasattr(request.data, "get") else None
        invalid = Response(
            {"detail": "Invalid or expired code.", "code": "invalid_code"},
            status=status.HTTP_400_BAD_REQUEST,
        )
        if not isinstance(code, str) or not code or len(code) > 200:
            return invalid
        key = f"org-sso-link-pending:{code}"
        pending = cache.get(key)
        # Another account's code is treated like an unknown one and is left alone.
        if not pending or pending.get("user_id") != request.user.id:
            return invalid
        provider = OrganizationOIDCProvider.objects.filter(
            pk=pending["provider_id"], organization=org, is_enabled=True
        ).first()
        if provider is None or not cache.delete(key):
            return invalid
        try:
            result = sso_service.link_existing_user(
                provider, {"iss": pending["iss"], "sub": pending["sub"]}, request.user
            )
        except SSOError as exc:
            _audit(request, "sso.login_failed", org.id, code=exc.code)
            return Response(
                {"detail": "Could not link this account.", "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result.linked:
            _audit(request, "sso.identity_linked", org.id, user_id=request.user.id)
        return Response({"linked": True})


# ----------------------------------------------------------------- public flow


class _PublicSSOView(APIView):
    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OAuthThrottle]


class SSODiscoverView(_PublicSSOView):
    """Domain routing: does this email belong to an organization with SSO?"""

    def post(self, request):
        email = request.data.get("email") if hasattr(request.data, "get") else None
        try:
            if not isinstance(email, str):
                raise DjangoValidationError("email must be a string")
            validate_email(email)
        except DjangoValidationError:
            return Response(
                {"detail": "Enter a valid email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        provider = sso_service.provider_for_email(email)
        if provider is None:
            return Response({"sso_enabled": False})
        start = request.build_absolute_uri(START_PATH)
        return Response(
            {
                "sso_enabled": True,
                "organization_id": provider.organization_id,
                "start_url": f"{start}?organization={provider.organization_id}",
            }
        )


class SSOStartView(_PublicSSOView):
    def get(self, request):
        provider = None
        org_param = request.query_params.get("organization")
        email = request.query_params.get("email")
        # isdigit() is also true for superscripts that int() can not parse
        if org_param and org_param.isascii() and org_param.isdigit():
            provider = (
                sso_service.enabled_provider_for_org(int(org_param))
                if len(org_param) <= 18
                else None
            )
        elif email:
            provider = sso_service.provider_for_email(email)
        if provider is None:
            return _error_redirect("sso_not_available")

        link_user_id = None
        link_token = request.query_params.get("link_token")
        if link_token:
            link = cache.get(f"org-sso-link:{link_token}")
            if link and cache.delete(f"org-sso-link:{link_token}"):
                if link["organization_id"] != provider.organization_id:
                    return _error_redirect("link_expired")
                link_user_id = link["user_id"]
            else:
                return _error_redirect("link_expired")

        try:
            discovery = oidc_client.discover(provider.issuer)
        except oidc_client.OIDCError as exc:
            logger.warning(
                "SSO discovery failed org=%s code=%s detail=%s",
                provider.organization_id,
                exc.code,
                exc.detail,
            )
            _audit(request, "sso.start_failed", provider.organization_id, code=exc.code)
            return _error_redirect(exc.code)

        state = oidc_client.new_token()
        nonce = oidc_client.new_token()
        verifier, challenge = oidc_client.pkce_pair()
        redirect_uri = _redirect_uri(request)
        _store_attempt(
            request,
            state,
            {
                "provider": provider.pk,
                "nonce": nonce,
                "verifier": verifier,
                "redirect_uri": redirect_uri,
                "link_user_id": link_user_id,
                "next": safe_next_path(request.query_params.get("next")),
            },
        )
        url = oidc_client.build_authorization_url(
            discovery,
            client_id=provider.client_id,
            redirect_uri=redirect_uri,
            state=state,
            nonce=nonce,
            code_challenge=challenge,
            login_hint=email if (email and not link_user_id) else None,
        )
        return HttpResponseRedirect(url)


class SSOCallbackView(_PublicSSOView):
    def get(self, request):
        state = request.query_params.get("state") or ""
        attempt = _pop_attempt(request, state) if state else None
        if attempt is None:
            return _error_redirect("invalid_state")

        provider = (
            OrganizationOIDCProvider.objects.select_related("organization")
            .filter(pk=attempt["provider"], is_enabled=True)
            .first()
        )
        if provider is None:
            return _error_redirect("sso_not_available")
        org_id = provider.organization_id

        if request.query_params.get("error"):
            _audit(request, "sso.login_failed", org_id, code="provider_denied")
            return _error_redirect("provider_denied")
        code = request.query_params.get("code")
        if not code or len(code) > 2048:
            return _error_redirect("invalid_request")

        try:
            discovery = oidc_client.discover(provider.issuer)
            id_token = oidc_client.exchange_code(
                discovery,
                client_id=provider.client_id,
                client_secret=provider.client_secret,
                code=code,
                redirect_uri=attempt["redirect_uri"],
                code_verifier=attempt["verifier"],
            )
            claims = oidc_client.validate_id_token(
                id_token,
                discovery=discovery,
                issuer=provider.issuer,
                client_id=provider.client_id,
                nonce=attempt["nonce"],
            )
            if attempt.get("link_user_id"):
                from django.contrib.auth import get_user_model

                user = (
                    get_user_model().objects.filter(pk=attempt["link_user_id"]).first()
                )
                if user is None:
                    raise SSOError("link_expired")
                # Nothing is linked here. This browser may not be the one the
                # account is signed in on, so the account has to confirm.
                sso_service.check_can_link(provider, claims, user)
                result = None
            else:
                result = sso_service.sign_in(provider, claims)
        except oidc_client.OIDCError as exc:
            logger.warning(
                "SSO login failed org=%s code=%s detail=%s",
                org_id,
                exc.code,
                exc.detail,
            )
            _audit(request, "sso.login_failed", org_id, code=exc.code)
            return _error_redirect(exc.code)
        except SSOError as exc:
            logger.info("SSO login refused org=%s code=%s", org_id, exc.code)
            _audit(request, "sso.login_failed", org_id, code=exc.code)
            return _error_redirect(exc.code)
        except Exception:
            logger.exception("SSO login crashed org=%s", org_id)
            _audit(request, "sso.login_failed", org_id, code="sso_failed")
            return _error_redirect("sso_failed")

        if result is None:
            confirm_code = oidc_client.new_token()
            try:
                cache.set(
                    f"org-sso-link-pending:{confirm_code}",
                    {
                        "user_id": attempt["link_user_id"],
                        "provider_id": provider.pk,
                        "iss": claims["iss"],
                        "sub": claims["sub"],
                    },
                    LINK_CONFIRM_TTL,
                )
            except Exception:
                logger.exception("SSO link hand-off failed org=%s", org_id)
                _audit(request, "sso.login_failed", org_id, code="sso_failed")
                return _error_redirect("sso_failed")
            return HttpResponseRedirect(
                _frontend_next_url(attempt["next"], {"sso_link": confirm_code})
            )

        user = result.user
        # Mint the tokens and park them behind the one-time code before anything is
        # reported as a success. If the cache or the signer fails here the person
        # gets a clean "try again", and the account that a first login just created
        # is reused on the next attempt.
        try:
            update_last_login(None, user)
            refresh = DynamicSaltRefreshToken.for_user(user)
            login_code = oidc_client.new_token()
            cache.set(
                f"org-sso-login:{login_code}",
                {"access": str(refresh.access_token), "refresh": str(refresh)},
                LOGIN_CODE_TTL,
            )
        except Exception:
            logger.exception("SSO login hand-off failed org=%s", org_id)
            _audit(request, "sso.login_failed", org_id, code="sso_failed")
            return _error_redirect("sso_failed")
        if result.created:
            _audit(request, "sso.user_provisioned", org_id, user_id=user.id)
        _audit(request, "sso.login_succeeded", org_id, user_id=user.id)
        query = {"code": login_code}
        if attempt["next"] != "/":
            query["next"] = attempt["next"]
        return HttpResponseRedirect(frontend_url("/auth/sso/callback", query))


class SSOExchangeView(_PublicSSOView):
    """Swap the one-time code from the callback redirect for JWT tokens."""

    def post(self, request):
        code = request.data.get("code") if hasattr(request.data, "get") else None
        if not isinstance(code, str) or not code or len(code) > 200:
            return Response(
                {"detail": "Invalid code.", "code": "invalid_request"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key = f"org-sso-login:{code}"
        tokens = cache.get(key)
        # delete() only reports success to one of two concurrent requests
        if not tokens or not cache.delete(key):
            return Response(
                {"detail": "Invalid or expired code.", "code": "invalid_code"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(tokens)
