# el-agent-deploy

> **YAML → ElevenLabs ConvAI agent configuration. One command.**

Reconcile your EL ConvAI agents' tool attachments + system-prompt blocks declaratively. Optional Twilio phone-number binding too. Stop clicking through the EL dashboard.

```sh
# Manual:
# 1. EL dashboard → Agents → click into each agent
# 2. Drag tools into Tools section
# 3. Edit system prompt textarea
# 4. Phone Numbers → click + bind to agent

# This skill:
python3 el_agent_deploy.py --apply --agent insync_main
```

## 30-second install

```sh
pip install -r requirements.txt
echo "ELEVENLABS_API_KEY=..." > .env

# Edit agents in el_agents.yaml
python3 el_agent_deploy.py             # dry-run
python3 el_agent_deploy.py --apply     # apply to all agents
python3 el_agent_deploy.py --apply --agent <slug>   # target one
```

## What you declare per agent

```yaml
agents:
  - slug: my_main_agent
    agent_id: agent_XXXXXXXXXXXXXXXXXXXX
    role: "Description for humans"
    tool_ids_required:
      - some_tool_name   # resolved to tool_id via EL catalog at runtime
    system_prompt_blocks:
      - marker: "## My block header"   # idempotency key
        body: |
          ## My block header
          Block content that gets appended to system prompt
          if marker not already present.
    # Optional safety brake — requires --override-gate to deploy
    deploy_gate: voice_lane_signoff
```

## Idempotent re-runs

- `tool_ids` are deduped against existing
- `system_prompt_blocks` use a `marker` line for idempotency — re-runs check if marker present, skip if so
- Never blanket-replaces system prompts — only appends marker-gated blocks

## Phone number binding (separate subcommand)

```sh
# Bind an EXISTING Twilio number to an agent (EL uses Twilio for ConvAI phones)
python3 el_agent_deploy.py --apply \
  --provision-phone my_main_agent \
  --phone-number +14155551234 \
  --twilio-sid ACxxxxxxxx \
  --to-number-name "Outbound Line"

# Outputs:
# EL_AGENT_PHONE_NUMBER_ID=phone_xxxxxxxxx
```

Paste that env var into your outbound-call orchestrator.

## Env vars required

| Var | Required for | Notes |
|---|---|---|
| `ELEVENLABS_API_KEY` | all | From EL dashboard |
| `TWILIO_ACCOUNT_SID` | --provision-phone | Falls back to `--twilio-sid` CLI arg |
| `TWILIO_AUTH_TOKEN` | --provision-phone | Falls back to `--twilio-token` CLI arg |
| `TWILIO_OUTBOUND_PHONE_NUMBER` | --provision-phone | Falls back to `--phone-number` CLI arg |

## Safety

- **Default is dry-run.** No PATCH calls until `--apply`.
- **`deploy_gate` field per agent** lets you require explicit `--override-gate <value>` for sensitive agents.
- **Marker-gated prompt append.** System prompts are NEVER blanket-replaced.
- **Phone binding requires existing Twilio number.** This skill BINDS to EL; it doesn't BUY from Twilio. Use `twilio phone-numbers:buy:local` first.

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with multi-agent dashboards + approval gates

## License

Apache 2.0
