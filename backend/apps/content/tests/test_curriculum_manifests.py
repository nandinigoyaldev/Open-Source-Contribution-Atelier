from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.content.models import (
    CurriculumEnrollment,
    CurriculumMigrationAudit,
    CurriculumReleaseManifest,
)
from apps.content.services.curriculum_manifests import (
    activate_release_manifest,
    apply_enrollment_migration,
    create_release_manifest,
    preview_enrollment_migration,
    validate_manifest_dag,
)

User = get_user_model()


class CurriculumManifestDAGValidationTest(TestCase):
    def test_valid_dag_topological_sort(self):
        manifest_data = {
            "items": [
                {"slug": "intro", "order": 1, "prerequisites": []},
                {"slug": "git-basics", "order": 2, "prerequisites": ["intro"]},
                {"slug": "branching", "order": 3, "prerequisites": ["git-basics"]},
                {"slug": "rebasing", "order": 4, "prerequisites": ["branching"]},
            ]
        }
        order = validate_manifest_dag(manifest_data)
        self.assertEqual(order, ["intro", "git-basics", "branching", "rebasing"])

    def test_branching_dag(self):
        manifest_data = {
            "items": [
                {"slug": "a", "prerequisites": []},
                {"slug": "b1", "prerequisites": ["a"]},
                {"slug": "b2", "prerequisites": ["a"]},
                {"slug": "c", "prerequisites": ["b1", "b2"]},
            ]
        }
        order = validate_manifest_dag(manifest_data)
        self.assertIn("a", order)
        self.assertIn("c", order)
        self.assertTrue(order.index("a") < order.index("b1"))
        self.assertTrue(order.index("a") < order.index("b2"))
        self.assertTrue(order.index("b1") < order.index("c"))
        self.assertTrue(order.index("b2") < order.index("c"))

    def test_closure_violation_raises_error(self):
        """Manifest is rejected if any prerequisite is not declared within the release."""
        manifest_data = {
            "items": [
                {"slug": "advanced-git", "prerequisites": ["undeclared-intro"]},
            ]
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_manifest_dag(manifest_data)
        self.assertIn("Closure violation", str(ctx.exception))
        self.assertIn("undeclared-intro", str(ctx.exception))

    def test_cycle_detection_simple(self):
        """Manifest is rejected if circular dependency A -> B -> A exists."""
        manifest_data = {
            "items": [
                {"slug": "a", "prerequisites": ["b"]},
                {"slug": "b", "prerequisites": ["a"]},
            ]
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_manifest_dag(manifest_data)
        self.assertIn("Cyclic prerequisite dependency", str(ctx.exception))

    def test_cycle_detection_multihop(self):
        """Manifest is rejected on multi-hop cycle A -> B -> C -> A."""
        manifest_data = {
            "items": [
                {"slug": "a", "prerequisites": ["c"]},
                {"slug": "b", "prerequisites": ["a"]},
                {"slug": "c", "prerequisites": ["b"]},
            ]
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_manifest_dag(manifest_data)
        self.assertIn("Cyclic prerequisite dependency", str(ctx.exception))

    def test_self_prerequisite_rejected(self):
        """Lesson cannot list itself as a prerequisite."""
        manifest_data = {
            "items": [
                {"slug": "self-loop", "prerequisites": ["self-loop"]},
            ]
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_manifest_dag(manifest_data)
        self.assertIn("cannot list itself", str(ctx.exception))

    def test_duplicate_slug_rejected(self):
        manifest_data = {
            "items": [
                {"slug": "intro", "prerequisites": []},
                {"slug": "intro", "prerequisites": []},
            ]
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_manifest_dag(manifest_data)
        self.assertIn("Duplicate lesson slug", str(ctx.exception))


class CurriculumReleaseAndMigrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="learner_alice", email="alice@example.com", password="pass"
        )
        self.admin = User.objects.create_user(
            username="curriculum_admin", email="admin@example.com", password="pass"
        )

        # Release V1 (initial curriculum)
        self.v1_data = {
            "items": [
                {"slug": "lesson-1", "title": "Lesson 1", "prerequisites": []},
                {"slug": "lesson-2", "title": "Lesson 2", "prerequisites": ["lesson-1"]},
                {"slug": "lesson-deprecated", "title": "Old Deprecated Lesson", "prerequisites": ["lesson-2"]},
            ]
        }
        self.release_v1 = create_release_manifest(
            curriculum_slug="git-fundamentals",
            version="1.0.0",
            manifest_data=self.v1_data,
            created_by=self.admin,
        )
        activate_release_manifest(self.release_v1)

        # Learner enrolled on V1
        self.enrollment = CurriculumEnrollment.objects.create(
            user=self.user,
            curriculum_slug="git-fundamentals",
            current_release=self.release_v1,
        )

        # Release V2 (evolved curriculum: lesson-deprecated removed, lesson-3 added with new prerequisite)
        self.v2_data = {
            "items": [
                {"slug": "lesson-1", "title": "Lesson 1", "prerequisites": []},
                {"slug": "lesson-1-ext", "title": "Lesson 1 Extension", "prerequisites": ["lesson-1"]},
                {"slug": "lesson-2", "title": "Lesson 2", "prerequisites": ["lesson-1", "lesson-1-ext"]},
                {"slug": "lesson-3", "title": "Lesson 3", "prerequisites": ["lesson-2"]},
            ]
        }
        self.release_v2 = create_release_manifest(
            curriculum_slug="git-fundamentals",
            version="2.0.0",
            manifest_data=self.v2_data,
            created_by=self.admin,
        )

    def test_active_release_activation(self):
        """Activating a new release deactivates previous active releases for the curriculum."""
        self.assertTrue(self.release_v1.is_active)
        activate_release_manifest(self.release_v2)

        self.release_v1.refresh_from_db()
        self.release_v2.refresh_from_db()

        self.assertFalse(self.release_v1.is_active)
        self.assertEqual(self.release_v1.status, CurriculumReleaseManifest.STATUS_ARCHIVED)
        self.assertTrue(self.release_v2.is_active)
        self.assertEqual(self.release_v2.status, CurriculumReleaseManifest.STATUS_ACTIVE)

        # Existing enrollment stays locked to V1 until explicitly migrated
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.current_release.version, "1.0.0")

    def test_migration_preview_deterministic_and_side_effect_free(self):
        """Preview correctly reports retained completions, removed lessons, and new prerequisites."""
        user_completions = {"lesson-1", "lesson-deprecated"}

        preview = preview_enrollment_migration(
            enrollment=self.enrollment,
            target_manifest=self.release_v2,
            user_completed_slugs=user_completions,
        )

        self.assertEqual(preview["source_version"], "1.0.0")
        self.assertEqual(preview["target_version"], "2.0.0")
        self.assertFalse(preview["is_rollback"])

        # lesson-1 is in target, so it is retained
        self.assertEqual(preview["retained_completions"], ["lesson-1"])

        # lesson-deprecated was removed from V2
        removed = preview["removed_lessons"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["slug"], "lesson-deprecated")
        self.assertTrue(removed[0]["was_completed"])

        # lesson-2 has new prerequisite lesson-1-ext which user has not finished
        new_prereqs = preview["newly_required_prerequisites"]
        self.assertTrue(any(item["lesson_slug"] == "lesson-2" for item in new_prereqs))

        # Check preview has NO database side-effects
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.current_release.version, "1.0.0")
        self.assertEqual(CurriculumMigrationAudit.objects.count(), 0)

    def test_apply_migration_with_source_version_check(self):
        """Applying approved migration updates enrollment and records audit trail."""
        audit = apply_enrollment_migration(
            enrollment=self.enrollment,
            target_manifest=self.release_v2,
            expected_source_version="1.0.0",
            approved_by=self.admin,
        )

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.current_release.version, "2.0.0")

        # Verify audit record
        self.assertEqual(audit.enrollment, self.enrollment)
        self.assertEqual(audit.source_release.version, "1.0.0")
        self.assertEqual(audit.target_release.version, "2.0.0")
        self.assertEqual(audit.approved_by, self.admin)
        self.assertFalse(audit.is_rollback)

    def test_apply_migration_rejects_stale_source_version(self):
        """Prevents race conditions if enrollment was concurrently migrated."""
        with self.assertRaises(ValidationError) as ctx:
            apply_enrollment_migration(
                enrollment=self.enrollment,
                target_manifest=self.release_v2,
                expected_source_version="0.9.0",  # Stale / wrong expectation
            )
        self.assertIn("Stale migration plan", str(ctx.exception))
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.current_release.version, "1.0.0")

    def test_audited_rollback(self):
        """Rolling back to a previous manifest is recorded as an audited migration and never fabricates XP."""
        # First migrate to V2
        apply_enrollment_migration(
            enrollment=self.enrollment,
            target_manifest=self.release_v2,
            expected_source_version="1.0.0",
            approved_by=self.admin,
        )

        # Now rollback to V1
        rollback_audit = apply_enrollment_migration(
            enrollment=self.enrollment,
            target_manifest=self.release_v1,
            expected_source_version="2.0.0",
            approved_by=self.admin,
        )

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.current_release.version, "1.0.0")
        self.assertTrue(rollback_audit.is_rollback)
        self.assertEqual(rollback_audit.source_release.version, "2.0.0")
        self.assertEqual(rollback_audit.target_release.version, "1.0.0")
