#!/usr/bin/env python3
"""live-code-watch — watch a repo's working diff get written, live.

Renders `git diff` for a repo and (with --watch) redraws ONLY when it changes —
no idle flicker, new files included (intent-to-add). Point it at a repo while an
AI agent (or you) edits, and watch the raw code appear line by line.

Zero dependencies beyond git + Python stdlib. Read-only: it never writes to your
repo except a transient `git add -N` (intent-to-add) so brand-new files show
their contents in the diff; that leaves no commit and is trivially undone.

Default (no flag) renders ONCE and exits 0 — handy as a quick "show me the diff"
and clean for CI. `--watch` is the live loop.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time


def _git(repo: str, *args: str, timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return p.returncode, p.stdout
    except FileNotFoundError:
        sys.stderr.write("FATAL: git not found on PATH.\n")
        sys.exit(2)
    except Exception:
        return 1, ""


def _is_git_repo(repo: str) -> bool:
    rc, out = _git(repo, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and "true" in out


def _snapshot(repo: str, color: bool, max_lines: int) -> str:
    # intent-to-add so brand-new files show their content; never commits.
    _git(repo, "add", "-A", "-N")
    diff_args = ["--no-pager", "diff", "HEAD"]
    if color:
        diff_args.append("--color=always")
    _, diff = _git(repo, *diff_args)
    _, status = _git(repo, "--no-pager", "status", "-s")
    body = "\n".join(diff.splitlines()[:max_lines])
    return f"{body}\n\n--- changed files ---\n{status}".rstrip() + "\n"


def _render(repo: str, body: str, home: bool) -> None:
    if home and sys.stdout.isatty():
        sys.stdout.write("\033[H\033[J")  # cursor home + clear (flicker-free)
    label = os.path.basename(os.path.abspath(repo)) or repo
    sys.stdout.write(f"=== live-code-watch · {label} ===\n\n{body}")
    sys.stdout.flush()


def main() -> int:
    ap = argparse.ArgumentParser(description="Watch a repo's working diff, live.")
    ap.add_argument("--repo", default=".", help="path to the git repo (default: .)")
    ap.add_argument("--watch", action="store_true", help="live loop (redraw on change)")
    ap.add_argument("--interval", type=float, default=1.0, help="poll seconds (default 1.0)")
    ap.add_argument("--max-iterations", type=int, default=0, help="stop after N redraws (0=forever)")
    ap.add_argument("--max-lines", type=int, default=600, help="diff lines to show (default 600)")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI color")
    args = ap.parse_args()

    repo = os.path.expanduser(args.repo)
    if not os.path.isdir(repo):
        sys.stderr.write(f"FATAL: not a directory: {repo}\n")
        return 2
    if not _is_git_repo(repo):
        print(f"live-code-watch: {repo} is not a git repository — nothing to diff.")
        return 0

    color = not args.no_color
    if not args.watch:
        _render(repo, _snapshot(repo, color, args.max_lines), home=False)
        return 0

    prev, n = None, 0
    try:
        while True:
            cur = _snapshot(repo, color, args.max_lines)
            if cur != prev:
                _render(repo, cur, home=True)
                prev = cur
                n += 1
                if args.max_iterations and n >= args.max_iterations:
                    return 0
            time.sleep(max(0.2, args.interval))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
