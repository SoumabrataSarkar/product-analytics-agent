# Evaluation record: Q07, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q07** Did newer signup cohorts convert to subscription at a lower rate? |
| Category | Cohorts |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 2 Q07 (o11) |
| Original output | `agent-runs/codex/q07/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Cohort rates Apr–Aug | 4.56 / 1.73 / 2.11 / 0.52 / 0.54% | Same | ✅ exact |
| July–August | 29 ÷ 5,426 = 0.53% | Same | ✅ |
| September excluded, with reason | Required | Yes, no complete 30-day window | ✅ |
| No cause claimed | Required | "does not identify a cause" | ✅ |
| **April flagged as unusual** (data starts with no subscribers, so April is the base-forming month) | **Required caveat** | **Not flagged.** April pooled into the baseline: Apr–Jun 167 ÷ 6,454 = 2.59%, and "every mature cohort after April converted below April" | ❌ |

## Outcome: **Fail**

Why Fail: the batch rules make a missing required caveat an automatic fail. Including April inflates the baseline (2.59% vs 1.94% for May–June) and overstates the decline (−2.05 pt / −79% vs −1.41 pt / −73%). The direction of the answer is right and every number is exact, so this is a narrow but real error: the comparison baseline isn't like-for-like. Same family as Q02 v1 failure F2 (comparison periods). **Round-2 rule candidate:** before using the first period of the data as a baseline, check whether it's a start-up period (e.g. subscriber base starting at zero) and say so.

**Seen in every run (not scored):** repeats that the registry file hash differs from the one recorded at build; correct but now noise. Resolve once in round 2.
