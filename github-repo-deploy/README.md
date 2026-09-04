# github-repo-deploy

> **YAML → GitHub repo metadata.** Stop clicking through Settings on every repo.

```sh
python3 github_repo_deploy.py
# # github-repo-deploy · mode=DRY-RUN · repos=5
# ⚠ aria-skills: drift
#     · description: 'Open-source Claude Code Skills replacing dashboard work' → 'Open-source Claude Code Skills that replace…'
#     · topics: +['claude-skills', 'devtools', 'yaml-reconcile'] -[]
# ⚠ aria-thesis: drift
#     · description: 'wall clock' → 'Wall-clock latency and continuity research…'
# # Summary: 5/5 repo(s) have drift
# # Run with --apply --prod to reconcile.
```

## What it reconciles

| Field | Mode |
|---|---|
| `description` | Reconciled |
| `homepage` | Reconciled |
| `topics` | Reconciled (full replace) |
| `default_branch` | **Warn-only** (never auto-flips) |
| `private` | **Refuses to change** without `--allow-visibility` |

## Auth

Prefers `gh auth token` (run `gh auth login` once). Falls back to `GITHUB_TOKEN` or `GH_TOKEN` env var.

## CLI

| Flag | Effect |
|---|---|
| (none) | Dry-run all repos |
| `--apply --prod` | Live PATCH |
| `--repo NAME` | Target single repo |
| `--owner OWNER` | Override config-level owner |
| `--config PATH` | Alternate YAML |

## Pattern

Same shape as [`cloudflare-dns-deploy`](../cloudflare-dns-deploy/). See [BUILDER_GUIDE.md](../BUILDER_GUIDE.md) for the YAML-reconcile + two-flag-prod pattern.

## License

Apache 2.0
