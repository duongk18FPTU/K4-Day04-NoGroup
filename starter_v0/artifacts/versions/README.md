# Artifact version map

Each evaluation version changes one main hypothesis:

| Version | System prompt | Tool declarations | Hypothesis |
|---|---|---|---|
| v0 | `v0/system_prompt.md` | `v0/tools.yaml` | Untouched starter baseline. |
| v1 | `v1/system_prompt.md` | `v0/tools.yaml` | Explicit routing, argument, multi-tool, and latest-turn rules reduce core errors. |
| v2 | `v1/system_prompt.md` | `../tools.yaml` | Precise capability boundaries and schemas reduce wrong tools/arguments. |
| v3 | `v3/system_prompt.md` | `../tools.yaml` | Trust, confirmation, privacy, and stale-state rules reduce adversarial failures without routing regression. |

The root `artifacts/system_prompt.md` and `artifacts/tools.yaml` are the final v3 pair.
