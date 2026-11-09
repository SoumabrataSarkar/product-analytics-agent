# Evaluation record: Q04, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q04** Did engaged users grow with active users? |
| Category | Comparison of two metrics |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 1 Q04 (o06–o08) |
| Original output | `agent-runs/codex/Q04/` (copied here; originals left in place) |
| Report | `v1-report.md` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| MAU / MEU / rate, all 6 months | 7,937→11,447 / 4,873→6,734 / 61.4%→58.8% | Same, every month | ✅ exact |
| Apr→Sep growth | MAU +44.2%, MEU +38.2% | Same | ✅ |
| 60-second threshold, watch time allocated to the month | Required | MEU v1.0 "at least 60 seconds of watch time allocated to that month" | ✅ |
| Activity and engagement kept distinct | Required | Separate definitions | ✅ |
| No cause claimed | Required | Paid-social split shown as "association" only | ✅ |

## Outcome: **Pass**

Beyond the key: split the growth by source (paid social 2,436 of +3,510 active, 1,327 of +1,861 engaged) and found paid social's own engagement rate fell (60.1% → 56.9%), with correct association language. Unidentified sessions reported.

**Seen in every run (not scored):** repeats that the registry file hash differs from the one recorded at build; correct but now noise. Resolve once in round 2.
