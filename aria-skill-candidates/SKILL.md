---
name: aria-skill-candidates
description: Observer + Gatekeeper for the Aria Builders meta-loop. Scans Claude Code transcripts for recurring vendor-API patterns and ranks them by a 5-axis rubric (recurrence · YAML-shape · multi-step · public-value · sovereignty-cost) to decide which patterns should become new skills. Filters out vendors already covered by an existing skill. Use when the user says "what should I build next", "skill candidates", "where am I repeating myself", "scan transcripts", or weekly as a passive review.
---

# aria-skill-candidates

The "should I build a skill for this?" question, answered automatically.

## Usage

```sh
python3 aria_skill_candidates.py                          # scan all transcripts
python3 aria_skill_candidates.py --limit-files 20         # last 20 sessions only
python3 aria_skill_candidates.py --json                   # machine-readable
```

## The 5-axis rubric

Each candidate scored 0-3 on:

- **Recurrence** — how often the pattern appears
- **YAML-shape** — how cleanly it maps to declarative reconcile
- **Multi-step** — manual-step count if unskilled
- **Public-value** — generalizes vs Aria-internal
- **Sovereignty** — touches doctrine/splat/voice (subtracted)

Score = `R + Y + M + P − S`. ≥10 = BUILD NOW · 5-9 = LOG PROBE · <5 = SKIP.

## License

Apache 2.0
