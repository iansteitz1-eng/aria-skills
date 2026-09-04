# session-cabinet

> Make your Claude Code history searchable.

Claude Code stores every session as a UUID-named `.jsonl` file — hundreds
of them, named like `a3f8c201-4d12-...jsonl`, with no titles and no way to
search. `session-cabinet` files them into a human-navigable archive:

```
~/Desktop/Claude Code Sessions/
  2026/
    06-June/
      2026-06-03_1420__nginx-deploy-fix/
        SESSION.md    ← title, timestamps, cwd, topics, summary
        manifest.log
        docs/ artifacts/ screenshots/ notes/
      _INDEX.md       ← month table
  _INDEX.md           ← master table (all sessions)
```

## Install

```sh
bash setup.sh
```

This installs a launchd agent (macOS) that runs the filer once per hour.
On Linux, the script prints a cron line you can add manually.

## Usage

```sh
# Preview what would be filed (no writes)
python3 session_cabinet.py --dry-run

# File everything now
python3 session_cabinet.py

# Custom archive location
python3 session_cabinet.py --cabinet ~/Documents/SessionArchive
# or: export CC_CABINET_DIR=~/Documents/SessionArchive

# Recover sessions from a server / backup disk
python3 session_cabinet.py \
  --source-dir /Volumes/Backup/.claude/projects \
  --source-label server
```

## Where the archive lands

Default: `~/Desktop/Claude Code Sessions/`

Override: `--cabinet <dir>` flag or `CC_CABINET_DIR` env var.

## Requirements

Python 3.8+, stdlib only — no pip install needed.

## License

Apache 2.0
