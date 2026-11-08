# Data Catalog: PocketToons reference fixture

**Status:** Draft for review. This catalog describes the synthetic SQLite fixture, not an implemented agent or a general catalog for every product. The fixture contains 17 modeled and source-quality tables plus dataset_metadata. The reference data model specifies the intended contract; the catalog describes available data, relationships and safe use. Metric definitions belong in a separate future metric registry. Frozen Architecture v1 is unchanged.

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

**Joins:** user_id → users (optional), anonymous_id → anonymous_identities; session_id is referenced by identity_links, views, events and optional transactions. Each parent has zero or many child records. **Use:** session activity by platform. **Limitations/checks:** A session can have zero or many views. A 30-minute inactivity gap on the same browser/device starts a new session; playback heartbeats count. The same user may use multiple devices concurrently. A different account on the same device starts a new session even without a 30-minute gap. The checker validates timestamp/date/duration, same-identity overlapping intervals, platform, linked identity consistency, and view, event and in-app transaction user/time consistency. It does not prove the 30-minute inactivity rule: that requires complete engagement and playback-heartbeat evidence, including within-session gaps. Anonymous IDs are browser/installation identifiers, not definitive proof of a physical device. The fixture includes browsing-only sessions; open and unidentified sessions are covered by isolated regression scenarios, not the generated population.

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

## 3. content_catalog

**Purpose:** Series/title metadata. **Grain:** One title. **Primary key:** content_id. **Time:** first_release_at, last_release_at?, available_from_at?, available_until_at?, created_at and updated_at; release_date derives from first release.

**Columns:** content_id — title ID; title — display name; genre — primary genre; total_episodes — published/planned episode count; release_date — first-release date; first_release_at — first release timestamp; total_duration_sec — sum of episode lengths; content_tier — free, premium or mixed; content_status — current scheduled, live, delisted or archived status; last_release_at? — most recent release; available_from_at?/available_until_at? — current/latest availability boundaries; created_at/updated_at — record audit times.

**Joins:** content_id → many content_episodes; identify an episode with both keys. **Use:** titles by genre. **Limitations/checks:** Title totals and current status do not describe every historical episode state. Required-value checks exist; propose reconciliation of episode counts/duration and release dates.

## 4. content_episodes

**Purpose:** Episode-level metadata and access. **Grain/key:** One episode per (content_id, episode_number). **Time:** release_at and current/latest available_from_at?/available_until_at?.

**Columns:** content_id and episode_number — composite episode key; episode_title? — display name; episode_duration_sec — length; release_at — release time; access_tier — free or premium; episode_status — current scheduled, live, delisted or archived; ppv_list_price_usd? — current list price when offered; available_from_at?/available_until_at? — availability interval.

**Joins:** content_id → content_catalog; composite key → views, availability history and attribution. **Use:** episodes and their access tiers. **Limitations/checks:** Episode number alone is not unique; current price is not necessarily purchase price. Required fields and selected relationships are checked; propose domain and price/tier consistency tests.

## 5. content_availability_history

**Purpose:** Episode availability and status over time. **Grain:** One effective episode/status interval. **Key:** availability_id. **Time:** available_from_at inclusive; available_until_at? exclusive; recorded_at is record time.

**Columns:** availability_id — interval ID; content_id/episode_number — episode; available_from_at — start; available_until_at? — end, NULL for open interval; status — status during interval; recorded_at — recording time.

**Joins:** Composite episode foreign key. Match episode and event time. **Use:** whether an episode was live when viewed. **Limitations/checks:** Without a time condition multiple intervals can duplicate a view. Existing checker tests views against live availability; propose explicit interval-overlap checks.

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

**Columns:** event_id — ID; user_id? — signed-in actor if known; anonymous_id? — identity when applicable; event_at — occurrence; event_name — event type; session_id?/view_id?/txn_id?/subscription_period_id? — relevant referenced record; content_id?/episode_number? — relevant content; event_properties_json? — event-specific context; event_timezone? — reported timezone; country_at_event? — observed country; ingested_at — arrival.

**Joins:** Optional FKs to user, identity, session, view, transaction, period and series; episode composite FK where populated. **Use:** paywall-to-checkout sequence. **Limitations/checks:** Different event types populate different fields. Select one owner for a business moment to avoid duplicating payment/view facts. Checker covers selected session timing, product labels, funnel and refund order; propose event-specific schema checks.

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

**Purpose:** Dataset-wide metadata. **Grain/key:** One value per metadata_key. **Columns:** metadata_key TEXT primary key NOT NULL; metadata_value TEXT NOT NULL. The users_snapshot_at value is the UTC as-of instant for all user snapshots. It is not a per-user update time. The checker requires one valid value; it does not validate unrelated metadata keys. **Use:** determine when the users snapshot applies. **Limitations:** Later datasets with independent user refresh times may need a different representation.
