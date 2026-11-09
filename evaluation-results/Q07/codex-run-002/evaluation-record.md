# Evaluation record: Q07, Codex run 002 (round 2)

| Field | Value |
|---|---|
| Scenario | **Q07** Did newer signup cohorts convert to subscription at a lower rate? |
| Runtime | Codex, fresh session, independent mode |
| Agent version | Round 2: `main` @ `cb3918d` (start-up baseline rule, PR #4), new ZIP download |
| Round 1 record | `../codex-run-001/evaluation-record.md` |
| Original output | `agent-runs/codex/round2/Q07/` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Cohort comparison | May–Jun 1.94% (94/4,854) vs Jul–Aug 0.53% (29/5,426) | Same | ✅ exact |
| April flagged | Required | "April is the first observed coverage month, so May–June is the principal comparison baseline"; April shown separately (4.56%) | ✅ fixed |
| September excluded with reason | Required | Yes | ✅ |
| No cause | Required | Within-source decline; "does not establish a cause" | ✅ |

## Outcome: **Pass** (round 1: Fail)

The round-2 rule worked: the baseline moved from Apr–Jun (2.59%) to May–Jun (1.94%), and the relative drop is now 72% instead of an overstated 79%. It gives 'first coverage month' as the reason rather than 'subscriber base starts at zero'; the comparison is right either way.
