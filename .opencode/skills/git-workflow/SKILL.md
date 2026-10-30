---
name: git-workflow
description: >
  Commit, branch, review and release hygiene for the Linux system health
  dashboard monorepo, with strict rules for what AI agents may and may not do
  with git. Use this skill whenever the user or an agent mentions commit, stage,
  branch, merge, rebase, push, pull request, tag, release, .gitignore,
  "save my work", "undo", "revert", "what changed", commit messages, diffs,
  reflog, or recovering lost work, even if they do not say "git". Also use it
  before any command that writes to the repository history or discards changes.
---

# Git Workflow Skill

Conventions for the monorepo (`backend/`, `frontend/`, `contracts/`, `docs/`, `.opencode/`). The core rule from `AGENTS.md` applies at all times: **agents do not commit, push, merge, reset, or delete anything unless the user explicitly asks.**

## 1. Non-negotiable rules

| # | Rule | Why |
|---|------|-----|
| 1 | **Read-only git is always fine** (`status`, `diff`, `log`, `show`, `blame`, `branch --list`). **Every write needs an explicit user request.** | History is the user's record; agents must not rewrite it. |
| 2 | **Never run destructive commands without showing exactly what will be lost and getting a clear "yes"**: `reset --hard`, `clean -fd`, `checkout -- <path>`, `restore` that discards edits, `push --force` (use `--force-with-lease` only if asked), `branch -D`, `stash drop`, rebase of pushed commits, `filter-branch`. | These cannot be undone reliably. |
| 3 | **Never change git configuration or identity** (`git config`, hooks, remotes) and never use `--no-verify` to skip checks. | Silent config changes and skipped hooks hide problems. |
| 4 | **Never commit secrets, tokens, `.env*`, unscrubbed host data, or generated junk.** Check the staged diff before every commit. | Once pushed, a leaked secret is compromised. |
| 5 | **One logical change per commit, and every commit leaves `make check` passing.** | Bisectable, revertable, reviewable history. |
| 6 | **Commit between agent tasks, never in the middle of one.** | Keeps each commit attributable to one specialist's single-writer task. |
| 7 | **Tests, contracts and generated files travel with the change that needs them.** | A commit that breaks the contract check or lacks its schema regeneration is broken. |

## 2. Who may do what

| Action | Who |
|--------|-----|
| `status`, `diff`, `log`, `show` | Any agent (read-only) |
| `add`, `commit`, `branch`, `switch`, `tag`, `merge`, `push`, `pull` | Only on explicit user request; the Orchestrator runs it (with permission prompts), specialists never do |
| Destructive commands (rule 2) | Only after the user confirms the exact command and what it discards |

When asked to commit: show `git status --short`, then `git diff --staged` (or `git diff` if nothing staged), propose the message, wait for approval, then commit. Never amend or rewrite a commit the user did not ask to change.

## 3. Branching

- Default branch is the repository's existing one (currently `master`). Do not rename it unless asked.
- Short-lived branches, one per phase task: `<type>/<scope>-<short-description>`.
  Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`. Example: `feat/domain-metric-result`, `test/ws-contract-fixtures`.
- Branch from an up-to-date default branch; keep branches under a few days; no long-lived feature branches.
- Merge to the default branch only after `make check` is green and `@code-reviewer` has no open Blocker or High findings. The **user** performs or explicitly authorizes the merge.
- Prefer squash merge for a branch with noisy WIP commits; use a regular merge when each commit is already clean and meaningful. State the choice in the PR.

## 4. Commits

**Format (Conventional Commits):**

```
<type>(<scope>): <imperative summary, max 72 chars>

<why this change, what it affects; wrap at 72>

Contract-Change: ws/v1 snapshot adds disk group (approved)   # only when applicable
Refs: Phase 1 task 1.2
```

- Types as in branching, plus `perf`. Breaking contract changes add `!` after the scope and a `BREAKING CHANGE:` footer.
- Scopes: `domain`, `infra`, `sampler`, `api`, `ws`, `contracts`, `frontend`, `tokens`, `tests`, `ci`, `deps`, `docs`, `agents`.
- Summary says what the change does, not "update files" or "fix stuff". The body explains **why** when it is not obvious.
- Split commits by concern: dependency changes (`deps`) alone with the lockfile; contract changes with regenerated schemas and fixtures; formatting-only changes never mixed with behavior changes.
- Commit `uv.lock` and `package-lock.json`; never commit `.venv/`, `node_modules/`, `dist/`, coverage output, caches, logs.

## 5. Pre-commit checklist (run before proposing any commit)

1. `git status --short`: only intended files; nothing unexpected or untracked-and-sensitive.
2. `git diff --staged`: read it. No debug code, commented-out blocks, TODOs without owner, fake or fabricated metric values in production paths, raw colors in components.
3. `make check` (or the real commands in `AGENTS.md`): report the **actual** result. If it was not run, say so and do not claim it passed.
4. Contracts: if `contracts/` changed, schemas regenerated and both server and client fixture tests pass.
5. No secrets, tokens, real hostnames, command lines or usernames in code, fixtures or logs.
6. Dependencies: only pre-approved ones, lockfile updated in the same commit.
7. Message follows section 4.

## 6. `.gitignore` baseline

```
# Python
__pycache__/  *.pyc  .venv/  .pytest_cache/  .mypy_cache/  .ruff_cache/  .coverage  htmlcov/  dist/  build/  *.egg-info/
# Node
node_modules/  frontend/dist/  frontend/coverage/  playwright-report/  test-results/
# Env and secrets
.env  .env.*  !.env.example  *.pem  *.key
# Editors and OS
.idea/  .vscode/  .DS_Store
# Logs
*.log
```

Commit `.opencode/` (agents, skills, commands) and `AGENTS.md`; they are project configuration. Do not commit local OpenCode state or session data.

## 7. Pull requests (when the repository has a remote)

PR description:

```
Summary: what and why
Phase/task: ...
Contracts touched: none | list with approval reference
Tests: commands run -> actual results; not run and why
Review: reviewer findings by severity, resolved or open
Risks / follow-ups:
Checklist: make check green, no secrets, lockfiles updated, docs updated
```

Keep PRs small (one task). A PR that mixes contract, backend and frontend changes is split unless the contract change requires them together.

## 8. Tags and releases

- Milestone tags after each completed phase: `phase-N-complete` (annotated, user-authorized).
- Release tags use semantic versioning `vMAJOR.MINOR.PATCH`; a wire-protocol version bump is a MAJOR change of the API contract and is documented in `contracts/ws/v1/PROTOCOL.md` and the changelog.
- Tag only after the release checklist in `testing-quality` section 14 is green.

## 9. Recovery (read first, act only with approval)

- "I lost changes": `git reflog` and `git fsck --lost-found` are read-only; show findings before restoring anything.
- Undoing a pushed commit: prefer `git revert <sha>` (adds a new commit) over rewriting history.
- Undoing local uncommitted work is destructive: show `git diff` of what would be lost and wait for confirmation.
- Before any risky operation, offer a safety net: `git branch backup/<name>` or `git stash push -u -m "<note>"` (both are writes, so only with approval).

## 10. Common pitfalls

- Committing "while I'm here" changes unrelated to the task.
- Committing a red build or an unregenerated schema.
- Mixing dependency upgrades with feature work.
- Staging with `git add -A` without reading the diff (picks up secrets and artifacts).
- `--no-verify`, `--amend` or force-push to "tidy up" without being asked.
- Agents committing mid-task so two specialists' work lands in one commit.
- Vague messages ("fixes", "wip", "update").
- Committing recorded fixtures that still contain real hostnames, usernames or command lines.
- Rewriting history that was already pushed or shared.

## 11. Definition of done for a git operation

- [ ] The user asked for it (or it is read-only).
- [ ] Staged diff reviewed; no secrets or artifacts; scope matches one task.
- [ ] `make check` result reported honestly.
- [ ] Message follows the format; contract changes declared.
- [ ] Nothing destructive happened without confirmation.
- [ ] Final report lists the commit hash, files, and anything left uncommitted.

## 12. Operations requiring user approval

Every write command (commit, branch, tag, merge, push, pull, stash), every destructive command in rule 2, any change to git config, hooks, remotes or `.gitignore` policy, adding a hook framework (for example `pre-commit`), and renaming the default branch.