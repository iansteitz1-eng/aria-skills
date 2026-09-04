---
name: headless-claude
description: Run the `claude` CLI fast, with your hooks skipped, and unattended for automation — wraps `claude -p` with --setting-sources project (skip your user hooks + heavy auto-memory, ~2s not ~15s), --permission-mode bypassPermissions (no interactive approval prompt that would block a script), and a neutral cwd. Uses your own plan, no API key. Use when the user says "run claude headless", "scriptable claude", "claude -p keeps hanging / prompting", "call claude from a cron/agent", or is automating Claude Code.
---

# headless-claude

> The flags that make `claude -p` actually behave in scripts, agents, and cron.

```sh
python3 headless_claude.py "summarize CHANGES.md in 3 bullets"          # prints the command (dry)
python3 headless_claude.py --apply "summarize CHANGES.md in 3 bullets"  # runs it
python3 headless_claude.py --apply --cwd ~/proj "fix the failing test"  # in a repo
```

## Why these flags

A bare `claude -p` in an automated context can **hang on a permission prompt**, **fire
your editor/notify/Stop hooks**, and **load your whole user memory** (slow). For
unattended use you almost always want:

| flag | effect |
|---|---|
| `--setting-sources project` | don't load USER `~/.claude` hooks/settings; skip auto-memory → fast, no side effects |
| `--permission-mode bypassPermissions` | no interactive approval gate — a script can't answer one |
| neutral `--cwd` | don't drag in a project's CLAUDE.md / file tree |

Escape hatches: `--allow-hooks` (keep your hooks), `--safe` (let it prompt). BYOK — uses
your logged-in plan, no API key.

## Behavior
- **Default:** print the exact command (dry), exit 0.
- **`--apply`:** run it, stream stdout. Missing `claude` / nonzero exit / timeout → `FATAL` + exit 2.

## Requires
- The `claude` CLI on PATH, logged in. No Python packages.
