# Weekly active users by acquisition source

Independent investigation. Periods: 2026-07-27 through 2026-08-02 and 2026-08-17 through 2026-08-23, UTC; SQL uses half-open bounds. WAU activity family v1.0, MAU identity v1.1. First-touch source is a fixed user attribute. Counts are distinct identified users with an overlapping session, not sums of daily counts. Gold is monthly; Silver preserves weekly detail.

- 01-inventory.jsonl: database objects and schemas.
- 02-metadata.jsonl: snapshot and coverage declarations.
- 03-build.jsonl: build status, versions, fingerprints, and reconciliation checks.
- 04-coverage.jsonl: observed Silver date coverage.
- 05-source.jsonl: source decomposition; organic decline and paid-social growth are supported as arithmetic observations, not causal mechanisms.
- 06-quality.jsonl: session-level recount, unidentified sessions and identity mismatches.
- 07-reconcile.jsonl: weekly totals and profile/source quality.
- 08-overlap.jsonl: user overlap between the selected, non-adjacent weeks; this is not consecutive-week retention or churn.

Result: WAU 5,914 to 5,831, change -83. Organic -213; paid social +182; paid search -52; unknown 0. Unknown source was 67 in each week; unidentified sessions were 859/10,704 and 765/10,782, excluded from WAU. Identity of people behind unresolved sessions is unknown, so impact on distinct users and source ranking cannot be determined.

The source snapshot label comes from dataset_metadata and is not a verified content hash. Build 3a0dbed21d2f45958aefa2887a0cadd8 succeeded 2026-11-09, and its activity reconciliation checks passed. Builder SHA-256 matches the current builder; the current registry SHA-256 4b5b2f0e881666570ace017c06ff1bca380fff83c8dfa679317706e6a8815554 differs from the build's 57b21d71027782fc28c8ea7eea4eb0dd9ed18273577d81bf00eaded632ff1227. Build definitions recorded activity family 1.0 and MAU 1.1; the cause and impact of the registry file difference are unverified. Source fingerprints were recorded by the build but not independently recomputed. The supplied repository has no .git metadata; file timestamp is November 9, 2026, not a verified download date or commit.
