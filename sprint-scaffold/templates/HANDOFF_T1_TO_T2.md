# Sprint NNN — Inter-terminal handoff template

**From:** Terminal 1
**To:** Terminal 2
**When:** YYYY-MM-DD
**Why:** <one sentence: what each terminal is solving for>

---

## 🛣️ Your continuing lane

| Item | Files (yours) | Size |
|---|---|---|

## 🚦 What I'm taking on Terminal 1

| Item | Files I'll touch |
|---|---|

---

## 🔒 File-lock contract — DO NOT EDIT THESE WHILE I'M ACTIVE

**Mine (don't touch):**
- <files I own this sprint>

**Yours (I won't touch):**
- <files T2 owns this sprint>

**Shared — coordinate via route prefix in main.py:**

| Route prefix | Owner |
|---|---|

---

## 📦 Shared mutable surfaces (both write — INSERT-only is fine)

| Surface | Protocol |
|---|---|
| `v4_ops_log` | INSERT freely. Tag `purpose='sprint_NNN'`. UPDATE rows you own. |
| `/v4/admin/playbook` tile | Both can flip ✅ status. Keep edits minimal. |
| `MEMORY.md` index + new memory files | INSERT-only. Add at TOP of index. Never delete each other's. |

---

## 🧭 Coordination tips

1. **Restart contract:** coordinate `<service>` restarts via Ian. No double-restart inside 30s. Static-dir-only changes need no restart.
2. **If you finish your items before I do:** stretch toward <named alternative items> — purely additive new files, won't conflict.

---

## 📊 Projected end-state if both lanes land

| | Done | Total | % |
|---|---|---|---|
| Now | | | |
| After T2 | | | |
| After T1 | | | |

---

## ✅ Ack

Send a one-liner ack via Ian when you've read this and confirmed no collisions. Then both terminals fire.

— T1
