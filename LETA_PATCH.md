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

`LetA-Tech/miman` **is a GitHub fork** of `mem0ai/mem0` (`fork: true`, parent
`mem0ai/mem0` — M0 finding, spec §1.2), seeded with full upstream history;
`upstream` remote added in M0. Consequences (standing facts): GitHub Actions is
disabled until the web-UI consent banner is clicked; `gh` PR commands pin
`--repo LetA-Tech/miman` (a fork can default to the parent); scheduled workflows
are disabled-by-default on forks (M3 verifies the sync cron arms).

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

## Shipped at M1 — server patch layer (spec §4.1-4.2, §5.1-5.3, §3.4)

The only Python-code delta over upstream. `server/main.py` edits are **additive**:
no existing upstream function is modified; the single existing-line change is the
`SKIPPED_REQUEST_LOG_PATHS` constant (health paths added).

| # | File | Kind | What LetA changed (spec) |
|---|---|---|---|
| L1 | `server/main.py` | M (additive) | `import urllib.parse`; env-driven vector-store selector + `_build_qdrant_vector_store_config` builder that survives the `QdrantConfig` before-validator by decomposing url-without-api_key to host/port (§5.1-5.2); `MEM0_VECTOR_STORE` unset/`pgvector` keep `DEFAULT_CONFIG` byte-identical, `qdrant` builds from `QDRANT_*`, else `RuntimeError` at boot; `GET /healthz` + `GET /readyz` (unauth, `include_in_schema=False`, readyz probes app-DB only — never Qdrant, §5.3); `MIMAN_ENV`-gated fail-closed Qdrant boot probe (§5.2); `/healthz`,`/readyz` added to `SKIPPED_REQUEST_LOG_PATHS` |
| L2 | `server/scripts/provision_service_key.py` | A (new) | Deploy-time member-credential provisioning (§3.4 delta-6, tracker DV-1). `--name --label [--rotate]`; creates a `role="member"` service user + API key via upstream `generate_api_key`; prints the full key once to stdout, never logs it; idempotent by name; zero API-surface / auth.py change |
| L3 | `tests/server/test_leta_qdrant_config.py` | A (new) | Regression suite T-1..T-17 (spec §9.4). Hermetic: mocks only, no live Postgres/Qdrant/network |

**Dropped, verified fixed upstream (not re-added):** `/search` filters wrapper
(§3.1, D-1 — regression-guarded by T-11) and `OPENAI_BASE_URL` forwarding (§3.2,
D-2 — regression-guarded by T-10). `infer` stays upstream-default; FinMem owns the
default (§3.5, D-3 — single-record invariant pinned by T-13).

## Remaining lanes

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
