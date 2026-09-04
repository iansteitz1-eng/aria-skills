---
name: skill-manifest-gen
description: Generate cross-harness discovery manifests (openai.json · gemini.json · mcp.json + README) so an aria-skill is findable from OpenAI/Codex/Grok, Google Gemini, and MCP clients (VS Code, Cursor, Claude Desktop) — not just Claude Code. Derived deterministically from SKILL.md + the script's argparse, so manifests never drift. --all sweeps the repo, --check is a CI drift gate, --force overwrites. Use when Ian says "generate manifests", "MCP marketplace", "discoverable in VS Code/Cursor", "backfill manifests", or after adding a skill.
---

# Skill Manifest Gen — cross-harness discovery, blanket-covered

Every aria-skill is one executable. Claude Code discovers it via `SKILL.md`;
other harnesses need their own discovery file. This generates all three from the
same sources of truth so they can't drift:

| Harness | File it needs |
|---|---|
| OpenAI / Codex / xAI Grok | `manifest/openai.json` (Tool/Function schema) |
| Google Gemini | `manifest/gemini.json` (`function_declarations`) |
| MCP — VS Code, Cursor, Claude Desktop | `manifest/mcp.json` (tool spec 2024-11-05) |

Sources of truth: **`SKILL.md` frontmatter** (name + description) + the skill's
**script argparse** (→ the input parameter schema). Nothing is hand-authored, so
a regenerate always matches the skill.

## Run it

```sh
# one skill (skips if manifest/ already exists)
python3 skill-manifest-gen/gen_manifests.py --skill-dir safe-restart

# blanket: every skill in the repo (existing manifests left untouched)
python3 skill-manifest-gen/gen_manifests.py --all --repo-root .

# CI drift gate: report any skill missing a manifest or whose description is stale
python3 skill-manifest-gen/gen_manifests.py --all --check        # exit 2 if any

# deliberately regenerate a curated one
python3 skill-manifest-gen/gen_manifests.py --skill-dir foo --force
```

## Safety / fidelity

- **Never clobbers.** In write mode an existing `manifest/` is **skipped** unless
  `--force` — curated manifests are often hand-tuned past what argparse exposes
  (richer param docs, corrected defaults), so a blanket `--all` is safe to run.
- **`--check` is the blanket enforcement.** It's wired into `aria-skill-test`, so
  a new skill that ships without manifests (or one whose `SKILL.md` description
  drifts from its manifest) FAILS the regression harness. That's how "nothing
  goes missing again" is guaranteed, not just fixed once.
- Generated manifests are a correct **starting point**; refine param descriptions
  by hand when useful, then they're protected by the no-clobber rule.

## Notes

- `manifest/` is discovery glue only — the script remains the behavior truth.
- Pairs with `marketplace-publish` (which uploads the VS Code extension /
  app-store builds) and `aria-skill-test` (the gate).

## License

Apache 2.0
