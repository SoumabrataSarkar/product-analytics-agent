# Metric Registry

**Scope:** Shared, model-neutral metric definitions for the analytics agent. Claude Code and Codex use the same definitions; runtime-specific instructions must not redefine them.

**Status of this registry:** Template agreed. Metric definitions are added one at a time and are approved individually by the user. Approved: `mau`, the activity family (`dau`, `wau`, `deu`, `weu`, `meu`), `stickiness`, `engaged_stickiness`, `engagement_rate` and `growth_accounting_monthly`. The Gold/Silver tables named in a definition are planned unless stated otherwise; the registry is not yet integrated with a working agent.

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

1. **Business meaning.** How many distinct people used the product in a UTC calendar month. It answers "how many people are active in a month?", not "how many watched" (see `meu`).

2. **Population.** Distinct resolved users. A session's resolved user is `sessions.user_id`; when that is NULL, it is the single user of the login/signup `identity_links` recorded in **the same session**. A session with no link, or with links to more than one user, is unidentified and excluded. Activity is never attributed to a user across sessions by `anonymous_id` or device, and anonymous IDs are never counted as people.

3. **Activity rule.** A user is active in a month if they have at least one session whose active span, from `session_started_at` (inclusive) to `last_activity_at` (inclusive), overlaps that month. A session does not need a content view; users who watched are counted by `meu`. Open sessions use `last_activity_at` and are not assumed to continue.

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

### Activity family: DAU, WAU, DEU, WEU, MEU        version: 1.0   status: approved

| id | Name | Period | Qualifying rule |
|---|---|---|---|
| `dau` | Daily active users | UTC day | Active, as in `mau` |
| `wau` | Weekly active users | ISO week, Monday 00:00 UTC to the next Monday | Active, as in `mau` |
| `mau` | Monthly active users | UTC calendar month | Approved definition above |
| `deu` | Daily engaged users | UTC day | Engaged |
| `weu` | Weekly engaged users | ISO week (UTC) | Engaged |
| `meu` | Monthly engaged users | UTC calendar month | Engaged |

1. **Business meaning.** Active metrics count people who used the product in a period; engaged metrics count people who actually watched content in it.
2. **Population.** Active: resolved users exactly as in `mau`. Engaged: the authenticated viewer recorded in `content_views.user_id` (playback requires an authenticated user, so no identity resolution is needed).
3. **Qualifying rule.** *Active:* a session whose span from `session_started_at` to `last_activity_at` (both inclusive) overlaps the period. *Engaged:* at least 60 seconds of watch time within the period, summed over all of the user's playback segments. A segment's `watch_duration_sec` is allocated to periods in proportion to the share of its wall-clock interval inside each period; a zero-length segment is allocated to the period containing it.
4. **Formula.** Distinct count of qualifying users per period; no denominator.
5. **Grain and time.** One value per complete UTC day, complete ISO week or complete UTC month, half-open `[start, next start)`. Only periods fully inside the activity coverage window are reported; a week that starts or ends outside it is not reported. Week labels are the Monday start date.
6. **Sources and layers.** Current fixture: `sessions`, `identity_links` (active); `content_views`, `playback_segments` (engaged). Planned (not implemented): Silver resolved sessions and period-allocated watch time; Gold daily, weekly and monthly activity marts.
7. **Canonical SQL.** The building blocks and metric blocks below. Parameters are the same coverage window as `mau`.
8. **Filters and dimensions.** Same rules as `mau`. For engaged metrics, activity-level slices use the view's or session's attributes.
9. **Null, status and refund rules.** As `mau`; payment and subscription state do not affect activity or engagement.
10. **Aggregation safety.** All are distinct counts and non-additive: never sum days into weeks or months, or weeks into months. A monthly figure for a daily metric is reported as an average over the month's complete days and labelled as such ("average DAU").
11. **Quality checks.** Implemented and tested: isolated tests for each metric's period boundaries, coverage, the 60-second threshold and proportional allocation; the fixture checker verifies that the shared active-user block reproduces `mau_monthly`. Proposed: as for `mau`.
12. **Caveats.** The fixture includes playback abandoned within the first minute, so engaged counts are lower than "started a view" counts. The first and last partial ISO weeks of the coverage window are not reported.

#### Shared building blocks

```sql
-- metric: periods_day
WITH RECURSIVE p(period_start) AS (
  SELECT :coverage_start
  UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 day') FROM p
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 day') < :coverage_end
)
SELECT substr(period_start, 1, 10) AS period, period_start,
       strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 day') AS period_end
FROM p
WHERE strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 day') <= :coverage_end
```

```sql
-- metric: periods_week
WITH RECURSIVE p(period_start) AS (
  SELECT strftime('%Y-%m-%dT00:00:00Z', :coverage_start, 'weekday 1')
  UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+7 days') FROM p
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+7 days') < :coverage_end
)
SELECT substr(period_start, 1, 10) AS period, period_start,
       strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+7 days') AS period_end
FROM p
WHERE period_start >= :coverage_start
  AND strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+7 days') <= :coverage_end
```

```sql
-- metric: periods_month
WITH RECURSIVE p(period_start) AS (
  SELECT :coverage_start
  UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') FROM p
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') < :coverage_end
)
SELECT substr(period_start, 1, 7) AS period, period_start,
       strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') AS period_end
FROM p
WHERE strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') <= :coverage_end
```

```sql
-- metric: resolved_sessions
SELECT s.session_id, s.session_started_at, s.last_activity_at, s.platform, s.country_at_event,
       COALESCE(s.user_id,
                (SELECT MIN(l.user_id) FROM identity_links l
                 WHERE l.session_id = s.session_id
                 HAVING COUNT(DISTINCT l.user_id) = 1)) AS resolved_user_id
FROM sessions s
```

The next two blocks read a `periods` table supplied by the metric that uses them.

```sql
-- metric: active_users
-- requires: resolved_sessions
SELECT p.period, p.period_start, COUNT(DISTINCT r.resolved_user_id) AS users
FROM periods p
LEFT JOIN resolved_sessions r
  ON r.session_started_at < p.period_end AND r.last_activity_at >= p.period_start
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: engaged_users
SELECT p.period, p.period_start, COUNT(e.user_id) AS users
FROM periods p
LEFT JOIN (
  SELECT q.period_start, v.user_id,
         SUM(s.watch_duration_sec *
             CASE WHEN julianday(s.segment_ended_at) = julianday(s.segment_started_at) THEN 1.0
                  ELSE (MIN(julianday(s.segment_ended_at), julianday(q.period_end))
                        - MAX(julianday(s.segment_started_at), julianday(q.period_start)))
                       / (julianday(s.segment_ended_at) - julianday(s.segment_started_at))
             END) AS watched_sec
  FROM periods q
  JOIN playback_segments s
    ON s.segment_started_at < q.period_end
   AND (s.segment_ended_at > q.period_start
        OR (s.segment_ended_at = s.segment_started_at AND s.segment_started_at >= q.period_start))
  JOIN content_views v ON v.view_id = s.view_id
  GROUP BY q.period_start, v.user_id
  HAVING watched_sec >= 60
) e ON e.period_start = p.period_start
GROUP BY p.period_start
ORDER BY p.period_start
```

#### Metric blocks

```sql
-- metric: dau
-- requires: periods=periods_day, active_users
SELECT period AS day, users AS dau FROM active_users ORDER BY day
```

```sql
-- metric: wau
-- requires: periods=periods_week, active_users
SELECT period AS week_start, users AS wau FROM active_users ORDER BY week_start
```

```sql
-- metric: mau_from_family
-- requires: periods=periods_month, active_users
SELECT period AS month, users AS mau FROM active_users ORDER BY month
```

`mau_from_family` exists to verify that the shared block reproduces the approved `mau_monthly`; report MAU from `mau_monthly`.

```sql
-- metric: deu
-- requires: periods=periods_day, engaged_users
SELECT period AS day, users AS deu FROM engaged_users ORDER BY day
```

```sql
-- metric: weu
-- requires: periods=periods_week, engaged_users
SELECT period AS week_start, users AS weu FROM engaged_users ORDER BY week_start
```

```sql
-- metric: meu
-- requires: periods=periods_month, engaged_users
SELECT period AS month, users AS meu FROM engaged_users ORDER BY month
```

### Stickiness and engagement rate        version: 1.0   status: approved

| id | Formula | Meaning |
|---|---|---|
| `stickiness` | average DAU over the month's complete days ÷ MAU | Share of a typical monthly user's days on which they are active; 1.0 means every monthly user is active every day. |
| `engaged_stickiness` | average DEU over the month's complete days ÷ MEU | The same for engaged users. |
| `engagement_rate` | MEU ÷ MAU | Share of monthly active users who watched at least 60 seconds. |

All three are monthly ratios of distinct counts for the same complete month. They are not additive: a quarter value is computed from the quarter's months only on an explicit request and labelled as an average of monthly ratios, never as a ratio of summed counts. A month with a zero denominator reports NULL. Sources, population and quality checks are those of the component metrics; isolated tests cover each formula and the zero-denominator case.

```sql
-- metric: stickiness
-- requires: daily=dau, monthly=mau_monthly
SELECT m.month, AVG(d.dau) AS average_dau, m.mau,
       AVG(d.dau) / NULLIF(m.mau, 0) AS stickiness
FROM monthly m JOIN daily d ON substr(d.day, 1, 7) = m.month
GROUP BY m.month
ORDER BY m.month
```

```sql
-- metric: engaged_stickiness
-- requires: daily=deu, monthly=meu
SELECT m.month, AVG(d.deu) AS average_deu, m.meu,
       AVG(d.deu) / NULLIF(m.meu, 0) AS engaged_stickiness
FROM monthly m JOIN daily d ON substr(d.day, 1, 7) = m.month
GROUP BY m.month
ORDER BY m.month
```

```sql
-- metric: engagement_rate
-- requires: active=mau_monthly, engaged=meu
SELECT a.month, e.meu, a.mau, e.meu * 1.0 / NULLIF(a.mau, 0) AS engagement_rate
FROM active a JOIN engaged e ON e.month = a.month
ORDER BY a.month
```

### Monthly growth accounting        id: growth_accounting_monthly   version: 1.0   status: approved

1. **Business meaning.** Explains the change in MAU from one complete month to the next.
2. **Population.** Resolved active users as in `mau`; account creation time from `users.signup_at`.
3. **Buckets for month M**, each user in exactly one:
   - *new:* active in M and signed up in M;
   - *retained:* active in M and in M−1;
   - *resurrected:* active in M, not active in M−1, and signed up before M (this includes users whose first activity comes after their signup month);
   - *churned:* active in M−1 and not active in M.
4. **Formula.** MAU(M) = new + retained + resurrected, and MAU(M) − MAU(M−1) = new + resurrected − churned. Quick ratio = (new + resurrected) ÷ churned, NULL when churned is zero.
5. **Grain and time.** One row per complete month M whose previous month is also complete inside the coverage window, so the first coverage month is not reported.
6. **Sources and layers.** `sessions`, `identity_links`, `users`. Planned: a Gold monthly growth-accounting mart.
7. **Canonical SQL.** Below.
8. **Filters and dimensions.** User-level fixed dimensions only (`acquisition_source`, signup month); activity-level slices are not supported because a user's bucket would depend on the slice.
9. **Null, status and refund rules.** As `mau`.
10. **Aggregation safety.** Bucket counts for one month add to that month's MAU. Do not sum buckets across months as distinct users.
11. **Quality checks.** Implemented and tested: isolated tests for every bucket and both identities; the fixture checker verifies both identities against `mau_monthly`. The bucket partition relies on the existing check that no session precedes its user's signup.
12. **Caveats.** "New" is based on signup month rather than first observed activity, so the result does not depend on activity before the coverage window. Users who signed up before the coverage window and first appear later are counted as resurrected.

```sql
-- metric: growth_accounting_monthly
-- requires: periods=periods_month, resolved_sessions
WITH active AS (
  SELECT DISTINCT p.period_start, r.resolved_user_id AS user_id
  FROM periods p
  JOIN resolved_sessions r
    ON r.session_started_at < p.period_end AND r.last_activity_at >= p.period_start
  WHERE r.resolved_user_id IS NOT NULL
),
pairs AS (
  SELECT cur.period AS month, cur.period_start, prev.period_start AS prev_start
  FROM periods cur JOIN periods prev ON prev.period_end = cur.period_start
),
buckets AS (
  SELECT pr.month, pr.period_start,
    (SELECT COUNT(*) FROM active a JOIN users u ON u.user_id = a.user_id
     WHERE a.period_start = pr.period_start AND u.signup_at >= pr.period_start) AS new_users,
    (SELECT COUNT(*) FROM active a
     WHERE a.period_start = pr.period_start
       AND EXISTS (SELECT 1 FROM active b WHERE b.user_id = a.user_id AND b.period_start = pr.prev_start)) AS retained_users,
    (SELECT COUNT(*) FROM active a JOIN users u ON u.user_id = a.user_id
     WHERE a.period_start = pr.period_start AND u.signup_at < pr.period_start
       AND NOT EXISTS (SELECT 1 FROM active b WHERE b.user_id = a.user_id AND b.period_start = pr.prev_start)) AS resurrected_users,
    (SELECT COUNT(*) FROM active b
     WHERE b.period_start = pr.prev_start
       AND NOT EXISTS (SELECT 1 FROM active a WHERE a.user_id = b.user_id AND a.period_start = pr.period_start)) AS churned_users
  FROM pairs pr
)
SELECT month, new_users, retained_users, resurrected_users, churned_users,
       (new_users + resurrected_users) * 1.0 / NULLIF(churned_users, 0) AS quick_ratio
FROM buckets
ORDER BY period_start
```

## Proposed metrics

| id | Intended meaning | Status |
|---|---|---|
| active_days_distribution | Number of users active on 1, 2, … N days of a period (power-user curve). | Proposed; not defined |
| sessions_per_active_user | Sessions per active user in a period. | Proposed; not defined |
| watch_time_per_engaged_user | Period-allocated watch seconds per engaged user. | Proposed; not defined |
