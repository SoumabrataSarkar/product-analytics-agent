# ADR-003 — Evidence-first hypothesis workflow with bounded autonomy

**Accepted:** 2026-11-07 (Architecture v1.0)

## Problem
Open-ended RCA may loop indefinitely, stop too soon or invent a plausible root cause.

## Decision
Validate the baseline first. Generate and investigate up to three distinct, evidence-informed hypotheses per round for at most three autonomous rounds. Track Supported/Rejected/Inconclusive/Not Tested with SQL evidence; stop early on sufficient quantification or on query/time/critical quality limits. If still unresolved, show what is known and request user hypotheses. Guided mode and interruption are always possible.

## Trade-offs
Nine hypotheses is a budget, not a completeness guarantee. Some difficult questions need human follow-up; supported observations must not be oversold as causal proof.

## Verification
Test early stop, inconclusive outcomes, data-quality blockers, impossible questions, exhausted budget and human handoff.
