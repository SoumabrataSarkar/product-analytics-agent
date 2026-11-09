# Shared coding-agent instructions

This file is the common project entrypoint. Architecture v1.0 is a **frozen design**, not an implemented application.

1. Read `docs/architecture/v1.md` and relevant ADRs before making changes.
2. For PocketToons metrics and joins, use the approved definitions in `docs/metrics/metric-registry.md` and the reference catalog at `docs/examples/pockettoons-data-catalog.md`. These files are shared across agent runtimes but are specific to the PocketToons fixture; do not assume they apply to another project. Do not invent denominators, cohorts, join keys or SQL definitions.
3. Keep analytical instructions neutral to Claude Code or Codex; runtime-specific entrypoints should only reference the common logic.
4. Investigate questions via baseline validation and evidence-led hypotheses: up to 3 hypotheses per round × 3 rounds, early stopping, bounded queries and honest human escalation.
5. Require traceable SQL, timeframe, data layer, snapshot, evidence, result and limitations for material findings. Never fabricate a root cause or treat correlation as causation.
6. Choose a validated layer that fits the question and preserves the required detail and evidence. Use Gold only when it exactly fits; otherwise consider Silver, and inspect Bronze/source when raw or other necessary evidence is not sufficiently available or reliable above. Correctness outranks speed, and non-additive metrics must not be summed incorrectly. Ask about material ambiguity instead of silently inventing definitions or business rules.
7. Use read-only/bounded SQL for agent queries, log errors, and keep secrets out of client files.
8. Preserve raw data lineage; transformations and derived metrics must have tests and reconciliation.
9. Do not silently rewrite `docs/architecture/v1.md`: document design changes with new ADRs and a new architecture version.
10. Do not publicly expose confidential assignment text, proprietary data or keys.
11. Documentation must state final requirements, decisions, results and limitations directly and consistently. Do not narrate the sequence of edits, add unsolicited interview coaching, or contrast obsolete drafts with the current design. For issue logs, use a factual issue → analytical impact → resolution/limitation format. Keep established rules in the relevant model or contract so they are applied to future generation.

Do not read `evaluation-results/`, `submission/` or `docs/evaluations/` during an investigation: they contain expected answers and previous reports.

For user-authorized product analytics investigations, read and follow the shared [product analytics investigation skill](skills/product-analytics-investigation/SKILL.md). The skill is common to Codex and Claude Code; its first implementation has not yet been independently evaluated end to end.

## Current repository layout and scope

- `docs/project-status.md` records project-wide progress and links to contribution history.
- `docs/architecture/` contains the frozen shared architecture and decision records.
- `docs/examples/pockettoons-reference-data-model-v1.md` and `docs/examples/pockettoons-data-catalog.md` describe the PocketToons reference data.
- `docs/metrics/metric-registry.md` currently defines metrics and SQL for the PocketToons fixture, shared by supported agent runtimes. It is not a universal registry for other datasets.
- `docs/data-layers/layer-build-workflow.md` is the dataset-independent method for building Bronze/Silver/Gold layers; `docs/data-layers/pockettoons-layer-contracts.md` holds the PocketToons layer table contracts.
- `examples/pockettoons/` holds the example generator, checks and tests; `docs/evaluations/` holds evaluation designs and `results.md`; `evaluation-results/` holds the answer key and scored runs, and `submission/` the assignment deliverables; `web/` holds the static explorer.
- `docs/data-layers/pockettoons-gold-questions.md` lists the questions Gold answers and what it does not support; `docs/deliverables/` holds report and write-up templates; `tools/` and `skills/` hold the query, evidence and investigation tooling.
- Future per-project catalogs, metric registries and an onboarding/updater workflow are not yet implemented. Do not move or rename files without an agreed migration; update references when one is requested.

**Current project status:** Architecture v1 is frozen. For the PocketToons reference dataset, the data catalog is accepted, every metric in the registry's map is approved, and the Bronze, Silver and Gold layers are built and reconciled; the reviewed SQLite file with all layers is local. Read-only query and evidence tools and the shared investigation skill exist. Independent evaluation of the agent is the next stage. See [project status and handoff](docs/project-status.md).
