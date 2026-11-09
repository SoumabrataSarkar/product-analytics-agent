# Evaluation record: Q02, run 002 (blind, round 2)

| Field | Value |
|---|---|
| Scenario | **Q02** "MAU is up 20% QoQ but revenue is flat. Board meeting Thursday. Figure out what's happening and what we should do about it." (GM wording, as in run 001) |
| Runtime | Claude Code, fresh helper agent with no memory of the evaluation conversation; standard prompt only; independent mode |
| Agent version | Clean copy of `main` @ `0b9a143` (includes the PR #1 certainty rules and the PR #4 start-up rule; no evaluation results), extracted to `agent-runs/claude/round2/repo/` |
| Isolation | Clean repo copy plus an instruction to read only that copy and the database. Same machine as the evaluation files; no technical sandbox |
| Run time | 2026-11-09 18:34:24–18:44:11 UTC (about 10 min) |
| Queries | 18 via `tools/evidence_query.py`; none failed or truncated |
| Report | `v1-report.pdf` (9 pages, repo template), `v1-content.json` |
| Scored against | Answer-key values (batches 1–2), the run-001 review points (`../run-001/feedback.md`) and spot checks on new figures |

## Numbers

| Item | Expected | Agent | Match |
|---|---|---|---|
| Avg MAU Q2 → Q3 | 9,015.7 → 10,818.7 (+20.0%) | Same | ✅ |
| Net revenue | $30,145.00 → $30,166.97 (+0.07%) | Same, split by type | ✅ |
| Paying users | ~1,036 both quarters | 1,035.7 / 1,036.0 | ✅ |
| MAU change by source | paid social +1,841.3, paid search +92.0, unknown +25.3, organic −155.7 | Same | ✅ |
| Growth accounting | key Q06 | Same ranges | ✅ |
| Paywall exposure | 11.6% (May) → 9.2% (Sep) | Same | ✅ |
| 30-day paywall reach, new cohorts | 4.4% (May) → 0.5% (Aug) | Same | ✅ |
| Paid-social spend / signups / new payers (spot check) | $13,918.32 → $30,760.27; 1,489 → 4,568 signups; 67 new payers in Q3 | Same; $459 per new payer; 6.7 vs 2.2 new payers per $1k | ✅ verified |
| Without April | MAU +13.2%, revenue −0.8% | Same | ✅ verified |

## Run-001 review points

| Review point (run 001) | This run |
|---|---|
| 1. Cause stated too confidently | ✅ Mostly fixed. Patterns labelled as associations; "why new users don't reach the paywall" left open; the limitations say low paywall reach is not claimed as the only reason. Minor: the headline still links "about 1,000 paywall viewers" to "about 1,000 subscribers" with "so" |
| 2. Mixed comparison periods | ✅ Fixed. Q2 vs Q3 labelled; cohort trends read from May with the April start-up stated; September cohort excluded |
| 3. Monthly vs quarterly mix-up | ✅ No mix-up; $459 per payer is Q3 spend ÷ Q3 new payers, labelled not a payback |
| 4. Data-quality impact too certain | ⚠️ Partly repeats. Logged-out sessions: "counting them… so the conclusion does not change" (reasonable but asserted). Payment corrections: "no impact" without noting the review times are unknown |
| 5. Hypotheses rejected too firmly | ⚠️ Mixed. Paywall-tracking gap (H7) correctly Inconclusive with an instrumentation recommendation; "measurement artefact" (H9) rejected on layer reconciliation alone, which doesn't rule out identity effects |
| 6. First-30-day window bounds | ✅ Fixed. Query enforces both bounds (`event_at >= signup_at` and `< signup_at + 30 days`) |
| 7. Unexplained anomaly | n/a: the Q2-cohort checkout anomaly was not surfaced |

**New strengths vs run 001:** applied the start-up rule unprompted; found that paywall-to-purchase conversion is flat from May (the point Q11 missed); added marketing spend and new payers per $1k; specific, testable recommendations (holdout test, first-paywall A/B tests, trigger instrumentation).

## Outcome: **Pass** (minor issues)

Every number is right, every material review point from run 001 is fixed, and the remaining issues (two data-quality impact statements and one hypothesis rejection stated a little too firmly) are minor and don't affect the conclusions or recommendations. Under the strictest reading of the rules, point 4 could be scored Partial; recorded here as Pass with that caveat.

**Housekeeping:** the run folder also holds the agent's helper scripts and a hidden `.preview/` folder of layout images it couldn't delete (deletion isn't allowed in that folder).
