# API error codes for frontend clients

Use the HTTP status first, then a machine-readable `code` when the response has one. Do not branch on `message` or `detail`: those are display text and can change. The standard Django REST Framework (DRF) exception handler is configured in `backend/config/settings.py` as `apps.accounts.exceptions.throttle_exception_handler`. It handles framework exceptions, but some views and middleware return their own response shapes. **A `code` field is not guaranteed on every error.**

The shared behavior is defined by the [exception handler](../../backend/apps/accounts/exceptions.py) and checked by the [authentication](../../backend/tests/test_auth_error_contract.py) and [signup validation](../../backend/apps/accounts/tests/test_signup_validation_errors.py) contract tests.

The examples below use placeholder values and contain no real credentials, account details, or internal errors.

## Codes and client handling

| HTTP status | `code` when present | Meaning | Recommended UI handling |
| :--- | :--- | :--- | :--- |
| 400 | `validation_error` | DRF rejected submitted data. `errors` contains field-to-message arrays; `error_codes` contains matching field-to-code arrays when field errors exist. | Keep the form open, mark affected fields, and show their messages. Use `error_codes` for programmatic choices. |
| 401 | `not_authenticated` | A protected operation was called without credentials. The handler also has an `authentication_required` fallback if an exception supplies no code. | Prompt for sign-in and preserve the intended destination. |
| 401 | `no_active_account`, `authentication_failed` | Login credentials could not be accepted. Current login uses `no_active_account`; `authentication_failed` is the handler fallback for other authentication failures. | Show a generic sign-in failure; do not disclose whether an account exists. |
| 401 | `token_not_valid` | An access or refresh token is malformed, expired, or otherwise rejected. | Clear the invalid access token and guide the user through refresh or sign-in. Avoid endless refresh loops. |
| 401 | `2fa_required` | Sign-in requires a second factor. The response can also contain `requires_2fa: true`. | Show the second-factor step; do not repeat the password request automatically. |
| 401 | `invalid_2fa_code`, `password_expired` | A second-factor code is invalid, or the password must be changed. | Keep the user in the appropriate authentication flow. |
| 403 | `permission_denied` | The authenticated user lacks permission for the action. | Explain that the action is unavailable; do not keep retrying. |
| 429 | `rate_limited` | A view throttle or API rate-limit middleware blocked the request. Here `error` is the string `"rate_limited"`, unlike the boolean `error` in the DRF examples. | Disable or slow retries until `Retry-After` seconds have passed. See [rate-limit headers](rate-limits.md). |
| 500 | `internal_server_error` | An unhandled exception reached the DRF exception handler. The response gives a safe message and may include `correlation_id`. | Show a generic failure, offer a retry for safe requests, and retain the correlation ID for support. Do not display a stack trace. |

These rows describe the shared handler, not an exhaustive list of endpoint-specific errors. For example, a DRF `NotFound` response can be `{"detail": "Not found."}` with HTTP 404 and no `code`; a view can return `{"error": "Lesson not found"}` instead. Handle 404 by status. Likewise, a server error produced outside the DRF handler need not have `internal_server_error`.

### Validation field codes

For a DRF validation error, `error_codes[field][index]` corresponds to `errors[field][index]`. Nested fields use dotted paths such as `profile.timezone` or `items.1.name`. Non-field errors may use `non_field_errors`; validation errors with no field key may have only `message`.

| Field code | Current use | UI handling |
| :--- | :--- | :--- |
| `required`, `blank`, `invalid`, `min_length`, `max_length` | Common serializer validation failures. | Highlight the field and display its corresponding message. |
| `email_taken`, `username_taken` | Duplicate email or username during signup. | Ask for a different value; avoid using this response to probe accounts. |
| `password_no_number`, `password_no_special`, `password_no_uppercase`, `password_no_lowercase` | Signup password rules. More than one code may be returned. | Show all unmet rules together. |

Other serializers can emit their own field codes. Unknown codes should still show the accompanying field message; clients should not fail closed on an unfamiliar value.

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": true,
  "code": "validation_error",
  "message": "This field is required.",
  "errors": {"username": ["This field is required."]},
  "error_codes": {"username": ["required"]}
}
```

### Throttling and server failures

Both DRF throttles and API rate-limit middleware return `rate_limited`. Use the response's `Retry-After` header or `retry_after` body value rather than assuming a fixed wait. Successful responses may have rate-limit headers too; their behavior is described in [rate-limit headers](rate-limits.md).

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 23
Content-Type: application/json

{"error": "rate_limited", "code": "rate_limited", "message": "Request limit exceeded. Please wait before retrying.", "retry_after": 23}
```

The DRF handler's `500` message omits the exception details. If present, `correlation_id` is also returned in `X-Correlation-ID` and `X-Request-ID`. Include the ID when reporting a failure to support; do not log credentials or form contents.

```json
{
  "error": true,
  "code": "internal_server_error",
  "message": "An unexpected server error occurred. (Ref: example-)",
  "correlation_id": "example-request-id"
}
```

## Version negotiation errors

API-version middleware runs before the DRF handler and does **not** use the `code` envelope. HTTP 406 has `error: "Unsupported API version"` and `supported_versions`; HTTP 410 has `error: "API version has been retired"` and `version`. Select a supported version or upgrade the client. See the [API versioning guide](../API_GUIDE.md#d-invalid-version-requests-406-not-acceptable) for the 406 example and [sunset policy](../API_GUIDE.md#4-endpoint-deprecation-and-sunset-policy) for 410.

## Robust client fallback

1. Choose the status-based path first: form correction for 400, sign-in for 401, access denied for 403, missing resource for 404, delayed retry for 429, and generic failure for 5xx.
2. If the body is JSON and has a known `code`, refine the UI using the table above. For validation, pair `errors` with `error_codes` by index.
3. If the body has no `code` or has an unknown one, show safe available text or a generic message for that status. Never expose raw server output or treat an unknown code as success.

This reference describes the current shared handler and known public exceptions. Endpoint-specific responses can have different fields; check the endpoint documentation before relying on a body shape.
