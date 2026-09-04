# aria-skills

> **One-line CLI alternatives to the dashboards you click through 50× a year.**

Open-source [Claude Code Skills](https://docs.anthropic.com/) that turn manual dashboard work into idempotent, declared-intent reconcile loops. Built and dogfooded by [InsyncTech](https://insynctech.io) for Vox Ordo — open-sourced so you can run them solo too.

```sh
# Manual:        an afternoon clicking through Settings on every repo
# With aria-skills:
python3 github-repo-deploy/github_repo_deploy.py --apply --prod
```

---

## What's in here

| Skill | What it replaces | Time saved per use |
|---|---|---|
| [**github-repo-deploy**](./github-repo-deploy/) | GitHub Settings on every repo: description, homepage, topics | 5-10 min per repo |
| [**cloudflare-dns-deploy**](./cloudflare-dns-deploy/) | Cloudflare dashboard + nginx + certbot ceremony | 15-30 min |
| [**surgical-patch**](./surgical-patch/) | Hand-editing a hot shared file that is ahead of your checkout | one exact, reversible edit instead of a clobber |
| [**sprint-scaffold**](./sprint-scaffold/) | The meta-skill: Filing Cabinet + Flowstate scaffolding for new sprints | n/a (workflow pattern) |
| [**goal-to-plan**](./goal-to-plan/) | Re-briefing an agent from a fuzzy goal every time it starts | one agent-ready brief per goal |
| [**premortem**](./premortem/) | The "how could this fail" talk that never becomes an artifact | a ledger row per failure mode |
| [**ffmpeg-audio**](./ffmpeg-audio/) | Re-typing the mono 16 kHz PCM ffmpeg line in every session | minutes per batch; no drift |
| [**video-ingest**](./video-ingest/) | Pasting a transcript by hand so the agent can "watch" a video | minutes per link |
| [**doc-to-pdf**](./doc-to-pdf/) | Print-to-PDF fiddling for a client-ready document | minutes per deliverable |
| [**session-cabinet**](./session-cabinet/) | Hunting through raw Claude Code transcripts for last week's session | a searchable, dated archive |
| [**live-code-watch**](./live-code-watch/) | `git diff` in a flickering loop; can't tell when code changed | watch agentic edits land in real time |
| [**screen-describe**](./screen-describe/) | Screenshot + upload somewhere to ask "what's on my screen" | seconds; runs local + private (BYOK) |
| [**headless-claude**](./headless-claude/) | `claude -p` hanging on a prompt / firing your hooks in a script | every automated/cron/agent claude call |
| [**call-scrub**](./call-scrub/) | Replaying ElevenLabs voice-call audio to find what broke | minutes per call debugged (tool calls + errors) |
| [**aria-skill-template**](./aria-skill-template/) | Copying an old skill directory and renaming things | 10-20 min per new skill |
| [**aria-skill-test**](./aria-skill-test/) | Opening each skill by hand to see if it still runs | seconds before every push |
| [**skill-manifest-gen**](./skill-manifest-gen/) | Hand-writing OpenAI, Gemini, and MCP tool schemas | 10 min per skill, never stale |
| [**aria-skill-candidates**](./aria-skill-candidates/) | Guessing what to automate next | a ranked list mined from your transcripts |

Skills that were tied to our own servers and workflow live under [`_retired/`](./_retired/) — kept for history, not maintained. More skills ship as we build them. Watch this repo, or see [insynctech.io/open-source](https://insynctech.io/open-source).

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
git clone https://github.com/iansteitz1-eng/aria-skills ~/aria-skills

# Link the skills you want into Claude Code's skill directory:
ln -s ~/aria-skills/github-repo-deploy ~/.claude/skills/github-repo-deploy
ln -s ~/aria-skills/cloudflare-dns-deploy ~/.claude/skills/cloudflare-dns-deploy
ln -s ~/aria-skills/surgical-patch ~/.claude/skills/surgical-patch

# Install Python deps (each skill lists what it needs):
pip install -r github-repo-deploy/requirements.txt
pip install -r cloudflare-dns-deploy/requirements.txt
pip install -r surgical-patch/requirements.txt
```

Then in Claude Code, the skills appear in your available-skills list. Or run the underlying Python scripts directly — they're self-contained.

Before you push a change, `python3 aria-skill-test/aria_skill_test.py` dry-runs every skill and checks its manifests.

## Configuration

Each skill is driven by a YAML file you author. Examples live in each skill's directory. Credentials read from environment variables (never committed). See per-skill READMEs.

## Use it solo, or use Vox Ordo

**Solo (this repo)** — clone, install, run. Your YAML + your credentials + your machine. Apache-2.0 licensed.

**Hosted ([Vox Ordo](https://insynctech.io))** — same skills, but Aria runs them on your behalf with:
- Multi-user team access
- Audit trail across your whole org (CertusOrdo splat log)
- Approval workflows for high-risk actions (live payments etc.)
- One-click scheduled runs (renew certs, sync products weekly)
- Zero server setup

→ **[Vox Ordo](https://insynctech.io)**

## Safety patterns embedded

Worth calling out because these are research-adjacent and we ship them in production:

| Pattern | Where you'll see it |
|---|---|
| **Declared-intent reconcile** | Every skill — YAML is intent; script compares to live state |
| **Two-flag live actions** | `github-repo-deploy` — `--apply --prod` is the only combination that writes; a visibility flip needs a further explicit override |
| **Mode separation** | `aria-skill-template` pre-wires `mode: test` in the generated config; `mode: live` still requires the explicit `--prod` flag |
| **Idempotent state matching** | `cloudflare-dns-deploy` matches records by (zone, type, name) and patches drift in place; `github-repo-deploy` replaces topics as a set — declared intent is the source of truth |
| **Hash-chained audit log** | Every state change in Aria's hosted version emits a splat; full chain is verifiable post-hoc |
| **User-scoping** | In hosted mode, every query filters by `user_email` resolved from session — no cross-tenant access by construction |

These aren't theoretical. They run today.

## Support

- **Email:** support@insynctech.io
- **Issues / questions:** [GitHub Issues](https://github.com/iansteitz1-eng/aria-skills/issues)
- **Vox Ordo (hosted):** [insynctech.io](https://insynctech.io)
- **Builder:** [@iansteitz](https://twitter.com/iansteitz) / [InsyncTech](https://insynctech.io)

## License

[Apache-2.0](./LICENSE). Use freely. Star the repo if you find it useful — that's how we find each other in this space.

## Contributing

PRs welcome. Especially: new skills for vendors we haven't covered (Linear, Notion, Vercel, Render, Fly.io, etc.).
