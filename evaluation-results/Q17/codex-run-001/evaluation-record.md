# Evaluation record: Q17, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q17** How many US users had an active subscription at the end of September? |
| Category | Filtered query |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 4 Q17 (o36, o37, o39) |
| Original output | `agent-runs/codex/Q17/` (copied here; originals left in place) |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| US subscribers at end of September | 349 | 349 | ✅ exact |
| Snapshot instant stated | Required | 1 Oct 2026 00:00 UTC | ✅ |
| Cancelled-but-paid-up counted | Required | Includes the 37, stated | ✅ |
| Country basis | User's country | Snapshot country, stated | ✅ |
| Independent recount | n/a | History recount also 349 | ✅ |

## Outcome: **Pass**

Clean run.
