# Submission: start here

| Deliverable | Where |
|---|---|
| Board-ready analysis of the GM question (9 pages) | [board-report.pdf](board-report.pdf) |
| The agent's first version of that analysis, before review | [board-report-v1-raw.pdf](board-report-v1-raw.pdf). The review feedback and what changed: [Q02 feedback](../evaluation-results/Q02/run-001/feedback.md) · [v1 vs v2](../evaluation-results/Q02/run-001/v1-vs-v2-changes.md) |
| One-page write-up | [write-up.pdf](write-up.pdf) ([markdown](../docs/deliverables/write-up.md)) |
| Eval: 18 questions, expected vs actual, pass/fail, failure analysis | [eval-results.pdf](eval-results.pdf) (detailed, 4 pages) · [results.md](../docs/evaluations/results.md); evidence in [evaluation-results/](../evaluation-results/) |
| Setup instructions | [QUICKSTART.md](../QUICKSTART.md) (clone, download the database, first question) · [SETUP.md](../SETUP.md) (full setup, regeneration, tests) |
| Agent source code | Clone the whole repository; the table below identifies the working components |
| HTML reference | Download [web/index.html](../web/index.html) and open it in a browser; setup and the first prompt are included |
| Data: generator, checks and layer builder | [examples/pockettoons/](../examples/pockettoons/) · [data catalog](../docs/examples/pockettoons-data-catalog.md) · [metric registry](../docs/metrics/metric-registry.md) |

Both versions of the board report were written by the agent (Claude Code, Claude Opus 5.5). v1 is its independent output; v2 is its revision after a review against the evidence and source data. The first-round score applies to v1. The reviewed revision and a separate fresh blind rerun are recorded as distinct follow-up results.

## Agent source code

The agent runs inside Codex or Claude Code: the coding agent does the reasoning, and this repository supplies the shared instructions, analytical definitions and tools it uses. Evaluation documents the tested behavior and its limits.

| Part | Files | What it does |
|---|---|---|
| Entry points | [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md) | Shared rules every run reads, for Codex and Claude Code |
| Investigation method | [skills/product-analytics-investigation/SKILL.md](../skills/product-analytics-investigation/SKILL.md) | Clarify, verify definitions, choose a layer, test hypotheses, separate pattern from cause, report |
| Definitions | [data catalog](../docs/examples/pockettoons-data-catalog.md), [metric registry](../docs/metrics/metric-registry.md), [layer contracts](../docs/data-layers/pockettoons-layer-contracts.md) | Approved metrics with canonical SQL; tables, grains, joins and known gaps |
| Query and evidence tools | [tools/safe_query.py](../tools/safe_query.py), [tools/evidence_log.py](../tools/evidence_log.py), [tools/evidence_query.py](../tools/evidence_query.py) | Read-only, bounded SQL; one evidence log per query |
| Report | [tools/report_pdf.py](../tools/report_pdf.py) | Fixed-template PDF, at most 10 pages |
| Experimental loop | [tools/investigation.py](../tools/investigation.py) | Model-neutral loop with round and hypothesis limits; scripted tests only, not the evaluated agent |
| Data pipeline | [examples/pockettoons/](../examples/pockettoons/): `generate.py`, `check_data.py`, `build_layers.py`, `metric_registry.py` | Synthetic data generator, 186 data checks, Bronze/Silver/Gold builder with 122 reconciliation checks |
| Tests | `tools/test_*.py` (29), `examples/pockettoons/test_*.py` (218) | Run as shown in [SETUP.md](../SETUP.md#check-the-installation) |
