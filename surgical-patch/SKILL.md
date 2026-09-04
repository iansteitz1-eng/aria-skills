---
name: surgical-patch
description: Drift-safe editor for a hot, shared, possibly-remote file (e.g. prod main.py that's AHEAD of your local checkout). Applies a data-driven list of exact-match edits with three guarantees — idempotent (sentinel no-op), exact (every anchor must match a precise count or it aborts writing nothing), and reversible (timestamped backup + verify-or-rollback). Works locally or over ssh. Use when Ian says "patch the live file", "surgically edit main.py", "apply this change to prod without clobbering", "the server file is ahead of mine", or before any edit to a shared file multiple lanes touch.
---

# Surgical Patch — drift-safe live-file editor

The safe way to change a file that you **can't** just rsync over, because the live
copy is ahead of your local one (other lanes' uncommitted edits live in it).

**Why it exists.** On 2026-06-03 the prod `main.py` was ~750 lines ahead of the
Mac checkout. A wholesale rsync would have wiped other lanes' work. The fix:
fetch the live file, build a minimal delta, and apply it with assertions + backup.
This skill is that pattern, made repeatable. Pairs with [[safe-restart]] (guard
the restart) and [[aria-deploy]] (do the restart). Enforces the drift rule in
[[project_local_first_doctrine_2026_06_02]].

## The loop

1. **Find the live anchors.** `ssh <host> "grep -n '<marker>' <path>"` /
   `sed -n` the region. Build edits against the LIVE text, never your stale local.
2. **Author an edits spec** (`edits.json`):
   ```json
   {
     "sentinel": "runner_provenance",
     "verify": "python3 -m py_compile {path}",
     "edits": [
       {"old": "<exact live block>", "new": "<replacement>", "count": 1}
     ]
   }
   ```
   - `sentinel` (optional) — a string unique to the patched state; if already
     present the run is a NO-OP (idempotent re-runs after a partial deploy).
   - `verify` (optional) — shell run after writing; `{path}` is substituted; a
     nonzero exit **rolls back** to the backup. For Python on the server use
     `python3 -m py_compile {path}` or a full `python3 -c "import main"`.
   - each edit `old` must match exactly `count` times (default 1) or the whole
     run aborts with **nothing written**.
3. **Dry-run** to confirm anchors: add `--dry-run`.
4. **Apply.**
   ```sh
   python3 ~/.claude/skills/surgical-patch/surgical_patch.py \
       --edits edits.json --path /srv/myapp/main.py --host <your-server>
   ```
5. **Then** `/safe-restart` (fleet clear?) → `/aria-deploy` (restart) →
   `/deploy-verify` (did my change go live?).

## Guarantees & exit codes

- **Idempotent** — `sentinel` present → exit 0, no change.
- **Exact / all-or-nothing** — any anchor whose match count ≠ expected aborts the
  entire run before writing (**exit 2**). You never get a half-applied file from a
  drifted anchor.
- **Reversible** — original copied to `<dir>/.deploy_bak/<ts>/<file>` before write;
  `verify` failure auto-rolls-back (**exit 3**).
- `0` applied/no-op · `1` error · `2` anchor assertion failed · `3` verify failed (rolled back).

## Notes

- Remote writes stream over stdin (`ssh host "cat > path"`) — no arg-length or
  shell-quoting limits on large files.
- `verify` on `--host` sources the service env file (`--env-file`, or `SURGICAL_PATCH_ENV_FILE`; default `/opt/aria/.env`) first so imports resolve like the
  running service.
- It edits ONE file per run by design (clear backups, clear rollback). For a
  multi-file change, run it once per file; each gets its own backup.
- Read the live file every run — do not cache it; another lane may have moved on.

## License

Apache 2.0
