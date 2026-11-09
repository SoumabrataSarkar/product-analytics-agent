# Evaluation record: Q14, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q14** Can we trust acquisition-channel conclusions when source values are missing? |
| Category | Data-quality / missing values |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 3 Q14 (o33, o34) |
| Original output | `agent-runs/codex/Q14/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Unknown signups | 135 of 13,600 (1.0%) | Same | ✅ exact |
| Unknown users overall | 238 of 24,000 | Same; no NULLs or blanks | ✅ |
| Unknown kept separate | Required | "Unknown remains separate"; reassignment only as a sensitivity bound | ✅ |
| Sensitivity bound | Required | All 25 unknown July signups to organic → paid social still leads by 1,104; extreme allocation bounds the social change | ✅ |
| No causal / campaign attribution | Required | "do not establish… that a channel caused an outcome" | ✅ |
| Answer | Yes at channel level, with caveat | "Yes, with limits" | ✅ |

## Outcome: **Pass**

Sensitivity used signups (July and the Jun→Jul change) rather than the Q2→Q3 MAU change in the key; different example, same reasoning and conclusion. Computed same-month CAC and labelled it, with no spend-to-user fan-out.

**Seen in every run (not scored):** registry-hash difference note; no git metadata in the repo copy.
