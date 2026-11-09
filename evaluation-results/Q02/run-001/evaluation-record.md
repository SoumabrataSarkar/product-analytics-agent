# Evaluation run 001: Q02, active users vs revenue (independent mode)

**Status:** Outcome decided by the evaluator (2026-11-09). Evaluator-only record; keep it outside the repository and outside any agent's investigation context.
**Drafted by:** the agent that ran the investigation (Claude Code). **Outcome set by the evaluator**, not by the agent.

**ID convention:** Q02 is the repository scenario ID (`docs/evaluations/investigation-paths.md`). Evidence names `q01`–`q21` are query/check IDs, not scenario IDs.

## Run information

| Field | Record for the run |
|---|---|
| Run ID / date (UTC) | eval-001 · 2026-11-09. Question received about 11:47; queries 11:48:22–11:50:33; v1 report finished about 11:58 |
| Dataset path and SHA-256 | `…/outputs/pockettoons.sqlite` (local, read-only) · `8d39e78bbaa756b594c9e38797490dc1879f2980a05f966aaf62d3919517790b` · 713,474,048 bytes |
| Database build ID / layers available | `3a0dbed21d2f45958aefa2887a0cadd8` (succeeded 11:16:56 UTC; 122/122 reconciliation checks) · 20 Bronze views, 10 Silver tables, 8 Gold tables |
| Generator and layer-builder commit | Builder SHA-256 `12fd6588…84c2`, matching `build_layers.py` at commit `1fd5121`. The build log doesn't record the generator commit: **unknown** |
| Coverage, timezone, data-quality version | 2026-04-01 to 2026-09-30, UTC; 13 reviewed payment corrections in `silver_quality_exceptions` |
| Skill, catalog and registry commit / metric versions | Repo `1fd5121`. The registry text at build time came from commit `d5ecd1a`; the later change in `7240dfe` was documentation only. mau 1.1, revenue_group 1.1, funnel_and_lifecycle 1.0, engagement 1.0, growth_accounting 1.0, supporting 1.1 |
| Runtime, model | Claude Code cloud session, Claude Opus 5.5. Queries ran on the user's Mac through the device bridge using unmodified copies of the repo's tools (SHA-256 verified) |
| Mode | **Independent.** Available to the agent: AGENTS.md, CLAUDE.md, project status, architecture and ADRs, skill, tools, catalog, registry, layer contracts and the Gold question list. Not read: `investigation-paths.md`, the generator README and evaluation files. The `eval-*` and `guided-*` files in the outputs folder were present but not opened |
| Query and time budgets | 3 rounds × 3 hypotheses (all 9 used); no time budget set |
| Result limits and timeout | 100 rows (default), 30 s per query; no result truncated, no timeouts |
| Oracle location | `Documents/eval-private/` (this record and evidence). **[Evaluator: add the reviewer's independent calculations here]** |

**Contamination notes:** the user's prompt stated the premise ("about 20% … nearly flat"). This session now holds the answer, so any rerun of this question must start in a **fresh session**.

## Results table

| ID | Question / variant | Category | Expected behaviour or value | Agent result / action | Outcome | Evidence | Failure or limitation |
|---|---|---|---|---|---|---|---|
| **Q02** | Why did active users grow while revenue stayed relatively flat? (Asked as: MAU up about 20% QoQ, revenue nearly flat: why?) | Multi-step investigation | Verify premise (avg MAU 9,016 → 10,819; net revenue $30,145 → $30,167); decompose; separate observation from cause; report quality caveats with uncertainty | Premise verified exactly; growth traced to Q3 signups and paid social; lower paywall reach and conversion found; 9 hypotheses logged | **Fail (v1)** | 16 logs (q01–q16); review checks q17–q21 | Overstated cause; mislabelled comparison periods; monthly vs quarterly mismatch; H8 and H9 rejected too firmly; quality impact overstated; delivered as a Claude Doc, not a PDF |

## Per-question record

### Q02: Why did active users grow while revenue stayed relatively flat?

- **Category / runtime / mode:** multi-step investigation · Claude Code (Claude Opus 5.5) · independent.
- **Exact question:** "Monthly active users increased by about 20% quarter over quarter, but revenue stayed nearly flat. What explains the difference? Verify the premise, investigate possible drivers and produce an evidence-backed answer…" No clarification was requested or given.
- **Snapshot, metrics, period:** snapshot above; `mau` 1.1 (quarter = average of 3 months), `net_revenue` 1.1 (quarter = sum); Q2 (Apr–Jun) vs Q3 (Jul–Sep) 2026, UTC; no filters.
- **Prerequisites and acceptable behaviour:** use Gold where it fits exactly and Silver/Bronze where needed; check data quality before explaining; quantify drivers; don't claim causation; report unknowns.
- **Expected (reviewer, independent source-level check):** average MAU about 9,016 → 10,819 (+20.0%); quarterly net revenue $30,145 → $30,167 (+0.07%). Breakdowns by source and cohort confirmed directionally by the reviewer. **[Evaluator: add oracle SQL/method and exact reference values]**
- **Actual (v1, original agent output):** premise numbers exact. Growth decomposed into signup groups (+3,457 Q3 signups; earlier groups −1,654) and sources (paid social +1,841). Paying users flat at about 1,036 a month; ARPPU about $9.70. 30-day paid conversion 1.94% (May–Jun) → 0.53% (Jul–Aug). First-30-day paywall reach 9.8% / 4.4% / 2.7% / 1.0% / 0.5% (Apr–Aug cohorts). Statuses: H1, H5, H6 supported; H2, H3, H4, H7, H8, H9 rejected.
- **v1 source:** exported 2026-11-09 (A4, 8 pages, 3 charts) from https://claude.ai/artifact/AibnRPMsuLXmkodAD7MgXz, doc revision 11. v1 evidence is q01–q16 (folder `inv1/` in the zip); q17–q21 (`inv1-review/`) came after the feedback.
- **Evidence:** 16 JSONL logs (SQL, SHA-256, layer, metric version, rows, truncation flag): Gold for KPIs, revenue, cohorts, funnel and segments; Silver for source × cohort and first-30-day behaviour; Bronze for tier history and raw events. One wrapper error (`json_each` blocked by the read-only authorizer) and one existing-log guard refusal, both during setup and both logged.
- **Measurements:** 16 queries (each under 1.6 s); about 2 min of querying; about 11 min from question to v1 report; model usage and cost **unknown**.
- **Outcome and rationale (for the evaluator):**
  - *Met:* exact premise; correct layer use; traceable evidence; rejected hypotheses recorded; recommendations to test rather than assume.
  - *Not met:* the v1 executive answer asserted a cause ("…so they don't become paying subscribers"); H8 and H9 were rejected without sufficient evidence; data-quality impact was called "none" and "the same each month".
  - **Outcome: Fail (original run, v1).** The agent verified the headline numbers and found useful patterns, but the original report overstated several conclusions (causation, identity gaps, tracking) and contained material comparison and data-quality errors. Under the template's rule, unsupported certainty is a fail.
  - The run is still **promising**: exact premise, sensible layer use, traceable evidence and recorded rejections.
  - **v2** was corrected after human review. It is assessed separately and does not turn the original run into a pass.
  - The score applies to this one question only, not to the whole agent or the full evaluation.
- **Failure categories / impact / next check:**

| # | Failure | Category | Impact | Fixed in v2? | Prevented in future runs? |
|---|---|---|---|---|---|
| F1 | Cause stated from an association (executive answer; H6 "Supported") | Unsupported certainty | Material | Yes: "suggests"; H6 marked "pattern supported" | Partly: PR #1 skill rule (pattern ≠ mechanism) |
| F2 | "Q3 vs Q2" conversion label actually covered Jul–Aug vs May–Jun | Wrong population / period label | Material | Yes | Yes: PR #1 rule (name periods exactly) |
| F3 | $760 a month compared with quarterly revenue (2.5% instead of about 7.6%); not labelled a scenario | Time-basis mismatch | Material | Yes | Yes: PR #1 rule (same time basis) |
| F4 | Data-quality effect overstated (unidentified sessions; payment corrections) | Unsupported certainty | Material | Yes: qualified; payment sensitivity measured (+0.15%) | Yes: PR #1 rule (quantify scope and impact where feasible and material, else say unknown) |
| F5 | H8 and H9 rejected when evidence could not decide | Status misuse | Material | Yes: Inconclusive | Yes: PR #1 rule (inconclusive when evidence can't decide) |
| F6 | First-30-day query lacked a lower time bound (q14) | Method | None on numbers (q17 identical) | Yes: verified, disclosed | Yes: PR #1 rule (enforce start/end boundaries, timezone, inclusive/exclusive, for time-bounded questions) |
| F7 | Q2-cohort checkout anomaly called irrelevant | Downplayed anomaly | Moderate | Yes: unresolved, prominent (q19–q21) | Yes: PR #1 rule (material anomaly stays open until resolved; no "no impact" without assessment) |
| F8 | Delivered as a Claude Doc, not the required PDF of at most 10 pages | Deliverable / process | Moderate | Yes: v2 PDF, 9 pages | Yes: PR #1 (generator + skill rule + hard 10-page limit) |

## Versions kept

See `v1-vs-v2-changes.md` for every feedback point mapped to its change.

- **v1 (raw agent output, scored):** `v1-report.pdf`, the PDF export of the Claude Doc "PocketToons: why MAU grew 20% QoQ while revenue stayed flat". Not edited. Before the feedback, v1 was also briefly turned into a quick PDF in chat; same content, not a separate version.
- **Feedback:** `feedback.md`, word for word (A format, B substance review, C decision).
- **v2 (corrected after peer review):** `v2-report.pdf` (9 pages; one page spare) and `v2-content.json`. Build line reads "20 Bronze views and 18 Silver/Gold tables". **v2: Pass (round 2).** Every review point is addressed (see `v1-vs-v2-changes.md`), confirmed by checks 17–21. v2 is the agent's revision after review feedback, written alongside the skill rules that came from that review; it is not a fresh blind run.
- **Evidence:** `evidence.zip`: q01–q16 (original run) and q17–q21 (review follow-up), with an index.

## Aggregate (this run only)

- Round 1 (v1): Fail. Round 2 (v2): Pass.
- Main failure pattern: **certainty beyond the evidence** (F1, F4, F5, F7) plus **labelling and time-basis precision** (F2, F3).
- Done: outcome decided; all 8 failure types now have a skill rule or tool guard in PR #1 (merged).
- v2 verified against checks 17–21. The other 17 scenarios were run in fresh Codex sessions (see `../../TRACKER.md`).
