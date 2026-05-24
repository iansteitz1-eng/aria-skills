#!/usr/bin/env python3
"""
aria_skill_candidates.py — Observer + Gatekeeper for the Aria Builders project.

Scans Claude Code transcript files for recurring patterns that should
maybe become skills. Ranks by the 5-axis rubric:

  Recurrence    (0-3)  How often this pattern shows up
  YAML-shape    (0-3)  How cleanly it maps to declarative reconcile
  Multi-step    (0-3)  Manual-step count if not skill-ified
  Public-value  (0-3)  Generalizes to other stacks vs Aria-internal
  Sovereignty   (0-3)  Touches doctrine/splat/voice (HIGHER = more caution)

Final score = (recurrence + yaml + steps + public) - sovereignty.
  ≥10 : "build now"
  5-9 : "log probe"
  <5  : "skip"

Pure stdlib. Read-only — never writes outside its config. Idempotent.
"""
import argparse
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_TRANSCRIPT_DIR = Path("/root/.claude/projects/-root")
DEFAULT_SKILLS_DIR = Path.home() / ".claude" / "skills"

# Vendor signature → (canonical name, public_value_score, sovereignty_score, yaml_score)
VENDOR_SIGNATURES = {
    "api.linear.app": ("linear", 3, 0, 3),
    "api.notion.com": ("notion", 3, 0, 3),
    "api.figma.com": ("figma", 3, 0, 2),
    "api.airtable.com": ("airtable", 3, 0, 3),
    "api.openai.com": ("openai", 2, 0, 2),
    "api.slack.com": ("slack", 3, 0, 2),
    "api.github.com": ("github", 3, 0, 3),
    "api.vercel.com": ("vercel", 3, 0, 3),
    "api.posthog.com": ("posthog", 3, 0, 2),
    "api.intercom.io": ("intercom", 3, 0, 2),
    "api.hubspot.com": ("hubspot", 3, 0, 2),
    "api.openphone.com": ("openphone", 3, 0, 2),
    "api.fly.io": ("fly", 3, 0, 3),
    "api.cloudflare.com": ("cloudflare", 3, 0, 3),  # already have skill
    "api.stripe.com": ("stripe", 3, 0, 3),  # already have skill
    "api.elevenlabs.io": ("elevenlabs", 2, 0, 3),  # already have skill
    "api.resend.com": ("resend", 3, 0, 2),  # used via email-send
    "api.twilio.com": ("twilio", 3, 0, 2),
    "api.anthropic.com": ("anthropic", 2, 1, 1),
}

# Patterns that flag sovereignty cost
SOVEREIGNTY_FLAGS = [
    re.compile(r"v4_splat_log|splat_id|locus|sacred|doctrine|peacock|xtts|sovereign"),
]


def _existing_skill_names(skills_dir: Path) -> set[str]:
    if not skills_dir.exists():
        return set()
    return {d.name for d in skills_dir.iterdir() if d.is_dir()}


def _iter_bash_commands(transcript_path: Path):
    """Yield (timestamp, command) for every Bash tool_use in the transcript."""
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") or {}
                content = msg.get("content") or []
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and block.get("name") == "Bash":
                        cmd = (block.get("input") or {}).get("command", "")
                        yield rec.get("timestamp", ""), cmd
    except Exception:
        return


def _extract_signals(commands):
    """Cluster commands by vendor signature + count multi-step recurrences."""
    vendor_hits = Counter()  # vendor_key -> count
    vendor_samples = defaultdict(list)
    sovereignty_hit_count = Counter()
    domain_pattern = re.compile(r"https?://([a-z0-9.-]+)")
    for _ts, cmd in commands:
        for host in domain_pattern.findall(cmd.lower()):
            for sig, (name, *_) in VENDOR_SIGNATURES.items():
                if sig in host:
                    vendor_hits[name] += 1
                    if len(vendor_samples[name]) < 3:
                        vendor_samples[name].append(cmd[:200])
                    break
        for sov in SOVEREIGNTY_FLAGS:
            if sov.search(cmd):
                # Use first vendor key matched as the carrier; fallback "general"
                sovereignty_hit_count["__any__"] += 1
    return vendor_hits, vendor_samples, sovereignty_hit_count


def _score(name: str, count: int, samples: list[str]) -> dict:
    """Apply 5-axis rubric. Returns dict with score + reasoning."""
    meta = next(
        (
            (n, pv, sov, ys)
            for sig, (n, pv, sov, ys) in VENDOR_SIGNATURES.items()
            if n == name
        ),
        None,
    )
    if not meta:
        return {}
    _, public_score, base_sov, yaml_score = meta

    # Recurrence: 0=<2, 1=2-4, 2=5-9, 3=10+
    if count >= 10:
        rec_score = 3
    elif count >= 5:
        rec_score = 2
    elif count >= 2:
        rec_score = 1
    else:
        rec_score = 0

    # Multi-step heuristic: longer commands or piped chains imply more manual steps
    avg_len = sum(len(s) for s in samples) / max(1, len(samples))
    if avg_len > 200 or any("&&" in s or "|" in s for s in samples):
        steps_score = 3
    elif avg_len > 80:
        steps_score = 2
    else:
        steps_score = 1

    sov_score = base_sov  # vendor-specific baseline
    total = rec_score + yaml_score + steps_score + public_score - sov_score

    verdict = "BUILD NOW" if total >= 10 else "LOG PROBE" if total >= 5 else "SKIP"

    return {
        "name": name,
        "count": count,
        "recurrence": rec_score,
        "yaml_shape": yaml_score,
        "multi_step": steps_score,
        "public_value": public_score,
        "sovereignty": sov_score,
        "total": total,
        "verdict": verdict,
        "samples": samples[:2],
    }


# Explicit vendor → skill mapping (overrides naming heuristic).
# Add entries here when a skill covers a vendor whose name doesn't appear in the skill slug.
VENDOR_TO_SKILL = {
    "resend": "email-send",  # email-send wraps Resend
    "stripe": "stripe-sync",
    "cloudflare": "cloudflare-dns-deploy",
    "elevenlabs": "el-agent-deploy",
    "anthropic": None,  # core LLM API — never a skill, framework-level
    "twilio": None,  # could be a skill candidate; currently no wrapper
}


def scan(
    transcript_dir: Path, skills_dir: Path, limit_files: int | None = None
) -> dict:
    existing = _existing_skill_names(skills_dir)
    # Build a more flexible existing-skill detector
    existing_keys = set()
    for s in existing:
        key = (
            s.replace("-sync", "")
            .replace("-deploy", "")
            .replace("aria-", "")
            .replace("-test", "")
        )
        existing_keys.add(key.split("-")[0])

    files = sorted(transcript_dir.glob("*.jsonl"))
    if limit_files:
        files = files[-limit_files:]

    all_vendor_hits = Counter()
    all_samples = defaultdict(list)
    for tp in files:
        v, s, _sov = _extract_signals(list(_iter_bash_commands(tp)))
        all_vendor_hits.update(v)
        for k, vs in s.items():
            all_samples[k].extend(vs[: 3 - len(all_samples[k])])

    candidates = []
    for name, count in all_vendor_hits.most_common():
        scored = _score(name, count, all_samples[name])
        if not scored:
            continue
        mapped_skill = VENDOR_TO_SKILL.get(name, "__heuristic__")
        if mapped_skill is None:
            # Explicit "never wrap as a skill"
            scored["already_have_skill"] = True
            scored["covered_by"] = "(framework-level / not skill-shaped)"
        elif mapped_skill != "__heuristic__":
            scored["already_have_skill"] = mapped_skill in existing
            scored["covered_by"] = (
                mapped_skill if scored["already_have_skill"] else None
            )
        else:
            scored["already_have_skill"] = (
                name in existing_keys
                or f"{name}-sync" in existing
                or f"{name}-deploy" in existing
            )
        candidates.append(scored)

    return {
        "transcripts_scanned": len(files),
        "existing_skills": sorted(existing),
        "candidates": candidates,
    }


def render_text(result: dict) -> str:
    lines = []
    lines.append("═" * 72)
    lines.append(
        f"  aria-skill-candidates  ·  scanned {result['transcripts_scanned']} transcript(s)"
    )
    lines.append("═" * 72)
    lines.append("")
    lines.append(
        f"  Existing skills ({len(result['existing_skills'])}): "
        + ", ".join(result["existing_skills"][:8])
        + ("..." if len(result["existing_skills"]) > 8 else "")
    )
    lines.append("")

    fresh = [c for c in result["candidates"] if not c["already_have_skill"]]
    existing_hits = [c for c in result["candidates"] if c["already_have_skill"]]

    lines.append("─" * 72)
    lines.append("  RANKED CANDIDATES (no skill yet)")
    lines.append("─" * 72)
    if not fresh:
        lines.append("  (none — no unbuilt vendor patterns above threshold)")
    for c in fresh:
        bar = f"R{c['recurrence']} Y{c['yaml_shape']} M{c['multi_step']} P{c['public_value']} S{c['sovereignty']}"
        lines.append(
            f"  {c['verdict']:<10} score={c['total']:>2}  {c['name']:<14}  count={c['count']:<4}  [{bar}]"
        )
        if c["samples"]:
            sample = c["samples"][0][:120].replace("\n", " ")
            lines.append(
                f"                                                       ↳ {sample}"
            )
    lines.append("")
    if existing_hits:
        lines.append("─" * 72)
        lines.append("  ALREADY HAVE A SKILL FOR (sanity check — still being invoked)")
        lines.append("─" * 72)
        for c in existing_hits[:5]:
            lines.append(f"   ✓  {c['name']:<14}  count={c['count']}")
    lines.append("")
    lines.append(
        "  Legend: R=recurrence Y=yaml-shape M=multi-step P=public-value S=sovereignty-cost"
    )
    lines.append(
        "  Score = R + Y + M + P − S    (≥10 BUILD NOW · 5-9 LOG PROBE · <5 SKIP)"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Identify skill-worthy patterns from transcripts."
    )
    ap.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPT_DIR))
    ap.add_argument("--skills-dir", default=str(DEFAULT_SKILLS_DIR))
    ap.add_argument(
        "--limit-files", type=int, help="Scan only the N most recent transcripts"
    )
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON")
    args = ap.parse_args()

    tdir = Path(args.transcripts)
    if not tdir.exists():
        sys.stderr.write(f"FATAL: transcript dir not found: {tdir}\n")
        return 2

    result = scan(tdir, Path(args.skills_dir), limit_files=args.limit_files)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
