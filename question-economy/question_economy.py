#!/usr/bin/env python3
"""question_economy.py — extract the question→answer ledger from a Claude Code session.

Pairs with the question-economy SKILL. The script EXTRACTS (mechanical); the
skill's steps CLASSIFY (judgment).

Emits, to stdout, a JSON summary of:
  - hard questions : AskUserQuestion modal calls (focus-stealing — costliest)
  - soft questions : an assistant turn ending in '?' + the user's next reply
and appends ONE metric row per run to question_economy_log.jsonl so the
question rate is trackable across sessions (the proof the loop is working).

Usage:
  python3 question_economy.py [--session <id>] [--projects-dir DIR] [--print-trend]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timezone


def _resolve_memory_dir() -> str:
    """Find this Claude Code install's long-term memory dir, portably.
    Looks for ~/.claude/projects/*/memory (the dir holding MEMORY.md); falls
    back to ~/.claude/memory, creating it if absent."""
    cands = sorted(glob.glob(os.path.expanduser("~/.claude/projects/*/memory")))
    for c in cands:
        if os.path.exists(os.path.join(c, "MEMORY.md")):
            return c
    if cands:
        return cands[0]
    d = os.path.expanduser("~/.claude/memory")
    os.makedirs(d, exist_ok=True)
    return d


def _projects_dir(arg: str | None) -> str:
    if arg:
        return os.path.expanduser(arg)
    return os.path.dirname(_resolve_memory_dir())  # holds the *.jsonl transcripts


def _latest_transcript(projects_dir: str) -> str | None:
    js = glob.glob(os.path.join(projects_dir, "*.jsonl"))
    return max(js, key=os.path.getmtime) if js else None


def _text(content) -> str:
    """Flatten a message.content (str | list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _is_real_user_text(row) -> str | None:
    """Return the user's plain-text answer, or None if this isn't a genuine
    user turn (skip tool_result, system-reminder, local-command echoes)."""
    if row.get("type") != "user":
        return None
    content = row.get("message", {}).get("content", "")
    blob = json.dumps(content)
    if "tool_result" in blob or "system-reminder" in blob or "local-command" in blob:
        return None
    return _text(content).strip() or None


def extract(transcript: str) -> dict:
    rows = []
    with open(transcript) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    hard, soft = [], []
    for i, row in enumerate(rows):
        if row.get("type") != "assistant":
            continue
        content = row.get("message", {}).get("content", [])
        blocks = content if isinstance(content, list) else []

        # (a) HARD: AskUserQuestion modal calls
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "tool_use" \
                    and b.get("name") == "AskUserQuestion":
                for q in (b.get("input", {}) or {}).get("questions", []):
                    hard.append({
                        "header": q.get("header", ""),
                        "question": q.get("question", ""),
                        "options": [o.get("label", "") for o in q.get("options", [])],
                    })

        # (b) SOFT: assistant prose ending in a question → next real user reply
        txt = _text(content).strip()
        if txt and "?" in txt[-300:]:
            answer = None
            for j in range(i + 1, min(i + 9, len(rows))):
                a = _is_real_user_text(rows[j])
                if a:
                    answer = a
                    break
            if answer:
                tail = txt[-300:]
                soft.append({
                    "question_tail": tail[tail.rfind(".") + 1:].strip()[:280],
                    "answer": answer[:280],
                })

    return {
        "session_id": os.path.basename(transcript).replace(".jsonl", ""),
        "turns_scanned": len(rows),
        "hard_questions": hard,
        "soft_questions": soft,
        "counts": {"hard": len(hard), "soft": len(soft),
                   "total": len(hard) + len(soft)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session")
    ap.add_argument("--projects-dir")
    ap.add_argument("--print-trend", action="store_true")
    args = ap.parse_args()

    pdir = _projects_dir(args.projects_dir)
    transcript = (os.path.join(pdir, f"{args.session}.jsonl")
                  if args.session else _latest_transcript(pdir))
    if not transcript or not os.path.exists(transcript):
        print(json.dumps({"error": "no transcript found", "projects_dir": pdir}))
        return

    summary = extract(transcript)

    log_path = os.path.join(_resolve_memory_dir(), "question_economy_log.jsonl")
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": summary["session_id"],
            "turns": summary["turns_scanned"],
            "hard": summary["counts"]["hard"],
            "soft": summary["counts"]["soft"],
            "total": summary["counts"]["total"],
        }) + "\n")
    summary["log_path"] = log_path

    if args.print_trend and os.path.exists(log_path):
        with open(log_path) as f:
            tail = [json.loads(l) for l in f if l.strip()][-8:]
        summary["trend"] = [{"session": r["session_id"][:8], "hard": r["hard"],
                             "soft": r["soft"], "total": r["total"]} for r in tail]

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
