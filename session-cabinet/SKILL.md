---
name: session-cabinet
description: Use when the user says "file my sessions", "session archive", "where are my old sessions", "make my Claude history searchable", "organize my Claude Code transcripts", "I can't find that session from last week", or "index my Claude sessions". Auto-files Claude Code session transcripts (~/.claude/projects/**/*.jsonl) into a human-navigable date-anchored archive with semantic SESSION.md cards, per-month _INDEX.md tables, and a master index. Idempotent — safe to run on a schedule. Free skill, stdlib only.
---

# session-cabinet

Auto-files Claude Code session transcripts into a searchable, date-anchored archive.

## What it does

Claude Code stores every session as a UUID-named `.jsonl` file under
`~/.claude/projects/`. These files are opaque by default — no titles, no
topics, no way to find "that deploy session from three weeks ago."

`session_cabinet.py` scans those transcripts and files each one into:

```
~/Desktop/Claude Code Sessions/
  2026/
    06-June/
      2026-06-03_1420__nginx-deploy-fix/
        SESSION.md          ← frontmatter card + summary
        manifest.log        ← one-line event record
        docs/
        artifacts/
        screenshots/
        notes/
    _INDEX.md               ← per-month table (Date · Title · Projects · Folder)
  _INDEX.md                 ← master table (all sessions)
```

The folder name is derived from the AI-generated title or the first real
thing you typed — not the UUID. Every session is findable by date, topic,
or keyword grep on the `SESSION.md` cards.

## CLI

```sh
# Dry-run (no writes — shows what would be filed)
python3 session_cabinet.py --dry-run

# File everything
python3 session_cabinet.py

# Verbose (shows each session path)
python3 session_cabinet.py --verbose

# Limit to N sessions (useful for testing)
python3 session_cabinet.py --limit 20

# Custom cabinet location
python3 session_cabinet.py --cabinet ~/Documents/SessionArchive

# Or via env var
CC_CABINET_DIR=~/Documents/SessionArchive python3 session_cabinet.py

# Override timezone (default: system local)
python3 session_cabinet.py --tz -5:00

# Recover sessions from an external drive / server backup
python3 session_cabinet.py --source-dir /Volumes/Backup/.claude/projects \
                           --source-label server
```

## Dry-run contract

`--dry-run` prints a full report — counts of new/migrated/updated/skipped
sessions, any day-burst dates, the cabinet tree — without writing a single
file. Always run dry first on a new machine.

## Folder layout

```
<CABINET>/
  YYYY/
    MM-MonthName/
      YYYY-MM-DD_HHMM__topic-slug/   ← one folder per session
        SESSION.md                   ← YAML frontmatter + summary
        manifest.log                 ← event log
        docs/                        ← subfolder stubs (empty at creation)
        artifacts/
        screenshots/
        notes/
      _INDEX.md                      ← month table
    [DD/]                            ← day-burst dir when >6 sessions/day
  _INDEX.md                          ← master table
```

## Scheduling (hourly via launchd)

Run `bash setup.sh` to install a launchd agent that runs the filer hourly.
The agent uses the `local` label `io.ariacode.session-cabinet`.

To check status after install:
```sh
launchctl list | grep session-cabinet
cat ~/Library/Logs/session-cabinet.log
```

## Safety model

- **No deletion.** Sessions are never deleted — only filed or moved.
- **Idempotent.** Re-running is safe; already-filed sessions are skipped.
- **No LLM calls.** Everything is heuristic parsing of the JSONL structure.
- **Stdlib only.** No pip install required.
- **Portable.** All paths derived from `pathlib.Path.home()`. Works on any
  user's machine; no hardcoded paths or usernames.
