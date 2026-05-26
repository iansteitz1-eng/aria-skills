#!/usr/bin/env python3
"""
aria_skill_template.py — Scaffolds a new skill in the aria-skills repo pattern.

Generates a fully-formed skill directory matching the BUILDER_GUIDE.md
conventions: README.md, SKILL.md, <name>.py with reconcile-loop stubs,
<name>_config.yaml with mode/vendor placeholders, requirements.txt.

Usage:
  aria_skill_template.py <skill-name> [--vendor <vendor>] [--dest <dir>]

Examples:
  # Scaffold a new linear-sync skill in the current directory:
  python3 aria_skill_template.py linear-sync --vendor linear

  # Custom destination:
  python3 aria_skill_template.py my-skill --vendor acme --dest ~/my-aria-skills

The generated skill is a runnable stub — you can dry-run it immediately,
then fill in the vendor-specific reconcile logic. The two-flag prod gate,
YAML-reconcile shape, and audit-via-splat hook are pre-wired.
"""
import argparse
import json
import re
import sys
from pathlib import Path

VALID_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")


def validate_name(name: str) -> str:
    """Skill names: lowercase, hyphen-separated, 3-40 chars, no leading/trailing hyphen."""
    if not VALID_SLUG.match(name):
        sys.stderr.write(
            f"FATAL: invalid skill name '{name}'.\n"
            "Must be lowercase, hyphen-separated, 3-40 chars, "
            "no leading/trailing hyphen. Examples: linear-sync, github-org-sync.\n"
        )
        sys.exit(2)
    return name


def snake(name: str) -> str:
    """linear-sync → linear_sync"""
    return name.replace("-", "_")


def title(name: str) -> str:
    """linear-sync → Linear-Sync (lightly title-cased for headings)"""
    return "-".join(w.capitalize() for w in name.split("-"))


def vendor_default(name: str) -> str:
    """Guess vendor from first hyphen-segment of skill name."""
    return name.split("-")[0]


def render_readme(name: str, snake_name: str, vendor: str) -> str:
    return f"""# {name}

> **YAML → {vendor} reconciler. One command. Idempotent.**

Replaces clicking through the {vendor} dashboard to manage <resource_type>. Your declared intent lives in `{snake_name}_config.yaml`; this skill reconciles it to your {vendor} account.

```sh
python3 {snake_name}.py --apply --prod
```

## 30-second install

```sh
pip install -r requirements.txt
# Get a credential from <vendor docs URL>
echo "{vendor.upper()}_API_KEY=..." > .env

# Edit your declared intent in {snake_name}_config.yaml
python3 {snake_name}.py             # dry-run, see what would happen
python3 {snake_name}.py --apply     # apply (test mode)
```

## Live mode

```sh
# In {snake_name}_config.yaml, flip:
mode: live

# Then:
python3 {snake_name}.py --apply --prod
```

The `--prod` flag is required for live mode (belt + braces — safety against accidental live hits).

## Idempotent re-runs

Re-running the same YAML produces no changes:

```
# Reconciliation summary:
#   <resource> X: matched (key=...)
#   <resource> Y: matched (key=...)
```

`matched` = the YAML declaration matches the live {vendor} object. No API write happens. Safe to cron.

## Match key choice

This skill matches existing resources by `metadata.aria_*` (or equivalent vendor-specific stable id), NOT by display name. Renames in the dashboard won't create duplicates. See [BUILDER_GUIDE.md §3](../BUILDER_GUIDE.md) for the why.

## Env vars required

| Var | Required for | Notes |
|---|---|---|
| `{vendor.upper()}_API_KEY` | all | from <vendor> account settings |

## Safety

- **Default is dry-run.**
- **`--apply` is the explicit opt-in for changes.**
- **`--prod` is mandatory for live mode** (catches accidental real-account hits).
- **Never matches by name** — always by metadata key.

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[Aria Code](https://staycool.ai/aria-code)** — hosted version with audit trail + scheduled runs + team approval
- **[BUILDER_GUIDE.md](../BUILDER_GUIDE.md)** — the pattern reference

## License

Apache 2.0
"""


def render_skill_md(name: str, snake_name: str, vendor: str) -> str:
    return f"""---
name: {name}
description: Reconcile <resource_type> from a declared YAML catalog to {vendor} via the API. Idempotent. --dry-run by default, --apply hits the API, --prod required for live mode. Use when the user says "sync {vendor}", "update <resource>", or before any {vendor} change ships. One-command alternative to clicking through the {vendor} dashboard.
---

# {name}

YAML-as-source-of-truth for <resource_type> in {vendor}. Reconciles to the live account; only diffs.

## When to use

- Initial setup at launch (replaces dashboard clicking)
- Bulk changes (audit-friendly, version-controlled)
- New deployments (add a block in YAML, run once)

## How it works

1. Reads `{snake_name}_config.yaml`
2. Lists current {vendor} state via API
3. For each declared resource: matches by metadata key. Creates if absent; patches if drift.
4. Idempotent on re-run.

## CLI

```sh
python3 {snake_name}.py                          # dry-run
python3 {snake_name}.py --apply                  # apply (test mode)
python3 {snake_name}.py --apply --prod           # apply (live mode)
```

## Env vars required

| Var | Required for |
|---|---|
| `{vendor.upper()}_API_KEY` | all |

## Safety

- Default dry-run
- `--prod` required for live mode
- Idempotency by metadata key

## Hosted version

[Aria Code](https://staycool.ai/aria-code) layers approval workflow + audit trail + scheduled runs.

## License

Apache 2.0
"""


def render_script(name: str, snake_name: str, vendor: str) -> str:
    return f'''#!/usr/bin/env python3
"""
{snake_name}.py — Declarative {vendor} reconciler.

Reads {snake_name}_config.yaml and reconciles to {vendor}.

CLI:
  python3 {snake_name}.py                  # dry-run (default)
  python3 {snake_name}.py --apply          # apply (test mode)
  python3 {snake_name}.py --apply --prod   # apply (live mode)

See ../BUILDER_GUIDE.md for the patterns this script implements:
- YAML-reconcile loop (§2)
- Match by metadata key, not name (§3)
- Two-flag prod gate (§4)
- Audit-via-splat hook (§6)
"""
import argparse
import os
import sys
from pathlib import Path

# Load .env if present
ENV_FILE = Path(".env")
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

try:
    import yaml
except ImportError:
    sys.stderr.write("FATAL: PyYAML not installed. pip install PyYAML\\n")
    sys.exit(1)

# TODO: import the vendor's SDK (e.g. `import {vendor}` or `import httpx` for REST)

DEFAULT_CONFIG = Path("{snake_name}_config.yaml")


def _load_config(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(f"FATAL: config not found at {{path}}\\n")
        sys.exit(1)
    return yaml.safe_load(path.read_text())


def _resolve_api_key(cfg_mode: str, prod_flag: bool) -> str:
    """Returns the API key. Refuses cross-mode keys (test-key in live-mode, vice versa).

    Follows BUILDER_GUIDE §4 (the two-flag prod gate).
    """
    if cfg_mode == "live" and not prod_flag:
        sys.stderr.write(
            "FATAL: config sets mode=live but --prod was not passed. "
            "Refusing to hit live API.\\n"
        )
        sys.exit(2)
    if cfg_mode == "live" and prod_flag:
        key = os.environ.get("{vendor.upper()}_API_KEY_LIVE") or os.environ.get("{vendor.upper()}_API_KEY")
        if not key:
            sys.stderr.write("FATAL: no live {vendor.upper()}_API_KEY in env.\\n")
            sys.exit(1)
        # TODO: validate key format (e.g. starts with "sk_live_") for the vendor
        return key
    # test mode
    key = os.environ.get("{vendor.upper()}_API_KEY_TEST") or os.environ.get("{vendor.upper()}_API_KEY")
    if not key:
        sys.stderr.write("FATAL: no test {vendor.upper()}_API_KEY in env.\\n")
        sys.exit(1)
    return key


def _list_existing_resources() -> list[dict]:
    """List all resources of the type this skill manages from the live {vendor} API.

    TODO: implement using the vendor's SDK/REST.
    """
    # Example shape:
    # return [
    #     {{"id": "...", "metadata": {{"aria_key": "..."}}, ...}},
    # ]
    return []


def _find_by_metadata_key(resources: list[dict], aria_key: str) -> dict | None:
    """Match an existing resource by the metadata key WE control.

    NEVER match by display name (per BUILDER_GUIDE §3 — names drift, metadata doesn't).
    """
    for r in resources:
        if (r.get("metadata") or {{}}).get("aria_key") == aria_key:
            return r
    return None


def _reconcile_one(spec: dict, existing: list[dict], apply: bool) -> str:
    """Reconcile a single declared resource. Returns a one-line status."""
    aria_key = spec["aria_key"]
    match = _find_by_metadata_key(existing, aria_key)
    if match:
        # TODO: detect drift; if drifted, patch (or note "would patch" in dry-run)
        return f"matched (aria_key={{aria_key}})"
    if apply:
        # TODO: create the resource via vendor API
        # res = vendor.Resource.create(..., metadata={{"aria_key": aria_key}})
        # return f"created (aria_key={{aria_key}}, id={{res.id}})"
        return f"created stub (aria_key={{aria_key}}) -- TODO: wire vendor API"
    return f"would create (aria_key={{aria_key}})"


def _emit_splat(*args, **kwargs):
    """No-op in standalone mode. Aria Code hosted version logs to CertusOrdo splat chain."""
    pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile YAML → {vendor}.")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--apply", action="store_true", help="Apply changes (default = dry-run)")
    ap.add_argument("--prod", action="store_true", help="Required if YAML config mode=live")
    args = ap.parse_args()

    cfg = _load_config(Path(args.config))
    cfg_mode = (cfg.get("mode") or "test").lower()

    api_key = _resolve_api_key(cfg_mode, args.prod)
    # TODO: pass api_key to the vendor SDK init
    # vendor.api_key = api_key

    print(f"# {name} · mode={{cfg_mode}} · apply={{args.apply}}")
    print(f"# config: {{args.config}}")
    print()

    existing = _list_existing_resources()
    print(f"# {{len(existing)}} existing resources in {vendor}")
    print()

    summary = []
    for spec in cfg.get("resources", []):
        status = _reconcile_one(spec, existing, args.apply)
        summary.append(f"  resource {{spec.get('aria_key','?')}}: {{status}}")

    print("# Reconciliation summary:")
    for line in summary:
        print(line)

    _emit_splat({{
        "mode": cfg_mode,
        "apply": args.apply,
        "resources_count": len(cfg.get("resources", [])),
        "summary": summary,
    }})
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def render_yaml(name: str, snake_name: str, vendor: str) -> str:
    return f"""# {snake_name}_config.yaml — declared catalog reconciled to {vendor}.
#
# Pattern (see ../BUILDER_GUIDE.md for full reference):
#   - Each resource has an `aria_key` (your stable internal id, used as match key)
#   - Re-runs match by aria_key → no duplicates
#
# Mode:
#   `test` uses {vendor.upper()}_API_KEY_TEST
#   `live` uses {vendor.upper()}_API_KEY_LIVE — and requires --prod CLI flag

mode: test

resources:
  # ── Example resource ────────────────────────────────────────────────
  - aria_key: my_first_resource
    # TODO: add vendor-specific fields here

  # Add more resources. Each new one = new aria_key. Idempotent on re-run.
"""


def render_requirements(vendor: str) -> str:
    return f"""# Common deps for aria-skills reconcilers
PyYAML>=6.0
httpx>=0.24

# TODO: add the {vendor} SDK if one exists, e.g.:
# {vendor}>=1.0.0
"""


def _default_manifest_description(name: str, vendor: str) -> str:
    """Default cross-harness description for scaffolded skills.

    Mirrors the YAML frontmatter description in render_skill_md() so all
    four manifests stay in sync. After scaffolding, the builder edits both
    SKILL.md and the manifest files when they specialize the resource_type.
    """
    return (
        f"Reconcile <resource_type> from a declared YAML catalog to {vendor} via the API. "
        f"Idempotent. dry-run by default, --apply hits the API, --prod required for live mode. "
        f"Use when the user says 'sync {vendor}', 'update <resource>', or before any {vendor} change ships."
    )


def _default_args_schema() -> dict:
    """Canonical 3-arg shape for scaffolded reconciler skills (config / apply / prod).

    Builders who add extra flags must hand-edit the manifests in lockstep
    with the python script's argparse block.
    """
    return {
        "config": {"type": "string", "description": "Path to the YAML catalog."},
        "apply": {
            "type": "boolean",
            "description": "Apply changes against the vendor API. Defaults to dry-run.",
            "default": False,
        },
        "prod": {
            "type": "boolean",
            "description": "Required for live mode; refuses to hit the live API without it.",
            "default": False,
        },
    }


def render_openai_manifest(name: str, vendor: str) -> str:
    fn_name = name.replace("-", "_")
    description = _default_manifest_description(name, vendor)
    obj = {
        "type": "function",
        "function": {
            "name": fn_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": _default_args_schema(),
                "required": [],
            },
        },
        "_aria_meta": {
            "harness": "openai",
            "compatible_with": ["openai-gpt", "openai-codex", "xai-grok"],
            "skill_name": name,
            "source_of_truth": "../SKILL.md",
        },
    }
    return json.dumps(obj, indent=2) + "\n"


def render_gemini_manifest(name: str, vendor: str) -> str:
    fn_name = name.replace("-", "_")
    description = _default_manifest_description(name, vendor)
    obj = {
        "function_declarations": [
            {
                "name": fn_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": _default_args_schema(),
                    "required": [],
                },
            }
        ],
        "_aria_meta": {
            "harness": "google-gemini",
            "compatible_with": ["gemini-1.5", "gemini-2.x"],
            "skill_name": name,
            "source_of_truth": "../SKILL.md",
        },
    }
    return json.dumps(obj, indent=2) + "\n"


def render_mcp_manifest(name: str, vendor: str) -> str:
    description = _default_manifest_description(name, vendor)
    obj = {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": _default_args_schema(),
            "required": [],
            "additionalProperties": False,
        },
        "_aria_meta": {
            "harness": "mcp",
            "spec_version": "2024-11-05",
            "compatible_with": [
                "claude-desktop",
                "claude-code",
                "cursor",
                "any-mcp-aware-client",
            ],
            "source_of_truth": "../SKILL.md",
        },
    }
    return json.dumps(obj, indent=2) + "\n"


def render_manifest_readme(name: str) -> str:
    return f"""# {name} — Cross-Harness Manifests

This directory holds discovery manifests for harnesses other than Claude Code. The Claude Code manifest is `../SKILL.md`. All four describe the SAME script — they're just discovery glue.

## Manifest matrix

| Harness | File | Format |
|---|---|---|
| Claude Code | `../SKILL.md` | YAML frontmatter |
| OpenAI / Codex / xAI Grok | `openai.json` | OpenAI Tool/Function schema |
| Google Gemini | `gemini.json` | `function_declarations` |
| MCP | `mcp.json` | MCP tool spec (2024-11-05) |

## Invocation contract

The harness adapter translates harness-side function arguments → CLI flags → invokes `../{name.replace('-', '_')}.py`.

When you add a CLI flag in the script, mirror it in all three manifests (the file shapes are nearly identical — same JSON Schema body, different wrappers).

## Cross-references

- `../SKILL.md` — Claude Code manifest, source of behavior truth
- Path A pattern doc: `/opt/aria/v4/sprints/055_master_todo_triage/reference/platform_agnostic_skills.md`
- Pilot reference: `aria-skills-repo/stripe-sync/manifest/`
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new aria-skills skill.")
    ap.add_argument(
        "name", help="Skill name (lowercase, hyphen-separated). E.g. linear-sync"
    )
    ap.add_argument(
        "--vendor", help="Vendor name (defaults to first hyphen-segment of skill name)"
    )
    ap.add_argument(
        "--dest", default=".", help="Destination directory (defaults to cwd)"
    )
    ap.add_argument("--force", action="store_true", help="Overwrite existing directory")
    args = ap.parse_args()

    name = validate_name(args.name)
    snake_name = snake(name)
    vendor = args.vendor or vendor_default(name)
    dest = Path(args.dest).expanduser().resolve() / name

    if dest.exists() and not args.force:
        sys.stderr.write(f"FATAL: {dest} already exists. Pass --force to overwrite.\n")
        return 2

    dest.mkdir(parents=True, exist_ok=True)
    (dest / "manifest").mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": render_readme(name, snake_name, vendor),
        "SKILL.md": render_skill_md(name, snake_name, vendor),
        f"{snake_name}.py": render_script(name, snake_name, vendor),
        f"{snake_name}_config.yaml": render_yaml(name, snake_name, vendor),
        "requirements.txt": render_requirements(vendor),
        "manifest/openai.json": render_openai_manifest(name, vendor),
        "manifest/gemini.json": render_gemini_manifest(name, vendor),
        "manifest/mcp.json": render_mcp_manifest(name, vendor),
        "manifest/README.md": render_manifest_readme(name),
    }
    for filename, content in files.items():
        (dest / filename).write_text(content)

    # Make the Python script executable
    (dest / f"{snake_name}.py").chmod(0o755)

    print(f"✓ Scaffolded skill at {dest}/")
    print()
    print("Files created:")
    for filename in files:
        print(f"  · {filename}")
    print()
    print("Next steps:")
    print(f"  1. cd {dest}")
    print(f"  2. Edit {snake_name}_config.yaml — declare your resources")
    print(f"  3. Edit {snake_name}.py — replace the TODO stubs with vendor SDK calls")
    print(
        f"  4. If you add CLI flags, mirror them in manifest/openai.json, gemini.json, mcp.json"
    )
    print(f"  5. pip install -r requirements.txt")
    print(f"  6. python3 {snake_name}.py    # dry-run to confirm the scaffold runs")
    print()
    print("Then read ../BUILDER_GUIDE.md for the patterns.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
