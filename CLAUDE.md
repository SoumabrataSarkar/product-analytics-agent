# Claude Code entrypoint

Read [AGENTS.md](AGENTS.md), [project status and handoff](docs/project-status.md) and [Architecture v1.0](docs/architecture/v1.md) first. Follow the same agent-neutral metrics, data catalog, evidence and safety contracts as Codex. The current metric registry and data catalog describe the PocketToons fixture; do not assume they apply unchanged to another project. Do not create divergent Claude-specific business logic.

**Status:** The architecture is frozen. For the PocketToons fixture, the catalog is accepted, the metric registry is complete and the Bronze/Silver/Gold layers are built and reconciled; the reviewed database with all layers is local. The query/evidence tools and shared investigation skill exist, and independent evaluation of the agent is next. Follow the current file locations in AGENTS.md; defer any reorganization until requested.
