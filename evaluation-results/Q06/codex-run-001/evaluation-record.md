# Evaluation record: Q06, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q06** Are more users new, retained or returning? |
| Category | Growth accounting / lifecycle |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 1 Q06 (o09) |
| Original output | `agent-runs/codex/Q06/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| New / retained / returning, May–Sep | e.g. Sep 1,720 / 5,071 / 4,656 | Same, every month, with % of MAU | ✅ exact |
| April not classified | Required | "April has no result because March is outside coverage" | ✅ |
| Groups reconcile to MAU | Required | MAU column; Sep change 1,720 + 4,656 − 5,800 = +576 | ✅ |
| No causal language | Required | "No causal explanation is established" | ✅ |

## Outcome: **Pass**

Headline answers 'which group is largest' (retained). The expected headline also stresses the trend (returning users roughly doubled, 2,176 → 4,656). The table shows it (23.8% → 40.7% of MAU) but the text doesn't say it. Not a 'must', so Pass; worth noting as a framing weakness. Also counted churned users (5,800) correctly.

**Seen in every run (not scored):** repeats that the registry file hash differs from the one recorded at build; correct but now noise. Resolve once in round 2.
