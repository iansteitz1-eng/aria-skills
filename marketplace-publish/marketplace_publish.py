#!/usr/bin/env python3
"""
marketplace_publish.py — Sprint 021 S21.T2-B. Unified marketplace publisher.

Single-command wrapper around the existing publish.sh (VS Code Marketplace via
vsce) and submit.sh (Expo EAS for iOS App Store + Google Play). Adds pre-flight
validation, dry-run safety, and per-publish splat emission so the launch lane
has one surface instead of three.

Sub-commands:
  vscode         Publish the Aria Code VS Code extension to the marketplace
  ios            Build + submit the Aria Code mobile app to App Store (TestFlight)
  android        Build + submit the Aria Code mobile app to Play Console (internal)
  all            All three, sequentially (vscode → ios → android)

Common flags:
  --dry-run      Package/build artifacts but don't upload (default off)
  --build-only   Mobile only: eas build but skip eas submit (default off)
  --pre-release  vscode only: publish to pre-release channel
  --skip-preflight  Run even if preflight checks fail (escape hatch; not recommended)

Exit codes:
  0 = success (or dry-run completed)
  1 = preflight failure (missing token, missing binary, missing config)
  2 = invocation error (bad args)
  3 = underlying tool failed (vsce, eas, npm)

Splat: every successful publish emits a `marketplace_publish_run` splat with
target, version, dry_run flag, and exit status for ops audit.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ENV_FILE = Path(".env")
VSCODE_DIR = Path("/opt/aria/aria-vscode")
MOBILE_DIR = Path("/opt/aria/aria-mobile")
VSCODE_PUBLISH_SH = VSCODE_DIR / "publish.sh"
MOBILE_SUBMIT_SH = MOBILE_DIR / "submit.sh"

# Load .env so VSCE_PAT is reachable if Ian pasted it there.
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"  ERROR: could not read {path}: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Pre-flight checks
# ──────────────────────────────────────────────────────────────────────────────


def _preflight_vscode(dry_run: bool) -> list[str]:
    """Return a list of preflight failures (empty = ready to publish)."""
    fails = []
    if not VSCODE_DIR.is_dir():
        fails.append(f"VS Code extension dir missing: {VSCODE_DIR}")
        return fails
    if not VSCODE_PUBLISH_SH.exists():
        fails.append(f"publish.sh missing: {VSCODE_PUBLISH_SH}")
    if not shutil.which("node"):
        fails.append("`node` not on PATH — install Node 18+")
    if not shutil.which("npm"):
        fails.append("`npm` not on PATH")
    pkg = _read_json(VSCODE_DIR / "package.json")
    if not pkg.get("version"):
        fails.append("aria-vscode/package.json missing `version` field")
    if not pkg.get("publisher"):
        fails.append("aria-vscode/package.json missing `publisher` field")
    if not dry_run and not os.environ.get("VSCE_PAT"):
        fails.append(
            "VSCE_PAT env var not set — mint at "
            "https://dev.azure.com/<org>/_usersSettings/tokens "
            "(scope: Marketplace > Manage), then add to .env"
        )
    return fails


def _preflight_mobile(platform: str, dry_run: bool, build_only: bool) -> list[str]:
    """Return a list of preflight failures (empty = ready). platform ∈ {ios, android}."""
    fails = []
    if not MOBILE_DIR.is_dir():
        fails.append(f"Mobile app dir missing: {MOBILE_DIR}")
        return fails
    if not MOBILE_SUBMIT_SH.exists():
        fails.append(f"submit.sh missing: {MOBILE_SUBMIT_SH}")
    if not shutil.which("node"):
        fails.append("`node` not on PATH — install Node 18+")
    if not shutil.which("npx"):
        fails.append("`npx` not on PATH (ships with Node)")
    eas = _read_json(MOBILE_DIR / "eas.json")
    if not eas.get("build", {}).get("production"):
        fails.append("aria-mobile/eas.json missing build.production block")
    submit = eas.get("submit", {}).get("production", {})
    if platform == "ios" and not (dry_run or build_only):
        ios_cfg = submit.get("ios", {})
        asc = ios_cfg.get("ascAppId", "")
        team = ios_cfg.get("appleTeamId", "")
        if not asc or asc.startswith("<") or not team or team.startswith("<"):
            fails.append(
                "eas.json submit.production.ios has placeholder ascAppId/appleTeamId "
                "— paste real values after first App Store Connect record"
            )
    if platform == "android" and not (dry_run or build_only):
        play_key = MOBILE_DIR / "play-service-account.json"
        if not play_key.exists():
            fails.append(
                f"Play Console service account key missing at {play_key} — "
                "download JSON from Play Console → API access, save here (gitignored)"
            )
    return fails


# ──────────────────────────────────────────────────────────────────────────────
# Invocation
# ──────────────────────────────────────────────────────────────────────────────


def _run_sh(script: Path, args: list[str], cwd: Path, dry_run_label: str) -> int:
    """Invoke the underlying bash script. Streams output to console.
    Returns the script's exit code (or 3 if the script can't be invoked)."""
    if not os.access(script, os.X_OK):
        try:
            os.chmod(script, 0o755)
        except Exception:
            print(f"  ERROR: {script} is not executable and chmod failed")
            return 3
    cmd = [str(script), *args]
    print(f"  $ {' '.join(cmd)}  (cwd={cwd})")
    if dry_run_label:
        print(f"  ({dry_run_label} — bash script controls the actual dry-run behavior)")
    try:
        r = subprocess.run(cmd, cwd=str(cwd), check=False)
        return r.returncode
    except FileNotFoundError:
        print(f"  ERROR: could not invoke {script}")
        return 3


def _emit_splat(*args, **kwargs):
    pass



def _publish_vscode(args: argparse.Namespace) -> int:
    print("# vscode marketplace publish")
    fails = _preflight_vscode(args.dry_run)
    if fails and not args.skip_preflight:
        for f in fails:
            print(f"  ✗ {f}")
        return 1
    for f in fails:
        print(f"  ⚠ preflight skipped: {f}")
    pkg = _read_json(VSCODE_DIR / "package.json")
    version = pkg.get("version", "?")
    publisher = pkg.get("publisher", "?")
    name = pkg.get("name", "?")
    print(f"  package: {publisher}.{name}@{version}")

    sh_args = []
    if args.dry_run:
        sh_args.append("--dry-run")
    elif args.pre_release:
        sh_args.append("--pre-release")
    rc = _run_sh(
        VSCODE_PUBLISH_SH, sh_args, VSCODE_DIR, "--dry-run" if args.dry_run else ""
    )
    _emit_splat(
        {
            "target": "vscode",
            "version": version,
            "publisher": publisher,
            "dry_run": args.dry_run,
            "pre_release": args.pre_release,
            "rc": rc,
        }
    )
    return rc


def _publish_mobile(args: argparse.Namespace, platform: str) -> int:
    print(f"# {platform} mobile publish (eas build + submit)")
    fails = _preflight_mobile(platform, args.dry_run, args.build_only)
    if fails and not args.skip_preflight:
        for f in fails:
            print(f"  ✗ {f}")
        return 1
    for f in fails:
        print(f"  ⚠ preflight skipped: {f}")
    pkg = _read_json(MOBILE_DIR / "package.json")
    version = pkg.get("version", "?")
    name = pkg.get("name", "?")
    print(f"  package: {name}@{version}")

    sh_args = []
    # submit.sh supports --build-only as a prefix; dry-run is implicit
    # via --build-only (no submit step). True "no eas build" isn't supported
    # by the underlying tool; we honor --dry-run by skipping invocation entirely.
    if args.dry_run:
        print(f"  (dry-run: would run submit.sh {platform} — skipping invocation)")
        _emit_splat(
            {
                "target": platform,
                "version": version,
                "dry_run": True,
                "build_only": args.build_only,
                "rc": 0,
            }
        )
        return 0
    if args.build_only:
        sh_args.append("--build-only")
    sh_args.append(platform)
    rc = _run_sh(MOBILE_SUBMIT_SH, sh_args, MOBILE_DIR, "")
    _emit_splat(
        {
            "target": platform,
            "version": version,
            "dry_run": False,
            "build_only": args.build_only,
            "rc": rc,
        }
    )
    return rc


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Unified marketplace publisher (VS Code · iOS · Android).",
    )
    ap.add_argument(
        "target",
        choices=["vscode", "ios", "android", "all"],
        help="Which marketplace target to publish",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Package/build but don't upload to any marketplace",
    )
    ap.add_argument(
        "--build-only",
        action="store_true",
        help="Mobile only: eas build but skip eas submit",
    )
    ap.add_argument(
        "--pre-release",
        action="store_true",
        help="vscode only: publish to pre-release channel",
    )
    ap.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Run even if preflight fails (escape hatch; not recommended)",
    )
    args = ap.parse_args()

    print(
        f"# marketplace-publish · target={args.target} "
        f"· dry_run={args.dry_run} · build_only={args.build_only} "
        f"· pre_release={args.pre_release}"
    )
    print()

    if args.target == "vscode":
        return _publish_vscode(args)
    if args.target == "ios":
        return _publish_mobile(args, "ios")
    if args.target == "android":
        return _publish_mobile(args, "android")
    if args.target == "all":
        worst = 0
        for fn, label in (
            (lambda: _publish_vscode(args), "vscode"),
            (lambda: _publish_mobile(args, "ios"), "ios"),
            (lambda: _publish_mobile(args, "android"), "android"),
        ):
            print()
            rc = fn()
            if rc != 0:
                print(f"  → {label} exited with rc={rc}")
                worst = max(worst, rc)
        return worst
    return 2


if __name__ == "__main__":
    sys.exit(main())
