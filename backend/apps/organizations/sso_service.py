# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false, reportOptionalMemberAccess=false, reportCallIssue=false
"""
Domain routing and account linking for organization OIDC single sign-on.

Linking rules (see ``docs/ORGANIZATION_OIDC_SSO.md``):

1. A returning login is matched on ``(provider, issuer, subject)`` only.
2. A person with no link yet is **never** attached to an existing account just
   because the email matches. That would let whoever controls the identity
   provider (or a mailbox at a claimed domain) take over any local account.
   They are told to sign in the usual way and link from their account instead.
3. Linking an existing account needs that account's own signed-in session, and
   the person must already be a member of the organization.
4. A brand new account is created only when the provider reports a *verified*
   email on one of the organization's domains and no local account uses it.
5. Staff and superuser accounts never sign in through a tenant provider.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    OrganizationMembership,
    OrganizationOIDCProvider,
    OrganizationSSODomain,
    OrganizationSSOIdentity,
)

logger = logging.getLogger(__name__)
User = get_user_model()

# Free mail providers. A tenant can not claim these for routing.
PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "yahoo.com",
        "ymail.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "mail.com",
        "zoho.com",
        "yandex.com",
        "qq.com",
        "example.com",
    }
)


class SSOError(Exception):
    """A refused SSO login. ``code`` is a fixed, user-safe identifier."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class SSOResult:
    user: AbstractBaseUser
    created: bool = False
    linked: bool = False


def email_domain(email: str) -> str:
    email = (email or "").strip().lower()
    if email.count("@") != 1:
        return ""
    return email.rsplit("@", 1)[1]


def provider_for_email(email: str) -> Optional[OrganizationOIDCProvider]:
    """Enabled provider whose organization claimed the email's domain."""
    domain = email_domain(email)
    if not domain:
        return None
    row = (
        OrganizationSSODomain.objects.select_related("provider__organization")
        .filter(domain=domain, provider__is_enabled=True)
        .first()
    )
    return row.provider if row else None


def enabled_provider_for_org(organization_id) -> Optional[OrganizationOIDCProvider]:
    return (
        OrganizationOIDCProvider.objects.select_related("organization")
        .filter(organization_id=organization_id, is_enabled=True)
        .first()
    )


def _verified_email(claims: dict) -> str:
    email = claims.get("email")
    verified = claims.get("email_verified")
    if verified is True or verified == "true":
        if isinstance(email, str) and email.strip():
            return email.strip().lower()
    return ""


def _new_username(claims: dict, email: str) -> str:
    from apps.accounts.views import available_username_from_value

    seed = claims.get("preferred_username")
    if not isinstance(seed, str) or not seed.strip():
        seed = email
    return available_username_from_value(seed)[:150]


def _check_user_allowed(user) -> None:
    if not user.is_active:
        raise SSOError("account_disabled")
    if user.is_staff or user.is_superuser:
        raise SSOError("privileged_account")


def _touch(identity: OrganizationSSOIdentity) -> None:
    identity.last_login_at = timezone.now()
    identity.save(update_fields=["last_login_at"])


def _link(provider, issuer, subject, user) -> OrganizationSSOIdentity:
    return OrganizationSSOIdentity.objects.create(
        provider=provider,
        issuer=issuer,
        subject=subject,
        user=user,
        last_login_at=timezone.now(),
    )


def check_can_link(provider, claims: dict, user) -> None:
    """
    The checks of :func:`link_existing_user` without writing anything. The callback
    runs this before it asks the signed-in user to confirm the link.
    """
    issuer, subject = claims["iss"], claims["sub"]
    _check_user_allowed(user)
    if not OrganizationMembership.objects.filter(
        organization_id=provider.organization_id, user=user
    ).exists():
        raise SSOError("not_a_member")
    existing = OrganizationSSOIdentity.objects.filter(
        provider=provider, issuer=issuer, subject=subject
    ).first()
    if existing is not None and existing.user_id != user.id:
        raise SSOError("identity_already_linked")
    if (
        existing is None
        and OrganizationSSOIdentity.objects.filter(
            provider=provider, user=user, issuer=issuer
        ).exists()
    ):
        raise SSOError("user_already_linked")


def link_existing_user(provider, claims: dict, user) -> SSOResult:
    """Attach the provider subject to a user who proved their own account."""
    issuer, subject = claims["iss"], claims["sub"]
    with transaction.atomic():
        _check_user_allowed(user)
        if not OrganizationMembership.objects.filter(
            organization_id=provider.organization_id, user=user
        ).exists():
            raise SSOError("not_a_member")

        existing = (
            OrganizationSSOIdentity.objects.select_for_update()
            .filter(provider=provider, issuer=issuer, subject=subject)
            .first()
        )
        if existing is not None:
            if existing.user_id != user.id:
                raise SSOError("identity_already_linked")
            _touch(existing)
            return SSOResult(user=user)
        if OrganizationSSOIdentity.objects.filter(
            provider=provider, user=user, issuer=issuer
        ).exists():
            # A second subject at the issuer that is current today.
            raise SSOError("user_already_linked")
        # A link made at an earlier issuer can not sign anyone in any more (login
        # matches on the issuer), and it would block the one-link-per-user rule.
        # The person has just proved the local account (signed-in confirmation) and
        # the identity at the new issuer, so the stale link is replaced.
        OrganizationSSOIdentity.objects.filter(provider=provider, user=user).exclude(
            issuer=issuer
        ).delete()
        try:
            _link(provider, issuer, subject, user)
        except IntegrityError:
            raise SSOError("identity_already_linked")
    return SSOResult(user=user, linked=True)


def sign_in(provider, claims: dict) -> SSOResult:
    """Resolve validated ID token claims to a local user for a normal SSO login."""
    issuer, subject = claims["iss"], claims["sub"]

    identity = (
        OrganizationSSOIdentity.objects.select_related("user")
        .filter(provider=provider, issuer=issuer, subject=subject)
        .first()
    )
    if identity is not None:
        user = identity.user
        _check_user_allowed(user)
        if not OrganizationMembership.objects.filter(
            organization_id=provider.organization_id, user=user
        ).exists():
            raise SSOError("not_a_member")
        _touch(identity)
        return SSOResult(user=user)

    email = _verified_email(claims)
    if not email:
        raise SSOError("email_not_verified")
    domain = email_domain(email)
    if not provider.domains.filter(domain=domain).exists():
        raise SSOError("domain_not_allowed")
    if User.objects.filter(email__iexact=email).exists():
        # Same email is not proof of the same person. Link from a signed-in session.
        raise SSOError("account_exists")
    if not provider.auto_provision:
        raise SSOError("provisioning_disabled")

    try:
        with transaction.atomic():
            # Provisioning for one provider is serialized on its row. A domain
            # belongs to one provider, so two first logins with the same email
            # always meet here: the second one waits, then sees the committed user.
            OrganizationOIDCProvider.objects.select_for_update().filter(
                pk=provider.pk
            ).first()
            if User.objects.filter(email__iexact=email).exists():
                # Checked again under the lock: the check above can be stale.
                raise SSOError("account_exists")
            user = User.objects.create_user(
                username=_new_username(claims, email), email=email, password=None
            )
            OrganizationMembership.objects.create(
                organization_id=provider.organization_id,
                user=user,
                role=OrganizationMembership.ROLE_MEMBER,
            )
            profile = getattr(user, "user_profile", None)
            if profile is not None and profile.organization_id is None:
                profile.organization_id = provider.organization_id
                profile.save(update_fields=["organization"])
            _link(provider, issuer, subject, user)
    except IntegrityError:
        # Lost a race with another first login (same subject, email or username).
        raise SSOError("provisioning_failed")
    return SSOResult(user=user, created=True)
