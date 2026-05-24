# aria-skill-test

> **Regression harness for the aria-skills repo.** Catches breakage before it ships.

```sh
python3 aria_skill_test.py
# ═══════════════════════════════════════════════════════════════════════
#   aria-skill-test  ·  9 skill(s)  ·  9 pass · 0 fail
# ═══════════════════════════════════════════════════════════════════════
#   ✓  stripe-sync                       1234ms
#   ✓  cloudflare-dns-deploy             892ms
#   ✓  el-agent-deploy                   1102ms
#   ...
#   All tests passed.
```

## What it checks

For every skill directory in the repo:

1. **SKILL.md exists + parses** — frontmatter valid YAML, `name` matches directory, `description` is 40-600 chars
2. **README.md exists** — public docs
3. **Executable script found** — `<snake_name>.py` or `<snake_name>.sh` or `<dir-name>.py`
4. **Dry-run runs clean** — exit code 0 (clean) or 2 (needs creds with clear FATAL message)
5. **No Python traceback in stderr** — script doesn't crash
6. **No credential leaks** — scans output for known token prefixes (`sk-ant-`, `sk_live_`, `act_`, `cfut_`, `ACxxxxx` Twilio, `re_`, `AKIA`, `ghp_`, `xi-`)

## CLI

```sh
# Test all skills:
python3 aria_skill_test.py

# Test one skill:
python3 aria_skill_test.py --skill stripe-sync

# Skip skills (can repeat):
python3 aria_skill_test.py --skip aria-skill-template --skip aria-skill-test

# CI mode (JUnit XML output):
python3 aria_skill_test.py --junit-xml results.xml

# Alternate repo root:
python3 aria_skill_test.py --repo-root /path/to/aria-skills
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All tests passed |
| 1 | At least one test failed |
| 2 | Invocation error (bad args, repo not found, etc.) |

## When to run it

- **Before pushing.** Catch broken skills before they hit the public repo.
- **In CI on every PR.** Block merges that break existing skills.
- **After editing a script.** Quick sanity check.
- **After running aria-skill-template.** Confirm the generated stub passes.

## Credential leak detection

The harness scans stderr + stdout for known credential prefixes:

| Pattern | Vendor |
|---|---|
| `sk-ant-...` | Anthropic |
| `sk_live_...` / `sk_test_...` | Stripe |
| `act_...` | aria-cli device token |
| `cfut_...` | Cloudflare scoped |
| `AC[hex]{32}` | Twilio SID |
| `re_...` | Resend |
| `AKIA...` | AWS access key |
| `ghp_...` | GitHub PAT |
| `xi-...` | ElevenLabs |

If a match appears, the skill fails with `Credential leak in stderr/stdout: pattern X matched`. The leaked value is redacted in the failure message itself.

## What it does NOT do

- **Doesn't make real API calls.** All tests run in dry-run mode (no creds required for the harness itself).
- **Doesn't test correctness of vendor logic.** That's per-skill smoke testing; this harness only catches structural breakage.
- **Doesn't reformat code.** Use a linter for that.

## See also

- **[BUILDER_GUIDE.md](../BUILDER_GUIDE.md)** — the patterns this harness enforces
- **[aria-skill-template](../aria-skill-template/)** — generator that produces test-passable stubs
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with continuous regression monitoring

## License

Apache 2.0
