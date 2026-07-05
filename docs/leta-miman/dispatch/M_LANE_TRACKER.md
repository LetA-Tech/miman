# M_LANE_TRACKER — miman track (carry-forward memory; update in the same PR as your lane)

**Authority:** `docs/leta-miman/03-M-MeM0-detailed-spec.md` (@ base `cd79fa89`) ·
`docs/leta-miman/DISPATCH_GUIDE.md` · finsor `CROSS_SESSION_BRIDGE.md` (BINDING).
**Doc home (recorded adaptation):** all LetA docs live under `docs/leta-miman/` (Lucas
move, 2026-07-05) — NOT `docs/dispatch/` as the guide's pre-move text says, and NOT in the
upstream Mintlify `docs/` tree (keeps sync friction zero and the llms-txt gate untouched).

## Plan of record (wave order — strictly sequential; one lane = one session = one PR)

```text
M0 ──▶ M1 ──▶ M2 ──▶ M3 ──▶ MA1 (wave audit) ──▶ MR1 (miman-v0.1.0-rc) ──▶ bridge B-2
                                                        └─ recurring: MS-<tag> sync lanes
M4 is NOT a miman lane (finsor/finmem rider; miman only signals via bridge B-2).
```

Rationale for strict sequencing: M1/M2 are file-disjoint but behavior-coupled (M2's
healthcheck and e2e need M1's `/healthz` merged); lanes are small, so parallelism buys
nothing and risks audit noise.

## Lane register

| Lane | Taxonomy | Title | Depends | Model | P6.5 | Status | PR | Audit |
|---|---|---|---|---|---|---|---|---|
| M0 | INFRA | Repo bootstrap: upstream remote, LETA_PATCH.md v1, CI-gate reality check | — | Sonnet 5 | no | MERGED | [#1](https://github.com/LetA-Tech/miman/pull/1) | — |
| M1 | PATCH | Server patch layer: vector-store selector, healthz/readyz, boot probe, provisioning script, tests T-1..T-15 | M0 | Opus 4.8 | **yes** | PENDING | — | — |
| M2 | INFRA | Prod image + deploy profile: Dockerfile, entrypoint, compose, env, deploy.sh smokes, Makefile targets, deploy/release scripts | M1 | Sonnet 5 | no | PENDING | — | — |
| M3 | RELEASE-infra | CI/CD: miman-checks.yml (+ci-gate reg), miman-cd.yml (+router arm), miman-upstream-sync.yml | M2 | Sonnet 5 | no | PENDING | — | — |
| MA1 | AUDIT | Fresh-session code-grounded wave audit (spec-vs-diff, full §12 acceptance sweep) | M3 | Opus 4.8 | no | PENDING | — | — |
| MR1 | RELEASE | Cut `miman-v0.1.0-rc1`: release-all → router → DOCR; then bridge B-2 signal | MA1 | Sonnet 5 | no | PENDING | — | — |
| MS-<tag> | SYNC | Recurring upstream sync (instantiate `MS_TEMPLATE.md` per upstream release tag) | MR1 | Opus 4.8 | **yes** | recurring | — | — |

## CI gate (D3-style — VERIFIED by M0 against repo reality; M1 wires the server/-specific targets)

**Env bootstrap (verified on this machine 2026-07-05 — no `hatch` binary available; Homebrew
ships `python3.11` directly, which is what `hatch shell dev_py_3_11` would target anyway):**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pip install -r server/requirements.txt
pip install ruff
```

**Lint (verified green):**

```bash
ruff check .
# -> All checks passed!
```

**Test — repo-reality proof, upstream's existing subset (verified):**

```bash
pytest tests/ --ignore=tests/vector_stores --ignore=tests/llms --ignore=tests/embeddings
# -> 816 passed, 19 skipped, 56 failed in ~45s
```

The 56 failures are all `TestAuthEnabled` cases in `tests/test_server_auth.py` — traced to
`sqlalchemy.engine.raw_connection()` trying to reach `postgresql+psycopg://...@postgres:5432/
mem0_app` (the docker-compose service hostname). Not an env-bootstrap defect: those tests need
a live Postgres (`docker-compose up` from `server/`), unavailable in a bare venv. The three
excluded dirs (`tests/vector_stores`, `tests/llms`, `tests/embeddings`) fail to *collect*
without optional per-provider packages (chromadb, weaviate, google-cloud-aiplatform, etc.) —
this mirrors upstream's own `ci.yml`, which installs the fuller
`pip install -e ".[test,graph,vector_stores,llms,extras]"` before running the full suite.

**Repo-reality finding (upstream `ci.yml` drift, out of scope — `.github/**` is a wall):**
that install line references a `graph` extra that does not exist in `pyproject.toml`
(`nlp`/`vector-stores`/`llms`/`extras`/`test`/`dev` are the only groups). Confirmed via
`pip install -e ".[graph]" --dry-run` — pip silently no-ops on the unknown extra rather than
erroring, so `ci.yml` isn't broken by this, just carrying a stale extra name. Recorded as a
follow-up candidate below, not fixed here.

**Not runnable yet (M1 deliverables — files don't exist on this base):**

```bash
python -m ruff check server/main.py server/scripts/provision_service_key.py tests/server/
python -m pytest tests/server/test_leta_qdrant_config.py -q
```

**From M2 onward:**

```bash
docker build -t miman:gate .
bash scripts/deploy-check.sh
```

## Accepted-deviations register (PROPOSED by lanes → Lucas ratifies; never self-ratified)

| # | Deviation vs spec 03-M | Proposed by | Status |
|---|---|---|---|
| DV-1 | `provision_service_key.py` moves lane M2 → M1 and lives at `server/scripts/` (PATCH taxonomy: imports server models, needs pytest coverage; mirrors upstream `server/scripts/reset_admin_password.py`; keeps M2 pure INFRA) | dispatch pack (architect) | RATIFIED at pack creation — spec §3.4/§4.6/§11 updated to match |
| DV-2 | Spec §11 "M5 — release" renamed lane **MR1**; **M5/MS = upstream-sync cadence** per DISPATCH_GUIDE lane organization (guide is dispatch authority) | dispatch pack (architect) | RATIFIED at pack creation |

## Decision log

| Date | Decision |
|---|---|
| 2026-07-05 | Dispatch pack created (tracker, kickoff, M0-M3, MA1, MR1, MS template). Guide adopted; canonical home `docs/leta-miman/`. Bridge adoption note appended. |
| 2026-07-05 | Base branch convention: **`main`** (miman has no dev line; upstream-history repo). Auto-merge (squash) on green — same Lucas authorization as finsor. |
| 2026-07-05 | B-4 status at pack creation: PROPOSED in bridge, awaiting finsor/Lucas confirm. M1 proceeds (script is miman-internal); consumer env naming (FINMEM_*) is the only pending piece — M1 P0 re-checks the bridge. |
| 2026-07-05 | M0 merged (PR #1): `upstream` remote wired, `LETA_PATCH.md` v1 created, CI-gate verified (no hatch on this machine — `python3.11` venv path proven instead). M1 unblocked. |

## Follow-up candidates (one-liners; not scope for any current lane)

- Upstream-contribution candidate: admin-only `POST /users` (member creation) — replaces
  delta-6 script long-term (spec §3.4).
- FinMem `infer=true` explicit option + policy gate wiring (D-3) — finsor-side.
- Per-consumer quotas beyond per-key auth (spec §8) — needs concrete trigger.
- Branch protection on `main` (Lucas, GitHub settings) — M0 do-not-touch (no API attempt made).
- `ci.yml`'s `pip install -e ".[test,graph,vector_stores,llms,extras]"` references a `graph`
  extra that doesn't exist in `pyproject.toml` (pip silently no-ops on it — harmless but
  stale); worth a one-line cleanup in a lane that's already touching `.github/**` (M0 found
  this, `.github/**` is a wall for M0 itself).
