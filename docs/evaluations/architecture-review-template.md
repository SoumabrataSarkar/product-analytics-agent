# Architecture version comparison — evaluation template

Use the **same dataset snapshot, test suite, metric registry and declared runtime environment** across versions. Never represent unmeasured values as results.

## Version metadata
- Version / commit:
- Date / evaluator:
- Runtime + model:
- DB checksum and generator seed:
- Metric Registry and question suite versions:
- Hardware / hosting / relevant cost assumptions:

## Change rationale
- Earlier observed issue:
- Proposed improvement / associated ADR:
- What changed:
- What did not change:

## Measured comparison
| Measure | Prior version | New version | Difference |
|---|---:|---:|---:|
| Correct numerical answers | Not measured | Not measured | N/A |
| Supported/traceable conclusions | Not measured | Not measured | N/A |
| Unsupported causal claims | Not measured | Not measured | N/A |
| Correct refusal of unanswerable queries | Not measured | Not measured | N/A |
| Data-quality traps detected | Not measured | Not measured | N/A |
| Median SQL queries per RCA | Not measured | Not measured | N/A |
| Median investigation latency | Not measured | Not measured | N/A |
| Cross-runtime numeric agreement | Not measured | Not measured | N/A |
| Human handoffs | Not measured | Not measured | N/A |

## Review
- What genuinely improved:
- What regressed and why:
- New/remaining failure cases:
- Production cost, permissions, reliability concerns:
- Keep/revert decision:
- Next iteration:
