#!/usr/bin/env python3
"""
goal_to_plan.py — turn a goal into an agent-ready brief: a spec_charter plus a dispatch block.

The brief is the bottleneck of an AI-native team, so it should be a file, not a chat
message. Everything prints to stdout; --write saves the same text. Fields you do not
supply render as TODO so the gaps stay visible.

Usage:
  goal_to_plan.py --goal "Ship the recent-calls dedup fix" \
      --acceptance "a real call's card shows recent calls exactly once"
  goal_to_plan.py --goal ... --acceptance ... --skill surgical-patch --skill premortem \
      --context src/gateway/main.py --deny "billing/*" \
      --risk "anchor drift|one file|med|assert the match count before writing" \
      --role "gateway lane" --owned-file src/gateway/main.py --write plans/dedup.md

Exit codes:
  0 = brief rendered
  2 = invocation error
"""
import argparse
import datetime
import json
import os
import sys

TODO = "TODO"


def _join(items: list[str]) -> str:
    items = [i.strip() for i in items if i and i.strip()]
    return "; ".join(items) if items else TODO


def _risk_lines(risks: list[str]) -> list[str]:
    if not risks:
        return [f"  - {TODO} (run premortem: failure · blast radius · likelihood → cheapest guard)"]
    out = []
    for raw in risks:
        parts = [p.strip() for p in raw.split("|")]
        parts += [TODO] * (4 - len(parts))
        failure, blast, likelihood, guard = parts[:4]
        out.append(f"  - {failure} · {blast} · {likelihood} → {guard}")
    return out


def render_charter(a: argparse.Namespace, today: str) -> str:
    title = a.title or a.goal
    lines = [
        f"# {title} · spec_charter v1",
        f"**Opened:** {today}",
        "",
        f"**Goal (one sentence):** {a.goal}",
        f"**Acceptance criterion (the bar):** {a.acceptance}",
        f"**Scope — IN:** {_join(a.scope_in)}",
        f"**Scope — OUT (explicitly not now):** {_join(a.scope_out)}",
        f"**Skills:** {_join(a.skill)}",
        f"**Tools:** {_join(a.tool)}",
        f"**Context (read):** {_join(a.context)}",
        f"**Do NOT touch:** {_join(a.deny)}",
        "**Risks (premortem → guard):**",
        *_risk_lines(a.risk),
        f"**Verification (how we prove the bar is met, in-product not code-trace):** {a.verification or TODO}",
    ]
    return "\n".join(lines)


def render_dispatch(a: argparse.Namespace) -> str:
    lines = [
        f"ROLE: {a.role or TODO}",
        f"OWNED FILES: {_join(a.owned_file)}",
        f"ACCEPTANCE: {a.acceptance}",
        f"REPORT: {a.report or 'on green, or on the first blocker'}",
        "CONTEXT: the spec_charter above plus the scoped reads it lists",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render an agent-ready brief (spec_charter + dispatch block) from a goal and one acceptance criterion.")
    ap.add_argument("--goal", required=True, help="the outcome in one sentence")
    ap.add_argument("--acceptance", required=True, help="the one objective, testable bar that defines done")
    ap.add_argument("--title", help="charter title (default: the goal)")
    ap.add_argument("--scope-in", action="append", default=[], help="something explicitly in scope; repeatable")
    ap.add_argument("--scope-out", action="append", default=[], help="something explicitly out of scope for now; repeatable")
    ap.add_argument("--skill", action="append", default=[], help="an installed skill the agent should use; repeatable")
    ap.add_argument("--tool", action="append", default=[], help="a concrete surface the agent will touch (CLI, API, DB, endpoint); repeatable")
    ap.add_argument("--context", action="append", default=[], help="a file, directory, or note the agent must read; repeatable")
    ap.add_argument("--deny", action="append", default=[], help="a path or area the agent must not touch; repeatable")
    ap.add_argument("--risk", action="append", default=[], help="premortem row as 'failure|blast radius|likelihood|guard'; repeatable")
    ap.add_argument("--verification", help="how the bar is proven in-product")
    ap.add_argument("--role", help="one-line role for the dispatch block")
    ap.add_argument("--owned-file", action="append", default=[], help="a file the agent owns exclusively (the file-lock contract); repeatable")
    ap.add_argument("--report", help="what to report back and when (default: on green, or on the first blocker)")
    ap.add_argument("--write", help="also save the brief to this path (directories are created)")
    ap.add_argument("--json", action="store_true", help="emit the two artifacts as JSON")
    args = ap.parse_args()

    if not args.goal.strip() or not args.acceptance.strip():
        ap.error("--goal and --acceptance must not be empty")

    today = datetime.date.today().isoformat()
    charter = render_charter(args, today)
    dispatch = render_dispatch(args)
    text = charter + "\n\n---\n\n" + dispatch + "\n"

    if args.json:
        print(json.dumps({"date": today, "spec_charter": charter, "dispatch": dispatch}, indent=2, ensure_ascii=False))
    else:
        print(text, end="")

    if args.write:
        path = os.path.expanduser(args.write)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"# wrote {path}", file=sys.stderr)
    if not args.risk:
        print("# no --risk given: run premortem before dispatching", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
