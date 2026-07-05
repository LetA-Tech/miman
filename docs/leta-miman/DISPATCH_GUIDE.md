# Miman Track — Dispatch Guide for Claude (Fable 5 architect / Claude Code executors)

**Home:** authored in mcfo-finsor (miman not mounted in the finsor session). FIRST ACTION
for the miman session: copy this file to `~/Projects/miman/docs/dispatch/DISPATCH_GUIDE.md`
— that copy becomes canonical; append a bridge note confirming adoption.
**Authority:** `miman/docs/03-M-MeM0-detailed-spec.md` (@ cd79fa89) + the repo-boundary
table in finsor `CROSS_SESSION_BRIDGE.md` (BINDING). Miman owns server runtime, Mem0+Qdrant
deployment, Docker, CI/CD, releases (`miman-vX.Y.Z`), upstream Mem0 sync. Miman NEVER
touches mcfo-finsor, mcfo-leankit, or finmem code.

## Lane organization (from spec 03-M; one lane = one session = one worktree = one PR)

M0 repo bootstrap · M1 server patch layer (vector-store selector, healthz/readyz, auth
posture verify) · M2 prod image + deploy profile · M3 CI/CD + release workflow ·
[M4 = finsor-side rider — NOT a miman lane; miman only SIGNALS readiness via bridge B-2]
· M5 upstream-sync cadence (recurring sync lanes: rebase-forward-only, patch-status
table, regression suite, minor-version bump).

Lane taxonomy: PATCH lane (server code deltas — smallest possible diff over upstream,
every patch documented in LETA_PATCH-style table) · INFRA lane (Docker/compose/deploy
profile) · RELEASE lane (tag, image push, changelog) · SYNC lane (M5 recurring). Never
mix taxonomies in one PR.

## Dispatch anatomy (same 14 sections as finsor DISPATCH_TEMPLATE — adapted)

Objective · Scope/Non-scope + do-not-touch (upstream auth flow; finsor/finmem repos;
never weaken admin gating) · Repo/branch (worktree off latest local main-or-dev per
miman convention; branch `lane/m<id>-<slug>`) · Read first (closed set: spec 03-M
sections + upstream files cited) · Inspect · Requirement checklist · Data-flow map where
relevant · Plan (P6.5 gate for AUTH or upstream-sync lanes — post plan, Lucas ack) ·
Acceptance (binary, each with a command) · Tests · Validation commands (CI gate:
`ruff check && pytest && docker build .` — adjust to repo reality at M0, record actual
gate in the tracker like finsor D3) · Expected files · Risks/rollback (image-tag revert;
patches re-appliable) · Terse report (PASS/FAIL + command output; deviations PROPOSED to
the miman tracker register, never silent).

## Execution flow (mirrors finsor, Lucas-ratified model)

Phases P0→P9 (entry checks → intake → inspect → map → validate → plan [→ P6.5] →
implement → verify → report). PARK-don't-stub absolute. Fresh Claude Code session per
lane; paste = miman kickoff block + lane dispatch; frozen at copy. One PR per lane,
auto-merge on green tests (same Lucas authorization as finsor — recorded in finsor
LANE_TRACKER decision log). Executor sessions are disposable: `miman/docs/dispatch/
M_LANE_TRACKER.md` (create at M0: lanes/status/PR/audit + deviations register +
decision log) is the only carry-forward memory. Wave audits: after M3 merges, one
fresh-session code-grounded audit before any release tag.

Model policy: Opus 4.8 for M1 (server patch/auth) + M5 sync lanes; Sonnet 5 fine for
M0/M2/M3 (bootstrap/infra/CI boilerplate). Subagents only where they reduce risk
(upstream-diff tracing, security review of auth surface); never parallel writers in one
worktree.

## Cross-track protocol (BINDING)

Read finsor `docs/agent/persistent-financial-cognition/CROSS_SESSION_BRIDGE.md` at every
session start; append signed dated entries. Obligations: B-2 signal when miman-v0.1.0-rc
is runnable (unblocks finsor X-4/M4) · B-3 publish admin-API surface doc for the
finmem-admin client · B-4 X-API-Key provisioning contract. Contract changes affecting
finmem/finsor (routes, auth, defaults) are NEVER silent — bridge entry + finsor ack
required before merge (the delta-1 precedent: bulk-delete admin-only reshaped finsor's
deletion coordinator).

## Session structure for future Claude Code sessions (paste-ready kickoff skeleton)

"You are Claude Code, sole implementer for miman lane M<id>. Load order: this guide →
M_LANE_TRACKER.md (confirm lane PENDING + deps MERGED, else PARK) → your lane dispatch →
spec 03-M cited sections → finsor CROSS_SESSION_BRIDGE.md. Doctrine: smallest diff over
upstream; never weaken admin gating; secrets never in repo; every observable event via
real telemetry (Redis never observability); PARK-don't-stub. Git: worktree → branch →
CI gate green → conventional commit → PR → auto-merge on green → sync → remove worktree
→ update M_LANE_TRACKER in the same PR. Report terse: PASS/FAIL per acceptance +
command output + 3-line summary."
