# ADR-002 — Bronze/Silver/Gold in SQLite

**Accepted:** 2026-11-07 (Architecture v1.0)

## Problem
Repeated raw-event scans are fragile and expensive at larger scale; analyses need documented cleaning, reusable aggregates and audit trails.

## Decision
Use a single SQLite file with logical `bronze_`, `silver_` and `gold_` table prefixes. Source raw rows remain observable; Silver cleans and validates; Gold materializes a small number of trusted metric marts. Layer-selection rules prioritize correct grain and data freshness over speed.

## Trade-offs
This adds transformation/refresh complexity; small demo datasets may not experience noticeable speed improvements. Distinct-user metrics and fact joins require careful non-additive/fanout handling. This demonstrates a scalable *pattern*, not a deployed enterprise warehouse.

## Verification
Reconciliation and quality tests, source-to-trusted traceability, query layer selection tests, cohort and distinct count correctness.
