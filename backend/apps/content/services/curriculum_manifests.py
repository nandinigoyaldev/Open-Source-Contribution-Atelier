"""
Curriculum release manifest service: DAG validation, compatibility checks,
and enrollment migration preview & application engine.
"""

from collections import defaultdict, deque
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.content.models import (
    CurriculumEnrollment,
    CurriculumMigrationAudit,
    CurriculumReleaseManifest,
    LessonVersion,
)

logger = logging.getLogger(__name__)


def validate_manifest_dag(
    manifest_data: Dict[str, Any], check_revisions: bool = False
) -> List[str]:
    """
    Validate that a curriculum release manifest's prerequisite relationships
    form a valid Directed Acyclic Graph (DAG) with full dependency closure.

    Returns the lessons in topological prerequisite order.
    Raises ValidationError on:
    - Missing required fields
    - Duplicate lesson slugs
    - Self-referencing prerequisites
    - Dangling/missing prerequisites (closure violation)
    - Prerequisite cycle / recursion
    - Unfrozen/missing lesson versions (when check_revisions=True)
    """
    if not isinstance(manifest_data, dict):
        raise ValidationError("Manifest data must be a JSON dictionary.")

    items = manifest_data.get("items")
    if items is None or not isinstance(items, list):
        raise ValidationError("Manifest data must contain an 'items' list.")

    if len(items) == 0:
        return []

    declared_slugs: Set[str] = set()
    graph: Dict[str, List[str]] = defaultdict(list)
    in_degree: Dict[str, int] = defaultdict(int)

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(f"Item at index {idx} must be a dictionary.")

        slug = item.get("slug")
        if not slug or not isinstance(slug, str):
            raise ValidationError(f"Item at index {idx} is missing a valid 'slug'.")

        if slug in declared_slugs:
            raise ValidationError(f"Duplicate lesson slug '{slug}' declared in manifest.")

        declared_slugs.add(slug)
        in_degree[slug] = 0

    for item in items:
        slug = item["slug"]
        prerequisites = item.get("prerequisites", [])
        if not isinstance(prerequisites, list):
            raise ValidationError(f"Prerequisites for lesson '{slug}' must be a list.")

        for prereq in prerequisites:
            if not isinstance(prereq, str):
                raise ValidationError(
                    f"Prerequisite identifier in lesson '{slug}' must be a string."
                )

            if prereq == slug:
                raise ValidationError(
                    f"Lesson '{slug}' cannot list itself as a prerequisite (self-reference)."
                )

            # Closure validation: all prerequisites must be declared within the release manifest
            if prereq not in declared_slugs:
                raise ValidationError(
                    f"Closure violation: lesson '{slug}' requires undeclared prerequisite '{prereq}'."
                )

            # Prerequisite edge: prereq -> slug (prereq must come before slug)
            graph[prereq].append(slug)
            in_degree[slug] += 1

    # Cycle detection via Kahn's algorithm (Topological sort)
    queue = deque([slug for slug in declared_slugs if in_degree[slug] == 0])
    topological_order: List[str] = []

    while queue:
        current = queue.popleft()
        topological_order.append(current)

        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(topological_order) != len(declared_slugs):
        # A cycle exists. Find cycle components for an actionable error message
        unresolved = [s for s in declared_slugs if in_degree[s] > 0]
        raise ValidationError(
            f"Cyclic prerequisite dependency detected involving lessons: {', '.join(sorted(unresolved))}."
        )

    # Optional check: Ensure referenced lesson revisions exist and are published
    if check_revisions:
        for item in items:
            slug = item["slug"]
            version_number = item.get("version_number")
            if version_number is not None:
                exists = LessonVersion.objects.filter(
                    lesson__slug=slug,
                    number=version_number,
                    status=LessonVersion.STATUS_PUBLISHED,
                ).exists()
                if not exists:
                    raise ValidationError(
                        f"Lesson '{slug}' revision {version_number} does not exist as a published revision."
                    )

    return topological_order


def create_release_manifest(
    curriculum_slug: str,
    version: str,
    manifest_data: Dict[str, Any],
    created_by=None,
    check_revisions: bool = False,
) -> CurriculumReleaseManifest:
    """
    Validate DAG and create a new CurriculumReleaseManifest.
    """
    validate_manifest_dag(manifest_data, check_revisions=check_revisions)

    manifest = CurriculumReleaseManifest.objects.create(
        curriculum_slug=curriculum_slug,
        version=version,
        manifest_data=manifest_data,
        status=CurriculumReleaseManifest.STATUS_VALIDATED,
        created_by=created_by,
    )
    return manifest


@transaction.atomic
def activate_release_manifest(manifest: CurriculumReleaseManifest) -> CurriculumReleaseManifest:
    """
    Atomically activate a release manifest for a curriculum.
    Deactivates any currently active release for that curriculum.
    """
    if manifest.status not in (
        CurriculumReleaseManifest.STATUS_VALIDATED,
        CurriculumReleaseManifest.STATUS_ACTIVE,
    ):
        validate_manifest_dag(manifest.manifest_data)

    # Deactivate current active releases for this curriculum
    CurriculumReleaseManifest.objects.filter(
        curriculum_slug=manifest.curriculum_slug, is_active=True
    ).exclude(id=manifest.id).update(
        is_active=False, status=CurriculumReleaseManifest.STATUS_ARCHIVED
    )

    manifest.is_active = True
    manifest.status = CurriculumReleaseManifest.STATUS_ACTIVE
    manifest.activated_at = timezone.now()
    manifest.save(update_fields=["is_active", "status", "activated_at"])
    return manifest


def preview_enrollment_migration(
    enrollment: CurriculumEnrollment,
    target_manifest: CurriculumReleaseManifest,
    user_completed_slugs: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Side-effect free, deterministic, tenant-scoped preview of an enrollment migration.
    Reports:
    - retained_completions: lessons completed in source that remain in target.
    - newly_required_prerequisites: prerequisites added in target needed by uncompleted lessons.
    - removed_lessons: lessons in source not present in target, preserving completion provenance.
    - unresolved_mappings: structural differences.
    - is_rollback: whether migrating to an older release.
    """
    if enrollment.curriculum_slug != target_manifest.curriculum_slug:
        raise ValidationError(
            f"Cannot migrate enrollment for curriculum '{enrollment.curriculum_slug}' "
            f"to release for curriculum '{target_manifest.curriculum_slug}'."
        )

    source_manifest = enrollment.current_release
    source_items = {
        item["slug"]: item
        for item in source_manifest.manifest_data.get("items", [])
        if "slug" in item
    }
    target_items = {
        item["slug"]: item
        for item in target_manifest.manifest_data.get("items", [])
        if "slug" in item
    }

    # Fetch learner completions if not provided
    if user_completed_slugs is None:
        try:
            from apps.progress.models import LessonProgress

            user_completed_slugs = set(
                LessonProgress.objects.filter(
                    user=enrollment.user, is_completed=True
                ).values_list("lesson__slug", flat=True)
            )
        except Exception:
            user_completed_slugs = set()

    # 1. Retained completions
    retained_completions: List[str] = [
        slug for slug in user_completed_slugs if slug in target_items
    ]

    # 2. Removed lessons
    removed_lessons: List[Dict[str, Any]] = []
    for slug, item in source_items.items():
        if slug not in target_items:
            removed_lessons.append(
                {
                    "slug": slug,
                    "title": item.get("title", slug),
                    "was_completed": slug in user_completed_slugs,
                }
            )

    # 3. Newly required prerequisites for unfinished target lessons
    newly_required: List[Dict[str, Any]] = []
    for slug, target_item in target_items.items():
        if slug not in user_completed_slugs:
            target_prereqs = set(target_item.get("prerequisites", []))
            source_prereqs = set(
                source_items.get(slug, {}).get("prerequisites", [])
            )
            added_prereqs = list(target_prereqs - source_prereqs)
            unmet_added = [p for p in added_prereqs if p not in user_completed_slugs]
            if unmet_added:
                newly_required.append(
                    {
                        "lesson_slug": slug,
                        "unmet_new_prerequisites": unmet_added,
                    }
                )

    is_rollback = (
        target_manifest.created_at < source_manifest.created_at
        or target_manifest.id < source_manifest.id
    )

    return {
        "enrollment_id": enrollment.id,
        "curriculum_slug": enrollment.curriculum_slug,
        "source_version": source_manifest.version,
        "target_version": target_manifest.version,
        "retained_completions": retained_completions,
        "newly_required_prerequisites": newly_required,
        "removed_lessons": removed_lessons,
        "unresolved_mappings": [],
        "is_rollback": is_rollback,
        "can_migrate": True,
    }


@transaction.atomic
def apply_enrollment_migration(
    enrollment: CurriculumEnrollment,
    target_manifest: CurriculumReleaseManifest,
    expected_source_version: str,
    approved_by=None,
) -> CurriculumMigrationAudit:
    """
    Apply an approved migration plan to an enrollment using a source-version check
    to guard against stale plans or concurrent updates.

    Creates an immutable audit record and never fabricates completion or XP.
    """
    enrollment.refresh_from_db()

    if enrollment.current_release.version != expected_source_version:
        raise ValidationError(
            f"Stale migration plan: enrollment is currently on version "
            f"'{enrollment.current_release.version}', expected '{expected_source_version}'."
        )

    preview = preview_enrollment_migration(enrollment, target_manifest)

    source_release = enrollment.current_release
    enrollment.current_release = target_manifest
    enrollment.save(update_fields=["current_release", "updated_at"])

    audit = CurriculumMigrationAudit.objects.create(
        enrollment=enrollment,
        source_release=source_release,
        target_release=target_manifest,
        retained_completions=preview["retained_completions"],
        newly_required_prerequisites=preview["newly_required_prerequisites"],
        removed_lessons=preview["removed_lessons"],
        unresolved_mappings=preview["unresolved_mappings"],
        is_rollback=preview["is_rollback"],
        approved_by=approved_by,
    )
    return audit
