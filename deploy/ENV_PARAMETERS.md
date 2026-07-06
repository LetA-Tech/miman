# miman `deploy/.env` — parameter reference

Source-grounded reference for every variable in `deploy/.env.example`. Copy
`.env.example` → `.env`, fill in the mandatory ones, then run `deploy.sh`
(smoke path) or the pull+tag+`up` flow (prod path, see root `README.md`).

**Important caveat that changes several "Mandatory" cells below:**
`scripts/deploy-check.sh` only lints `deploy/.env.example` (the committed
template) — it never reads your real `deploy/.env`. So rows marked
"template-only" are guaranteed well-formed in the example file, but nothing
in this repo stops your actual `.env` from omitting or misconfiguring them —
the app just falls back to its (often silently wrong) code default at
runtime. Rows marked "runtime-enforced" instead have a real code/Compose
check (`RuntimeError`, Compose `${VAR:?err}`) that fires against your actual
`.env`.

## Store selection / Qdrant

| Var | What it is | Mandatory | Valid values | Default if unset | Notes |
|---|---|---|---|---|---|
| `MEM0_VECTOR_STORE` | Which vector store backend the SDK uses | **Template-only.** Optional in code (silently defaults `pgvector`); `deploy-check.sh` only forces `.env.example` to say `qdrant` | `qdrant`, `pgvector` | `pgvector` (empty/unset) | Trimmed+lowercased before comparison. Unsupported value (typo etc.) → `RuntimeError` at boot (`server/main.py:185-190`). **Risk:** if your real `.env` omits this or typos it, the app boots fine on pgvector against `appdb`, which has no pgvector extension installed in this compose profile — first vector op fails, not boot. |
| `QDRANT_URL` | Qdrant endpoint the app connects to | **Template-only** for the `http://qdrant:*` format check; runtime-required in the sense that omitting both this and `QDRANT_HOST`/`QDRANT_PORT` raises at boot | `http://qdrant:6333` (must stay the private compose hostname) | none — `RuntimeError` at boot if neither this nor host+port given (`server/main.py:177`) | If set without `QDRANT_API_KEY`, code decomposes it to host+port internally — the SDK's own validator rejects url-without-key (`docs/leta-miman/03-M-MeM0-detailed-spec.md:170-176`) |
| `QDRANT_COLLECTION_NAME` | Qdrant collection name | **Template-only** — the `_v<N>` suffix regex is only checked against `.env.example`; nothing stops a real `.env` from using an unversioned name | Convention: `<class>_<env>_<consumer>_memory_<embedder>_v<N>` | SDK default `"memories"` if unset | `_vN` bump is the *only* safe way to change embedding model — dims are immutable per collection, spec §5.5 (documentation convention, not code-enforced at request time). Current `.env` value `miman_local_smoke_memory_e3small_v1` is a dev/smoke name — rename before prod. |
| `QDRANT_API_KEY` | Auth key sent to Qdrant | **Runtime-enforced, presence only** — `docker-compose.yml` declares it `${QDRANT_API_KEY:?set QDRANT_API_KEY in deploy/.env}`; `deploy.sh:47-51` also pre-flight-checks it. Server code itself treats it as optional (spec §9.3 calls it "optional on private network" — that line is stale vs. this profile's actual enforcement) | any string, **no minimum length checked anywhere** | none — Compose refuses to render/start without it | Leaving it *set but empty* is the failure mode to avoid: Qdrant then demands an `Api-Key` header the app never sends → 401 loop that looks like a network bug |
| `QDRANT_EMBEDDING_MODEL_DIMS` | Vector dimensionality Qdrant stores | Recommended | Integer matching your embedder (`1536` for `text-embedding-3-small`) | SDK default `1536` | Int-converted, fails fast on garbage. Boot probe + FinMem construction probe both check this seam |
| `QDRANT_ON_DISK` | Store vectors on disk vs. in memory | Optional | Truthy set: `1`, `true`, `yes`, `on` (anything else = false) | `false` | |

## Auth

| Var | What it is | Mandatory | Valid values | Default if unset | Notes |
|---|---|---|---|---|---|
| `AUTH_DISABLED` | Disables all auth (JWT/API-key checks) | No — leave `false` outside a throwaway local run | `true` / `false` | `false` (unset → falsy) | README's own "MUST NOT" list: never `true` outside a throwaway local smoke test (`deploy/README.md:92`) |
| `JWT_SECRET` | Signs/verifies session JWTs (HS256) | **Runtime-enforced presence, unless `AUTH_DISABLED=true`** | any non-empty string — **no minimum length enforced anywhere in code**, even a 1-character secret boots successfully | none | App **refuses to boot**: `if not AUTH_DISABLED and not JWT_SECRET: raise RuntimeError(...)` (`server/main.py:90-94`), re-checked defensively in `auth.py:51-54`. The `openssl rand -base64 48` convention below is a recommendation, not something anything validates. |
| `ADMIN_API_KEY` | Legacy static admin credential (`X-API-Key` header), bypasses JWT for admin-plane routes | Optional — no hard requirement to boot, but you need *some* admin path (this key, or a JWT admin user via the setup wizard) | any string — **soft** 16-char minimum only | none | Below 16 chars (`MIN_KEY_LENGTH`, `server/main.py:48`) → boots but only logs a warning (`server/main.py:98-101`), never rejected. If neither this nor an admin user exists, server logs a startup warning that admin endpoints will 401 (`server/main.py:66-87`) |

## App DB (Postgres)

| Var | What it is | Mandatory | Valid values | Default if unset | Notes |
|---|---|---|---|---|---|
| `POSTGRES_HOST` | DB hostname | Listed for the record only — **pinned to `appdb` in `docker-compose.yml`, not read from `.env`** | — | code default `postgres` if the var were read | Must match the `appdb` service name; don't bother setting it here |
| `POSTGRES_PORT` | DB port | Same as above — pinned in compose, not read from `.env` | — | code default `5432` | |
| `POSTGRES_DB` | App DB name | Yes (compose requires it: `${POSTGRES_DB:?...}`) | any valid Postgres DB name | none — compose refuses to start without it | Bridged internally to `APP_DB_NAME` for `server/db.py`, which reads that var name, not `POSTGRES_DB` directly (compose `environment:` block does the bridging) |
| `POSTGRES_USER` | DB user | Yes (compose: `${POSTGRES_USER:?...}`) | any valid Postgres role name | none | |
| `POSTGRES_PASSWORD` | DB password | Yes (compose: `${POSTGRES_PASSWORD:?...}`) | any string — **no minimum length enforced anywhere**, presence-only check | none | Also bootstraps the `appdb` container's own Postgres superuser via the official `postgres` image's env vars. Rotating this in `.env` later does **not** change the DB's real password — Postgres only reads it on first init (see rotation note at bottom) |

## LLM + embedder

| Var | What it is | Mandatory | Valid values | Default if unset | Notes |
|---|---|---|---|---|---|
| `OPENAI_API_KEY` | Credential for the LLM/embedder provider | **Template-only** — `deploy-check.sh` only checks the key exists in `.env.example`, doesn't validate a real `.env`'s value at all | an OpenAI or OpenRouter key, matching `OPENAI_BASE_URL` | none | Boots fine even if empty/wrong — client is constructed with `api_key=None`, failure only surfaces as an upstream auth error on the **first LLM/embed call**, not at boot |
| `OPENAI_BASE_URL` | API base URL — lets you route through OpenRouter instead of OpenAI directly | No | any OpenAI-compatible base URL, e.g. `https://openrouter.ai/api/v1` or `https://api.openai.com/v1` | `https://api.openai.com/v1` (LLM client, `mem0/llms/openai.py:51`); embedder also checks legacy `OPENAI_API_BASE` first (deprecation-warned) | Honored directly by the core SDK provider constructors — no server-side forwarding code (spec §3.2) |
| `MEM0_DEFAULT_LLM_MODEL` | Default chat/completion model | No | any model string your `OPENAI_BASE_URL` provider serves, e.g. `gpt-5-mini`, `openai/gpt-5-mini` (OpenRouter routing prefix) | `gpt-4.1-nano-2025-04-14` (`server/main.py:117`) | |
| `MEM0_DEFAULT_EMBEDDER_MODEL` | Default embedding model | No | must match `QDRANT_EMBEDDING_MODEL_DIMS` | `text-embedding-3-small` (`server/main.py:118`) | Changing this on an existing collection = new collection + reindex, never in-place (§5.5) |

## Hygiene / misc

| Var | What it is | Mandatory | Valid values | Default if unset | Notes |
|---|---|---|---|---|---|
| `MEM0_TELEMETRY` | Anonymous PostHog telemetry (install UUID, email domain, version) | **Template-only** — `deploy-check.sh` requires `.env.example` to say `false`, but a real `.env` that omits this key gets telemetry **ON** with zero warning | `false`/`0`/`no`/`off` = disabled, anything else (incl. unset) = enabled | **enabled** if unset — opt-out model, upstream mem0 OSS default | Sends at most 2 events (`admin_registered`, `onboarding_completed`). Double-check this key is actually present in your real `.env`, not just the example — this is the one most likely to silently regress since the unset behavior is the opposite of what the LetA profile wants (PostHog egress not acceptable from prod, spec §9.3) |
| `REQUEST_LOG_RETENTION_DAYS` | Days of `request_logs` rows kept before `prune-logs` deletes them | No | positive integer | `30` | `prune_request_logs.py` exits with an error if non-integer or `< 1`. Pruning isn't automatic — run `make -C server prune-logs` (e.g. via cron) |
| `HISTORY_DB_PATH` | Path to the local memory-change-history sqlite file | No | any writable path inside the container | `/app/history/history.db` | **No volume is mounted for `/app/history` in `deploy/docker-compose.yml`** — history.db is currently ephemeral, wiped on container recreate, unless you add a volume for it |
| `MIMAN_ENV` | Gates the fail-closed Qdrant boot probe | No, but should be `prod` outside local dev | `prod`, `local` (or anything != `local`, treated as non-local) | unset behaves as non-local | `prod`(-like): unreachable Qdrant at boot → process exits non-zero. `local`: same probe only warns, doesn't block boot (spec §5.2) |
| `IMAGE_VERSION` | Tag for the `miman` image compose builds/runs | Yes for a real deploy | For **local build**: any string (`dev-local` is fine). For **pulling a release**: the bare version after re-tagging, e.g. `0.1.0-rc1` — NOT the full `miman-v0.1.0-rc1` release-tag string | `dev-local` | Compose service: `image: miman:${IMAGE_VERSION:-dev-local}`. `docker compose build` always rebuilds regardless of this value — the pull-based prod flow bypasses `build` entirely (see root `README.md:84-92`) |
| `IMAGE_REVISION` | Git SHA baked into OCI image labels | No | any string, conventionally a full git SHA | `dev-local` | Passed as a Docker build-arg / OCI label only — no runtime behavior depends on it |

---

## Generating the secrets

All four below are plain random strings — no provider account needed, generate
straight from the terminal with `openssl` (already on macOS/Linux, no install):

```bash
# JWT_SECRET — 48 random bytes, base64 (server/main.py:90-94 rejects boot if empty; no length check beyond that)
openssl rand -base64 48

# ADMIN_API_KEY — 32 random bytes, base64 (server/main.py:48 soft-warns under 16 chars)
openssl rand -base64 32

# QDRANT_API_KEY — 32 random bytes, base64 (docker-compose.yml hard-requires non-empty)
openssl rand -base64 32

# POSTGRES_PASSWORD — 32 random bytes, base64 (docker-compose.yml hard-requires non-empty)
openssl rand -base64 32
```

`OPENAI_API_KEY` is the one exception — it's not a generated secret, it's an
account credential from whichever provider `OPENAI_BASE_URL` points at
(OpenAI dashboard, or OpenRouter dashboard if routing through
`https://openrouter.ai/api/v1`). Nothing to `openssl` there.

One-shot to regenerate + fill all four random secrets straight into `deploy/.env`:

```bash
cd deploy
sed -i '' "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -base64 48)|" .env
sed -i '' "s|^ADMIN_API_KEY=.*|ADMIN_API_KEY=$(openssl rand -base64 32)|" .env
sed -i '' "s|^QDRANT_API_KEY=.*|QDRANT_API_KEY=$(openssl rand -base64 32)|" .env
sed -i '' "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -base64 32)|" .env
```
(`sed -i ''` is the BSD/macOS form; drop the `''` on GNU/Linux.)

Rotating any of these later: update `.env`, then `docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d` to recreate the affected containers. Rotating `POSTGRES_PASSWORD` after the `appdb` volume already exists does **not** change the DB's actual password (Postgres only reads that env var on first init) — you'd need `ALTER ROLE ... PASSWORD` inside the running DB, or wipe the volume, to actually rotate it post-init.
