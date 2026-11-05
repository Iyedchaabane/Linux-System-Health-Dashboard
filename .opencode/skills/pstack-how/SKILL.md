---
name: pstack-how
description: Advisory pstack investigation to trace existing subsystem behavior, data flow and boundaries before planning a change.
license: MIT
---

# How — project adaptation

Read [provenance](PROVENANCE.md). This is the `how` method from painhardcore/pstack,
not its controller. Follow `AGENTS.md`. Investigate read-only and inline; no
model selection, required helper skills, MCP grants, or automatic delegation.
The orchestrator alone may assign bounded research to existing approved agents.

## 1. Assess complexity

State the target and question. For a single module or utility, trace and explain
in one pass. For a subsystem, split into two to four non-overlapping angles and
investigate each. When in doubt, take the simple path. Ask if ambiguity would
materially alter scope; do not silently guess.

## 2. Explore

For each angle, record:

- **Components found:** types, services, functions and abstractions with paths
  and one-sentence responsibilities.
- **Flow:** trigger, functions called, data transformations, decision points,
  error/cleanup paths and what is called next.
- **Files read:** actual inspected paths and relevant line ranges.
- **Boundaries:** inputs, outputs, contracts and owning layers.
- **Non-obvious things:** surprising behavior and likely pitfalls.
- **Open questions:** anything not fully traced. Separate observation from
  inference; current behavior alone does not establish historical intent.

## 3. Synthesize

Reconcile overlapping accounts and contradictions by checking the code. Cite
specific files and symbols. Explain at the level of an engineer onboarding to
the subsystem, not annotated source or large code dumps. Use a small diagram
only if it clarifies a multi-component flow.

## 4. Present

Use the useful sections: Overview, Key Concepts, How It Works, Where Things
Live, Gotchas, and Open Questions. Do not pad simple explanations. If this
precedes modification, include the central Understand Before Modify assessment
of modules, contracts, dependencies, tests, risks, owners and verification.
