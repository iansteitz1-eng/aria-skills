---
name: cloudflare-dns-deploy
description: Reconcile DNS records from a declared YAML catalog to Cloudflare via the API, and optionally run the companion nginx + certbot bootstrap for records pointing at your server. Idempotent. --dry-run by default, --apply hits the API, --server-setup also wires nginx + obtains Let's Encrypt cert. Use when the user says "deploy DNS", "add a subdomain", "stand up <X>.example.com", or before any subdomain launch.
---

# cloudflare-dns-deploy

YAML → Cloudflare DNS → nginx → certbot, in one command.

## When to use

- New subdomain launches (replaces dashboard click + SSH + nginx + certbot dance)
- DNS audits (`--dry-run` shows drift between YAML and live)
- Multi-zone management (one YAML covers all your zones)
- Pruning stale records (`--prune` deletes A/AAAA/CNAME/TXT/MX not in YAML)

## How it works

1. Reads `dns_records.yaml`
2. For each zone, lists current Cloudflare records
3. For each declared record: matches by (zone, type, name). Creates if absent; patches if drift in content/TTL/proxied.
4. With `--server-setup`: waits for DNS propagation, enables nginx site, runs certbot, verifies HTTPS.

## Env vars required

| Var | Required for | Notes |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | all | Scoped Token (Zone:Read + DNS:Edit on target zones) |

Token creation: `dash.cloudflare.com` → My Profile → API Tokens → Create Token → "Edit zone DNS" template.

## Safety

- **Default is dry-run.** No API write until `--apply`.
- **Doesn't delete by default.** `--prune` is the explicit opt-in to remove records.
- **Server-setup is opt-in.** Default `--apply` only touches Cloudflare; you don't accidentally invoke certbot.
- **Cert renewal stays under certbot.timer** — this skill issues; renewal is automatic via the system service.

## Hosted version

[Vox Ordo](https://voxordo.io) runs this with:
- Multi-zone team management
- Scheduled drift checks (alerts on manual dashboard changes)
- Approval workflow for `--prune` and `--server-setup`
- Free tier · BYOK · no credit card

## License

Apache 2.0
