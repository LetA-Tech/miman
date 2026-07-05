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
| M0 | INFRA | Repo bootstrap: upstream remote, LETA_PATCH.md v1, CI-gate reality check | — | Sonnet 5 | no | PENDING | — | — |
| M1 | PATCH | Server patch layer: vector-store selector, healthz/readyz, boot probe, provisioning script, tests T-1..T-15 | M0 | Opus 4.8 | **yes** | PENDING | — | — |
| M2 | INFRA | Prod image + deploy profile: Dockerfile, entrypoint, compose, env, deploy.sh smokes, Makefile targets, deploy/release scripts | M1 | Sonnet 5 | no | PENDING | — | — |
| M3 | RELEASE-infra | CI/CD: miman-checks.yml (+ci-gate reg), miman-cd.yml (+router arm), miman-upstream-sync.yml | M2 | Sonnet 5 | no | PENDING | — | — |
| MA1 | AUDIT | Fresh-session code-grounded wave audit (spec-vs-diff, full §12 acceptance sweep) | M3 | Opus 4.8 | no | PENDING | — | — |
| MR1 | RELEASE | Cut `miman-v0.1.0-rc1`: release-all → router → DOCR; then bridge B-2 signal | MA1 | Sonnet 5 | no | PENDING | — | — |
| MS-<tag> | SYNC | Recurring upstream sync (instantiate `MS_TEMPLATE.md` per upstream release tag) | MR1 | Opus 4.8 | **yes** | recurring | — | — |

## CI gate (D3-style — M0 verifies against repo reality and finalizes here)

Proposed (M0 to confirm/adjust and record the working bootstrap commands):

```bash
python -m ruff check server/main.py server/scripts/provision_service_key.py tests/server/
python -m pytest tests/server/test_leta_qdrant_config.py -q
docker build -t miman:gate .          # from M2 onward
bash scripts/deploy-check.sh          # from M2 onward
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

## Follow-up candidates (one-liners; not scope for any current lane)

- Upstream-contribution candidate: admin-only `POST /users` (member creation) — replaces
  delta-6 script long-term (spec §3.4).
- FinMem `infer=true` explicit option + policy gate wiring (D-3) — finsor-side.
- Per-consumer quotas beyond per-key auth (spec §8) — needs concrete trigger.
