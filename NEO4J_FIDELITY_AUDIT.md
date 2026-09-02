# NEO4J_FIDELITY_AUDIT - structural fidelity of the RAI ontology to the supplied Neo4j model

Audit task FIDELITY-01, written 2026-09-02 against `rai_code/aviation_model/` as built.
**Revised 2026-09-02 by TRUTH-01**, because the model and the data both moved after the audit was
written and the audit went on asserting the state it found. Every revision is marked in place and
every superseded finding keeps its original text, because an audit that quietly rewrites its own
history is worth less than one that is wrong in a dated, traceable way.

Current baseline: `build/design/ontology_inventory.json` regenerated after D-0027 (the live
`inspect.schema()` dump: **46 concepts, 1,412 properties, 22 concept relationships, 11 bare
relationships, 37 declared sources, 805 declared columns, SDK 1.20.1**), plus live SELECTs against
`PK_AVIATION_TEMPORAL.MODEL_INPUT`. The figures the original audit carried here (44 concepts,
1,292 properties, 34 sources, 749 columns) were correct when written and were the pre-D-0027
snapshot recorded in `build/task_reports/MODEL-01.json`. `tests/test_model.py::test_inventory_artifact`
now pins all of them exactly, so this header cannot silently fall behind again.

Every verdict below is grounded in the built code or the live inventory. Where a repo document
claims a mapping the code does not implement, that is recorded in section C as a documentation
defect, not accepted as evidence. That rule cuts both ways and it caught this document: finding
A1 below claimed an edge did not exist after it had been built, and the `FULFILLED` row carried a
population figure two orders of magnitude stale. Both are corrected in place with their history.

## Element count

The supplied model has **11 node labels** and **13 typed edge definitions** (12 distinct type
names; `HAS` is used once in each use case).

| Verdict | Labels | Edges | Total |
|---|---|---|---|
| IDENTICAL | 8 | 2 | 10 |
| RENAMED | 0 | 6 | 6 |
| RESHAPED | 2 | 4 | 6 |
| MERGED | 1 | 1 | 2 |
| SPLIT | 0 | 0 | 0 |
| MISSING | 0 | 0 | 0 |
| **Total** | **11** | **13** | **24** |

**Revised 2026-09-02 (TRUTH-01).** The table as first written read `RESHAPED | 2 | 3 | 5` and
`MISSING | 0 | 1 | 1`. The one MISSING edge was `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)`,
which was subsequently built (see the row in section B and the A1 status note in section 1), so it
moves to RESHAPED and MISSING goes to zero. **No supplied element is missing from the ontology
today.** That sentence was not true when this audit was written; it is true now, and the audit
that found the gap is the reason.

Plus **35 ADDED concepts** with no counterpart in the supplied model (46 built concepts minus the
11 that carry a supplied label). None of the 35 replaces a supplied element; all are
implementation controls, lineage, evidence, or a calendar. Originally 33 of 44; D-0027 added
`CodeResolution` and `CodeResolutionCandidate`.

## A. Node labels

| Neo4j element | Our concept/relationship | Verdict | Detail |
|---|---|---|---|
| `AIRCRAFT` (identity, key `aircraft_id`) | `Aircraft` (`identify_by={"id": Integer}`) | RESHAPED | Identity, cardinality and "never carries state" are exact. The **immutable/versioned attribute split is not**. Their `AIRCRAFT` holds physical dimensions, APU details and design weights as immutable. Ours holds only four of them, prefixed `master_current_only_` (`aircraft_width_m`, `apu_type`, `certified_maximum_takeoff_weight_lb`, `operating_maximum_takeoff_weight_lb`), and the historical values live on the versioned assignment instead. Deliberate: D-0005 ("version historically observed values in `aircraft_state`; treat master-only copies as `CURRENT_ONLY` and prohibit them from historical as-of reconstruction"). Also absent entirely from our `Aircraft`: `aircraft_length_m`, `aircraft_height_m`, `apu_family`, `apu_type_subseries`, `apu_manufacturer`, `maximum_landing_weight_lb`, `maximum_zero_fuel_weight_lb`, `operating_empty_weight_lb`, `maximum_payload_lb`, `maximum_cargo_volume_cu_ft`, `maximum_fuel_capacity_gal`, `is_accidents_only`, `aircraft_type_id`. Present and correct: serial, line number, all five lifecycle dates plus `*_is_unknown_future` companions, build airport (name + IATA), original delivery operator (+ category), end-of-life date, and the derived `existence_from` / `existence_to` bounds. |
| `AIRCRAFT_STATE` (state, key `aircraft_id \|\| '_' \|\| valid_from`, ~38 versioned attributes) | `AircraftStateDailyAssignment`, a subtype of `AircraftDimensionDailyAssignment`; `AircraftStateAuditAssignment` in parallel | MERGED | Three merges and one split, all in one place. (1) The state **node and its `HAS` edge are one concept** - validity, provenance and payload sit on the same association entity. (2) That concept is **shared with the other three dimensions**: one physical `AircraftDimensionDailyAssignment` with a `dimension: String` discriminator carries all 61 non-identity properties, so `aircraft_registration_number` is declared on `AircraftTypeDailyAssignment` too (it is simply absent as a fact there). The four dimension subtypes are `extends=[DailyAssignment]` with `identity_includes_type=False`, i.e. views over one entity set, not four entity sets. (3) The identity is `(dimension, aircraft, valid_from, event)` - one component **more** than theirs. Their `aircraft_id||'_'||valid_from` collapses two same-day observations into one node; ours keeps them apart permanently (D-0004). The DV-05 string spelling is retained as a non-identity property `daily_assignment_id`. (4) SPLIT into two layers: the audit stream carries no interval at all, the daily stream carries the half-open interval. Neo4j has one layer. Versioned payload present: registration number, transponder code, registration country ISO code, registration region, operating and certified MTOW, cargo, base airport / IATA / city / country, storage location + storage airport IATA. Versioned payload **absent**: `base_state`, `base_region`, `aircraft_registration_country` (name form), `transponder_miscode`, `noise_certification`, `aircraft_length_m`, `aircraft_height_m`, `has_winglets`, `winglet_modifier`, `aircraft_minor_variant`, `aircraft_modifiers`, `storage_location_type`, and the four non-MTOW weights. We carry roughly 20 of their ~38. |
| `AIRCRAFT_TYPE` (state, key `aircraft_subseries`) | `AircraftType` (`identify_by={"subseries": String}`) | IDENTICAL | Same key, same grain, definition attributes only. We carry `aircraft_family`, `aircraft_type`, `aircraft_series`, `aircraft_manufacturer`, `aircraft_design_class`. Their watched set also includes `AIRCRAFT_CODE_IATA`, `AIRCRAFT_CODE_ICAO`, `AIRCRAFT_MASTER_SERIES` and `AIRCRAFT_VALUE_SUB_SERIES`; ours binds those on the assignment, not on the definition. `definition_status` / `definition_variant_count` / `source_configuration_count` are ADDED controls. |
| `ENGINE_TYPE` (state, key `engine_subseries`) | `EngineType` (`identify_by={"subseries": String}`) | IDENTICAL | Same key, same grain. `engine_count` and `has_multiple_engine_types` deliberately sit on the assignment, not the definition (asserting one engine count per subseries identity would be wrong in the domain and would FDError on a mixed-engine configuration). Absent from the definition: `engine_master_series`, `engine_nox_emission_gm`, `max_thrust`. |
| `AIRCRAFT_STATUS` (state, key `aircraft_status`) | `AircraftStatus` (`identify_by={"code": String}`) | IDENTICAL | Raw source string, no trim, no case fold, **zero attributes** - matches theirs exactly. Minted from the observed audit values rather than a hard-coded enum. Live vocabulary: `In Service`, `Storage`, `Maintenance`. |
| `ROUTE` (identity, key `route` e.g. `ATL->LAX`) | `Route` (`identify_by={"route_id": String}`) | IDENTICAL | Key format verified live: `ORD->MIA`, `BOS->MIA`, `SEA->DEN`. Carrier-agnostic and directional. |
| `ROUTE_STATE` (state, key `schedule_key \|\| '\|' \|\| valid_from`) | `RouteState` (`identify_by={"route_state_key": String}`) | RESHAPED | Key format verified live and byte-identical (`SYN-SK-MKT_COPY_702\|2026-08-03`). `Route` correctly does not appear in the identity, so multi-open is the default and no constraint has to be relaxed. But the **four `HAS`-edge temporal properties are now node properties**: `valid_from`/`valid_to` are `RouteState.knowledge_valid_from`/`knowledge_valid_to` and `effective_date`/`discontinue_date` are `RouteState.operating_effective_date`/`operating_discontinue_date`. Functionally equivalent because a state has exactly one route, but a reader comparing schemas will not find the edge properties where theirs are. Also: a new `Schedule` identity concept is extracted so `RouteState.schedule` is explicit, which theirs leaves implicit inside the key string. |
| `PASSENGER_FLIGHT` (identity, key `flight_service_key`) | `PassengerFlight` (`identify_by={"passenger_flight_key": String}`) | IDENTICAL | Key construction verified live and identical: `carrier\|flight_number\|dep\|arr\|operating_date`. Historical-over-forward union precedence retained and auditable via `PassengerSourceLineage`. One improvement over theirs: our node **does expose `publish_date`**, which their document explicitly names as the reason the temporal join has to be rebuilt from raw tables. |
| `AIRCRAFT_FLIGHT` (identity, key `flight_id`) | `AircraftFlight` (`identify_by={"flight_id": Integer}`) | IDENTICAL | Same key, same grain, actuals only, separate from the plan side. |
| `AIRPORT` (identity only, key `airport_code_internal`) | `Airport` (`identify_by={"airport_id": String}`) | IDENTICAL | Identity only, as scoped. Source effective periods retained as lineage properties (`selected_effective_start_date`, `selected_effective_end_date`, `reference_period_count`, `projection_rule`) rather than modelled as state - same choice theirs makes. |
| `AIRLINE` (identity only, key `airline_code_internal`) | `Airline` (`identify_by={"airline_id": String}`) | IDENTICAL | Same as `Airport`. Controlled-duplicate flag retained as resolution evidence. |

## B. Edge types

| Neo4j element | Our concept/relationship | Verdict | Detail |
|---|---|---|---|
| `(AIRCRAFT)-[:HAS]->(AIRCRAFT_STATE)` `{valid_from, valid_to}` | `Aircraft.daily_assignments` (multi-valued `Relationship`), inverse of `DailyAssignment.aircraft`; plus `Aircraft.audit_assignments` | MERGED | One physical association concept serves all four Neo4j edges, but four dimension-scoped readings recover them. *Revised 2026-09-02 (TRUTH-01): this cell read "**There is no dimension-scoped edge from `Aircraft`.** ... The design brief section 2.1 specified `Aircraft.state_assignments`; it was not built (grep returns nothing)." That was true when audited and is false now.* `Aircraft.state_assignments`, `.type_assignments`, `.engine_assignments` and `.status_assignments` are built at `rai_code/aviation_model/computed_aircraft.py:109-133`, each a `Relationship` defined by a `dimension ==` filter over `DailyAssignment`, so the `HAS` edge is directly enterable and does not have to be recovered by subtype predicate. The unscoped `Aircraft.daily_assignments`, which ranges over all four dimensions, remains available for the general case. Cardinality is right in both directions: `assignment -> Aircraft` is a functional `Property`, `Aircraft -> assignments` is an unconstrained `Relationship`. Edge properties `valid_from`/`valid_to` are `DailyAssignment.valid_from` (an identity component) and `DailyAssignment.valid_to`. The parallel audit edge is ADDED - theirs has no equivalent. |
| `(AIRCRAFT)-[:CONFORMED]->(AIRCRAFT_TYPE)` `{valid_from, valid_to}` | `DailyAssignment.aircraft_type` (`Property`, reading "conformed to"), inverse `AircraftType.daily_assignments`; subtype `AircraftTypeDailyAssignment` | RESHAPED | The single Neo4j edge became a **two-hop path through an association concept**: `Aircraft -> AircraftTypeDailyAssignment -> AircraftType`. That is the right call for a temporal edge with payload, and the reading verb "conformed to" is preserved. *Revised 2026-09-02 (TRUTH-01): this cell read "What is lost is the direct `Aircraft -> AircraftType` hop: no `Aircraft.conformed_types` exists, so a customer's one-hop Cypher becomes two hops plus a subtype predicate." The direct hop was subsequently built.* `Aircraft.conformed_to` at `computed_aircraft.py:148-170` reads `Aircraft conformed to AircraftType:aircraft_type from Date:valid_from until Date:valid_to`, carrying both supplied edge properties, so a one-hop Cypher pattern stays one hop; the two-hop path through the assignment remains for the rest of its payload. `Property` (at most one target) means an unresolved configuration is the absence of a fact, matching their zero-target gap. |
| `(AIRCRAFT)-[:EQUIPPED]->(ENGINE_TYPE)` `{valid_from, valid_to}` | `DailyAssignment.engine_type` (`Property`, "equipped with"), inverse `EngineType.daily_assignments`; subtype `EngineTypeDailyAssignment` | RESHAPED | Same shape as `CONFORMED`. Assignment-level `engine_count` and `mixed_engine_set_complete` are additional payload theirs does not carry on the edge. |
| `(AIRCRAFT)-[:ASSIGNED]->(AIRCRAFT_STATUS)` `{valid_from, valid_to, start_event, event_source}` | `DailyAssignment.status` (`Property`, "assigned status"); subtype `AircraftStatusDailyAssignment` | RESHAPED | Same two-hop reshape. **Provenance is preserved**: `start_event` and `event_source` are properties on the assignment, which is exactly the "edge carries provenance" case with no modelling loss. *Revised 2026-09-02 (TRUTH-01): this cell read "One asymmetry: **there is no inverse from `AircraftStatus`** (`AircraftStatus` has zero relationships in the inventory), so 'which aircraft were ever in Storage' cannot start from the status node the way it can in Cypher." Both halves were fixed.* `Aircraft.assigned_status` at `computed_aircraft.py:156-190` gives the direct one-hop reading with both edge dates, and `AircraftStatus.daily_assignments` at `computed_aircraft.py:192-196` gives the inverse, so "which aircraft were ever in Storage" is now enterable from the status node exactly as in Cypher. `AircraftStatus` has one relationship in the live inventory, not zero. |
| `(ROUTE)-[:HAS]->(ROUTE_STATE)` `{valid_from, valid_to, effective_date, discontinue_date}` | `RouteState.route` (`Property`, "covers") with `.alt()` inverse `Route.states` ("Route has state") | RENAMED | The Neo4j edge recovered exactly, and this is the model's strongest point. Because the FD points state -> route and `Route.states` is an `.alt()` reading over the same fields, it carries no inverse FD, so many concurrently-open states per route are the default rather than a relaxation. Measured live: 1,339 concurrent open states on `SFO->LAX` at knowledge date 2026-08-31, returned without error. The four edge properties moved to the node (see the `ROUTE_STATE` row). No `unique()` over the `Route` slot and no `Route.current_state`, deliberately. |
| `(ROUTE)-[:STARTS]->(AIRPORT)` | `Route.origin_airport` (`Property`, "Route starts at Airport:origin_airport") | RENAMED | Verb preserved in the reading. Two same-type slots correctly split into two role-labelled Properties rather than one two-slot Relationship. Bound only where `origin_airport_resolution_status == EXACT`; the raw code stays on `Route.origin_station_code_iata` so a failed resolution still shows. No inverse reading from `Airport`. |
| `(ROUTE)-[:ENDS]->(AIRPORT)` | `Route.destination_airport` (`Property`, "Route ends at Airport:destination_airport") | RENAMED | As above. |
| `(AIRLINE)-[:OPERATES]->(ROUTE_STATE)` | `RouteState.operating_airline` (`Property`) with `.alt()` inverse `Airline.operates` | IDENTICAL | Edge type name and direction preserved verbatim in the inverse reading `Airline:operating_airline operates RouteState:state`. Never merged with the marketing role. Exact-resolution-only, raw code retained. |
| `(AIRLINE)-[:COMMERCIALIZES]->(ROUTE_STATE)` | `RouteState.marketing_airline` (`Property`) with `.alt()` inverse `Airline.commercializes` | IDENTICAL | As above. `RouteState.codeshare_airline` is an ADDED third role with no Neo4j counterpart. |
| `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)` | `RouteStateSchedules` / `RouteState.schedules` (multi-valued `Relationship`) with the `.alt()` inverse `PassengerFlight.scheduled_by` | RESHAPED (was MISSING) | **Revised 2026-09-02 (TRUTH-01).** *Original verdict, preserved:* "**MISSING. Not deliberate.** No relationship, property or derived rule connects `RouteState` to `PassengerFlight` anywhere in `rai_code/aviation_model/` or in the generated `rai_code/manual/aviation_temporal.py` (grep for `SCHEDULES` / `schedules(` returns zero hits in both)." That was true on the tree as audited and it is false on the tree today. The edge was built in response to this finding and exists at `rai_code/aviation_model/computed_schedule.py:155-169`, with the generated standalone artifact carrying the same definition in `rai_code/manual/aviation_temporal.py`; the same grep now returns hits in both. RESHAPED rather than IDENTICAL because it is **derived, not loaded**: `model.define(RouteStateSchedules(RouteState, PassengerFlight))` fires on a four-clause conjunction - same `Schedule` identity, passenger publish date inside the state's half-open knowledge interval, passenger operating date inside the state's inclusive operating interval, and the operating date's ISO weekday one the state actually operates. That makes the publish-date pin, which the original finding correctly identified as the point of their edge, structural rather than retyped per query. Live population is **7,950 pairs** over 7,950 distinct passenger flights and 2,000 distinct route states (SQL replica of the rule, run 2026-09-02); see the A1 status note in section 1 for the population history. |
| `(AIRCRAFT_FLIGHT)-[:FULFILLED]->(PASSENGER_FLIGHT)` | `AircraftFlight.fulfils` (`Property`) with `.alt()` inverse `PassengerFlight.fulfilled_by` | RENAMED | Direction preserved. Structurally **better** than the property-graph edge: the FD `leg -> plan` is enforced while the inverse carries no FD, so the stopover case (one plan, two legs) loads without an out-of-band constraint. Also correctly optional in both directions, which their document asks for. Two deviations: (a) `fulfils` is derived from `ExactFulfillment` only, so heuristic and ambiguous candidates never satisfy the edge - stricter than their "partial match by design"; (b) it is populated on **704 of 3,900** aircraft flights live (18 percent), over 653 distinct canonical passenger flights, so the one-plan-to-many-legs case is genuinely exercised. *Revised 2026-09-02 (TRUTH-01): this cell read "populated on **4 of 3,900** aircraft flights live, so the edge exists but is barely exercised", which was true of the pre-D-0023 fixture and was already contradicted by the A7 status table further down this same file.* |
| `(AIRCRAFT_FLIGHT)-[:STARTED]->(AIRPORT)` | `AircraftFlight.actual_origin` (`Property`, "leg started at Airport:actual_origin") | RENAMED | Verb preserved. Role-labelled, exact-resolution-only. No inverse from `Airport`. |
| `(AIRCRAFT_FLIGHT)-[:ENDED]->(AIRPORT)` | `AircraftFlight.actual_destination` (`Property`, "leg ended at Airport:actual_destination") | RENAMED | Verb preserved. `AircraftFlight.diverted_airport` is an ADDED third endpoint role; the diverted airport never repairs `actual_destination`, which is the continuity endpoint. |

## B1. ADDED - in ours, not in theirs

None of these replaces a supplied element. 35 concepts, grouped by why they exist. (33 when this
audit was written; D-0027 added the two row-scoped code-resolution concepts, see that row below.)

| Added concept(s) | Why it exists |
|---|---|
| `AircraftEvent`, `AircraftEventQuarantine` | The ordered history row promoted to an identity so same-day ordering is structural (`event` is an identity component of both assignment concepts) rather than a query convention. Quarantine retains rows that cannot form an identity. |
| `AircraftConfiguration` | Join target for the configuration reference, left-preserving: an event whose configuration does not resolve keeps its identity and carries no configuration fact. |
| `AircraftDimensionAuditAssignment` + `AircraftState/Type/Engine/Status AuditAssignment` (5) | The second temporal layer (D-0004). Carries **no interval**, only order. A same-day `Storage -> In Service` spell exists only here. |
| `AircraftState/Type/Engine/Status DailyAssignment` (4) | Subtype views that recover the four Neo4j dimensions from the one shared assignment concept. |
| `Schedule` | Extracted from the `ROUTE_STATE` key so the version partition is a visible concept. |
| `ScheduleObservation`, `RouteStateSnapshotLineage`, `SnapshotDate` | Per-snapshot observation grain, coalescing lineage, and explicit snapshot eligibility. Their model coalesces in the SCD builder and keeps no eligibility control. |
| `ScheduleComparison`, `ScheduleExactChange`, `ScheduleAmendmentSide/Candidate/Group/GroupMember` (6) | Golden question 1's diff, with exact changes structurally separated from conservative key-shift amendment evidence (D-0006). Their document says the key-shift problem is "not solved on our side". |
| `CodeResolutionCode`, `CodeResolutionCodeCandidate`, `CodeResolution`, `CodeResolutionCandidate` | Zero/one/many code resolution kept queryable so only a cardinality-one EXACT match creates a concept link. D-0019 moved link semantics from row grain to code grain and provisionally dropped the row grain on a cost suspicion; D-0027 measured that cost at 0.18s, refuted the premise, and reinstated it. *Revised 2026-09-02 (TRUTH-01): this row listed only the two code-grain concepts and said "D-0019 moved this from row grain to code grain", which reads as a replacement. Both grains are bound today.* The code grain answers "does this raw code resolve to exactly one identity"; the row grain answers "which source object, row and field role mentioned it". |
| `PassengerSourceLineage`, `PassengerSourceQuarantine`, `InvalidPassengerObservation`, `PassengerPlannedLeg` | Union precedence auditability, retained invalid observations, and the ordered planned station sequence that makes the stopover case real. |
| `ExactFulfillment`, `FulfillmentCandidate`, `FulfillmentGroupMember` | Confirmed fulfilment separated from candidates and ambiguous groups. |
| `RotationLinkValidation` | One row per candidate `NEXT_FLIGHT_ID` edge plus a terminal row per leg, carrying the acceptance verdict. Their model has the raw pointer only. |
| `MonthEnd` | Calendar dimension so golden question 3 is one join, not 120 queries. |

Added relationships and properties worth naming: `AircraftFlight.next_flight_raw`,
`AircraftFlight.accepted_next_flight`, `rotation_leg_distance` (transitive closure),
`RotationSegmentHead`, `AircraftFlight.as_of_aircraft_type` / `as_of_engine_type` /
`type_discrepancy`, `InServiceOnMonthEnd`, `RouteStateOperatesOnWeekday`,
`RouteStateIsPhysicalRepresentative`, `RouteState.origin_airport` / `destination_airport`
(a `ROUTE_STATE`-level endpoint their model reaches only through `ROUTE`), and five integrity
guards RAI cannot declare so it derives them (`SentinelLeak`, `EndEventDisagreement`,
`PhysicalServiceDisagreement`, `CabinDerivationDisagreement`, and the two snapshot-gap flags).

## Section 1 - Deviations that change what a query can express

Ranked worst first.

**A1. `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)` does not exist.** This is the one hard
gap. The customer's edge is a two-predicate temporal join - match the schedule identity, then pin
to the one route-state version whose knowledge window contains the flight's publish date. We
built neither half as a relationship. `PassengerFlight.schedule` reaches the schedule
*identity*, which is a strictly weaker link: from a passenger flight you can find every version
of its schedule but not the version that was live when we learned about the flight. Concretely,
these become unaskable as a traversal: "for this flight, what frequency and capacity had we
published at the time", "which schedule version generated these flights", and any walk from
airport -> route -> route state -> airlines -> the flights those schedules generated, which their
use-case-2 document names as the shape that motivates the graph. The pin is *computable* at query
time - we expose `PassengerFlight.publish_date` (which their node does not) and
`temporal.known_on` already implements the half-open predicate - but it is not declared, so every
consumer would retype it, which is precisely the failure the `temporal.py` layer exists to
prevent. Cost to fix: one `model.Relationship` plus one `define(...).where(...)`. Data caveat: it
would be nearly empty today, because `PASSENGER_FLIGHT_CANONICAL.schedule_key` is non-null on
**1 of 19,996 rows**.

**A1 status: closed, by MODEL-01 for the structure and by D-0023 for the data.** Both halves of
the finding were acted on and the finding above is left verbatim as the record of what was found.

*Structure.* `RouteStateSchedules` exists at `rai_code/aviation_model/computed_schedule.py:155-169`
and in the generated `rai_code/manual/aviation_temporal.py`, with `RouteState.schedules` and the
`.alt()` inverse `PassengerFlight.scheduled_by`. It is exactly the fix costed above - one
`model.Relationship` plus one `define(...).where(...)` - and it declares more than the two
predicates the finding asked for: schedule identity, the half-open knowledge-window pin on the
passenger publish date, the inclusive operating-window pin, and the weekday applicability check.
The traversals the finding named as unaskable ("for this flight, what frequency and capacity had
we published at the time", "which schedule version generated these flights") are askable now.

*Data.* The "nearly empty" caveat is also out of date, and by a wide margin.
`PASSENGER_FLIGHT_CANONICAL.schedule_key` is non-null on **7,951 of 19,446** canonical passenger
flights, not 1 of 19,996, and a SQL replica of the full four-clause rule returns **7,950 pairs**
(7,950 distinct passenger flights, 2,000 distinct route states), measured 2026-09-02:

```sql
SELECT COUNT(*) FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.ROUTE_STATE rs
JOIN PK_AVIATION_TEMPORAL.MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL pf
  ON rs.SCHEDULE_KEY = pf.SCHEDULE_KEY
WHERE rs.KNOWLEDGE_VALID_FROM <= pf.PUBLISH_DATE AND pf.PUBLISH_DATE < rs.KNOWLEDGE_VALID_TO
  AND rs.OPERATING_EFFECTIVE_DATE <= pf.OPERATING_DATE
  AND pf.OPERATING_DATE <= rs.OPERATING_DISCONTINUE_DATE
  AND <IS_OPERATING_<DAY> matching DAYOFWEEKISO(pf.OPERATING_DATE)>;
-- 7950
```

*What remains true.* No named `EXPECTED_ANSWERS.yaml` scenario reads a value through this
relationship, so it is populated but ungraded: no frozen fixture would catch a regression in it.
Say "implemented and populated, not covered by a golden-question fixture". Do not say "zero live
pairs", and do not say "does not exist"; this document said both, and both are now false.

**A2. The four independent Neo4j edges are one physical concept discriminated by a string.**
`AircraftDimensionDailyAssignment` carries all 61 non-identity properties for all four
dimensions, and the subtypes are views (`identity_includes_type=False`), not separate entity
sets. Three consequences a customer would hit. (i) Any query over an assignment that forgets to
scope the dimension silently answers a different question - this already caused a live wrong
answer during the build (aircraft 1001 at 2022-05-15 reported both `OK` and `UNKNOWN_STATE`
because an unscoped `assignment` ranged over all four dimensions), and `temporal.dv33_branches`
now takes a mandatory `scope` parameter as a guard rail. In Neo4j the edge type *is* the scope and
the mistake is not available. (ii) `AircraftTypeDailyAssignment` declares
`aircraft_registration_number` and 40 other state-dimension properties that are always absent
there, so the ontology a customer inspects does not tell them which properties belong to which
dimension. (iii) `Aircraft` has exactly two outbound relationships, not eight, so the "four
independent clocks" story is a subtype predicate rather than four visibly distinct edges.

**A2 status: (i) and (ii) stand, (iii) is closed.** *Revised 2026-09-02 (TRUTH-01).* The single
shared physical concept and its always-absent cross-dimension properties are unchanged, so the
scoping footgun in (i) and the inspection problem in (ii) are still real and `dv33_branches` still
requires its `scope`. But (iii) is no longer true: `Aircraft` has **nine** outbound relationships
in the live inventory, not two. Four of them are dimension-scoped
(`state_assignments`, `type_assignments`, `engine_assignments`, `status_assignments`) and three
are the direct one-hop readings named in A3 below, all at `computed_aircraft.py:109-190`. The
"four independent clocks" story is four visibly distinct edges again.

**A3. No direct `Aircraft -> AircraftType` / `EngineType` / `AircraftStatus` hop, and no inverse
from `AircraftStatus`.** Every one-hop Cypher pattern on `CONFORMED`, `EQUIPPED` and `ASSIGNED`
becomes two hops plus a dimension predicate. `AircraftType` and `EngineType` at least have
`.daily_assignments` inverses; `AircraftStatus` and `AircraftConfiguration` have none, so
"aircraft that were ever in Storage" cannot be entered from the status node. In RAI the join is
still writable from the assignment side, so this is ergonomic loss rather than lost
expressiveness - but it is the deviation a Cypher-literate reviewer will notice first.

**A3 status: closed for the three named hops and for `AircraftStatus`; open for
`AircraftConfiguration`.** *Revised 2026-09-02 (TRUTH-01), verified against the live inventory and
`rai_code/aviation_model/computed_aircraft.py`.* `Aircraft.conformed_to`, `Aircraft.equipped_with`
and `Aircraft.assigned_status` (lines 148-190) each read
`Aircraft <verb> <Target> from Date:valid_from until Date:valid_to`, so all three one-hop Cypher
patterns are one hop again and carry both supplied edge properties.
`AircraftStatus.daily_assignments` (lines 192-196) supplies the missing inverse, so "aircraft that
were ever in Storage" is enterable from the status node. `AircraftConfiguration` still has no
inverse reading; that half of the finding stands.

**A4. `AIRCRAFT_STATE` versioned payload is roughly 20 of their ~38 attributes, and four
immutable attributes were moved from `AIRCRAFT` to the versioned stream.** The absent versioned
columns are listed in section A. Point-in-time reconstruction (their golden question 1) therefore
cannot return `base_state`, `base_region`, `noise_certification`, `has_winglets`,
`aircraft_length_m`/`height_m`, `transponder_miscode`, `storage_location_type` or the four
non-MTOW weights at all.

**A4 status: partly closed by D-0024.** Nine of the named attributes were added as AH-34 through
AH-42, taking the contracted column count from 195 to 204 and attribute coverage from roughly 20
of 38 to roughly 29 of 38. `base_state`, `base_region`, `storage_location_type`,
`noise_certification`, `has_winglets`, `aircraft_registration_country`, `transponder_miscode`,
`maximum_landing_weight_lb` and `operating_empty_weight_lb` are now watched `aircraft_state`
values and are returned by point-in-time reconstruction. The remaining nine are named with a
reason in `SOURCE_CONTRACT.md` section 12: two physical dimensions, two non-MTOW weights, three
free-text modifier strings and two master-side descriptors, each immutable or non-queryable in
the bounded workload. Separately, D-0005 versioned width, APU type and both MTOWs, so
`Aircraft.master_current_only_*` is prohibited from historical reconstruction: asking their
question "what were this aircraft's dimensions" as at a past date returns the versioned value
where one was observed and nothing otherwise, where their model returns the immutable master
value always. Different answers, deliberately, and defensible - but different.

**A5. `FULFILLED` is exact-only, where theirs is a partial match by design.** Our edge is derived
from `ExactFulfillment` alone; candidate and ambiguous evidence never satisfies it. Their document
describes `FULFILLED` as covering all tracked movements with a substantial unmatched share. Ours
is the stricter, more defensible reading, but "how many actual legs fulfilled a planned service"
returns a smaller number than theirs on the same data, and the difference is not visible from the
edge.

**A6. The state identity carries an extra component.** Theirs is `aircraft_id || '_' ||
valid_from`; ours is `(dimension, aircraft, valid_from, event)`. Where two observations share a
date, theirs mints one node and ours mints two. Ours is correct (D-0004, and their own document
warns that "getting that ordering wrong silently corrupts the version history"), but a
row-for-row count comparison against their graph will not match, and the difference has to be
explained rather than discovered on stage.

**A7. Data caveat, not a structural one, but it changes what the demo demonstrates.** The
fixture barely exercises two of the four dimensions: `aircraft_state` averages **1.005** versions
per aircraft with only **2 of 999** aircraft having more than one, and `aircraft_status` averages
**1.004** with **2 of 999** having more than one (live: `In Service` 1,001 observations,
`Storage` 3, `Maintenance` 2). The `aircraft_type` and `engine_type` dimensions average 48
versions per aircraft, but the bulk is synthetic daily churn through `SYN-TYPE-FILL-NNN` values
rather than realistic conversions. Their golden question 2 (In Service -> Storage -> In Service
spells) has essentially no population behind it, and `FULFILLMENT_EXACT` holds 4 rows. The
ontology can express these questions; the loaded data cannot show them convincingly.

**A7 status: closed by D-0023, measured against the live v2 load.** Every figure below is a
measurement, not a prediction.

| Measure | v1 live | v2 live |
|---|---:|---:|
| `aircraft_state` versions per aircraft | 1.005 | **8.770** |
| aircraft with more than one state version | 2 of 999 | **995 of 999** |
| `aircraft_status` versions per aircraft | 1.004 | **2.337** |
| aircraft with more than one status version | 2 of 999 | **470 of 999** |
| `aircraft_type` versions per aircraft | 48 (synthetic daily churn) | **1.204**, 202 aircraft convert |
| `engine_type` versions per aircraft | 48 (synthetic daily churn) | **1.309**, 307 aircraft re-engine |
| status observation vocabulary | 1,001 / 3 / 2 | **28,287 / 1,661 / 285** |
| closed In Service -> Storage -> In Service spells | 2 | **439** over 258 aircraft |
| spell-duration buckets populated | 2 | **7**, minimum 0 days, median 157, maximum 1,091 |
| Q03 over its window | 132 rows, 2 aircraft, 2 types | **985 rows, 120 month ends, 10 types** (2025-2034) |
| Q05 rows and populated classes | 35 rows, 8 classes, 6 of them at 1 to 3 rows | **392 rows, 8 classes, minimum 6** |
| `AIRCRAFT_HISTORY` rows | 48,000 | **30,233** - fewer rows, more structure |
| exact fulfilments | 4 | **704** over 653 canonical passenger flights |
| canonical passenger flights carrying a schedule key | 1 of 19,996 | **7,951 of 19,446** |
| versioned A4 attributes carried | about 20 of 38 | about **29 of 38** |

The type and engine version counts fall, and that is the improvement: 48 daily
`SYN-TYPE-FILL-NNN` values per aircraft was noise that made golden question 4 unreadable.

**Density rows re-measured 2026-09-02 (TRUTH-01), and the definition tightened.** The first six
rows previously read "per filler aircraft" at 8.83 / 993 of 993 / 2.36 / 468 / 1.20, 200 / 1.31,
305, and the vocabulary row at 28,272 / 1,654 / 283. Those came from `ENRICH-02`'s generator-side
count over the 993 filler aircraft. The figures above are counted instead from the shipped
`MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT`, grouped by `(dimension, aircraft_id)` over all
**999** eligible aircraft, and the vocabulary row from `SOURCE.AIRCRAFT_HISTORY.START_AIRCRAFT_STATUS`
(30,233 rows, all non-null). The two sets differ by under half a percent and by a handful of
aircraft; the difference is the denominator (999 rather than 993) and the grain (the daily
assignment coalesces same-day observations that the generator counts separately), not a
correction. Quote the figures above, because they are the ones a customer can reproduce from the
tables the demo actually reads. Restricted to the 993 filler aircraft the same query returns
8.795 / 991, 2.339 / 467, 1.201 / 200 and 1.305 / 303, which is the closest reproduction of
`ENRICH-02`'s column from `MODEL_INPUT` and is still not identical to it.

## Section 2 - Deviations that are cosmetic

- **Edge-type names became relationship readings.** `STARTS`/`ENDS` -> "starts at"/"ends at",
  `STARTED`/`ENDED` -> "started at"/"ended at", `CONFORMED` -> "conformed to", `EQUIPPED` ->
  "equipped with", `ASSIGNED` -> "assigned status", `FULFILLED` -> "fulfilled", `HAS` -> "has
  state" / "has daily assignment". `OPERATES` and `COMMERCIALIZES` survive verbatim. Every verb
  is recognisable; no meaning moved.
- **Concept names are singular CamelCase** where theirs are SCREAMING_SNAKE: `AircraftFlight`
  for `AIRCRAFT_FLIGHT`, and so on. One-to-one and mechanical.
- **`ROUTE_STATE` temporal properties renamed and relocated.** `valid_from`/`valid_to` ->
  `knowledge_valid_from`/`knowledge_valid_to`, `effective_date`/`discontinue_date` ->
  `operating_effective_date`/`operating_discontinue_date`, moved from the `HAS` edge to the node.
  Because a state has exactly one route the relocation is semantically free, and the rename is an
  improvement: their document warns that "a query that uses only one of them will look plausible
  and be wrong", and the prefixes make the mistake harder to make. Both key formats and both
  interval conventions (knowledge half-open, operating inclusive at both ends) are preserved
  exactly, and `9999-01-01` remains the open sentinel.
- **Directed `Property` plus `.alt()` inverse instead of a bidirectional edge.** For
  `Route.states`, `Airline.operates`, `Airline.commercializes`, `Aircraft.actual_flights`,
  `PassengerFlight.fulfilled_by`, `AircraftType.daily_assignments` and
  `EngineType.daily_assignments` the inverse reading exists and costs nothing. Where the inverse
  reading is missing (`Airport`, `AircraftConfiguration`) the join is still writable from the other
  side; see A3. *Revised 2026-09-02 (TRUTH-01): this list also named `AircraftStatus` and
  `Schedule -> PassengerFlight`. Both now have an inverse -
  `AircraftStatus.daily_assignments` and `PassengerFlight.scheduled_by` respectively.*
- **Inverses of identity components are `Relationship`s, not `.alt()` readings** - a mechanical
  consequence of `identify_by` naming the owner slot after the lowercased concept. No cardinality
  difference.
- **Module placement.** UC1 in `core_aircraft.py`, UC2 split across `core_schedule.py` /
  `core_flight.py`, derived layers in `computed_*.py`, shared predicates in `temporal.py`. No
  structural meaning.
- **`Schedule` extracted as a concept** rather than left implicit inside the `ROUTE_STATE` key
  string. Adds a name, changes nothing.

## Section 3 - Where `NEO4J_RAI_MAPPING.md` is wrong about our own code

The mapping document was written before the ontology existed, and our parity claims cite it. Six
defects, three of them load-bearing.

**Section 3 status, 2026-09-02 (TRUTH-01).** Defects 1, 2 and 4 were closed by building the code
the mapping described, so the mapping became right and this section became wrong. Their original
text is kept verbatim below, each with a status line, because the sequence matters: the mapping
asserted something that was not built, the audit caught it, and the response was to build it
rather than to soften the claim. Defect 3 is still open on substance and its concept count is
refreshed. Defects 5 and 6 are unchanged.

1. **`NEO4J_RAI_MAPPING.md:108` claims a built `RouteState`-to-`PassengerFlight` scheduling
   `Relationship`.** It does not exist. `NEO4J_PARITY_MATRIX.md:57` inherits the claim
   ("clock-qualified scheduling relationship", "Bounded plan-link parity"), and
   `build/design/ONTOLOGY_DESIGN.md:451` and `:581` and `:742` all specify it. Line 113's summary
   sentence, "No supplied edge is omitted", is therefore false. **This is the one place where a
   published parity claim is not backed by code.**

   **Status: closed.** `RouteStateSchedules` is built at
   `rai_code/aviation_model/computed_schedule.py:155-169` and mirrored in the generated
   `rai_code/manual/aviation_temporal.py`. "No supplied edge is omitted" is true today. The
   mapping row and the parity-matrix row are no longer the defect; their *population* figure was
   ("zero live pairs" against a measured 7,950), and that is corrected in both files.
2. **Lines 99-102 imply four separate dimension-scoped edges from `Aircraft`.** They read
   "Aircraft to `AircraftStateDailyAssignment`", "`AircraftTypeDailyAssignment` links Aircraft to
   optional exact AircraftType", and so on. Built code has exactly two relationships from
   `Aircraft` - `daily_assignments` and `audit_assignments` - both unscoped across all four
   dimensions. The per-dimension edges named in `ONTOLOGY_DESIGN.md` section 2.1/2.2
   (`Aircraft.state_assignments`, `Aircraft.type_assignments`) were never written. The mapping is
   directionally right about cardinality and wrong about how many edges exist, which matters
   because it is the sentence a customer would read as "we have your four edges".

   **Status: closed.** The four dimension-scoped relationships were written at
   `computed_aircraft.py:109-133` and the three direct one-hop readings at lines 148-190.
   `Aircraft` now carries nine outbound relationships in the live inventory. The mapping's "we
   have your four edges" reading is backed by code.
3. **Line 68 lists `QueryExecutionContext` as an RAI concept.** It is not in the model (46
   concepts as of D-0027, none by that name; 44 when this was first checked). `ONTOLOGY_DESIGN.md` section 9 item 4 explains why it moved to
   the query API boundary; the mapping table was never updated to match. Line 156 repeats it
   ("QueryExecutionContext plus RouteState two-clock predicates").
4. **Line 57-58 describe `CodeResolution` keyed by a "deterministic resolution-context hash" over
   "source object / DV-46 row token / field role / raw code / method", with
   `CodeResolutionCandidate` keyed `(resolution_id, candidate_id)`.** Built code has
   `CodeResolutionCode` keyed `(domain, method, raw_code)` and
   `CodeResolutionCodeCandidate` keyed `(resolution, candidate_id)` - the D-0019 substitution to
   code grain. The row-scoped variant the mapping describes was deliberately dropped, but the
   mapping still describes it.

   **Status: closed, by reversal rather than by alignment.** D-0019's exclusion was provisional on
   a cost suspicion; D-0027 measured the cost at 0.18s against an 18s first query, refuted the
   premise, and reinstated the row grain. `CodeResolution` (`resolution_id`) and
   `CodeResolutionCandidate` (`resolution`, `candidate_id`) are bound concepts today, alongside
   the code-grain pair, and `CODE_RESOLUTION`, `CODE_RESOLUTION_CANDIDATE` and
   `CODE_RESOLUTION_INPUT` are three of the 37 declared sources. Neither grain supersedes the
   other. The mapping's key description is still not literally the built one - the built identity
   is `resolution_id`, not a described hash over five fields - so read the mapping row for intent
   and `core_reference.py:140-180` for the shipped keys.
5. **Lines 62 and 66 name `ScheduleAmendmentEvidence` and `FulfillmentCandidateEvidence` as
   concepts.** Built as four and three concepts respectively:
   `ScheduleAmendmentSide` / `Candidate` / `Group` / `GroupMember`, and `FulfillmentCandidate` /
   `FulfillmentGroupMember`. Naming only, no structural error.
6. **Lines 106-107 say the `OPERATES`/`COMMERCIALIZES` inverses are "inverse Relationship"s.**
   They are `.alt()` readings over the forward `Property`, which is a different construct with
   the same cardinality. Harmless, but the mapping should say `.alt()` because the *reason*
   multi-open works at all is that `.alt()` adds no inverse FD, and that is the demo's headline
   argument.

Also stale but lower stakes: line 78 says `AIRCRAFT` is "Direct identity parity" without noting
that D-0005 moved four immutable attributes into the versioned stream, and line 79's "Daily
association supplies point-in-time parity" does not say that roughly 18 of the ~38 versioned
attributes are not carried.
