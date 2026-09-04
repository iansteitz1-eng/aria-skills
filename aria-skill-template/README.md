# aria-skill-template

> **The skill that creates skills.** Scaffold a new aria-skills-pattern skill in 5 seconds.

```sh
python3 aria_skill_template.py linear-sync --vendor linear
# ✓ Scaffolded skill at ./linear-sync/
# Files created:
#   · README.md
#   · SKILL.md
#   · linear_sync.py
#   · linear_sync_config.yaml
#   · requirements.txt
```

Multiplies contributor velocity. Every new skill starts from a working stub that already wires the conventions in [BUILDER_GUIDE.md](../BUILDER_GUIDE.md): YAML-reconcile, two-flag prod gate, match-by-metadata-not-name, splat audit hook, dry-run default.

## What gets generated

For `aria_skill_template.py my-new-skill --vendor acme`, the output directory is a complete, runnable skill:

```
my-new-skill/
├── README.md                    ← public-facing docs
├── SKILL.md                     ← Claude Code manifest
├── my_new_skill.py              ← script with reconcile-loop stubs
├── my_new_skill_config.yaml     ← YAML config template
└── requirements.txt             ← Python deps (PyYAML + httpx)
```

The script has TODO markers exactly where you need to plug in vendor-specific logic:
- `_list_existing_resources()` — vendor API list call
- `_reconcile_one()` — vendor API create/patch call
- Vendor SDK import at the top
- API key format validation

Everything else (CLI parsing, mode/prod-flag handling, YAML loading, summary printing, splat no-op) is pre-wired.

## Usage

```sh
# Basic (vendor inferred from first hyphen-segment of name):
python3 aria_skill_template.py linear-sync

# Explicit vendor:
python3 aria_skill_template.py my-skill --vendor acmecorp

# Custom destination:
python3 aria_skill_template.py my-skill --dest ~/my-projects

# Overwrite existing:
python3 aria_skill_template.py my-skill --force
```

## Why bother with a generator?

Three reasons:

1. **Pattern enforcement.** Every generated skill ships with the safety gates already in place. Contributors don't accidentally skip `--prod` checks because the stub has them by default.
2. **Discoverability.** A new contributor sees the file structure and learns the convention by reading working code, not by reading docs first.
3. **Velocity.** 5-second scaffold → 30-90 minute fill-in for vendor specifics. Beats the 2-3 hour green-field equivalent.

## What this skill does NOT do

- **Doesn't fill in vendor logic.** The TODOs are yours to complete.
- **Doesn't add the skill to the public repo.** You can do that with a git commit when you're ready.
- **Doesn't generate tests.** Use `aria-skill-test` for that (separate skill).

## See also

- **[BUILDER_GUIDE.md](../BUILDER_GUIDE.md)** — the patterns this template enforces
- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Vox Ordo](https://voxordo.io)** — hosted version

## License

Apache 2.0
