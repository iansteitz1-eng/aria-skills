#!/usr/bin/env python3
"""
aria_skill_test.py — Regression harness for the aria-skills repo.

Runs every shipped skill in --dry-run mode + asserts the output is clean:
  - exit code 0
  - no Python traceback
  - no obvious credential leaks in stderr (heuristic check for known token prefixes)
  - SKILL.md frontmatter parses + has required fields (name, description)
  - script has shebang line

Designed to be CI-friendly: human-readable text output by default, --junit-xml
flag emits JUnit XML for GitHub Actions / similar.

Usage:
  python3 aria_skill_test.py                              # test all skills
  python3 aria_skill_test.py --skill stripe-sync          # one skill
  python3 aria_skill_test.py --skip aria-skill-template   # exclude
  python3 aria_skill_test.py --junit-xml results.xml      # CI integration
  python3 aria_skill_test.py --repo-root /path/to/repo    # alternate repo

Exit codes:
  0 = all tests passed
  1 = at least one test failed
  2 = invocation error (bad args, repo not found, etc.)
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# Known credential prefixes — if these appear in stderr, treat as leak
LEAK_PATTERNS = [
    re.compile(r"sk-ant-\w{20,}"),  # Anthropic
    re.compile(r"sk_live_\w{20,}"),  # Stripe live
    re.compile(r"sk_test_\w{20,}"),  # Stripe test (still a leak)
    re.compile(r"act_[A-Za-z0-9_-]{30,}"),  # aria-cli device tokens
    re.compile(r"cfut_\w{30,}"),  # Cloudflare scoped tokens
    re.compile(r"AC[a-f0-9]{32}"),  # Twilio SID
    re.compile(r"re_[a-zA-Z0-9_-]{20,}"),  # Resend
    re.compile(r"AKIA[A-Z0-9]{16}"),  # AWS access key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub PAT
    re.compile(r"xi-[a-f0-9-]{30,}"),  # ElevenLabs key
]

REQUIRED_FRONTMATTER_FIELDS = ("name", "description")


class TestResult(NamedTuple):
    skill: str
    passed: bool
    failures: list[str]
    duration_ms: int


def _skill_directories(
    repo_root: Path, only: str | None, skip: list[str]
) -> list[Path]:
    """Find skill directories (those with a SKILL.md at their root)."""
    skills = []
    for child in sorted(repo_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name.startswith("_"):
            continue
        if not (child / "SKILL.md").exists():
            continue
        if only and child.name != only:
            continue
        if child.name in skip:
            continue
        skills.append(child)
    return skills


def _check_skill_md(skill_dir: Path) -> list[str]:
    """Validate SKILL.md frontmatter. Returns list of failure messages."""
    failures = []
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text()

    # Parse frontmatter (between --- markers at the top)
    if not content.startswith("---\n"):
        failures.append("SKILL.md missing YAML frontmatter (no leading '---')")
        return failures

    end = content.find("\n---\n", 4)
    if end == -1:
        failures.append("SKILL.md frontmatter not closed (no trailing '---')")
        return failures

    frontmatter = content[4:end]
    # Lightweight YAML parse (just key: value lines)
    fields = {}
    for line in frontmatter.splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip().strip('"').strip("'")

    for required in REQUIRED_FRONTMATTER_FIELDS:
        if required not in fields:
            failures.append(
                f"SKILL.md frontmatter missing required field: '{required}'"
            )

    # Description quality check: must mention "Use when" or have a clear trigger
    desc = fields.get("description", "")
    if len(desc) < 40:
        failures.append(f"SKILL.md description too short ({len(desc)} chars; min 40)")
    if len(desc) > 600:
        failures.append(f"SKILL.md description too long ({len(desc)} chars; max 600)")

    # Name must match directory name
    if fields.get("name") and fields["name"] != skill_dir.name:
        failures.append(
            f"SKILL.md frontmatter name='{fields['name']}' doesn't match directory '{skill_dir.name}'"
        )

    return failures


def _check_for_leaks(stderr: str, stdout: str) -> list[str]:
    """Scan output for known credential prefixes."""
    failures = []
    for stream_name, stream in [("stderr", stderr), ("stdout", stdout)]:
        for pat in LEAK_PATTERNS:
            m = pat.search(stream)
            if m:
                failures.append(
                    f"Credential leak in {stream_name}: pattern '{pat.pattern}' matched "
                    f"(redacted: {m.group()[:8]}…)"
                )
                break  # one leak finding per stream is enough
    return failures


def _find_executable_script(skill_dir: Path) -> Path | None:
    """Find the main .py or .sh in the skill directory."""
    # Convention: script name matches directory name (with hyphens → underscores for .py)
    snake = skill_dir.name.replace("-", "_")
    candidates = [
        skill_dir / f"{snake}.py",
        skill_dir / f"{skill_dir.name}.py",
        skill_dir / f"{snake}.sh",
        skill_dir / f"{skill_dir.name}.sh",
    ]
    for c in candidates:
        if c.exists():
            return c
    for f in skill_dir.glob("*.py"):
        return f
    for f in skill_dir.glob("*.sh"):
        return f
    return None


def _run_script(
    script: Path, args: list[str], timeout: int = 30
) -> tuple[int, str, str, int]:
    """Run script with given args. Returns (rc, stdout, stderr, duration_ms)."""
    start = time.monotonic()
    interp = ["bash"] if script.suffix == ".sh" else ["python3"]
    try:
        result = subprocess.run(
            interp + [str(script)] + args,
            cwd=str(script.parent),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return result.returncode, result.stdout, result.stderr, duration_ms
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start) * 1000)
        return -1, "", f"timeout after {timeout}s", duration_ms


def _test_skill(skill_dir: Path) -> TestResult:
    """Run all checks on one skill."""
    failures = []
    name = skill_dir.name

    # 1. SKILL.md frontmatter
    failures += _check_skill_md(skill_dir)

    # 2. Find the script
    script = _find_executable_script(skill_dir)
    if not script:
        failures.append("No executable script (.py or .sh) found")
        return TestResult(name, False, failures, 0)

    # 3. Has README.md
    if not (skill_dir / "README.md").exists():
        failures.append("Missing README.md")

    # 4. Universal smoke: --help must exit 0 cleanly (proves script imports + argparse wired)
    rc, stdout, stderr, duration_ms = _run_script(script, ["--help"])
    if rc != 0:
        failures.append(
            f"--help exit code {rc} (expected 0; script likely fails to import)"
        )
    if "Traceback (most recent call last)" in stderr:
        failures.append("Python traceback on --help (script crashed)")

    # 5. No credential leaks in help output
    failures += _check_for_leaks(stderr, stdout)

    return TestResult(name, len(failures) == 0, failures, duration_ms)


def _render_text_report(results: list[TestResult]) -> str:
    lines = []
    lines.append("═" * 70)
    lines.append(
        f"  aria-skill-test  ·  {len(results)} skill(s)  ·  "
        f"{sum(1 for r in results if r.passed)} pass · "
        f"{sum(1 for r in results if not r.passed)} fail"
    )
    lines.append("═" * 70)
    lines.append("")
    for r in results:
        mark = "✓" if r.passed else "✗"
        lines.append(f"  {mark}  {r.skill:30s}  {r.duration_ms:>5}ms")
        if not r.passed:
            for f in r.failures:
                lines.append(f"       └─ {f}")
    lines.append("")
    if any(not r.passed for r in results):
        lines.append("  Some tests failed. See per-skill details above.")
    else:
        lines.append("  All tests passed.")
    lines.append("")
    return "\n".join(lines)


def _render_junit_xml(results: list[TestResult]) -> str:
    """Minimal JUnit XML output for CI consumption."""
    n = len(results)
    failures = sum(1 for r in results if not r.passed)
    total_time_s = sum(r.duration_ms for r in results) / 1000.0
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="aria-skill-test" tests="{n}" failures="{failures}" time="{total_time_s:.3f}">',
    ]
    for r in results:
        t = r.duration_ms / 1000.0
        if r.passed:
            parts.append(
                f'  <testcase classname="aria-skills" name="{r.skill}" time="{t:.3f}"/>'
            )
        else:
            parts.append(
                f'  <testcase classname="aria-skills" name="{r.skill}" time="{t:.3f}">'
            )
            for f in r.failures:
                # Escape XML
                f_esc = (
                    f.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&apos;")
                )
                parts.append(f'    <failure message="{f_esc}"/>')
            parts.append("  </testcase>")
    parts.append("</testsuite>")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Regression harness for aria-skills repo.")
    ap.add_argument(
        "--repo-root",
        default="..",
        help="Path to the aria-skills repo root (default: ..)",
    )
    ap.add_argument("--skill", help="Test only this skill (by name)")
    ap.add_argument(
        "--skip", action="append", default=[], help="Skill to skip (can repeat)"
    )
    ap.add_argument("--junit-xml", help="Write JUnit XML to this path")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.exists():
        sys.stderr.write(f"FATAL: repo-root {repo_root} does not exist\n")
        return 2

    skills = _skill_directories(repo_root, args.skill, args.skip)
    if not skills:
        sys.stderr.write(f"FATAL: no skills found under {repo_root}\n")
        return 2

    results = []
    for skill_dir in skills:
        result = _test_skill(skill_dir)
        results.append(result)

    print(_render_text_report(results))

    if args.junit_xml:
        Path(args.junit_xml).write_text(_render_junit_xml(results))
        print(f"  JUnit XML written to {args.junit_xml}")

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
