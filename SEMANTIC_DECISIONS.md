# SPEC-01 semantic decisions

## Status and authority

This file is the frozen semantic input to `SPEC-02`. It resolves the release-blocking ambiguities
identified by the adversarial review without representing any provisional interpretation as
customer-confirmed fact.

The four confidential source documents were read in full for requirements. They remain outside the
repository. This file contains normalized requirements and decisions only; it contains no source
excerpts, customer identifiers, or source data.

Normative terms are `MUST`, `MUST NOT`, `SHOULD`, and `MAY`. If a later source-contract detail
conflicts with this file, this file wins until a superseding, reviewed decision is appended to
`DECISION_LOG.md`. Frozen expected answers must then be regenerated from independently authored
fixtures before implementation continues; an implementation mismatch is not grounds to change a
decision.

## Release-blocking decision index

| ID | Frozen subject | Hard-test anchor |
|---|---|---|
| P0-01 | Aircraft/event/assignment identity and same-day visibility | HT-01 through HT-04 |
| P0-02 | Validity, interval boundaries, sentinels, and source end dates | HT-05 through HT-07 |
| P0-03 | Aircraft existence and end-of-life behavior | HT-08 through HT-10 |
| P0-04 | Attribute ownership and temporal treatment | HT-11 |
| P0-05 | Snapshot completeness, gaps, disappearance, and reappearance | HT-12 through HT-15 |
| P0-06 | Schedule grain, deterministic de-duplication, and multi-open states | HT-16 through HT-18 |
| P0-07 | Exact schedule changes versus candidate amendments | HT-19 through HT-22 |
| P0-08 | Knowledge and operating clocks | HT-23 through HT-25 |
| P0-09 | Carrier role, codeshares, frequency, and cabin capacity | HT-26 through HT-29 |
| P0-10 | Passenger/actual separation, source union, and fulfillment | HT-30 through HT-33 |
| P0-11 | Actual rotation and cross-use-case enrichment | HT-34 through HT-37 |
| P0-12 | Code resolution, missing configuration, and mixed-engine limits | HT-38 through HT-40 |
| P0-13 | Snowflake/RAI responsibility, independent oracles, and artifact drift | HT-41 through HT-43 |
| P0-14 | Evidence, performance claims, and the UC1 fallback | HT-44 through HT-46 |
| P0-15 | Curated query and agent ambiguity behavior | HT-47 through HT-49 |

There are no open identity, validity, carrier, amendment, or end-of-life semantics in this
contract. The explicitly provisional decisions remain binding for this release unless changed by
the review-and-rollback protocol at the end of this file.

## P0-01 — Aircraft, event, and assignment identity

1. A physical aircraft is identified only by `aircraft_id`. Registration, configuration, type,
   engine, status, operator, and tail number MUST NOT be used as aircraft identity.
2. A source aircraft event is identified by `aircraft_history_id`. Canonical event order for an
   aircraft is ascending
   `(start_event_date, row_sequence_number, event_sequence_number, aircraft_history_id)`.
   `event_sequence_number` and `aircraft_history_id` are deterministic fallbacks after the source's
   primary `row_sequence_number`; they MUST NOT reverse a valid source order.
3. An eligible event with a null `aircraft_id`, `aircraft_history_id`, `start_event_date`, or
   `row_sequence_number` is quarantined and counted. The pipeline MUST NOT guess its identity or
   position.
4. Each independently versioned dimension is one of `aircraft_state`, `aircraft_type`,
   `engine_type`, or `aircraft_status`. An audit assignment observation is identified by
   `(dimension, aircraft_id, start_event_date, row_sequence_number, aircraft_history_id)`. This key
   remains unique even when multiple events occur on the same date. Audit assignment observations
   are ordered facts; they do not carry calendar-date `valid_from`/`valid_to` intervals.
5. Change detection is per dimension and null-safe (`IS DISTINCT FROM`). A new assignment is opened
   only when that dimension's watched value set differs from the immediately preceding eligible
   observation for that aircraft. An irrelevant event does not create an assignment.
6. De-duplication is consecutive, never global. `A -> B -> A` produces three audit assignments.
   Repeated reversion spells all remain queryable.
7. The complete audit sequence and date-visible state are separate products:
   - `aircraft_dimension_audit_assignment` retains every relevant same-day assignment observation in
     source order, owns sequence/spell analysis, and has no date interval;
   - `aircraft_dimension_daily_assignment` retains the final relevant observation per aircraft,
     dimension, and event date, and owns the positive-width half-open interval used by as-of
     reconstruction;
   - for an as-of calendar date, the daily assignment chosen from the last relevant observation on
     that date is visible for that dimension; and
   - earlier same-day observations remain in the audit sequence but are not asserted as distinct
     full-day states.
8. A same-day `In Service -> Storage -> In Service` sequence is a real status reversion spell. It
   has `storage_days = 0` and `same_day = true`; it MUST NOT disappear because its date-visible
   start and end values match.
9. Reloading identical events MUST produce identical event and assignment identities and ordering.

## P0-02 — Validity and date conventions

1. Model knowledge/state intervals are half-open: `valid_from <= date AND date < valid_to`.
2. Only `aircraft_dimension_daily_assignment` owns aircraft calendar-date validity. Its
   `valid_from` is a source event date, never ingestion time, and its `valid_to` is the next distinct
   daily assignment date for the same aircraft and dimension, clipped by aircraft existence.
   Same-day audit assignment observations own no date interval; their order is represented by the
   source ordering tuple, not by zero-width intervals or invented timestamps.
3. Schedule knowledge `valid_from` is the first eligible complete snapshot date that opens a
   presence/content segment. Its `valid_to` is the next eligible complete snapshot date that proves
   a content change or absence. An unchanged snapshot does not open a version.
4. Schedule operating dates use inclusive source bounds:
   `effective_date <= operating_date AND operating_date <= discontinue_date`, followed by the
   matching weekday flag. Implementations MAY normalize `discontinue_date + 1 day` to an exclusive
   internal bound, but results must retain the inclusive source meaning.
5. Source date `9999-12-31` means unknown future. It is normalized to an explicit
   `unknown_future` condition and MUST NOT be treated as a real event, milestone, or finite bound.
6. Model `9999-01-01` is the sole open-interval `valid_to` sentinel. It is derived, never copied
   from a source event. Source `9999-12-31` and model `9999-01-01` MUST remain distinguishable in
   lineage and tests.
7. Source `end_event_date` is retained as provenance and checked against derived intervals. It is
   not the authority for assignment `valid_to`; a disagreement is a surfaced data-quality result,
   not an automatic overwrite.
8. Null event/state values are observations, not an excuse to carry a previous known value forward.
   Every value-to-null or null-to-value transition emits its corresponding audit observation. A
   value-to-null transition opens an `UNKNOWN_STATE` daily interval only when null is the final
   date-visible observation for that dimension on that date; the daily gap persists until a later
   final-per-day resolvable assignment. An intraday null followed by a same-day value remains in the
   audit sequence but does not invent a calendar-date unknown gap.

## P0-03 — Aircraft existence and end of life

1. Aircraft identity can exist without a date-visible dimension value. The existence lower bound is
   a real `aircraft_start_of_life_date`; if unavailable, it is the first eligible event date. A date
   before the first dimension event MUST NOT be backfilled from a later event.
2. For this release, a real `aircraft_end_of_life_date` is an exclusive existence boundary:
   `existence_from <= date AND date < aircraft_end_of_life_date`. The boundary-date choice is
   provisional because the supplied field description does not state whether the terminal day is
   inclusive. The half-open choice is binding and visible in the demo until customer confirmation.
3. Null or source-sentinel end-of-life means no known finite upper bound and maps to model
   `9999-01-01` for interval evaluation.
4. Every daily dimension-assignment interval is clipped to the aircraft existence interval. Audit
   observations do not acquire clipped date intervals; an observation outside existence is rejected
   or quarantined under item 6. No as-of state is returned on or after a finite end-of-life boundary,
   even if the final daily source assignment would otherwise be open.
5. Query status distinguishes:
   - `OUTSIDE_EXISTENCE` before existence or on/after finite end of life;
   - `NO_RECORDED_STATE` inside existence but before the first assignment for a requested dimension;
   - `UNKNOWN_STATE` inside an explicit value-to-null or unresolved gap; and
   - `OK` when all requested dimensions are resolved.
   Composite reconstruction may return resolved dimensions alongside per-dimension status, but it
   MUST NOT claim a complete reconstruction unless every requested dimension is `OK`.
6. An end-of-life date earlier than existence or an eligible event on/after end of life is a hard
   temporal-integrity failure for the fixture/golden subset and a quarantined source-quality issue
   for non-golden filler.
7. Aircraft existence, assignment validity, and source `end_event_date` are three separately tested
   semantics.

## P0-04 — Attribute authority and temporal treatment

The detailed column-by-column matrix belongs to `SPEC-02`, but it MUST instantiate exactly these
ownership rules:

| Attribute group | Semantic owner | Temporal treatment |
|---|---|---|
| Aircraft ID, serial/line identifiers, source milestone dates, build location, original-delivery metadata | aircraft master | identity/current source fact; dates still honor unknown-future normalization |
| Aircraft start/end of life | aircraft master | existence bounds, not an assignment version |
| Registration, transponder, registration geography, storage/cargo, base, APU, aircraft-level dimensions, and aircraft-level weights when historical observations exist | aircraft history | `aircraft_state` versions |
| A master-only copy of an otherwise mutable APU/dimension/weight field | aircraft master | `CURRENT_ONLY`; prohibited from historical as-of reconstruction |
| Type hierarchy and type descriptive attributes | configuration reference | type definition; assignment comes from the event's configuration ID |
| Engine hierarchy, count, and multiple-type indicator | configuration reference | engine definition; assignment comes from the event's configuration ID |
| Lifecycle status and status provenance | aircraft history | independent `aircraft_status` assignments |
| Schedule content, carriers, operating bounds, capacity, and snapshot observation | schedule snapshots | per-schedule knowledge versions plus operating bounds |
| Airport and airline descriptive fields | reference sources | identity-only in v1; source effective periods retained as lineage, not modeled state |
| Passenger-flight plan | typed historical/forward canonical union | passenger-flight identity with source precedence and lineage |
| Flown leg, actual airports/times, cancellation/diversion, and next link | actual-flight source | aircraft-flight identity/actual fact |

When the same named field appears in master, history, configuration, or actuals, the semantic owner
above wins for the associated question. Current master values MUST NOT overwrite historical event
values. Actual type fields on a flown leg remain actual-source observations; aircraft as-of type and
engine enrichment comes independently from the aircraft history model and discrepancies are shown.

The conflict over whether APU, dimensions, and weights are immutable is resolved conservatively:
historical observations are versioned; master-only observations are explicitly current-only and are
not projected backward. A field is omitted from a historical claim if neither treatment is possible.

## P0-05 — Snapshot completeness and gaps

1. A snapshot calendar is authoritative for expected publish dates. Each date has explicit
   `present`, `complete`, source lineage, row count, and validation evidence. Completeness MUST NOT be
   inferred merely because some rows arrived.
2. A snapshot is eligible for schedule state/change inference only when `present = true` and
   `complete = true`. Incomplete rows may be retained for diagnostics but do not prove presence or
   absence.
3. A missing or incomplete snapshot never creates additions, removals, market entries/exits, state
   closures, or mass disappearance.
4. At the next complete snapshot after a gap, comparison is made to the last prior complete
   snapshot, with `crosses_snapshot_gap = true` and the missing dates exposed. These endpoints are
   adjacent in the eligible complete-snapshot sequence even though they are not adjacent calendar
   dates. Presence/absence is exactly observed at the later endpoint; the occurrence day inside the
   gap is unknown and MUST NOT be invented.
5. A schedule absent from the next snapshot in the eligible complete-snapshot sequence is an exact
   key removal observed at the newer publish date. If the comparison crosses a gap, the removal's
   observation date is exact while its occurrence date within the gap is unknown. A later presence
   opens a new segment even if content matches the old segment and is labeled `REAPPEARANCE` when an
   earlier complete absence is proven.
6. The latest-versus-seven-days market question requires both exact endpoint dates to be complete.
   It returns `ENDPOINT_INCOMPLETE` or `ENDPOINT_MISSING` rather than substituting a nearby date.
7. An unchanged complete snapshot creates no new route-state version or change event.

## P0-06 — Schedule grain and deterministic versions

1. `route` is the carrier-agnostic directional origin/destination identity.
2. `schedule_key` is the exact source schedule identity. Versioning is partitioned by
   `schedule_key`, never by route.
3. `route_state_key = schedule_key || '|' || valid_from`, where `valid_from` is the complete
   snapshot date that opened a coalesced presence/content segment. Raw per-day publish dates do not
   mint versions for unchanged content.
4. A route may have any number of concurrently open schedule states. A uniqueness constraint of one
   open state per route is invalid.
5. Before change detection, itinerary variants are reduced deterministically within
   `(schedule_key, publish_date)` by descending weekly frequency, descending total seats, ascending
   itinerary variation identifier, then ascending stable hash of the normalized source row. Nulls
   sort last in each business field. Reordering raw input cannot change the selected variant.
6. Content comparison is null-safe and excludes ingestion metadata. `SPEC-02` must list every
   watched schedule field. A presence segment closes on a proven key absence; a content segment also
   closes on a watched-field change.
7. Route-state lineage retains every contributing complete snapshot and the selected itinerary
   variant evidence.

## P0-07 — Schedule changes and key-shift candidates

1. A key present in both eligible comparison snapshots with a watched-field change is an
   `EXACT_KEY_PRESERVING_MODIFICATION`. Changed fields and old/new values are emitted.
2. A key present only before is an `EXACT_REMOVAL`; a key present only after is an
   `EXACT_ADDITION`. These exact presence facts are never deleted or relabeled by a heuristic.
3. A possible key-shifting amendment is a separate candidate link between an exact removal and an
   exact addition from the same eligible comparison. Candidate eligibility requires identical
   `(marketing_carrier, flight_number, origin, destination)` and overlapping inclusive operating
   date ranges. Operating carrier, days, times, equipment, capacity, and range differences are
   evidence fields, not hidden tie-breakers.
4. If one eligible removal and one eligible addition share the candidate signature, emit
   `CANDIDATE_UNIQUE`, confidence `MEDIUM`, with all evidence. It is not exact.
5. If either side has multiple eligible partners, emit an `AMBIGUOUS_CANDIDATE_GROUP`, confidence
   `LOW`, retaining every member and no chosen pair.
6. If there is no eligible partner, retain `UNPAIRED_REMOVAL` or `UNPAIRED_ADDITION`. Non-overlapping
   date-range shifts are a declared false-negative limitation of this conservative rule.
7. Only a future source-stable amendment identifier may promote a key-shift link to exact. A score,
   model, UI choice, or one-to-one coincidence MUST NOT do so.
8. Agent, notebook, and HTML output must preserve the words `exact`, `candidate`, `ambiguous`, and
   `unpaired`; they must never summarize all four as modifications.

## P0-08 — Knowledge and operating clocks

1. `knowledge_date` evaluates half-open route-state knowledge validity.
2. `operating_date` evaluates the inclusive effective/discontinue window and weekday pattern.
3. Capacity and route-frequency queries require both parameters. There is no one-date default. A
   natural-language request supplying only one date must be clarified before execution.
4. Schedule-change and market-update questions are explicitly knowledge-clock comparisons. They
   accept named knowledge endpoints and do not pretend to answer which schedules operate on an
   unspecified date.
5. A query may intentionally use one clock only when its catalog definition names that semantics
   (for example, snapshot market entry/exit). Every result carries the clock parameters actually
   applied.
6. Boundary tests cover the cross product of before/inside/at-end knowledge validity and
   before/inside/at-end operating validity. Knowledge `valid_to` is excluded; source operating
   `discontinue_date` is included.
7. Recurring schedule times remain `TIME` plus `arrival_day_indicator`. A local operating instance
   is constructed as `operating_date + local_departure_time` and
   `operating_date + arrival_day_indicator + local_arrival_time`. A UTC instance timestamp is
   constructed only from a source expanded timestamp or from an explicit source UTC offset/date
   conversion. If only UTC `TIME` values are available, UTC date alignment remains
   `UNRESOLVED_UTC_DATE`; the model retains the `TIME` and arrival-day evidence and MUST NOT combine a
   local operating date with UTC `TIME` by assumption. Midnight crossing is never inferred from
   comparing clock values alone.

## P0-09 — Carrier role and capacity

1. Marketing and operating airlines are separate roles and separate relationships. A query
   parameter is `carrier_role = marketing | operating`; a generic “by airline” request without a
   role is ambiguous and must be clarified.
2. Commercial capacity/frequency uses `carrier_role = marketing` and describes seats/frequency sold
   under each marketing schedule. It may show the same physical service under multiple marketers.
3. Physical capacity/frequency uses `carrier_role = operating`. It counts only a source-controlled
   physical-service representative. In the reduced schema, a non-codeshare/base row whose marketing
   carrier equals the operating carrier is the eligible representative; marketing-only codeshare
   rows are excluded. If no unambiguous representative exists, the service is reported as
   `UNRESOLVED_PHYSICAL_SERVICE` and is not guessed or counted.
4. If a future source supplies a stable operating-service/group identifier, that identifier may
   replace the conservative representative rule after a reviewed parity test. Fuzzy grouping by
   time/equipment MUST NOT be used to claim exact physical capacity.
5. Weekly frequency is summed across distinct eligible active schedule states after both clocks and
   carrier role are applied. Weekly seats are each schedule's weekly frequency multiplied by its
   source total seats, then summed; neither metric is multiplied by itinerary variants or codeshare
   marketing copies in physical mode.
6. Cabin fields retain source values and add exclusive analytic buckets. Because premium economy is
   a subset of economy in the forward source:
   `economy_excluding_premium = economy_class_seats - premium_economy_seats`, floored only for
   display after flagging a negative source inconsistency. Exclusive cabin sum is
   `first + business + premium_economy + economy_excluding_premium`; it is compared with
   `total_seats`. Source totals are never silently overwritten to force reconciliation.
7. Negative, null, or inconsistent cabin values produce quality flags and are excluded from an
   evidence-backed reconciled total, while raw values remain visible.
8. Market identity is `(carrier_role, resolved_airline_id, route)`. Entry means zero eligible
   schedule keys before and one or more after; exit is the reverse. Carrier resolution ambiguity
   prevents an exact airline-level entry/exit.

## P0-10 — Passenger flights, actual flights, and fulfillment

1. `passenger_flight` (plan/passenger view) and `aircraft_flight` (actual aircraft leg) remain
   distinct identities. Neither is collapsed into the other.
2. The canonical passenger-flight key is the typed composite of marketing carrier code, flight
   number, planned origin, planned destination, and operating date; every component is required. A
   source row with a null component is an `INVALID_PASSENGER_KEY` observation, identified for audit
   by `(source_system, stable_source_row_id)`, and does not create a canonical passenger-flight
   identity. If its stable source row ID is also null, it is quarantined. Historical and forward rows
   are normalized to one schema. On a canonical-key overlap, historical wins and both source
   lineages are retained; forward-only historical fields remain null rather than fabricated.
3. Source duplicates within a side are deterministically reduced by descending source publish date,
   ascending stable source row ID, then ascending stable normalized-row hash. Rows with identical
   normalized hashes are semantically duplicate; the lowest stable source row ID is retained. A
   source-precedence flag is present on every canonical row.
4. Fulfillment is optional in both directions and may be one passenger flight to many actual legs.
   Unmatched passenger and actual rows remain first-class results.
5. `EXACT_FULFILLMENT` requires an explicit stable source link or a non-null direct shared source ID
   that passes carrier/date sanity checks. A heuristic composite MUST NOT be labeled exact.
6. Heuristic fulfillment candidates require compatible carrier, flight number, operating date, and
   endpoint/stopover evidence. A unique compatible candidate is `HEURISTIC_CANDIDATE`; multiple
   candidates are an unlinked `AMBIGUOUS_CANDIDATE_GROUP`; invalid-key or incompatible observations
   are `UNMATCHED` with reason. Candidate links are stored separately from confirmed fulfillment.
7. Planned airports/times always come from the passenger/schedule side; actual airports/times always
   come from actual legs. Diversions MUST NOT overwrite the plan, and the plan MUST NOT repair actual
   rotation continuity.

## P0-11 — Aircraft rotation

1. The supported baseline is the source `next_flight_id` self-reference. A graph path implementation
   is optional and cannot be on the release critical path unless the installed runtime passes a live
   equality test against the baseline.
2. A daily rotation is selected by aircraft and source local `flight_departure_date`; legs are
   ordered by actual gate departure UTC, then `flight_id`. Every target leg must have the same
   `flight_departure_date` as the selected date. Cross-midnight arrivals remain on their departure-day
   leg, but a next link whose target departs on another local date terminates the selected-day segment
   with `OUTSIDE_SELECTED_DAY`. The selected date basis is returned in query metadata.
3. An operated-chain leg must be non-cancelled and have actual departure and arrival times. Cancelled
   or missing-time rows are retained as anomalies but not silently placed in the strict operated
   chain.
4. A next link is valid only when the target exists, is not self, has the same aircraft and selected
   local departure date, satisfies
   `target.actual_gate_departure_time_utc >= current.actual_gate_arrival_time_utc`, and the current
   actual arrival airport equals the target actual departure airport. Actual diverted arrival is
   authoritative for this continuity test.
5. Self-loops, cycles, missing targets, different-aircraft links, backward time, and broken actual
   airport continuity terminate the valid segment and emit a typed anomaly. Traversal has a visited
   set and a finite step bound.
6. The result returns ordered valid segments plus anomaly rows; it MUST NOT invent an edge to make a
   single chain. A clean golden aircraft/day has exactly one start, one finish, and full coverage.
7. Type and engine enrichment evaluates the independently versioned aircraft dimensions on each
   leg's source local departure date. Mixed-engine and unknown-gap rules still apply.

## P0-12 — Resolution, missing configurations, and mixed engines

1. Airport and airline code resolution outputs `EXACT`, `AMBIGUOUS`, `UNRESOLVED`, or
   `INVALID_INPUT`, plus raw code, method, candidate count, candidates, and source lineage. A
   concept-valued relationship is created only for `EXACT` cardinality one.
2. Controlled duplicate codes and reference effective dates are retained. Current-reference
   identity scope does not justify choosing one of multiple candidates.
3. Aircraft history is left-preserved through configuration resolution. A null or missing
   configuration ID closes previous known type and engine assignments at that event and opens
   unresolved gaps until resolvable assignments appear. When a configuration row resolves but only
   its type fields or only its engine fields are null/unresolvable, the gap is dimension-specific:
   the resolvable dimension remains known. No type/engine node is invented.
4. The pipeline records how many history rows the source-style inner join would have lost and names
   the affected event IDs. Golden fixtures assert the loss; canonical semantics do not silently
   discard those events.
5. The engine source supports one reported engine type, engine count, and a multiple-types flag. If
   the flag is true, output `mixed_engine_set_complete = false` and describe only the reported type.
   A second type, per-position fitment, or exact mixed-engine set is unsupported and MUST NOT be
   inferred.

## P0-13 — Snowflake/RAI responsibility and independent evidence

1. Snowflake owns physical ingestion, deterministic de-duplication, typed source union, resolution
   candidates, snapshot completeness, and interval candidates. It MUST NOT replace the required RAI
   temporal relationships and query logic with final answer tables.
2. RAI owns stable semantic identities/associations, per-dimension temporal validity, two-clock
   predicates, status sequence semantics, multi-open route associations, cross-domain enrichment,
   and the golden query logic.
3. Every `model.Table()` source is a demo-owned physical table with change tracking. A source view is
   materialized before binding. Account/role/application access, one-table sync, and one-table query
   are hard prerequisites, not inferred from import success.
4. Expected rows are hand-authored from named fixtures before SQL or PyRel implementation. SQL and
   RAI complete result sets both compare to that independent manifest; they do not validate each
   other by agreement alone.
5. The standalone upload artifact is generated from the canonical package when possible. Its schema
   inventory and smoke results must equal the package; textual similarity or import success is not
   enough.

## P0-14 — Evidence, performance, and fallback claims

1. Synthetic results prove functional behavior at representative shape only. They do not prove
   production scale, universal replacement, cost, security, or performance superiority.
2. Every timing artifact records scale, exact row counts, Python/SDK/CLI/engine versions, engine
   size/config, materialization state, cold/warm classification, and elapsed time. No source-size
   extrapolation is permitted.
3. Cold start, warm repeat, CDC initialization, and idempotent repeat are distinct measured cases.
   A producer's earlier successful run is not gate evidence.
4. UC1 is an independently runnable vertical slice. If UC2 is red, the query catalog, agent,
   notebook, HTML, and claims must expose only verified UC1 behavior plus an explicit UC2 limitation.
5. No green report may rely only on mocks, imports, deployment existence, or producer claims when a
   live success criterion exists.

## P0-15 — Curated query and agent behavior

1. The agent selects only from a curated query catalog with typed parameters. It does not generate
   arbitrary PyRel for the release path.
2. Missing clock or carrier-role parameters are clarification states, not opportunities to choose a
   plausible default. Invalid dates/IDs return typed errors. Empty exact results remain empty.
3. Exact changes, heuristic candidates, ambiguous groups, and unsupported questions are visibly
   distinct in every interface.
4. Unsupported mixed-engine-set, optimization, prediction, universal-comparison, or production-size
   questions return an explicit scope limitation and do not synthesize an answer.
5. Actual rotation uses actual airports/times; a prompt attempting to mix planned arrival with actual
   continuity is rejected or answered as an explicit plan-versus-actual comparison.

## Required negative fixture inventory

Fixture IDs and semantic assertions are frozen here. `DATA-01` will add concrete synthetic row IDs
and dates without changing the assertions.

| Fixture | Required pattern | Non-negotiable assertion |
|---|---|---|
| NF-A01 | null-to-value, value-to-null, same-day value-to-null-to-value, and irrelevant aircraft events | Null transitions remain audit observations; they open/close daily known/unknown intervals only when date-visible; irrelevant events mint no assignment. |
| NF-A02 | at least two `A -> B -> A` status spells, including three ordered same-day transitions | Every audit assignment remains; same-day spell returns zero days and date-visible state is the final event. |
| NF-A03 | type and engine changes on different dates, including unchanged observations between | Their intervals remain independent and do not align by force. |
| NF-A04 | null and non-resolving configuration IDs | History survives the left-preserved canonical path; known assignments close into unresolved gaps; inner-join loss is counted. |
| NF-A05 | real/unknown start/end-of-life and conflicting source `end_event_date` | Existence, derived assignment validity, and source provenance produce three separate assertions. |
| NF-S01 | duplicate itinerary variants plus reordered raw input | The same canonical row/hash is selected in every run. |
| NF-S02 | unchanged complete snapshot | No version or change event is created. |
| NF-S03 | missing snapshot and present-but-incomplete snapshot | Neither creates removals, additions, closure, or mass market exits. |
| NF-S04 | disappearance from a complete snapshot and later reappearance | Exact removal and a new reappearance segment are preserved, even when content repeats. |
| NF-S05 | key-preserving change, unique key shift, ambiguous key shift, and unpaired add/remove | Outputs are respectively exact, medium candidate, low ambiguous group, and unpaired; exact presence facts remain. |
| NF-S06 | several concurrent schedules on one route, including two for one carrier | All eligible states remain concurrently open; capacity sees each distinct service once. |
| NF-S07 | marketing/operating divergence, base operating row, marketing codeshare copy, and unresolved codeshare-only service | Marketing and operating results differ; physical capacity does not double-count and flags unresolved service. |
| NF-S08 | cabin values with premium economy as economy subset, mismatch, null, negative, and premium greater than economy | Raw values remain; reconciled totals/quality flags follow P0-09 and no source value is silently repaired. |
| NF-S09 | both-clock boundary cross-product | Knowledge end is excluded, operating discontinue is included, and dropping either clock changes at least one expected row. |
| NF-S10 | local/UTC midnight and positive arrival-day crossing, with and without explicit offset/expanded timestamps | Local instances and resolvable UTC instances are correct; insufficient UTC evidence yields `UNRESOLVED_UTC_DATE`; clock-value comparison alone is proven wrong. |
| NF-F01 | historical/forward key overlap and forward-only historical-null fields | Historical wins overlap with both lineages; forward-only nulls stay null. |
| NF-F02 | exact, heuristic, unmatched, one-to-many stopover, null-key, missing-source-ID, and ambiguous fulfillment | Invalid passenger keys are audit observations or quarantined and never canonical identities; exact/candidate/group/unmatched outputs stay separate and valid passenger/actual cardinalities are preserved. |
| NF-R01 | clean rotation plus self-loop, cycle, diversion, cancellation, missing time, missing target, different-aircraft link, outside-selected-day target, backward time, and broken continuity | Only validated same-day links form ordered segments; every invalid case emits its typed anomaly. |
| NF-R02 | actual leg whose as-of type/engine differs from actual-source descriptive fields | Independent enrichment is returned with a discrepancy; actual fields do not overwrite history. |
| NF-X01 | ambiguous/unresolved airport and airline codes | Only exact single matches create concept links; raw codes and candidates remain visible. |
| NF-X02 | engine row with multiple-types flag | Reported engine/count remain and complete mixed fitment is explicitly unsupported. |
| NF-E01 | cold load, warm repeat, first CDC sync, reordered-input repeat, and identical rerun | Timings are separately labeled; manifests/IDs/results are deterministic; repeat load adds no duplicates. |

## Hard tests

These are contract tests. Later tasks may add lower-level tests but may not weaken these assertions.

| Test | Required evidence |
|---|---|
| HT-01 | Three same-day events yield three stable audit keys after two clean generations/reloads. |
| HT-02 | Date-visible lookup returns the final same-day dimension observation. |
| HT-03 | Same-day and multi-spell `A -> B -> A` results retain every spell with correct day count. |
| HT-04 | An irrelevant event creates no assignment; null transitions remain audit observations and create daily gaps exactly when null is date-visible. |
| HT-05 | Every daily aircraft and schedule-knowledge interval includes its start and excludes its end; audit assignment observations are ordered facts with no date interval. |
| HT-06 | Source unknown-future and model open sentinel remain distinct through load and query. |
| HT-07 | Source `end_event_date` disagreement is surfaced without changing derived validity. |
| HT-08 | Before-existence, before-first-assignment, unknown-gap, and after-EOL statuses are distinct. |
| HT-09 | The exact EOL boundary date is excluded; the preceding date is eligible. |
| HT-10 | No assignment escapes a finite aircraft existence interval. |
| HT-11 | Every in-scope contract column has exactly one owner and one temporal treatment matching P0-04. |
| HT-12 | Missing/incomplete snapshots create zero absence-derived events. |
| HT-13 | A post-gap comparison exposes the gap and does not invent a change date inside it. |
| HT-14 | Exact seven-day market comparison refuses an ineligible endpoint. |
| HT-15 | Complete disappearance/reappearance closes and reopens distinct presence segments. |
| HT-16 | Raw reorder and duplicate variants produce byte-identical selected rows/manifests. |
| HT-17 | Repeated unchanged complete snapshots produce one coalesced route-state version. |
| HT-18 | One route has multiple valid concurrent states without uniqueness failure. |
| HT-19 | Key-preserving watched-field delta is exact and lists old/new changed values. |
| HT-20 | One-to-one eligible key shift remains a medium candidate plus exact add/remove. |
| HT-21 | One-to-many key shift remains a low-confidence ambiguous group with no chosen link; its exact additions/removals remain. |
| HT-22 | Ineligible/unpaired changes remain unpaired and are not hidden. |
| HT-23 | The both-clock boundary cross-product equals the frozen truth table. |
| HT-24 | Capacity execution fails parameter validation if either required clock is absent. |
| HT-25 | Local midnight/arrival-day instances and UTC instances with explicit evidence produce expected timestamps; UTC `TIME` without date-shift evidence returns `UNRESOLVED_UTC_DATE`. |
| HT-26 | Missing carrier role is a clarification state; marketing and operating outputs differ. |
| HT-27 | Physical capacity counts a codeshared physical service once and flags an unresolved-only copy. |
| HT-28 | Cabin exclusive sum and quality flags match every consistent/inconsistent fixture. |
| HT-29 | Market entry/exit is computed at `(carrier_role, airline, route)` grain only from eligible endpoints. |
| HT-30 | Historical rows win overlap; forward-only historical fields remain null with lineage. |
| HT-31 | Passenger and actual counts survive optional one-to-many fulfillment. |
| HT-32 | Exact, heuristic candidate, ambiguous group, invalid passenger key, quarantined missing-source-ID, and unmatched states do not merge. |
| HT-33 | Diversion preserves both planned and actual endpoints. |
| HT-34 | Clean actual rotation has one start/finish and exact ordered-leg equality with the oracle. |
| HT-35 | Every invalid link class, including `OUTSIDE_SELECTED_DAY`, terminates a segment and emits the expected anomaly. |
| HT-36 | Cancellation/missing time are retained but absent from the strict operated chain. |
| HT-37 | Each valid leg's type/engine equals independent local-date as-of reconstruction. |
| HT-38 | Resolution cardinality zero/one/many maps to unresolved/exact/ambiguous and only one creates a link. |
| HT-39 | Missing configurations produce unresolved gaps and a nonzero measured would-be inner-join loss. |
| HT-40 | Multiple-engine flag never yields a fabricated second engine type or complete set. |
| HT-41 | Live RAI smoke binds and queries a change-tracked physical table under the demo role. |
| HT-42 | All eight SQL and RAI complete result sets independently equal the frozen fixture manifest. |
| HT-43 | Package and standalone ontology inventories/smoke results are identical. |
| HT-44 | Timing artifacts contain scale, counts, versions, config, materialization state, and cold/warm labels. |
| HT-45 | Claim scan finds no universal, production, performance, cost, or security superiority claim. |
| HT-46 | UC1 executes from its own documented path when all UC2 artifacts are withheld. |
| HT-47 | Canonical/adversarial prompts select the expected catalog ID and exact typed parameters. |
| HT-48 | Missing clock/carrier, invalid IDs/dates, and unsupported mixed engines fail safely. |
| HT-49 | Agent/notebook/HTML preserve exact/candidate/ambiguous/unpaired and plan/actual labels. |

## Provisional decisions and rollback tests

These decisions are frozen for this release but deliberately easy to reverse if authoritative
clarification arrives. Reversal requires an append-only decision-log entry, updates to the source
contract and frozen expected manifest, and rerunning every named test; it never occurs as a quiet
implementation patch.

| Decision | Why this treatment is safest now | Rollback path and required tests |
|---|---|---|
| End-of-life date is exclusive | Uniform half-open semantics avoid asserting state on a terminal boundary whose inclusive meaning is undocumented. | Change only the existence-boundary normalizer to `end_date + 1 day`; update boundary fixtures; rerun HT-05 and HT-08 through HT-10 plus every as-of query. |
| Final event of a calendar day is date-visible | The source gives date plus audit sequence but no intraday timestamp; choosing an earlier event would be arbitrary. | If source supplies effective timestamps, change date-visible evaluation to timestamp visibility while preserving audit IDs; rerun HT-01 through HT-05 and status oracles. |
| Historically observed APU/dimensions/weights are versioned; master-only values are current-only | This avoids projecting a current value backward while respecting event-history change detection. | Move a named field only with source lineage proving immutability/history; update the P0-04 matrix; rerun HT-11 and every aircraft reconstruction oracle. |
| Key shifts are categorical candidates, never exact | The source key changes with operating dates and contains no stable amendment ID. | Promote only after a stable source amendment ID is contracted; retain old candidate evidence; rerun HT-19 through HT-22 and agent label tests. |
| Physical capacity excludes marketing-only codeshare rows when no stable physical-service ID exists | Exclusion prevents a false double count; unresolved output makes possible undercount visible. | Adopt a stable source physical-service ID/group and compare old/new results; rerun HT-26 through HT-29 before replacing the rule. |

## G1 release checklist

`SPEC-02` may declare G1 green only when:

1. its source and attribute-authority contracts implement every P0 decision;
2. every in-scope column has exactly one semantic owner and temporal treatment;
3. every negative fixture has concrete synthetic row IDs/dates in `DATA-01`;
4. every hard test is mapped to an executable owner and expected result;
5. no interface silently defaults a missing clock, carrier role, match confidence, or plan/actual
   dimension; and
6. identity, validity, carrier, amendment, end-of-life, and data-gap rules remain fully specified.
