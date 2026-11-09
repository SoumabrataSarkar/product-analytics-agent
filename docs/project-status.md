# Project status and handoff

**Last updated:** 2026-11-09 UTC (2026-11-09 IST).  
**Repository:** `SoumabrataSarkar/product-analytics-agent` (private).  
**Current focus:** Continue the PocketToons reference Metric Registry across product metrics and business questions.

This is the common project progress and handoff record. The frozen architecture describes the intended reusable framework; the current catalog, data model, metric definitions and executable SQL describe the **PocketToons reference dataset**. They are shared between supported agents, not automatically valid for every product or data source.

## At a glance

Dates and times are shown in UTC, with IST (UTC+05:30) in brackets where a precise commit timestamp is available. Soumabrata Sarkar is the project originator and leads the decisions and reviews. The AI tools assist with refinement, implementation and testing; an unknown AI model version does not make Soumabrata's contribution uncertain. See the [contribution and date record](#contribution-and-date-record) for details and commit links.

| Step | Status | In short | Contributors and time |
|---|---|---|---|
| [Agent architecture](architecture/v1.md) · [ADRs](architecture/decisions/) | Design frozen | Soumabrata Sarkar proposed the agent flow, data layers, catalog and registry; AI assisted in refinement. | Soumabrata Sarkar and AI assistance; architecture recorded 2026-11-07 07:15 UTC (12:45 IST). [Record](#contribution-and-date-record) |
| [PocketToons data model](examples/pockettoons-reference-data-model-v1.md) · [generator](../examples/pockettoons/generate.py) · [dataset guide](../examples/pockettoons/README.md) | Available | Soumabrata specified and refined the example's journeys, relationships and data; AI assisted with generation and checks. | Soumabrata Sarkar with AI assistance; early generator commit 2026-11-07 14:11 UTC (19:41 IST). [Record](#contribution-and-date-record) |
| [PocketToons data catalog](examples/pockettoons-data-catalog.md) | Reviewed for this stage | Soumabrata read and manually reviewed the catalog in depth, raised gaps and approved the changes; AI collaborators assisted with updates and tests. | Soumabrata Sarkar with Codex and Claude contributions; catalog began 2026-11-08 09:31 UTC (15:01 IST). [Record](#contribution-and-date-record) |
| [PocketToons metric registry](metrics/metric-registry.md) | In progress | Project-specific metric definitions and SQL are approved individually. | Soumabrata Sarkar and Claude; template recorded 2026-11-08 19:40 UTC (2026-11-09 01:10 IST). [Record](#contribution-and-date-record) |
| [Investigation and evaluation paths](evaluations/investigation-paths.md) | Design draft | Connects candidate questions to checks, data and safeguards; not an implemented agent or evaluation suite. | Soumabrata Sarkar and Codex; recorded 2026-11-08 20:54 UTC (2026-11-09 02:24 IST). [Record](#contribution-and-date-record) |
| [Static documentation explorer](../web/index.html) | Available as prototype | Explains the project; it does not run the agent or connect to a model. | Soumabrata Sarkar and AI assistance; recent Codex update 2026-11-09 04:42 UTC (10:12 IST). [Record](#contribution-and-date-record) |
| Data layers, agent and evaluation | In progress | Some layer transformations and foundational query/evidence tools exist; the shared investigation skill and independent evaluation remain pending. | Led by Soumabrata Sarkar with AI assistance. |

The [contribution record](#contribution-and-date-record) includes links to representative commits; the detailed sections below retain decisions and limitations.

## Scope and current file placement

- **Common project:** This file, [Architecture v1](architecture/v1.md) and the architecture decision records describe project-wide status or the intended framework. An ADR is an Architecture Decision Record: a document explaining an important design choice and its trade-offs.
- **PocketToons-specific:** The [reference data model](examples/pockettoons-reference-data-model-v1.md), [data catalog](examples/pockettoons-data-catalog.md), [metric registry](metrics/metric-registry.md) and `examples/pockettoons/` code describe or use this example's data and business decisions. The registry is shared across agent runtimes; its current SQL and approved definitions must not be assumed valid for a different product.
- **Current placement:** These links reflect the repository as it exists. The catalog already lives under `docs/examples/`; the metric registry currently lives under `docs/metrics/` even though its current definitions use the PocketToons fixture. A future per-project organization can make that distinction more explicit. No folder migration or new paths are decided here.
- **Authority:** The catalog and reference model govern their documented dataset; approved metric definitions are in the registry. A different dataset needs its own reviewed definitions, mappings, limitations and source contracts.

## Completed and accepted for this stage

1. **Architecture v1:** Frozen design and ADRs define an LLM-neutral, evidence-led analytics workflow, bounded investigation and logical Bronze/Silver/Gold layers. The architecture is a design baseline, not a running agent.
2. **Reference data model:** The PocketToons example provides a detailed relational model, business rules, temporal relationships and safeguards. It is a reference fixture for a generalized analytics framework, not a claim that the agent is specific to one product.
3. **Synthetic data:** A deterministic Python generator, SQLite fixture and validation suite cover users, sessions, content, subscriptions, payments, refunds, events, attribution and intentional data-quality issues. The issue log records generation issues, analytical impact and resolution/limits.
4. **Data catalog:** All 20 current fixture tables have catalog entries. Soumabrata Sarkar personally read and reviewed the catalog in depth, identified gaps, requested and approved changes, and accepted the earlier reviewed tables without repeating the review. The main event, payment-quality, marketing and identity checks have also been reviewed. This is acceptance for the current stage, not a claim of complete production coverage or machine-readable agent integration.
5. **Recent event and payment safeguards:** Event timestamps and properties, episode links, paywall/checkout links, refund and subscription links, raw-payment coverage and units, and review timestamp handling have documented checks and targeted tests.
6. **Marketing and identities:** Marketing uses UTC reporting days, valid non-negative spend/counts, a fanout-safe day/channel comparison and separately seeded daily variation. Shared-device account switches start new sessions; identity lifetime and observed link/session checks are documented and tested.
7. **Static visual explorer:** `web/index.html` is a documentation prototype, not a connected AI frontend or working agent.

The full fixture checker and targeted tests passed on the local fixture snapshots tested during this work. The current generator may be newer than those snapshots; regenerate and validate the exact version used. Synthetic data does not establish causal relationships, and some edge cases are represented only in isolated tests.

## Pending work

1. **PocketToons Metric Registry — in progress.** As recorded in this handoff, the [registry](metrics/metric-registry.md) template, variant rule and MAU (`mau`) are approved; MAU's canonical SQL is run by the fixture checker and isolated tests. The activity family (DAU, WAU, DEU, WEU, MEU), stickiness, engagement rate and monthly growth accounting are approved. The revenue group (net, subscription and PPV net revenue, ARPU, ARPPU) is approved at v1.1, which excludes invalid amounts and ambiguous double successes rather than rounding them. The funnel and lifecycle group (conversion, churn, retention, paywall funnel, marketing CTR) is approved; MAU v1.1 adds subscriber-status slicing. The registry's metric map lists the remaining planned metrics and what the data does not support; the engagement group is approved. The supporting activity, monetisation, lifecycle and marketing metrics are approved, completing the metric map. Check the registry itself for the latest status. Define the remaining metrics with the user one at a time. For each definition cover business meaning, population, numerator/denominator where applicable, grain, timestamps/timezone, eligible data, source tables and layers, canonical calculation/SQL, filters, nulls, payment/refund/status rules, aggregation safety, quality checks, version and caveats. Do not assume an unresolved definition.
2. **Data layers — in progress.** The dataset-independent [layer build workflow](data-layers/layer-build-workflow.md) records the method, contract format, safety rules and known blockers. In the [PocketToons layer contracts](data-layers/pockettoons-layer-contracts.md), Bronze views over all 20 classified source tables, `layer_build_log`, `silver_resolved_sessions`, `silver_payment_attempts`, `silver_subscription_access`, `silver_user_profile`, `silver_user_day_activity`, `silver_user_day_title_watch` and `silver_user_episodes` are approved and built by `examples/pockettoons/build_layers.py` with reconciliation and tests. Next: the remaining Silver contracts one at a time, then Gold designed from supported questions. The builder has been verified on a copy only; applying it to the reviewed local database requires a separate decision.
3. **Shared agent tools and workflow.** Bounded read-only SQL and local evidence-log foundations exist with tests. The [shared investigation skill](../skills/product-analytics-investigation/SKILL.md) directs Codex and Claude Code to use the catalog, registry and query/evidence command. Its end-to-end behavior, layer selection and clarification handling need independent evaluation. The experimental Python investigation loop has only scripted tests. These foundations do not yet establish a verified working end-to-end agent.
4. **Evaluation.** The [investigation paths](evaluations/investigation-paths.md) document contains a draft decision graph and 16 scenarios. Implement and run independent evaluations, including expected results, quality traps, ambiguity and failure cases; compare supported runtimes on a fixed dataset. Keep expected synthetic findings out of the agent's independent investigation context.
5. **Outputs and optional UI.** Implement the evidence-backed report; pursue connected web or other UI work only when requested and with a secure backend.
6. **Catalog follow-through.** Integrate the reviewed catalog with the agent and choose a machine-readable representation if needed. Preserve documented limitations, including incomplete historical review versions, source coverage, unsupported bundle cases and attribution uncertainty.

### Future idea: project-specific knowledge-base updater

This is an idea for later discussion, not an implemented or approved architecture change. When connecting another data source, a future updater could inspect the available schema and ask the user about business definitions, joins, time rules, exceptions and data-quality expectations. It could then propose a project-specific catalog, metric registry and mappings for the user to review and approve.

Definitions from one project should not silently overwrite or become assumptions for another. Generated changes would need validation, versioning and user approval, with access and sensitive-data safeguards. The updater's architecture and the eventual folder structure remain to be designed.

The order of dependent work may be refined with the user; do not represent planned components as implemented.

## Data location and reproduction

The reviewed SQLite file is a local artifact, not a committed GitHub file. Earlier local copies, such as `pockettoons-marketing-variation.sqlite`, predate the activity-realism generator changes; generate a new copy (about 0.66 GB) to obtain the current fixture. A fresh database can be created and checked from repository code:

```sh
python3 examples/pockettoons/generate.py --output pockettoons.sqlite
python3 examples/pockettoons/check_data.py pockettoons.sqlite
```

The generator **creates a new database file** at the path supplied after `--output`; if no path is supplied, it uses `pockettoons.sqlite` in the current working directory. It refuses to run when that file already exists so an existing database, including manual changes, is not silently overwritten. Choose a new filename to generate another copy.

The checker reads the specific file path passed to it; in the example above, both commands refer to the new `pockettoons.sqlite`. Changing generator code changes what a **future** generation produces; it does not update a database file that already exists. Direct, approved changes to an existing database affect that specific copy and must also be represented in the generator or a documented migration if they should be reproducible. Record the generator version, seeds and any separate changes for the exact fixture being analyzed.

The main seed is 8126; marketing uses an independent seed, 10844. The current generator also uses other independent streams for specific behavior. Seeds make the generator's random selections repeatable for the same generator version and compatible environment; they do not contain the database. Review completion times are NULL when unknown. The sample fixture is synthetic; the logical layers and agent are separate work.

## Contribution and date record

**Project ownership and review:** Soumabrata Sarkar conceived and proposed the agent architecture, including its workflow, Bronze/Silver/Gold layers, data catalog and metric registry. Soumabrata set the business direction, personally reviewed the data catalog in depth, identified gaps and approved changes. Codex, Claude and other AI assistance supported refinement, implementation, documentation and testing under Soumabrata's direction.

UTC is shown first; IST is in brackets. The times below are **representative Git commit timestamps**, not exact times of every discussion, review or approval. The Git author does not by itself identify an AI model. Where an AI model is marked unverified, only its exact identity is unknown—not Soumabrata's contribution.

| Representative time: UTC (IST) | Contributors and work | Evidence |
|---|---|---|
| 2026-11-07 07:15:03 UTC (2026-11-07 12:45:03 IST) | Soumabrata Sarkar proposed and directed the architecture; AI assisted with refinement. Exact AI model version not reliably recorded. | [Frozen Architecture v1](architecture/v1.md) · [architecture commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/f355fbff) |
| 2026-11-07 12:43:02 UTC (2026-11-07 18:13:02 IST) | Soumabrata Sarkar specified and refined the PocketToons model and journeys with AI assistance. Exact AI model attribution for every edit is not available. | [Reference data model](examples/pockettoons-reference-data-model-v1.md) · [model scope commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/975382de) |
| 2026-11-07 14:11:46 UTC (2026-11-07 19:41:46 IST) | Soumabrata Sarkar guided synthetic-data requirements and reviews; AI assisted in building the generator and checks. | [Generator](../examples/pockettoons/generate.py) · [prototype commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/162e503b) · [generation issue log](examples/pockettoons-data-generation-issue-log.md) |
| 2026-11-08 09:31:13 UTC (2026-11-08 15:01:13 IST); continued across later sessions | Soumabrata Sarkar personally reviewed the catalog table by table, raised issues, guided fixes and approved decisions; Codex and Claude assisted on documented changes and checks. Individual manual review times are not recorded. | [Data catalog](examples/pockettoons-data-catalog.md) · [initial catalog commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/eefd2952) · [example subsequent check](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/b4b61a3b) |
| 2026-11-08 11:57:58–12:11:05 UTC (2026-11-08 17:27:58–17:41:05 IST) | Soumabrata Sarkar directed the PPV entitlement review; Claude Opus 5.5 is identified in commit co-author metadata for the example entitlement fixes and tests. | [Entitlement-start commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/35981da0) · [snapshot test commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/dc5ec726) |
| 2026-11-08 17:12:34–19:24:53 UTC (2026-11-08 22:42:34–2026-11-09 00:54:53 IST) | Soumabrata Sarkar reviewed decisions; Codex assisted with event, payment-quality, marketing and shared-device checks. Codex's exact model version is not recorded in commit metadata. | [Event JSON check](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/46937e32) · [identity lifetime check](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/1aa56d7b) · [Data catalog](examples/pockettoons-data-catalog.md) |
| 2026-11-08 19:40:01 UTC (2026-11-09 01:10:01 IST); ongoing | Soumabrata Sarkar reviews and approves metric decisions; Claude Opus 5.5 is identified in the template commit's co-author metadata. | [Metric Registry](metrics/metric-registry.md) · [template commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/7187b3bb) |
| 2026-11-08 20:54:29 UTC (2026-11-09 02:24:29 IST) | Soumabrata Sarkar requested the connected investigation/evaluation design; Codex assisted in documenting it. | [Investigation paths](evaluations/investigation-paths.md) · [design commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/936ee0c8) |
| 2026-11-09 04:42:15 UTC (2026-11-09 10:12:15 IST) | Soumabrata Sarkar directed the explorer improvements; Codex assisted with the day/night interface. | [HTML explorer](../web/index.html) · [day/night commit](https://github.com/SoumabrataSarkar/product-analytics-agent/commit/9d2e0708) |

Use the linked commits and Git history for exact changes. Discussion and manual review timestamps are not inferred from commit times.

## Instructions for the next collaborator

- Read `AGENTS.md`, `CLAUDE.md`, the frozen `docs/architecture/v1.md`, relevant ADRs, `docs/examples/pockettoons-data-catalog.md` and `docs/examples/pockettoons-reference-data-model-v1.md`.
- Continue the Metric Registry from its current progress, prioritizing metrics and business questions with the user. Explain the problem and recommendation in short, simple language; ask the user to confirm material choices before locking them in. Work one item at a time.
- Keep shared analytical definitions model-neutral. Do not implement separate Claude-only metric logic, silently invent metric semantics, or reopen accepted catalog tables without a concrete issue.
- Distinguish implemented code and tests from proposed behavior; do not claim the agent or data layers already work.
- Do not edit frozen Architecture v1. Any architecture change requires the documented ADR/version process.
- Write contracts as direct final descriptions. Reserve issue/impact/resolution history for the issue log; do not add unsolicited interview coaching.
- Avoid assumptions of causation, silent quality corrections, cross-session identity claims or fact-join fanout. Preserve raw values and distinguish unknown review times from known historical availability.
- Keep the repository private and avoid committing confidential assignment materials, secrets or API keys.
