# Builder Guide

> **How we build Claude Code Skills at InsyncTech.** Patterns, conventions, anti-patterns, and the reasoning underneath each.

This is the canonical reference. If you're contributing to `aria-skills` (or building your own skills off our pattern), start here.

---

## TL;DR — the six patterns

1. **YAML is canonical.** Your declared intent lives in version control; the vendor's state should match.
2. **Reconcile loops, not imperative scripts.** Read YAML → diff against live → only change what differs.
3. **Idempotent by metadata, not name.** Match existing resources by a metadata key you control; display names drift, metadata doesn't.
4. **`--dry-run` is the default; `--apply` is the explicit opt-in.** Never surprise the user.
5. **Two-flag prod gate for live mode; triple-gate for irreversible.** `--apply` + `--prod` minimum; `--confirm-amount` matching for money moves.
6. **Audit-via-splat.** Every state change emits a structured log entry that's verifiable post-hoc.

Each is detailed below with examples from skills currently in the repo.

---

## 1. The SKILL.md format

Every skill in this repo has a `SKILL.md` at its root. Claude Code reads this file's frontmatter on startup and auto-registers the skill in the available-skills list.

### Minimum viable SKILL.md

```yaml
---
name: my-skill
description: One-line trigger description. Claude uses this to decide when to invoke the skill. Be specific about what the skill replaces or enables — vague descriptions get ignored.
---

# my-skill

Body content — usage examples, env vars, safety notes, etc. This part is markdown; Claude reads it when the skill is invoked.
```

### Frontmatter rules

| Field | Required | What it does |
|---|---|---|
| `name` | yes | Slug used in Claude Code's `Skill` tool call. Must match directory name. Lowercase, hyphen-separated. |
| `description` | yes | First-line hook Claude uses to decide *whether* to invoke. Lead with the trigger ("Use when…") + the value prop. ~100-200 characters. |

### What goes in the description (where 90% of skills fail)

❌ **Bad:** `Manages Stripe stuff.`
❌ **Bad:** `A skill for Stripe operations.`
✅ **Good:** `Reconcile the Stripe product + price catalog from /opt/aria/config/stripe_products.yaml to the live Stripe account. Idempotent, --dry-run by default. Use when the user says "sync stripe", "create stripe prices", or before any pricing change ships.`

The description is a trigger signal. List the explicit phrases that should invoke the skill. Claude reads thousands of descriptions; specificity wins.

---

## 2. The YAML-reconcile pattern

The shape every reconcile skill in this repo follows:

```
┌────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ YAML config    │────▶│ Reconcile loop   │────▶│ Vendor API      │
│ (your intent)  │     │ - list current   │     │ (Stripe, CF,    │
│                │     │ - compute diff   │     │  EL, etc.)      │
│                │◀────│ - apply changes  │◀────│                 │
└────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Audit log (splat)│
                       └──────────────────┘
```

### Why YAML, not JSON or TOML?

- **Comments survive.** Stripe SKU explanations, deferred-decision notes, links to related issues — these belong in the config and YAML respects them.
- **Multi-line strings.** Email templates, system prompts, descriptions — all live well in YAML's `|` block syntax.
- **Diff-friendly.** YAML diffs read cleanly in PRs.

### Why declared intent, not procedural?

Procedural ("step 1: create product; step 2: create price; step 3: ..."):
- Breaks on re-run (duplicate products)
- Doesn't capture *what should exist*; only *what was done*
- Hard to audit ("did we ever set the annual price?")

Declared intent ("these 9 products + 11 prices SHOULD exist"):
- Re-runnable; matches what's there, creates what's missing
- Captures the desired state in version control
- Audit trivial ("what should exist vs. what does exist")

### Match key choice (the load-bearing decision)

When the script asks "does this product already exist?" — how does it know?

**Anti-pattern:** match by display name.
```python
# DON'T:
for p in stripe.Product.list():
    if p.name == "Pro Plan":
        return p.id
```
Name drift in the dashboard breaks this. Rename → ghost product → duplicate created.

**Pattern:** match by metadata key you control.
```python
# DO:
for p in stripe.Product.list():
    if (p.metadata or {}).get('aria_sku') == 'pro':
        return p.id
```
Even if someone renames "Pro Plan" → "Pro Tier" in the dashboard, the `aria_sku: pro` metadata is your stable anchor.

**Every reconcile skill in this repo uses a metadata key.** Pick yours up front. Hard to retrofit later.

---

## 3. The dry-run-first contract

Every skill ships with these CLI flags:

```sh
my_skill.py                          # dry-run (default)
my_skill.py --apply                  # apply against test mode (where applicable)
my_skill.py --apply --prod           # apply against live API
my_skill.py --apply --prod --write-env   # also merge IDs into .env
```

### Why dry-run by default

- **You see the diff before any API write.** Mistakes happen at YAML time, not API time.
- **No flag = no production effect.** Safe to invoke from Claude Code or shell history.
- **Forces user to opt in explicitly.** Reduces "I didn't mean to apply that" incidents to ~zero.

### Implementation

```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Apply changes (default = dry-run)")
    ap.add_argument("--prod", action="store_true",
                    help="Allow live mode (required if YAML mode=live)")
    args = ap.parse_args()
    
    if cfg_mode == "live" and not args.prod:
        sys.stderr.write("FATAL: YAML mode=live requires --prod flag.\n")
        sys.exit(2)
```

---

## 4. The two-flag prod gate

For any skill that can write to a live external account, `--apply` is necessary but not sufficient. Live mode requires `--apply` + `--prod` both.

### Why two flags?

`--apply` is the user saying "do the thing." `--prod` is the user saying "do the LIVE thing." One flag is too easy to fat-finger; two flags forces deliberation.

### The mode-mismatch guard

```yaml
# YAML header:
mode: test
```

```python
# In the skill:
if cfg_mode == "live" and not args.prod:
    fail("YAML says live; CLI must pass --prod")
if cfg_mode == "test" and key.startswith("sk_live_"):
    fail("Live key but test mode requested")
if cfg_mode == "live" and key.startswith("sk_test_"):
    fail("Test key but live mode requested")
```

Belt + braces. Refuse to use the wrong credential for the declared mode.

---

## 5. Triple-gating for irreversible actions

Money moves. Production data deletions. Sending real emails to real customers. These can't be un-done.

For these, two flags isn't enough. We add a **third gate that must match a derived value:**

```sh
vendor_billing.py pay --vendor liquidweb \
  --amount 250.00 \
  --confirm-amount 250.00 \
  --apply --prod
```

If `--amount` and `--confirm-amount` don't match exactly, the skill refuses.

### Why this works

A fat-fingered `--amount 2500.00` (extra zero) gets caught because the user has to type it twice. The friction is the point. Money can't be un-moved.

### When to triple-gate

- ✅ Real money moves (vendor payments, refunds, payouts)
- ✅ Account deletions (Stripe customer, GitHub repo, DNS zones)
- ✅ Bulk destructive operations (delete 100 records)
- ❌ Creating resources (these are reversible — just archive/delete after)
- ❌ Updating non-destructive fields (re-runnable)

---

## 6. Audit-via-splat

Every state-changing skill emits a structured log entry — a "splat" — that the hosted version writes to a hash-chained audit table.

### Splat schema (the abstract shape)

```
splat_id      = generated UUID
created_at    = now()
layer         = "stripe_sync_run" / "el_agent_deploy_run" / etc.
harness_source = name of the skill that emitted
pre_state_hash = hash of state BEFORE the change
post_state_hash = hash of state AFTER the change
payload       = JSONB with the diff + metadata
```

### In standalone (open-source) skills

The `_emit_splat()` function in each script is a **no-op**:

```python
def _emit_splat(*args, **kwargs):
    """No-op in standalone mode. Vox Ordo hosted version logs to CertusOrdo splat chain."""
    pass
```

Skills work fine without the audit chain. The hosted version layers it on top.

### In Vox Ordo hosted

Splat emits to `v4_splat_log` (Postgres). Hash-chained — each new splat's `pre_state_hash` must equal the previous splat's `post_state_hash`. Tamper-evident. Full chain verifiable post-hoc.

Why this matters for alignment: every action an AI agent takes through the skills layer is recorded in a way you can verify wasn't tampered with. Practical AI safety primitive.

---

## 7. Per-vendor adapter pattern

When a skill talks to multiple vendor APIs (e.g. `vendor-billing-action` handles Liquid Web + future vendors), each vendor lives in an **adapter module**:

```python
def _adapter_liquid_web_pay(amount):
    """Live payment through LW API."""
    ...

def _adapter_generic_pay(amount):
    """No-op — generic vendors don't have live API."""
    return {"ok": False, "error": "no live adapter for generic vendor"}
```

Then dispatch by vendor's declared `adapter:` field in YAML:

```yaml
vendors:
  - id: my_host
    adapter: liquid_web      # routes to _adapter_liquid_web_*
  - id: my_email_svc
    adapter: generic         # routes to _adapter_generic_*
```

### Why adapters, not if/else trees

- New vendors plug in by writing one adapter module
- Each adapter is independently testable
- Generic adapter is a safe default for vendors without live APIs

### Anti-pattern: subclassing

Don't `class LiquidWebAdapter(VendorAdapter): ...`. Plain functions named `_adapter_<vendor>_<action>` are simpler, more discoverable, easier to read. We're not building a framework; we're building a skill.

---

## 8. The hosted-version differentiator

The skills are open-source. The hosted version (Vox Ordo at `voxordo.io`) is the SaaS. What separates them:

| | Solo (this repo) | Hosted (Vox Ordo) |
|---|---|---|
| Run skills | manual, your machine | scheduled, multi-user |
| State | your `.env` + local files | server-side, per-user-scoped |
| Audit | local splat (no-op) | hash-chained v4_splat_log |
| Approval workflow | none | team-approval gates for triple-gated actions |
| Cost | none beyond your own machine | BYOK + monthly subscription |
| Setup | clone + pip install | sign up + go |

The skills here work fully standalone. The hosted version is "you don't have to maintain it yourself."

**Don't break the standalone experience.** Anyone should be able to clone this repo + run a skill in 60 seconds.

---

## 9. Anti-patterns we've burned ourselves on

### Anti-pattern: hard-coded paths
```python
# DON'T:
ENV_FILE = "/opt/aria/.env"
CONFIG = "/opt/aria/config/stripe_products.yaml"
```
Hard-coded paths break open-source distribution. Use relative paths or environment-variable-driven paths.

### Anti-pattern: hard-coded human names
```python
# DON'T:
DEFAULT_OWNER = "Ian Steitz"
PRIMARY_USER = "ian@insynctech.io"
```
Standing rule: identity is `user_email` from session or env, never hard-coded. Even in YAML examples, use placeholder strings (`founder@example.com`).

### Anti-pattern: matching resources by display name
See section 3. Use metadata keys.

### Anti-pattern: silent failures on apply
```python
# DON'T:
try:
    stripe.Product.create(...)
except Exception:
    pass  # silently swallow
```
If `--apply` fails, the user MUST see why. Fail loudly. Exit non-zero.

### Anti-pattern: in-place price modification
```python
# DON'T:
stripe.Price.modify(price_id, unit_amount=new_amount)  # WILL FAIL
```
Stripe prices are immutable. Create new, archive old. Same logic applies to many vendor APIs (Anthropic API keys, Cloudflare records, etc.).

### Anti-pattern: auto-deletion
Never delete by default. Pruning requires explicit `--prune` opt-in. Even then, only prune the safe resource types (A/AAAA/CNAME/TXT/MX records; NEVER NS, MX delegations, root records without a sub-flag).

---

## 10. Naming conventions

### Skill names
- Lowercase, hyphen-separated
- Verb-noun or noun-verb (action implied): `stripe-sync`, `cloudflare-dns-deploy`, `vendor-billing-action`
- Avoid generic words ("manager", "helper", "tool", "system") — they describe nothing

### Script names (inside skill directories)
- snake_case Python: `stripe_sync.py`, `cloudflare_dns.py`
- Matches the SKILL.md name but with underscores instead of hyphens

### YAML config files
- snake_case + descriptive: `stripe_products.yaml`, `dns_records.yaml`, `el_agents.yaml`
- Each skill has one canonical config file; multi-config support is over-engineering for v1

### Env vars
- UPPER_SNAKE_CASE
- Vendor-prefixed: `STRIPE_SECRET_KEY`, `CLOUDFLARE_API_TOKEN`, `ELEVENLABS_API_KEY`
- For test/live separation: `_TEST` / `_LIVE` suffixes — `STRIPE_SECRET_KEY_TEST` / `STRIPE_SECRET_KEY_LIVE`

---

## 11. Directory structure (canonical)

Every skill in the repo follows this shape:

```
my-skill/
├── README.md                  ← user-facing docs (full)
├── SKILL.md                   ← Claude Code manifest (frontmatter + short body)
├── my_skill.py                ← main script
├── my_skill_config.yaml       ← config template (if applicable)
├── requirements.txt           ← Python deps
└── tests/                     ← (optional) pytest fixtures
    └── test_my_skill.py
```

- **README.md** is what GitHub renders. Should answer: "what does this do, how do I install, how do I use, what's the safety model."
- **SKILL.md** is what Claude Code reads. Should be tighter; description in frontmatter is the trigger signal.
- **my_skill.py** has a top docstring + argparse + a `_emit_splat` no-op + the reconcile logic.
- **my_skill_config.yaml** is the user's intent declaration. Ship a template with comments; users copy to `local.yaml` or edit in place.

---

## 12. Testing

### Smoke test (manual, per skill)
```sh
python3 my_skill.py             # dry-run — should report what would happen
python3 my_skill.py --apply     # test mode — should actually run against test API
```

### Skill-test harness (programmatic, all skills)
```sh
aria-skill-test                 # runs dry-run on every shipped skill, reports clean/dirty
aria-skill-test --skill my-skill   # target one
aria-skill-test --junit-xml=out.xml   # CI integration
```

See `aria-skill-test/` for the harness. Every shipped skill should pass `aria-skill-test`.

### End-to-end smoke (before any public push)
1. Fresh clone in `/tmp/`
2. `pip install -r requirements.txt`
3. `python3 my_skill.py` (dry-run)
4. Expect clean output, no traceback, no auth-token leak in stderr

---

## 13. Contributing flow

1. Pick or open a GitHub Issue describing the gap
2. `aria-skill-template my-new-skill` (uses our template generator)
3. Edit the generated stubs (script + YAML + README + SKILL.md)
4. `aria-skill-test --skill my-new-skill` until clean
5. Open PR against `iansteitz1-eng/aria-skills` (or `InsyncTech/aria-skills` post-transfer)
6. CI runs `aria-skill-test --all`; PR auto-labelled green/red
7. Reviewer checks: SKILL.md description quality · safety patterns honored · README is reader-friendly

PRs welcome. Especially: new vendor skills (Linear, Notion, GitHub orgs, Vercel, Render, Fly.io, Cloudflare Workers, Twilio, etc.).

---

## 14. Where this guide lives

- **In the repo:** `BUILDER_GUIDE.md` at the root (this file)
- **On the marketing site:** Linked from [downloads.voxordo.io/skills/](https://downloads.voxordo.io/skills/) "Read the guide"
- **In Claude Code:** Mentioned by the `aria-skill-template` skill's SKILL.md (so Claude reads it before scaffolding a new skill)

If you find a pattern that should be in this guide but isn't, open an issue or PR. The guide is alive.

---

## License

This guide is Apache 2.0, same as the rest of the repo. Quote, fork, remix freely.
