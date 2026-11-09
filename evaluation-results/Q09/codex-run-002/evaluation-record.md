# Evaluation record: Q09, Codex run 002 (round 2)

| Field | Value |
|---|---|
| Scenario | **Q09** Did refunds materially change the revenue comparison? |
| Runtime | Codex, fresh session, independent mode |
| Agent version | Round 2: `main` @ `cb3918d` (start-up baseline rule, PR #4), new ZIP download |
| Round 1 record | `../codex-run-001/evaluation-record.md` |
| Original output | `agent-runs/codex/round2/Q09/` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Gross / refunds / net, Q2 vs Q3 | As key | Same | ✅ exact |
| Answer | Refunds don't change the conclusion | "did not change the direction… substantially changed the size of a very small increase" | ✅ |
| New: start-up baseline | Not required | Flagged April as a start-up month and added May–Jun vs Aug–Sep: gross −1.466%, net −1.409% (both verified from o12) | ✅ |

## Outcome: **Pass** (round 1: Pass; no regression)

The new rule also fired here, correctly: both comparisons are shown and labelled, and the extra one is computed correctly. This is the rule generalising, not just patching Q07. Watch for over-use in future: the extra comparison is helpful here but lengthens the answer.
