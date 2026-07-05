# Canonical Implementation Dispatch Template — Finsor Cognition Lanes

**Created:** 2026-07-05 · Authority: `09_technical_specification.md` + `09M` lanes + FD
register. Every lane dispatch is instantiated from this template. **Frozen at copy-time**
(8B-2 lesson): edits after the prompt is copied into an executor session never ran —
re-dispatch explicitly. One lane = one worktree = one PR.

## Executor model

Orchestrator: Claude Code (Opus 4.8 Max). The orchestrator NEVER jumps to coding. Hard
phase order, each phase gated on the previous:

```text
P0 ENTRY CHECKS → P1 INTAKE → P2 CODE INSPECTION → P3 CALL-GRAPH/DATA-FLOW MAP
→ P4 ASSUMPTION VALIDATION → P5 RISK+DEPENDENCY REGISTER → P6 IMPLEMENTATION PLAN
→ [P6.5 PLAN GATE — high-risk lanes only] → P7 IMPLEMENT → P8 VERIFY → P9 REPORT
```

PARK rule (absolute): any entry check or P4 validation that fails ⇒ STOP, report
`PARKED(<reason>, <evidence file:line>)`, propose nothing, stub nothing. A stub is not
delivered work.

Subagent policy: spawn subagents only when they reduce risk or context load — never for
ceremony. Sanctioned uses: (a) fan-out code audit / call-graph tracing across packages or
repos (Explore-type, read-only, must return file:line citations); (b) independent test
design from the spec BEFORE implementation (test-first pressure); (c) adversarial review
of the finished diff (fresh eyes, spec-vs-diff); (d) contract/API cross-checks against a
pinned dependency (e.g. agentkit v0.3.0 seams, finmem fixtures); (e) security/tenancy/
ownership review on consent, deletion, or policy lanes; (f) observability review (metric
names vs 09J vocabularies). NOT sanctioned: single-file edits, trivial lookups, parallel
implementation by multiple agents in one worktree (exactly one writer per worktree).
Subagent output is evidence for the orchestrator — the orchestrator synthesizes and
remains solely accountable for the diff.

Context discipline: the lane's Read-first list is a CLOSED set — do not wander into
other documents; the spec inlines what the lane needs. If the lane discovers it is
larger than scoped, PARK and report — do not grow the scope in-session.

## Dispatch anatomy (every section mandatory; "n/a" must be justified)

```markdown
# LANE <id> — <title>                          [wave Wx · depends: <lanes/gates>]

## 1. Objective
One paragraph: the outcome, not the activity. The FD/spec clause this lane realizes.

## 2. Scope / Non-scope
In: exact capabilities delivered. Out: adjacent work explicitly excluded (name the lane
that owns it). Do-not-touch walls (from 09M cross-lane list + lane-specific).

## 3. Repos and branch
Repo(s); canonical line (CONFIRMED by Lucas); worktree name; pinned dependency versions
that must hold (e.g. agentkit v0.3.0 in go.mod — drift ⇒ PARK).

## 4. Read first (closed set, in order)
- Spec sections: 09 §<x>, 09M lane <id> (contracts)
- Decision basis: 08 FD-<n> rows relevant to the lane
- Intake/context docs to load: <exact paths> (only when the lane needs history)
- The lane reads NOTHING else without recording why in the report.

## 5. Inspect (code areas, exact)
Files/packages with the questions to answer in each (e.g. "conversation_repo.go:810-905 —
confirm single cascadeFilter still present; capture current test coverage of purge").

## 6. Requirement analysis (P1–P4 output, in-session artifact)
Before any code: restate requirements as a numbered checklist mapped to spec clauses;
each with the acceptance test that will prove it. Flag any spec ambiguity ⇒ PARK if
load-bearing, note-and-proceed if cosmetic.

## 7. Call-graph / data-flow map (where relevant)
Trace the paths this lane touches end-to-end (config → constructor → call sites → store/
wire), quoting file:line. Cross-package or cross-repo traces: fan out read-only subagents,
synthesize. Output: a short map in the report; discrepancies vs spec ⇒ P4 failure ⇒ PARK.

## 8. Implementation plan (pre-change, recorded)
Ordered file-level steps (create/modify per 09B lists); test-first where practical;
migration/index steps before producers; flag wiring last. High-risk lanes (consent,
deletion, cascade, policy, catalog events): plan is posted in the report BEFORE coding
[P6.5 gate — Lucas or designated reviewer approves in-thread].

## 9. Acceptance criteria (binary, each with a command)
PASS/FAIL items — every item maps to a requirement from §6 and carries the exact
verify command (go test -run …, go build ./... && go vet ./... && go test ./... && golangci-lint run  # repo has no make lint/test target (E1 D3), grep-proofs, staged e2e).

## 10. Test cases (from 09K, expanded)
File paths + test names + fixtures + assertions. New behavior without a listed test is
scope creep. Cross-tenant negatives and red-team fixtures are MERGE-BLOCKING where the
lane touches memory/consent/deletion.

## 11. Validation commands
The full command list a reviewer runs to reproduce PASS (lint, unit, race, targeted
integration, parity where applicable).

## 12. Expected files changed
The complete expected create/modify list (from 09B). Diff touching files outside this
list ⇒ explain or revert before report.

## 13. Risks, blast radius, rollback
Top risks + mitigations; blast radius statement; rollback = flag-off / revert /
ContractVersion revert per 09L; data-rollback path if any writes occur.

## 14. Report format (terse — no ceremony)
- Entry-check results (PASS/PARK + evidence)
- Requirement checklist: PASS/FAIL each, with verify-command output snippets
- Call-graph findings that changed the plan (if any)
- Deviations vs spec: PROPOSED (never silently applied) → accepted-deviations register
- Files changed list · New follow-ups discovered (as tracker candidates, not scope)
- Completion summary: 3–6 lines, outcome-focused.
```

## Git workflow (binding — full commands in KICKOFF_SESSION_PROMPT.md)

Worktree off latest LOCAL `dev` (pull origin/dev first) · branch `lane/<id>-<slug>` ·
all tests green BEFORE commit · conventional commits · push · PR base `dev` ·
**auto-merge (squash) on green tests — no Lucas approval** · sync local dev · remove
worktree · update LANE_TRACKER.md in the same PR. Never merge PARKED/failing lanes;
never push dev directly.

## Wave/parallelism rules

Lanes run in 09M order (E1 → … → E17); parallel lanes MUST be file-disjoint (check §12
lists pairwise before co-dispatching); every wave exits through a fresh-session,
code-grounded wave audit before the next wave dispatches; prod-facing flag flips are
Lucas gates recorded in the tracker decision log. Executor sessions are disposable;
the tracker + accepted-deviations register are the only carry-forward memory.
