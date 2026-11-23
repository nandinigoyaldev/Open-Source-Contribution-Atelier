# Organization single sign-on (OIDC)

A managed organization can sign its members in through its own OpenID Connect
identity provider. This is the other direction from the OIDC provider that Atelier
itself exposes under `/oauth/`: here Atelier is the *relying party*.

Only the authorization-code flow with PKCE is supported.

```
Browser                       Atelier backend                      Organization IdP
  | GET /api/auth/sso/oidc/start/?organization=7 |                          |
  |--------------------------------------------->| discovery (cached)       |
  |<---------- 302 to IdP (state, nonce, S256) --|                          |
  |------------------------------------------------------------------------>|
  |<-------------- 302 /api/auth/sso/oidc/callback/?code&state -------------|
  |--------------------------------------------->| code -> token endpoint   |
  |                                              | verify ID token (JWKS)   |
  |<----- 302 frontend /auth/sso/callback?code=<one-time> -----------------|
  | POST /api/auth/sso/exchange/ {code}          |                          |
  |<---------------- {access, refresh} ----------|                          |
```

## Setting up an organization

An organization owner or admin manages the provider at
`/api/organizations/<id>/sso/` (`GET`, `PUT`, `PATCH`, `DELETE`):

```json
{
  "issuer": "https://login.acme.com/realms/acme",
  "client_id": "atelier",
  "client_secret": "...",
  "domains": ["acme.com", "acme.io"],
  "is_enabled": true,
  "auto_provision": true
}
```

* Register `https://<your-api-host>/api/auth/sso/oidc/callback/` as the redirect
  URI at the provider. Set `OIDC_SSO_REDIRECT_URI` to that exact value behind a
  proxy, so it does not depend on the incoming `Host` header.
* `issuer` must be the exact `issuer` string of the provider's
  `/.well-known/openid-configuration`. It has to be `https` and must not point at
  a private or loopback address.
* `client_secret` is write-only. It is encrypted at rest with
  `FIELD_ENCRYPTION_KEY`, never returned by the API (only `has_client_secret`),
  never written to the audit log or application logs, and never part of any
  redirect. Leave it out for a public client: PKCE alone is then used. Sending
  `PATCH` without it keeps the stored value; sending `""` clears it.
* `domains` are the email domains routed to this provider. A domain can belong to
  one organization only, and free mail domains (`gmail.com`, `outlook.com`, ...)
  can not be claimed. SSO can only be enabled when at least one domain is set.

## Domain-based routing

`POST /api/auth/sso/discover/ {"email": "ada@acme.com"}` answers
`{"sso_enabled": true, "organization_id": 7, "start_url": ".../start/?organization=7"}`
when the email's domain is claimed by an organization with SSO enabled, and
`{"sso_enabled": false}` otherwise. The frontend can use this to send the person
to `start_url` instead of the password form. Matching is on the exact domain
(case-insensitive): `sub.acme.com` and `acme.com.evil.com` do not match `acme.com`.

## What is validated

| Step | Check |
| --- | --- |
| Start | provider enabled; discovery document's `issuer` equals the configured one; endpoints are `https` |
| Redirect | fresh `state`, `nonce` and PKCE `S256` challenge per attempt, kept in the browser's session for 10 minutes and used once |
| Callback | `state` must be in *this browser's* session (stops login CSRF), then is consumed; provider `error` is never echoed |
| Token exchange | server side, with the PKCE verifier; confidential clients use HTTP Basic (`client_secret_basic`) |
| ID token | signature against the provider's JWKS (asymmetric algorithms only, `none` and `HS*` refused), `iss`, `aud` (plus `azp` when present), `exp`, `iat`, `nbf` (60 s leeway), `sub`, and `nonce` |
| Key rotation | an unknown `kid` refreshes the JWKS once (at most every 30 s) |

All requests to the provider use short timeouts, a 1 MB response cap, no
redirects, and are refused when the host resolves to a non-public address. That
guard is checked when the request is made. A hostile DNS server could still
answer differently between that check and the connection, so keep egress
filtering in place for production if the threat model includes that.
`OIDC_SSO_ALLOW_LOCAL_PROVIDERS=True` lifts the https and private-host rules for
local development with something like Keycloak on `localhost`. Do not set it in
production.

## Account linking rules

1. A returning login is matched on `(provider, issuer, subject)` only. A changed
   email in the token does nothing, and changing the provider's issuer does not
   reuse links made against the old one.
2. A person with no link yet is **never** attached to an existing account just
   because the email matches. Whoever controls an identity provider (or a mailbox
   at a claimed domain) could otherwise take over any local account. They get the
   `account_exists` error and must link from their account (rule 3).
3. Linking an existing account needs that account's own signed-in session:
   `POST /api/organizations/<id>/sso/link/` (JWT, member of the organization)
   returns a one-time `start_url` (valid 5 minutes) for the browser. After the
   provider login the subject is linked and the browser lands on the frontend with
   `?sso=linked`. A subject can be linked to one account only, and an account holds
   one link per provider.
4. A new account is created (member role, unusable password, organization set on
   the profile) only when `auto_provision` is on, the ID token has
   `email_verified: true`, the email is on one of the organization's domains, and
   no local account uses that email.
5. Staff and superuser accounts never sign in through an organization provider.
   Inactive accounts and people who are no longer members are refused.

Removing a person from the organization stops their SSO login. It does not delete
the account or revoke JWTs already issued.

## Failures

A failed login ends with a redirect to `<FRONTEND_URL>/login?sso_error=<code>`.
Codes are a fixed set and carry no provider text: `sso_not_available`,
`invalid_state`, `invalid_request`, `provider_denied`, `provider_unavailable`,
`provider_misconfigured`, `token_exchange_failed`, `id_token_invalid`,
`nonce_mismatch`, `email_not_verified`, `domain_not_allowed`, `account_exists`,
`provisioning_disabled`, `provisioning_failed`, `account_disabled`,
`privileged_account`, `not_a_member`, `identity_already_linked`,
`user_already_linked`, `link_expired`, `sso_failed`. The server log has the
detail (never tokens, codes or secrets), and successes and failures are written
to the audit trail (`sso.login_succeeded`, `sso.login_failed`,
`sso.user_provisioned`, `sso.identity_linked`).

## Operational notes

* Migration `organizations.0003_oidc_sso` adds three tables.
* The one-time login code and the link token live in the Django cache (60 s and
  5 min), like the GitHub login flow. Use a shared cache (Redis) when running more
  than one worker.
* The routes sit under `/api/auth/`, so they count against the auth rate limits
  (`RATE_LIMIT_AUTH_CATEGORY`, default 5/minute per IP). One login is three
  requests (start, callback, exchange); raise the limit if a whole office signs in
  from one address.
* Not included: SAML, SCIM provisioning, forcing SSO for an organization (password
  login stays available), IdP-initiated login and single logout.
