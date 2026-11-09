# Did engaged users grow with active users?

Independent investigation, 9 November 2026. Scope: all six complete months in the documented activity coverage, 1 April through 30 September 2026 UTC; intervals are month-start inclusive and next-month-start exclusive.

Yes, both rose every month, but engagement grew more slowly over the full period. MAU rose from 7,937 to 11,447 (+3,510; +44.2%); MEU rose from 4,873 to 6,734 (+1,861; +38.2%). The engagement rate fell from 61.4% to 58.8% (-2.57 percentage points), despite a July rebound. At April's rate, September MAU would imply about 7,028 engaged users, 294 more than observed; this is a descriptive comparison, not a causal estimate.

| UTC month | MAU | MEU | MEU / MAU | Unidentified sessions |
|---|---:|---:|---:|---:|
| Apr | 7,937 | 4,873 | 61.4% | 2,286 |
| May | 9,134 | 5,532 | 60.6% | 3,044 |
| Jun | 9,976 | 5,965 | 59.8% | 3,184 |
| Jul | 10,138 | 6,143 | 60.6% | 3,354 |
| Aug | 10,871 | 6,453 | 59.4% | 3,480 |
| Sep | 11,447 | 6,734 | 58.8% | 3,703 |

Definitions: MAU v1.1 counts distinct resolved users with a session whose active span overlaps the month. MEU v1.0 counts distinct authenticated viewers with at least 60 seconds of watch time allocated to that month. Engagement rate v1.0 is MEU / MAU. Monthly distinct users cannot be added across months. Gold KPI matches the required metrics, time grain, and dimensions; its recorded build reconciliation passed. Evidence: 04_baseline.jsonl, 03_build.jsonl.

## Decomposition and hypotheses

- Supported as an observed pattern: paid social accounted for 2,436 of the 3,510 increase in active users (69.4%) and 1,327 of the 1,861 increase in engaged users (71.3%) between April and September. Its own engagement rate decreased from 60.1% (1,086 / 1,807) to 56.9% (2,413 / 4,243). This association does not establish that acquisition caused the overall decline. Evidence: 05_segments.jsonl.
- Inconclusive: whether shifts in acquisition mix alone explain the rate decline. Rates also changed within sources; no causal or standardized mix decomposition was estimated. Follow up with source/cohort-level retention and experience analysis.
- Inconclusive: whether unidentified sessions change the growth comparison. Unidentified sessions are excluded from MAU, and are sessions, not distinct people: 2,286 of 35,409 sessions starting in April (6.5%), and 3,702 of 48,714 starting in September (7.6%). September's Gold count is 3,703 because one unidentified session began in August and overlapped September. Their user-level impact cannot be determined from these counts. Evidence: 04_baseline, 08_identity, 09_boundary.

## Provenance and limitations

Database metadata asserts users, catalog and entitlement snapshots at 2026-09-30T23:59:59Z and coverage labels complete_synthetic_v1; this is not an independently verified database hash or freshness guarantee. Documented activity coverage is 2026-04-01 to 2026-10-01 UTC. Build 3a0dbed21d2f45958aefa2887a0cadd8 succeeded at 2026-11-09T11:16:56Z, and recorded reconciliations for MAU, MEU, rates and acquisition-source partitions passed. All 20 Bronze views, 10 Silver tables and 8 Gold tables are present (01_objects); full source fingerprints and build definitions are in 03_build. Current source row counts for sessions, views and segments match build counts, but no fresh content fingerprint was computed. Silver user-day keys have no nulls or duplicates in the checked columns; identity mismatch/ambiguous-link count is zero; 13 quality exceptions concern reviewed payment corrections, not activity (06_quality, 07_validation). The quality checks do not detect every possible fault.

The repository has no Git metadata, so a commit or actual download date cannot be verified. The local directory creation timestamp is 2026-11-09 20:12:48 IST; repository examined 2026-11-09. Builder SHA-256 matches the recorded build hash (12fd6588547bdfe88d12a2d8180f4db4d4781c334dc24770bd937accbe5d84c2). The current registry hash (4b5b2f0e881666570ace017c06ff1bca380fff83c8dfa679317706e6a8815554) differs from the build-recorded registry hash (57b21d71027782fc28c8ea7eea4eb0dd9ed18273577d81bf00eaded632ff1227). The stored metric versions match those in the current registry, but this hash difference prevents verification that the full registry text was identical at build time. Rebuild/reconcile on a separate authorized copy if exact provenance is required.

Evidence index: 01 objects; 02 snapshot metadata; 03 build and reconciliation; 04 baseline; 05 source decomposition; 06 quality exceptions; 07 source counts and key checks; 08 session-start identity coverage; 09 boundary check. All queries succeeded without truncation. Evidence 07 and 08 are incorrectly labeled Gold in their caller metadata; their SQL shows Bronze/Silver and Silver respectively. The evidence tools were read-only; the source database was not modified.
