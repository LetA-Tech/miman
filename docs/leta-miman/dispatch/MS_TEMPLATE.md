# LANE MS-<upstream-tag> — Upstream sync (recurring; instantiate per upstream release tag)
[recurring · depends: MR1 done once; previous MS merged · taxonomy SYNC · model Opus 4.8 ·
**P6.5: YES — post merge-plan + patch-status table, Lucas ack before merging**]

Instantiate: copy to `MS-<tag>.md`, fill `<tag>`, add tracker row, dispatch fresh session.
Usually triggered by a `miman-upstream-sync.yml` PR — this lane ADOPTS that PR's branch
(or recreates it) and owns it to green.

## 1. Objective
Merge upstream release `<tag>` into main with the LetA patch surface intact, re-verified,
and re-documented. Realizes spec §6.4.

## 2. Scope / Non-scope
In: the merge, conflict resolution, patch re-verification, LETA_PATCH.md base re-pin,
regression suite, minor miman version bump prep. Out: new features; opportunistic
refactors (never); adopting new upstream capabilities (file tracker candidates instead).

## 3. Repos and branch
miman; branch `sync/upstream-<tag>` off latest main. PARK if a previous sync lane is open.

## 4. Read first (closed set)
Spec §6.4 (protected-file checklist), §3 (the FIXED list — re-verify each still holds on
`<tag>`), §4.6 · LETA_PATCH.md (current base + patch table) · tracker · upstream
release notes for `<tag>` (`gh release view <tag> -R mem0ai/mem0`).

## 5. Inspect (the sync-specific sweep — every item quoted file:line in report)
For EACH protected file (spec §6.4 list): changed upstream? conflicts with LetA hunks?
Specifically re-verify on `<tag>`: search-shim still present (drop-patch stays dropped);
OPENAI_BASE_URL chains intact; QdrantConfig validator branches (T-4 assumption!);
`Memory.add` infer default + infer=False single-record path; `Memory.search` defaults;
DEFAULT_CONFIG shape at the LetA insertion point; auth guards on
/reset · unscoped GET /memories · bulk DELETE (contract facts in the bridge); router case
block still has `miman-v*` above `v*`; alembic chain linear.

## 6. Requirement checklist
R1 merge complete, LetA region intact. R2 patch-status table (per patch item:
UNCHANGED / REWORKED(<why>) / OBSOLETE-PROPOSED(<upstream fix evidence>)). R3 full gate +
T-suite green. R4 LETA_PATCH.md re-pinned to `<tag>`. R5 contract-fact deltas (auth,
routes, defaults, wire shapes) ⇒ bridge entry + finsor ack BEFORE merge; none ⇒ state
"no contract deltas" explicitly. R6 image builds; deploy profile boots.

## 7. Call-graph / data-flow map
Re-run M1 §7 trace on the merged tree.

## 8. Implementation plan (P6.5 — post before merging)
fetch → merge tag → resolve (patch-preserving; upstream wins outside LetA surface) →
re-verify §5 sweep → suites → LETA_PATCH.md → post plan+table → Lucas ack → PR.

## 9. Acceptance criteria
A1 gate + tests green (output). A2 §5 sweep table complete. A3 R5 bridge evidence or
explicit none. A4 `git diff <tag>..sync-branch --name-only` == LetA surface only.
A5 deploy profile boots on the merged tree.

## 10. Test cases
Existing T-1..T-17 (they exist to catch exactly this drift) + any new pin the sweep shows
necessary (add to the suite, note in report).

## 11. Validation commands
Tracker gate · `pytest tests/server/ -q` · `docker build` · `bash scripts/deploy-check.sh`
· A4 diff.

## 12. Expected files changed
Upstream-merged files (bulk, expected) + LetA surface only where conflicts forced it +
LETA_PATCH.md + tracker. Any LetA-surface change beyond conflict resolution = deviation,
PROPOSED.

## 13. Risks, blast radius, rollback
Highest-risk recurring lane (upstream churn lands here by design). Blast radius: entire
runtime. Mitigations: P6.5 gate; T-suite; §5 sweep; never sync main-to-main (tags only).
Rollback: revert merge commit; previous release image unaffected.

## 14. Report format
Template terse report; the §5 sweep table and R2 patch-status table are mandatory
sections. Cut `miman-vX.Y.Z` AFTER merge via a fresh MR-style close (or same session if
trivial — record either way).
