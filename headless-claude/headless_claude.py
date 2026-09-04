#!/usr/bin/env python3
"""headless-claude — run `claude -p` fast, hooks skipped, and unattended.

A thin, honest wrapper around the local `claude` CLI for AUTOMATION: it runs in
print mode with three flags that make headless runs behave —

  --setting-sources project   don't load your USER settings/hooks (no Stop-hook
                              side effects, no editor/notify hooks firing, and it
                              skips heavy auto-memory so a quick turn is ~2s not ~15s)
  --permission-mode bypassPermissions   edit/run without an interactive approval
                              prompt that would block an unattended process
  (run in a neutral cwd)      so it doesn't drag in a project's CLAUDE.md/tree

That combination is the difference between `claude -p` hanging on a permission
prompt (or firing your desktop hooks) and a clean, fast, scriptable call. Uses
your own plan via the logged-in CLI — no API key (BYOK).

Default prints the exact command (dry); --apply runs it.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="Fast, hooks skipped, unattended `claude -p`.")
    ap.add_argument("prompt", nargs="*", help="the prompt (quote it)")
    ap.add_argument("--apply", action="store_true", help="actually run (default: print the command)")
    ap.add_argument("--model", default="claude-haiku-4-5", help="model (default haiku for speed)")
    ap.add_argument("--cwd", default="", help="working dir (default: a neutral temp dir)")
    ap.add_argument("--allow-hooks", action="store_true", help="DON'T pass --setting-sources project (load user hooks)")
    ap.add_argument("--safe", action="store_true", help="DON'T bypass permissions (let it prompt)")
    ap.add_argument("--timeout", type=int, default=180, help="seconds (default 180)")
    args = ap.parse_args()

    if not shutil.which("claude"):
        sys.stderr.write("FATAL: the `claude` CLI is not on PATH. Install Claude Code and log in.\n")
        return 2

    prompt = " ".join(args.prompt).strip()
    cmd = ["claude", "-p", prompt or "<prompt>", "--model", args.model]
    if not args.allow_hooks:
        cmd += ["--setting-sources", "project"]
    if not args.safe:
        cmd += ["--permission-mode", "bypassPermissions"]

    cwd = os.path.expanduser(args.cwd) if args.cwd else None
    if not args.apply:
        print("headless-claude would run:")
        print("  (cwd: %s)" % (cwd or "<neutral temp dir>"))
        print("  " + " ".join(repr(c) if " " in c else c for c in cmd))
        print("\nRun with --apply to execute.")
        return 0

    if not prompt:
        sys.stderr.write("FATAL: no prompt given.\n")
        return 2
    if cwd is None:
        import tempfile
        cwd = tempfile.mkdtemp(prefix="headless_claude_")
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"FATAL: timed out after {args.timeout}s.\n")
        return 2
    if out.returncode != 0:
        sys.stderr.write(f"FATAL: claude exited {out.returncode}: {(out.stderr or '')[:300]}\n")
        return 2
    sys.stdout.write(out.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
