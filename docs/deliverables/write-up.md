# Write-up

The formatted one-page version is [`submission/write-up.pdf`](../../submission/write-up.pdf), built by [`build_write_up.py`](build_write_up.py). This file mirrors its text.

## 01 What I built and why

One investigation runs in six steps: **clarify** (metric, period, population; asks if ambiguous) → **verify the definition** (the metric exists, with its approved definition in the registry and catalog) → **route to a layer** (Gold if it fits, Silver for detail, Bronze for raw audits) → **query with evidence** (read-only, bounded, one log per query) → **test hypotheses** (up to 3 per round, 3 rounds) → **report** (pattern ≠ cause; fixed PDF template, at most 10 pages). Every run, in Claude Code or Codex, reads the same `AGENTS.md`, `SKILL.md`, data catalog and metric registry. The SQLite database holds 8 Gold tables, 10 Silver tables and 20 Bronze views, built in one transaction with 122 reconciliation checks.

- **Clarifies instead of assuming.** When the metric, period or meaning is open, it asks first or states a clear choice, as it did in every evaluation question that needed it, and it states every assumption it keeps.
- **Verifies the metric before computing it.** It checks that the metric exists and reads its approved, versioned definition and SQL in the metric registry, plus grains, joins and known gaps in the data catalog. Unsupported requests are declined, not improvised.
- **Chooses the layer that fits.** Gold serves supported monthly summaries; Silver preserves detail; Bronze provides source evidence. Correctness and coverage take priority over speed.
- **Evidence for every number.** Each query writes its SQL, layer, metric version and row count to its own log.
- **LLM-neutral by design.** Both runtimes read shared definitions, rules and tools. This keeps analytical instructions consistent; it does not guarantee identical behavior. A reference website is included; investigations run in the coding-agent runtime.

## 02 How it performed: 18 blind test questions, two rounds

Round 1: 15 pass, 1 partial, 2 fail. After selected reruns: 17 pass, 1 partial, 0 fail as the latest outcome per scenario. Q02 had a reviewed revision and a separate blind rerun; Q07 and Q11 were rerun, with Q01 and Q09 as regression checks. Other first-round outcomes carry forward.

| Question type | Questions | Result | What happened |
|---|---|---|---|
| Simple numbers and filters | Q01 Q05 Q08 Q17 Q18 | All pass | Exact to the user and the cent |
| Vague or ambiguous questions | Q03 Q10 Q15 Q18 | All pass | Asked, or stated a clear choice, before picking a metric, period or meaning |
| Unanswerable question | Q16 | Pass | Declined and named the data that's missing |
| Data-quality traps | Q12 Q13 Q14 | All pass | Caught both planted issues |
| Comparisons and lifecycle | Q04 Q06 Q09 | All pass | Right time basis; groups reconcile to the total |
| Cohort conversion | Q07 | Fail → Pass | Used April, the month the subscriber base forms, as a normal baseline; a new skill rule fixed it |
| Funnel drop-off | Q11 | Partial | Right answer and gaps, but read April's start-up as a funnel decline; the new rule didn't trigger here |
| GM investigation | Q02 | Fail → Pass | v1: headline numbers and story right, but some conclusions stated more firmly than the evidence allowed. After review the skill gained three certainty rules; v2 and a blind rerun on the updated skill both passed |

**Hardest:** comparisons that need context the data doesn't announce, such as a start-up month. Details: [evaluation results](../evaluations/results.md).

## 03 Proposed rollout for a 20-person product team

Time to answer (observed): simple 2–3 min, normal 5–6 min, complex 10–12 min.

- **How the team uses it:** analysts and PMs ask in plain English from Claude Code or Codex (later Slack or a web page), all on one shared repository, so definitions and guardrails are the same for every person and model.
- **Set-up:** build a data catalog and metric registry for the team's warehouse, with the analytics lead approving each definition, then the Gold and Silver layers the agent routes to.
- **Cost:** mostly model tokens; local SQLite has no per-query service fee; warehouse costs would depend on the deployment. Not measured here: log tokens per question, then budget by question type. Answering from the smallest layer that fits keeps both cost and latency down.
- **Guardrails:** read-only access (database role plus the query tool's check), row and time limits, an evidence log behind every figure, no sensitive columns in the catalog, and a question back when the ask is unclear.
- **Freshness:** real data keeps arriving, unlike this dataset; the production integration should supply a freshness tracker that the agent checks (last load per source and layer) and warns or stops when data is stale.
- **Quality over time:** a test set of questions with known answers (these 18, growing from real ones), rerun on every change to the skill, definitions or data; track pass rate, clarification rate, query errors and user ratings; turn failures into rules.

## 04 With more time

- Run the same questions in both runtimes for a direct Claude vs Codex comparison, plus held-out questions.
- Measure tokens and time per question to put a real cost on each question type.
- A helper that drafts the catalog and metric registry for a new database; a Slack or web front end.

*Note on tools:* Claude Code (Claude Opus 5.5, medium) built the framework, ran the GM investigation and computed the answer key. Codex (GPT Terra 6.1, medium) ran the evaluation. ChatGPT (Terra 5.6, later 6.1, medium) reviewed the GM report and evaluation decisions independently.
