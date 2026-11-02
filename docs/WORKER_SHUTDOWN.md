# Notification Worker Shutdown

Background tasks (emails, notifications, webhooks, PDF generation) run in the `worker` container with Django-Q (`python manage.py qcluster`). This note describes what happens when that container is stopped or replaced, for example during a deploy.

## Grace period

| Setting | Value | Where |
| --- | --- | --- |
| Task `timeout` | 90s (`Q_TASK_TIMEOUT`) | `backend/config/settings.py` |
| Task `retry` | `timeout + 30` = 120s | `backend/config/settings.py` |
| Container `stop_grace_period` | 120s | `docker-compose.yml` (base), repeated in `infra/deploy/docker-compose.prod.yml` |

`Q_TASK_TIMEOUT` must be a positive integer; anything else fails at startup with `ImproperlyConfigured`.

Rules to keep: `retry > timeout`, and `stop_grace_period > timeout`. If you raise `Q_TASK_TIMEOUT`, raise `stop_grace_period` with it.

## Where qcluster runs

| Manifest | Runs qcluster? | Grace period |
| --- | --- | --- |
| `docker-compose.yml` (`worker`) | yes | `stop_grace_period: 120s` |
| `infra/deploy/docker-compose.prod.yml` (`worker`) | yes, inherits the command | `stop_grace_period: 120s` (explicit) |
| `infra/deploy/docker-compose.override.yml.example` | inherits the base service | inherited |
| `backend/Procfile` | no, web process only | not applicable |
| `backend/Dockerfile` | no, default `CMD` is runserver / daphne | not applicable |

If qcluster is deployed on another platform (Kubernetes, Render, ECS and so on), set that platform's equivalent (for example `terminationGracePeriodSeconds`) to more than `Q_TASK_TIMEOUT`. The platform's default is often 10s to 30s, which is too short.

## Behaviour on SIGTERM

1. `docker stop` / a container replacement sends SIGTERM to the `qcluster` process (in the compose `worker` service `command` is a plain string, which Compose splits into an argv list and runs without a shell, so the Django-Q cluster process is PID 1 of the container; its worker processes are children. Do not wrap the command in `sh -c` without `exec`, or the shell becomes PID 1 and the signal may never reach the cluster).
2. The cluster stops pulling new tasks and sends a stop signal to each worker after its current task. Workers finish the task they are running.
3. The cluster waits up to `timeout` (90s) for workers to exit. Tasks that need longer than this are terminated.
4. A task that was taken from the broker but not acknowledged (terminated, or the container was killed) is delivered again after `retry` seconds. Tasks still waiting in the broker (Redis, or the ORM fallback) are untouched and picked up by the replacement worker.

Because an interrupted task can run a second time, notification tasks must be safe to repeat (idempotent).

## Long-running tasks

Tasks expected to run longer than `Q_TASK_TIMEOUT` should be split into smaller tasks, or the timeout and grace period raised together. Docker's default grace period is 10s, which is why the explicit `stop_grace_period` is set.

## Checking it locally

```bash
docker compose up -d worker
docker compose stop worker   # should return after in-flight tasks finish, not after 10s
```
