# Evaluation record: Q10, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q10** How many subscription cancellations took effect during a period? |
| Category | Ambiguous definition (request vs access ended) |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 2 Q10 (o17–o19) |
| Original output | `agent-runs/codex/Q10/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Access ended, August | 113 | 113 (users and subscriptions) | ✅ exact |
| Requests, August | 92 | 92, shown separately and explained | ✅ |
| Meaning stated | Required | "Effective cancellation" = paid access actually ended; request defined separately | ✅ |
| Effective history, not user snapshot | Required | Silver history, Bronze recount agrees | ✅ |
| Window bounds | Required | 1 Aug 00:00 UTC inclusive to 1 Sep exclusive | ✅ |

## Outcome: **Pass**

Chose August without saying why (one month, not a quarter). The period was stated clearly, which passes under the rule. Calls the access-ended count an 'ad hoc' definition; the registry does define access loss (resubscription block), so that's over-cautious, not wrong. Didn't mention the request → loss one-month lag pattern (not required).

**Seen in every run (not scored):** registry-hash difference note; no git metadata in the repo copy.
