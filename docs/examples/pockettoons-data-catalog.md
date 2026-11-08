# Data Catalog: PocketToons reference fixture

**Status:** Draft for review. This catalog describes the synthetic SQLite fixture, not an implemented agent or a general catalog for every product. The fixture contains 20 tables, including dataset_metadata, content_tier_history and playback_segments. The reference data model specifies the intended contract; the catalog describes available data, relationships and safe use. Metric definitions belong in a separate future metric registry. Frozen Architecture v1 is unchanged.

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

**Values/nulls:** Model acquisition values: organic, paid_search, paid_social, creator, referral, other, unknown. Subscription values: never_subscribed, active, cancel_at_period_end, expired, refunded. A never-subscribed user has never_subscribed and NULL start/end. NULL country means unknown; NULL subscription boundary means not applicable or unavailable.

**Joins:** user_id is referenced by sessions, content_views, transactions, subscription_history, identity_links and user_events; one user can have many children. A logical marketing-channel match is not a foreign key. **Use:** signups by acquisition source; report unknown.

**Limitations/checks:** Use subscription_history for historical status and event country for historical location. The checker reads users_snapshot_at from dataset_metadata and checks required values, date/UTC format, value domains, country agreement, never-subscribed state, status and period boundaries, chronology, monthly renewal dates, and selected source-profile update timing. Audit validation checks known generated subscription-status changes, not every possible profile change. For active subscriptions, subscription_end is the scheduled exclusive paid-period end; a successful refund for that still-active period ends its access at the refund's success-effective time. Monthly billing follows calendar months; treatment of days 26–31 in shorter months is not defined by this fixture.

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
  SELECT session_id, COUNT(*) AS payment_records
  FROM transactions WHERE session_id IS NOT NULL GROUP BY session_id
)
SELECT s.session_id, COALESCE(v.view_count, 0) AS view_count,
       COALESCE(v.watch_seconds, 0) AS watch_seconds,
       COALESCE(p.payment_records, 0) AS payment_records
FROM sessions s
LEFT JOIN view_summary v ON v.session_id = s.session_id
LEFT JOIN payment_summary p ON p.session_id = s.session_id;
```

This query returns one row per session, including sessions with no views or payments. The payment record count includes failed attempts. Off-session renewals and refunds are deliberately excluded. For money, validate and convert individual USD values to integer cents before separately aggregating them as described in the transaction entry; do not use an unvalidated REAL sum. The fixture checker reconciles the session-grain summary's row count, view count, watch seconds, linked payment count and succeeded charge/refund amounts in cents to their independent source totals. An isolated regression case demonstrates that directly joining two views to two payments produces four rows and inflated sums. This validates the documented pattern, not every possible downstream join or metric.

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

For the fixture's c12 episode 20, the live period ends exactly as delisted begins on 10 September 2026 UTC; live resumes exactly on 20 September. Every succeeded PPV entitlement active immediately before delisting ends at that boundary. Prior fully refunded or other already-ended entitlements remain ended; relisting does not restore them. Each affected holder has a prior synthetic notice. An entitlement after relisting requires a new succeeded purchase while live.

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

**Joins:** Required user, session and identity FKs and composite episode FK. Tier, availability, subscription and PPV entitlement use separate as-of lookups at view start. view_id → many playback_segments and user_events; aggregate each child independently to avoid fanout. **Use:** watch time by episode or a user journey. **Limitations/checks:** Views are not distinct viewers or necessarily complete episodes. Current fixture requires view_ended_at although the model allows NULL for incomplete events. Checks cover dates, first-view flag, free quota sequencing and resumes, access precedence, historical access, session consistency, playback bounds and segment reconciliation. These fixture checks do not cover every possible playback, late event or data-source behavior.

### View column details

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| view_id | TEXT primary key | Required by checker | Playback-attempt ID. |
| user_id | TEXT | No | Authenticated viewer. |
| anonymous_id | TEXT | No | Session browser/installation identity. |
| session_id | TEXT | No | Session containing the view. |
| content_id | TEXT | No | Parent title ID. |
| episode_number | INTEGER | No | Episode within the title. |
| date | TEXT | No | UTC date derived from view start. |
| view_started_at | TEXT | No | Playback start or resume time. |
| view_ended_at | TEXT | No in fixture | Playback end; the model permits NULL for incomplete records. |
| watch_duration_sec | INTEGER | No | Total time watched in this attempt, including repeated sections. |
| content_duration_sec | INTEGER | No | Episode duration at playback. |
| view_type | TEXT | No | Access at start: free, sub or ppv. |
| completion_pct | REAL | Yes | Unique position coverage in this attempt divided by duration, from 0 to 1; NULL if coverage unknown. |
| playback_position_start_sec | INTEGER | No | Starting position. |
| playback_position_end_sec | INTEGER | Yes | Final position if known; can be below start after a rewind. |
| is_first_view_of_episode | INTEGER | No | 1 for first known user/episode attempt, otherwise 0. |
| free_quota_consuming | INTEGER | No | 1 if this free attempt consumes a new UTC-day slot, otherwise 0. |
| free_quota_sequence | INTEGER | Yes | Slot 1–8 for a quota-consuming attempt; NULL otherwise. |
| event_timezone | TEXT | Yes | Reported IANA timezone if known, context only. |
| country_at_event | TEXT | Yes | Observed country if known. |

The fixture declares complete synthetic playback-segment coverage and contains both rewind and skip examples. For ranges [0,300) and [180,360), 480 seconds were watched but only 360 unique content seconds were covered. Per-attempt completion is 360 divided by the episode duration. For completion across attempts, merge all ranges for the chosen user and episode; do not sum attempt completion fractions. In other datasets, missing segments make exact unique coverage unknown, not zero.

## 7. transactions

**Purpose:** Payment and refund records including failed attempts. **Grain:** One financial/provider record. **Key:** txn_id; provider_transaction_id is unique. **Time:** transaction_at and derived date; payment-status effective time is in payment_status_history.

**Columns:** txn_id — transaction ID; user_id — economic user; date — UTC transaction date; type — subscription, ppv or refund; transaction_subtype — more specific kind; amount_usd — curated positive amount; payment_method — method; status — recorded status; transaction_at — time; session_id? — initiating session or NULL for off-session operations; checkout_event_id? — captured initiating checkout event; provider_transaction_id — provider ID; payment_provider — provider; currency — original currency; original_amount — original-currency amount; related_txn_id? — original charge for refund; subscription_id? — logical subscription; list_price_usd?/discount_usd? — price and discount if known; country_at_event? — country if known; refund_reason? — reported refund reason, NULL for non-refunds.

**Joins:** user FK, optional session FK and self-FK for original charge; txn_id links status, source, review and attribution. subscription_id is a logical link rather than a declared subscription-entity FK. Each transaction can have many status transitions and attribution rows; raw source/review each have at most one row per transaction. **Use:** payment attempts and succeeded charges/refunds. **Limitations/checks:** Subtract positive refunds; exclude failed attempts where appropriate. Off-session records must not be lost to an inner session join. Do not multiply amounts through status or attribution joins. Historical status requires its effective-time history, not the current status field.

**Checkout link:** transactions.checkout_event_id optionally references the checkout_started event that initiated the payment attempt. One checkout can have multiple attempts, such as a failed attempt followed by a success. A captured link must match user, session and product and occur no later than transaction creation. For a PPV transaction with episode attribution, at least one attributed episode must match the checkout episode; failed attempts are not required to have entitlement rows. NULL can mean an off-session transaction or an uncaptured link. user_events.txn_id may refer to an individual transaction and cannot represent every retry; use transactions.checkout_event_id to enumerate the attempts.

### Transaction columns

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| txn_id | TEXT primary key | Required by checker | Unique transaction ID. |
| user_id | TEXT | No | Purchaser or refund recipient. |
| date | TEXT | No | UTC date derived from transaction_at. |
| type | TEXT | No | subscription, ppv or refund. |
| transaction_subtype | TEXT | No | Initial/renewal subscription, episode purchase or corresponding refund subtype. |
| amount_usd | REAL | No | Curated USD amount; positive for both charges and refunds. |
| payment_method | TEXT | No | apple_app_store, google_play, credit_debit_card, paypal, wallet or other. |
| status | TEXT | No | Current recorded pending, succeeded, failed or voided status. |
| transaction_at | TEXT | No | UTC transaction creation time; not necessarily success time. |
| session_id | TEXT | Yes | Initiating session; NULL for off-session flows. |
| checkout_event_id | TEXT | Yes | Captured checkout_started event; NULL for off-session or uncaptured links. Many attempts can reference one checkout. |
| provider_transaction_id | TEXT | No | Unique provider transaction identifier. |
| payment_provider | TEXT | No | Processing provider. |
| currency | TEXT | No | Original currency code; the current fixture uses USD. |
| original_amount | REAL | No | Amount in original currency; not a second payment. |
| related_txn_id | TEXT | Yes | Original charge for a refund; NULL for purchase records. |
| subscription_id | TEXT | Yes | Logical subscription ID where applicable, not a declared subscription-entity FK. |
| list_price_usd | REAL | Yes | Purchase-time list price if known; not full price history. |
| discount_usd | REAL | Yes | Discount if known; nonnegative. |
| country_at_event | TEXT | Yes | Observed country if known. |
| refund_reason | TEXT | Yes | Reported reason for refunds, NULL on purchases; not an independently verified cause. |

Valid subtypes are subscription_initial, subscription_renewal, ppv_episode_purchase, subscription_refund and ppv_refund, paired with their corresponding broad type. The current fixture includes succeeded and failed records; delayed pending-to-success and later void transitions are isolated tests, not main-fixture examples. Valid refund reasons in this fixture contract are did_not_like_content, accidental_purchase and poor_playback_quality.

### Exact USD amounts and time

SQLite REAL is binary floating point. For the two-decimal USD fixture, validate each individual amount and convert using Python Decimal(str(value)) to integral cents before aggregation; reject non-finite, non-numeric or excess-precision amounts rather than silently rounding them. This conversion cannot restore precision already lost before storage; reconcile to source evidence when precision is uncertain. Subtract positive refund cents. Convert the final integer to dollars only for presentation. The checker registers a usd_cents function for its own connection; that function is not stored in SQLite and must not be assumed to exist for the agent. This USD rule does not define FX conversion or minor-unit handling for other currencies, and a stored exact-cents column in a future layer is not yet implemented.

transaction_at is creation time; payment_status_history.effective_at supplies the time a status took effect. A refund's original charge must be successful at the refund attempt time, not merely have a current successful-looking status. The checker compares the current transaction status with the latest stored effective transition and rejects identical effective timestamps for the same transaction and duplicate success transitions as ambiguous in this fixture; a broader provider transition/idempotency policy remains to be designed.

### Existing checks and coverage

The checker validates required IDs/columns, allowed type/subtype/method/status combinations, UTC creation dates, positive exact-cent USD amounts and discount bounds, provider ID uniqueness, status history ordering and snapshot consistency, historical original-charge status at refund, exact-cent refund caps, refund reason, subscription references, PPV purchase/refund allocation reconciliation, session/user consistency and evidence-backed raw-source discrepancies. The session and episode summary checks demonstrate selected fanout-safe patterns, not every downstream metric. Currency validation checks the three-uppercase-letter shape, not membership in an authoritative ISO list; multi-currency normalization and FX are not implemented. The checker rejects a void after success; returning money after success is represented by a separate refund transaction. The metric registry remains a separate stage.

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

**Purpose:** Effective subscription-status and access history. **Grain:** One status interval per subscription_period_id. The status interval is not necessarily the full paid month: a cancellation can split a paid period into multiple intervals. **Primary key:** subscription_period_id. **Logical subscription ID:** subscription_id links intervals and renewals, but is not a foreign key to a separate subscription table.

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| subscription_period_id | TEXT primary key | Required by checker | Status-interval identifier. |
| subscription_id | TEXT | No | Logical subscription identifier shared across its periods. |
| user_id | TEXT | No | Subscriber; foreign key to users. |
| effective_start_at | TEXT | No | UTC inclusive status-interval start. |
| effective_end_at | TEXT | Yes | UTC exclusive status-interval end; NULL for an open interval. |
| subscription_status_updated_at | TEXT | No | UTC time this user's current status last changed. It equals the interval start when status changes and carries forward across subsequent intervals with the same status, including renewals. |
| status | TEXT | No | active, cancel_at_period_end, expired or refunded. |
| plan_code | TEXT | No | Plan identifier; the current fixture uses monthly_9_99. |
| source_txn_id | TEXT | Yes | Related charge or refund where applicable. NULL when no payment record is linked to this status interval. |
| cancelled_at | TEXT | Yes | UTC cancellation-request time when applicable; not necessarily access-end time. |
| recorded_at | TEXT | No | UTC time the interval was recorded; it is not a complete versioned audit history. |

**Access and status:** active and cancel_at_period_end grant subscription access for the effective interval. A cancellation-at-period-end stops renewal but preserves paid access until the interval's end. expired and refunded are non-access states. Cancellation at period end means turning off the next automatic renewal while retaining access through the existing paid period. A never-subscribed user has no prior subscription history and an explicit never_subscribed value in the user snapshot; a missing historical interval after subscription is a data gap, not proof of never-subscribed status.

**Status-change time:** If an active subscription starts on 1 October and renews on 1 November without changing status, the renewal interval starts on 1 November but retains 1 October as subscription_status_updated_at. If the user cancels renewal on 10 November, status becomes cancel_at_period_end and its status-change time is 10 November. This is event-effective time, not the time a late correction was recorded.

**Cancellation example:** A user pays for 1 October 10:00 through 1 November 10:00 UTC and cancels renewal on 10 October. Status changes from active to cancel_at_period_end on 10 October, but access continues until 1 November 10:00. If no new entitlement begins, status then becomes expired. Cancellation is not a refund and does not itself return the payment.

**Joins and fanout:** user_id → users, and nullable source_txn_id → transactions. A transaction source must agree with the period's user and logical subscription; check its payment_status_history for successful-payment timing. For a historical view or event, match user_id plus effective_start_at <= event time < effective_end_at, treating a NULL end as open. Separately aggregate payments, views and periods before joining at user grain. Do not sum transaction amounts after joining them to multiple status intervals. users.subscription_* is a snapshot at dataset_metadata.users_snapshot_at, not a substitute for event-time history.

**Refund timing:** A successful refund ends access for its linked paid period at the refund event's effective_at if that period is still active. A refund for an already-ended period does not terminate a separately paid later period or create a refunded state for it; the refund still reduces revenue. Pending and failed refunds do not themselves produce a refunded interval. The checker verifies selected refund timing, including delayed success and an isolated earlier-period refund case. Immediate refunds exactly at paid-period start and billing days 26–31 are not established by the fixture.

**Checks and limitations:** The checker validates required fields, allowed status values, UTC period/recording/cancellation timestamps, last status-change time across successive intervals, ordered period boundaries, selected source-transaction ownership, absence of overlapping periods, adjacency between successive periods, selected user-snapshot reconciliation and entitlement/payment scenarios. It does not prove every allowed state transition, complete source-event ingestion, historical versions, or refund scenarios outside the tested fixture assumptions. A status record's recorded_at alone does not reconstruct overwritten records. Snapshot and entitlement checks are limited by the available fixture's observations.

**Initial paid subscription:** The first active interval starts at the succeeded payment-status event's effective_at, not at transaction creation or recording time. A pending or failed initial payment does not itself grant subscription access. The first monthly period ends one calendar month after success at the same UTC time; days 26–31 remain outside the fixture's defined renewal-date policy. The checker tests initial grant timing, monthly end, selected user-snapshot reconciliation and selected journey timing. Renewals and refunds have separate timing rules.

**Renewal timing:** A succeeded renewal starts its next paid period at the later of its success effective_at and the preceding paid period's exclusive end. A payment that succeeds early does not shorten the existing period. A late success leaves a gap with no subscription access until success; pending or failed renewal attempts do not extend access. The next period ends one calendar month after its actual start, subject to the stated month-end limitation. Record an appropriate non-access interval, such as expired after an ordinary expiry. The checker validates the start against success and the preceding entitlement end, non-access status coverage across a late-renewal gap, selected paid-period and snapshot boundaries, and rejects grants sourced to pending or failed renewals. Gap coverage assumes the separately checked non-overlapping subscription intervals; it does not establish every possible subscription lifecycle transition. The snapshot uses the paid period active by the snapshot time, not an early payment's creation time.

**Fixture coverage:** All initial subscription payments in the main fixture succeed at creation time, and its renewals succeed at the prior period end. Delayed initial success, early and late renewal, and pending/failed attempts are covered by isolated tests rather than the main dataset. The fixture's subscription refunds succeed at transaction creation; delayed and failed subscription refunds are isolated test cases.

## 12. transaction_content_attribution

**Purpose:** Link a PPV purchase to its episode entitlement and the purchase amount allocated to that episode. **Grain:** One purchase × episode entitlement. **Primary key:** txn_content_attribution_id. **Unique:** (txn_id, content_id, episode_number); a purchase has at most one row per episode, and a bundle has one row per distinct episode. The generator declares this as a SQLite UNIQUE constraint; the checker enforces the rule whether or not a database declares it. **Joins:** txn_id → transactions; (content_id, episode_number) → content_episodes. The user is identified through the purchase. A transaction can have multiple episode allocations; independent views and refunds must be pre-aggregated before joining to avoid fanout.

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| txn_content_attribution_id | TEXT primary key | Required by checker | Attribution identifier. |
| txn_id | TEXT | No | Original PPV purchase transaction; must be a type='ppv' transaction, never a subscription charge or refund. |
| content_id | TEXT | No | Title identifier; combine with episode_number. |
| episode_number | INTEGER | No | Episode within the title. |
| entitlement_start_at | TEXT | No | Inclusive UTC entitlement start; equals the purchase's succeeded effective_at in payment_status_history. |
| entitlement_end_at | TEXT | Yes | Exclusive UTC end when entitlement closes; NULL means open under the intended contract. |
| attributed_amount_usd | REAL | No | Purchase amount allocated to this episode; not a separate payment. |
| attribution_status | TEXT | No | Entitlement state at entitlement_snapshot_at: granted, refunded or expired_delisting. |
| refunded_at | TEXT | Yes | UTC time a full episode refund ended this entitlement, when applicable. |
| delisted_at | TEXT | Yes | UTC time delisting ended this entitlement, when applicable. |

**Entitlement start:** A PPV entitlement starts exactly at the success effective time of its purchase: the effective_at of the purchase's succeeded payment_status_history event. It does not start at purchase creation (transaction_at), while the purchase is pending, or at the time the success was recorded (recorded_at); recorded_at applies only to knowledge-time questions. A purchase that has no succeeded event has no entitlement. The episode tier and availability rules for a new purchase are evaluated at this same instant.

**One open entitlement per user and episode:** A user holds at most one open PPV entitlement for an episode at any instant. A new PPV purchase cannot start an entitlement while another entitlement of the same user for the same episode is open at that start (start inclusive, end exclusive, where a full refund or delisting supplies the end). A new purchase starting exactly when the earlier entitlement ends is valid, including a repurchase after relisting. As a result, an as-of PPV entitlement join returns at most one row per view.

**Status and end timestamps:** attribution_status and the end columns must agree. granted has no entitlement_end_at, refunded_at or delisted_at. refunded has refunded_at, entitlement_end_at equal to refunded_at, and no delisted_at. expired_delisting has delisted_at, entitlement_end_at equal to delisted_at, and no refunded_at. An entitlement has at most one end reason, and an end is later than its start. A full refund and delisting are the only supported end reasons; other revocation, such as a chargeback or fraud reversal, is not modeled. attribution_status is the state at dataset_metadata.entitlement_snapshot_at; for access at any other instant use the timestamps, not the status. No entitlement start, entitlement_end_at, refunded_at or delisted_at is later than that instant: a refund or delisting is recorded only once it has taken effect.

**Refund policy:** Succeeded partial PPV refunds reduce revenue but do not end the episode entitlement. For each original purchase and episode, add the positive allocations of succeeded refunds in exact cents. When cumulative allocated refunds reach the full episode purchase allocation, the entitlement ends at the success effective time of the refund that completes the total, provided it has not already ended. Refunds cannot exceed the episode allocation. If delisting ended access earlier, a later refund does not rewrite the earlier end. A refund request or failed refund is not a successful refund. Refunds and their allocations are separate records, not negative purchase amounts. Subscription-refund access is a separate policy.

**Bundle limitation:** Episode allocations are required to identify which episode is fully refunded. The fixture has only single-episode purchases; its bundle allocation method is not specified. The policy is tested with a small isolated bundle case, not demonstrated in the main fixture. A bundle that includes an episode the user already holds is not supported: it violates the one-open-entitlement rule, and no bundle policy for it is defined.

**Use and checks:** At a view instant, match the user through the purchase, the composite episode key, a succeeded purchase as of the view, and the entitlement's start-inclusive/end-exclusive interval. Check availability separately. Relisting does not revive an entitlement ended by delisting. The checker reconciles succeeded PPV allocations to purchase amounts in exact USD cents, checks that each row belongs to a PPV purchase, that each entitlement starts at its purchase's success effective time that no purchase repeats an episode and that no user holds overlapping entitlements for an episode, that status, end timestamps and UTC formats agree, that no timestamp is later than entitlement_snapshot_at, validates selected entitlement/view and delisting/notice scenarios, and checks cumulative succeeded episode refund allocations, early refund revocation, over-refund and required full-refund end timing. It does not validate every bundle allocation policy. Current SQLite REAL storage and USD conversion limitations are described in the transactions entry. The fixture has 251 single-episode purchase rows, including 44 full PPV refunds and no partial PPV refunds; partial and cumulative cases are isolated regression tests. Every fixture purchase succeeds at its creation time, so entitlement start equals transaction_at in the fixture; delayed success (pending before success) is an isolated regression test.

## 13. refund_content_attribution

**Purpose:** Allocate a PPV refund transaction to the episode or episodes it concerns. An allocation is an intended amount until the refund succeeds; it is not another payment. **Grain:** One refund transaction × episode. **Primary key:** refund_allocation_id. **Unique:** (refund_txn_id, content_id, episode_number). Separate refunds may refer to the same episode, and one refund may cover multiple distinct episodes. The generator enforces uniqueness; the checker also detects duplicates in older fixtures.

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| refund_allocation_id | TEXT primary key | Required by checker | Allocation identifier. |
| refund_txn_id | TEXT | No | PPV refund transaction; its related_txn_id points to the original purchase. |
| content_id | TEXT | No | Title ID; use with episode_number. |
| episode_number | INTEGER | No | Episode number within the title. |
| allocated_refund_usd | REAL | No | Positive amount allocated to this episode, intended before success and completed upon success. |
| created_at | TEXT | No | UTC allocation-record creation time. |
| updated_at | TEXT | No | UTC time of the latest allocation-record update; equals created_at when unchanged. |

**Lifecycle:** Record allocation rows for PPV refund transactions in all statuses: pending, succeeded, failed or voided. Their amounts sum to the refund transaction amount in each status, including failed and voided attempts. Only succeeded refund allocations reduce revenue or count toward full-refund entitlement termination, effective at the succeeded payment-status event's effective_at. Allocation created_at and updated_at give creation and latest update times; they do not retain prior episode or amount values and cannot fully reconstruct what allocation was known at an earlier instant. The synthetic fixture sets both equal to the refund transaction time and models no allocation corrections; these are synthetic assumptions, not observed production audit events. This policy concerns a refund transaction, not a refund request event that has not produced a transaction.

**Joins and timing:** refund_txn_id → transactions → related_txn_id → original PPV purchase; match the original purchase and composite episode key to transaction_content_attribution. Join the refund to payment_status_history for status and success time. One refund can have many status events and episode allocations; independently summarise each child to the required grain before combining. Use success effective time for revenue periods and use the relevant event-time cutoff for as-of analysis; current status alone is not historical evidence. Filter by recorded_at as well for knowledge-time questions, subject to the history/versioning limitations documented in payment_status_history.

**Money and entitlement:** Store refund amounts as positive values and subtract succeeded allocations from episode purchase allocations. Convert valid USD values to exact cents before aggregation. Pending, failed and voided allocations are not completed refunds and do not count toward the succeeded-refund cap or entitlement termination. A partial refund retains access; cumulative succeeded allocations reaching the full episode purchase allocation terminate access at the success time of the final refund, if it was still open.

**Example: succeeded refund allocation in cents as of a UTC instant**

```sql
SELECT COALESCE(SUM(usd_cents(a.allocated_refund_usd)),0)
FROM refund_content_attribution a
JOIN transactions r ON r.txn_id=a.refund_txn_id
JOIN payment_status_history p ON p.txn_id=r.txn_id AND p.status='succeeded'
WHERE r.type='refund' AND r.transaction_subtype='ppv_refund'
  AND a.content_id=:content_id AND a.episode_number=:episode_number
  AND p.effective_at<=:as_of;
```

This is a cumulative amount, not a complete net-revenue metric. It assumes valid two-decimal USD amounts, unique success events and the fixture's no-post-success-void rule; it excludes knowledge-time filtering and does not prove allocations were available at a past cutoff. usd_cents is a Python function registered on the fixture checker's connection, not a built-in SQLite function or a database object; another client must provide an equivalent validated exact-cent conversion. The fixture checker separately rejects invalid amounts and duplicate success events.

**Checks and coverage:** The checker validates required values, UTC audit timestamps, updated_at not before created_at, allocation creation not before its refund transaction, foreign keys, unique refund–episode combinations, positive exact-cent amounts, the original purchased episode, allocations adding to the transaction amount for every refund status, and cumulative succeeded refund caps and selected access timing. Lifecycle, delayed-success and failed/voided cases are isolated regression tests. The main fixture contains 44 single-episode succeeded full PPV refunds and no pending, failed, voided or partial PPV refunds. Bundle allocation methodology is not specified. Counts and sums of all allocation rows, including the episode fanout reconciliation check, are structural reconciliation rather than recognised revenue.

## 14. payment_status_history

**Purpose:** Record payment-provider status events, including changes over time. **Grain:** One event for one transaction. **Primary key:** payment_status_event_id. **Relationship:** One transaction has one or more history events; each event belongs to one transaction.

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| payment_status_event_id | TEXT primary key | Required by checker | Unique identifier for this history event. |
| txn_id | TEXT | No | Foreign key to transactions.txn_id. |
| status | TEXT | No | pending, succeeded, failed or voided. |
| effective_at | TEXT | No | UTC time when the status became effective. |
| recorded_at | TEXT | No | UTC time when the event was recorded. |
| provider_event_id | TEXT | No; unique | Provider event identifier, used as an idempotency key. |

**Interpretation:** A pending transaction may later succeed, fail or be voided. A void is a cancellation before success. An event effective after a success cannot be voided; money returned after success is a separate positive-amount refund transaction linked to the original charge. This rule applies to status records for charges and refunds. The checker enforces the no-post-success-void rule, not a complete provider-specific transition state machine.

**Time and joins:** For status at an event instant, select the latest effective event at or before that instant, then join the resulting one row per transaction to the parent. For a historical knowledge-time question, also restrict recorded_at to the chosen knowledge cutoff; this is not a complete audit/versioning contract and late corrections or source deletions may require additional history. Before the first known status, the status is unknown. No separate transaction snapshot timestamp is stored; the current transaction status is checked against the latest stored effective event. A direct join to all history events repeats transaction amounts; never sum them without first reducing the history to the required transaction grain. Monthly payment-event amounts are counted once at success effective time, with refunds subtracted separately, subject to the monetary and metric limitations in the transactions entry.

### Status at event time and knowledge time

For ordinary historical analysis, use the latest status effective by the event instant among the events available now. For a question about what was known at a past instant, also exclude events recorded after the knowledge cutoff. If no eligible event exists, the status is unknown. Explain which interpretation was used when the distinction affects a conclusion.

Example: pending at 10:00, succeeded effective at 10:05 and recorded at 10:07 (all UTC). For event time 10:06, the status using current knowledge is succeeded. With a knowledge cutoff of 10:06 it is pending; with a cutoff of 10:07 it is succeeded.

```sql
SELECT p.status
FROM transactions t
LEFT JOIN payment_status_history p
  ON p.payment_status_event_id = (
    SELECT h.payment_status_event_id
    FROM payment_status_history h
    WHERE h.txn_id = t.txn_id
      AND h.effective_at <= :event_at
      AND (:known_at IS NULL OR h.recorded_at <= :known_at)
    ORDER BY h.effective_at DESC, h.recorded_at DESC, h.payment_status_event_id DESC
    LIMIT 1
  )
WHERE t.txn_id = :txn_id;
```

Set :known_at to NULL to use events available now, or to a UTC timestamp for a past knowledge cutoff. A NULL status for an existing transaction means no eligible event was found; a nonexistent transaction returns no row. The isolated regression test covers the example and both unknown cases. This reconstruction assumes the relevant original events remain available: recorded_at alone cannot reconstruct overwritten or deleted records. It is not a complete historical versioning or correction policy.

**Checks:** The checker validates required identifiers, allowed status values, UTC timestamp formats, status effective time not before transaction creation, unique provider event IDs, no duplicate effective timestamps or multiple successes per transaction, current-status agreement with the latest event, and no void effective after success. Existing foreign-key checks cover transaction references. These checks do not validate every permissible transition, establish a universal provider policy, or prove all late events were captured. They do not require recorded_at to follow effective_at.

**Fixture coverage:** The current fixture has one status row per transaction, with succeeded and failed statuses; delayed success, late recording and pre-success void are exercised in isolated tests, not represented as multi-step histories in the fixture.

## 15. user_events

**Purpose:** Behavioral and business-event timeline. **Grain/key:** One event per event_id. **Time:** event_at is occurrence time; ingested_at is arrival time; event_timezone? is contextual.

**Columns:** event_id — ID; user_id? — signed-in actor if known; anonymous_id? — identity when applicable; event_at — occurrence; event_name — event type, including session_engagement and playback_heartbeat for synthetic timing evidence; session_id?/view_id?/txn_id?/subscription_period_id? — relevant referenced record; content_id?/episode_number? — relevant content; event_properties_json? — event-specific context including the synthetic marker for these observations; event_timezone? — reported timezone; country_at_event? — observed country; ingested_at — arrival; triggering_paywall_event_id? — observed paywall event that led into this checkout, if captured.

**Joins:** Optional FKs to user, identity, session, view, transaction, period and series; episode composite FK where populated. **Use:** paywall-to-checkout sequence. **Limitations/checks:** Different event types populate different fields. Synthetic engagement and heartbeat observations are not additional views, watch-time increments, payments or proof of deliberate interaction. Select one owner for a business moment to avoid duplicating payment/view facts. Checker covers selected session timing and heartbeat bounds, product labels, funnel and refund order; propose broader event-specific schema checks.

**PPV paywall and checkout keys:** For paywall_viewed and checkout_started where event_properties_json identifies product ppv, content_id must be non-empty and episode_number must be a positive integer; the composite key must identify an existing episode. Subscription paywalls and checkouts do not require an episode. The checker validates the required PPV key and the fixture foreign-key check validates populated episode references. The current fixture already has these keys for every PPV paywall and checkout; missing-key cases are isolated tests.

A checkout can be referenced by multiple payment attempts through transactions.checkout_event_id. This captured relationship is independent of the checkout event's optional txn_id, which can identify at most one transaction and is not a complete retry list. A NULL checkout_event_id may indicate an off-session payment or an uncaptured link. To satisfy both nullable foreign keys, ingestion can insert the checkout event with txn_id NULL, then insert transactions referencing it; an event-level txn_id can be populated afterward if available.

A checkout's optional triggering_paywall_event_id references the specific triggering paywall_viewed event. NULL means direct checkout or that the link was not captured; it does not distinguish the two. A paywall may link to many checkout attempts, while each checkout links to at most one paywall. When populated, the referenced paywall must be earlier, in the same non-null session, with the same labelled product and, for PPV, the same title and episode. Other event types leave the field NULL. The link represents observed navigation, not proof that exposure caused a purchase. Without a captured link, matching by episode, session or nearest time does not prove which exposure led to checkout. Other existing funnel checks assume valid JSON and can error on malformed payloads; malformed-event handling is not covered by this key check. An initial subscription may be completed without an immediate view. If a view occurs later, subscription entitlement is checked at its playback start, including in a different session.

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

**Purpose:** Dataset-wide metadata. **Grain/key:** One value per metadata_key. **Columns:** metadata_key TEXT primary key NOT NULL; metadata_value TEXT NOT NULL. users_snapshot_at, content_catalog_snapshot_at and entitlement_snapshot_at are separate UTC as-of instants for the respective snapshots; entitlement_snapshot_at is the as-of instant for transaction_content_attribution.attribution_status. The checker requires each to be present exactly once in valid UTC format. session_activity_coverage=complete_synthetic_v1 declares this fixture's synthetic session evidence; playback_segment_coverage=complete_synthetic_v1 declares complete watched-range evidence for the fixture. The checker requires these values; it does not validate unrelated metadata keys. **Use:** determine snapshot timing and applicable coverage checks. **Limitations:** Later datasets with independent refresh times or incomplete telemetry need different handling; synthetic coverage flags are not proof of completeness in real data.

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

## 20. playback_segments

**Purpose:** Observed continuous watched position ranges within an attempt. **Grain:** One forward-consumed range in one view; a seek or rewind starts another segment. **Key:** segment_id; (view_id, segment_index) is unique. **Time:** segment_started_at and segment_ended_at are UTC event times.

| Column | SQLite type | Nullable? | Meaning |
|---|---|---|---|
| segment_id | TEXT primary key | No | Segment identifier. |
| view_id | TEXT | No | Parent playback attempt. |
| segment_index | INTEGER | No | Positive chronological sequence within the view. |
| segment_started_at | TEXT | No | Wall-clock segment start. |
| segment_ended_at | TEXT | No | Wall-clock segment end. |
| position_start_sec | INTEGER | No | Inclusive episode position where this continuous range starts. |
| position_end_sec | INTEGER | No | Exclusive episode position where the range ends. |
| watch_duration_sec | INTEGER | No | Time watched within the segment; not necessarily the position difference at every playback speed. |

**Joins:** view_id → content_views, one view to many segments. Use the parent view for user, session and episode. Sum segment watch time only once per segment, and merge overlapping position intervals for unique coverage. **Checks:** parent FK, required values, ordered non-overlapping wall-clock intervals, view/time/position bounds, view watch-time reconciliation, first/final position consistency and per-attempt unique-completion reconciliation. **Limitations:** The fixture declares full synthetic segment coverage and uses second-level positions; real sources can lose segments, and current data does not model historical episode-length changes. Seek actions themselves are inferred from discontinuous positions rather than stored as separately timed events.

The following SQLite query merges overlapping position ranges for one attempt without relying on checker-specific functions:

```sql
WITH ordered AS (
  SELECT view_id, segment_id, position_start_sec AS start_pos, position_end_sec AS end_pos,
         MAX(position_end_sec) OVER (
           PARTITION BY view_id ORDER BY position_start_sec, position_end_sec, segment_id
           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
         ) AS previous_max_end
  FROM playback_segments
), grouped AS (
  SELECT *, SUM(CASE WHEN previous_max_end IS NULL OR start_pos > previous_max_end
                     THEN 1 ELSE 0 END) OVER (
           PARTITION BY view_id ORDER BY start_pos, end_pos, segment_id
         ) AS island
  FROM ordered
), ranges AS (
  SELECT view_id, island, MIN(start_pos) AS start_pos, MAX(end_pos) AS end_pos
  FROM grouped GROUP BY view_id, island
)
SELECT view_id, SUM(end_pos - start_pos) AS unique_content_seconds
FROM ranges GROUP BY view_id;
```

This returns views with segment records only. Confirm declared coverage before interpreting missing views or computing completion. For user/episode coverage across attempts, partition and group by the chosen user and episode instead, while accounting for compatible episode versions and the analysis window.
