---
name: github-repo-deploy
description: Reconcile a YAML catalog of GitHub repo metadata (description, homepage, topics) to the live GitHub account. Idempotent, --dry-run by default, --apply --prod for the live PATCH. Auth via `gh auth token` or GITHUB_TOKEN env. Refuses to change visibility (public/private) or default_branch without explicit override. Use when the user says "polish my repos", "update GitHub descriptions", "tag my repos for discoverability", "fix repo metadata", or before any campaign that drives traffic to GitHub. Single-command alternative to clicking through every repo's settings page.
---

# github-repo-deploy

YAML → GitHub repo metadata reconciler. Same pattern as `stripe-sync` and `cloudflare-dns-deploy`.

## Usage

```sh
python3 github_repo_deploy.py                       # dry-run (read-only)
python3 github_repo_deploy.py --apply --prod        # reconcile live
python3 github_repo_deploy.py --repo aria-skills    # one repo
```

## Config

See `github_repos.yaml`. Each entry can declare: `name`, `description`, `homepage`, `topics`.

## Safety

- **`description` / `homepage` / `topics`** — reconciled.
- **`private`** — refuses to flip without `--allow-visibility` (not implemented; deliberate).
- **`default_branch`** — warn-only, never auto-flipped.

## License

Apache 2.0
