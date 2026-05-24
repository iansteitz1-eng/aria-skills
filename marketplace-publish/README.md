# marketplace-publish

> **One publish command, three surfaces.** VS Code Marketplace + iOS App Store + Google Play Console.

Stop juggling `vsce`, Expo EAS submit, and three sets of credentials. Declare your release targets once; ship to all of them.

```sh
python3 marketplace_publish.py --target vscode
python3 marketplace_publish.py --target ios
python3 marketplace_publish.py --target android
python3 marketplace_publish.py --target all   # all three
```

## 30-second install

```sh
pip install -r requirements.txt

# Add credentials for the targets you want to ship to (see env vars below)
echo "VSCE_PAT=eyJ..." > .env

# Dry-run (no uploads):
python3 marketplace_publish.py --target vscode

# Real publish:
python3 marketplace_publish.py --target vscode --apply
```

## Pre-flight checks

Before doing anything destructive, the skill validates:
- VS Code: `VSCE_PAT` set + extension package builds
- iOS: Apple Developer credentials valid + EAS project exists
- Android: Google Play service-account JSON readable + EAS config exists

If pre-flight fails, the skill prints exactly what's missing and exits with code 2 (no uploads happen).

## Env vars required

| Var | Target | Notes |
|---|---|---|
| `VSCE_PAT` | vscode | Azure DevOps PAT with Marketplace (Manage) scope |
| `APPLE_ID` | ios | Apple Developer account email |
| `APPLE_APP_SPECIFIC_PASSWORD` | ios | from appleid.apple.com → Sign-In and Security |
| `EXPO_TOKEN` | ios, android | from expo.dev → access tokens |
| `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` | android | path to the service-account .json file |

## Safety

- **`--dry-run` default.** Skips actual uploads — validates credentials + package builds only.
- **`--apply` is the explicit opt-in** for real submissions.
- **Per-target isolation.** If iOS submission fails, Android still ships.
- **No auto-version-bump.** You bump the version explicitly in `package.json` / `app.json`; the skill reads it but doesn't write.

## What's NOT automated

- **First-time account creation** (Apple $99/yr enroll · Google Play $25 one-time · Azure DevOps free) — KYC + identity verification gates.
- **Initial extension/app metadata** (icons, descriptions, screenshots) — author once, the skill uses them on every subsequent publish.
- **App Store review** — Apple's manual review is what it is; the skill submits, then it's in Apple's hands.

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with release scheduling + cross-team approval gates

## License

Apache 2.0
