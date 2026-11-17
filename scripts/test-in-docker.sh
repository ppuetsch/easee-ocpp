#!/usr/bin/env bash
# Runs the tests in a Linux container on a Docker host (Home Assistant's test harness needs Linux).
# Usage: scripts/test-in-docker.sh [pytest args...]   (DOCKER_HOST_SSH=root@host to change the host)
set -euo pipefail
DOCKER_HOST_SSH="${DOCKER_HOST_SSH:-root@docker.fritz.box}"
IMAGE="easee-ocpp-test"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ensure_image() {
  if ! ssh "$DOCKER_HOST_SSH" "docker image inspect $IMAGE >/dev/null 2>&1"; then
    ssh "$DOCKER_HOST_SSH" "docker build -t $IMAGE -" < "$REPO_ROOT/scripts/Dockerfile.test"
  fi
}

run_tests() {
  tar -C "$REPO_ROOT" --exclude=__pycache__ -cf - custom_components tests pyproject.toml requirements-test.txt \
    | ssh "$DOCKER_HOST_SSH" "docker run --rm -i -e PYTHONUNBUFFERED=1 $IMAGE sh -c 'tar --no-same-owner -xf - && timeout ${TEST_TIMEOUT_SECONDS:-300} python -m pytest -p no:cacheprovider $*'"
}

ensure_image
run_tests "$@"
