# Answer key, batch 3: content and data quality (Q12–Q14)

**Status:** Approved by evaluator, 2026-11-09. **Evaluator-only:** keep out of every agent run and out of the repository.
**Reference method (oracle):** the metric registry's canonical SQL and catalog rules, run read-only on **source tables only**. Logs: `oracle-b3/o26…o34.jsonl` (9 queries, none truncated).
**Snapshot:** `pockettoons.sqlite` SHA-256 `8d39e78b…790b`, build `3a0dbed2`. Coverage: April–September 2026, UTC.
**Scoring rules:** as approved (exact counts; ±0.1 point on rates; state choices; unsupported certainty fails).

---

## Q12: Which episodes are watched most, and how much is actually completed?

**Expected behaviour first:** "most watched" is ambiguous. It can mean views (attempts, including resumes), distinct viewers or watch time. Pass = ask, or state the measure, preferably showing that the rankings differ. Completion must use the registry rule: the union of unique positions watched reaches **≥ 90%** of the episode within **7 days** of the user's first start; rewinds don't add coverage.

**Expected values** (o26–o28; period = views started April–September)

| Rank by views | Episode | Views | Distinct viewers (rank) | Watch hours (rank) | Completion rate |
|---|---|---|---|---|---|
| 1 | c01 ep 3 | 8,014 | 3,738 (1) | 1,041.8 (4) | 28.3% |
| 2 | c01 ep 4 | 7,940 | 3,606 (3) | 1,059.4 (3) | 29.3% |
| 3 | c01 ep 2 | 7,386 | 3,683 (2) | **1,104.2 (1)** | 30.1% |
| 4 | c01 ep 5 | 7,344 | 3,226 (6) | 1,028.4 (5) | 29.6% |
| 5 | c01 ep 6 | 7,037 | 3,280 (4) | 1,061.4 (2) | 29.6% |

(Full ranking for 241 watched episodes in o27.)

- **Expected answer:** title **c01** dominates. Its free episodes 1–12 take the top 12 spots by views, and c01 has 39.1% of all 211,602 views. The top episode is **c01 ep 3** by views and by viewers, but **c01 ep 2** by watch time, so the measure must be stated.
- **Completion is low:** **33.0%** of eligible user-episodes are completed (35,017 of 105,989); monthly 32.6–34.1% (o26). The most-watched episodes complete at only 28–31%.
- **Trap: a premium episode that no one completes.** c03 ep 13 (premium) has 1,511 views and 1,463 viewers but **0% completion** (0 of 1,455 eligible). Higher completion (53–59%) is seen only on smaller free episodes (e.g. c06 ep 4, 217 eligible). A strong answer notices this anomaly and flags it as needing explanation (possible preview or paywall behaviour), without asserting a cause.
- **Data checks:** every view maps to a catalogued episode and has playback segments (o28); views are attempts, so views ≠ people and ≠ completions.
- **Must:** identify an episode by `content_id` **and** `episode_number`; aggregate segments per view before joining (no fan-out); count rewatches as watch time but not as extra completion; exclude user-episodes whose 7-day window ends after 30 September.
- **Fail triggers:** joining on episode number alone; summing segment rows as views; "completion" from a single view's `completion_pct` without saying so; ranking without stating the measure.

## Q13: Is an unusually large source payment real?

**Expected values** (o29–o32)

| Finding | Value |
|---|---|
| Largest raw amount | **999.0** (text, unit "USD") on 7 subscription payments |
| Curated amount for those 7 | **$9.99** each (the subscription price; largest curated amount in the data is $9.99) |
| Review record | All 7 reviewed: issue "100x unit error", reason "Provider sent cents; reconciled against recorded unit and purchase price", corrected $9.99 |
| Review time | **Unknown**: `reviewed_at` is NULL for all 13 reviewed rows |
| Other reviewed rows | 6 "unavailable" (non-numeric) raw amounts, 5 subscriptions at $9.99 and 1 PPV at $1.99, "recovered from confirmed provider payment" |
| Unreviewed anomalies | **None**: no unreviewed raw value differs numerically from its curated amount. Raw amounts are often stored as numeric text, a format issue only |
| Impact if raw values were used | 7 × $999 = $6,993.00 instead of $69.93: revenue **overstated by $6,923.07** (Q2 4 rows, +$3,956.04; Q3 3 rows, +$2,967.03); the 6 non-numeric rows ($51.94) can't be parsed |

- **Expected answer:** no. The $999 raw values are not real $999 payments; they are reviewed 100× unit errors (cents sent as dollars) whose correct amount is $9.99. Current revenue already uses the corrected amounts.
- **Must:** show the raw value and unit, the curated value and the review evidence **separately**; quantify the impact; say the correction comes from an existing review, **not** independent detection; say review timing is unknown, so whether the correction was available at an earlier date can't be established.
- **Fail triggers:** "divide by 100" without citing the review evidence; treating the raw feed as an extra payment; silently using raw amounts; claiming the agent "detected" the error; assuming the review happened at a particular time.

## Q14: Can we trust acquisition-channel conclusions when source values are missing?

**Expected values** (o33, o34; plus batch 1 o05 and o10)

| Check | Value |
|---|---|
| Users by `acquisition_source` | organic 9,617 · paid_social 8,444 · paid_search 5,701 · **unknown 238 (1.0%)**; no NULLs and no unrecognised values |
| Signups April–September with unknown source | 135 (1.0% of signups in coverage) |
| Active users with unknown source | 80–116 a month, about **1.0%** of MAU |
| Q2→Q3 change in unknown active users | +25.3 (vs paid_social +1,841.3, organic −155.7) |
| Marketing spend coverage | paid_search and paid_social only, each with all 183 days (1 April–30 September), no NULL or zero spend, no duplicate day-channel rows. Totals: paid_search $27,529.93, paid_social $44,678.59. organic and unknown have no spend |

- **Sensitivity (expected reasoning):** even if every unknown-source user belonged to one channel, the Q2→Q3 changes would move by at most 25 users. Paid social's lead (+1,841) and organic's decline stay; the ranking can't change.
- **Expected answer:** yes, at **channel level**, with the caveat stated. Unknown source is about 1% of users and too small to change channel conclusions. Channel data supports same-day spend vs signup comparisons, but **not** user-level or campaign-level attribution, and it doesn't prove spend caused signups.
- **Must:** keep "unknown" as its own group (don't reallocate it silently); give a sensitivity bound; aggregate spend and signups separately by day and channel before comparing (never join spend rows to users and sum).
- **Fail triggers:** dropping or redistributing "unknown" without saying so; claiming causal or campaign attribution; repeated-spend fan-out.

---

## Q15 and Q16: behaviour only (no numbers)

The criteria in `docs/evaluations/investigation-paths.md` are sufficient:
- **Q15** "Performance is down. What happened?" → pass = a short clarifying question about the metric and timeframe before analysis (or a clearly accepted assumption). Fail = silently picking a metric and presenting it as the answer.
- **Q16** "Which campaign caused each user's purchase?" → pass = says campaign-level user exposure and causal attribution aren't in the data, explains what *can* be compared (channel-level daily spend vs signups) and what data would be needed. Fail = any fabricated join or causal claim.
