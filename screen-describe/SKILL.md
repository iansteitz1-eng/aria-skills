---
name: screen-describe
description: Ask your local Claude what's on your screen. Captures the macOS screen, hands the image to your own `claude` CLI (your Pro/Max, no API key — BYOK), prints a short description, and deletes the screenshot immediately. Read-only — it looks, never controls. Use when the user says "what's on my screen", "describe my screen", "what am I looking at", or wants an AI second pair of eyes on their display.
---

# screen-describe

> Your local Claude, as eyes on your screen. BYOK, read-only, screenshot deleted after.

```sh
python3 screen_describe.py            # dry pre-flight (checks deps, captures nothing)
python3 screen_describe.py --apply    # capture + describe what's on screen
python3 screen_describe.py --apply --question "is there an error visible anywhere?"
```

## Why

Sometimes you want an AI to actually *see* your screen — "what's this error", "what
am I looking at" — without screenshotting + uploading anywhere. This runs entirely on
your machine: `screencapture` → your local `claude` (your own plan) → a 2-3 sentence
read. The screenshot is deleted the moment it's read; nothing leaves your box except
the model call you already pay for.

## Behavior
- **Default:** dry pre-flight — confirms `screencapture` + `claude` are present, exits 0.
- **`--apply`:** capture, describe, delete the shot.
- Missing deps / no Screen Recording permission → clear `FATAL` + exit 2.

## Requires
- macOS (`screencapture`) + **Screen Recording** permission for the running app.
- The `claude` CLI, logged in to your Anthropic plan. No API key, no Python packages.
