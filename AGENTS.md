# Shared coding-agent instructions

This file is the common project entrypoint. Architecture v1.0 is a **frozen design**, not an implemented application.

1. Read `docs/architecture/v1.md` and relevant ADRs before making changes.
2. For PocketToons metrics and joins, use the approved definitions in `docs/metrics/metric-registry.md` and the reference catalog at `docs/examples/pockettoons-data-catalog.md`. These files are shared across agent runtimes but are specific to the PocketToons fixture; do not assume they apply to another project. Do not invent denominators, cohorts, join keys or SQL definitions.
3. Keep analytical instructions neutral to Claude Code or Codex; runtime-specific entrypoints should only reference the common logic.
4. Investigate questions via baseline validation and evidence-led hypotheses: up to 3 hypotheses per round × 3 rounds, early stopping, bounded queries and honest human escalation.
5. Require traceable SQL, timeframe, data layer, snapshot, evidence, result and limitations for material findings. Never fabricate a root cause or treat correlation as causation.
6. Gold for supported aggregates; Silver for trusted details; Bronze for audit/debugging. Correctness outranks speed, and non-additive metrics must not be summed incorrectly.
7. Use read-only/bounded SQL for agent queries, log errors, and keep secrets out of client files.
8. Preserve raw data lineage; transformations and derived metrics must have tests and reconciliation.
9. Do not silently rewrite `docs/architecture/v1.md`: document design changes with new ADRs and a new architecture version.
10. Do not publicly expose confidential assignment text, proprietary data or keys.
11. Documentation must state final requirements, decisions, results and limitations directly and consistently. Do not narrate the sequence of edits, add unsolicited interview coaching, or contrast obsolete drafts with the current design. For issue logs, use a factual issue → analytical impact → resolution/limitation format. Keep established rules in the relevant model or contract so they are applied to future generation.

## Current repository layout and scope

- `docs/project-status.md` records project-wide progress and links to contribution history.
- `docs/architecture/` contains the frozen shared architecture and decision records.
- `docs/examples/pockettoons-reference-data-model-v1.md` and `docs/examples/pockettoons-data-catalog.md` describe the PocketToons reference data.
- `docs/metrics/metric-registry.md` currently defines metrics and SQL for the PocketToons fixture, shared by supported agent runtimes. It is not a universal registry for other datasets.
- `docs/data-layers/layer-build-workflow.md` is the dataset-independent method for building Bronze/Silver/Gold layers; `docs/data-layers/pockettoons-layer-contracts.md` holds the PocketToons layer table contracts.
- `examples/pockettoons/` holds the example generator, checks and tests; `docs/evaluations/` holds evaluation designs; `web/` holds the static explorer.
- Future per-project catalogs, metric registries and an onboarding/updater workflow are not yet implemented. Do not move or rename files while the current registry work is in progress; agree on a migration and update references when requested.

**Current project status:** Architecture v1 is frozen. The PocketToons reference data catalog is accepted for this stage; the fixture generator and validation checks are available, and the reviewed SQLite files are local. The PocketToons metric registry is in progress. The data-layer transformations, analytics agent, shared SQL tooling and evaluation remain pending. See [project status and handoff](docs/project-status.md).
