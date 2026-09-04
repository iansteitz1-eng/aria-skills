#!/usr/bin/env python3
"""surgical_patch.py — drift-safe editor for a hot, shared, possibly-remote file.

The problem this solves (2026-06-03, the main.py provenance deploy): the live
prod file is AHEAD of the local checkout (other lanes' uncommitted edits), so you
must NOT rsync your local copy over it — you'd wipe their work. Instead you fetch
the live file, build a MINIMAL delta, and apply it surgically with guards.

This tool applies a data-driven list of exact-match edits to a target file
(local or over ssh) with three safety properties:

  1. IDEMPOTENT — if the file already contains `sentinel`, it exits 0 having done
     nothing (safe to re-run after a partial deploy).
  2. EXACT — every `old` block must match EXACTLY once (configurable via `count`);
     any mismatch aborts with NO changes written.
  3. REVERSIBLE — the original is copied to a timestamped backup before writing.

Edits are JSON:  --edits edits.json  where the file is
  {
    "sentinel": "runner_provenance",          # if already present → no-op (optional)
    "verify": "python3 -m py_compile {path}",  # run after write; nonzero → rollback (optional)
    "edits": [
      {"old": "...exact text...", "new": "...replacement...", "count": 1},
      ...
    ]
  }

Local:   surgical_patch.py --edits edits.json --path /srv/myapp/main.py
Remote:  surgical_patch.py --edits edits.json --path /srv/myapp/main.py --host <your-server>

Exit: 0 = applied (or no-op), 2 = an anchor failed its count assertion (no change),
      3 = verify failed (rolled back), 1 = error. Pairs with /safe-restart + /aria-deploy.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def sh(cmd: list[str], inp: str | None = None, timeout: int = 60):
    return subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=timeout)


def read_target(host: str | None, path: str) -> str:
    if host:
        r = sh(["ssh", host, f"cat {shq(path)}"])
        if r.returncode != 0:
            raise RuntimeError(f"ssh cat failed: {r.stderr.strip()}")
        return r.stdout
    with open(path) as f:
        return f.read()


def write_target(host: str | None, path: str, content: str):
    if host:
        # stream via stdin to avoid arg-length + quoting issues
        r = sh(["ssh", host, f"cat > {shq(path)}"], inp=content)
        if r.returncode != 0:
            raise RuntimeError(f"ssh write failed: {r.stderr.strip()}")
    else:
        with open(path, "w") as f:
            f.write(content)


def backup(host: str | None, path: str, ts: str) -> str:
    """Copy path → <dir>/.deploy_bak/<ts>/<basename>. Returns backup path."""
    d = os.path.dirname(path) or "."
    base = os.path.basename(path)
    bak_dir = f"{d}/.deploy_bak/{ts}"
    bak = f"{bak_dir}/{base}"
    if host:
        r = sh(["ssh", host, f"mkdir -p {shq(bak_dir)} && cp {shq(path)} {shq(bak)}"])
        if r.returncode != 0:
            raise RuntimeError(f"ssh backup failed: {r.stderr.strip()}")
    else:
        os.makedirs(bak_dir, exist_ok=True)
        with open(path) as f, open(bak, "w") as g:
            g.write(f.read())
    return bak


def shq(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


ENV_FILE = os.environ.get("SURGICAL_PATCH_ENV_FILE", "/opt/aria/.env")


def run_verify(host: str | None, verify_cmd: str, path: str, env_file: str | None = None) -> tuple[bool, str]:
    cmd = verify_cmd.replace("{path}", path)
    env_file = ENV_FILE if env_file is None else env_file
    if host:
        # load the service env so imports resolve like the running app
        source_env = f". {shq(env_file)} 2>/dev/null; " if env_file else ""
        full = f"cd {shq(os.path.dirname(path) or '.')} && set -a && {source_env}set +a; {cmd}"
        r = sh(["ssh", host, full], timeout=120)
    else:
        r = sh(["bash", "-lc", cmd], timeout=120)
    ok = r.returncode == 0
    return ok, (r.stdout + r.stderr).strip()[-1500:]


def main():
    global ENV_FILE
    ap = argparse.ArgumentParser(description="Drift-safe surgical file patcher (local or ssh).")
    ap.add_argument("--edits", required=True, help="JSON file: {sentinel?, verify?, edits:[{old,new,count?}]}")
    ap.add_argument("--path", required=True, help="absolute path to the target file (on --host if remote)")
    ap.add_argument("--host", default=None, help="ssh host (omit for a local file)")
    ap.add_argument("--ts", default=None, help="backup timestamp dir name (default: ask the remote/local clock)")
    ap.add_argument("--dry-run", action="store_true", help="assert + preview only; write nothing")
    ap.add_argument("--env-file", default=ENV_FILE, help="env file sourced on --host before verify (default: $SURGICAL_PATCH_ENV_FILE, else the built-in fallback named in README.md; pass '' to skip)")
    args = ap.parse_args()
    ENV_FILE = args.env_file

    with open(args.edits) as f:
        spec = json.load(f)
    edits = spec.get("edits", [])
    if not edits:
        print("ERROR: no edits in spec.")
        return 1

    try:
        src = read_target(args.host, args.path)
    except Exception as e:
        print(f"ERROR reading target: {e}")
        return 1

    # 1) idempotency
    sentinel = spec.get("sentinel")
    if sentinel and sentinel in src:
        print(f"NO-OP: sentinel {sentinel!r} already present in {args.path} — already patched.")
        return 0

    # 2) exact-match assertions (all-or-nothing)
    for i, e in enumerate(edits):
        old = e["old"]
        want = e.get("count", 1)
        got = src.count(old)
        if got != want:
            preview = old.strip().splitlines()[0][:70] if old.strip() else "(empty)"
            print(f"ABORT: edit #{i} anchor matched {got}x (expected {want}). No changes written.")
            print(f"       anchor starts: {preview!r}")
            return 2
    print(f"OK: all {len(edits)} anchors matched exactly. Target: {args.host or 'local'}:{args.path}")

    if args.dry_run:
        print("DRY-RUN: assertions pass; nothing written.")
        return 0

    # 3) backup
    ts = args.ts
    if not ts:
        if args.host:
            ts = sh(["ssh", args.host, "date +%Y%m%d_%H%M%S"]).stdout.strip()
        else:
            ts = sh(["date", "+%Y%m%d_%H%M%S"]).stdout.strip()
    try:
        bak = backup(args.host, args.path, ts)
        print(f"backup: {bak}")
    except Exception as e:
        print(f"ERROR backing up: {e}")
        return 1

    # apply
    out = src
    for e in edits:
        out = out.replace(e["old"], e["new"])
    try:
        write_target(args.host, args.path, out)
    except Exception as e:
        print(f"ERROR writing target: {e}")
        return 1
    print(f"PATCHED: {len(edits)} edit(s) applied to {args.path}")

    # 4) verify (rollback on failure)
    verify_cmd = spec.get("verify")
    if verify_cmd:
        ok, log = run_verify(args.host, verify_cmd, args.path)
        if ok:
            print(f"verify OK: {verify_cmd}")
        else:
            print(f"verify FAILED — rolling back from {bak}")
            try:
                if args.host:
                    sh(["ssh", args.host, f"cp {shq(bak)} {shq(args.path)}"])
                else:
                    with open(bak) as f, open(args.path, "w") as g:
                        g.write(f.read())
                print("rolled back OK.")
            except Exception as e:
                print(f"!! ROLLBACK FAILED: {e} — restore manually from {bak}")
            print("--- verify output (tail) ---")
            print(log)
            return 3

    print("DONE. Next: /safe-restart to check the fleet, then /aria-deploy to restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
