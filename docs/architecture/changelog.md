# Architecture history

## v1.0 — 2026-11-07 — Frozen design baseline
**State:** Designed, not implemented or measured.

**Decisions:** Interchangeable Claude Code/Codex runtime; shared analytics skill, Metric Registry and Data Catalog; logical SQLite Bronze/Silver/Gold layers; audited read-only SQL; autonomous evidence-led hypothesis workflow (three rounds × up to three hypotheses, early stop, human handoff); standardized reports and 15+ question evaluation; future visualization and chat workbench.

**Known risks:** Model-dependent paths and explanations; data freshness and join fanout; unanswerable questions; confidential-public boundary; browser runtime versus secure server execution; user installation portability.

## Future version entry
- Version / date / status:
- Problem discovered in previous version:
- Supporting baseline tests and failures:
- Architecture components added/changed/removed:
- Alternatives and reason for decision:
- Migration/compatibility effects:
- Same-snapshot evaluation setup:
- Before/after metrics and regressions:
- Remaining limitations:
- Related ADRs and commits:
