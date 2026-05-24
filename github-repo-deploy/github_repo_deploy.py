#!/usr/bin/env python3
"""
github_repo_deploy.py — Reconcile a YAML catalog of repo metadata to GitHub.

Idempotent. Reads desired state from YAML, fetches current state via GitHub
REST, diffs, prints summary, applies only with --apply. --prod required for
the actual PATCH call (mirrors the two-flag-prod pattern from BUILDER_GUIDE).

Touches per repo:
  - description     (string)
  - homepage        (URL string)
  - topics          (list of tags — replaced wholesale)
  - private         (bool — read-only by default; refuses to flip without --allow-visibility)
  - default_branch  (read-only; warns on drift but never auto-flips)

Auth: uses `gh` CLI if available (relies on its token cache), else falls
back to GITHUB_TOKEN env var.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).parent / "github_repos.yaml"


def _get_token() -> str | None:
    """Prefer gh CLI token cache, fall back to env."""
    try:
        r = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _require_token() -> str:
    tok = _get_token()
    if not tok:
        sys.stderr.write(
            "FATAL: no GitHub token. Run `gh auth login` or set GITHUB_TOKEN.\n"
        )
        sys.exit(2)
    return tok


def _api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-repo-deploy/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="ignore")[:300]
        raise RuntimeError(f"GitHub API {method} {path}: HTTP {e.code} — {msg}")


def _load_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        sys.stderr.write("FATAL: PyYAML not installed. pip install PyYAML\n")
        sys.exit(2)
    if not path.exists():
        sys.stderr.write(f"FATAL: config not found at {path}\n")
        sys.exit(2)
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _topics_diff(current: list[str], desired: list[str]) -> tuple[list[str], list[str]]:
    cur_set, des_set = set(current or []), set(desired or [])
    return sorted(des_set - cur_set), sorted(cur_set - des_set)


def _reconcile_repo(
    owner: str, repo_cfg: dict, token: str, apply: bool, prod: bool
) -> dict:
    repo_name = repo_cfg["name"]
    path = f"/repos/{owner}/{repo_name}"
    try:
        current = _api("GET", path, token)
    except RuntimeError as e:
        return {"name": repo_name, "ok": False, "error": str(e)}

    diffs = []
    patch_body = {}
    for field in ("description", "homepage"):
        desired_val = repo_cfg.get(field)
        current_val = current.get(field) or ""
        if desired_val is not None and (current_val or "") != desired_val:
            diffs.append(
                f"{field}: {repr(current_val)[:50]} → {repr(desired_val)[:50]}"
            )
            patch_body[field] = desired_val

    # default_branch — warn-only, never auto-flip
    desired_branch = repo_cfg.get("default_branch")
    if desired_branch and current.get("default_branch") != desired_branch:
        diffs.append(
            f"default_branch DRIFT (READ-ONLY): {current.get('default_branch')} ≠ {desired_branch}"
        )

    # visibility — refuse unless explicit
    desired_private = repo_cfg.get("private")
    if desired_private is not None and current.get("private") != desired_private:
        diffs.append(
            f"visibility DRIFT: private={current.get('private')} → {desired_private} "
            "(use --allow-visibility to flip)"
        )

    # topics — separate API endpoint
    desired_topics = repo_cfg.get("topics") or []
    current_topics = current.get("topics") or []
    add, remove = _topics_diff(current_topics, desired_topics)
    topic_patch = None
    if add or remove:
        diffs.append(f"topics: +{add or []} -{remove or []}")
        topic_patch = sorted(set(desired_topics))

    if not diffs:
        return {"name": repo_name, "ok": True, "clean": True}

    if apply and prod:
        if patch_body:
            _api("PATCH", path, token, body=patch_body)
        if topic_patch is not None:
            _api(
                "PUT",
                f"{path}/topics",
                token,
                body={"names": topic_patch},
            )
        return {"name": repo_name, "ok": True, "applied": True, "diffs": diffs}

    return {"name": repo_name, "ok": True, "clean": False, "diffs": diffs}


def _print_summary(results: list[dict], apply: bool, prod: bool) -> None:
    mode = "APPLY" if (apply and prod) else "DRY-RUN"
    print(f"# github-repo-deploy · mode={mode} · repos={len(results)}")
    print()
    for r in results:
        if not r.get("ok"):
            print(f"  ✗ {r['name']}: {r.get('error', 'unknown')}")
            continue
        if r.get("clean"):
            print(f"  ✓ {r['name']}: clean")
            continue
        if r.get("applied"):
            print(f"  ✓ {r['name']}: APPLIED")
        else:
            print(f"  ⚠ {r['name']}: drift")
        for d in r.get("diffs", []):
            print(f"      · {d}")
    print()
    drifted = sum(1 for r in results if r.get("ok") and not r.get("clean"))
    print(f"# Summary: {drifted}/{len(results)} repo(s) have drift")
    if drifted and not (apply and prod):
        print("# Run with --apply --prod to reconcile.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile YAML → GitHub repo metadata.")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--owner", help="GitHub owner/org (override config-level owner)")
    ap.add_argument("--apply", action="store_true", help="Stage changes")
    ap.add_argument(
        "--prod",
        action="store_true",
        help="Actually call the live API (paired with --apply)",
    )
    ap.add_argument("--repo", help="Target a single repo by name; default = all")
    args = ap.parse_args()

    cfg = _load_config(Path(args.config))
    owner = args.owner or cfg.get("owner")
    if not owner:
        sys.stderr.write("FATAL: no owner in config or --owner flag.\n")
        return 2

    repos = cfg.get("repos") or []
    if args.repo:
        repos = [r for r in repos if r.get("name") == args.repo]
        if not repos:
            sys.stderr.write(f"FATAL: repo {args.repo} not in config.\n")
            return 2

    token = _require_token()

    results = []
    for repo_cfg in repos:
        try:
            results.append(
                _reconcile_repo(owner, repo_cfg, token, args.apply, args.prod)
            )
        except Exception as e:
            results.append(
                {"name": repo_cfg.get("name", "?"), "ok": False, "error": str(e)}
            )

    _print_summary(results, args.apply, args.prod)
    return 0


if __name__ == "__main__":
    sys.exit(main())
