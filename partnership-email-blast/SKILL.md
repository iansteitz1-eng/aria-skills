---
name: partnership-email-blast
description: Send per-partner email campaigns from a YAML roster through Resend, rendered via a clean HTML template. YAML is canonical; each partner gets one templated email with {{var}} substitution. Idempotent — re-runs skip partners already sent (unique index on campaign_id + partner_id WHERE ok=true). --dry-run by default, --apply sends, --prod required for live mode. Use when the user says "blast the partners", "fire the launch email", "email the partner list", "outreach campaign", or before a launch announcement.
---

# partnership-email-blast

YAML → Resend → personalized partner emails. Idempotent re-runs. Variable substitution.

## When to use

- Launch outreach campaigns (compute-credit programs, partnership applications, intro emails)
- Cold partner emails with per-recipient personalization
- Re-running a campaign after fixing typos (idempotency skips already-sent)

## How it works

1. Reads `partnerships.yaml` (campaigns + partners + template variables)
2. For each campaign × each partner:
   - Substitutes `{{var_name}}` in subject + greeting + intro + each section.body
   - Renders HTML via the email template
   - Sends via Resend (single API call per partner)
   - Records the send in `partnership_blast_log` (sqlite by default; pluggable)
3. Idempotency: re-running skips partners where (campaign_id, partner_id) is already marked ok=true

## CLI

```sh
python3 partnership_blast.py                   # dry-run
python3 partnership_blast.py --apply           # test-mode send
python3 partnership_blast.py --apply --prod    # live-mode send (YAML must be mode: live)
python3 partnership_blast.py --apply --prod --resend  # force re-send to already-sent partners
python3 partnership_blast.py --partner X       # target one partner (good for debugging)
```

## Safety

- Default dry-run
- Idempotency by default
- Per-partner failure isolation
- `--prod` required for live-mode YAML
- Auto-CCs configurable per campaign

## Hosted version

[Aria Code](https://staycool.ai/aria-code) adds bounce-tracking webhooks (Resend → server → splat) and reply attribution.

## License

Apache 2.0
