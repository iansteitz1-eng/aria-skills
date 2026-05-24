# cloudflare-dns-deploy

> **YAML → Cloudflare DNS + nginx + Let's Encrypt. One command.**

Stand up a new subdomain (DNS record · server config · HTTPS cert) without leaving your terminal. Your DNS catalog lives in `dns_records.yaml`; this skill reconciles it to Cloudflare AND optionally runs the companion nginx + certbot bootstrap.

```sh
# Manual:
# 1. Cloudflare dashboard: Add A record (~2 min)
# 2. Wait for DNS propagation (~1-30 min)
# 3. SSH to server, ln -s nginx site, nginx -t, systemctl reload nginx
# 4. certbot --nginx -d ...

# This skill:
python3 cloudflare_dns.py --apply --server-setup
```

## 30-second install

```sh
pip install -r requirements.txt

# Get a scoped token from dash.cloudflare.com → My Profile → API Tokens
# → Create Token → "Edit zone DNS" template → Include specific zone
echo "CLOUDFLARE_API_TOKEN=cf_..." > .env

# Edit dns_records.yaml to declare your records
python3 cloudflare_dns.py             # dry-run
python3 cloudflare_dns.py --apply     # creates DNS records
python3 cloudflare_dns.py --apply --server-setup  # also wires nginx + certbot
```

## What's in the YAML

```yaml
server_ip: 50.28.69.120          # your server's public IP
certbot_email: ops@example.com   # for Let's Encrypt registration

zones:
  - zone: example.com
    records:
      - type: A
        name: downloads
        point_at: this_server     # resolves to server_ip above
        proxied: false            # grey-cloud (required for HTTP-01 ACME)
        server_setup:
          # Optional — runs nginx + certbot bootstrap for this record
          nginx_site: /etc/nginx/sites-available/downloads.example.com
          enable_https: true
```

## What `--server-setup` actually does

After the DNS A record is created, the skill:
1. Waits up to `--wait-dns N` seconds for the record to propagate
2. Verifies DNS resolves to your server IP
3. `ln -s` the staged nginx site config into `sites-enabled`
4. Runs `nginx -t` then `systemctl reload nginx`
5. Runs `certbot --nginx -d <domain> --redirect`
6. Verifies HTTPS endpoint returns 200

Fails fast at any step with a useful error message.

## Idempotent re-runs

- Existing DNS records: matched by (zone, type, name). Drift in content/TTL/proxied gets patched in place.
- `--prune` flag: delete CF records not in YAML (A/AAAA/CNAME/TXT/MX only — never deletes NS or other critical record types).
- nginx + certbot steps skip if cert already exists + nginx config already enabled.

## Common gotcha: nameserver migration

If you just moved a domain from another DNS provider to Cloudflare, **both NS sets may be returned by resolvers during the transition** (cached delegation expiring). Let's Encrypt's resolver may hit the OLD NS and get NXDOMAIN.

Two fixes:
- **Add the same record at the old DNS provider** during the transition (24-48h)
- **Wait** for the registry NS to fully propagate

This skill emits a clear error message when certbot fails for DNS-resolution reasons + tells you which NS responded.

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with team approval + cert renewal scheduling

## License

Apache 2.0
