---
name: premortem
description: The DVE/GVE prosthetic premortem reflex — before writing, changing, debugging, or deploying code, briefly imagine how the decision could fail and turn that into an ARTIFACT (predicted failure modes → cheapest guard → predicted-vs-actual ledger), not just talk. Use before any risky change or deploy, or when the user says "premortem", "how could this fail", "what's the risk", "/premortem", "/dve". The operational core of the DVE Guidebook tool.
---

# Premortem (DVE / Guided Vibe Engineering)

Vibe coding is speed. **GVE is scar tissue** — the externalized expert reflex a non-expert builder doesn't have yet. The shift: from *"what should I build next?"* → *"if I build this next, how could it fail, and what should we clarify, test, or document first?"* The risk only counts if it becomes an **artifact** — "if the AI only talks about risk, the risk evaporates."

## When to fire
At each lifecycle transition, a **small phase-specific** premortem (not one giant upfront one — that's waterfall): intent → requirements → architecture → implementation → testing → debugging → **deployment** → iteration. Highest value before a deploy, a schema change, or touching a hot path (e.g. a polling loop, a service entrypoint, anything user-facing in production).

## Steps

1. **Name the decision + its phase.** One line: "Deploying X to the live gateway" / "Adding column Y" / "Refactoring the pull loop."

2. **Imagine 3-5 concrete failure modes.** Be specific to *this* change, not generic. For each:
   - **What breaks** (the failure, in one line)
   - **Blast radius** (who/what is affected — one user? all devices? billing? the outage class)
   - **Likelihood** (low / med / high)
   - **Cheapest guard** — the smallest thing that prevents or catches it: a clarifying question, a boot-test, a canary, a rollback path, a test, a doc line, an `|| true` non-fatal wrap.

3. **Write the artifact.** Append to `notes/premortem.md` next to the work (or wherever your session notes live) — `premortem.py` in this directory writes the block for you. Structure:
   ```
   ## <date> — <decision>  [phase: <phase>]
   | # | failure | blast radius | likelihood | guard | predicted | actual |
   |---|---------|--------------|------------|-------|-----------|--------|
   ...one row per failure mode; leave "actual" blank until after.
   ```
   The **predicted-vs-actual ledger** is the learning signal — after the change ships, come back and fill "actual." A predicted failure that fired → a rule candidate / a future deployment guard.

4. **Act on the top guard before proceeding.** Don't just file it — do the cheapest 1-2 guards now (ask the clarifying question, add the boot-test, write the rollback line). Then proceed with the change.

5. **Teaching mode (for non-expert builders).** If the user is learning, explain *why* each failure mode matters in plain language and which guard you chose — narrate the scar tissue so they build their own.

## CLI

`premortem.py` writes the ledger block so the artifact exists before the change does:

```sh
python3 premortem.py "Deploy the new gateway build" --phase deployment              # print the block
python3 premortem.py "Add column X" --failure "migration locks the table" \
    --failure "old rows carry NULLs" --apply --out notes/premortem.md           # append it
```

Dry-run by default; `--apply` appends to `--out`. `--json` for machine output.

## The loop it serves
Real failure → premortem artifact → predicted-vs-actual ledger → learning signal → rule candidate → test → approval → future deployment guard. That's the proof goal of GVE, and it's how a team converts incidents into permanent guards instead of repeating them.

## Notes
- Keep it short — a premortem is minutes, not a meeting. 3-5 failure modes, cheapest guards, file it, act.
- This skill is the operational embodiment of the **DVE Guidebook**. The guidebook is the teaching text; this skill is the reflex.
- Pairs with the destructive-command guard hook and the syntax-check hook — those are *automatic* guards; this is the *judgment* layer above them.
- Source doctrine: the GVE Premortem Module of the DVE Guidebook.
