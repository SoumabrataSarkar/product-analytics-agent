# Answer key, batch 2: revenue, lifecycle and funnel (Q07–Q11)

**Status:** Approved by evaluator, 2026-11-09. Q10 rule: picking one meaning of "cancellation" without saying so fails. **Evaluator-only:** keep out of every agent run and out of the repository.
**Reference method (oracle):** the metric registry's canonical SQL on **source tables only**, plus three labelled extra queries (o19, o22, o24) built on registry and catalog rules. Logs: `oracle-b2/o11…o25.jsonl` (15 queries, none truncated).
**Snapshot:** `pockettoons.sqlite` SHA-256 `8d39e78b…790b`, build `3a0dbed2`. Coverage: complete UTC months, April–September 2026. Money in exact cents, shown here in USD.
**Cross-checks:** subscription + PPV = net = gross − refunds for every month and quarter; in-app purchases and funnel counts match Gold (consistency only; the reference never reads Gold).
**Scoring rules:** as approved with batch 1 (exact counts and cents; ±0.1 point on rates; a stated, defensible choice of comparison passes; silent or mixed choices fail; unsupported certainty fails).

---

## Q07: Did newer signup cohorts convert to subscription at a lower rate?

**Expected values** (`conversion_30d`, funnel and lifecycle 1.0; o11). A user counts if a charge succeeds in `[signup_at, signup_at + 720 h)`.

| Signup cohort | Eligible users | Subscribed within 30 days | Rate |
|---|---|---|---|
| Apr | 1,600 | 73 | 4.56% |
| May | 2,201 | 38 | 1.73% |
| Jun | 2,653 | 56 | 2.11% |
| Jul | 2,477 | 13 | 0.52% |
| Aug | 2,949 | 16 | 0.54% |
| Sep | n/a | n/a | **not eligible**: 30-day window ends after the data |

- Grouped: May–June **94 ÷ 4,854 = 1.94%**; July–August **29 ÷ 5,426 = 0.53%**.
- **Expected answer:** yes. The July and August cohorts converted at about a quarter of the May–June rate.
- **Must:** compare only cohorts with a full 30-day window (exclude September and say why); flag April as unusual (the data starts with no subscribers, so April is the base-forming month); state the 30-day window.
- **Note:** subscription and paid conversion are identical here; no one's first purchase within 30 days was PPV only.
- **Fail triggers:** including September as a low-converting cohort; comparing windows of different lengths; claiming a cause (e.g. "paid social users don't convert") without evidence. The drop occurs in every source (Q02, check 8).

## Q08: How much net revenue came from subscriptions versus PPV?

**Expected values** (revenue group 1.1; o12–o14). Bookings basis (counted when the payment succeeds); refunds are subtracted under the type of the original charge.

| Period | Subscription net | PPV net | Unattributed refunds | Total net | PPV share |
|---|---|---|---|---|---|
| Q2 (Apr–Jun) | $29,940.03 | $204.97 | $0.00 | $30,145.00 | 0.68% |
| Q3 (Jul–Sep) | $29,960.01 | $206.96 | $0.00 | $30,166.97 | 0.69% |
| Apr–Sep | $59,900.04 | $411.93 | $0.00 | $60,311.97 | 0.68% |

- Monthly detail in o12. Subscription charges are $9.99 each; PPV charges are $1.99 each.
- **Expected answer:** subscriptions are about 99.3% of net revenue; PPV is under 1%. Both are flat Q2→Q3 (+0.07% and +0.97%).
- **Must:** distinguish gross from net (gross Q2 $30,182.93, Q3 $30,192.92); count each transaction once, at its success time; assign refunds to the original charge's type; report "unattributed" even though it is $0.
- **Optional context:** PPV payment failure rate 11–14% vs 5–6% for subscription renewals (o16). Worth mentioning, not required.
- **Fail triggers:** using `transactions.status` or creation time instead of the success event; adding refunds; double-counting through attribution tables; using the raw provider feed.

## Q09: Did refunds materially change the revenue comparison?

**Expected values** (o13, o15)

| | Q2 | Q3 |
|---|---|---|
| Gross charges | $30,182.93 | $30,192.92 |
| Refunds (positive, subtracted) | $37.93 (7 refunds) | $25.95 (5 refunds) |
| Net revenue | $30,145.00 | $30,166.97 |
| Refunds as % of gross | 0.13% | 0.09% |

- Q3 vs Q2: gross **+0.03%**, net **+0.07%**. Refunds shift the comparison by about 0.04 points; they don't change it.
- Monthly refund rate is about 0.12% (April–August) and 0.02% in September. Each refund is booked in the month it succeeds; no refund falls in a later month than its charge.
- **Expected answer:** no. Refunds are tiny (under $40 a quarter) and don't change the conclusion that revenue is flat.
- **Must:** subtract only successful refunds, at their success time; don't count pending or failed refunds; use the same time basis for both quarters.
- **Fail triggers:** adding refunds to revenue; counting refund requests; "material" claims without numbers.

## Q10: How many subscription cancellations took effect during a period?

**Expected behaviour first:** the question is ambiguous between a **cancellation request** and **access actually ending**. Pass = ask, or state the interpretation and preferably give both. The question also names no period, so state the period used (monthly, or a stated quarter).

**Expected values** (o17–o19, o23)

| Month | Cancellation **requests** (`cancellation_request_rate`) | Access **ended** (losses; o19) | Of which after a request | Subscribers at month start | Churn (snapshot) |
|---|---|---|---|---|---|
| Apr | 91 | 1 | 1 | 0 | n/a (no subscribers at data start) |
| May | 108 | 91 | 91 | 980 | 91 (9.3%) |
| Jun | 96 | 108 | 108 | 1,023 | 108 (10.6%) |
| Jul | 113 | 96 | 96 | 994 | 96 (9.7%) |
| Aug | 92 | 113 | 113 | 1,011 | 113 (11.2%) |
| Sep | 95 | 91 | 91 | 977 | 91 (9.3%) |

- Quarter totals: requests Q2 **295**, Q3 **300**; access ended Q2 **200**, Q3 **300**.
- **Key pattern:** a request takes effect at the end of the paid period, about a month later. April's 91 requests became May's 91 losses, and so on. Every access loss in the data followed a request; payment failures caused none.
- Resubscription within 60 days (o23): May 9.9%, June 6.5%, July 3.1%. **August and September can't be measured** (the window runs past the data).
- **Must:** use effective intervals from `subscription_history`, not the current `users` snapshot; treat `cancel_at_period_end` as a request, not immediate loss of access; state which meaning was used.
- **Fail triggers:** answering with the user snapshot; counting requests as cancellations "taking effect" without saying so; reporting August/September resubscription rates as if complete.

## Q11: Where do users drop from viewing a paywall to starting checkout and purchasing?

**Expected values** (`paywall_funnel_monthly`, `paywall_exposure_monthly`; o20–o22, o24). Unit = one paywall view; steps count only through **captured links** (`triggering_paywall_event_id`, `checkout_event_id`); a paywall counts once however many checkouts or attempts it has.

| Product, period | Paywalls | → with checkout | → with purchase | Paywall→checkout | Checkout→purchase | Paywall→purchase |
|---|---|---|---|---|---|---|
| Subscription, May–Jun | 1,813 | 710 | 196 | 39.2% | 27.6% | 10.8% |
| Subscription, Jul–Sep | 2,717 | 1,074 | 296 | 39.5% | 27.6% | 10.9% |
| PPV, May–Jun | 298 | 144 | 66 | 48.3% | 45.8% | 22.1% |
| PPV, Jul–Sep | 458 | 212 | 98 | 46.3% | 46.2% | 21.4% |

(Monthly rows in o20. April is atypical: subscription paywall→purchase 50.6% while the base forms.)

- **Expected answer:** the biggest drop is **paywall → checkout start**: about 60% of subscription paywall views and 52–54% of PPV views never start a checkout. Next is checkout → purchase: about 72% of subscription checkouts don't complete. Rates are stable across the period, so the funnel's **conversion rates** didn't change; what changed is how many users reach a paywall (exposure 23.2% in April → 11.6% in May → 9.2% in September; o21).
- **Must report the gaps:** checkouts without a captured paywall link, 17–65 a month (3.9–5.9%); in-app purchases without a checkout link, 2–33 a month (o24); checkouts that never produced a payment attempt, 293–331 a month (64–75% of checkouts from May, 25% in April). No checkout had a retried payment.
- **Must:** state the funnel unit and that later steps are credited to the paywall's month; never match unlinked events by time or user; no causal claim that the paywall *causes* purchase.
- **Fail triggers:** counting each payment attempt as a purchase; inferring links from nearest events; dropping the unlinked cases.
