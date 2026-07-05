# LANE MR1 — Release miman-v0.1.0-rc1 + bridge B-2 signal
[wave 1 exit · depends: MA1 verdict `MR1 UNBLOCKED` · taxonomy RELEASE · model Sonnet 5 · P6.5: no]

## 1. Objective
Cut the first release candidate through the full pipeline (release-all → GitHub Release →
router → miman-cd → DOCR image), verify the published artifact, and signal finsor via
bridge B-2 — unblocking their M4/X-4 rider. Realizes spec §11 M5(release)/tracker MR1,
§12 items 8, 10-prep.

## 2. Scope / Non-scope
In: version choice `0.1.0-rc1` (tag `miman-v0.1.0-rc1`), release execution, artifact
verification, bridge entry, tracker close-out. Out: any code change (if ANYTHING needs
fixing ⇒ PARK, new PATCH/INFRA lane, MA1 re-verdict); deploying to any LetA host
(platform-repo concern); PyPI/npm anything.

## 3. Repos and branch
miman `main`, clean, synced. Release runs from main directly per release-all guards (no
worktree needed; tracker update = tiny PR after).

## 4. Read first (closed set)
Tracker (MA1 verdict + gate) · spec §6.3, §12 items 7-8 · `scripts/release-all.sh` ·
bridge (B-2 wording owed).

## 5. Inspect
`gh secret list` (DIGITALOCEAN_ACCESS_TOKEN present — else PARK) · MA1 verdict line ·
`git describe` state.

## 6. Requirement checklist
R1 `make miman-release-all VERSION=0.1.0-rc1` completes (guards pass).
R2 Router routed the release to miman-cd.yml (run link; NOT cd.yml).
R3 Image lands: `miman:miman-v0.1.0-rc1` + `miman:<sha>` in DOCR (doctl or registry UI
   evidence).
R4 Pull-and-boot verification: `docker pull <ref>` on the dev machine → deploy profile
   boots against it (deploy.sh green, spec §12 item 4 against the PUBLISHED image).
R5 Bridge B-2 entry appended: image ref, compose profile path, env contract pointer,
   provisioning command for the runtime key, `MIMAN_ENV` note — everything finsor/finmem
   need to run the rc for fixture re-freeze. B-2 flips to SIGNALED.
R6 Tracker: MR1 MERGED-equivalent (RELEASED), decision-log row with tag + image digests.

## 7. Call-graph / data-flow map
n/a (pipeline exercised, not traced — R2 is the evidence; justified).

## 8. Implementation plan
verify preconditions → release → watch runs → R3/R4 verification → bridge → tracker.

## 9. Acceptance criteria
A1-A6 = R1-R6, each with command output / run links / digest.

## 10. Test cases
R4 is the test (published-artifact e2e). Justified.

## 11. Validation commands
`make miman-release-all VERSION=0.1.0-rc1` · `gh run list --workflow=miman-cd.yml` ·
`doctl registry repository list-tags miman` (or equivalent) · deploy.sh output.

## 12. Expected files changed
Tracker only (+ bridge append in finsor repo — sanctioned).

## 13. Risks, blast radius, rollback
Blast radius: a published rc image (immutable, harmless if broken — nothing deploys it
automatically). Rollback: tag/image stay, mark rc dead in tracker, cut rc2. Never delete
published tags.

## 14. Report format
Template terse report; MUST include the exact bridge entry text appended.
