# Project write-up outline — one page maximum

**Status:** Outline only. Replace prompts with observed facts after the final
investigation and evaluation. Keep the finished write-up to one page.

## What we built and why

Describe the actual runtime (Codex or Claude Code), shared investigation
skill, dataset-specific catalog and metric registry, read-only query tool,
evidence and report workflow. Explain the most important design trade-offs.
Name the tools and models actually used. Distinguish implemented functionality
from planned work.

## What worked and where it breaks

Summarize the actual evaluation coverage and outcomes, with the number of
questions run and the pass/partial/fail/not-run counts. Describe the most
important observed failure modes, their analytical impact and how uncertainty
or unsupported questions were handled. Do not claim a fix or measurement
without evidence.

## How a 20-person product team could use it

Propose a practical deployment approach and access boundaries. Cover
estimated **or measured, clearly labelled** cost and latency; bounded
read-only access; handling of sensitive data and errors; monitoring, feedback
and periodic quality checks. State assumptions and unknowns. Do not imply
production safeguards already exist.

## With more time

List the highest-value improvements and why, based on actual limitations—for
example independent evaluations, better data routing or verified chart
generation. Avoid treating unfinished ideas as completed features.
