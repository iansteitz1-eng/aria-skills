# headless-claude

Run `claude -p` the way automation needs it: no hanging permission prompt, no user
hooks firing, no heavy memory load — fast and scriptable. A thin wrapper around the
three flags that matter (`--setting-sources project`, `--permission-mode
bypassPermissions`, neutral cwd).

```sh
python3 headless_claude.py --apply "your prompt here"
```

BYOK — uses your logged-in `claude` plan, no API key. See `SKILL.md`.
