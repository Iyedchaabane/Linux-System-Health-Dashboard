# pstack How provenance

Source: <https://github.com/painhardcore/pstack>, master pinned to
`7f2d936bba86c2c512c4ad83e759752f4f065b7c`.
Upstream README advertises copying `.opencode` skills and agents for OpenCode;
we selectively adapt instructions instead of replacing project orchestration.
MIT, Copyright (c) 2026 Lauren Tan; [full terms](LICENSE).

Reviewed complete sources and SHA-256:

- `.opencode/skills/how/SKILL.md`:
  `8132d32c24e47dad5793f9a2770d9cdd2f527ed0acc16db5a364dcbc9c2f79d4`
- `references/explorer-prompt.md` under that skill:
  `6300128385ee940fd42ecb84b0e623435440a2dc283eae54ee4a52ba56947ba1`
- `references/explainer-prompt.md` under that skill:
  `ddb89cebefc24e2b54517a331aedfe045b6971e101f45c71b8cef4cccff45bff`

Local changes: namespaced ID; inline investigation replaces automatic explorer/
explainer spawns, parent-model/reasoning selection and `poteto-mode` dependency.
The templates' substantive component/flow/boundary/evidence output is folded
into the skill; no missing helper references or executable files are installed.
Ambiguity that materially changes scope requires clarification. The existing
orchestrator may delegate under project policy; reviewers never delegate.
Runtime dependencies: none. Distinct value: structured subsystem tracing and
reconciliation, not another generic minimalism or architecture policy.
See [integration notes](../ponytail/PROVENANCE.md) for limitations and rollback.
