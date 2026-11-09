# Evaluation record: Q01, Codex run 002 (round 2)

| Field | Value |
|---|---|
| Scenario | **Q01** How did monthly active users change across the available months? |
| Runtime | Codex, fresh session, independent mode |
| Agent version | Round 2: `main` @ `cb3918d` (start-up baseline rule, PR #4), new ZIP download |
| Round 1 record | `../codex-run-001/evaluation-record.md` |
| Original output | `agent-runs/codex/round2/Q01/` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| MAU, all months | 7,937 → 11,447 (+3,510, +44.2%) | Same | ✅ exact |
| Unidentified sessions excluded, not people | Required | 6.5–7.6% of sessions; effect on people unknown | ✅ |
| Silver recount | n/a | Matches all six months | ✅ |

## Outcome: **Pass** (round 1: Pass; no regression)

No regression. Did not raise the registry-hash note this time.
