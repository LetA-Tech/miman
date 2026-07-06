# MA1 — Wave-audit findings (M0–M3, pre-release gate)

**Session:** fresh, code-grounded · **Base:** `cd79fa89` · **HEAD audited:** `c9fbf563` (main, post-M3)
**Model:** Opus 4.8 + one adversarial Opus subagent · **Date:** 2026-07-06

**Verdict: `MR1 UNBLOCKED`.** Zero BLOCKERs. All in-scope §12 items PASS; item 10 is the
finsor-side M4 rider (out of scope this wave, gated *after* MR1). Six MINOR findings, all
tracker candidates — none block the release.

Entry checks: MA1 PENDING ✓ · M3 MERGED ✓ · base `cd79fa89` valid ✓ ·
`git diff cd79fa89..main --name-only` = 19 patch files + `docs/leta-miman/**` governance tree.

---

## §12 acceptance sweep (the report body)

| # | Acceptance item | Verdict | Evidence (command / file:line) |
|---|---|---|---|
| 1 | `LETA_PATCH.md` names base `cd79fa89`; `git diff base..main --name-only` == §4.6 KEEP list | **PASS**¹ | Base pin `LETA_PATCH.md:16` = `cd79fa8914b5…` ✓. Every non-docs file is spec-mandated & explained (A2 holds — zero rogue files). **MINOR F1:** §4.6 KEEP *summary* omits 3 shipped, spec-mandated files + the docs tree — literal equality fails, substantive intent passes |
| 2 | No `/search` wrapper, no base-url forwarding (D-1/D-2) | **PASS** | `git diff base..main -- server/main.py \| grep -iE '+.*(openai_base_url\|def search\|filters\[)'` → none. `git diff … -- server/auth.py` = 0 lines |
| 3 | T-1…T-17 pass; upstream suite untouched | **PASS** | `pytest tests/server/test_leta_qdrant_config.py -q` → **30 passed**. No-regression subset → **759 passed / 10 failed / 133 errors / 19 skipped** = identical failure profile to pristine `main` (+30 new suite, zero new failures; 10 fails = Postgres-needing, 133 errors = pre-existing bare-venv import path) |
| 4 | Compose boots from `deploy/` on `.env` edits; `deploy.sh` add→search→delete smoke | **PASS**² | `docker compose config` → exit 0, 3 services, miman `127.0.0.1:8000` only, qdrant/appdb no host ports. `deploy.sh:91-113` has the round-trip. Live round-trip recorded green in **M2-fixup (PR #5)** — not re-spent this session (needs Lucas's live OpenAI key) |
| 5 | Boot fails closed: bad store / unparseable URL / unreachable Qdrant(prod) / missing JWT_SECRET | **PASS** | Live at import (`AUTH_DISABLED=true`, exit=1 each): `Unsupported MEM0_VECTOR_STORE='cassandra'`; `QDRANT_URL is not parseable: 'http://'`; qdrant-no-url `requires QDRANT_URL or QDRANT_HOST+QDRANT_PORT`; `JWT_SECRET is required` (upstream guard). Unreachable-Qdrant(prod) case = T-15 (green) |
| 6 | `/healthz`+`/readyz` unauth, log-skipped, Qdrant-untouched | **PASS** | `main.py:619-640` no `Depends`; both in `SKIPPED_REQUEST_LOG_PATHS` (`main.py:57`); `readyz` queries only `SessionLocal`/`User.id`, never Qdrant. T-8/T-9/T-12 green |
| 7 | Image = local patched tree, non-root, healthcheck, migrations at start | **PASS** | Rebuilt `miman:ma1-audit`: `mem0.__file__`=`/app/mem0/__init__.py`, `Editable project location: /app`, **0** `pip install mem0ai` layers; `id`=`uid=10001(miman)`; `HEALTHCHECK`→`/healthz`; OCI `revision` label = repo HEAD `c9fbf563` exactly; `entrypoint.sh` = `alembic upgrade head` then uvicorn (no `--reload`) |
| 8 | `miman-v*` routes to `miman-cd.yml`; bare `v*` can't publish an image | **PASS** | `release.yml:48` `miman-v*) workflow="miman-cd.yml"` strictly above `release.yml:49` bare `v*) workflow="cd.yml"` — prefixed tag can never fall through to PyPI |
| 9 | Weekly sync workflow, opens PRs on drift, never auto-merges | **PASS** | `miman-upstream-sync.yml`: cron `17 6 * * 1` + dispatch; drift vs `LETA_PATCH.md` Sync horizon; clean merge → PR (`:6,113` never auto-merge); conflict → `git merge --abort` + fail loud (`:88-90`); only `refs/tags/<v>`, never `upstream/main` |
| 10 | FinMem fixtures re-frozen vs rc image; construction probe green; §7.3 in 09C.8 | **N/A**³ | M4 = finsor-side rider, **not a miman lane** (spec §11; tracker plan-of-record). Definitionally needs "the rc image" → gated *after* MR1. Belongs to finsor X-4, not this wave |
| 11 | Telemetry egress off in LetA profile (`MEM0_TELEMETRY=false` asserted by deploy-check) | **PASS** | `.env.example:39` `MEM0_TELEMETRY=false`; `deploy-check.sh:152` asserts it, citing "spec §12 item 11" |
| 12 | Deprecated repo untouched; rollback documented in `deploy/README.md` | **PASS** | No diff file touches the deprecated repo (separate repo). `deploy/README.md:74` `## Rollback` section |
| 13 | Provisioned member key: `POST /reset` + unscoped `GET /memories` → 403; admin ops admin-only | **PASS** | `provision_service_key.py:43` `role="member"`; `deploy.sh:115-123` asserts both 403s. Live 403 pair recorded green in **M2-fixup (PR #5)** |

¹ ² ³ = see notes below the findings register.

---

## Findings register (all MINOR — tracker candidates, none block MR1)

| ID | Sev | File:line | Finding | Fix |
|---|---|---|---|---|
| MA1-F1 | MINOR | spec §4.6 (`03-M…:299-314`) + `LETA_PATCH.md:37-50` | KEEP *summary* omits 3 shipped, detailed-spec-mandated files: `docker/entrypoint.sh` (§6.1), `.github/workflows/ci-gate.yml` mod (§6.2), `.github/workflows/miman-upstream-sync.yml` (§6.4). Also `docs/leta-miman/**` governance tree is in base-diff but named in no KEEP list. So §12-item-1's literal "diff == KEEP list" is false, though every file is spec-justified (A2 zero-unexplained still holds) | One-line update to both KEEP summaries listing the 3 files + acknowledging the docs tree |
| MA1-F2 | MINOR | `server/main.py:167` | Malformed `QDRANT_URL` port (e.g. `http://qdrant:notaport`) → `urllib.parse`'s `.port` raises a raw `ValueError: Port could not be cast to integer` **before** the intended `RuntimeError("QDRANT_URL is not parseable")` on `:168` can fire. Still fail-closed (crashes at import, non-zero) — cosmetic (wrong exception type + less-helpful message). Canonical `http://qdrant:6333` unaffected | Wrap the `parsed.port` access in try/except → re-raise as the intended `RuntimeError` |
| MA1-F3 | MINOR | `server/main.py:642` | Boot-probe docstring claims it catches "wrong URL/key/**dims**", but `get_collections()` (`:647`) verifies only connectivity + auth — a dims mismatch vs a pre-existing collection surfaces on first op, not boot. Overstated comment, not a code defect | Drop "dims" from the docstring (or add a real dims check) |
| MA1-F4 | MINOR | `scripts/deploy-check.sh:68-79` | Public-bind guard catches literal `0.0.0.0:` and long-syntax `published:`, but a short-syntax regression `ports: ["6333:6333"]` (binds 0.0.0.0) would slip past. Current compose is long-syntax + no qdrant/appdb ports, so latent, not live | Extend the grep to also flag short-syntax `ports:` entries lacking a `127.0.0.1:` host_ip |
| MA1-F5 | MINOR | `03-M…:75` vs `LETA_PATCH.md:21` | Spec §1.2 still reads "It is **not** a GitHub-fork relationship"; ground truth is `fork: true` (LETA_PATCH.md:21, M0 finding). Decision-log `M_LANE_TRACKER.md:167` *claims* "spec §1.2 corrected" but the spec prose was never edited. No operational risk (fork hazards mitigated — sync workflow pins `--repo`), just stale doc + inaccurate log claim | Actually edit spec §1.2 to match, or correct the decision-log claim |
| MA1-F6 | MINOR | `miman-upstream-sync.yml:117-136` + spec §6.4 | Protected-file review checklist omits `Makefile` (additive-modified by L8) — an upstream `Makefile` change on a sync PR wouldn't prompt review. Low: additive `miman-*` targets rarely conflict and merge diffs are visible anyway | Add `Makefile` to the §6.4 checklist + the workflow PR body |

**Process observation (not a lane finding):** the main working copy carried an *uncommitted* edit to
`docs/leta-miman/dispatch/KICKOFF_SESSION_PROMPT.md` (a header-line deletion) at session start — not
part of the merged M0–M3 wave, not authored here, left untouched (outside MA1's allowed-edit scope).
Flagged for Lucas.

---

## Notes

1. **§12 item 1 (F1):** The base pin is correct and there are **zero unexplained files** in the
   diff — A2 (acceptance A2) holds. The gap is documentation-completeness only: the §4.6 KEEP
   *summary* and `LETA_PATCH.md`'s "Patch surface (target state)" block are incomplete relative to
   what the detailed spec (§6.1/§6.2/§6.4) mandates and what shipped. `LETA_PATCH.md`'s detailed
   L1–L15 tables *do* list all 15 patch items correctly. Non-blocking.
2. **§12 item 4 & 13 (live legs):** the compose render + `deploy.sh` smoke content are verified
   here; the actual add→search→delete round-trip and the member-key 403 pair were verified **live**
   in M2-fixup (PR #5, 2026-07-06) with Lucas's real embedder key. Not re-run this session to avoid
   re-spending his OpenAI credits — the recorded evidence + code/config chain is complete.
3. **§12 item 10:** the only §12 row that is not a miman deliverable. Spec §11 defines M4 as a
   "finsor-side rider … not in this repo"; it consumes the MR1 rc image, so it is downstream of the
   release this audit gates. Correctly deferred to finsor X-4.

## Independent re-verification performed (anti-rubber-stamp)

- 30-test M1 suite re-run green; 759-vs-759 no-regression re-run (independent of tracker's recorded numbers).
- Image **rebuilt from scratch** and provenance re-proven (not trusting M2's recorded A3).
- Boot fail-closed matrix exercised **live** at import (3 distinct RuntimeErrors + JWT guard).
- Router arm, R6 no-publish grep, deploy-check assertions, sync workflow — all re-read at file:line.
- One **adversarial Opus subagent** did a fresh-eyes diff-vs-spec (§4.6/§5/§6) pass → zero BLOCKERs,
  surfaced F2/F3/F4 and the F5 doc contradiction (all re-verified here with command output).
