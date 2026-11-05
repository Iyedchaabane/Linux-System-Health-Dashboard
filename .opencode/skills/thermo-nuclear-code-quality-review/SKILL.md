---
name: thermo-nuclear-code-quality-review
description: Findings-only Thermo-Nuclear maintainability audit of changed code for cohesion, duplication, branching complexity and canonical-layer/type boundaries.
license: MIT
---

# Thermo-Nuclear Code Quality Review — findings-only adaptation

Read [provenance](PROVENANCE.md). Follow `AGENTS.md` and the existing reviewer
permissions and report format. This rubric complements the separate
`thermo-nuclear-review` correctness/security audit; it does not replace project
architecture rules or authorize implementation.

Review only the requested change and its integration points, with the agreed
baseline. Use surrounding code to establish context, not to demand unrelated
cleanup. Investigate inline: no nested agents, model selection, report files,
autofix, refactoring, host mutation or permission bypass.

## Maintainability questions

1. **Canonical layer and reuse:** does added logic belong in this layer? Does
   an existing canonical helper already solve it? Identify concrete duplicated
   behavior or leaked implementation details, not merely similar syntax.
2. **Cohesion and coupling:** did a cohesive component gain unrelated concerns,
   shared state or hidden dependencies? Trace the affected responsibilities and
   explain the maintenance cost, rather than prescribing decomposition by size.
3. **Branching complexity:** do scattered flags, special cases or repeated
   conditionals obscure a real invariant? Would an existing domain model or
   simpler direct flow remove concepts rather than spread them across helpers?
4. **Type and contract boundaries:** do casts, avoidable optionality, `any`,
   loosely shaped objects or silent fallbacks hide assumptions? Explain the
   specific invariant and its canonical boundary; do not treat every `unknown`
   or defensive check as a smell without understanding its purpose.
5. **Abstractions:** does a wrapper, generic mechanism or pass-through helper
   earn its indirection? Compare a focused simpler alternative with actual
   requirements. Respect existing layering; fewer lines alone is not better.
6. **Orchestration and atomicity:** could related updates leave inconsistent
   state? Does sequencing or parallelism add avoidable complexity? Check shared
   state, ordering and resource limits before suggesting concurrency changes.

File growth can prompt investigation, but **no line-count threshold is an
automatic blocker**. Likewise, a hypothetical elegant rewrite is not a defect.
Look for evidenced regressions in understandability, coupling or invariants;
do not demand architecture changes, new abstractions or parallelism by default.

## Findings and recommendations

Return a small set of high-conviction, actionable findings with `file:line`,
evidence, maintenance impact and the smallest focused recommendation to the
owning specialist. Distinguish confirmed regressions from optional suggestions.
Prioritize structural regressions and boundary problems over cosmetic nits.
Use the project's existing severity and approval rules, not a new quality bar.
If a broader redesign seems useful, label it separately as an optional proposal
requiring approval; never implement it. Report unverified assumptions and checks.
Say explicitly when no actionable findings exist.
