# Evaluation record: Q11, Codex run 002 (round 2)

| Field | Value |
|---|---|
| Scenario | **Q11** Where do users drop from viewing a paywall to starting checkout and purchasing? |
| Runtime | Codex, fresh session, independent mode |
| Agent version | Round 2: `main` @ `cb3918d` (start-up baseline rule, PR #4), new ZIP download |
| Round 1 record | `../codex-run-001/evaluation-record.md` |
| Original output | `agent-runs/codex/round2/Q11/` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Biggest drop, unit, link gaps | As round 1 | All still met (4.9% checkouts without paywall link; 3.2% IAPs without checkout link) | ✅ |
| April | Start-up month; rates flat from May; what changed is paywall exposure | Still "subscription conversion shifted after April… both steps worsened"; recommends auditing "changes around April–May"; exposure not mentioned | ⚠️ not fixed |

## Outcome: **Partial** (round 1: Partial, unchanged)

The rule did not fire here. The question isn't phrased as a baseline comparison, so the agent didn't check whether April is a start-up period; it still reads April's high conversion as a funnel change. **Lesson:** a rule phrased around 'baselines' doesn't reach descriptions of trends. A stronger version would be: 'when the first period is an outlier, check whether it is a start-up period before describing a change over time.'
