# goal-to-plan

> **A fuzzy goal in, an agent-ready brief out.**

The bottleneck of an AI-native team is not the model, it is the quality of the
brief. An agent earns autonomy once it has the four things a good new hire gets:
a clear goal, the right skills, the right tools, and scoped context. This skill
turns a vague ask into exactly that, as an artifact an agent (a lane, a runner,
or a teammate's session) can pick up without re-briefing.

It is a skill chain: it calls `premortem` (failure modes to cheapest guard) and
reuses the `sprint-scaffold` spec_charter template. Two artifacts come out:

- a **spec_charter**: goal, one acceptance criterion, scope in and out, skills,
  tools, context, risks (premortem to guard), verification
- a **dispatch block**: role, owned files, acceptance, report protocol, context

`SKILL.md` is the playbook Claude Code follows. `goal_to_plan.py` renders both
artifacts from flags, so the brief is a file and the gaps stay visible as `TODO`.

## Usage

```sh
python3 goal_to_plan.py \
    --goal "Ship the recent-calls dedup fix" \
    --acceptance "a real call's card shows recent calls exactly once" \
    --skill surgical-patch --skill premortem \
    --context src/gateway/main.py --deny "billing/*" \
    --risk "anchor drift|one file|med|assert the match count before writing" \
    --role "gateway lane" --owned-file src/gateway/main.py \
    --write plans/dedup.md
```

Prints to stdout; `--write` saves the same text; `--json` for machine output.

## Done means

A fresh agent could execute the plan without asking you anything, and you could
objectively check the result against the acceptance criterion. If either is not
true, the brief is not done. Tighten it.

## License

Apache 2.0
