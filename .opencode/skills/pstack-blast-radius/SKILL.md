---
name: pstack-blast-radius
description: Advisory pstack change-risk planning to find cross-boundary breakage and the critical safety facts that need evidence.
license: MIT
---

# Blast radius — project adaptation

Read [provenance](PROVENANCE.md). Follow `AGENTS.md`; this is risk assessment,
not authority to write scripts, run an app, switch models or launch agents.
The reviewer returns findings only. Owner-run verification needs authorization;
unavailable proof is marked unproven, never silently replaced with confidence.

Listing direct callers is not enough. Look for breakage symbol search misses:
serialized data, lifecycle timing, version-specific library behavior, downstream
consumers, flags, configuration, and callers across languages or packages.

## Evidence ladder

For each fact the change's safety depends on, state where verification stopped:

1. Assertion alone — unproven.
2. Real `file:line` or pinned library source.
3. A traced failure path showing why the bad case cannot occur.
4. An authorized test or script exercising the real boundary and failing loudly
   if the fact is false.
5. An authorized same-surface reproduction in the running application.

Do not treat the highest rung as mandatory: use the cheapest sufficient check
allowed by the task. Suggest checks for owners when read-only or out of scope.

## Steps

1. Read the actual change and surrounding code: what symbols are added, changed,
   or removed, and what behavior differs beyond the obvious diff. Consult
   permitted local history where useful; do not assume a PR or external tool.
2. Find the one or two facts safety most depends on. Spend effort establishing
   them rather than generating a long list of hypothetical risks.
3. Trace beyond grep: installed dependency version and patches, teardown and
   scheduling, JSON/REST/WS consumers, fields, flags and downstream code.
4. Separate confirmed risks from possibilities and checked/cleared cases.
   Cite real evidence; do not invent callers or APIs. A search returning no
   results is evidence only about that search's coverage.
5. Propose the cheapest deterministic regression check for the critical fact.
   The orchestrator assigns it to the test owner if approved; report raw output
   only when it was actually run. Wider changes may warrant an independent
   existing reviewer, not automatic arena/swarm or model diversity.

## Hand back

- What changes, including non-obvious effects.
- The critical safety fact, evidence rung and proof (or **unproven**).
- Risks: mechanism, `file:line`, impact, likelihood and proposed check.
- Cleared cases and why.
- Smallest safe implementation plan: owners, modules/contracts/dependencies,
  tests, approval gates and verification before shipping. No merge/commit step
  is authorized by this skill.
