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
| M1 | PATCH | Server patch layer: vector-store selector, healthz/readyz, boot probe, provisioning script, tests T-1..T-17 | M0 | Opus 4.8 | **yes** | MERGED (local gate; repo CI Actions pending) | [#2](https://github.com/LetA-Tech/miman/pull/2) | — |
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

**M1 server targets (now wired — verified green on this machine 2026-07-05):**

```bash
python -m ruff check server/main.py server/scripts/provision_service_key.py tests/server/
# -> All checks passed!
python -m pytest tests/server/test_leta_qdrant_config.py -q
# -> 30 passed
```

**A18 no-regression proof (M1, this machine):** full gate subset `pytest tests/
--ignore=tests/vector_stores --ignore=tests/llms --ignore=tests/embeddings` gives
**729 passed / 10 failed / 133 errors / 19 skipped** on pristine `main`, and **759
passed** (= +30, the new suite) with **identical 10 failed / 133 errors / 19 skipped**
under M1 → zero new failures. The 133 errors are a pre-existing bare-venv path issue
(`test_server_auth`/`test_server_params` do bare `import server.main` without prepending
`server/`, so `import telemetry` fails unless the full suite pre-imports it); the 10
failures are the Postgres-needing cases. Neither is introduced by M1. (Counts differ from
M0's recorded 816/56 because M0's env had `server/` importable — MA1 re-runs on the CI
image where both are moot.)

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
| 2026-07-05 | **M1 MERGED ([#2](https://github.com/LetA-Tech/miman/pull/2)).** Server patch shipped additive-only: env vector-store selector + Qdrant builder (url-without-key → host/port decomposition survives the `QdrantConfig` before-validator), `/healthz`+`/readyz`, `MIMAN_ENV`-gated fail-closed boot probe, `SKIPPED_REQUEST_LOG_PATHS` +health paths, `server/scripts/provision_service_key.py` (delta-6 member key), `tests/server/test_leta_qdrant_config.py` T-1..T-17 (30 tests green). `git diff -U0 server/main.py` = additions only + the one sanctioned SKIPPED-constant line (A20). Merged on **local gate only** (repo Actions still pending — `gh workflow list` shows only Dependency Graph + CodeQL); **MA1 must re-run the suite on CI**. Two impl notes (within spec, not deviations): boot probe raises `RuntimeError` not `SystemExit` (uvicorn aborts startup non-zero either way; `SystemExit` gets swallowed by anyio's TestClient portal — untestable); `LETA_PATCH.md` fork line corrected (Lucas-approved) to match the M0 fork ratification. Reconciled 2 uncommitted tracker entries from the main working copy (fork decision + Actions follow-up) into this PR so the carry-forward memory isn't lost. B-2 stays MR1's job; no new bridge entry (healthz/readyz shapes match spec §5.3, already disclosed B-3). |
| 2026-07-05 | **M0 finding ratified: repo IS a GitHub fork** (`fork: true`, parent mem0ai/mem0) — spec §1.2 corrected (was wrong: "not a fork" inferred from `git remote -v` alone). Kickoff pins `--repo LetA-Tech/miman` on all gh PR commands + `gh repo set-default`. M1 gains Actions-enablement P0 check + hermetic-tests requirement; M3 gains cron-arms-on-fork verification. Actions enablement (web-UI consent) = **Lucas gate, urgent** — without it M1/M2 PRs merge on local gate only and MA1 re-runs everything. |

## Follow-up candidates (one-liners; not scope for any current lane)

- Upstream-contribution candidate: admin-only `POST /users` (member creation) — replaces
  delta-6 script long-term (spec §3.4).
- FinMem `infer=true` explicit option + policy gate wiring (D-3) — finsor-side.
- Per-consumer quotas beyond per-key auth (spec §8) — needs concrete trigger.
- M1 boot probe uses the deprecated `@app.on_event("startup")` (FastAPI warns) — chosen
  because `lifespan=` would force editing the upstream `FastAPI(...)` constructor (breaks
  additive-only). Migrate to a lifespan handler if/when upstream adds one (then it's a
  one-line hook into their lifespan, still additive).
- Branch protection on `main` (Lucas, GitHub settings) — M0 do-not-touch (no API attempt made).
- **GitHub Actions enablement on the fork (Lucas, web-UI Actions tab — URGENT: blocks repo
  CI for M1+; no API path).** After clicking: `gh workflow list` must show repo workflows.
- Optional: detach repo from the fork network (GitHub Support request) — removes fork
  banner/PR-default hazards permanently; only worth it if fork limits keep biting.
- `ci.yml`'s `pip install -e ".[test,graph,vector_stores,llms,extras]"` references a `graph`
  extra that doesn't exist in `pyproject.toml` (pip silently no-ops on it — harmless but
  stale); worth a one-line cleanup in a lane that's already touching `.github/**` (M0 found
  this, `.github/**` is a wall for M0 itself).
