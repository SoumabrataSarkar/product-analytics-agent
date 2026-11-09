# Metric Registry

**Scope:** Shared, model-neutral metric definitions for the analytics agent. Claude Code and Codex use the same definitions; runtime-specific instructions must not redefine them.

**Status of this registry:** Template agreed. Metric definitions are added one at a time and are approved individually by the user. Approved: `mau`, the activity family (`dau`, `wau`, `deu`, `weu`, `meu`), `stickiness`, `engaged_stickiness`, `engagement_rate`, `growth_accounting_monthly` and the revenue group (`net_revenue`, `subscription_net_revenue`, `ppv_net_revenue`, `arpu`, `arppu`) and the funnel and lifecycle group, the engagement group and the supporting metrics. Every metric in the metric map is defined. Canonical SQL runs on the source tables; the Silver and Gold tables in the [PocketToons layer contracts](../data-layers/pockettoons-layer-contracts.md) reproduce these definitions and are reconciled against this SQL at every build. The registry is not yet integrated with an evaluated end-to-end agent.

## Registry rules

- Each metric has an `id`, a `version` and a `status`. `draft` means under review and not to be relied on. `approved` means the user has accepted the definition. A material change to an approved definition increases its version.
- Canonical SQL runs against the current PocketToons SQLite fixture tables and must run on SQLite 3.37 or later. Layer tables that reproduce a definition are named in its sources-and-layers field.
- The registry contains definitions only. Expected values for the synthetic fixture belong in tests or evaluation files kept outside the agent's investigation context.
- Table meanings, keys and joins come from the [data catalog](../examples/pockettoons-data-catalog.md) and the [reference data model](../examples/pockettoons-reference-data-model-v1.md). A metric definition must not contradict them.
- Each quality check is marked **implemented and tested** or **proposed**.
- A request that differs from a registered definition uses a registered alternative when one exists. Otherwise the result is labelled as an ad hoc variant, is not reported under the registered metric's name and is shown with its SQL. The evidence log records the definition used: registry id and version, or ad hoc with its SQL.
- A proposed metric is named for future definition only; it has no approved semantics and must not be computed as if it were registered.
- Canonical SQL must run on SQLite 3.37 or later. For example, `HAVING` needs a `GROUP BY` clause before it (required before SQLite 3.39).

## Metric map

The registry targets a bounded core set for this product rather than every possible metric. A question that needs a metric outside the map is answered from registered building blocks as a labelled ad hoc variant, or as unsupported.

| Group | Defined | Planned |
|---|---|---|
| Activity | `mau`, `dau`, `wau`, `deu`, `weu`, `meu`, `stickiness`, `engaged_stickiness`, `engagement_rate`, `growth_accounting_monthly`, `new_signups`, `activation_7d`, `sessions_per_active_user`, `session_duration`, `active_days_distribution` | — |
| Engagement | watch time, watch time per engaged user, views per viewer, episode completion, series continuation, title reach, free-quota hit rate, paywall exposure rate | — |
| Revenue | `net_revenue`, `subscription_net_revenue`, `ppv_net_revenue`, `arpu`, `arppu`, `paying_users`, `active_subscribers`, `mrr`, `refund_rate`, `payment_failure_rate` | — |
| Funnel and lifecycle | 30-day subscription and paid conversion, subscriber churn, D1/D7/D30 retention, monthly cohort retention, paywall funnel, `cancellation_request_rate`, `resubscription_rate_60d` | — |
| Marketing | `marketing_ctr`, `marketing_spend`, `marketing_cpc`, `cost_per_signup`, `marketing_cac` | — |

**Not supported by this data.** The agent states that these cannot be answered from the fixture rather than approximating them:

| Request | Reason |
|---|---|
| Customer lifetime value (LTV) | Six months of history is too short for a defensible lifetime. |
| NPS, satisfaction or survey results | No survey data. |
| Advertising revenue or ad metrics | The product has no ads. |
| Revenue net of provider fees, app-store commission or tax | No fee, commission or tax data. |
| Free-trial metrics | There are no trials. |
| Push, email or notification metrics | No messaging data. |
| Search, recommendation or in-app click-through metrics | No search or recommendation events; only paywall and checkout navigation is captured. |
| App performance, crashes or latency | No technical telemetry. |
| Campaign-level ROAS or attribution beyond channel | Marketing data is daily channel totals without campaign-to-user links. |

## Definition template

```text
## <Metric name>        id: <id>   version: <x.y>   status: draft | approved

1. Business meaning       What question the metric answers.
2. Population             Entity counted and identity rules.
3. Activity / event rule  Exactly what qualifies.
4. Formula                Numerator and denominator, or the count/sum with no denominator.
5. Grain and time         Reporting period, timestamp used, time zone, period boundaries, partial periods.
6. Sources and layers     Current fixture tables; the Silver/Gold tables that reproduce the definition.
7. Canonical SQL          Runnable against the current fixture.
8. Filters / dimensions   Supported slices and how an entity is assigned to a slice.
9. Null, status and refund rules
10. Aggregation safety    What must not be summed or averaged, and the correct roll-up.
11. Quality checks        Each marked implemented and tested, or proposed.
12. Caveats               Known limitations.
```

## Metrics

### MAU — Monthly active users        id: mau   version: 1.1   status: approved

1. **Business meaning.** How many distinct people used the product in a UTC calendar month. It answers "how many people are active in a month?", not "how many watched" (see `meu`).

2. **Population.** Distinct resolved users. A session's resolved user is `sessions.user_id`; when that is NULL, it is the single user of the login/signup `identity_links` recorded in **the same session**. A session with no link, or with links to more than one user, is unidentified and excluded. Activity is never attributed to a user across sessions by `anonymous_id` or device, and anonymous IDs are never counted as people.

3. **Activity rule.** A user is active in a month if they have at least one session whose active span, from `session_started_at` (inclusive) to `last_activity_at` (inclusive), overlaps that month. A session does not need a content view; users who watched are counted by `meu`. Open sessions use `last_activity_at` and are not assumed to continue.

4. **Formula.** Distinct count of resolved users per month; no denominator.

5. **Grain and time.** One value per complete UTC calendar month, `[month start, next month start)`. A session counts in every month its active span touches; a user counts at most once per month. Only months fully inside the data's activity coverage window are reported. A partial month is labelled month-to-date and is not compared with complete months or used in a quarter average.

6. **Sources and layers.** Current fixture: `sessions`, `identity_links`. Layers: `silver_resolved_sessions`, `silver_user_day_activity`; `gold_kpi_monthly` (`mau`, `unidentified_sessions`) and `gold_activity_segments_monthly` (platform and subscriber-status slices).

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
                   GROUP BY l.session_id
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
   - *Subscriber status* (activity-level): a session is assigned by whether its user is a subscriber, as defined in the lifecycle group, at `session_started_at`. A user can be in both slices in one month; slices are not summed. SQL: `mau_monthly_by_subscriber_status`.
   - *Not supported:* plan and other time-varying user states without a defined as-of rule. Such a request is answered as unsupported or as a labelled ad hoc variant.

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
                   GROUP BY l.session_id
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

12. **Caveats.** The PocketToons fixture's coverage window is `2026-04-01T00:00:00Z` to `2026-10-01T00:00:00Z` (April–September), taken from the documented dataset contract rather than declared in the data. Do not assume every session has an identified user or that sessions cannot cross a month boundary; check the chosen snapshot. Unidentified sessions are excluded from MAU and should be reported alongside it.

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
6. **Sources and layers.** Current fixture: `sessions`, `identity_links` (active); `content_views`, `playback_segments` (engaged). Layers: `silver_user_day_activity` (session-active days and day-split watch seconds); `gold_kpi_monthly` (MAU, MEU, monthly sums of daily DAU and DEU). Daily and weekly values are computed from Silver.
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
                 GROUP BY l.session_id
                 HAVING COUNT(DISTINCT l.user_id) = 1)) AS resolved_user_id
FROM sessions s
```

The `active_users`, `period_watch_seconds` and `engaged_users` blocks read a `periods` table supplied by the metric that uses them.

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
-- metric: period_watch_seconds
SELECT q.period_start, v.user_id, v.content_id,
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
GROUP BY q.period_start, v.user_id, v.content_id
```

```sql
-- metric: engaged_users
-- requires: period_watch_seconds
SELECT p.period, p.period_start, COUNT(e.user_id) AS users
FROM periods p
LEFT JOIN (
  SELECT period_start, user_id FROM period_watch_seconds
  GROUP BY period_start, user_id
  HAVING SUM(watched_sec) >= 60
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
6. **Sources and layers.** `sessions`, `identity_links`, `users`. Layers: `gold_growth_accounting_monthly`, from `silver_user_day_activity` and `silver_user_profile`.
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

### Revenue group: net revenue, subscription and PPV net revenue, ARPU, ARPPU        version: 1.1   status: approved

| id | Name | Formula (per complete UTC month) |
|---|---|---|
| `net_revenue` | Net revenue | Successful subscription and PPV charges − successful refunds; reported with gross charges and refunds |
| `subscription_net_revenue` | Subscription net revenue | `net_revenue` restricted to subscription charges and refunds of subscription charges |
| `ppv_net_revenue` | PPV net revenue | `net_revenue` restricted to PPV charges and refunds of PPV charges |
| `arpu` | Average revenue per user | `net_revenue` ÷ `mau` for the same month |
| `arppu` | Average revenue per paying user | `net_revenue` ÷ paying users in the same month |

1. **Business meaning.** Money the product earned in a month after refunds, how it splits between subscriptions and PPV, and how much it earned per active and per paying user.
2. **Population.** Transactions in `transactions`. A *paying user* is a user with at least one successful subscription or PPV charge in the month, whether or not it is later refunded. ARPU uses the `mau` population.
3. **Qualifying rule.** A transaction counts only if it has a `succeeded` event in `payment_status_history`, and it counts at that event's `effective_at`, not at creation time and not by the current `transactions.status`. Failed attempts count for nothing. Refunds are stored as positive amounts and subtracted. A refund counts in the month it succeeds, not in its original charge's month. A refund is assigned to the type of the charge it refunds through `related_txn_id`; a refund whose original charge is missing or never succeeded is `unattributed` and still reduces net revenue. A transaction counts only if its `amount_usd` is numeric, positive and exact to the cent, and it has exactly one `succeeded` event; otherwise it is excluded from revenue, not rounded or guessed, and is listed as an exception in Silver.
4. **Formula.** Net = Σ successful charges − Σ successful refunds, computed in exact integer cents from the curated `amount_usd`. ARPU and ARPPU divide net revenue in USD by a distinct user count; a zero denominator reports NULL.
5. **Grain and time.** Bookings basis: a payment counts in full when it succeeds; a subscription payment is not spread across the days it covers. One value per complete UTC month inside the coverage window. Quarter revenue is the sum of its three complete months.
6. **Sources and layers.** Current fixture: `transactions`, `payment_status_history`; ARPU also uses the `mau` sources. Layers: `silver_payment_attempts`; `gold_kpi_monthly` and `gold_revenue_monthly` (by revenue type).
7. **Canonical SQL.** Below. Parameters are the same coverage window as `mau`. Money columns are integer cents.
8. **Filters and dimensions.** Revenue is additive: subscription and PPV net revenue add to net revenue, and slices by `transactions.country_at_event`, payment method or user-level fixed dimensions add to the total. A refund is sliced by its own transaction's attributes, except revenue type, which comes from the refunded charge. Per-episode PPV revenue uses the attribution tables as described in the catalog, never repeated transaction amounts.
9. **Null, status and refund rules.** As in the qualifying rule. Raw provider amounts in `raw_payment_source` are never used; reviewed corrections are already reflected in `amount_usd`.
10. **Aggregation safety.** Net, gross and refund amounts are additive across months and slices. ARPU and ARPPU are ratios: never sum or average them across months as if additive; a quarter value is reported only on explicit request and labelled as an average of monthly ratios.
11. **Quality checks.** Implemented and tested: isolated tests cover success-time booking, failed and pending attempts, refunds in a later month, refund type assignment, exact cents, quarter sums, ARPU and ARPPU denominators and zero denominators; the fixture checker reconciles `net_revenue` with its independent cent calculation and the type split with the total. Existing catalog checks validate exact-cent amounts, status histories and refund linkage.
12. **Caveats.** "Net" is net of refunds only: payment-provider fees, app-store commission and taxes are not in the data. All fixture amounts are USD without discounts. Recognised (ratable) revenue is a different metric. In the fixture no refund falls in a later month than its charge.

```sql
-- metric: succeeded_transactions
SELECT t.txn_id, t.user_id, t.type, p.effective_at AS succeeded_at,
       CASE WHEN t.type <> 'refund' THEN t.type
            WHEN o.txn_id IS NOT NULL
             AND EXISTS (SELECT 1 FROM payment_status_history q WHERE q.txn_id = o.txn_id AND q.status = 'succeeded')
            THEN o.type ELSE 'unattributed' END AS revenue_type,
       CAST(ROUND(t.amount_usd * 100) AS INTEGER) AS amount_cents,
       t.country_at_event
FROM transactions t
JOIN payment_status_history p ON p.txn_id = t.txn_id AND p.status = 'succeeded'
LEFT JOIN transactions o ON o.txn_id = t.related_txn_id
WHERE typeof(t.amount_usd) IN ('integer', 'real') AND t.amount_usd > 0
  AND abs(t.amount_usd * 100 - ROUND(t.amount_usd * 100)) < 0.000001
  AND (SELECT COUNT(*) FROM payment_status_history d WHERE d.txn_id = t.txn_id AND d.status = 'succeeded') = 1
```

```sql
-- metric: net_revenue_monthly
-- requires: periods=periods_month, succeeded_transactions
SELECT p.period AS month,
       COALESCE(SUM(CASE WHEN s.type <> 'refund' THEN s.amount_cents END), 0) AS gross_charges_cents,
       COALESCE(SUM(CASE WHEN s.type = 'refund' THEN s.amount_cents END), 0) AS refunds_cents,
       COALESCE(SUM(CASE WHEN s.type = 'refund' THEN -s.amount_cents ELSE s.amount_cents END), 0) AS net_revenue_cents
FROM periods p
LEFT JOIN succeeded_transactions s
  ON s.succeeded_at >= p.period_start AND s.succeeded_at < p.period_end
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: net_revenue_by_type_monthly
-- requires: periods=periods_month, succeeded_transactions
SELECT p.period AS month, t.revenue_type,
       COALESCE(SUM(CASE WHEN s.type <> 'refund' THEN s.amount_cents END), 0) AS gross_charges_cents,
       COALESCE(SUM(CASE WHEN s.type = 'refund' THEN s.amount_cents END), 0) AS refunds_cents,
       COALESCE(SUM(CASE WHEN s.type = 'refund' THEN -s.amount_cents ELSE s.amount_cents END), 0) AS net_revenue_cents
FROM periods p
CROSS JOIN (SELECT 'subscription' AS revenue_type UNION ALL SELECT 'ppv' UNION ALL SELECT 'unattributed') t
LEFT JOIN succeeded_transactions s
  ON s.revenue_type = t.revenue_type
 AND s.succeeded_at >= p.period_start AND s.succeeded_at < p.period_end
GROUP BY p.period_start, t.revenue_type
ORDER BY p.period_start, t.revenue_type
```

`subscription_net_revenue` and `ppv_net_revenue` are the `subscription` and `ppv` rows of `net_revenue_by_type_monthly`; the `unattributed` row holds refunds that cannot be assigned to a successful original charge, so the three rows add to net revenue.

```sql
-- metric: net_revenue_quarterly
-- requires: monthly=net_revenue_monthly
SELECT substr(month, 1, 4) || '-Q' || ((CAST(substr(month, 6, 2) AS INTEGER) + 2) / 3) AS quarter,
       SUM(gross_charges_cents) AS gross_charges_cents,
       SUM(refunds_cents) AS refunds_cents,
       SUM(net_revenue_cents) AS net_revenue_cents
FROM monthly
GROUP BY quarter
HAVING COUNT(*) = 3
ORDER BY quarter
```

```sql
-- metric: arpu
-- requires: revenue=net_revenue_monthly, active=mau_monthly
SELECT r.month, r.net_revenue_cents, a.mau,
       r.net_revenue_cents / 100.0 / NULLIF(a.mau, 0) AS arpu_usd
FROM revenue r JOIN active a ON a.month = r.month
ORDER BY r.month
```

```sql
-- metric: arppu
-- requires: periods=periods_month, succeeded_transactions, revenue=net_revenue_monthly
SELECT r.month, r.net_revenue_cents, COUNT(DISTINCT s.user_id) AS paying_users,
       r.net_revenue_cents / 100.0 / NULLIF(COUNT(DISTINCT s.user_id), 0) AS arppu_usd
FROM revenue r
JOIN periods p ON p.period = r.month
LEFT JOIN succeeded_transactions s
  ON s.type <> 'refund' AND s.succeeded_at >= p.period_start AND s.succeeded_at < p.period_end
GROUP BY r.month
ORDER BY r.month
```

### Funnel and lifecycle group        version: 1.0   status: approved

| id | Name | Definition |
|---|---|---|
| `subscription_conversion_30d` | 30-day subscription conversion | Share of a signup cohort with a successful subscription charge within 30 days of signup |
| `paid_conversion_30d` | 30-day paid conversion | Share of a signup cohort with any successful subscription or PPV charge within 30 days of signup |
| `subscriber_churn_monthly` | Monthly subscriber churn | Subscribers at a month's start who are not subscribers at the next month's start ÷ subscribers at the month's start |
| `retention_day_n` | D1 / D7 / D30 retention | Share of a signup cohort active on UTC day 1, 7 or 30 after the signup date (signup date = day 0) |
| `retention_monthly_cohort` | Monthly cohort retention | Share of a signup-month cohort active in each later calendar month (M1, M2, …) |
| `paywall_funnel` | Paywall funnel | Paywall views → paywalls with a linked checkout → paywalls with a successful linked purchase, by product |
| `marketing_ctr` | Marketing click-through rate | Σ clicks ÷ Σ impressions for a month and channel |

1. **Business meaning.** How signups become payers, how long users and subscribers stay, where purchase intent drops, and how well paid marketing earns clicks.
2. **Population.** Signup cohorts are users by UTC `signup_at` month. A user is a **subscriber at instant t** if a `subscription_history` period with status `active` or `cancel_at_period_end` has `effective_start_at` ≤ t and `effective_end_at` NULL or > t; `expired` and `refunded` periods do not grant access. Retention activity uses the resolved users of `mau`. The funnel unit is a `paywall_viewed` event; marketing rows are `marketing_spend` days by channel.
3. **Qualifying rules.**
   - *Conversion:* a charge counts if it succeeds (success effective time, as in the revenue group) in `[signup_at, signup_at + 30 days)`, half-open, exactly 720 hours.
   - *Churn:* a start-of-month and start-of-next-month snapshot; lapsing and resubscribing within the month is not churn. A refunded or expired period that ends access counts as churn if access is not restored by the next snapshot.
   - *Retention:* active means a session overlapping the UTC day or month, as in `dau`/`mau`.
   - *Funnel:* a checkout counts only through its captured `triggering_paywall_event_id`; a purchase only through `transactions.checkout_event_id` and a successful status. Unlinked checkouts or purchases are never matched by time or user. Several attempts on one checkout, or several checkouts on one paywall, count the paywall once.
4. **Formulas.** Rates are counts of qualifying units ÷ eligible units for the same cohort or period; a zero denominator reports NULL.
5. **Grain and time.**
   - Conversion: cohort = signup month, users whose whole 30-day window lies inside the coverage window (`signup_at` ≥ coverage start and `signup_at + 30 days` ≤ coverage end).
   - Day-N retention: cohort = signup month; a user is eligible for day N when the signup date is inside coverage and day N ends inside coverage.
   - Monthly cohort retention: cohorts are signup months inside coverage; M*k* is reported only for complete months.
   - Churn: one row per complete month whose next month start is within the coverage window (≤ coverage end).
   - Funnel: paywalls by their `event_at` month; later checkout and purchase steps are credited to the paywall's month. Paywalls late in the last month may convert after the data ends.
   - CTR: `marketing_spend.date` months.
6. **Sources and layers.** `users`, `transactions`, `payment_status_history`, `subscription_history`, `sessions`, `identity_links`, `user_events`, `marketing_spend`. Layers: `silver_user_profile`, `silver_subscription_access`, `silver_paywall_funnel`, `silver_marketing_daily`; `gold_cohorts`, `gold_kpi_monthly` (subscribers, churn, MRR), `gold_funnel_monthly`, `gold_marketing_monthly`.
7. **Canonical SQL.** Below; parameters as for `mau`.
8. **Filters and dimensions.** Cohort metrics slice by user-level fixed dimensions (acquisition source, signup month). The funnel slices by product (`event_properties_json.product`). CTR slices by channel. Subscriber status at an instant follows the population rule.
9. **Null, status and refund rules.** A later refund does not undo a conversion or a funnel purchase; it is reflected in revenue metrics. Unknown acquisition source is its own slice.
10. **Aggregation safety.** All are ratios: combine cohorts or months only by summing numerators and denominators, never by averaging rates. CTR across channels or months is Σ clicks ÷ Σ impressions.
11. **Quality checks.** Implemented and tested: isolated tests cover each metric's window boundary, eligibility and zero-denominator case, resubscription within a month, unlinked checkouts and repeated payment attempts; the fixture checker reconciles `subscription_conversion_30d` with its independent cohort comparison. Proposed: purchase-lag coverage for the funnel's last month.
12. **Caveats.** Renewals are off-session, so funnel purchases are mostly first subscriptions and PPV. Captured links are observed navigation, not proof of causation. March signups are not eligible for conversion or retention because activity coverage starts in April.

```sql
-- metric: conversion_30d
-- requires: succeeded_transactions
WITH cohort AS (
  SELECT user_id, signup_at, substr(signup_at, 1, 7) AS signup_month
  FROM users
  WHERE signup_at >= :coverage_start
    AND strftime('%Y-%m-%dT%H:%M:%SZ', signup_at, '+30 days') <= :coverage_end
),
converted AS (
  SELECT c.user_id,
         MAX(s.type = 'subscription') AS subscription_converted,
         MAX(s.type IN ('subscription', 'ppv')) AS paid_converted
  FROM cohort c
  JOIN succeeded_transactions s
    ON s.user_id = c.user_id AND s.type <> 'refund'
   AND s.succeeded_at >= c.signup_at
   AND s.succeeded_at < strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_at, '+30 days')
  GROUP BY c.user_id
)
SELECT c.signup_month, COUNT(*) AS eligible_users,
       COALESCE(SUM(v.subscription_converted), 0) AS subscription_converted,
       COALESCE(SUM(v.paid_converted), 0) AS paid_converted,
       COALESCE(SUM(v.subscription_converted), 0) * 1.0 / COUNT(*) AS subscription_conversion_30d,
       COALESCE(SUM(v.paid_converted), 0) * 1.0 / COUNT(*) AS paid_conversion_30d
FROM cohort c LEFT JOIN converted v ON v.user_id = c.user_id
GROUP BY c.signup_month
ORDER BY c.signup_month
```

```sql
-- metric: subscription_access_periods
SELECT user_id, effective_start_at, effective_end_at
FROM subscription_history
WHERE status IN ('active', 'cancel_at_period_end')
```

```sql
-- metric: subscriber_churn_monthly
-- requires: periods=periods_month, access=subscription_access_periods
WITH at_start AS (
  SELECT DISTINCT p.period_start, a.user_id
  FROM periods p
  JOIN access a ON a.effective_start_at <= p.period_start
              AND (a.effective_end_at IS NULL OR a.effective_end_at > p.period_start)
),
outcome AS (
  SELECT s.period_start, s.user_id,
         NOT EXISTS (SELECT 1 FROM access b, periods q
                     WHERE q.period_start = s.period_start AND b.user_id = s.user_id
                       AND b.effective_start_at <= q.period_end
                       AND (b.effective_end_at IS NULL OR b.effective_end_at > q.period_end)) AS churned
  FROM at_start s
)
SELECT p.period AS month,
       COUNT(o.user_id) AS subscribers_at_start,
       COALESCE(SUM(o.churned), 0) AS churned,
       SUM(o.churned) * 1.0 / NULLIF(COUNT(o.user_id), 0) AS churn_rate
FROM periods p
LEFT JOIN outcome o ON o.period_start = p.period_start
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: mau_monthly_by_subscriber_status
-- requires: periods=periods_month, resolved_sessions, access=subscription_access_periods
SELECT p.period AS month,
       CASE WHEN EXISTS (SELECT 1 FROM access a
                         WHERE a.user_id = r.resolved_user_id
                           AND a.effective_start_at <= r.session_started_at
                           AND (a.effective_end_at IS NULL OR a.effective_end_at > r.session_started_at))
            THEN 'subscriber' ELSE 'non_subscriber' END AS subscriber_status,
       COUNT(DISTINCT r.resolved_user_id) AS mau
FROM periods p
JOIN resolved_sessions r
  ON r.session_started_at < p.period_end AND r.last_activity_at >= p.period_start
WHERE r.resolved_user_id IS NOT NULL
GROUP BY p.period_start, subscriber_status
ORDER BY p.period_start, subscriber_status
```

```sql
-- metric: retention_day_n
-- requires: resolved_sessions
WITH RECURSIVE day_numbers(day_n) AS (VALUES (1), (7), (30)),
eligible AS (
  SELECT u.user_id, substr(u.signup_at, 1, 7) AS signup_month, d.day_n,
         date(substr(u.signup_at, 1, 10), '+' || d.day_n || ' days') AS active_day
  FROM users u CROSS JOIN day_numbers d
  WHERE substr(u.signup_at, 1, 10) || 'T00:00:00Z' >= :coverage_start
    AND strftime('%Y-%m-%dT%H:%M:%SZ', substr(u.signup_at, 1, 10), '+' || (d.day_n + 1) || ' days') <= :coverage_end
),
session_days(user_id, active_day, last_day) AS (
  SELECT resolved_user_id, date(session_started_at), date(last_activity_at)
  FROM resolved_sessions WHERE resolved_user_id IS NOT NULL
  UNION
  SELECT user_id, date(active_day, '+1 day'), last_day FROM session_days WHERE active_day < last_day
),
activity_days AS (SELECT DISTINCT user_id, active_day FROM session_days)
SELECT e.signup_month, e.day_n, COUNT(*) AS eligible_users, COUNT(a.user_id) AS retained_users,
       COUNT(a.user_id) * 1.0 / COUNT(*) AS retention_rate
FROM eligible e
LEFT JOIN activity_days a ON a.user_id = e.user_id AND a.active_day = e.active_day
GROUP BY e.signup_month, e.day_n
ORDER BY e.signup_month, e.day_n
```

```sql
-- metric: retention_monthly_cohort
-- requires: periods=periods_month, resolved_sessions
WITH cohort AS (
  SELECT u.user_id, p.period AS signup_month, p.period_start AS cohort_start
  FROM users u JOIN periods p ON u.signup_at >= p.period_start AND u.signup_at < p.period_end
),
activity AS (
  SELECT DISTINCT p.period_start, r.resolved_user_id AS user_id
  FROM periods p
  JOIN resolved_sessions r ON r.session_started_at < p.period_end AND r.last_activity_at >= p.period_start
  WHERE r.resolved_user_id IS NOT NULL
)
SELECT c.signup_month, p.period AS month,
       (CAST(substr(p.period, 1, 4) AS INTEGER) * 12 + CAST(substr(p.period, 6, 2) AS INTEGER))
       - (CAST(substr(c.signup_month, 1, 4) AS INTEGER) * 12 + CAST(substr(c.signup_month, 6, 2) AS INTEGER)) AS months_since_signup,
       COUNT(*) AS cohort_users,
       COUNT(a.user_id) AS retained_users,
       COUNT(a.user_id) * 1.0 / COUNT(*) AS retention_rate
FROM cohort c
JOIN periods p ON p.period_start > c.cohort_start
LEFT JOIN activity a ON a.user_id = c.user_id AND a.period_start = p.period_start
GROUP BY c.signup_month, p.period_start
ORDER BY c.signup_month, p.period_start
```

```sql
-- metric: paywall_funnel_monthly
-- requires: periods=periods_month, succeeded_transactions
SELECT p.period AS month,
       json_extract(pw.event_properties_json, '$.product') AS product,
       COUNT(DISTINCT pw.event_id) AS paywalls,
       COUNT(DISTINCT CASE WHEN co.event_id IS NOT NULL THEN pw.event_id END) AS paywalls_with_checkout,
       COUNT(DISTINCT CASE WHEN st.txn_id IS NOT NULL THEN pw.event_id END) AS paywalls_with_purchase,
       COUNT(DISTINCT CASE WHEN co.event_id IS NOT NULL THEN pw.event_id END) * 1.0
         / NULLIF(COUNT(DISTINCT pw.event_id), 0) AS paywall_to_checkout_rate,
       COUNT(DISTINCT CASE WHEN st.txn_id IS NOT NULL THEN pw.event_id END) * 1.0
         / NULLIF(COUNT(DISTINCT CASE WHEN co.event_id IS NOT NULL THEN pw.event_id END), 0) AS checkout_to_purchase_rate,
       COUNT(DISTINCT CASE WHEN st.txn_id IS NOT NULL THEN pw.event_id END) * 1.0
         / NULLIF(COUNT(DISTINCT pw.event_id), 0) AS paywall_to_purchase_rate
FROM periods p
JOIN user_events pw
  ON pw.event_name = 'paywall_viewed' AND pw.event_at >= p.period_start AND pw.event_at < p.period_end
LEFT JOIN user_events co
  ON co.event_name = 'checkout_started' AND co.triggering_paywall_event_id = pw.event_id
LEFT JOIN transactions t ON t.checkout_event_id = co.event_id
LEFT JOIN succeeded_transactions st ON st.txn_id = t.txn_id AND st.type <> 'refund'
GROUP BY p.period_start, product
ORDER BY p.period_start, product
```

```sql
-- metric: marketing_ctr_monthly
-- requires: periods=periods_month
SELECT p.period AS month, m.channel,
       SUM(m.clicks) AS clicks, SUM(m.impressions) AS impressions,
       SUM(m.clicks) * 1.0 / NULLIF(SUM(m.impressions), 0) AS ctr
FROM periods p
JOIN marketing_spend m ON m.date >= substr(p.period_start, 1, 10) AND m.date < substr(p.period_end, 1, 10)
GROUP BY p.period_start, m.channel
UNION ALL
SELECT p.period, 'all',
       SUM(m.clicks), SUM(m.impressions),
       SUM(m.clicks) * 1.0 / NULLIF(SUM(m.impressions), 0)
FROM periods p
JOIN marketing_spend m ON m.date >= substr(p.period_start, 1, 10) AND m.date < substr(p.period_end, 1, 10)
GROUP BY p.period_start
ORDER BY 1, 2
```

### Engagement group        version: 1.0   status: approved

| id | Name | Definition (per complete UTC month) |
|---|---|---|
| `watch_time` | Total watch time | Σ period-allocated watch seconds, reported in seconds and hours |
| `watch_time_per_engaged_user` | Watch time per engaged user | Watch seconds of `meu` users ÷ `meu` |
| `views_per_viewer` | Views per viewer | Views started in the month ÷ distinct users who started a view in the month |
| `episode_completion_rate` | Episode completion rate | User-episodes completed ÷ user-episodes started |
| `series_continuation_rate` | Series continuation rate | Completed user-episodes followed by the same user starting the next episode of the title ÷ completed user-episodes that have a next episode |
| `title_reach` | Title reach | Distinct users who started a view of a title in the month |
| `free_quota_hit_rate` | Free-quota hit rate | Free viewer-days that reach the eight-episode limit ÷ free viewer-days |
| `paywall_exposure_rate` | Paywall exposure rate | Users who saw at least one paywall ÷ `mau` |

1. **Business meaning.** How much people watch, whether they finish episodes and continue a series, which titles reach people, and how often free users meet the free limit or a paywall.
2. **Population.** Viewers are `content_views.user_id`. A *user-episode* is a user and a (`content_id`, `episode_number`), started at the user's first recorded view of that episode. A *free viewer-day* is a user and UTC date with at least one quota-consuming free view. Paywall exposure resolves an event's user from `user_events.user_id`, or else the event session's resolved user as in `mau`.
3. **Qualifying rules.**
   - *Watch time* is the period-allocated segment `watch_duration_sec` used by `deu`; rewatched sections count as watch time.
   - *Completion:* the union of unique positions covered by all of the user's playback segments of the episode within 7 days of the first start reaches at least 90% of `content_episodes.episode_duration_sec`. Rewinds and repeated sections do not add coverage; resumed viewing in a later attempt does.
   - *Continuation:* the same user starts episode *n*+1 of the same title within 7 days of the first start of completed episode *n*.
   - *Free-quota hit:* the viewer-day has a view with `free_quota_sequence` 8.
   - *Paywall exposure:* at least one `paywall_viewed` event in the month.
4. **Formulas.** As in the table; a zero denominator reports NULL. Views are attempts (`view_id`), not segments or heartbeats.
5. **Grain and time.** Complete UTC months. Watch time is split across periods by wall-clock share. Views, viewers, title reach and paywall exposure use event or view start time. User-episodes belong to the month of the first start and are eligible only when the 7-day window ends inside the coverage window; free viewer-days belong to their UTC date's month.
6. **Sources and layers.** `content_views`, `playback_segments`, `content_episodes`, `user_events`, `sessions`, `identity_links`. Layers: `silver_user_day_title_watch`, `silver_user_episodes`, `silver_user_day_activity` (free-quota slots), `silver_paywall_funnel`; `gold_content_monthly` and `gold_funnel_monthly` (exposure).
7. **Canonical SQL.** Below; parameters as for `mau`.
8. **Filters and dimensions.** Title (`content_id`), view type (free, subscription, PPV), platform and country from the view or session. Titles and view types can overlap per user; watch seconds are additive across titles and view types.
9. **Null, status and refund rules.** Engagement does not depend on payment state; a refunded PPV view's watch time still counts. Views without segments contribute no watch time or coverage.
10. **Aggregation safety.** Watch seconds and view counts are additive. Rates and per-user values are ratios: combine periods only by summing numerators and denominators. Title reach is a distinct count and must not be summed across titles or months.
11. **Quality checks.** Implemented and tested: isolated tests cover watch-time splitting across midnight, the engaged-user population for per-user watch time, completion with resume, rewinds and the 7-day window, the 90% threshold, continuation timing and the last episode, quota hits, paywall exposure through session resolution and zero denominators; the fixture checker reconciles monthly watch time with total playback-segment seconds; existing catalog checks validate segments, positions and quota sequences. Proposed: completion windows for titles with episodes released during the window.
12. **Caveats.** Completion requires playback segments; the fixture covers every view. The 90% threshold treats closing credits as optional. Watch time includes time watched by users below the engaged threshold, except in `watch_time_per_engaged_user`.

```sql
-- metric: watch_time_monthly
-- requires: periods=periods_month, period_watch_seconds, engaged=meu
SELECT p.period AS month,
       COALESCE(SUM(w.watched_sec), 0) AS watch_sec,
       COALESCE(SUM(w.watched_sec), 0) / 3600.0 AS watch_hours,
       e.meu,
       (SELECT SUM(t.user_sec) FROM (SELECT SUM(x.watched_sec) AS user_sec FROM period_watch_seconds x
                                      WHERE x.period_start = p.period_start GROUP BY x.user_id
                                      HAVING SUM(x.watched_sec) >= 60) t) / NULLIF(e.meu, 0) AS watch_sec_per_engaged_user
FROM periods p
LEFT JOIN period_watch_seconds w ON w.period_start = p.period_start
JOIN engaged e ON e.month = p.period
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: views_per_viewer_monthly
-- requires: periods=periods_month
SELECT p.period AS month, COUNT(v.view_id) AS views, COUNT(DISTINCT v.user_id) AS viewers,
       COUNT(v.view_id) * 1.0 / NULLIF(COUNT(DISTINCT v.user_id), 0) AS views_per_viewer
FROM periods p
LEFT JOIN content_views v ON v.view_started_at >= p.period_start AND v.view_started_at < p.period_end
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: user_episodes
SELECT v.user_id, v.content_id, v.episode_number, MIN(v.view_started_at) AS first_start_at,
       strftime('%Y-%m-%dT%H:%M:%SZ', MIN(v.view_started_at), '+7 days') AS window_end_at
FROM content_views v
GROUP BY v.user_id, v.content_id, v.episode_number
```

```sql
-- metric: user_episode_completion
-- requires: user_episodes
WITH segments AS (
  SELECT e.user_id, e.content_id, e.episode_number, s.position_start_sec AS a, s.position_end_sec AS b
  FROM user_episodes e
  JOIN content_views v ON v.user_id = e.user_id AND v.content_id = e.content_id
                      AND v.episode_number = e.episode_number
                      AND v.view_started_at < e.window_end_at
  JOIN playback_segments s ON s.view_id = v.view_id
  WHERE s.position_end_sec > s.position_start_sec
),
ordered AS (
  SELECT *, MAX(b) OVER (PARTITION BY user_id, content_id, episode_number ORDER BY a, b
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_end
  FROM segments
),
islands AS (
  SELECT *, SUM(CASE WHEN prior_end IS NULL OR a > prior_end THEN 1 ELSE 0 END)
              OVER (PARTITION BY user_id, content_id, episode_number ORDER BY a, b
                    ROWS UNBOUNDED PRECEDING) AS island
  FROM ordered
),
coverage AS (
  SELECT user_id, content_id, episode_number, SUM(island_sec) AS covered_sec
  FROM (SELECT user_id, content_id, episode_number, MAX(b) - MIN(a) AS island_sec
        FROM islands GROUP BY user_id, content_id, episode_number, island)
  GROUP BY user_id, content_id, episode_number
)
SELECT e.user_id, e.content_id, e.episode_number, e.first_start_at, e.window_end_at,
       COALESCE(c.covered_sec, 0) AS covered_sec, d.episode_duration_sec,
       COALESCE(c.covered_sec, 0) >= 0.9 * d.episode_duration_sec AS completed
FROM user_episodes e
JOIN content_episodes d ON d.content_id = e.content_id AND d.episode_number = e.episode_number
LEFT JOIN coverage c ON c.user_id = e.user_id AND c.content_id = e.content_id AND c.episode_number = e.episode_number
```

```sql
-- metric: episode_completion_monthly
-- requires: periods=periods_month, completion=user_episode_completion
SELECT p.period AS month, COUNT(c.user_id) AS user_episodes_started,
       COALESCE(SUM(c.completed), 0) AS user_episodes_completed,
       SUM(c.completed) * 1.0 / NULLIF(COUNT(c.user_id), 0) AS episode_completion_rate
FROM periods p
LEFT JOIN completion c
  ON c.first_start_at >= p.period_start AND c.first_start_at < p.period_end
 AND c.window_end_at <= :coverage_end
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: series_continuation_monthly
-- requires: periods=periods_month, completion=user_episode_completion
SELECT p.period AS month,
       COUNT(c.user_id) AS completed_with_next_episode,
       COALESCE(SUM(EXISTS (
         SELECT 1 FROM content_views n
         WHERE n.user_id = c.user_id AND n.content_id = c.content_id
           AND n.episode_number = c.episode_number + 1
           AND n.view_started_at >= c.first_start_at AND n.view_started_at < c.window_end_at)), 0) AS continued,
       SUM(EXISTS (
         SELECT 1 FROM content_views n
         WHERE n.user_id = c.user_id AND n.content_id = c.content_id
           AND n.episode_number = c.episode_number + 1
           AND n.view_started_at >= c.first_start_at AND n.view_started_at < c.window_end_at)) * 1.0
         / NULLIF(COUNT(c.user_id), 0) AS series_continuation_rate
FROM periods p
LEFT JOIN completion c
  ON c.completed = 1 AND c.first_start_at >= p.period_start AND c.first_start_at < p.period_end
 AND c.window_end_at <= :coverage_end
 AND EXISTS (SELECT 1 FROM content_episodes x
             WHERE x.content_id = c.content_id AND x.episode_number = c.episode_number + 1)
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: title_reach_monthly
-- requires: periods=periods_month
SELECT p.period AS month, v.content_id, COUNT(DISTINCT v.user_id) AS viewers
FROM periods p
JOIN content_views v ON v.view_started_at >= p.period_start AND v.view_started_at < p.period_end
GROUP BY p.period_start, v.content_id
ORDER BY p.period_start, v.content_id
```

```sql
-- metric: free_quota_hit_monthly
-- requires: periods=periods_month
SELECT p.period AS month, COUNT(d.user_id) AS free_viewer_days,
       COALESCE(SUM(d.hit), 0) AS quota_hit_days,
       SUM(d.hit) * 1.0 / NULLIF(COUNT(d.user_id), 0) AS free_quota_hit_rate
FROM periods p
LEFT JOIN (
  SELECT user_id, date, MAX(free_quota_sequence = 8) AS hit
  FROM content_views WHERE free_quota_consuming = 1
  GROUP BY user_id, date
) d ON d.date >= substr(p.period_start, 1, 10) AND d.date < substr(p.period_end, 1, 10)
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: paywall_exposure_monthly
-- requires: periods=periods_month, resolved_sessions, active=mau_monthly
SELECT p.period AS month,
       COUNT(DISTINCT COALESCE(e.user_id, r.resolved_user_id)) AS exposed_users,
       a.mau,
       COUNT(DISTINCT COALESCE(e.user_id, r.resolved_user_id)) * 1.0 / NULLIF(a.mau, 0) AS paywall_exposure_rate
FROM periods p
JOIN active a ON a.month = p.period
LEFT JOIN user_events e
  ON e.event_name = 'paywall_viewed' AND e.event_at >= p.period_start AND e.event_at < p.period_end
LEFT JOIN resolved_sessions r ON r.session_id = e.session_id
GROUP BY p.period_start
ORDER BY p.period_start
```

### Supporting metrics: activity, monetisation, lifecycle and marketing        version: 1.1   status: approved

| id | Name | Definition (per complete UTC month unless stated) |
|---|---|---|
| `new_signups` | New signups | Users by `signup_at` month, by `acquisition_source` and in total |
| `activation_7d` | 7-day activation | Share of a signup cohort with an engaged UTC day (≥ 60 s watched that day) on days 0–6 after the signup date |
| `sessions_per_active_user` | Sessions per active user | Identified sessions overlapping the month ÷ `mau` |
| `session_duration` | Session duration | Median and mean observed span, `session_started_at` to `last_activity_at`, of identified sessions starting in the month |
| `active_days_distribution` | Active-days distribution | Users by number of distinct active UTC days in the month |
| `paying_users` | Paying users | Users with at least one successful subscription or PPV charge in the month, in total and by product |
| `active_subscribers` | Active subscribers and net adds | Subscribers at the month's start and at the next month's start; net adds = end − start |
| `mrr` | Monthly recurring revenue | Σ monthly list price of subscribers at the next month's start (month end) |
| `refund_rate` | Refund rate | Successful refund amount ÷ successful gross charges in the month; counts reported alongside |
| `payment_failure_rate` | Payment failure rate | Failed attempts ÷ attempts with a final succeeded or failed outcome, by attempt creation month and product |
| `cancellation_request_rate` | Cancellation-request rate | Users requesting cancellation in the month ÷ subscribers at the month's start |
| `resubscription_rate_60d` | 60-day resubscription rate | Share of access losses followed by regained subscriber access within 60 days |
| `marketing_spend` | Marketing spend | Σ `marketing_spend.spend_usd` by channel |
| `marketing_cpc` | Cost per click | Spend ÷ clicks |
| `cost_per_signup` | Cost per signup | Channel spend ÷ signups with that `acquisition_source` in the same month |
| `marketing_cac` | Customer acquisition cost | Channel spend ÷ new paying users (first-ever successful charge) from that `acquisition_source` in the same month |

1. **Business meaning.** Inputs and companions to the headline metrics: how many people join and start watching, how intensively users visit, how many pay and subscribe, what recurring revenue the subscriber base represents, how often payments fail, how subscribers leave and return, and what paid acquisition costs.
2. **Population.** Users and signup cohorts as in the lifecycle group; active users and sessions as in `mau`; subscribers at an instant as in the lifecycle group; transactions and successful charges as in the revenue group. Marketing channels are `marketing_spend.channel`; a user's channel is `users.acquisition_source`, and `unknown` users are never reallocated to a channel.
3. **Qualifying rules.**
   - *Activation:* an engaged day has at least 60 watch seconds allocated to that UTC day by wall-clock share, the same allocation as `deu`.
   - *Session duration:* identified sessions only; open sessions use `last_activity_at`.
   - *Active days:* a session counts on every UTC day its span touches inside the month.
   - *MRR:* price is the `list_price_usd` of the charge that started the access period. A price that is not numeric, positive and exact to the cent is excluded from MRR rather than rounded; the subscriber still counts in `subscribers_at_end`.
   - *Payment failure:* an attempt's outcome is its latest succeeded or failed status event; an attempt without either is excluded. A failed renewal followed by a successful retry counts as one failed and one successful attempt.
   - *Cancellation request:* a `subscription_history` period with status `cancel_at_period_end` whose `cancelled_at` is in the month.
   - *Access loss:* the end of an access period at which no other access period covers the same instant; regained access is a new access period starting within 60 days after the loss.
   - *New paying user:* the user's earliest successful subscription or PPV charge falls in the month.
4. **Formulas.** As in the table; a zero denominator reports NULL. Money is computed in integer cents.
5. **Grain and time.** Complete UTC months. Activation cohorts need days 0–6 inside the coverage window and a signup date inside it. Resubscription is by the month of access loss and needs the 60-day window to end inside the coverage window. Cost per signup and CAC are same-month blended ratios; spend is not lagged to later conversions.
6. **Sources and layers.** `users`, `sessions`, `identity_links`, `content_views`, `playback_segments`, `transactions`, `payment_status_history`, `subscription_history`, `marketing_spend`. Layers: the Silver tables of their groups; `gold_kpi_monthly`, `gold_cohorts`, `gold_revenue_monthly` and `gold_marketing_monthly`.
7. **Canonical SQL.** Below; parameters as for `mau`.
8. **Filters and dimensions.** Signups, activation, paying users and CAC slice by user-level fixed dimensions. Session metrics slice by platform and country. Payment failure slices by product and payment method.
9. **Null, status and refund rules.** MRR and subscriber counts ignore refunds except where a refund ends access. Failed attempts are never revenue.
10. **Aggregation safety.** Signups, spend, clicks, sessions, attempts and money are additive. Distinct users, MRR at an instant, medians and all rates are not: recompute from components for longer periods.
11. **Quality checks.** Implemented and tested: isolated tests cover each formula, its window or snapshot boundary and zero denominators. The fixture checker verifies that paying users match the ARPPU denominator and that subscriber snapshots reconcile with churn.
12. **Caveats.** Cost per signup and CAC attribute by first-touch acquisition source and the same month, so they ignore conversion lag and organic influence. MRR uses list price; the fixture has one $9.99 plan and no discounts. Cancellation requests from users who subscribed during the month are in the numerator but not the denominator.

```sql
-- metric: new_signups_monthly
-- requires: periods=periods_month
SELECT p.period AS month, COALESCE(u.acquisition_source, 'unknown') AS acquisition_source, COUNT(*) AS signups
FROM periods p JOIN users u ON u.signup_at >= p.period_start AND u.signup_at < p.period_end
GROUP BY p.period_start, 2
UNION ALL
SELECT p.period, 'all', COUNT(u.user_id)
FROM periods p LEFT JOIN users u ON u.signup_at >= p.period_start AND u.signup_at < p.period_end
GROUP BY p.period_start
ORDER BY 1, 2
```

```sql
-- metric: activation_7d
WITH RECURSIVE segment_days(user_id, day, seg_start, seg_end, watched) AS (
  SELECT v.user_id, date(s.segment_started_at), s.segment_started_at, s.segment_ended_at, s.watch_duration_sec
  FROM playback_segments s JOIN content_views v ON v.view_id = s.view_id
  UNION ALL
  SELECT user_id, date(day, '+1 day'), seg_start, seg_end, watched FROM segment_days
  WHERE date(day, '+1 day') < substr(seg_end, 1, 10) OR (date(day, '+1 day') = substr(seg_end, 1, 10) AND substr(seg_end, 12) <> '00:00:00Z')
),
engaged_days AS (
  SELECT user_id, day
  FROM segment_days
  GROUP BY user_id, day
  HAVING SUM(watched *
             CASE WHEN julianday(seg_end) = julianday(seg_start) THEN 1.0
                  ELSE (MIN(julianday(seg_end), julianday(day, '+1 day')) - MAX(julianday(seg_start), julianday(day)))
                       / (julianday(seg_end) - julianday(seg_start))
             END) >= 60
),
cohort AS (
  SELECT user_id, substr(signup_at, 1, 7) AS signup_month, substr(signup_at, 1, 10) AS signup_day
  FROM users
  WHERE substr(signup_at, 1, 10) || 'T00:00:00Z' >= :coverage_start
    AND strftime('%Y-%m-%dT%H:%M:%SZ', substr(signup_at, 1, 10), '+7 days') <= :coverage_end
),
flags AS (
  SELECT c.signup_month, c.user_id, MAX(d.user_id IS NOT NULL) AS activated
  FROM cohort c
  LEFT JOIN engaged_days d
    ON d.user_id = c.user_id AND d.day >= c.signup_day AND d.day < date(c.signup_day, '+7 days')
  GROUP BY c.signup_month, c.user_id
)
SELECT signup_month, COUNT(*) AS eligible_users, SUM(activated) AS activated_users,
       SUM(activated) * 1.0 / COUNT(*) AS activation_rate
FROM flags
GROUP BY signup_month
ORDER BY signup_month
```

```sql
-- metric: sessions_per_active_user_monthly
-- requires: periods=periods_month, resolved_sessions, active=mau_monthly
SELECT p.period AS month, COUNT(r.session_id) AS sessions, a.mau,
       COUNT(r.session_id) * 1.0 / NULLIF(a.mau, 0) AS sessions_per_active_user
FROM periods p
JOIN active a ON a.month = p.period
LEFT JOIN resolved_sessions r
  ON r.resolved_user_id IS NOT NULL
 AND r.session_started_at < p.period_end AND r.last_activity_at >= p.period_start
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: session_duration_monthly
-- requires: periods=periods_month, resolved_sessions
WITH spans AS (
  SELECT p.period AS month, p.period_start,
         CAST(ROUND((julianday(r.last_activity_at) - julianday(r.session_started_at)) * 86400) AS INTEGER) AS sec
  FROM periods p
  JOIN resolved_sessions r
    ON r.resolved_user_id IS NOT NULL
   AND r.session_started_at >= p.period_start AND r.session_started_at < p.period_end
),
ranked AS (
  SELECT month, period_start, sec,
         ROW_NUMBER() OVER (PARTITION BY month ORDER BY sec) AS n,
         COUNT(*) OVER (PARTITION BY month) AS total
  FROM spans
)
SELECT month, MAX(total) AS sessions, AVG(sec) AS mean_sec,
       AVG(CASE WHEN n IN ((total + 1) / 2, (total + 2) / 2) THEN sec END) AS median_sec
FROM ranked
GROUP BY period_start
ORDER BY period_start
```

```sql
-- metric: active_days_distribution_monthly
-- requires: periods=periods_month, resolved_sessions
WITH RECURSIVE session_days(user_id, active_day, last_day) AS (
  SELECT resolved_user_id, date(session_started_at), date(last_activity_at)
  FROM resolved_sessions WHERE resolved_user_id IS NOT NULL
  UNION
  SELECT user_id, date(active_day, '+1 day'), last_day FROM session_days WHERE active_day < last_day
),
user_month AS (
  SELECT p.period AS month, p.period_start, s.user_id, COUNT(DISTINCT s.active_day) AS active_days
  FROM periods p
  JOIN session_days s ON s.active_day >= substr(p.period_start, 1, 10) AND s.active_day < substr(p.period_end, 1, 10)
  GROUP BY p.period_start, s.user_id
)
SELECT month, active_days, COUNT(*) AS users
FROM user_month
GROUP BY period_start, active_days
ORDER BY period_start, active_days
```

```sql
-- metric: paying_users_monthly
-- requires: periods=periods_month, succeeded_transactions
SELECT p.period AS month,
       COUNT(DISTINCT s.user_id) AS paying_users,
       COUNT(DISTINCT CASE WHEN s.type = 'subscription' THEN s.user_id END) AS subscription_payers,
       COUNT(DISTINCT CASE WHEN s.type = 'ppv' THEN s.user_id END) AS ppv_payers
FROM periods p
LEFT JOIN succeeded_transactions s
  ON s.type <> 'refund' AND s.succeeded_at >= p.period_start AND s.succeeded_at < p.period_end
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: active_subscribers_monthly
-- requires: periods=periods_month, access=subscription_access_periods
WITH snapshots AS (
  SELECT p.period, p.period_start,
         (SELECT COUNT(DISTINCT a.user_id) FROM access a
          WHERE a.effective_start_at <= p.period_start
            AND (a.effective_end_at IS NULL OR a.effective_end_at > p.period_start)) AS subscribers_at_start,
         (SELECT COUNT(DISTINCT a.user_id) FROM access a
          WHERE a.effective_start_at <= p.period_end
            AND (a.effective_end_at IS NULL OR a.effective_end_at > p.period_end)) AS subscribers_at_end
  FROM periods p
)
SELECT period AS month, subscribers_at_start, subscribers_at_end,
       subscribers_at_end - subscribers_at_start AS net_adds
FROM snapshots
ORDER BY period_start
```

```sql
-- metric: mrr_monthly
-- requires: periods=periods_month
SELECT p.period AS month, COUNT(m.user_id) AS subscribers_at_end, COALESCE(SUM(m.price_cents), 0) AS mrr_cents
FROM periods p
LEFT JOIN (
  SELECT q.period_start, h.user_id,
         MAX(CASE WHEN typeof(t.list_price_usd) IN ('integer', 'real') AND t.list_price_usd > 0
                   AND abs(t.list_price_usd * 100 - ROUND(t.list_price_usd * 100)) < 0.000001
                  THEN CAST(ROUND(t.list_price_usd * 100) AS INTEGER) END) AS price_cents
  FROM periods q
  JOIN subscription_history h
    ON h.status IN ('active', 'cancel_at_period_end')
   AND h.effective_start_at <= q.period_end
   AND (h.effective_end_at IS NULL OR h.effective_end_at > q.period_end)
  LEFT JOIN transactions t ON t.txn_id = h.source_txn_id
  GROUP BY q.period_start, h.user_id
) m ON m.period_start = p.period_start
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: refund_rate_monthly
-- requires: periods=periods_month, succeeded_transactions
SELECT p.period AS month,
       COALESCE(SUM(CASE WHEN s.type <> 'refund' THEN s.amount_cents END), 0) AS gross_charges_cents,
       COALESCE(SUM(CASE WHEN s.type = 'refund' THEN s.amount_cents END), 0) AS refunds_cents,
       COUNT(CASE WHEN s.type <> 'refund' THEN 1 END) AS charges,
       COUNT(CASE WHEN s.type = 'refund' THEN 1 END) AS refunds,
       SUM(CASE WHEN s.type = 'refund' THEN s.amount_cents ELSE 0 END) * 1.0
         / NULLIF(SUM(CASE WHEN s.type <> 'refund' THEN s.amount_cents ELSE 0 END), 0) AS refund_rate
FROM periods p
LEFT JOIN succeeded_transactions s ON s.succeeded_at >= p.period_start AND s.succeeded_at < p.period_end
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: payment_failure_rate_monthly
-- requires: periods=periods_month
WITH outcomes AS (
  SELECT t.txn_id, t.type, t.transaction_at,
         (SELECT h.status FROM payment_status_history h
          WHERE h.txn_id = t.txn_id AND h.status IN ('succeeded', 'failed')
          ORDER BY h.effective_at DESC, h.recorded_at DESC LIMIT 1) AS outcome
  FROM transactions t WHERE t.type <> 'refund'
)
SELECT p.period AS month, o.type AS product,
       COUNT(*) AS attempts, SUM(o.outcome = 'failed') AS failed,
       SUM(o.outcome = 'failed') * 1.0 / NULLIF(COUNT(*), 0) AS payment_failure_rate
FROM periods p
JOIN outcomes o ON o.outcome IS NOT NULL
               AND o.transaction_at >= p.period_start AND o.transaction_at < p.period_end
GROUP BY p.period_start, o.type
ORDER BY p.period_start, o.type
```

```sql
-- metric: cancellation_request_rate_monthly
-- requires: periods=periods_month, access=subscription_access_periods
WITH counts AS (
  SELECT p.period, p.period_start,
         (SELECT COUNT(DISTINCT h.user_id) FROM subscription_history h
          WHERE h.status = 'cancel_at_period_end'
            AND h.cancelled_at >= p.period_start AND h.cancelled_at < p.period_end) AS cancellation_requests,
         (SELECT COUNT(DISTINCT a.user_id) FROM access a
          WHERE a.effective_start_at <= p.period_start
            AND (a.effective_end_at IS NULL OR a.effective_end_at > p.period_start)) AS subscribers_at_start
  FROM periods p
)
SELECT period AS month, cancellation_requests, subscribers_at_start,
       cancellation_requests * 1.0 / NULLIF(subscribers_at_start, 0) AS cancellation_request_rate
FROM counts
ORDER BY period_start
```

```sql
-- metric: resubscription_60d
-- requires: periods=periods_month, access=subscription_access_periods
WITH losses AS (
  SELECT DISTINCT a.user_id, a.effective_end_at AS lost_at
  FROM access a
  WHERE a.effective_end_at IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM access b
                    WHERE b.user_id = a.user_id AND b.effective_start_at <= a.effective_end_at
                      AND (b.effective_end_at IS NULL OR b.effective_end_at > a.effective_end_at))
),
outcomes AS (
  SELECT l.user_id, l.lost_at,
         EXISTS (SELECT 1 FROM access r WHERE r.user_id = l.user_id
                 AND r.effective_start_at > l.lost_at
                 AND r.effective_start_at <= strftime('%Y-%m-%dT%H:%M:%SZ', l.lost_at, '+60 days')) AS resubscribed
  FROM losses l
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', l.lost_at, '+60 days') <= :coverage_end
)
SELECT p.period AS month, COUNT(o.user_id) AS access_losses, COALESCE(SUM(o.resubscribed), 0) AS resubscribed,
       SUM(o.resubscribed) * 1.0 / NULLIF(COUNT(o.user_id), 0) AS resubscription_rate
FROM periods p
LEFT JOIN outcomes o ON o.lost_at >= p.period_start AND o.lost_at < p.period_end
GROUP BY p.period_start
ORDER BY p.period_start
```

```sql
-- metric: marketing_efficiency_monthly
-- requires: periods=periods_month, succeeded_transactions
WITH spend AS (
  SELECT p.period, p.period_start, p.period_end, m.channel,
         SUM(CAST(ROUND(m.spend_usd * 100) AS INTEGER)) AS spend_cents, SUM(m.clicks) AS clicks
  FROM periods p
  JOIN marketing_spend m ON m.date >= substr(p.period_start, 1, 10) AND m.date < substr(p.period_end, 1, 10)
  GROUP BY p.period_start, m.channel
),
first_paid AS (
  SELECT user_id, MIN(succeeded_at) AS first_paid_at FROM succeeded_transactions
  WHERE type <> 'refund' GROUP BY user_id
),
counts AS (
  SELECT s.*,
         (SELECT COUNT(*) FROM users u WHERE u.acquisition_source = s.channel
            AND u.signup_at >= s.period_start AND u.signup_at < s.period_end) AS signups,
         (SELECT COUNT(*) FROM first_paid f JOIN users u ON u.user_id = f.user_id
          WHERE u.acquisition_source = s.channel
            AND f.first_paid_at >= s.period_start AND f.first_paid_at < s.period_end) AS new_paying_users
  FROM spend s
)
SELECT period AS month, channel, spend_cents, clicks, signups, new_paying_users,
       spend_cents / 100.0 / NULLIF(clicks, 0) AS cpc_usd,
       spend_cents / 100.0 / NULLIF(signups, 0) AS cost_per_signup_usd,
       spend_cents / 100.0 / NULLIF(new_paying_users, 0) AS cac_usd
FROM counts
ORDER BY period_start, channel
```

## Proposed metrics

None. A new metric is listed here before it is defined.
