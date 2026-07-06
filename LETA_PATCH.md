# LetA Patch Manifest — miman v1

LetA-owned patch layer on top of upstream `mem0ai/mem0`. This document is the
source of truth for what LetA changed and why. Anyone reviewing this repo
starts here before reading code.

**Design authority:** `docs/leta-miman/03-M-MeM0-detailed-spec.md` — every
claim below is a summary of that spec; the spec wins on conflict.

---

## Base pin

| | |
|---|---|
| Upstream base commit | `cd79fa89` (`cd79fa8914b5b1cf66daacc957d826065df57df8`) |
| Upstream package version at base | `mem0ai 2.0.11` (pyproject.toml) |
| Sync horizon (newest upstream release tag at pin time) | `v2.0.11` (upstream commit `f2532f0`, ancestor of `cd79fa89`) |
| Re-pin policy | Re-pin to the next upstream `v*` tag at the first `MS-<tag>` sync lane (never track `upstream/main`) |

`LetA-Tech/miman` **is a GitHub fork** of `mem0ai/mem0` (`fork: true`, parent
`mem0ai/mem0` — M0 finding, spec §1.2), seeded with full upstream history;
`upstream` remote added in M0. Consequences (standing facts): GitHub Actions is
disabled until the web-UI consent banner is clicked; `gh` PR commands pin
`--repo LetA-Tech/miman` (a fork can default to the parent); scheduled workflows
are disabled-by-default on forks (M3 verifies the sync cron arms).

## Release tag rule

Miman release tags are **`miman-vX.Y.Z`** only. A bare `vX.Y.Z` tag is
**forbidden** in this repo — `release.yml`'s router sends bare `v*` tags to
`cd.yml` (PyPI publish of the `mem0ai` package); reusing that scheme here
would route image releases into the Python-SDK publish path (spec §6.3).

## Patch surface (target state, spec §4.6)

```text
KEEP (rewritten for the new base)          DROP (fixed upstream, never re-add)
────────────────────────────────          ──────────────────────────────────
server: vector-store selector + builders   /search filters wrapper        (§3.1)
server: /healthz /readyz + log-skip        OPENAI_BASE_URL forwarding     (§3.2)
root Dockerfile + .dockerignore
deploy/ (compose, env, deploy.sh, README)
Makefile targets (miman-*)
scripts/deploy-check.sh, release-all.sh
server/scripts/provision_service_key.py (delta-6, §3.4 — lane M1, tracker DV-1)
.github/workflows: miman-checks.yml, miman-cd.yml (+1-line router arm)
tests/server/test_leta_qdrant_config.py (rewritten, §9.4)
LETA_PATCH.md (this file)
```

Everything else in the repo stays byte-identical to upstream — that is the
sync-cost model (spec §4.6).

## Shipped at M1 — server patch layer (spec §4.1-4.2, §5.1-5.3, §3.4)

The only Python-code delta over upstream. `server/main.py` edits are **additive**:
no existing upstream function is modified; the single existing-line change is the
`SKIPPED_REQUEST_LOG_PATHS` constant (health paths added).

| # | File | Kind | What LetA changed (spec) |
|---|---|---|---|
| L1 | `server/main.py` | M (additive) | `import urllib.parse`; env-driven vector-store selector + `_build_qdrant_vector_store_config` builder that survives the `QdrantConfig` before-validator by decomposing url-without-api_key to host/port (§5.1-5.2); `MEM0_VECTOR_STORE` unset/`pgvector` keep `DEFAULT_CONFIG` byte-identical, `qdrant` builds from `QDRANT_*`, else `RuntimeError` at boot; `GET /healthz` + `GET /readyz` (unauth, `include_in_schema=False`, readyz probes app-DB only — never Qdrant, §5.3); `MIMAN_ENV`-gated fail-closed Qdrant boot probe (§5.2); `/healthz`,`/readyz` added to `SKIPPED_REQUEST_LOG_PATHS` |
| L2 | `server/scripts/provision_service_key.py` | A (new) | Deploy-time member-credential provisioning (§3.4 delta-6, tracker DV-1). `--name --label [--rotate]`; creates a `role="member"` service user + API key via upstream `generate_api_key`; prints the full key once to stdout, never logs it; idempotent by name; zero API-surface / auth.py change |
| L3 | `tests/server/test_leta_qdrant_config.py` | A (new) | Regression suite T-1..T-17 (spec §9.4). Hermetic: mocks only, no live Postgres/Qdrant/network |

**Dropped, verified fixed upstream (not re-added):** `/search` filters wrapper
(§3.1, D-1 — regression-guarded by T-11) and `OPENAI_BASE_URL` forwarding (§3.2,
D-2 — regression-guarded by T-10). `infer` stays upstream-default; FinMem owns the
default (§3.5, D-3 — single-record invariant pinned by T-13).

## Shipped at M2 — production image + deploy profile (spec §4.3-4.4, §5.4-5.5, §6.1, §9.3, §12 items 4-7)

| # | File | Kind | What LetA changed (spec) |
|---|---|---|---|
| L4 | `Dockerfile` (root) | A (new) | Multi-stage-free image: `python:3.12-slim` (conflict pin, matches upstream `ci.yml`'s 3.10-3.12 matrix); `libpq5` runtime for bare `psycopg`; editable install (`pip install -e .`) of the **local** `mem0/` tree so `mem0.__file__` resolves under `/app` (image-provenance proof, not a site-packages copy indistinguishable from a PyPI install); `server/requirements.txt`'s `mem0ai` line filtered before install; non-root `miman:10001`; `/app/history` writable; `HEALTHCHECK GET /healthz`; `ENTRYPOINT docker/entrypoint.sh` (no `--reload`) |
| L5 | `.dockerignore` (root) | A (new) | Ports the deprecated-repo pattern to the current layout (`integrations/`, `cli/`, `mem0-ts/`, `openmemory/`, `evaluation/`, `skills/` excluded; `embedchain/` no longer exists upstream); additionally excludes `server/dashboard/` (separate Next.js app, not shipped — miman runs headless per §5.4) and the dev-only `server/dev.Dockerfile`/`server/docker-compose.yaml`/`server/init-db.sh` |
| L6 | `docker/entrypoint.sh` | A (new) | `alembic upgrade head` (idempotent) then `exec uvicorn main:app --host 0.0.0.0 --port 8000`; runs from `WORKDIR /app/server` so `alembic.ini`'s relative `script_location` and `server/db.py`'s env-driven `_build_database_url()` resolve correctly |
| L7 | `deploy/{docker-compose.yml,.env.example,deploy.sh,README.md}` | A (new) | LetA profile: `miman` + `qdrant` (`qdrant/qdrant:v1.18.2-unprivileged` — **spec's `v1.18.3-unprivileged` pin does not exist on Docker Hub; `v1.18.2-unprivileged` is the actual latest stable line as of 2026-07-05, verified by pull**) + `appdb` (`postgres:18-alpine`, confirmed `postgres (PostgreSQL) 18.4`); 127.0.0.1-only bind on miman, no host ports on qdrant/appdb, `no-new-privileges`, private bridge network, no dashboard; compose bridges `.env`'s `POSTGRES_DB` to the app's `APP_DB_NAME` env var (the app reads `APP_DB_NAME`, not `POSTGRES_DB` — that var only bootstraps the appdb container's initial database; the two must agree or the app can't find its schema) |
| L8 | `Makefile` (root) | M (additive) | `miman-test`, `miman-docker-build`, `miman-deploy-check`, `miman-release-all`, `miman-compose-config` — all prefixed, zero edits to existing targets |
| L9 | `scripts/deploy-check.sh` | A (new) | P9-style static checks: required files/executables, `miman-*` Makefile targets present, `bash -n` on all new scripts, `MEM0_VECTOR_STORE=qdrant` + `QDRANT_URL` private-service assert, `_v<N>` collection suffix, `MEM0_TELEMETRY=false`, no `MEM0_API_KEY`, no public compose binds, no `:latest` images, no tracked `.env`, `miman-v` prefix in `release-all.sh`. Read-only — reran twice, idempotent |
| L10 | `scripts/release-all.sh` | A (new) | P10 guards (version format, on `main`, clean tree, synced with `origin/main`, new tag) then `gh release create` tagged `miman-v${VERSION}` targeting `main` — a GitHub Release (not a bare tag push), since `release.yml`'s router only listens on `release: published` (spec §6.3). **Not executed this lane** (dispatch R8) |

**Image pins verified at implementation (2026-07-05):** `python:3.12-slim` (conflict pin, unchanged), `postgres:18-alpine` → `18.4` (matches spec), `qdrant/qdrant:v1.18.2-unprivileged` (spec said `v1.18.3-unprivileged`; corrected — see deviations register).

**Known gap (credentials, not code):** the live `deploy.sh` add→search→delete smoke (acceptance A4, spec §12 item 4) needs a real `OPENAI_API_KEY`/OpenRouter key for the embedder call; none was available in this session's environment and Lucas declined to paste one into chat. `deploy/.env` is fully populated (generated `JWT_SECRET`/`ADMIN_API_KEY`/`POSTGRES_PASSWORD`, valid `_v1` collection name) except that one line — filling it in and running `bash deploy/deploy.sh` is the only remaining step to close A4. Everything not requiring a live embedder call was verified: image build (A1), provenance + no-floating-install (A3), non-root (A5), deploy-check green twice (A2), `docker compose config` render, all new scripts `bash -n` clean, `miman-test` 30/30 green (no regression vs M1).

## Remaining lanes

- M3 — CI/CD (miman-checks.yml, miman-cd.yml, miman-upstream-sync.yml)

Each lane updates this file with what it actually shipped.

## Upstream sync

Sync targets **upstream release tags**, never `upstream/main`. Weekly
drift-check workflow (`miman-upstream-sync.yml`, lane M3) opens a sync PR on
drift; never auto-merges (spec §6.4).

## Cross-references

- Design spec: `docs/leta-miman/03-M-MeM0-detailed-spec.md`
- Dispatch guide: `docs/leta-miman/DISPATCH_GUIDE.md`
- Lane tracker: `docs/leta-miman/dispatch/M_LANE_TRACKER.md`
