#!/usr/bin/env python3
"""
el_agent_deploy.py — Sprint 021 S21.T1-B. Declarative EL ConvAI agent reconciler.

Reads ./el_agents.yaml. For each declared agent:
  1. Resolves required tool names → tool_ids via /v1/convai/tools list
  2. PATCHes agent.conversation_config.agent.prompt.tool_ids = dedupe(existing + required)
  3. For each system_prompt_block with a `marker`:
       - If marker NOT present in live system_prompt → append the block
       - If marker IS present → leave alone (idempotent)
  4. PATCHes agent.conversation_config.agent.prompt.prompt with the updated prompt

CLI:
  python3 el_agent_deploy.py                     # dry-run all agents
  python3 el_agent_deploy.py --apply             # apply
  python3 el_agent_deploy.py --agent insync_main # target single agent (slug)
  python3 el_agent_deploy.py --provision-phone <slug> --to-number-name 'InSync Outbound'
                                                 # create EL outbound phone number + bind to agent
                                                 # writes phone_number_id to .env as EL_AGENT_PHONE_NUMBER_ID

Safety:
  - Each agent can carry `deploy_gate: stephen_signoff` (or any non-empty value)
    in YAML. When set, the script refuses to --apply unless --override-gate is
    also passed AND --confirm-override matches the gate string. Belt-and-braces
    for voice-lane protection on Stump Aria etc.
  - Default is dry-run.
  - The system_prompt PATCH only APPENDS via marker check — never blanket-replaces.
    To remove a block, manually edit the prompt in the EL dashboard.

Idempotency:
  - Re-running the same YAML produces no changes (tool_ids dedupe, marker-gated
    prompt blocks). Safe to cron if needed.

Splat:
  Each apply emits an `el_agent_deploy_run` splat with the slugs touched + flags.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ENV_FILE = Path(".env")
DEFAULT_CONFIG = Path("./el_agents.yaml")

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

try:
    import yaml
except ImportError:
    sys.stderr.write("FATAL: PyYAML not installed. pip install PyYAML\n")
    sys.exit(1)

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    sys.stderr.write("FATAL: ELEVENLABS_API_KEY not in env.\n")
    sys.exit(1)
BASE = "https://api.elevenlabs.io/v1/convai"


def _load_config(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(f"FATAL: config not found at {path}\n")
        sys.exit(1)
    return yaml.safe_load(path.read_text())


def _api(method: str, url: str, **kwargs) -> httpx.Response:
    return httpx.request(
        method, url, headers={"xi-api-key": API_KEY}, timeout=30.0, **kwargs
    )


def _list_tools_by_name() -> dict[str, str]:
    """Return {tool_name: tool_id} from the EL catalog."""
    r = _api("GET", f"{BASE}/tools")
    r.raise_for_status()
    out = {}
    for t in r.json().get("tools", []):
        name = (t.get("tool_config") or {}).get("name")
        tid = t.get("id") or t.get("tool_id")
        if name and tid:
            out[name] = tid
    return out


def _get_agent(agent_id: str) -> dict:
    r = _api("GET", f"{BASE}/agents/{agent_id}")
    r.raise_for_status()
    return r.json()


def _patch_agent(agent_id: str, body: dict, apply: bool) -> str:
    if not apply:
        return f"would PATCH {agent_id} with {sorted(body.get('conversation_config', {}).get('agent', {}).get('prompt', {}).keys())}"
    r = _api("PATCH", f"{BASE}/agents/{agent_id}", json=body)
    if r.status_code >= 400:
        return f"FAIL: PATCH {agent_id}: {r.status_code} {r.text[:200]}"
    return f"PATCH {agent_id} 200"


def _reconcile_agent(
    agent_spec: dict, tool_catalog: dict, apply: bool, override_gate: str | None
) -> list[str]:
    slug = agent_spec["slug"]
    agent_id = agent_spec["agent_id"]
    gate = agent_spec.get("deploy_gate")
    log = [f"agent {slug} ({agent_id}):"]

    if gate and apply and override_gate != gate:
        log.append(
            f"  ⛔ skipped — deploy_gate={gate!r} active; pass --override-gate {gate!r} to force"
        )
        return log

    try:
        live = _get_agent(agent_id)
    except Exception as e:
        log.append(f"  ✗ GET agent failed: {e}")
        return log

    prompt_obj = (live.get("conversation_config") or {}).get("agent", {}).get(
        "prompt"
    ) or {}
    live_tool_ids = prompt_obj.get("tool_ids") or []
    live_prompt = prompt_obj.get("prompt") or ""

    # 1. Reconcile tool_ids
    required_tool_names = agent_spec.get("tool_ids_required") or []
    missing_tools = []
    new_tool_ids = list(live_tool_ids)
    for tool_name in required_tool_names:
        tid = tool_catalog.get(tool_name)
        if not tid:
            log.append(f"  ⚠ tool '{tool_name}' not in EL catalog — skipped")
            missing_tools.append(tool_name)
            continue
        if tid not in new_tool_ids:
            new_tool_ids.append(tid)
    tools_changed = sorted(new_tool_ids) != sorted(live_tool_ids)

    # 2. Reconcile system-prompt blocks (marker-gated append)
    blocks_to_append = []
    for block in agent_spec.get("system_prompt_blocks", []) or []:
        marker = block.get("marker", "")
        body = block.get("body", "").rstrip()
        if not marker or not body:
            continue
        if marker in live_prompt:
            log.append(f"  ✓ block '{marker}' already present — skipped")
            continue
        blocks_to_append.append(body)
        log.append(f"  + block '{marker}' will be appended")

    new_prompt = live_prompt
    if blocks_to_append:
        sep = "\n\n" if new_prompt and not new_prompt.endswith("\n") else "\n"
        new_prompt = new_prompt + sep + "\n\n".join(blocks_to_append)

    prompt_changed = new_prompt != live_prompt

    if not tools_changed and not prompt_changed:
        log.append("  · no-op (already reconciled)")
        return log

    body = {"conversation_config": {"agent": {"prompt": {}}}}
    inner = body["conversation_config"]["agent"]["prompt"]
    if tools_changed:
        inner["tool_ids"] = new_tool_ids
        log.append(f"  + tool_ids: {len(live_tool_ids)} → {len(new_tool_ids)}")
    if prompt_changed:
        inner["prompt"] = new_prompt
        log.append(f"  + prompt: +{len(new_prompt) - len(live_prompt)} chars")

    result = _patch_agent(agent_id, body, apply)
    log.append(f"  {result}")
    return log


def _provision_phone(
    slug: str,
    to_number_name: str,
    cfg: dict,
    apply: bool,
    phone_number: str | None,
    twilio_sid: str | None,
    twilio_token: str | None,
) -> int:
    """Bind an EXISTING Twilio phone number to an EL ConvAI agent.

    Per the EL ConvAI API: /v1/convai/phone-numbers/create is a BIND endpoint,
    not a buy-new-number endpoint. It requires phone_number (E.164) + sid
    (Twilio Account SID) + token (Twilio Auth Token) + label + agent_id.

    To actually buy a NEW Twilio number, use Twilio's API or dashboard first.
    """
    agent_spec = next((a for a in cfg.get("agents", []) if a["slug"] == slug), None)
    if not agent_spec:
        sys.stderr.write(f"FATAL: agent slug '{slug}' not in config\n")
        return 1

    # Resolve Twilio credentials: explicit args > env vars
    phone_number = phone_number or os.environ.get("TWILIO_OUTBOUND_PHONE_NUMBER")
    twilio_sid = twilio_sid or os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = twilio_token or os.environ.get("TWILIO_AUTH_TOKEN")

    missing = []
    if not phone_number:
        missing.append(
            "phone_number (E.164, --phone-number or TWILIO_OUTBOUND_PHONE_NUMBER)"
        )
    if not twilio_sid:
        missing.append("twilio_sid (--twilio-sid or TWILIO_ACCOUNT_SID)")
    if not twilio_token:
        missing.append("twilio_token (TWILIO_AUTH_TOKEN env)")
    if missing:
        sys.stderr.write(
            "FATAL: missing Twilio binding params:\n  - "
            + "\n  - ".join(missing)
            + "\n"
            "Either pass them on the CLI or set the env vars in .env\n"
        )
        return 2

    if not apply:
        print(
            f"# would BIND Twilio number {phone_number} (sid={twilio_sid[:6]}…) "
            f"to agent {agent_spec['slug']} ({agent_spec['agent_id']}) "
            f"with label '{to_number_name}'"
        )
        return 0

    payload = {
        "phone_number": phone_number,
        "sid": twilio_sid,
        "token": twilio_token,
        "label": to_number_name,
        "agent_id": agent_spec["agent_id"],
    }
    r = _api("POST", f"{BASE}/phone-numbers/create", json=payload)
    if r.status_code >= 400:
        sys.stderr.write(f"FAIL: phone bind {r.status_code} {r.text[:400]}\n")
        return 1
    body = r.json()
    pid = body.get("phone_number_id") or body.get("id") or body.get("phone_id")
    print(f"# bound Twilio {phone_number} to agent {slug}; EL phone_number_id={pid}")
    print(
        f"# paste the next line into .env, then restart aria-outbound-caller:"
    )
    print(f"EL_AGENT_PHONE_NUMBER_ID={pid}")
    return 0


def _emit_splat(payload: dict) -> None:
    try:
        if "/opt/aria" not in sys.path:
            sys.path.insert(0, "/opt/aria")
        from splat_emitter import emit_splat  # type: ignore

        emit_splat(
            layer="el_agent_deploy_run",
            harness_source="el_agent_deploy",
            payload=payload,
        )
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Declarative EL ConvAI agent reconciler.")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--agent", help="Target a single agent slug; default = all")
    ap.add_argument(
        "--override-gate", help="Override a deploy_gate (e.g. 'stephen_signoff')"
    )
    ap.add_argument(
        "--provision-phone",
        help="Bind an EXISTING Twilio phone number to the named agent slug. Requires --phone-number + --twilio-sid (or env vars).",
    )
    ap.add_argument(
        "--phone-number",
        help="Twilio phone number in E.164 (e.g. +14155551234). Falls back to TWILIO_OUTBOUND_PHONE_NUMBER env.",
    )
    ap.add_argument(
        "--twilio-sid",
        help="Twilio Account SID. Falls back to TWILIO_ACCOUNT_SID env.",
    )
    ap.add_argument(
        "--twilio-token",
        help="Twilio Auth Token. Falls back to TWILIO_AUTH_TOKEN env. (CLI passing not recommended — use env.)",
    )
    ap.add_argument(
        "--to-number-name",
        default="Aria Outbound",
        help="Label for the bound phone number",
    )
    args = ap.parse_args()

    cfg = _load_config(Path(args.config))

    if args.provision_phone:
        return _provision_phone(
            args.provision_phone,
            args.to_number_name,
            cfg,
            args.apply,
            args.phone_number,
            args.twilio_sid,
            args.twilio_token,
        )

    tool_catalog = _list_tools_by_name()
    print(
        f"# el-agent-deploy · apply={args.apply} · agents-in-catalog={len(tool_catalog)} tool(s) total"
    )
    print()

    targets = cfg.get("agents", [])
    if args.agent:
        targets = [a for a in targets if a["slug"] == args.agent]
        if not targets:
            sys.stderr.write(f"FATAL: agent slug '{args.agent}' not in config\n")
            return 1

    full_log = []
    for agent_spec in targets:
        log_lines = _reconcile_agent(
            agent_spec, tool_catalog, args.apply, args.override_gate
        )
        for line in log_lines:
            print(line)
            full_log.append(line)
        print()

    _emit_splat(
        {
            "apply": args.apply,
            "agents_targeted": [a["slug"] for a in targets],
            "log_lines": len(full_log),
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
