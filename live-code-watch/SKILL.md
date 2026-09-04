---
name: live-code-watch
description: Watch a git repo's working diff get written live — a terminal that redraws ONLY when the code changes (no idle flicker), with brand-new files shown inline via intent-to-add. Point it at a repo while an AI agent (or you) edits and watch the raw code appear line by line. Zero deps beyond git. Use when the user says "watch the code", "show me the live diff", "watch this repo change", or wants to see edits happen in real time.
---

# live-code-watch

> A live view of your repo's working diff that redraws only when the code changes.

```sh
python3 live_code_watch.py                 # render the current diff once, exit
python3 live_code_watch.py --watch         # live: redraw only when it changes
python3 live_code_watch.py --repo ~/proj --watch --interval 1
```

## Why

When an AI agent edits your code (or you're pair-watching a build), `git diff` in a
loop with `clear` *flickers* and you can't tell when something actually changed.
This redraws **only on change** (cursor-home + clear-to-end), so it sits still when
idle and updates smoothly when code lands — and `git add -N` surfaces brand-new
files' contents in the diff.

## Behavior

- **Default (no flag):** render the diff once and exit 0 — quick "what's changed."
- **`--watch`:** live loop; redraws on change only. `Ctrl-C` to stop. `--max-iterations N` to auto-stop.
- Read-only: the only mutation is a transient `git add -N` (intent-to-add); it never commits.
- Not a git repo → prints a note and exits 0.

## Requires
- `git` on PATH. No Python packages.
