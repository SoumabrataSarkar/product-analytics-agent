# Product analytics agent: evaluation run template

**Status:** Preparation template. Rows are not test results. Populate only
after running an agent on a fixed, validated dataset; do not invent values.

## Purpose and boundaries

Evaluate whether a coding-agent runtime can answer varied product questions
using the shared investigation skill, selected data catalog, metric registry,
read-only query tool and evidence. The current repository contains 16
[investigation scenarios](investigation-paths.md); this template is the
evaluator's format, not evidence that those scenarios have been run.

Keep expected answers, planted findings, evaluator-only SQL and held-out
questions outside the agent's accessible investigation context. During an
independent run, do not supply the generator's answer-bearing README or
question-specific investigation paths. If a scenario guide is supplied,
label the run **guided** and report it separately. Use a fresh session without
prior access to the answer key; document unavoidable contamination.

## Run information

| Field | Record for the run |
|---|---|
| Run ID / date (UTC) | |
| Dataset path or ID and SHA-256 | |
| Database build ID / data layers available | |
| Generator and layer-builder commit | |
| Coverage, timezone and relevant data-quality version | |
| Skill, catalog and registry commit / metric versions | |
| Runtime, model and model version if known | |
| Mode | Independent / guided; inputs actually available to agent |
| Query and time budgets | |
| Result limits and timeout | |
| Oracle location | Private evaluator-only location; not agent context |

For comparisons between runtimes, use the same snapshot, question wording,
permitted context, budgets and oracle; record any unavoidable differences.

## Question coverage plan

Use at least 15 varied questions. Reference existing scenario IDs where
appropriate, but validate or revise their prerequisites against the current
registry and final snapshot. The scenario list alone does not guarantee
that the following assignment categories are covered.

| Coverage | Example test direction | Scenario IDs / additional IDs |
|---|---|---|
| Simple aggregates | DAU, MAU and total revenue | |
| Filters | US subscribers and mobile sessions | |
| Time comparisons | Current versus preceding complete month | |
| Cohorts / retention | Comparable eligible signup cohorts, D1/D7/D30 | |
| Multi-step investigation | Active users versus revenue | |
| Ambiguous question | Missing metric or time period; clarification expected | |
| Unanswerable question | Unsupported attribution or missing data | |
| Data quality | Missing source, suspicious amount or invalid record | |
| Layer selection | Choose a validated layer with sufficient detail and evidence; inspect raw records when needed | |

Include held-out variants, boundary cases and realistic follow-ups. Exclude
unsupported or unavailable cases from the executed denominator and mark them
`Not run — reason`; do not silently count them as passes.

## Results table

One row per question, runtime and run. Record the exact question, expected
value or behavior, actual answer or action, outcome, evidence and failure or
limitation. Link the detailed record below; fill the table only after execution.
Scenario IDs identify evaluation questions; query IDs identify evidence checks
within a question and must not be counted as separate evaluation questions.
Preserve the agent's original response and score before any review or edits.
Label corrected outputs and later reruns separately; do not overwrite the first
result or silently turn a failed original run into a pass.

| ID | Question / variant | Category | Expected behavior or value* | Agent result / action | Outcome | Evidence | Failure or limitation |
|---|---|---|---|---|---|---|---|
| | | | | | Pass / Partial / Fail / Not run | | |

*For numeric cases, record the reference value and independent calculation in
the evaluator-only record. The published submission may include expected vs
actual after the blind run, while keeping answer keys out of the agent context
during testing.

## Per-question record

### [ID] — [question]

- **Category / runtime / mode:**
- **Exact question and clarification provided:** 
- **Snapshot, metric ID/version, period, timezone and filters:**
- **Prerequisites and acceptable behavior:** including any expected
  clarification, unsupported answer, quality warning and safe layer choice.
- **Expected:** independently computed values with units, oracle SQL or
  reference method and reviewer. For a nonnumeric case, explicit behavior and
  evidence criteria; do not fabricate a numeric answer.
- **Actual:** answer, numerical values, clarification, abstention or failure;
  retain the unedited response and record any human assistance or intervention.
- **Evidence:** query/evidence log locations, source tables/layers, SQL,
  parameters, row truncation, errors, assumptions and quality caveats.
- **Measurements:** query count, elapsed time, timeout/errors and, where
  available, model usage/cost. Record unavailable measurements as unknown.
- **Outcome and rationale:** Pass / Partial / Fail / Not run; explain which
  criteria did or did not hold.
- **Failure category / impact / next check:**

### Outcome rules

- **Pass:** All material numeric and behavioral criteria are met, with
  traceable evidence and appropriate uncertainty.
- **Partial:** Some material requirements are correct but an important part
  is missing or incomplete; explain why.
- **Fail:** A material result or method is wrong, an unsafe operation is
  attempted, or the response asserts unsupported certainty.
- **Not run:** Prerequisites or execution were unavailable; state why. It is
  neither a pass nor a fail.

For exact counts and integer cents, require exact equality unless the metric
contract says otherwise. For ratios or time allocations, specify units,
rounding and a justified tolerance **before** comparing. A correct number with
the wrong population, timeframe, source or unsupported reasoning does not
automatically pass. An appropriate clarification or abstention can pass when
that is the expected behavior.
For layer-routing cases, evaluate the suitability of the chosen available,
validated layer and the explanation, not a fixed requirement to query Bronze.
Check that material ambiguity is clarified rather than silently assumed.

## Aggregate and failure analysis

- Executed: [ ]; pass: [ ]; partial: [ ]; fail: [ ]; not run: [ ].
- Report the denominator and each outcome separately; do not inflate the pass
  rate by treating partial or not-run cases as passes.
- Main failure patterns, representative IDs, analytical impact and fixes:
- Remaining untested cases and known limits:
- Runtime comparisons, where actually run on matched conditions:
- Next evaluation after fixes, including regression results:

## Submission and improvement record

After the relevant runs are complete, prepare a reviewer-facing summary table
with question, expected result or behavior, actual result, outcome, evidence,
and failure or limitation. Include a concise failure analysis describing
impact, proposed or implemented fixes, and whether a regression test was run.
Separate results by runtime, model and run; distinguish the original response
from a human-reviewed report and from a fresh rerun after changes. Do not
invent results or claim automatic model learning: improvements require reviewed
changes and repeatable regression tests.

Keep answer keys and held-out cases outside the agent's accessible context
until those tests finish. A folder outside the repository is organizational,
not an access-control boundary. After testing, include the appropriate
expected-versus-actual results and supporting evidence in the authorized
private submission, excluding secrets, sensitive data and material that should
not be shared. The evaluator chooses what can be shared and when.
