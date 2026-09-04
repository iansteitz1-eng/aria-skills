---
name: goal-to-plan
description: Turn a vague/ambiguous ask into an agent-ready plan — the "quality of the brief" discipline an AI-native team runs on. Emits a spec_charter (mission · scope · ONE acceptance criterion · risks) + a ready-to-dispatch lane brief (role · owned files · acceptance · report protocol), chaining the premortem + sprint-scaffold skills. Use when the user says "plan this", "turn this into a brief", "scope this out", "make this agent-ready", "what's the plan for X", "goal to plan", "/goal-to-plan", or before dispatching a lane / starting multi-step work from a fuzzy goal.
---

# Goal → Plan

The bottleneck of an AI-native team is **not the model — it's the quality of the brief.** An agent earns autonomy (runs for hours, holds a real bar) once it has the four things a good new hire gets: a **clear goal**, the **right skills**, the **right tools**, and **rich, scoped context**. This skill turns a vague ask into exactly that — an artifact an agent (a lane, the runner, or a teammate's session) can pick up and run without re-briefing.

It is a **skill chain**: it calls `premortem` (failure-modes → cheapest guard) and reuses the `sprint-scaffold` `spec_charter` template, then emits a dispatch block for whatever runs your agents (a lane, a runner, a teammate's session). Source idea: the Greg Isenberg / LCA "AI-native in under 60 minutes" planning pillar.

## When to use
- A goal arrives fuzzy ("build the CRM", "fix onboarding", "do the affiliate program") and you're about to start work or dispatch a lane.
- Before any multi-step / multi-session effort that should have one canonical, agent-readable home.
- When triaging an inbound request (a call note, an issue, an email) into something actionable.

## Steps

1. **Compress the goal to ONE sentence + ONE acceptance criterion.** The acceptance criterion is the bar that makes "done" objective and testable ("a real call's card shows recent-calls exactly once", not "improve the card"). If the ask is genuinely ambiguous, ask **at most 2–3** targeted questions — otherwise pick sensible defaults, state them, and proceed (prefer stated defaults over approval prompts).

2. **Name the four things** (this IS the plan's spine):
   - **Goal** — the one-sentence outcome + acceptance criterion from step 1.
   - **Skills** — which installed skills apply (type `/` to scan; e.g. `surgical-patch`, `sprint-scaffold`, `doc-to-pdf`, `ffmpeg-audio`). Name them; don't reinvent.
   - **Tools** — the concrete surfaces the agent will touch: CLIs, APIs, the database, service endpoints, a browser.
   - **Context** — the *scoped* set of files/dirs/memory the agent should read (and the denylist of what it must NOT touch). Narrow beats broad.

3. **Run a premortem** (chain `premortem`). 3–5 concrete failure modes for THIS goal → blast radius → likelihood → the **cheapest guard** for each. These become the plan's "Risks" section — not prose, an artifact.

4. **Emit the `spec_charter`** (reuse the `sprint-scaffold` template; `goal_to_plan.py` renders it):

   ```markdown
   # <Title> · spec_charter v1
   **Goal (one sentence):** …
   **Acceptance criterion (the bar):** …            # objective, testable
   **Scope — IN:** …
   **Scope — OUT (explicitly not now):** …
   **Skills:** …            **Tools:** …
   **Context (read):** …    **Do NOT touch:** …
   **Risks (premortem → guard):**
     - <failure> · <blast radius> · <likelihood> → <cheapest guard>
   **Verification (how we prove the bar is met, in-product not code-trace):** …
   ```

5. **Emit the dispatch block** — ready to hand to an agent, a runner, or a teammate:

   ```
   ROLE: <one line>
   OWNED FILES: <exact paths — the file-lock contract>
   ACCEPTANCE: <the criterion from step 1>
   REPORT: <what to report back + when (e.g. on green / on blocker)>
   CONTEXT: <pointer to the spec_charter + the scoped reads>
   ```

6. **Decide the home.** Single self-contained task → keep the spec_charter inline / in the relevant project folder. Multi-item, multi-session, or multi-lane → run `sprint-scaffold` to drop it in a real sprint folder so nothing ships "homeless."

## CLI

`goal_to_plan.py` renders both artifacts from flags so the brief is a file, not a chat message:

```sh
python3 goal_to_plan.py --goal "Ship the recent-calls dedup fix" \
    --acceptance "a real call's card shows recent calls exactly once" \
    --skill surgical-patch --skill premortem --context src/gateway/main.py --deny "billing/*" \
    --risk "anchor drift|one file|med|assert the match count before writing" \
    --role "gateway lane" --owned-file src/gateway/main.py --write plans/dedup.md
```

Prints to stdout; `--write` saves the same text. Missing fields render as `TODO` so the gaps stay visible.

## Output
One artifact (the spec_charter) + one dispatch block. That's a vague goal turned into "goal + skills + tools + context + a bar + guards" — the agent-ready brief. If the work is dispatch-ready, offer to hand it off; never auto-dispatch without the bar and the premortem present.

## Done = 
The plan is agent-ready when a fresh agent could execute it **without asking you anything** and you could **objectively check the result** against the acceptance criterion. If either isn't true, the brief isn't done — tighten it.
