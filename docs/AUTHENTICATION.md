# JWT and Magic Link Authentication Architecture

The Open-Source Contribution Atelier uses JSON Web Tokens (JWT) for secure, stateless authentication. The platform is configured using `rest_framework_simplejwt` to provide secure access and refresh tokens.

In addition to traditional password-based authentication, the platform supports **Passwordless Magic Link Login**.

## Magic Link Authentication Architecture

The Magic Link authentication provides a secure, passwordless login flow by verifying the user's access to their registered email address.

1. The user requests a magic link by submitting their email address.
2. The backend generates a cryptographically secure, single-use `MagicLinkToken` mapped to the user.
3. An email containing a secure login link with the embedded token is dispatched.
4. When the user clicks the link, the frontend extracts the token and sends it to the verification endpoint.
5. If the token is valid, unused, and unexpired, the backend marks it as used and issues JWT access and refresh tokens.

## Magic Link API Endpoints

### Request Magic Link

**POST** `/api/auth/magic-link/request/`
**Payload:**

```json
{
  "email": "user@example.com"
}
```

**Success Response (200 OK):**

```json
{
  "message": "If an account with that email exists, a magic login link has been sent."
}
```

### Verify Magic Link

**POST** `/api/auth/magic-link/verify/`
**Payload:**

```json
{
  "token": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Success Response (200 OK):**

```json
{
  "refresh": "eyJhbGciOiJIUzI1...",
  "access": "eyJhbGciOiJIUzI1...",
  "user": {
    "username": "user",
    "email": "user@example.com",
    "is_staff": false
  },
  "message": "You have been successfully logged in."
}
```

## Email Service Configuration

Magic link emails are dispatched asynchronously using Celery via `send_magic_link_email_task`.
The default backend is `django.core.mail.backends.console.EmailBackend` for development. In production, configure an SMTP backend via the `EMAIL_BACKEND` environment variable.

## Token Lifecycle and Expiration Policies

- **Access Tokens**: Short-lived tokens used to authenticate requests to protected API endpoints. By default, they expire after **30 minutes** (configurable via `ACCESS_TOKEN_LIFETIME_MINUTES`).
- **Refresh Tokens**: Long-lived tokens used to securely obtain new access tokens without requiring the user to re-authenticate. By default, they expire after **7 days** (configurable via `REFRESH_TOKEN_LIFETIME_DAYS`).
- **Refresh Token Rotation**: When a valid refresh token is submitted to the `/api/auth/refresh/` endpoint, a _new_ access token and a _new_ refresh token are issued. The previously used refresh token is immediately blacklisted.
- **Magic Link Tokens**: Single-use tokens that expire after **15 minutes** (configurable via `MAGIC_LINK_TIMEOUT_MINUTES`). Once successfully verified, the token is permanently marked as used.

## Security Considerations

1. **Refresh Token Rotation & Blacklisting**: We have enabled rotation and blacklisting (`ROTATE_REFRESH_TOKENS=True` and `BLACKLIST_AFTER_ROTATION=True`).
2. **Token Storage**: Client applications should never store tokens in LocalStorage if they are vulnerable to XSS. Prefer secure HttpOnly cookies or secure memory storage where possible.
3. **No Revocation Lists for Access Tokens**: Because access tokens are stateless and short-lived, they cannot be individually revoked before expiration.
4. **Magic Link Security**:
   - Tokens are cryptographically secure (`uuid.uuid4`).
   - Tokens are single-use (`is_used` boolean flag).
   - Rate limits are applied to prevent email bombing (`3/minute` for request, `5/minute` for verify).
   - Generic responses are used for the request endpoint to prevent email enumeration attacks.

## Sessions After a Password Change or Reset

Changing or resetting a password must end every other way the account is signed in. Otherwise a stolen
token keeps working for as long as it lives (30 days for access tokens and a year for refresh tokens by
default).

### What is revoked

| Credential | How it is revoked |
| --- | --- |
| Access tokens | They carry the profile's `token_version` and the first 16 characters of the password hash. The version is incremented and the hash changes, so every earlier token fails verification (`apps/accounts/jwt.py`). |
| Refresh tokens | Every outstanding token for the user is added to the SimpleJWT blacklist on the server, and the refresh endpoint verifies the same claims. A refresh token that was never rotated is rejected as well. |
| Device sessions | The `UserSession` rows (the device list) are deleted. |
| WebSocket connections | A `token_revoked` event is published so open connections close. A Redis outage never blocks the change. |
| Tokens issued before the claims existed | They are accepted only if they were issued after the last password change, so they cannot survive one. |

The change and the revocation run in one database transaction: if revoking fails the password is not changed.

### What is kept

* **`POST /api/auth/change-password/`** (signed in): the device making the request stays signed in. Its
  `UserSession` is kept and the response contains a **fresh pair**, `access` and `refresh`, bound to that
  same session. Store them and replace the old pair. The previous tokens of that device stop working too.
  The existing `status` field is unchanged.
* **`POST /api/auth/password-reset/confirm/`** (signed out): everything is revoked and nothing is issued. The
  user signs in again with the new password.
* A failed change (wrong current password, weak new password) revokes nothing.
* Other users are never affected.

### Where tokens are issued

Login, the refresh endpoint, magic-link and OAuth sign-in, and `TokenService` all use
`DynamicSaltRefreshToken`, which carries the claims above and records the token so it can be blacklisted. Use it
for any new place that issues tokens, not SimpleJWT's plain `RefreshToken`.

Tests: `apps/accounts/tests/test_password_change_sessions.py`.

## Password Reset

`POST /api/auth/password-reset/` always answers the same way. The view validates the address and queues `process_password_reset_request`, for every address. Looking up the account, creating the token and sending the email all happen in the worker, so neither the response nor its timing depends on whether the account exists.

Tokens:

* The link keeps its format, `/reset-password?token=<uuid>`, but only a keyed hash of the token is stored (`PasswordResetToken.token_hash`). The hash is keyed with `SECRET_KEY` and salted with the token's purpose, so a value issued for another flow does not match, and rotating the key ends any link in flight. The raw value goes straight into the email and never passes through the task queue.
* A token lasts `PASSWORD_RESET_TIMEOUT_SECONDS` (900 by default). It dies when it is used, when a newer one is issued, and when the password changes.
* `redeem_password_reset_token` is the only place a token gets spent. It takes a lock on the user, and a conditional `UPDATE` on `is_used` decides the winner, so of several concurrent confirms exactly one changes the password. If the reset fails halfway the transaction rolls back and the token still works.

Limits, all of which apply to signed-in callers too:

| What | Limit | Setting |
| --- | --- | --- |
| Request and confirm, per client address | 3 per hour, shared | `RATE_AUTH_PASSWORD_RESET` |
| Request, per email address | 3 per hour | `RATE_AUTH_PASSWORD_RESET` |
| Validate, per client address | 10 per hour | `RATE_AUTH_PASSWORD_RESET_VALIDATE` |
| Reset emails for one account | 5 per hour, counted from its own tokens | `PASSWORD_RESET_MAX_PER_HOUR` |

The last one is checked in the worker, so hitting it looks like any other request to the caller. The middleware limit on `/api/auth/` (5 per minute) applies on top of these.

Every step writes an audit event, see [AUDIT_EVENTS.md](AUDIT_EVENTS.md#password-reset-events).

Tests: `apps/accounts/tests/test_password_reset.py`, `apps/accounts/tests/test_password_reset_hardening.py`.

## Guidelines for Extending Passwordless Authentication

- When introducing new passwordless mechanisms (e.g., OTP via SMS), use the existing token generation and verification architecture as a baseline.
- Extract common token validation logic (checking expiration, usage status) into reusable model mixins or service classes.
- Ensure any new endpoint maintains strict rate limiting to prevent brute-forcing.

## Integration Examples for Client Applications

### Intercepting 401 Responses (Axios / JavaScript)

When an API call fails with a `401 Unauthorized` status (indicating an expired access token), the client should automatically attempt to refresh the session.

```javascript
import axios from "axios";

const api = axios.create({ baseURL: "https://api.atelier.dev" });

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If the error is 401 and we haven't already retried this request
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = getStoredRefreshToken(); // e.g. from secure storage

      try {
        const { data } = await axios.post(
          "https://api.atelier.dev/api/auth/refresh/",
          {
            refresh: refreshToken,
          },
        );

        // Store the new tokens (rotation)
        storeAccessToken(data.access);
        storeRefreshToken(data.refresh);

        // Retry the original request with the new access token
        originalRequest.headers["Authorization"] = `Bearer ${data.access}`;
        return api(originalRequest);
      } catch (refreshError) {
        // The refresh token is invalid or expired. Force logout.
        logoutUser();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  },
);
```

## OIDC Provider (Atelier as Identity Provider)

In addition to logging _into_ Atelier via Google/GitHub, Atelier can act
as an OpenID Connect **provider** for third-party applications that want
to let users "Sign in with Atelier."

**Endpoints:**
| Purpose | Path |
|---|---|
| Discovery | `GET /.well-known/openid-configuration` |
| JWKS | `GET /.well-known/jwks.json` |
| Authorize | `GET /oauth/authorize/` |
| Token | `POST /oauth/token/` |
| Introspect | `POST /oauth/introspect/` |
| Revoke | `POST /oauth/revoke/` |
| Manage registered client apps | `/api/oauth/clients/` |
| Manage user-authorized apps | `/api/oauth/user-apps/` |

**Registering a client app:** a client is created via
`OAuthClientViewSet` (`/api/oauth/clients/`), which issues a
`client_id`/`client_secret` pair and requires a `redirect_uri`.

**Status:** implemented, covered by tests as of #2346. No first-party
consumer currently exists — this is intended for future third-party
integrations (e.g. partner learning platforms), not used by the Atelier
frontend itself.

## Validation Errors (Sign-up and Other Endpoints)

A request that fails validation, whichever rule fails and whichever endpoint, answers `400` with one envelope (`apps/accounts/exceptions.py`):

```json
{
  "error": true,
  "code": "validation_error",
  "message": "An account with this email address already exists.",
  "errors":      { "email": ["An account with this email address already exists."] },
  "error_codes": { "email": ["email_taken"] }
}
```

- `message` is the first message, ready to show. `errors` maps each field to its messages so a form can show them next to the fields; nested serializers and list items use dotted keys (`profile.timezone`, `items.1.name`), and errors that belong to no field use `non_field_errors`.
- `error_codes` has the same shape with **stable codes** to branch on instead of parsing text. Sign-up codes: `required`, `blank`, `invalid` (bad email or type), `min_length`, `max_length`, `username_taken`, `email_taken`, `password_too_long`, `password_no_number`, `password_no_special`, `password_no_uppercase`, `password_no_lowercase`. Every failed password rule is reported at once.
- `errors` and `error_codes` are left out when no field is involved (for example a request body that is a list gets `non_field_errors`).
- The response never contains stored account data (hashes, ids, names or e-mail of the existing account) and the submitted password is never echoed. Like most sign-up forms it does say that a username or e-mail is taken.

On the frontend, `ApiError` exposes these as `fieldErrors` and `fieldCodes`, and the sign-up form shows them under each field.

## Sign in with Google (social login)

Users can sign up / sign in with a Google account via `POST /api/auth/google/`.
The frontend opens a Google popup (`@react-oauth/google`), then exchanges the
returned token/code with the backend, which verifies it against Google's
tokeninfo/userinfo endpoints and issues a JWT.

See [`docs/GOOGLE_LOGIN.md`](GOOGLE_LOGIN.md) for the Google Cloud Console
setup, the required environment variables, and a troubleshooting table for
every error code the endpoint can return.
