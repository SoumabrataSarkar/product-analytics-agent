# Answer key, batch 1: activity scenarios (Q01, Q03, Q04, Q05, Q06)

**Status:** Approved by evaluator, 2026-11-09. **Evaluator-only:** keep out of every agent run and out of the repository.
**Reference method (oracle):** the metric registry's canonical SQL, assembled with `examples/pockettoons/metric_registry.py` and run read-only on the **source tables only** (no Silver or Gold). Q03 and Q05 also use labelled extra queries built from the registry's building blocks. Logs: `oracle-b1/o01…o10.jsonl` (10 queries, none truncated).
**Snapshot:** `pockettoons.sqlite` SHA-256 `8d39e78b…790b`, build `3a0dbed2`. Coverage: complete UTC months, April–September 2026.
**Cross-checks:** MAU = new + retained + resurrected (Q06); source groups add up to MAU (Q03); every value equals the matching Gold column. The Gold match is a consistency check only: the reference never reads Gold.
**Note:** every metric these scenarios use is now approved (registry complete), so the "definition needed" notes in `investigation-paths.md` no longer apply.

## Scoring rules for this batch

- **Counts:** exact match.
- **Percentages and rates:** ±0.1 percentage point (rounding only).
- **Quarter averages:** ±0.1 user.
- **Comparison period:** where the question doesn't name one, any clearly stated, defensible choice passes, such as Q2 vs Q3 quarter averages, April vs September, or month by month. Asking a short clarifying question also passes. **Silently** picking a period, or mixing periods, is a fail criterion.
- **Automatic fails:** summing distinct users across months or across overlapping slices; claiming a cause from an association; leaving out a required caveat listed below.

---

## Q01: How did monthly active users change across the available months?

**Expected values** (`mau` v1.1; checks o01, o02)

| Month | MAU | Change vs previous month | Unidentified sessions (excluded) |
|---|---|---|---|
| Apr 2026 | 7,937 | (first month) | 2,286 |
| May | 9,134 | +1,197 (+15.1%) | 3,044 |
| Jun | 9,976 | +842 (+9.2%) | 3,184 |
| Jul | 10,138 | +162 (+1.6%) | 3,354 |
| Aug | 10,871 | +733 (+7.2%) | 3,480 |
| Sep | 11,447 | +576 (+5.3%) | 3,703 |

- April → September: **+3,510 (+44.2%)**. Quarter averages: Q2 **9,015.7**, Q3 **10,818.7** (+20.0%).
- **Must:** use complete UTC months; count distinct users per month; report unidentified sessions as excluded, not as people; state the metric version.
- **Fail triggers:** a "total MAU" made by adding months (59,503 is meaningless); counting anonymous device IDs as users; counting a partial month.

## Q03: Which acquisition sources contributed most to the change in active users?

**Expected values** (ad hoc `mau` v1.1 by fixed first-touch `acquisition_source`; o05, o10)

| Source | Q2 avg | Q3 avg | Q2→Q3 | Apr → Sep | Share of MAU Apr → Sep |
|---|---|---|---|---|---|
| paid_social | 2,059.0 | 3,900.3 | **+1,841.3** | **+2,436** | 22.8% → 37.1% |
| paid_search | 2,423.7 | 2,515.7 | +92.0 | +480 | 26.7% → 22.7% |
| organic | 4,444.0 | 4,288.3 | **−155.7** | +561 | 49.6% → 39.3% |
| unknown | 89.0 | 114.3 | +25.3 | +33 | 1.0% → 1.0% |
| **Total (= MAU)** | 9,015.7 | 10,818.7 | +1,803.0 | +3,510 | |

- Supporting context: paid_social's share of signups rose from 24% (May, 522 of 2,201) to 64% (July–August, 3,469 of 5,426). No active user lacks a users row.
- **Expected answer:** paid_social contributed by far the most on either comparison. Note that organic **fell** Q2→Q3 but **rose** April→September, so the answer depends on the comparison; the agent must state which it used.
- **Must:** use the fixed user-level source (source values partition MAU, so they may be added); show "unknown" separately (about 1% of MAU) with a sensitivity remark; no claim that advertising **caused** the change.
- **Fail triggers:** using session-level or "last touch" source without saying so; dropping "unknown"; a causal claim about ads.

## Q04: Did engaged users grow with active users?

**Expected values** (`meu`, `engagement_rate`, activity family 1.0; o06–o08)

| Month | MAU | MEU (≥60 s watch in month) | Engagement rate (MEU ÷ MAU) |
|---|---|---|---|
| Apr | 7,937 | 4,873 | 61.4% |
| May | 9,134 | 5,532 | 60.6% |
| Jun | 9,976 | 5,965 | 59.8% |
| Jul | 10,138 | 6,143 | 60.6% |
| Aug | 10,871 | 6,453 | 59.4% |
| Sep | 11,447 | 6,734 | 58.8% |

- April → September: MEU **+38.2%** vs MAU **+44.2%**. Quarter averages: MEU 5,456.7 → 6,443.3 (**+18.1%**) vs MAU **+20.0%**.
- Engagement rate as an average of monthly ratios: Q2 **60.6%**, Q3 **59.6%**. If shown by quarter, it must be labelled "average of monthly ratios".
- **Expected answer:** yes, engaged users grew, but slightly more slowly than active users, so the engaged share drifted down by about 2.6 points (61.4% → 58.8%).
- **Must:** apply the 60-second threshold and split watch time across periods by wall-clock share (registry); keep activity and engagement distinct.
- **Optional context:** stickiness (average DAU ÷ MAU) stays at about 11.8–12.8%.
- **Fail triggers:** treating "watched anything" or "had a view" as engaged without the threshold; summing or averaging ratios without labelling.

## Q05: Did the platform mix change?

**Expected values** (`mau_monthly_by_platform`; o03, o04). Shares are of MAU and **overlap**: a user can count on several platforms.

| Month | Android | iOS | Web | MAU | Users on 2+ platforms | Sum of platform counts |
|---|---|---|---|---|---|---|
| Apr | 4,376 (55.1%) | 3,634 (45.8%) | 2,183 (27.5%) | 7,937 | 2,242 (28.2%) | 10,193 |
| Jun | 5,512 (55.3%) | 4,548 (45.6%) | 2,785 (27.9%) | 9,976 | 2,853 (28.6%) | 12,845 |
| Sep | 6,312 (55.1%) | 5,237 (45.7%) | 3,140 (27.4%) | 11,447 | 3,225 (28.2%) | 14,689 |

(All six months in o03/o04. Shares stay within 55.1–55.4% Android, 45.3–46.2% iOS and 27.4–28.0% web.)

- **Expected answer:** no material change in the platform mix; all platforms grew in line with MAU.
- **Must:** state that platform counts overlap (about 28% of active users use 2+ platforms) and that total MAU comes from a single distinct count across all platforms, not from adding platforms.
- **Fail triggers:** adding platform MAUs (e.g. "14,689 users in September"); shares that add to 100% without explaining how overlaps were assigned.

## Q06: Are more users new, retained or returning?

**Expected values** (`growth_accounting_monthly` v1.0; o09). Here "resurrected" = returning.

| Month | New | Retained | Resurrected (returning) | Churned | Quick ratio | MAU check |
|---|---|---|---|---|---|---|
| May | 2,201 | 4,757 | 2,176 | 3,180 | 1.38 | 9,134 |
| Jun | 2,653 | 4,867 | 2,456 | 4,267 | 1.20 | 9,976 |
| Jul | 2,477 | 4,753 | 2,908 | 5,223 | 1.03 | 10,138 |
| Aug | 2,949 | 4,415 | 3,507 | 5,723 | 1.13 | 10,871 |
| Sep | 1,720 | 5,071 | 4,656 | 5,800 | 1.10 | 11,447 |

- **Expected answer:** returning (resurrected) users roughly doubled (2,176 → 4,656) and are the fastest-growing group. New users were 2,200–2,950 a month until September, when they dropped to 1,720. Retained users were roughly stable (4,400–5,100). Churned users also rose (3,180 → 5,800), and the quick ratio fell from 1.38 to about 1.1.
- **Must:** say April has no row because there is no prior month in the data, so April users can't be classified; reconcile new + retained + resurrected = MAU; avoid calling "returning" a sign of what *caused* the return.
- **Fail triggers:** an April classification; buckets summed across months as distinct users; causal language.
- **Evaluator note:** September's lower new-user count (1,720 vs 2,949 in August) is a real feature of the data (signups by source o10), not a partial month. The agent is not required to explain it, but should not call it an artifact without evidence.
