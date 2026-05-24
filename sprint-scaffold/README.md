# sprint-scaffold

> **The meta-skill.** Scaffold a new sprint folder with the Filing Cabinet `spec_charter.md` + Flowstate `pr-review.md` patterns + reference/sql/ subdirs.

If you're shipping multi-day projects (especially multi-terminal in parallel), this skill drops a working skeleton that enforces clean ownership boundaries up front + makes every shipped item auditable.

## What it scaffolds

```
sprints/NNN_slug/
├── spec_charter.md                    ← Filing Cabinet pattern
├── .claude/agents/pr-review.md        ← Flowstate pattern (5-dim rubric)
├── HANDOFF_T1_TO_T2.md                ← Inter-terminal coordination template
├── reference/                          ← Source docs that fed the sprint
└── sql/                                ← Schema migrations
```

## When to use

- Starting a multi-day project (3+ items)
- Multi-terminal / multi-contributor work (the HANDOFF template is the file-lock contract)
- Anything where you want every shipped item to have a memory file with a Flowstate self-review

## The patterns

### Filing Cabinet `spec_charter.md`
- Mission (1-2 sentences)
- Stakeholders (Owner / T1 / T2 / Informed)
- Constraints (calendar, file locks, doctrine)
- Scope (P0 / P1 / P2 / Out of scope)
- Risks (with mitigations)
- Open questions (numbered)
- v1 acceptance criteria (checkable)
- Versioning protocol (copy to v2 if scope changes; never edit v1 in place)
- Tools/skills reuse log
- New skills emerging

### Flowstate `pr-review.md` (5-dim rubric per item)
1. Correctness
2. Security
3. Test coverage
4. Doctrine alignment
5. Follow-ups

Each item gets a self-review block in its memory file before shipping.

## See also

- **[SKILL.md](./SKILL.md)** — Claude Code skill manifest
- **[templates/](./templates/)** — copy-paste-ready templates for each file

## License

Apache 2.0
