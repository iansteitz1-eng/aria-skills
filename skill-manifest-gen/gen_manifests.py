#!/usr/bin/env python3
"""gen_manifests.py — generate cross-harness discovery manifests for a skill.

Every aria-skill ships a `manifest/` dir so the SAME executable is discoverable
from harnesses other than Claude Code (which reads `SKILL.md`):

  manifest/openai.json  — OpenAI / Codex / xAI Grok  (Tool/Function schema)
  manifest/gemini.json  — Google Gemini              (function_declarations)
  manifest/mcp.json     — MCP                         (tool spec 2024-11-05)
  manifest/README.md    — the matrix + invocation contract

All four are DERIVED, deterministically, from two sources of truth:
  • SKILL.md frontmatter   → name + description
  • the skill's script     → argparse options → the input parameter schema

So manifests can never drift from the skill: regenerate any time. This is the
"blanket" fix — run with --all to cover every skill in the repo, and
`--check` to fail (CI) if any skill is missing/stale.

Usage:
  gen_manifests.py --skill-dir safe-restart            # one skill
  gen_manifests.py --all --repo-root .                 # every skill in the repo
  gen_manifests.py --all --check                       # report missing/stale, write nothing (exit 2)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MCP_SPEC = "2024-11-05"
MCP_COMPAT = ["claude-desktop", "claude-code", "cursor", "any-mcp-aware-client"]


# ── source-of-truth readers ──────────────────────────────────────────────────
def read_frontmatter(skill_dir: Path) -> dict:
    md = (skill_dir / "SKILL.md").read_text()
    if not md.startswith("---"):
        raise ValueError("SKILL.md has no frontmatter")
    end = md.find("\n---", 3)
    fm = md[3:end]
    fields = {}
    key = None
    for line in fm.splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            fields[key] = m.group(2).strip()
    # strip wrapping quotes on description
    for k in fields:
        v = fields[k]
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            fields[k] = v[1:-1]
    return fields


def find_script(skill_dir: Path) -> Path | None:
    # prefer a .py, then .sh; skip dunder/helpers named like tests
    cands = sorted(skill_dir.glob("*.py")) + sorted(skill_dir.glob("*.sh"))
    cands = [c for c in cands if not c.name.startswith("_") and "test" not in c.name.lower()]
    return cands[0] if cands else (sorted(skill_dir.glob("*.py")) or [None])[0]


_ADD_ARG = re.compile(r"add_argument\s*\(", re.S)


def parse_argparse(script: Path) -> tuple[dict, list]:
    """Best-effort: extract {param: schema} + required[] from argparse calls.
    Handles the simple, multi-line add_argument style used across this repo."""
    if not script or script.suffix != ".py":
        return {}, []
    src = script.read_text()
    props: dict = {}
    required: list = []
    for m in _ADD_ARG.finditer(src):
        # capture the parenthesized call (balanced enough for our style)
        i = m.end()
        depth = 1
        buf = []
        while i < len(src) and depth:
            ch = src[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            buf.append(ch)
            i += 1
        call = "".join(buf)

        # the option/positional name = first string literal
        nm = re.search(r"""^\s*['"]([^'"]+)['"]""", call)
        if not nm:
            continue
        flag = nm.group(1)
        is_opt = flag.startswith("-")
        name = flag.lstrip("-").replace("-", "_")
        if not name or name in ("h", "help"):
            continue

        # type
        if re.search(r"action\s*=\s*['\"]store_(true|false)['\"]", call):
            typ = "boolean"
        elif re.search(r"type\s*=\s*int\b", call):
            typ = "integer"
        elif re.search(r"type\s*=\s*float\b", call):
            typ = "number"
        else:
            typ = "string"

        # help → description
        hm = re.search(r"help\s*=\s*\(?\s*['\"](.+?)['\"]\s*\)?(?:,|$)", call, re.S)
        desc = re.sub(r"\s+", " ", hm.group(1)).strip() if hm else ""

        prop = {"type": typ}
        if desc:
            prop["description"] = desc

        # default
        dm = re.search(r"default\s*=\s*([^,\)]+)", call)
        if dm and "store_true" not in call and "store_false" not in call:
            dv = dm.group(1).strip()
            if typ == "boolean":
                prop["default"] = dv == "True"
            elif typ in ("integer", "number") and re.match(r"^-?\d", dv):
                prop["default"] = json.loads(dv) if dv.replace(".", "", 1).lstrip("-").isdigit() else dv
            elif dv.startswith(("'", '"')):
                prop["default"] = dv.strip("'\"")
        if typ == "boolean" and "default" not in prop:
            prop["default"] = "store_false" in call  # store_true defaults False

        props[name] = prop

        # required: explicit required=True, OR a positional (no leading dash, no nargs='?')
        if re.search(r"required\s*=\s*True", call):
            required.append(name)
        elif not is_opt and not re.search(r"nargs\s*=\s*['\"]\?['\"]", call):
            required.append(name)

    return props, required


# ── emitters ──────────────────────────────────────────────────────────────────
def fn_name(skill_name: str) -> str:
    return skill_name.replace("-", "_")


def build(skill_name: str, desc: str, props: dict, required: list):
    schema = {"type": "object", "properties": props, "required": required}
    openai = {"type": "function", "function": {
        "name": fn_name(skill_name), "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}
    gemini = {"function_declarations": [{
        "name": fn_name(skill_name), "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}],
        "_aria_meta": {"harness": "google-gemini", "source_of_truth": "../SKILL.md"}}
    mcp = {"name": skill_name, "description": desc,
           "inputSchema": {**schema, "additionalProperties": False},
           "_aria_meta": {"harness": "mcp", "spec_version": MCP_SPEC,
                          "compatible_with": MCP_COMPAT, "source_of_truth": "../SKILL.md"}}
    return openai, gemini, mcp


README_TMPL = """# {name} — Cross-Harness Manifests

This directory holds discovery manifests for harnesses other than Claude Code
(which reads `../SKILL.md`). All describe the SAME executable — discovery glue,
not behavior. Generated by `skill-manifest-gen` from `../SKILL.md` + the script's
argparse; regenerate any time (never hand-edit).

| Harness | File | Format |
|---|---|---|
| Claude Code (CLI) | `../SKILL.md` | YAML frontmatter |
| OpenAI / Codex / xAI Grok | `openai.json` | OpenAI Tool/Function schema |
| Google Gemini | `gemini.json` | `function_declarations` |
| MCP | `mcp.json` | MCP tool spec ({spec}) |

The script is the source of behavior truth; the harness adapter translates
function arguments → CLI flags → invokes the script.
"""


def write_manifest(skill_dir: Path, check: bool, force: bool = False) -> tuple[str, bool]:
    """Returns (status, ok). status in {written, ok, missing, stale, skipped, error}.

    In write mode, an EXISTING manifest/ is left untouched unless force=True —
    existing manifests are often hand-tuned beyond what argparse exposes, so a
    blanket --all never clobbers curated work. Use --check to detect drift, and
    --force only to deliberately overwrite."""
    try:
        fm = read_frontmatter(skill_dir)
        name = fm.get("name") or skill_dir.name
        desc = fm.get("description", "")
        if len(desc) < 40:
            return (f"{skill_dir.name}: description too short", False)
        props, required = parse_argparse(find_script(skill_dir))
        openai, gemini, mcp = build(name, desc, props, required)
        mdir = skill_dir / "manifest"
        targets = {"openai.json": openai, "gemini.json": gemini, "mcp.json": mcp}

        if check:
            if not mdir.is_dir():
                return (f"{skill_dir.name}: MISSING manifest/", False)
            for fn, obj in targets.items():
                p = mdir / fn
                if not p.exists():
                    return (f"{skill_dir.name}: missing manifest/{fn}", False)
                cur = json.loads(p.read_text())
                if cur.get("description", cur.get("function", {}).get("description")) != desc \
                   and fn != "gemini.json":
                    return (f"{skill_dir.name}: {fn} description STALE vs SKILL.md", False)
            return (f"{skill_dir.name}: ok", True)

        if mdir.is_dir() and not force:
            return (f"{skill_dir.name}: manifest exists — skipped (--force to overwrite)", True)
        mdir.mkdir(exist_ok=True)
        for fn, obj in targets.items():
            (mdir / fn).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
        (mdir / "README.md").write_text(README_TMPL.format(name=name, spec=MCP_SPEC))
        return (f"{skill_dir.name}: wrote {len(targets)} manifests ({len(props)} params)", True)
    except Exception as e:
        return (f"{skill_dir.name}: ERROR {type(e).__name__}: {e}", False)


def main():
    ap = argparse.ArgumentParser(description="Generate cross-harness manifests for a skill (or all).")
    ap.add_argument("--skill-dir", help="path to one skill dir")
    ap.add_argument("--all", action="store_true", help="every skill dir under --repo-root")
    ap.add_argument("--repo-root", default=".", help="repo root for --all (default .)")
    ap.add_argument("--check", action="store_true", help="report missing/stale, write nothing (exit 2 if any)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing manifest/ (default: skip existing)")
    args = ap.parse_args()

    dirs = []
    if args.all:
        root = Path(args.repo_root)
        dirs = sorted([d for d in root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()])
    elif args.skill_dir:
        dirs = [Path(args.skill_dir)]
    else:
        print("ERROR: pass --skill-dir <dir> or --all"); return 1

    bad = 0
    for d in dirs:
        status, ok = write_manifest(d, args.check, args.force)
        print(("  ✓ " if ok else "  ✗ ") + status)
        if not ok:
            bad += 1
    print(f"\n{len(dirs)} skill(s); {bad} {'need attention' if args.check else 'failed'}.")
    return 2 if (bad and args.check) else (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
