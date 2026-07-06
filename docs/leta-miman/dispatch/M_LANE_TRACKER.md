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
| M0 | INFRA | Repo bootstrap: upstream remote, LETA_PATCH.md v1, CI-gate reality check | — | Sonnet 5 | no | MERGED | [#1](https://github.com/LetA-Tech/miman/pull/1) | MA1 PASS |
| M1 | PATCH | Server patch layer: vector-store selector, healthz/readyz, boot probe, provisioning script, tests T-1..T-17 | M0 | Opus 4.8 | **yes** | MERGED (local gate; repo CI Actions pending) | [#2](https://github.com/LetA-Tech/miman/pull/2) | MA1 PASS (additive-only re-verified; 30 tests green) |
| M2 | INFRA | Prod image + deploy profile: Dockerfile, entrypoint, compose, env, deploy.sh smokes, Makefile targets, deploy/release scripts | M1 | Sonnet 5 | no | MERGED (A4 closed) | [#4](https://github.com/LetA-Tech/miman/pull/4) + [#5](https://github.com/LetA-Tech/miman/pull/5) | MA1 PASS (image rebuilt, provenance re-proven) |
| M3 | RELEASE-infra | CI/CD: miman-checks.yml (+ci-gate reg), miman-cd.yml (+router arm), miman-upstream-sync.yml | M2 | Sonnet 5 | no | MERGED (real CI green — Actions is now enabled on the fork) | [#8](https://github.com/LetA-Tech/miman/pull/8) | MA1 PASS (router arm + sync re-read) |
| MA1 | AUDIT | Fresh-session code-grounded wave audit (spec-vs-diff, full §12 acceptance sweep) | M3 | Opus 4.8 | no | MERGED — **`MR1 UNBLOCKED`** (0 BLOCKERs, 6 MINORs → follow-ups); findings: [`MA1_FINDINGS.md`](./MA1_FINDINGS.md) | [#10](https://github.com/LetA-Tech/miman/pull/10) | — |
| MR1 | RELEASE | Cut `miman-v0.1.0-rc1`: release-all → router → DOCR; then bridge B-2 signal | MA1 | Sonnet 5 | no | **RELEASED** — tag `miman-v0.1.0-rc1` published, image in DOCR, bridge B-2 SIGNALED | — | — |
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

**From M2 onward (verified green on this machine 2026-07-05):**

```bash
docker build -t miman:gate .
# -> Successfully tagged miman:gate
bash scripts/deploy-check.sh
# -> deploy-check: ok  (run twice — idempotent)
```

Additional M2 verification: `make miman-docker-build VERSION=0.0.0-audit` (A1) green;
`docker run --rm --entrypoint python miman:0.0.0-audit -c "import mem0; print(mem0.__file__)"`
→ `/app/mem0/__init__.py` (A3, editable install resolves under `/app`, not site-packages);
`docker history miman:0.0.0-audit --no-trunc | grep -c "pip install.*mem0ai"` → `0` (A3);
`docker run --rm --entrypoint id miman:0.0.0-audit` → `uid=10001(miman) gid=10001(miman)`
(A5); `docker compose -f deploy/docker-compose.yml config` renders clean; `bash -n` on all
new scripts clean; `make miman-test` → 30 passed (no regression vs M1).
**A4 (live add→search→delete + member-key 403 pair) NOT run** — needs a real
OpenAI/OpenRouter key for the embedder call, none available in-session; see decision log.

**M3 (verified 2026-07-06 — real GitHub Actions run, not local-only, for the first time this
track — see decision log for the Actions-enablement finding):**

```bash
actionlint .github/workflows/miman-checks.yml .github/workflows/miman-cd.yml \
  .github/workflows/miman-upstream-sync.yml .github/workflows/release.yml \
  .github/workflows/ci-gate.yml
# -> (no output, exit 0)
```

PR #8's own CI Gate ran for real and went green, including all four new `miman` jobs
(Ruff, LetA regression suite, Deploy-check, Docker build smoke) —
https://github.com/LetA-Tech/miman/actions/runs/28768684375 (A1).

Post-merge dry-runs against `main` (A4):
- `gh workflow run miman-cd.yml -f tag=miman-v0.0.0-dry -f prerelease=false` →
  `validate` job fails fast at checkout (`A branch or tag with the name 'miman-v0.0.0-dry'
  could not be found`), `publish` job correctly skipped — proves the `needs:` gate and the
  `startsWith(inputs.tag, 'miman-v')` guard both work
  (https://github.com/LetA-Tech/miman/actions/runs/28768830617).
- `gh workflow run miman-upstream-sync.yml` → green, logged `Recorded base
  (LETA_PATCH.md): v2.0.11` / `Newest upstream release tag: v2.0.11` / `no drift: recorded
  base is already at or ahead of upstream's newest release tag`
  (https://github.com/LetA-Tech/miman/actions/runs/28768847439).

R6 grep-proof: `grep -niE "pypi|npm publish|npmjs|twine|hatch publish"
.github/workflows/miman-*.yml` → no matches. A3: `miman-v*) workflow="miman-cd.yml" ;;` at
`release.yml:48`, bare `v*)` at `release.yml:49`.

`DIGITALOCEAN_ACCESS_TOKEN`: confirmed absent (`gh secret list --repo LetA-Tech/miman` →
empty), independent of the now-resolved Actions-enablement blocker. `miman-cd.yml`'s
`publish` job fails fast with a clear message if dispatched before the secret exists — the
first real (non-dry) release will need this from Lucas before MR1.

## Accepted-deviations register (PROPOSED by lanes → Lucas ratifies; never self-ratified)

| # | Deviation vs spec 03-M | Proposed by | Status |
|---|---|---|---|
| DV-1 | `provision_service_key.py` moves lane M2 → M1 and lives at `server/scripts/` (PATCH taxonomy: imports server models, needs pytest coverage; mirrors upstream `server/scripts/reset_admin_password.py`; keeps M2 pure INFRA) | dispatch pack (architect) | RATIFIED at pack creation — spec §3.4/§4.6/§11 updated to match |
| DV-2 | Spec §11 "M5 — release" renamed lane **MR1**; **M5/MS = upstream-sync cadence** per DISPATCH_GUIDE lane organization (guide is dispatch authority) | dispatch pack (architect) | RATIFIED at pack creation |
| DV-3 | Spec §5.4/§12 pin `qdrant/qdrant:v1.18.3-unprivileged` — **that tag does not exist** (confirmed via Docker Hub tag list + `docker pull` 404). Substituted `v1.18.2-unprivileged`, the actual latest stable line as of 2026-07-05 (verified pull + policy re-check per §5.4's own "re-check latest stable at implementation" clause) | M2 | PROPOSED |
| DV-4 | Spec §12's env table lists `QDRANT_API_KEY` as `optional` ("optional on private network"). Live A4 run proved blank-but-set breaks qdrant auth (env-var-present-with-empty-value ≠ unset, from qdrant's config loader's perspective) while the app sends no header at all when its own copy is empty — a 401 loop, not graceful no-auth. Made it **mandatory** in this deploy profile (`${QDRANT_API_KEY:?...}`, same as the other generated secrets) instead of trying to make "blank" mean "no auth" end-to-end | M2 fixup | PROPOSED |

## Decision log

| Date | Decision |
|---|---|
| 2026-07-05 | Dispatch pack created (tracker, kickoff, M0-M3, MA1, MR1, MS template). Guide adopted; canonical home `docs/leta-miman/`. Bridge adoption note appended. |
| 2026-07-05 | Base branch convention: **`main`** (miman has no dev line; upstream-history repo). Auto-merge (squash) on green — same Lucas authorization as finsor. |
| 2026-07-05 | B-4 status at pack creation: PROPOSED in bridge, awaiting finsor/Lucas confirm. M1 proceeds (script is miman-internal); consumer env naming (FINMEM_*) is the only pending piece — M1 P0 re-checks the bridge. |
| 2026-07-05 | M0 merged (PR #1): `upstream` remote wired, `LETA_PATCH.md` v1 created, CI-gate verified (no hatch on this machine — `python3.11` venv path proven instead). M1 unblocked. |
| 2026-07-05 | **M1 MERGED ([#2](https://github.com/LetA-Tech/miman/pull/2)).** Server patch shipped additive-only: env vector-store selector + Qdrant builder (url-without-key → host/port decomposition survives the `QdrantConfig` before-validator), `/healthz`+`/readyz`, `MIMAN_ENV`-gated fail-closed boot probe, `SKIPPED_REQUEST_LOG_PATHS` +health paths, `server/scripts/provision_service_key.py` (delta-6 member key), `tests/server/test_leta_qdrant_config.py` T-1..T-17 (30 tests green). `git diff -U0 server/main.py` = additions only + the one sanctioned SKIPPED-constant line (A20). Merged on **local gate only** (repo Actions still pending — `gh workflow list` shows only Dependency Graph + CodeQL); **MA1 must re-run the suite on CI**. Two impl notes (within spec, not deviations): boot probe raises `RuntimeError` not `SystemExit` (uvicorn aborts startup non-zero either way; `SystemExit` gets swallowed by anyio's TestClient portal — untestable); `LETA_PATCH.md` fork line corrected (Lucas-approved) to match the M0 fork ratification. Reconciled 2 uncommitted tracker entries from the main working copy (fork decision + Actions follow-up) into this PR so the carry-forward memory isn't lost. B-2 stays MR1's job; no new bridge entry (healthz/readyz shapes match spec §5.3, already disclosed B-3). |
| 2026-07-05 | **M0 finding ratified: repo IS a GitHub fork** (`fork: true`, parent mem0ai/mem0) — spec §1.2 corrected (was wrong: "not a fork" inferred from `git remote -v` alone). Kickoff pins `--repo LetA-Tech/miman` on all gh PR commands + `gh repo set-default`. M1 gains Actions-enablement P0 check + hermetic-tests requirement; M3 gains cron-arms-on-fork verification. Actions enablement (web-UI consent) = **Lucas gate, urgent** — without it M1/M2 PRs merge on local gate only and MA1 re-runs everything. |
| 2026-07-05 | Pre-M2 session start: local `main` had diverged (one unpushed doc commit sitting on the pre-M1 base instead of on `origin/main`'s M1 merge). Diffed before acting — 4 of 5 touched files were byte-identical to what PR #2 already reconciled in, the 5th (this tracker) was strictly stale. `git reset --hard origin/main` (Lucas-confirmed) brought local `main` to `02a18840` (M1 merged) with no unique content lost. Separately found an undocumented `dev` branch on the fork (PR #3, "M1 → dev...") — not part of any doctrine here (`main` is the only integration branch per the decision above); content-identical mirror of `main`'s M0+M1 via raw re-commits, not a merge. Left untouched; flagged to Lucas, no action taken pending his call on its purpose. |
| 2026-07-05 | **M2 MERGED ([#4](https://github.com/LetA-Tech/miman/pull/4)).** Shipped root `Dockerfile`+`.dockerignore` (editable local install for provenance-checkability — `mem0.__file__` resolves under `/app`, not a site-packages copy indistinguishable from a PyPI install), `docker/entrypoint.sh` (alembic-then-uvicorn), `deploy/{docker-compose.yml,.env.example,deploy.sh,README.md}`, `miman-*` Makefile targets, `scripts/{deploy-check,release-all}.sh`. Qdrant pin corrected `v1.18.3`→`v1.18.2-unprivileged` (DV-3, spec's tag doesn't exist). **A4 (live add→search→delete + member-key 403 smoke) not run this lane** — blocked on a real embedder API key; Lucas declined to paste one into chat and none was present in the session environment. `deploy/.env` is fully populated (generated secrets, valid `_v1` collection name) except `OPENAI_API_KEY`; filling that one line and running `bash deploy/deploy.sh` is the only step left to close A4 — tracked as a follow-up below, not silently dropped. Everything else verified with command output (A1,A2,A3,A5,A6; see CI gate section above). Local docker environment also needed two host-level fixes this session (Lucas-approved): Colima's docker disk was 100% full (110 of 111 volumes dangling, unrelated to miman) — full `docker system prune -a --volumes -f` reclaimed 16.68GB; `~/.docker/config.json` had `credsStore: desktop` pointing at a missing Docker Desktop binary, breaking all pulls — removed the key. Neither touches repo state. |
| 2026-07-06 | Local working tree was found checked out on the undocumented `dev` branch (see 2026-07-05 finding above) instead of `main`, with pre-existing uncommitted deletions of unrelated repo files (`marketplace.json` ×4, `LICENSE`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`) — same anomaly, still untouched. Stashed those deletions (`git stash push -u`, not dropped) and switched back to `main`; M2's merged state was intact on `main` throughout, only the local checkout's branch pointer was wrong. Root cause of the checkout drift not identified this session — flagged as a follow-up below. |
| 2026-07-06 | **M2 fixup MERGED ([#5](https://github.com/LetA-Tech/miman/pull/5)).** Lucas supplied a real `OPENAI_API_KEY` directly into `deploy/.env` (never in chat). First `deploy.sh` run surfaced three real bugs (not local-env noise), all fixed: `appdb` (postgres:18-alpine) mount path for pg18's new data-dir layout, `qdrant` healthcheck rewritten for the `-unprivileged` image (no wget/curl, `/bin/sh` is dash not bash — needs explicit `bash -c` + `/dev/tcp`), `QDRANT_API_KEY` made mandatory (DV-4 — blank-but-set broke qdrant auth against the app's no-header-when-empty behavior). Also caught and reverted a bad edit to `.env.example`'s model IDs (that file is an OpenRouter-flavored reference — `openai/`-prefixed model IDs are correct there; only the live, native-OpenAI-targeting `.env` needed bare model IDs). Full `deploy.sh` run green end to end: A4 now PASSES (add→search→delete + both member-key 403s). |
| 2026-07-06 | **GitHub Actions is now enabled on the fork** (finding, not a miman change — Lucas clicked the web-UI consent banner between the M2 fixup and this M3 session). Discovered when M3's own PR (#8) triggered a real `CI Gate` run instead of nothing: `gh workflow list` now shows the repo's own workflows (`CI Gate`, `ci`, `miman checks`, etc.) alongside the default Dependency Graph/CodeQL, where M0-M2 only ever saw the latter two. This **resolves the M0-tracked "GitHub Actions enablement" urgent follow-up** — moved out of the follow-up list below. Consequence for MA1: the wave audit can now re-run the M1/M2 suites via real CI instead of only local-gate re-verification. |
| 2026-07-06 | **MA1 wave audit complete — verdict `MR1 UNBLOCKED`** ([#10](https://github.com/LetA-Tech/miman/pull/10)). Fresh Opus session + one adversarial Opus subagent. Full §12 sweep: 12 in-scope items PASS, item 10 N/A (M4 finsor rider, post-MR1). Zero BLOCKERs. Independent re-verification (not trusting recorded numbers): 30-test M1 suite green; 759-vs-759 no-regression re-run (zero new failures); image **rebuilt from scratch** — `mem0.__file__`=`/app`, 0 PyPI mem0ai layers, `uid=10001`, OCI revision=HEAD; boot fail-closed matrix exercised **live** at import (3 RuntimeErrors + JWT guard); router arm / R6 no-publish grep / deploy-check asserts / sync workflow all re-read at file:line; `server/auth.py` byte-identical to upstream (admin gating unweakened). 6 MINOR findings filed above (F1-F6), all doc/cosmetic, none block the release. Live add→search→delete + member-key 403 pair NOT re-spent this session (recorded green in M2-fixup PR #5; avoids re-billing Lucas's OpenAI key — code+config+recorded chain complete). MR1 remaining gate: `DIGITALOCEAN_ACCESS_TOKEN` before the non-dry publish. |
| 2026-07-06 | **MR1 RELEASED — `miman-v0.1.0-rc1` cut, published, verified end to end; bridge B-2 SIGNALED.** Lucas added the `DIGITALOCEAN_ACCESS_TOKEN` repo secret (confirmed via `gh secret list`, no org-level/environment fallback existed — genuinely blocking until set). `make miman-release-all VERSION=0.1.0-rc1` green (deploy-check passed, tag/release published: https://github.com/LetA-Tech/miman/releases/tag/miman-v0.1.0-rc1). Release Router correctly dispatched `miman-cd.yml` (not `cd.yml`) — run [28798742332](https://github.com/LetA-Tech/miman/actions/runs/28798742332). Publish run [28798749670](https://github.com/LetA-Tech/miman/actions/runs/28798749670) green: validate (ruff+pytest+deploy-check) → build → push. Image landed in DOCR: `registry.digitalocean.com/leta-container-registry/miman:miman-v0.1.0-rc1` + `:25fe5c2947d8234c6fd054c2e54de361f71fc820`, digest `sha256:4498d13594309c5c67f49daa3272fcb15c5c34a222beddc43455fc811a9fc7db` — confirmed twice: once from the CI push log, once independently via local `doctl registry login` + `docker pull` of both tags (identical digest both times). Pull-and-boot verification (spec §12 item 4, against the **published** image, not a rebuild): tagged the pulled image to satisfy the compose `image:` reference so `up` used it directly with no build step; `/healthz` + `/readyz` green; live add→search→delete round-trip + both member-key 403s (`POST /reset`, unscoped `GET /memories`) all passed against real OpenAI embedder calls. Bridge B-2 appended (image ref/digest, compose profile path, provisioning command, `MIMAN_ENV` note) and its open-items row flipped to SIGNALED — X-4/M4 unblocked on finsor's side. Full local teardown after verification, Lucas-directed: `docker compose down -v`, `docker system prune -a --volumes -f`, `docker volume prune -a -f` (caught one unrelated leftover volume from another project) — final state 0 containers/images/volumes/build-cache. No deployment to any LetA host performed (out of scope, platform-repo concern) — Lucas deploys separately by logging into the server directly. No code changes this lane (RELEASE lane, tracker-only diff). |
| 2026-07-06 | **M3 MERGED ([#8](https://github.com/LetA-Tech/miman/pull/8)).** Shipped `miman-checks.yml` (ruff → pytest → deploy-check → docker build, chained via `needs:`), `ci-gate.yml` registration (`miman` filter/call-job/needs entry, additive), `miman-cd.yml` (`workflow_dispatch` tag/prerelease inputs, `validate`→`publish`, doctl DOCR login, buildx push `miman:<tag>`+`miman:<sha>`), one-line `release.yml` router arm (`miman-v*` above bare `v*`), `miman-upstream-sync.yml` (weekly cron + dispatch, `git ls-remote` + `sort -V` drift check against `LETA_PATCH.md`'s recorded Sync-horizon tag, clean-merge→PR / conflict→fail-loud, never auto-merges, never tracks `upstream/main`). Real CI Gate went green on the PR itself (A1) — first genuinely-live verification this track, since Actions was enabled between M2 fixup and this session (see finding above). Post-merge dry-runs on `main` proved both new dispatchable workflows wire correctly (A4; see CI gate section). No new deviations proposed. `DIGITALOCEAN_ACCESS_TOKEN` confirmed absent — recorded as a Lucas follow-up, blocking only the eventual real `miman-cd.yml` publish (MR1), not this lane's merge. Tracker update itself landed as a small separate follow-up PR ([#9](https://github.com/LetA-Tech/miman/pull/9)) since PR #8 was already merged before this file was updated — process note for future lanes: update the tracker *before* merging, not after. |

## MA1 wave-audit findings (2026-07-06 — all MINOR, none block MR1; full detail in `MA1_FINDINGS.md`)

- **MA1-F1** (doc): spec §4.6 KEEP summary + `LETA_PATCH.md:37-50` omit 3 shipped, detail-spec-mandated
  files (`docker/entrypoint.sh` §6.1, `ci-gate.yml` mod §6.2, `miman-upstream-sync.yml` §6.4) and the
  `docs/leta-miman/**` tree — so §12-item-1's literal "diff == KEEP list" is false though every file is
  spec-justified (zero rogue files). Fix = one-line KEEP-summary update.
- **MA1-F2** (code, cosmetic): `server/main.py:167` — malformed `QDRANT_URL` port raises raw `ValueError`
  before the intended `RuntimeError`; still fail-closed at import. Wrap `parsed.port` in try/except.
- **MA1-F3** (comment): `server/main.py:642` boot-probe docstring overstates "dims" — `get_collections()`
  checks connectivity/auth only. Drop "dims" or add a real dims check.
- **MA1-F4** (code, latent): `scripts/deploy-check.sh:68-79` public-bind guard misses short-syntax
  `ports: ["x:y"]`. Current compose safe; extend the grep.
- **MA1-F5** (doc drift): spec §1.2 (`03-M…:75`) still says "not a GitHub-fork" vs ground-truth `fork:true`
  (`LETA_PATCH.md:21`); decision-log line claims "spec §1.2 corrected" but the prose was never edited.
  Edit the spec, or correct the log claim.
- **MA1-F6** (doc): sync protected-file checklist + spec §6.4 omit `Makefile` (additive-modified) — an
  upstream Makefile change on a sync PR wouldn't prompt review. Add `Makefile` to the checklist.
- **Process note:** main working copy carried an uncommitted edit to `KICKOFF_SESSION_PROMPT.md` at MA1
  session start (header-line deletion) — not part of the merged wave, left untouched (outside MA1 scope).

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
- Optional: detach repo from the fork network (GitHub Support request) — removes fork
  banner/PR-default hazards permanently; only worth it if fork limits keep biting.
- `ci.yml`'s `pip install -e ".[test,graph,vector_stores,llms,extras]"` references a `graph`
  extra that doesn't exist in `pyproject.toml` (pip silently no-ops on it — harmless but
  stale); worth a one-line cleanup in a lane that's already touching `.github/**` (M0 found
  this, `.github/**` is a wall for M0 itself).
- **Undocumented `dev` branch on the fork** (first commit `4805f311`, 2026-07-05 22:03
  local, via an untracked PR #3 "M1 → dev...") — content-identical mirror of `main`'s M0+M1
  via raw re-commits, not a merge. Contradicts the "main has no dev line" decision above and
  isn't referenced by any dispatch. Left untouched pending Lucas's call: delete it, or state
  its intended purpose so it can be documented.
- **Local checkout drifted onto `dev`** between the M2 merge and the A4 follow-up session
  (found 2026-07-06, see decision log) — cause not root-caused (no shell history captured
  showing `git checkout dev`). If it recurs, check for an editor/tool auto-switching branches
  on this machine.
