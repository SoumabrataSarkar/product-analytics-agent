# PocketToons layer contracts

**Scope:** Contracts for the Bronze, Silver and Gold layers of the PocketToons fixture, following the [layer build workflow](layer-build-workflow.md). Business rules come from the [Metric Registry](../metrics/metric-registry.md) and the [data catalog](../examples/pockettoons-data-catalog.md); a contract implements them and must not contradict them.

**Status:** Bronze, `layer_build_log`, `silver_resolved_sessions`, `silver_payment_attempts` and `silver_subscription_access` are approved and implemented by `examples/pockettoons/build_layers.py`. The remaining Silver tables and Gold are not yet defined.

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
