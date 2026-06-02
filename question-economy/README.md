# question-economy

> **Claude learns your answers so it stops re-asking. Fewer interruptions, every session.**

Every question an AI assistant asks costs you a context-switch — worst of all a focus-stealing modal in the middle of voice dictation. And every answer you give is a *standing default* the assistant should remember. This skill mines each session's question→answer ledger, turns the generalizable answers into memories, and tracks the question rate so it visibly **declines over time**.

```sh
# At session close:
python3 question_economy.py --print-trend
# → hard/soft question counts, the Q&A ledger, and the last 8 sessions' trend
```

The goal isn't *zero* questions — it's zero **avoidable** ones. Novel decisions still earn a question; what decays is re-litigating preferences you've already stated.

## What it does

- **Extracts** every question Claude asked you this session — `hard` (focus-stealing AskUserQuestion modals, weighted heaviest) and `soft` (a prose turn ending in `?` + your reply).
- **Distills** each generalizable answer into a memory ("whenever X → do Y") so Claude applies it next time instead of asking.
- **Measures** the decline: one metric row per session in `question_economy_log.jsonl`. If the avoidable-question rate stops falling, the skill is told to name what's still being re-asked — a sign a memory is missing or mis-scoped.

## Install

Drop the `question-economy/` folder into your Claude Code skills directory (`~/.claude/skills/`). Python 3.9+, standard library only — no dependencies.

## The loop

```
question asked → you answer → answer → memory (standing default)
      ↑                                        ↓
   fewer next time  ←  Claude applies it instead of asking
```

Run it every session and the conversation converges onto novel decisions, not known preferences.

---
Part of [aria-skills](https://github.com/iansteitz1-eng/aria-skills) · Powered by [Aria Code](https://staycool.ai/aria-code).
