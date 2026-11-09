# Evaluation record: Q11, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q11** Where do users drop from viewing a paywall to starting checkout and purchasing? |
| Category | Funnel with link gaps |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 2 Q11 (o20–o22, o24) |
| Original output | `agent-runs/codex/Q11/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Biggest drop | Paywall → checkout | Same: 53.0% of views have no linked checkout (59.5% for May–Sep) | ✅ |
| Monthly funnel | o20 | Views/checkouts/purchases per month; May–Sep totals reconcile with the key (subscription 39.4% / 27.6%) | ✅ |
| Funnel unit, credit to paywall month, no time-matching | Required | All stated | ✅ |
| Link gaps reported | Required | 175 checkouts without paywall link; 56 of 1,725 IAPs without checkout link; later subscription checkouts with no payment attempt (1,292) | ✅ |
| No causal claim | Required | "Missing telemetry and behaviour remain indistinguishable" | ✅ |
| **Trend reading** | Rates **stable** from May; April atypical (base forming); what changed is paywall **exposure** | Headline "funnel weakened sharply after April"; compares April with pooled May–Sep; recommends investigating "the May transition"; exposure not mentioned | ⚠️ |

## Outcome: **Partial**

Why Partial: every must is met and the main answer is right, but the trend story is misleading. April is the start-up month (no subscribers at the start of the data), so 'weakened sharply after April' is a start-up effect, not a change in the funnel; from May the rates are flat. It hedged ('April is one month') but still led with the comparison and pointed the team at a 'May transition'. **Same blind spot as Q07** (April treated as a normal baseline). Round-2 rule candidate (same as Q07): check whether the first period of the data is a start-up period before comparing against it.

**Seen in every run (not scored):** registry-hash difference note; no git metadata in the repo copy.
