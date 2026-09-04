#!/usr/bin/env python3
"""
cloudflare_dns.py — Sprint 021 S21.T2-A. Declarative DNS reconciler.

Reads ./dns_records.yaml and reconciles to Cloudflare. Idempotent.

Matching rules:
  - Zones must already exist on the Cloudflare account (no auto-create — too
    consequential, and zone creation requires NS-records work at the registrar).
  - Records: matched by (zone, type, name). If absent, created. If present
    with drift in content / ttl / proxied, updated in place via PUT.
  - Deletes are NOT automatic (safety). A record removed from YAML stays in
    Cloudflare until --prune is passed.

Companion server bootstrap (--server-setup):
  For records with a `server_setup:` block AND `point_at: this_server`,
  after the DNS apply:
    1. Verify dig +short <domain> returns server_ip (poll up to --wait-dns
       seconds, default 60).
    2. Enable the staged nginx site (ln -s ... sites-enabled).
    3. nginx -t && systemctl reload nginx.
    4. certbot --nginx -d <domain> (with --redirect if requested).
    5. Reload nginx.
  Each step is idempotent — re-running is safe.

CLI:
  python3 cloudflare_dns.py                            # dry-run, no API hits
  python3 cloudflare_dns.py --apply                    # apply DNS changes
  python3 cloudflare_dns.py --apply --server-setup     # also run nginx+certbot bootstrap
  python3 cloudflare_dns.py --apply --prune            # also delete records not in YAML

Exit codes:
  0 = success (or dry-run completed)
  1 = config or API error
  2 = ambiguous / unsafe state — refused to write
  3 = server-setup precondition failed (DNS hasn't propagated, nginx config invalid, etc.)

Splat: every run emits a `cloudflare_dns_run` splat with the reconciled record
list and the dry-run/apply/prune/server-setup flags, for ops audit.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(".env")
DEFAULT_CONFIG = Path("./dns_records.yaml")
CF_API_BASE = "https://api.cloudflare.com/client/v4"

# Load .env so CLOUDFLARE_API_TOKEN is reachable.
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

try:
    import yaml
except ImportError:
    sys.stderr.write("FATAL: PyYAML not installed. pip install PyYAML\n")
    sys.exit(1)


def _load_config(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(f"FATAL: config not found at {path}\n")
        sys.exit(1)
    return yaml.safe_load(path.read_text())


def _cf_request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    """Single Cloudflare API call. Returns parsed JSON. Exits on hard auth errors."""
    url = f"{CF_API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"FATAL: Cloudflare API {method} {path} → {e.code}: {msg}\n")
        if e.code == 401 or e.code == 403:
            sys.exit(2)
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"FATAL: Cloudflare API unreachable: {e}\n")
        sys.exit(1)
    if not payload.get("success"):
        errs = payload.get("errors") or []
        sys.stderr.write(f"FATAL: Cloudflare API returned success=false: {errs}\n")
        sys.exit(1)
    return payload


def _resolve_zone_id(zone_name: str, token: str) -> str:
    """Get the Cloudflare zone_id for a zone name. Refuses to auto-create."""
    payload = _cf_request("GET", f"/zones?name={zone_name}", token)
    results = payload.get("result") or []
    if not results:
        sys.stderr.write(
            f"FATAL: zone '{zone_name}' not found in Cloudflare account. "
            f"Add the zone via the Cloudflare dashboard first (NS records at the "
            f"registrar are out of scope for this skill).\n"
        )
        sys.exit(2)
    return results[0]["id"]


def _list_records(zone_id: str, token: str) -> list[dict]:
    """List all DNS records in a zone (paginated)."""
    out: list[dict] = []
    page = 1
    while True:
        payload = _cf_request(
            "GET", f"/zones/{zone_id}/dns_records?per_page=100&page={page}", token
        )
        out.extend(payload.get("result") or [])
        info = payload.get("result_info") or {}
        if page * info.get("per_page", 100) >= info.get("total_count", 0):
            break
        page += 1
    return out


def _full_name(zone_name: str, record_name: str) -> str:
    """Resolve a YAML `name:` field to a fully-qualified DNS name.
    Conventions:
      - '@'  → apex (zone itself)
      - bare label like 'downloads' → '<label>.<zone>'
      - already-qualified (ends with zone) → unchanged
    """
    if record_name == "@":
        return zone_name
    if record_name.endswith("." + zone_name) or record_name == zone_name:
        return record_name
    return f"{record_name}.{zone_name}"


def _resolve_content(spec: dict, server_ip: str | None) -> str:
    """Resolve a record's `content` field. Honors `point_at: this_server` sentinel."""
    point_at = spec.get("point_at")
    if point_at == "this_server":
        if not server_ip:
            sys.stderr.write(
                "FATAL: record uses point_at: this_server but server_ip not set in YAML.\n"
            )
            sys.exit(2)
        return server_ip
    content = spec.get("content")
    if not content:
        sys.stderr.write(
            f"FATAL: record {spec.get('name')!r} has neither content nor point_at\n"
        )
        sys.exit(1)
    return content


def _record_drift(existing: dict, desired: dict) -> list[str]:
    """Return a list of fields that differ between existing CF record and desired."""
    drift = []
    if existing.get("content") != desired["content"]:
        drift.append(f"content {existing.get('content')!r}→{desired['content']!r}")
    if int(existing.get("ttl") or 1) != int(desired.get("ttl") or 1):
        drift.append(f"ttl {existing.get('ttl')}→{desired.get('ttl')}")
    if bool(existing.get("proxied")) != bool(desired.get("proxied")):
        drift.append(
            f"proxied {bool(existing.get('proxied'))}→{bool(desired.get('proxied'))}"
        )
    return drift


def _reconcile_record(
    zone_name: str,
    zone_id: str,
    existing_records: list[dict],
    spec: dict,
    server_ip: str | None,
    token: str,
    apply: bool,
) -> tuple[dict | None, str]:
    """Reconcile one record. Returns (record_dict_after, status_str)."""
    rtype = spec["type"]
    fqdn = _full_name(zone_name, spec["name"])
    content = _resolve_content(spec, server_ip)
    desired = {
        "type": rtype,
        "name": fqdn,
        "content": content,
        "ttl": spec.get("ttl", 1),
        "proxied": bool(spec.get("proxied", False)),
    }
    existing = next(
        (
            r
            for r in existing_records
            if r.get("type") == rtype and r.get("name") == fqdn
        ),
        None,
    )
    if existing:
        drift = _record_drift(existing, desired)
        if not drift:
            return existing, f"matched {rtype} {fqdn} → {content}"
        if apply:
            payload = _cf_request(
                "PUT",
                f"/zones/{zone_id}/dns_records/{existing['id']}",
                token,
                body=desired,
            )
            return payload.get("result"), (
                f"updated {rtype} {fqdn} ({'; '.join(drift)})"
            )
        return existing, f"would update {rtype} {fqdn} ({'; '.join(drift)})"
    # Create
    if apply:
        payload = _cf_request(
            "POST", f"/zones/{zone_id}/dns_records", token, body=desired
        )
        return payload.get("result"), f"created {rtype} {fqdn} → {content}"
    return None, f"would create {rtype} {fqdn} → {content}"


def _prune_records(
    zone_name: str,
    zone_id: str,
    existing_records: list[dict],
    declared: list[dict],
    server_ip: str | None,
    token: str,
    apply: bool,
) -> list[str]:
    """Delete CF records not present in YAML. Returns status lines.
    Skips records the skill shouldn't touch (NS records, SOA, anything outside
    the declared types). Only prunes A/AAAA/CNAME/TXT/MX.
    """
    prunable_types = {"A", "AAAA", "CNAME", "TXT", "MX"}
    declared_keys = set()
    for spec in declared:
        fqdn = _full_name(zone_name, spec["name"])
        declared_keys.add((spec["type"], fqdn))
    out = []
    for r in existing_records:
        if r.get("type") not in prunable_types:
            continue
        if (r.get("type"), r.get("name")) in declared_keys:
            continue
        if apply:
            _cf_request("DELETE", f"/zones/{zone_id}/dns_records/{r['id']}", token)
            out.append(f"pruned {r['type']} {r['name']} → {r.get('content')}")
        else:
            out.append(f"would prune {r['type']} {r['name']} → {r.get('content')}")
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Server-setup companion: nginx + certbot
# ──────────────────────────────────────────────────────────────────────────────


def _wait_for_dns(domain: str, expected_ip: str, timeout_s: int) -> bool:
    """Poll dig +short <domain> until it returns expected_ip. Returns True on hit."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = subprocess.run(
                ["dig", "+short", domain, "A"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            resolved = [line.strip() for line in r.stdout.splitlines() if line.strip()]
            if expected_ip in resolved:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def _run_cmd(cmd: list[str], dry_run: bool) -> tuple[int, str]:
    """Run a shell command. Returns (returncode, combined_output). dry_run prints only."""
    if dry_run:
        print(f"  $ (dry-run) {' '.join(cmd)}")
        return 0, ""
    print(f"  $ {' '.join(cmd)}")
    try:
        r = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=180
        )
        out = (r.stdout or "") + (r.stderr or "")
        if out.strip():
            for line in out.strip().splitlines():
                print(f"    {line}")
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except FileNotFoundError as e:
        return 127, f"not found: {e}"


def _server_setup_one(
    spec: dict,
    server_ip: str,
    certbot_email: str,
    apply: bool,
    wait_dns_s: int,
) -> int:
    """Run nginx + certbot bootstrap for one record. Returns exit code."""
    setup = spec.get("server_setup") or {}
    if not setup:
        return 0
    if spec.get("point_at") != "this_server":
        print(f"  skip server-setup: record does not point_at this_server")
        return 0
    domain = setup.get("domain")
    nginx_site = setup.get("nginx_site")
    want_certbot = bool(setup.get("certbot"))
    redirect = bool(setup.get("redirect", True))

    if not domain or not nginx_site:
        print(f"  ERROR: server_setup requires both domain and nginx_site")
        return 3

    print(f"  → server-setup: {domain}")
    print(f"  step 1/4: verify DNS resolves {domain} → {server_ip}")
    if apply:
        if not _wait_for_dns(domain, server_ip, wait_dns_s):
            print(f"  ERROR: DNS did not resolve to {server_ip} within {wait_dns_s}s")
            return 3
        print(f"    ✓ DNS confirmed")
    else:
        print(f"    (dry-run — skipping DNS poll)")

    print(f"  step 2/4: enable nginx site")
    nginx_enabled = Path("/etc/nginx/sites-enabled") / Path(nginx_site).name
    if not Path(nginx_site).exists():
        print(f"  ERROR: nginx site config not found at {nginx_site}")
        return 3
    if nginx_enabled.exists() or nginx_enabled.is_symlink():
        print(f"    ✓ already enabled at {nginx_enabled}")
    else:
        rc, _ = _run_cmd(["ln", "-s", nginx_site, str(nginx_enabled)], not apply)
        if rc != 0:
            return 3

    rc, _ = _run_cmd(["nginx", "-t"], not apply)
    if rc != 0:
        print(f"  ERROR: nginx -t failed; refusing to reload")
        return 3
    rc, _ = _run_cmd(["systemctl", "reload", "nginx"], not apply)
    if rc != 0:
        return 3

    if want_certbot:
        print(f"  step 3/4: certbot --nginx -d {domain}")
        cert_dir = Path("/etc/letsencrypt/live") / domain
        if cert_dir.exists():
            print(f"    ✓ certbot cert already present at {cert_dir}")
        else:
            cmd = [
                "certbot",
                "--nginx",
                "-d",
                domain,
                "--non-interactive",
                "--agree-tos",
                "--email",
                certbot_email,
            ]
            if redirect:
                cmd.append("--redirect")
            rc, _ = _run_cmd(cmd, not apply)
            if rc != 0:
                return 3

        print(f"  step 4/4: nginx reload after certbot")
        rc, _ = _run_cmd(["systemctl", "reload", "nginx"], not apply)
        if rc != 0:
            return 3
    else:
        print(f"  step 3/4: certbot disabled in YAML — skipped")
        print(f"  step 4/4: nginx reload — skipped")

    print(f"  ✓ server-setup complete for {domain}")
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Splat emit (best-effort)
# ──────────────────────────────────────────────────────────────────────────────


def _emit_splat(payload: dict) -> None:
    try:
        if "/opt/aria" not in sys.path:
            sys.path.insert(0, "/opt/aria")
        from splat_emitter import emit_splat  # type: ignore

        emit_splat(
            layer="cloudflare_dns_run",
            harness_source="cloudflare_dns",
            payload=payload,
        )
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Reconcile YAML → Cloudflare DNS records (+ optional nginx/certbot)."
    )
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="YAML config path")
    ap.add_argument(
        "--apply", action="store_true", help="Apply changes (default = dry-run)"
    )
    ap.add_argument(
        "--prune",
        action="store_true",
        help="Delete CF records not present in YAML (only A/AAAA/CNAME/TXT/MX)",
    )
    ap.add_argument(
        "--server-setup",
        action="store_true",
        help="After DNS apply, run nginx + certbot bootstrap for records with server_setup blocks",
    )
    ap.add_argument(
        "--wait-dns",
        type=int,
        default=60,
        help="Seconds to wait for DNS propagation before running server-setup (default 60)",
    )
    args = ap.parse_args()

    cfg = _load_config(Path(args.config))
    server_ip = cfg.get("server_ip")
    certbot_email = cfg.get("certbot_email", "")
    zones = cfg.get("zones") or []

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        sys.stderr.write(
            "FATAL: CLOUDFLARE_API_TOKEN not in env. "
            "Add it to .env (scope: Zone:Read + DNS:Edit on the listed zones).\n"
        )
        return 1

    print(
        f"# cloudflare-dns-deploy · apply={args.apply} · prune={args.prune} "
        f"· server_setup={args.server_setup}"
    )
    print(f"# config: {args.config}")
    print()

    summary: list[str] = []
    server_setup_specs: list[dict] = []

    for zone_block in zones:
        zone_name = zone_block["zone"]
        print(f"# zone: {zone_name}")
        zone_id = _resolve_zone_id(zone_name, token)
        existing = _list_records(zone_id, token)
        declared = zone_block.get("records") or []
        for spec in declared:
            _, status = _reconcile_record(
                zone_name, zone_id, existing, spec, server_ip, token, args.apply
            )
            print(f"  - {status}")
            summary.append(f"{zone_name}: {status}")
            if spec.get("server_setup"):
                server_setup_specs.append(spec)
        if args.prune:
            prune_status = _prune_records(
                zone_name, zone_id, existing, declared, server_ip, token, args.apply
            )
            for ps in prune_status:
                print(f"  - {ps}")
                summary.append(f"{zone_name}: {ps}")
        print()

    setup_failures = 0
    if args.server_setup and server_setup_specs:
        print("# server-setup pass")
        if os.geteuid() != 0:
            print(
                "  WARNING: not running as root — nginx + certbot steps likely to fail"
            )
        for spec in server_setup_specs:
            rc = _server_setup_one(
                spec, server_ip, certbot_email, args.apply, args.wait_dns
            )
            if rc != 0:
                setup_failures += 1
            print()

    _emit_splat(
        {
            "apply": args.apply,
            "prune": args.prune,
            "server_setup": args.server_setup,
            "summary": summary[:50],  # cap payload size
            "setup_failures": setup_failures,
        }
    )

    if setup_failures:
        print(f"# {setup_failures} server-setup failure(s) — see output above")
        return 3
    print("# done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
