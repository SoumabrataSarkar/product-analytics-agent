# Investigation report structure

**Status:** Structure only. Fill it with results from the validated final
snapshot and actual agent investigation. Never insert illustrative figures as
findings or present association as a proven cause.

## Deliverable

Prepare a board-ready PDF or slides of **at most 10 pages/slides**. Keep the
raw agent output and its evidence. If the board-ready version is edited,
include both the raw output and edited version in the submission.

## Suggested flow

Use fewer sections when they do not add value; the limit is a maximum, not a
target.

1. **Executive answer.** Business question, key finding, quantified movement,
   strongest supported drivers, recommendation and the most important caveat.
2. **Scope and trust.** Periods, timezone, dataset/snapshot, metric definitions
   and versions, coverage and material data-quality limitations.
3. **Baseline.** Show the actual movement of the requested metrics for
   comparable periods. State whether quarter values are sums, averages or
   distinct users across a quarter.
4. **Decomposition.** Break the movement into meaningful, non-overlapping
   components where valid. Reconcile components to the total.
5. **Driver investigation.** Present material findings, hypothesis outcomes
   and their supporting evidence; distinguish arithmetic contribution from
   association and causal evidence.
6. **Data-quality findings.** Describe the issue, affected population or value,
   impact on interpretation, review evidence and unresolved uncertainty.
7. **Recommendations.** Give specific actions, expected decision value and
   validation plans. Quantify impact only where supported.
8. **Limitations and next steps.** Name the remaining unexplained movement,
   unavailable data, untested hypotheses and follow-up checks.
9. **Evidence appendix, if useful.** Reference metric versions, SQL, parameters,
   source tables/layers, results and evidence records without overwhelming the
   decision-maker. The 10-page/slide limit still applies.

## Chart plan

For each selected chart, complete this only after the relevant data is verified:

| Field | Record |
|---|---|
| Decision / question | |
| Chart title and takeaway supported by evidence | |
| Measure, definition and version | |
| Period, timezone, units and comparison | |
| Chart type and why it fits | |
| Source table/layer, SQL and evidence record | |
| Quality, coverage, denominator and causality caveats | |

Possible charts include metric trends, a revenue-component breakdown, a
reconciled segment contribution, and comparable cohort conversion. Choose
only those supported by the investigation. Show unknown categories, avoid
misleading dual axes and do not sum overlapping distinct users.

## Final review

- Are numbers reproducible from the final snapshot and approved definitions?
- Do reported components reconcile? Are uncertainty and unsupported claims
  handled explicitly?
- Can a reader connect each material finding and chart to evidence?
- Is the raw agent output retained separately from edits?
- Is the submitted document within the page/slide limit?
