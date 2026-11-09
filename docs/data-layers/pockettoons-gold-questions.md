# PocketToons Gold: supported questions and tables

**Status:** Approved question list and table plan for Gold v1. Contracts for each table are added to [pockettoons-layer-contracts.md](pockettoons-layer-contracts.md) as they are implemented.

Gold holds small, pre-checked monthly answers for the questions the agent is asked most. Each Gold table reads Silver only, reproduces approved registry metrics, and records the definition versions it used. Finer grains stay in Silver.

## Design rules

- **Monthly only in v1.** Gold rows are complete UTC months inside the coverage window. Daily and weekly figures come from Silver.
- **Counts as well as rates.** Every rate is stored with its numerator and denominator, so it can be explained and recombined correctly.
- **Long format for segments.** Segment tables use (month, dimension, value) rows. Segment values are never summed: one user can appear in several values.
- **Definition versions.** Every Gold row stores the registry definition versions it used.

## Tables and questions

| Gold table | Grain | Questions | Silver inputs | Registry metrics reproduced | Evaluation scenarios |
|---|---|---|---|---|---|
| `gold_kpi_monthly` | month | MAU, average DAU, stickiness, engaged users, engagement rate, signups, gross, refunds and net revenue, paying users, ARPU, ARPPU, subscribers at start and end, net adds, churn, MRR, cancellation requests; coverage: unidentified sessions and unknown-source signups | day activity, resolved sessions, profile, payment attempts, subscription access | `mau`, activity family, stickiness and engagement rate, revenue group, lifecycle and supporting metrics | Q01, Q02, Q04, Q10 |
| `gold_activity_segments_monthly` | month × dimension × value | Active and engaged users by platform, acquisition source, country and subscriber status | resolved sessions, day activity, profile, subscription access | `mau_monthly_by_platform`, `mau_monthly_by_subscriber_status` | Q03, Q05, Q14 |
| `gold_growth_accounting_monthly` | month | New, retained, resurrected and churned users; quick ratio | day activity, profile | `growth_accounting_monthly` | Q06 |
| `gold_cohorts` | signup month × months since signup | Cohort size and retention; 7-day activation; 30-day conversion; day-1, day-7 and day-30 retention | profile, day activity | `retention_monthly_cohort`, `retention_day_n`, `activation_7d`, `conversion_30d` | Q07 |
| `gold_revenue_monthly` | month × revenue type | Gross, refunds and net by subscription, PPV and unattributed refunds; payers; failed attempts; refund rate | payment attempts | revenue group, `refund_rate_monthly`, `payment_failure_rate_monthly` | Q08, Q09 |
| `gold_funnel_monthly` | month × product | Paywall views, checkouts, purchases and rates; checkouts and purchases without a captured link; exposure | paywall funnel | `paywall_funnel_monthly`, `paywall_exposure_monthly` | Q11 |
| `gold_content_monthly` | month × title | Viewers, views, watch hours, episode completion, series continuation, free-quota hits | title watch, episodes, day activity | engagement group | Q12 |
| `gold_marketing_monthly` | month × channel | Spend, impressions, clicks, CTR, CPC, signups, new payers, cost per signup, CAC | marketing daily | `marketing_ctr_monthly`, `marketing_efficiency_monthly` | Q14 |

## Answered outside Gold

| Need | Where | Why |
|---|---|---|
| Data quality and trust checks | `silver_quality_exceptions` | Already small and row-level; the agent checks it before trusting a figure (Q13). |
| Daily or weekly figures, episode-level detail, combined slices such as platform × source | Silver tables | Not pre-computed in v1; built from Silver on request. |
| Clarifying an ambiguous request | The agent workflow | Q15 is a clarification behaviour, not a data question. |

## Not supported in v1

- Campaign- or click-level attribution and causal claims about what caused a purchase (Q16): the data has no user-level campaign exposure.
- Lifetime value, payback and forecasting.
- Historical user attributes other than subscription status: country and status in `silver_user_profile` are snapshots.
