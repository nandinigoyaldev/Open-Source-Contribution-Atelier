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

* **Frontend prerequisite.** This backend change does not include any UI. Before
  SSO is usable, the frontend needs a route at `/auth/sso/callback` that reads the
  one-time `code` (and optional `next`) from the query, posts it to
  `/api/auth/sso/exchange/` to get the tokens, and a `/login` page that shows the
  `sso_error` code. Linking an existing account needs a second handler (see
  "Account linking rules"). Without these the redirect lands on a page that can
  not finish the sign-in.
* Register `https://<your-api-host>/api/auth/sso/oidc/callback/` as the redirect
  URI at the provider. Set `OIDC_SSO_REDIRECT_URI` to that exact value behind a
  proxy, so it does not depend on the incoming `Host` header.
* `issuer` must be the exact `issuer` string of the provider's
  `/.well-known/openid-configuration`. It has to be `https` and must not point at
  a private or loopback address.
* `client_secret` is write-only and is stored exactly as sent (whitespace is not
  trimmed, since providers can issue secrets with it). It is encrypted at rest with
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
| ID token | signature against the provider's JWKS (asymmetric algorithms only, `none` and `HS*` refused), `iss`, `aud` (every value must be our `client_id`: extra audiences are refused because there is no trusted-audience setting), `azp` when present, `exp`, `iat`, `nbf` (60 s leeway), `sub`, and `nonce` |
| Key rotation | an unknown `kid` refreshes the JWKS once (at most every 30 s) |

All requests to the provider use short timeouts, a 1 MB response cap, no
redirects, and are refused when the host resolves to a non-public address. The
address is checked again when the socket opens and the connection goes to that
checked address (certificate and SNI still use the hostname), so a DNS answer that
changes between the check and the connection does not reach an internal host.
This does not apply when an HTTP proxy is configured in the environment, because
the proxy then resolves the target. Keep egress filtering in place if the proxy is
not trusted. The issuer must be a plain URL without a query; the authorization,
token and JWKS endpoints from discovery may carry a query (RFC 6749 allows it) but
never a fragment.
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
3. Linking an existing account needs that account's own signed-in session, twice:
   `POST /api/organizations/<id>/sso/link/` (JWT, member of the organization)
   returns a one-time `start_url` (valid 5 minutes) for the browser, optionally
   with `&next=/some/path`. After the provider login nothing is linked yet: the
   browser lands on the frontend at `next` (default `/`) with `?sso_link=<code>`
   merged into any query it already has. The frontend then posts
   `{"code": "<code>"}` with the account's JWT to
   `POST /api/organizations/<id>/sso/link/confirm/` (valid 5 minutes, single use),
   which links the subject and answers `{"linked": true}`. A code can only be
   confirmed by the account that started the link, so a leaked `start_url` cannot
   attach somebody else's provider identity to it. A subject can be linked to one
   account only, and an account holds one link per provider and issuer.
   If the organization changes the provider's issuer, existing members' old links
   stop working for login; linking again against the new issuer replaces the old
   link (a second subject at the current issuer is still refused).
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
