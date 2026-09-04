#!/usr/bin/env python3
"""call-scrub — pull and analyze your ElevenLabs Conversational-AI voice calls.

Lists recent conversations, or scrubs one transcript and surfaces what actually
happened: every tool the agent called, the result it got back, errors, and timing
— the fast way to debug "why did that call misbehave" instead of replaying audio.

BYOK: uses YOUR ElevenLabs API key (env ELEVENLABS_API_KEY or --api-key). Read-only;
nothing is written anywhere. Stdlib only (urllib).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

API = "https://api.elevenlabs.io/v1/convai"


def _get(path: str, key: str) -> dict:
    req = urllib.request.Request(API + path, headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _list(key: str, agent_id: str, n: int) -> int:
    q = f"/conversations?page_size={n}" + (f"&agent_id={agent_id}" if agent_id else "")
    convs = _get(q, key).get("conversations", [])
    if not convs:
        print("No conversations found.")
        return 0
    print(f"{'started(UTC)':<14} {'conversation_id':<40} {'msgs':>5} {'dur':>6}  status")
    import datetime
    for c in convs[:n]:
        ts = c.get("start_time_unix_secs")
        when = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%m-%d %H:%M") if ts else "?"
        print(f"{when:<14} {c.get('conversation_id',''):<40} {c.get('message_count',0):>5} "
              f"{str(c.get('call_duration_secs',0))+'s':>6}  {c.get('status','')}")
    return 0


def _scrub(key: str, cid: str) -> int:
    d = _get(f"/conversations/{cid}", key)
    turns = d.get("transcript", []) or []
    print(f"conversation {cid} — {len(turns)} turns\n")
    print("=== tool calls + results ===")
    calls = errors = 0
    for turn in turns:
        for tc in (turn.get("tool_calls") or []):
            calls += 1
            params = json.dumps(tc.get("params_as_json") or {})[:90]
            print(f"  CALL  {tc.get('tool_name','?'):<22} {params}")
        for tr in (turn.get("tool_results") or []):
            r = tr.get("result_value") or tr.get("tool_result") or ""
            rs = json.dumps(r)[:150]
            flag = "  ⚠" if any(w in rs.lower() for w in ("error", "fail", "timed out", "didn't", "abandon")) else ""
            if flag:
                errors += 1
            print(f"     ->  {tr.get('tool_name',''):<20} {rs}{flag}")
    print(f"\nsummary: {calls} tool call(s), {errors} flagged result(s) (⚠ = error/fail/timeout).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull + analyze ElevenLabs voice calls (BYOK).")
    ap.add_argument("--conversation-id", default="", help="scrub one call's transcript + tool activity")
    ap.add_argument("--agent-id", default="", help="filter the list to one agent")
    ap.add_argument("--list", action="store_true", help="list recent conversations (default)")
    ap.add_argument("--limit", type=int, default=12, help="how many to list (default 12)")
    ap.add_argument("--api-key", default="", help="EL API key (else env ELEVENLABS_API_KEY)")
    args = ap.parse_args()

    key = args.api_key or os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        sys.stderr.write("FATAL: no ElevenLabs API key. Set ELEVENLABS_API_KEY or pass --api-key. (BYOK)\n")
        return 2
    try:
        if args.conversation_id:
            return _scrub(key, args.conversation_id)
        return _list(key, args.agent_id, args.limit)
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"FATAL: ElevenLabs API {e.code} — check your key / id.\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"FATAL: {type(e).__name__}: {e}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
