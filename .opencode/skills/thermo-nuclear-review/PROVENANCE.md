# Thermo-Nuclear provenance

Source: <https://github.com/michael-denyer/pstack-claude>, main pinned to
`2f789d9d483d7bd800da4bbf3bc0ea7b27e907d9`.
Only `plugins/pstack/skills/thermo-nuclear-review/SKILL.md` is adapted,
SHA-256 `8e285b67eb7457715d44b1be8294c9a1aeae069242cb10a92903ad87f019c76a`.
No pstack investigation/router/setup content is taken from this distribution.
README “Other harnesses” advertises shared SKILL.md installs for OpenCode;
we use project-local native discovery instead of global symlinks/installers.

Its `NOTICE-skills.md` attributes thermos separately to
`cursor/plugins/thermos` at `118e73b0e196e4d49d5aade7ce6dd8985a621f68`,
Copyright (c) 2026 Cursor; this lineage is reported by the pinned distribution,
not an assertion of a separate direct Cursor checkout. Port modifications are
Copyright (c) 2026 Michael Denyer. Both MIT notices travel here:
[thermos license](LICENSE-thermos), [port license](LICENSE).

Retained diff-only audit, cross-module correctness, developer-experience
regressions, feature-gate leaks, intended-change distinction, severity
calibration, complete research and independent audit before other reviews.
Replaced impossible “NOTHING can slip through” guarantee with honest limits;
intended breakage never excuses unauthorized safeguard removal. PR discussions
are requested as authorized excerpts, not mandatory `gh`/`glab` execution.
Findings use existing project reviewer format; no report files or nested agents.
No helpers or runtime dependencies are needed by this standalone rubric.

Explicitly skipped: `thermos` parallel dispatcher (custom agents/model sheet),
the quality skill's aggressive structural rewrites, file/report writes and
divergent blocker policy (a separate safe findings-only adaptation is now
installed as `thermo-nuclear-code-quality-review`), both upstream agent definitions, platform
mappings, routing hooks, setup/model scripts and all unrelated skills.
This distinct correctness/security rubric supplements—not replaces—the local
reviewer's domain checklists. See [integration notes](../ponytail/PROVENANCE.md)
for configuration validation limits and rollback.
