---
name: ponytail
description: Supplementary Ponytail minimalism for choosing the smallest complete change without weakening project tests, ownership, or approvals.
license: MIT
---

# Ponytail — project skill-only adaptation

Adapted from DietrichGebert/ponytail, not the runtime plugin. Read
[provenance](PROVENANCE.md). Follow the central supplementary-workflow and
Understand Before Modify rules in `AGENTS.md`; Karpathy remains the baseline.
This skill adds no persistent mode, level switching, commands, or automatic
injection. Apply it to the task at hand, not as a new session controller.

## Before you write

Read the task and code it touches. List every place the change must reach:
callers, tests, fixtures, configuration, and exports. Check what it could break
for users, including data exposure and callers that stop working. That is scope;
extra features are not. Work remains with the authorized file owner.

## The smallest complete change

Take the first option that fully works:

1. Does it need to exist? Name unrequested features, options, and flexibility
   you are skipping. Clarify ambiguity that changes the design.
2. Already in this codebase? Reuse its helper, component, service, or pattern
   the way surrounding code does.
3. Standard library or platform feature? Prefer it unless the project already
   has its own appropriate abstraction.
4. Installed dependency? Reuse it; do not add a dependency for a few lines.
5. One line a reader understands at a glance? Use it; otherwise use the minimum
   clear implementation, not compressed code that needs decoding.

- Be lazy about the solution, not completeness: include required callers,
  tests and fixtures, through their owners.
- No speculative wrappers, options, conversions, or abstractions. Keep existing
  layers and conventions. Do not delete pre-existing work as unrelated cleanup.
- Before a bug fix, inspect every relevant caller and fix the evidenced root
  cause in the canonical layer. Moved code retains validation and error handling.
- Among equally small options, prefer correctness on edge cases.
- Follow `testing-quality` and area-specific checks, including configuration
  validation. This adaptation grants no exemption for “trivial” changes and
  never substitutes production asserts for required regression tests.
- Describe a deliberate shortcut's limit and upgrade condition without creating
  an unapproved code-comment convention.

Never cut trust-boundary validation, security, accessibility, essential error
handling, hardware calibration, or an explicit requirement. Report what you
skipped or did not verify and any material risk in the project report format.
