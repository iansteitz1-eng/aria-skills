#!/usr/bin/env python3
"""screen-describe — ask your local Claude what's on your screen.

Captures the screen (macOS `screencapture`), hands the image to your local
`claude` CLI (your own Pro/Max — no API key, BYOK), and prints a short
description. The screenshot is deleted immediately after. Read-only: it never
controls anything, just looks.

Default is a dry pre-flight (checks deps, prints the plan, captures nothing) so
it's safe to run blind and clean for CI. `--apply` does the real capture+describe.
Needs macOS Screen Recording permission for whatever process runs it.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

DEFAULT_Q = "Describe what is currently on the screen in 2-3 short sentences — apps, windows, and what the user appears to be doing. Only what you can actually see."


def _preflight() -> list[str]:
    missing = []
    if sys.platform != "darwin" or not shutil.which("screencapture"):
        missing.append("macOS `screencapture` (this skill is macOS-only)")
    if not shutil.which("claude"):
        missing.append("the `claude` CLI (install Claude Code; logged in to your plan)")
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description="Ask your local Claude what's on your screen.")
    ap.add_argument("--apply", action="store_true", help="actually capture + describe (default: dry pre-flight)")
    ap.add_argument("--question", default=DEFAULT_Q, help="what to ask about the screen")
    ap.add_argument("--model", default="claude-haiku-4-5", help="claude model (default haiku)")
    args = ap.parse_args()

    missing = _preflight()
    if missing:
        sys.stderr.write("FATAL: missing prerequisites:\n  - " + "\n  - ".join(missing) + "\n")
        return 2
    if not args.apply:
        print("screen-describe: pre-flight OK (screencapture + claude found).")
        print("Run with --apply to capture your screen and describe it. Screenshot is deleted after.")
        return 0

    shot = os.path.join(tempfile.gettempdir(), "screen_describe_shot.png")
    try:
        r = subprocess.run(["screencapture", "-x", "-t", "png", shot], timeout=15,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0 or not os.path.exists(shot) or os.path.getsize(shot) < 2048:
            sys.stderr.write("FATAL: screen capture failed — grant Screen Recording in "
                             "System Settings > Privacy & Security to the app running this.\n")
            return 2
        prompt = (f"Read the screenshot image at {shot}. {args.question}")
        out = subprocess.run(
            ["claude", "-p", prompt, "--setting-sources", "project",
             "--permission-mode", "bypassPermissions", "--model", args.model],
            capture_output=True, text=True, timeout=120,
        )
        desc = (out.stdout or "").strip()
        if not desc:
            sys.stderr.write("FATAL: claude returned nothing (check `claude` is logged in).\n")
            return 2
        print(desc)
        return 0
    finally:
        try:
            os.remove(shot)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
