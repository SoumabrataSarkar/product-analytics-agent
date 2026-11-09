# Write-up

The formatted one-page version is [`submission/write-up.pdf`](../../submission/write-up.pdf), built by [`build_write_up.py`](build_write_up.py). This file mirrors its text.

## 01 What I built and why

One investigation runs in six steps: **clarify** (metric, period, population; asks if ambiguous) → **verify the definition** (the metric exists, with its approved definition in the registry and catalog) → **route to a layer** (Gold if it fits, Silver for detail, Bronze for raw audits) → **query with evidence** (read-only, bounded, one log per query) → **test hypotheses** (up to 3 per round, 3 rounds) → **report** (pattern ≠ cause; fixed PDF template, at most 10 pages). Every run, in Claude Code or Codex, reads the same `AGENTS.md`, `SKILL.md`, data catalog and metric registry. The SQLite database holds 8 Gold tables, 10 Silver tables and 20 Bronze views, built in one transaction with 122 reconciliation checks.

- **Clarifies instead of assuming.** When the metric, period or meaning is open, it asks first, as it did in all four evaluation questions that needed it, and it states every assumption it keeps.
- **Verifies the metric before computing it.** It checks that the metric exists and reads its approved, versioned definition and SQL in the metric registry, plus grains, joins and known gaps in the data catalog. Unsupported requests are declined, not improvised.
- **Maps the question to a layer for speed.** Gold answers standard monthly questions in milliseconds and is reconciled; Silver keeps per-user and per-event detail; Bronze is used only to audit raw values.
- **Evidence for every number.** Each query writes its SQL, layer, metric version and row count to its own log.
- **LLM-neutral by design.** Definitions, rules and guardrails live in files, not prompts, so Claude Code and Codex behave the same and a failure becomes a rule that every later run reads. Trade-off: no UI; quality depends on the agent following the skill.

**Tools.** Claude Code (Claude Opus 5.5, medium) built the framework, ran the GM investigation and computed the answer key. Codex (GPT Terra 6.1, medium) ran 17 of 18 evaluation runs. ChatGPT (Terra 5.6, later 6.1, medium) was the independent reviewer.

## 02 Where it breaks: before and after one improvement round

| Failure mode | Where | Round 1 | What changed | Round 2 |
|---|---|---|---|---|
| Stating a cause the data can't prove; mixed comparison periods | GM report v1 (Q02) | Fail | Skill rules: pattern ≠ cause; exact periods; quantify or say "unknown" | Not seen again in 17 later runs |
| First month used as a normal baseline (subscriber base starts at zero) | Q07 cohorts | Fail | Rule: check for a start-up period before using it as a baseline | Pass |
| Same, in a trend description | Q11 funnel | Partial | (same rule) | Partial: rule didn't trigger |
| Harmless registry-version warning repeated | All runs | 18 of 18 | Change verified as docs-only and recorded | 3 of 4 |
| **Overall, 18 questions (pass / partial / fail)** | | **15 / 1 / 2** | | **16 / 1 / 1** |

**Hardest:** comparisons that need context the data doesn't announce, such as a start-up month. **Strongest:** ambiguity and traps. Details: [evaluation results](../evaluations/results.md).

## 03 Running it for a 20-person product team

| Question type | Example | Time to answer (observed) |
|---|---|---|
| Simple | MAU by month; US subscribers | 2–3 minutes |
| Normal | Refund impact; funnel drop-off | 5–6 minutes |
| Complex | MAU up 20% but revenue flat: why? | 10–12 minutes, report included |

- **Access and guardrails:** a read-only role on a warehouse replica; the query tool's limits stay on; sensitive columns kept out of the catalog (not built yet).
- **Cost:** not measured here; log tokens per run before setting a per-question budget.
- **Quality over time:** the 18 questions become a regression suite, rerun whenever the skill, registry or data model changes; track pass rate, clarification rate and query errors; review a weekly sample of real questions.

## 04 With more time

- Make the start-up check apply whenever the first month looks unusual, not only when choosing a baseline (the remaining Q11 issue).
- Run the same questions in both runtimes for a direct Claude vs Codex comparison; add held-out questions.
- Measure cost per run; a short-answer mode for simple questions; a machine-readable catalog; a simple UI.
