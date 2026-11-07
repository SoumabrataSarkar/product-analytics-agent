# Product Analytics Agent

An LLM-agnostic product analytics agent using shared analytical skills, metric definitions, and evidence-backed multi-step reasoning to investigate business questions, query data, identify root causes, and recommend actions.

> **Project status:** Architecture v1.0 frozen on 2026-11-07; the analytics agent, synthetic database and query tooling are **not implemented yet**. This is initially a **private** repository.

## Start here

- [Architecture v1.0 — frozen baseline](docs/architecture/v1.md)
- [Architecture changelog](docs/architecture/changelog.md)
- [Architecture Decision Records](docs/architecture/decisions/)
- [Architecture evaluation template](docs/evaluations/architecture-review-template.md)
- [Coding-agent guidance](AGENTS.md) · [Claude entrypoint](CLAUDE.md)
- [Architecture Explorer (HTML)](web/index.html) · [Web scope](web/README.md)

## System concept

```text
Business question
      ↓
Claude Code or Codex
      ↓
Shared analytics skill + Metric Registry + Data Catalog
      ↓
Evidence-led hypothesis manager + bounded read-only SQL
      ↓
Gold (trusted metric marts) / Silver (validated detail) / Bronze (raw audit)
      ↓
Evidence ledger → quantified RCA report and recommendations
```

The default investigation is autonomous, with at most three rounds of up to three distinct hypotheses; it stops early when adequately explained, or asks for human direction when exhausted. It never invents causes.

## Visual explorer

The committed [`web/index.html`](web/index.html) is a **static documentation prototype** showing the directory, data flow, workflow and version history. It is not yet connected to the database, GitHub APIs or an AI model. Open it locally to inspect the interface. Live chat will require a separately secured execution backend or supported agent runtime.

## Planned work

1. Data Catalog and canonical Metric Registry.
2. Reproducible synthetic data and Bronze/Silver/Gold SQLite transformations.
3. Shared bounded SQL and evidence tools.
4. Runnable analytical skill and independent evaluation (15+ questions).
5. Board-ready investigation output and secure optional web integration.

The framework is intended for eventual open-source publication. Keep confidential assignment material, keys and private data out of public releases and their Git history. Licensing will be decided before publication.
