# PocketToons data-generation issue log

This log records the identified issues, their analytical impact, and their resolution or current limitation for the PocketToons v7 synthetic dataset. It is a reference for project review and is separate from the data-model contract.

The log contains planted story details and expected findings. Exclude it from the agent's investigation context when testing independent discovery. The SQLite database is a local review file; the generator and checks are in the private repository.

## Data model and journey issues

### Event timestamps

**Issue and impact:** Date-only representations do not establish the order of views, purchases, cancellations and refunds. An ERD that omits timestamps can make the required fields difficult to identify.

**Resolution:** UTC timestamps are the source of truth. Assignment-required dates are derived from them. The ERD shows important timestamps and the schema maps dates to their source timestamps. Daily marketing totals retain their actual source reporting date.

### Cross-session journeys and join fanout

**Issue and impact:** A journey cannot be reconstructed reliably when views lack session links or PPV transactions lack episode attribution. Joining multiple detailed fact tables can multiply revenue and watch time.

**Resolution:** Views link to sessions; transaction and refund attribution identify the purchased episode; events and subscription history record the timeline. Facts have documented grains, foreign keys and fanout-safe join rules.

### Subscription status over time

**Issue and impact:** A current subscription status does not establish entitlement at an earlier view. Missing effective periods for expired or refunded states leave historical status questions unanswered.

**Resolution:** Explicit non-overlapping effective periods represent active, cancellation-pending, expired and refunded states. The current user snapshot is reconciled to the state effective at the snapshot time. Access ends at the applicable expiration or approved refund time.

### Episode detail and availability

**Issue and impact:** A series-level catalog alone cannot represent episode duration, price, tier or availability. This limits PPV attribution and historical playback analysis.

**Resolution:** Episode-level catalog records and effective availability periods describe these attributes. A delisting notice and a delist/relist/repurchase journey are recorded. Delisting ends the existing PPV entitlement; a new purchase is required on return.

### Access, identity and free quota

**Issue and impact:** Unclear rules for premium episodes, retries, time zones or anonymous identity can produce invalid access and quota counts across devices.

**Resolution:** Playback requires login. A user's first eight distinct free-tier episodes per UTC day use free slots; a same-day resume uses no additional slot. Premium episodes require subscription or valid PPV. Pre-login browsing can be linked to the same session after authentication. A boundary journey records a blocked ninth new free episode.

### Refund amounts and linkage

**Issue and impact:** An ambiguous sign convention, missing purchase links or missing subscription refunds can misstate net revenue and prevent analysis by episode or subscription.

**Resolution:** Charge and refund amounts are positive; net revenue subtracts successful refunds. Every refund links to its original charge and carries a customer-reported reason. PPV refunds link to the episode; approved subscription refunds end access while retaining earlier views. Refund requests refer to the original charge and precede the resulting refund.

## Generator and analytical issues

### Uniform distributions and missing time coverage

**Issue and impact:** Uniform episode counts, rounded MAU, identical monthly revenue, fixed session lengths or absent signup/activity days can create misleading time-based patterns.

**Resolution:** Episode counts, monthly activity, payment volumes, session lengths and playback durations vary. All analysis months have signup cohorts and all 183 analysis days contain sessions. Monthly targets remain controlled to support the synthetic assignment scenario.

### Cohort window and cohort size

**Issue and impact:** Comparing cohorts with equal artificial sizes looks unrealistic. Comparing conversion over unequal or incompletely observed windows can misstate the conversion difference.

**Resolution:** Cohort sizes vary. Conversion is compared over a complete, equal 30-day observation window. May–June: 96 of 4,854 signups (1.98%); July–August: 31 of 5,426 (0.57%). The March signup cohort has incomplete observation before April and is excluded from that comparison. The association is not proof of causation.

### Accidental country/channel correlation

**Issue and impact:** Reusing deterministic assignment patterns can accidentally produce implausible empty country/channel combinations, which an agent may interpret as a business decision.

**Resolution:** Country and acquisition source are generated independently, with a specified later-cohort channel mix. Country-by-channel coverage is reviewable in the dataset.

### Funnel denominator and event ordering

**Issue and impact:** Paywall events recorded only for purchasers yield artificially high conversion. Missing checkout events also prevent a complete funnel.

**Resolution:** Subscription and PPV paywall/checkout events carry a product label. The fixture includes purchasers and non-purchasers: 4,800 subscription-paywall sessions have no in-session purchase, and 1,631 of those start checkout. Every successful PPV purchase and initial subscription has a preceding matching checkout; initial subscriptions also link to a session and subsequent viewing.

### Browsing and resume behavior

**Issue and impact:** If every session has a view, app activity and viewing activity become indistinguishable. A repeat view at position zero does not demonstrate resume behavior.

**Resolution:** The fixture includes 5,273 browsing-only sessions and repeat views with playback-position continuity. Session duration, playback duration and completion are separate measures.

### Cancellation and refund timing

**Issue and impact:** Identical cancellation delays or refund approval times create artificial spikes and may be mistaken for product patterns.

**Resolution:** Cancellation and refund request/approval times vary inside valid paid periods. Checks validate timing, status transitions and access end.

### Schema implementation coverage

**Issue and impact:** Missing documented columns, including creation and update timestamps, prevent the SQLite database from implementing the agreed model.

**Resolution:** Documented columns for the model and source-quality tables are present. Validation checks table/column presence, required values, foreign keys and selected business invariants. Column coverage alone does not prove every possible behavior.

### Episode tier changes

**Issue and impact:** A current episode tier alone cannot identify the tier that applied when an earlier view or purchase occurred. Applying the current value retroactively can misclassify access and PPV eligibility.

**Resolution:** Effective-dated tier history records each episode's tier over time. As-of checks validate free views and PPV purchases against the appropriate interval, and a premium-to-free example includes views on both sides. The current tier snapshot is checked at the declared catalog snapshot time. Historical list-price changes remain outside this fixture.

### Delisting entitlement coverage

**Issue and impact:** Ending only a selected PPV entitlement at an episode's delisting leaves other affected purchases incorrectly active, allowing an analysis to treat their old access as valid after relisting. A check restricted to records already marked as delisted cannot discover missed entitlements.

**Resolution:** All succeeded entitlements active immediately before a delisting end at its boundary, and affected holders receive recorded prior notices. Already-refunded or ended entitlements are not changed. The checker independently compares all purchases with delisting intervals and validates notice coverage, continuity, snapshot status, live purchase timing and historical playback. Relisting does not revive earlier purchases.

### Identical episode durations

**Issue and impact:** A single episode length across the entire catalog is unrealistic and can obscure incorrect assumptions about durations and completion.

**Resolution:** Episode durations vary by title and episode. Title duration totals and view duration/completion fields reconcile to the episode values. The fixture uses continuous, non-rewinding playback and does not model historical changes to episode length; those limitations constrain completion and duration-history tests.

## Deliberate data-quality issues

| Issue | Analytical impact | Representation and handling |
|---|---|---|
| Missing acquisition source | Channel-level comparisons have an unknown group and need qualification. | 238 users have `unknown` source. A worst-case allocation check preserves the direction of paid-social activity growth; it does not prove campaign causality. |
| Mixed numeric and text amounts | Silent conversion can turn invalid text into an incorrect number. | Raw payment amounts include numeric values and numeric strings; six values are non-numeric. Curated transaction amounts are separate and reconciled. |
| 100× source values | Raw revenue can be materially overstated. | Seven raw amounts contain a unit error. Review records provide correction evidence; an unusually large value is not automatically divided by 100. |

The quality-review table is available as evidence. Consulting an existing correction is distinct from independently detecting an unexplained source error.

## Verification and limitations

The fixed-seed generator and checks cover the documented columns, required values, foreign keys, timestamps, subscription and PPV entitlement, refund linkage, checkout order, quota behavior, cohort windows and the MAU/revenue targets. Independent checks cover additional timeline and relationship cases. The generator refuses to overwrite an existing output file.

The dataset is a controlled synthetic fixture. Payment-status transitions, concurrent-device activity and some edge cases have limited examples; one quota-boundary and one delist/relist journey do not prove coverage of every combination. The data-quality corrections are explicitly documented. The agent, its 15+ evaluation questions and the investigation output remain separate work.

