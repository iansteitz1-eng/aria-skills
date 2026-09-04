# Social launch drafts — `iansteitz1-eng/aria-skills`

Hold these until the GitHub repo is actually public + the `/skills/` landing page is reachable. Then post manually from Ian's accounts. Don't auto-fire.

---

## 🐦 Twitter / X thread (8 tweets)

### Tweet 1 (hook)
```
I automated everything I used to do in Stripe / Cloudflare / ElevenLabs dashboards.

Open-sourcing the pattern as Claude Code Skills.

3 skills shipping today, more on the way:
github.com/iansteitz1-eng/aria-skills

🧵 how they work + why this is the right shape for agentic AI ↓
```

### Tweet 2 (the pain)
```
Pain shape:

▪️ Stripe dashboard: 45 min creating 10 products + 15 prices manually
▪️ Cloudflare + nginx + certbot: 30 min for one new subdomain
▪️ EL ConvAI: dashboard click-fest every time an agent config changes

Multiply by 50× a year. That's a week of clicking I'll never get back.
```

### Tweet 3 (the shape)
```
The fix isn't "more dashboards." It's the Terraform / Pulumi model applied to *every external service*:

  1. YAML is canonical (your intent in version control)
  2. Reconcile loop (script compares YAML to live state)
  3. Idempotent (re-run = no diff = no writes)
  4. --dry-run by default
  5. --prod for live mode
```

### Tweet 4 (stripe-sync demo)
```
Example — stripe-sync.

```yaml
products:
  - sku: pro
    name: "Acme Pro"
    prices:
      - env_var: STRIPE_PRICE_PRO_MONTHLY
        unit_amount_cents: 2500
        recurring: { interval: month }
```

```sh
python3 stripe_sync.py --apply --prod --write-env
```

Done. Live. 5 seconds.
```

### Tweet 5 (cloudflare-dns demo)
```
cloudflare-dns-deploy goes one step further: it also runs the nginx + certbot bootstrap.

New subdomain → DNS record → HTTPS cert → live behind nginx → all in one command.

The pre-launch ceremony for downloads.voxordo.io tonight: ~2 minutes.
```

### Tweet 6 (the safety bit)
```
Embedded patterns I cared about:

▪️ --prod required for live mode (belt + braces)
▪️ Triple-gated live payments (--apply + --prod + --confirm-amount must match)
▪️ deploy_gate field per agent (voice-lane sign-off)
▪️ Idempotency via metadata.aria_sku, not name (declared intent is source of truth)

These aren't theoretical. They ship today.
```

### Tweet 7 (the why)
```
Why open-source: skills are commodity. The *hosted version* — where Aria runs these on your behalf with team approval, audit chain, scheduled runs — is the product.

Solo: clone, run, it is yours.
Hosted: voxordo.io, BYOK.
```

### Tweet 8 (CTA)
```
Repo: github.com/iansteitz1-eng/aria-skills
Docs + landing: downloads.voxordo.io/skills
Hosted: voxordo.io

Built and dogfooded by @InSync_Tech. Star if useful — that's how we find each other in this space.

(More skills shipping next 2 weeks. PRs welcome for vendors we missed.)
```

---

## 📰 Hacker News post

### Title (60 char limit, optimize for click-through)

Pick ONE:
1. `Show HN: Aria Skills – Claude Code skills replacing dashboard work`
2. `Show HN: YAML-driven CLI for Stripe/Cloudflare/ElevenLabs ops`
3. `Show HN: aria-skills – open-source Claude Code skills`

Best is #1 — leads with the platform tag (HN crowd skews technical-aware) + the value prop (replace dashboards).

### Body

```
Hi HN,

I built a small collection of Claude Code Skills that replace dashboard work I was doing 50 times a year:

- stripe-sync: declares products + prices in YAML, reconciles to Stripe via API. Idempotent. Replaces ~45 min of dashboard clicking per pricing change.

- cloudflare-dns-deploy: YAML → Cloudflare DNS → nginx → certbot in one command. New subdomain live behind HTTPS in ~2 min.

- el-agent-deploy: declarative ElevenLabs ConvAI agent config (tool attachments, system-prompt blocks, Twilio phone binding).

The pattern is the same shape Terraform / Pulumi use for cloud infra — declared-intent YAML, reconcile loop, idempotent re-runs, --dry-run by default, explicit --prod for live mode. The novelty is packaging it as Claude Skills so an LLM can drive it on your behalf.

Repo: https://github.com/iansteitz1-eng/aria-skills

A few safety patterns I'd be curious for feedback on:

1. --apply + --prod two-flag opt-in for live mode (one flag is too easy to fat-finger)
2. Triple-gated live payments (--apply + --prod + --confirm-amount must match) for vendor-billing-action (shipping soon)
3. Idempotency by metadata key, not display name — so manual dashboard creates don't accidentally collide
4. deploy_gate field per agent — voice-lane sign-off requirement we use internally
5. Hash-chained audit log (in the hosted version) — every state change splat-logged

I open-sourced these because the skills are the commodity. The hosted version (https://voxordo.io) is the actual product — team approval, scheduled runs, audit, multi-user. Free tier exists; no credit card.

Apache 2.0. PRs welcome — especially for vendors not yet covered (Linear, Notion, GitHub, Vercel, Render, Fly.io, etc.).

Happy to answer questions, especially about the safety-pattern choices.
```

---

## 📝 Reddit r/ClaudeAI post (similar but more casual)

### Title
`Open-sourced 3 Claude Code Skills that replaced my Stripe/Cloudflare/ElevenLabs dashboard time`

### Body (skip the formal HN tone)
```
Built these for my own use over the last few weeks, just open-sourced them tonight.

Each one replaces ~15-45 min of dashboard clicking with a one-command CLI flow:

▪️ stripe-sync — YAML → Stripe products + prices, idempotent
▪️ cloudflare-dns-deploy — YAML → Cloudflare DNS + nginx + certbot
▪️ el-agent-deploy — YAML → ElevenLabs ConvAI agents (tools + system prompts + phone bindings)

Same pattern across all three: declared-intent YAML, reconcile loop, --dry-run default, --prod for live.

Repo: github.com/iansteitz1-eng/aria-skills (Apache 2.0)
Landing: downloads.voxordo.io/skills

If you've been clicking through these dashboards too — try the skills, lmk what breaks.

(Disclosure: I run voxordo.io — these skills are open source separately; the hosted platform is where they get team approval / audit / scheduling, but solo use is fine forever.)
```

---

## 📝 Suggested posting cadence

1. **Day 0** (tonight): GitHub repo public, /skills/ landing page live
2. **Day 1** (tomorrow): Twitter thread (morning, ~9-10am ET when dev Twitter wakes up)
3. **Day 1** (tomorrow): Reddit r/ClaudeAI + r/LocalLLaMA (afternoon, after Twitter has 12-24h of visibility)
4. **Day 2** (next day): Hacker News Show HN (best window: weekday 8-10am ET; avoid Friday/weekend)
5. **Day 3**: post in `awesome-claude-code` lists via PR

Each post links back to the GitHub repo. The GitHub repo's README links to `voxordo.io`. The funnel runs itself.

---

## ⚠️ Before posting

1. Verify GitHub repo is public + has at least the README + 3 skill directories visible
2. Verify `downloads.voxordo.io/skills/` resolves (already confirmed 200)
3. Verify `voxordo.io` is the right destination URL for the CTAs (it is)
4. Sanity-check one skill's `--dry-run` runs cleanly from a fresh clone

These four checks take 5 minutes total + prevent the "post got 100 upvotes but the link 404s" disaster.
