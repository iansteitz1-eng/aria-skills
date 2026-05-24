#!/usr/bin/env python3
"""
vendor_billing.py — Sprint 021 T3-B. Vendor billing-action worker.

Declarative vendor roster + adapter layer for live billing actions.

Subcommands:
  sync                          — mirror YAML roster into v4_vendors (idempotent)
  status                        — print all vendors with state + last action
  next-due [--days N]           — list vendors with renewal in next N days (default 30)
  record-payment --vendor X --amount Y --ref Z [--apply]
                                — log a manual payment to v4_vendor_billing_log
  fetch-balance --vendor X      — adapter call (Liquid Web only today)
  pay --vendor X --amount Y --apply --prod --confirm-amount Y
                                — live payment through adapter. TRIPLE-GATED:
                                  (1) --apply, (2) --prod, (3) --confirm-amount
                                  must equal --amount. Refuses without LIQUID-WEB creds.

Default mode is dry-run for any state-changing subcommand. The triple-gate
on `pay` exists because vendor payments are HIGH BLAST RADIUS — money
moves and cannot be undone by the worker.

Splat: every action emits a `vendor_billing_action` external splat.

CLI examples:
  python3 vendor_billing.py sync
  python3 vendor_billing.py status
  python3 vendor_billing.py next-due --days 45
  python3 vendor_billing.py record-payment --vendor liquid_web --amount 250.00 --ref "stripe ch_xyz" --apply
  python3 vendor_billing.py fetch-balance --vendor liquid_web        # safe; read-only
  python3 vendor_billing.py pay --vendor liquid_web --amount 250.00 --confirm-amount 250.00 --apply --prod
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ENV_FILE = Path(".env")
DEFAULT_CONFIG = Path("./vendors.yaml")

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
    import psycopg2
    from psycopg2.extras import Json, RealDictCursor
except ImportError:
    sys.stderr.write("FATAL: psycopg2 not installed.\n")
    sys.exit(1)


def _load_config(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(f"FATAL: config not found at {path}\n")
        sys.exit(1)
    cfg = yaml.safe_load(path.read_text()) or {}
    if not isinstance(cfg, dict):
        sys.stderr.write("FATAL: config must be a mapping.\n")
        sys.exit(1)
    return cfg


def _resolve_mode(cfg_mode: str, prod_flag: bool, requires_live: bool) -> str:
    """Returns 'test' or 'live'. Refuses live without --prod when requires_live."""
    cfg_mode = (cfg_mode or "test").lower()
    if cfg_mode not in ("test", "live"):
        sys.stderr.write(f"FATAL: unknown mode '{cfg_mode}' in config.\n")
        sys.exit(1)
    if requires_live:
        if cfg_mode == "live" and not prod_flag:
            sys.stderr.write(
                "FATAL: config says mode=live but --prod not passed.\n"
                "Refusing live billing action.\n"
            )
            sys.exit(2)
        if cfg_mode == "test" and prod_flag:
            sys.stderr.write(
                "FATAL: --prod was passed but config says mode=test.\n"
                "Flip mode: live in YAML to actually move money.\n"
            )
            sys.exit(2)
    return cfg_mode


def _db():
    db_url = os.environ.get("V4_DB_URL", "")
    if not db_url:
        sys.stderr.write("FATAL: V4_DB_URL missing.\n")
        sys.exit(2)
    return psycopg2.connect(db_url)


def _insert_log(
    conn,
    *,
    vendor_id: str,
    action: str,
    mode: str,
    amount: Decimal | None,
    currency: str | None,
    ref: str | None,
    ok: bool,
    error: str | None,
    meta: dict,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO v4_vendor_billing_log (
                vendor_id, action, mode, amount, currency, ref, ok, error, meta
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                vendor_id,
                action,
                mode,
                amount,
                currency,
                ref,
                ok,
                error,
                Json(meta),
            ),
        )
        conn.commit()
        return cur.fetchone()[0]


def _emit_splat(payload: dict) -> None:
    try:
        from splat_emitter import emit_external_splat  # type: ignore

        emit_external_splat(
            interface="vendor_billing",
            session_id=f"vendor:{payload.get('vendor_id', '?')}",
            prompt=f"action={payload.get('action', '?')} amount={payload.get('amount', '')}",
            response=f"ok={payload.get('ok', False)} ref={payload.get('ref', '')}",
            model_used="vendor_billing",
            layer=4,
            extra_meta=payload,
        )
    except Exception:
        pass


# ---------- adapter layer ----------


def _adapter_liquid_web_creds() -> tuple[str, str] | None:
    u = os.environ.get("LIQUIDWEB_USERNAME", "")
    p = os.environ.get("LIQUIDWEB_PASSWORD", "")
    if not u or not p:
        return None
    return u, p


def _adapter_liquid_web_fetch_balance() -> dict:
    """Returns {ok, balance_usd, raw} or {ok:False, error}."""
    creds = _adapter_liquid_web_creds()
    if not creds:
        return {
            "ok": False,
            "error": "adapter_unavailable: LIQUIDWEB_USERNAME/PASSWORD missing in .env",
        }
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx not installed"}
    u, p = creds
    try:
        with httpx.Client(timeout=20.0, auth=(u, p)) as c:
            r = c.post(
                "https://api.liquidweb.com/bleed/billing/account/details",
                json={"params": {}},
            )
        if r.status_code not in (200, 201):
            return {"ok": False, "error": f"http {r.status_code}: {r.text[:200]}"}
        body = r.json()
        return {"ok": True, "balance_usd": body.get("balance"), "raw": body}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _adapter_liquid_web_pay(amount: Decimal) -> dict:
    """Live payment through LW. Returns {ok, ref, raw} or {ok:False, error}."""
    creds = _adapter_liquid_web_creds()
    if not creds:
        return {
            "ok": False,
            "error": "adapter_unavailable: LIQUIDWEB_USERNAME/PASSWORD missing in .env",
        }
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx not installed"}
    u, p = creds
    try:
        with httpx.Client(timeout=30.0, auth=(u, p)) as c:
            r = c.post(
                "https://api.liquidweb.com/bleed/billing/payment/submit",
                json={"params": {"amount": str(amount)}},
            )
        if r.status_code not in (200, 201):
            return {"ok": False, "error": f"http {r.status_code}: {r.text[:200]}"}
        body = r.json()
        return {
            "ok": True,
            "ref": str(body.get("id") or body.get("ref") or "lw_payment"),
            "raw": body,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


# ---------- subcommands ----------


def cmd_sync(args, cfg: dict) -> int:
    """Mirror YAML roster into v4_vendors. Idempotent UPSERT."""
    vendors = cfg.get("vendors") or []
    print(f"# vendor-billing sync · {len(vendors)} vendor(s) in YAML")
    conn = _db()
    try:
        with conn.cursor() as cur:
            for v in vendors:
                vid = v.get("id")
                if not vid:
                    print(f"WARN: vendor with no id, skipping: {v}", file=sys.stderr)
                    continue
                cur.execute(
                    """
                    INSERT INTO v4_vendors (
                        vendor_id, display_name, vendor_type, adapter,
                        contact_email, portal_url, next_renewal,
                        autopay, monthly_cost_usd, currency, notes, meta, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                    ON CONFLICT (vendor_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        vendor_type  = EXCLUDED.vendor_type,
                        adapter      = EXCLUDED.adapter,
                        contact_email= EXCLUDED.contact_email,
                        portal_url   = EXCLUDED.portal_url,
                        next_renewal = EXCLUDED.next_renewal,
                        autopay      = EXCLUDED.autopay,
                        monthly_cost_usd = EXCLUDED.monthly_cost_usd,
                        currency     = EXCLUDED.currency,
                        notes        = EXCLUDED.notes,
                        meta         = EXCLUDED.meta,
                        updated_at   = now()
                    """,
                    (
                        vid,
                        v.get("display_name", vid),
                        v.get("vendor_type", "unknown"),
                        v.get("adapter", "generic"),
                        v.get("contact_email"),
                        v.get("portal_url"),
                        v.get("next_renewal"),
                        bool(v.get("autopay", False)),
                        v.get("monthly_cost_usd"),
                        v.get("currency", "USD"),
                        v.get("notes"),
                        Json(v.get("meta") or {}),
                    ),
                )
                print(f"   - {vid} ({v.get('display_name', vid)}): upserted")
        conn.commit()
    finally:
        conn.close()
    return 0


def cmd_status(args, cfg: dict) -> int:
    conn = _db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT v.*, (
                    SELECT json_build_object(
                        'action', l.action,
                        'amount', l.amount,
                        'ok', l.ok,
                        'occurred_at', l.occurred_at
                    )
                    FROM v4_vendor_billing_log l
                    WHERE l.vendor_id = v.vendor_id
                    ORDER BY l.occurred_at DESC LIMIT 1
                ) AS last_action
                FROM v4_vendors v
                ORDER BY v.vendor_id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    print(f"# vendor-billing status · {len(rows)} vendor(s)")
    print()
    for r in rows:
        autopay = "AUTOPAY-ON " if r["autopay"] else "AUTOPAY-OFF"
        renewal = r["next_renewal"] or "—"
        cost = (
            f"${r['monthly_cost_usd']:.2f}/mo"
            if r["monthly_cost_usd"] is not None
            else "—"
        )
        last = r["last_action"]
        last_str = (
            f"last: {last['action']} ok={last['ok']} {last['occurred_at']}"
            if last
            else "last: (none)"
        )
        print(
            f"  {r['vendor_id']:14}  {autopay}  {cost:14}  renewal={renewal}  [{r['adapter']}]"
        )
        print(f"                {last_str}")
    return 0


def cmd_next_due(args, cfg: dict) -> int:
    conn = _db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT vendor_id, display_name, next_renewal, monthly_cost_usd, autopay
                FROM v4_vendors
                WHERE next_renewal IS NOT NULL
                  AND next_renewal <= CURRENT_DATE + (%s || ' days')::interval
                ORDER BY next_renewal ASC
                """,
                (args.days,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    print(f"# vendors with renewal in next {args.days} day(s) · {len(rows)} found")
    for r in rows:
        flag = "(autopay)" if r["autopay"] else "(MANUAL)"
        cost = (
            f"${r['monthly_cost_usd']:.2f}"
            if r["monthly_cost_usd"] is not None
            else "?"
        )
        print(f"  {r['next_renewal']}  {r['vendor_id']:14}  {cost:>10}  {flag}")
    return 0


def cmd_record_payment(args, cfg: dict) -> int:
    """Manual record of a payment Ian made out-of-band. No money moves."""
    try:
        amount = Decimal(args.amount)
    except InvalidOperation:
        sys.stderr.write(f"FATAL: invalid amount '{args.amount}'\n")
        return 1
    if amount <= 0:
        sys.stderr.write("FATAL: amount must be > 0\n")
        return 1
    mode = _resolve_mode(cfg.get("mode"), False, requires_live=False)
    if not args.apply:
        print(
            f"# DRY-RUN record-payment vendor={args.vendor} amount={amount} "
            f"currency={args.currency} ref={args.ref or '—'}"
        )
        print("# pass --apply to actually write the audit row.")
        return 0
    conn = _db()
    try:
        log_id = _insert_log(
            conn,
            vendor_id=args.vendor,
            action="record_payment",
            mode=mode,
            amount=amount,
            currency=args.currency,
            ref=args.ref,
            ok=True,
            error=None,
            meta={"source": "manual_record"},
        )
    finally:
        conn.close()
    _emit_splat(
        {
            "vendor_id": args.vendor,
            "action": "record_payment",
            "amount": str(amount),
            "ref": args.ref,
            "ok": True,
        }
    )
    print(f"# recorded payment vendor={args.vendor} amount={amount} log_id={log_id}")
    return 0


def cmd_fetch_balance(args, cfg: dict) -> int:
    """Read-only adapter call. Doesn't move money."""
    conn = _db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM v4_vendors WHERE vendor_id=%s", (args.vendor,))
            v = cur.fetchone()
    finally:
        conn.close()
    if not v:
        sys.stderr.write(
            f"FATAL: vendor '{args.vendor}' not in v4_vendors. Run `sync` first.\n"
        )
        return 1
    adapter = v["adapter"] or "generic"
    if adapter == "liquid_web":
        result = _adapter_liquid_web_fetch_balance()
    elif adapter == "generic":
        result = {
            "ok": False,
            "error": "no live adapter for generic vendors; check portal manually",
        }
    else:
        result = {"ok": False, "error": f"unknown adapter '{adapter}'"}

    mode = _resolve_mode(cfg.get("mode"), False, requires_live=False)
    conn = _db()
    try:
        _insert_log(
            conn,
            vendor_id=args.vendor,
            action="fetch_balance",
            mode=mode,
            amount=(
                Decimal(str(result.get("balance_usd")))
                if result.get("balance_usd") is not None
                else None
            ),
            currency="USD",
            ref=None,
            ok=bool(result.get("ok")),
            error=None if result.get("ok") else result.get("error"),
            meta={k: v for k, v in result.items() if k != "raw"},
        )
    finally:
        conn.close()
    _emit_splat(
        {
            "vendor_id": args.vendor,
            "action": "fetch_balance",
            "ok": bool(result.get("ok")),
            "balance_usd": result.get("balance_usd"),
        }
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


def cmd_pay(args, cfg: dict) -> int:
    """TRIPLE-GATED live payment. Refuses unless --apply AND --prod AND --confirm-amount matches."""
    try:
        amount = Decimal(args.amount)
        confirm = Decimal(args.confirm_amount)
    except InvalidOperation:
        sys.stderr.write("FATAL: invalid amount or confirm-amount\n")
        return 1
    if amount != confirm:
        sys.stderr.write(
            f"FATAL: --amount ({amount}) != --confirm-amount ({confirm}). "
            "Refusing — confirm-amount must match exactly.\n"
        )
        return 2
    if amount <= 0:
        sys.stderr.write("FATAL: amount must be > 0\n")
        return 1
    if not args.apply:
        sys.stderr.write("FATAL: --apply required to actually pay.\n")
        return 2
    if not args.prod:
        sys.stderr.write(
            "FATAL: --prod required to actually pay.\n"
            "Live payments require BOTH --apply AND --prod (and a matching --confirm-amount).\n"
        )
        return 2

    mode = _resolve_mode(cfg.get("mode"), args.prod, requires_live=True)
    # mode is guaranteed 'live' here due to requires_live + --prod gate

    conn = _db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM v4_vendors WHERE vendor_id=%s", (args.vendor,))
            v = cur.fetchone()
    finally:
        conn.close()
    if not v:
        sys.stderr.write(f"FATAL: vendor '{args.vendor}' not in v4_vendors.\n")
        return 1

    adapter = v["adapter"] or "generic"
    if adapter == "liquid_web":
        result = _adapter_liquid_web_pay(amount)
    else:
        result = {
            "ok": False,
            "error": f"adapter '{adapter}' has no live-pay implementation. "
            "Use `record-payment` for manual recording.",
        }

    conn = _db()
    try:
        log_id = _insert_log(
            conn,
            vendor_id=args.vendor,
            action="live_payment",
            mode=mode,
            amount=amount,
            currency=v["currency"] or "USD",
            ref=result.get("ref"),
            ok=bool(result.get("ok")),
            error=None if result.get("ok") else result.get("error"),
            meta={k: v for k, v in result.items() if k != "raw"},
        )
    finally:
        conn.close()
    _emit_splat(
        {
            "vendor_id": args.vendor,
            "action": "live_payment",
            "amount": str(amount),
            "ok": bool(result.get("ok")),
            "ref": result.get("ref"),
        }
    )

    if result.get("ok"):
        print(
            f"# PAID vendor={args.vendor} amount={amount} ref={result.get('ref')} log_id={log_id}"
        )
        return 0
    print(
        f"# FAIL vendor={args.vendor} log_id={log_id} err={result.get('error')}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Vendor billing actions (Sprint 021 T3-B)."
    )
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="YAML config path")

    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sync", help="Mirror YAML roster into v4_vendors")
    sub.add_parser("status", help="Print all vendors with state + last action")

    sp_due = sub.add_parser("next-due", help="Show upcoming renewals")
    sp_due.add_argument("--days", type=int, default=30)

    sp_rec = sub.add_parser("record-payment", help="Log a manual payment")
    sp_rec.add_argument("--vendor", required=True)
    sp_rec.add_argument("--amount", required=True)
    sp_rec.add_argument("--currency", default="USD")
    sp_rec.add_argument("--ref", default="")
    sp_rec.add_argument("--apply", action="store_true")

    sp_fb = sub.add_parser("fetch-balance", help="Adapter balance read")
    sp_fb.add_argument("--vendor", required=True)

    sp_pay = sub.add_parser("pay", help="LIVE payment through adapter — triple-gated")
    sp_pay.add_argument("--vendor", required=True)
    sp_pay.add_argument("--amount", required=True)
    sp_pay.add_argument("--confirm-amount", required=True)
    sp_pay.add_argument("--apply", action="store_true")
    sp_pay.add_argument("--prod", action="store_true")

    args = ap.parse_args()
    cfg = _load_config(Path(args.config))

    dispatch = {
        "sync": cmd_sync,
        "status": cmd_status,
        "next-due": cmd_next_due,
        "record-payment": cmd_record_payment,
        "fetch-balance": cmd_fetch_balance,
        "pay": cmd_pay,
    }
    fn = dispatch.get(args.cmd)
    if not fn:
        sys.stderr.write(f"FATAL: unknown subcommand '{args.cmd}'\n")
        return 1
    return fn(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
