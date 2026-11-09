# Data-layer build workflow

**Scope:** A dataset-independent method for turning source tables into Bronze, Silver and Gold layers that an analytics agent can trust. It records how the work is done, the blockers that occur, how to work around them and why. Table-specific contracts belong in each dataset's own contract document; for PocketToons see [pockettoons-layer-contracts.md](pockettoons-layer-contracts.md).

**Status:** Method in use for PocketToons. Steps marked *(PocketToons: done)* are complete for that dataset only.

## Principles

1. **Definitions are the authority; layers implement them.** Metric definitions and the data catalog decide what a number means. A layer table implements those rules and must be tested against them. Shared SQL avoids two diverging versions of the same logic, but it cannot validate itself, so every table also needs an *independent* check.
2. **Contract first, then code.** Every layer table gets a written contract that is reviewed before it is built.
3. **One table at a time.** Review, build, reconcile and test a table before starting the next. The first table also fixes the contract format.
4. **Gold is designed from questions, not from a target number of tables.** Each Gold table states exactly which questions it answers and which must go elsewhere.
5. **Never trade correctness for speed.** A precomputed answer that does not exactly fit a question is not used.
6. **Source data is never modified.** Layers are added beside the source; the source is only read.

## Layer roles

| Layer | Role | Typical form |
|---|---|---|
| Bronze | Source records as received, including their quality problems; used for audits and reconciliation | Views over source tables, or copies when an immutable snapshot is required |
| Silver | Cleaned, validated, consistently keyed facts at a stated grain, with lineage and labelled exceptions | Materialised tables |
| Gold | A small number of precomputed metric tables for frequent questions, at a stated grain | Materialised tables |
| Build log | Evidence of every build: inputs, versions, row counts, reconciliation and test results | One table |

## Workflow

### 1. Inventory and classify the source *(PocketToons: pending)*

List every source table and classify its role: raw event or transaction records, current-state snapshots, effective-dated histories, reference data, metadata, review or correction evidence. The role decides how a table is exposed in Bronze and how it may be used: a history is queried as of a time, a snapshot only at its declared instant, review evidence never as an extra fact.

### 2. Define Bronze

Decide, per table, whether Bronze is a view or a copy.

- **View:** no duplication and no drift between Bronze and source, but a view always shows the source's *current* content. It is not an audit snapshot. Record a source fingerprint (row counts and content hashes) in the build log so that later changes to the source are detectable.
- **Copy:** an immutable snapshot, at the cost of storage and a refresh process. Use when the source can change after review and the original must be preserved.

Never rename or alter source tables to fit the layer naming; required source tables and columns stay as they are.

### 3. Write each Silver contract

Use this format for every layer table:

| Part | Content |
|---|---|
| Purpose | Why the table exists and which repeated logic it removes from queries |
| Grain | What one row represents; whether any source rows are excluded |
| Key and indexes | Primary key; indexes for the expected access paths |
| Columns | Name, meaning, type, null meaning; source columns are carried unaltered under a clear name |
| Rules | The business rules applied, cited to the approved definitions |
| Time | Time zone, timestamps used, inclusive and exclusive boundaries |
| Lineage | Source tables, cardinality from source to row, build identifier |
| Exceptions | What is excluded, what is retained but labelled, what is flagged as suspicious but usable |
| Supports | Metrics and questions the table serves |
| Does not support | Questions that need another table or the source |
| Reconciliation | Checks suited to this grain, at least one independent of the build query |
| Tests | Isolated cases for each rule and edge |

Before accepting a set of Silver tables, map every approved metric, dimension and example question to the table and columns that answer it. A gap means another table, a view, or a documented safe query against the source.

### 4. Design Gold from questions

For each Gold table: the row grain (for example one month, or one month per channel), the metrics and dimensions it contains, which values may be summed across rows, and which questions must go to Silver. Distinct counts and ratios are stored only at their own grain and never summed or averaged into another grain.

### 5. Build safely

The builder must:

- own an **explicit list** of the objects it creates, and drop or replace only those;
- **check the source schema** (required tables and columns) before building, and stop if it does not match;
- build **atomically**: all layer objects in one transaction, so an interrupted or failed build leaves the previous successful layers in place;
- write a **build record** on success: build identifier, time, source fingerprint, builder version, relevant definition versions, row counts and reconciliation results; a failed build is recorded with its error and does not replace the previous layers;
- run first on a **copy** of any reviewed or important database, and be applied to the original only after its results are verified;
- report measured size and time; never rely on estimates.

### 6. Reconcile by grain

Choose reconciliation that fits the transformation rather than one universal equation:

| Transformation | Reconciliation |
|---|---|
| One row per source row | Row counts equal; category counts add up to the total; key sets equal |
| Filtering with labelled exceptions | Kept + excluded = source; suspicious-but-usable rows are counted separately and not subtracted |
| Aggregation to a coarser grain | Additive measures (counts, seconds, cents) sum to the source totals; distinct counts are recomputed, not summed |
| Money | Charges and refunds reconcile separately in integer cents; invalid amounts are rejected or flagged, never rounded into trusted values |
| Metric tables | Each value equals the approved definition computed directly on the source for the same period, filters and dimensions |

At least one reconciliation per table must be computed independently of the query that built it.

### 7. Test

Isolated tests with small hand-built tables cover each rule, boundary and exception. Fixture-level checks run the reconciliations against a full build.

### 8. Document and route

Add every layer table to the data catalog with its contract, record the build in project status, and state routing rules for the agent: the most precise layer that exactly fits the question, Bronze for audits.

## Blockers and workarounds

| Blocker | Why it matters | Workaround |
|---|---|---|
| Required source tables cannot be renamed to layer prefixes | Renaming breaks the required schema and existing consumers | Bronze as prefixed views over unchanged source tables |
| A view is not a snapshot | Later source changes silently change Bronze | Fingerprint the source in the build log; use copies where immutability is required |
| Shared SQL cannot validate itself | The same faulty query run twice agrees with itself | Add independent reconciliation for every table |
| Daily flags do not aggregate to weekly or monthly flags | A threshold met over a week may be met on no single day | Store additive measures (for example watch seconds per user-day) and apply thresholds at the query's grain |
| Distinct counts are non-additive | Summing monthly users overstates quarterly users | Store distinct counts only at their grain; compute other grains from Silver |
| Rounding hides invalid money values | A malformed amount becomes a trusted figure | Validate exact cents; route invalid values to exceptions |
| SQLite fails to write through some shared or network folders (`disk I/O error`) | A build can corrupt or abandon the target file | Build on local disk, verify, then copy the finished file |
| Range joins between large derived sets are slow in SQLite | A correct query can take minutes | Expand ranges to equality keys (for example one row per active day) and index Silver tables on their access paths |
| An interrupted build leaves mixed old and new layers | Queries see an inconsistent state | One transaction per build; the build record is written only on success |
| Important local databases | A faulty build damages reviewed data | Build and verify on a copy first; keep a backup before applying |
| Several contributors change shared definitions | Layers drift from definitions | Record definition versions in the build record; rebuild after definition changes |
