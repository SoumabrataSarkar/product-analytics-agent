# PocketToons layer contracts

**Scope:** Contracts for the Bronze, Silver and Gold layers of the PocketToons fixture, following the [layer build workflow](layer-build-workflow.md). Business rules come from the [Metric Registry](../metrics/metric-registry.md) and the [data catalog](../examples/pockettoons-data-catalog.md); a contract implements them and must not contradict them.

**Status:** `silver_resolved_sessions` and `layer_build_log` are approved and implemented by `examples/pockettoons/build_layers.py`. Bronze classification, the remaining Silver tables and Gold are not yet defined.

**Build target:** the builder adds its objects to an existing generated database and never modifies source tables. It is verified on a copy before being applied to a reviewed database.

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
