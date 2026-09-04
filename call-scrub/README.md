# call-scrub

Pull and analyze your **ElevenLabs Conversational-AI** voice calls. List recent
conversations, or scrub one transcript to see every tool the agent called, the
result, errors, and timing — debug a bad call by *reading* it, not replaying audio.

```sh
export ELEVENLABS_API_KEY=...
python3 call_scrub.py --conversation-id conv_xxx
```

BYOK (your own key), read-only, stdlib only. See `SKILL.md`.
