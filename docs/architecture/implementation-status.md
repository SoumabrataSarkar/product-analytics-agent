# Architecture implementation status

**Scope:** Current implementation of the reusable product analytics framework and the PocketToons reference dataset. This is an implementation map, not a new architecture version. The [v1.0 design](v1.md) is frozen; architectural changes require the established ADR and versioning process.

## Runtime and investigation

| Component | Current state and boundary |
|---|---|
| Agent runtime | The user operates this framework through their own Codex or Claude Code runtime and available model, following the shared [investigation skill](../../skills/product-analytics-investigation/SKILL.md). Model availability, local-file access and permissions depend on that runtime. No separate standalone model service or custom API is required for this workflow. |
| Catalog and definitions | The [catalog](../examples/pockettoons-data-catalog.md), [registry](../metrics/metric-registry.md) and [layer contracts](../data-layers/pockettoons-layer-contracts.md) describe the PocketToons example. They are shared across runtimes, not universal definitions for other datasets. |
| Reasoning and stopping | The shared skill instructs the coding agent to clarify material ambiguity, investigate evidence-led hypotheses, and observe stopping rules. These instructions are not a deterministic or independently verified guarantee of reasoning. |
| Read-only queries and evidence | [Query and evidence tools](../../tools/INVESTIGATION.md) execute bounded SQLite reads and record SQL, context and optional results. Layer and snapshot labels are supplied by the caller and must be verified; this is not a complete security sandbox. |
| Data storage | The source data and layers are in one local SQLite file. The reviewed file is distributed separately from the repository. |
| Data layers | PocketToons implements 20 Bronze views, 10 Silver tables and 8 Gold tables. Bronze views expose source tables; Silver and Gold are physical tables with build metadata and reconciliation. Consult the contracts and verify the specific build rather than assuming every dataset has these layers. |
| Routing | Use Gold only when validated and suitable for the measure, dimensions, grain, period and evidence; otherwise consider Silver or source/Bronze as needed. Correctness outranks speed. |
| Reports | A coding agent can produce an evidence-backed report. A PDF generator is proposed in an open pull request and is not part of the main branch until merged. Preserve original agent output and identify human-reviewed edits. |
| Evaluation | A first independent-mode MAU/revenue investigation was run and reviewed; the original report had material failures and a corrected report was produced after feedback. The broader 15+ question evaluation is not yet complete. |
| Visual explorer | The repository website is a static documentation prototype, not a connected agent or database interface. |

## Data preparation and investigation flow

A generator creates a new synthetic source database. The source checker and layer builder are separate commands; the builder adds layers to the same database and logs its build and reconciliation. For an investigation, the coding agent reads the applicable contracts, selects a verified layer, runs bounded read-only queries, and records evidence separately from the database.

A downloaded reference database is a fixed snapshot; a generated database can only be treated as equivalent after its source data and relevant definitions are verified. Build IDs, timestamps and SQLite file hashes can differ even if source contents match.

## Known documentation and delivery boundaries

- The frozen blueprint describes the design at approval time and is not a live implementation status report. Use this map, the [project status](../project-status.md) and the code for current implementation details.
- Some older registry and catalog passages need review against the current fixture, including the MAU caveat about unidentified sessions. Do not infer the current data from an outdated caveat.
- The current assessment uses a local SQLite file and an external coding-agent runtime. The repository does not provide an autonomous hosted service, a guaranteed model connection, a live database-connected web app, or a project onboarding/updater.
- Reproducibility and reviewer handoff must include the exact database or verifiable source fingerprint, relevant code/definition versions, setup instructions, and authorized evidence access. Do not include private answer keys in an agent's independent evaluation context.
