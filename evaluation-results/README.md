# Evaluation results: evidence

The material behind [the evaluation results](../docs/evaluations/results.md): the answer key, every scored run and the raw agent outputs. It was kept outside the repository during the blind runs and published after they finished (2026-11-09). Status lines inside the files that say "evaluator-only" or "keep out of the repository" describe that period.

**Agents: do not read this folder during an investigation.** It contains expected answers.

## Layout

- `answer-key/`: expected values and scoring rules in four batches (`batch1`–`batch4`), each approved before any agent run. `oracle-b1/`–`oracle-b5/` hold the reference queries as evidence logs. They use the metric registry's canonical SQL on the source tables only, never the Silver/Gold tables the agent uses. `oracle-b5` extends Q03 to the weeks chosen when the agent asked for clarification.
- `QNN/`: one folder per scenario (IDs from [investigation-paths.md](../docs/evaluations/investigation-paths.md)).
  - `codex-run-001/`: round 1. `codex-run-002/`: round 2 (Q01, Q07, Q09, Q11 only).
  - Each run has `evaluation-record.md` (expected vs actual and the outcome), `v1-report.pdf` or `.md` (the agent's output, unedited), `v1-content.json` where the agent used the PDF generator, and `evidence.zip` (one evidence log per query, the query requests and the run note).
- `Q02/run-001/`: the GM question, run in Claude Code. It holds `v1-report.pdf` (the agent's raw output, scored), `feedback.md` (the review, word for word), `v2-report.pdf` (the agent's revision after that review), `v1-vs-v2-changes.md` and `evidence.zip`.
- `Q02/run-002-blind/`: a blind rerun of the GM question on the updated skill (fresh Claude Code agent, clean repo copy): Pass with minor issues.
- `TRACKER.md`: status of every scenario in both rounds.

The scoring rules are at the top of each answer-key batch: exact counts and cents, ±0.1 point on rates, and a fail for unsupported certainty, a silently chosen period or definition, or a missing required caveat.
