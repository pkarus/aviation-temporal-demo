# SPEC-02 attribute authority matrix

## Contract rule

Every reduced field in `SOURCE_CONTRACT.md` appears exactly once below and has exactly one semantic
owner and one temporal treatment. A source may be joinable without being authoritative. When the
same business label appears in several inputs, this matrix decides which value can answer which
question. No downstream task may use a current/master or actual descriptive copy to overwrite the
authoritative historical or planned value.

Treatment vocabulary:

| Treatment | Meaning |
|---|---|
| `IDENTITY` | Stable identity component; never versioned by another date. |
| `CURRENT_FACT` | Current/master source fact with lineage; no historical claim. |
| `CURRENT_ONLY` | Potentially mutable master copy explicitly barred from historical as-of use. |
| `EXISTENCE_BOUND` | Aircraft existence lower/upper bound, separate from assignments. |
| `ELIGIBILITY` | Filter/quality input; not modeled as business history. |
| `EVENT_FACT` | Ordered source observation/provenance; no calendar validity interval. |
| `AUDIT_ORDER` | Deterministic audit-order component; no invented timestamp. |
| `VERSIONED_STATE` | Watched input to independent `aircraft_state` assignment. |
| `VERSIONED_TYPE` | Watched input/reference to independent `aircraft_type` assignment. |
| `VERSIONED_ENGINE` | Watched input/reference to independent `engine_type` assignment. |
| `VERSIONED_STATUS` | Watched input to independent `aircraft_status` assignment. |
| `DEFINITION` | Reference definition keyed by a stable identity; assignment is separate. |
| `VERSIONED_CONFIGURATION` | One event configuration reference whose type and engine outcomes are versioned independently. |
| `TYPE_DEFINITION` | Reference attribute of an aircraft-type definition. |
| `TYPE_DEFINITION_IDENTITY` | Stable aircraft-type definition identity. |
| `ENGINE_DEFINITION` | Reference attribute of an engine-type definition. |
| `ENGINE_DEFINITION_IDENTITY` | Stable engine-type definition identity. |
| `ENGINE_ASSIGNMENT_ATTRIBUTE` | Configuration-sourced payload on an engine assignment, not a functional engine-type attribute. |
| `KNOWLEDGE_OBSERVATION` | Snapshot knowledge date controlling segment inference. |
| `KNOWLEDGE_VERSIONED_CONTENT` | Null-safe watched content of a schedule knowledge version. |
| `OPERATING_BOUND` | Inclusive schedule operating-date bound, evaluated separately from knowledge. |
| `OPERATING_VERSIONED_CONTENT` | Inclusive operating bound that is also null-safe watched schedule content. |
| `SNAPSHOT_CONTROL` | Explicit expected/present/complete eligibility evidence. |
| `PLAN_FACT` | Passenger/schedule-side planned fact; never actual outcome. |
| `PLAN_IDENTITY` | Canonical passenger-flight identity component that is also a planned fact. |
| `SOURCE_OBSERVATION_IDENTITY` | Stable identity of a raw source observation, distinct from the business concept. |
| `ACTUAL_FACT` | Actual-leg fact; never plan repair or historical aircraft authority. |
| `ACTUAL_REFERENCE` | Actual-leg reference to another concept; exact only after identity resolution. |
| `ACTUAL_DESCRIPTION` | Actual-source descriptive copy used only for comparison/lineage. |
| `ACTUAL_SELF_REFERENCE` | Raw actual-leg self-reference requiring validation before traversal. |
| `REFERENCE_IDENTITY` | Airport/airline identity or current description used by resolution. |
| `REFERENCE_CODE` | Airport/airline code used to enumerate resolution candidates. |
| `REFERENCE_DESCRIPTION` | Current identity description; not historical state. |
| `REFERENCE_LINEAGE` | Effective/current/ambiguity evidence; identity-only in v1. |
| `SOURCE_LINEAGE` | Provenance/de-duplication evidence, not business validity. |
| `SYNTHETIC_DERIVATION` | Deterministic modeled field derived under a named contract rule. |

## Aircraft master fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| AM-01 | `aircraft_id` | Aircraft master | `IDENTITY` | no | All UC1 and rotation enrichment. |
| AM-02 | `aircraft_serial_number` | Aircraft master | `CURRENT_FACT` | no | Identity description/lineage. |
| AM-03 | `aircraft_line_number` | Aircraft master | `CURRENT_FACT` | no | Identity description/lineage. |
| AM-04 | `aircraft_order_date` | Aircraft master | `CURRENT_FACT` | no | Sentinel/milestone evidence. |
| AM-05 | `aircraft_build_date` | Aircraft master | `CURRENT_FACT` | no | Sentinel/milestone evidence. |
| AM-06 | `aircraft_delivery_date` | Aircraft master | `CURRENT_FACT` | no | Sentinel/milestone evidence. |
| AM-07 | `aircraft_start_of_life_date` | Aircraft master | `EXISTENCE_BOUND` | no | Before-existence tests. |
| AM-08 | `aircraft_end_of_life_date` | Aircraft master | `EXISTENCE_BOUND` | no | Exclusive EOL boundary. |
| AM-09 | `aircraft_build_airport_code_iata` | Aircraft master | `CURRENT_FACT` | no | Original-build location only. |
| AM-10 | `original_delivery_operator` | Aircraft master | `CURRENT_FACT` | no | Original-delivery fact only. |
| AM-11 | `apu_type` | Aircraft master | `CURRENT_ONLY` | no | Proves no backward projection. |
| AM-12 | `aircraft_width_m` | Aircraft master | `CURRENT_ONLY` | no | Proves no backward projection. |
| AM-13 | `operating_maximum_takeoff_weight_lb` | Aircraft master | `CURRENT_ONLY` | no | Proves no backward projection. |
| AM-14 | `certified_maximum_takeoff_weight_lb` | Aircraft master | `CURRENT_ONLY` | no | Proves no backward projection. |
| AM-15 | `not_for_use` | Aircraft master | `ELIGIBILITY` | no | Source eligibility. |
| AM-16 | `aircraft_roll_out_date` | Aircraft master | `CURRENT_FACT` | no | Sentinel/milestone evidence. |
| AM-17 | `aircraft_first_flight_date` | Aircraft master | `CURRENT_FACT` | no | Sentinel/milestone evidence. |
| AM-18 | `aircraft_build_airport` | Aircraft master | `CURRENT_FACT` | no | Original-build location description. |
| AM-19 | `original_delivery_operator_category` | Aircraft master | `CURRENT_FACT` | no | Original-delivery classification. |

## Aircraft event fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| AH-01 | `aircraft_history_id` | Aircraft history | `IDENTITY` | no | Stable event/assignment identity. |
| AH-02 | `aircraft_id` | Aircraft history | `EVENT_FACT` | no | Event-to-aircraft reference. |
| AH-03 | `row_sequence_number` | Aircraft history | `AUDIT_ORDER` | no | Primary same-day ordering. |
| AH-04 | `event_sequence_number` | Aircraft history | `AUDIT_ORDER` | no | Deterministic fallback order. |
| AH-05 | `start_event_date` | Aircraft history | `EVENT_FACT` | no | Assignment opening/date-visible projection. |
| AH-06 | `end_event_date` | Aircraft history | `SOURCE_LINEAGE` | no | Disagreement quality test only. |
| AH-07 | `is_current` | Aircraft history | `SOURCE_LINEAGE` | no | Diagnostic, never interval authority. |
| AH-08 | `start_event` | Aircraft history | `EVENT_FACT` | no | Status-assignment provenance. |
| AH-09 | `start_aircraft_status` | Aircraft history | `VERSIONED_STATUS` | yes | Status history/reversion. |
| AH-10 | `end_event` | Aircraft history | `SOURCE_LINEAGE` | no | Event provenance only. |
| AH-11 | `end_aircraft_status` | Aircraft history | `SOURCE_LINEAGE` | no | Provenance, not next-state authority. |
| AH-12 | `event_source` | Aircraft history | `EVENT_FACT` | no | Status provenance. |
| AH-13 | `aircraft_configuration_id` | Aircraft history | `VERSIONED_CONFIGURATION` | resolved outcome only, independently | Type/engine resolution and gaps; raw ID change alone is not a watched business delta. |
| AH-14 | `aircraft_code_iata` | Aircraft history | `VERSIONED_TYPE` | yes | Event-observed type association. |
| AH-15 | `aircraft_code_icao` | Aircraft history | `VERSIONED_TYPE` | yes | Event-observed type association. |
| AH-16 | `aircraft_value_sub_series` | Aircraft history | `VERSIONED_TYPE` | yes | Event-observed type association. |
| AH-17 | `aircraft_registration_number` | Aircraft history | `VERSIONED_STATE` | yes | Aircraft as-of registration. |
| AH-18 | `aircraft_transponder_code` | Aircraft history | `VERSIONED_STATE` | yes | Independent state reconstruction. |
| AH-19 | `aircraft_registration_country_code_iso` | Aircraft history | `VERSIONED_STATE` | yes | Independent state reconstruction. |
| AH-20 | `aircraft_registration_region` | Aircraft history | `VERSIONED_STATE` | yes | Independent state reconstruction. |
| AH-21 | `aircraft_cargo` | Aircraft history | `VERSIONED_STATE` | yes | Mutable aircraft state. |
| AH-22 | `storage_location` | Aircraft history | `VERSIONED_STATE` | yes | Mutable state; no storage node in v1. |
| AH-23 | `storage_airport_code_iata` | Aircraft history | `VERSIONED_STATE` | yes | Raw/resolved state evidence. |
| AH-24 | `base_airport` | Aircraft history | `VERSIONED_STATE` | yes | Aircraft as-of base. |
| AH-25 | `base_airport_code_iata` | Aircraft history | `VERSIONED_STATE` | yes | Aircraft as-of base resolution. |
| AH-26 | `base_city` | Aircraft history | `VERSIONED_STATE` | yes | Mutable base state. |
| AH-27 | `base_country` | Aircraft history | `VERSIONED_STATE` | yes | Mutable base state. |
| AH-28 | `apu_type` | Aircraft history | `VERSIONED_STATE` | yes | Historical authority over AM-11. |
| AH-29 | `aircraft_width_m` | Aircraft history | `VERSIONED_STATE` | yes | Historical authority over AM-12. |
| AH-30 | `operating_maximum_takeoff_weight_lb` | Aircraft history | `VERSIONED_STATE` | yes | Historical authority over AM-13. |
| AH-31 | `certified_maximum_takeoff_weight_lb` | Aircraft history | `VERSIONED_STATE` | yes | Historical authority over AM-14. |
| AH-32 | `not_for_use` | Aircraft history | `ELIGIBILITY` | no | Event quality/eligibility. |
| AH-33 | `publish_date` | Aircraft history | `SOURCE_LINEAGE` | no | Lineage, never assignment validity. |

AH-13 participates in two independent dimension watchers, but it still has one semantic owner and
one compound temporal treatment: it is the event's configuration reference whose type and engine
resolution results are compared independently. A partial configuration resolution may therefore
change one dimension without forcing the other to align.

## Configuration reference fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| AC-01 | `aircraft_configuration_id` | Configuration reference | `IDENTITY` | no | Exact history-to-configuration resolution. |
| AC-02 | `aircraft_family` | Configuration reference | `TYPE_DEFINITION` | via resolved assignment | Type history. |
| AC-03 | `aircraft_type` | Configuration reference | `TYPE_DEFINITION` | via resolved assignment | Type reconstruction. |
| AC-04 | `aircraft_series` | Configuration reference | `TYPE_DEFINITION` | via resolved assignment | Type hierarchy. |
| AC-05 | `aircraft_subseries` | Configuration reference | `TYPE_DEFINITION_IDENTITY` | via resolved assignment | Type target/parity key. |
| AC-06 | `aircraft_manufacturer` | Configuration reference | `TYPE_DEFINITION` | via resolved assignment | Type hierarchy. |
| AC-07 | `aircraft_design_class` | Configuration reference | `TYPE_DEFINITION` | via resolved assignment | Type hierarchy/lineage. |
| AC-08 | `engine_count` | Configuration reference | `ENGINE_ASSIGNMENT_ATTRIBUTE` | via resolved assignment | Engine history/limitations. |
| AC-09 | `has_multiple_engine_types` | Configuration reference | `ENGINE_ASSIGNMENT_ATTRIBUTE` | via resolved assignment | Mixed-engine incompleteness. |
| AC-10 | `engine_manufacturer` | Configuration reference | `ENGINE_DEFINITION` | via resolved assignment | Engine hierarchy. |
| AC-11 | `engine_family` | Configuration reference | `ENGINE_DEFINITION` | via resolved assignment | Engine hierarchy. |
| AC-12 | `engine_type` | Configuration reference | `ENGINE_DEFINITION` | via resolved assignment | Engine reconstruction. |
| AC-13 | `engine_series` | Configuration reference | `ENGINE_DEFINITION` | via resolved assignment | Engine hierarchy. |
| AC-14 | `engine_subseries` | Configuration reference | `ENGINE_DEFINITION_IDENTITY` | via resolved assignment | Engine target/parity key. |
| AC-15 | `engine_propulsion_type` | Configuration reference | `ENGINE_DEFINITION` | via resolved assignment | Engine description. |
| AC-16 | `publish_date` | Configuration reference | `SOURCE_LINEAGE` | no | Definition lineage, not assignment validity. |

## Schedule snapshot fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| SS-01 | `schedule_key` | Schedule snapshot | `IDENTITY` | partition key | Exact schedule identity/version partition. |
| SS-02 | `schedule_key_readable` | Schedule snapshot | `SOURCE_LINEAGE` | no | Trace/debug only. |
| SS-03 | `publish_date` | Schedule snapshot | `KNOWLEDGE_OBSERVATION` | segment opening/closure evidence | Knowledge clock. |
| SS-04 | `marketing_carrier_internal` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Marketing role/candidate signature. |
| SS-05 | `operating_carrier_internal` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating role/codeshare. |
| SS-06 | `flight_number` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Exact/candidate changes. |
| SS-07 | `service_type_iata` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Schedule content. |
| SS-08 | `effective_date` | Schedule snapshot | `OPERATING_VERSIONED_CONTENT` | yes | Operating clock/key shift. |
| SS-09 | `discontinue_date` | Schedule snapshot | `OPERATING_VERSIONED_CONTENT` | yes | Operating clock/key shift. |
| SS-10 | `departure_station_code_iata` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Route origin/candidate signature. |
| SS-11 | `arrival_station_code_iata` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Route destination/candidate signature. |
| SS-12 | `departure_terminal` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Change detail. |
| SS-13 | `arrival_terminal` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Change detail. |
| SS-14 | `is_operating_monday` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating predicate. |
| SS-15 | `is_operating_tuesday` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating predicate. |
| SS-16 | `is_operating_wednesday` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating predicate. |
| SS-17 | `is_operating_thursday` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating predicate. |
| SS-18 | `is_operating_friday` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating predicate. |
| SS-19 | `is_operating_saturday` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating predicate. |
| SS-20 | `is_operating_sunday` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Operating predicate. |
| SS-21 | `days_pattern` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Weekday validation/change detail. |
| SS-22 | `weekly_frequency` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Rank/change/frequency. |
| SS-23 | `passenger_departure_utc_time` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Recurring UTC evidence. |
| SS-24 | `passenger_arrival_utc_time` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Recurring UTC evidence. |
| SS-25 | `passenger_departure_local_time` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Local instance construction. |
| SS-26 | `passenger_arrival_local_time` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Local instance construction. |
| SS-27 | `arrival_day_indicator` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Explicit day crossing. |
| SS-28 | `scheduled_block_minutes` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Change detail. |
| SS-29 | `equipment_subtype_code_iata` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Equipment modification. |
| SS-30 | `total_seats` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Capacity/rank/change. |
| SS-31 | `first_class_seats` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Cabin capacity. |
| SS-32 | `business_class_seats` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Cabin capacity. |
| SS-33 | `premium_economy_seats` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Economy-subset reconciliation. |
| SS-34 | `economy_class_seats` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Economy-subset reconciliation. |
| SS-35 | `is_codeshare` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Physical representative rule. |
| SS-36 | `codeshare_carrier_internal` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Codeshare evidence. |
| SS-37 | `number_of_intermediate_stops` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Itinerary/fulfillment evidence. |
| SS-38 | `intermediate_stop_station_codes_iata` | Schedule snapshot | `KNOWLEDGE_VERSIONED_CONTENT` | yes | Itinerary/fulfillment evidence. |
| SS-39 | `itinerary_variation_identifier` | Schedule snapshot | `SOURCE_LINEAGE` | no | Deterministic variant rank only. |
| SS-40 | `normalized_row_hash` | Synthetic normalizer over schedule snapshot | `SOURCE_LINEAGE` | no | Final tie-break/idempotency. |

## Snapshot control fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| SC-01 | `expected_publish_date` | Snapshot calendar | `IDENTITY` | no | Expected endpoint/calendar grain. |
| SC-02 | `is_present` | Snapshot calendar | `SNAPSHOT_CONTROL` | eligibility | Missing snapshot behavior. |
| SC-03 | `is_complete` | Snapshot calendar | `SNAPSHOT_CONTROL` | eligibility | Incomplete snapshot behavior. |
| SC-04 | `source_lineage_id` | Snapshot calendar | `SOURCE_LINEAGE` | no | Control-batch provenance. |
| SC-05 | `observed_row_count` | Snapshot calendar | `SNAPSHOT_CONTROL` | no | Validation evidence, not inferred completeness. |
| SC-06 | `validation_status` | Snapshot calendar | `SNAPSHOT_CONTROL` | no | Named completeness evidence. |

## Passenger forward fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| PF-01 | `forward_source_row_id` | Forward passenger source | `SOURCE_OBSERVATION_IDENTITY` | union de-dup | Lineage/quarantine. |
| PF-02 | `marketing_carrier_internal` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Passenger key/marketing role. |
| PF-03 | `operating_carrier_internal` | Typed passenger union | `PLAN_FACT` | union de-dup | Operating role. |
| PF-04 | `flight_number` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Passenger key/matching. |
| PF-05 | `operating_date` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Passenger key/matching. |
| PF-06 | `publish_date` | Forward passenger source | `SOURCE_LINEAGE` | union precedence/de-dup | Latest forward evidence. |
| PF-07 | `service_type_iata` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned service. |
| PF-08 | `departure_station_code_iata` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Planned origin. |
| PF-09 | `arrival_station_code_iata` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Planned destination. |
| PF-10 | `passenger_departure_time_local` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned local departure. |
| PF-11 | `passenger_arrival_time_local` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned local arrival. |
| PF-12 | `passenger_departure_time_utc` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned UTC departure. |
| PF-13 | `passenger_arrival_time_utc` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned UTC arrival. |
| PF-14 | `arrival_day_indicator` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned day crossing. |
| PF-15 | `equipment_subtype_code_iata` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned equipment. |
| PF-16 | `total_seats` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned capacity. |
| PF-17 | `is_codeshare` | Typed passenger union | `PLAN_FACT` | union de-dup | Plan carrier evidence. |
| PF-18 | `number_of_intermediate_stops` | Typed passenger union | `PLAN_FACT` | union de-dup | Stopover matching. |
| PF-19 | `intermediate_stop_station_codes_iata` | Typed passenger union | `PLAN_FACT` | union de-dup | Stopover matching. |

## Passenger historical fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| PH-01 | `historical_source_row_id` | Historical passenger source | `SOURCE_OBSERVATION_IDENTITY` | union de-dup | Shared historical-flight ID domain with AF-01; lineage/direct fulfillment. |
| PH-02 | `schedule_key` | Historical passenger source | `PLAN_FACT` | union de-dup | Exact schedule link when available. |
| PH-03 | `publish_date` | Historical passenger source | `SOURCE_LINEAGE` | union precedence/de-dup | Historical lineage. |
| PH-04 | `operating_date` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Passenger key/matching. |
| PH-05 | `marketing_carrier_internal` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Passenger key/marketing role. |
| PH-06 | `operating_carrier_internal` | Typed passenger union | `PLAN_FACT` | union de-dup | Operating role. |
| PH-07 | `flight_number` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Passenger key/matching. |
| PH-08 | `service_type_iata` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned service. |
| PH-09 | `effective_date` | Historical passenger source | `SOURCE_LINEAGE` | union de-dup | Historical schedule lineage. |
| PH-10 | `departure_station_code_iata` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Planned origin. |
| PH-11 | `arrival_station_code_iata` | Typed passenger union | `PLAN_IDENTITY` | union de-dup | Planned destination. |
| PH-12 | `passenger_departure_local_time` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned local departure. |
| PH-13 | `passenger_arrival_local_time` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned local arrival. |
| PH-14 | `passenger_departure_utc_time` | Typed passenger union | `PLAN_FACT` | union de-dup | UTC time-only evidence. |
| PH-15 | `passenger_arrival_utc_time` | Typed passenger union | `PLAN_FACT` | union de-dup | UTC time-only evidence. |
| PH-16 | `departure_utc_offset_minutes` | Typed passenger union | `PLAN_FACT` | union de-dup | Explicit UTC conversion evidence. |
| PH-17 | `arrival_utc_offset_minutes` | Typed passenger union | `PLAN_FACT` | union de-dup | Explicit UTC conversion evidence. |
| PH-18 | `arrival_day_indicator` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned day crossing. |
| PH-19 | `equipment_subtype_code_iata` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned equipment. |
| PH-20 | `total_seats` | Typed passenger union | `PLAN_FACT` | union de-dup | Planned capacity. |
| PH-21 | `is_codeshare` | Typed passenger union | `PLAN_FACT` | union de-dup | Plan carrier evidence. |
| PH-22 | `number_of_intermediate_stops` | Typed passenger union | `PLAN_FACT` | union de-dup | Stopover matching. |
| PH-23 | `intermediate_stop_station_codes_iata` | Typed passenger union | `PLAN_FACT` | union de-dup | Stopover matching. |

Historical is the authoritative source on a canonical-key overlap. This precedence does not make
its missing fields authoritative values: a forward-only historical-null field stays null and both
lineages remain visible.

## Actual-flight fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| AF-01 | `flight_id` | Actual-flight source | `IDENTITY` | no | Actual leg/shared historical-flight ID domain with PH-01. |
| AF-02 | `aircraft_id` | Actual-flight source | `ACTUAL_REFERENCE` | no | Rotation selection/enrichment. |
| AF-03 | `operating_carrier_code` | Actual-flight source | `ACTUAL_FACT` | no | Fulfillment sanity/resolution. |
| AF-04 | `marketing_carrier_code` | Actual-flight source | `ACTUAL_FACT` | no | Fulfillment sanity/resolution. |
| AF-05 | `flight_number` | Actual-flight source | `ACTUAL_FACT` | no | Fulfillment evidence. |
| AF-06 | `flight_departure_date` | Actual-flight source | `ACTUAL_FACT` | no | Local selected-day/enrichment date. |
| AF-07 | `flight_departure_date_utc` | Actual-flight source | `ACTUAL_FACT` | no | UTC lineage only. |
| AF-08 | `departure_airport_code` | Actual-flight source | `ACTUAL_FACT` | no | Actual start/continuity. |
| AF-09 | `arrival_airport_code` | Actual-flight source | `ACTUAL_FACT` | no | Actual end/continuity. |
| AF-10 | `diverted_airport_code` | Actual-flight source | `ACTUAL_FACT` | no | Diversion evidence. |
| AF-11 | `is_cancelled` | Actual-flight source | `ACTUAL_FACT` | no | Strict-chain exclusion/anomaly. |
| AF-12 | `is_diverted` | Actual-flight source | `ACTUAL_FACT` | no | Plan/actual divergence. |
| AF-13 | `actual_gate_departure_time_utc` | Actual-flight source | `ACTUAL_FACT` | no | Strict ordering. |
| AF-14 | `actual_gate_arrival_time_utc` | Actual-flight source | `ACTUAL_FACT` | no | Strict continuity. |
| AF-15 | `actual_gate_departure_time_local` | Actual-flight source | `ACTUAL_FACT` | no | Actual display/lineage. |
| AF-16 | `actual_gate_arrival_time_local` | Actual-flight source | `ACTUAL_FACT` | no | Actual display/lineage. |
| AF-17 | `aircraft_type` | Actual-flight source | `ACTUAL_DESCRIPTION` | no | Discrepancy only; not as-of authority. |
| AF-18 | `aircraft_code_iata` | Actual-flight source | `ACTUAL_DESCRIPTION` | no | Discrepancy only. |
| AF-19 | `aircraft_family` | Actual-flight source | `ACTUAL_DESCRIPTION` | no | Discrepancy only. |
| AF-20 | `next_flight_id` | Actual-flight source | `ACTUAL_SELF_REFERENCE` | no | Rotation baseline/anomalies. |

## Reference fields

| Field ID | Column | Semantic owner | Temporal treatment | Change detection | Golden/fixture relevance |
|---|---|---|---|---|---|
| AP-01 | `airport_id` | Airport reference | `REFERENCE_IDENTITY` | no | Exact airport target. |
| AP-02 | `effective_start_date` | Airport reference | `REFERENCE_LINEAGE` | no | Resolution evidence. |
| AP-03 | `effective_end_date` | Airport reference | `REFERENCE_LINEAGE` | no | Resolution evidence. |
| AP-04 | `airport_code_iata` | Airport reference | `REFERENCE_CODE` | no | Code resolution. |
| AP-05 | `airport_code_icao` | Airport reference | `REFERENCE_CODE` | no | Code resolution. |
| AP-06 | `airport_name` | Airport reference | `REFERENCE_DESCRIPTION` | no | Resolved display. |
| AP-07 | `is_active` | Airport reference | `REFERENCE_LINEAGE` | no | Candidate evidence only. |
| AP-08 | `is_current` | Airport reference | `REFERENCE_LINEAGE` | no | Candidate evidence only. |
| AP-09 | `time_zone_name` | Airport reference | `REFERENCE_LINEAGE` | no | Explicit conversion evidence only. |
| AL-01 | `airline_id` | Airline reference | `REFERENCE_IDENTITY` | no | Exact airline target. |
| AL-02 | `effective_start_date` | Airline reference | `REFERENCE_LINEAGE` | no | Resolution evidence. |
| AL-03 | `effective_end_date` | Airline reference | `REFERENCE_LINEAGE` | no | Resolution evidence. |
| AL-04 | `carrier_code_iata` | Airline reference | `REFERENCE_CODE` | no | Code resolution. |
| AL-05 | `carrier_code_icao` | Airline reference | `REFERENCE_CODE` | no | Code resolution. |
| AL-06 | `carrier_short_name` | Airline reference | `REFERENCE_DESCRIPTION` | no | Resolved display. |
| AL-07 | `carrier_full_name` | Airline reference | `REFERENCE_DESCRIPTION` | no | Resolved display. |
| AL-08 | `is_iata_controlled_duplicate` | Airline reference | `REFERENCE_LINEAGE` | no | Explicit ambiguity evidence. |
| AL-09 | `is_active` | Airline reference | `REFERENCE_LINEAGE` | no | Candidate evidence only. |
| AL-10 | `is_current` | Airline reference | `REFERENCE_LINEAGE` | no | Candidate evidence only. |

Reference effective periods are retained for provenance/resolution, but Airport and Airline are
identity-only in v1. `is_current` and `is_active` never justify silently choosing one of multiple
code candidates.

## Derived modeled-field authority

Every non-source semantic field planned for the RAI model is declared here. Data-layer-only
operational diagnostics may retain contracted source fields plus a named reason, count, or batch
token, but they do not become undeclared semantic Properties. No implementation may introduce an
uncontracted semantic field without first updating this matrix and its lineage rule.

| Derived ID | Modeled field | Semantic owner | Temporal treatment | Deterministic lineage |
|---|---|---|---|---|
| DV-01 | `existence_from` | Aircraft | `SYNTHETIC_DERIVATION` existence bound | Normalized AM-07, else first eligible AH-05. |
| DV-02 | `existence_to` | Aircraft | `SYNTHETIC_DERIVATION` existence bound | Exclusive normalized AM-08, else model open sentinel. |
| DV-03 | `event_order` | Aircraft event | `SYNTHETIC_DERIVATION` audit order | Tuple AH-05/AH-03/AH-04/AH-01. |
| DV-04 | `audit_assignment_id` | Dimension audit assignment | `SYNTHETIC_DERIVATION` identity | `(dimension, AH-02, AH-05, AH-03, AH-01)`. |
| DV-05 | `daily_assignment_id` | Dimension daily assignment | `SYNTHETIC_DERIVATION` identity | `(dimension, AH-02, AH-05, AH-01)` after final-per-day selection. |
| DV-06 | `assignment_valid_from` | Dimension daily assignment | `SYNTHETIC_DERIVATION` half-open start | AH-05 of final relevant daily observation. |
| DV-07 | `assignment_valid_to` | Dimension daily assignment | `SYNTHETIC_DERIVATION` half-open end | Next distinct daily assignment date clipped to DV-02/open sentinel. |
| DV-08 | `dimension_resolution_status` | Dimension assignment | `SYNTHETIC_DERIVATION` state | Exact/null/unresolved/ambiguous result from AH watched values and AC resolution. |
| DV-09 | `mixed_engine_set_complete` | Engine assignment/definition | `SYNTHETIC_DERIVATION` limitation | False when AC-09 true; otherwise true/unknown only with valid source evidence. |
| DV-10 | `resolution_status` | Code resolution | `SYNTHETIC_DERIVATION` identity-only resolution | Zero/one/many/invalid cardinality over AP/AL candidates. |
| DV-11 | `resolution_candidate_count` | Code resolution | `SYNTHETIC_DERIVATION` lineage | Exact count of candidate IDs; candidates/method retained. |
| DV-12 | `route_id` | Route | `SYNTHETIC_DERIVATION` identity | Typed directional non-null SS-10/SS-11 raw-code pair; null component is `INVALID_ROUTE_KEY` evidence, not identity. |
| DV-13 | `route_state_key` | Route state | `SYNTHETIC_DERIVATION` identity | SS-01 plus segment-opening knowledge date. |
| DV-14 | `knowledge_valid_from` | Route state | `SYNTHETIC_DERIVATION` half-open start | Eligible SS-03 opening presence/content segment. |
| DV-15 | `knowledge_valid_to` | Route state | `SYNTHETIC_DERIVATION` half-open end | Next eligible content change/proven absence or model open sentinel. |
| DV-16 | `crosses_snapshot_gap` | Schedule comparison | `SYNTHETIC_DERIVATION` knowledge lineage | Non-adjacent calendar dates adjacent in eligible SC sequence. |
| DV-17 | `schedule_exact_change_kind` | Exact schedule change | `SYNTHETIC_DERIVATION` knowledge event | Exact key presence/content comparison only. |
| DV-18 | `amendment_candidate_class` | Amendment evidence | `SYNTHETIC_DERIVATION` candidate fact | Unique/ambiguous/unpaired eligibility under P0-07. |
| DV-19 | `amendment_confidence` | Amendment evidence | `SYNTHETIC_DERIVATION` candidate fact | MEDIUM for unique, LOW for ambiguous; never exact. |
| DV-20 | `passenger_flight_key` | Passenger flight | `SYNTHETIC_DERIVATION` identity | Typed PF-02/04/08/09/05 or PH-05/07/10/11/04. |
| DV-21 | `passenger_source_precedence` | Passenger flight | `SYNTHETIC_DERIVATION` lineage | Historical wins overlap; both lineages retained. |
| DV-22 | `passenger_key_status` | Passenger source observation | `SYNTHETIC_DERIVATION` audit state | Valid/invalid/quarantined from key and source-row identity completeness. |
| DV-23 | `fulfillment_class` | Fulfillment evidence | `SYNTHETIC_DERIVATION` association state | Exact/heuristic/ambiguous/unmatched under P0-10. |
| DV-24 | `rotation_link_status` | Rotation link validation | `SYNTHETIC_DERIVATION` actual-chain state | AF-01/02/06/08/11/13/14/20 plus DV-45 validation. |
| DV-25 | `rotation_anomaly_class` | Rotation link validation | `SYNTHETIC_DERIVATION` actual-chain state | Typed self/cycle/missing/different/day/time/continuity/diversion-conflict/cancel/missing-time reason. |
| DV-26 | `economy_excluding_premium` | Route-state capacity | `SYNTHETIC_DERIVATION` analytic fact | SS-34 minus SS-33; raw inconsistency flagged before display flooring. |
| DV-27 | `cabin_quality_status` | Route-state capacity | `SYNTHETIC_DERIVATION` analytic fact | Null/negative/mismatch/premium-over-economy checks over SS-30 through SS-34. |
| DV-28 | `physical_service_status` | Operating capacity | `SYNTHETIC_DERIVATION` analytic fact | Base representative or `UNRESOLVED_PHYSICAL_SERVICE` under D-0007. |
| DV-29 | `carrier_role` | Query execution metadata | `SYNTHETIC_DERIVATION` required parameter | Explicit `marketing|operating`; no default. |
| DV-30 | `knowledge_date` | Query execution metadata | `SYNTHETIC_DERIVATION` required parameter | Explicit half-open knowledge evaluation date. |
| DV-31 | `operating_date` | Query execution metadata | `SYNTHETIC_DERIVATION` required parameter | Explicit inclusive operating/weekday evaluation date. |
| DV-32 | `plan_actual_discrepancy` | Cross-domain enrichment | `SYNTHETIC_DERIVATION` comparison fact | Passenger plan versus AF actual, or AF-17/18/19 versus independent as-of aircraft history. |
| DV-33 | `dimension_query_status` | Dimension daily assignment/query | `SYNTHETIC_DERIVATION` as-of state | Exactly `OUTSIDE_EXISTENCE`, `NO_RECORDED_STATE`, `UNKNOWN_STATE`, or `OK` from DV-01/DV-02/DV-06/DV-07/DV-08. |
| DV-34 | `schedule_comparison_id` | Schedule comparison | `SYNTHETIC_DERIVATION` identity | SHA-256 over older and newer eligible knowledge endpoint dates. |
| DV-35 | `amendment_candidate_id` | Schedule amendment candidate | `SYNTHETIC_DERIVATION` identity | SHA-256 over DV-34, exact removed SS-01, exact added SS-01. |
| DV-36 | `amendment_group_id` | Schedule amendment group | `SYNTHETIC_DERIVATION` identity | SHA-256 over DV-34, typed candidate signature, sorted removed keys, and sorted added keys. |
| DV-37 | `amendment_group_member_id` | Schedule amendment group member | `SYNTHETIC_DERIVATION` identity | `(DV-36, side, SS-01)` with side `REMOVED|ADDED`. |
| DV-38 | `normalized_actual_flight_number` | Fulfillment matching | `SYNTHETIC_DERIVATION` matching value | Trim AF-05, require ASCII digits only, cast to NUMBER(38,0); invalid values remain raw and ineligible. |
| DV-39 | `exact_fulfillment_id` | Exact fulfillment | `SYNTHETIC_DERIVATION` identity | SHA-256 over AF-01, DV-20, and literal `EXACT` after direct-ID and sanity checks. |
| DV-40 | `fulfillment_candidate_id` | Fulfillment candidate | `SYNTHETIC_DERIVATION` identity | SHA-256 over AF-01, DV-20, and literal `HEURISTIC`. |
| DV-41 | `fulfillment_group_id` | Ambiguous fulfillment group | `SYNTHETIC_DERIVATION` identity | SHA-256 over sorted actual IDs and passenger keys in a compatibility connected component. |
| DV-42 | `fulfillment_group_member_id` | Ambiguous fulfillment member | `SYNTHETIC_DERIVATION` identity | `(DV-41, side, source identity)` with side `ACTUAL|PASSENGER`. |
| DV-43 | `typed_normalized_row_hash` | Canonical source normalization | `SYNTHETIC_DERIVATION` lineage | SHA-256 over ordered Field IDs with type tags, explicit null token, and canonical value encodings. |
| DV-44 | `quarantine_id` | Invalid source observation | `SYNTHETIC_DERIVATION` identity | SHA-256 over source object, stable source-row ID when present else DV-43, and reason code. |
| DV-45 | `actual_continuity_arrival_code` | Rotation continuity | `SYNTHETIC_DERIVATION` actual fact | AF-09 exactly; AF-10/AF-12 corroborate or emit `DIVERSION_ENDPOINT_CONFLICT` but never repair AF-09. |
| DV-46 | `source_row_token` | Canonical source lineage | `SYNTHETIC_DERIVATION` identity component | Source-system-prefixed stable raw ID where present, else source-system-prefixed DV-43; never null for a retained row. |
| DV-47 | `historical_departure_local_timestamp` | Historical passenger plan | `SYNTHETIC_DERIVATION` plan time | PH-04 operating date plus PH-12 local departure TIME. |
| DV-48 | `historical_arrival_local_timestamp` | Historical passenger plan | `SYNTHETIC_DERIVATION` plan time | PH-04 plus PH-18 day offset plus PH-13 local arrival TIME. |
| DV-49 | `historical_departure_utc_timestamp` | Historical passenger plan | `SYNTHETIC_DERIVATION` plan time | Under binding provisional D-0008, DV-47 minus PH-16 offset minutes when finite/non-null. |
| DV-50 | `historical_arrival_utc_timestamp` | Historical passenger plan | `SYNTHETIC_DERIVATION` plan time | Under binding provisional D-0008, DV-48 minus PH-17 offset minutes when finite/non-null. |
| DV-51 | `utc_date_status` | Passenger/schedule plan | `SYNTHETIC_DERIVATION` time evidence | `EXPLICIT_EXPANDED`, `OFFSET_DERIVED`, or `UNRESOLVED_UTC_DATE`; never inferred from clock ordering. |
| DV-52 | `is_cancelled_boolean` | Actual-flight source normalization | `SYNTHETIC_DERIVATION` actual fact | AF-11 integer 0=false, 1=true; null/other is `UNKNOWN_OR_INVALID` and excludes the leg from strict rotation. |
| DV-53 | `is_diverted_boolean` | Actual-flight source normalization | `SYNTHETIC_DERIVATION` actual fact | AF-12 integer 0=false, 1=true; null/other is `UNKNOWN_OR_INVALID` quality evidence and cannot override DV-45. |

## Authority conflict rules

1. AH-28 through AH-31 own historical APU/dimension/weight values; AM-11 through AM-14 are
   `CURRENT_ONLY` and may be displayed only as such.
2. AH/AC own aircraft as-of type and engine; AF-17 through AF-19 are actual-source observations and
   may only be compared, never substituted.
3. Typed passenger union fields own planned endpoints/times; AF-08 through AF-16 own actual
   endpoints/times. A diversion preserves both.
4. SS-04 and SS-05 are separate carrier roles. No generic airline owner exists.
5. SC-02/SC-03 own snapshot eligibility. Row presence or SC-05 alone cannot infer completeness.
6. Derived half-open validity owns as-of evaluation; AH-06 and source current flags are lineage.
7. Code resolution results own concept linkage. Raw codes and current flags cannot bypass
   zero/one/many cardinality proof.
