# Evaluation record: Q18, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q18** How many mobile sessions were there in September versus August? |
| Category | Filtered query + time comparison |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 4 Q18 (o35, o40) |
| Original output | `agent-runs/codex/q18/` (copied here; originals left in place) |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Mobile defined | iOS + Android | Asked; evaluator confirmed iOS + Android | ✅ |
| August mobile sessions | 36,295 | 36,295 | ✅ exact |
| September mobile sessions | 38,366 (overlap rule) | 38,365 by start month, and 38,366 by overlap, both stated | ✅ |
| Same counting in both months | Required | All sessions incl. unidentified, start-month basis, both months | ✅ |
| Cross-month session | Optional credit | Found and explained (one August session continues into September) | ✅ |

## Outcome: **Pass**

Used start-month assignment rather than the registry's overlap rule, but said so and gave the overlap figure too, so it passes. Didn't mention that September has one day fewer (per-day +9.2%), which was optional.
