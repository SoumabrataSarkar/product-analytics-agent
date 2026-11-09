# Evaluation record: Q03, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q03** Which acquisition sources contributed most to the change in active users? |
| Category | Comparison / decomposition, with an open period (clarification expected) |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Agent version | Repo ZIP download; no git metadata, so commit not verifiable (the agent said so) |
| Clarification | Agent asked the evaluator: daily, weekly or monthly? Evaluator chose weekly. Agent proposed two weeks or asked for dates; the evaluator gave a non-Monday date and the agent adjusted to complete Monday–Sunday UTC weeks. Final scope: **WAU, 27 Jul–2 Aug vs 17–23 Aug 2026** |
| Queries | 8 read-only, all logged, none truncated |
| Answer key | `batch1-activity.md` Q03 covers monthly comparisons only, so the key was extended for the clarified scope: `oracle-b5/o41–o42` (registry `resolved_sessions` + WAU rule on source tables, sliced by `users.acquisition_source`) |
| Report | Chat answer + `INDEX.md` (saved here as `v1-report.md`); no PDF |

## Expected vs actual (clarified scope)

| Item | Expected (o41, o42) | Agent | Match |
|---|---|---|---|
| WAU total | 5,914 → 5,831 (−83) | Same | ✅ exact |
| Organic | 2,443 → 2,230 (−213) | Same | ✅ |
| Paid social | 2,001 → 2,183 (+182) | Same | ✅ |
| Paid search | 1,403 → 1,351 (−52) | Same | ✅ |
| Unknown source | 67 → 67, shown separately | Same, shown separately | ✅ |
| Unidentified sessions | 859 of 10,704; 765 of 10,782 | Same, excluded, impact on ranking stated as unknown | ✅ |
| Fixed first-touch source | Required | Stated | ✅ |
| No causal claim about acquisition | Required | "arithmetic contributions, not evidence that acquisition activity caused the change" | ✅ |

## Outcome: **Pass** (clarified variant)

**Behaviour (the main thing this scenario tests):** the question has no period or measure, and the agent asked instead of guessing. When the evaluator gave a date that doesn't start a week, the agent proposed complete Monday–Sunday weeks rather than a partial one. Numbers are exact for the chosen scope.

**Also good:** warned that the weeks are not adjacent, so the difference is not retention or churn; checked user overlap between the weeks; said the repo had no git metadata instead of inventing a commit.

**Limitation of this run:** because the evaluator chose two August weeks, the run does not test the main monthly story (paid social +1,841 Q2→Q3). That is covered by Q02 and the answer key, not by this run.

**Minor, not scored:**
- Repeats the registry-hash difference note (as in Q01). Correct, but it now appears in every run; worth resolving once (likely the registry doc was edited after the build without a definition change) so it stops being noise.
- No PDF this time, though the prompt asked for a report. Inconsistent with Q01 (5-page PDF). Fine for scoring.
