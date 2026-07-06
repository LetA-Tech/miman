# miman

LetA's private memory-layer service — a patched, single-purpose deployment of
[Mem0](https://github.com/mem0ai/mem0) (self-hosted OSS core) backed by Qdrant
+ Postgres, running headless as an internal HTTP service for LetA's agent
stack (`finsor`/`finmem` consumers).

This repo is a fork of `mem0ai/mem0`. Nearly everything in it is upstream
Mem0 code, kept byte-identical to make future syncs cheap. LetA's own changes
are a thin patch layer documented in **[`LETA_PATCH.md`](LETA_PATCH.md)**
(source of truth for *what* changed) and
**[`docs/leta-miman/03-M-MeM0-detailed-spec.md`](docs/leta-miman/03-M-MeM0-detailed-spec.md)**
(design authority for *why* — wins on conflict with any summary, including
this README).

## What it is

- Base: `mem0ai/mem0` pinned at commit `cd79fa89` (`mem0ai` 2.0.11).
- Runs as a single FastAPI service (`server/`) + Qdrant (vectors) + Postgres
  (auth, API keys, request logs, alembic migrations) — no dashboard, no
  multi-tenant SaaS surface. One deployment per environment.
- Consumers (e.g. finsor/finmem) talk to it over HTTP with a per-consumer
  `X-API-Key`; there's no public sign-up path — keys are minted at deploy
  time, not through the API.

## How it works

- `server/main.py` (patched, additive-only over upstream): env-driven vector
  store selector. Unset or `pgvector` keeps upstream's default config
  byte-identical; `MEM0_VECTOR_STORE=qdrant` builds a `QdrantConfig` from
  `QDRANT_*` env vars; anything else fails closed at boot.
- `GET /healthz` / `GET /readyz` — unauthenticated, excluded from request
  logging. `/readyz` checks the app DB only, never Qdrant.
- Auth: JWT + per-consumer `X-API-Key`, resolved server-side to a
  `role="member"` service user. Member keys 403 on admin-only routes
  (`POST /reset`, unscoped `GET /memories`, etc.), which are gated by a
  separate `ADMIN_API_KEY`.
- `server/scripts/provision_service_key.py` — the only way to mint a member
  key. Deploy-time only (`docker compose exec`), idempotent by consumer
  name, prints the key once, never logs it.
- LLM/embedder calls go through OpenRouter via `OPENAI_API_KEY` +
  `OPENAI_BASE_URL` (plain upstream Mem0 config, no patch needed).

## What you need to deploy

Copy `deploy/.env.example` to `deploy/.env` and fill in:

| Variable | Purpose |
|---|---|
| `MEM0_VECTOR_STORE`, `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION_NAME`, `QDRANT_EMBEDDING_MODEL_DIMS` | Vector store config — this profile always runs `qdrant` mode |
| `AUTH_DISABLED`, `JWT_SECRET`, `ADMIN_API_KEY` | Auth — `AUTH_DISABLED=false` requires `JWT_SECRET` set or the server refuses to boot |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | App DB — required even in Qdrant mode (auth/keys/logs/migrations live here) |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MEM0_DEFAULT_LLM_MODEL`, `MEM0_DEFAULT_EMBEDDER_MODEL` | LLM/embedder, routed through OpenRouter |
| `MIMAN_ENV` | `prod` (default) fails closed if the Qdrant boot probe errors; `local` only warns |
| `IMAGE_VERSION`, `IMAGE_REVISION` | Image tag to build/pull |

Generate secrets with `openssl rand -base64 32` (keys) / `48` (`JWT_SECRET`).
Never commit `deploy/.env`.

## Deploy

**Local build + smoke test:**
```bash
cp deploy/.env.example deploy/.env   # fill in secrets first
./deploy/deploy.sh
```
Builds the compose stack, waits for `/healthz`/`/readyz`, provisions a scratch
member key, and runs an add→search→delete round trip plus the two admin-403
checks.

**Cut a release:**
```bash
scripts/release-all.sh <X.Y.Z>
```
Tags and pushes `miman-vX.Y.Z`, cuts a GitHub Release. The release router
(`release.yml`) dispatches `miman-cd.yml`, which builds and pushes the image
to DigitalOcean Container Registry
(`registry.digitalocean.com/leta-container-registry/miman`).

> Tag prefix matters: `miman-vX.Y.Z` routes to this repo's image release.
> A bare `vX.Y.Z` tag routes to upstream's PyPI publish path instead — never
> use it here.

**Run a published image without rebuilding:**
```bash
docker pull registry.digitalocean.com/leta-container-registry/miman:miman-vX.Y.Z
docker tag registry.digitalocean.com/leta-container-registry/miman:miman-vX.Y.Z miman:X.Y.Z
IMAGE_VERSION=X.Y.Z docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
```
`docker-compose.yml`'s `miman` service has both `build:` and `image:` —
compose only builds if the tagged image isn't already present locally, so
pre-tagging the pulled image skips the rebuild.

**Provision a runtime key for a consumer:**
```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env exec -T miman \
  python -m scripts.provision_service_key --name <consumer> --label <label> --rotate
```

## Docs

- [`docs/leta-miman/03-M-MeM0-detailed-spec.md`](docs/leta-miman/03-M-MeM0-detailed-spec.md) — design authority for the LetA patch layer.
- [`LETA_PATCH.md`](LETA_PATCH.md) — what changed vs. upstream and why, file by file.

## Upstream sync

`upstream` remote points at `mem0ai/mem0`. This repo does **not** track
`upstream/main` automatically — updates come in as reviewed PRs that
cherry-pick specific upstream commits, re-pinning `LETA_PATCH.md`'s base
commit at each sync. Everything outside the patch surface listed in
`LETA_PATCH.md` is expected to stay byte-identical to upstream, which is what
keeps that cherry-pick path cheap.

## License

Apache-2.0 (inherited from `mem0ai/mem0` — see [`LICENSE`](LICENSE)).
