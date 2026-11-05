---
name: pstack-debugging
description: Advisory adaptation of pstack's bug-fix playbook for evidence-driven reproduction, hypothesis elimination and regression planning.
license: MIT
---

# Debugging — adapted bug-fix playbook excerpt

Read [provenance](PROVENANCE.md). This is an explicitly edited extraction of a
playbook, not an upstream standalone skill or a replacement orchestrator.
Follow `AGENTS.md`. Investigation is read-only unless an owner receives an
approved implementation task. No automatic instrumentation, browser/network
tests, repeat loops, git operations or PR workflow is authorized here.

Be scientific: every proposed fix should trace to evidence. Defensive changes
that merely “might help” are hypotheses, not established fixes.

1. **Establish a reproduction.** Identify expected and actual behavior, matching
   surface and triggering conditions. Prefer the existing deterministic test
   harness. Run only authorized bounded checks; otherwise request owner-run
   evidence. If it will not reproduce, state the limitation instead of claiming
   it fixed. Do not force real hardware, privileged or external environments.
2. **Narrow the cause.** Form candidate hypotheses and choose the observation
   that eliminates the most remaining possibilities. Trace affected code using
   `pstack-how` when helpful and permitted history for regressions. Maintain a
   short table of hypothesis, expected observation, actual evidence and status.
   Instrumentation/logging is a separately scoped owner change with privacy and
   cleanup considered, not permission to mutate production or host state.
3. **Confirm the surviving mechanism.** Check related client/server and lifecycle
   boundaries. Do not infer root cause just because one workaround hides a
   symptom. Stop and report inconclusive if evidence cannot discriminate causes.
4. **Plan the smallest justified fix.** Report affected modules, owners,
   contracts, dependencies, tests and risks before modification. Contract or
   architecture changes still need approval; crossing a function boundary does
   not automatically trigger an architect agent or rewrite.
5. **Verify on the same surface.** Through the test owner, capture a regression
   failing before the fix and passing after it when practical. Distinguish unit
   branch coverage from reproducing the original bug. Wrong-surface or
   inconclusive checks are not passes. Report broader checks and remaining gaps.

If evidence refutes a hypothesis, do not ship the speculative change. Propose
removal of only that task's authorized experimental edits to its owner; never
reset, restore, stage or commit anyone's work automatically.

Return what was broken, root-cause evidence, proposed/implemented fix (clearly
distinguished), exact failing/passing output if available, and unresolved risks.
