# Evaluation record: Q16, Codex run 001

| Field | Value |
|---|---|
| Scenario | **Q16** Which advertising campaign caused each user's purchase? |
| Category | Unanswerable (should decline) |
| Runtime | Codex, fresh session, independent mode. Round 1 |
| Answer key | `answer-key/` Batch 3 note (behaviour only) |
| Original output | `agent-runs/codex/Q16/` (copied here; originals left in place) |
| Report | `v1-report.pdf` |

## Expected vs actual

| Item | Expected | Agent | Match |
|---|---|---|---|
| Declines | Required | "cannot be identified from this database" | ✅ |
| Why | No campaign-level exposure or user link | No campaign/UTM columns, no campaign keys in event JSON; marketing is channel-level only | ✅ |
| No fabricated join or causal claim | Required | First-touch counts shown as "descriptive labels, not campaign attribution" | ✅ |
| What data would be needed | Required | Campaign IDs, impression/click events linked to identity and purchases; agreed attribution rules; holdout experiments | ✅ |

## Outcome: **Pass**

One PRAGMA query was blocked by the read-only guard; the agent kept the failure in the evidence and used sqlite_master instead (good). Could have said more explicitly that channel-level daily spend vs signups is what *can* be compared; it notes Gold marketing is channel-level.

**Seen in every run (not scored):** registry-hash difference note; no git metadata in the repo copy.
