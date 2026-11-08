# Metric Registry

**Scope:** Shared, model-neutral metric definitions for the analytics agent. Claude Code and Codex use the same definitions; runtime-specific instructions must not redefine them.

**Status of this registry:** Template agreed. Metric definitions are added one at a time and are approved individually by the user. The Gold/Silver tables named in a definition are planned unless stated otherwise; the registry is not yet integrated with a working agent.

## Registry rules

- Each metric has an `id`, a `version` and a `status`. `draft` means under review and not to be relied on. `approved` means the user has accepted the definition. A material change to an approved definition increases its version.
- Canonical SQL runs against the current PocketToons SQLite fixture tables unless it names a planned layer table, which is marked as planned.
- The registry contains definitions only. Expected values for the synthetic fixture belong in tests or evaluation files kept outside the agent's investigation context.
- Table meanings, keys and joins come from the [data catalog](../examples/pockettoons-data-catalog.md) and the [reference data model](../examples/pockettoons-reference-data-model-v1.md). A metric definition must not contradict them.
- Each quality check is marked **implemented and tested** or **proposed**.
- A request that differs from a registered definition uses a registered alternative when one exists. Otherwise the result is labelled as an ad hoc variant, is not reported under the registered metric's name and is shown with its SQL. The evidence log records the definition used: registry id and version, or ad hoc with its SQL.
- A proposed metric is named for future definition only; it has no approved semantics and must not be computed as if it were registered.

## Definition template

```text
## <Metric name>        id: <id>   version: <x.y>   status: draft | approved

1. Business meaning       What question the metric answers.
2. Population             Entity counted and identity rules.
3. Activity / event rule  Exactly what qualifies.
4. Formula                Numerator and denominator, or the count/sum with no denominator.
5. Grain and time         Reporting period, timestamp used, time zone, period boundaries, partial periods.
6. Sources and layers     Current fixture tables; planned Silver/Gold tables marked as planned.
7. Canonical SQL          Runnable against the current fixture.
8. Filters / dimensions   Supported slices and how an entity is assigned to a slice.
9. Null, status and refund rules
10. Aggregation safety    What must not be summed or averaged, and the correct roll-up.
11. Quality checks        Each marked implemented and tested, or proposed.
12. Caveats               Known limitations.
```

## Metrics

No metric definitions are approved yet.

## Proposed metrics

| id | Intended meaning | Status |
|---|---|---|
| monthly_active_viewers | Distinct users who started at least one content view in a UTC calendar month; a stricter companion to MAU. | Proposed; not defined |
