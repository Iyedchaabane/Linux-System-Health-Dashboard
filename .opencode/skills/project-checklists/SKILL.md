---
name: project-checklists
description: Consult targeted project details for approved tooling, phase scope, MetricResult, sampling/client/history limits or thresholds; dashboard brief/screenshots and color constraints; command entry points or OpenCode permission guidance; imported advisory workflows; detailed test planning for backend, metrics, WebSocket, frontend, fixtures, coverage or CI. Load only for the relevant topic, then read its named reference section, not all checklists.
---

# Project checklists (on demand)

These extracted project requirements supplement `AGENTS.md`; they do not grant
permissions or override ownership, contracts, approval gates or user instructions.
Approved decisions remain binding even when this skill is not loaded. Do not load
every reference for every task. Paths below are relative to this skill directory;
repository paths within references are relative to the repository root.

## Select only the relevant reference/section

| Trigger | Reference and section |
| --- | --- |
| Tooling, phase scope, metric result, limits, thresholds, history | `references/project-details.md` — Approved decisions |
| Dashboard layout, styling, charts, navigation, widgets, screenshots | `references/project-details.md` — Dashboard design reference |
| Theme, colors, tokens, contrast, status styling | `references/project-details.md` — Color system |
| File locations, skill combinations, test/build command discovery | `references/project-details.md` — Repository layout / Skill routing / Commands |
| Imported minimalism, investigation, risk, debugging or deep review | `references/project-details.md` — Supplementary instruction-only workflows |
| OpenCode agent/skill layout or permission work | `references/project-details.md` — OpenCode configuration notes |
| Test setup or uncertain target/framework/contract evidence | `references/testing-details.md` — Targeted inspection |
| Unit/integration/E2E/contract strategy | `references/testing-details.md` — Testing architecture |
| API, metrics, permissions, process races, sampler lifecycle | `references/testing-details.md` — Backend testing |
| WebSocket endpoint, concurrency, reconnect, shutdown | `references/testing-details.md` — WebSocket testing |
| Components, hooks, charts, themes, accessibility | `references/testing-details.md` — Frontend testing |
| Fixtures, flaky tests, performance, security, coverage, CI | Matching section of `references/testing-details.md` |

Trust orchestrator findings for discovery; verify only what you will modify.
Reviewers modify nothing but still verify the focused diff and integration
evidence read-only. Missing or contradictory evidence goes to the orchestrator.
Use exact commands and compact actual results, with detailed logs by reference.
Examples are not authorization to install tools, change configuration or run checks.
