# Frontend CI concurrency

Workflows that build or validate the frontend use a concurrency group containing the workflow name and the pull request number. When a contributor pushes a newer commit to the same pull request, GitHub cancels the older run of that workflow. Different pull requests and different workflows keep their own groups, so one contributor does not cancel another contributor's checks.

Cancellation is enabled only for `pull_request` events. Other events use their unique run ID in the group because GitHub replaces an older pending run when a group is full, even if `cancel-in-progress` is false. This preserves every `main` push, scheduled audit and manual run. Job names and required check names are unchanged, so branch protection still evaluates the current pull request head.

This applies to Accessibility Checks, Performance Budget, API Types Freshness, Verify Source Maps, and Security Audit. Frontend Unit Tests and Quality Gates already had pull request concurrency groups. To verify a change, push twice to the same pull request and check that only the newest run completes; then confirm a separate pull request's checks and a `main` push still run normally.
