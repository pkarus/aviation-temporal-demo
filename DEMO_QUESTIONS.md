# SPEC-03 golden questions and independent oracles

## Authority and freeze rule

This catalog freezes the eight release questions before synthetic-data generation, Snowflake SQL,
ontology code, or PyRel query code exists. `EXPECTED_ANSWERS.yaml` is the independent, hand-specified
answer authority. Later fixture, SQL, and RAI implementations must conform to it; implementation
agreement is not permission to edit it. A semantic change requires the append-only review and
rollback protocol in `DECISION_LOG.md`.

The catalog is source-grounded in `SOURCE_CONTRACT.md`, `ATTRIBUTE_AUTHORITY.md`, and
`NEO4J_RAI_MAPPING.md`. There is not yet a live ontology to inspect, so discovery feasibility is
reported honestly as `MODEL_GAP`: all required source fields and target concepts are
contracted, but `DATA-04` and `MODEL-01` must materialize/map them before execution can become
`READY`. No question is blocked by a known data gap for its bounded fixture answer.

All eight questions target the binding D-0009 synthetic U.S.-domestic core. D-0010 and D-0011
supersede only the v1.0 schedule-universe construction: manifest v1.1.1 uses one unfiltered source
universe, repairs every Q05 event forced by Q06/Q07 fixtures, and moves the missing/incomplete
snapshot control outside the August adjacency window. No Q06 canonical row or Q07 result set was
changed. D-0012 narrowly supersedes v1.1.0 by replacing one impossible human-readable null-ID
lineage alias with its independently verified DV-43 digest; no business result, row ID, cardinality,
schedule closure, or Q05/Q06/Q07 result changes. The closed airport
whitelist is `SFO`, `LAX`, `LAS`, `SEA`, `DEN`, `ORD`, `PHX`, `BOS`, and `MIA`, with corresponding synthetic actual-source
internal IDs `SYN-AP-*`. Public airport IATA/ICAO codes, names, and IANA time-zone names are
geography labels only. Planned endpoints use whitelisted IATA labels; actual endpoints use the
synthetic internal IDs required by the closed resolution map. Every carrier, registration, schedule,
passenger token, and display identity is `SYN-*`; numeric aircraft/history/flight IDs occupy the
reserved synthetic ranges declared in `EXPECTED_ANSWERS.yaml`. No row states or implies an observed
fact about a real carrier, and the ontology does not derive country or domestic classification.
The manifest machine-checks carrier/schedule/registration prefixes, reserved NUMBER ranges,
planned-IATA versus actual-internal endpoint forms, both endpoints of every named route, U.S.
Pacific/Mountain/Central/Eastern time-zone labels, spring-forward/fall-back offsets, a Phoenix
non-DST control, local-to-UTC date crossings, and AP-09 non-authority.

The v1.1 schedule closure is independently constructible. Its five and only five eligible complete
Q05 dates are August 3, 10, 17, 24, and 31, 2026. Twenty-two explicitly anchored schedule keys have
complete SS-04-through-SS-38 defaults, an explicit route-anchor-to-SS-06/10/11 field map, per-key
overrides, presence maps, and ordered content transitions. The manifest therefore recomputes 22
exact events and 13 separately labeled amendment
evidence rows. Every exact presence event is machine-accounted for as unique-candidate, ambiguous,
or exactly one unpaired row. A separate October 5/12/19/26 control freezes complete, missing,
incomplete, and post-gap behavior without inserting an eligible date into the Q05 window.

The D-0012 lineage known-answer uses byte grammar `dv43-lp-v1`. `LP(s)` writes the ASCII decimal
length of the UTF-8 bytes, an ASCII colon, and the bytes. The named PF-01-through-PF-19 vector is
exactly 610 bytes and hashes to
`a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7`; its null-ID DV-46 token is
`FORWARD|` followed by that digest. `SYN-PAX-VALID-NULL-ID-01` is presentation text only and is never
passenger identity, source-row identity, or a substitute DV-43 input.

All comparisons use typed values, null-safe equality, the declared row order, and the complete result
set. An empty result is an expected answer, not a failed query. Dates are ISO calendar dates and
timestamps are ISO `TIMESTAMP_NTZ` strings. Model validity is half-open; schedule operating bounds
remain inclusive. The result-set and scenario IDs below are immutable release identifiers.

## Classification landscape

The supplied questions ask what is true of known facts. Their primary discovery classification is
`rules`, implemented later as reusable deterministic derivation, classification, validation, and
reconciliation rules plus relational filtering/aggregation. None asks what should be optimized or
what will happen, so prescriptive and predictive reasoners are out of scope. Q08 contains a same-type
self-reference, but its required answer is a source-ordered validated chain; the supported baseline
is ordinary self-reference traversal. Optional graph path enumeration remains non-critical until an
installed-version live equality test adds demonstrable value.

| Query | Catalog ID | Primary rules type | Execution pattern | Current feasibility |
|---|---|---|---|---|
| 1 | `aircraft_as_of` | derivation / validation | independent half-open as-of joins | `MODEL_GAP` |
| 2 | `status_reversion_spells` | derivation / classification | ordered audit sequence and spell pairing | `MODEL_GAP` |
| 3 | `month_end_fleet_composition` | derivation | month calendar, as-of filters, aggregation | `MODEL_GAP` |
| 4 | `type_engine_histories` | derivation / reconciliation | independent assignment histories | `MODEL_GAP` |
| 5 | `schedule_four_week_changes` | reconciliation / classification | eligible snapshot comparisons | `MODEL_GAP` |
| 6 | `market_latest_vs_seven_days` | classification / reconciliation | exact complete endpoint set comparison | `MODEL_GAP` |
| 7 | `route_capacity_two_clocks` | derivation / validation | two-clock predicates and grouped aggregation | `MODEL_GAP` |
| 8 | `actual_rotation_enriched` | validation / derivation | validated self-reference traversal plus as-of joins | `MODEL_GAP` |

## Q01 — Reconstruct an aircraft as of a date

- **Business question:** For one physical aircraft and calendar date, what type, reported engine,
  lifecycle status, registration, and base were date-visible, and which requested dimensions are
  unresolved?
- **Canonical parameters:** synthetic `aircraft_id=1001`, `as_of_date=2026-08-31`.
- **Typed parameters:** `aircraft_id NUMBER(38,0)` and `as_of_date DATE`; both required.
- **Rules hint:** `rule_type=derivation`; source concept `Aircraft`; condition properties are
  existence bounds and the four independent daily assignment intervals; output is one composite
  reconstruction row with per-dimension status.
- **Feasibility:** `MODEL_GAP`. AM-01/07/08 and AH/AC assignment inputs exist in the contract;
  target mappings are `Aircraft` and the state/type/engine/status daily association concepts.
- **Expected result sets:** `Q01-CANONICAL` (`Q01-R001`), `Q01-BEFORE-FIRST` (`Q01-R002`),
  `Q01-UNKNOWN-GAP` (`Q01-R003`), and `Q01-EOL-BOUNDARY` (`Q01-R004`).
  `Q01-INVALID-AIRCRAFT-ID` freezes a typed validation error with zero rows.
- **SQL oracle shape:** one row from `AIRCRAFT_ELIGIBLE`, left joining each independently derived
  `AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT` where `valid_from <= :as_of_date < valid_to`; return raw
  resolved values, four DV-33 statuses, and `is_complete`. Do not backfill from master/current fields.
- **RAI shape:** select the Aircraft identity and independently match the four daily association
  concepts under the same point predicate; return the same scalar fields and statuses.
- **Order:** `aircraft_id`, `as_of_date`; each successful non-error scenario has exactly one row,
  while typed parameter errors return zero rows.
- **Scoped parity claim:** reproduces supplied point-in-time aircraft state/type/engine/status lookup
  for the named identity and boundary workloads while preserving same-day audit facts separately.
- **Snowflake differentiation:** the same source-resident facts and role-governed model can be checked
  against a Snowflake SQL oracle without copying customer data outside Snowflake.
- **Limitation:** historical APU/dimension/weight values not observed in events are not backfilled;
  exact mixed-engine fitment is unavailable; EOL is provisionally exclusive under D-0003.
- **Traceability:** P0-01 through P0-04, P0-12; HT-02, HT-05 through HT-11, HT-39/40; DV-01/02,
  DV-05 through DV-09, DV-33; NF-A01/A03/A04/A05/X02.

## Q02 — Find every In Service → Storage → In Service spell

- **Business question:** For an aircraft, which ordered audit-status assignments form every reversion
  spell, how many calendar days did Storage last, and was it a same-day spell?
- **Canonical parameters:** synthetic `aircraft_id=1001`; statuses are fixed catalog semantics
  `from_status='In Service'`, `middle_status='Storage'`, `return_status='In Service'`.
- **Rules hint:** `rule_type=derivation`; source concept `AircraftStatusAuditAssignment`; use canonical
  source order, consecutive equality suppression, and pair each Storage assignment with its next
  qualifying In Service assignment without deleting later reversion occurrences.
- **Feasibility:** `MODEL_GAP`; AH-01/03/04/05/09 and the audit-assignment target are contracted.
- **Expected result sets:** `Q02-CANONICAL` (`Q02-R001`, `Q02-R002`) and `Q02-NO-SPELLS` (zero rows).
- **SQL oracle shape:** ordered audit assignments with `LAG/LEAD` or equivalent sequence pairing;
  return source event IDs/sequences, storage/return dates, `storage_days`, and `same_day`.
- **RAI shape:** query the ordered audit assignment associations and derive qualifying adjacent status
  occurrences; no daily interval is assigned to audit observations.
- **Order:** `storage_start_date`, `storage_start_sequence`, `storage_event_id`, `return_event_id`.
- **Scoped parity claim:** matches the supplied status-reversion workload and additionally retains the
  date-grain zero-day spell that a coarse aircraft/date state key can lose.
- **Snowflake differentiation:** SQL and RAI independently validate the same ordered source lineage.
- **Limitation:** dates plus source sequence establish audit order, not intraday elapsed time.
- **Traceability:** P0-01/P0-02; HT-01/03/04/05; DV-03/04; NF-A01/A02.

## Q03 — Produce 120 month-end fleet-composition points

- **Business question:** At each month end for ten calendar years, how many in-service aircraft are
  assigned to each exact aircraft type?
- **Canonical parameters:** `start_month_end=2015-01-31`, `end_month_end=2024-12-31`,
  `status='In Service'`; exactly 120 month ends are required.
- **Rules hint:** `rule_type=derivation`; source concepts are Aircraft plus independent type/status
  daily assignments; generate calendar month ends, apply existence and both half-open point
  predicates, then group by type identity.
- **Feasibility:** `MODEL_GAP`; all data is contracted, but calendar and daily associations
  must be materialized/mapped.
- **Expected result set:** `Q03-CANONICAL`, rows `Q03-R001` through `Q03-R132`. The set contains 120
  distinct month ends and 132 nonzero `(month_end,type)` rows; zero-count type rows are omitted.
- **SQL oracle shape:** `(month_end DATE, aircraft_type_id VARCHAR, aircraft_type VARCHAR,
  in_service_aircraft_count NUMBER)` at one row per nonzero month/type.
- **RAI shape:** the identical grouped relation over month-end concepts and date-visible assignments;
  filler rows are barred from the anchored aircraft IDs.
- **Order:** `month_end`, `aircraft_type_id`.
- **Scoped parity claim:** proves bounded temporal aggregation over independently versioned type and
  status assignments for the named ten-year synthetic population.
- **Snowflake differentiation:** a SQL baseline and reusable semantic rule share governed tables and
  can be narrated with exact source counts.
- **Limitation:** synthetic counts establish functional behavior, not production size or timing.
- **Traceability:** P0-01 through P0-04/P0-14; HT-02/05/08/09/42/44/45; DV-01/02/05/06/07/33;
  NF-A02/A03/A05/E01.

## Q04 — Show independent type and engine histories

- **Business question:** For one aircraft, list type and engine assignment intervals independently
  and identify the type assignments that change the type from the preceding assignment.
- **Canonical parameters:** synthetic `aircraft_id=1001`.
- **Rules hint:** `rule_type=reconciliation`; compare two independent assignment streams, never align
  their boundaries by force; derive `is_type_change` only within the type stream.
- **Feasibility:** `MODEL_GAP`; AH-13 through AH-16, AC-02 through AC-15, and the target daily
  association concepts are contracted.
- **Expected result set:** `Q04-CANONICAL` (`Q04-R001` through `Q04-R004`).
- **SQL oracle shape:** normalized union with `dimension`, stable assignment key, `valid_from`,
  `valid_to`, resolved definition ID/label, engine count/completeness where applicable, and
  type-change flag where applicable.
- **RAI shape:** union/export of the independently defined type and engine daily associations.
- **Order:** `dimension` ascending (`aircraft_type` before `engine_type`), `valid_from`,
  `assignment_id`.
- **Scoped parity claim:** reproduces temporal type/engine links while making independent clocks and
  unresolved configuration gaps explicit.
- **Snowflake differentiation:** source lineage and ontology association payload remain queryable in
  the same governed environment.
- **Limitation:** one reported engine definition plus count is shown; a complete mixed-engine set is
  not derivable.
- **Traceability:** P0-01/P0-02/P0-04/P0-12; HT-04/05/11/39/40; DV-04 through DV-09;
  NF-A03/A04/X02.

## Q05 — Classify four weeks of schedule changes

- **Business question:** Across five complete weekly snapshots (four comparisons), which exact
  schedule keys were added, removed, or modified, and which key-shift amendment relationships are
  unique candidates, ambiguous groups, or unpaired evidence?
- **Canonical parameters:** `start_knowledge_date=2026-08-03`,
  `end_knowledge_date=2026-08-31`, `cadence_days=7`.
- **Rules hint:** `rule_type=reconciliation`; compare adjacent eligible complete snapshots, emit exact
  presence/content facts first, then separately classify conservative amendment evidence.
- **Feasibility:** `MODEL_GAP`; SS-01 through SS-40 and SC-01 through SC-06 are contracted,
  with target exact-change and amendment-evidence concepts defined.
- **Expected result sets:** `Q05-CANONICAL` (all 35 named rows `Q05-R001` through `Q05-R035`;
  22 exact rows plus 13 candidate/ambiguous/unpaired evidence rows) and
  `Q05-INELIGIBLE-ENDPOINT` for `2026-10-12` through `2026-10-19` (zero rows with status
  `ENDPOINT_MISSING`).
- **SQL oracle shape:** one normalized event relation with comparison endpoints, class, exactness,
  confidence, schedule/member keys, optional changed field/old/new values, candidate/group ID, and
  gap evidence, computed over every schedule observation in `SYN-SCHEDULE-UNIVERSE-01`. Exact
  add/remove rows remain even when candidate evidence exists; no question-private fixture filter is
  permitted.
- **RAI shape:** query `ScheduleExactChange` and `ScheduleAmendmentEvidence`, normalize to the same
  result schema, preserve typed labels, and apply the same complete-snapshot adjacency relation to
  the same unfiltered universe.
- **Order:** `comparison_date`, the manifest's `Q05_event_class` rank, `event_id`, `member_side`,
  `member_schedule_key`, with null member fields last.
- **Scoped parity claim:** matches key-preserving and key-presence workload semantics; key-changing
  relationships are parity evidence only as explicitly labeled candidates/groups, never exact. The
  bounded claim covers exactly the 35 v1.1 rows. Under D-0018 that claim is qualified: the event set,
  classification, keys, field deltas, gap flags and the candidate/ambiguous/unpaired closure are
  independently recomputed, but `event_id` and `row_id` are supplied manifest labels and the declared
  row sequence therefore is not independently verified. 490 of Q05-CANONICAL's 560 cells are
  recomputed; 65 are supplied.
- **Snowflake differentiation:** deterministic snapshot control, lineage, SQL reconciliation, and RAI
  rules execute over the same Snowflake-resident data.
- **Limitation:** without a stable amendment ID, non-overlapping shifts may remain unpaired and
  candidate ambiguity cannot be resolved. Q05 is an unfiltered demonstration universe, not a
  production completeness or performance claim.
- **Traceability:** P0-05 through P0-08/P0-15; HT-12 through HT-22/42/49; DV-13 through DV-19,
  DV-34 through DV-37/DV-43; NF-S01 through NF-S05; D-0010/D-0011;
  `CROSS-QUESTION-EVENT-CLOSURE-V1.1`.

## Q06 — Compare market entries and exits seven days apart

- **Business question:** For one explicit carrier role, which exact resolved airline/route markets
  entered or exited between an exact latest complete snapshot and the snapshot seven days earlier?
- **Canonical parameters:** `latest_knowledge_date=2026-08-31`,
  `comparison_knowledge_date=2026-08-24`, `carrier_role='marketing'`.
- **Rules hint:** `rule_type=classification`; classify zero-to-positive eligible schedule-key counts
  as entry and positive-to-zero as exit at `(carrier_role, airline_id, route)` grain.
- **Feasibility:** `MODEL_GAP`; snapshot, route, airline-resolution, and route-state inputs are
  contracted. Exact carrier resolution is required.
- **Expected result sets:** `Q06-CANONICAL` (`Q06-R001`, `Q06-R002`),
  `Q06-INCOMPLETE-ENDPOINT` for latest `2026-10-26` versus incomplete `2026-10-19` (zero rows with
  status `ENDPOINT_INCOMPLETE`), and
  `Q06-MISSING-CARRIER-ROLE` plus `Q06-INVALID-DATE` (typed validation errors, zero rows).
- **SQL oracle shape:** endpoint eligibility status plus complete set difference grouped by exact
  carrier-role airline and directional route over the same unfiltered schedule universe; return
  before/after key counts and change kind.
- **RAI shape:** the same endpoint-filtered classification over RouteState and labeled carrier links.
- **Order:** `change_kind` (`ENTRY` before `EXIT`), `airline_id`, `route_id`.
- **Scoped parity claim:** proves the supplied exact seven-day market comparison at the contracted
  market grain, with incomplete endpoints refused rather than substituted. D-0010's market-entry
  addition and market-exit removal are both also visible as Q05 exact/unpaired evidence, while
  stable market shadows prevent unrelated zero-crossings.
- **Snowflake differentiation:** completeness control and governance are visible beside semantic
  classifications and SQL evidence.
- **Limitation:** unresolved or ambiguous airline codes cannot yield exact airline-level markets;
  the query says when knowledge changed, not which service operates on another date.
- **Traceability:** P0-05/P0-08/P0-09/P0-12/P0-15; HT-12/14/26/29/38/48;
  DV-10 through DV-16/DV-29/30; NF-S03/S04/S06/S07/X01; D-0010/D-0011;
  `CROSS-QUESTION-EVENT-CLOSURE-V1.1`.

## Q07 — Compute route frequency and cabin capacity with both clocks

- **Business question:** At an explicit knowledge date and operating date, what weekly route
  frequency and cabin capacity are visible for an explicit marketing or operating carrier role?
- **Canonical parameter sets:**
  - marketing: `knowledge_date=2026-08-31`, `operating_date=2026-09-07`,
    `carrier_role='marketing'`;
  - operating: the same dates with `carrier_role='operating'`.
- **Rules hint:** `rule_type=derivation` plus validation; apply knowledge half-open validity,
  inclusive operating bounds and weekday, role-specific carrier links, physical-representative rule,
  and cabin reconciliation before grouping.
- **Feasibility:** `MODEL_GAP`; RouteState, carrier links, QueryExecutionContext, and capacity
  derivations are contracted.
- **Expected result sets:** `Q07-MARKETING` (`Q07-R001`, `Q07-R002`, `Q07-R005`), `Q07-OPERATING`
  (`Q07-R003`, `Q07-R004`), `Q07-KNOWLEDGE-END-EMPTY` (zero rows), and
  `Q07-MISSING-KNOWLEDGE-DATE`/`Q07-MISSING-OPERATING-DATE`/`Q07-MISSING-CARRIER-ROLE`
  (typed validation errors, zero rows). The nine-row
  `TT-BOTH-CLOCKS` truth table freezes HT-23; `TT-UTC-OFFSETS` freezes D-0008/HT-25;
  `TT-US-CLOCK-AUTHORITY` freezes U.S. DST/no-DST and AP-09 precedence assertions under D-0009.
- **SQL oracle shape:** grouped relation by carrier role, exact airline, and route with active
  schedule count, weekly frequency, total/cabin weekly seats, quality/unresolved status, and applied
  clock parameters.
- **RAI shape:** apply reusable two-clock predicates and role-specific relationships, then aggregate
  the same measures; no result table is imported as ontology semantics.
- **Order:** `result_status` (`COUNTED` before unresolved), `airline_id`, `route_id`.
- **Scoped parity claim:** proves both-clock route-state filtering, carrier-role separation,
  multi-open schedules, and conservative physical-capacity de-duplication for the named fixtures.
  The five canonical output rows are unchanged from v1.0: four single-field terminal changes open
  their target states at August 31, while a null→`PHX`→null clock-route transition and an
  operating-ineligible shadow preserve the separate both-clock truth table without adding Q07 rows.
- **Snowflake differentiation:** governed raw capacity, data-quality flags, SQL validation, semantic
  rules, and agent-ready typed parameters remain in one platform.
- **Limitation:** codeshare-only physical service without a stable service-group ID is visibly
  unresolved and excluded; synthetic scale does not support performance or cost claims.
- **Traceability:** P0-05/P0-06/P0-08/P0-09/P0-12/P0-15; HT-18/23 through HT-29/38/48;
  DV-10 through DV-15/DV-26 through DV-31/DV-47 through DV-51; NF-S06 through NF-S10/X01;
  D-0010; `CROSS-QUESTION-EVENT-CLOSURE-V1.1`.

## Q08 — Reconstruct and enrich an actual aircraft rotation

- **Business question:** For one aircraft and source-local departure date, what is the validated
  ordered actual-leg chain, where did each leg actually operate, and what aircraft type/engine was
  independently date-visible for each leg?
- **Canonical parameters:** synthetic `aircraft_id=1001`, `flight_departure_date=2026-08-31`.
- **Rules hint:** `rule_type=validation` then derivation; validate each AF-20 self-reference using
  actual times, actual airports, aircraft, and selected local date; traverse with visited set and
  finite bound; enrich each valid leg through independent type/engine daily assignments.
- **Feasibility:** `MODEL_GAP`; AF-01/02/06/08/09/10/11/12/13/14/17/20 and all target associations
  are contracted. Self-reference is sufficient; no graph reasoner is required.
- **Expected result sets:** `Q08-CANONICAL` (`Q08-R001` through `Q08-R003`),
  `Q08-ANOMALIES` (`Q08-R004` through `Q08-R014`), and `Q08-NOT-FOUND` (zero rows), plus the
  AF-06 local-date versus AF-07 UTC-date assertion in `TT-US-CLOCK-AUTHORITY`.
- **SQL oracle shape:** recursive traversal or bounded iterative self-join over validated links,
  returning segment/leg order, actual endpoints/times, terminal/link status, as-of type/engine,
  source descriptive fields, and discrepancy flags; anomalies are a typed companion union.
- **RAI shape:** ordinary typed self-reference traversal over accepted `next_flight` plus anomaly
  query, then point-in-time joins to type/engine daily associations.
- **Cycle normalization:** retain all member/link evidence but emit one `CYCLE` output row per cycle
  component at its minimum `flight_id`, preventing duplicate component-level anomalies.
- **Order:** `segment_id`, `row_kind` (`LEG` before `ANOMALY`), `leg_order`, `flight_id`,
  `anomaly_code`.
- **Scoped parity claim:** reproduces the supplied actual rotation/path workload through the source
  self-reference and adds independently governed as-of aircraft enrichment.
- **Snowflake differentiation:** actual facts, plan/actual distinction, aircraft history, SQL oracle,
  ontology traversal, and lineage remain jointly governed.
- **Limitation:** this is not arbitrary network path analytics. Optional graph path enumeration may
  be added only after an installed-runtime live equality test against these frozen rows. Actual
  endpoints/times never borrow planned values; actual endpoints are `SYN-AP-*` internal IDs, not
  the public IATA labels used on the plan side.
- **Traceability:** P0-02/P0-10/P0-11/P0-12/P0-15; HT-30 through HT-40/42/49;
  DV-05 through DV-09/DV-20 through DV-25/DV-38 through DV-45/DV-52/53;
  NF-F01/F02/R01/R02/X01/X02; D-0012 `dv43-lp-v1` known-answer and presentation-only token rule.

## Interface-wide negative behavior

Curated callers must reject missing required clocks or carrier role, invalid dates/IDs, unsupported
mixed-engine-set requests, optimization/prediction requests, and universal or production-scale
comparison prompts. Exact empty sets remain empty. Interfaces preserve `exact`, `candidate`,
`ambiguous`, `unpaired`, and `plan` versus `actual` labels. These behaviors are frozen by
`EXPECTED_ANSWERS.yaml` scenarios and P0-15; later agent work may improve wording but not silently
choose missing semantics.

For a retained forward passenger row with null stable source ID, the interface exposes only
`FORWARD|<64-lowercase-hex DV-43>` as lineage identity; a human-readable passenger token remains
presentation-only. These behaviors are frozen by D-0012, `TT32-R11`, HT-32/42/49, and the
`EXPECTED_ANSWERS.yaml` known-answer metadata.
