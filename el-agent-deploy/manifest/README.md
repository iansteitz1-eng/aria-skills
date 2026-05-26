# el-agent-deploy — Cross-Harness Manifests

This directory holds discovery manifests for harnesses other than Claude Code. The Claude Code manifest is `../SKILL.md`. All four manifests describe the SAME executable — they're just discovery glue.

Part of the Path A multi-harness pattern. Pilot reference: `aria-skills-repo/stripe-sync/manifest/README.md`.

## Manifest matrix

| Harness | File | Format |
|---|---|---|
| Claude Code (CLI) | `../SKILL.md` | YAML frontmatter |
| OpenAI / Codex / xAI Grok | `openai.json` | OpenAI Tool/Function schema |
| Google Gemini | `gemini.json` | `function_declarations` |
| MCP | `mcp.json` | MCP tool spec (2024-11-05) |

All describe the same input contract. Script is the source of behavior truth; manifests are discovery.

## Invocation contract

The harness adapter translates harness-side function arguments → CLI flags → invokes the script.

## Cross-references

- `../SKILL.md` — Claude Code manifest, source of behavior truth
- `/opt/aria/v4/sprints/055_master_todo_triage/reference/platform_agnostic_skills.md` — Path A architecture
- `aria-skills-repo/stripe-sync/manifest/README.md` — pilot reference
