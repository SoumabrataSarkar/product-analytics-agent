# Monthly platform mix

Independent investigation. Repository: SoumabrataSarkar/product-analytics-agent, commit c405664dfba7134d66e3694103457045d6b21bdd. Database: /Users/soum/Documents/Codex/2026-11-07/referenced-chatgpt-conversation-this-is-an/outputs/pockettoons.sqlite (read only). Snapshot: dataset_metadata users_snapshot_at 2026-09-30T23:59:59Z; this is a metadata assertion, not a verified file hash. Layer build 3a0dbed21d2f45958aefa2887a0cadd8 succeeded 2026-11-09 11:16:56 UTC; builder SHA-256 12fd6588547bdfe88d12a2d8180f4db4d4781c334dc24770bd937accbe5d84c2, registry SHA-256 57b21d71027782fc28c8ea7eea4eb0dd9ed18273577d81bf00eaded632ff1227. MAU v1.1; activity family v1.0. Source hashes recorded in 03-build.jsonl were not freshly recomputed. Source and Silver session counts match the build (257,175), but this is not proof that content is unchanged.

The latest complete months are August and September 2026, UTC, with half-open month boundaries. Android reached 55.40% then 55.14% of MAU (-0.25 percentage points); iOS 45.31% then 45.75% (+0.44 pp); web 27.97% then 27.43% (-0.54 pp). This is a small month-to-month shift, not a substantial redistribution. Counts respectively: Android 6,022 to 6,312; iOS 4,926 to 5,237; web 3,041 to 3,140. Total MAU 10,871 to 11,447 (+576, 5.3%). The April–September series is in 05-platform.jsonl. Android ranged 55.08–55.40%, iOS 45.31–46.16%, web 27.43–28.03%.

MAU is distinct resolved users with a session whose active span touches the month; platform is taken from sessions. Shares use total MAU as denominator; they are overlapping reach, not an exclusive allocation. In August 3,101 of 10,871 users (28.5%) used multiple platforms; in September 3,225 of 11,447 (28.2%). Platform counts cannot be added into a total or used as additive contributions to MAU growth.

Hypothesis: a major platform shift occurred — not supported by observed identified-user shares in the latest months. Hypothesis: cross-platform use makes these shares overlap — supported. Hypothesis: unidentified sessions could change the inferred mix — inconclusive: August 3,480/46,241 sessions (7.53%) and September 3,703/48,715 (7.60%) were unidentified; they cannot be converted into unique people or allocated without identity assumptions. Missing platform and link-user mismatch counts were zero in each month. No causal mechanism has been established. Continue monitoring platform reach and identity coverage; investigate identity resolution before treating small movements as meaningful.

Gold was selected because its monthly platform grain, definition, complete periods and reconciliation fit the question. The successful build records that platform counts reconcile to the registry source SQL; Silver coverage checks reproduce overall MAU. Gold, Silver and Bronze objects and build checks are recorded below. The activity coverage window April 1 through October 1 exclusive is the registry's documented contract, not declared as explicit boundaries in dataset metadata. The latest source activity was 2026-09-30 23:59:48 UTC. No new fingerprint comparison was made. The identified-user result does not measure exclusive platform preference or session share.

Evidence index (all query outputs untruncated):
- 01-schema.jsonl: Bronze views, Silver and Gold tables present.
- 02-metadata.jsonl: snapshot and synthetic coverage labels.
- 03-build.jsonl: build status, versions, source fingerprints and reconciliations.
- 04-gold-schema.jsonl: table schemas and keys.
- 05-platform.jsonl: monthly platform reach and denominators (Gold).
- 06-coverage.jsonl: monthly session counts, unresolved identity, mismatch, missing platform and MAU (Silver).
- 07-quality.jsonl: quality exception summary; 13 relate to payments.
- 08-overlap.jsonl: distinct users by number of platforms, August and September.
- 09-unidentified.jsonl: unidentified sessions by platform and start month.
- 10-freshness.jsonl: source/Silver counts, event bounds and build counts.
