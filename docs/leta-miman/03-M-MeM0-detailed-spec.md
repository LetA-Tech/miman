# Miman — LetA Memory Runtime: Detailed Implementation Spec

**Document:** `03-M-MeM0-detailed-spec.md`
**Date:** 2026-07-05 · **Author of record:** Lucas (LetA) · **Prepared with:** Claude (Fable 5)
**Status:** Implementation-ready spec — dispatchable to Claude Code lanes after Lucas approval.
**Ties into:** mcfo-finsor lane **X-4** ("Mem0 fork v3 rebase", LANE_TRACKER.md:47, PENDING) and
substrate gates SUB-1/2/3 (LANE_TRACKER.md:45).

## Ground-truth pins (every claim below is cited against these)

| Repo | Path | HEAD / base | Notes |
|---|---|---|---|
| `miman` (target) | `~/Projects/miman` | `cd79fa89`, pyproject `mem0ai 2.0.11` | Full-history clone of `mem0ai/mem0`, origin = `LetA-Tech/miman`. **No `upstream` remote configured yet** (verified `git remote -v`). |
| `mem0-v2.0-deprecated` (reference) | `~/leta/mem0-v2.0-deprecated` | `ca66532c`; upstream base tag `v2.0.2` = `9043fbf6` (LETA_PATCH.md:3-4) | 8 LetA commits ahead of upstream base commit `79793b0d`. Reference only — never copied blindly. |
| `mcfo-finsor` (doctrine) | `~/Projects/mcfo-finsor` | docs @ 2026-07-05 | `03_memory_architecture.md`, `09_technical_specification.md` (09B.7, 09C.8), LANE_TRACKER.md. |
| `mcfo-leankit` | `~/Projects/mcfo-leankit` | **UNVERIFIED** — not readable this session | AgentKit seam facts taken from finsor docs (re-verified there 2026-07-05). |

## Naming register (canonical, one source of truth)

```text
miman        LetA memory runtime = Mem0 OSS distribution + LetA patch layer (this repo)
finmem       Go SDK, github.com/LetA-Tech/finmem (binding name — finsor 03 §13, 09B.7)
FinMem boundary = finmem SDK + agentmemory service + settings/admin API (finsor 03 §13)
Image        registry.digitalocean.com/leta-container-registry/miman:<tag>
Release tag  miman-vX.Y.Z   (bare vX.Y.Z is FORBIDDEN — §6.3, routes to PyPI upstream)
```

---

## 1. Miman architecture and repo strategy

### 1.1 Position in the stack

```text
Finsor / FinAI / Forge          consumers (Go services)
        │
        ▼
FinMem SDK (finmem)             Go client: DTOs, ForbidInfer, breaker, capability probe,
        │                       filters-only search, idempotency keys   [sibling repo]
        ▼  HTTPS (REST, per-service X-API-Key)
Miman                           THIS repo: Mem0 OSS server + LetA patch layer,
        │                       packaged as one Docker image + compose stack
        ▼  in-process
Mem0 OSS v3 engine              extraction (FinMem default: infer=false), embedding, ranking
        │
        ▼  qdrant-client — upstream floor >=1.12.0 (pyproject.toml:17); LetA floor v1.18.3+
Qdrant                          vectors + payload-filtered similarity
```

Miman is a **distribution** of the Mem0 OSS server — a deploy patch of Mem0 + Qdrant — not
an additional network hop and not a rewrite. Consumers never see Mem0 concepts; they see the
FinMem boundary (finsor 03 §13: "Agents never see Mem0; there are no Mem0 concepts in any
prompt").

Version note: **"v3" names the Mem0 engine generation, and it is what miman ships.** The
pinned base runs the ADD-only "V3 PHASED BATCH PIPELINE" (mem0/memory/main.py:868; async twin
:2494) with `ADDITIVE_EXTRACTION_PROMPT`, and upstream docs badge the current line "v3"
(docs/platform/features/temporal-reasoning.mdx:3-4). The **Python package** carrying that v3
engine is versioned `mem0ai 2.0.11` at `cd79fa89` (pyproject.toml) — package semver and
engine generation are different axes. Wherever this spec says "v3" it means the engine
generation, matching the finsor doctrine's "v3 rebase" (03 §13, lane X-4). The LetA
qdrant-client floor (v1.18.3+, matching the deployed Qdrant server line) is a LetA deploy
constraint layered on upstream's `>=1.12.0`, enforced in the image build — not an upstream
fact.

Doctrine constraints inherited (finsor 03 §0, §13-§15): Mem0 is storage + search only, never
extractor, never authority; Mongo (Finsor-side) is authoritative; Mem0/Qdrant are disposable
derived indexes; rebuild-from-Mongo via `finmem-admin reindex` is the recovery and migration
primitive. Therefore **miman carries no data-migration machinery** — v2.0.2-era deployments
are not migrated in place; indexes are rebuilt through the FinMem admin plane (§5.6).

### 1.2 Repo strategy (decided)

- `LetA-Tech/miman` is a standalone repo seeded with full upstream history (already done —
  HEAD `cd79fa89` matches upstream; only LetA remote is origin). It is **not** a GitHub-fork
  relationship: no upstream-default PR targeting, independent issues/releases.
- Add the missing upstream remote as lane M0 work:
  `git remote add upstream https://github.com/mem0ai/mem0.git`.
- The deprecated repo stays frozen as the v2.0.2 reference. No archive branches are created
  inside miman — the archive already exists as a separate repo.
- LetA changes land as a small, reviewable commit series on `main`. Patch surface is
  documented in a rewritten `LETA_PATCH.md` (lane M1 deliverable) which names the upstream
  base commit/tag explicitly.
- Upstream sync targets **upstream release tags**, never `upstream/main` (§6.4). Weekly
  drift-check workflow opens a sync PR; no auto-merge.

### 1.3 Branch and tag model

```text
main                    miman runtime line (protected; sync PRs + patch PRs only)
sync/upstream-<tag>     temporary upstream-sync branches
miman-vX.Y.Z            miman release tags (image builds)  — never bare vX.Y.Z (§6.3)
```

`evaluation/` is an upstream submodule → `mem0ai/memory-benchmarks` (.gitmodules:1-4). Leave
it untouched and uninitialized in CI; never vendor it.

---

## 2. Deprecated Mem0 v2.0.2 fork — patch audit (reference repo)

Measured with `git diff --name-status 79793b0d..ca66532c`: **13 files, +1,349 / −18**.
The fork is an operational patch layer, not a product fork. Complete inventory:

| # | File | Kind | Content (deprecated repo citations) |
|---|---|---|---|
| P1 | `server/main.py` | M | Vector-store selector `MEM0_VECTOR_STORE` (main.py:118,169-177); Qdrant env builder (main.py:129-151); `/healthz` (577-580); `/readyz` (586-593); `/search` top-level→filters wrapper (486-508); `OPENAI_BASE_URL` forwarding into LLM+embedder config (110,192-194); health paths in `SKIPPED_REQUEST_LOG_PATHS` (52) |
| P2 | `Dockerfile` (root) | A | `python:3.12.12-slim-bookworm`; installs **local** patched mem0 source, filters floating `mem0ai` out of server requirements (Dockerfile:28-36); `libpq5` for psycopg runtime (19-21, commit `110f5368`); non-root `mem0:10001` (23-24); `/app/history` (41-42); `EXPOSE 8000`; HEALTHCHECK → `/healthz` (49-50); `uvicorn` without `--reload` (52) |
| P3 | `.dockerignore` | A | excludes VCS, env files, caches, and all non-server upstream subtrees (openmemory, embedchain, docs, cli, mem0-ts, …) (.dockerignore:32-43) |
| P4 | `deploy/docker-compose.yml` | A | 3 services: mem0 (127.0.0.1:8000 only), `qdrant/qdrant:v1.18.0-unprivileged` (no host port), `postgres:16-alpine` app DB; healthchecks on all; `no-new-privileges`; private bridge network |
| P5 | `deploy/.env.example` | A | 16 vars — qdrant selection, auth trio, app-DB, OpenRouter routing, `MEM0_TELEMETRY=false` |
| P6 | `deploy/deploy.sh` | A | env guards (JWT_SECRET unless AUTH_DISABLED) → compose config check → build/pull → up → poll `/healthz` (24×5s, fatal) → poll `/readyz` (12×5s, warn) |
| P7 | `deploy/README.md` | A | dev-loop only; production stack lives in the platform repo (`mcfo-finsys/agent-memory-server`); "never AUTH_DISABLED outside a dev machine" |
| P8 | `Makefile` | M | `lint`, `test` (scoped to LetA files), `docker-build VERSION=`, `deploy-check`, `release-all VERSION=`, `compose-config` |
| P9 | `scripts/deploy-check.sh` | A | file/target existence; env presence + `MEM0_VECTOR_STORE=qdrant` and internal `QDRANT_URL` asserts; **collection name must end `_v<N>`** (dims are immutable — deploy-check.sh:95-111); forbids SSH deploy steps, `MEM0_API_KEY`, `0.0.0.0` port binds, `:latest` tags, tracked `.env` |
| P10 | `scripts/release-all.sh` | A | guards (main branch, clean tree, synced, tag-unique) → deploy-check → push main → annotated `vX.Y.Z` tag → push; CI does the rest; **no deployment** |
| P11 | `.github/workflows/release.yml` | A | on tag `v[0-9]*.[0-9]*.[0-9]*`; validate job (lint/test/deploy-check, tag-on-main ancestor check) → publish job (DOCR `mem0-server-qdrant:<tag>+<sha>`, `DIGITALOCEAN_ACCESS_TOKEN`) |
| P12 | `tests/server/test_leta_qdrant_config.py` | A | 7 cases: qdrant selector, pgvector-absent-under-qdrant, base-url propagation to LLM+embedder, healthz, readyz ok/503, no `MEM0_API_KEY` in canonical config |
| P13 | `LETA_PATCH.md` | A | patch manifest + rebase-forward workflow + release/tag rules |

The fork's own auth posture (LETA_PATCH.md:110-116): upstream auth untouched, all routes keep
`verify_auth`. The fork predates upstream's role model only partially — see §3.4.

---

## 3. What upstream has already fixed (verified in miman @ `cd79fa89`)

### 3.1 `/search` top-level scope → `filters` — FIXED, drop P1's wrapper

`SearchRequest` keeps top-level `user_id/run_id/agent_id` as **deprecated** fields
(miman `server/main.py:199-201`); the handler moves them into `filters` and logs a
deprecation warning (main.py:455-467), then calls
`get_memory_instance().search(query=..., filters=filters, **params)` (main.py:477).
`Memory.search` itself is keyword-only with `filters` (mem0/memory/main.py:
`def search(self, query, *, top_k=20, filters=None, threshold=0.1, rerank=False, ...)`).

Behavioral delta vs the old LetA wrapper, recorded for completeness: on a key collision
upstream **top-level wins** (main.py:460 assigns unconditionally); the old fork let
client-supplied `filters` win (deprecated main.py:502). Irrelevant to FinMem — the SDK always
sends the filters wrapper and never top-level fields (finsor 09C.8: "SDK always sends the
`filters` wrapper") — but any curl/manual tooling relying on filters-wins must not.

**Decision D-1: do not re-apply the /search wrapper. Keep a contract test asserting both
shapes reach the SDK correctly (§9.4 T-11).**

### 3.2 `OPENAI_BASE_URL` — FIXED in core, drop P1's forwarding

- LLM: `base_url = self.config.openai_base_url or os.getenv("OPENAI_BASE_URL") or
  "https://api.openai.com/v1"` (mem0/llms/openai.py:51); OpenRouter has a dedicated branch
  (openai.py:45).
- Embedder: `config.openai_base_url or os.getenv("OPENAI_API_BASE") or
  os.getenv("OPENAI_BASE_URL") or default` (mem0/embeddings/openai.py:22-27), with an
  `OPENAI_API_BASE` deprecation warning (28-31).

The server's `DEFAULT_CONFIG` no longer needs to inject `openai_base_url` — the env var
reaches the core provider directly.

**Decision D-2: do not re-apply base-url forwarding. Keep env-honored regression tests
(§9.4 T-10).**

### 3.3 Qdrant provider — supported in core (was never the gap)

`qdrant` is a registered provider — in fact the **SDK-level default**
(mem0/vector_stores/configs.py:9 `default="qdrant"`; factory:
mem0/utils/factory.py:180). `QdrantConfig` fields: `collection_name` (default "mem0"),
`embedding_model_dims` (default 1536), `client`, `host`, `port`, `path`
(default "/tmp/qdrant"), `url`, `api_key`, `https`, `on_disk` (default False)
(mem0/configs/vector_stores/qdrant.py:11-23). Only the **server** hardcodes pgvector (§4.1).

⚠ **Validator quirk (new since v2.0.2, drives builder design §5.2):** the
`mode="before"` validator requires `path` OR (`host` AND `port`) OR (`url` AND `api_key`) in
the **raw input** (qdrant.py:31-38). A config of `{"url": "http://qdrant:6333"}` with no
API key **fails validation** even though the underlying client accepts url-only
(mem0/vector_stores/qdrant.py `__init__` builds `params["url"]` independently of api_key).
The old fork's builder emitted url-only configs (deprecated main.py:137-138) — re-applying it
verbatim would fail boot on the new base. This is exactly why P1 cannot be cherry-picked.

### 3.4 Auth and route protection — landed upstream, satisfies the 09L posture

Upstream now ships JWT + per-user `X-API-Key` + legacy `ADMIN_API_KEY`, with roles
(server/auth.py:15-20,105,144-150,193-214), rate-limited auth endpoints (slowapi,
main.py:156-157), and boot-fails when `JWT_SECRET` is missing and auth is enabled
(main.py:89-93). Route protection as of `cd79fa89`:

| Route | Guard | Cite |
|---|---|---|
| `POST /memories`, `GET/PUT/DELETE /memories/{id}`, `POST /search`, `GET /memories?user_id=…`, `/memories/{id}/history` | `verify_auth` (any authenticated principal) | main.py:367,443,452,487,515,506 |
| `GET /memories` **unscoped** (list all) | admin role or admin key required | main.py:420-427 |
| `POST /configure` | `require_admin` | main.py:332 |
| `DELETE /memories` (scoped bulk) | **`require_admin`** | main.py:527-531 |
| `POST /reset` | `require_admin` | main.py:546-547 |
| `GET /configure`, `GET /configure/providers` | `verify_auth` | main.py:321-328 |

This natively implements finsor 09C.8's "unscoped `GET /memories` and `POST /reset` MUST be
unreachable from Finsor credentials" **by credential class**: the FinMem runtime credential
is a non-admin API key; admin operations live behind the distinct `finmem-admin` credential
(09B.7). One consequence is a **contract delta against the 09C.8 wire list**: scoped bulk
`DELETE /memories` is now admin-only upstream. Resolution in §7.3.

⚠ **Provisioning gap (delta-6, drives a new patch item):** the base provides **no path to a
non-admin principal**. `POST /auth/register` creates only the first user, hardcoded
`role="admin"`, then closes (routers/auth.py:97-108); `User.role` defaults `"admin"`
(models.py:25); every `X-API-Key` resolves to its creating user (auth.py:126-141) — so every
issuable key today is an admin key. The credential-class model above therefore requires a
LetA provisioning tool: `server/scripts/provision_service_key.py` (mirrors upstream's
`server/scripts/reset_admin_password.py` pattern — deploy-time, `docker exec`, zero
API-surface change) creating a `role="member"` service user + minting its API key, printed
once.
Member-role enforcement is already server-side (`require_admin` 403, auth.py:213-214;
unscoped-list guard, main.py:424-425). An admin-only `POST /users` API is recorded as an
upstream-contribution candidate, not patched in v0.1.0. Note: key revocation is
owner-scoped upstream (api_keys.py:86) — rotation runs through the provisioning script, not
`finmem-admin`.

### 3.5 `infer` semantics on the new base

`Memory.add(..., infer: bool = True)` (mem0/memory/main.py:717-727; async twin :2357-2367).
`infer=False` performs a raw, per-message, embed-and-store ADD, skipping `system` messages
(mem0/memory/main.py:831-861) — a single user message yields **exactly one** record with
`event: "ADD"`, which is precisely what the FinMem construction probe verifies (finsor
09C.8: "infer=false single-record verification"). `infer=True` runs the
"V3 PHASED BATCH PIPELINE" with `ADDITIVE_EXTRACTION_PROMPT` (main.py:863-894) — ADD-only
extraction, consistent with the finsor v3-native stance (03 §13: in-house dedup is the only
conflict authority). The server passes `infer` through only when the client sets it
(server/main.py:186,372).

**Decision D-3 (revised, Lucas 2026-07-05): `infer` ownership.** Miman preserves upstream
Mem0 compatibility byte-for-byte: the upstream default (`infer=True`, SDK-side) is not
patched, and a server-side guard (`MEM0_REJECT_INFER`) is **rejected**, not deferred — the
runtime stays a faithful Mem0 distribution. **FinMem owns default behavior:** the SDK
defaults every add to `infer=false`; `infer=true` is reachable only through an **explicit
per-call option AND a policy gate** (Finsor-side policy/consent evaluation) — never
implicitly, never by omission. The construction probe (infer=false single-record
verification, 09C.8) is unchanged. Doctrine delta flagged for finsor alignment: 09C.8
currently reads `Infer bool /*always false; ForbidInfer guard*/` — "always false" relaxes to
"false by default; true requires explicit option + policy gate". Folded into finsor docs via
the X-4 handoff note (same process as §7.3).

### 3.6 Also new upstream since v2.0.2 (adopt as-is, no patches)

Request-ID logging + `X-Request-ID` header (main.py:44,294-302); request-log persistence to
Postgres with skip rules (main.py:261-318); `REQUEST_LOG_RETENTION_DAYS` + `make prune-logs`
(server/.env.example:34-36, server/Makefile:57-59); bundled-provider validation for
`/configure` (main.py:61-62,231-258); `expiration_date` on create/update, `explain` and
`show_expired` on search (main.py:185,205-206); entities router; alembic migrations (6, in
`server/alembic/versions/`); PostHog server telemetry, default ON, egress
`us.i.posthog.com`, opt-out `MEM0_TELEMETRY=false` (server/telemetry.py:25-27).

---

## 4. What miman still needs to patch (the reduced LetA layer)

Verified gaps in `cd79fa89`:

### 4.1 Vector-store selection — still hardcoded pgvector

`DEFAULT_CONFIG` pins `"provider": "pgvector"` with `POSTGRES_*` env inputs
(server/main.py:119-131). No `MEM0_VECTOR_STORE`, no `QDRANT_*` anywhere in `server/`
(grepped). The only alternative is runtime `POST /configure` (admin), which is not
boot-deterministic and violates the deploy-contract requirement that the store is fixed by
environment. **KEEP a rewritten selector patch** (§5.2).

### 4.2 Health endpoints — still absent

No `/healthz`, `/readyz`, or `/health` route exists (full read of server/main.py; routers are
auth/api_keys/entities/requests only). Readiness proxying still uses authenticated-adjacent
surfaces: `wait-api` curls `/auth/setup-status` (server/Makefile:37-39) and `make health`
curls `/docs` (Makefile:44-46). `SKIPPED_REQUEST_LOG_PATHS` contains only
`/api/health` (the **dashboard's** Next.js route) + docs paths (main.py:58). **KEEP the
healthz/readyz patch** (§5.3).

### 4.3 Production image — upstream's is dev-grade

`server/Dockerfile` installs **floating `mem0ai>=0.1.48` from PyPI** instead of the local
tree (server/requirements.txt:4 + `pip install -r requirements.txt`), runs as root, has no
healthcheck, and its CMD ships `--reload` (server/Dockerfile:15). The dev compose even
force-reinstalls `mem0ai` from PyPI at container start (server/docker-compose.yaml:command).
A miman image built this way would silently run **upstream PyPI code, not the patched tree**.
**KEEP the LetA root Dockerfile pattern (P2), updated** for the new dependency set
(sqlalchemy/alembic/passlib/bcrypt/python-jose/slowapi/posthog — server/requirements.txt) and
an entrypoint that runs `alembic upgrade head` before uvicorn (§6.1).

### 4.4 Deployment stack — upstream compose has no Qdrant and no prod posture

Upstream compose = mem0 (dev image, port 8888) + `pgvector/pg17` + Next.js dashboard; no
Qdrant service, host-published Postgres port 8432, bind-mounted source
(server/docker-compose.yaml). **KEEP the LetA deploy/ profile (P4-P7), updated** (§5.4).

### 4.5 CI/CD for the image — none upstream, and the old tag scheme is now unsafe

No workflow builds/publishes a server image (full `.github/workflows/` inventory: SDK/CLI/
plugin pipelines + `ci-gate.yml` + `release.yml` router only). The router routes **bare
`v*` release tags to `cd.yml` = PyPI publish of the `mem0ai` package** (release.yml:40-53,
`v*) workflow="cd.yml"`). The deprecated fork cut image releases on bare `vX.Y.Z`
(release-all.sh) — replaying that convention in miman would route image releases into the
Python-SDK publish path. **KEEP the release tooling, migrated to the `miman-v*` prefix**
(§6.2-6.3).

### 4.6 Patch surface summary (the whole LetA layer, target state)

```text
KEEP (rewritten for the new base)          DROP (fixed upstream)
────────────────────────────────          ─────────────────────
server: vector-store selector + builders   /search filters wrapper        (§3.1)
server: /healthz /readyz + log-skip        OPENAI_BASE_URL forwarding     (§3.2)
root Dockerfile + .dockerignore
deploy/ (compose, env, deploy.sh, README)
Makefile targets (miman-*)
scripts/deploy-check.sh, release-all.sh
server/scripts/provision_service_key.py (delta-6, §3.4 — lane M1, tracker DV-1)
.github/workflows: miman-checks.yml, miman-cd.yml (+1-line router arm)
tests/server/test_leta_qdrant_config.py (rewritten, §9.4)
LETA_PATCH.md (rewritten manifest)
```

Everything else in the repo stays byte-identical to upstream — that is the sync-cost model.

---

## 5. Qdrant-native configuration and deployment

### 5.1 Selection contract

```text
MEM0_VECTOR_STORE unset      -> pgvector (upstream default preserved — zero drift for
                                upstream users; the LetA deploy profile always sets it)
MEM0_VECTOR_STORE=pgvector   -> upstream pgvector config, byte-identical behavior
MEM0_VECTOR_STORE=qdrant     -> Qdrant config from QDRANT_* env (§5.2)
anything else                -> RuntimeError at import/boot, names supported values
```

Values are trimmed + lowercased before comparison (normalize inputs; never trust raw config
— finsor CLAUDE.md doctrine). "Qdrant out of the box" is delivered by the **deployment
profile**, not by flipping the code default: `deploy/.env.example` pins
`MEM0_VECTOR_STORE=qdrant` and `scripts/deploy-check.sh` fails unless the resolved provider
is qdrant (P9 behavior, kept). This keeps the server patch minimal and upstream-mergeable
while making a LetA deployment impossible to boot silently on pgvector.

### 5.2 Qdrant config builder (replaces deprecated main.py:129-151 — do not cherry-pick)

```python
def _build_qdrant_vector_store_config() -> dict:
    config: dict = {"collection_name": QDRANT_COLLECTION_NAME}
    if QDRANT_URL and QDRANT_API_KEY:
        config["url"] = QDRANT_URL
        config["api_key"] = QDRANT_API_KEY
    elif QDRANT_URL:
        # QdrantConfig's before-validator rejects url-without-api_key
        # (mem0/configs/vector_stores/qdrant.py:31-38); decompose to host+port.
        parsed = urllib.parse.urlparse(QDRANT_URL)
        if not parsed.hostname or not (parsed.port or parsed.scheme in ("http", "https")):
            raise RuntimeError(f"QDRANT_URL is not parseable: {QDRANT_URL!r}")
        config["host"] = parsed.hostname
        config["port"] = parsed.port or (443 if parsed.scheme == "https" else 6333)
        if parsed.scheme == "https":
            config["https"] = True
    elif QDRANT_HOST and QDRANT_PORT:
        config["host"] = QDRANT_HOST
        config["port"] = int(QDRANT_PORT)
    else:
        raise RuntimeError("MEM0_VECTOR_STORE=qdrant requires QDRANT_URL or QDRANT_HOST+QDRANT_PORT.")
    if QDRANT_EMBEDDING_MODEL_DIMS:
        config["embedding_model_dims"] = int(QDRANT_EMBEDDING_MODEL_DIMS)
    config["on_disk"] = QDRANT_ON_DISK
    return {"provider": "qdrant", "config": config}
```

Env vars (all read once at module level, mirroring upstream style):

| Var | Required | Default | Notes |
|---|---|---|---|
| `QDRANT_URL` | preferred | — | decomposed to host/port when no API key (validator quirk §3.3) |
| `QDRANT_HOST` / `QDRANT_PORT` | fallback | — | port int-converted, fail-fast on garbage |
| `QDRANT_COLLECTION_NAME` | yes (deploy-check) | `"memories"` | must end `_v<N>` — dims immutability convention (P9 kept) |
| `QDRANT_API_KEY` | optional | — | when set with URL, passed straight through |
| `QDRANT_EMBEDDING_MODEL_DIMS` | recommended | provider default 1536 | int-converted, fail-fast |
| `QDRANT_ON_DISK` | optional | `false` | truthy set: `{1,true,yes,on}` |

Never set `path` — it selects embedded local mode. `client` and `https`-forcing beyond the
URL scheme are not exposed.

**Boot-time behavior probe (new vs old fork — doctrine: validate by behavior, fail-closed
non-local):** when `MEM0_VECTOR_STORE=qdrant` and `MIMAN_ENV != local`, startup performs one
`get_memory_instance().vector_store.client.get_collections()` round-trip; on failure the
process exits non-zero with the resolved (redacted) target. This catches wrong URL/key/dims
wiring at deploy time instead of first-request time. Implemented in a FastAPI startup hook,
skipped entirely for pgvector (upstream behavior untouched).

### 5.3 Health endpoints (port of P1's healthz/readyz, unchanged semantics)

- `GET /healthz` — unauthenticated, `include_in_schema=False`, returns `{"status":"ok"}`;
  process liveness only.
- `GET /readyz` — unauthenticated; app-DB `SELECT` via `SessionLocal` (the current base's
  session factory, server/db.py); 200 `{"status":"ready"}` / 503 `{"status":"not_ready"}`.
  **Deliberately does not probe Qdrant**: a vector-store outage must degrade-open at the
  Finsor recall layer (finsor 03 §18), not flap miman out of the load balancer while the
  rest of the API is healthy. The boot probe (§5.2) plus deploy smoke test own Qdrant
  verification.
- Both added to `SKIPPED_REQUEST_LOG_PATHS` (extend main.py:58) so request-log persistence
  (main.py:270-288) stays healthcheck-noise-free.

### 5.4 Deployment stack (deploy/ profile, updated P4-P7)

```text
services:
  miman    LetA image (§6.1)      127.0.0.1:8000 only · healthcheck GET /healthz
           depends_on: qdrant(healthy), appdb(healthy)
  qdrant   qdrant/qdrant:v1.18.3-unprivileged   no host ports · /qdrant/storage volume
           (latest stable line at writing)      healthcheck GET /healthz (qdrant's own)
  appdb    postgres:18-alpine     no host ports · pgdata volume · pg_isready healthcheck
           (PG 18.4 = latest stable, 2026-05; PG19 is beta — not deployed)
```

- The dashboard is **not** part of the LetA profile — miman runs headless; admin access is
  `ADMIN_API_KEY`/admin JWT via `finmem-admin`. (CORS default `DASHBOARD_URL` stays
  untouched, main.py:159-166.)
- `appdb` is required even in qdrant mode: auth users/API keys, request logs, entities, and
  alembic migrations live there (server/db.py, models.py, alembic/). This must be stated in
  deploy/README.md — "Qdrant-native" does not mean "no Postgres".
- `.env.example` (see §9.3 for the full contract) pins `MEM0_VECTOR_STORE=qdrant`,
  `AUTH_DISABLED=false`, `MEM0_TELEMETRY=false` (server + SDK telemetry off — PostHog egress
  is not acceptable from LetA production, telemetry.py:25-27), OpenRouter base URL wiring.
- `deploy.sh` keeps the P6 flow, with one addition after `/readyz` goes green: an
  authenticated add→search→delete smoke round-trip against a scratch `user_id` (the
  behavior-level verification the old fork deferred to "a separate smoke test" —
  LETA_PATCH.md:101-103 — now made real).

**Image-version policy (standing rule):** every image in the LetA profile ships the **latest
stable release, pinned to an exact tag** (floating `:latest` stays forbidden — deploy-check
P9). Versions are re-checked at every miman release and every upstream sync; a lower version
is allowed only on a verified conflict, and the conflict must be recorded next to the pin and
in `LETA_PATCH.md`. Current pins and their status: `postgres:18-alpine` (latest stable line,
18.4 as of 2026-05; 19 beta excluded), `qdrant/qdrant:v1.18.3-unprivileged` (latest stable
line; keep server ≥ client floor §1.1), `python:3.12-slim` (**conflict pin** — upstream's
test matrix caps at 3.12, ci.yml; lifted when upstream lifts it). Versions inside
`server/requirements.txt` are upstream-owned and never bumped by LetA — they ride upstream
syncs.

### 5.5 Collection naming and embedding-dims discipline

Kept verbatim from P9 + finsor 03 §14: collection per class+env with embedding-model suffix
(e.g. `user_service_prod_finsor_memory_e3small_v1`), `_v<N>` suffix enforced by deploy-check;
an embedding-model change is a **new collection + reindex from Mongo**, never in-place.
`QDRANT_EMBEDDING_MODEL_DIMS` must match the deployed embedder (e.g. 1536 for
text-embedding-3-small); the §5.2 boot probe plus the FinMem construction probe (config →
embedder model+dim, 09C.8) both check this seam.

### 5.6 Data migration: none in miman (explicit non-goal)

Existing v2.0.2-era deployments are not upgraded in place. Mongo is authoritative
(finsor 03 §15); Qdrant/Mem0 state is rebuilt via `finmem-admin reindex` (09B.7) into a
fresh collection against a fresh miman stack. The deprecated stack stays runnable as
rollback until X-4 exit criteria pass. Anyone proposing a v2→v3 in-place data migrator is
working against doctrine.

---

## 6. Docker / CI/CD migration

### 6.1 Production image (root `Dockerfile`, port of P2)

```text
FROM python:3.12-slim          # conflict pin, not staleness: upstream tests cap at 3.12
                               # (ci.yml matrix 3.10-3.12); bump when upstream's matrix does.
                               # -slim tracks current Debian stable; no -bookworm suffix pin.
- apt: libpq5 only (psycopg>=3.2.8 runtime — server/requirements.txt:6; deprecated fix 110f5368)
- copy pyproject.toml/poetry.lock/README/LICENSE + mem0/ ; pip install .   (LOCAL tree,
  never PyPI mem0ai — upstream requirements.txt:4 is filtered out, P2 pattern)
- pip install -r server/requirements.txt (mem0ai line removed)
- copy server/ ; non-root user miman:10001 ; writable /app/history
- ENTRYPOINT: alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000
  (no --reload; migrations are idempotent and the image is the only migration runner)
- EXPOSE 8000 ; HEALTHCHECK GET /healthz (P2 parameters)
- OCI labels: source/revision/version build args (P11 pattern)
```

`.dockerignore`: port P3, updated for the new layout (`integrations/` replaces the old
per-plugin dirs; `embedchain/` no longer exists upstream — verified root listing).

### 6.2 CI — `miman-checks.yml` (new file)

Follows the repo's own convention for adding a package pipeline (miman AGENTS.md, CI
section): workflow with `workflow_call` + `workflow_dispatch`, registered in `ci-gate.yml`
(path filter + call job + `needs` entry). Path filter:

```yaml
miman:
  - 'server/**'
  - 'deploy/**'
  - 'scripts/deploy-check.sh'
  - 'scripts/release-all.sh'
  - 'Dockerfile'
  - '.dockerignore'
  - 'tests/server/**'
  - '.github/workflows/miman-checks.yml'
  - '.github/workflows/ci-gate.yml'
```

Jobs: ruff on the LetA-touched files → `pytest tests/server/test_leta_qdrant_config.py` →
`scripts/deploy-check.sh` → `docker build` smoke (no push). Editing `ci-gate.yml` is an
accepted, additive merge surface — the file's own header documents the registration pattern
(ci-gate.yml:45-88).

### 6.3 CD — `miman-cd.yml` + router registration (the tag-collision fix)

**Grounded hazard:** `release.yml` routes any published release with a bare `v*` tag to
`cd.yml` = PyPI publish of `mem0ai` (release.yml:48; cd.yml guard
`startsWith(inputs.tag, 'v') && !contains(inputs.tag, '-v')`, cd.yml:23). The deprecated
fork's `vX.Y.Z` image tags are therefore **forbidden** in miman.

- New `miman-cd.yml`: `workflow_dispatch` with `tag`/`prerelease` inputs (router
  uniformity, per AGENTS.md CD rules); validate job (tag format `miman-vX.Y.Z`, tag on
  `main`, lint+test+deploy-check — P11's validate stage) → publish job (buildx, DOCR login
  via `DIGITALOCEAN_ACCESS_TOKEN`, push `miman:miman-vX.Y.Z` + `miman:<git-sha>`, OCI
  labels, GHA cache).
- Register one arm in the router's case block, **above** the bare `v*` arm
  (release.yml:40-48): `miman-v*) workflow="miman-cd.yml" ;;`.
- `scripts/release-all.sh`: keep all P10 guards; tag becomes `miman-v${VERSION}`; it now
  creates a GitHub Release (which triggers the router) instead of a bare tag push.
- Defense in depth, no action needed: upstream's PyPI/npm OIDC trusted publishing is pinned
  to the `mem0ai/mem0` repo + workflow filenames (AGENTS.md CD notes), so an accidental
  dispatch from `LetA-Tech/miman` cannot publish packages. Leave upstream CD workflows
  untouched for merge cleanliness.

### 6.4 Upstream sync — `miman-upstream-sync.yml` (new file)

**Sync policy (Lucas, 2026-07-05 — manual-first):** the workflow is a **detector and
PR-opener only**; it never merges and it is not the sync. Every actual sync is a manual
**MS-\<tag\> lane** (standing dispatch: `docs/leta-miman/MS_SYNC_DISPATCH.md`),
P6.5-gated. Cadence is **on-demand, not calendar
churn**: instantiate an MS lane only for (a) a security fix touching our surface, (b) a
capability finsor/finmem concretely needs, or (c) periodic hygiene when drift has
accumulated (quarterly review is enough). **Stable release tags only** — never
`upstream/main`, never rc/beta/pre-release tags. The cron trigger is optional; on a
GitHub fork scheduled workflows are disabled by default, which matches this policy —
`workflow_dispatch` is the expected invocation. Workflow behavior when run:

```text
fetch upstream --tags
newest upstream release tag (bare v*, SDK line) > recorded base in LETA_PATCH.md?
  no drift            -> exit green
  drift, clean merge  -> branch sync/upstream-<tag>, merge tag, run miman-checks
                         suite, open PR with the protected-file checklist
  drift, conflict     -> fail loudly; conflicts resolved by a human/Claude session
never auto-merge; never track upstream/main
```

Protected-file review checklist embedded in the PR body (successor of the migration doc's
§12.3, corrected to real paths): `server/main.py`, `server/auth.py`, `server/db.py`,
`server/requirements.txt`, `server/alembic/**`, `mem0/configs/vector_stores/qdrant.py`,
`mem0/vector_stores/{configs.py,qdrant.py}`, `mem0/llms/openai.py`,
`mem0/embeddings/openai.py`, `mem0/memory/main.py` (infer + search signatures), root
`Dockerfile`, `deploy/**`, `scripts/**`, `.github/workflows/{release.yml,ci-gate.yml}`,
`tests/server/**`, `LETA_PATCH.md`. Every sync PR re-runs the full §9.4 suite; FinMem
fixture re-freeze is required only when the wire surface changes (09B.7).

---

## 7. FinMem SDK contract (what miman must hold stable)

FinMem is specified and owned in mcfo-finsor (09B.7/09C.8/09D); this section states the
contract **from miman's side** — what the runtime guarantees.

### 7.1 Wire surface consumed by the FinMem runtime credential (non-admin API key)

```text
POST   /memories                    add (FinMem default infer=false — D-3; scoped)
GET    /memories?user_id=…          scoped list (unscoped variant is admin-only, §3.4)
GET    /memories/{id}               get
POST   /search                      filters-wrapper only; top_k/threshold/explain/show_expired
PUT    /memories/{id}               update (supersession metadata flips — finsor 03 §16.3)
DELETE /memories/{id}               per-record delete
GET    /memories/{id}/history       history (available; not consumed v1)
GET    /healthz · GET /readyz       probes (unauthenticated)
GET    /configure                   probe step 2 — embedder model+dims (redacted response,
                                    main.py:221-228,321-323; requires runtime credential)
```

### 7.2 Admin plane (distinct credential, `finmem-admin` only — 09B.7)

`POST /configure`, unscoped `GET /memories`, `DELETE /memories` (scoped bulk), `POST /reset`,
plus reindex orchestration (Mongo→miman rebuild). The runtime Provider package cannot import
the admin package (lint-enforced, 09B.7).

### 7.3 Contract delta vs finsor 09C.8 wire list — needs a one-line doctrine ack

09C.8 lists scoped `DELETE /memories` in the FinMem (runtime) wire surface; on the new base
it is `require_admin` (main.py:527-531). Resolution options, in preference order:

1. **Adopt upstream (recommended):** the Finsor Memory Deletion Coordinator already resolves
   record `_id` sets from Mongo before touching the provider (finsor 03 §10), so per-id
   `DELETE /memories/{id}` fan-out under the runtime credential suffices; scoped bulk delete
   moves to the admin plane for DSAR/purge batch legs. No miman patch; 09C.8 fixture set
   updates at X-4 re-freeze.
2. Patch miman to relax scoped bulk-delete back to `verify_auth` — rejected by default:
   widens the patch surface and weakens upstream's blast-radius posture.

This is flagged as **X-4 exit-criteria input**, not silently decided here (finsor doctrine:
halt on contradictory contract and surface it).

### 7.4 Behavioral guarantees miman pins (regression-tested, §9.4)

- `infer=false` ⇒ exactly one record per non-system message, `event: "ADD"` (§3.5) — the
  FinMem construction probe depends on it (probe fails construction otherwise, 09C.8).
- Search accepts the filters wrapper without deprecation warnings; server defaults are the
  SDK defaults `top_k=20, threshold=0.1, rerank=false` (mem0/memory/main.py search
  signature) — retrieval parameters are Finsor recall-plan data (threshold ≥0.45 per plan,
  09C.8), never miman config.
- `/healthz`,`/readyz` never require auth, never touch Qdrant, never appear in request logs.
- Scoped reads/writes require at least one of `user_id/agent_id/run_id`
  (main.py:369-370 enforces on add; FinMem enforces scope on every call site as well).
- Error mapping: 400/404 for validation/not-found (`_client_error`, main.py:213-218), 401/403
  auth, 5xx upstream — FinMem's error model (Unknown/Unauthorized/NotFound/…, 09C.8) maps
  onto this; `X-Request-ID` (main.py:302) joins FinMem logs to miman logs.

---

## 8. Finsor / FinAI / Forge integration

- **Finsor** consumes miman exclusively through the FinMem boundary: `finmem` provider client
  (09B.7) inside the `agentmemory` service (09D); recall/capture doctrine, namespaces,
  validation, consent, deletion coordination are all Finsor-side (finsor 03) — miman is
  storage+search only. Sequencing: this spec = lane X-4 substrate work; live-provider lanes
  gate on SUB-1/2/3 + X-4 exit (LANE_TRACKER.md:45-47).
- **FinAI / Forge** integrate through the same finmem SDK and the same runtime contract.
  Isolation is by credential + scope, not by deployment: each consumer gets its own
  **non-admin API key** (upstream api_keys router) and its own `agent_id`/collection-scoping
  conventions per the finsor 03 §14 collection-naming scheme. No consumer-specific code
  exists in miman.
- A standalone FinMem gRPC service is **not** built unless a second consumer materializes —
  recorded trigger (finsor 03 §13), reaffirmed here.
- Per-consumer rate/quota isolation beyond per-key auth is out of scope v1 (upstream
  rate-limits auth endpoints only, rate_limit.py); revisit only with a concrete need.

## 9. Data models and API contracts

### 9.1 Memory record (wire shape, as serialized by the server)

`_serialize_memory` (main.py:388-401): `{id, memory, user_id, agent_id, run_id, hash,
expiration_date, metadata{...}, created_at, updated_at}` — reserved payload keys
(main.py:385) are lifted, everything else lands in `metadata`. FinMem's `ProviderSnippet`
(`ID/Content/Score/Metadata`, 09C.8) maps from search results; `AddResponse.Created` derives
from the `results[].event == "ADD"` list.

### 9.2 Request models (server-side, current base)

- `MemoryCreate` (main.py:179-188): `messages[{role,content}]`, scope ids, `metadata`,
  `expiration_date`, `infer`, `memory_type`, `prompt`. FinMem sends: messages(1), one+ scope
  id, metadata (incl. idempotency key `sha256(writer_id‖source_ref‖namespace‖content)` —
  09C.8), `infer:false` by default; `infer:true` only via explicit option + policy gate (D-3).
- `SearchRequest` (main.py:197-206): `query`, deprecated top-level ids, `filters`, `top_k`,
  `threshold`, `explain`, `show_expired`. FinMem sends `query`+`filters` (+clamped
  `top_k/threshold`).
- `MemoryUpdate` (main.py:191-194): `text`, `metadata`, `expiration_date` —
  field-presence-sensitive (uses `model_fields_set`, main.py:490).

### 9.3 Deployment environment contract (LetA profile, deploy/.env.example)

```env
# store selection — deploy-check enforces qdrant in this profile
MEM0_VECTOR_STORE=qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=<class>_<env>_<consumer>_memory_<embedder>_v1   # _v<N> enforced
QDRANT_API_KEY=                       # optional on private network
QDRANT_EMBEDDING_MODEL_DIMS=1536
QDRANT_ON_DISK=false
# auth — hard requirements in non-local
AUTH_DISABLED=false
JWT_SECRET=<openssl rand -base64 48>
ADMIN_API_KEY=<long-random; admin plane only>
# app DB (auth, request logs, entities, migrations — required even in qdrant mode)
POSTGRES_HOST=appdb / POSTGRES_PORT=5432 / POSTGRES_DB=miman_app / POSTGRES_USER / POSTGRES_PASSWORD
# LLM + embedder (OpenRouter via core env fallback — §3.2)
OPENAI_API_KEY=<openrouter key> / OPENAI_BASE_URL=https://openrouter.ai/api/v1
MEM0_DEFAULT_LLM_MODEL=…  / MEM0_DEFAULT_EMBEDDER_MODEL=…
# hygiene
MEM0_TELEMETRY=false                  # PostHog egress off (telemetry.py:25-27)
REQUEST_LOG_RETENTION_DAYS=30         # + prune-logs cron (server/Makefile:57-59)
HISTORY_DB_PATH=/app/history/history.db
MIMAN_ENV=prod                        # gates the fail-closed boot probe (§5.2)
```

`POSTGRES_COLLECTION_NAME` is intentionally absent — pgvector-only knob (main.py:112,129).

### 9.4 Regression test suite (rewrite of P12 — `tests/server/test_leta_qdrant_config.py`)

| # | Test | Asserts |
|---|---|---|
| T-1 | default unset → pgvector | provider==pgvector, upstream config byte-shape (main.py:119-131 parity) |
| T-2 | `=pgvector` → upstream parity | same as T-1 with var set |
| T-3 | `=qdrant` + URL + api_key | provider==qdrant, url+api_key passed through |
| T-4 | `=qdrant` + URL, **no api_key** | host/port decomposition, no `url` key (validator quirk §3.3) — config validates against real `QdrantConfig` |
| T-5 | `=qdrant` + host/port only | int conversion; garbage port fails fast |
| T-6 | dims + on_disk conversions | int/bool coercions; truthy-set exactness |
| T-7 | unsupported value | RuntimeError naming supported values |
| T-8 | `/healthz` | 200 `{"status":"ok"}`, no auth |
| T-9 | `/readyz` ok + failure | 200 ready / 503 not_ready on session failure |
| T-10 | `OPENAI_BASE_URL` env honored | LLM+embedder clients constructed with the env base (core path §3.2) — no server config keys involved |
| T-11 | `/search` both shapes | top-level and filters-wrapped payloads produce identical SDK `filters` argument |
| T-12 | health paths not request-logged | `_should_log_request` false for both (extends main.py:261-267) |
| T-13 | `infer=false` single-record | one user message → exactly one `ADD` result (embedder mocked) — probe contract §7.4 |
| T-14 | no `MEM0_API_KEY` in canonical config | P12 case retained |
| T-15 | boot probe fail-closed | `MIMAN_ENV=prod` + unreachable Qdrant → process refuses startup; `MIMAN_ENV=local` → warns only |

Plus one compose-based e2e in `miman-checks.yml` (nightly / manual, needs no external
creds when run with a stub embedder — else gated on OPENROUTER secret): up the §5.4 stack →
`/readyz` green → authenticated add→search→delete round-trip → down.

## 10. Sequence diagrams

### 10.1 Boot (qdrant profile, fail-closed)

```text
docker compose up
   appdb ──healthy──▶ miman entrypoint
                        │ alembic upgrade head            (app DB schema)
                        │ import server.main
                        │   ├─ auth guard: JWT_SECRET or AUTH_DISABLED  (main.py:89-93)
                        │   ├─ MEM0_VECTOR_STORE=qdrant → _build_qdrant_config()   (§5.2)
                        │   │     bad env ──▶ RuntimeError ──▶ exit 1
                        │   └─ initialize_state(DEFAULT_CONFIG)
                        │ startup hook (MIMAN_ENV != local):
                        │     qdrant get_collections() ──fail──▶ exit 1   (§5.2 probe)
                        ▼
                     uvicorn serving ──▶ /healthz 200 ──▶ compose healthy
deploy.sh: poll /healthz → poll /readyz → smoke add/search/delete → done
```

### 10.2 FinMem construction probe (09C.8, what miman must answer)

```text
finmem.New(cfg)
   ├─ GET /healthz                       → 200 {"status":"ok"}
   ├─ GET /configure   (runtime key)     → embedder {provider, model, dims} (redacted cfg)
   │       dims ≠ expected → CONSTRUCTION FAILS
   ├─ POST /memories {1 user msg, infer:false, scratch scope}
   │       results length ≠ 1 or event ≠ "ADD" → CONSTRUCTION FAILS (ForbidInfer proof)
   └─ DELETE /memories/{probe-id}        → cleanup
   cache probe result for process lifetime; breaker wraps all subsequent calls
```

### 10.3 Recall path (runtime, per finsor 03 §4 — miman's slice)

```text
Finsor FinsorMemoryHook.Recall
   └─ agentmemory service → finmem.Search
        └─ POST /search {query, filters:{user_id, agent_id, namespace…}, top_k, threshold}
             miman: verify_auth → Memory.search(query, filters=…)   (main.py:451-477)
                └─ embed query → Qdrant payload-filtered ANN → ranked results
        ◀─ {results:[{id, memory, score, metadata…}]}
   Finsor side: consent filter → decay-rank → clip → render Snippets   (not miman's concern)
```

### 10.4 Governed write (capture → provider leg)

```text
Finsor worker/service (validated, redacted, consent-checked candidate — finsor 03 §16)
   └─ finmem.Add {content, scope ids, metadata(+idempotency key), infer:false}
        └─ POST /memories → Memory.add(infer=False)
             └─ per-message embed → Qdrant upsert → history row (SQLite, HISTORY_DB_PATH)
        ◀─ {results:[{id, event:"ADD"}]}
   Mongo stays authoritative; miman/Qdrant row is the derived index    (finsor 03 §15)
Supersession later: finmem.Update → PUT /memories/{id} (metadata superseded=true)
Deletion legs:      finmem per-id → DELETE /memories/{id}; bulk/DSAR → admin plane (§7.3)
```

### 10.5 Upstream sync

```text
cron weekly → miman-upstream-sync.yml
   fetch upstream --tags → newest v* SDK release tag T
   T == LETA_PATCH.md base? ──yes──▶ exit green
   merge T into sync/upstream-T
      conflict?  ──yes──▶ red run; human/Claude resolves on the branch
      clean      ──────▶ run miman-checks suite → open PR (protected-file checklist §6.4)
   human review → merge → LETA_PATCH.md base updated → (if wire surface changed)
   finsor X-4 rider: re-freeze finmem fixtures + re-run contract suite
```

## 11. Implementation lanes

Each lane is a self-contained Claude Code dispatch: worktree off latest `main`, terse
PASS/FAIL output per acceptance item, verify-command output included. Order is binding where
noted.

**M0 — repo bootstrap** (no code):
`git remote add upstream`; branch protection on `main`; rewrite `LETA_PATCH.md` (manifest =
§4.6, base pin = `cd79fa89` + "re-pin to next upstream v-tag at first sync"); delete
stale root files that upstream removed if any diff exists (verify with
`git diff upstream-base --stat` = empty). Acceptance: clean tree identical to upstream base +
LETA_PATCH.md only.

**M1 — server patch** (after M0):
`server/main.py` selector + builders (§5.1-5.2), healthz/readyz (§5.3), log-skip extension,
startup probe (§5.2), `MIMAN_ENV`; `server/scripts/provision_service_key.py` (delta-6,
tracker DV-1); rewrite `tests/server/test_leta_qdrant_config.py` (T-1…T-15 + provisioning
cases). Constraint: additive-only edits to main.py; zero changes to handlers/auth.
Verify: `ruff check server/main.py server/scripts/provision_service_key.py tests/server/`,
`pytest tests/server/ -q`.

**M2 — image + deploy profile** (after M1):
Root `Dockerfile` + `.dockerignore` (§6.1); `deploy/{docker-compose.yml,.env.example,
deploy.sh,README.md}` (§5.4, §9.3); root `Makefile` additions (`miman-docker-build`,
`miman-deploy-check`, `miman-release-all`, `miman-test` — prefixed to avoid colliding with
upstream targets, root Makefile:1-50); `scripts/deploy-check.sh` (P9 + provider==qdrant
assert + `_v<N>`), `scripts/release-all.sh` (P10, `miman-v` prefix). (The provisioning script itself ships in
M1 — tracker DV-1; M2 wires the deploy smoke that exercises it.) Verify:
`docker build`, `bash scripts/deploy-check.sh`, compose config render, local stack up +
§9.4 e2e, and a provisioned member key getting **403** on `POST /reset` and unscoped
`GET /memories` (added to the deploy.sh smoke).

**M3 — CI/CD** (after M2):
`miman-checks.yml` + ci-gate registration (§6.2); `miman-cd.yml` + router arm (§6.3);
`miman-upstream-sync.yml` (§6.4). Verify: gate run green on a touch-PR; `workflow_dispatch`
dry-run of miman-cd validate job; sync workflow manual run reports "no drift".

**M4 — FinMem alignment** (finsor-side rider, coordinates with X-4 — not in this repo):
re-freeze finmem fixtures from a running miman `miman-v0.1.0-rc`; capability probe matrix
green; resolve §7.3 delta in 09C.8; parity report to LANE_TRACKER X-4.

**M5 — release**: `make miman-release-all VERSION=0.1.0` → router → DOCR image; deprecated
stack stays deployable until M4 exits green.

Deferred (recorded, not lost): FinMem `infer=true` option + policy gate wiring (D-3 —
finsor-side work, not miman); FinMem gRPC
service (trigger: second consumer); per-consumer quotas (§8); any change to upstream's
pgvector default; Neo4j/graph, reranker, hybrid-retrieval tuning (consumed as ranking only —
finsor 03 §13).

## 12. Acceptance criteria (migration complete when all hold)

1. `LETA_PATCH.md` names base `cd79fa89` (or newer pinned v-tag) and exactly the §4.6 KEEP
   list; `git diff <base>..main --name-only` equals that list.
2. No `/search` wrapper and no base-url forwarding exist in the patch (D-1, D-2).
3. T-1…T-15 pass; upstream's own test suite still passes untouched (`hatch run test`).
4. Compose stack boots from `deploy/` with only `.env` edits; `deploy.sh` completes including
   the add→search→delete smoke.
5. Boot fails closed (non-zero exit) on: bad `MEM0_VECTOR_STORE`, unparseable `QDRANT_URL`,
   unreachable Qdrant with `MIMAN_ENV=prod`, missing `JWT_SECRET` with auth enabled.
6. `/healthz`+`/readyz` unauthenticated, log-skipped, Qdrant-untouched.
7. Image = local patched tree (proof: image `mem0ai.__version__`+git-sha label match repo;
   no PyPI `mem0ai` layer), non-root, healthcheck present, migrations run at start.
8. `miman-v0.1.0` release routes to `miman-cd.yml` and lands in DOCR with tag+sha; a bare
   `v*` tag in this repo cannot publish an image (router arm ordering test by inspection).
9. Weekly sync workflow exists, opens PRs on drift, never auto-merges.
10. FinMem fixtures re-frozen against the rc image; construction probe (healthz → configure
    dims → infer=false single-record) green; §7.3 resolution recorded in 09C.8.
11. Telemetry egress off in the LetA profile (`MEM0_TELEMETRY=false` asserted by
    deploy-check).
12. Deprecated repo untouched; rollback documented in deploy/README.md.
13. A provisioned service key is member-role: `POST /reset` and unscoped `GET /memories`
    return 403 under it; admin ops succeed only under the admin credential (delta-6, §3.4).

## 13. Risk register

| # | Risk | Grounding | Mitigation |
|---|---|---|---|
| R-1 | Bare `v*` tag publishes to PyPI path | release.yml:48, cd.yml:23 | `miman-v*` prefix everywhere; release-all validates prefix; router arm above `v*`; OIDC pinned upstream as backstop |
| R-2 | Image silently runs PyPI mem0ai, not the patched tree | server/requirements.txt:4; dev compose force-reinstall | P2 Dockerfile pattern (filter + local install); acceptance #7 proof |
| R-3 | Qdrant URL-without-key boot failure | QdrantConfig validator, qdrant.py:31-38 | §5.2 decomposition + T-4; boot probe catches residual cases |
| R-4 | `server/main.py` merge friction on every sync | upstream churn (559-line file, active) | additive-only patch placement; protected-file checklist; sync-to-release-tags only |
| R-5 | Auth semantics shift breaks FinMem fixtures | new roles/rate-limits since v2.0.2 (auth.py) | fixtures frozen per miman release; probe fails construction, degrade-open at Finsor (03 §18) |
| R-6 | A consumer runs `infer=true` (LLM extraction on raw content) without governance | add default True (mem0/memory/main.py:727); miman deliberately unpatched (D-3) | FinMem default false; `infer=true` only via explicit option + policy gate (D-3); every consumer must enter through the FinMem boundary (finsor 03 §13) — no direct miman credentials for app code |
| R-7 | Embedding-dims mismatch vs existing collection | dims immutable in Qdrant | `_v<N>` naming (P9), dims in probe chain (§5.2, §10.2), reindex-not-migrate (§5.6) |
| R-8 | Scoped-bulk-delete contract delta unresolved | main.py:527-531 vs 09C.8 | §7.3 flagged to Lucas/X-4 — blocking for M4, not M1-M3 |
| R-9 | PostHog egress from prod | telemetry.py:25-27 default ON | profile pins false; deploy-check asserts |
| R-10 | Alembic chain breaks on future sync | 6 migrations, upstream-owned | entrypoint runs upgrade head; sync checklist includes alembic/**; never author LetA migrations |

**UNVERIFIED carried:** `mcfo-leankit` not readable this session (AgentKit facts taken from
finsor docs); DOCR registry/namespace values assumed unchanged from P11; deployed
substrate image parity = SUB-1 (substrate owner, LANE_TRACKER.md:45). (The former "v3 vs
2.0.11" open item is resolved in §1.1's version note: v3 = engine generation, verified in
code; 2.0.11 = package semver at the pin.)

---

*End of spec. Dispatch order: M0 → M1 → M2 → M3 (this repo), M4 rider in mcfo-finsor (X-4),
M5 release. Every lane cites this document; deviations return here first.*
