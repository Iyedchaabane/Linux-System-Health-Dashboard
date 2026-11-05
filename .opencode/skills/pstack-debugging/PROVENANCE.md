# pstack debugging excerpt provenance

Source: <https://github.com/painhardcore/pstack>, master pinned to
`7f2d936bba86c2c512c4ad83e759752f4f065b7c`.
Extracted/adapted `.opencode/skills/poteto-mode/playbooks/bug-fix.md`, SHA-256
`fb785ce4f075856432e3c03444df9904db3477c8628a825e257b503a7e464481`.
**Not** an upstream standalone skill; this directory is an explicitly local
instruction-only extraction. MIT, Copyright (c) 2026 Lauren Tan;
[full terms](../pstack-how/LICENSE).

Retained reproduction, binary-search/hypothesis elimination, evidence-backed
root cause, smallest justified fix and same-surface before/after verification.
Removed controller replacement, control-skill/browser obligations, repeat/wait
loops, automatic instrumentation, `why`/`architect`/`tdd` dependencies, inline
fallback implementation, staged failing-test commits and Opening a PR.
The scoped method requests authorized owner evidence instead; it never treats
an inconclusive reproduction as passing. Experimental rollback is a proposal,
not a destructive action. Runtime/helper dependencies: none. Distinct value:
an explicit hypothesis/reproduction loop, not a second test policy or router.
See [integration notes](../ponytail/PROVENANCE.md) for limitations and rollback.
