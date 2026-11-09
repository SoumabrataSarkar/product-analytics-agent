# Q02 run-001: version history (v1 → feedback → v2)

This file explains how the report changed and why. Read it with:

- `v1-report.pdf`: what the agent produced on its own (scored **Fail**)
- `feedback.md`: the feedback, word for word (A = format, B = substance review, C = decision)
- `v2-report.pdf`: what was produced after the feedback (**awaiting evaluator verification**)

The score belongs to v1. v2 was corrected with human help, so it can't turn v1 into a pass (C.1).

## Timeline (2026-11-09, IST)

| Time | Step |
|---|---|
| 17:13 | Question asked in independent mode |
| before 17:51 | v1 delivered as a Claude Doc (+ a first 4-page PDF in chat); user asks for a PDF, a consistent template, charts and simple wording |
| 17:51 | User asks for a white-paper style template |
| 18:08 | Feedback A (format and readability) |
| 18:11 | Feedback B (substance review) |
| 18:21–18:29 | v2 built: extra checks 17–21 run, report rewritten in the new template |
| 18:34 | Feedback C (Fail for v1; Q02; three refined rules; private folder; two small v2 fixes) |
| after 18:34 | Small v2 fixes applied; v2 now 9 pages |

## Substance changes (feedback B and C)

| Feedback | What v1 said | What v2 says | How it was checked |
|---|---|---|---|
| B1/B2-3: cause stated too confidently | "New users rarely reach a paywall, so they don't become paying subscribers." H6 "Supported" | Lower paywall reach and lower conversion **go together**; the data doesn't show why. Every 30-day payer also saw a paywall, which shows the two go together, not that one causes the other | Check 17 |
| B2/B2-1: mixed comparison periods | "Q3 signups 0.5% (was 1.9%)" | 1.9% for **May–June** signups vs 0.5% for **July–August** signups. April left out (subscriber base starting from zero), September left out (its 30 days end after the data does) | Existing checks q07, q14 |
| B3/B2-2: monthly vs quarterly mix-up | ~$760 a month = "about 2.5% of revenue" | Labelled **a scenario, not a forecast**: ~$760 a month ≈ **7.6%** of Q3's average monthly net revenue ($10,056), with its assumptions (rate reachable, $9.99 price, renewals) | Arithmetic shown in the report |
| B4/B2-4: data quality too certain | Unidentified sessions understate MAU "by the same amount each month"; impact "none" | Unidentified share 6.5–7.6% and varies; how many people that is: **unknown**. Payment corrections: $71.92 (Q2) and $49.95 (Q3); removing all of them changes QoQ revenue by +0.15%; when they were made is unknown | Checks 15, 18 |
| B5/B2-5: H8 and H9 rejected too firmly | H8 Rejected, H9 Rejected | H8 **Inconclusive**, H9 **Inconclusive**, with a tracking audit recommended | Checks 15, 16, 20 |
| B6/B2-6: first-30-day window had no lower bound | Rates presented as exact | Query rerun with both boundaries; results identical; window definition disclosed | Check 17 |
| B7: anomaly called irrelevant | Q2-signup paywall views with no purchases "doesn't affect the main finding" | Kept **open** and shown prominently: 183 checkouts by Q2 signups in Aug–Sep, none reached a payment attempt; cause unknown | Checks 19–21 |
| C: "all 38 layer tables" | n/a (v2 wording) | "20 Bronze views and 18 Silver/Gold tables" | Build log |
| C: uses all 10 pages | n/a (first v2 draft) | 9 pages, leaving one spare | Generator page count |

## Format changes (feedback A, plus the earlier requests)

| Feedback | Change in v2 |
|---|---|
| PDF, not a Claude Doc; same template every time | Fixed-template PDF generator (`tools/report_pdf.py`), now in the repo via PR #1 |
| White-paper style | Cover, contents, numbered chapters, red accent |
| "registry mau v1.1" means nothing to a reader | Metric names and versions replaced by plain definitions in a glossary |
| Cohort definition too generic | "Everyone who created an account in the same calendar month. Example: the July cohort = all accounts created 1–31 July. We follow each cohort for its first 30 days." |
| Chart on page 01 showing the user split | Stacked chart of MAU by signup group on the answer page |
| Colours easy but not tacky; show legend colours | Muted palette; legend swatches next to every chart |
| Paywall needs its own chart, with absolute numbers and the maths | Separate paywall chart with counts (signups, saw a paywall, paid) per cohort and the calculation written out |
| A page showing how the investigation went | Chapter 02 "How we investigated": workflow of stages, layer used, what was checked, why, and Supported / Rejected / Inconclusive |
| MAU growth chart hard to follow (−1,338, −316, +3,457) | Explained as a sum: the three signup groups don't overlap, so 9,016 − 1,338 − 316 + 3,457 = 10,819 |
| "evidence q06" is confusing | Renamed "check 6", with a numbered evidence appendix |

## Rule changes so future runs don't repeat this (C.3)

Merged in PR #1 (`skills/product-analytics-investigation/SKILL.md`):

1. Data-quality caveats: give the affected scope and impact where feasible; say "unknown" when it is.
2. Time-bounded questions: define start and end, timezone, and inclusive/exclusive.
3. A material anomaly stays open until evidence resolves it.

Also: a PDF is required only when a report is requested or for the assignment deliverable, with a hard 10-page limit.

## Pattern to reuse for later runs

Every run folder (`QNN/<agent>-run-NNN/`, e.g. `Q01/codex-run-001/`) uses the same file names:

```
v1-report.pdf          what the agent made first, never edited
feedback.md            feedback word for word (only if given)
v2-report.pdf          final report after feedback (only if any)
v1-vs-v2-changes.md    what changed and why (only if there is a v2)
evaluation-record.md   the score (always belongs to v1)
v2-content.json        text and numbers behind v2-report.pdf
evidence.zip           query logs
```
