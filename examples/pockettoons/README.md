# PocketToons synthetic data — prototype

This is a deterministic first-pass SQLite dataset for testing the data model and analysis workflow. Run with Python 3, no third-party packages:

```sh
python3 examples/pockettoons/generate.py --output pockettoons.sqlite
python3 examples/pockettoons/check_data.py pockettoons.sqlite
```

The generator refuses to overwrite an existing database. The random seed is 8126. The six analysis months are April–September 2026; 12,000 existing users signed up in March, followed by five cohorts of 2,400. All times are UTC. The database has 24,000 users, about 71,000 sessions and views, and over 6,000 financial events.

## Intended story and definitions

Quarter MAU is the average of monthly distinct active users, where activity is a session. Monthly MAU is 8,000, 9,000, 10,000, 10,200, 10,800, and 11,400, a 20% increase in quarter-average MAU. Revenue is succeeded subscription and PPV charges less succeeded refunds, before fees/tax, measured at success time. It is $10,053.68 each month. This exact flatness and fixed targets are intentional fixtures, not natural variation.

The later growth has an increased paid-social share; new signup cohorts have lower cumulative subscription uptake than the original cohort. One hundred subscriptions leave each month and are replaced. Channel comparisons must account for unknown sources and different cohort ages; the generated patterns are associations, not experimental proof of marketing causality.

## Data quality

`users.acquisition_source` is `unknown` for 238 users. `raw_payment_source.raw_amount` is text, and seven positive amounts are 100 times the dollar value because the incoming raw unit was cents but was labelled dollars. `payment_quality_review` records the evidence and the correction; `transactions.amount_usd` is the corrected analytical amount. Do not silently cast arbitrary text or assume every large value is wrong. The raw amount is not a second payment.

## Current limitations

This is an early fixture, not a full implementation of the reference model. It models sessions, free/subscription views, login links, subscriptions, PPV payments and refunds, payment status, episode attribution and daily channel spend. PPV purchases currently have no corresponding PPV playback; cancellation requests are represented in subscription history rather than UI events; there are no pre-login browsing events or delist/relist examples. It does not yet generate 15 evaluation questions, test an agent, implement bronze/silver/gold pipelines, or establish a quantified revenue bridge. Several reference-model optional catalog/event fields are omitted, and business tests in `check_data.py` do not cover every model rule. The amount outliers are isolated in a raw source table and do not distort the curated transaction totals. Extend and review these limitations before relying on the fixture for full assessment.
