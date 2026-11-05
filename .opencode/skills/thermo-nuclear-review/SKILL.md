---
name: thermo-nuclear-review
description: Optional deep findings-only Thermo-Nuclear correctness and security audit of changed code and its cross-module effects.
license: MIT
---

# Thermo-Nuclear Review — read-only project adaptation

Adapted solely from the distinct thermos correctness/security rubric carried by
michael-denyer/pstack-claude. Read [provenance](PROVENANCE.md). This does not
install that distribution's pstack router or agents, `thermos` dispatcher, model
defaults, or code-quality restructuring workflow.

Follow `AGENTS.md` and the existing `code-reviewer` agent's permissions and
report format. Findings only: no edits, autofix, refactor, host mutation,
report-file creation, nested delegation, Code Mode or MCP escape hatch.

## Scope

Audit only the requested added/modified code. Establish the actual review base
with the orchestrator; do not assume `main` or ignore uncommitted changes. Read
surrounding code to understand effects, but report only defects introduced by
or directly affected by this change. Thoroughness is effort, not a guarantee
that no defect can escape review.

## Correctness and security audit

1. **Breaking functionality:** trace callers, cross-module contracts and side
   effects, including errors, cleanup, ordering and unavailable-data handling.
   Small changes can break behavior outside the diff.
2. **Breaking developer experience:** inspect changes to environment variables,
   secret handling, ports, networking, startup/build scripts, required setup
   and dependencies. Distinguish an optional new path from a broken old one.
3. **Feature/safety leaks:** trace gates, internal checks and trust boundaries
   end to end. Look for paths that expose gated capabilities or bypass checks.
4. **Intended breakage:** distinguish an approved, constrained behavior change
   from an accidental regression. Never hide an unapproved safeguard removal
   or a serious security/data-integrity consequence merely because it appears
   intentional. Explain impacts the author may have missed.
5. **Calibrated findings:** investigate client/server defenses before asserting
   a bug. Do not present unfinished research as a confirmed defect when code
   is available to check. If access is blocked, request evidence and label the
   uncertainty. Severity must reflect a real mechanism and impact, not the
   dramatic name of this skill.

## Independent pass, then other evidence

Complete your own audit before reading others' conclusions. If a PR/MR exists
and you have meaningful medium-or-higher findings, ask the orchestrator for
authorized read-only discussion excerpts if useful. Do not invoke unavailable
`gh`/`glab` or bypass reviewer shell restrictions. Validate, deduplicate and
attribute bot/human findings; do not copy them as truth. Report when discussion
was not consulted and why.

## Return

Use the existing reviewer format and severity scale: each finding needs
`file:line`, evidence, failure mechanism/impact, and a focused recommendation
to the owning specialist. Separate confirmed defects, investigation needs and
unverified tests. No stylistic rewrite demands, automatic restructuring, or
unsupported claim of completeness. If no actionable findings, say so.
