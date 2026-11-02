#!/usr/bin/env bash
# compose_smoke.sh - bring the Docker Compose stack up and check that the
# expected service endpoints answer.
#
# Usage: scripts/compose_smoke.sh   (or: make smoke)
#
# - Needs no real credentials: throwaway SECRET_KEY / FIELD_ENCRYPTION_KEY
#   values are generated and passed through a temporary compose override.
# - On failure it names the service that failed and prints its recent logs.
# - The stack (containers, network, volumes) is always torn down on exit.
#
# Env: SMOKE_TIMEOUT (seconds to wait per endpoint, default 180),
#      SMOKE_LOG_LINES (log lines shown per failing service, default 100).

set -u

cd "$(dirname "$0")/.."

TIMEOUT="${SMOKE_TIMEOUT:-180}"
LOG_LINES="${SMOKE_LOG_LINES:-100}"
export COMPOSE_PROJECT_NAME="atelier-smoke"

TMP_DIR="$(mktemp -d)"
OVERRIDE="$TMP_DIR/override.yml"
FAILED_SERVICES=()

compose() {
  docker compose -f docker-compose.yml -f "$OVERRIDE" "$@"
}

cleanup() {
  local status=$?
  echo "Cleaning up compose stack..."
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$TMP_DIR"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
FIELD_KEY="$(python3 -c 'import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')"

cat >"$OVERRIDE" <<YAML
services:
  backend:
    environment:
      - SECRET_KEY=$SECRET
      - FIELD_ENCRYPTION_KEY=$FIELD_KEY
  worker:
    environment:
      - SECRET_KEY=$SECRET
      - FIELD_ENCRYPTION_KEY=$FIELD_KEY
YAML

report_failure() {
  local service="$1" reason="$2"
  echo "FAIL [$service]: $reason" >&2
  FAILED_SERVICES+=("$service")
  echo "---- last $LOG_LINES log lines for '$service' ----" >&2
  compose logs --no-color --tail "$LOG_LINES" "$service" >&2 || true
  echo "---- end of '$service' logs ----" >&2
}

wait_for_url() {
  local service="$1" url="$2" waited=0
  while [ "$waited" -lt "$TIMEOUT" ]; do
    if curl -fsS -o /dev/null --max-time 5 "$url" 2>/dev/null; then
      echo "ok   [$service] $url"
      return 0
    fi
    sleep 3
    waited=$((waited + 3))
  done
  report_failure "$service" "$url did not return 2xx within ${TIMEOUT}s"
  return 1
}

echo "Validating compose configuration..."
if ! compose config --quiet; then
  echo "FAIL [compose]: docker compose config is invalid" >&2
  exit 1
fi

echo "Starting stack..."
if ! compose up -d --build; then
  echo "FAIL [compose]: 'docker compose up' failed" >&2
  for svc in $(compose config --services); do
    state="$(compose ps --format '{{.State}}' "$svc" 2>/dev/null | head -n 1)"
    if [ "$state" != "running" ]; then
      report_failure "$svc" "state is '${state:-not created}'"
    fi
  done
  exit 1
fi

wait_for_url meilisearch "http://localhost:7700/health"
wait_for_url backend "http://localhost:8000/health/live/"
wait_for_url frontend "http://localhost:5173/"

if [ "${#FAILED_SERVICES[@]}" -gt 0 ]; then
  echo "Smoke test failed for: ${FAILED_SERVICES[*]}" >&2
  exit 1
fi

echo "Smoke test passed."
