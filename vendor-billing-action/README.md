# vendor-billing-action

> **Vendor billing roster + renewal tracking + triple-gated live payments.**

Unified surface for your vendor billing operations. Track who you pay, when renewals are due, log manual payments, and (for vendors with an adapter) trigger live payments through a strict three-flag safety gate.

```sh
python3 vendor_billing.py status         # vendor table + last-action snapshot
python3 vendor_billing.py next-due       # upcoming renewals
python3 vendor_billing.py record-payment --vendor liquidweb --amount 250.00 --ref "stripe ch_xyz" --apply
python3 vendor_billing.py pay --vendor liquidweb --amount 250.00 --confirm-amount 250.00 --apply --prod
```

## 30-second install

```sh
pip install -r requirements.txt

# Edit vendors.yaml — your vendor roster
python3 vendor_billing.py sync           # mirror YAML into the local ledger
python3 vendor_billing.py status         # see current state
```

## Subcommands

| Subcommand | What it does |
|---|---|
| `sync` | Mirror `vendors.yaml` roster into the local `vendors` table |
| `status` | Print all vendors with state + last action |
| `next-due` | Show upcoming renewals (sortable, filterable) |
| `record-payment` | Log a manual payment to the local ledger |
| `fetch-balance` | Adapter call to vendor API (where supported) |
| `pay` | **TRIPLE-GATED live payment** through adapter |

## The triple-gate

`pay` is the only subcommand that can move real money. To execute, you must provide:

1. `--apply` flag (the standard live-mode opt-in)
2. `--prod` flag (the cross-mode-to-live confirmation)
3. `--confirm-amount X.XX` matching the `--amount X.XX` flag exactly

Why three? Because **money cannot be un-moved**. A typo here triggers a real ACH or card charge that's hard to reverse. Three flags is annoying by design — the friction is the point.

If any one of the three is missing or doesn't match, the skill prints what's wrong and exits with code 2. No payment fires.

## Adapter pattern

Each vendor has an `adapter` field in YAML:

- `generic` — record-only. Manual payments logged; no live API.
- `liquid_web` — live API integration (`api.liquidweb.com/bleed/billing/payment/submit`)
- `<your-vendor>` — write your own adapter; PRs welcome

To add a vendor without writing an adapter, set `adapter: generic`. You can still use `record-payment` for ledger tracking; you just can't `pay` via the script.

## Env vars (per-adapter)

| Adapter | Required env |
|---|---|
| `liquid_web` | `LIQUIDWEB_USERNAME`, `LIQUIDWEB_PASSWORD` |
| `generic` | (none — no live API) |

## Safety

- **Triple-gated live payments** (the only way money can move)
- **`record-payment` is opt-in via `--apply`** even though it's local-only
- **Adapter must be configured** before `pay` works — generic vendors refuse `pay`
- **Splat-logged in hosted version** for compliance

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with team approval workflow + scheduled renewals

## License

Apache 2.0
