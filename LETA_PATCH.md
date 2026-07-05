# LetA Patch Manifest — miman v1

LetA-owned patch layer on top of upstream `mem0ai/mem0`. This document is the
source of truth for what LetA changed and why. Anyone reviewing this repo
starts here before reading code.

**Design authority:** `docs/leta-miman/03-M-MeM0-detailed-spec.md` — every
claim below is a summary of that spec; the spec wins on conflict.

---

## Base pin

| | |
|---|---|
| Upstream base commit | `cd79fa89` (`cd79fa8914b5b1cf66daacc957d826065df57df8`) |
| Upstream package version at base | `mem0ai 2.0.11` (pyproject.toml) |
| Sync horizon (newest upstream release tag at pin time) | `v2.0.11` (upstream commit `f2532f0`, ancestor of `cd79fa89`) |
| Re-pin policy | Re-pin to the next upstream `v*` tag at the first `MS-<tag>` sync lane (never track `upstream/main`) |

`LetA-Tech/miman` is a standalone repo seeded with full upstream history
(origin only until this lane; `upstream` remote added in M0). Not a
GitHub-fork relationship — independent issues/releases.

## Release tag rule

Miman release tags are **`miman-vX.Y.Z`** only. A bare `vX.Y.Z` tag is
**forbidden** in this repo — `release.yml`'s router sends bare `v*` tags to
`cd.yml` (PyPI publish of the `mem0ai` package); reusing that scheme here
would route image releases into the Python-SDK publish path (spec §6.3).

## Patch surface (target state, spec §4.6)

```text
KEEP (rewritten for the new base)          DROP (fixed upstream, never re-add)
────────────────────────────────          ──────────────────────────────────
server: vector-store selector + builders   /search filters wrapper        (§3.1)
server: /healthz /readyz + log-skip        OPENAI_BASE_URL forwarding     (§3.2)
root Dockerfile + .dockerignore
deploy/ (compose, env, deploy.sh, README)
Makefile targets (miman-*)
scripts/deploy-check.sh, release-all.sh
server/scripts/provision_service_key.py (delta-6, §3.4 — lane M1, tracker DV-1)
.github/workflows: miman-checks.yml, miman-cd.yml (+1-line router arm)
tests/server/test_leta_qdrant_config.py (rewritten, §9.4)
LETA_PATCH.md (this file)
```

Everything else in the repo stays byte-identical to upstream — that is the
sync-cost model (spec §4.6).

## Status at this lane (M0 — repo bootstrap)

No server code patches exist yet. This lane only wires the `upstream` remote
and creates this manifest with the base pin. The KEEP list above is the
**target state**; it is realized incrementally:

- M1 — server patch layer (vector-store selector, healthz/readyz, provisioning script)
- M2 — production image + deploy profile
- M3 — CI/CD (miman-checks.yml, miman-cd.yml, miman-upstream-sync.yml)

Each lane updates this file with what it actually shipped.

## Upstream sync

Sync targets **upstream release tags**, never `upstream/main`. Weekly
drift-check workflow (`miman-upstream-sync.yml`, lane M3) opens a sync PR on
drift; never auto-merges (spec §6.4).

## Cross-references

- Design spec: `docs/leta-miman/03-M-MeM0-detailed-spec.md`
- Dispatch guide: `docs/leta-miman/DISPATCH_GUIDE.md`
- Lane tracker: `docs/leta-miman/dispatch/M_LANE_TRACKER.md`
