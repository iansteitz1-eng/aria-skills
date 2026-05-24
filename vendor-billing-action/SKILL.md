---
name: vendor-billing-action
description: Unified vendor billing surface — sync a YAML vendor roster, snapshot status, list upcoming renewals, record manual payments, and (for vendors with an adapter) fetch live balance or trigger a live payment. TRIPLE-GATED on live payments (--apply AND --prod AND --confirm-amount must match) because money cannot be un-moved. Use when the user says "vendor status", "what bills are coming up", "record that I paid X", "pay X", "renewal check", or "vendor sync".
---

# vendor-billing-action

YAML → vendor roster → renewal alerts → payments (manual or adapter-driven, with triple-gated safety on live moves).

## When to use

- Tracking all your vendor bills in one place (replaces spreadsheet)
- Renewal reminders (cron the `next-due` subcommand)
- Logging manual payments for audit
- Live payments via vendor APIs (with three-flag safety gate)

## Subcommands

```sh
python3 vendor_billing.py sync                            # YAML → local ledger
python3 vendor_billing.py status                          # snapshot
python3 vendor_billing.py next-due                        # upcoming renewals
python3 vendor_billing.py record-payment --vendor X --amount Y --ref Z --apply
python3 vendor_billing.py fetch-balance --vendor X        # adapter call
python3 vendor_billing.py pay --vendor X --amount Y --confirm-amount Y --apply --prod
                                                          # ↑ TRIPLE-GATED
```

## Triple-gating

`pay` requires:
1. `--apply`
2. `--prod`
3. `--confirm-amount` matching `--amount`

Friction by design. Money can't be un-moved.

## Adapter pattern

- `generic` — record-only
- `liquid_web` — live API
- (PRs welcome for more)

## Hosted version

[Aria Code](https://staycool.ai/aria-code) layers approval workflow + scheduled renewals + audit chain.

## License

Apache 2.0
