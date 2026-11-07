# PocketToons synthetic data: issues, decisions and lessons

**Purpose:** A record of the problems encountered while designing and generating the PocketToons dataset, how they could have affected an analytics agent, and what was changed. This is an interview preparation and project-history document, not an agent instruction file.

**Status:** Reflects the locally reviewed v7 dataset and the generator/checks in `examples/pockettoons`. The SQLite file has not yet been uploaded to GitHub. Counts and findings below describe this synthetic dataset; they are not observations about a real PocketToons product.

> **Evaluation note:** This document includes the planted story, data-quality issues and expected findings. Keep it out of the agent's investigation context when testing whether the agent can independently discover those findings. A reviewer can use it afterwards to assess the agent's work.

## 1. Project context

The interview assignment asks for six months of synthetic data, roughly 10,000 or more users, six named tables and fields, at least 2–3 interrelated drivers of an MAU-versus-revenue story, and at least one data-quality issue. The scenario is that MAU increased 20% quarter over quarter while revenue remained flat.

The reviewed dataset has 24,000 users, 72,094 sessions and 94,047 content views. The main planned story is that growth includes a larger paid-social audience, newer cohorts convert to subscriptions at a lower rate over a comparable period, and subscriber departures are offset by other payments. These are synthetic patterns built for investigation—not evidence that an acquisition campaign caused the changes.

The work progressed through a reference data model, an initial generator and several local review versions. The issues below distinguish a product-policy choice, a defect in an earlier version, a deliberate data-quality trap and a limitation that still remains.

## 2. Issues found while designing the model

### 2.1 Dates were visible, but the important timestamps were not

**Issue and impact:** The first ERD displayed assignment-required dates without showing the event timestamps. A date alone cannot establish whether a user watched before buying PPV, subscribed before playback, or cancelled before a refund. The detailed schema had timestamps for several actions, but leaving them out of the diagram made the model appear incomplete and caused understandable confusion during review.

**Decision and change:** Event timestamps are UTC and are the source of truth. Required assignment date fields are retained as derived UTC dates. The ERD shows the important timestamps and the detailed schema maps each timestamp to the assignment field. Daily marketing spend remains a daily aggregate: a real event time cannot be recovered from a daily total.

**Interview lesson:** A design may technically contain a field while its diagram tells a different story. Check the ERD and detailed schema together, especially for event ordering.

### 2.2 The six assignment tables alone did not explain complete journeys

**Issue and impact:** A user can watch in one session, return in another, buy an episode, subscribe and later cancel or request a refund. If a view has no session link, or a transaction has no episode attribution, the agent cannot reconstruct the journey reliably. Joining several child tables directly can also multiply revenue and watch time.

**Change:** Kept the six assignment tables and added session-linked views, subscription history, user events, payment-status history, episode-level catalog and PPV/refund attribution. Documented each table's grain, relationships and fanout-safe join patterns. In-app purchases point to a session; renewals and other background actions can be off-session.

**Interview lesson:** Ask what one row represents before joining tables. Aggregate facts at their own grain or use an ordered event timeline; do not sum money after a many-to-many join.

### 2.3 A current subscription flag could not answer historical questions

**Issue and impact:** `users.subscription_status` is a current snapshot. Using it to classify an earlier view would give the wrong answer after a user subscribes, cancels or gets a refund.

**Change:** Added `subscription_history` with effective start and end timestamps. A later review found that expired and refunded statuses had disappeared from the effective timeline even though they existed in the current snapshot. The generator now creates explicit expired and refunded periods and checks the snapshot against the status effective at the end of the analysis window.

**Interview lesson:** Current state and historical state are different questions. Use the state effective at the time of the behavior, and distinguish a cancellation request from the end of paid access.

### 2.4 A title-level catalog could not describe an episode

**Issue and impact:** One row per series could not accurately represent an individual episode's duration, release, tier, price or availability. That would make PPV attribution and historical content analysis unreliable.

**Change:** Added `content_episodes` and episode availability history. The 12 titles now have different episode counts. A delisting closes the earlier PPV entitlement in this synthetic policy; a notice is recorded, and a later return requires a new purchase. A test checks that a subscriber is not charged PPV.

**Interview lesson:** Model the level at which the business decision happens. A title may stay live while an individual episode changes availability.

### 2.5 Access, identity and free-quota rules needed explicit decisions

**Issue and impact:** The initial rules left room for contradictory results: a premium episode might be treated as one of the eight free episodes; resuming a previously counted free episode might be blocked; or anonymous viewing could let the same person gain a fresh quota on another device.

**Decision and change:** Watching requires login. The eight-episode allowance applies to distinct free-tier episodes per user per UTC day across devices; premium viewing requires subscription or valid PPV. Resuming an already-counted free episode on the same UTC day consumes no additional slot. Anonymous IDs can still link pre-login browsing to a later login in that session. A generated example reaches eight and records the ninth attempt as blocked.

**Interview lesson:** Time zones, identity resolution and retry behavior are product rules, not just database details. A consistent UTC reset is a deliberate v1 assumption; it occurs at different local times around the world.

## 3. Issues found while generating and reviewing data

### 3.1 Prototype patterns were too regular

**Issue and impact:** Earlier versions gave every series 20 episodes, used rounded monthly MAU numbers, and produced virtually identical revenue every month. Sessions all lasted 20 minutes, and watch durations had only two values. This would make the dataset look artificial and could lead an agent to infer patterns caused solely by generation rules.

**Change:** Varied title episode counts, monthly MAU targets, payment volumes, session durations and watch durations. All 183 analysis days now contain sessions. The deliberate quarterly targets remain: average monthly MAU is approximately 20% higher in July–September, while quarterly net revenue is nearly flat.

**Remaining limitation:** The dataset is controlled synthetic data. Its monthly targets and several distributions are still constructed rather than observed, so it should not be presented as a natural random sample.

### 3.2 There were no signups in April

**Issue and impact:** A later audit found an entire analysis month had no new signups because the cohort generator moved directly from March to May. A follow-up question about acquisition or activation in April would produce a misleading gap.

**Change:** Added an April cohort and varied cohort sizes while retaining 24,000 users. The checks now require signup cohorts in every analysis month.

**Interview lesson:** Check the distribution over time, not just total row counts. A sufficiently large dataset can still have missing or implausible periods.

### 3.3 Signup cohorts had equal sizes and the first conversion comparison was invalid

**Issue and impact:** May–June and July–August originally each contained 4,800 signups, which looked engineered. More seriously, an earlier 30-day conversion check compared March signups with later users even though activity and payments began in April. Part of March users' first 30 days was not observed; treating that missing period as zero purchases made the comparison unreliable.

**Change:** Varied monthly signup counts and limited the conversion check to cohorts with complete observation windows. In the current fixture, 96 of 4,854 May–June signups subscribed within 30 days (1.98%), versus 31 of 5,426 July–August signups (0.57%).

**Remaining limitation:** This is an intentionally planted association. A cohort difference alone does not establish why conversion changed, and small or missing segments still require cautious interpretation.

### 3.4 Marketing source and country had an accidental relationship

**Issue and impact:** A deterministic assignment pattern gave Mexico no paid-social users. An agent might have described an accidental generator artifact as a marketing strategy.

**Change:** Generated country and acquisition source independently, while retaining a deliberately larger paid-social share in later cohorts. The resulting database has paid-social users in Mexico.

**Interview lesson:** Examine combinations of dimensions, not only each column's distribution. Reusing a numeric ID modulo in several fields can accidentally create relationships.

### 3.5 Subscription and PPV funnels did not initially include enough non-purchasers

**Issue and impact:** In an earlier version, paywall events were generated mainly for people who purchased. After subscription journeys were added, every explicitly labelled subscription paywall was followed by a subscription. A funnel query would have reported 100% conversion, a generator artifact rather than product behavior. Successful PPV purchases initially lacked checkout-start events.

**Change:** Added labelled subscription and PPV paywall and checkout events for purchasers and non-purchasers. The current data includes 4,800 subscription-paywall sessions without an in-session purchase, including 1,631 abandoned checkouts. Checks require a matching earlier paywall for checkouts and a checkout before successful PPV payments.

**Interview lesson:** A funnel needs both the numerator and denominator. Generating events only for successful journeys makes conversion look artificially strong.

### 3.6 App sessions were initially identical to viewing sessions

**Issue and impact:** Earlier, every session contained a view and every active user watched content. That prevented meaningful questions about browsing without playback and made session-based activity identical to viewer activity.

**Change:** Added 5,273 browsing-only sessions. Logged-in users may browse without viewing, and a sample of pre-login browsing can be linked to the account after login. Anonymous playback remains prohibited.

### 3.7 Return visits were described as resumes without resume positions

**Issue and impact:** A previous generator created a second session but restarted playback at position zero. Calling that a resume would be misleading.

**Change:** Repeat views now start from the previous playback position. Checks cover playback positions, session timing and quota use.

### 3.8 Refund representation and timelines needed correction

**Issue and impact:** The early design stored refunds as negative amounts, and the first dataset contained only PPV refunds. It could not demonstrate a subscription refund or explain why a refund was requested. Later, PPV refunds lacked request events, while subscription request events pointed at a refund transaction before its recorded creation time.

**Decision and change:** Store charges and refunds as positive amounts and subtract successful refunds explicitly in net-revenue calculations. Each refund links to its original payment and has a reported reason, such as accidental purchase, disliked content or poor playback quality. Requests point to the original payment; the subsequent refund points to that same payment. The data includes 44 PPV refunds and five subscription refunds. A successful subscription refund ends access without deleting earlier views.

**Interview lesson:** Clearly define the sign convention, source event, timing and refund attribution before calculating revenue. A customer-reported reason is not proof of the underlying cause.

### 3.9 Cancellation and refund timing was mechanical

**Issue and impact:** All 500 cancellation requests initially occurred exactly 24 hours after a payment, and all five subscription refunds occurred at the same late-night time. This could create a fabricated timing pattern for an agent to investigate.

**Change:** Varied cancellation and refund request/approval timestamps within valid paid periods, preserving the order of payment, request and access end. Checks test the sequence and require variation.

### 3.10 The subscription and delisting journeys were incomplete

**Issue and impact:** Every initial subscription payment originally had a null session and no subscription-start event, so an in-app paywall → checkout → subscription → viewing journey could not be reconstructed. An initial delist/relist example also selected a user who was subscribed at repurchase time; the user should not have needed to buy PPV. The earlier example lacked the promised notice.

**Change:** Initial subscriptions now have linked sessions, checkout and subscription-start events, and a subsequent premium view; renewals remain off-session. The delisting example uses a non-subscriber and records a prior notice. Checks cover both journeys.

### 3.11 The prototype omitted columns from the agreed model

**Issue and impact:** The initial generator implemented the fields needed for its first queries, but it wasn't checked against every documented column. For example, `created_at` and `updated_at` were absent from `users` and `content_catalog`. This was an implementation oversight, not an assignment requirement change.

**Change:** Added the missing columns and an automated comparison of the 15 documented model tables and their columns, plus required-value checks. The six assignment tables and mandated fields remain present.

**Interview lesson:** A model document is only useful as a contract if the generated database is checked against it. Column checks help, but do not by themselves prove every behavioral rule.

## 4. Deliberately planted data-quality issues

These are intentional test cases, not accidental defects to hide:

| Issue | Intended challenge | Handling and boundary |
|---|---|---|
| Missing acquisition source | Check whether channel analysis includes and discloses unknowns. | 238 users have `unknown` source. A worst-case check confirms the direction of paid-social activity growth survives assigning all unknown first-quarter activity to paid social and none in the second quarter. This does not prove campaign causality. |
| Mixed numeric and text values | Check whether the agent validates types instead of silently converting invalid input. | The raw payment source contains numeric values and numeric strings; six values are non-numeric. Curated transaction amounts are separate. |
| 100× source values | Check whether unusually large amounts trigger investigation before revenue is trusted. | Seven raw amounts contain a documented unit error. The quality-review table records evidence and corrected values. The agent should not automatically divide every large value by 100. |

The quality-review table is available to analysts. Finding an existing correction record is useful, but it is not the same as independently detecting an unexplained source error. When evaluating the agent, be clear about which tables and evidence it was allowed to inspect.

## 5. Current verification and remaining boundaries

The generator uses a fixed seed and refuses to overwrite an existing output file. The validation script checks documented columns and required values; foreign keys; signup, session and viewing times; subscription and PPV entitlement; refund links and limits; checkout ordering; quota behavior; the selected cohort comparison; and the main MAU/revenue targets. A separate audit checked additional timeline and relationship cases. A second generation of v7 produced an identical file in the same environment.

These checks substantially reduce known risks, but they do not prove that every possible user journey or database rule is covered. The payment-status table supports transitions, while this fixture mainly records one final status per payment. There is one quota-boundary example and one delist/relist example. Some optional or future product behaviors have no generated examples. Synthetic associations are not causal proof.

The agent, the 15+ evaluation questions and the final investigation are separate deliverables. At the time of this log, they have not been completed. The next stage should test the agent against the database—including ambiguous, unanswerable and data-quality questions—rather than keep expanding the fixture indefinitely.

## 6. How to explain this in an interview

An honest short version:

> I started with the assignment's six tables and added the minimum history and attribution needed to follow users across sessions. The first synthetic dataset passed basic checks, but reviews uncovered misleading artifacts: missing timestamps in the ERD, an invalid cohort comparison, a funnel that only represented purchasers, mechanical event timing, and subscription statuses that disappeared from history. I corrected the model and generator, added targeted checks, and kept deliberate data-quality traps separate from accidental defects. I also documented what remains simplified, because passing checks isn't proof that the agent can answer every question.

For a deeper discussion, pick one example and trace **problem → analytical consequence → change → validation**. The invalid cohort comparison, funnel denominator or historical subscription status each provides a concrete example.
