# ADR-001 — LLM-neutral analytics core

**Accepted:** 2026-11-07 (Architecture v1.0)

## Problem
A single project should work with Claude Code and Codex without diverging metric meanings or duplicating analytical logic.

## Decision
Keep shared product analytics skill, Metric Registry, Data Catalog, deterministic Python/SQL tools and output/evidence contracts in model-independent files. `AGENTS.md` and `CLAUDE.md` refer to those shared files. Model-specific runtime instructions may differ, but business logic must not.

## Trade-offs
Shared numbers can be tested; identical natural language output cannot be guaranteed. A standalone web application might later require an authenticated model API/backend, whereas eligible coding-agent runtimes can initially operate through their supported subscription environments.

## Verification
Run identical fixed-snapshot evaluation queries in each supported runtime and compare numerical accuracy, source traces and failure handling.
