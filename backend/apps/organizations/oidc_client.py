# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false, reportOptionalMemberAccess=false, reportCallIssue=false
"""
Minimal OpenID Connect relying-party client used for organization SSO.

Only the authorization-code flow with PKCE is implemented. Everything that
comes back from the provider is treated as untrusted until it has been checked:

* discovery: the document's ``issuer`` must equal the configured issuer
* token exchange: sent from the server, with the code verifier
* ID token: signature (JWKS of the provider), ``iss``, ``aud`` (and ``azp``),
  ``exp``, ``iat``, ``nbf`` and the per-login ``nonce``

Every failure raises :class:`OIDCError` with a short, fixed ``code``. The
``detail`` is for server logs only and never holds a token, code or secret.

Outgoing requests go only to https URLs (unless ``OIDC_SSO_ALLOW_LOCAL_PROVIDERS``
is set for local development), never follow redirects, and refuse hosts that
resolve to loopback, private or link-local addresses, because the URLs come
from per-organization configuration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
from typing import Any, Optional
from urllib.parse import quote, urlencode, urlsplit

import jwt
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

DISCOVERY_TTL = 3600
JWKS_TTL = 3600
JWKS_REFRESH_COOLDOWN = 30
CLOCK_LEEWAY_SECONDS = 60
HTTP_TIMEOUT = (3.05, 8)
MAX_RESPONSE_BYTES = 1024 * 1024
SCOPES = "openid email profile"

# Asymmetric algorithms only. "none" and the HMAC family are never accepted, so a
# token can not be forged with the public key or without a signature.
ALLOWED_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
    }
)


class OIDCError(Exception):
    """A failed SSO step. ``code`` is safe to show, ``detail`` is for logs."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


def _allow_local() -> bool:
    return bool(getattr(settings, "OIDC_SSO_ALLOW_LOCAL_PROVIDERS", False))


# ---------------------------------------------------------------- PKCE / random


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def pkce_pair() -> tuple[str, str]:
    """Return ``(code_verifier, S256 code_challenge)``."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ------------------------------------------------------------------ URL safety


def check_url_syntax(url: str, *, what: str = "url") -> str:
    """
    Validate an issuer or endpoint URL without touching the network. Raises
    ``ValueError`` with a message that is safe to return to an admin.
    """
    if not isinstance(url, str) or not url or len(url) > 500:
        raise ValueError(f"{what} is required")
    parts = urlsplit(url)
    allowed = ("https", "http") if _allow_local() else ("https",)
    if parts.scheme not in allowed:
        raise ValueError(f"{what} must use https")
    host = parts.hostname
    if not host:
        raise ValueError(f"{what} must include a host")
    if parts.username or parts.password:
        raise ValueError(f"{what} must not contain credentials")
    if parts.query or parts.fragment:
        raise ValueError(f"{what} must not contain a query or fragment")
    if not _allow_local():
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError(f"{what} must not point at a local host")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not ip.is_global:
                raise ValueError(f"{what} must not point at a private address")
    return url


def _resolve_host(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise OIDCError("provider_unavailable", f"cannot resolve {host}") from exc
    return [info[4][0] for info in infos]


def assert_public_url(url: str) -> None:
    """Refuse a URL whose host resolves to a non-public address (SSRF guard)."""
    try:
        check_url_syntax(url)
    except ValueError as exc:
        raise OIDCError("provider_misconfigured", str(exc)) from exc
    if _allow_local():
        return
    host = urlsplit(url).hostname or ""
    for addr in _resolve_host(host):
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError as exc:
            raise OIDCError("provider_misconfigured", "bad address") from exc
        if not ip.is_global:
            raise OIDCError("provider_misconfigured", f"{host} is not a public host")


def _send(method: str, url: str, **kwargs: Any) -> tuple[int, bytes]:
    """The only place that talks to the network. Tests replace this."""
    try:
        resp = requests.request(
            method,
            url,
            timeout=HTTP_TIMEOUT,
            allow_redirects=False,
            stream=True,
            **kwargs,
        )
        try:
            body = b""
            for chunk in resp.iter_content(chunk_size=16384):
                body += chunk
                if len(body) > MAX_RESPONSE_BYTES:
                    raise OIDCError("provider_unavailable", "response too large")
            return resp.status_code, body
        finally:
            resp.close()
    except requests.RequestException as exc:
        raise OIDCError("provider_unavailable", type(exc).__name__) from exc


def _request_json(method: str, url: str, **kwargs: Any) -> dict:
    assert_public_url(url)
    status, body = _send(method, url, **kwargs)
    if status != 200:
        raise OIDCError(
            "provider_unavailable", f"{method} {urlsplit(url).netloc} -> {status}"
        )
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise OIDCError("provider_unavailable", "response is not JSON") from exc
    if not isinstance(data, dict):
        raise OIDCError("provider_unavailable", "response is not a JSON object")
    return data


# ------------------------------------------------------------------- discovery


def _cache_key(kind: str, value: str) -> str:
    return f"org-sso:{kind}:{hashlib.sha256(value.encode()).hexdigest()}"


def discover(issuer: str) -> dict:
    """Return the provider's endpoints, cached for an hour."""
    key = _cache_key("discovery", issuer)
    cached = cache.get(key)
    if cached:
        return cached

    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    doc = _request_json("GET", url)

    if doc.get("issuer") != issuer:
        raise OIDCError("provider_misconfigured", "discovery issuer mismatch")
    result = {"issuer": issuer}
    for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        value = doc.get(field)
        try:
            result[field] = check_url_syntax(value, what=field)
        except ValueError as exc:
            raise OIDCError("provider_misconfigured", str(exc)) from exc
    cache.set(key, result, DISCOVERY_TTL)
    return result


def build_authorization_url(
    discovery: dict,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
    login_hint: Optional[str] = None,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if login_hint:
        params["login_hint"] = login_hint
    endpoint = discovery["authorization_endpoint"]
    sep = "&" if urlsplit(endpoint).query else "?"
    return f"{endpoint}{sep}{urlencode(params)}"


# -------------------------------------------------------------- code exchange


def exchange_code(
    discovery: dict,
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> str:
    """Trade the authorization code for tokens and return the raw ID token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    headers = {"Accept": "application/json"}
    if client_secret:
        # client_secret_basic, with both values form-urlencoded (RFC 6749 2.3.1)
        raw = f"{quote(client_id, safe='')}:{quote(client_secret, safe='')}"
        headers["Authorization"] = "Basic " + base64.b64encode(raw.encode()).decode()
    else:
        data["client_id"] = client_id

    try:
        body = _request_json(
            "POST", discovery["token_endpoint"], data=data, headers=headers
        )
    except OIDCError as exc:
        if exc.code == "provider_unavailable":
            raise OIDCError("token_exchange_failed", exc.detail) from exc
        raise
    id_token = body.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise OIDCError("token_exchange_failed", "no id_token in response")
    return id_token


# ------------------------------------------------------------------ id token


def _load_jwks(jwks_uri: str, *, force: bool = False) -> list[dict]:
    key = _cache_key("jwks", jwks_uri)
    if not force:
        cached = cache.get(key)
        if cached is not None:
            return cached
    body = _request_json("GET", jwks_uri)
    keys = body.get("keys")
    if not isinstance(keys, list):
        raise OIDCError("id_token_invalid", "jwks has no keys")
    keys = [k for k in keys if isinstance(k, dict)]
    cache.set(key, keys, JWKS_TTL)
    return keys


def _pick_key(keys: list[dict], kid: Optional[str], alg: str) -> Optional[dict]:
    candidates = [
        k for k in keys if k.get("use", "sig") == "sig" and k.get("alg", alg) == alg
    ]
    if kid is not None:
        for k in candidates:
            if k.get("kid") == kid:
                return k
        return None
    # No kid in the header: only acceptable when there is exactly one usable key.
    return candidates[0] if len(candidates) == 1 else None


def _signing_key(jwks_uri: str, kid: Optional[str], alg: str):
    keys = _load_jwks(jwks_uri)
    jwk = _pick_key(keys, kid, alg)
    if jwk is None:
        # The provider may have rotated keys. Refresh once, but not on every
        # bad token, so a forged kid can not turn into a request flood.
        cooldown = _cache_key("jwks-refresh", jwks_uri)
        if cache.add(cooldown, 1, JWKS_REFRESH_COOLDOWN):
            jwk = _pick_key(_load_jwks(jwks_uri, force=True), kid, alg)
    if jwk is None:
        raise OIDCError("id_token_invalid", "no matching signing key")
    try:
        return jwt.PyJWK(jwk, algorithm=alg).key
    except Exception as exc:  # malformed or mismatched key material
        raise OIDCError("id_token_invalid", "unusable signing key") from exc


def validate_id_token(
    id_token: str,
    *,
    discovery: dict,
    issuer: str,
    client_id: str,
    nonce: str,
) -> dict:
    """Verify the ID token and return its claims."""
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as exc:
        raise OIDCError("id_token_invalid", "unreadable header") from exc

    alg = header.get("alg")
    if alg not in ALLOWED_ALGORITHMS:
        raise OIDCError("id_token_invalid", f"algorithm {alg!r} not allowed")
    kid = header.get("kid")
    if kid is not None and not isinstance(kid, str):
        raise OIDCError("id_token_invalid", "bad kid")

    key = _signing_key(discovery["jwks_uri"], kid, alg)
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=[alg],
            audience=client_id,
            issuer=issuer,
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise OIDCError("id_token_invalid", type(exc).__name__) from exc

    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != client_id:
        raise OIDCError("id_token_invalid", "azp does not match client")
    if "azp" in claims and claims["azp"] != client_id:
        raise OIDCError("id_token_invalid", "azp does not match client")

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > 255:
        raise OIDCError("id_token_invalid", "bad sub")

    token_nonce = claims.get("nonce")
    if not isinstance(token_nonce, str) or not hmac.compare_digest(
        token_nonce.encode(), nonce.encode()
    ):
        raise OIDCError("nonce_mismatch")
    return claims
