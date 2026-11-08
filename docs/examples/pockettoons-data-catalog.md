# Data Catalog: PocketToons reference fixture

**Status:** Draft for review. This catalog describes the synthetic SQLite fixture, not an implemented agent or a general catalog for every product. The fixture contains 19 tables, including dataset_metadata and content_tier_history. The reference data model specifies the intended contract; the catalog describes available data, relationships and safe use. Metric definitions belong in a separate future metric registry. Frozen Architecture v1 is unchanged.

**Reading the column lists:** Each line identifies a column and its meaning. All columns have SQLite TEXT type except amounts and completion percentages (REAL), counts, durations, positions, episode numbers and boolean flags (INTEGER), and raw_amount (no declared type). Timestamps are UTC ISO-8601 values stored as TEXT. Dates are TEXT. A question mark after a column means nullable in the current schema; other non-key columns are declared NOT NULL. SQLite text primary keys are not always explicitly declared NOT NULL, but the model and existing checker require non-null identifiers. Composite key columns are declared NOT NULL.

All tables below exist in newly generated fixtures. Logical Bronze/Silver/Gold assignments, transformations and reconciliation are planned, not implemented. Dataset-level metadata stores the user snapshot timestamp. Examples are illustrative; not real customer records. Existing checker coverage is selective: a model requirement is not automatically a database constraint or a passing test.

## Shared safe-use rules

- State the reporting grain before joining. Aggregate separate one-to-many facts before combining them; do not sum a repeated transaction or session amount.
- Identify an episode by both content_id and episode_number. Use effective start-inclusive, end-exclusive intervals for as-of joins; check that at most one applicable interval matches.
- Event dates are derived UTC compatibility fields; the marketing spend date is a source reporting date and cannot be assumed UTC without source evidence.
- Preserve unknown acquisition attribution; do not allocate it silently. A direct channel match is not proof of user-level marketing attribution.
- Raw, corrected and allocated amounts are related representations, not separate payments. Refunds are positive and subtracted in revenue calculations.
- The reference model governs intended business rules. This catalog describes actual physical availability and known gaps; discrepancies require resolution rather than an invented assumption.

## 1. users

**Purpose:** Registered-user profile, acquisition and subscription snapshot. **Grain:** One registered user. **Primary key:** user_id. **Time:** signup_at is the signup instant; signup_date is its derived UTC date. Subscription fields represent the common snapshot, not a historical timeline.

**Columns:** user_id — opaque user ID; signup_date — derived date; signup_at — account-creation timestamp; country — current country or unknown; country_origin? — signup country, not nationality; country_current? — current profile country; acquisition_source — first-touch source, including unknown for missing attribution; subscription_status — snapshot status; subscription_start? and subscription_end? — current/latest period boundaries; created_at and updated_at — source-profile creation and latest update times, not ingestion times.

**Values/nulls:** Model acquisition values: organic, paid_search, paid_social, creator, referral, other, unknown. Subscription values: never_subscribed, active, cancel_at_period_end, expired, refunded, paused. A never-subscribed user has never_subscribed and NULL start/end. NULL country means unknown; NULL subscription boundary means not applicable or unavailable.

**Joins:** user_id is referenced by sessions, content_views, transactions, subscription_history, identity_links and user_events; one user can have many children. A logical marketing-channel match is not a foreign key. **Use:** signups by acquisition source; report unknown.

**Limitations/checks:** Use subscription_history for historical status and event country for historical location. The checker reads users_snapshot_at from dataset_metadata and checks required values, date/UTC format, value domains, country agreement, never-subscribed state, status and period boundaries, chronology, monthly renewal dates, and selected source-profile update timing. Audit validation checks known generated subscription-status changes, not every possible profile change. For active subscriptions, subscription_end is the scheduled exclusive paid-period end; refund ends access at approval. Monthly billing follows calendar months; treatment of days 26–31 in shorter months is not defined by this fixture.

### User columns: physical schema and interpretation

| Column | SQLite type | Nullable? | Meaning / example |
|---|---|---|---|
| user_id | TEXT primary key | Required by checker | Opaque ID; e.g. u00001. |
| signup_date | TEXT | No | UTC date derived from signup_at; e.g. 2026-04-12. |
| signup_at | TEXT | No | UTC account creation time, e.g. 2026-04-12T10:30:00Z. |
| country | TEXT | No | Current country, or unknown if unavailable. |
| country_origin | TEXT | Yes | Signup country; NULL if unavailable, not nationality. |
| country_current | TEXT | Yes | Current profile country; NULL if unavailable. |
| acquisition_source | TEXT | No | First touch; unknown means missing attribution. |
| subscription_status | TEXT | No | Status at users_snapshot_at; never_subscribed is explicit. |
| subscription_start | TEXT | Yes | Start of current/latest paid period; NULL if never subscribed or unavailable. |
| subscription_end | TEXT | Yes | Scheduled exclusive end for an active paid period, or actual earlier refund termination; NULL if never subscribed or unknown. |
| created_at | TEXT | No | Source-profile creation timestamp. |
| updated_at | TEXT | No | Source-profile latest update timestamp, not ingestion timestamp. |

An active period beginning 1 October ends at 1 November at the same UTC time; this is a calendar month, not necessarily 30 days. A cancellation-at-period-end remains entitled through its scheduled exclusive end. For expired or refunded users, the status-period start differs from the paid-period start: the status begins when access ended. A never-subscribed user has NULL period boundaries. Event examples and identifiers are illustrative.

## 2. sessions

**Purpose:** App visits, including anonymous browsing before login. **Grain:** One continuous device visit. **Primary key:** session_id. **Time:** session_started_at, last_activity_at, session_ended_at?; date is derived from start.

**Columns:** session_id — visit ID; user_id? — signed-in user if known; anonymous_id — installation/browser identity; date — UTC start date; session_started_at — start; session_ended_at? — end, NULL while open; last_activity_at — latest engagement; duration_sec? — session elapsed seconds, not episode duration; platform — device platform; country_at_event? — observed country; device_id_hash? — optional privacy-safe device identifier; app_version? — optional version.

**Joins:** user_id → users (optional), anonymous_id → anonymous_identities; session_id is referenced by identity_links, views, events and optional transactions. Each parent has zero or many child records. **Use:** session activity by platform. **Limitations/checks:** A session can have zero or many views. A 30-minute inactivity gap on the same browser/device starts a new session; playback heartbeats count. The same user may use multiple devices concurrently. A different account on the same device starts a new session even without a 30-minute gap. The checker validates timestamp/date/duration, same-identity overlapping intervals, platform, linked identity consistency, view/event/transaction consistency and activity-evidence gaps. The fixture declares complete synthetic activity evidence and provides session_engagement and playback_heartbeat observations. This supports testing fixture timing but is not proof that a real-world source captured all activity. Anonymous IDs are browser/installation identifiers, not definitive proof of a physical device. The fixture includes browsing-only sessions; open and unidentified sessions are covered by isolated regression scenarios, not the generated population.

### Session columns and null meanings

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| session_id | TEXT primary key | Required by checker | Session identifier. |
| user_id | TEXT | Yes | Authenticated user when identified; NULL otherwise. |
| anonymous_id | TEXT | No | Browser/installation identity, not a person identifier. |
| date | TEXT | No | UTC date of session_started_at. |
| session_started_at | TEXT | No | UTC session start. |
| session_ended_at | TEXT | Yes | End at last observed activity; NULL for an open session. |
| last_activity_at | TEXT | No | Latest observed engagement or playback heartbeat. |
| duration_sec | INTEGER | Yes | Elapsed seconds; NULL while open. |
| platform | TEXT | No | ios, android, web or tv; fixture contains ios, android, web. |
| country_at_event | TEXT | Yes | Observed country, NULL if unavailable. |
| device_id_hash | TEXT | Yes | Privacy-safe device identifier if available; not a person key. |
| app_version | TEXT | Yes | App version when available. |

Example: user U1 may have a phone session from 10:00 to 10:30 and a separate browser session from 10:10 to 10:20. A session may contain no views, one view or multiple views. Aggregate views and transactions separately by session_id before combining them. The current checker uses no client clock tolerance for these comparisons; adding a tolerance is a separate decision.

### Example: one row per session without multiplying facts

```sql
WITH view_summary AS (
  SELECT session_id, COUNT(*) AS view_count,
         SUM(watch_duration_sec) AS watch_seconds
  FROM content_views GROUP BY session_id
), payment_summary AS (
  SELECT session_id, COUNT(*) AS payment_records,
         SUM(CASE WHEN status = 'succeeded' AND type IN ('subscription', 'ppv')
                  THEN amount_usd ELSE 0 END) AS successful_charges,
         SUM(CASE WHEN status = 'succeeded' AND type = 'refund'
                  THEN amount_usd ELSE 0 END) AS successful_refunds
  FROM transactions WHERE session_id IS NOT NULL GROUP BY session_id
)
SELECT s.session_id, COALESCE(v.view_count, 0) AS view_count,
       COALESCE(v.watch_seconds, 0) AS watch_seconds,
       COALESCE(p.payment_records, 0) AS payment_records,
       COALESCE(p.successful_charges, 0) AS successful_charges,
       COALESCE(p.successful_refunds, 0) AS successful_refunds
FROM sessions s
LEFT JOIN view_summary v ON v.session_id = s.session_id
LEFT JOIN payment_summary p ON p.session_id = s.session_id;
```

This query returns one row per session, including sessions with no views or payments. The payment record count includes failed attempts; the amount columns include succeeded transactions only. Off-session renewals and refunds are deliberately excluded, so these amounts are not total product revenue. The fixture checker reconciles the session-grain summary's row count, view count, watch seconds, linked payment count, succeeded charge amounts and refund amounts to their independent source totals. An isolated regression case demonstrates that directly joining two views to two payments produces four rows and inflated sums. This validates the documented pattern, not every possible downstream join or metric.

## 3. content_catalog

**Purpose:** Series/title metadata. **Grain:** One title. **Primary key:** content_id. **Time:** first_release_at, last_release_at?, available_from_at?, available_until_at?, created_at and updated_at; release_date derives from first release.

**Columns:** content_id — title ID; title — display name; genre — primary genre; total_episodes — published/planned episode count; release_date — first-release date; first_release_at — first release timestamp; total_duration_sec — sum of episode lengths; content_tier — free, premium or mixed; content_status — current scheduled, live, delisted or archived status; last_release_at? — most recent release; available_from_at?/available_until_at? — current/latest availability boundaries; created_at/updated_at — record audit times.

**Joins:** content_id → many content_episodes; identify an episode with both keys. content_views references an episode composite key; join on content_id alone only for an explicitly title-level analysis. Availability history is episode-grain; match both episode keys and event time. **Use:** titles by genre or total catalog inventory. **Limitations/checks:** Current title tier and status do not prove an episode's historical tier or availability. Inventory includes scheduled episodes; it is not a count of episodes live now. The checker validates required fields, UTC formatting and derived release date, title status/tier, availability boundaries, inventory episode count/duration, tier consistency and title-grain join reconciliation. Its release-summary check uses non-scheduled episode status as a proxy for released episodes, not independent proof of release timing. Historical availability uses episode history at the event time.

### Title columns

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| content_id | TEXT primary key | Required by checker | Series identifier. |
| title | TEXT | No | Title name. |
| genre | TEXT | No | Primary genre. |
| total_episodes | INTEGER | No | Count of all episode records, including scheduled episodes. |
| release_date | TEXT | No | UTC date derived from first_release_at. |
| first_release_at | TEXT | No | First episode release timestamp. |
| last_release_at | TEXT | Yes | Latest released episode timestamp if known; NULL when none known. |
| total_duration_sec | INTEGER | No | Total duration of all episode records, including scheduled episodes. |
| content_tier | TEXT | No | free if all episodes are free, premium if all premium, mixed if both; includes scheduled episodes. |
| content_status | TEXT | No | Current title status: scheduled, live, delisted or archived. |
| available_from_at | TEXT | Yes | Start of current/latest title availability if known. |
| available_until_at | TEXT | Yes | Exclusive end of availability if known; NULL for open or unknown. |
| created_at | TEXT | No | Record creation timestamp. |
| updated_at | TEXT | No | Record update timestamp. |

For example, a title with 10 live episodes and 2 scheduled episodes has total_episodes=12; total_duration_sec includes all 12 durations. To calculate currently live episodes, use episode-level availability at an explicitly specified time, not the inventory count. A title containing both free and premium episodes is mixed; the episode tier governs access to a particular episode.

### Safe title-grain summary

```sql
WITH episodes AS (
  SELECT content_id, COUNT(*) AS episode_rows,
         SUM(episode_duration_sec) AS episode_seconds
  FROM content_episodes GROUP BY content_id
), views AS (
  SELECT content_id, COUNT(*) AS view_rows,
         SUM(watch_duration_sec) AS watch_seconds
  FROM content_views GROUP BY content_id
)
SELECT c.content_id, c.total_duration_sec,
       COALESCE(e.episode_rows, 0) AS episode_rows,
       COALESCE(e.episode_seconds, 0) AS episode_seconds,
       COALESCE(v.view_rows, 0) AS view_rows,
       COALESCE(v.watch_seconds, 0) AS watch_seconds
FROM content_catalog c
LEFT JOIN episodes e ON e.content_id = c.content_id
LEFT JOIN views v ON v.content_id = c.content_id;
```

This returns one row per title. Episode inventory and view facts are summarized independently. It does not determine live episodes, historical tier, revenue or a finalized engagement metric. The checker reconciles this pattern to source totals; isolated regression tests demonstrate how a direct join can multiply title duration and watch time.

## 4. content_episodes

**Purpose:** Episode-level metadata and access. **Grain/key:** One episode per (content_id, episode_number). **Time:** release_at and current/latest available_from_at?/available_until_at?.

**Columns:** content_id and episode_number — composite episode key; episode_title? — display name; episode_duration_sec — length; release_at — release time; access_tier — free or premium; episode_status — current scheduled, live, delisted or archived; ppv_list_price_usd? — current list price when offered; available_from_at?/available_until_at? — availability interval.

**Joins:** content_id → content_catalog; composite key → views, availability history, tier history and attribution. Each parent episode may have many views, purchases, refunds and history rows. **Use:** episode catalog and current tier at content_catalog_snapshot_at. **Limitations/checks:** Episode number alone is not unique; current price is not necessarily purchase price. The fixture stores current list price and actual charged transaction amount, not historical list-price changes. The checker validates episode domains, UTC times and availability boundaries, nonnegative premium-only list prices, episode FK resolution, duration/position bounds, title inventory reconciliation, as-of tier eligibility and safe episode-grain aggregation. The current fixture assumes episode lengths do not change over time; production data may require versioned duration history.

### Episode column details

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| content_id | TEXT composite primary key | No | Parent title ID. |
| episode_number | INTEGER composite primary key | No | Positive episode number within the title. |
| episode_title | TEXT | Yes | Episode name; NULL if unavailable. |
| episode_duration_sec | INTEGER | No | Positive full episode duration in seconds. |
| release_at | TEXT | No | UTC scheduled or actual release time. |
| access_tier | TEXT | No | Current snapshot: free or premium; use content_tier_history for earlier times. |
| episode_status | TEXT | No | Current scheduled, live, delisted or archived status. |
| ppv_list_price_usd | REAL | Yes | Current premium-episode PPV list price, nonnegative; NULL when not offered. A past actual charge is in transactions. |
| available_from_at | TEXT | Yes | Current/latest availability start, if known. |
| available_until_at | TEXT | Yes | Exclusive end; NULL for open or unknown. |

Example: episode 21 of title c01 is premium before 2026-07-01T00:00:00Z and free from that instant. A subscriber view before the change and a free view afterward remain distinct historical facts. Use episode key plus event timestamp to look up the effective tier; availability and entitlement are separate checks. The snapshot date is stored in dataset_metadata.content_catalog_snapshot_at.

### Episode-grain joins and safeguards

content_views, transaction_content_attribution and refund_content_attribution are independent one-to-many facts. Pre-aggregate each by (content_id, episode_number), then join those summaries to content_episodes. A direct join of 100 views with 10 allocations can produce 1,000 rows. The checker reconciles this independent-aggregate pattern to source counts, watch seconds and allocation totals; this is not a complete revenue metric or a guarantee for arbitrary queries. The data layers and their layer-specific mappings remain planned.

```sql
-- One row per view, joined to the tier in effect at its playback start.
SELECT v.view_id, v.content_id, v.episode_number, v.view_started_at,
       h.access_tier AS tier_at_view
FROM content_views v
JOIN content_tier_history h
  ON h.content_id = v.content_id
 AND h.episode_number = v.episode_number
 AND h.effective_start_at <= v.view_started_at
 AND (h.effective_end_at IS NULL OR v.view_started_at < h.effective_end_at);
```

The example requires non-overlapping tier periods and matches only views with known history. Use a left join plus missing-match checks when auditing completeness; separately establish episode availability and the user's entitlement. An as-of tier match is not, by itself, proof of access or a complete metric.

## 5. content_availability_history

**Purpose:** Episode availability and status over time. **Grain:** One effective episode/status interval. **Key:** availability_id. **Time:** available_from_at inclusive; available_until_at? exclusive; recorded_at is record time.

**Columns:** availability_id — interval ID; content_id/episode_number — episode; available_from_at — start; available_until_at? — end, NULL for open interval; status — status during interval; recorded_at — recording time.

**Joins:** Composite episode foreign key. Match episode and event time. **Use:** whether an episode was live when viewed. **Limitations/checks:** Without a time condition multiple intervals can duplicate a view. From the first tracked instant periods are contiguous, non-overlapping and half-open; before tracking or with missing source history the answer is unknown, not an inferred status. The checker validates period fields, gaps/overlaps, episode status at content_catalog_snapshot_at, current live-period boundaries, views, PPV purchases while live, delisting entitlement cutoffs and prior holder notices. For non-live snapshots it validates status but does not infer what the optional current/latest availability boundary fields must contain. recorded_at is not complete bitemporal version history.

### Availability columns

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| availability_id | TEXT primary key | Required by checker | Availability period ID. |
| content_id | TEXT | No | Parent title ID. |
| episode_number | INTEGER | No | Episode within title; composite FK with content_id. |
| status | TEXT | No | scheduled, live, delisted or archived during this interval. |
| available_from_at | TEXT | No | Inclusive effective start, including for a non-live status. |
| available_until_at | TEXT | Yes | Exclusive effective end; NULL while the period is open. |
| recorded_at | TEXT | No | UTC recording time; not necessarily the effective time. |

For the fixture's c12 episode 20, the live period ends exactly as delisted begins on 10 September 2026 UTC; live resumes exactly on 20 September. Every succeeded PPV entitlement active immediately before delisting ends at that boundary. Prior refunds or other already-ended entitlements remain ended; relisting does not restore them. Each affected holder has a prior synthetic notice. An entitlement after relisting requires a new succeeded purchase while live.

### As-of join

```sql
SELECT v.view_id, v.view_started_at, h.status AS availability_at_view
FROM content_views v
LEFT JOIN content_availability_history h
  ON h.content_id = v.content_id
 AND h.episode_number = v.episode_number
 AND h.available_from_at <= v.view_started_at
 AND (h.available_until_at IS NULL OR v.view_started_at < h.available_until_at);
```

The LEFT JOIN keeps a view with missing history visible as an unknown rather than silently dropping it. Validate uniqueness and coverage before relying on one row per view. A live status alone does not establish subscription or PPV entitlement. Tier history and the relevant access period are separate as-of joins; the physical layer and query grain depend on the use case.

## 6. content_views

**Purpose:** Authenticated measurable playback. **Grain:** One playback start/attempt; a resume may be another row. **Key:** view_id. **Time:** view_started_at/view_ended_at; date derives from start.

**Columns:** view_id — attempt ID; user_id — authenticated viewer; anonymous_id — session identity; session_id — containing session; content_id/episode_number — episode; date — UTC start date; view_started_at/view_ended_at — boundaries; watch_duration_sec — watched seconds, including rewatches; content_duration_sec — episode length at playback; view_type — free, sub or ppv entitlement at start; completion_pct? — known unique coverage fraction; playback_position_start_sec/playback_position_end_sec? — positions; is_first_view_of_episode — first known view flag; free_quota_consuming — slot-consumption flag; free_quota_sequence? — slot number if applicable; event_timezone? — reported IANA timezone; country_at_event? — viewing country.

**Joins:** Required user, session and identity FKs and composite episode FK. **Use:** watch time by episode. **Limitations/checks:** Views are not distinct viewers or necessarily complete episodes. Current fixture requires view_ended_at although the model allows NULL for incomplete events. Existing tests cover selected login, session chronology, availability, quota and entitlement cases; propose full position, date and fanout validation.

## 7. transactions

**Purpose:** Payment and refund records including failed attempts. **Grain:** One financial/provider record. **Key:** txn_id; provider_transaction_id is unique. **Time:** transaction_at and derived date; payment-status effective time is in payment_status_history.

**Columns:** txn_id — transaction ID; user_id — economic user; date — UTC transaction date; type — subscription, ppv or refund; transaction_subtype — more specific kind; amount_usd — curated positive amount; payment_method — method; status — recorded status; transaction_at — time; session_id? — initiating session or NULL for off-session operations; provider_transaction_id — provider ID; payment_provider — provider; currency — original currency; original_amount — original-currency amount; related_txn_id? — original charge for refund; subscription_id? — logical subscription; list_price_usd?/discount_usd? — price and discount if known; country_at_event? — country if known; refund_reason? — reported refund reason, NULL for non-refunds.

**Joins:** user FK, optional session FK and self-FK for original charge; txn_id links status, source, review and attribution. subscription_id is a logical link rather than a declared subscription-entity FK. **Use:** succeeded charges and refunds. **Limitations/checks:** Subtract positive refunds; exclude failed attempts where appropriate. Do not multiply amounts through status or attribution joins. Checker validates selected refund linkage, reasons and ceilings; propose comprehensive status and financial reconciliation.

## 8. marketing_spend

**Purpose:** Daily channel-level spend and delivery. **Grain/key:** (date, channel). **Time:** source reporting date and loaded_at.

**Columns:** date — source reporting date; channel — marketing channel; spend_usd — spend; impressions — delivered impressions; clicks — delivered clicks; loaded_at — ingestion time.

**Joins:** Channel/time matching to acquisition is logical, not an individual-user FK. **Use:** spend by channel and day. **Limitations/checks:** No campaign/country breakdown; source timezone must be established. Joining one spend row to many users repeats spend. Required fields are checked; propose non-negative values and clicks ≤ impressions checks.

## 9. anonymous_identities

**Purpose:** Pseudonymous browser/installation identities. **Grain/key:** One identity per anonymous_id. **Time:** created_at and retired_at?.

**Columns:** anonymous_id — identity; created_at — creation time; retired_at? — retirement if applicable.

**Joins:** Referenced by sessions, identity_links, views and optional events. **Use:** browser-level pre-login activity. **Limitations/checks:** An identity is not a person; shared devices can have multiple users. Anonymous playback is prohibited. Existing checks test authenticated playback; propose shared-device resolution checks.

## 10. identity_links

**Purpose:** Observed login/signup connection between identity and account in a session. **Grain/key:** One link per identity_link_id. **Time:** linked_at.

**Columns:** identity_link_id — ID; anonymous_id — installation identity; user_id — linked account; session_id — session; linked_at — login/signup time; link_method — login or signup.

**Joins:** Required FKs to identity, user and session. **Use:** resolve eligible pre-login browsing in that same session. **Limitations/checks:** Do not claim other sessions or ambiguous shared-device behavior. Checker tests preceding link for views; propose conflicting-link and resolution tests.

## 11. subscription_history

**Purpose:** Effective subscription status and entitlement history. **Grain/key:** One status interval per subscription_period_id. **Time:** effective_start_at inclusive, effective_end_at? exclusive; subscription_status_updated_at, cancelled_at? and recorded_at have distinct meanings.

**Columns:** subscription_period_id — period ID; subscription_id — logical subscription; user_id — owner; effective_start_at/effective_end_at? — boundaries; subscription_status_updated_at — change time; status — period status; plan_code — plan; source_txn_id? — related payment if applicable; cancelled_at? — cancellation request; recorded_at — recording time.

**Joins:** User FK, optional source transaction FK, and period can be referenced by events. **Use:** subscription status at playback. **Limitations/checks:** Cancellation may retain access until end. Checker tests overlap and selected cancellation/refund cases; propose complete continuity and snapshot reconciliation. recorded_at does not preserve every historical warehouse version.

## 12. transaction_content_attribution

**Purpose:** PPV transaction-to-episode grant and allocation. **Grain/key:** One transaction × episode attribution per txn_content_attribution_id. **Time:** entitlement_start_at, entitlement_end_at?, refunded_at?, delisted_at?.

**Columns:** txn_content_attribution_id — attribution ID; txn_id — purchase; content_id/episode_number — episode; entitlement_start_at/entitlement_end_at? — access interval; attributed_amount_usd — allocated purchase amount; attribution_status — grant status; refunded_at?/delisted_at? — relevant cutoff.

**Joins:** Transaction FK and episode composite FK; user obtained through transaction. **Use:** PPV entitlement at playback. **Limitations/checks:** A bundle can create multiple rows; do not repeat full purchase amount. Refund or delisting ends entitlement; relisting requires repurchase. Checker covers selected PPV access and failed-payment scenarios; propose full allocation reconciliation.

## 13. refund_content_attribution

**Purpose:** Episode-level allocation of PPV refunds. **Grain/key:** One refund × episode allocation per refund_allocation_id. **Time:** refund timing comes from the linked transaction/status history.

**Columns:** refund_allocation_id — allocation ID; refund_txn_id — refund; content_id/episode_number — episode; allocated_refund_usd — positive allocated refund.

**Joins:** Refund transaction FK and episode composite FK. **Use:** PPV net revenue by episode. **Limitations/checks:** Not a second payment; subtract positive refund. Checker reconciles PPV refund allocations; do not assume subscription refunds are episode allocations.

## 14. payment_status_history

**Purpose:** Payment-provider status transitions. **Grain/key:** One transition per payment_status_event_id; provider_event_id unique. **Time:** effective_at is status-effective time; recorded_at is recording time.

**Columns:** payment_status_event_id — event ID; txn_id — payment; status — transition status; effective_at — effective time; recorded_at — recorded time; provider_event_id — provider event ID.

**Joins:** txn_id → transactions; one transaction can have many transitions. **Use:** status at a chosen time. **Limitations/checks:** Summing transaction amounts after joining all transitions can duplicate revenue. Checker uses status history in selected checks; propose transition-order and latest-status reconciliation.

## 15. user_events

**Purpose:** Behavioral and business-event timeline. **Grain/key:** One event per event_id. **Time:** event_at is occurrence time; ingested_at is arrival time; event_timezone? is contextual.

**Columns:** event_id — ID; user_id? — signed-in actor if known; anonymous_id? — identity when applicable; event_at — occurrence; event_name — event type, including session_engagement and playback_heartbeat for synthetic timing evidence; session_id?/view_id?/txn_id?/subscription_period_id? — relevant referenced record; content_id?/episode_number? — relevant content; event_properties_json? — event-specific context including the synthetic marker for these observations; event_timezone? — reported timezone; country_at_event? — observed country; ingested_at — arrival.

**Joins:** Optional FKs to user, identity, session, view, transaction, period and series; episode composite FK where populated. **Use:** paywall-to-checkout sequence. **Limitations/checks:** Different event types populate different fields. Synthetic engagement and heartbeat observations are not additional views, watch-time increments, payments or proof of deliberate interaction. Select one owner for a business moment to avoid duplicating payment/view facts. Checker covers selected session timing and heartbeat bounds, product labels, funnel and refund order; propose broader event-specific schema checks.

## 16. raw_payment_source

**Purpose:** Preserve raw payment source evidence. **Grain/key:** One source record per txn_id. **Time:** received_at.

**Columns:** txn_id — linked transaction; raw_amount — untyped source value, which may be numeric, numeric text, unavailable text or mis-scaled; raw_unit — reported unit, which may be misleading; received_at — source arrival.

**Joins:** txn_id FK → transactions; logical same-key link to optional payment_quality_review. **Use:** investigate unusual source amounts. **Limitations/checks:** Not another payment; do not silently cast invalid text or correct an outlier without evidence. Checker reconciles reviewed values with curated transactions; propose source profiling and completeness checks.

## 17. payment_quality_review

**Purpose:** Evidence and corrections for reviewed payment records. **Grain/key:** One reviewed transaction per txn_id. **Time:** No review timestamp exists.

**Columns:** txn_id — reviewed transaction; issue — issue type; corrected_amount_usd — reviewed corrected amount; reason — correction rationale.

**Joins:** txn_id FK → transactions; logical same-key match to raw_payment_source. **Use:** reconcile source and corrected values. **Limitations/checks:** Not another payment and not proof that an agent independently detected the issue. Checker tests reviewed amounts against curated transaction values. Proposed: review timestamp and evidence/coverage checks.

## Open implementation work

The user-profile update check covers generated status changes but not all possible source profile changes. The full data layers, metric registry, catalog machine-readable format and agent integration remain future work. Each proposed quality check must be implemented and verified before it is described as an existing check.

## 18. dataset_metadata

**Purpose:** Dataset-wide metadata. **Grain/key:** One value per metadata_key. **Columns:** metadata_key TEXT primary key NOT NULL; metadata_value TEXT NOT NULL. users_snapshot_at and content_catalog_snapshot_at are separate UTC as-of instants for the respective snapshots. session_activity_coverage=complete_synthetic_v1 declares this fixture's synthetic evidence coverage for session boundary and heartbeat checks. The checker requires these values; it does not validate unrelated metadata keys. **Use:** determine snapshot timing and applicable activity checks. **Limitations:** Later datasets with independent refresh times or incomplete source telemetry need different handling; the synthetic coverage flag is not proof of completeness in real data.

## 19. content_tier_history

**Purpose:** Effective-dated episode access tiers. **Grain:** One tier period for one episode. **Primary key:** tier_period_id. **Time:** effective_start_at inclusive, effective_end_at exclusive; recorded_at is when the period was recorded.

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| tier_period_id | TEXT primary key | No | Period identifier. |
| content_id | TEXT | No | Parent title. |
| episode_number | INTEGER | No | Episode number within title. |
| access_tier | TEXT | No | free or premium during this interval. |
| effective_start_at | TEXT | No | UTC inclusive start. |
| effective_end_at | TEXT | Yes | UTC exclusive end; NULL for an open interval. |
| recorded_at | TEXT | No | UTC recording time; not a full historical warehouse version. |

**Joins:** Composite FK (content_id, episode_number) → content_episodes, then match event timestamp within the interval. **Use:** determine whether an episode was free at view start or premium at PPV purchase. **Limitations/checks:** Do not multiply a view by all historical periods or infer availability from tier. Checker validates domains, UTC timestamps, contiguous non-overlapping intervals, coverage from release, current snapshot reconciliation, free views and PPV purchase eligibility. Price and duration history are not represented by this table.

If an episode changes from free to premium while an authorized playback attempt is already in progress, that attempt may continue under the decision made at its start. A later start or resume is a separate attempt and must be checked against the tier and user entitlement at that later time. The isolated regression test verifies the tier decision at the exact boundary; subscription and PPV entitlement and episode availability remain separate checks. This scenario is tested independently and is not represented as an in-progress tier change in the main fixture.
