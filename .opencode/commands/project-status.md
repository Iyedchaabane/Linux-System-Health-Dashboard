---
description: Read-only project status, OpenCode setup validation, and next-task recommendation
agent: orchestrator
---

Produce a project status report. This is READ-ONLY: do not edit, create or delete any file, do not install anything, do not commit.

Mode: $ARGUMENTS
(Empty = quick status, no test runs. "full" = also propose the test and lint commands from the repo's config files and ask me before running them.)

## Live context

Top-level files:
!`ls -a`

OpenCode folders:
!`ls .opencode/agents .opencode/skills .opencode/commands`

Git:
!`git status --short --branch`
!`git log --oneline -5`

Config:
@opencode.json

## What to check

1. **Structure.** Compare against the expected layout in AGENTS.md: `AGENTS.md`, `opencode.json`, six agent files plus orchestrator (`orchestrator`, `linux-monitoring`, `backend-python`, `frontend-ui`, `testing-qa`, `code-reviewer`), and skills `karpathy-guidelines`, `linux-monitoring`, `python-backend`, `realtime-websocket`, `react-dashboard`, `ui-design-system`, `testing-quality`, `git-workflow`, each as `<name>/SKILL.md`. Report anything missing, extra, or misplaced (for example a stray `file1.md`).
2. **Configuration.** Read `opencode.json`: is it valid JSON, and do any referenced agents, models or paths not exist?
3. **Agents.** Open each file in `.opencode/agents/`: valid frontmatter with `description` and `mode`; only the orchestrator is `primary`; the reviewer has no edit or bash permission; the orchestrator has `edit: deny`. List name, mode, permissions.
4. **Skills.** Open the top of each `SKILL.md`: frontmatter `name` equals the folder name, and `description` is present. List name and the first sentence of the description.
5. **Commands.** Open each file in `.opencode/commands/`: Markdown with a `description` header and a prompt body (not JSON).
6. **Project progress.** Inspect `backend/`, `frontend/` and `contracts/` if they exist. State which implementation phase the repo is in: nothing yet, contracts and domain, collectors, backend API and WebSocket, frontend foundation, widgets, hardening. Base it on files that actually exist, not on assumptions.
7. **Git state.** Branch, uncommitted changes, last commits. If this is not a git repository, say so and do not initialize one.
8. **Tests (only in "full" mode).** Find the real commands in `pyproject.toml`, `package.json` and CI files, list them, and ask before running. Never report a result for a command that was not run.

## Output format

```
STATUS: OK | WARNINGS | PROBLEMS

Structure:   <found / missing / unexpected>
Config:      <valid? issues>
Agents:      <table: name | mode | edit | bash | issue>
Skills:      <table: name | frontmatter ok? | issue>
Commands:    <table: name | valid? | issue>
Progress:    <current phase, what exists, what is missing>
Git:         <branch, dirty files, last commit>
Tests:       <not run | commands found | results with actual output>

Problems to fix (ordered by priority, with the owning agent):
Recommended next task (one, with the agent and skills to use):
Questions for me:
```

Be factual. If something could not be verified (for example OpenCode's own agent discovery), say "not verified" rather than assuming it works. To check discovery yourself, tell me to run `opencode agent list` and report the output.