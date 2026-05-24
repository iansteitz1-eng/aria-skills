---
name: marketplace-publish
description: Unified marketplace publisher for VS Code Marketplace (via vsce), iOS App Store / TestFlight (via Expo EAS submit), and Google Play Console (via Expo EAS submit). Single command surface around publish.sh + submit.sh. Pre-flight validates credentials before doing anything destructive. --dry-run by default skips uploads. Use when the user says "publish the extension", "submit to App Store", "ship to Play Store", "marketplace publish", "release the vsix", "build and submit", or before any app-store push.
---

# marketplace-publish

YAML-as-source-of-truth for releases across VS Code Marketplace + iOS App Store + Google Play. Triggers `vsce` + Expo EAS submit with the credentials you've staged in env.

## When to use

- Cutting a new release across one or more app surfaces
- CI/CD release step (after version bump + git tag)
- Audit-friendly publish records (every publish emits a splat in the hosted version)

## How it works

1. Reads project metadata from `package.json` / `app.json` / `eas.json`
2. Pre-flight: validates the credentials for each target you've selected
3. Builds the package (vsce for VS Code; EAS for mobile)
4. Submits to the marketplace
5. Reports back the published version + URL

## CLI

```sh
python3 marketplace_publish.py --target vscode             # dry-run
python3 marketplace_publish.py --target ios                # dry-run
python3 marketplace_publish.py --target android            # dry-run
python3 marketplace_publish.py --target all                # dry-run all three
python3 marketplace_publish.py --target vscode --apply     # real publish
python3 marketplace_publish.py --target all --apply        # ship to all three
```

## Safety

- `--dry-run` default
- Pre-flight credential check before any destructive action
- Per-target isolation (one failure doesn't block others)

## Hosted version

[Aria Code](https://staycool.ai/aria-code) layers scheduled releases + team approval gates + release-notes pipeline on top.

## License

Apache 2.0
