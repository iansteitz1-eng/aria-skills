# live-code-watch

Watch a git repo's working diff get written **live** — a terminal pane that redraws
only when the code actually changes (no idle flicker), with new files shown inline.

```sh
python3 live_code_watch.py --watch --repo .
```

Pairs perfectly with any agentic coding loop: keep this open while your AI edits and
you'll watch the raw code appear. Zero dependencies beyond `git`.

See `SKILL.md` for full flags. Read-only (only a transient `git add -N`; never commits).
