---
name: question-economy
description: Near session end, when you're winding down, or on request, analyze the questions Claude asked you and your answers — then distill each answer into a standing default written to memory, so Claude asks fewer (only genuinely novel) questions over time. Tracks a per-session question-rate metric so the decline is measurable. Use when you say "wrap up", "winding down", "what did you learn about working with me", "question economy", or proactively at session close.
---

# question-economy

Every question Claude asks has a cost — it interrupts your flow (especially a focus-stealing modal in the middle of voice dictation). And every answer you give is a latent **standing default**: next time the same situation arises, Claude should already know the answer and just proceed, stating the choice instead of asking.

**The goal is not zero questions — it's zero *avoidable* questions.** Genuinely novel decisions that need your judgment still deserve a question. What should decay toward zero is re-asking things you've effectively already answered. Run this every session and the avoidable-question count should trend down, session over session.

## Steps

1. **Extract the question→answer ledger.** Run the extractor on this session's transcript:
   ```sh
   python3 question_economy.py --print-trend
   ```
   It prints JSON: `hard_questions` (AskUserQuestion modals — the costliest), `soft_questions` (an assistant turn ending in `?` + your next reply), `counts`, and `trend` (the last 8 sessions' question rates). It also appends one metric row to `question_economy_log.jsonl` in your memory dir.

2. **Classify each pair.** For every question→answer, decide:
   - **Standing default** — your answer generalizes ("whenever X, do Y"). → becomes a memory.
   - **One-off** — context-specific, doesn't generalize. → skip.
   - **Avoidable** — Claude *could* have inferred the answer from existing memory or a sensible default and shouldn't have asked. → flag it; this is the number to drive down.
   - **Good question** — genuinely needed your judgment. → leave it; not every question is waste.

3. **Write the new defaults to memory.** For each standing default, write a memory entry that leads with the generalized rule (not the one instance), followed by **Why:** and **How to apply:** lines. If your setup curates memories through an inbox/review step, write proposals there rather than straight to live memory. Check your existing memories first — update a related one instead of duplicating.

4. **Report the economy.** One short readout:
   - This session: N hard + M soft questions; **K were avoidable** (and why).
   - New standing defaults learned → so Claude won't ask these again: (list).
   - The trend: this session vs the last few — is the avoidable count actually falling?
   - If the rate is NOT falling, say so plainly and name what's still being re-asked — a signal a memory isn't being honored or is mis-scoped.

## The loop it serves
Question asked → you answer → answer distilled to a standing default → memory → next session Claude applies the default instead of asking → avoidable-question count falls. The `question_economy_log.jsonl` metric is the proof; the memories are the mechanism. Over many sessions this converges Claude onto your working style, so the conversation is about novel decisions, not re-litigating known preferences.

## Notes
- Hard (modal) questions are weighted heaviest — a modal mid-dictation is the worst interruption. If the log shows hard questions not falling, that's the priority fix.
- Distinguish *workflow* defaults (how you want work done) from *technical* defaults (architecture/tooling choices you keep making the same way) — capture both, tagged, so the memories stay findable.
- Complements broad session-close memory capture; this skill is narrow on purpose: the Q&A ledger and the question-rate metric.

## Requirements
Python 3.9+. No dependencies — standard library only. Reads Claude Code session transcripts from `~/.claude/projects/*/`.
