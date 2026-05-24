---
name: aria-skill-test
description: Regression harness for the aria-skills repo. Runs every shipped skill in dry-run mode + asserts clean output (no traceback, no credential leaks, valid SKILL.md frontmatter, README.md present). Text report by default; --junit-xml flag for CI integration. Use when the user says "test the skills", "regression check", "before push", "run the test harness", or any time before opening a PR or pushing to main.
---

# aria-skill-test

Regression harness. Pythonic + zero-dependency. Tests structural correctness across every skill in the repo without making any real API calls.

## When to use

- Before pushing changes to the public repo
- In CI on every PR (use `--junit-xml` flag)
- After running `aria-skill-template` to confirm the generated stub passes
- After editing any skill script — quick sanity check

## What gets checked

Per skill directory:
- SKILL.md frontmatter parses (YAML between `---` markers)
- `name` field in frontmatter matches directory name
- `description` field is 40-600 chars
- README.md exists
- Executable script found (snake_case or kebab-case .py / .sh)
- Dry-run exits 0 (clean) or 2 (needs creds with clear FATAL message)
- No Python traceback in stderr
- No credential leak patterns in output (Anthropic / Stripe / Resend / Twilio / Cloudflare / EL / AWS / GitHub PAT)

## CLI

```sh
python3 aria_skill_test.py                              # all skills
python3 aria_skill_test.py --skill <name>               # one skill
python3 aria_skill_test.py --skip <name> --skip <name>  # exclude
python3 aria_skill_test.py --junit-xml results.xml      # CI mode
python3 aria_skill_test.py --repo-root /path/to/repo    # alternate
```

## See also

- **[BUILDER_GUIDE.md](../BUILDER_GUIDE.md)** — the patterns enforced
- **[aria-skill-template](../aria-skill-template/)** — generator paired with this harness

## License

Apache 2.0
