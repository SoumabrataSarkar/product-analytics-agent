# PocketToons synthetic data — review candidate

This is a deterministic SQLite dataset for review and testing. Run with Python 3, no third-party packages:

```sh
python3 examples/pockettoons/generate.py --output pockettoons.sqlite
python3 examples/pockettoons/check_data.py pockettoons.sqlite
```

The generator refuses to overwrite an existing database. The random seed is 8126. The six analysis months are April–September 2026. Existing users signed up in March; the monthly signup cohorts from May through September are 2,201, 2,653, 2,477, 2,949, and 1,720. All times are UTC. The database has 24,000 users, 70,614 sessions, 92,431 views, and 6,331 payment/refund attempts (including 30 failed attempts). Its 12 titles have between 20 and 39 episodes each.

## Intended story and definitions

Quarter MAU is the average of monthly distinct active users, where activity is a session. Monthly MAU is 7,937, 9,134, 9,976, 10,138, 10,871, and 11,447, an approximately 20% increase in quarter-average MAU. Revenue is succeeded subscription and PPV charges less succeeded refunds, before fees/tax, measured at success time. All charges and refunds are stored as positive amounts; subtract refunds explicitly with `CASE WHEN type='refund' THEN -amount_usd ELSE amount_usd END`. Monthly net revenue is $9,863.83, $10,293.40, $9,987.77, $10,171.53, $9,819.93, and $10,175.51 respectively. These are deliberately chosen targets, not natural random variation.

The later growth has an increased paid-social share; newer signup cohorts have lower 30-day subscription uptake than the immediately preceding cohorts. One hundred subscriptions leave each month, while replacements vary with the monthly target. Comparing unequal cohort ages is not a fair conversion test: use a fixed observation window and include only cohorts with a complete window. The checks compare May–June (96 of 4,854, 1.98%) with July–August (31 of 5,426, 0.57%). Do not use the March cohort for 30-day conversion: its observation window begins before the data starts in April. Channel comparisons must account for unknown sources; these patterns are associations, not experimental proof of marketing causality. The validation checks whether paid-social activity growth survives assigning all unknown Q1 users to paid social and none in Q2.

An arithmetic revenue bridge compares users who joined before July with users who joined in July or later. Q1 gross subscription charges were $29,970 from pre-July users; in Q2 they were $29,210.76 from those users and $769.23 from new users, before subtracting refunds. This cohort bridge demonstrates offsetting amounts, but does not by itself prove that all lost pre-July revenue was caused by cancellation; use subscription history to analyze the cancellations. PPV and refunds vary by month, including one additional purchase after a relisting.

Refunds comprise 44 PPV refunds and five subscription refunds, each linked to its original purchase. `refund_reason` is populated only on refunds and records a synthetic reported reason (`did_not_like_content`, `accidental_purchase`, or `poor_playback_quality`), not an independently verified cause. Subscription refunds close access when approved; prior views remain in the data.

## Data quality

`users.acquisition_source` is `unknown` for 238 users. `raw_payment_source.raw_amount` mixes numeric and numeric-string values; six records are non-numeric and seven values are 100 times the dollar amount because the incoming value was cents labelled USD. `payment_quality_review` records evidence and corrections; `transactions.amount_usd` is the corrected analytical amount. Do not silently cast arbitrary text or assume every large value is wrong. The raw amount is not a second payment. The review table is explicitly available to analysts; using it is not the same as independently detecting the issue.

## Current limitations

This candidate includes free, subscription and PPV playback, same-day resumes, multi-episode sessions, 5,273 browsing-only sessions, pre-login browsing, checkout before successful purchases, non-purchaser paywall observations, 30 failed payment attempts, one eight-episode quota boundary, cancellation requests, subscription and PPV refund requests, and one delist/relist/repurchase journey. Requests link to the original charge; refunds also link to that charge. All 183 analysis days have sessions. Subscription renewals follow the original day-of-month; PPV and refund times vary. It remains a simplified fixture, not a complete implementation of the reference model: it does not contain every possible status and event, and monthly counts remain deliberately controlled. Several optional reference-model columns are omitted. The checks cover selected invariants, not every model rule. Outliers live in a raw source table and do not distort curated transaction totals. It does not include the agent or the 15+ evaluation questions; those are separate later work.
