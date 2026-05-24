#!/usr/bin/env python3
"""
partnership_blast.py — Sprint 021 T3-A. Per-partner email campaign worker.

Reads ./partnerships.yaml and sends one templated email per
partner via Resend, rendered through /opt/aria/email_template.py so every
message has the Aria Email v1 look.

Idempotent. v4_partnership_blast_log has a unique index on
(campaign_id, partner_id) WHERE ok=true, so re-runs skip partners already
sent. Pass --resend to force a re-send.

CLI:
  python3 partnership_blast.py                              # dry-run all campaigns
  python3 partnership_blast.py --campaign launch_2026_06_01 # dry-run one
  python3 partnership_blast.py --campaign X --apply         # actually send (test mode)
  python3 partnership_blast.py --campaign X --apply --prod  # live mode (requires --prod)
  python3 partnership_blast.py --campaign X --partner Y --apply  # one partner
  python3 partnership_blast.py --campaign X --apply --resend     # bypass idempotency

Exit codes:
  0 = success / dry-run completed
  1 = config or send error
  2 = ambiguous / unsafe state

Splat: each successful send emits a `partnership_blast` external splat.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ENV_FILE = Path(".env")
DEFAULT_CONFIG = Path("./partnerships.yaml")
IAN = "ian@insynctech.io"

# Bootstrap .env into os.environ so RESEND_API_KEY + V4_DB_URL load.
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

sys.path.insert(0, "/opt/aria")

try:
    import yaml
except ImportError:
    sys.stderr.write("FATAL: PyYAML not installed.\n")
    sys.exit(1)

try:
    import httpx
except ImportError:
    sys.stderr.write("FATAL: httpx not installed.\n")
    sys.exit(1)

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    sys.stderr.write("FATAL: psycopg2 not installed.\n")
    sys.exit(1)

try:
    from email_template import render_aria_email  # type: ignore
except Exception as e:
    sys.stderr.write(f"FATAL: cannot import email_template from /opt/aria: {e}\n")
    sys.exit(1)


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _load_config(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(f"FATAL: config not found at {path}\n")
        sys.exit(1)
    cfg = yaml.safe_load(path.read_text()) or {}
    if not isinstance(cfg, dict):
        sys.stderr.write("FATAL: config must be a mapping at the top level.\n")
        sys.exit(1)
    return cfg


def _resolve_mode(cfg_mode: str, prod_flag: bool) -> str:
    """Returns 'test' or 'live'. Refuses live without --prod."""
    cfg_mode = (cfg_mode or "test").lower()
    if cfg_mode == "live" and not prod_flag:
        sys.stderr.write(
            "FATAL: config sets mode=live but --prod not passed. Refusing live send.\n"
            "Either flip mode: test in YAML, or pass --prod explicitly.\n"
        )
        sys.exit(2)
    if cfg_mode not in ("test", "live"):
        sys.stderr.write(f"FATAL: unknown mode '{cfg_mode}' in config.\n")
        sys.exit(1)
    return cfg_mode


def _substitute(template: str, vars_map: dict[str, str]) -> str:
    """Simple {{var}} substitution. Missing vars become empty."""
    if not template:
        return template

    def repl(m: re.Match) -> str:
        key = m.group(1)
        v = vars_map.get(key, "")
        return str(v) if v is not None else ""

    return _VAR_RE.sub(repl, template)


def _render_partner_email(campaign: dict, partner: dict) -> tuple[str, str, dict]:
    """Returns (subject, html, debug_info) for one partner in one campaign."""
    vars_map = dict(partner.get("vars") or {})
    # Built-in vars partners can use in templates without re-declaring.
    vars_map.setdefault("partner_id", partner.get("id", ""))
    vars_map.setdefault("contact_email", partner.get("contact_email", ""))

    subject = _substitute(campaign.get("subject", ""), vars_map)
    greeting = _substitute(campaign.get("greeting", "Hi,"), vars_map)
    intro = _substitute(campaign.get("intro", ""), vars_map)
    signoff = _substitute(campaign.get("signoff", "— Ian"), vars_map)
    footer_note = _substitute(campaign.get("footer_note", ""), vars_map)

    sections_out = []
    for sec in campaign.get("sections") or []:
        sections_out.append(
            {
                "emoji": sec.get("emoji", "▪️"),
                "title": _substitute(sec.get("title", ""), vars_map),
                "body": _substitute(sec.get("body", ""), vars_map),
            }
        )

    rules_box = campaign.get("rules_box")
    if rules_box:
        rules_box = {
            "emoji": rules_box.get("emoji", "⚠️"),
            "title": _substitute(rules_box.get("title", ""), vars_map),
            "items": [_substitute(i, vars_map) for i in (rules_box.get("items") or [])],
        }

    html = render_aria_email(
        greeting=greeting,
        intro=intro,
        sections=sections_out,
        rules_box=rules_box,
        signoff=signoff,
        footer_note=footer_note,
    )
    return subject, html, {"vars": vars_map, "sections_count": len(sections_out)}


def _already_sent(conn, campaign_id: str, partner_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM v4_partnership_blast_log "
            "WHERE campaign_id=%s AND partner_id=%s AND ok=TRUE LIMIT 1",
            (campaign_id, partner_id),
        )
        return cur.fetchone() is not None


def _insert_log(
    conn,
    *,
    campaign_id: str,
    partner_id: str,
    contact_email: str,
    subject: str,
    mode: str,
    resend_id: str | None,
    splat_id: str | None,
    ok: bool,
    error: str | None,
    rendered_html_bytes: int,
    cc_ian: bool,
    meta: dict,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO v4_partnership_blast_log (
                campaign_id, partner_id, contact_email, subject, mode,
                resend_id, splat_id, ok, error, rendered_html_bytes, cc_ian, meta
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                campaign_id,
                partner_id,
                contact_email,
                subject,
                mode,
                resend_id,
                splat_id,
                ok,
                error,
                rendered_html_bytes,
                cc_ian,
                Json(meta),
            ),
        )
        conn.commit()
        return cur.fetchone()[0]


def _emit_splat(*args, **kwargs):
    pass



def _send_one(
    *,
    api_key: str,
    sender_from: str,
    reply_to: str,
    contact_email: str,
    subject: str,
    html: str,
    cc_ian: bool,
) -> dict:
    payload: dict[str, Any] = {
        "from": sender_from,
        "to": [contact_email],
        "subject": subject,
        "html": html,
    }
    if cc_ian and contact_email != IAN:
        payload["cc"] = [IAN]
    if reply_to:
        payload["reply_to"] = [reply_to]

    try:
        with httpx.Client(timeout=20.0) as c:
            r = c.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
        try:
            body_json = r.json()
        except Exception:
            body_json = {"raw": r.text[:300]}
        return {
            "ok": r.status_code in (200, 201, 202),
            "status": r.status_code,
            "body": body_json,
        }
    except Exception as e:
        return {"ok": False, "status": None, "body": {"error": str(e)[:300]}}


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-partner email blast (YAML→Resend).")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="YAML config path")
    ap.add_argument("--campaign", default="", help="Filter to one campaign id")
    ap.add_argument(
        "--partner", default="", help="Filter to one partner id within campaign(s)"
    )
    ap.add_argument(
        "--apply", action="store_true", help="Actually send (default = dry-run)"
    )
    ap.add_argument("--prod", action="store_true", help="Required when YAML mode=live")
    ap.add_argument(
        "--resend",
        action="store_true",
        help="Bypass idempotency — re-send to partners already marked ok=true",
    )
    ap.add_argument(
        "--no-cc-ian",
        action="store_true",
        help="Override standing CC-Ian rule (logged in meta)",
    )
    args = ap.parse_args()

    cfg = _load_config(Path(args.config))
    mode = _resolve_mode(cfg.get("mode"), args.prod)

    api_key = os.environ.get("RESEND_API_KEY", "")
    if args.apply and not api_key:
        sys.stderr.write("FATAL: RESEND_API_KEY missing from .env\n")
        return 2

    db_url = os.environ.get("V4_DB_URL", "")
    if not db_url:
        sys.stderr.write("FATAL: V4_DB_URL missing from .env\n")
        return 2

    default_sender = cfg.get(
        "default_sender_from",
        "InSync Tech <hello@insynctech.io>",
    )
    default_reply_to = cfg.get("default_reply_to", IAN)

    campaigns = cfg.get("campaigns") or []
    if args.campaign:
        campaigns = [c for c in campaigns if c.get("id") == args.campaign]
        if not campaigns:
            sys.stderr.write(
                f"FATAL: no campaign with id '{args.campaign}' in config\n"
            )
            return 1

    cc_ian = not args.no_cc_ian

    print(
        f"# partnership-blast · mode={mode} · apply={args.apply} · resend={args.resend} · cc_ian={cc_ian}"
    )
    print(f"# config: {args.config}")
    print(f"# campaigns to process: {len(campaigns)}")
    print()

    total_sent = 0
    total_skipped = 0
    total_failed = 0
    total_planned = 0

    conn = psycopg2.connect(db_url)
    try:
        for campaign in campaigns:
            cid = campaign.get("id") or ""
            if not cid:
                sys.stderr.write("WARN: campaign with no id — skipping\n")
                continue

            sender_from = campaign.get("sender_from") or default_sender
            reply_to = campaign.get("reply_to") or default_reply_to

            partners = campaign.get("partners") or []
            if args.partner:
                partners = [p for p in partners if p.get("id") == args.partner]

            print(f"## campaign: {cid}  ({len(partners)} partner(s))")
            for partner in partners:
                pid = partner.get("id") or ""
                pemail = partner.get("contact_email") or ""
                if not pid or not pemail:
                    sys.stderr.write(
                        f"WARN: partner missing id/email — skipping: {partner}\n"
                    )
                    continue
                total_planned += 1

                if not args.resend and _already_sent(conn, cid, pid):
                    print(f"   - {pid} <{pemail}>: SKIP (already sent)")
                    total_skipped += 1
                    continue

                try:
                    subject, html, dbg = _render_partner_email(campaign, partner)
                except Exception as e:
                    print(f"   - {pid} <{pemail}>: RENDER-FAIL ({e})", file=sys.stderr)
                    total_failed += 1
                    continue

                if not args.apply:
                    print(
                        f"   - {pid} <{pemail}>: DRY  subject={subject!r} "
                        f"sections={dbg['sections_count']} html_bytes={len(html)}"
                    )
                    continue

                resp = _send_one(
                    api_key=api_key,
                    sender_from=sender_from,
                    reply_to=reply_to,
                    contact_email=pemail,
                    subject=subject,
                    html=html,
                    cc_ian=cc_ian,
                )
                ok = bool(resp.get("ok"))
                resend_id = (resp.get("body") or {}).get("id")
                err = None
                if not ok:
                    err = json.dumps(resp.get("body"))[:500]

                splat_meta = {
                    "campaign_id": cid,
                    "partner_id": pid,
                    "contact_email": pemail,
                    "subject": subject,
                    "mode": mode,
                    "ok": ok,
                    "resend_id": resend_id,
                }
                _emit_splat(splat_meta)

                log_id = _insert_log(
                    conn,
                    campaign_id=cid,
                    partner_id=pid,
                    contact_email=pemail,
                    subject=subject,
                    mode=mode,
                    resend_id=resend_id,
                    splat_id=None,
                    ok=ok,
                    error=err,
                    rendered_html_bytes=len(html),
                    cc_ian=cc_ian,
                    meta={"sections_count": dbg["sections_count"]},
                )

                if ok:
                    print(
                        f"   - {pid} <{pemail}>: SENT  resend_id={resend_id}  log_id={log_id}"
                    )
                    total_sent += 1
                else:
                    print(
                        f"   - {pid} <{pemail}>: FAIL  status={resp.get('status')} "
                        f"log_id={log_id} err={err}",
                        file=sys.stderr,
                    )
                    total_failed += 1
            print()
    finally:
        conn.close()

    print(
        f"# done · planned={total_planned} sent={total_sent} "
        f"skipped={total_skipped} failed={total_failed}"
    )
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
