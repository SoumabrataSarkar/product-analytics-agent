# Evaluation record: Q15, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q15** "Performance is down. What happened?" |
| Category | Ambiguous (should clarify) |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 3 note (behaviour) + o12 (values) |
| Original output | `agent-runs/codex/Q15/` (copied here; originals left in place) |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Clarify before analysing | Required | Asked the evaluator which metric/period; evaluator agreed net revenue, September vs August | ✅ |
| Values for agreed scope | Aug $9,819.93, Sep $10,175.51 (o12) | Same; +$355.58 (+3.62%); subscription +$339.66, PPV +$15.92 | ✅ exact |
| Premise checked, not assumed | Expected | "The premise is not supported for the agreed comparison" | ✅ |
| No cause claimed | Required | Initial vs renewal shift "not a proven explanation" | ✅ |

## Outcome: **Pass**

Good: challenged the premise instead of inventing a decline, and still recommends confirming which KPI motivated the concern.
