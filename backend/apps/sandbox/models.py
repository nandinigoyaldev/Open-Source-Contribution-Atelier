import uuid

from django.conf import settings
from django.db import models


class SandboxExecutionLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sandbox_execution_logs",
        help_text="The user who attempted the command.",
    )
    command = models.TextField(help_text="The command the user attempted to execute.")
    accepted = models.BooleanField(help_text="Whether the command was accepted.")
    feedback = models.TextField(blank=True, help_text="Feedback returned to the user.")
    score_delta = models.IntegerField(
        help_text="Score change resulting from this attempt."
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the attempt was made."
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        username = self.user.get_username() if self.user else "Anonymous"
        cmd_preview = (
            (self.command[:47] + "...") if len(self.command) > 50 else self.command
        )
        return (
            f"[{'Accepted' if self.accepted else 'Rejected'}] {username}: {cmd_preview}"
        )


class ExecutionViolationLog(models.Model):
    class ViolationType(models.TextChoices):
        MEMORY = "memory", "Memory Limit Exceeded"
        TIMEOUT = "timeout", "Execution Timeout"
        SECURITY = "security", "AST Security Violation"
        CONCURRENCY = "concurrency", "Concurrency Limit Exceeded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_violations",
    )
    user_identifier = models.CharField(
        max_length=255, help_text="Fallback for anonymous users (e.g., channel name)"
    )
    code_snippet = models.TextField()
    violation_type = models.CharField(max_length=20, choices=ViolationType.choices)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.violation_type} by {self.user_identifier or self.user} at {self.timestamp}"


class CollabSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "sandbox.Project",
        on_delete=models.CASCADE,
        related_name="collab_sessions",
        null=True,
        blank=True,
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="allowed_collab_sessions",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    document_state = models.BinaryField(
        blank=True, null=True, help_text="Yjs binary document state"
    )

    def __str__(self):
        return f"Session {self.id} (Active: {self.is_active})"


class CollabSessionLog(models.Model):
    session = models.ForeignKey(
        CollabSession, on_delete=models.CASCADE, related_name="logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField(max_length=50, help_text="e.g., joined, left, modified")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        username = self.user.get_username() if self.user else "Anonymous"
        return (
            f"{username} {self.action} session {self.session_id} at {self.created_at}"
        )


class CodeSnapshot(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="code_snapshots",
        help_text="The user who created this snapshot.",
    )
    code = models.TextField(help_text="The snapshot code content.")
    timestamp = models.DateTimeField(
        auto_now_add=True, help_text="When the snapshot was created."
    )
    label = models.CharField(
        max_length=255, blank=True, help_text="Optional label/bookmark name."
    )
    is_auto = models.BooleanField(
        default=True, help_text="Whether this was an auto-save."
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Snapshot by {self.user} at {self.timestamp}"


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sandbox_projects",
        help_text="The user who owns this project.",
    )
    name = models.CharField(max_length=255, help_text="The name of the project.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Project {self.name} by {self.user}"


class ProjectFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="files",
        help_text="The project this file belongs to.",
    )
    path = models.CharField(
        max_length=1024,
        help_text="The full file path within the project (e.g., src/index.js).",
    )
    content = models.TextField(blank=True, help_text="The code content of the file.")
    language = models.CharField(
        max_length=50, default="javascript", help_text="The language of the file."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["path"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "path"], name="unique_project_file_path"
            )
        ]

    def __str__(self):
        return f"{self.path} ({self.project.name})"


class CodeExecutionTrace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="execution_traces",
        help_text="The user who ran this code.",
        null=True,
        blank=True,
    )
    code = models.TextField(help_text="The code that was traced.")
    trace_events = models.JSONField(help_text="Array of trace event snapshots.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        username = self.user.get_username() if self.user else "Anonymous"
        return f"Trace by {username} at {self.created_at}"


class CodeReviewThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CollabSession,
        on_delete=models.CASCADE,
        related_name="review_threads",
        help_text="The collaboration session this thread belongs to.",
    )
    line_number = models.IntegerField(
        help_text="The line number where this comment thread was started."
    )
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["line_number", "created_at"]

    def __str__(self):
        return f"Thread {self.id} on line {self.line_number} (Resolved: {self.is_resolved})"


class CodeReviewComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        CodeReviewThread, on_delete=models.CASCADE, related_name="comments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text="The author of this comment.",
    )
    content = models.TextField(help_text="The comment text.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user} at {self.created_at}"


class SnippetCollection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="snippet_collections",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class CodeSnippet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="snippets"
    )
    collection = models.ForeignKey(
        SnippetCollection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snippets",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    code = models.TextField()
    language = models.CharField(max_length=50, default="python")
    is_favorite = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class TerminalSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="terminal_sessions",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="terminal_sessions",
    )
    name = models.CharField(max_length=255, default="Terminal")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class BulkReplaceOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="bulk_operations"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    previous_state = models.JSONField(
        help_text="Mapping of file_id to their original code content"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Bulk Replace in {self.project.name} by {self.user} at {self.created_at}"
        )


class WorkspaceSnapshot(models.Model):
    """
    A saved, shareable snapshot of a project's full file tree at a point in
    time. Fields match migration 0009_workspacesnapshot_snapshotfile.py,
    which created these tables before the corresponding model/view code
    landed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="snapshots",
        help_text="The project this snapshot was taken from.",
    )
    name = models.CharField(max_length=255, help_text="Name of the snapshot")
    description = models.TextField(
        blank=True, help_text="Optional description of the snapshot"
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        help_text="Store editor layout, execution settings, etc.",
    )
    is_public = models.BooleanField(
        default=False, help_text="Whether this snapshot can be forked by anyone"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Snapshot '{self.name}' of {self.project.name}"


class SnapshotFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        WorkspaceSnapshot,
        on_delete=models.CASCADE,
        related_name="files",
        help_text="The snapshot this file belongs to.",
    )
    path = models.CharField(
        max_length=1024,
        help_text="The full file path within the snapshot (e.g., src/index.js).",
    )
    content = models.TextField(blank=True, help_text="The code content of the file.")
    language = models.CharField(
        max_length=50, default="javascript", help_text="The language of the file."
    )

    class Meta:
        ordering = ["path"]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "path"], name="unique_snapshot_file_path"
            )
        ]

    def __str__(self):
        return f"{self.path} ({self.snapshot.name})"


class MaintainerScenario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    original_code = models.TextField(help_text="The baseline code.")
    flawed_code = models.TextField(help_text="The code with bugs/flaws.")
    diff_content = models.TextField(help_text="The unified diff content.")
    required_findings = models.JSONField(help_text="List of dicts: {'line': 42, 'bug_type': 'security'}")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class MaintainerEvaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(MaintainerScenario, on_delete=models.CASCADE, related_name="evaluations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    submitted_comments = models.JSONField(help_text="The comments submitted by the user.")
    score = models.IntegerField(default=0)
    passed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.scenario.title} ({self.passed})"


# ============================================================
# CI/CD PIPELINE SIMULATOR
# ============================================================


class PipelineExecution(models.Model):
    """Represents a simulated CI/CD pipeline run triggered from the sandbox."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        IN_PROGRESS = "in_progress", "In Progress"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pipeline_executions",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pipeline_executions",
        help_text="The project this pipeline was triggered from.",
    )
    trigger_command = models.CharField(
        max_length=512,
        blank=True,
        help_text="The sandbox command that triggered this pipeline.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
# MERGE CONFLICT ARENA
# ============================================================


class ConflictScenario(models.Model):
    """A pre-configured merge conflict scenario for the Conflict Arena."""

    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(help_text="What the user needs to accomplish.")
    language = models.CharField(max_length=50, default="python")
    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER
    )
    base_code = models.TextField(help_text="The common ancestor (base) code.")
    current_code = models.TextField(
        help_text="The current branch version (HEAD) of the file."
    )
    incoming_code = models.TextField(
        help_text="The incoming branch version of the file."
    )
    expected_resolution = models.TextField(
        help_text="The correct/expected resolved file content."
    )
    hint = models.TextField(
        blank=True, help_text="Optional hint shown to struggling users."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["difficulty", "-created_at"]

    def __str__(self):
        return f"[{self.difficulty}] {self.title}"


class ConflictAttempt(models.Model):
    """Records a user's attempt at resolving a ConflictScenario."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(
        ConflictScenario,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conflict_attempts",
    )
    submitted_code = models.TextField(
        help_text="The user's final submitted merged file."
    )
    passed = models.BooleanField(
        default=False,
        help_text="Whether the submitted code matched the expected resolution.",
    )
    error_message = models.TextField(
        blank=True, help_text="Reason for failure (e.g., unresolved markers)."
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PipelineJob(models.Model):
    """Represents a single stage within a PipelineExecution (e.g., Lint, Test, Audit)."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        IN_PROGRESS = "in_progress", "In Progress"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    class JobType(models.TextChoices):
        LINT = "lint", "Linting"
        TEST = "test", "Unit Tests"
        SECURITY = "security", "Security Audit"
        BUILD = "build", "Build"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(
        PipelineExecution,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED
    )
    log_output = models.TextField(
        blank=True, help_text="Simulated console log output for this job."
    )
    duration_seconds = models.FloatField(
        null=True, blank=True, help_text="How long this job took in seconds."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.job_type} job in pipeline {self.pipeline_id} [{self.status}]"
