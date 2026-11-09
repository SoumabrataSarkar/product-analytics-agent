# Evaluation results

**Status:** Complete for this stage (2026-11-09). 18 scenarios run blind, scored against an answer key written beforehand; one improvement round. Scenario definitions: [investigation-paths.md](investigation-paths.md). Method: [evaluation-process.md](evaluation-process.md).

## Summary

| | Round 1 | Round 2 (after one skill rule) |
|---|---|---|
| Scenarios | 18 | 4 rerun (2 failures + 2 regression checks) |
| Pass | 15 | 16 of 18 overall |
| Partial | 1 (Q11) | 1 (Q11, unchanged) |
| Fail | 2 (Q02 v1, Q07) | 1 (Q02 v1, run before the rules; not rerun) |

- **Runtimes:** Q02 in Claude Code (Claude Opus 5.5); all others in Codex, one fresh session per question, independent mode (no evaluation docs, answer keys or previous reports in context).
- **Snapshot:** `pockettoons.sqlite` SHA-256 `8d39e78b…790b`, build `3a0dbed2` (122/122 layer checks). Coverage April–September 2026, complete UTC months.
- **Answer key:** computed with the metric registry's canonical SQL on the **source tables only**, never on the Silver/Gold tables the agent uses, and approved before any run. Exact counts and cents; ±0.1 point on rates. Correct numbers are not enough: unsupported certainty, a silent choice of period or definition, or a missing required caveat fails.
- **Agent versions:** round 1 = `main` after PR #1 (certainty, time-window and anomaly rules from the Q02 review). Round 2 = `cb3918d` (PR #4: start-up baseline rule).

## Results by scenario

| ID | Type | Question | Expected (key points) | Agent result | R1 | R2 |
|---|---|---|---|---|---|---|
| Q01 | Simple aggregate, time | How did MAU change across the months? | 7,937 → 11,447 (+44.2%); unidentified sessions excluded, not people | Exact; Silver recount matched | Pass | Pass |
| Q02 | Multi-step | Why did MAU grow 20% while revenue stayed flat? | Premise verified; growth from new users; association, not cause | Numbers exact; cause overstated; mislabelled periods; quality caveats too certain | **Fail** | v2: agent revision after review (see below) |
| Q03 | Ambiguous period, decomposition | Which sources contributed most to the change in active users? | Ask or state the period; unknown shown separately; no causal claim | **Asked** daily/weekly/monthly; exact for the chosen weeks | Pass | |
| Q04 | Comparison of metrics | Did engaged users grow with active users? | MEU +38.2% vs MAU +44.2%; 60-second rule | Exact | Pass | |
| Q05 | Filter, overlapping slices | Did the platform mix change? | No material change; platforms overlap (~28%) and can't be added | Exact; overlap explained | Pass | |
| Q06 | Lifecycle | Are more users new, retained or returning? | Growth accounting May–Sep; April not classifiable | Exact; headline missed that returning users doubled | Pass | |
| Q07 | Cohort | Did newer cohorts convert to subscription less? | May–Jun 1.94% vs Jul–Aug 0.53%; April flagged as start-up; September excluded | R1: April pooled into baseline (2.59%), decline overstated. R2: May–Jun baseline, exact | **Fail** | **Pass** |
| Q08 | Simple aggregate | Net revenue from subscriptions vs PPV? | $59,900.04 vs $411.93; unattributed $0 reported | Exact to the cent | Pass | |
| Q09 | Time comparison | Did refunds materially change the revenue comparison? | No; refunds $37.93 → $25.95 | Exact; R2 also flagged April and added a fair comparison | Pass | Pass |
| Q10 | Ambiguous definition | How many cancellations took effect in a period? | Request vs access ended; state which | Gave both: 113 ended, 92 requests (August) | Pass | |
| Q11 | Funnel | Where do users drop from paywall to purchase? | Biggest drop before checkout; rates flat from May; April is start-up; link gaps reported | Main answer and gaps right; reads April as a funnel decline | Partial | Partial |
| Q12 | Ambiguous measure, trap | Most-watched episodes and completion? | State the measure; 33.0% completion; premium episode with 0% completion | Exact; caught the 0-of-1,455 episode | Pass | |
| Q13 | Data-quality trap | Is an unusually large source payment real? | No: reviewed 100× unit error ($999 → $9.99); review time unknown | Exact incl. +$6,923.07 impact; didn't claim own detection | Pass | |
| Q14 | Missing data | Trust channel conclusions with missing sources? | Unknown ~1%; sensitivity bound; no causal or campaign claim | Exact; sensitivity shown | Pass | |
| Q15 | Ambiguous | "Performance is down. What happened?" | Clarify before analysing | **Asked**; for the agreed metric, revenue rose 3.62% (exact); premise challenged | Pass | |
| Q16 | Unanswerable | Which campaign caused each purchase? | Decline; say what data is missing | Declined; listed the data needed; no fabricated join | Pass | |
| Q17 | Filter | US subscribers at end of September? | 349 (incl. 37 cancelled but paid up) | Exact | Pass | |
| Q18 | Filter, time | Mobile sessions, September vs August? | Define mobile; 36,295 → 38,366 | **Asked** what mobile means; exact | Pass | |

Assignment coverage: simple aggregates Q01, Q08; filtered queries Q05, Q17, Q18; time comparisons Q01, Q09, Q18; cohort/retention Q06, Q07; ambiguous or unanswerable Q03, Q10, Q12, Q15, Q16; data-quality traps Q09, Q12, Q13, Q14; multi-step Q02, Q04, Q11.

## Q02: the GM question, v1 → feedback → v2

v1 is the agent's raw output (Claude Code, independent mode) and is the version scored. A reviewer then checked it against the evidence and source data, and the agent produced v2 from that feedback. The brief allows showing both; v2 is the board-ready report.

| Feedback on v1 | v2 |
|---|---|
| Cause stated too confidently ("so they don't become paying subscribers") | Lower paywall reach and lower conversion described as going together; cause left open |
| Conversion compared across mixed periods ("Q3 0.5% vs 1.9%") | May–June 1.94% vs July–August 0.53%; April (start-up) and September (incomplete window) excluded, with reasons |
| $760 a month compared with quarterly revenue ("2.5%") | Labelled a scenario: about 7.6% of average monthly net revenue, with its assumptions |
| Data-quality impact called "none" and "the same each month" | Scope given; impact "unknown" where it is (unidentified sessions 6.5–7.6% and varying; payment corrections change QoQ by +0.15%) |
| Identity-gap (H8) and tracking (H9) hypotheses rejected too firmly | Both marked Inconclusive; tracking audit recommended |
| First-30-day query lacked a lower time bound | Rerun with both bounds; results identical (check 17) |
| Unexplained Q2-cohort funnel result dismissed | Kept open: 183 checkouts with no payment attempt, cause unknown (checks 19–21) |
| Format: PDF template, plainer wording, clearer charts, a page on how the investigation ran | Fixed-template PDF, 9 pages |

The three reasoning lessons became skill rules (PR #1) before the other 17 scenarios ran.

## Failure analysis

| Failure mode | Where | Impact | Response | Result |
|---|---|---|---|---|
| Certainty beyond the evidence (cause stated, hypotheses rejected too firmly, data-quality impact called "none") | Q02 v1 | Board-level conclusion overstated | Skill rules: pattern ≠ mechanism; quantify or say "unknown"; keep anomalies open | Did not recur in the 17 later runs |
| Mixed or mislabelled comparison periods | Q02 v1 | Wrong conversion and revenue comparisons | Skill rule: exact periods, same time basis, explicit boundaries | Did not recur |
| First month of data treated as a normal baseline (the subscriber base starts at zero in April) | Q07, Q11 | Declines overstated; Q11 points the team at the wrong cause | Skill rule (round 2): check for a start-up period before using the first period as a baseline | Fixed Q07; also applied correctly in Q09; **did not reach Q11**, where the question isn't phrased as a comparison |
| Noise: every run reported the registry file hash differing from build time | All | Longer reports; a non-issue presented as a risk | Verified the change is docs-only (56 SQL blocks identical) and recorded it in project status | Still raised in 3 of 4 round-2 runs; agents compute the hashes and don't read the note |

**Hardest question types:** comparisons that need context the data doesn't announce (a start-up month, a fair baseline). The agent computes correctly but doesn't ask whether the comparison is fair unless a rule names the situation.
**Strongest:** behaviour under ambiguity. It asked in all four scenarios that needed it, declined the unanswerable one, and caught both planted data traps.

## Evidence

Every run keeps one JSONL evidence log per query (SQL, SQL hash, layer, metric version, row count, truncation flag), the report and a run note. Per-scenario records, answer key and raw outputs: `evaluation-results/` (evaluator material; not for agent use during independent runs).
