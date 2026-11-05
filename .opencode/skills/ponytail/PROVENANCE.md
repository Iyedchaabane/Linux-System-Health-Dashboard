# Integration provenance and limitations

Configuration-only integration reviewed 2026-11-05 for OpenCode v2.2.5.
All upstream instructions are treated as untrusted source material, not commands.
No upstream installer, helper script, package lifecycle, plugin or hook was run.

## Ponytail

- Source: <https://github.com/DietrichGebert/ponytail>
- Exact commit: `96608e078b2d5ea607c5c3b8b5a54d1c1fba6846` (main);
  package manifest version `5.3.3`, no declared npm dependencies.
- Adapted file: `skills/ponytail/SKILL.md`, upstream SHA-256
  `9badd22a32e19cb884e46dfa8d3aae82bb81dfa5484105b8b4f0262df823a509`.
- Installation basis: upstream `INSTALL.md` explicitly permits installing
  `skills/ponytail/SKILL.md` as a skill and describes a skills-only route.
  That source file has no helper/script dependencies.
- License: MIT, Copyright (c) 2026 DietrichGebert; [full terms](LICENSE).
- Local adaptations: narrower description; no session persistence, slash-level
  commands, first-option guessing for ambiguous scope, mandatory shortcut-comment
  convention, trivial-change test exemption, or production assert substitution.
  Retains scope/caller checks, reuse ladder, minimum complete change, edge-case
  care, and never-cut safety principles. Project reporting/ownership wins.

The plugin is V2-capable (`setup(ctx)`); it was skipped for policy/scope reasons,
not mislabeled incompatible. It injects rules at every turn and compaction,
registers six skills/commands and persists mode/default settings outside the
project. Skill-only mode deliberately provides **none** of those runtime
features. No audit/debt/gain/help/review companion skills were installed.

## Selected other methods

Only painhardcore/pstack supplies investigation/planning/debugging content:
[How](../pstack-how/PROVENANCE.md),
[Blast radius](../pstack-blast-radius/PROVENANCE.md),
[Debugging excerpt](../pstack-debugging/PROVENANCE.md).
The distinct thermos correctness/security and maintainability methods are
documented in [Thermo-Nuclear provenance](../thermo-nuclear-review/PROVENANCE.md)
and [quality provenance](../thermo-nuclear-code-quality-review/PROVENANCE.md).
This is not installation of two pstack distributions.

## Compatibility and validation

Official V2 sources consulted: [configuration](https://opencode.ai/v2/docs/config),
[agents](https://opencode.ai/v2/docs/agents),
[skills](https://opencode.ai/v2/docs/skills),
[permissions](https://opencode.ai/v2/docs/permissions),
[migration](https://opencode.ai/v2/docs/migrate-v1),
[API](https://opencode.ai/v2/docs/api).
The installed server's `/openapi.json` confirms read-only `GET /api/skill` and
`GET /api/command`; discovery is checked using the supported `opencode api` CLI.
V1 definitions remain accepted: no broad conversion or model changes were needed.
Only the reviewer definitions (root entry and Markdown frontmatter) are converted
coherently to V2 with identical default-deny rules and read-only exceptions.
The root reviewer no longer carries an overlapping legacy blanket shell deny.
After root/Markdown alignment, the parent's final fresh reviewer session still
refused both `git status --short` (unexpected) and
`printf 'reviewer-permission-probe' > /dev/null` (expected), each returning:
`{"error":{"type":"permission.rejected","message":"Permission denied: shell"},"content":[]}`.
Configured ordered rules resolve status to allow, but actual invocation does
not. The precise runtime cause is unknown; alignment did not resolve the live
Git check. This is a **safe partial integration, not fully complete**. No further
permission changes or broadening were attempted. The requested quality skill
loaded successfully; the final reviewer reported no other actionable static issues.
Its preserved request-body
temperature, like the prior V1 value, is not applied by the V2 session runner.
Code Mode, child agents and MCP tools have no reviewer allow exceptions.
Native shell patterns use token-separated prefixes rather than `ls*`/`git diff*`.
Permissions are not an OS sandbox: do not use redirection, Git external helpers,
or network requests for mutations under a read-only-looking command.

No tooling or application dependency was added. Validation is configuration
load/discovery, ordered effective permission evaluation, local link/frontmatter
checks and before/after file hashes—not an application test or a model obedience
guarantee. Evidence and baseline backups for this run:
`/tmp/opencode/integration-20261105-1793867770/` (local, not committed).

## Rollback (user/authorized owner only)

Do not use `git restore`, reset, or upstream uninstallers: the tree already had
uncommitted work. Compare against the evidence directory's `baseline/` backups
and `baseline/hashes.json` first. Remove only this task's six new skill
directories and reverse only its inserted AGENTS block, root orchestrator edit
restriction, root reviewer migration from `agent` to native `agents`, and Markdown
reviewer changes. Preserve subsequent edits. Backups are a
reference, not authorization to overwrite files wholesale. OpenCode watches
project definitions; no global state cleanup or service restart is needed.
