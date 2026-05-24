#!/usr/bin/env python3
"""
stripe_sync.py — Sprint 021 S21.T1-A. Declarative product/price reconciler.

Reads stripe_products.yaml and reconciles to Stripe. Idempotent.

Matching rules:
  - Products: matched by metadata.aria_sku (the `sku:` field in YAML).
    If a product with that aria_sku doesn't exist on the account, it's created
    with the metadata baked in. If it exists, name/description are updated
    in place via stripe.Product.modify.
  - Prices: matched by (product, unit_amount, currency, recurring.interval).
    Stripe prices are IMMUTABLE — to change a price, you create a new one
    (the old one stays in Stripe as inactive, accessible to existing
    subscriptions). The skill creates new prices when the YAML changes
    them; it never tries to modify an existing price.

CLI:
  python3 stripe_sync.py                         # dry-run, test mode (default)
  python3 stripe_sync.py --apply                 # apply, test mode
  python3 stripe_sync.py --apply --prod          # apply, live mode (requires explicit --prod)
  python3 stripe_sync.py --apply --write-env     # also write resolved IDs into .env

Output:
  Prints a key=value map of {env_var: price_id, ...} that can be redirected
  or pasted into .env. Or use --write-env to merge in place.

Exit codes:
  0 = success (or dry-run completed)
  1 = config or API error
  2 = ambiguous / unsafe state — refused to write

Splat: every run emits a `stripe_sync_run` splat with the reconciled SKU list
and the dry-run/apply/prod flags, for ops audit.
"""
import argparse
import os
import re
import sys
from pathlib import Path

ENV_FILE = Path(".env")
DEFAULT_CONFIG = Path("stripe_products.yaml")

# Load .env so we can read Stripe keys + write to it
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

try:
    import stripe
except ImportError:
    sys.stderr.write("FATAL: stripe SDK not installed. pip install stripe\n")
    sys.exit(1)

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


def _resolve_stripe_key(cfg_mode: str, prod_flag: bool) -> tuple[str, str]:
    """Returns (api_key, mode_label). Refuses to use the live key without --prod."""
    if cfg_mode == "live" and not prod_flag:
        sys.stderr.write(
            "FATAL: config sets mode=live but --prod was not passed. Refusing to hit live API.\n"
            "Either flip mode: test in YAML, or pass --prod explicitly.\n"
        )
        sys.exit(2)
    if cfg_mode == "live" and prod_flag:
        key = os.environ.get("STRIPE_SECRET_KEY_LIVE") or os.environ.get(
            "STRIPE_SECRET_KEY"
        )
        if not key or not key.startswith("sk_live_"):
            sys.stderr.write(
                "FATAL: --prod requested but STRIPE_SECRET_KEY_LIVE (or STRIPE_SECRET_KEY) is not a live key (sk_live_...).\n"
            )
            sys.exit(1)
        return key, "live"
    # test mode
    key = os.environ.get("STRIPE_SECRET_KEY_TEST") or os.environ.get(
        "STRIPE_SECRET_KEY"
    )
    if not key:
        sys.stderr.write("FATAL: no STRIPE_SECRET_KEY in env (test mode).\n")
        sys.exit(1)
    if not key.startswith("sk_test_"):
        # If the only key available is a live key but mode=test, refuse — too easy to mis-fire.
        if key.startswith("sk_live_") and not prod_flag:
            sys.stderr.write(
                "FATAL: STRIPE_SECRET_KEY is a live key (sk_live_...) but mode=test was requested.\n"
                "Set STRIPE_SECRET_KEY_TEST=sk_test_... to use test mode.\n"
            )
            sys.exit(2)
    return key, "test"


def _find_product_by_sku(sku: str) -> dict | None:
    """List all active products and find the one with metadata.aria_sku=<sku>.
    Returns the Stripe Product object dict or None."""
    # Search API supports metadata queries; use it if available.
    try:
        results = stripe.Product.search(
            query=f"active:'true' AND metadata['aria_sku']:'{sku}'", limit=1
        )
        if results.get("data"):
            return results["data"][0]
    except stripe.error.InvalidRequestError:
        # Search not available on this account / API version — fall back to listing
        pass

    # Fallback: paginate through products
    starting_after = None
    while True:
        params = {"limit": 100, "active": True}
        if starting_after:
            params["starting_after"] = starting_after
        page = stripe.Product.list(**params)
        for p in page.get("data", []):
            if (p.get("metadata") or {}).get("aria_sku") == sku:
                return p
        if not page.get("has_more"):
            return None
        starting_after = page["data"][-1]["id"]


def _find_matching_price(product_id: str, price_spec: dict) -> dict | None:
    """Return existing Stripe Price matching unit_amount + currency + recurring.interval,
    or None if no match (need to create)."""
    recurring = price_spec.get("recurring") or {}
    starting_after = None
    while True:
        params = {"product": product_id, "limit": 100, "active": True}
        if starting_after:
            params["starting_after"] = starting_after
        page = stripe.Price.list(**params)
        for pr in page.get("data", []):
            if pr.get("unit_amount") != price_spec["unit_amount_cents"]:
                continue
            if pr.get("currency") != price_spec.get("currency", "usd").lower():
                continue
            r = pr.get("recurring") or {}
            if recurring:
                if r.get("interval") != recurring.get("interval"):
                    continue
                if r.get("interval_count", 1) != recurring.get("interval_count", 1):
                    continue
            else:
                # YAML says no recurring — only match one-time prices
                if r:
                    continue
            return pr
        if not page.get("has_more"):
            return None
        starting_after = page["data"][-1]["id"]


def _reconcile_product(product_spec: dict, apply: bool) -> tuple[str | None, str]:
    """Return (product_id, status_str)."""
    sku = product_spec["sku"]
    existing = _find_product_by_sku(sku)
    if existing:
        # Update name/description in place if drifted
        needs_update = existing.get("name") != product_spec["name"] or existing.get(
            "description"
        ) != product_spec.get("description", "")
        if needs_update:
            if apply:
                stripe.Product.modify(
                    existing["id"],
                    name=product_spec["name"],
                    description=product_spec.get("description", ""),
                )
                return existing["id"], f"updated (sku={sku})"
            else:
                return existing["id"], f"would update (sku={sku})"
        return existing["id"], f"matched (sku={sku})"
    # Create new
    if apply:
        new = stripe.Product.create(
            name=product_spec["name"],
            description=product_spec.get("description", ""),
            metadata={"aria_sku": sku},
        )
        return new["id"], f"created (sku={sku})"
    return None, f"would create (sku={sku})"


def _reconcile_price(
    product_id: str | None, price_spec: dict, apply: bool
) -> tuple[str | None, str]:
    env_var = price_spec["env_var"]
    if not product_id:
        return None, f"{env_var}: product not yet created (dry-run)"
    existing = _find_matching_price(product_id, price_spec)
    if existing:
        return existing["id"], f"{env_var}: matched ({existing['id']})"
    if apply:
        kwargs = dict(
            product=product_id,
            unit_amount=price_spec["unit_amount_cents"],
            currency=price_spec.get("currency", "usd").lower(),
            metadata={"aria_env_var": env_var},
        )
        recurring = price_spec.get("recurring")
        if recurring:
            kwargs["recurring"] = {
                "interval": recurring["interval"],
                "interval_count": recurring.get("interval_count", 1),
            }
        new = stripe.Price.create(**kwargs)
        return new["id"], f"{env_var}: created ({new['id']})"
    return None, f"{env_var}: would create"


def _write_env_vars(resolved: dict) -> int:
    """Merge resolved {env_var: price_id} into .env. Returns count updated."""
    if not ENV_FILE.exists():
        sys.stderr.write(f"FATAL: {ENV_FILE} does not exist\n")
        sys.exit(1)
    lines = ENV_FILE.read_text().splitlines()
    seen = set()
    out = []
    updated = 0
    added = 0
    for line in lines:
        m = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if m and m.group(1) in resolved:
            key = m.group(1)
            old_val = line.split("=", 1)[1].strip().strip('"').strip("'")
            new_val = resolved[key]
            seen.add(key)
            if old_val != new_val:
                out.append(f"{key}={new_val}")
                updated += 1
            else:
                out.append(line)
        else:
            out.append(line)
    # Append any keys that weren't in .env yet
    appendable = [(k, v) for k, v in resolved.items() if k not in seen]
    if appendable:
        out.append("")
        out.append(
            "# stripe-sync: appended "
            + __import__("datetime").datetime.now().isoformat()
        )
        for k, v in appendable:
            out.append(f"{k}={v}")
            added += 1
    ENV_FILE.write_text("\n".join(out) + "\n")
    return updated + added


def _emit_splat(payload: dict) -> None:
    """No-op in standalone mode. Aria Code hosted version logs to CertusOrdo splat chain."""
    pass



def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile YAML → Stripe products/prices.")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="YAML config path")
    ap.add_argument(
        "--apply", action="store_true", help="Apply changes (default = dry-run)"
    )
    ap.add_argument(
        "--prod",
        action="store_true",
        help="Allow live mode (required if YAML config mode=live)",
    )
    ap.add_argument(
        "--write-env",
        action="store_true",
        help="Merge resolved IDs into .env (requires --apply)",
    )
    args = ap.parse_args()

    cfg = _load_config(Path(args.config))
    cfg_mode = (cfg.get("mode") or "test").lower()

    api_key, mode_label = _resolve_stripe_key(cfg_mode, args.prod)
    stripe.api_key = api_key

    apply_flag = args.apply
    write_env = args.write_env and apply_flag

    print(
        f"# stripe-sync · mode={mode_label} · apply={apply_flag} · write_env={write_env}"
    )
    print(f"# config: {args.config}")
    print()

    resolved = {}
    summary = []

    for product_spec in cfg.get("products", []):
        product_id, product_status = _reconcile_product(product_spec, apply_flag)
        summary.append(f"product {product_spec['sku']}: {product_status}")
        for price_spec in product_spec.get("prices", []):
            price_id, price_status = _reconcile_price(
                product_id, price_spec, apply_flag
            )
            summary.append(f"  {price_status}")
            if price_id:
                resolved[price_spec["env_var"]] = price_id

    print("# Reconciliation summary:")
    for line in summary:
        print(f"#   {line}")
    print()

    print("# Resolved env vars (paste into .env or use --write-env):")
    for k in sorted(resolved.keys()):
        print(f"{k}={resolved[k]}")

    if write_env:
        n = _write_env_vars(resolved)
        print(f"\n# wrote {n} env var(s) into {ENV_FILE}", file=sys.stderr)

    _emit_splat(
        {
            "mode": mode_label,
            "apply": apply_flag,
            "write_env": write_env,
            "products_count": len(cfg.get("products", [])),
            "resolved_count": len(resolved),
            "summary": summary,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
