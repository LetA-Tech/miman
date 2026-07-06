#!/usr/bin/env bash
# Static checks over the miman release/deploy artifacts (spec 03-M §12 items
# 4-7,11,13). Read-only — safe to run repeatedly (idempotent by construction).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_ENV="${REPO_ROOT}/deploy/.env.example"
DEPLOY_COMPOSE="${REPO_ROOT}/deploy/docker-compose.yml"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

warn() {
  echo "WARN: $1" >&2
}

require_file() {
  local path="$1"
  [ -f "$path" ] || fail "required file not found: ${path}"
}

require_executable() {
  local path="$1"
  [ -x "$path" ] || fail "required executable not found: ${path}"
}

env_value() {
  local key="$1"
  awk -F= -v key="$key" '
    $0 ~ "^[[:space:]]*#" { next }
    $1 == key {
      value = $0
      sub("^[^=]*=", "", value)
      sub(/[[:space:]]+#.*/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
    }
  ' "$DEPLOY_ENV" | tail -1
}

require_make_target() {
  local target="$1"
  grep -Eq "^${target}:" "${REPO_ROOT}/Makefile" || fail "Makefile missing target: ${target}"
}

require_env_key() {
  local key="$1"
  grep -Eq "^${key}=" "$DEPLOY_ENV" || fail "deploy/.env.example missing ${key}"
}

require_no_canonical_mem0_cloud() {
  # LETA_PATCH.md is a changelog, not a release/deploy artifact — it
  # necessarily *names* MEM0_API_KEY when documenting this very check
  # (self-match false positive), so it's excluded from the scan.
  if grep -R -n 'MEM0_API_KEY' \
      "${REPO_ROOT}/Dockerfile" \
      "${REPO_ROOT}/Makefile" \
      "${REPO_ROOT}/scripts/release-all.sh" \
      "${REPO_ROOT}/deploy" >/dev/null 2>&1; then
    fail "canonical LetA release/deploy artifacts must not use MEM0_API_KEY"
  fi
}

require_no_public_compose_binds() {
  if grep -nE '(^|[^0-9])0\.0\.0\.0:' "$DEPLOY_COMPOSE" >/dev/null; then
    fail "deploy compose must not publish host ports on 0.0.0.0"
  fi

  if grep -nE 'host_ip:[[:space:]]*"?0\.0\.0\.0"?' "$DEPLOY_COMPOSE" >/dev/null; then
    fail "deploy compose must not use host_ip 0.0.0.0"
  fi

  if grep -nE 'published:[[:space:]]*"?6333"?|published:[[:space:]]*"?6334"?|published:[[:space:]]*"?5432"?' \
      "$DEPLOY_COMPOSE" >/dev/null; then
    fail "deploy compose must not publish Qdrant or Postgres ports"
  fi
}

require_no_latest_images() {
  # The deploy compose intentionally tracks the DOCR `latest` tag (fleet
  # doctrine — CD also ships immutable miman-vX.Y.Z + sha tags for rollback),
  # so only the Dockerfile base images are held to the no-floating-tag rule.
  if grep -R -n -E '(:latest|TAG:-latest)' "${REPO_ROOT}/Dockerfile" >/dev/null; then
    fail "Dockerfile base images must not use floating :latest tags"
  fi
}

require_collection_suffix_versioned() {
  # Provider-agnostic guard. Qdrant collection vector dimensions are immutable —
  # swapping the embedding model on an existing collection corrupts retrieval.
  # The required signal that "model changed" is a bump of the _vN suffix in
  # the collection name (spec §5.5).
  local model collection
  model="$(env_value "MEM0_DEFAULT_EMBEDDER_MODEL" | tr '[:upper:]' '[:lower:]')"
  collection="$(env_value "QDRANT_COLLECTION_NAME" | tr '[:upper:]' '[:lower:]')"

  [ -n "$model" ] || fail "MEM0_DEFAULT_EMBEDDER_MODEL is missing in deploy/.env.example"
  [ -n "$collection" ] || fail "QDRANT_COLLECTION_NAME is missing in deploy/.env.example"

  [[ "$collection" =~ _v[0-9]+$ ]] \
    || fail "QDRANT_COLLECTION_NAME must end with _v<N> (Qdrant dim is immutable; embedding-model swaps must bump N)"
}

require_no_tracked_env_secrets() {
  local tracked_env
  tracked_env="$(git -C "$REPO_ROOT" ls-files | grep -E '(^|/)\.env$' || true)"
  [ -z "$tracked_env" ] || fail "tracked .env file is forbidden: ${tracked_env}"
}

require_release_tag_prefix() {
  grep -q 'miman-v' "${REPO_ROOT}/scripts/release-all.sh" \
    || fail "scripts/release-all.sh must use the miman-v tag prefix"
}

require_file "${REPO_ROOT}/Dockerfile"
require_file "${REPO_ROOT}/.dockerignore"
require_file "${REPO_ROOT}/docker/entrypoint.sh"
require_file "${REPO_ROOT}/Makefile"
require_file "${REPO_ROOT}/LETA_PATCH.md"
require_file "$DEPLOY_ENV"
require_file "$DEPLOY_COMPOSE"
require_file "${REPO_ROOT}/deploy/deploy.sh"
require_file "${REPO_ROOT}/deploy/README.md"
require_executable "${REPO_ROOT}/deploy/deploy.sh"
require_executable "${REPO_ROOT}/scripts/release-all.sh"
require_file "${REPO_ROOT}/tests/server/test_leta_qdrant_config.py"

require_make_target miman-test
require_make_target miman-docker-build
require_make_target miman-deploy-check
require_make_target release-all
require_make_target miman-compose-config

bash -n "${REPO_ROOT}/scripts/release-all.sh"
bash -n "${REPO_ROOT}/scripts/deploy-check.sh"
bash -n "${REPO_ROOT}/deploy/deploy.sh"
bash -n "${REPO_ROOT}/docker/entrypoint.sh"

require_env_key MEM0_VECTOR_STORE
require_env_key QDRANT_URL
require_env_key QDRANT_COLLECTION_NAME
require_env_key ADMIN_API_KEY
require_env_key JWT_SECRET
require_env_key POSTGRES_PASSWORD
require_env_key MEM0_TELEMETRY
require_env_key OPENAI_API_KEY

[ "$(env_value MEM0_VECTOR_STORE)" = "qdrant" ] || fail "MEM0_VECTOR_STORE must be qdrant in canonical deploy env"
[[ "$(env_value QDRANT_URL)" == http://qdrant:* ]] || fail "QDRANT_URL must point to the private qdrant service"
[ "$(env_value MEM0_TELEMETRY | tr '[:upper:]' '[:lower:]')" = "false" ] || fail "MEM0_TELEMETRY must be false in the LetA profile (spec §12 item 11)"

require_collection_suffix_versioned
require_no_canonical_mem0_cloud
require_no_public_compose_binds
require_no_latest_images
require_no_tracked_env_secrets
require_release_tag_prefix

if command -v docker >/dev/null 2>&1; then
  docker compose --env-file "$DEPLOY_ENV" -f "$DEPLOY_COMPOSE" config >/dev/null
else
  warn "docker not found; skipped docker compose config validation"
fi

echo "deploy-check: ok"
