#!/usr/bin/env python3
"""
premortem.py — write the premortem artifact (a predicted-vs-actual ledger) instead of only talking about risk.

Renders one ledger block for one decision. Dry-run by default (prints the block);
--apply appends it to the ledger file so the artifact exists before the change does.

Usage:
  premortem.py "Deploy the new gateway build" --phase deployment
  premortem.py "Add column X" --failure "migration locks the table" --failure "old rows carry NULLs"
  premortem.py "Refactor the poll loop" --rows 5 --apply --out notes/premortem.md
  premortem.py "Rotate the API key" --json

Exit codes:
  0 = block printed / appended
  2 = invocation error
"""
import argparse
import datetime
import json
import os
import sys

PHASES = [
    "intent", "requirements", "architecture", "implementation",
    "testing", "debugging", "deployment", "iteration",
]
HEADER = (
    "| # | failure | blast radius | likelihood | guard | predicted | actual |\n"
    "|---|---------|--------------|------------|-------|-----------|--------|"
)


def render(decision: str, phase: str, failures: list[str], rows: int, date: str) -> str:
    entries = failures if failures else [""] * max(rows, 1)
    lines = [f"## {date} — {decision}  [phase: {phase}]", "", HEADER]
    for i, failure in enumerate(entries, 1):
        lines.append(f"| {i} | {failure} |  |  |  |  |  |")
    lines += ["", "_Fill blast radius, likelihood, guard, and predicted now. Come back for actual after the change ships._", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Premortem ledger writer: failure modes -> cheapest guard -> predicted vs actual.")
    ap.add_argument("decision", help="one line: the decision being made (e.g. 'Deploy X to the live gateway')")
    ap.add_argument("--phase", default="implementation", choices=PHASES, help="lifecycle phase the decision sits in (default: implementation)")
    ap.add_argument("--failure", action="append", default=[], help="a predicted failure mode; repeatable, one ledger row each")
    ap.add_argument("--rows", type=int, default=4, help="empty rows to leave when no --failure is given (default: 4)")
    ap.add_argument("--out", default="notes/premortem.md", help="ledger file appended to with --apply (default: notes/premortem.md)")
    ap.add_argument("--apply", action="store_true", help="append the block to --out (default: print only)")
    ap.add_argument("--json", action="store_true", help="emit the block as JSON instead of markdown")
    args = ap.parse_args()

    decision = args.decision.strip()
    if not decision:
        ap.error("decision must not be empty")
    if args.rows < 1:
        ap.error("--rows must be at least 1")

    date = datetime.date.today().isoformat()
    block = render(decision, args.phase, [f.strip() for f in args.failure if f.strip()], args.rows, date)

    if args.json:
        print(json.dumps({"date": date, "decision": decision, "phase": args.phase,
                          "failures": args.failure, "markdown": block}, indent=2, ensure_ascii=False))
        return 0

    if not args.apply:
        print(block)
        print(f"# dry-run: add --apply to append this block to {args.out}", file=sys.stderr)
        return 0

    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    needs_gap = os.path.exists(out) and os.path.getsize(out) > 0
    with open(out, "a", encoding="utf-8") as fh:
        fh.write(("\n" if needs_gap else "") + block)
    print(f"appended premortem for {decision!r} to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
