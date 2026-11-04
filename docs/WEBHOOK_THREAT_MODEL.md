# Webhook Signature Threat Model

What the signature checks in `backend/apps/webhooks/security.py` defend against, and what they do not. Setup and header details are in [WEBHOOKS.md](WEBHOOKS.md).

Code that signs or verifies:

| Where | Role |
| --- | --- |
| `tasks.deliver_webhook` | Signs outgoing deliveries (`build_signature_headers`). Also used by dead letter replay. |
| `views.TestWebhookView` | Signs the ephemeral test ping the same way. |
| `middleware.WebhookSignatureMiddleware` | Verifies incoming requests on the webhook URL prefixes or with a signature header. Timestamp required. |
| `views.GitHubWebhookView` | Verifies incoming GitHub style requests. Timestamp optional because GitHub sends none. |
| `security.require_webhook_signature` | Decorator for other receiver views. |

All of them go through `security.check_signature`.

## Covered

| Attack | What stops it | Test |
| --- | --- | --- |
| Replay of a captured request | The timestamp is signed (`"<timestamp>." + body`) and must be within `WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS` (default 300) of the server clock. | `test_captured_request_replayed_later_is_stale`, window edge tests |
| Fresh timestamp glued onto an old signature | The timestamp is part of the signed material, so the signature no longer matches. | `test_swapping_the_timestamp_breaks_the_signature` |
| Timestamp that is in the future | Rejected beyond the same bound. | `test_window_edge_in_the_future` |
| Timestamp parsing tricks (`nan`, `inf`, `-1`, `1e10`, whitespace, fullwidth digits, 30 digit numbers) | Strict `[0-9]{1,12}(.[0-9]{1,9})?` match before anything is computed. `float("nan")` used to pass the old window check because `abs(now - nan) > window` is false. | `test_malformed_timestamps_are_rejected`, `test_nan_timestamp_cannot_skip_the_window_check` |
| Body tampering | HMAC over the exact bytes. No JSON re-serialization on the verify side. | `test_tampered_body`, whitespace and unicode normalization tests |
| Signature format games (`SHA256=`, double prefix, uppercase, padding, truncation, non-ASCII) | Only `(sha256=)?[0-9a-f]{64}` is accepted. Non-ASCII input used to make `hmac.compare_digest` raise `TypeError` (a 500). | `test_signature_format_variants_are_rejected_without_crashing` |
| Timing side channel | `hmac.compare_digest` on equal-length bytes, run against every key and both formats without stopping at the first hit. | `test_comparison_goes_through_compare_digest_on_bytes` |
| Signature and bytes disagreeing on the sender | Outgoing deliveries were signed as compact JSON but sent with `requests.post(json=...)`, which adds spaces, so the body a receiver saw never matched what was signed. The task now sends the exact signed bytes (`data=body`). | `test_delivery_signs_the_exact_bytes_it_sends` |
| Retired key still working | Verification only uses the configured key ring. Removing a key rejects it. | `test_retired_key_is_rejected_once_removed` |
| Sender naming a key that does not exist, or using one key while claiming another | `X-Webhook-Key-Id` is checked against the ring and limits verification to that key. | `test_unknown_key_id_is_rejected`, `test_claimed_key_id_restricts_verification_to_that_key` |
| Forging with the published default secret | The hard coded fallback key is used only when `DEBUG` is on. Otherwise no key means a 500, not a successful verification. | `test_the_old_public_default_secret_no_longer_forges` |
| Log forging and secret leaks through the audit trail | Audit lines are one JSON object, sender supplied values are cut to 64 safe characters, and the secret, signature and body are never logged. | `test_reject_writes_one_structured_event_without_secrets`, `test_sender_controlled_values_cannot_forge_log_lines` |
| Error responses revealing which check failed | Signature, format, key id and legacy problems all return the same 403 message. (Timestamp problems return 400 with their own message.) | `test_decorator_hides_the_reason_behind_one_message` |

## Not covered

* **Replay inside the window.** A captured request can be sent again for up to the tolerance (5 minutes by default, in both directions). Receivers that need exactly-once handling must store `X-Webhook-Delivery-Id` and drop repeats. Nothing in this repo does that for incoming requests.
* **Legacy payload-only signatures while `WEBHOOK_ALLOW_LEGACY_SIGNATURES` is `True`.** They have no authenticated timestamp, so they can be replayed forever. The setting defaults to `True` for one release so existing receivers keep working; every such request is logged as `webhook.legacy_signature_accepted`. Set it to `False` once the log goes quiet.
* **GitHub deliveries.** GitHub signs only the body and sends no timestamp, so `GitHubWebhookView` cannot bound their age. Use `X-GitHub-Delivery` for dedupe if that matters.
* **Compromised secret or signing key.** Anyone holding the secret can sign anything. Rotate with `rotate_webhook_signing_key` and remove the old key from `WEBHOOK_SIGNING_KEYS`. Rotation here is a settings change; there is no automatic expiry of retired keys.
* **Clock attacks on the verifying host.** If the server clock is moved, the window moves with it. Keep NTP on.
* **Transport.** Signatures do not hide the body. Use HTTPS for `target_url`.
* **SSRF through `target_url`.** Not part of signature verification and not touched here.
* **Flooding.** Forged requests are rejected cheaply, but there is no rate limit in this module. Rejects go to the log, not the database, so a flood does not write rows.
* **`services/signature_signer.HMACSignatureSigner`.** A separate helper that only the tests use. It is still payload-only and was not changed.
