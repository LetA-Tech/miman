# MS-<upstream-tag> — Upstream sync lane (standing dispatch; self-contained)

**Policy (Lucas 2026-07-06, manual-first — spec 03-M §6.4):** syncs are MANUAL, on-demand,
P6.5-gated. `miman-upstream-sync.yml` is a detector/PR-opener only (run via
`workflow_dispatch`; fork cron is disabled by default and stays that way). Stable upstream
release tags only — never `upstream/main`, never rc/beta. Default answer to "should we
sync?" is **no**; instantiate this lane only when at least one holds:

1. Security fix touching our surface (server/, mem0 core paths we exercise, deps).
2. A capability finsor/finmem concretely needs.
3. Quarterly hygiene with meaningful accumulated drift.

Skipping releases is normal — sync jumps straight to the newest qualifying tag.
Model: Opus 4.8. One session, one PR. **P6.5: post the merge plan + patch-status table in
the PR and get Lucas's ack BEFORE merging.**

## Authority and read-first (closed set)

`docs/leta-miman/03-M-MeM0-detailed-spec.md` §3 (the FIXED-upstream list — re-verify each
on `<tag>`), §4.6, §6.4 · root `LETA_PATCH.md` (current base pin + patch table L1..Ln) ·
finsor bridge `~/Projects/mcfo-finsor/docs/agent/persistent-financial-cognition/
CROSS_SESSION_BRIDGE.md` (standing contract facts; append entries — the ONLY out-of-repo
write allowed) · `gh release view <tag> -R mem0ai/mem0`.

## Git workflow (fork-safe; Lucas-authorized auto-merge only AFTER P6.5 ack + green)

```bash
cd /Users/lucas/Projects/miman
gh repo set-default LetA-Tech/miman        # fork of mem0ai/mem0 — never target the parent
git checkout main && git pull origin main
git fetch upstream --tags
git worktree add ../wt-ms -b sync/upstream-<tag> main
cd ../wt-ms && git merge <tag>             # resolve: upstream wins outside the LetA surface;
                                           # LetA patch region preserved verbatim
# ... sweep + suites below, all green ...
git push -u origin sync/upstream-<tag>
gh pr create --repo LetA-Tech/miman --base main --title "MS-<tag>: upstream sync" \
  --body "<sweep table + patch-status table + plan>"   # then WAIT for Lucas P6.5 ack
gh pr merge  --repo LetA-Tech/miman --squash --delete-branch
```

## Mandatory re-verification sweep (quote file:line on `<tag>` for every row)

For each protected file — `server/main.py`, `server/auth.py`, `server/db.py`,
`server/requirements.txt`, `server/alembic/**`, `mem0/configs/vector_stores/qdrant.py`,
`mem0/vector_stores/{configs.py,qdrant.py}`, `mem0/llms/openai.py`,
`mem0/embeddings/openai.py`, `mem0/memory/main.py`, root `Dockerfile`, `deploy/**`,
`scripts/**`, `.github/workflows/{release.yml,ci-gate.yml}`, `tests/server/**`: changed
upstream? conflicts with LetA hunks? Then specifically:

- /search deprecation shim still present (our drop-patch stays dropped).
- `OPENAI_BASE_URL` chains intact in LLM + embedder.
- `QdrantConfig` before-validator branches (T-4 pins url-without-key decomposition).
- `Memory.add` infer default + infer=False single-record path; `Memory.search` defaults.
- `DEFAULT_CONFIG` shape at the LetA insertion point.
- Auth guards: `/reset`, unscoped `GET /memories`, bulk `DELETE /memories` still
  admin-only; member-role 403s intact (bridge standing facts).
- Release router: `miman-v*` arm still ABOVE bare `v*`.
- Alembic chain linear; new migrations noted.

## Requirements

R1 merge complete, LetA patch region intact. R2 patch-status table per LETA_PATCH.md item:
UNCHANGED / REWORKED(why) / OBSOLETE-PROPOSED(upstream evidence). R3 full suite green:
`ruff check .` · `pytest tests/server/ -q` · upstream subset per LETA_PATCH.md gate ·
`docker build` · `bash scripts/deploy-check.sh` · deploy profile boots. R4 LETA_PATCH.md
re-pinned to `<tag>` (+ sync row appended to its history). R5 contract deltas (routes,
auth, defaults, wire shapes) ⇒ bridge entry + finsor ack BEFORE merge; none ⇒ write
"no contract deltas" explicitly in the PR. R6 after merge: cut `miman-vX.Y.Z` via
release-all; if the wire surface changed, the release notes flag finmem fixture re-freeze.

## Acceptance (each with command output in the PR)

A1 suites green · A2 sweep table complete · A3 R5 evidence · A4
`git diff <tag>..sync/upstream-<tag> --name-only` == LetA surface only · A5 deploy boots.

## Risks / rollback

Highest-risk recurring work — upstream churn lands here by design. Never grow scope
in-session (new upstream capabilities = follow-up notes in the PR, not adoptions).
Rollback: revert the merge commit; the previous `miman-v*` image is unaffected and stays
deployable.
