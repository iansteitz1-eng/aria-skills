#!/usr/bin/env python3
"""
aria_status.py — Config-driven one-screen status of a server stack.

Reads a YAML config declaring what to probe (systemd timers, healthz URLs,
disk mounts, GPU presence, optional shell commands), runs every probe in
parallel with short timeouts, prints a compact text report. --json for
machine output, --brief for one-screen summary.

YAML-canonical, dry-run-free (read-only by design), zero vendor SDKs.
"""
import argparse
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_S = 4
DEFAULT_CONFIG = Path(__file__).parent / "aria_status_config.yaml"


def _http_get(url: str, timeout: int = TIMEOUT_S) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aria-status/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "status": r.status}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code}
    except Exception as e:
        return {"ok": False, "status": None, "err": f"{type(e).__name__}: {e}"[:120]}


def _run(cmd: list[str], timeout: int = TIMEOUT_S) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "stdout": r.stdout, "code": r.returncode}
    except Exception as e:
        return {"ok": False, "stdout": "", "code": -1, "err": str(e)[:120]}


def check_timers(unit_patterns: list[str]) -> dict:
    """List systemd timers matching any of the regex patterns."""
    r = _run(["systemctl", "list-timers", "--all", "--no-pager"], timeout=6)
    if not r["ok"]:
        return {"ok": False, "summary": "systemctl unreachable"}
    pat = re.compile("|".join(unit_patterns)) if unit_patterns else re.compile(".*")
    matching = [line.strip() for line in r["stdout"].splitlines() if pat.search(line)]
    return {"ok": True, "total": len(matching), "rows": matching[:50]}


def check_health(targets: dict[str, str]) -> dict:
    """Parallel-probe HTTP healthz endpoints."""
    out = {}
    if not targets:
        return out
    with cf.ThreadPoolExecutor(max_workers=max(1, len(targets))) as ex:
        futs = {ex.submit(_http_get, url, 3): label for label, url in targets.items()}
        for f in cf.as_completed(futs):
            r = f.result()
            out[futs[f]] = {"ok": r["ok"], "status": r["status"]}
    return out


def check_disk(mounts: list[str]) -> dict:
    """Disk usage for given mount paths (default: /)."""
    out = {}
    for m in mounts or ["/"]:
        try:
            u = shutil.disk_usage(m)
            pct = round(u.used / u.total * 100, 1)
            out[m] = {"pct": pct, "avail_gb": round(u.free / 1e9, 1)}
        except Exception as e:
            out[m] = {"err": str(e)[:80]}
    return out


def check_gpu() -> dict:
    """nvidia-smi summary if present; silent skip otherwise."""
    if not shutil.which("nvidia-smi"):
        return {"present": False}
    r = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.used,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        timeout=4,
    )
    if not r["ok"]:
        return {"present": True, "ok": False}
    cards = []
    for line in r["stdout"].strip().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) == 4:
            cards.append(
                {
                    "name": parts[0],
                    "mem_used_mb": int(parts[1]),
                    "mem_total_mb": int(parts[2]),
                    "util_pct": int(parts[3]),
                }
            )
    return {"present": True, "ok": True, "cards": cards}


def check_commands(commands: list[dict]) -> dict:
    """Run optional user-defined shell commands. Each: {name, cmd, parse_json?}"""
    out = {}
    for c in commands or []:
        name = c.get("name", "?")
        cmd = c.get("cmd")
        if not cmd:
            continue
        r = _run(
            cmd if isinstance(cmd, list) else cmd.split(), timeout=c.get("timeout", 8)
        )
        if c.get("parse_json") and r["ok"]:
            try:
                out[name] = {"ok": True, "data": json.loads(r["stdout"])}
                continue
            except Exception:
                pass
        out[name] = {"ok": r["ok"], "stdout": r["stdout"][:400]}
    return out


def _load_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        sys.stderr.write("FATAL: PyYAML not installed. pip install PyYAML\n")
        sys.exit(1)
    if not path.exists():
        sys.stderr.write(f"FATAL: config not found at {path}\n")
        sys.exit(2)
    with open(path) as f:
        return yaml.safe_load(f) or {}


def collect(cfg: dict) -> dict:
    return {
        "timers": check_timers(cfg.get("timer_patterns") or []),
        "health": check_health(cfg.get("healthz") or {}),
        "disk": check_disk(cfg.get("disk_mounts") or []),
        "gpu": check_gpu(),
        "extras": check_commands(cfg.get("commands") or []),
    }


def render_text(r: dict, brief: bool = False) -> str:
    lines = []
    add = lines.append
    h = r.get("health") or {}
    if h:
        ok = sum(1 for v in h.values() if v.get("ok"))
        add(f"HEALTH: {ok}/{len(h)} endpoints green")
        if not brief:
            for label, v in sorted(h.items()):
                mark = "✓" if v["ok"] else "✗"
                add(f"  {mark} {label}  status={v.get('status')}")
    t = r.get("timers") or {}
    add(f"TIMERS: {t.get('total', 0)} matching units present")
    d = r.get("disk") or {}
    for m, v in d.items():
        if "err" in v:
            add(f"DISK {m}: {v['err']}")
        else:
            add(f"DISK {m}: {v['pct']}% used · {v['avail_gb']} GB free")
    g = r.get("gpu") or {}
    if g.get("present") and g.get("ok"):
        for c in g.get("cards", []):
            pct_mem = round(c["mem_used_mb"] / c["mem_total_mb"] * 100, 1)
            add(f"GPU {c['name']}: {pct_mem}% mem · {c['util_pct']}% util")
    e = r.get("extras") or {}
    for name, v in e.items():
        mark = "✓" if v.get("ok") else "✗"
        snippet = (v.get("stdout") or "").strip().splitlines()[:1]
        add(f"{mark} {name}: {snippet[0] if snippet else ''}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Config-driven server status.")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON")
    ap.add_argument("--brief", action="store_true", help="One-screen summary")
    args = ap.parse_args()

    cfg = _load_config(Path(args.config))
    result = collect(cfg)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(render_text(result, brief=args.brief))
    return 0


if __name__ == "__main__":
    sys.exit(main())
