# question-economy — Cross-Harness Manifests

This directory holds discovery manifests for harnesses other than Claude Code. The Claude Code manifest is `../SKILL.md`. All manifests describe the SAME executable (`../question_economy.py`) — they're just discovery glue.

Part of the Path A multi-harness pattern.

## Manifest matrix

| Harness | File | Format |
|---|---|---|
| Claude Code (CLI) | `../SKILL.md` | YAML frontmatter |
| OpenAI / Codex / xAI Grok | `openai.json` | OpenAI Tool/Function schema |
| Google Gemini | `gemini.json` | `function_declarations` |
| MCP | `mcp.json` | MCP tool spec (2024-11-05) |

All describe the same input contract. The script is the source of behavior truth; manifests are discovery.

## Invocation contract

The harness adapter translates harness-side function arguments → CLI flags → invokes the script:

| Argument | Flag | Default |
|---|---|---|
| `session` | `--session <id>` | most recent transcript |
| `print_trend` | `--print-trend` | true |

## Cross-references

- `../SKILL.md` — Claude Code manifest, source of behavior truth
- `../README.md` — public skill overview
