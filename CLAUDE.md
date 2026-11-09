# Claude Code entrypoint

Read [AGENTS.md](AGENTS.md), [project status and handoff](docs/project-status.md) and [Architecture v1.0](docs/architecture/v1.md) first. Follow the same agent-neutral metrics, data catalog, evidence and safety contracts as Codex. The current metric registry and data catalog describe the PocketToons fixture; do not assume they apply unchanged to another project. Do not create divergent Claude-specific business logic.

**Status:** The architecture is frozen, the catalog is accepted for this stage, and a synthetic SQLite generator and checks are committed. The reviewed database is local; the PocketToons metric registry is in progress, while data-layer transformations and the working analytics agent remain pending. Follow the current file locations in AGENTS.md; defer any reorganization until requested.
