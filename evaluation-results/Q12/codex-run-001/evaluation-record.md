# Evaluation record: Q12, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q12** Which episodes are watched most, and how much is actually completed? |
| Category | Ambiguous measure + content grain + trap |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 3 Q12 (o26–o28) |
| Original output | `agent-runs/codex/Q12/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Most watched | c01 ep 3 by viewers (3,738) and views (8,014) | "Skybound episode 3", 3,738 viewers, 8,014 views | ✅ exact |
| Measure stated | Required | Distinct viewers; notes episode 2 leads on completions | ✅ |
| Top 12 all c01 | Expected | "The 12 most-viewed episodes are all Skybound" | ✅ |
| Completion rule (≥90% unique coverage within 7 days; rewatches don't add) | Required | Stated and applied; ep 3 28.3% | ✅ exact |
| Overall completion | 33.0% (35,017 / 105,989) | Same | ✅ exact |
| Immature windows excluded | Required | 4,385 of 110,374 (4.0%) excluded | ✅ |
| **Trap:** c03 ep 13, 0 of 1,455 completed | Strong answers notice | Flagged: "zero of 1,455 eligible… reason unknown", tested as H2, cause left inconclusive | ✅ |

## Outcome: **Pass**

Strong run. Didn't show the watch-time ranking (ep 2 leads by watch hours), but it stated its measure and showed the views vs viewers vs completions differences, which meets the must. Contents again skip chapter 04.

**Seen in every run (not scored):** registry-hash difference note; no git metadata in the repo copy.
