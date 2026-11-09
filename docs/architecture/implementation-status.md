# Architecture implementation status

**Scope:** Current implementation of the reusable product analytics framework and the PocketToons reference dataset. This is an implementation map, not a new architecture version. The [v1.0 design](v1.md) is frozen; architectural changes require the established ADR and versioning process.

## Runtime and investigation

| Component | Current state and boundary |
|---|---|
| Agent runtime | The user operates this framework through their own Codex or Claude Code runtime and available model, following the shared [investigation skill](../../skills/product-analytics-investigation/SKILL.md). Model availability, local-file access and permissions depend on that runtime. |
| Catalog and definitions | The [catalog](../examples/pockettoons-data-catalog.md), [registry](../metrics/metric-registry.md) and [layer contracts](../data-layers/pockettoons-layer-contracts.md) describe the PocketToons example. They are shared across runtimes, not universal definitions for other datasets. |
| Reasoning and stopping | The shared skill instructs the coding agent to clarify material ambiguity, investigate evidence-led hypotheses, and observe stopping rules. These instructions are not a deterministic or independently verified guarantee of reasoning. |
| Read-only queries and evidence | [Query and evidence tools](../../tools/INVESTIGATION.md) execute bounded SQLite reads and record SQL, context and optional results. Layer and snapshot labels are supplied by the caller and must be verified; this is not a complete security sandbox. |
| Data storage | The source data and layers are in one local SQLite file. The reviewed file is distributed separately from the repository. |
| Data layers | PocketToons implements 20 Bronze views, 10 Silver tables and 8 Gold tables. Bronze views expose source tables; Silver and Gold are physical tables with build metadata and reconciliation. Consult the contracts and verify the specific build rather than assuming every dataset has these layers. |
| Routing | Use Gold only when validated and suitable for the measure, dimensions, grain, period and evidence; otherwise consider Silver or source/Bronze as needed. Correctness outranks speed. |
| Reports | A coding agent can produce an evidence-backed report. `tools/report_pdf.py` renders it as a fixed-template PDF and refuses reports over 10 pages. Preserve original agent output and identify human-reviewed edits. |
| Evaluation | 18 scenarios were run blind and checked against source-level references. Round 1: 15 pass, 1 partial, 2 fail. After selected reruns, the latest outcome per scenario is 17 pass, 1 partial, 0 fail; the other first-round outcomes carry forward. Q02 used reviewer source checks; Q03’s clarified weekly reference was computed after its run. See [results](../evaluations/results.md). |
| Visual explorer | The repository website is a self-contained reference website, not a connected agent or database interface. |

## Data preparation and investigation flow

A generator creates a new synthetic source database. The source checker and layer builder are separate commands; the builder adds layers to the same database and logs its build and reconciliation. For an investigation, the coding agent reads the applicable contracts, selects a verified layer, runs bounded read-only queries, and records evidence separately from the database.

A downloaded reference database is a fixed snapshot; a generated database can only be treated as equivalent after its source data and relevant definitions are verified. Build IDs, timestamps and SQLite file hashes can differ even if source contents match.

## Known documentation and delivery boundaries

- The frozen blueprint describes the design at approval time and is not a live implementation status report. Use this map, the [project status](../project-status.md) and the code for current implementation details.
- The catalog and registry describe the reviewed fixture, not every possible snapshot. Verify session identity, period coverage and layer build metadata for the database used in each investigation.
- Investigations use a local SQLite file and the user's selected coding-agent runtime. The visual explorer is a self-contained reference website; a project onboarding/updater is a future idea.
- Reproducibility and reviewer handoff must include the exact database or verifiable source fingerprint, relevant code/definition versions, setup instructions, and authorized evidence access. Do not include private answer keys in an agent's independent evaluation context.
