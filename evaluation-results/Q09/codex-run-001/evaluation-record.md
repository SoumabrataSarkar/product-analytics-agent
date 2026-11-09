# Evaluation record: Q09, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q09** Did refunds materially change the revenue comparison? |
| Category | Revenue / data nuance |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 2 Q09 (o13, o15) |
| Original output | `agent-runs/codex/Q09/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Gross Q2 / Q3 | $30,182.93 / $30,192.92 | Same | ✅ exact |
| Refunds Q2 / Q3 | $37.93 (7) / $25.95 (5) | Same, with counts | ✅ |
| Net Q2 / Q3 | $30,145.00 / $30,166.97 | Same | ✅ |
| Answer | No: revenue still flat | "changed the size of the very small increase, but not its direction or the conclusion that revenue was nearly flat" | ✅ |
| Successful refunds only, at success time; same basis both quarters | Required | Stated | ✅ |
| "Material" backed by numbers | Required | Yes; also says no materiality threshold was given | ✅ |

## Outcome: **Pass**

Beyond the key: split by type incl. unattributed $0; sensitivity on the 13 reviewed payment corrections (Q2 $71.92, Q3 $49.95 → net change would be $43.94), labelled as sensitivity, not a correction. Matches the Q02 review follow-up check.

**Seen in every run (not scored):** registry-hash difference note; no git metadata in the repo copy.
