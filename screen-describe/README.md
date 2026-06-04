# screen-describe

Ask your **local** Claude what's on your screen. Captures the macOS display, sends
the image to your own `claude` CLI (your Pro/Max — no API key), prints a short
description, and deletes the screenshot immediately.

```sh
python3 screen_describe.py --apply
```

Read-only (it never clicks or types). macOS-only; needs Screen Recording permission
+ the `claude` CLI logged in. See `SKILL.md`.
