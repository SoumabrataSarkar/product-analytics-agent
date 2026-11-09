# Answer key, batch 4: filtered queries (Q17–Q18)

**Status:** Approved by evaluator, 2026-11-09. **Evaluator-only:** keep out of every agent run and out of the repository.
**Why this batch:** the assignment lists "Filtered queries (US-only subscribers, mobile sessions)" as a required question type; Q01–Q16 cover it only partly (Q05).
**Reference method (oracle):** the metric registry's canonical SQL on **source tables only** (`subscription_access_periods`, `active_subscribers_monthly`, `resolved_sessions`), with a country or platform filter added. Logs: `oracle-b4/o35…o40.jsonl` (6 queries, none truncated).
**Snapshot:** `pockettoons.sqlite` SHA-256 `8d39e78b…790b`, build `3a0dbed2`. Coverage: complete UTC months, April–September 2026.
**Scoring rules:** as approved with batch 1 (exact counts; ±0.1 point on rates; a stated, defensible choice passes; a silent choice that changes the number fails).

---

## Q17: How many US users had an active subscription at the end of September?

**Expected values** (supporting metrics 1.1 `active_subscribers`; o36, o37, o39). A subscriber is a user with subscription access (status `active` or `cancel_at_period_end`) covering the instant **2026-10-01 00:00:00 UTC**, the end of September.

| | Users |
|---|---|
| **US subscribers at end of September** | **349** |
| of which still renewing (`active`) | 312 |
| of which cancelled but paid up to period end (`cancel_at_period_end`) | 37 |
| All countries, end of September | 1,011 (US = 34.5%) |

- Other countries at the same instant: BR 176, PH 163, MX 142, ID 103, TH 78 (sum 1,011).
- `users.subscription_status` (snapshot as of 2026-09-30 23:59:59Z) agrees exactly with the history for US users (o39): 312 + 37 have access, 154 expired, 6,724 never subscribed.
- Country is the user's `users.country` (a fixed user-level dimension), as the registry prescribes for subscriber slices.
- **Expected answer:** 349 US subscribers at the end of September.
- **Must:** say which instant "end of September" means; count `cancel_at_period_end` users as subscribers (they still have access), or state clearly that only renewing subscribers were counted.
- **Pass with a stated choice:** 312, if the answer says it counts only subscribers who will renew and gives 349 as the access-based figure, or explains the difference.
- **Fail triggers:** 312 with no explanation (silently drops 37 people who still have access); counting everyone who ever subscribed (503); using country at payment time without saying so.

## Q18: How many mobile sessions were there in September versus August?

**Expected values** (`resolved_sessions`; the session count behind `sessions_per_active_user`, sliced by `sessions.platform`; o35, o40). Platforms in the data: `android`, `ios`, `web`. "Mobile" = `android` + `ios`. A session counts in a month if its active span overlaps the month.

| | August | September | Change |
|---|---|---|---|
| Android | 20,085 | 21,070 | +4.9% |
| iOS | 16,210 | 17,296 | +6.7% |
| **Mobile (all sessions)** | **36,295** | **38,366** | **+5.7%** |
| Mobile (identified sessions only) | 33,650 | 35,516 | +5.5% |
| Web | 9,946 | 10,349 | +4.1% |
| All platforms | 46,241 | 48,715 | +5.4% |
| Mobile share of sessions | 78.5% | 78.8% | +0.3 pt |
| Mobile sessions per day | 1,170.8 (31 days) | 1,278.9 (30 days) | +9.2% |

- **Expected answer:** mobile sessions rose from 36,295 in August to 38,366 in September (+5.7%). Identified-only counts (33,650 → 35,516, +5.5%) are also acceptable if labelled.
- **Must:** state that mobile means iOS + Android (web is not counted as mobile; the data can't tell mobile browsers apart); say whether all sessions or identified sessions only are counted.
- **Optional, earns credit:** September has one day fewer, so per-day growth is larger (+9.2%); one iOS session starts in August and continues into September, so it counts in both months (the overlap rule). This contradicts the registry's caveat that no fixture session crosses a month boundary, and is worth reporting.
- **Fail triggers:** including web as mobile without saying so; mixing all and identified sessions between the two months; counting distinct users instead of sessions without saying so.
