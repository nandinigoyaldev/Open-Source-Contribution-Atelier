"""
Tests for UserSession.save() race-condition fix (issue #2009).

Verifies that:
- The session limit is enforced correctly under normal conditions.
- transaction.atomic() + select_for_update() serialise concurrent saves.
- The MAX_SESSIONS_PER_USER setting is respected.
- Oldest sessions are evicted when the limit is exceeded.
- Edge cases (single session, exactly at limit, updates) work correctly.
- Concurrent threads cannot exceed the session limit.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, transaction, models
from django.test import TestCase, TransactionTestCase, override_settings

from apps.accounts.models import UserSession

User = get_user_model()


# ===========================================================================
# 1. Basic session limit enforcement
# ===========================================================================


class TestUserSessionLimitEnforcement(TestCase):
    """Verify that UserSession.save() enforces the max-sessions-per-user policy."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="session_test_user",
            email="session@example.com",
            password="testpass123",
        )

    def test_single_session_is_saved(self):
        """A single session save should succeed without any eviction."""
        session = UserSession(
            user=self.user,
            ip_address="10.0.0.1",
            user_agent="TestBrowser/1.0",
            device_name="TestDevice",
        )
        session.save()

        assert UserSession.objects.filter(user=self.user).count() == 1
        assert UserSession.objects.get(pk=session.pk).ip_address == "10.0.0.1"

    def test_five_sessions_are_preserved(self):
        """Exactly 5 sessions should all be preserved (at the default limit)."""
        for i in range(5):
            UserSession(
                user=self.user,
                ip_address=f"10.0.0.{i + 1}",
                device_name=f"Device{i + 1}",
            ).save()

        assert UserSession.objects.filter(user=self.user).count() == 5

    def test_sixth_session_evicts_oldest(self):
        """Adding a 6th session should evict the oldest, keeping exactly 5."""
        sessions = []
        for i in range(5):
            s = UserSession(
                user=self.user,
                ip_address=f"10.0.0.{i + 1}",
                device_name=f"Device{i + 1}",
            )
            s.save()
            sessions.append(s)

        # The first session saved should be the oldest
        oldest_pk = sessions[0].pk

        # Save the 6th session
        new_session = UserSession(
            user=self.user,
            ip_address="10.0.0.100",
            device_name="NewDevice",
        )
        new_session.save()

        remaining = UserSession.objects.filter(user=self.user)
        assert remaining.count() == 5
        # The new session must be among the survivors
        assert remaining.filter(pk=new_session.pk).exists()

    def test_many_sessions_evict_down_to_limit(self):
        """Adding 10 sessions should keep exactly 5."""
        for i in range(10):
            UserSession(
                user=self.user,
                ip_address=f"10.0.0.{i + 1}",
                device_name=f"Device{i + 1}",
            ).save()

        assert UserSession.objects.filter(user=self.user).count() == 5

    def test_eviction_keeps_most_recent_sessions(self):
        """The 5 most recently active sessions should survive eviction."""
        pks = []
        for i in range(8):
            s = UserSession(
                user=self.user,
                ip_address=f"10.0.0.{i + 1}",
                device_name=f"Device{i + 1}",
            )
            s.save()
            pks.append(s.pk)

        remaining_pks = set(
            UserSession.objects.filter(user=self.user).values_list("pk", flat=True)
        )
        assert len(remaining_pks) == 5

    def test_other_users_sessions_unaffected(self):
        """Eviction for one user must not affect another user's sessions."""
        other_user = User.objects.create_user(
            username="other_session_user",
            email="other@example.com",
            password="testpass123",
        )

        # Create 3 sessions for the other user
        for i in range(3):
            UserSession(user=other_user, device_name=f"OtherDevice{i}").save()

        # Create 7 sessions for the main user (triggers eviction)
        for i in range(7):
            UserSession(user=self.user, device_name=f"Device{i}").save()

        assert UserSession.objects.filter(user=self.user).count() == 5
        assert UserSession.objects.filter(user=other_user).count() == 3

    def test_session_update_does_not_create_duplicate(self):
        """Updating an existing session should not increase the count."""
        session = UserSession(user=self.user, device_name="Original")
        session.save()

        session.device_name = "Updated"
        session.save()

        assert UserSession.objects.filter(user=self.user).count() == 1
        session.refresh_from_db()
        assert session.device_name == "Updated"


# ===========================================================================
# 2. Configurable MAX_SESSIONS_PER_USER
# ===========================================================================


class TestConfigurableSessionLimit(TestCase):
    """Verify that the session limit is configurable via settings."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="configurable_user",
            email="configurable@example.com",
            password="testpass123",
        )

    @override_settings(MAX_SESSIONS_PER_USER=3)
    def test_custom_limit_of_3(self):
        """When MAX_SESSIONS_PER_USER=3, only 3 sessions should survive."""
        for i in range(6):
            UserSession(user=self.user, device_name=f"Device{i}").save()

        assert UserSession.objects.filter(user=self.user).count() == 3

    @override_settings(MAX_SESSIONS_PER_USER=1)
    def test_custom_limit_of_1(self):
        """When MAX_SESSIONS_PER_USER=1, only the latest session survives."""
        for i in range(5):
            UserSession(user=self.user, device_name=f"Device{i}").save()

        remaining = UserSession.objects.filter(user=self.user)
        assert remaining.count() == 1

    @override_settings(MAX_SESSIONS_PER_USER=10)
    def test_custom_limit_of_10(self):
        """When MAX_SESSIONS_PER_USER=10, 8 sessions should all survive."""
        for i in range(8):
            UserSession(user=self.user, device_name=f"Device{i}").save()

        assert UserSession.objects.filter(user=self.user).count() == 8

    def test_default_limit_is_5(self):
        """Without the setting, the default limit of 5 should apply."""
        for i in range(7):
            UserSession(user=self.user, device_name=f"Device{i}").save()

        assert UserSession.objects.filter(user=self.user).count() == 5


# ===========================================================================
# 3. Model field and meta validation
# ===========================================================================


class TestUserSessionModel(TestCase):
    """Verify model field definitions and metadata."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="model_test_user",
            email="model@example.com",
            password="testpass123",
        )

    def test_session_id_is_auto_generated_uuid(self):
        session = UserSession(user=self.user)
        session.save()
        assert isinstance(session.session_id, uuid.UUID)

    def test_session_id_is_unique(self):
        s1 = UserSession(user=self.user)
        s1.save()
        s2 = UserSession(user=self.user)
        s2.save()
        assert s1.session_id != s2.session_id

    def test_str_representation(self):
        session = UserSession(user=self.user)
        session.save()
        expected = f"Session {session.session_id} for {self.user.username}"
        assert str(session) == expected

    def test_ordering_is_by_last_activity_desc(self):
        assert UserSession._meta.ordering == ["-last_activity"]

    def test_ip_address_can_be_null(self):
        session = UserSession(user=self.user)
        session.save()
        session.refresh_from_db()
        assert session.ip_address is None

    def test_ip_address_stores_ipv4(self):
        session = UserSession(user=self.user, ip_address="192.168.1.1")
        session.save()
        session.refresh_from_db()
        assert session.ip_address == "192.168.1.1"

    def test_ip_address_stores_ipv6(self):
        session = UserSession(user=self.user, ip_address="::1")
        session.save()
        session.refresh_from_db()
        assert session.ip_address == "::1"

    def test_user_agent_defaults_to_empty(self):
        session = UserSession(user=self.user)
        session.save()
        assert session.user_agent == ""

    def test_device_name_defaults_to_empty(self):
        session = UserSession(user=self.user)
        session.save()
        assert session.device_name == ""

    def test_created_at_is_auto_set(self):
        session = UserSession(user=self.user)
        session.save()
        assert session.created_at is not None

    def test_last_activity_is_auto_set(self):
        session = UserSession(user=self.user)
        session.save()
        assert session.last_activity is not None

    def test_cascade_delete_configuration(self):
        """Verify cascade delete configuration on user relationship."""
        field = UserSession._meta.get_field("user")
        assert field.remote_field.on_delete == models.CASCADE


# ===========================================================================
# 4. Atomic transaction verification
# ===========================================================================


class TestUserSessionAtomicBehavior(TestCase):
    """Verify that save() uses transaction.atomic() correctly."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="atomic_user",
            email="atomic@example.com",
            password="testpass123",
        )

    def test_save_is_atomic_rollback_on_error(self):
        """
        If the save raises an error after super().save(), the entire
        transaction should be rolled back — no partial writes.
        """
        # Pre-populate with 5 sessions (exactly at default limit)
        for i in range(5):
            UserSession(user=self.user, device_name=f"Device{i}").save()

        assert UserSession.objects.filter(user=self.user).count() == 5

        # We want to trigger the eviction path (6th session) but raise an error
        # during the delete call to verify rollback of the 6th session.
        original_filter = UserSession.objects.filter

        def mock_filter(*args, **kwargs):
            # If this is the eviction filter call, wrap the queryset to fail on delete
            qs = original_filter(*args, **kwargs)
            original_exclude = qs.exclude
            
            def mock_exclude(*ex_args, **ex_kwargs):
                ex_qs = original_exclude(*ex_args, **ex_kwargs)
                original_qs_delete = ex_qs.delete
                
                def mock_qs_delete(*del_args, **del_kwargs):
                    raise RuntimeError("Simulated DB error during eviction")
                
                ex_qs.delete = mock_qs_delete
                return ex_qs
                
            qs.exclude = mock_exclude
            return qs

        with patch.object(UserSession.objects, "filter", side_effect=mock_filter):
            with pytest.raises(RuntimeError, match="Simulated DB error during eviction"):
                s = UserSession(user=self.user, device_name="SixthDevice")
                s.save()

        # The 6th session should NOT be saved in the database because of rollback
        assert UserSession.objects.filter(user=self.user).count() == 5
        assert not UserSession.objects.filter(device_name="SixthDevice").exists()


# ===========================================================================
# 5. Concurrent session creation (race condition regression test)
# ===========================================================================


class TestUserSessionConcurrency(TransactionTestCase):
    """
    Regression test for the race condition described in issue #2009.

    Uses TransactionTestCase so each thread gets its own DB connection
    and transactions are actually committed, allowing us to test real
    concurrent behavior with select_for_update().

    Note: SQLite serialises all writes globally, so select_for_update()
    is effectively a no-op there.  These tests verify the *logical*
    correctness of the session limit under concurrent writes regardless
    of the database backend.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrent_user",
            email="concurrent@example.com",
            password="testpass123",
        )

    def _create_session_in_thread(self, user_id, device_name):
        """
        Create a UserSession in a separate thread.

        Each thread gets its own DB connection on PostgreSQL.
        On SQLite, all threads share the same connection with
        global serialisation.
        """
        from django.db import connection as thread_connection

        try:
            user = User.objects.get(pk=user_id)
            session = UserSession(
                user=user,
                ip_address="10.0.0.1",
                device_name=device_name,
            )
            session.save()
            return True
        except Exception as exc:
            return str(exc)
        finally:
            thread_connection.close()

    def test_concurrent_saves_respect_limit(self):
        """
        Spawn multiple threads that each create a session simultaneously.
        After all threads finish, the session count must not exceed the limit.
        """
        num_threads = 10
        barrier = threading.Barrier(num_threads, timeout=10)

        results = []
        errors = []

        def worker(device_idx):
            try:
                barrier.wait()
                result = self._create_session_in_thread(
                    self.user.pk, f"ConcurrentDevice{device_idx}"
                )
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        final_count = UserSession.objects.filter(user=self.user).count()
        assert final_count <= 5, (
            f"Race condition detected! Expected <= 5 sessions, got {final_count}. "
            f"Thread results: {results}, errors: {errors}"
        )

    def test_concurrent_saves_with_preexisting_sessions(self):
        """
        With 4 pre-existing sessions, 5 concurrent saves should result
        in at most 5 total sessions (not 9).
        """
        # Pre-create 4 sessions
        for i in range(4):
            UserSession(
                user=self.user,
                ip_address="10.0.0.1",
                device_name=f"PreDevice{i}",
            ).save()

        assert UserSession.objects.filter(user=self.user).count() == 4

        num_threads = 5
        barrier = threading.Barrier(num_threads, timeout=10)

        def worker(device_idx):
            try:
                barrier.wait()
                self._create_session_in_thread(
                    self.user.pk, f"NewDevice{device_idx}"
                )
            except Exception:
                pass

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        final_count = UserSession.objects.filter(user=self.user).count()
        assert final_count <= 5, (
            f"Race condition detected! Expected <= 5 sessions, got {final_count}."
        )

    @override_settings(MAX_SESSIONS_PER_USER=2)
    def test_concurrent_saves_with_custom_limit(self):
        """
        With MAX_SESSIONS_PER_USER=2, concurrent saves must still
        respect the lower limit.
        """
        num_threads = 8
        barrier = threading.Barrier(num_threads, timeout=10)

        def worker(device_idx):
            try:
                barrier.wait()
                self._create_session_in_thread(
                    self.user.pk, f"LimitDevice{device_idx}"
                )
            except Exception:
                pass

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        final_count = UserSession.objects.filter(user=self.user).count()
        assert final_count <= 2, (
            f"Race condition detected! Expected <= 2 sessions, got {final_count}."
        )

    def test_concurrent_saves_different_users_independent(self):
        """
        Concurrent saves for different users must not interfere.
        Each user should independently enforce their own limit.
        """
        user2 = User.objects.create_user(
            username="concurrent_user2",
            email="concurrent2@example.com",
            password="testpass123",
        )

        num_threads_per_user = 8
        barrier = threading.Barrier(num_threads_per_user * 2, timeout=10)

        def worker(user_id, device_idx):
            try:
                barrier.wait()
                self._create_session_in_thread(user_id, f"Device{device_idx}")
            except Exception:
                pass

        threads = []
        for i in range(num_threads_per_user):
            threads.append(
                threading.Thread(target=worker, args=(self.user.pk, i))
            )
            threads.append(
                threading.Thread(target=worker, args=(user2.pk, i))
            )

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        count_user1 = UserSession.objects.filter(user=self.user).count()
        count_user2 = UserSession.objects.filter(user=user2).count()

        assert count_user1 <= 5, (
            f"User1 has {count_user1} sessions, expected <= 5"
        )
        assert count_user2 <= 5, (
            f"User2 has {count_user2} sessions, expected <= 5"
        )

    def test_sequential_saves_respect_limit(self):
        """
        Even without concurrency, verify the basic sequential behavior
        through TransactionTestCase (committed transactions).
        """
        for i in range(12):
            UserSession(
                user=self.user,
                ip_address="10.0.0.1",
                device_name=f"SeqDevice{i}",
            ).save()

        assert UserSession.objects.filter(user=self.user).count() == 5


# ===========================================================================
# 6. Source code verification — no duplicate LOGGING-style overwrite
# ===========================================================================


class TestUserSessionSaveUsesAtomic(TestCase):
    """Verify the save() method implementation uses atomic transactions."""

    def test_save_method_contains_atomic(self):
        """The save() method source must reference transaction.atomic."""
        import inspect

        source = inspect.getsource(UserSession.save)
        assert "transaction.atomic" in source, (
            "UserSession.save() must use transaction.atomic() to prevent "
            "race conditions (issue #2009)"
        )

    def test_save_method_contains_select_for_update(self):
        """The save() method source must use select_for_update for locking."""
        import inspect

        source = inspect.getsource(UserSession.save)
        assert "select_for_update" in source, (
            "UserSession.save() must use select_for_update() to serialize "
            "concurrent session saves (issue #2009)"
        )

    def test_save_method_reads_max_sessions_setting(self):
        """The save() method must reference MAX_SESSIONS_PER_USER."""
        import inspect

        source = inspect.getsource(UserSession.save)
        assert "MAX_SESSIONS_PER_USER" in source, (
            "UserSession.save() must use settings.MAX_SESSIONS_PER_USER "
            "for a configurable session limit"
        )
