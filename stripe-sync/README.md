# stripe-sync

> **YAML → Stripe products + prices. One command. Idempotent.**

Replaces clicking through the Stripe dashboard to create or update products and prices. Your catalog lives in `stripe_products.yaml`; this skill reconciles it to your Stripe account.

```sh
# Manual: ~45 min in Stripe dashboard for ~10 products + ~15 prices
# This skill:
python3 stripe_sync.py --apply --prod --write-env
```

## 30-second install

```sh
pip install -r requirements.txt

# Get a test secret key from dashboard.stripe.com → Developers → API keys (toggle to Test mode)
echo "STRIPE_SECRET_KEY_TEST=sk_test_..." > .env

# Edit your products + prices in stripe_products.yaml
python3 stripe_sync.py             # dry-run, see what would happen
python3 stripe_sync.py --apply     # apply (test mode)
```

## Live mode

```sh
# In stripe_products.yaml, flip:
mode: live

# Add live key to .env:
echo "STRIPE_SECRET_KEY_LIVE=sk_live_..." >> .env

# Then:
python3 stripe_sync.py --apply --prod --write-env
```

The `--prod` flag is required for live mode (belt + braces — safety against accidental live hits). `--write-env` merges resolved price IDs into your `.env` for your application to read.

## Idempotent re-runs

Re-running the same YAML produces no changes:

```
# Reconciliation summary:
#   product pro: matched (sku=pro)
#     STRIPE_PRICE_PRO_MONTHLY: matched (price_1NXy...)
```

`matched` = the YAML declaration matches the live Stripe object. No API write happens. Safe to cron.

## When prices change

Stripe prices are **immutable**. If you change `unit_amount_cents` in YAML:
- The OLD price stays in Stripe (still works for existing subscriptions)
- A NEW price gets created with the new amount
- `env_var` resolves to the NEW price ID
- After `--write-env`, your checkout flow points at the new price

This is the correct + safe pattern for SaaS pricing changes.

## What the YAML looks like

```yaml
mode: test

products:
  - sku: pro
    name: "Acme Pro"
    description: "Pro tier subscription"
    prices:
      - env_var: STRIPE_PRICE_PRO_MONTHLY
        unit_amount_cents: 2500
        currency: usd
        recurring:
          interval: month
          interval_count: 1
      - env_var: STRIPE_PRICE_PRO_ANNUAL
        unit_amount_cents: 25000
        currency: usd
        recurring:
          interval: year
          interval_count: 1

  - sku: course_x
    name: "Course X"
    description: "One-time digital product"
    prices:
      - env_var: STRIPE_PRICE_COURSE_X
        unit_amount_cents: 49700
        currency: usd
        # No `recurring:` block = one-time price
```

See [`stripe_products.yaml`](./stripe_products.yaml) for the full example.

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with audit + scheduling + team approval
