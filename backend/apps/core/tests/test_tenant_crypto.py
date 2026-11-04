"""Tenant-scoped encryption: isolation, key versioning, rotation, migration, failure behaviour (#3280)."""

import base64
import os
from io import StringIO
from typing import Any
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import fields as legacy
from apps.core import tenant_crypto as tc
from apps.core.tenant import clear_current_tenant, set_current_tenant
from apps.notifications.models import Notification


def new_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.fixture(autouse=True)
def keys(settings):
    settings.TENANT_ENCRYPTION_KEYS = {"k1": new_key()}
    settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k1"
    tc.clear_registrations()
    yield
    tc.clear_registrations()
    clear_current_tenant()


def flip(token_value: str) -> str:
    """The same ciphertext with one bit of the sealed data changed."""
    scheme, key_id, token = token_value.split(":", 2)
    raw = bytearray(base64.urlsafe_b64decode(token))
    raw[-1] ^= 1
    return f"{scheme}:{key_id}:" + base64.urlsafe_b64encode(bytes(raw)).decode()


# -------------------------------------------------------------------------- configuration


class TestConfiguration:
    def test_a_single_key_is_the_primary_without_saying_so(self, settings):
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = ""
        assert tc.load_master_keys().primary == "k1"

    def test_keys_can_be_given_as_a_comma_separated_string(self, settings):
        a, b = new_key(), new_key()
        settings.TENANT_ENCRYPTION_KEYS = f"old:{a}, new:{b}"
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "new"
        cfg = tc.load_master_keys()
        assert set(cfg.keys) == {"old", "new"} and cfg.primary == "new"

    @pytest.mark.parametrize("value", ["", None, {}, "k1", "k1;abc", 5])
    def test_missing_or_unreadable_configuration_fails_closed(self, settings, value):
        settings.TENANT_ENCRYPTION_KEYS = value
        with pytest.raises(tc.CryptoConfigurationError):
            tc.encrypt(1, "profile.token", "secret")
        with pytest.raises(tc.CryptoConfigurationError):
            tc.decrypt(1, "profile.token", "tenc1:k1:AAAA")

    @pytest.mark.parametrize(
        "bad",
        [
            "not base64!!",
            base64.urlsafe_b64encode(b"short").decode(),
            base64.urlsafe_b64encode(os.urandom(33)).decode(),
        ],
    )
    def test_a_key_must_be_32_bytes_of_base64(self, settings, bad):
        settings.TENANT_ENCRYPTION_KEYS = {"k1": bad}
        with pytest.raises(tc.CryptoConfigurationError) as info:
            tc.load_master_keys()
        assert bad not in str(info.value)

    def test_key_ids_are_restricted(self, settings):
        settings.TENANT_ENCRYPTION_KEYS = {"bad:id": new_key()}
        with pytest.raises(tc.CryptoConfigurationError):
            tc.load_master_keys()

    def test_the_same_key_under_two_ids_is_refused(self, settings):
        same = new_key()
        settings.TENANT_ENCRYPTION_KEYS = {"a": same, "b": same}
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "a"
        with pytest.raises(tc.CryptoConfigurationError):
            tc.load_master_keys()

    def test_the_primary_has_to_be_named_when_there_are_several_keys(self, settings):
        settings.TENANT_ENCRYPTION_KEYS = {"a": new_key(), "b": new_key()}
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = ""
        with pytest.raises(tc.CryptoConfigurationError):
            tc.load_master_keys()
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "c"
        with pytest.raises(tc.CryptoConfigurationError):
            tc.load_master_keys()

    def test_configuration_errors_are_django_configuration_errors_too(self):
        from django.core.exceptions import ImproperlyConfigured

        assert issubclass(tc.CryptoConfigurationError, ImproperlyConfigured)


# ----------------------------------------------------------------------------- round trips


class TestRoundTrip:
    @pytest.mark.parametrize(
        "value",
        ["secret", "pässwörd-日本語-🔑", "x" * 100_000, "line\nbreak", " spaces "],
    )
    def test_values_come_back_unchanged(self, value):
        sealed = tc.encrypt(7, "profile.token", value)
        assert sealed.startswith("tenc1:k1:") and value not in sealed
        assert tc.decrypt(7, "profile.token", sealed) == value

    def test_the_same_value_is_sealed_differently_each_time(self):
        a, b = tc.encrypt(7, "p", "same"), tc.encrypt(7, "p", "same")
        assert a != b
        assert tc.decrypt(7, "p", a) == tc.decrypt(7, "p", b) == "same"

    def test_nonces_do_not_repeat(self):
        nonces = {
            base64.urlsafe_b64decode(tc.encrypt(1, "p", "v").split(":", 2)[2])[:12]
            for _ in range(500)
        }
        assert len(nonces) == 500

    def test_none_and_empty_are_stored_as_they_are(self):
        assert tc.encrypt(1, "p", None) is None
        assert tc.encrypt(1, "p", "") == ""
        assert tc.decrypt(1, "p", None) is None
        assert tc.decrypt(1, "p", "") == ""

    def test_only_text_can_be_encrypted(self):
        wrong_types: list[Any] = [5, b"bytes", ["a"], {"a": 1}]
        for bad in wrong_types:
            with pytest.raises(TypeError):
                tc.encrypt(1, "p", bad)

    def test_the_tenant_may_be_given_as_a_number_or_text(self):
        assert tc.decrypt("12", "p", tc.encrypt(12, "p", "v")) == "v"

    def test_a_bound_cipher_does_the_same(self):
        cipher = tc.TenantCipher(5, "profile.token")
        assert cipher.decrypt(cipher.encrypt("v")) == "v"
        assert tc.decrypt(5, "profile.token", cipher.encrypt("v")) == "v"

    def test_the_cipher_for_the_current_tenant(self):
        set_current_tenant(9)
        cipher = tc.cipher_for_current_tenant("profile.token")
        assert tc.decrypt(9, "profile.token", cipher.encrypt("v")) == "v"

    def test_there_is_no_cipher_without_a_tenant(self):
        clear_current_tenant()
        with pytest.raises(tc.MissingTenantError):
            tc.cipher_for_current_tenant("profile.token")


# ------------------------------------------------------------------------------- isolation


class TestIsolation:
    def test_one_tenants_value_cannot_be_read_as_another(self):
        sealed = tc.encrypt(1, "profile.token", "tenant one secret")
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(2, "profile.token", sealed)

    def test_a_value_cannot_be_moved_to_another_field(self):
        sealed = tc.encrypt(1, "profile.github_token", "t")
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "profile.google_token", sealed)

    def test_a_value_can_be_bound_to_one_record(self):
        sealed = tc.encrypt(1, "p", "t", context="user:42")
        assert tc.decrypt(1, "p", sealed, context="user:42") == "t"
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "p", sealed, context="user:43")
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "p", sealed)
        unbound = tc.encrypt(1, "p", "t")
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "p", unbound, context="user:42")

    def test_bindings_cannot_be_confused_with_each_other(self):
        # "a|b" as a purpose and "a" + context "b" must not collide
        sealed = tc.encrypt(1, "a.b", "t", context="c")
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "a", sealed, context="b.c")

    def test_each_tenant_and_purpose_has_its_own_derived_key(self, settings):
        master = tc.load_master_keys().keys["k1"]
        keys = {tc._derive(master, str(t), p) for t in (1, 2, 3) for p in ("a", "b")}
        assert len(keys) == 6 and master not in keys
        assert tc._derive(master, "1", "a") == tc._derive(master, "1", "a")

    def test_a_different_master_key_cannot_read_it(self, settings):
        sealed = tc.encrypt(1, "p", "t")
        settings.TENANT_ENCRYPTION_KEYS = {"k1": new_key()}
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "p", sealed)


# ----------------------------------------------------------------------------- failure modes


class TestFailureBehaviour:
    @pytest.mark.parametrize("tenant", [None, "", "  ", False, True])
    def test_there_is_no_shared_fallback_key(self, tenant):
        with pytest.raises(tc.MissingTenantError):
            tc.encrypt(tenant, "p", "v")
        with pytest.raises(tc.MissingTenantError):
            tc.decrypt(tenant, "p", tc.encrypt(1, "p", "v"))

    @pytest.mark.parametrize(
        "purpose", ["", "Has Caps", "has space", "x" * 101, None, 5]
    )
    def test_a_purpose_must_be_well_formed(self, purpose):
        with pytest.raises(ValueError):
            tc.encrypt(1, purpose, "v")

    def test_tampered_data_is_rejected(self):
        sealed = tc.encrypt(1, "p", "v")
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "p", flip(sealed))

    @pytest.mark.parametrize(
        "bad",
        [
            "tenc1:k1:",
            "tenc1:k1:AAAA",
            "tenc1:k1:!!!",
            "tenc1:k1",
            "tenc1::AAAA",
            "tenc1:bad id:AAAA",
        ],
    )
    def test_malformed_ciphertext_is_rejected_not_passed_through(self, bad):
        with pytest.raises(tc.TenantCryptoError):
            tc.decrypt(1, "p", bad)

    def test_a_key_that_is_not_configured_is_an_error_and_not_a_guess(self, settings):
        sealed = tc.encrypt(1, "p", "v")
        settings.TENANT_ENCRYPTION_KEYS = {"k9": new_key()}
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k9"
        with pytest.raises(tc.UnknownKeyError):
            tc.decrypt(1, "p", sealed)

    def test_relabelling_the_key_id_does_not_help(self, settings):
        settings.TENANT_ENCRYPTION_KEYS = {"k1": new_key(), "k2": new_key()}
        sealed = tc.encrypt(1, "p", "v")
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "p", sealed.replace(":k1:", ":k2:", 1))

    def test_errors_never_contain_secrets(self, settings):
        secret = "super-secret-token-value"
        sealed = tc.encrypt(1, "p", secret)
        key = settings.TENANT_ENCRYPTION_KEYS["k1"]
        messages = []
        for call in (
            lambda: tc.decrypt(2, "p", sealed),
            lambda: tc.decrypt(1, "p", flip(sealed)),
            lambda: tc.decrypt(None, "p", sealed),
            lambda: tc.decrypt(1, "p", "plain text"),
        ):
            with pytest.raises(tc.TenantCryptoError) as info:
                call()
            messages.append(str(info.value) + repr(info.value))
        joined = " ".join(messages)
        assert secret not in joined and key not in joined and sealed not in joined

    def test_plaintext_is_not_accepted_unless_the_caller_asks(self):
        with pytest.raises(tc.NotEncryptedError):
            tc.decrypt(1, "p", "plain")
        assert tc.decrypt(1, "p", "plain", allow_plaintext=True) == "plain"

    def test_a_failed_decryption_never_hands_back_the_ciphertext(self):
        sealed = tc.encrypt(1, "p", "v")
        try:
            result = tc.decrypt(2, "p", sealed)
        except tc.DecryptionError:
            result = None
        assert result is None


# --------------------------------------------------------------------- versions and rotation


class TestKeyVersions:
    def two_keys(self, settings):
        old = settings.TENANT_ENCRYPTION_KEYS["k1"]
        settings.TENANT_ENCRYPTION_KEYS = {"k1": old, "k2": new_key()}

    def test_the_value_names_the_key_that_sealed_it(self, settings):
        sealed = tc.encrypt(1, "p", "v")
        assert tc.key_id_of(sealed) == "k1"
        self.two_keys(settings)
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        assert tc.key_id_of(tc.encrypt(1, "p", "v")) == "k2"
        assert tc.key_id_of("plain") is None

    def test_old_values_stay_readable_after_the_primary_changes(self, settings):
        sealed = tc.encrypt(1, "p", "v")
        self.two_keys(settings)
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        assert tc.decrypt(1, "p", sealed) == "v"
        assert tc.needs_rotation(sealed) is True

    def test_rotating_moves_a_value_to_the_primary_key(self, settings):
        sealed = tc.encrypt(1, "p", "v", context="c")
        self.two_keys(settings)
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        rotated = tc.rotate(1, "p", sealed, context="c")
        assert tc.key_id_of(rotated) == "k2" and rotated != sealed
        assert tc.decrypt(1, "p", rotated, context="c") == "v"
        assert tc.needs_rotation(rotated) is False

    def test_rotating_twice_changes_nothing(self, settings):
        self.two_keys(settings)
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        sealed = tc.encrypt(1, "p", "v")
        assert tc.rotate(1, "p", sealed) == sealed

    def test_once_nothing_uses_the_retired_key_it_can_be_removed(self, settings):
        sealed = tc.encrypt(1, "p", "v")
        self.two_keys(settings)
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        rotated = tc.rotate(1, "p", sealed)
        settings.TENANT_ENCRYPTION_KEYS = {"k2": settings.TENANT_ENCRYPTION_KEYS["k2"]}
        assert tc.decrypt(1, "p", rotated) == "v"
        with pytest.raises(tc.UnknownKeyError):
            tc.decrypt(1, "p", sealed)

    def test_rotation_refuses_a_value_it_cannot_read_and_leaves_it_alone(
        self, settings
    ):
        sealed = tc.encrypt(1, "p", "v")
        self.two_keys(settings)
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        with pytest.raises(tc.DecryptionError):
            tc.rotate(2, "p", sealed)  # wrong tenant

    def test_needs_rotation_for_other_forms(self):
        assert tc.needs_rotation(None) is False and tc.needs_rotation("") is False
        assert tc.needs_rotation("plain") is False
        assert tc.needs_rotation("plain", allow_plaintext=True) is True
        assert tc.needs_rotation(legacy.encrypt_value("legacy")) is True


# ------------------------------------------------------------------------------ migration


class TestMigrationFromLegacyAndPlaintext:
    def test_a_value_from_the_old_global_key_field_can_be_read_during_migration(self):
        old = legacy.encrypt_value("old-token")
        assert old.startswith("enc:")
        with pytest.raises(tc.NotEncryptedError):
            tc.decrypt(1, "p", old)
        assert tc.decrypt(1, "p", old, allow_legacy=True) == "old-token"

    def test_a_legacy_value_that_cannot_be_decrypted_is_an_error_not_the_ciphertext(
        self, settings
    ):
        old = legacy.encrypt_value("old-token")
        settings.FIELD_ENCRYPTION_KEY = new_key()  # the global key changed
        with pytest.raises(tc.DecryptionError):
            tc.decrypt(1, "p", old, allow_legacy=True)

    def test_rotating_a_legacy_value_gives_a_tenant_value(self):
        old = legacy.encrypt_value("old-token")
        new = tc.rotate(4, "p", old)
        assert tc.is_encrypted(new) and tc.decrypt(4, "p", new) == "old-token"

    def test_backfilling_plaintext(self):
        assert tc.rotate(4, "p", "plain") == "plain"  # not unless asked
        new = tc.rotate(4, "p", "plain", allow_plaintext=True)
        assert tc.is_encrypted(new) and tc.decrypt(4, "p", new) == "plain"


# ------------------------------------------------------- rotating columns in the database


@pytest.fixture
def two_keys_primary_k2(settings):
    first = settings.TENANT_ENCRYPTION_KEYS["k1"]
    settings.TENANT_ENCRYPTION_KEYS = {"k1": first, "k2": new_key()}


@pytest.fixture
def target():
    return tc.register_rotation_target(
        tc.RotationTarget(
            model="notifications.Notification",
            field="message",
            purpose="notification.message",
            tenant="recipient_id",
        )
    )


@pytest.fixture
def seeded(db, user, django_user_model):
    other = django_user_model.objects.create_user(
        username="tc-other", email="tc@example.com", password="x"
    )
    rows = {}
    for owner in (user, other):
        for i in range(6):
            n = Notification.objects.create(
                recipient=owner, notif_type="badge", title="t", message="x", meta={}
            )
            sealed = tc.encrypt(
                owner.id, "notification.message", f"secret {owner.id}-{i}"
            )
            Notification.objects.filter(pk=n.pk).update(message=sealed)
            rows[n.pk] = (owner.id, f"secret {owner.id}-{i}")
    return rows, user, other


def stored(pk):
    return Notification.objects.get(pk=pk).message


@pytest.mark.django_db
class TestRotatingStoredData:
    def switch(self, settings):
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"

    def test_every_row_moves_to_the_primary_key_and_keeps_its_value(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        rows, _, _ = seeded
        self.switch(settings)
        stats = tc.rotate_target(target, batch_size=4)
        assert (
            stats["scanned"] == len(rows)
            and stats["rotated"] == len(rows)
            and stats["errors"] == 0
        )
        for pk, (tenant, plain) in rows.items():
            assert tc.key_id_of(stored(pk)) == "k2"
            assert tc.decrypt(tenant, "notification.message", stored(pk)) == plain

    def test_running_it_again_does_nothing(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        self.switch(settings)
        tc.rotate_target(target)
        before = {pk: stored(pk) for pk in seeded[0]}
        again = tc.rotate_target(target)
        assert again["rotated"] == 0 and again["skipped_current"] == len(before)
        assert {pk: stored(pk) for pk in before} == before

    def test_a_dry_run_changes_nothing(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        self.switch(settings)
        before = {pk: stored(pk) for pk in seeded[0]}
        stats = tc.rotate_target(target, dry_run=True)
        assert stats["rotated"] == len(before)
        assert {pk: stored(pk) for pk in before} == before

    def test_one_tenant_can_be_rotated_on_its_own(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        rows, user, other = seeded
        self.switch(settings)
        stats = tc.rotate_target(target, tenant_id=user.id)
        assert stats["rotated"] == 6 and stats["skipped_other_tenant"] == 6
        for pk, (tenant, _) in rows.items():
            assert tc.key_id_of(stored(pk)) == ("k2" if tenant == user.id else "k1")

    def test_a_value_that_cannot_be_decrypted_is_reported_and_left_alone(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        rows, _, _ = seeded
        bad_pk = next(iter(rows))
        Notification.objects.filter(pk=bad_pk).update(
            message="tenc1:k1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        self.switch(settings)
        stats = tc.rotate_target(target)
        assert stats["errors"] == 1 and stats["error_ids"] == [bad_pk]
        assert stats["rotated"] == len(rows) - 1
        assert stored(bad_pk).startswith("tenc1:k1:AAAA")

    def test_a_row_changed_by_someone_else_meanwhile_is_not_overwritten(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        rows, _, _ = seeded
        victim = next(iter(rows))
        real = tc.rotate
        newer = tc.encrypt(rows[victim][0], "notification.message", "written meanwhile")

        def rotate_then_lose_the_race(tenant, purpose, value, *args, **kwargs):
            result = real(tenant, purpose, value, *args, **kwargs)
            if tc.decrypt(tenant, purpose, value) == rows[victim][1]:
                Notification.objects.filter(pk=victim).update(message=newer)
            return result

        self.switch(settings)
        with patch.object(tc, "rotate", rotate_then_lose_the_race):
            stats = tc.rotate_target(target)
        assert stats["conflicts"] == 1
        assert stored(victim) == newer

    def test_plaintext_rows_are_skipped_unless_asked(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        rows, _, _ = seeded
        pk = next(iter(rows))
        Notification.objects.filter(pk=pk).update(message="still plain")
        self.switch(settings)
        tc.rotate_target(target)
        assert stored(pk) == "still plain"
        tc.rotate_target(target, allow_plaintext=True)
        assert (
            tc.decrypt(rows[pk][0], "notification.message", stored(pk)) == "still plain"
        )

    def test_legacy_rows_are_converted(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        rows, _, _ = seeded
        pk = next(iter(rows))
        Notification.objects.filter(pk=pk).update(
            message=legacy.encrypt_value("from the old field")
        )
        self.switch(settings)
        tc.rotate_target(target)
        assert (
            tc.decrypt(rows[pk][0], "notification.message", stored(pk))
            == "from the old field"
        )

    def test_a_record_context_is_part_of_the_binding(
        self, db, user, settings, two_keys_primary_k2
    ):
        target = tc.register_rotation_target(
            tc.RotationTarget(
                model="notifications.Notification",
                field="message",
                purpose="m",
                tenant="recipient_id",
                context="id",
            )
        )
        n = Notification.objects.create(
            recipient=user, notif_type="badge", title="t", message="x", meta={}
        )
        Notification.objects.filter(pk=n.pk).update(
            message=tc.encrypt(user.id, "m", "bound", context=str(n.pk))
        )
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        assert tc.rotate_target(target)["rotated"] == 1
        assert tc.decrypt(user.id, "m", stored(n.pk), context=str(n.pk)) == "bound"

    def test_the_tenant_can_come_from_a_function(
        self, seeded, settings, two_keys_primary_k2
    ):
        rows, _, _ = seeded
        target = tc.RotationTarget(
            model="notifications.Notification",
            field="message",
            purpose="notification.message",
            tenant=lambda row: row.recipient_id,
        )
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        assert tc.rotate_target(target)["rotated"] == len(rows)

    def test_hooks_are_told_and_a_broken_hook_does_not_stop_the_run(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        calls = []
        tc.register_rotation_hook(
            lambda t, s: (_ for _ in ()).throw(RuntimeError("hook bug"))
        )
        tc.register_rotation_hook(lambda t, s: calls.append((t.field, s["rotated"])))
        self.switch(settings)
        tc.rotate_target(target)
        assert calls == [("message", len(seeded[0]))]

    def test_registering_the_same_column_twice_keeps_one(self, target):
        tc.register_rotation_target(
            tc.RotationTarget(
                model=target.model,
                field=target.field,
                purpose="other",
                tenant="recipient_id",
            )
        )
        assert [t.purpose for t in tc.rotation_targets()] == ["other"]

    def test_a_broken_key_configuration_is_one_clear_error(
        self, seeded, target, settings
    ):
        settings.TENANT_ENCRYPTION_KEYS = ""
        with pytest.raises(tc.CryptoConfigurationError):
            tc.rotate_target(target)


@pytest.mark.django_db
class TestRotationCommand:
    def run(self, *args):
        out = StringIO()
        call_command("rotate_tenant_encryption", *args, stdout=out)
        return out.getvalue()

    def test_nothing_registered_nothing_to_do(self):
        assert "nothing to rotate" in self.run()

    def test_it_rotates_and_reports(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        text = self.run("--batch-size", "3")
        assert "Primary key: k2" in text and "rotated 12" in text
        assert all(tc.key_id_of(stored(pk)) == "k2" for pk in seeded[0])
        assert "already current 12" in self.run()

    def test_a_dry_run_says_what_it_would_do(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        assert "would rotate 12" in self.run("--dry-run")
        assert all(tc.key_id_of(stored(pk)) == "k1" for pk in seeded[0])

    def test_one_column_or_one_tenant(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        assert "nothing to rotate" in self.run(
            "--target", "notifications.Notification.other"
        )
        text = self.run("--tenant", str(seeded[1].id))
        assert "rotated 6" in text

    def test_undecryptable_rows_make_it_fail_loudly(
        self, seeded, target, settings, two_keys_primary_k2
    ):
        pk = next(iter(seeded[0]))
        Notification.objects.filter(pk=pk).update(
            message="tenc1:k1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        settings.TENANT_ENCRYPTION_PRIMARY_KEY = "k2"
        with pytest.raises(CommandError) as info:
            self.run()
        assert "could not be decrypted" in str(info.value)

    def test_a_missing_configuration_stops_it_at_once(self, settings, target):
        settings.TENANT_ENCRYPTION_KEYS = ""
        with pytest.raises(tc.CryptoConfigurationError):
            self.run()
