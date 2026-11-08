# Metric Registry

**Scope:** Shared, model-neutral metric definitions for the analytics agent. Claude Code and Codex use the same definitions; runtime-specific instructions must not redefine them.

**Status of this registry:** Template agreed. Metric definitions are added one at a time and are approved individually by the user. Approved: `mau`. The Gold/Silver tables named in a definition are planned unless stated otherwise; the registry is not yet integrated with a working agent.

## Registry rules

- Each metric has an `id`, a `version` and a `status`. `draft` means under review and not to be relied on. `approved` means the user has accepted the definition. A material change to an approved definition increases its version.
- Canonical SQL runs against the current PocketToons SQLite fixture tables unless it names a planned layer table, which is marked as planned.
- The registry contains definitions only. Expected values for the synthetic fixture belong in tests or evaluation files kept outside the agent's investigation context.
- Table meanings, keys and joins come from the [data catalog](../examples/pockettoons-data-catalog.md) and the [reference data model](../examples/pockettoons-reference-data-model-v1.md). A metric definition must not contradict them.
- Each quality check is marked **implemented and tested** or **proposed**.
- A request that differs from a registered definition uses a registered alternative when one exists. Otherwise the result is labelled as an ad hoc variant, is not reported under the registered metric's name and is shown with its SQL. The evidence log records the definition used: registry id and version, or ad hoc with its SQL.
- A proposed metric is named for future definition only; it has no approved semantics and must not be computed as if it were registered.

## Definition template

```text
## <Metric name>        id: <id>   version: <x.y>   status: draft | approved

1. Business meaning       What question the metric answers.
2. Population             Entity counted and identity rules.
3. Activity / event rule  Exactly what qualifies.
4. Formula                Numerator and denominator, or the count/sum with no denominator.
5. Grain and time         Reporting period, timestamp used, time zone, period boundaries, partial periods.
6. Sources and layers     Current fixture tables; planned Silver/Gold tables marked as planned.
7. Canonical SQL          Runnable against the current fixture.
8. Filters / dimensions   Supported slices and how an entity is assigned to a slice.
9. Null, status and refund rules
10. Aggregation safety    What must not be summed or averaged, and the correct roll-up.
11. Quality checks        Each marked implemented and tested, or proposed.
12. Caveats               Known limitations.
```

## Metrics

### MAU — Monthly active users        id: mau   version: 1.0   status: approved

1. **Business meaning.** How many distinct people used the product in a UTC calendar month. It answers "how many people are active in a month?", not "how many watched" (see the proposed `monthly_active_viewers`).

2. **Population.** Distinct resolved users. A session's resolved user is `sessions.user_id`; when that is NULL, it is the single user of the login/signup `identity_links` recorded in **the same session**. A session with no link, or with links to more than one user, is unidentified and excluded. Activity is never attributed to a user across sessions by `anonymous_id` or device, and anonymous IDs are never counted as people.

3. **Activity rule.** A user is active in a month if they have at least one session whose active span, from `session_started_at` (inclusive) to `last_activity_at` (inclusive), overlaps that month. A session does not need a content view. Open sessions use `last_activity_at` and are not assumed to continue.

4. **Formula.** Distinct count of resolved users per month; no denominator.

5. **Grain and time.** One value per complete UTC calendar month, `[month start, next month start)`. A session counts in every month its active span touches; a user counts at most once per month. Only months fully inside the data's activity coverage window are reported. A partial month is labelled month-to-date and is not compared with complete months or used in a quarter average.

6. **Sources and layers.** Current fixture: `sessions`, `identity_links`. Planned (not implemented): a Silver resolved-session table and a Gold monthly MAU mart at month grain.

7. **Canonical SQL.** Parameters: `:coverage_start` and `:coverage_end` are the activity coverage window as UTC month-start timestamps in fixture format, with `:coverage_end` exclusive. Output: one row per complete month with `mau` and the count of unidentified sessions that were excluded.

```sql
-- metric: mau_monthly
WITH RECURSIVE months(month_start) AS (
  SELECT :coverage_start
  UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') FROM months
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') < :coverage_end
),
resolved AS (
  SELECT s.session_id, s.session_started_at, s.last_activity_at,
         COALESCE(s.user_id,
                  (SELECT MIN(l.user_id) FROM identity_links l
                   WHERE l.session_id = s.session_id
                   HAVING COUNT(DISTINCT l.user_id) = 1)) AS resolved_user_id
  FROM sessions s
),
month_activity AS (
  SELECT m.month_start, r.session_id, r.resolved_user_id
  FROM months m
  LEFT JOIN resolved r
    ON r.session_started_at < strftime('%Y-%m-%dT%H:%M:%SZ', m.month_start, '+1 month')
   AND r.last_activity_at >= m.month_start
)
SELECT substr(month_start, 1, 7) AS month,
       COUNT(DISTINCT resolved_user_id) AS mau,
       COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND resolved_user_id IS NULL
                           THEN session_id END) AS unidentified_sessions
FROM month_activity
GROUP BY month_start
ORDER BY month_start
```

Quarter MAU is the average of the three complete monthly values, applied to the result of `mau_monthly`; a quarter with fewer than three complete months is not reported.

```sql
-- metric: mau_quarter_average
SELECT substr(month, 1, 4) || '-Q' || ((CAST(substr(month, 6, 2) AS INTEGER) + 2) / 3) AS quarter,
       AVG(mau) AS quarter_average_mau
FROM mau_monthly
GROUP BY quarter
HAVING COUNT(*) = 3
ORDER BY quarter
```

8. **Filters and dimensions.**
   - *Activity-level* (`sessions.platform`, `sessions.country_at_event`): a user counts in every slice in which they had a qualifying session that month. Slices can overlap; never sum them, and take total MAU from the unsliced query. A NULL country is reported as `unknown`. Historical location uses `country_at_event`, not the `users` snapshot country.
   - *User-level fixed* (`users.acquisition_source`, signup month): each user is in exactly one slice, so slices add to the total. `unknown` acquisition is a separate slice and is never reallocated.
   - *Not supported:* subscription status or plan, and other time-varying user states, until an as-of rule is defined. Such a request is answered as unsupported or as a labelled ad hoc variant.

```sql
-- metric: mau_monthly_by_platform
WITH RECURSIVE months(month_start) AS (
  SELECT :coverage_start
  UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') FROM months
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') < :coverage_end
),
resolved AS (
  SELECT s.session_id, s.session_started_at, s.last_activity_at, s.platform,
         COALESCE(s.user_id,
                  (SELECT MIN(l.user_id) FROM identity_links l
                   WHERE l.session_id = s.session_id
                   HAVING COUNT(DISTINCT l.user_id) = 1)) AS resolved_user_id
  FROM sessions s
)
SELECT substr(m.month_start, 1, 7) AS month, r.platform,
       COUNT(DISTINCT r.resolved_user_id) AS mau
FROM months m
JOIN resolved r
  ON r.session_started_at < strftime('%Y-%m-%dT%H:%M:%SZ', m.month_start, '+1 month')
 AND r.last_activity_at >= m.month_start
WHERE r.resolved_user_id IS NOT NULL
GROUP BY m.month_start, r.platform
ORDER BY m.month_start, r.platform
```

9. **Null, status and refund rules.** NULL `user_id` follows the population rule. Subscription status, payments and refunds do not affect MAU: free, subscribed and paying users count equally.

10. **Aggregation safety.** MAU is non-additive. Do not sum it across months, quarters, or activity-level slices. Quarter MAU is the average of complete monthly MAUs; distinct users across a quarter is a different metric.

11. **Quality checks.**
    - Implemented and tested: the fixture checker computes monthly MAU and the quarter-average change from this registry's `mau_monthly` SQL; isolated tests cover month-boundary sessions, same-session login resolution, unidentified and ambiguous sessions, no cross-session device attribution, overlapping platform slices, quarter averaging and partial-month exclusion. Existing catalog checks validate session timestamps, identity links and activity evidence.
    - Proposed: declare the activity coverage window in `dataset_metadata` and check that reported months are fully covered.

12. **Caveats.** The PocketToons fixture's coverage window is `2026-04-01T00:00:00Z` to `2026-10-01T00:00:00Z` (April–September), taken from the documented dataset contract rather than declared in the data. In the fixture every session has a `user_id` and no session crosses a month boundary; those cases are exercised only by isolated tests. Unidentified sessions are excluded from MAU and should be reported alongside it.

## Proposed metrics

| id | Intended meaning | Status |
|---|---|---|
| monthly_active_viewers | Distinct users who started at least one content view in a UTC calendar month; a stricter companion to MAU. | Proposed; not defined |
