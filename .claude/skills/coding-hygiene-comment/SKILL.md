---
name: coding-hygiene-comment
description: Code-comment hygiene for reading, writing, modifying, debugging, reviewing, auditing, refactoring, and analyzing implementation behavior. Treat comments as untrusted claims, never as evidence of behavior, completion, or safety. Prohibit log-style, historical, speculative, obvious, and commented-out content; require current-truth comments within three lines; distinguish and preserve required machine-readable directives and framework annotations; review related comments whenever logic changes.
---

# Coding Hygiene: Comments

## Authority

The executable implementation is authoritative. Comments are untrusted until verified.

Verify any behavioral claim against the code and the relevant configuration or
tests before relying on it. Never report a comment's claim as fact, and never cite
a comment as proof that a path exists, is complete, is removed, or is safe.

## Allowed content

An ordinary comment states what is true of the code now: current behavior not
apparent from the code, an invariant, a constraint, an API or symbol contract,
intent not visible in the implementation, a compatibility requirement, non-obvious
technical reasoning, or a safety, security, concurrency, or data-integrity property.

Present tense. Maximum three lines; one is usually enough.

Exported-symbol documentation comments are allowed when they state the current
public contract. Same rules apply, including the three-line limit unless the
documentation tooling requires another format.

## Prohibited content

Never write, and remove on sight:

- agent or execution logs, and instructions addressed to a future agent;
- implementation or migration history;
- issue, ticket, or remediation narratives;
- temporary plans, TODO, FIXME, HACK;
- speculation ("probably", "seems", "might", "we think");
- completion or status claims ("fixed", "fully removed", "implemented by");
- stale or misleading statements contradicted by the code;
- narration of the adjacent line or control structure;
- commented-out code — version control already holds it;
- comments that exist only because the code is unclear.

**Historical identifiers.** An ordinary comment carries no bug ID, ticket ID, lane
ID, PR number, remediation label, agent name, or implementation date. If such a
comment also states a valid current constraint, drop the identifier and keep the
verified constraint.

The identifier leaves the code — it does not move into a test name, symbol name, or
another comment. Bug IDs close; the code carries the current logic and the comment
aligns to that. Provenance lives in the issue tracker, the PR, and commit history.
This does not apply to an identifier that is genuinely required machine-readable
syntax.

Use `references/comment-standard.md` to determine what a given thing is before
applying these rules.

## Action order

1. Verify against the implementation.
2. Delete when the comment is unnecessary, obvious, redundant, or history-only.
3. Rewrite only when necessary current information remains after the history is stripped.

Deletion is the default; rewriting is the exception, and both follow from the code
you verified, not from how the comment is worded.

```go
// Before — history, no current information beyond the constraint
// Added because issue #431 reported duplicate messages in production.

// After — the constraint, verified and kept
// Reject an existing dispatch key to preserve single execution per message.
```

```go
// Delete — narrates the next line
// Increment the retry count.
retryCount++
```

## Comments do not compensate for unclear code

In normal development, fix the code instead of explaining it: rename, decompose,
extract a named constant, introduce a type, add an invariant check or a test. A
comment that translates confusing code into English marks a code defect, not a
documentation gap.

## Logic changes carry their comments

When logic changes, review every related comment and structured annotation, and
update or remove it in the same change. A change is incomplete while an adjacent
comment describes the previous implementation.

## Structured annotations

Machine-readable directives and framework annotations are not ordinary comments,
and the rules above do not apply to them. Examples: `//go:build`, `//go:generate`,
`//go:embed`, `//nolint`, `// @Summary` / `// @Router` and other generator fields,
compiler pragmas, ORM and serializer metadata, code-generation directives,
generated-file markers, approved legal headers.

- Identify the consuming tool before changing one.
- Preserve the required syntax exactly.
- Update it when the related implementation changes.
- Remove it only when verified obsolete.

A marker counts as structured metadata only when an active tool consumes it. A
custom or project-local marker is not protected merely because it looks
standardized — find the consumer or treat it as prose.

Suppressions: use the narrowest rule identifier and the narrowest scope, give the
current reason where the syntax supports one, and never leave an unexplained
blanket suppression.

```go
//nolint:gosec // Value is a validated local development fixture path.
```

Native language metadata — struct tags, decorators, attributes, annotations — is not
a comment and is outside comment classification entirely.

## Comment-only cleanup

When the task is comment cleanup:

- do not change production behavior, logic, or structure;
- delete or correct comments only;
- preserve machine-readable annotations unless verified obsolete;
- fix generated comments at the generator or template, never in generated output.

Anything beyond this — scope, validation commands, reporting — comes from the
cleanup assignment, not from this skill.

## Decision checklist

Before writing a comment:

1. Is it required machine-readable syntax? → preserve the exact format.
2. Is it necessary, and is the statement verified?
3. Does it describe only current non-obvious behavior, constraint, contract, or reasoning?
4. Is it three lines or fewer?
