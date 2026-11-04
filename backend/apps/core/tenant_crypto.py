"""
Tenant-scoped encryption for sensitive profile values.

Design and operations are written up in ``docs/TENANT_ENCRYPTION.md``. In short:

* **Key ownership.** The platform owns *master keys* (``TENANT_ENCRYPTION_KEYS``, versioned by id).
  A tenant never holds key material. The key that protects a tenant's value is *derived* from a
  master key, the tenant id and the purpose of the value (HKDF-SHA256), so it is never stored and
  cannot be turned back into the master key or into another tenant's key.
* **Binding.** The tenant, the purpose and an optional record context are authenticated as AES-GCM
  associated data. A ciphertext moved to another tenant, another field or another record does not
  decrypt, even though the master key is the same.
* **Versioning.** Every ciphertext names the master key that sealed it, so decryption uses that key
  directly, any number of retired keys can stay available for reading, and ``needs_rotation`` and
  ``rotate`` move values to the primary key.
* **Failure behaviour.** It fails closed. A missing tenant, a bad configuration, an unknown key id
  or a failed authentication raises a typed error. Nothing is ever returned in place of a value
  that could not be decrypted, and errors never contain key material, plaintext or ciphertext.

Nothing here is wired into a model yet: that is deliberately a later step (see the doc).
"""

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Union, overload

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

SCHEME = "tenc1"
LEGACY_PREFIX = "enc:"
KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
PURPOSE = re.compile(r"^[a-z0-9_.:-]{1,100}$")
NONCE_BYTES = 12
_HKDF_INFO = b"atelier/tenant-crypto/v1"


class TenantCryptoError(Exception):
    """Base class. Messages never contain keys, plaintext or ciphertext."""


class CryptoConfigurationError(TenantCryptoError, ImproperlyConfigured):
    """The master keys are missing or malformed."""


class MissingTenantError(TenantCryptoError):
    """No tenant was given. There is deliberately no shared fallback key."""


class UnknownKeyError(TenantCryptoError):
    """The ciphertext was sealed with a master key this deployment does not have."""


class DecryptionError(TenantCryptoError):
    """Authentication failed: tampered data, or the wrong tenant, purpose, context or key."""


class NotEncryptedError(TenantCryptoError):
    """The value is plaintext, which is not accepted unless the caller allows it."""


# ------------------------------------------------------------------------------ configuration


@dataclass(frozen=True)
class MasterKeys:
    keys: dict  # key id -> 32 raw bytes
    primary: str


def _decode_key(key_id: str, raw: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(raw.strip().encode("ascii"))
    except Exception:
        key = b""
    if len(key) != 32:
        # say which key, never what it contains
        raise CryptoConfigurationError(
            f"TENANT_ENCRYPTION_KEYS['{key_id}'] must be a urlsafe-base64 encoded 32-byte key"
        )
    return key


def load_master_keys() -> MasterKeys:
    """
    Read and validate the configuration on every call, so a bad change is caught where it is used.

    ``TENANT_ENCRYPTION_KEYS`` maps key ids to base64 keys (a dict, or the string
    ``"k1:<key>,k2:<key>"``); ``TENANT_ENCRYPTION_PRIMARY_KEY`` names the one used to encrypt.
    """
    configured = getattr(settings, "TENANT_ENCRYPTION_KEYS", None)
    if isinstance(configured, str):
        pairs = [p for p in (item.strip() for item in configured.split(",")) if p]
        try:
            configured = dict(p.split(":", 1) for p in pairs)
        except ValueError:
            raise CryptoConfigurationError(
                "TENANT_ENCRYPTION_KEYS must look like 'k1:<key>,k2:<key>'"
            ) from None
    if not configured or not isinstance(configured, dict):
        raise CryptoConfigurationError("TENANT_ENCRYPTION_KEYS is not set")

    keys = {}
    for key_id, raw in configured.items():
        if not isinstance(key_id, str) or not KEY_ID.match(key_id):
            raise CryptoConfigurationError(
                "TENANT_ENCRYPTION_KEYS ids must be 1 to 32 letters, digits, '_' or '-'"
            )
        keys[key_id] = _decode_key(key_id, str(raw))
    if len(set(keys.values())) != len(keys):
        raise CryptoConfigurationError(
            "TENANT_ENCRYPTION_KEYS contains the same key twice"
        )

    primary = getattr(settings, "TENANT_ENCRYPTION_PRIMARY_KEY", None)
    if not primary:
        if len(keys) != 1:
            raise CryptoConfigurationError(
                "TENANT_ENCRYPTION_PRIMARY_KEY must say which of several keys encrypts"
            )
        primary = next(iter(keys))
    if primary not in keys:
        raise CryptoConfigurationError(
            "TENANT_ENCRYPTION_PRIMARY_KEY is not one of the keys"
        )
    return MasterKeys(keys=keys, primary=primary)


# ------------------------------------------------------------------------------- primitives


def _check_tenant(tenant_id) -> str:
    if tenant_id is None or isinstance(tenant_id, bool) or str(tenant_id).strip() == "":
        raise MissingTenantError("A tenant is required to encrypt or decrypt")
    return str(tenant_id)


def _check_purpose(purpose) -> str:
    if not isinstance(purpose, str) or not PURPOSE.match(purpose):
        raise ValueError(
            "purpose must be 1 to 100 lowercase letters, digits or . _ : -"
        )
    return purpose


def _derive(master: bytes, tenant: str, purpose: str) -> bytes:
    """The data key for one tenant and one purpose. Deterministic, one-way, never stored."""
    info = json.dumps(
        [_HKDF_INFO.decode(), tenant, purpose], separators=(",", ":")
    ).encode()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(
        master
    )


def _aad(tenant: str, purpose: str, context: Optional[str]) -> bytes:
    """What the ciphertext is bound to, in a form where no two bindings can look alike."""
    return json.dumps(
        [SCHEME, tenant, purpose, context or ""], separators=(",", ":")
    ).encode()


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(SCHEME + ":")


def is_legacy(value) -> bool:
    return isinstance(value, str) and value.startswith(LEGACY_PREFIX)


def key_id_of(value: Optional[str]) -> Optional[str]:
    """The master key id a ``tenc1`` value was sealed with, without decrypting it."""
    if not isinstance(value, str) or not is_encrypted(value):
        return None
    parts = value.split(":", 2)
    return parts[1] if len(parts) == 3 and KEY_ID.match(parts[1]) else None


@overload
def encrypt(
    tenant_id, purpose: str, value: str, context: Optional[str] = None
) -> str: ...


@overload
def encrypt(
    tenant_id, purpose: str, value: None, context: Optional[str] = None
) -> None: ...


@overload
def encrypt(
    tenant_id, purpose: str, value: Optional[str], context: Optional[str] = None
) -> Optional[str]: ...


def encrypt(
    tenant_id, purpose: str, value: Optional[str], context: Optional[str] = None
) -> Optional[str]:
    """
    Encrypt ``value`` for a tenant under the primary master key.

    ``None`` and the empty string are stored as they are (empty means "not set").
    ``context`` binds the value to something more specific, such as ``"user:42"``; the same
    context has to be given to decrypt.
    """
    if value is None or value == "":
        return value
    if not isinstance(value, str):
        raise TypeError("Only text can be encrypted")
    tenant, purpose = _check_tenant(tenant_id), _check_purpose(purpose)
    config = load_master_keys()
    key = _derive(config.keys[config.primary], tenant, purpose)
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(key).encrypt(
        nonce, value.encode("utf-8"), _aad(tenant, purpose, context)
    )
    token = base64.urlsafe_b64encode(nonce + sealed).decode("ascii")
    return f"{SCHEME}:{config.primary}:{token}"


def decrypt(
    tenant_id,
    purpose: str,
    value: Optional[str],
    context: Optional[str] = None,
    allow_plaintext: bool = False,
    allow_legacy: bool = False,
):
    """
    Decrypt a stored value for a tenant.

    ``allow_plaintext`` and ``allow_legacy`` exist for the migration window only: a value with no
    prefix is returned as it is, and a value from the old global-key ``EncryptedCharField`` is
    decrypted with that key. Both are off by default, so a plaintext value where ciphertext is
    expected is an error and not silently accepted.
    """
    if value is None or value == "":
        return value
    tenant, purpose = _check_tenant(tenant_id), _check_purpose(purpose)

    if is_legacy(value):
        if not allow_legacy:
            raise NotEncryptedError("Value uses the legacy encryption format")
        return _decrypt_legacy(value)
    if not is_encrypted(value):
        if allow_plaintext:
            return value
        raise NotEncryptedError("Value is not encrypted")

    parts = value.split(":", 2)
    if len(parts) != 3 or not KEY_ID.match(parts[1]):
        raise DecryptionError("Malformed ciphertext")
    key_id, token = parts[1], parts[2]
    config = load_master_keys()
    master = config.keys.get(key_id)
    if master is None:
        raise UnknownKeyError(f"No master key '{key_id}' is configured")
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except Exception:
        raise DecryptionError("Malformed ciphertext") from None
    if len(raw) < NONCE_BYTES + 16:
        raise DecryptionError("Malformed ciphertext")
    try:
        plain = AESGCM(_derive(master, tenant, purpose)).decrypt(
            raw[:NONCE_BYTES], raw[NONCE_BYTES:], _aad(tenant, purpose, context)
        )
    except InvalidTag:
        # wrong tenant, purpose, context or key, or the data was changed: indistinguishable on purpose
        raise DecryptionError("Decryption failed") from None
    return plain.decode("utf-8")


def _decrypt_legacy(value: str) -> str:
    """Read a value written by ``apps.core.fields`` (one global key, no tenant)."""
    from apps.core import fields as legacy

    plain = legacy.decrypt_value(value)
    if plain == value:  # the legacy reader returns its input when it cannot decrypt
        raise DecryptionError("Legacy value could not be decrypted")
    return plain


# ----------------------------------------------------------------------------------- rotation


def needs_rotation(value, allow_plaintext: bool = False) -> bool:
    """True if the value is not sealed under the current primary key."""
    if value is None or value == "":
        return False
    if is_encrypted(value):
        return key_id_of(value) != load_master_keys().primary
    return is_legacy(value) or allow_plaintext


@overload
def rotate(
    tenant_id,
    purpose: str,
    value: str,
    context: Optional[str] = None,
    allow_plaintext: bool = False,
    allow_legacy: bool = True,
) -> str: ...


@overload
def rotate(
    tenant_id,
    purpose: str,
    value: Optional[str],
    context: Optional[str] = None,
    allow_plaintext: bool = False,
    allow_legacy: bool = True,
) -> Optional[str]: ...


def rotate(
    tenant_id,
    purpose: str,
    value: Optional[str],
    context: Optional[str] = None,
    allow_plaintext: bool = False,
    allow_legacy: bool = True,
) -> Optional[str]:
    """
    Re-encrypt a value under the primary master key. Idempotent: a value that is already current is
    returned unchanged. Raises if the value cannot be decrypted; it is never altered in that case.
    """
    if not needs_rotation(value, allow_plaintext=allow_plaintext):
        return value
    plain = decrypt(
        tenant_id,
        purpose,
        value,
        context,
        allow_plaintext=allow_plaintext,
        allow_legacy=allow_legacy,
    )
    return encrypt(tenant_id, purpose, plain, context)


class TenantCipher:
    """A tenant and a purpose bound together, for code that encrypts one kind of value."""

    def __init__(self, tenant_id, purpose: str):
        self.tenant_id = _check_tenant(tenant_id)
        self.purpose = _check_purpose(purpose)

    def encrypt(self, value, context=None):
        return encrypt(self.tenant_id, self.purpose, value, context)

    def decrypt(self, value, context=None, **kwargs):
        return decrypt(self.tenant_id, self.purpose, value, context, **kwargs)

    def rotate(self, value, context=None, **kwargs):
        return rotate(self.tenant_id, self.purpose, value, context, **kwargs)


def cipher_for_current_tenant(purpose: str) -> TenantCipher:
    """A cipher for the tenant of the current request. Raises when there is no tenant context."""
    from apps.core.tenant import get_current_tenant_id

    return TenantCipher(get_current_tenant_id(), purpose)


# -------------------------------------------------------------------- rotation of stored data

RotationHook = Callable[["RotationTarget", dict], None]


@dataclass(frozen=True)
class RotationTarget:
    """
    A column that holds tenant-encrypted values, so the rotation command knows where to look.

    ``tenant`` is the name of a field on the row (such as ``"organization_id"``) or a function that
    takes the row and returns the tenant id. ``context`` is the same, optional.
    """

    model: str  # "app_label.ModelName"
    field: str
    purpose: str
    tenant: Union[str, Callable[[Any], Any]]
    context: Union[str, Callable[[Any], Optional[str]], None] = None

    def tenant_of(self, row):
        if callable(self.tenant):
            return self.tenant(row)
        return getattr(row, self.tenant)

    def context_of(self, row) -> Optional[str]:
        if self.context is None:
            return None
        if callable(self.context):
            return self.context(row)
        return str(getattr(row, self.context))


_TARGETS: list = []
_HOOKS: list = []


def register_rotation_target(target: RotationTarget) -> RotationTarget:
    _TARGETS[:] = [
        t for t in _TARGETS if (t.model, t.field) != (target.model, target.field)
    ]
    _TARGETS.append(target)
    return target


def rotation_targets() -> list:
    return list(_TARGETS)


def register_rotation_hook(hook: RotationHook) -> RotationHook:
    """``hook(target, stats)`` is called after each target has been rotated."""
    if hook not in _HOOKS:
        _HOOKS.append(hook)
    return hook


def run_rotation_hooks(target: RotationTarget, stats: dict) -> None:
    for hook in list(_HOOKS):
        try:
            hook(target, stats)
        except Exception:
            logger.exception("Tenant encryption rotation hook failed")


def clear_registrations() -> None:
    """Forget all targets and hooks (tests)."""
    _TARGETS.clear()
    _HOOKS.clear()


def rotate_target(
    target: RotationTarget,
    batch_size: int = 500,
    dry_run: bool = False,
    tenant_id=None,
    allow_plaintext: bool = False,
    after_pk=None,
    max_errors: int = 50,
) -> dict:
    """
    Move every value of one column to the primary master key, in primary-key order and in batches.

    Safe to repeat and to stop at any time: rows already on the primary key are skipped, each row is
    updated only if its value is still what was read (a concurrent write is never overwritten), and
    a value that cannot be decrypted is left untouched and reported.
    """
    from django.apps import apps

    load_master_keys()  # a broken configuration is one clear error, not one per row
    model = apps.get_model(target.model)
    stats = {
        "scanned": 0,
        "rotated": 0,
        "skipped_current": 0,
        "skipped_other_tenant": 0,
        "conflicts": 0,
        "errors": 0,
        "error_ids": [],
    }
    last_pk = after_pk
    while True:
        queryset = model._base_manager.order_by("pk")
        if last_pk is not None:
            queryset = queryset.filter(pk__gt=last_pk)
        rows = list(queryset[:batch_size])
        if not rows:
            break
        for row in rows:
            last_pk = row.pk
            stats["scanned"] += 1
            value = getattr(row, target.field)
            try:
                row_tenant = target.tenant_of(row)
                if tenant_id is not None and str(row_tenant) != str(tenant_id):
                    stats["skipped_other_tenant"] += 1
                    continue
                if not needs_rotation(value, allow_plaintext=allow_plaintext):
                    stats["skipped_current"] += 1
                    continue
                if dry_run:
                    stats["rotated"] += 1
                    continue
                new_value = rotate(
                    row_tenant,
                    target.purpose,
                    value,
                    target.context_of(row),
                    allow_plaintext=allow_plaintext,
                )
            except TenantCryptoError as exc:
                stats["errors"] += 1
                if len(stats["error_ids"]) < max_errors:
                    stats["error_ids"].append(row.pk)
                logger.warning(
                    "Tenant encryption rotation: %s.%s pk=%s: %s",
                    target.model,
                    target.field,
                    row.pk,
                    exc.__class__.__name__,
                )
                continue
            changed = model._base_manager.filter(
                pk=row.pk, **{target.field: value}
            ).update(**{target.field: new_value})
            stats["rotated" if changed else "conflicts"] += 1
    run_rotation_hooks(target, stats)
    return stats


def known_key_ids() -> Iterable[str]:
    return load_master_keys().keys.keys()
