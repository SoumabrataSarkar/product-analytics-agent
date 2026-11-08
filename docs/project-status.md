# Project status and handoff

**Last updated:** 2026-11-09 (Asia/Kolkata).  
**Repository:** `SoumabrataSarkar/product-analytics-agent` (private).  
**Current focus:** Extend the shared Metric Registry beyond the approved MAU definition.

This is a progress and handoff record. The data catalog, reference data model and frozen architecture remain the authoritative sources for their respective contracts.

## Completed and accepted for this stage

1. **Architecture v1:** Frozen design and ADRs define an LLM-neutral, evidence-led analytics workflow, bounded investigation and logical Bronze/Silver/Gold layers. The architecture is a design baseline, not a running agent.
2. **Reference data model:** The PocketToons example provides a detailed relational model, business rules, temporal relationships and safeguards. It is a reference fixture for a generalized analytics framework, not a claim that the agent is specific to one product.
3. **Synthetic data:** A deterministic Python generator, SQLite fixture and validation suite cover users, sessions, content, subscriptions, payments, refunds, events, attribution and intentional data-quality issues. The issue log records generation issues, analytical impact and resolution/limits.
4. **Data catalog:** All 20 current fixture tables have catalog entries. The user accepted the earlier reviewed tables and chose not to repeat their review; the main event, payment-quality, marketing and identity checks have also been reviewed. This is acceptance for the current stage, not a claim of complete production coverage or machine-readable agent integration.
5. **Recent event and payment safeguards:** Event timestamps and properties, episode links, paywall/checkout links, refund and subscription links, raw-payment coverage and units, and review timestamp handling have documented checks and targeted tests.
6. **Marketing and identities:** Marketing uses UTC reporting days, valid non-negative spend/counts, a fanout-safe day/channel comparison and separately seeded daily variation. Shared-device account switches start new sessions; identity lifetime and observed link/session checks are documented and tested.
7. **Static visual explorer:** `web/index.html` is a documentation prototype, not a connected AI frontend or working agent.

The full fixture checker and targeted tests passed against the latest local database after the recent checks. Synthetic data does not establish causal relationships, and some edge cases are represented only in isolated tests.

## Pending work

1. **Metric Registry — in progress.** The [registry](metrics/metric-registry.md) template, variant rule and MAU (`mau` v1.0) are approved; MAU's canonical SQL is run by the fixture checker and isolated tests. The activity family (DAU, WAU, DEU, WEU, MEU), stickiness, engagement rate and monthly growth accounting are drafted for review. Define the remaining metrics with the user one at a time. For each definition cover business meaning, population, numerator/denominator where applicable, grain, timestamps/timezone, eligible data, source tables and layers, canonical calculation/SQL, filters, nulls, payment/refund/status rules, aggregation safety, quality checks, version and caveats. Do not assume an unresolved definition.
2. **Data layers.** Design and implement actual Bronze/Silver/Gold transformations, lineage, quality handling, refresh and reconciliations. The catalog's layer assignments are planned; the existing SQLite fixture is not proof that the full layers exist.
3. **Shared agent tools and workflow.** Implement bounded read-only SQL access, evidence logging, layer selection, clarification handling and the shared evidence-led investigation skill.
4. **Evaluation.** Define and run at least 15 questions, expected results, quality traps, ambiguity and failure scenarios; compare supported runtimes on a fixed dataset. Keep expected synthetic findings out of the agent's independent investigation context.
5. **Outputs and optional UI.** Implement the evidence-backed report; pursue connected web or other UI work only when requested and with a secure backend.
6. **Catalog follow-through.** Integrate the reviewed catalog with the agent and choose a machine-readable representation if needed. Preserve documented limitations, including incomplete historical review versions, source coverage, unsupported bundle cases and attribution uncertainty.

The order of dependent work may be refined with the user; do not represent planned components as implemented.

## Data location and reproduction

The reviewed SQLite file is a local artifact, not a committed GitHub file. The latest local copy from this work is named `pockettoons-marketing-variation.sqlite`. A fresh database can be created and checked from repository code:

```sh
python3 examples/pockettoons/generate.py --output pockettoons.sqlite
python3 examples/pockettoons/check_data.py pockettoons.sqlite
```

The generator refuses to overwrite an existing file. The main seed is 8126; marketing uses an independent seed, 10844. Review completion times are NULL when unknown. The sample fixture is synthetic; the logical layers and agent are separate work.

## Contribution and date record

Dates below use Asia/Kolkata. Git commit author names alone do not identify the AI model. Model names are included only where the conversation or commit metadata supports them; earlier work without such evidence is marked unverified.

| Date | Contributor / model | Verified work and evidence |
|---|---|---|
| 2026-11-07 | User with AI assistance; model version not reliably recorded | Architecture v1 frozen; see `docs/architecture/v1.md` and ADRs. |
| By 2026-11-08 | User with AI assistance; per-change model attribution not reliably recorded | Reference model, synthetic generator, checker, issue log and catalog work appear in repository history. Do not infer a model from the Git author. |
| 2026-11-08, approximately 17:27–17:41 | Claude Opus 5.5, **as identified in commit co-author metadata** | PPV entitlement start, duplicate ownership, status/end consistency, PPV purchase restrictions and snapshot-bound checks. Example commits: `35981da0`, `817b12b7`, `02544b45`, `91d8f35f`, `dc5ec726`. |
| 2026-11-08 to 2026-11-09 | Codex in the current chat; exact model version not recorded in commit metadata | Event JSON and link checks; payment source/review contracts; marketing rules and variation; shared-device and identity-lifetime checks. Representative commits: `46937e32`, `463246aa`, `c2c73ef6`, `f5448627`, `1aa56d7b`. |
| 2026-11-09 | Codex in the current chat; exact model version not recorded | This status and handoff record and entrypoint references. |
| 2026-11-09 | Claude Opus 5.5, **as identified in commit co-author metadata** | Metric Registry template, variant rule and approved MAU definition with registry-driven checker SQL and tests. Example commits: `7187b3b`, `6957332`, `f1e8077`. |

Git history contains the exact timestamps and full changes. The user also reported earlier work with GPT and Claude; attribution of every earlier table or file to a specific model cannot be verified from available evidence.

## Instructions for the next collaborator

- Read `AGENTS.md`, `CLAUDE.md`, the frozen `docs/architecture/v1.md`, relevant ADRs, `docs/examples/pockettoons-data-catalog.md` and `docs/examples/pockettoons-reference-data-model-v1.md`.
- Begin with the Metric Registry and propose MAU first. Explain the problem and recommendation in short, simple language; ask the user to confirm material choices before locking them in. Work one item at a time.
- Keep shared analytical definitions model-neutral. Do not implement separate Claude-only metric logic, silently invent metric semantics, or reopen accepted catalog tables without a concrete issue.
- Distinguish implemented code and tests from proposed behavior; do not claim the agent or data layers already work.
- Do not edit frozen Architecture v1. Any architecture change requires the documented ADR/version process.
- Write contracts as direct final descriptions. Reserve issue/impact/resolution history for the issue log; do not add unsolicited interview coaching.
- Avoid assumptions of causation, silent quality corrections, cross-session identity claims or fact-join fanout. Preserve raw values and distinguish unknown review times from known historical availability.
- Keep the repository private and avoid committing confidential assignment materials, secrets or API keys.
