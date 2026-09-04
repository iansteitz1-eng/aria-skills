---
name: aria-skill-template
description: Scaffolds a new aria-skills-pattern skill from a template. Generates README.md + SKILL.md + script.py with reconcile-loop stubs + config.yaml + requirements.txt — a fully-formed skill directory ready to fill in with vendor-specific logic. Multiplies contributor velocity. Use when the user says "scaffold a new skill", "create a skill for X", "new skill template", "I want to build a skill for <vendor>", or starting any new vendor integration.
---

# aria-skill-template

YAML-reconcile skill scaffolder. Generates a fully-formed skill directory in 5 seconds.

## When to use

- Starting a new vendor integration (Linear, Notion, GitHub, etc.)
- Contributor wants to ship a PR — scaffold first, then fill in
- Pattern enforcement (the template embeds BUILDER_GUIDE conventions)

## How it works

1. Validates the skill name (lowercase + hyphens, 3-40 chars)
2. Computes derived names (snake_case for Python, title for headings)
3. Renders 5 template files via Python string formatting
4. Writes them to `<dest>/<name>/`
5. Chmods the Python script executable
6. Prints next-steps + path to the new skill

## CLI

```sh
python3 aria_skill_template.py <skill-name> [--vendor <vendor>] [--dest <dir>] [--force]
```

Examples:
```sh
python3 aria_skill_template.py linear-sync
python3 aria_skill_template.py github-org-sync --vendor github
python3 aria_skill_template.py my-skill --dest /tmp/scratch
```

## What gets generated

5 files in `<dest>/<name>/`:
- `README.md` — public docs with the standard structure
- `SKILL.md` — Claude Code manifest with frontmatter trigger description
- `<snake_name>.py` — script with reconcile-loop stubs + TODO markers for vendor specifics
- `<snake_name>_config.yaml` — YAML config template
- `requirements.txt` — common deps (PyYAML + httpx)

## Conventions enforced

Per [BUILDER_GUIDE.md](../BUILDER_GUIDE.md):
- Two-flag prod gate pre-wired (--apply + --prod for live mode)
- Mode-mismatch safety (refuses test-key in live-mode and vice-versa)
- Match-by-metadata-key (`aria_key` field), not by display name
- Splat audit hook stub
- Dry-run default

## See also

- **[BUILDER_GUIDE.md](../BUILDER_GUIDE.md)** — the pattern reference
- **[aria-skill-test](../aria-skill-test/)** — regression harness for shipped skills

## License

Apache 2.0
