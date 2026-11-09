# Evaluation record: Q01, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q01** How did monthly active users change across the available months? |
| Category | Simple aggregate / time comparison |
| Runtime | Codex, fresh session, independent mode |
| Agent version | Repo ZIP download; commit not recorded by the run (likely `main` after PR #2, which includes the Q02 skill rules). Round 1. |
| Run time | 2026-11-09 15:41:06–15:45:27 UTC (about 4.5 min of investigation, after setup) |
| Queries | 6 read-only, all logged, none truncated (Gold monthly KPI, Silver recount, build log, session quality) |
| Answer key | `answer-key/batch1-activity.md`, Q01 (checks o01, o02) |
| Original output | `agent-runs/codex/Q01/` (copied here; originals left in place) |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| MAU Apr–Sep | 7,937 / 9,134 / 9,976 / 10,138 / 10,871 / 11,447 | Same | ✅ exact |
| Month-on-month changes | +1,197, +842, +162, +733, +576 | Same, with % | ✅ exact |
| Apr → Sep | +3,510 (+44.2%) | +3,510 (+44.2%) | ✅ |
| Unidentified sessions | 2,286 … 3,703, excluded, not people | Same range; "do not translate directly into a number of missing people" | ✅ |
| Complete UTC months | Required | Apr–Sep, end 2026-10-01 exclusive | ✅ |
| Metric version | Required | `mau` v1.1 | ✅ |
| No summing of months | Fail trigger | Explicitly warns MAU is non-additive | ✅ |
| No cause claimed | Implied by skill rules | "The trend alone does not establish why" | ✅ |

## Outcome: **Pass**

All numbers exact; every "must" met; no fail trigger.

**Beyond the key (positive):**
- Recounted MAU from Silver and matched all six Gold values (independent check).
- Found the one session spanning August and September (3,702 started vs 3,703 touching September). This contradicts the registry's caveat that no fixture session crosses a month boundary; same finding as answer-key batch 4 (Q18).
- Flagged that the registry file hash differs from the one recorded at build, and called exact equivalence "unverified" rather than assuming it. Appropriately cautious.

**Minor, not scored:**
- Report contents skip chapter 04 ("Why it happened") and jump 03 → 05. Correct for a descriptive question, but the numbering looks like a page is missing. Candidate generator tweak for round 2: renumber or show "04 not applicable".
- A 5-page PDF for a one-number question. Allowed (the prompt asked for a report) but costly; for round 2 consider asking for a short answer on simple questions.
- Start time recorded after initial setup, so total elapsed time is slightly understated.

## Files

- `v1-report.pdf`, `v1-content.json`: Codex's report and its content file, unedited
- `evidence.zip`: 6 request files, 6 evidence logs, run note
- No feedback and no v2 (none needed)
