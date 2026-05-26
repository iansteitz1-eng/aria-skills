# stripe-sync — Cross-Harness Manifests

This directory holds discovery manifests for harnesses other than Claude Code. The Claude Code manifest is `../SKILL.md` (the parent dir). All four manifests describe the SAME `stripe_sync.py` script — they're just discovery glue.

This is the **Path A pilot** for the Aria multi-harness skill distribution pattern. Recommended sequence in `/opt/aria/v4/sprints/055_master_todo_triage/reference/platform_agnostic_skills.md`.

## Manifest matrix

| Harness | File | Format spec | Tested |
|---|---|---|---|
| **Claude Code** (CLI) | `../SKILL.md` | YAML frontmatter; slash-command invocation | ✅ 17/17 in `aria-skill-test` |
| **OpenAI / Codex / xAI Grok** | `openai.json` | OpenAI Tool/Function calling schema (JSON Schema body) | ⏳ untested in live harness |
| **Google Gemini** | `gemini.json` | Gemini `function_declarations` array | ⏳ untested |
| **MCP** (Model Context Protocol) | `mcp.json` | MCP tool spec (2024-11-05) | ⏳ untested |

All four describe **the same input contract**: `config`, `apply`, `prod`, `write_env`. The script does the work; manifests are just how each harness discovers/invokes it.

## Why the same JSON Schema appears in three files

OpenAI's Tool format, Gemini's `function_declarations`, and MCP's `inputSchema` all use **JSON Schema** for the parameters body. The wrapper differs (`type: function` vs `function_declarations: [...]` vs `name + inputSchema`) but the parameters block is identical content per harness.

A future refactor could:
- Keep ONE `canonical.json` JSON Schema as source of truth.
- Emit the three wrapper variants from it via a build step (5 lines of Python).
- Bake that into the `aria-skill-template` scaffold so every new skill ships all variants for free.

Filed as Window B work — see ops_log #423.

## Invocation contract (the same on every harness)

Every harness ultimately runs:

```sh
python3 stripe_sync.py [--config <path>] [--apply] [--prod] [--write-env]
```

The harness adapter is responsible for:
1. Calling `stripe_sync.py` with the right CLI flags derived from the harness's function-call arguments.
2. Capturing stdout/stderr for the harness's tool-result envelope.
3. Forwarding exit code (0 = ok, 2 = needs-creds, non-zero-other = error).

This invocation is identical across Codex, Grok, Gemini, MCP, and Claude Code — the script is the moat; manifests are just discovery.

## What's deliberately NOT in the manifests

- **Trigger phrases.** Claude Code uses them; OpenAI / Gemini / MCP don't. Trigger logic lives in the host harness, not in the manifest.
- **Cost / tier gating.** Premium-skill tier checks happen at the gateway (when the user's harness calls into our `aria-skills-premium` repo), not in the manifest.
- **Concurrency limits.** Same — harness-side concern.

## Test pattern (when a harness is wired up)

```sh
# OpenAI / Codex / Grok (using openai-python client):
python3 -c "import openai, json; c=openai.OpenAI(); r=c.chat.completions.create(model='gpt-4o', messages=[{'role':'user','content':'sync stripe in dry-run'}], tools=[json.load(open('openai.json'))]); print(r.choices[0].message.tool_calls)"

# Gemini (using google-generativeai):
# (template; needs Gemini client harness)

# MCP (using mcp-server-sdk in any client):
# server = MCPServer.load_skill('stripe-sync', cwd=..., manifest='mcp.json')
```

## Cross-references

- Parent: `../SKILL.md` (Claude Code format — source of behavior truth)
- Script: `../stripe_sync.py` (the actual implementation)
- Spec: `/opt/aria/v4/sprints/055_master_todo_triage/reference/platform_agnostic_skills.md`
- Doctrine: `feedback_implementation_is_a_skill_in_gated_repo` (gated vs public split)
