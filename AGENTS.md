# Shared coding-agent instructions

This file is the common project entrypoint. Architecture v1.0 is a **frozen design**, not an implemented application.

1. Read `docs/architecture/v1.md` and relevant ADRs before making changes.
2. For metrics and joins, use the canonical Metric Registry and Data Catalog once implemented. Do not invent denominators, cohorts, join keys or SQL definitions.
3. Keep analytical instructions neutral to Claude Code or Codex; runtime-specific entrypoints should only reference the common logic.
4. Investigate questions via baseline validation and evidence-led hypotheses: up to 3 hypotheses per round × 3 rounds, early stopping, bounded queries and honest human escalation.
5. Require traceable SQL, timeframe, data layer, snapshot, evidence, result and limitations for material findings. Never fabricate a root cause or treat correlation as causation.
6. Gold for supported aggregates; Silver for trusted details; Bronze for audit/debugging. Correctness outranks speed, and non-additive metrics must not be summed incorrectly.
7. Use read-only/bounded SQL for agent queries, log errors, and keep secrets out of client files.
8. Preserve raw data lineage; transformations and derived metrics must have tests and reconciliation.
9. Do not silently rewrite `docs/architecture/v1.md`: document design changes with new ADRs and a new architecture version.
10. Do not publicly expose confidential assignment text, proprietary data or keys.

**Current project status:** Design documentation only; SQL tooling, database, evaluation and web UI are pending.
