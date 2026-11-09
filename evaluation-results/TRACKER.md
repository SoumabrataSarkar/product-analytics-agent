# Evaluation tracker

Status of all 18 scenarios (IDs from `docs/evaluations/investigation-paths.md`). Evaluator-only: keep out of agent runs. Updated after every step.

**Last updated:** 2026-11-09

| ID | Question (short) | Answer key | Claude Code run | Codex run | Outcome |
|---|---|---|---|---|---|
| Q01 | How did MAU change across the months? | Batch 1, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q01/codex-run-001/`) | **Pass** |
| **Q02** | **Why did MAU grow while revenue stayed flat?** | **Not needed (scored against reviewer's source-level check)** | **Run 001, 2026-11-09** (`Q02/run-001/`) | **n/a (Claude Code only)** | **Fail (v1) → Pass (v2 after review; blind run 002 on the updated skill: Pass, minor issues)** |
| Q03 | Which acquisition sources drove the MAU change? | Batch 1, approved; extended for clarified weekly scope (o41–o42) | n/a (Codex only) | Run 001, 2026-11-09 (`Q03/codex-run-001/`); asked to clarify, evaluator chose 2 weeks | **Pass** (clarified variant) |
| Q04 | Did engaged users grow with active users? | Batch 1, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q04/codex-run-001/`) | **Pass** |
| Q05 | Did the platform mix change? | Batch 1, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q05/codex-run-001/`) | **Pass** |
| Q06 | Are more users new, retained or returning? | Batch 1, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q06/codex-run-001/`) | **Pass** |
| Q07 | Did newer cohorts convert to subscription less? | Batch 2, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q07/codex-run-001/`) | **Fail** (April baseline caveat missing; numbers exact) |
| Q08 | Net revenue from subscriptions vs PPV | Batch 2, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q08/codex-run-001/`) | **Pass** |
| Q09 | Did refunds materially change the revenue comparison? | Batch 2, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q09/codex-run-001/`) | **Pass** |
| Q10 | How many cancellations took effect in a period? | Batch 2, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q10/codex-run-001/`) | **Pass** |
| Q11 | Where do users drop from paywall to checkout to purchase? | Batch 2, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q11/codex-run-001/`) | **Partial** (April start-up read as a funnel decline) |
| Q12 | Most-watched episodes and actual completion | Batch 3, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q12/codex-run-001/`) | **Pass** |
| Q13 | Is an unusually large source payment real? | Batch 3, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q13/codex-run-001/`) | **Pass** |
| Q14 | Can we trust channel conclusions with missing sources? | Batch 3, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q14/codex-run-001/`) | **Pass** |
| Q15 | "Performance is down. What happened?" (should ask) | Behaviour rules (repo + batch 3 note), approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q15/codex-run-001/`) | **Pass** |
| Q16 | Which campaign caused each purchase? (should decline) | Behaviour rules (repo + batch 3 note), approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q16/codex-run-001/`) | **Pass** |
| Q17 | US subscribers at end of September (filtered) | Batch 4, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q17/codex-run-001/`) | **Pass** |
| Q18 | Mobile sessions, September vs August (filtered) | Batch 4, approved | n/a (Codex only) | Run 001, 2026-11-09 (`Q18/codex-run-001/`) | **Pass** |

## Run plan (decided 2026-11-09)

- **Q02:** Claude Code only (run 001, done). Not rerun in Codex.
- **Q01, Q03–Q18:** Codex only, one fresh session per question. The answer key was computed with Claude, so the runtime being tested did not build its own key.
- **Limitation for the write-up:** no question is run in both runtimes, so there is no same-question Claude-vs-Codex comparison. Agent-agnostic use is shown by both runtimes running the same skill and tools, not by matched numerical agreement.
- **Run outputs:** `Documents/agent-runs/codex/QNN/` (one folder per question; never inside the repo or this folder). After scoring, each run's record goes in `QNN/codex-run-001/` here.

## Pending actions

Done: answer key complete for all 16 scenarios (batches 1–3 approved). PR #1 (PDF generator, skill rules) and PR #2 (evaluation process doc + Evaluation tab) merged.

**Storage decision (2026-11-09):** evaluation material stays local in this folder (no separate private repo). It is copied into the main repository only after **all** blind runs, Claude Code and Codex, are finished; once it is in the repo, any new run of these questions is no longer independent. Keep a backup copy of this folder.

1. `pip install reportlab matplotlib` on the Mac (needed by the PDF generator).
2. Done: moved to `Documents/eval-private/` (outside Codex's `Documents/Codex/` working area), 2026-11-09.
3. Codex runs in **fresh** sessions with only the question, database path and "independent mode": Q01 first (setup smoke test), then Q03–Q16.
4. Verify Q02 v2 against checks 17–21.
5. Score each Codex run against its answer key; record it in `QNN/codex-run-001/` (same file names as `Q02/run-001/`, see README) and in the table above.

## Scoring rules (approved with batch 1)

- Counts must match exactly; percentages and rates may differ by ±0.1 point; quarter averages by ±0.1.
- Where the question doesn't name a comparison period, a clearly stated, defensible choice passes, and so does a clarifying question. A silent or mixed choice fails.
- Q10: picking one meaning of "cancellation" (request vs end of access) without saying so fails.
- Unsupported certainty (for example, a causal claim from an association) fails, as in the run template.

## Files

- `answer-key/batch1-activity.md` with reference query logs in `answer-key/oracle-b1/`
- `answer-key/batch2-revenue-lifecycle.md` with reference query logs in `answer-key/oracle-b2/`
- `answer-key/batch3-content-quality.md` (Q12–Q14 values; Q15–Q16 behaviour) with reference query logs in `answer-key/oracle-b3/`
- `Q02/run-001/`: v1-report.pdf, feedback.md, v2-report.pdf, v1-vs-v2-changes.md, evaluation-record.md


## Round 1 result (2026-11-09)

- 18 scenarios run: **15 Pass, 1 Partial (Q11), 2 Fail (Q02 on the pre-PR #1 agent; Q07)**.
- Main failure pattern: the first month of data (April, subscriber base starting at zero) used as a normal baseline (Q07 fail, Q11 partial). Q02 v1 failures (certainty, comparison labels) did not recur after the PR #1 rules.
- Behaviour scenarios all passed: asked to clarify (Q03, Q10, Q15, Q18), declined the unanswerable one (Q16), caught both data traps (Q12 premium episode, Q13 $999).
- Noise in every run: registry-hash mismatch note; no git metadata in the repo copy.
- Next: round 2 = general rule for start-up periods (and fix the noise), then rerun Q07 and Q11 plus 2–3 passes in fresh sessions.

## Round 2 (agent version: `main` @ `cb3918d`, PRs #3 and #4 merged 2026-11-09)

| ID | Why rerun | Folder | Outcome |
|---|---|---|---|
| Q07 | Round-1 fail (April baseline) | `agent-runs/codex/round2/Q07/` → `Q07/codex-run-002/` | **Pass** (fixed) |
| Q11 | Round-1 partial (April baseline) | `agent-runs/codex/round2/Q11/` | **Invalid, rerun**: first attempt ran on the round-1 repo copy (`Github/product-analytics-agent`), so it didn't have the new rule |
| Q01 | Regression check (round-1 pass) | `agent-runs/codex/round2/Q01/` → `Q01/codex-run-002/` | **Pass** (no regression) |
| Q09 | Regression check (round-1 pass) | `agent-runs/codex/round2/Q09/` | **Pass** (no regression; rule also applied correctly) |

**Round 2 result:** Q07 fixed (Fail → Pass); Q11 unchanged (Partial); no regressions. Final round-2 standing over 18 scenarios: 17 Pass, 1 Partial (Q11), 0 Fail. Q02's round 2 is v2, the agent's revision after review feedback (not a fresh blind run). The registry-hash note still appears in 3 of 4 runs: agents compute the hashes themselves and don't use the project-status note.

**Q02 blind rerun (2026-11-09):** fresh Claude Code helper agent, clean `main` @ `0b9a143`, standard prompt, GM wording → **Pass (minor issues)**. Record: `Q02/run-002-blind/`. Board report in the submission stays v2.
