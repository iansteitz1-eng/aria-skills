# partnership-email-blast

> **Per-partner email campaigns from YAML through Resend.** Idempotent. Rendered via a clean HTML template.

```sh
python3 partnership_blast.py --apply --prod
```

Stop manually copying email drafts into Gmail for each partner. Declare the campaign once; the skill sends one personalized email per partner and tracks idempotency so re-runs skip already-sent recipients.

## 30-second install

```sh
pip install -r requirements.txt
echo "RESEND_API_KEY=re_..." > .env   # from resend.com → API Keys

# Edit partnerships.yaml — one campaign with N partners
python3 partnership_blast.py             # dry-run, renders without sending
python3 partnership_blast.py --apply     # test-mode send
```

## What the YAML looks like

```yaml
mode: test

default_sender_from: "You · Your Company <hello@yourdomain.com>"
default_reply_to: "you@yourdomain.com"

campaigns:
  - id: launch_outreach_2026
    subject: "{{partner_name}} — quick intro"
    sender_from: "You · Your Company <hello@yourdomain.com>"
    reply_to: "you@yourdomain.com"
    greeting: "Hi {{partner_name}} team,"
    intro: |
      Quick introduction from us...
    sections:
      - emoji: "🎯"
        title: "What we do"
        body: |
          Per-partner pitch here. Use {{partner_name}} and other vars for personalization.
    partners:
      - id: partner_a
        contact_email: "team@partner-a.com"
        vars:
          partner_name: "Partner A"
      - id: partner_b
        contact_email: "hello@partner-b.com"
        vars:
          partner_name: "Partner B"
```

## Idempotent re-runs

Re-running skips partners already marked `ok=true` in the local log. Failed partners get retried automatically:

```
- partner_a <team@partner-a.com>: SKIP (already sent)
- partner_b <hello@partner-b.com>: SENT  resend_id=...
```

`--resend` flag bypasses idempotency and re-sends to ok=true partners (use when you want to re-send the same campaign to the same list).

## Domain verification

Resend requires the `default_sender_from` domain to be verified in your Resend account. Add a TXT record for SPF + DKIM via Cloudflare (or use `cloudflare-dns-deploy` skill from this repo).

## Safety

- **Default dry-run.** Renders + previews HTML without sending.
- **`--apply` opt-in for sending.** `--prod` required for live-mode YAML.
- **Idempotency by default.** Won't double-send a partner unless `--resend` is passed.
- **Per-partner failure isolation.** If one send fails (rate-limit, bounce, etc.), others continue.

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with bounce-tracking webhooks + reply-attribution

## License

Apache 2.0
