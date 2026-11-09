# Evaluation record: Q08, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q08** How much net revenue came from subscriptions versus PPV? |
| Category | Revenue decomposition |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 2 Q08 (o12–o14) |
| Original output | `agent-runs/codex/q08/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Subscription net Apr–Sep | $59,900.04 | Same | ✅ exact |
| PPV net | $411.93 | Same | ✅ exact |
| Total net / gross / refunds | $60,311.97 / $60,375.85 / $63.88 | Same | ✅ |
| Gross vs net distinguished | Required | Yes, by type | ✅ |
| Booked at success time; refunds to original type | Required | Both stated | ✅ |
| Unattributed reported even at $0 | Required | "zero unattributed refunds" | ✅ |

## Outcome: **Pass**

Used the full period rather than Q2 vs Q3; stated it, so it passes. Noted net excludes fees, commissions and tax. Silver re-aggregation matched Gold.

**Seen in every run (not scored):** repeats that the registry file hash differs from the one recorded at build; correct but now noise. Resolve once in round 2.
