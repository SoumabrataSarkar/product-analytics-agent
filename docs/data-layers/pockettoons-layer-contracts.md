# PocketToons layer contracts

**Scope:** Contracts for the Bronze, Silver and Gold layers of the PocketToons fixture, following the [layer build workflow](layer-build-workflow.md). Business rules come from the [Metric Registry](../metrics/metric-registry.md) and the [data catalog](../examples/pockettoons-data-catalog.md); a contract implements them and must not contradict them.

**Status:** Bronze, `layer_build_log`, `silver_resolved_sessions`, `silver_payment_attempts`, `silver_subscription_access`, `silver_user_profile`, `silver_user_day_activity`, `silver_user_day_title_watch`, `silver_user_episodes`, `silver_paywall_funnel`, `silver_marketing_daily` and `silver_quality_exceptions` are approved and implemented by `examples/pockettoons/build_layers.py`. Silver is complete; Gold is not yet defined.

**Build target:** the builder adds its objects to an existing generated database and never modifies source tables. It is verified on a copy before being applied to a reviewed database.

## Bronze

| Part | Contract |
|---|---|
| Purpose | Expose every source record, unchanged and with its quality problems, for audit and reconciliation |
| Form | One view `bronze_<table>` per source table, `SELECT *` over the unchanged table. Source tables keep their names and columns. |
| Snapshot behaviour | A view shows the source's current content, not a frozen copy. The build log stores a row count and content hash for every source table, so a later change is detectable by comparing a fresh fingerprint. |
| Reconciliation | Each view's row count equals its source table's |

| Role | Tables | How to use |
|---|---|---|
| Raw record | `sessions`, `identity_links`, `content_views`, `playback_segments`, `user_events`, `transactions`, `payment_status_history`, `marketing_spend` | Facts at their own grain; aggregate each child table independently to avoid fanout |
| Raw provider feed | `raw_payment_source` | Audit only; contains deliberate unit and format errors and is never a revenue source |
| Effective-dated history | `subscription_history`, `content_availability_history`, `content_tier_history` | Query as of an instant with half-open intervals |
| Current-state snapshot | `users`, `anonymous_identities`, `content_catalog`, `content_episodes` | Valid at the declared snapshot instant; history comes from the histories |
| Derived business bridge | `transaction_content_attribution`, `refund_content_attribution` | Entitlement and refund allocation; join through them, never repeat transaction amounts per row |
| Review evidence | `payment_quality_review` | Explains corrections already in curated amounts; never an additional fact |
| Metadata | `dataset_metadata` | Snapshot instants and coverage labels |

## layer_build_log

| Part | Contract |
|---|---|
| Purpose | Evidence for every build attempt: what was built, from which source, with which definitions, and whether it reconciled |
| Grain | One row per build attempt, successful or failed |
| Key | `build_id` |
| Columns | `build_id`; `started_at` and `finished_at` (UTC); `status` (`succeeded` or `failed`); `builder_sha256` (hash of the builder file); `registry_sha256` (hash of the Metric Registry file); `definitions` (registry definitions implemented, with versions); `source_fingerprint` (JSON: row count and content hash per source table read); `row_counts` (JSON per built object); `reconciliation` (JSON: each check and its result); `error` (failure message, NULL on success) |
| Rules | A failed attempt is recorded with its error and leaves the previous successful layers unchanged |
| Lineage | The builder; this table is never dropped by a rebuild |
| Supports | Freshness questions ("which build is this?"), audit of definitions and source used, detection of source changes after a build |

## silver_resolved_sessions

| Part | Contract |
|---|---|
| Purpose | Every session with its person resolved by the approved identity rule, so activity metrics never repeat identity logic |
| Grain | One row per source session; no session is excluded |
| Key and indexes | `session_id` primary key; indexes on (`resolved_user_id`, `session_started_at`) and on `session_started_at` |
| Columns | `session_id`; `raw_user_id` (source `sessions.user_id`, unaltered); `resolved_user_id`; `resolution_method`; `anonymous_id`; `platform`; `country_at_event`; `app_version`; `session_started_at`; `last_activity_at`; `session_ended_at` (NULL for open sessions); `start_date` and `last_activity_date` (UTC dates); `active_span_sec` (whole seconds from start to last activity); `link_count` (identity links in the session); `linked_user_count` (distinct linked users); `link_user_mismatch` (1 when the session's user differs from a linked user); `build_id` |
| Resolution | `session_user`: `sessions.user_id` is present and is the resolved user. `same_session_link`: no session user and the session's links name exactly one user. `unresolved_no_link`: no session user and no link. `unresolved_ambiguous`: no session user and links name more than one user. Unresolved sessions have NULL `resolved_user_id`. |
| Rules | As in the approved `mau` definition: resolution uses links in the same session only; activity is never attributed across sessions by `anonymous_id` or device; ambiguity stays unresolved |
| Time | UTC; the active span runs from `session_started_at` to `last_activity_at`, both inclusive; open sessions are not extended |
| Lineage | `sessions` one-to-one; `identity_links` zero or more per session; `build_id` → `layer_build_log` |
| Exceptions | Nothing is excluded. Unresolved sessions are retained and labelled by method. A session whose user differs from one of its linked users is flagged with `link_user_mismatch` as suspicious but usable; the session's own user remains the resolved user. |
| Supports | `dau`, `wau`, `mau`; active-days distribution; sessions per active user; session duration; platform, country and subscriber-status slices of activity; the unidentified-session share; inputs to growth accounting and retention |
| Does not support | Viewing, engagement, content, payments and subscriptions; use the corresponding Silver tables or the source |
| Reconciliation | Row count equals source sessions, and the key sets are equal. The four resolution methods add up to the total. An independent recount of methods and mismatches from `sessions` and `identity_links` matches. Monthly MAU from this table equals the registry `mau_monthly` computed on the source. |
| Tests | Isolated cases for each resolution method, a mismatched link, no cross-session attribution, schema mismatch, a failed build leaving the previous layer in place, and rebuilds touching only owned objects |

## silver_payment_attempts

| Part | Contract |
|---|---|
| Purpose | Every payment attempt with its outcome, success time, revenue type and validated amount, so revenue metrics never repeat status, refund or money logic |
| Grain | One row per source transaction: charges, refunds and failed attempts; none is excluded |
| Key and indexes | `txn_id` primary key; indexes on `succeeded_at` and on (`user_id`, `succeeded_at`) |
| Columns | `txn_id`; `user_id`; `type`; `transaction_subtype`; `revenue_type` (the charge's type, or the refunded charge's type, or `unattributed`); `related_txn_id`; `subscription_id`; `session_id`; `checkout_event_id`; `payment_method`; `country_at_event`; `created_at` (`transaction_at`); `outcome` (latest `succeeded` or `failed` status event, else `no_outcome`); `success_event_count`; `succeeded_at` and `succeeded_recorded_at` (the single success event, else NULL); `amount_usd_source` (source value, unaltered); `amount_cents` (NULL when invalid); `list_price_cents`; `amount_valid`; `revenue_cents` (+ for a valid charge with one success, − for such a refund, 0 otherwise); `exception_status`; `exception_reason`; `build_id` |
| Rules | Revenue group v1.1: count at the single success event's effective time, never by current status; refunds are positive and subtracted; a refund's type comes from its successful original charge |
| Money | An amount is valid when it is numeric, positive and exact to the cent. Invalid amounts are never rounded into trusted values. |
| Time | UTC; `created_at` for payment-failure months, `succeeded_at` for revenue months |
| Lineage | `transactions` one-to-one; `payment_status_history` for outcome and success time; the refunded charge through `related_txn_id` |
| Exceptions | `excluded`: `invalid_amount` or `multiple_success_events`; contributes no revenue. `suspicious_usable`: `refund_without_successful_original`; reduces net revenue under `unattributed`. `ok` otherwise. |
| Supports | Net, subscription and PPV revenue; ARPU and ARPPU; paying users; refund rate; payment failure rate; first paid charge for CAC and conversion |
| Does not support | Raw provider values (`bronze_raw_payment_source`); entitlement and per-episode PPV revenue (attribution bridges) |
| Reconciliation | Row count equals source transactions; outcome counts add up to the total; an independent Python `Decimal` recount of monthly charge and refund cents matches; monthly net revenue from this table equals the registry `net_revenue_monthly` on the source |
| Tests | Valid and invalid amounts (non-exact cents, non-numeric), success later than creation, failure before a retry, double success, refund of a failed or missing charge, refund type assignment |

## silver_subscription_access

| Part | Contract |
|---|---|
| Purpose | Whether a user was a subscriber at any instant, and where each continuous run of subscriber access starts and ends |
| Grain | One row per source subscription period, all statuses; `expired` and `refunded` periods are retained with `grants_access` 0 |
| Key and indexes | `subscription_period_id` primary key; index on (`user_id`, `effective_start_at`) |
| Columns | `subscription_period_id`; `subscription_id`; `user_id`; `status`; `grants_access` (1 for `active` or `cancel_at_period_end`); `effective_start_at`; `effective_end_at` (NULL is open); `cancelled_at`; `source_txn_id`; `plan_code`; `price_cents` (validated list price of the source charge; NULL when invalid or no access); `starts_access_spell`; `ends_access_spell`; `access_spell_number` (1st, 2nd … run of the user's access; NULL without access); `exception_status`; `exception_reason`; `build_id` |
| Rules | Subscriber at instant t: an access period with `effective_start_at` ≤ t and `effective_end_at` NULL or > t (lifecycle group). Access periods that overlap or touch, where one ends exactly when the next begins, form one continuous run, so renewals and cancellation notices are not losses. |
| Access loss | `ends_access_spell` is 1 only when a run ends at or before `dataset_metadata.users_snapshot_at`. An end after the snapshot is a scheduled end whose renewal is not yet known and is not a loss. |
| Time | UTC; half-open periods |
| Lineage | `subscription_history` one-to-one; source charge and list price from `transactions`; charge success from `payment_status_history`; snapshot instant from `dataset_metadata` |
| Exceptions | `suspicious_usable` with reasons `overlapping_access`, `source_charge_not_successful` or `invalid_list_price` (several are listed comma-separated). An invalid price is excluded from MRR; the period still grants access. |
| Supports | Subscribers at any instant, net adds, churn, MRR, cancellation-request rate, 60-day resubscription, subscriber-status slices of activity, status history |
| Does not support | Payments (`silver_payment_attempts`) |
| Reconciliation | Row count equals source periods; access and no-access counts add to the total; an independent Python merge of each user's access intervals reproduces run starts and known losses; subscribers at each month start equal the registry churn denominator on the source; month-end subscribers and MRR equal the registry `mrr_monthly` on the source |
| Tests | Renewal continuity, cancellation notice, lapse and return, scheduled end after the snapshot, expired and refunded periods, overlap, unsuccessful source charge, invalid price |

## silver_user_profile

| Part | Contract |
|---|---|
| Purpose | One place for who each user is and when they first reached each lifecycle milestone, for cohorts and acquisition slices |
| Grain | One row per `users` row, including users with no activity |
| Key and indexes | `user_id` primary key; indexes on `signup_at` and (`acquisition_source`, `signup_at`) |
| Columns | `user_id`; `signup_at`; `signup_date`; `signup_month`; `acquisition_source` (NULL becomes `unknown`; an unrecognised value is kept as given); `country_origin`; `country_current_snapshot`; `subscription_status_snapshot`; `first_session_at`; `first_engaged_date`; `first_paid_at`; `first_subscription_at`; `first_ppv_at`; `subscription_spells`; `is_returning_subscriber` (1 when spells > 1); `exception_status`; `exception_reason`; `build_id` |
| Rules | Milestones are derived from other Silver tables so each rule lives in one place: first session from `silver_resolved_sessions` (resolved users only); first paid, subscription and PPV charge from `silver_payment_attempts` rows with `revenue_cents` > 0, so a later refund does not erase the milestone; spells from `silver_subscription_access`. First engaged date is the first UTC day with at least 60 watched seconds, split across days by wall-clock share as in `activation_7d`. |
| Snapshot attributes | `_snapshot` columns are the values as of `dataset_metadata.users_snapshot_at`, not history. Use them for current-state slices only; use `silver_subscription_access` for status at a past instant. |
| Time | UTC |
| Lineage | `users` one-to-one; `content_views` and `playback_segments` for engagement; the three Silver tables above |
| Exceptions | `suspicious_usable` with reasons `invalid_signup_time`, `activity_before_signup` or `unrecognised_acquisition_source` (comma-separated when several apply) |
| Supports | Signups by month and source, 7-day activation, 30-day conversion, time to first payment, returning subscribers, acquisition and country slices |
| Does not support | Activity counts or revenue amounts (use the activity and payment tables); historical country or status |
| Reconciliation | Rows and keys equal `users`; an independent Python recount reproduces first valid paid charge and first identified session; monthly signups by source equal the registry `new_signups_monthly`, activation equals `activation_7d` and conversion equals `conversion_30d` on the source |
| Tests | No activity, PPV before subscription, refunded first charge, excluded charges, cross-midnight engagement, under-60-second watching, returning subscriber, snapshot country, unknown and unrecognised source, invalid signup time, activity before signup |

## silver_user_day_activity

| Part | Contract |
|---|---|
| Purpose | Daily, weekly and monthly active and engaged users, stickiness, active days and retention from one table instead of raw sessions and segments |
| Grain | One row per resolved user and UTC day with any session, watch time or view start; days without activity have no row and read as inactive |
| Key and indexes | (`user_id`, `activity_date`) primary key; index on (`activity_date`, `user_id`) |
| Columns | `user_id`; `activity_date`; `activity_month`; `sessions_touching` (sessions whose span touches the day); `sessions_started`; `started_session_span_sec` (span of sessions started that day); `watch_seconds` (REAL); `views_started`; `free_quota_slots_used` (highest `free_quota_sequence` that UTC day, 0–8); `subscriber_at_day_start`; `exception_status`; `exception_reason`; `build_id` |
| Rules | Active on a day: `sessions_touching` > 0. A session touches every day from its start to its `last_activity_at`, both inclusive, so a session crossing midnight counts on both days and one whose last activity is exactly midnight touches the later day (activity family rule). Watch seconds are split across days by wall-clock share; a zero-length segment counts on its day. Engagement is not stored: engaged in a period is `SUM(watch_seconds)` ≥ 60 over the period's days, so the threshold can change without a rebuild. `subscriber_at_day_start` uses `silver_subscription_access` at 00:00:00Z. The free quota is per user and UTC day across all titles: a quota hit is `free_quota_slots_used` = 8. |
| Aggregation | Distinct-user counts over several days are recounted from rows, never summed from daily counts. Days align with week and month boundaries, so watch seconds sum exactly into any day-aligned period. |
| Time | UTC days; all days are kept, not only the coverage window |
| Lineage | `silver_resolved_sessions` (resolved users only); `playback_segments` and `content_views`; `silver_subscription_access`; `users` for exceptions |
| Exceptions | `suspicious_usable` with reasons `user_not_in_users`, `activity_before_signup` or `free_quota_sequence_gap` (the highest slot differs from the number of quota-consuming views) |
| Supports | DAU, WAU, MAU, DEU, WEU, MEU, stickiness, engagement rate, active-days distribution, day-N and monthly retention, sessions and views per active user, subscriber versus non-subscriber activity |
| Does not support | Platform or country slices (a user can have several in a day: use `silver_resolved_sessions`); title-level watching (`silver_user_day_title_watch`) |
| Reconciliation | An independent Python recount reproduces every session-active user-day and daily DAU; an exact-fraction Python recount reproduces daily engaged users (differences allowed only within 10⁻⁶ s of the threshold); total watch seconds equal the segments; started sessions and views equal the source; WAU, WEU, MAU and MEU equal the registry the active-days distribution equals `active_days_distribution_monthly` and free-viewer days and quota hits equal `free_quota_hit_monthly` on the source. Daily registry DAU and DEU are not re-run in the build because their range joins take about three minutes. |
| Tests | Midnight-crossing session, last activity exactly at midnight, watch-only day, segment split across midnight, view start, subscriber at day start, ambiguous session excluded, activity before signup, user not in `users`, quota hit, subscription views using no slot, quota sequence gap |

## silver_user_day_title_watch

| Part | Contract |
|---|---|
| Purpose | Watch time, reach and views by title and entitlement: title reach, views per viewer, free versus subscription versus PPV watching |
| Grain | One row per resolved user, UTC day, `content_id` and `view_type` with a view start or watch time |
| Key and indexes | (`user_id`, `activity_date`, `content_id`, `view_type`) primary key; index on (`activity_date`, `content_id`) |
| Columns | `user_id`; `activity_date`; `activity_month`; `content_id`; `view_type` (`free`, `sub` or `ppv`: the entitlement at view start); `views_started`; `episodes_started` (distinct episodes among views started); `first_views_of_episode`; `watch_seconds` (REAL); `exception_status`; `exception_reason`; `build_id` |
| Rules | Views, episodes and first views count on the UTC day the view starts (registry rule). Watch seconds are split across days by wall-clock share, as in `silver_user_day_activity`, so a view that crosses midnight can give a row with watch time but no view start. |
| Aggregation | Viewers of a title over several days are recounted from rows; `episodes_started` is distinct within a row and is not summed across days as distinct episodes. |
| Time | UTC days; all days kept |
| Lineage | `content_views` and `playback_segments`; `users` for exceptions |
| Exceptions | `suspicious_usable` with reasons `user_not_in_users` or `unrecognised_view_type` |
| Supports | Title reach, watch time by title and by entitlement, views per viewer, first views of an episode, PPV and subscription watching |
| Does not support | Episode completion and series continuation (`silver_user_episodes`); free-quota use (`silver_user_day_activity`) |
| Reconciliation | Per user-day, watch seconds and views equal `silver_user_day_activity`; views equal the source; monthly title reach equals `title_reach_monthly`, views and viewers equal `views_per_viewer_monthly` and watch seconds equal `watch_time_monthly` on the source |
| Tests | Two titles on one day, one title under two view types, rewatch that is not a first view, split across midnight, watch-only day for a title, eight-slot free day |

## silver_user_episodes

| Part | Contract |
|---|---|
| Purpose | Episode completion and series continuation without re-merging playback positions for every question |
| Grain | One row per user, `content_id` and `episode_number` the user has started |
| Key and indexes | (`user_id`, `content_id`, `episode_number`) primary key; index on `first_start_at` |
| Columns | `user_id`; `content_id`; `episode_number`; `first_start_at`; `first_start_month`; `window_end_at` (first start + 7 days); `window_complete` (1 when `window_end_at` ≤ the coverage end); `first_view_type` (entitlement of the first view); `views_in_window`; `covered_sec`; `episode_duration_sec` (NULL when the episode is not in the catalog); `has_next_episode`; `started_next_episode_in_window`; `exception_status`; `exception_reason`; `build_id` |
| Rules | `covered_sec` is the union of playback-position intervals from views started inside the window, so rewinds and rewatches are not double-counted. Completion is not stored: completed means `covered_sec` ≥ 0.9 × `episode_duration_sec`, so the threshold can change without a rebuild. Continuation is stored as a fact: the user started episode n + 1 of the same title within the window, whatever the completion. |
| Registry use | Completion rate: rows with `window_complete` = 1 and a known duration, by `first_start_month`. Continuation rate: completed rows with `has_next_episode` = 1 and `window_complete` = 1. |
| Time | UTC; the window is half-open `[first_start_at, window_end_at)` |
| Lineage | `content_views`, `playback_segments`, `content_episodes`; `users` for exceptions |
| Exceptions | `suspicious_usable` with reasons `user_not_in_users`, `episode_not_in_catalog` or `coverage_exceeds_duration` |
| Supports | Episode completion rate, series continuation rate, completion by entitlement, views per user-episode, binge and drop-off analysis by episode number |
| Does not support | Watch time (`silver_user_day_title_watch`); completion for a later rewatch window (only the first 7 days are measured) |
| Reconciliation | Rows equal distinct user-episodes in `content_views`; an independent Python interval merge reproduces `covered_sec` for every row; monthly completion equals `episode_completion_monthly` and continuation equals `series_continuation_monthly` on the source |
| Tests | Completed episode with the next started, rewind overlap, view after the window, no segments, last episode, window past the coverage end, episode not in the catalog, coverage longer than the episode |

## silver_paywall_funnel

| Part | Contract |
|---|---|
| Purpose | Paywall → checkout → purchase conversion and paywall exposure |
| Grain | One row per `paywall_viewed` event |
| Key and indexes | `paywall_event_id` primary key; indexes on `event_at` and (`user_id`, `event_at`) |
| Columns | `paywall_event_id`; `event_at`; `event_month`; `session_id`; `user_id` (the event's user, else the resolved session user); `product` (from `event_properties_json`); `content_id`; `episode_number`; `checkouts_started`; `first_checkout_event_id`; `first_checkout_at`; `purchase_txn_id`; `purchased_at`; `purchase_revenue_cents`; `exception_status`; `exception_reason`; `build_id` |
| Rules | A checkout belongs to the paywall named in its `triggering_paywall_event_id`. A paywall is purchased when any of its checkouts has a transaction with positive `revenue_cents` in `silver_payment_attempts` (a successful, valid, non-refund charge); the earliest such charge is stored. A purchase is credited only through that link: no time-window attribution. A later refund does not remove the purchase. |
| Time | UTC; month by `event_at` |
| Lineage | `user_events` (paywalls and checkouts); `transactions.checkout_event_id`; `silver_payment_attempts`; `silver_resolved_sessions` |
| Exceptions | `suspicious_usable` with reasons `unidentified_viewer`, `unrecognised_product` or `checkout_before_paywall` |
| Supports | Paywall-to-checkout, checkout-to-purchase and paywall-to-purchase rates by product, title or episode; paywall exposure rate; revenue from paywall purchases |
| Does not support | Purchases without a checkout link; marketing attribution (`silver_marketing_daily`) |
| Reconciliation | Rows equal source paywall views; an independent Python recount reproduces checkouts and the first valid purchase per paywall; monthly paywalls, checkouts and purchases by product equal `paywall_funnel_monthly` and exposed users equal `paywall_exposure_monthly` on the source |
| Tests | Paywall with a purchase and a failed retry, viewer from the resolved session, unidentified viewer, unrecognised product, checkout before the paywall, non-paywall events excluded |

## silver_marketing_daily

| Part | Contract |
|---|---|
| Purpose | CTR, cost per click, cost per signup and CAC by channel, and paid versus unpaid acquisition, from one table |
| Grain | One row per UTC `date` and `channel` that has a spend row, a signup or a first payment; channels are `marketing_spend.channel` and the users' acquisition sources, including `organic` and `unknown` |
| Key and indexes | (`date`, `channel`) primary key; index on (`channel`, `date`) |
| Columns | `date`; `month`; `channel`; `has_spend_row`; `spend_cents` (NULL without a spend row or when invalid); `impressions`; `clicks`; `signups` (users of that acquisition source who signed up that day); `new_paying_users` (users of that source whose first successful charge, from `silver_user_profile`, fell that day); `loaded_at`; `exception_status`; `exception_reason`; `build_id` |
| Rules | Spend is exact cents, never rounded: a value that is not a non-negative number with at most two decimals is stored as NULL and the row is `excluded`. Attribution is the user's `acquisition_source` only; there is no click-level link. New paying users count on their first-payment day, not their signup day, so a month's CAC is that month's spend ÷ that month's new payers from the channel, not a cohort CAC. |
| Time | UTC dates; all dates kept |
| Lineage | `marketing_spend` one-to-one for spend rows; `silver_user_profile` for signups and first payments |
| Exceptions | `excluded` with reason `invalid_spend`; `suspicious_usable` with reasons `negative_count` or `clicks_exceed_impressions` |
| Supports | Spend, impressions, clicks, CTR, CPC, cost per signup and CAC by channel and period; signups and new paying users by acquisition source, paid and unpaid |
| Does not support | Click- or campaign-level attribution; cohort CAC or payback by signup month (use `silver_user_profile` with spend) |
| Reconciliation | Spend rows equal the source; an independent Decimal recount reproduces total spend cents; signups and new payers add up to `silver_user_profile`; monthly clicks and impressions equal `marketing_ctr_monthly`; monthly spend, clicks, signups and new paying users equal `marketing_efficiency_monthly` on the source (where a channel-month has invalid spend, the registry rounds it and only spend is not compared) |
| Tests | Valid spend with a signup, invalid spend kept blank and excluded, clicks above impressions, unpaid channel without spend, first payment on another channel, NULL source as `unknown` |

## silver_quality_exceptions

| Part | Contract |
|---|---|
| Purpose | One place to answer "what is wrong with the data, and how much?" and to check before trusting a figure |
| Grain | One row per flagged Silver row and exception reason; a row with two reasons appears twice |
| Key and indexes | (`table_name`, `row_key`, `exception_reason`) primary key; index on (`exception_reason`, `table_name`) |
| Columns | `table_name`; `row_key` (the row's primary key as text, parts joined with `|`); `exception_status` (`excluded` or `suspicious_usable`); `exception_reason`; `build_id` |
| Rules | Built last, from every Silver table with exception columns. From `silver_resolved_sessions`, ambiguous identity links (`ambiguous_identity_link`) and links naming a different user (`link_user_mismatch`) are listed as `suspicious_usable`; anonymous sessions without a link are normal browsing and are not listed. A flagged row without a reason is listed as `unspecified`. |
| Lineage | All other Silver tables |
| Supports | Exception counts by table, reason and status; the rows behind any flagged figure, by joining `row_key` back to its table |
| Does not support | Faults no Silver rule detects |
| Reconciliation | Counts per table, status and reason equal each table's own flagged rows split by reason; every flagged row is listed exactly once per reason |
| Tests | Multiple reasons split into rows, composite keys, session-resolution problems, anonymous sessions excluded, `excluded` status carried |
| Current data | The PocketToons source currently has no flagged rows. A small, documented set of realistic faults is planned for the final rebuild. |
