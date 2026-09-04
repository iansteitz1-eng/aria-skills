---
name: sprint-scaffold
description: Scaffold a new sprint folder with the Filing Cabinet spec_charter.md + Flowstate .claude/agents/pr-review.md + reference/sql/ subdirs. Use when starting a new sprint (e.g. "open sprint 021", "start a sprint for X", "new sprint folder"). Drops a working skeleton in ./sprints/NNN_slug/ with the load-bearing files pre-filled so every shipped item gets an audit-trail home. Validated over a two-terminal sprint that shipped 20+ items under this pattern.
---

# Sprint Scaffold

Apply the Filing Cabinet product `spec_charter.md` template + the Flowstate product `.claude/agents/pr-review.md` template to **internal Aria sprints** (not just customer-facing project tarballs). Closes the audit-trail loop: every sprint has a mission, scope, risks, acceptance criteria, and a review rubric for everything shipped under it.

This skill emerged from Sprint 020 (`two_terminal_push`, 2026-05-23) where T1 and T2 shipped 11 items in parallel with zero conflicts because the sprint folder enforced clean ownership boundaries up front.

## When to use

- User says "open sprint NNN" / "start sprint for X" / "new sprint" / "scaffold a sprint" / "let's sprint on Y"
- You're about to start work that spans 3+ items + multiple sessions and should have one canonical home
- Multiple terminals or contributors need a file-lock contract (this skill ships HANDOFF_*.md templates)

## Steps

`./sprint_scaffold.sh NNN slug [--dest DIR]` runs steps 2-5 in one shot; the steps below are what it does.

1. **Pick the sprint number.** Look at `./sprints/` (or your `--dest`) — find the highest existing NNN and add 1. Slug is lowercase-hyphenated.

   ```sh
   ls ./sprints/ | sort -n | tail -3
   ```

2. **Create the folder + subdirs:**

   ```sh
   SPRINT=021_<slug>
   mkdir -p ./sprints/$SPRINT/{reference,sql,.claude/agents}
   ```

3. **Write spec_charter.md** (Filing Cabinet pattern). Use the template below — pre-fill what you know, leave the rest as `TODO`:

   ```markdown
   # Sprint NNN — <Title> · spec_charter v1

   **Opened:** YYYY-MM-DD
   **Closes:** YYYY-MM-DD (target)
   **Method:** Filing Cabinet spec_charter pattern + Flowstate pr-review pattern

   ## 1. Mission
   <1-2 sentences. What changes if this sprint succeeds?>

   ## 2. Stakeholders
   | Role | Person | Responsibility |
   |---|---|---|
   | Owner | <owner> | Final call |
   | T1 | Claude | <lane> |
   | T2 | (if applicable) | <lane> |
   | Informed | <teammate> | <when needed> |

   ## 3. Constraints
   1. <calendar / doctrine / file-lock / restart / etc.>

   ## 4. Scope
   ### P0 (must ship)
   | # | Item | Owner | Status |
   ### P1 (close if possible)
   ### P2 (stretch)
   ### Out of scope (defensibly deferable)

   ## 5. Risks
   | Risk | Likelihood | Mitigation |

   ## 6. Open questions

   ## 7. v1 acceptance criteria
   - [ ] <criterion>

   ## 8. Versioning
   Per Filing Cabinet versioning protocol: copy to spec_charter_v2.md when scope changes. Never edit v1 in place.

   ## 9. Tools/skills used (reuse log)
   | Tool/skill | Used for | New or existing |

   ## 10. New skill emerging (if any)
   ```

4. **Write .claude/agents/pr-review.md** (Flowstate pattern). Use this 5-dim rubric template:

   ```markdown
   # Sprint NNN PR-Review Rubric (Flowstate pattern, sprint-local)

   Apply to every item shipped before marking done.

   ## The 5 dimensions
   ### 1. Correctness — does it do what the charter §4 said?
   ### 2. Security — auth gates? secrets? injection?
   ### 3. Test coverage — smoke trace saved?
   ### 4. Doctrine alignment — which feedback_* rules apply?
   ### 5. Follow-ups — what was deferred?

   ## Output format
   ```
   ## Sprint NNN self-review — <item slug>
   **1. Correctness:**  ✅ / ⚠️ / ❌  — <one-line evidence>
   **2. Security:**     ✅ / ⚠️ / ❌
   **3. Test coverage:** ✅ / ⚠️ / ❌
   **4. Doctrine:**     ✅ / ⚠️ / ❌
   **5. Follow-ups:**   <ops_log ids, skill ideas>
   **Verdict:** APPROVE / REQUEST CHANGES / RETHINK
   **Smoke command:** <copy-paste-able>
   ```
   ```

5. **Drop a HANDOFF template** (if multi-terminal):

   ```sh
   touch ./sprints/$SPRINT/HANDOFF_T1_TO_T2.md
   ```

   Pre-fill with the file-lock contract + route-prefix partition pattern from the Sprint 020 handoff.

6. **Insert a parent row in your ops log** (example against our `v4_ops_log` table):

   ```sql
   INSERT INTO v4_ops_log (priority, status, category, area, title, detail, owner, purpose) VALUES
   ('P0','in_progress','product','<area>',
    'Sprint NNN — <title>',
    'Charter at ./sprints/NNN_slug/spec_charter.md',
    'claude','sprint_NNN');
   ```

   Subsequent items in this sprint tag `purpose='sprint_NNN'` for clean filtering.

7. **Report.** Print the absolute path to the new sprint folder + the next 1-3 items to populate.

## Folder layout this skill creates

```
./sprints/NNN_slug/
├── spec_charter.md             ← Filing Cabinet pattern
├── .claude/agents/pr-review.md ← Flowstate pattern
├── HANDOFF_T1_TO_T2.md         ← Inter-terminal coordination (template)
├── reference/                  ← Source docs that fed the sprint
└── sql/                        ← Schema migrations this sprint introduces
```

## Notes

- This skill was promoted from Sprint 020 (`two_terminal_push`, 2026-05-23) where the pattern proved itself shipping 11 items in parallel between T1 and T2 with zero file collisions.
- The `spec_charter.md` template here is the same one that ships at the root of every Filing Cabinet customer tarball, just retargeted at our internal sprint context. The Mission/Stakeholders/Constraints/Risks/Acceptance pattern works identically for both.
- The `pr-review.md` template here matches the Flowstate scaffold pack — `.claude/agents/pr-review.md` at sprint root means Claude Code agents picked up later in the sprint will auto-honor the rubric.
- Charter versioning rule (never edit v1 in place; copy to v2 if scope changes) is load-bearing. Audit trail needs the WHY of pivots.
- Pair with your session-close routine — at sprint close, the per-item memories that piled up should each have a `## Sprint NNN self-review` block already.
- Cross-link sprint memories with `[[other-slug]]` for navigability.
