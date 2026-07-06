#!/usr/bin/env bash
# ============================================================================
# miman — deploy.sh (spec 03-M §5.4, §10.1)
# ============================================================================
# Build/up the LetA compose profile, wait for health, then run the behavior
# smokes: provisioned member-key add->search->delete round-trip, plus proof
# that the same member key gets 403 on the two admin-only endpoints
# (spec §12 item 13, bridge B-4).
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"
BASE_URL="http://127.0.0.1:8000"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

log()  { printf '[%s] %s\n' "$TS" "$*"; }
fail() { log "ERROR: $*" >&2; exit 1; }

[[ -r "$ENV_FILE" ]]     || fail ".env missing. Copy .env.example to .env first."
[[ -r "$COMPOSE_FILE" ]] || fail "docker-compose.yml missing in deploy/"

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
  ' "$ENV_FILE" | tail -1
}

# Refuse to run if AUTH_DISABLED is not true and JWT_SECRET is missing — that
# combination means the server will refuse to boot. Surface the fix early.
auth_disabled="$(env_value AUTH_DISABLED | tr '[:upper:]' '[:lower:]')"
jwt_secret="$(env_value JWT_SECRET)"
if [[ "$auth_disabled" != "true" && -z "$jwt_secret" ]]; then
    fail "JWT_SECRET unset and AUTH_DISABLED is not true. miman will refuse to boot."
fi

log "validating compose config"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config >/dev/null

log "building + pulling images"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull --ignore-buildable 2>/dev/null || true

log "starting stack"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

log "waiting for /healthz"
ATTEMPTS=24
for i in $(seq 1 "$ATTEMPTS"); do
    if curl -fsS -m 3 "$BASE_URL/healthz" >/dev/null 2>&1; then
        log "miman /healthz ok"
        break
    fi
    [[ "$i" -eq "$ATTEMPTS" ]] && fail "miman /healthz never came up; check 'docker compose -f $COMPOSE_FILE logs miman'"
    sleep 5
done

log "waiting for /readyz"
for i in $(seq 1 "$ATTEMPTS"); do
    if curl -fsS -m 3 "$BASE_URL/readyz" >/dev/null 2>&1; then
        log "miman /readyz ok"
        break
    fi
    [[ "$i" -eq "$ATTEMPTS" ]] && fail "miman /readyz never came up; check 'docker compose -f $COMPOSE_FILE logs miman'"
    sleep 5
done

log "provisioning member service key for the smoke test"
MEMBER_KEY="$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T miman \
    python -m scripts.provision_service_key --name deploy-smoke --label "deploy.sh smoke ${TS}" --rotate)"
[[ -n "$MEMBER_KEY" ]] || fail "provision_service_key produced no key"

SCRATCH_USER="deploy-smoke-$(date -u +%s)"

log "smoke: add (infer=false, scratch user_id=$SCRATCH_USER)"
ADD_RESPONSE="$(curl -fsS -m 10 -X POST "$BASE_URL/memories" \
    -H "X-API-Key: $MEMBER_KEY" -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"miman deploy.sh smoke test memory\"}],\"user_id\":\"$SCRATCH_USER\",\"infer\":false}")"
MEMORY_ID="$(printf '%s' "$ADD_RESPONSE" | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"]; assert len(r)==1, r; print(r[0]["id"])')"
[[ -n "$MEMORY_ID" ]] || fail "add smoke did not return a memory id: $ADD_RESPONSE"
log "smoke: add ok (memory_id=$MEMORY_ID)"

log "smoke: search"
SEARCH_RESPONSE="$(curl -fsS -m 10 -X POST "$BASE_URL/search" \
    -H "X-API-Key: $MEMBER_KEY" -H "Content-Type: application/json" \
    -d "{\"query\":\"miman deploy smoke test\",\"filters\":{\"user_id\":\"$SCRATCH_USER\"}}")"
printf '%s' "$SEARCH_RESPONSE" | python3 -c "
import json, sys
results = json.load(sys.stdin).get('results', [])
ids = [r.get('id') for r in results]
assert '$MEMORY_ID' in ids, f'expected $MEMORY_ID in search results, got {ids}'
"
log "smoke: search ok (found $MEMORY_ID)"

log "smoke: delete"
curl -fsS -m 10 -X DELETE "$BASE_URL/memories/$MEMORY_ID" -H "X-API-Key: $MEMBER_KEY" >/dev/null
log "smoke: delete ok"

log "smoke: member key must 403 on POST /reset"
RESET_STATUS="$(curl -sS -m 10 -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/reset" -H "X-API-Key: $MEMBER_KEY")"
[[ "$RESET_STATUS" == "403" ]] || fail "expected 403 from POST /reset under member key, got $RESET_STATUS"
log "smoke: POST /reset -> 403 ok"

log "smoke: member key must 403 on unscoped GET /memories"
LIST_STATUS="$(curl -sS -m 10 -o /dev/null -w '%{http_code}' "$BASE_URL/memories" -H "X-API-Key: $MEMBER_KEY")"
[[ "$LIST_STATUS" == "403" ]] || fail "expected 403 from unscoped GET /memories under member key, got $LIST_STATUS"
log "smoke: unscoped GET /memories -> 403 ok"

log "stack up and smokes green. API: $BASE_URL/docs"
log "tail: docker compose -f $COMPOSE_FILE logs -f miman"
