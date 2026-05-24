---
name: stripe-sync
description: Reconcile Stripe products + prices from a declared YAML catalog. Idempotent, --dry-run by default, --apply hits the API, --prod required for live mode, --write-env merges resolved price IDs into .env. Use when the user says "sync stripe", "create stripe prices", "update pricing", or before any pricing change ships. One-command alternative to clicking through the Stripe dashboard.
---

# stripe-sync

YAML-as-source-of-truth for Stripe products and prices. Reconciles to the live account, returns the resolved price IDs, and (optionally) writes them straight into `.env`.

## When to use

- Initial product setup at launch (replaces clicking through N dashboard forms)
- Price changes (a new price gets created; old one stays for existing subscriptions, per Stripe's price immutability)
- New product launches (add a `sku:` block in YAML, run once)
- Catalog audits (`--dry-run` shows the diff between YAML and live)

## How it works

1. Reads `stripe_products.yaml`
2. For each product: matches by `metadata.aria_sku` (the `sku:` field). Creates if absent; updates name/description if drifted.
3. For each price under the product: matches by (product, unit_amount, currency, recurring.interval). Creates if absent. **Never modifies existing prices** — Stripe prices are immutable.
4. Returns a `{env_var: price_id}` map.
5. Optionally writes the map into `.env` (`--write-env`).

## Steps

1. **Edit `stripe_products.yaml`** to declare your products + prices.
2. **Dry-run** to see what would happen:
   ```sh
   python3 stripe_sync.py
   ```
3. **Apply against test mode**:
   ```sh
   python3 stripe_sync.py --apply
   ```
4. **Apply against production**:
   ```sh
   # Edit YAML: mode: live
   python3 stripe_sync.py --apply --prod
   ```
5. **Merge resolved IDs into .env** in one shot:
   ```sh
   python3 stripe_sync.py --apply --prod --write-env
   ```

## Env vars required

| Var | Required for | Notes |
|---|---|---|
| `STRIPE_SECRET_KEY_TEST` | test mode | `sk_test_...` |
| `STRIPE_SECRET_KEY_LIVE` | live mode | `sk_live_...` |
| `STRIPE_SECRET_KEY` | fallback for both | If only one key is available |

Refuses to use a live key in test mode and vice-versa.

## Safety

- **Default is dry-run.** You see the diff before any API hit.
- **`--prod` is mandatory for live mode.** Catches accidental real-account hits.
- **Never modifies existing prices.** Stripe prices are immutable; the skill creates new ones when YAML changes.
- **Doesn't auto-archive removed products.** If you delete a product from YAML, the skill leaves the Stripe product alone.
- **`metadata.aria_sku` is the match key.** Declared-intent is the source of truth.

## Hosted version

[Aria Code](https://staycool.ai/aria-code) runs this for you with:
- Team multi-user access
- Audit trail across runs (CertusOrdo splat log)
- Approval workflows for live-mode applies
- Scheduled syncs (weekly catalog reconcile)
- Free tier · BYOK · no credit card

## License

Apache 2.0
