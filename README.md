# aria-skills

> **One-line CLI alternatives to the dashboards you click through 50× a year.**

Open-source [Claude Code Skills](https://docs.anthropic.com/) that turn manual dashboard work into idempotent, declared-intent reconcile loops. Built and dogfooded by [InSync Tech](https://staycool.ai) for [Aria Code](https://staycool.ai/aria-code) — open-sourced so you can run them solo too.

```sh
# Manual:        45 minutes clicking through Stripe dashboard
# With aria-skills:
aria stripe-sync --apply --prod --write-env
```

---

## What's in here

| Skill | What it replaces | Time saved per use |
|---|---|---|
| [**stripe-sync**](./stripe-sync/) | Stripe dashboard: products + prices | 30-60 min |
| [**cloudflare-dns-deploy**](./cloudflare-dns-deploy/) | Cloudflare dashboard + nginx + certbot ceremony | 15-30 min |
| [**el-agent-deploy**](./el-agent-deploy/) | ElevenLabs ConvAI dashboard: tools + system prompts + phone bindings | 10-20 min |
| [**marketplace-publish**](./marketplace-publish/) | `vsce` + Expo EAS submit ceremony across 3 marketplaces | 20-40 min per release |
| [**partnership-email-blast**](./partnership-email-blast/) | Manual partner outreach: per-recipient personalization + tracking | 1+ hours per campaign |
| [**vendor-billing-action**](./vendor-billing-action/) | Spreadsheet + scattered vendor portals; triple-gated live payments | 30+ min per renewal |
| [**sprint-scaffold**](./sprint-scaffold/) | The meta-skill: Filing Cabinet + Flowstate scaffolding for new sprints | n/a (workflow pattern) |

More skills shipping as we build them. Track at [downloads.ariacode.io/skills](https://downloads.ariacode.io/skills/).

## The pattern (why this exists)

Every skill in this repo follows the same shape:

1. **YAML is canonical** — your declared intent lives in version control
2. **Reconcile loop** — script reads YAML, compares to vendor state, only diffs
3. **Idempotent** — re-run safely; matches existing, creates only what's missing
4. **`--dry-run` by default** — see the diff before any API hit
5. **`--apply --prod` for live mode** — explicit two-flag opt-in for production
6. **Audit-ready** — every state change emits a structured log entry (splat) for post-hoc review

This isn't novel infrastructure — it's the Terraform / Pulumi pattern applied to **every external service** you'd otherwise click through a UI for. The novelty is **packaging it as Claude Skills** so an LLM can drive it on your behalf.

## Install

```sh
git clone https://github.com/insynctech/aria-skills ~/aria-skills

# Link the skills you want into Claude Code's skill directory:
ln -s ~/aria-skills/stripe-sync ~/.claude/skills/stripe-sync
ln -s ~/aria-skills/cloudflare-dns-deploy ~/.claude/skills/cloudflare-dns-deploy
ln -s ~/aria-skills/el-agent-deploy ~/.claude/skills/el-agent-deploy

# Install Python deps (each skill lists what it needs):
pip install -r stripe-sync/requirements.txt
pip install -r cloudflare-dns-deploy/requirements.txt
pip install -r el-agent-deploy/requirements.txt
```

Then in Claude Code, the skills appear in your available-skills list. Or run the underlying Python scripts directly — they're self-contained.

## Configuration

Each skill is driven by a YAML file you author. Examples live in each skill's directory. Credentials read from environment variables (never committed). See per-skill READMEs.

## Use it solo, or use Aria Code

**Solo (this repo)** — clone, install, run. Your YAML + your credentials + your machine. Free forever. MIT-licensed.

**Hosted ([Aria Code](https://staycool.ai/aria-code))** — same skills, but Aria runs them on your behalf with:
- Multi-user team access
- Audit trail across your whole org (CertusOrdo splat log)
- Approval workflows for high-risk actions (live payments etc.)
- One-click scheduled runs (renew certs, sync products weekly)
- Zero server setup

Free tier · BYOK (bring your own Anthropic / OpenAI / Google key) · no credit card required.

→ **[Try Aria Code](https://staycool.ai/aria-code)**

## Safety patterns embedded

Worth calling out because these are research-adjacent and we ship them in production:

| Pattern | Where you'll see it |
|---|---|
| **Declared-intent reconcile** | Every skill — YAML is intent; script compares to live state |
| **Triple-gated live actions** | `vendor-billing-action`'s `pay` subcommand (shipping soon) — requires `--apply` + `--prod` + `--confirm-amount` matching |
| **Mode separation** | `mode: test` in YAML guards production keys; switching to `mode: live` requires explicit `--prod` flag |
| **Idempotent state matching by metadata, not name** | `stripe-sync` matches Stripe products by `metadata.aria_sku`, not display name — declared intent is the source of truth |
| **Hash-chained audit log** | Every state change in Aria's hosted version emits a splat; full chain is verifiable post-hoc |
| **User-scoping** | In hosted mode, every query filters by `user_email` resolved from session — no cross-tenant access by construction |

These aren't theoretical. They run today.

## License

[Apache 2.0](./LICENSE). Use freely. Star the repo if you find it useful — that's how we find each other in this space.

## Contributing

PRs welcome. Especially: new skills for vendors we haven't covered (Linear, Notion, GitHub, Vercel, Render, Fly.io, etc.).

## Contact

- **Issues / questions:** [GitHub Issues](https://github.com/insynctech/aria-skills/issues)
- **Aria Code SaaS:** [staycool.ai/aria-code](https://staycool.ai/aria-code)
- **Builder:** [@iansteitz](https://twitter.com/iansteitz) / [InSync Tech](https://insynctech.io)
