# skill-manifest-gen

Generate cross-harness discovery manifests (`openai.json` · `gemini.json` ·
`mcp.json` + README) so an aria-skill is discoverable from OpenAI/Codex/Grok,
Google Gemini, and MCP clients (VS Code, Cursor, Claude Desktop) — not just
Claude Code.

Everything is derived deterministically from `SKILL.md` frontmatter + the
script's argparse, so manifests never drift from the skill.

```sh
python3 gen_manifests.py --skill-dir safe-restart    # one (skips if exists)
python3 gen_manifests.py --all --repo-root .          # blanket (no clobber)
python3 gen_manifests.py --all --check                # CI drift gate (exit 2)
python3 gen_manifests.py --skill-dir foo --force      # deliberate overwrite
```

Never clobbers a curated `manifest/` without `--force`. `--check` is wired into
`aria-skill-test` so missing/stale manifests fail the regression harness — the
blanket guarantee that nothing goes missing again. Pairs with `marketplace-publish`.

## License

Apache 2.0
