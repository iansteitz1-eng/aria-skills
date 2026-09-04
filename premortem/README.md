# premortem

> **Before the risky change: name how it fails, pick the cheapest guard, write it down.**

A premortem is minutes, not a meeting. Name the decision, imagine three to five
concrete ways it breaks, choose the smallest guard for each, and file it as a
ledger you return to after the change ships. The predicted-vs-actual column is
the learning signal: a predicted failure that fired becomes a permanent guard
instead of a repeat incident.

`SKILL.md` is the playbook Claude Code follows. `premortem.py` writes the
artifact, so the risk does not evaporate as talk.

## Usage

```sh
# print the ledger block for one decision
python3 premortem.py "Deploy the new gateway build" --phase deployment

# pre-fill rows and append to the ledger
python3 premortem.py "Add column X" \
    --failure "migration locks the table" \
    --failure "old rows carry NULLs" \
    --apply --out notes/premortem.md
```

Dry-run by default. `--apply` appends to `--out`; `--json` for machine output.

## The artifact

```
## 2026-09-04 — Add column X  [phase: implementation]

| # | failure                    | blast radius | likelihood | guard | predicted | actual |
|---|----------------------------|--------------|------------|-------|-----------|--------|
| 1 | migration locks the table  |              |            |       |           |        |
| 2 | old rows carry NULLs       |              |            |       |           |        |
```

Fill blast radius, likelihood, guard, and predicted now. Act on the top guard
before proceeding. Come back for actual after the change ships.

## License

Apache 2.0
