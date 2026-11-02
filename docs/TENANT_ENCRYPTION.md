# Tenant-scoped encryption

`apps/core/tenant_crypto.py` encrypts sensitive values (OAuth/GitHub tokens and similar profile
data) with keys that are specific to a tenant, so that one tenant's data cannot be read with another
tenant's key and the keys can be rotated without downtime. It complements
[TENANT_ISOLATION.md](TENANT_ISOLATION.md), which covers isolation of rows; this covers isolation of
the values themselves.

> **Status.** This adds the service, the rotation tooling and the tests. No model field uses it yet.
> Switching a column over is a separate, deliberate step (see [Migrating a column](#migrating-a-column)),
> because it needs a data backfill. The existing `EncryptedFieldMixin` (global `FIELD_ENCRYPTION_KEY`)
> is unchanged and keeps working.

## Who owns the keys

| Key | Owned by | Where it lives |
| --- | --- | --- |
| **Master key** (one or more, each with an id) | The platform operator | `TENANT_ENCRYPTION_KEYS` (environment / secret manager) |
| **Tenant-and-purpose key** | Nobody; it is derived on use | Never stored |

A tenant never holds key material. The key that protects a value is

```
HKDF-SHA256(master_key, info = ["atelier/tenant-crypto/v1", tenant_id, purpose])
```

so every (tenant, purpose) pair has its own 256-bit key, and a key cannot be turned back into the
master key or into another tenant's key. Because nothing derived is stored, there is nothing per
tenant to back up, lose or leak: the master keys are the only secrets. Losing a master key loses the
data encrypted under it, so back them up like any other production secret.

> Deleting one tenant's data cryptographically ("crypto-shredding") is not possible with derived keys,
> since the tenant's key can always be re-derived. Delete the rows instead.

## Format

```
tenc1:<key_id>:<urlsafe-base64( nonce(12) || AES-256-GCM ciphertext+tag )>
```

* `tenc1` is the scheme version. `<key_id>` is the master key that sealed the value, so decryption
  picks the right key directly and any number of retired keys can stay available for reading.
* The nonce is 96 random bits per value. The tenant, the purpose and an optional record context are
  authenticated as GCM associated data (a JSON array, so `("a.b", "c")` and `("a", "b.c")` cannot
  collide). A ciphertext copied to another tenant, another field or another record fails to decrypt
  even though the master key is the same.
* `None` and `""` are stored as they are.

## Configuration

```
# each key: 32 random bytes, urlsafe base64
python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

TENANT_ENCRYPTION_KEYS=k1:<key>
TENANT_ENCRYPTION_PRIMARY_KEY=k1      # optional while there is a single key
```

`TENANT_ENCRYPTION_KEYS` also accepts a dict in settings. Key ids are 1–32 characters of
`A-Za-z0-9_-`. The same key under two ids, a key that is not 32 bytes, an unreadable list or a
primary that is not in the list are all configuration errors. With more than one key the primary
must be named. Unset, the feature raises `CryptoConfigurationError` when it is used and nothing else
in the application is affected.

## Using it

```python
from apps.core import tenant_crypto as tc

sealed = tc.encrypt(tenant_id, "profile.github_token", token, context=f"user:{user.id}")
token = tc.decrypt(tenant_id, "profile.github_token", sealed, context=f"user:{user.id}")

cipher = tc.cipher_for_current_tenant("profile.github_token")   # uses apps.core.tenant
cipher.encrypt(token)
```

* `purpose` names the field (`[a-z0-9_.:-]`, up to 100 characters). Use one purpose per field.
* `context` is optional. Pass something stable and unique to the record (a primary key) to bind the
  value to it, so a value cannot be copied between rows. It has to be the same on decrypt.

## Failure behaviour

It fails closed. Every error is a subclass of `TenantCryptoError`, and none of them contains key
material, plaintext or ciphertext.

| Situation | Error |
| --- | --- |
| No tenant (`None`, empty, a bool) | `MissingTenantError` (there is no shared fallback key) |
| Missing, malformed or duplicate keys; bad primary | `CryptoConfigurationError` (also `ImproperlyConfigured`) |
| Value names a key id that is not configured | `UnknownKeyError` |
| Wrong tenant, purpose or context; tampered or truncated data; wrong key | `DecryptionError` |
| Value is not in the `tenc1` format | `NotEncryptedError` (unless the caller opts in, below) |
| Bad purpose, or a value that is not text | `ValueError` / `TypeError` |

A value that cannot be decrypted is never returned in its encrypted form. (The older
`EncryptedFieldMixin` returns the stored ciphertext in that case; that behaviour is untouched, but is
worth moving away from when a column migrates.)

## Rotating keys

Rotation changes which master key new values are sealed with and re-seals the old ones.

1. **Add** a new key and make it the primary, keeping the old one listed:
   `TENANT_ENCRYPTION_KEYS=k1:<old>,k2:<new>` and `TENANT_ENCRYPTION_PRIMARY_KEY=k2`.
   Deploy. New writes use `k2`; old values still read with `k1`.
2. **Re-encrypt** what exists: `python manage.py rotate_tenant_encryption`. It scans each
   registered column in primary-key order in batches (`--batch-size`, default 500), and for each value
   that is not on the primary key decrypts it and writes it back sealed under the primary.
   * It is safe to repeat and to interrupt; a second run only touches what is left.
   * Each write is `UPDATE … WHERE pk = … AND column = <value that was read>`, so a row that was
     changed by the application in the meantime is left as the application wrote it and counted as
     "changed meanwhile". Run it again to pick those up.
   * `--dry-run` reports what would change. `--tenant <id>` restricts it to one tenant,
     `--target app.Model.field` to one column (repeatable).
   * A value that cannot be decrypted is reported (with its primary key) and left unchanged. The
     command then exits with an error, which usually means a retired key is missing from the list.
3. **Retire** the old key only when a run reports nothing left on it (`already current` equals
   `scanned`, no errors). Removing it earlier turns the remaining values into `UnknownKeyError`.
   Keep it in a secret backup for as long as backups that were encrypted under it may be restored.

`needs_rotation(value)` and `rotate(tenant, purpose, value)` are the per-value building blocks,
useful for rotating lazily on read.

### Registering a column

```python
from apps.core import tenant_crypto as tc

tc.register_rotation_target(tc.RotationTarget(
    model="accounts.Profile", field="github_token", purpose="profile.github_token",
    tenant="tenant_id",              # attribute name or callable(row)
    context=lambda row: f"user:{row.user_id}",   # optional
))
tc.register_rotation_hook(lambda target, stats: audit(target, stats))
```

Hooks run after each column and a hook that raises is logged and does not stop the run.

## Migrating a column

For a column that currently holds plaintext or `enc:` values (the old global-key format):

1. **Deploy the service** and the keys. Nothing changes yet.
2. **Dual-read.** Read through `decrypt(..., allow_legacy=True, allow_plaintext=True)`, write through
   `encrypt`. New writes are tenant-encrypted; old values still read.
3. **Backfill.** Register the column and run
   `python manage.py rotate_tenant_encryption --include-plaintext`. Legacy `enc:` values are converted
   (the old `FIELD_ENCRYPTION_KEY` must still be configured for this), plaintext is encrypted, both
   in the same compare-and-set batches as a normal rotation.
4. **Tighten.** Once nothing is left, drop `allow_legacy` and `allow_plaintext` so that anything
   unencrypted becomes an error instead of being accepted.

The model field itself (and its migration, if the column width changes) is the part that is not in
this change; ciphertexts are roughly 1.4× the plaintext plus about 30 characters.

## Threat model

Protects against: a leaked database or backup without the master keys; one tenant's key (or a
bug that decrypts with the wrong tenant) exposing another tenant's values; ciphertexts being swapped
between tenants, fields or records; tampering.

Does not protect against: an attacker who has both the database and the master keys, or who can run
code in the application (which can call `decrypt`); key loss.

## Tests

`apps/core/tests/test_tenant_crypto.py`: configuration validation, round trips, tenant / purpose /
context isolation, tamper and malformed input, key versioning and rotation, legacy and plaintext
migration, absence of secrets in errors, and the database rotation (batches, dry run, per-tenant,
compare-and-set conflicts, unreadable rows, hooks) and the management command.
