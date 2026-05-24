# Sprint NNN — <Title> · spec_charter v1

**Opened:** YYYY-MM-DD
**Closes:** YYYY-MM-DD (target)
**Method:** Filing Cabinet spec_charter pattern + Flowstate pr-review pattern + sprint-scaffold skill

---

## 1. Mission

<One or two sentences. What measurable thing changes if this sprint succeeds?>

## 2. Stakeholders

| Role | Person | Responsibility |
|---|---|---|
| Owner | Ian | Final call on every item; external-action items |
| Terminal 1 | Claude (primary) | <lane> |
| Terminal 2 | Claude (parallel — if applicable) | <lane> |
| Informed | Stephen / Brandon / etc. | <when their domain is touched> |

## 3. Constraints

1. **Calendar:** T-<N> days to <date>.
2. **File-lock contract** — partition listed in `HANDOFF_T1_TO_T2.md` if multi-terminal.
3. **Doctrine compliance:** [[feedback_*]] rules that bind this sprint.
4. **Restart contract:** which services + which guards (e.g. /admin/active_sessions for voice).

## 4. Scope

### P0 (must ship before closes-date)
| # | Item | Owner | Status |
|---|---|---|---|

### P1 (close if possible)
| # | Item | Owner |
|---|---|---|

### P2 (stretch only)
| # | Item | Owner |
|---|---|---|

### Out of scope (defensibly deferable past closes-date)
- <item with one-line why>

## 5. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|

## 6. Open questions

1. <unresolved item>

## 7. v1 acceptance criteria

- [ ] All P0 items shipped or explicitly deferred with doctrine justification
- [ ] Each shipped item has a memory file in `/root/.claude/projects/-root/memory/`
- [ ] Each shipped item self-reviewed against `.claude/agents/pr-review.md`
- [ ] `v4_ops_log` reflects every item's status
- [ ] Smoke trace saved in each item's memory file
- [ ] No regressions on `aria-status` skill output

## 8. Versioning

Per Filing Cabinet versioning protocol: when scope changes materially, copy this file to `spec_charter_v2.md` rather than editing v1 in place. Both files stay on disk so the audit trail of WHY we changed direction survives.

This is v1.

## 9. Tools/skills used (reuse log)

| Tool/skill | Used for | New or existing |
|---|---|---|

## 10. New skill / tool emerging

<If a pattern emerges worth promoting to ~/.claude/skills/, note it here.>
