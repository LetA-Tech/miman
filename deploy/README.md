# miman — `/deploy/` (LetA deployment profile)

**Scope:** the runnable miman stack — miman + Qdrant + Postgres app-DB, Qdrant-native
(spec `docs/leta-miman/03-M-MeM0-detailed-spec.md` §5.4). Used both to smoke-test a
release before tagging and as the operator-run deploy on the target host.

---

## What's here

```text
deploy/
├── docker-compose.yml   # miman + qdrant + appdb
├── .env.example         # env contract (spec §9.3) — copy to .env, fill in secrets
├── deploy.sh            # build/up + health-wait + behavior smoke (add/search/delete
│                         # round-trip, member-key 403 on admin-only routes)
└── README.md            # this file
```

The root `Dockerfile` builds **the image** from the local patched tree (never PyPI
`mem0ai` — see the root `LETA_PATCH.md`). This directory runs **the stack**.

`appdb` is required even though the vector store is Qdrant: auth users, API keys,
request logs, and entities all live in Postgres via alembic-managed tables
(`server/db.py`, `server/models.py`, `server/alembic/`). "Qdrant-native" does not mean
"no Postgres."

The dashboard is **not** part of this profile — miman runs headless. Admin access is
via `ADMIN_API_KEY` or an admin user's JWT/API key (`finmem-admin` is the intended admin
client).

---

## Deploy loop

```bash
cd deploy/
cp .env.example .env
# Fill in: JWT_SECRET, ADMIN_API_KEY, POSTGRES_PASSWORD, QDRANT_COLLECTION_NAME
# (must end _v<N> — spec §5.5), OPENAI_API_KEY (+ OPENAI_BASE_URL if routing
# through OpenRouter), IMAGE_VERSION/IMAGE_REVISION for a tagged release.
bash deploy.sh
```

`deploy.sh` builds the image, brings up the stack, waits for `/healthz` and `/readyz`,
provisions a scratch member-role service key (via `server/scripts/provision_service_key.py`,
spec §3.4 delta-6), and runs the behavior smoke: authenticated add→search→delete
round-trip under that key, plus proof that the same non-admin key gets **403** on
`POST /reset` and unscoped `GET /memories` (spec §12 item 13).

Tear down:

```bash
docker compose down       # keep volumes (qdrant/appdb data)
docker compose down -v    # also wipe qdrant/appdb data
```

---

## Tagging a release

```bash
make miman-release-all VERSION=X.Y.Z
```

Pushes `main` and creates a GitHub Release tagged `miman-vX.Y.Z`, which the release
router (`release.yml`) dispatches to `miman-cd.yml` (lane M3) to build and push the
image to DOCR. **CI builds immutable images only — it does not deploy.** Point
`IMAGE_VERSION` in your `.env` at the released tag and re-run `deploy.sh` on the target
host to roll forward.

---

## Rollback

miman is a new (v3-generation) stack; it is not a drop-in replacement for the frozen
v2.0.2 fork. If a miman deployment needs to be rolled back, the fallback is the
**deprecated stack** (`mem0-v2.0-deprecated`, referenced read-only from this spec —
never modified, never deleted): redeploy its own `deploy/` profile against the same
Postgres/pgvector data it was already using. Data is not migrated in place between the
two (spec §5.6, explicit non-goal) — Qdrant/miman state is rebuilt from Mongo via
`finmem-admin reindex`, so rolling back means resuming reads/writes against the
deprecated stack's existing store, not replaying miman's Qdrant collection backward.
The deprecated stack stays deployable until the X-4 exit criteria pass (spec §11 M4).

---

## What `/deploy/` here MUST NOT do

- Publish the miman API on anything other than the VPC-private interface
  (`${MIMAN_BIND_IP}:8000`, e.g. `10.118.0.3:8000`) — **never** `0.0.0.0` or the host's
  public IP. MeM0 is internal-only; finsor reaches it across the VPC. Qdrant and Postgres
  publish no host ports at all (reachable only on the private `miman-net` bridge network).
- Run with `AUTH_DISABLED=true` outside a throwaway local smoke test.
- Send telemetry — `MEM0_TELEMETRY=false` is asserted by `scripts/deploy-check.sh`.
- Hold a tracked `.env` file — `.env` is git-ignored; `scripts/deploy-check.sh` fails the
  build if one is ever accidentally tracked.
