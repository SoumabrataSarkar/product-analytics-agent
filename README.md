# Product Analytics Agent

An LLM-agnostic product analytics agent using shared analytical skills, metric definitions, and evidence-backed multi-step reasoning to investigate business questions, query data, identify root causes, and recommend actions.

> **Project status:** Architecture v1.0 is frozen. For the PocketToons reference dataset, the data catalog, the metric registry and the Bronze/Silver/Gold data layers are complete and reconciled, and the reviewed database is local. Read-only query and evidence tools and a shared investigation skill exist; independent evaluation of the agent is the next stage.

**Project originator and lead:** Soumabrata Sarkar, with AI assistance for refinement, implementation and documentation. See the [contribution record](docs/project-status.md#contribution-and-date-record) for details.

## Start here

- **[Submission: deliverables and where to find them](submission/README.md)** · [Evaluation results](docs/evaluations/results.md)
- [Setup and reviewer guide](SETUP.md) · [Current architecture implementation](docs/architecture/implementation-status.md)
- [Project status and handoff](docs/project-status.md)
- [PocketToons data catalog](docs/examples/pockettoons-data-catalog.md)
- [PocketToons metric registry](docs/metrics/metric-registry.md)
- [Data layers: build workflow](docs/data-layers/layer-build-workflow.md) · [PocketToons layer contracts](docs/data-layers/pockettoons-layer-contracts.md) · [Gold question list](docs/data-layers/pockettoons-gold-questions.md)
- [Investigation paths and evaluation scenarios](docs/evaluations/investigation-paths.md) · [Evaluation run template](docs/evaluations/evaluation-run-template.md)
- [Deliverable templates](docs/deliverables/)
- [Architecture v1.0 — frozen baseline](docs/architecture/v1.md)
- [Architecture changelog](docs/architecture/changelog.md)
- [Architecture Decision Records](docs/architecture/decisions/)
- [Architecture evaluation template](docs/evaluations/architecture-review-template.md)
- [Coding-agent guidance](AGENTS.md) · [Claude entrypoint](CLAUDE.md)
- [Investigation tools and current status](tools/INVESTIGATION.md)
- [Shared investigation skill](skills/product-analytics-investigation/SKILL.md)
- [PocketToons data-model contract](docs/examples/pockettoons-reference-data-model-v1.md)
- [PocketToons dataset and validation](examples/pockettoons/README.md)
- [Data-generation issue log](docs/examples/pockettoons-data-generation-issue-log.md)
- [Architecture Explorer (HTML)](web/index.html) · [Web scope](web/README.md)

## Current file placement

The architecture under `docs/architecture/` and the project handoff are common to the framework. The current data model and catalog under `docs/examples/`, metric registry under `docs/metrics/`, and generator under `examples/pockettoons/` describe the PocketToons reference dataset. Sharing those definitions between Claude and Codex does not make them automatically applicable to another project. The data-layer workflow under `docs/data-layers/` is dataset-independent; the PocketToons layer contracts and Gold question list there are specific to this dataset. A future project-specific structure and knowledge-base updater are ideas for later; files are not moved without an agreed migration.

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
Gold (8 monthly marts) / Silver (10 validated detail tables) / Bronze (20 source views)
      ↓
Evidence ledger → quantified RCA report and recommendations
```

The planned investigation is autonomous, with at most three rounds of up to three distinct hypotheses; it should stop early when adequately explained or ask for human direction when exhausted. It must not invent causes.

The intended product is a reusable analytics framework operated through the user's own Codex or Claude Code runtime and available model. The runtime follows the shared investigation skill and uses the repository's definitions, catalog and evidence tools with the user's authorized local database. One independent-mode investigation has been reviewed; the broader evaluation remains incomplete. Runtime access depends on the user's chosen tool, model and account.

## Visual explorer

The committed [`web/index.html`](web/index.html) is a **static documentation prototype** showing the directory, data flow, workflow and version history. It is not connected to the database, GitHub APIs or an AI model. Open it locally to inspect the interface. Live chat will require a separately secured execution backend or supported agent runtime.

## Data layers

`examples/pockettoons/build_layers.py` builds all layers inside the same SQLite file in one transaction: 20 Bronze views over the unchanged source tables, 10 Silver tables (resolved sessions, payments, subscription access, user profile, user-day activity, user-day-title watching, user episodes, paywall funnel, daily marketing and quality exceptions) and 8 monthly Gold tables designed from the approved question list. Each build checks the source schema, records a source fingerprint and definition versions in `layer_build_log`, and reconciles every table against the metric registry or an independent recount (122 checks); a failed check rolls the whole build back.

## Remaining work

1. Evaluate the agent independently on at least 15 questions with an evaluator-only answer key, in Codex and Claude Code, and improve the skill and tools from the results.
2. Provide a machine-readable catalog and layer map for the agent.
3. Produce evidence-backed investigation reports and the submission write-up.
4. When requested, secure optional web integration.

The framework is intended for future open-source publication and continued improvements.
