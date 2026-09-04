# surgical-patch

Drift-safe editor for a hot, shared, possibly-remote file — the safe way to change
a prod file you **can't** rsync over because the live copy is ahead of your local
one (other lanes' uncommitted edits live in it).

Applies a data-driven list of exact-match edits with three guarantees:

- **Idempotent** — a `sentinel` string already present → no-op (safe re-runs).
- **Exact / all-or-nothing** — every anchor must match a precise count or the run
  aborts having written nothing (no half-applied files from drifted anchors).
- **Reversible** — timestamped backup before write; a failing `verify` command
  auto-rolls-back.

```sh
python3 surgical_patch.py --edits edits.json --path /srv/myapp/main.py --host <your-server>
```

Exit: `0` applied/no-op · `1` error · `2` anchor assertion failed · `3` verify failed (rolled back).

On `--host`, the `verify` command runs with the service env file sourced first
(`--env-file`, or `SURGICAL_PATCH_ENV_FILE`; default `/opt/aria/.env`; pass `''` to skip).

Born from the 2026-06-03 runner-provenance deploy, where prod `main.py` was ~750
lines ahead of the Mac checkout. Pairs well with a pre-restart guard and a
post-deploy verifier.

## License

Apache 2.0
