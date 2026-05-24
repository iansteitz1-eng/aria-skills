---
name: el-agent-deploy
description: Declarative ElevenLabs ConvAI agent reconciler. Reads el_agents.yaml and PATCHes the live agents to ensure each has the declared tool_ids attached + the declared system-prompt blocks appended (marker-gated, idempotent). Optional --provision-phone binds an existing Twilio number to an agent. Use when the user says "deploy el agent", "wire the tool", "update agent system prompt", "reconcile el agents", or before any agent-config change ships.
---

# el-agent-deploy

YAML-as-source-of-truth for EL ConvAI agents. Reconciles tool_ids + system-prompt blocks via the EL REST API. Optionally binds Twilio phone numbers.

## When to use

- Wire a new tool to an agent (replaces dashboard drag-drop)
- Append a system-prompt block (idempotent — won't double-append)
- Bind an existing Twilio phone number to an agent
- Audit agent state (`--dry-run` reports drift between YAML and live)

## How it works

1. Reads `el_agents.yaml`
2. Lists EL tool catalog (`GET /v1/convai/tools`) to resolve tool names → tool_ids
3. For each agent:
   - GETs current agent config
   - Builds new `tool_ids` = dedupe(existing + required)
   - Builds new `system_prompt` = existing + any marker-gated blocks not already present
   - PATCHes via `PATCH /v1/convai/agents/{agent_id}` (only if changes detected)
4. Idempotent: re-running with no YAML change = no API writes

## CLI

```sh
python3 el_agent_deploy.py                              # dry-run all agents
python3 el_agent_deploy.py --apply                      # apply all
python3 el_agent_deploy.py --apply --agent <slug>       # one agent
python3 el_agent_deploy.py --apply --agent <slug> --override-gate <value>
                                                        # force-apply through deploy_gate
python3 el_agent_deploy.py --apply \                    # bind phone
  --provision-phone <slug> \
  --phone-number +14155551234 \
  --twilio-sid ACxxxxxxxx \
  --to-number-name "Outbound Line"
```

## Safety

- **Default dry-run.**
- **`deploy_gate` field** per agent gates voice-lane-sensitive agents behind explicit override.
- **Marker-gated prompt append.** Never blanket-replaces.
- **Phone binding is a BIND not a CREATE** — requires existing Twilio number; doesn't buy from Twilio.

## Hosted version

[Aria Code](https://staycool.ai/aria-code) runs this with:
- Multi-agent dashboards
- Approval workflows for tool wires
- Prompt version history + diff
- Free tier · BYOK · no credit card

## License

Apache 2.0
