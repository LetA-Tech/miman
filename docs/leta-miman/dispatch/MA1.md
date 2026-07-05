# LANE MA1 — Wave audit (fresh session, code-grounded, pre-release gate)
[wave 1 exit · depends: M3 MERGED · taxonomy AUDIT · model Opus 4.8 · P6.5: no]

## 1. Objective
Independent spec-vs-code audit of the merged M0-M3 wave before any release tag exists.
This session writes NO product code — findings only. Realizes the guide's wave-audit rule
and gates MR1.

## 2. Scope / Non-scope
In: full read of the LetA diff (`git diff cd79fa89..main`), spec §12 acceptance sweep,
citation spot-checks, doctrine checks. Out: fixing anything (file findings as tracker
lanes/candidates); releasing. May edit ONLY: tracker (audit column + findings) and, if
findings warrant, a `MA1_FINDINGS.md` next to this file.

## 3. Repos and branch
miman `main` (post-M3). No worktree needed for reading; findings PR from
`lane/ma1-wave-audit` touching only §2's allowed files.

## 4. Read first (closed set)
Spec 03-M end-to-end · LETA_PATCH.md · tracker (all lane reports/PRs) · the full diff ·
bridge (verify no unacked contract changes shipped).

## 5. Inspect (the audit checklist)
(a) diff-vs-LETA_PATCH-table exactness (spec §12 item 1). (b) main.py additive-only claim
(M1 A20) re-verified independently. (c) No re-added obsolete patches (spec §3.1-3.2).
(d) Boot fail-closed matrix (spec §12 item 5) — run each failure case against the built
image. (e) Full §12 acceptance list 1-13: PASS/FAIL each with command output. (f) Security
pass: no secrets in repo, admin gating unweakened (grep verify_auth/require_admin
unchanged), member-key 403 pair live. (g) Sync-readiness: LETA_PATCH.md base pin correct,
protected-file checklist matches shipped files. (h) Subagent (sanctioned, adversarial):
one fresh-eyes review of the full diff against spec §4.6/§5/§6, returning file:line
discrepancies.

## 6. Requirement checklist
R1 every §12 item verdicted. R2 every discrepancy filed with file:line + severity
(BLOCKER = MR1 stays blocked; MINOR = tracker candidate). R3 tracker audit column updated.

## 7. Call-graph / data-flow map
Re-run M1's §7 trace on merged code; confirm unchanged.

## 8. Implementation plan
Read → run → verdict → file. No code.

## 9. Acceptance criteria
A1 §12 sweep table complete (13 rows, PASS/FAIL + command). A2 zero unexplained files in
the base-diff. A3 verdict line: `MR1 UNBLOCKED` or `MR1 BLOCKED(<findings>)`.

## 10. Test cases
n/a (audit lane — reruns existing suites; justified).

## 11. Validation commands
Tracker-recorded gate + spec §12 commands + `git diff cd79fa89..main --name-only`.

## 12. Expected files changed
Tracker · optional `docs/leta-miman/dispatch/MA1_FINDINGS.md`.

## 13. Risks, blast radius, rollback
None (read-only). Risk of rubber-stamping — mitigated by fresh session + adversarial
subagent + command-output evidence requirement.

## 14. Report format
The §12 sweep table IS the report body + 3-line verdict summary.
