---
name: call-scrub
description: Pull and analyze your ElevenLabs Conversational-AI voice calls — list recent conversations, or scrub one transcript to surface every tool the agent called, the result it got, errors, and timing. The fast way to debug "why did that call misbehave" without replaying audio. BYOK (your own ElevenLabs API key); read-only; stdlib only. Use when the user says "scrub that call", "what happened on the call", "pull the call transcript", "debug the voice call", "what tools fired".
---

# call-scrub

> Debug a voice call by reading what actually happened — tool calls, results, errors — not by re-listening.

```sh
export ELEVENLABS_API_KEY=...                          # BYOK (your key)
python3 call_scrub.py                                  # list recent conversations
python3 call_scrub.py --agent-id agent_xxx --limit 20  # filter to one agent
python3 call_scrub.py --conversation-id conv_xxx       # scrub one call's tool activity
```

## Why

When a Conversational-AI call goes sideways, the audio doesn't tell you *which tool
returned an error* or *where it timed out*. This reads the transcript via the EL API
and lays out every `CALL` and its `->` result, flagging anything that looks like an
error/fail/timeout (⚠). We built it debugging our own voice stack; it's the first
thing to reach for after a bad call.

## Behavior
- **Default / `--list`:** recent conversations (started, id, msgs, duration, status).
- **`--conversation-id`:** the full tool-call/result trail + an error count.
- No API key → clear `FATAL` + exit 2. Read-only; nothing is written.

## Requires
- An ElevenLabs API key (env `ELEVENLABS_API_KEY` or `--api-key`). No Python packages.
