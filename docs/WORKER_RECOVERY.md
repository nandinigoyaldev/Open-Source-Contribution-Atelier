# Notification Worker Recovery Runbook

This runbook explains how maintainers identify a stuck notification worker, inspect safe diagnostics, restart it, verify recovery, and roll back a faulty deployment.

The goal is to restore processing while preserving all queued work.

## 1. Scope and worker identification

The root `docker-compose.yml` defines a `worker` service that runs:

```bash
python manage.py qcluster
```

This is the Django-Q worker.

| Setting | Value | Location |
| --- | --- | --- |
| Task timeout | 90 seconds by default (`Q_TASK_TIMEOUT`) | `backend/config/settings.py` |
| Task retry | Timeout + 30 seconds (120 seconds by default) | `backend/config/settings.py` |
| Worker processes | 4 | `backend/config/settings.py` |
| Container stop grace period | 120 seconds | `docker-compose.yml` |
| Production grace period | 120 seconds | `infra/deploy/docker-compose.prod.yml` |

Redis is optional in the root Compose configuration and belongs to the `redis` and `full` profiles. Django-Q can use Redis when configured and reachable, or use the ORM broker fallback.

**Important:** Do not confuse this Compose Django-Q worker with the separate Celery implementation under `services/notifications_worker`. The commands in this runbook target the root Compose `worker` service only.

## 2. Recognize a potentially stuck worker

Investigate when one or more of these symptoms occur:

- The worker container is stopped, repeatedly restarting, or exits shortly after starting.
- Background notifications or other queued tasks are not progressing.
- Worker logs repeatedly show exceptions or database or broker connection failures.
- The delay between a task being queued and its expected completion keeps increasing.
- A task appears to remain in progress beyond its expected execution time.

A running container does not prove that tasks are being processed. The root Compose worker does not define a dedicated worker health check, so `Up` alone is not evidence of successful task execution.

The configured task timeout is 90 seconds by default. Check recent logs and task context before interrupting in-flight work.

## 3. Capture incident details

Before changing anything, record:

- Incident start time and timezone.
- Environment and deployment revision or image version.
- Worker service state.
- Approximate user or feature impact.
- Relevant task identifiers and timestamps, when available.
- Any recent backend, configuration, database, or infrastructure deployment.

Use task identifiers and sanitized diagnostic details. Do not copy notification bodies, user data, access tokens, passwords, environment files, or secret-bearing configuration into an issue or chat.

## 4. Inspect safe diagnostics

Run these read-only checks from the directory containing the applicable Compose file.

### 4.1 Check container state

```bash
docker compose ps worker
docker compose ps db pgbouncer meilisearch
```

Check whether the worker is running, exited, or repeatedly restarting. Also check whether its database and other declared dependencies are available.

### 4.2 Inspect recent worker logs

```bash
docker compose logs --since=30m --tail=300 worker
```

Look for startup failures, repeated exceptions, database or broker connection failures, the same task failing repeatedly, or evidence that the worker starts but does not make progress.

### 4.3 Compare backend logs

```bash
docker compose logs --since=30m --tail=200 backend
```

Check whether the backend is producing related errors, whether the incident began after a deployment, and whether the problem may originate outside the worker.

### 4.4 Check Redis when this deployment uses the Compose Redis service

Redis is optional in the root Compose file and is enabled through a profile.

When the deployment is intended to use that Compose Redis service, inspect it with:

```bash
docker compose --profile redis ps redis
docker compose --profile redis exec redis redis-cli ping
```

A responding Redis instance returns:

```text
PONG
```

If the deployment uses an external Redis service or the Django-Q ORM fallback, use the corresponding deployment diagnostics instead. Do not start a different broker or change the queue backend merely because the optional local Redis container is absent.

### 4.5 Protect diagnostic information

Do not share raw `.env` files, secret values, complete environment dumps, notification payloads, or unredacted production data. Share only the minimum sanitized log excerpts needed to explain the failure.

## 5. Decide whether a restart is appropriate

A controlled restart may be appropriate when:

- The worker process has exited or is unhealthy and the cause is understood.
- The worker is no longer making progress after dependency availability has been checked.
- A confirmed transient failure has left the worker unable to recover by itself.

Before restarting:

1. Save the incident details and relevant log excerpts.
2. Check whether a deployment, database, or broker issue is still active.
3. Confirm that the worker is the affected component.
4. Avoid repeated restarts while the underlying cause remains unresolved.

A restart can interrupt an in-flight task. Django-Q's configured timeout and retry behavior can cause an unacknowledged task to be delivered again. Notification task handlers must therefore be safe to repeat (idempotent).

## 6. Restart the worker

### 6.1 Worker container is running but appears stuck

Use a single controlled restart:

```bash
docker compose restart worker
```

The Compose worker has a 120-second `stop_grace_period`. This allows the Django-Q cluster to receive SIGTERM and gives in-flight tasks time to finish before Docker forcefully stops the container.

Do not shorten the grace period as a recovery shortcut.

### 6.2 Worker container is stopped

Start the worker service:

```bash
docker compose up -d worker
```

This starts the Compose worker service. It does not clear or recreate the task queue.

If the deployment uses a different Compose file, profile, or hosting platform, apply the equivalent restart or start operation to the actual deployed worker service. Do not assume the root Compose service is the production worker without checking the deployment configuration.

## 7. Verify recovery

### 7.1 Confirm the worker is running

```bash
docker compose ps worker
```

Confirm that the worker container is running and is not repeatedly restarting.

### 7.2 Inspect fresh worker logs

```bash
docker compose logs --since=5m --tail=150 worker
```

Confirm that Django-Q starts without repeated startup, database, or broker errors.

### 7.3 Confirm that work is progressing

Use the application's existing task or notification monitoring, where configured, to confirm that pending work is progressing. Check a known task identifier or a controlled test notification path, if one is available.

Do not send test notifications to real users without authorization. Do not infer successful processing solely from the container showing `Up`.

### 7.4 Observe for recurring failures

Continue monitoring worker and backend logs. Confirm that the original error does not recur and that expected background operations resume.

The release checklist also calls for checking background-work logs and confirming there are no new errors for 10 minutes after deployment.

If tasks remain stalled, stop repeating restarts. Revisit the database, broker, application configuration, and task-specific failure details, then escalate with sanitized evidence.

## 8. Rollback guidance

Use rollback when the incident began after a backend release or configuration change and the evidence points to that change.

### Backend code or worker image regression

- Identify the last known-good backend commit or image.
- Redeploy that previous version using the deployment platform's established rollback procedure.
- Ensure the worker runs the corresponding compatible backend code or image.
- Restart or redeploy the worker through the same deployment mechanism.
- Repeat the verification steps in Section 7.

The Django-Q worker runs application code from the backend project. Rolling back only an unrelated frontend deployment will not fix a backend worker regression.

### Configuration regression

If a changed environment variable caused the failure:

- Restore its last known-good value in the deployment environment.
- Restart or redeploy the affected worker so it receives the restored configuration.
- Never put secret values in incident reports or logs.

### Database migration concerns

Do not reverse a database migration as a routine worker-recovery action. Follow `docs/RELEASE_CHECKLIST.md` and `docs/MIGRATIONS.md`: verify that a migration is reversible and that an appropriate backup exists before attempting any reversal or restoration.

After any rollback, repeat the worker and application checks in Section 7. Record the rollback revision, reason, and outcome.

## 9. Actions explicitly prohibited during routine recovery

**Never delete queued work as a routine worker-recovery step.** The queue may contain notifications and other pending work that has not yet been processed.

Do not run any of these as a routine recovery action:

```bash
docker compose down -v
docker volume rm <volume>
docker system prune --volumes
```

Also do not:

- Run `FLUSHDB` or `FLUSHALL` against Redis.
- Delete Redis queue keys or Django-Q broker records.
- Delete queued task rows or clear task tables to make the worker appear healthy.
- Remove persistent database or broker volumes.
- Repeatedly restart the worker without investigating the underlying failure.
- Disable retries or change timeout and grace-period settings without understanding the impact.

These actions can destroy persistent data or pending work. A normal worker restart should leave queued work intact. An interrupted, unacknowledged task may be delivered again after the configured retry interval, so duplicate-safe task handling is important.

The volume-reset examples in the general local-development troubleshooting guide are for specific local setup failures. They are **not** instructions for routine notification-worker recovery.

## 10. Escalation checklist

If recovery does not work, escalate with:

- Incident start time and timezone.
- Environment and deployment revision or image.
- Output of `docker compose ps worker` and relevant dependency status.
- Sanitized worker and backend log excerpts with timestamps.
- Whether the deployment uses Redis or the ORM broker fallback (do not include connection credentials).
- Affected task identifiers and approximate delay, if available.
- Actions already attempted and their results.
- Whether a recent code, environment, infrastructure, or migration change preceded the incident.

Do not attach secrets, full environment files, notification content, or unnecessary personal data.



## Related documentation

- [Worker shutdown behavior](WORKER_SHUTDOWN.md)
- [Docker Compose troubleshooting](TROUBLESHOOTING.md)
- [Release and rollback checklist](RELEASE_CHECKLIST.md)
- [Migration guidance](MIGRATIONS.md)
