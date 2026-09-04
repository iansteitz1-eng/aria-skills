# Sprint NNN PR-Review Rubric (Flowstate pattern, sprint-local)

Apply this rubric to **every item shipped in this sprint** before marking it done in `v4_ops_log` and the playbook tile. Output goes into the per-item memory file.

## The 5 dimensions

### 1. Correctness
- Does it do what the spec_charter §4 line item said?
- Does it handle empty / null / malformed input cases?
- Does it avoid obvious race conditions (atomic UPDATE patterns for state flips, etc.)?
- Was the end-to-end smoke-tested (not just unit-tested in isolation)?

### 2. Security
- Auth gate present on every new endpoint? (Shared-secret, session cookie, BYOK token — whichever fits the surface.)
- No secrets in repo / logs / templates?
- No SQL injection (parameterized queries everywhere)?
- No path traversal on file-handling endpoints?
- Does the change widen the attack surface? If yes, is the widening justified + documented?

### 3. Test coverage
- Smoke-test command documented in the memory file ("how would a future-me verify this works")?
- For voice / billing / auth changes: a manual smoke + the smoke trace saved?
- For UI changes: which browser + which user flow was clicked through?

### 4. Doctrine alignment
- Which `feedback_*` rules apply, and were they honored?
- For voice items: [[your-voice-doctrine]]
- For UI: [[your-design-rule]]
- For user-data surfaces: [[your-user-scoping-rule]]
- For deploy perimeters: [[who-owns-which-deploy]]
- Always: [[save-a-memory-after-every-push]]

### 5. Follow-ups
- What was deferred and why?
- What new items did we surface that should go into `v4_ops_log`?
- Did this item expose a new skill / tool / pattern worth promoting to `~/.claude/skills/`?

## Output format (per item, copied into memory file)

```
## Sprint NNN self-review — <item slug>

**1. Correctness:**  ✅ / ⚠️ / ❌  — <one-line evidence>
**2. Security:**     ✅ / ⚠️ / ❌  — <one-line evidence>
**3. Test coverage:** ✅ / ⚠️ / ❌  — <one-line evidence>
**4. Doctrine:**     ✅ / ⚠️ / ❌  — <one-line evidence>
**5. Follow-ups:**   <ops_log ids added, skill ideas surfaced>

**Verdict:** APPROVE / REQUEST CHANGES / RETHINK
**Smoke command:** <copy-paste-able verification command>
```

A ⚠️ on Security or Correctness is a blocker; a ⚠️ on Test coverage or Doctrine is a release-note caveat; ⚠️ on Follow-ups is fine.
