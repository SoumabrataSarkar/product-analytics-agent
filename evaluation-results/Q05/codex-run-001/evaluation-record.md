# Evaluation record: Q05, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q05** Did the platform mix change? |
| Category | Overlapping slices (trap: adding platforms) |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 1 Q05 (o03, o04) |
| Original output | `agent-runs/codex/Q05/` (copied here; originals left in place) |
| Report | `v1-report.md` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Aug platform MAU | Android 6,022, iOS 4,926, web 3,041 | Same | ✅ exact |
| Sep platform MAU | 6,312 / 5,237 / 3,140 | Same | ✅ exact |
| Overlap | Aug 28.5%, Sep 28.2% on 2+ platforms | Same; "rows cannot be added" | ✅ |
| Comparison period | Stated, defensible | Aug vs Sep (latest two months), plus "Apr–Sep shares within about one point" | ✅ |
| Answer | No material change | Changed "only slightly" | ✅ |

## Outcome: **Pass**

Shares correctly sum above 100% and the agent explains why. Recorded repo commit c405664 (this copy had git metadata, unlike the others).

**Seen in every run (not scored):** repeats that the registry file hash differs from the one recorded at build; correct but now noise. Resolve once in round 2.
