# SPEC-02 Neo4j-to-RAI ontology mapping

## Mapping contract

This document maps every in-scope supplied graph node and edge to the proposed RelationalAI
ontology without copying the graph's unsafe assumptions. It is a functional parity design for the
eight named workloads, not a claim that either representation is universally superior.

The RAI design is domain-first and source-grounded:

- concepts have stable identities from authoritative keys;
- a functional Property is used only after the source multiplicity/FD gate passes;
- one-to-many, many-to-many, multi-attribute, and temporal links use Relationships or association
  concepts;
- same-type roles such as route origin/destination and actual departure/arrival are explicitly
  labeled;
- ordered audit observations and date-visible daily intervals remain separate;
- temporal/provenance fields live on association concepts, preserving the graph-edge semantics
  without pretending that a multi-attribute edge is a scalar property; and
- raw codes and unresolved/ambiguous candidate evidence remain queryable even when no concept link
  can be asserted.

`SOURCE_CONTRACT.md` defines physical lineage and multiplicity. `ATTRIBUTE_AUTHORITY.md` chooses one
owner/treatment for each field. `SEMANTIC_DECISIONS.md` and D-0003 through D-0008 are binding.

## Proposed RAI semantic inventory

### Identity and reference concepts

| RAI concept | Stable identity | Authoritative source/derivation | Notes |
|---|---|---|---|
| `Aircraft` | AM-01 `aircraft_id` | Aircraft master | Registration, type, engine, status, and tail are not identity. DV-01/DV-02 bound existence. |
| `AircraftEvent` | AH-01 `aircraft_history_id` | Aircraft history | Ordered by DV-03; missing required order/identity fields are quarantined. |
| `AircraftConfiguration` | AC-01 | Configuration reference | Join target left-preserves every eligible event. |
| `AircraftType` | AC-05 `aircraft_subseries` | Configuration reference after FD proof | No node is invented when subseries/definition resolution is absent or ambiguous. |
| `EngineType` | AC-14 `engine_subseries` | Configuration reference after FD proof | One reported type only; DV-09 exposes mixed-set incompleteness. |
| `AircraftStatus` | exact non-null raw AH-09 value | Aircraft history | No trim/case normalization is applied in SPEC-02; repeated assignments remain separate association instances. |
| `Route` | DV-12 typed directional endpoint pair | Selected schedule observation | Carrier-agnostic and directional; raw endpoint codes survive failed resolution. |
| `Schedule` | SS-01 `schedule_key` | Schedule snapshot | Exact source schedule identity and route-state version partition. |
| `PassengerFlight` | DV-20 typed composite | Historical-over-forward canonical union | Plan/passenger identity; invalid composites create audit evidence, not concepts. |
| `AircraftFlight` | AF-01 `flight_id` | Actual-flight source | Actual flown-leg identity; separate from PassengerFlight. |
| `Airport` | AP-01 `airport_id` | Airport reference | Identity-only in v1; source effective periods are lineage. |
| `Airline` | AL-01 `airline_id` | Airline reference | Identity-only in v1; controlled duplicates remain resolution evidence. |
| `SnapshotDate` | SC-01 | Snapshot calendar | Explicit eligibility control, not inferred from snapshot rows. |

### Association, version, and evidence concepts

| RAI association/evidence concept | Stable identity | Roles/payload | Required multiplicity treatment |
|---|---|---|---|
| `AircraftDimensionAuditAssignment` | DV-04 | one Aircraft, one AircraftEvent, `dimension`, watched payload, optional resolved target, order/provenance | Aircraft/event targets are functional only after key proof; inverse Aircraft-to-assignments is one-to-many. No date interval. |
| `AircraftDimensionDailyAssignment` | DV-05 | one Aircraft, one dimension, final daily source observation, optional resolved target, DV-06/DV-07, DV-08 resolution and DV-33 query status | One-to-many from Aircraft; association owns half-open validity and provenance. |
| `AircraftStateAuditAssignment` | DV-04 where dimension=`aircraft_state` | AH-17 through AH-31 | Multi-attribute temporal association; never bundled into a scalar. |
| `AircraftStateDailyAssignment` | DV-05 where dimension=`aircraft_state` | date-visible state payload plus interval | Neo4j `AIRCRAFT_STATE/HAS` parity projection. |
| `AircraftTypeAuditAssignment` / `AircraftTypeDailyAssignment` | DV-04/DV-05 where dimension=`aircraft_type` | event/config evidence, optional exact AircraftType | Missing config creates unresolved gaps without dropping event. |
| `EngineTypeAuditAssignment` / `EngineTypeDailyAssignment` | DV-04/DV-05 where dimension=`engine_type` | event/config evidence, optional exact EngineType, count, DV-09 | Type and engine clocks are independent. |
| `AircraftStatusAuditAssignment` / `AircraftStatusDailyAssignment` | DV-04/DV-05 where dimension=`aircraft_status` | optional AircraftStatus, AH-08/AH-12 provenance, interval on daily only | Audit sequence preserves every reversion, including zero-day same-day spell. |
| `CodeResolutionCode` (D-0019 supersedes the row-scoped `CodeResolution`) | `(domain, method, raw_code)` | resolved identity, candidate count, resolution status, matched code systems, DV-10/DV-11 | Stable result exists at zero/one/many candidates. Concept-valued link exists only for exact cardinality one. **As built the grain is the distinct raw code, not the source row.** D-0019: the row-scoped `MODEL_INPUT.CODE_RESOLUTION` is 546,494 rows - 3.8 times the whole SOURCE layer - and link semantics only ever ask "does this raw code resolve to exactly one identity", which is a property of the code. The row-scoped table stays materialized and reachable from SQL so the NF-X01 truth table and any audit of a specific ambiguous code remain answerable. |
| `CodeResolutionCodeCandidate` | `(resolution, candidate_id)` where `resolution` is a `CodeResolutionCode` | one CodeResolutionCode and one Airport/Airline candidate | Zero-to-many from resolution result; avoids nullable candidate identity for unresolved inputs. Renamed with its parent under D-0019. |
| `RouteState` | DV-13 `route_state_key` | one Schedule, one Route, SS-04 through SS-38, DV-14/DV-15, carrier/endpoint resolution statuses | Versioned by Schedule, not Route; Route-to-state is one-to-many and can be multi-open. |
| `RouteStateSnapshotLineage` | `(route_state_key, SS-03, SS-40)` | contributing SnapshotDate, selected variant/hash | Many observations per coalesced state. |
| `ScheduleExactChange` | deterministic endpoint/key/kind/field key | exact old/new values, presence/content kind, DV-16 | Exact facts stay separate from amendment candidates. |
| `ScheduleAmendmentEvidence` - **built as four concepts**: `ScheduleAmendmentSide`, `ScheduleAmendmentCandidate` (DV-35), `ScheduleAmendmentGroup` (DV-36), `ScheduleAmendmentGroupMember` (DV-37) | DV-35 candidate, DV-36 group, DV-37 member, plus the per-side signature and eligibility verdict | DV-18/DV-19, DV-34 comparison, removed/added schedules, typed candidate signature and evidence | Many-to-many evidence; ambiguous groups have all members and no chosen pair. The member identity is its own id column because `AMENDMENT_GROUP_ID` is non-null on only 3 of 12,029 member rows - unpaired evidence carries none (D-0020 A6) - so the group link is an optional `Property` and never a nullable identity component. |
| `InvalidPassengerObservation` | `(source_system, stable_source_row_id)` | missing key components, raw lineage, DV-22 | No PassengerFlight identity; missing source row ID quarantines. |
| `PassengerSourceLineage` | `(DV-20, source_system, DV-46)` | DV-21, source publish/DV-43 evidence | One canonical passenger flight may retain all historical/forward lineage even when a stable source ID is null. |
| `ExactFulfillment` | DV-39 | PH-01=AF-01 shared historical ID plus resolved-carrier/operating-date sanity | Optional; several PH lineage rows coalesced to one DV-20 can confirm one passenger service to many actual legs. Absence of equality leaves only candidates. |
| `FulfillmentCandidateEvidence` - **built as two concepts**: `FulfillmentCandidate` (DV-40) and `FulfillmentGroupMember` (DV-42 member grain) | DV-40 candidate, DV-42 member | DV-23, DV-38 carrier/date/ordered stopover compatibility | Separate from confirmed fulfillment; unique-per-actual candidates may preserve one-to-many stopovers, while competing-plan groups remain unlinked. **No separate DV-41 group concept exists**: `MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP` stores the group at member grain with `FULFILLMENT_GROUP_ID` non-null on 3 of 23,887 rows (D-0020 A6), so the group is an optional property of the member rather than an entity. |
| `RotationLinkValidation` | `(AF-01, target_token)` with `NO_TARGET` terminal token | DV-24/DV-25, DV-45 actual continuity/time/date evidence, DV-52/DV-53 flag quality | Raw target is zero-or-one; accepted link is conditional, terminals/anomalies retained without nullable identity. |
| `QueryExecutionContext` - **NOT a model concept as built** | query invocation ID | DV-29 carrier role, DV-30 knowledge date, DV-31 operating date | Capacity/frequency requires all three; missing input is a clarification/error state. **As built it is a frozen Python dataclass at the query API boundary, not a RAI Concept**: its identity is a query invocation, the model is append-only, and PyRel warns after fifty `define()` calls from one call site, so a concept would need one `define()` per invocation. Contract parity is preserved - the three values are validated before the first RAI call and echoed verbatim into every result frame - and only the storage location changes. Owner: `QUERY-INT`. |

Association concepts are deliberate. They preserve identity, validity, provenance, resolution
status, and multiplicity on facts that cannot safely be expressed as one functional scalar. Inverse
relationships may be exposed for query ergonomics, but they do not change cardinality.

## Complete supplied Neo4j node mapping

| Supplied Neo4j label | Supplied grain/key | RAI mapping | Parity treatment / intentional difference |
|---|---|---|---|
| `AIRCRAFT` | physical aircraft / `aircraft_id` | `Aircraft` | Direct identity parity. Immutable/current facts and existence bounds are explicit; mutable master copies are current-only. |
| `AIRCRAFT_STATE` | mutable state version / aircraft plus `valid_from` | `AircraftStateDailyAssignment`, with `AircraftStateAuditAssignment` retained separately | Daily association supplies point-in-time parity. Audit association fixes same-day key collisions and preserves earlier same-day/reversion evidence that the coarse state key can lose. |
| `AIRCRAFT_TYPE` | type definition / `aircraft_subseries` | `AircraftType` | Direct definition parity after uniqueness/FD proof; assignment validity belongs to type-assignment association. |
| `ENGINE_TYPE` | engine definition / `engine_subseries` | `EngineType` | Direct definition parity for the one reported type. Exact mixed fitment is explicitly unsupported. |
| `AIRCRAFT_STATUS` | lifecycle status value / status code | `AircraftStatus` | Direct value parity; audit/daily assignment associations retain repeated occurrences and provenance. |
| `ROUTE` | carrier-agnostic directional O&D | `Route` | Direct identity parity, with typed origin/destination roles and raw-code resolution status. |
| `ROUTE_STATE` | schedule knowledge version / schedule key plus `valid_from` | `RouteState` | Direct state parity. Version partition is Schedule; many concurrent states per Route are allowed. Both clocks are explicit. |
| `PASSENGER_FLIGHT` | planned passenger service on one date / composite key | `PassengerFlight` | Direct identity parity after typed historical/forward union and invalid-key handling. |
| `AIRCRAFT_FLIGHT` | actual flown leg / `flight_id` | `AircraftFlight` | Direct identity parity; actual facts remain distinct from plan and aircraft-history enrichment. |
| `AIRPORT` | airport identity / internal ID | `Airport` | Identity-only parity; source effective periods retained as lineage, not modeled state. |
| `AIRLINE` | airline identity / internal ID | `Airline` | Identity-only parity; controlled duplicates and effective periods remain resolution evidence. |

No supplied node label is omitted. `AircraftEvent`, `Schedule`, `SnapshotDate`, resolution, change,
lineage, fulfillment-candidate, and rotation-validation concepts are RAI/Snowflake-normalized
extensions required for stable identity, auditability, and ambiguity rather than replacements for
supplied nodes.

## Complete supplied Neo4j edge mapping

| Supplied edge | RAI mapping | Roles and payload | Multiplicity / assertion policy |
|---|---|---|---|
| `(AIRCRAFT)-[:HAS]->(AIRCRAFT_STATE)` | `Aircraft.state_assignments` (dimension-scoped `Relationship` to `AircraftStateDailyAssignment`), plus the unscoped `Aircraft.daily_assignments` / `Aircraft.audit_assignments` for the general case | aircraft, state assignment, DV-06/DV-07, event lineage | One-to-many association. Daily parity plus separate audit history. **As built:** the four Neo4j dimensions share one physical `AircraftDimensionDailyAssignment` concept discriminated by `dimension`; the four subtypes are `extends=` views with `identity_includes_type=False`, not four entity sets. The four scoped relationships off `Aircraft` (`state_assignments`, `type_assignments`, `engine_assignments`, `status_assignments`) restore the four visibly distinct outbound edges. |
| `(AIRCRAFT)-[:CONFORMED]->(AIRCRAFT_TYPE)` | `AircraftTypeDailyAssignment` links Aircraft to optional exact AircraftType, **plus the direct one-hop `Aircraft.conformed_to(Aircraft, AircraftType, valid_from, valid_to)`** | aircraft/type roles, DV-06/DV-07, AH/AC resolution/provenance | One-to-many over time; zero target in unresolved gap. Audit assignments preserve every event-level change. The direct reading carries the two supplied edge properties so a one-hop Cypher pattern stays one hop; the two-hop path through the assignment remains for the rest of its payload. |
| `(AIRCRAFT)-[:EQUIPPED]->(ENGINE_TYPE)` | `EngineTypeDailyAssignment` links Aircraft to optional exact EngineType, **plus the direct one-hop `Aircraft.equipped_with(Aircraft, EngineType, valid_from, valid_to)`** | aircraft/engine roles, DV-06/DV-07, count, DV-09, lineage | One-to-many over time; zero target in unresolved gap; no fabricated second type. |
| `(AIRCRAFT)-[:ASSIGNED]->(AIRCRAFT_STATUS)` | `AircraftStatusDailyAssignment`, plus audit assignment sequence, **plus the direct one-hop `Aircraft.assigned_status(Aircraft, AircraftStatus, valid_from, valid_to)` and the inverse `AircraftStatus.daily_assignments`** | aircraft/status roles, DV-06/DV-07, AH-08/AH-12 | Daily validity for as-of; audit association for all reversion spells and same-day zero-day spell. The inverse from `AircraftStatus` is what makes "which aircraft were ever in Storage" enterable from the status node, as it is in Cypher. |
| `(ROUTE)-[:HAS]->(ROUTE_STATE)` | Route to `RouteState` | route/state roles, DV-14/DV-15, SS-08/SS-09, lineage | One-to-many and multi-open. No one-open-per-route FD. |
| `(ROUTE)-[:STARTS]->(AIRPORT)` | Route `origin` exact Airport link | explicitly labeled origin role; SS-10/raw status | Functional only for exact one-candidate resolution; raw code retained otherwise. |
| `(ROUTE)-[:ENDS]->(AIRPORT)` | Route `destination` exact Airport link | explicitly labeled destination role; SS-11/raw status | Functional only for exact one-candidate resolution; raw code retained otherwise. |
| `(AIRLINE)-[:OPERATES]->(ROUTE_STATE)` | RouteState `operating_airline` exact `Property`; the inverse `Airline.operates` is an **`.alt()` reading over the same fields, not a second `Relationship`** | explicitly labeled operating role; SS-05 and resolution | Zero-or-one exact link per state after cardinality proof; raw code/status otherwise. The `.alt()` form matters and is not a detail: an alternative reading refers to the same underlying relationship fields, so it adds a name and **never an inverse functional dependency**. That is the mechanism behind the multi-open route result. |
| `(AIRLINE)-[:COMMERCIALIZES]->(ROUTE_STATE)` | RouteState `marketing_airline` exact `Property`; the inverse `Airline.commercializes` is an **`.alt()` reading over the same fields, not a second `Relationship`** | explicitly labeled marketing role; SS-04 and resolution | Zero-or-one exact link per state after cardinality proof; never merged with operating role. |
| `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)` | `RouteStateSchedules` / `RouteState.schedules`, a derived multi-valued `Relationship`, with the `.alt()` inverse `PassengerFlight.scheduled_by` (`computed_schedule.py`) | exact schedule identity where available; passenger publish date in DV-14/DV-15; passenger operating date within inclusive SS-08/SS-09 and matching weekday; plan lineage | Potential one-to-many; no functional claim. Missing schedule identity or failed clock applicability remains unlinked/visible. **Live population is zero pairs**, and the cause is data rather than the rule: `PASSENGER_FLIGHT_CANONICAL.schedule_key` is non-null on 1 of 19,996 rows, and that one key (`SYN-SK-HIST_700`) has no `ROUTE_STATE` at all. The edge is declared, derived and evaluated without error; it is unexercised by the shipped fixture. |
| `(AIRCRAFT_FLIGHT)-[:FULFILLED]->(PASSENGER_FLIGHT)` | `ExactFulfillment` association | actual leg, planned passenger service, exact evidence | Optional both ways; one passenger flight to many actual legs. Heuristics live separately. |
| `(AIRCRAFT_FLIGHT)-[:STARTED]->(AIRPORT)` | AircraftFlight `actual_origin` exact Airport link | explicitly labeled actual-origin role; AF-08/raw status | Zero-or-one exact link; raw code/status retained. |
| `(AIRCRAFT_FLIGHT)-[:ENDED]->(AIRPORT)` | AircraftFlight `actual_destination` exact Airport link | explicitly labeled actual-destination role; DV-45 from AF-09, with AF-10/AF-12 reconciliation evidence | Zero-or-one exact link. AF-09 is the post-diversion actual endpoint; mismatch with diversion evidence terminates continuity and is never repaired. |

All thirteen supplied edges are mapped and all thirteen are implemented in
`rai_code/aviation_model/`; `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)` is derived rather than
loaded and is currently unexercised by the fixture, as noted in its row. Validity and
multi-attribute edge payloads are association properties, not copied onto target identities. This
keeps repeated assignments and concurrent states distinct.

Corrected 2026-09-02 by MODEL-01 after the FIDELITY-01 audit. The earlier text asserted "no
supplied edge is omitted" while `SCHEDULES` had no implementation behind it. The claim is now
true; it was not when it was written, and a published parity claim with no code behind it is the
one defect this document cannot carry.

## Required cross-use-case extensions

| Extension | RAI representation | Evidence / rule |
|---|---|---|
| Actual leg belongs to physical aircraft | AircraftFlight `aircraft` exact link plus inverse Aircraft-to-flights Relationship | AF-02 exact identity match; null/unresolved remains visible. Enables independent UC1 enrichment. |
| Actual leg points to next actual leg | `RotationLinkValidation` and accepted `next_flight` link | AF-20 validated using same aircraft/local day, nondecreasing actual UTC time, AF-08/DV-45 continuity, no self/cycle/missing target or diversion conflict. |
| Plan versus actual endpoints/times | explicit comparison using PassengerFlight plan and AircraftFlight actual facts | Neither side overwrites the other; diversion preserves both. |
| As-of type/engine on each actual leg | join AF-06 to independent daily type/engine assignments | Half-open date-visible evaluation; actual descriptive AF-17 through AF-19 become discrepancy evidence only. |
| Exact/candidate code links | `CodeResolution` plus optional exact concept link | Only status `EXACT` with cardinality one links. |
| Exact/candidate schedule amendments | `ScheduleExactChange` and separate `ScheduleAmendmentEvidence` | Exact add/remove remains even when candidate evidence exists. |

## Clock, version, and multiplicity semantics

1. Aircraft audit assignments are identified by dimension, aircraft, source event date, source
   row sequence, and source history ID. They are ordered facts without calendar intervals.
2. Aircraft daily assignments select the final relevant observation per dimension/day and own
   positive-width half-open validity. Daily intervals are clipped to DV-01/DV-02; the finite EOL
   date itself is excluded under D-0003.
3. RouteState knowledge validity is half-open DV-14/DV-15. Operating validity is inclusive SS-08
   through SS-09 plus the matching weekday. Capacity/frequency requires both dates.
4. A Route may have many concurrent open RouteStates because state versions partition by Schedule,
   not Route. An unchanged complete observation contributes lineage without minting a state.
5. Marketing and operating Airline roles never collapse. Physical capacity uses only the
   D-0007 base representative; unresolved codeshare-only service remains visible and uncounted.
6. PassengerFlight and AircraftFlight remain separate. Confirmed fulfillment is optional and
   one-to-many from passenger plan to actual legs. Candidates do not satisfy confirmed edges.
7. Airport/Airline links are optional because code resolution can be zero/one/many. Raw codes and
   candidate sets are always preserved.

## P0 rule coverage

| Frozen rule | Contract realization | RAI ontology anchor | Downstream executable evidence |
|---|---|---|---|
| P0-01 | AH identity/order; DV-04/DV-05 split; consecutive null-safe watched sets | Audit and daily dimension assignment concepts | HT-01 through HT-04 in DATA-02/DATA-04 and UC1 queries. |
| P0-02 | Source/model sentinels separated; DV-06/DV-07 half-open; AH-06 lineage only | Daily assignments and RouteState own intervals; audit assignments own none | HT-05 through HT-07. |
| P0-03 | DV-01/DV-02 existence; finite AM-08 exclusive; intervals clipped | Aircraft existence plus DV-33 per-dimension query status | HT-08 through HT-10. |
| P0-04 | Every AM/AH/AC/SS/PF/PH/AF/AP/AL/SC ID has one matrix row | Source-bound Properties/association payloads follow owner, never label coincidence | HT-11 exact inventory comparison. |
| P0-05 | SC eligibility controls state inference; DV-16 exposes gaps | SnapshotDate and RouteStateSnapshotLineage | HT-12 through HT-15. |
| P0-06 | SS deterministic selection; DV-13 partitioned by SS-01; multi-open Route | Schedule, Route, RouteState, lineage association | HT-16 through HT-18. |
| P0-07 | Exact changes and amendment evidence are separate concepts | ScheduleExactChange and ScheduleAmendmentEvidence | HT-19 through HT-22. |
| P0-08 | DV-30/DV-31 required; DV-47 through DV-51 implement provisional D-0008 offset/time evidence | QueryExecutionContext plus RouteState two-clock predicates | HT-23 through HT-25. |
| P0-09 | Separate marketing/operating links; DV-26/DV-27/DV-28 | Role-labeled RouteState carrier links and capacity derivations | HT-26 through HT-29. |
| P0-10 | Typed PF/PH union; DV-20/21/22; exact and candidate fulfillment split | PassengerFlight, invalid/source lineage, ExactFulfillment, candidate evidence | HT-30 through HT-33. |
| P0-11 | AF actual facts; DV-24/DV-25/DV-45/DV-52/DV-53; next link validation; AF-06 enrichment | AircraftFlight, RotationLinkValidation, Aircraft cross-link | HT-34 through HT-37. |
| P0-12 | DV-10/DV-11 zero/one/many; left-preserved config; DV-09 | CodeResolution and optional targets; engine completeness limitation | HT-38 through HT-40. |
| P0-13 | Canonical physical tables stop before final answers; RAI owns associations/predicates | Core source-bound and computed semantic layers; generated standalone inventory parity | HT-41 through HT-43. |
| P0-14 | Scope/omission policy below; UC1 contracts have no UC2 dependency | Evidence metadata and independently runnable UC1 subset | HT-44 through HT-46. |
| P0-15 | Required typed QueryExecutionContext; exact/candidate/actual-plan labels | Curated catalog consumers over the ontology | HT-47 through HT-49. |

## Hard-test traceability

Every frozen hard test has an implementation owner, contracted inputs, and expected evidence. These
rows freeze the test intent; later tasks may add tests but may not weaken them.

| Test | Contracted inputs / ontology anchors | Required later evidence | Owner task(s) |
|---|---|---|---|
| HT-01 | AH-01/03/04/05 and DV-04 | Three stable same-day audit keys across two generations/reloads. | DATA-02, DATA-04 |
| HT-02 | Final ordered audit observation and DV-05/DV-06 | Date-visible lookup equals final same-day value. | DATA-04, QUERY-UC1 |
| HT-03 | Status audit assignments, AH-09 | Every multi-spell and zero-day same-day `A -> B -> A` spell returned. | DATA-04, QUERY-UC1 |
| HT-04 | Per-dimension watched sets and null-safe comparison | Irrelevant event mints no assignment; date-visible null alone opens daily gap. | DATA-04, QUERY-UC1 |
| HT-05 | DV-06/07 and DV-14/15; audit has no interval | All starts included, ends excluded; no audit date interval. | DATA-04 |
| HT-06 | Source sentinel normalization and model open sentinel | Source unknown-future remains distinguishable from open interval. | DATA-04 |
| HT-07 | AH-06 versus DV-07 | Disagreement surfaced without changing derived closure. | DATA-04 |
| HT-08 | DV-01/02/08/33 | `OUTSIDE_EXISTENCE`, `NO_RECORDED_STATE`, `UNKNOWN_STATE`, and `OK` distinct. | DATA-04, QUERY-UC1 |
| HT-09 | AM-08/DV-02 | Day before EOL eligible; exact EOL date excluded. | DATA-04, QUERY-UC1 |
| HT-10 | DV-06/07 clipped to DV-01/02 | No daily assignment escapes finite existence. | DATA-04 |
| HT-11 | Field IDs in SOURCE_CONTRACT and ATTRIBUTE_AUTHORITY | Exact one-to-one inventory with one owner/treatment; no missing/duplicate ID. | SPEC-02, GATE-01 |
| HT-12 | SC-01/02/03 | Missing/incomplete dates create zero absence-derived events. | DATA-04 |
| HT-13 | Eligible SC sequence and DV-16 | Post-gap comparison exposes dates/gap and no invented internal change date. | DATA-04, QUERY-UC2 |
| HT-14 | Exact SC endpoints | Seven-day comparison returns endpoint missing/incomplete status. | DATA-04, QUERY-UC2 |
| HT-15 | DV-13/14/15 presence segments | Complete disappearance closes and reappearance opens distinct segment. | DATA-04, QUERY-UC2 |
| HT-16 | SS-22/30/39/40 ranking | Reordered/duplicate raw inputs yield byte-identical canonical selection. | DATA-02, DATA-04 |
| HT-17 | SS null-safe watched set and RouteState lineage | Unchanged complete snapshots coalesce to one state. | DATA-04 |
| HT-18 | Route-to-RouteState one-to-many | Concurrent open states on one route load/query without FD failure. | DATA-04, MODEL-01 |
| HT-19 | ScheduleExactChange over SS-04 through SS-38 | Key-preserving delta exact with field-level old/new values. | DATA-04, QUERY-UC2 |
| HT-20 | DV-18/19 unique candidate | Medium candidate plus untouched exact add/removal. | DATA-04, QUERY-UC2 |
| HT-21 | Ambiguous group association | Low group retains every member, no chosen link, exact facts preserved. | DATA-04, QUERY-UC2 |
| HT-22 | Unpaired candidate evidence | Ineligible/unpaired facts visible and not summarized away. | DATA-04, QUERY-UC2 |
| HT-23 | DV-14/15, SS-08/09/14-20, DV-30/31 | Full both-clock boundary truth table equals manifest. | DATA-04, QUERY-UC2 |
| HT-24 | QueryExecutionContext | Capacity validation fails if either clock absent. | QUERY-UC2, QUERY-INT |
| HT-25 | SS/PF/PH local, UTC, offset, arrival-day fields and DV-47 through DV-51 | Positive/negative/zero offset, both endpoints, arrival-day and midnight shifts, expanded precedence, and unresolved evidence match the binding provisional D-0008 truth table. | DATA-04, QUERY-UC2 |
| HT-26 | DV-29 and separate SS-04/SS-05 links | Missing role clarifies; marketing and operating results differ. | QUERY-UC2, AGENT-02 |
| HT-27 | SS-35, role resolution, DV-28 | Physical service counted once; unresolved-only copy flagged/excluded. | DATA-04, QUERY-UC2 |
| HT-28 | SS-30 through SS-34, DV-26/27 | Exclusive cabin sum and every quality flag equal fixture manifest. | DATA-04, QUERY-UC2 |
| HT-29 | DV-29, exact airline resolution, DV-12, eligible SC endpoints | Market entry/exit grain is exactly carrier role, airline, route. | DATA-04, QUERY-UC2 |
| HT-30 | PF/PH union and DV-21 | Historical wins overlap; forward-only historical-null fields stay null with lineage. | DATA-04 |
| HT-31 | PassengerFlight, AircraftFlight, ExactFulfillment | Independent counts survive optional one-to-many association. | DATA-04, MODEL-01 |
| HT-32 | DV-22/23 and separate evidence concepts | Exact/heuristic/ambiguous/invalid/quarantine/unmatched never merge. | DATA-04, QUERY-INT |
| HT-33 | PF/PH planned endpoints and AF-08/DV-45 actual endpoints with AF-10/12 evidence | Diversion preserves plan and actual separately; conflict is explicit. | DATA-04, QUERY-ROT |
| HT-34 | AF-01/02/06/08/13/14/20, DV-45, and accepted link | Clean rotation one start/finish and exact ordered equality. | DATA-04, QUERY-ROT |
| HT-35 | DV-24/25/45/52/53 | Every invalid class, including outside selected day and diversion endpoint conflict, terminates and emits anomaly. | DATA-04, QUERY-ROT |
| HT-36 | AF-11/13/14 and DV-52 | Cancelled/missing-time/unknown-cancellation rows retained but excluded from strict chain. | QUERY-ROT |
| HT-37 | AF-06 and type/engine daily assignments | Every valid leg enrichment equals independent local-date reconstruction. | QUERY-ROT |
| HT-38 | AP/AL candidates and DV-10/11 | Zero/one/many -> unresolved/exact/ambiguous; only one links. | DATA-03, DATA-04, MODEL-01 |
| HT-39 | AH-13 left preservation and DV-08 | Missing config opens dimension gaps; would-be inner-join loss nonzero/named. | DATA-04, MODEL-01 |
| HT-40 | AC-08/09/10-15 and DV-09 | No second type or complete mixed set fabricated. | MODEL-01, QUERY-INT |
| HT-41 | All RAI-bound physical canonical tables | Live change-tracked table bind/query under demo role. | MODEL-01 |
| HT-42 | All concepts/associations above | Eight complete RAI and SQL results independently equal frozen manifest. | QUERY-INT |
| HT-43 | Proposed inventory and generated standalone | Package/upload schema inventory and smoke results identical. | MODEL-02 |
| HT-44 | Counts/versions/engine/materialization/cold-warm metadata | Complete timing artifact with no source-scale extrapolation. | PERF-01 |
| HT-45 | Limitation/claim policy | Scan finds no universal/production/performance/cost/security superiority. | HTML-01, REDTEAM-01 |
| HT-46 | Aircraft concepts/associations and UC1-only inputs | UC1 runs with all UC2 artifacts withheld. | QUERY-UC1, GATE-01 |
| HT-47 | Curated query IDs and QueryExecutionContext | Canonical/adversarial prompts select exact catalog ID/typed parameters. | AGENT-02 |
| HT-48 | DV-09/29/30/31 and identity validation | Missing semantics, invalid inputs, mixed-engine ask fail safely. | AGENT-02 |
| HT-49 | Exact/candidate evidence and plan/actual separation | Agent/notebook/HTML preserve required labels. | AGENT-02, REDTEAM-01 |

## Omissions and limitations

- Organization/ownership/operator/manager/financing chains and organization state are omitted.
- Separate aircraft storage-location, airport-state, and airline-state concepts are omitted; raw
  state/reference lineage needed by in-scope questions is retained.
- Connected routes, passenger itineraries/connections, and minimum-connection rules are omitted.
- The source supplies only one reported engine type plus count and a multiple-types indicator. The
  exact mixed-engine set, per-position fitment, and a second type are not available and are never
  inferred.
- Master-only APU/dimension/weight fields are current-only. Historical as-of results use event
  history or return no recorded/unknown state; they do not backfill from master.
- Key-changing schedule amendments lack a stable amendment identity. Unique matches remain medium
  candidates, ambiguous matches remain low groups, and non-overlapping shifts can remain unpaired.
- Physical capacity lacks a stable physical-service group. The conservative base-row rule prevents
  false double counts while visibly allowing undercount for unresolved codeshare-only service.
- Airport/airline code resolution can be ambiguous. Current/active flags do not force a choice.
- Fulfillment is partial and heuristic candidates are not confirmed links.
- UTC schedule times without date-shift evidence remain unresolved; midnight is not inferred by
  comparing clock values.
- Rotation parity uses the validated source self-reference baseline. Optional general path
  enumeration requires a later live runtime equality test and is not release-critical.
- Results and timings apply only to deterministic synthetic representative-shape fixtures. No
  production sizing, performance superiority, cost advantage, security superiority, or universal
  Neo4j replacement claim is supported.
