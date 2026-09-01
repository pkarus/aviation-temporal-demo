# SPEC-02 source contract

## Authority and scope

This contract is the physical and canonical input boundary for the `aviation_temporal` demo. It
implements `SEMANTIC_DECISIONS.md` and D-0003 through D-0008. If prose here can be read two ways,
the frozen semantic decision wins. The inputs below are normalized demo-owned aliases; no external
database path, customer identifier, customer row, or production-scale claim is part of this
artifact.

Only the fields needed for the eight golden questions, their lineage, and their negative fixtures
are in scope. A field omitted from this contract is not silently modeled. `DATA-03` must materialize
every RAI-bound object as a physical table under `PK_AVIATION_TEMPORAL`, enable change tracking, and
prove its types and counts before `MODEL-01` binds it.

Normative conventions:

- `source nullable` describes the raw source contract, not permission to invent an identity.
- A required identity component that is null is rejected, audited, or quarantined exactly as stated.
- The Snowflake types listed below are authoritative. `DATA-03` must compare them to live
  `INFORMATION_SCHEMA`; `MODEL-01` must derive installed-SDK RAI types from that evidence rather
  than names or samples. Source `TIME` remains `TIME`; any canonical representation added for an
  installed-runtime constraint must retain the raw field and have an explicit round-trip test.
- Dates equal to source sentinel `9999-12-31` normalize to `unknown_future`; they never become a
  real event or bound. Derived open intervals alone use model sentinel `9999-01-01`.
- State and knowledge intervals are half-open: `valid_from <= date < valid_to`. Source schedule
  operating bounds remain inclusive: `effective_date <= operating_date <= discontinue_date`.
- `end_event_date` is provenance, not the authority for derived assignment closure.

## Source objects and reduced fields

### `SOURCE.AIRCRAFT_MASTER`

- Grain: one source observation per physical aircraft.
- Declared key: `aircraft_id`; raw nulls are possible, but null IDs cannot create `Aircraft`.
- Eligibility: `not_for_use = false`; null is not silently treated as false.
- Write shape: upsert/current master.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| AM-01 | `aircraft_id` | NUMBER(38,0) | yes | Sole physical-aircraft identity. |
| AM-02 | `aircraft_serial_number` | VARCHAR | yes | Current source fact; never identity. |
| AM-03 | `aircraft_line_number` | VARCHAR | yes | Current source fact; never identity. |
| AM-04 | `aircraft_order_date` | DATE | yes | Source milestone; sentinel-aware. |
| AM-05 | `aircraft_build_date` | DATE | yes | Source milestone; sentinel-aware. |
| AM-06 | `aircraft_delivery_date` | DATE | yes | Source milestone; sentinel-aware. |
| AM-07 | `aircraft_start_of_life_date` | DATE | yes | Preferred existence lower bound. |
| AM-08 | `aircraft_end_of_life_date` | DATE | yes | Exclusive finite existence upper bound under D-0003. |
| AM-09 | `aircraft_build_airport_code_iata` | VARCHAR | yes | Original-build location fact; resolution is optional and provenance-preserving. |
| AM-10 | `original_delivery_operator` | VARCHAR | yes | Original-delivery fact, not current operator. |
| AM-11 | `apu_type` | VARCHAR | yes | Master-only copy, explicitly `CURRENT_ONLY`. |
| AM-12 | `aircraft_width_m` | FLOAT | yes | Master-only copy, explicitly `CURRENT_ONLY`. |
| AM-13 | `operating_maximum_takeoff_weight_lb` | NUMBER(38,0) | yes | Master-only copy, explicitly `CURRENT_ONLY`. |
| AM-14 | `certified_maximum_takeoff_weight_lb` | NUMBER(38,0) | yes | Master-only copy, explicitly `CURRENT_ONLY`. |
| AM-15 | `not_for_use` | BOOLEAN | yes | Eligibility flag, not modeled history. |
| AM-16 | `aircraft_roll_out_date` | DATE | yes | Source milestone; sentinel-aware. |
| AM-17 | `aircraft_first_flight_date` | DATE | yes | Source milestone; sentinel-aware. |
| AM-18 | `aircraft_build_airport` | VARCHAR | yes | Original-build location display fact. |
| AM-19 | `original_delivery_operator_category` | VARCHAR | yes | Original-delivery classification fact. |

### `SOURCE.AIRCRAFT_HISTORY`

- Grain: one source aircraft event.
- Declared key: `aircraft_history_id`.
- Required eligible columns: `aircraft_history_id`, `aircraft_id`, `start_event_date`, and
  `row_sequence_number`; null in any of them quarantines the event.
- Canonical order: `(start_event_date, row_sequence_number, event_sequence_number,
  aircraft_history_id)`, with the last two used only as deterministic fallbacks.
- Write shape: append-only events.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| AH-01 | `aircraft_history_id` | NUMBER(38,0) | yes | Stable event identity; required when eligible. |
| AH-02 | `aircraft_id` | NUMBER(38,0) | yes | Aircraft reference; required when eligible. |
| AH-03 | `row_sequence_number` | NUMBER(38,0) | yes | Primary same-day order; required when eligible. |
| AH-04 | `event_sequence_number` | NUMBER(38,0) | yes | Secondary deterministic order. |
| AH-05 | `start_event_date` | DATE | yes | Event effective date; required and sentinel-aware. |
| AH-06 | `end_event_date` | DATE | yes | Provenance/check only; never derived `valid_to` authority. |
| AH-07 | `is_current` | BOOLEAN | yes | Source diagnostic only. |
| AH-08 | `start_event` | VARCHAR | yes | Status-assignment provenance. |
| AH-09 | `start_aircraft_status` | VARCHAR | yes | Watched value for independent `aircraft_status`. |
| AH-10 | `end_event` | VARCHAR | yes | Source provenance. |
| AH-11 | `end_aircraft_status` | VARCHAR | yes | Source provenance, not next-state authority. |
| AH-12 | `event_source` | VARCHAR | yes | Assignment lineage/provenance. |
| AH-13 | `aircraft_configuration_id` | NUMBER(38,0) | yes | Optional configuration reference; unresolved/null closes known type/engine dimensions. |
| AH-14 | `aircraft_code_iata` | VARCHAR | yes | Event-observed aircraft-type association attribute. |
| AH-15 | `aircraft_code_icao` | VARCHAR | yes | Event-observed aircraft-type association attribute. |
| AH-16 | `aircraft_value_sub_series` | VARCHAR | yes | Event-observed aircraft-type association attribute. |
| AH-17 | `aircraft_registration_number` | VARCHAR | yes | Watched `aircraft_state` value. |
| AH-18 | `aircraft_transponder_code` | VARCHAR | yes | Watched `aircraft_state` value. |
| AH-19 | `aircraft_registration_country_code_iso` | VARCHAR | yes | Watched `aircraft_state` value. |
| AH-20 | `aircraft_registration_region` | VARCHAR | yes | Watched `aircraft_state` value. |
| AH-21 | `aircraft_cargo` | VARCHAR | yes | Watched `aircraft_state` value. |
| AH-22 | `storage_location` | VARCHAR | yes | Watched `aircraft_state` value, not a separate location concept in v1. |
| AH-23 | `storage_airport_code_iata` | VARCHAR | yes | Watched raw location code with explicit resolution status. |
| AH-24 | `base_airport` | VARCHAR | yes | Watched base display value. |
| AH-25 | `base_airport_code_iata` | VARCHAR | yes | Watched base code with explicit resolution status. |
| AH-26 | `base_city` | VARCHAR | yes | Watched `aircraft_state` value. |
| AH-27 | `base_country` | VARCHAR | yes | Watched `aircraft_state` value. |
| AH-28 | `apu_type` | VARCHAR | yes | Historically observed, watched `aircraft_state` value. |
| AH-29 | `aircraft_width_m` | FLOAT | yes | Historically observed, watched `aircraft_state` value. |
| AH-30 | `operating_maximum_takeoff_weight_lb` | NUMBER(38,0) | yes | Historically observed, watched `aircraft_state` value. |
| AH-31 | `certified_maximum_takeoff_weight_lb` | NUMBER(38,0) | yes | Historically observed, watched `aircraft_state` value. |
| AH-32 | `not_for_use` | BOOLEAN | yes | Event eligibility/quality flag. |
| AH-33 | `publish_date` | DATE | yes | Source lineage date, not state validity. |

Under D-0004, the complete ordered audit sequence and the final-per-day projection are different
products. The complete `aircraft_state` watched set for this reduced demo is AH-17 through AH-31. The
`aircraft_type` watched set is AH-14 through AH-16 plus the resolved type fields AC-02 through
AC-07 and the type-resolution outcome of AH-13. The `engine_type` watched set is AC-08 through
AC-15 plus the engine-resolution outcome of AH-13. Raw AH-13 itself is resolution/provenance, not
a watched business value: changing to a different configuration with an identical resolved
dimension does not mint a false assignment, while changing from resolved to null/unresolved does
open the required dimension-specific gap. The `aircraft_status` watched set is AH-09, while AH-08
and AH-12 remain provenance. Comparison is null-safe and per dimension. Consecutive equality is
suppressed; global equality is not, so `A -> B -> A` remains three assignments.

### `SOURCE.AIRCRAFT_CONFIGURATION`

- Grain: one configuration reference row.
- Declared key: `aircraft_configuration_id`.
- Write shape: upsert/reference.
- A history event is left-preserved across resolution. Failure to resolve AC-01 never drops AH-01.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| AC-01 | `aircraft_configuration_id` | NUMBER(38,0) | yes | Configuration identity/reference target. |
| AC-02 | `aircraft_family` | VARCHAR | yes | Aircraft-type definition. |
| AC-03 | `aircraft_type` | VARCHAR | yes | Aircraft-type definition. |
| AC-04 | `aircraft_series` | VARCHAR | yes | Aircraft-type definition. |
| AC-05 | `aircraft_subseries` | VARCHAR | yes | Aircraft-type identity candidate; required for exact type link. |
| AC-06 | `aircraft_manufacturer` | VARCHAR | yes | Aircraft-type definition. |
| AC-07 | `aircraft_design_class` | VARCHAR | yes | Aircraft-type definition. |
| AC-08 | `engine_count` | NUMBER(38,0) | yes | Reported engine count. |
| AC-09 | `has_multiple_engine_types` | BOOLEAN | yes | Completeness limitation flag. |
| AC-10 | `engine_manufacturer` | VARCHAR | yes | Engine-type definition. |
| AC-11 | `engine_family` | VARCHAR | yes | Engine-type definition. |
| AC-12 | `engine_type` | VARCHAR | yes | Engine-type definition. |
| AC-13 | `engine_series` | VARCHAR | yes | Engine-type definition. |
| AC-14 | `engine_subseries` | VARCHAR | yes | Engine-type identity candidate; required for exact engine link. |
| AC-15 | `engine_propulsion_type` | VARCHAR | yes | Engine-type definition. |
| AC-16 | `publish_date` | DATE | yes | Reference lineage date, not assignment validity. |

Before `AircraftType` or `EngineType` is used as a functional target, `DATA-03` must prove one
consistent definition per non-null subseries in the reduced data (AC-02 through AC-07 for aircraft
type and AC-10 through AC-15 for engine type). AC-08 and AC-09 are configuration/assignment payload,
not functional properties of an engine-subseries identity; this avoids asserting one engine count
for every configuration that reports that type. Zero or many candidates produce dimension-specific
unresolved/ambiguous assignment evidence rather than an invented node link. When AC-09 is true,
AC-08 and the one reported engine definition remain visible, but
`mixed_engine_set_complete = false`; a second engine type or per-position fitment is unsupported.

### `SOURCE.SCHEDULE_SNAPSHOT`

- Raw grain: one normalized itinerary observation per `(schedule_key, publish_date,
  itinerary_variation_identifier, normalized_row_hash)`. Identical hashes are semantic duplicates.
- Source-declared schedule identity: `schedule_key`; knowledge observation date: `publish_date`.
- Canonical selected grain: at most one row per `(schedule_key, publish_date)` after deterministic
  ranking by weekly frequency descending, total seats descending, itinerary variation ascending,
  then normalized row hash ascending; business nulls sort last.
- Only snapshot dates eligible in `SOURCE.SCHEDULE_SNAPSHOT_CALENDAR` participate in presence or
  change inference.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| SS-01 | `schedule_key` | VARCHAR | yes | Exact schedule identity; required for an eligible observation. |
| SS-02 | `schedule_key_readable` | VARCHAR | yes | Lineage/debug representation, not semantic identity. |
| SS-03 | `publish_date` | DATE | yes | Knowledge observation date; required. |
| SS-04 | `marketing_carrier_internal` | VARCHAR | yes | Raw marketing carrier code for resolution and candidate signature. |
| SS-05 | `operating_carrier_internal` | VARCHAR | yes | Raw operating carrier code; kept separate from marketing. |
| SS-06 | `flight_number` | NUMBER(38,0) | yes | Schedule identity/candidate evidence. |
| SS-07 | `service_type_iata` | VARCHAR | yes | Watched schedule content. |
| SS-08 | `effective_date` | DATE | yes | Inclusive operating lower bound; also exact key/candidate evidence. |
| SS-09 | `discontinue_date` | DATE | yes | Inclusive operating upper bound; also exact key/candidate evidence. |
| SS-10 | `departure_station_code_iata` | VARCHAR | yes | Raw planned origin; route and resolution input. |
| SS-11 | `arrival_station_code_iata` | VARCHAR | yes | Raw planned destination; route and resolution input. |
| SS-12 | `departure_terminal` | VARCHAR | yes | Watched schedule content. |
| SS-13 | `arrival_terminal` | VARCHAR | yes | Watched schedule content. |
| SS-14 | `is_operating_monday` | BOOLEAN | yes | Operating weekday predicate and watched content. |
| SS-15 | `is_operating_tuesday` | BOOLEAN | yes | Operating weekday predicate and watched content. |
| SS-16 | `is_operating_wednesday` | BOOLEAN | yes | Operating weekday predicate and watched content. |
| SS-17 | `is_operating_thursday` | BOOLEAN | yes | Operating weekday predicate and watched content. |
| SS-18 | `is_operating_friday` | BOOLEAN | yes | Operating weekday predicate and watched content. |
| SS-19 | `is_operating_saturday` | BOOLEAN | yes | Operating weekday predicate and watched content. |
| SS-20 | `is_operating_sunday` | BOOLEAN | yes | Operating weekday predicate and watched content. |
| SS-21 | `days_pattern` | VARCHAR | no | Watched compact weekday evidence; validated against booleans. |
| SS-22 | `weekly_frequency` | NUMBER(38,0) | no | Watched content, de-duplication rank, and frequency metric. |
| SS-23 | `passenger_departure_utc_time` | TIME | yes | Watched recurring UTC time; never combined with a local date without evidence. |
| SS-24 | `passenger_arrival_utc_time` | TIME | yes | Watched recurring UTC time; never used to infer day shift alone. |
| SS-25 | `passenger_departure_local_time` | TIME | yes | Watched recurring local time. |
| SS-26 | `passenger_arrival_local_time` | TIME | yes | Watched recurring local time. |
| SS-27 | `arrival_day_indicator` | NUMBER(38,0) | yes | Explicit local arrival-day offset. |
| SS-28 | `scheduled_block_minutes` | NUMBER(38,0) | yes | Watched schedule content. |
| SS-29 | `equipment_subtype_code_iata` | VARCHAR | yes | Watched equipment content. |
| SS-30 | `total_seats` | FLOAT | yes | Watched raw capacity. |
| SS-31 | `first_class_seats` | FLOAT | yes | Watched raw cabin capacity. |
| SS-32 | `business_class_seats` | FLOAT | yes | Watched raw cabin capacity. |
| SS-33 | `premium_economy_seats` | FLOAT | yes | Watched raw subset of economy. |
| SS-34 | `economy_class_seats` | FLOAT | yes | Watched raw cabin capacity including premium economy. |
| SS-35 | `is_codeshare` | BOOLEAN | yes | Watched carrier/physical-service evidence. |
| SS-36 | `codeshare_carrier_internal` | VARCHAR | yes | Watched codeshare evidence. |
| SS-37 | `number_of_intermediate_stops` | NUMBER(38,0) | yes | Watched itinerary/fulfillment evidence. |
| SS-38 | `intermediate_stop_station_codes_iata` | VARCHAR | yes | Watched itinerary/fulfillment evidence. |
| SS-39 | `itinerary_variation_identifier` | NUMBER(38,0) | yes | Deterministic selection evidence, excluded from content comparison. |
| SS-40 | `normalized_row_hash` | VARCHAR | no | DV-43 SHA-256 over typed normalized SS-01 through SS-39; final stable tie-break and lineage. |

The exact reduced watched-field set is SS-04 through SS-38. SS-01 is the partition identity;
SS-03 controls knowledge observation; SS-02, SS-39, and SS-40 are lineage/de-duplication evidence.
All watched comparisons are null-safe. A route is directional and carrier-agnostic with identity
`departure_station_code_iata || '->' || arrival_station_code_iata`; both components must be non-null.
A null component yields `INVALID_ROUTE_KEY` audit evidence and no Route identity, while the raw
schedule observation remains counted. Non-null raw codes remain visible even if reference resolution
is not exact. Likewise, a null SS-01 or SS-03 prevents an eligible canonical schedule observation
and is quarantined/counted rather than guessed. A valid SS-01/SS-03 with an invalid route may still
produce exact schedule-key presence and watched-content change evidence; it cannot produce a Route,
RouteState, route market/capacity result, or key-shift candidate.

DV-43 serialization is fixed for every contracted hash: ascending Field ID; each value encoded as
Field ID, Snowflake type tag, and canonical value; null uses a distinct `NULL` token; integer uses
base-10 without padding; float uses lossless canonical decimal; Boolean is `true|false`; DATE is
ISO `YYYY-MM-DD`; TIME and TIMESTAMP_NTZ use ISO forms with full stored precision and no invented
timezone; VARCHAR is UTF-8 with source-preserving Unicode normalization. Fields are length-prefixed
before SHA-256 so delimiters cannot collide. SS-40 hashes SS-01 through SS-39 and never hashes itself.
DV-46 is source-system-prefixed and uses the retained stable source key when available: AM-01,
AH-01, AC-01, `(SS-01, SS-03, SS-40)`, SC-01, PF-01, PH-01, AF-01,
`(AP-01, AP-02)`, or `(AL-01, AL-02)`. For a retained PF/PH observation whose stable source ID is
null, it uses that source token plus DV-43. It is never built from an unqualified nullable ID.
DV-44 uses the same source qualification, stable ID when present or DV-43 otherwise, plus a closed
reason code; identical invalid observations retain an occurrence count rather than an unstable row
ordinal.

### `SOURCE.SCHEDULE_SNAPSHOT_CALENDAR`

- Grain/key: one expected snapshot publish date, `expected_publish_date`.
- Source: a declared synthetic fixture/control input, not inferred from received row presence.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| SC-01 | `expected_publish_date` | DATE | no | Snapshot-calendar identity. |
| SC-02 | `is_present` | BOOLEAN | no | Explicit arrival evidence. |
| SC-03 | `is_complete` | BOOLEAN | no | Explicit completeness evidence. |
| SC-04 | `source_lineage_id` | VARCHAR | no | Synthetic input batch/fixture lineage. |
| SC-05 | `observed_row_count` | NUMBER(38,0) | yes | Validation evidence, never completeness by itself. |
| SC-06 | `validation_status` | VARCHAR | no | Named validation outcome/evidence token. |

Eligibility is exactly `is_present = true AND is_complete = true`. A missing or incomplete date
cannot open/close a segment or create additions, removals, entries, or exits. A post-gap comparison
uses the previous eligible date, exposes the gap, and never invents an occurrence date within it.
Latest-versus-seven-days requires both exact calendar endpoints to be eligible.

### `SOURCE.PASSENGER_FORWARD`

- Grain: one forward planned flight source observation.
- Source row identity: `forward_source_row_id`; missing ID is quarantined if the canonical key is
  also invalid.
- Canonical key components are PF-02, PF-04, PF-08, PF-09, and PF-05; all are required.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| PF-01 | `forward_source_row_id` | NUMBER(38,0) | yes | Stable forward source-row lineage. |
| PF-02 | `marketing_carrier_internal` | VARCHAR | yes | Typed passenger-key component and marketing role. |
| PF-03 | `operating_carrier_internal` | VARCHAR | yes | Operating role; does not replace marketing identity. |
| PF-04 | `flight_number` | NUMBER(38,0) | yes | Typed passenger-key component. |
| PF-05 | `operating_date` | DATE | yes | Typed passenger-key component and plan operating date. |
| PF-06 | `publish_date` | DATE | yes | Source precedence/de-duplication lineage. |
| PF-07 | `service_type_iata` | VARCHAR | yes | Planned-service fact. |
| PF-08 | `departure_station_code_iata` | VARCHAR | yes | Typed passenger-key planned origin. |
| PF-09 | `arrival_station_code_iata` | VARCHAR | yes | Typed passenger-key planned destination. |
| PF-10 | `passenger_departure_time_local` | TIMESTAMP_NTZ | yes | Planned local departure timestamp. |
| PF-11 | `passenger_arrival_time_local` | TIMESTAMP_NTZ | yes | Planned local arrival timestamp. |
| PF-12 | `passenger_departure_time_utc` | TIMESTAMP_NTZ | yes | Planned UTC departure timestamp with date evidence. |
| PF-13 | `passenger_arrival_time_utc` | TIMESTAMP_NTZ | yes | Planned UTC arrival timestamp with date evidence. |
| PF-14 | `arrival_day_indicator` | NUMBER(38,0) | yes | Planned local arrival-day evidence. |
| PF-15 | `equipment_subtype_code_iata` | VARCHAR | yes | Planned equipment fact. |
| PF-16 | `total_seats` | NUMBER(38,0) | yes | Planned raw capacity fact. |
| PF-17 | `is_codeshare` | BOOLEAN | yes | Planned carrier-role evidence. |
| PF-18 | `number_of_intermediate_stops` | NUMBER(38,0) | yes | Stopover/fulfillment evidence. |
| PF-19 | `intermediate_stop_station_codes_iata` | VARCHAR | yes | Stopover/fulfillment evidence. |

### `SOURCE.PASSENGER_HISTORICAL`

- Grain: one historical planned flight source observation.
- Source row identity: `historical_source_row_id`.
- Canonical key components are PH-05, PH-07, PH-10, PH-11, and PH-04; all are required.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| PH-01 | `historical_source_row_id` | NUMBER(38,0) | yes | Stable historical-flight ID in the same contracted ID domain as AF-01; direct-link candidate. |
| PH-02 | `schedule_key` | VARCHAR | yes | Exact schedule identity when available. |
| PH-03 | `publish_date` | DATE | yes | Knowledge/source precedence lineage. |
| PH-04 | `operating_date` | DATE | yes | Typed passenger-key component. |
| PH-05 | `marketing_carrier_internal` | VARCHAR | yes | Typed passenger-key component and marketing role. |
| PH-06 | `operating_carrier_internal` | VARCHAR | yes | Operating role, separate from marketing. |
| PH-07 | `flight_number` | NUMBER(38,0) | yes | Typed passenger-key component. |
| PH-08 | `service_type_iata` | VARCHAR | yes | Planned-service fact. |
| PH-09 | `effective_date` | DATE | yes | Historical schedule lineage. |
| PH-10 | `departure_station_code_iata` | VARCHAR | yes | Typed passenger-key planned origin. |
| PH-11 | `arrival_station_code_iata` | VARCHAR | yes | Typed passenger-key planned destination. |
| PH-12 | `passenger_departure_local_time` | TIME | yes | Planned recurring/local time evidence. |
| PH-13 | `passenger_arrival_local_time` | TIME | yes | Planned recurring/local time evidence. |
| PH-14 | `passenger_departure_utc_time` | TIME | yes | UTC time only; date remains unresolved without offsets. |
| PH-15 | `passenger_arrival_utc_time` | TIME | yes | UTC time only; day shift is not inferred from clock values. |
| PH-16 | `departure_utc_offset_minutes` | FLOAT | yes | Explicit UTC conversion evidence. |
| PH-17 | `arrival_utc_offset_minutes` | FLOAT | yes | Explicit UTC conversion evidence. |
| PH-18 | `arrival_day_indicator` | NUMBER(38,0) | yes | Planned local arrival-day evidence. |
| PH-19 | `equipment_subtype_code_iata` | VARCHAR | yes | Planned equipment fact. |
| PH-20 | `total_seats` | FLOAT | yes | Planned raw capacity fact. |
| PH-21 | `is_codeshare` | BOOLEAN | yes | Planned carrier-role evidence. |
| PH-22 | `number_of_intermediate_stops` | NUMBER(38,0) | yes | Stopover/fulfillment evidence. |
| PH-23 | `intermediate_stop_station_codes_iata` | VARCHAR | yes | Stopover/fulfillment evidence. |

`PassengerFlight` is a typed canonical union, not an untyped append. Historical wins a canonical
key overlap and both lineages are retained. Within a side, deterministic reduction is publish date
descending, stable source row ID ascending, then DV-43 typed normalized-row hash ascending. PF rows
hash PF-01 through PF-19 prefixed by source-system token `FORWARD`; PH rows hash PH-01 through PH-23
prefixed by `HISTORICAL`, using the same fixed serialization above. Forward-only historical fields
stay null. A null key component creates `INVALID_PASSENGER_KEY` audit evidence;
it creates no `PassengerFlight`. Missing both canonical identity and stable row ID is quarantined.

Under binding provisional D-0008, PH-16/PH-17 use the source convention `offset_minutes = local - UTC`.
DV-47 is PH-04 plus PH-12. DV-48 is PH-04 plus PH-18 calendar days plus PH-13. DV-49 is DV-47
minus PH-16 minutes, and DV-50 is DV-48 minus PH-17 minutes. A null or non-finite required offset
sets DV-51 to `UNRESOLVED_UTC_DATE` and yields no dated UTC timestamp; clock ordering never supplies
the missing sign/date. PF-12/PF-13 are source-expanded timestamps with DV-51=`EXPLICIT_EXPANDED` and
are not recomputed. Schedule SS-23/SS-24 remain TIME-only `UNRESOLVED_UTC_DATE` unless a future
contracted offset or expanded timestamp is present. The rollback for authoritative opposite-sign
evidence changes only subtraction to addition and reruns HT-25 and every both-clock/UTC test.

### `SOURCE.AIRCRAFT_FLIGHT`

- Grain/key: one actual flown-leg observation, `flight_id`.
- Actual facts never overwrite passenger/schedule plan facts.
- Null `flight_id` cannot create `AircraftFlight`.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| AF-01 | `flight_id` | NUMBER(38,0) | yes | Actual-leg identity in the same contracted historical-flight ID domain as PH-01; direct fulfillment candidate. |
| AF-02 | `aircraft_id` | NUMBER(38,0) | yes | Optional physical-aircraft reference. |
| AF-03 | `operating_carrier_code` | VARCHAR | yes | Actual operating-carrier evidence. |
| AF-04 | `marketing_carrier_code` | VARCHAR | yes | Actual marketing-carrier evidence. |
| AF-05 | `flight_number` | VARCHAR | yes | Actual flight-number evidence; typed normalization required for matching. |
| AF-06 | `flight_departure_date` | DATE | yes | Source local selected-day basis and enrichment date. |
| AF-07 | `flight_departure_date_utc` | DATE | yes | UTC lineage, not selected-day substitute. |
| AF-08 | `departure_airport_code` | VARCHAR | yes | Actual departure airport resolution input. |
| AF-09 | `arrival_airport_code` | VARCHAR | yes | Actual arrival airport; authoritative for continuity. |
| AF-10 | `diverted_airport_code` | VARCHAR | yes | Diversion evidence; plan remains separate. |
| AF-11 | `is_cancelled` | NUMBER(38,0) | yes | Actual operational state; normalized to Boolean with invalid values flagged. |
| AF-12 | `is_diverted` | NUMBER(38,0) | yes | Actual diversion state; normalized to Boolean with invalid values flagged. |
| AF-13 | `actual_gate_departure_time_utc` | TIMESTAMP_NTZ | yes | Strict rotation ordering/start time. |
| AF-14 | `actual_gate_arrival_time_utc` | TIMESTAMP_NTZ | yes | Strict rotation continuity/end time. |
| AF-15 | `actual_gate_departure_time_local` | TIMESTAMP_NTZ | yes | Actual local-time evidence. |
| AF-16 | `actual_gate_arrival_time_local` | TIMESTAMP_NTZ | yes | Actual local-time evidence. |
| AF-17 | `aircraft_type` | VARCHAR | yes | Actual-source descriptive observation; never aircraft-history authority. |
| AF-18 | `aircraft_code_iata` | VARCHAR | yes | Actual-source descriptive observation. |
| AF-19 | `aircraft_family` | VARCHAR | yes | Actual-source descriptive observation. |
| AF-20 | `next_flight_id` | NUMBER(38,0) | yes | Optional actual-leg self-reference; baseline rotation edge. |

DV-45 `actual_continuity_arrival_code` is exactly AF-09. AF-10 and AF-12 are reconciliation evidence:
when diverted, non-null AF-10 must equal AF-09; disagreement emits `DIVERSION_ENDPOINT_CONFLICT`
and terminates continuity. AF-10 never repairs a null or conflicting AF-09. Strict rotation uses
AF-06, AF-13, AF-14, AF-08, DV-45, DV-52, and AF-20. A link is accepted only
when the target exists, is different, has the same aircraft and AF-06, departs no earlier than the
current arrival, and departs from the current actual arrival airport. Self-loop, cycle, missing
target, different aircraft, `OUTSIDE_SELECTED_DAY`, backward time, broken airport continuity,
cancellation, and missing time stay visible as typed anomalies. Enrichment uses AF-06 against the
independent daily aircraft type/engine assignments; AF-17 through AF-19 are discrepancy evidence.

DV-52 maps AF-11 integer 0 to false and 1 to true. Null, non-integer, or any other value emits
`UNKNOWN_OR_INVALID_CANCELLATION_FLAG`; the row remains visible but is excluded from the strict
operated chain. DV-53 applies the same 0/1 mapping to AF-12; null/invalid emits
`UNKNOWN_OR_INVALID_DIVERSION_FLAG` and cannot override DV-45. Any non-null AF-10 must reconcile to
AF-09 regardless of DV-53; mismatch remains `DIVERSION_ENDPOINT_CONFLICT` and terminates continuity.

### `SOURCE.AIRPORT_REFERENCE`

- Grain: one airport reference observation per `(airport_id, effective_start_date)`.
- Semantic identity in v1: `airport_id`; effective periods remain lineage, not modeled state.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| AP-01 | `airport_id` | VARCHAR | yes | Airport identity; required for a concept. |
| AP-02 | `effective_start_date` | DATE | yes | Resolution lineage only. |
| AP-03 | `effective_end_date` | DATE | yes | Resolution lineage only. |
| AP-04 | `airport_code_iata` | VARCHAR | yes | Resolution candidate code. |
| AP-05 | `airport_code_icao` | VARCHAR | yes | Resolution candidate code. |
| AP-06 | `airport_name` | VARCHAR | yes | Current identity description. |
| AP-07 | `is_active` | BOOLEAN | yes | Resolution/description evidence, not silent tie-breaker. |
| AP-08 | `is_current` | BOOLEAN | yes | Resolution/description evidence, not silent tie-breaker. |
| AP-09 | `time_zone_name` | VARCHAR | yes | Conversion evidence only when explicit rules support it. |

### `SOURCE.AIRLINE_REFERENCE`

- Grain: one airline reference observation per `(airline_id, effective_start_date)`.
- Semantic identity in v1: `airline_id`; effective periods remain lineage, not modeled state.

| Field ID | Demo source column | Snowflake type | Source nullable | Canonical role |
|---|---|---|---|---|
| AL-01 | `airline_id` | VARCHAR | yes | Airline identity; required for a concept. |
| AL-02 | `effective_start_date` | DATE | yes | Resolution lineage only. |
| AL-03 | `effective_end_date` | DATE | yes | Resolution lineage only. |
| AL-04 | `carrier_code_iata` | VARCHAR | yes | Resolution candidate code. |
| AL-05 | `carrier_code_icao` | VARCHAR | yes | Resolution candidate code. |
| AL-06 | `carrier_short_name` | VARCHAR | yes | Current identity description. |
| AL-07 | `carrier_full_name` | VARCHAR | yes | Current identity description. |
| AL-08 | `is_iata_controlled_duplicate` | BOOLEAN | yes | Ambiguity evidence, never a forced choice. |
| AL-09 | `is_active` | BOOLEAN | yes | Resolution/description evidence. |
| AL-10 | `is_current` | BOOLEAN | yes | Resolution/description evidence, not silent tie-breaker. |

### Closed code-resolution method map

Resolution uses source-preserving exact string equality: no case folding, punctuation stripping,
or fuzzy/name match. Null/empty input is `INVALID_INPUT`. Candidate counts are distinct AP-01 or
AL-01 identities; all matching effective-period rows remain lineage, while active/current flags do
not select a winner.

| Raw Field IDs / role | Domain | Contracted method and candidate column(s) |
|---|---|---|
| AM-09 build airport; AH-23 storage airport; AH-25 base airport | Airport | `AIRPORT_IATA_EXACT` against AP-04. |
| SS-10 route origin; SS-11 route destination | Airport | `AIRPORT_IATA_EXACT` against AP-04. |
| PF-08/PF-09 and PH-10/PH-11 planned endpoints | Airport | `AIRPORT_IATA_EXACT` against AP-04. |
| AF-08 actual origin; AF-09 actual destination; AF-10 diversion evidence | Airport | `AIRPORT_INTERNAL_ID_EXACT` against AP-01. |
| SS-04 marketing, SS-05 operating, SS-36 codeshare carrier | Airline | `AIRLINE_ALIAS_UNION_EXACT`: candidate AL-01 when raw equals AL-01, AL-04, or AL-05; matched code system(s) retained. No precedence is assigned among systems. |
| PF-02/PF-03 and PH-05/PH-06 marketing/operating carriers | Airline | `AIRLINE_ALIAS_UNION_EXACT` against the same AL-01/AL-04/AL-05 union. |
| AF-03 actual operating carrier; AF-04 actual marketing carrier | Airline | `AIRLINE_INTERNAL_ID_EXACT` against AL-01. |

AM-10 is an original-delivery name fact and is not code-resolved in v1. AH-14/AH-15 and SS-29 are
aircraft/equipment codes, not Airport/Airline references. Any future alias crosswalk or normalization
method is a new contracted source and cannot be inserted silently into these candidate sets.

## Canonical physical model-input contracts

These are deterministic synthetic derivations materialized in `MODEL_INPUT`; they are not final
golden-answer tables. Each row retains the listed raw Field IDs or its declared derivation.

| Canonical object | Stable grain/key | Required modeled fields and derivation |
|---|---|---|
| `AIRCRAFT_ELIGIBLE` | AM-01 | Aircraft master fields; `existence_from = normalized AM-07`, falling back to first eligible AH-05; `existence_to = normalized exclusive AM-08` or model open sentinel. |
| `AIRCRAFT_EVENT_ELIGIBLE` | AH-01 | AH-01 through AH-33 after eligibility/sentinel normalization; canonical order tuple retained. |
| `AIRCRAFT_EVENT_QUARANTINE` | DV-44 | Raw lineage, missing required-field list, occurrence count, and reason; no guessed aircraft/event identity. Identical invalid rows without source IDs share a deterministic semantic quarantine key and retain occurrence count. |
| `AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT` | `(dimension, AH-02, AH-05, AH-03, AH-01)` | `dimension`, ordered source tuple, null-safe watched-value payload, optional exact target, resolution status, AH-06/AH-08/AH-12 provenance; no `valid_from`/`valid_to`. |
| `AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT` | `(dimension, AH-02, AH-05, AH-01)` | Final relevant observation for aircraft/dimension/date; `valid_from = AH-05`; `valid_to = next distinct daily assignment date` clipped to existence; target/DV-08 resolution/DV-33 query status and audit lineage. |
| `AIRCRAFT_TYPE_DEFINITION` | AC-05 | AC-02 through AC-07 after one-definition-per-key proof. |
| `ENGINE_TYPE_DEFINITION` | AC-14 | AC-10 through AC-15 after definition FD proof; AC-08/AC-09 and `mixed_engine_set_complete` stay on the configuration/engine-assignment association. |
| `CODE_RESOLUTION` | deterministic `resolution_id = SHA-256(domain, source_object, DV-46 source_row_token, field_role, raw_code, method)` | Raw code from AH/SS/PF/PH/AF, `candidate_count`, `EXACT|AMBIGUOUS|UNRESOLVED|INVALID_INPUT`, and effective/reference lineage. This stable result exists even at zero candidates and for valid PF/PH rows with null source IDs. Concept link exists only for `EXACT` cardinality one. |
| `CODE_RESOLUTION_CANDIDATE` | `(resolution_id, candidate_id)` | Zero, one, or many AP-01/AL-01 candidates associated with the stable result; no nullable candidate is used as identity. |
| `SCHEDULE_CANONICAL_OBSERVATION` | `(SS-01, SS-03)` | Deterministically selected SS row; SS-40 and selected variant evidence; only eligible SC dates drive inference. |
| `ROUTE` | `(SS-10, SS-11)` typed directional pair | Raw planned origin/destination, optional exact airport links, and resolution statuses. |
| `ROUTE_STATE` | `route_state_key = SS-01 || '|' || valid_from` | Selected SS-04 through SS-38 with a valid non-null DV-12 Route; `valid_from` is segment-opening eligible SS-03; `valid_to` is next eligible content change/absence or model open sentinel. `INVALID_ROUTE_KEY` observations remain counted diagnostics and exact schedule-key changes, but are ineligible for RouteState, route market/capacity, or key-shift candidate inference. |
| `ROUTE_STATE_LINEAGE` | `(route_state_key, SS-03, SS-40)` | Every contributing complete snapshot and selected itinerary evidence. |
| `SCHEDULE_EXACT_CHANGE` | `(DV-34, SS-01, change_kind, field_name)` | Exact key-preserving field deltas or exact presence addition/removal; old/new values; gap metadata; never replaced by candidates. Presence additions/removals use non-null synthetic field token `__presence__`. |
| `SCHEDULE_AMENDMENT_CANDIDATE` | DV-35 | Unique eligible removal/addition pair for one DV-34, requiring every typed signature component `(SS-04, SS-06, SS-10, SS-11)` and both inclusive range bounds SS-08/SS-09 to be non-null/valid, with overlapping ranges; `CANDIDATE_UNIQUE/MEDIUM` plus all evidence. Missing candidate inputs retain exact add/remove and explicit invalid/unpaired evidence. |
| `SCHEDULE_AMENDMENT_GROUP` | DV-36 | Ambiguous compatibility component within DV-34; typed signature plus sorted exact removed/added schedule keys; `AMBIGUOUS_CANDIDATE_GROUP/LOW` and no chosen pair. |
| `SCHEDULE_AMENDMENT_GROUP_MEMBER` | DV-37 | Every removed/added SS-01 member and side. Unpaired identity is `(DV-34, side, SS-01)` with explicit `UNPAIRED_REMOVAL|UNPAIRED_ADDITION`. |
| `PASSENGER_FLIGHT_CANONICAL` | typed `(marketing carrier, flight number, planned origin, planned destination, operating date)` | Historical-over-forward union, source precedence, both source lineages, typed normalized hash, plan fields only. |
| `PASSENGER_SOURCE_LINEAGE` | `(DV-20, source_system, DV-46 source_row_token)` | Every contributing PF/PH observation, including non-selected overlap/duplicate evidence, its DV-43 hash, and DV-21 precedence. |
| `PASSENGER_FLIGHT_INVALID` | `(source_system, stable_source_row_id)` | Missing canonical-key components and reason; stable source row ID is required for this audit identity. |
| `PASSENGER_SOURCE_QUARANTINE` | DV-44 | Missing canonical-key component plus null stable source row ID; raw typed hash, reason, and occurrence count, with no passenger or invalid-observation identity guessed. |
| `FULFILLMENT_EXACT` | DV-39 | In this reduced contract PH-01 and AF-01 share the historical-flight-ID domain. Each non-null PH-01 lineage token equal to AF-01 may link after operating-date and resolved-carrier sanity checks. Multiple historical lineage rows coalescing to one DV-20 may therefore confirm one passenger service to many actual legs. Without this equality, only candidate evidence is permitted; PF has no exact link field. |
| `FULFILLMENT_CANDIDATE` | DV-40 | Compatible resolved carrier, DV-38 flight number, operating date, and ordered endpoint/stopover evidence. An actual leg with exactly one compatible PassengerFlight is `HEURISTIC_CANDIDATE`; many actual legs may independently point to the same passenger service. It is never exact. |
| `FULFILLMENT_AMBIGUOUS_GROUP` | DV-41 with DV-42 members | A many-member connected component of the bipartite actual/passenger compatibility graph; no chosen link. Unmatched actual/passenger observations retain a deterministic source/business identity plus reason. |
| `AIRCRAFT_FLIGHT` | AF-01 | AF-01 through AF-20 as actual facts, normalized flags, optional exact aircraft/airport/airline links, resolution statuses, and raw codes. |
| `ROTATION_LINK_VALIDATION` | `(AF-01, target_token)` where `target_token = AF-20` or literal `NO_TARGET` | Link validity, terminal/anomaly class, selected local date, continuity/time evidence; actual endpoints/times only. Null next link is represented as a terminal fact without a nullable identity. |

An AM-08 finite bound earlier than DV-01, or an otherwise eligible AH event on/after finite AM-08,
is a hard temporal-integrity failure for named golden fixtures and a quarantined quality issue for
non-golden filler. Per-dimension DV-33 as-of status is exactly `OUTSIDE_EXISTENCE` before DV-01 or
on/after DV-02, `NO_RECORDED_STATE` inside existence before a first assignment, `UNKNOWN_STATE` during an
explicit null/unresolved daily gap, or `OK` for an exact resolved assignment. A composite may expose
resolved dimensions alongside their statuses but cannot report a complete reconstruction unless all
requested dimensions are `OK`.

Every null-to-value and value-to-null watched transition remains an audit assignment. A null final
observation for a dimension/day opens a date-visible `UNKNOWN_STATE` interval; a same-day intraday
null followed by a resolvable final observation remains auditable but does not invent a daily gap.

DV-38 trims AF-05, accepts ASCII digits only, and casts to NUMBER(38,0); all other forms preserve the
raw AF-05, emit `INVALID_FLIGHT_NUMBER`, and are ineligible for exact or heuristic matching. The
fulfillment compatibility graph requires: exact resolved carrier-role agreement (marketing-to-
marketing or operating-to-operating), DV-38 equal to PF-04/PH-07, AF-06 equal to PF-05/PH-04, and
actual endpoints that occupy a valid consecutive leg in the ordered planned station sequence
`origin, intermediate stops, destination`. The stop list is parsed from the contracted source order;
it is not sorted. An AircraftFlight with exactly one compatible PassengerFlight is a unique
heuristic candidate; multiple actual legs may independently have that same unique passenger
candidate, preserving the one-to-many stopover shape. A connected component in which any actual
leg has multiple compatible passenger candidates is DV-41 ambiguous with all DV-42 members and no
chosen link.

Schedule knowledge versioning is partitioned by SS-01, never route. Therefore one `Route` may link
to many concurrently open `RouteState` rows. A repeated unchanged eligible observation contributes
lineage but does not mint a state. A proven absence closes presence; later return opens a new segment
and is labeled `REAPPEARANCE`, even if content repeats.

Under D-0006, exact additions/removals and key-preserving modifications never merge with
key-changing candidate evidence. Capacity and route frequency require both `knowledge_date` and `operating_date`, plus
`carrier_role = marketing|operating`. Marketing counts distinct eligible schedule states under the
marketing role. Operating/physical mode counts only an unambiguous base representative where the
marketing and operating carrier resolve to the same airline and the row is not codeshare. A
codeshare-only service is `UNRESOLVED_PHYSICAL_SERVICE` and excluded rather than guessed. Cabin
reconciliation retains raw SS-30 through SS-34; premium economy is a subset of economy, so the
exclusive economy bucket is `economy - premium`, with negative/null/inconsistent inputs flagged and
excluded from an evidence-backed reconciled total.

## Multiplicity and integrity gates

| Link/fact | Allowed cardinality | Enforcement before functional modeling |
|---|---|---|
| Aircraft master to Aircraft | one raw eligible row per AM-01 | Duplicate AM-01 is a hard source gate failure. |
| Aircraft to audit assignments | one-to-many | Association concept; never a functional property. |
| Aircraft/dimension/date to daily assignment | zero-or-one final relevant observation | Deterministic final-order selection; duplicate winner is a hard failure. |
| Configuration to type/engine definition | zero-or-one exact target per dimension | Prove key/definition FD; otherwise unresolved/ambiguous evidence. |
| Route to route states | one-to-many, including many concurrent open | Association concept; one-open-per-route constraint is prohibited. |
| Route state to marketing airline | zero-or-one exact resolved target | Raw code/status retained if not exact. |
| Route state to operating airline | zero-or-one exact resolved target | Separate role; raw code/status retained if not exact. |
| Route endpoints to airports | zero-or-one exact target per role | Origin/destination roles are labeled; raw codes remain. |
| Passenger flight to actual flight | zero-to-many confirmed legs | Optional association; no totality or one-to-one assumption. |
| Actual flight to passenger flight | zero-or-one confirmed plan in v1 | Competing matches remain candidates/groups, not exact. |
| Actual flight to next actual flight | zero-or-one raw reference | Accepted rotation link only after validation; anomalies retained. |
| Raw code to reference identity | zero/one/many candidates | Only cardinality one with `EXACT` status creates concept link. |

## Explicit limitations and omissions

- The exact mixed-engine set is not supplied. Only one reported engine type, count, and a
  multiple-types flag are represented; completeness is false when multiple types are indicated.
- Under D-0005, master APU, dimension, and weight copies AM-11 through AM-14 are current-only and prohibited from
  historical reconstruction. Historical AH-28 through AH-31 own historical claims.
- Ownership, operator/manager/financing chains, organization state, separate storage-location
  concepts, airport/airline state, connected routes, connection/MCT rules, and passenger itineraries
  are out of scope.
- Key-changing schedule amendments are candidates, ambiguous groups, or unpaired facts—not exact
  modifications. Non-overlapping range shifts are a known conservative false negative.
- A stable physical-service group is absent. Operating capacity may visibly undercount
  codeshare-only services rather than double-count them.
- UTC `TIME` without an explicit offset/date conversion or expanded timestamp remains
  `UNRESOLVED_UTC_DATE`.
- Fulfillment is partial. Heuristic evidence never becomes confirmed fulfillment.
- Rotation uses validated `next_flight_id` self-reference as the supported baseline. General graph
  path enumeration is optional and not required for parity.
- Synthetic fixtures demonstrate functional representative shape only, not production scale,
  performance, cost, security, or universal replacement.

## Downstream hard gates

`DATA-01` must assign concrete synthetic row IDs/dates to every NF fixture. `DATA-03` must prove
types, key uniqueness, resolution cardinalities, completeness, and change tracking. `DATA-04` must
prove all canonical derivations and SQL oracles without pre-answering the RAI semantics. `MODEL-01`
may use a functional Property only after the multiplicity gate above passes; otherwise it uses an
association/Relationship and preserves all values. Frozen expected answers may not be altered to
hide a contract mismatch.
