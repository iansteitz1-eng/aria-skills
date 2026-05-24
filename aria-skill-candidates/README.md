# aria-skill-candidates

> **The Observer + Gatekeeper for the Aria Builders meta-loop.** Answers "what skill should I build next?" by watching what you keep doing manually.

```sh
python3 aria_skill_candidates.py --limit-files 20
# ════════════════════════════════════════════════════════════════════════
#   aria-skill-candidates  ·  scanned 20 transcript(s)
# ════════════════════════════════════════════════════════════════════════
#   RANKED CANDIDATES (no skill yet)
#   ─────────────────────────────────
#   BUILD NOW  score=11  linear     count=14  [R3 Y3 M3 P3 S0]
#   LOG PROBE  score= 8  twilio     count= 5  [R2 Y2 M3 P3 S0]
#   ...
```

## The problem

You keep `curl`ing the same vendor API from sessions and not noticing. Or you build a skill prematurely for a one-shot task. **Building isn't hard — gating is.**

## The 5-axis rubric

Each candidate scored 0-3 on:

| Axis | 0 = no | 3 = yes |
|---|---|---|
| **Recurrence** | One-shot | 10+ times across sessions |
| **YAML-shape** | Stateful/conversational | Clean declarative reconcile |
| **Multi-step** | Single command | 5+ manual steps |
| **Public-value** | Aria-internal only | Generalizes to any stack |
| **Sovereignty** | Free | Touches doctrine/splat/voice (subtracted) |

Final score = `R + Y + M + P − S`:
- **≥10** — `BUILD NOW`
- **5-9** — `LOG PROBE` (keep watching)
- **<5** — `SKIP`

## What it scans

Claude Code transcripts at `~/.claude/projects/<project>/*.jsonl`. Specifically: every `Bash` tool call, clustered by vendor domain (`api.linear.app`, `api.notion.com`, etc.).

## Vendor signature table

Currently recognizes: linear · notion · figma · airtable · openai · slack · github · vercel · posthog · intercom · hubspot · openphone · fly · cloudflare · stripe · elevenlabs · resend · twilio · anthropic.

Add more in `VENDOR_SIGNATURES` at the top of `aria_skill_candidates.py`.

## Existing-skill detection

Cross-references against `~/.claude/skills/*/SKILL.md`. Vendors covered by an existing skill are surfaced separately as a sanity check ("still being invoked → good") rather than as build candidates.

Explicit overrides in `VENDOR_TO_SKILL`:
- `resend` → `email-send`
- `stripe` → `stripe-sync`
- `cloudflare` → `cloudflare-dns-deploy`
- `elevenlabs` → `el-agent-deploy`
- `anthropic` → `None` (framework-level, never a skill)

## CLI

| Flag | Effect |
|---|---|
| `--limit-files N` | Scan only the N most recent transcripts |
| `--transcripts DIR` | Alternate transcript directory |
| `--skills-dir DIR` | Alternate skills directory |
| `--json` | Machine-readable output |

## Design

- **Read-only.** Never writes outside its own config.
- **Pure stdlib.** No external deps.
- **Idempotent.** Re-run any time; no state stored.
- **No telemetry sent anywhere** — your transcripts never leave the machine.

## When to run it

- Weekly, passively, to see what's accumulating
- After a marathon session ("what did I just do 12 times?")
- Before opening a new sprint ("what should be on the docket?")

## What it's NOT

- **Not a code generator** — it surfaces *what* to build, not *how*. Pair with [`aria-skill-template`](../aria-skill-template/) for that.
- **Not exhaustive** — only catches vendor-API patterns visible in `Bash` calls. Multi-step Python workflows, manual editor patterns, and pure shell flows are out of scope today.
- **Not a replacement for judgment** — score ≥10 says "consider it," not "build it." Sovereignty cost still requires human sign-off.

## See also

- **[BUILDER_GUIDE.md](../BUILDER_GUIDE.md)** — the patterns this rubric enforces
- **[aria-skill-template](../aria-skill-template/)** — scaffold the skill once you decide to build
- **[aria-skill-test](../aria-skill-test/)** — verify the built skill before push

## License

Apache 2.0
