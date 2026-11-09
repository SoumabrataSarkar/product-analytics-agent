# Write-up

The formatted one-page version is [`submission/write-up.pdf`](../../submission/write-up.pdf), built by [`build_write_up.py`](build_write_up.py). This file mirrors its text.

## 01 What I built and why

One investigation runs in six steps: **clarify** (metric, period, population; asks if ambiguous) → **verify the definition** (the metric exists, with its approved definition in the registry and catalog) → **route to a layer** (Gold if it fits, Silver for detail, Bronze for raw audits) → **query with evidence** (read-only, bounded, one log per query) → **test hypotheses** (up to 3 per round, 3 rounds) → **report** (pattern ≠ cause; fixed PDF template, at most 10 pages). Every run, in Claude Code or Codex, reads the same `AGENTS.md`, `SKILL.md`, data catalog and metric registry. The SQLite database holds 8 Gold tables, 10 Silver tables and 20 Bronze views, built in one transaction with 122 reconciliation checks.

- **Clarifies instead of assuming.** When the metric, period or meaning is open, it asks first, as it did in all four evaluation questions that needed it, and it states every assumption it keeps.
- **Verifies the metric before computing it.** It checks that the metric exists and reads its approved, versioned definition and SQL in the metric registry, plus grains, joins and known gaps in the data catalog. Unsupported requests are declined, not improvised.
- **Maps the question to a layer for speed.** Gold answers standard monthly questions in milliseconds and is reconciled; Silver keeps per-user and per-event detail; Bronze is used only to audit raw values.
- **Evidence for every number.** Each query writes its SQL, layer, metric version and row count to its own log.
- **LLM-neutral by design.** Definitions, rules and guardrails live in files, not prompts, so Claude Code and Codex behave the same and a failure becomes a rule that every later run reads. Trade-off: no UI; quality depends on the agent following the skill.

## 02 How it performed: 18 blind test questions, two rounds

Round 1: 15 pass, 1 partial, 2 fail. Round 2 (Q02 v2 after review plus a blind rerun on the updated skill; Q07 and Q11 rerun; Q01 and Q09 as regression checks): 17 pass, 1 partial, 0 fail.

| Question type | Questions | Result | What happened |
|---|---|---|---|
| Simple numbers and filters | Q01 Q05 Q08 Q17 Q18 | All pass | Exact to the user and the cent |
| Vague or ambiguous questions | Q03 Q10 Q15 Q18 | All pass | Asked before choosing a metric, period or meaning |
| Unanswerable question | Q16 | Pass | Declined and named the data that's missing |
| Data-quality traps | Q12 Q13 Q14 | All pass | Caught both planted issues |
| Comparisons and lifecycle | Q04 Q06 Q09 | All pass | Right time basis; groups reconcile to the total |
| Cohort conversion | Q07 | Fail → Pass | Used April, the month the subscriber base forms, as a normal baseline; a new skill rule fixed it |
| Funnel drop-off | Q11 | Partial | Right answer and gaps, but read April's start-up as a funnel decline; the new rule didn't trigger here |
| GM investigation | Q02 | Fail → Pass | v1: headline numbers and story right, but some conclusions stated more firmly than the evidence allowed. After review the skill gained three certainty rules; v2 and a blind rerun on the updated skill both passed |

**Hardest:** comparisons that need context the data doesn't announce, such as a start-up month. Details: [evaluation results](../evaluations/results.md).

## 03 Running it for a 20-person product team

Time to answer (observed): simple 2–3 min, normal 5–6 min, complex 10–12 min.

- **Set-up for real data:** first build a data catalog and metric registry for the team's warehouse; the agent relies on both.
- **Cost (estimate):** running the 18 questions twice used about half of one 5-hour window on an INR 1,999-a-month Codex plan, so one seat covers a heavy day of questions: about INR 1,999 per active analyst a month. Token cost per run wasn't measured.
- **Lower cost and latency:** answer from the smallest layer that fits, with targeted queries instead of raw scans.
- **Guardrails:** data is only ever read: a read-only database role on a replica plus the query tool's read-only check, row and time limits; every figure traceable to its evidence log; sensitive columns kept out of the catalog.
- **Freshness:** real data keeps arriving, unlike this static dataset. Add a freshness tracker (last load per source and layer) that the agent checks first, warning or stopping when data is stale.
- **Quality over time:** rerun the 18 questions on every change to the skill, registry or data; track pass rate, clarification rate and query errors; review a weekly sample of real questions and turn failures into rules.

## 04 With more time

- Run the same questions in both runtimes for a direct Claude vs Codex comparison, plus held-out questions.
- Log tokens and time per run to replace the cost estimate with a measured cost per question.
- A short-answer mode for simple questions; a helper that drafts the catalog for a new database; a Slack or web front end.

*Note on tools:* Claude Code (Claude Opus 5.5, medium) built the framework, ran the GM investigation and computed the answer key. Codex (GPT Terra 6.1, medium) ran the evaluation. ChatGPT (Terra 5.6, later 6.1, medium) reviewed the GM report and evaluation decisions independently.
