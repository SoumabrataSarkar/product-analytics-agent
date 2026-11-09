# Evaluation record: Q13, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q13** Is an unusually large source payment real? |
| Category | Data-quality trap |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 3 Q13 (o29–o32) |
| Original output | `agent-runs/codex/Q13/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Raw value and unit | 999.0 "USD" on 7 rows | Same | ✅ |
| Curated amount | $9.99 each | Same; 6 initial + 1 renewal | ✅ |
| Review evidence shown separately | Required | "100x"/cents review, reason quoted; "review rationale is a recorded assertion" | ✅ |
| Impact if raw used | +$6,923.07 ($6,993.00 vs $69.93) | Same | ✅ exact |
| Correction from existing review, not detection | Required | Yes; provider evidence not available to verify | ✅ |
| Review timing unknown | Required | "Review timestamps are NULL" | ✅ |
| Other reviewed rows | 6 "unavailable" raw amounts | Reported | ✅ |

## Outcome: **Pass**

Also noted one of the seven was later refunded ($59.94 net). Tested H1 (unit error) supported vs H2 ($999 real) contradicted. Strong, well-hedged run.

**Seen in every run (not scored):** registry-hash difference note; no git metadata in the repo copy.
