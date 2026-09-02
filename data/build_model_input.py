#!/usr/bin/env python3
"""Build and verify the canonical temporal model-input layer in PK_AVIATION_TEMPORAL.MODEL_INPUT.

Scope is pinned to connection `rai`, role RAI_DEMO_AVIATION_TEMPORAL, warehouse RAI_XS and
database PK_AVIATION_TEMPORAL.  No caller override is accepted and no object outside MODEL_INPUT
is created or altered; SOURCE and VALIDATION are read-only here.

    --plan     print the ordered DDL without connecting to Snowflake
    --apply    execute the DDL live, then annotate every column and enable change tracking
    --verify   run the multiplicity, integrity and adversarial temporal gates live
    --report   write build/task_reports/DATA-04a.json from the last --apply/--verify in this run

Semantic invariants implemented by the SQL and proven by --verify:
  * half-open intervals valid_from <= d < valid_to;
  * source sentinel 9999-12-31 (unknown future) stays distinct from model sentinel 9999-01-01;
  * aircraft event identity is (date, row sequence, source history ID), never date alone;
  * A -> B -> A stays three assignments;
  * schedule versioning partitions by SS-01, never by route, and many concurrent open RouteStates
    on one route are preserved and never collapsed;
  * marketing and operating airline roles stay separate;
  * exact and candidate/heuristic evidence stay separate and visibly labelled;
  * incomplete or absent snapshots manufacture no removals.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = Path(__file__).resolve().parent / "model_input"
REPORT_PATH = ROOT / "build" / "task_reports" / "DATA-04a.json"

CONNECTION = "rai"
ROLE = "RAI_DEMO_AVIATION_TEMPORAL"
WAREHOUSE = "RAI_XS"
DATABASE = "PK_AVIATION_TEMPORAL"
SCHEMA = "MODEL_INPUT"
BUILD_VERSION = "model-input-v1"

MODEL_OPEN_SENTINEL = "9999-01-01"
SOURCE_UNKNOWN_FUTURE = "9999-12-31"

SQL_FILES: tuple[str, ...] = (
    "00_setup.sql",
    "10_reference.sql",
    "15_passenger_source.sql",
    "20_code_resolution.sql",
    "30_aircraft.sql",
    "31_aircraft_assignments.sql",
    "40_schedule.sql",
    "41_schedule_changes.sql",
    "50_passenger.sql",
    "60_actual_flight.sql",
    "70_fulfillment.sql",
    "90_metadata.sql",
)


class GateError(RuntimeError):
    """A live gate failed. The task stays red."""


# Which source Field-ID prefixes a MODEL_INPUT table's plain source columns may resolve against,
# in priority order.  This removes the ambiguity of names such as `publish_date`, which exists as
# AC-16, AH-33, PF-06, PH-03 and SS-03.
TABLE_SOURCE_PREFIXES: dict[str, tuple[str, ...]] = {
    "AIRPORT_CURRENT": ("AP",),
    "AIRLINE_CURRENT": ("AL",),
    "AIRCRAFT_TYPE_DEFINITION": ("AC",),
    "ENGINE_TYPE_DEFINITION": ("AC",),
    "MONTH_END_CALENDAR": (),
    "PASSENGER_SOURCE_OBSERVATION": ("PH", "PF"),
    "CODE_RESOLUTION_CODE_CANDIDATE": (),
    "CODE_RESOLUTION_CODE": (),
    "CODE_RESOLUTION_INPUT": (),
    "CODE_RESOLUTION": (),
    "CODE_RESOLUTION_CANDIDATE": (),
    "AIRCRAFT_ELIGIBLE": ("AM",),
    "AIRCRAFT_EVENT_ELIGIBLE": ("AH", "AC"),
    "AIRCRAFT_EVENT_QUARANTINE": ("AH",),
    "AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT": ("AH", "AC"),
    "AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT": ("AH", "AC"),
    "SCHEDULE_CANONICAL_OBSERVATION": ("SS", "SC"),
    "ROUTE": ("SS",),
    "ROUTE_STATE": ("SS",),
    "ROUTE_STATE_LINEAGE": ("SS",),
    "SCHEDULE_COMPARISON": ("SS", "SC"),
    "SCHEDULE_EXACT_CHANGE": ("SS",),
    "SCHEDULE_AMENDMENT_SIDE": ("SS",),
    "SCHEDULE_AMENDMENT_CANDIDATE": ("SS",),
    "SCHEDULE_AMENDMENT_GROUP": ("SS",),
    "SCHEDULE_AMENDMENT_GROUP_MEMBER": ("SS",),
    "PASSENGER_FLIGHT_CANONICAL": ("PH", "PF"),
    "PASSENGER_SOURCE_LINEAGE": ("PH", "PF"),
    "PASSENGER_FLIGHT_INVALID": ("PH", "PF"),
    "PASSENGER_SOURCE_QUARANTINE": ("PH", "PF"),
    "AIRCRAFT_FLIGHT": ("AF",),
    "ROTATION_LINK_VALIDATION": ("AF",),
    "FULFILLMENT_EXACT": ("AF",),
    "PASSENGER_PLANNED_LEG": ("PH", "PF"),
    "FULFILLMENT_COMPATIBILITY": ("AF",),
    "FULFILLMENT_CANDIDATE": ("AF",),
    "FULFILLMENT_AMBIGUOUS_GROUP": (),
}

# Contract objects that the SOURCE_CONTRACT.md canonical-object table names, mapped to the
# MODEL_INPUT table that implements them.
CONTRACT_OBJECTS: dict[str, str] = {
    "AIRCRAFT_ELIGIBLE": "AIRCRAFT_ELIGIBLE",
    "AIRCRAFT_EVENT_ELIGIBLE": "AIRCRAFT_EVENT_ELIGIBLE",
    "AIRCRAFT_EVENT_QUARANTINE": "AIRCRAFT_EVENT_QUARANTINE",
    "AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT": "AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT",
    "AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT": "AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT",
    "AIRCRAFT_TYPE_DEFINITION": "AIRCRAFT_TYPE_DEFINITION",
    "ENGINE_TYPE_DEFINITION": "ENGINE_TYPE_DEFINITION",
    "CODE_RESOLUTION": "CODE_RESOLUTION",
    "CODE_RESOLUTION_CANDIDATE": "CODE_RESOLUTION_CANDIDATE",
    "SCHEDULE_CANONICAL_OBSERVATION": "SCHEDULE_CANONICAL_OBSERVATION",
    "ROUTE": "ROUTE",
    "ROUTE_STATE": "ROUTE_STATE",
    "ROUTE_STATE_LINEAGE": "ROUTE_STATE_LINEAGE",
    "SCHEDULE_EXACT_CHANGE": "SCHEDULE_EXACT_CHANGE",
    "SCHEDULE_AMENDMENT_CANDIDATE": "SCHEDULE_AMENDMENT_CANDIDATE",
    "SCHEDULE_AMENDMENT_GROUP": "SCHEDULE_AMENDMENT_GROUP",
    "SCHEDULE_AMENDMENT_GROUP_MEMBER": "SCHEDULE_AMENDMENT_GROUP_MEMBER",
    "PASSENGER_FLIGHT_CANONICAL": "PASSENGER_FLIGHT_CANONICAL",
    "PASSENGER_SOURCE_LINEAGE": "PASSENGER_SOURCE_LINEAGE",
    "PASSENGER_FLIGHT_INVALID": "PASSENGER_FLIGHT_INVALID",
    "PASSENGER_SOURCE_QUARANTINE": "PASSENGER_SOURCE_QUARANTINE",
    "FULFILLMENT_EXACT": "FULFILLMENT_EXACT",
    "FULFILLMENT_CANDIDATE": "FULFILLMENT_CANDIDATE",
    "FULFILLMENT_AMBIGUOUS_GROUP": "FULFILLMENT_AMBIGUOUS_GROUP",
    "AIRCRAFT_FLIGHT": "AIRCRAFT_FLIGHT",
    "ROTATION_LINK_VALIDATION": "ROTATION_LINK_VALIDATION",
}

# Objects beyond the contract table, each with the authority that requires them.
ADDITIONAL_OBJECTS: dict[str, str] = {
    "AIRPORT_CURRENT": "ONTOLOGY_DESIGN.md G-03: v1 Airport identity is AP-01 while the source grain is (AP-01, AP-02).",
    "AIRLINE_CURRENT": "ONTOLOGY_DESIGN.md G-04: v1 Airline identity is AL-01 while the source grain is (AL-01, AL-02).",
    "MONTH_END_CALENDAR": "ONTOLOGY_DESIGN.md section 5.5: bounded month-end date entity for the Q03 as-of rule.",
    "SCHEDULE_COMPARISON": "ONTOLOGY_DESIGN.md section 1.2: DV-34 ScheduleComparison is a Concept, not a per-invocation parameter.",
    "PASSENGER_SOURCE_OBSERVATION": "Declared derivation: typed PF/PH union carrying DV-43, DV-46, DV-22 and DV-47..DV-51.",
    "CODE_RESOLUTION_CODE": "Declared derivation: the closed method map evaluated once per distinct raw code.",
    "CODE_RESOLUTION_CODE_CANDIDATE": "Declared derivation: code-level candidate identities behind CODE_RESOLUTION_CANDIDATE.",
    "CODE_RESOLUTION_INPUT": "Declared derivation: the row-scoped raw-code inputs of the closed method map.",
    "SCHEDULE_AMENDMENT_SIDE": "Declared derivation: exact removals/additions with their typed candidate signature and eligibility verdict.",
    "PASSENGER_PLANNED_LEG": "Declared derivation: ordered planned station sequence legs for fulfillment endpoint compatibility.",
    "FULFILLMENT_COMPATIBILITY": "Declared derivation: the bipartite actual/passenger compatibility graph behind DV-40 and DV-41.",
}

DERIVED_COLUMNS: dict[str, str] = {
    # generic identity / lineage
    "SOURCE_OBJECT": "Source object token of the originating row.",
    "SOURCE_SYSTEM": "Source system token, FORWARD or HISTORICAL.",
    "SOURCE_ROW_TOKEN": "DV-46 source row token: source system prefix plus the stable source row ID when present, else the DV-43 hash.",
    "SOURCE_ROW_TOKEN_BASIS": "Whether DV-46 used STABLE_SOURCE_ROW_ID or DV43_HASH_FALLBACK.",
    "STABLE_SOURCE_ROW_ID": "Retained stable source row ID (PF-01 or PH-01); null is legitimate and drives the DV-43 fallback.",
    "TYPED_NORMALIZED_ROW_HASH": "DV-43 typed normalized row hash under D-0012 grammar dv43-lp-v1.",
    "SELECTION_RANK": "Deterministic selection rank within the declared reduction order; 1 is the retained row.",
    "SELECTION_RULE": "The declared deterministic selection order applied.",
    "PROJECTION_RULE": "The declared deterministic projection order used to choose one reference row per identity.",
    "OCCURRENCE_COUNT": "Number of identical source observations collapsed onto this deterministic semantic key.",
    "SOURCE_OCCURRENCE_COUNT": "Number of raw source rows that shared this DV-46 source row token; a semantic source duplicate collapses to one resolution result and keeps its multiplicity here.",
    # aircraft existence
    "EXISTENCE_FROM": "DV-01 aircraft existence lower bound: normalized AM-07, else the first eligible AH-05.",
    "EXISTENCE_TO": "DV-02 aircraft existence upper bound, exclusive: normalized AM-08 else the model open sentinel 9999-01-01.",
    "EXISTENCE_FROM_BASIS": "Which rule supplied DV-01: AM_07_START_OF_LIFE, FIRST_ELIGIBLE_EVENT_DATE or UNBOUNDED.",
    "HAS_FINITE_END_OF_LIFE": "True when AM-08 supplied a real finite exclusive existence bound.",
    "FIRST_ELIGIBLE_EVENT_DATE": "Earliest AH-05 among required-field-eligible events for this aircraft.",
    "AIRCRAFT_ORDER_DATE_IS_UNKNOWN_FUTURE": "True when raw AM-04 equalled the source unknown-future sentinel 9999-12-31.",
    "AIRCRAFT_BUILD_DATE_IS_UNKNOWN_FUTURE": "True when raw AM-05 equalled the source unknown-future sentinel 9999-12-31.",
    "AIRCRAFT_DELIVERY_DATE_IS_UNKNOWN_FUTURE": "True when raw AM-06 equalled the source unknown-future sentinel 9999-12-31.",
    "AIRCRAFT_ROLL_OUT_DATE_IS_UNKNOWN_FUTURE": "True when raw AM-16 equalled the source unknown-future sentinel 9999-12-31.",
    "AIRCRAFT_FIRST_FLIGHT_DATE_IS_UNKNOWN_FUTURE": "True when raw AM-17 equalled the source unknown-future sentinel 9999-12-31.",
    "AIRCRAFT_START_OF_LIFE_DATE_IS_UNKNOWN_FUTURE": "True when raw AM-07 equalled the source unknown-future sentinel 9999-12-31.",
    "AIRCRAFT_END_OF_LIFE_DATE_IS_UNKNOWN_FUTURE": "True when raw AM-08 equalled the source unknown-future sentinel 9999-12-31.",
    "END_EVENT_DATE_IS_UNKNOWN_FUTURE": "True when raw AH-06 equalled the source unknown-future sentinel 9999-12-31.",
    "PUBLISH_DATE_IS_UNKNOWN_FUTURE": "True when the raw source publish date equalled the source unknown-future sentinel 9999-12-31.",
    "MASTER_CURRENT_ONLY_APU_TYPE": "Field AM-11, explicitly CURRENT_ONLY under D-0005; prohibited from historical reconstruction.",
    "MASTER_CURRENT_ONLY_AIRCRAFT_WIDTH_M": "Field AM-12, explicitly CURRENT_ONLY under D-0005; prohibited from historical reconstruction.",
    "MASTER_CURRENT_ONLY_OPERATING_MAXIMUM_TAKEOFF_WEIGHT_LB": "Field AM-13, explicitly CURRENT_ONLY under D-0005.",
    "MASTER_CURRENT_ONLY_CERTIFIED_MAXIMUM_TAKEOFF_WEIGHT_LB": "Field AM-14, explicitly CURRENT_ONLY under D-0005.",
    # aircraft events and assignments
    "EVENT_ORDER_RANK": "DV-03 canonical event order rank within an aircraft over (AH-05, AH-03, AH-04, AH-01).",
    "EVENT_DATE": "Field AH-05 start_event_date, the observation date of this assignment.",
    "CONFIGURATION_RESOLVED": "True when AH-13 resolved to an AIRCRAFT_CONFIGURATION row.",
    "CONFIGURATION_PUBLISH_DATE": "Field AC-16 configuration reference lineage date, never assignment validity.",
    "TYPE_RESOLUTION_STATUS": "DV-08 aircraft-type resolution outcome of AH-13; part of the aircraft_type watched set.",
    "ENGINE_RESOLUTION_STATUS": "DV-08 engine-type resolution outcome of AH-13; part of the engine_type watched set.",
    "MIXED_ENGINE_SET_COMPLETE": "DV-09; false when AC-09 reports multiple engine types. A second engine type is unsupported and never invented.",
    "WOULD_BE_LOST_BY_INNER_JOIN": "P0-12.4 measurement: true when a source-style inner join on AH-13 would have dropped this event.",
    "AUDIT_ASSIGNMENT_ID": "DV-04 audit assignment identity: dimension, AH-02, AH-05, AH-03, AH-01 joined by '|'.",
    "DAILY_ASSIGNMENT_ID": "DV-05 daily assignment identity: dimension, AH-02, AH-05, AH-01 joined by '|'.",
    "DIMENSION": "Independently versioned dimension: aircraft_state, aircraft_type, engine_type or aircraft_status.",
    "DIMENSION_SEQUENCE": "Ordinal of this assignment within its (dimension, aircraft) audit sequence.",
    "IS_FINAL_RELEVANT_OBSERVATION_OF_DAY": "True when this is the final relevant observation of its (dimension, aircraft, event date) and therefore date-visible.",
    "WATCHED_SIGNATURE": "SHA-256 over the D-0012 typed encoding of this dimension's watched value set; null-safe change detection input.",
    "PREVIOUS_WATCHED_SIGNATURE": "Watched signature of the immediately preceding eligible observation; null for the first.",
    "DIMENSION_RESOLUTION_STATUS": "DV-08 per-dimension resolution status of this assignment.",
    "DIMENSION_QUERY_STATUS": "DV-33 status inside the interval: OK or UNKNOWN_STATE. OUTSIDE_EXISTENCE and NO_RECORDED_STATE are evaluated at query time against DV-01/DV-02.",
    "VALID_FROM": "DV-06 half-open interval start, inclusive; the AH-05 of the final relevant daily observation.",
    "VALID_TO": "DV-07 half-open interval end, exclusive; the next distinct daily assignment date clipped to DV-02 existence, else the model open sentinel 9999-01-01.",
    "NEXT_ASSIGNMENT_DATE": "Next distinct daily assignment date for the same aircraft and dimension before existence clipping.",
    "VALID_TO_CLIPPED_TO_EXISTENCE": "True when DV-02 existence clipped the derived DV-07 upper bound.",
    "END_EVENT_DATE_DISAGREES_WITH_VALID_TO": "HT-07 evidence: source AH-06 disagrees with the derived DV-07 without changing it.",
    "AIRCRAFT_STATUS_CODE": "Field AH-09 start_aircraft_status, the aircraft_status watched value, retained without trim or case fold.",
    "AIRCRAFT_TYPE_SUBSERIES": "Field AC-05 resolved through AH-13; the aircraft-type identity candidate.",
    "EXACT_AIRCRAFT_TYPE_SUBSERIES": "AC-05 exposed only when the type resolution is EXACT; the sole basis for an AircraftType link.",
    "AIRCRAFT_TYPE_LABEL": "Field AC-03 aircraft_type descriptive label resolved through AH-13.",
    "ENGINE_TYPE_SUBSERIES": "Field AC-14 resolved through AH-13; the engine-type identity candidate.",
    "EXACT_ENGINE_TYPE_SUBSERIES": "AC-14 exposed only when the engine resolution is EXACT; the sole basis for an EngineType link.",
    "ENGINE_TYPE_LABEL": "Field AC-12 engine_type descriptive label resolved through AH-13.",
    "AIRCRAFT_LINK_EXISTS": "True when AF-02 resolves to an eligible Aircraft identity.",
    # quarantine
    "QUARANTINE_ID": "DV-44 quarantine identity: SHA-256 over source object, the stable source row ID when present else DV-43, and the closed reason code.",
    "QUARANTINE_REASON": "Closed reason code explaining why the observation is ineligible.",
    "QUARANTINE_KEY_BASIS": "Whether DV-44 used STABLE_SOURCE_ROW_ID or DV43_HASH_FALLBACK.",
    "MISSING_REQUIRED_FIELDS": "Comma-joined list of required identity columns that were null.",
    "MISSING_KEY_COMPONENTS": "Comma-joined list of canonical passenger-key components that were null.",
    "INELIGIBILITY_REASON": "Closed reason code explaining why the row is not candidate eligible.",
    "INVALID_REASON": "Closed reason code for an invalid passenger observation.",
    "RAW_AIRCRAFT_HISTORY_ID": "Raw AH-01 as observed, retained as quarantine lineage only.",
    "RAW_AIRCRAFT_ID": "Raw AH-02 as observed, retained as quarantine lineage only.",
    "RAW_ROW_SEQUENCE_NUMBER": "Raw AH-03 as observed, retained as quarantine lineage only.",
    "RAW_EVENT_SEQUENCE_NUMBER": "Raw AH-04 as observed, retained as quarantine lineage only.",
    "RAW_START_EVENT_DATE": "Raw AH-05 as observed, retained as quarantine lineage only.",
    "RAW_MARKETING_CARRIER_INTERNAL": "Raw marketing carrier code as observed, retained as audit lineage only.",
    "RAW_FLIGHT_NUMBER": "Raw source flight number as observed, before normalization.",
    "RAW_DEPARTURE_STATION_CODE_IATA": "Raw planned origin code as observed, retained as audit lineage only.",
    "RAW_ARRIVAL_STATION_CODE_IATA": "Raw planned destination code as observed, retained as audit lineage only.",
    "RAW_OPERATING_DATE": "Raw operating date as observed, retained as audit lineage only.",
    "RAW_IS_CANCELLED": "Field AF-11 raw integer cancellation flag before DV-52 normalization.",
    "RAW_IS_DIVERTED": "Field AF-12 raw integer diversion flag before DV-53 normalization.",
    # type/engine definitions
    "DEFINITION_STATUS": "EXACT when the definition functional dependency holds for this subseries, otherwise AMBIGUOUS_DEFINITION with null definition fields.",
    "DEFINITION_VARIANT_COUNT": "Number of distinct definitions observed for this subseries; the FD holds only at 1.",
    "SOURCE_CONFIGURATION_COUNT": "Number of AIRCRAFT_CONFIGURATION rows reporting this subseries.",
    # reference projections
    "SELECTED_EFFECTIVE_START_DATE": "Effective start date of the deterministically selected reference period; lineage only, not modeled state.",
    "SELECTED_EFFECTIVE_END_DATE": "Effective end date of the deterministically selected reference period; lineage only, not modeled state.",
    "REFERENCE_PERIOD_COUNT": "Number of source effective-period rows for this reference identity.",
    # month-end calendar
    "MONTH_END": "Calendar month-end date.",
    "MONTH_START": "First day of the same calendar month.",
    "CALENDAR_YEAR": "Calendar year of the month end.",
    "CALENDAR_MONTH": "Calendar month number of the month end.",
    "MONTH_INDEX": "Zero-based month offset from 2000-01.",
    # code resolution
    "RESOLUTION_ID": "Deterministic resolution identity: SHA-256 over domain, source object, DV-46 source row token, field role, raw code and method.",
    "DOMAIN": "Resolution domain: AIRPORT or AIRLINE.",
    "FIELD_ROLE": "Labelled role of the raw code on its source row, for example marketing_carrier or route_origin.",
    "RAW_FIELD_ID": "SOURCE_CONTRACT.md Field ID of the raw code being resolved.",
    "RAW_CODE": "The raw source code, preserved exactly; no case folding, punctuation stripping or fuzzy matching.",
    "METHOD": "Contracted resolution method from the closed method map.",
    "CANDIDATE_COUNT": "DV-11 count of distinct AP-01 or AL-01 candidate identities.",
    "RESOLUTION_STATUS": "DV-10 status: EXACT, AMBIGUOUS, UNRESOLVED or INVALID_INPUT.",
    "RESOLVED_IDENTITY_ID": "The single reference identity, populated only for EXACT cardinality one.",
    "MATCHED_CODE_SYSTEMS": "Which reference code systems matched, with no precedence assigned among them.",
    "CANDIDATE_ID": "A candidate AP-01 or AL-01 reference identity.",
    "SINGLE_CANDIDATE_ID": "The candidate identity when exactly one exists; null otherwise.",
    # schedule observations
    "SNAPSHOT_IS_PRESENT": "Field SC-02 explicit arrival evidence for this publish date.",
    "SNAPSHOT_IS_COMPLETE": "Field SC-03 explicit completeness evidence for this publish date.",
    "IS_ELIGIBLE_SNAPSHOT": "SC-02 AND SC-03. Only eligible dates drive presence or change inference.",
    "SNAPSHOT_VALIDATION_STATUS": "Field SC-06 named validation outcome for this publish date.",
    "SNAPSHOT_SOURCE_LINEAGE_ID": "Field SC-04 synthetic input batch lineage for this publish date.",
    "RAW_OBSERVATION_COUNT": "Number of raw SCHEDULE_SNAPSHOT rows for this (SS-01, SS-03) before deterministic selection.",
    "SEMANTIC_DUPLICATE_COUNT": "Number of raw rows sharing the selected SS-40 normalized row hash; identical hashes are semantic duplicates.",
    "ROUTE_ID": "DV-12 directional route identity SS-10 || '->' || SS-11; null when either component is null.",
    "ROUTE_KEY_STATUS": "VALID or INVALID_ROUTE_KEY. An invalid route key still permits exact schedule-key presence and content evidence.",
    "WATCHED_CONTENT_SIGNATURE": "SHA-256 over the D-0012 typed encoding of the SS-04..SS-38 watched content set; null-safe change detection input.",
    "ECONOMY_EXCLUDING_PREMIUM": "DV-26 exclusive economy bucket, SS-34 minus SS-33. Always computed; raw values are never overwritten.",
    "EXCLUSIVE_CABIN_SUM": "First + business + premium economy + DV-26, computed only when the cabin inputs pass the DV-27 quality checks.",
    "CABIN_QUALITY_STATUS": "DV-27: NULL_CABIN_VALUE, NEGATIVE_CABIN_VALUE, PREMIUM_EXCEEDS_ECONOMY, TOTAL_MISMATCH or RECONCILED, evaluated in that order.",
    "MARKETING_AIRLINE_ID": "Exact resolved marketing-role airline identity; null unless resolution is EXACT.",
    "MARKETING_AIRLINE_RESOLUTION_STATUS": "DV-10 status of the marketing carrier code resolution.",
    "OPERATING_AIRLINE_ID": "Exact resolved operating-role airline identity; a separate role from marketing.",
    "OPERATING_AIRLINE_RESOLUTION_STATUS": "DV-10 status of the operating carrier code resolution.",
    "CODESHARE_AIRLINE_ID": "Exact resolved codeshare-carrier airline identity.",
    "CODESHARE_AIRLINE_RESOLUTION_STATUS": "DV-10 status of the codeshare carrier code resolution.",
    "ORIGIN_AIRPORT_ID": "Exact resolved origin airport identity; null unless resolution is EXACT.",
    "ORIGIN_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the origin station code resolution.",
    "DESTINATION_AIRPORT_ID": "Exact resolved destination airport identity; null unless resolution is EXACT.",
    "DESTINATION_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the destination station code resolution.",
    "PHYSICAL_SERVICE_STATUS": "DV-28 under D-0007: PHYSICAL_SERVICE_REPRESENTATIVE only for an unambiguous non-codeshare base row, else UNRESOLVED_PHYSICAL_SERVICE.",
    "UTC_DATE_STATUS": "DV-51: EXPLICIT_EXPANDED, OFFSET_DERIVED or UNRESOLVED_UTC_DATE. Never inferred from clock ordering.",
    "ORIGIN_STATION_CODE_IATA": "Field SS-10 raw planned origin code, retained even when resolution is not exact.",
    "DESTINATION_STATION_CODE_IATA": "Field SS-11 raw planned destination code, retained even when resolution is not exact.",
    "CANONICAL_OBSERVATION_COUNT": "Number of canonical schedule observations on this route.",
    "DISTINCT_SCHEDULE_KEY_COUNT": "Number of distinct SS-01 schedule identities observed on this route.",
    # route states
    "ROUTE_STATE_KEY": "DV-13 route state identity: SS-01 || '|' || the segment-opening knowledge date. Route is deliberately absent from the identity.",
    "KNOWLEDGE_VALID_FROM": "DV-14 half-open knowledge interval start, inclusive; the eligible SS-03 that opened the segment.",
    "KNOWLEDGE_VALID_TO": "DV-15 half-open knowledge interval end, exclusive; the next eligible SS-03 proving a content change or absence, else the model open sentinel 9999-01-01.",
    "IS_OPEN_STATE": "True when DV-15 is the model open sentinel.",
    "SEGMENT_OPEN_KIND": "Why the segment opened: INITIAL, CONTENT_CHANGE or REAPPEARANCE.",
    "IS_REAPPEARANCE": "True when this segment reopened after a proven complete absence, even if content repeats.",
    "CLOSING_REASON": "CONTENT_CHANGE, ABSENCE or null while open.",
    "PREVIOUS_ELIGIBLE_PUBLISH_DATE_AT_OPEN": "The eligible snapshot date immediately preceding the segment opening date.",
    "OPEN_CROSSES_SNAPSHOT_GAP": "DV-16 at the opening endpoint: a declared SC-01 date lies strictly between the two eligible dates.",
    "OPEN_SKIPPED_CALENDAR_DATES": "The declared SC-01 dates skipped at the opening endpoint; the occurrence date inside a gap is never invented.",
    "CLOSE_CROSSES_SNAPSHOT_GAP": "DV-16 at the closing endpoint.",
    "CLOSE_SKIPPED_CALENDAR_DATES": "The declared SC-01 dates skipped at the closing endpoint.",
    "CONTRIBUTING_SNAPSHOT_COUNT": "Number of eligible complete snapshots coalesced into this state; repeats contribute lineage but mint no state.",
    "OPERATING_EFFECTIVE_DATE": "Field SS-08 inclusive operating lower bound. Deliberately inclusive, unlike the half-open knowledge clock.",
    "OPERATING_DISCONTINUE_DATE": "Field SS-09 inclusive operating upper bound. Deliberately inclusive, unlike the half-open knowledge clock.",
    "IS_SEGMENT_OPENING_OBSERVATION": "True when this lineage observation is the one that opened the RouteState segment.",
    # comparisons and changes
    "COMPARISON_ID": "DV-34 comparison identity: SHA-256 over the older and newer eligible knowledge endpoint dates.",
    "COMPARISON_DATE": "The newer eligible knowledge endpoint of the comparison.",
    "PREVIOUS_KNOWLEDGE_DATE": "The older eligible knowledge endpoint of the comparison.",
    "PREVIOUS_ELIGIBLE_RANK": "Ordinal of the older endpoint in the eligible snapshot sequence.",
    "COMPARISON_ELIGIBLE_RANK": "Ordinal of the newer endpoint in the eligible snapshot sequence.",
    "CALENDAR_DAY_SPAN": "Calendar days between the two endpoints; a gap makes this larger than the nominal cadence.",
    "SKIPPED_CALENDAR_DATE_COUNT": "Number of declared SC-01 dates strictly between the endpoints that were not eligible.",
    "SKIPPED_CALENDAR_DATES": "Comma-joined declared SC-01 dates skipped between the endpoints.",
    "CROSSES_SNAPSHOT_GAP": "DV-16: true when the two endpoints are adjacent in the eligible sequence but not adjacent in the declared calendar.",
    "COMPARISON_KIND": "How the comparison was formed; CONSECUTIVE_ELIGIBLE for every row in this release.",
    "CHANGE_KIND": "DV-17 exact change class: EXACT_ADDITION, EXACT_REMOVAL or EXACT_KEY_PRESERVING_MODIFICATION.",
    "FIELD_NAME": "Changed watched field name, or the non-null synthetic token __presence__ for a presence change.",
    "OLD_VALUE": "Display rendering of the watched value at the older endpoint; null means the source value was null.",
    "NEW_VALUE": "Display rendering of the watched value at the newer endpoint; null means the source value is null.",
    # amendment candidates
    "SIDE": "REMOVED or ADDED side of a key-shift comparison.",
    "CANDIDATE_ELIGIBLE": "True when every typed signature component and both inclusive operating bounds are present and valid.",
    "CANDIDATE_SIGNATURE": "Typed key-shift signature over SS-04, SS-06, SS-10 and SS-11, length-prefixed.",
    "AMENDMENT_CANDIDATE_ID": "DV-35 identity: SHA-256 over the comparison, the exact removed SS-01 and the exact added SS-01.",
    "AMENDMENT_CANDIDATE_CLASS": "DV-18 class: CANDIDATE_UNIQUE or AMBIGUOUS_CANDIDATE_GROUP.",
    "AMENDMENT_CONFIDENCE": "DV-19 confidence: MEDIUM for unique, LOW for ambiguous, NONE for unpaired. Never exact.",
    "EXACTNESS": "Whether the row is EXACT, CANDIDATE, AMBIGUOUS or UNPAIRED evidence. Interfaces must preserve this word.",
    "REMOVED_SCHEDULE_KEY": "The exact removed SS-01 of a candidate pair.",
    "ADDED_SCHEDULE_KEY": "The exact added SS-01 of a candidate pair.",
    "REMOVED_SCHEDULE_KEYS": "Sorted comma-joined exact removed SS-01 members of an ambiguous group.",
    "ADDED_SCHEDULE_KEYS": "Sorted comma-joined exact added SS-01 members of an ambiguous group.",
    "REMOVED_EFFECTIVE_DATE": "SS-08 of the removed side; evidence, never a hidden tie-breaker.",
    "REMOVED_DISCONTINUE_DATE": "SS-09 of the removed side; evidence, never a hidden tie-breaker.",
    "ADDED_EFFECTIVE_DATE": "SS-08 of the added side; evidence, never a hidden tie-breaker.",
    "ADDED_DISCONTINUE_DATE": "SS-09 of the added side; evidence, never a hidden tie-breaker.",
    "REMOVED_OPERATING_CARRIER_INTERNAL": "SS-05 of the removed side; evidence only.",
    "ADDED_OPERATING_CARRIER_INTERNAL": "SS-05 of the added side; evidence only.",
    "REMOVED_DAYS_PATTERN": "SS-21 of the removed side; evidence only.",
    "ADDED_DAYS_PATTERN": "SS-21 of the added side; evidence only.",
    "REMOVED_WEEKLY_FREQUENCY": "SS-22 of the removed side; evidence only.",
    "ADDED_WEEKLY_FREQUENCY": "SS-22 of the added side; evidence only.",
    "REMOVED_EQUIPMENT_SUBTYPE_CODE_IATA": "SS-29 of the removed side; evidence only.",
    "ADDED_EQUIPMENT_SUBTYPE_CODE_IATA": "SS-29 of the added side; evidence only.",
    "REMOVED_TOTAL_SEATS": "SS-30 of the removed side; evidence only.",
    "ADDED_TOTAL_SEATS": "SS-30 of the added side; evidence only.",
    "AMENDMENT_GROUP_ID": "DV-36 identity: SHA-256 over the comparison, typed signature, sorted removed keys and sorted added keys.",
    "AMENDMENT_GROUP_MEMBER_ID": "DV-37 member identity; for an unpaired side it is SHA-256 over the comparison, side and SS-01 with a null group.",
    "MEMBER_SCHEDULE_KEY": "The SS-01 of this group or unpaired member.",
    "MEMBER_CLASS": "AMBIGUOUS_GROUP_MEMBER, UNPAIRED_REMOVAL or UNPAIRED_ADDITION.",
    "UNPAIRED_REASON": "Why the side stayed unpaired: NO_ELIGIBLE_PARTNER or a named signature/range ineligibility.",
    "REMOVED_MEMBER_COUNT": "Number of distinct removed members in the ambiguous group.",
    "ADDED_MEMBER_COUNT": "Number of distinct added members in the ambiguous group.",
    # passenger
    "PASSENGER_FLIGHT_KEY": "DV-20 canonical passenger identity: typed marketing carrier, flight number, planned origin, planned destination and operating date joined by '|'.",
    "PASSENGER_KEY_STATUS": "DV-22: VALID, INVALID_PASSENGER_KEY or QUARANTINED.",
    "KEY_MARKETING_CARRIER_INTERNAL": "Canonical passenger-key marketing carrier component (PF-02 or PH-05).",
    "KEY_FLIGHT_NUMBER": "Canonical passenger-key flight number component (PF-04 or PH-07).",
    "KEY_DEPARTURE_STATION_CODE_IATA": "Canonical passenger-key planned origin component (PF-08 or PH-10).",
    "KEY_ARRIVAL_STATION_CODE_IATA": "Canonical passenger-key planned destination component (PF-09 or PH-11).",
    "KEY_OPERATING_DATE": "Canonical passenger-key operating date component (PF-05 or PH-04).",
    "PLAN_DEPARTURE_LOCAL_TIMESTAMP": "DV-47 planned local departure instant; for forward rows the source-expanded PF-10.",
    "PLAN_ARRIVAL_LOCAL_TIMESTAMP": "DV-48 planned local arrival instant including the PH-18 or PF-14 day offset.",
    "PLAN_DEPARTURE_UTC_TIMESTAMP": "DV-49 planned UTC departure instant; PF-12 verbatim, or DV-47 minus PH-16 minutes under D-0008.",
    "PLAN_ARRIVAL_UTC_TIMESTAMP": "DV-50 planned UTC arrival instant; PF-13 verbatim, or DV-48 minus PH-17 minutes under D-0008.",
    "HISTORICAL_EFFECTIVE_DATE": "Field PH-09 historical schedule lineage date; null when a forward row wins the union.",
    "SELECTED_SOURCE_SYSTEM": "Which side won the canonical-key overlap; historical always wins.",
    "SELECTED_SOURCE_ROW_TOKEN": "DV-46 token of the winning observation.",
    "SELECTED_SOURCE_ROW_TOKEN_BASIS": "Whether the winning DV-46 used the stable ID or the DV-43 fallback.",
    "SELECTED_STABLE_SOURCE_ROW_ID": "Stable source row ID of the winning observation; null is legitimate.",
    "SELECTED_TYPED_NORMALIZED_ROW_HASH": "DV-43 hash of the winning observation.",
    "SOURCE_PRECEDENCE_RULE": "The frozen union precedence rule, HISTORICAL_OVER_FORWARD.",
    "SOURCE_PRECEDENCE_RANK": "DV-21 precedence rank; 0 for historical, 1 for forward.",
    "LINEAGE_OBSERVATION_COUNT": "Number of contributing PF/PH observations retained for this canonical passenger flight.",
    "HISTORICAL_LINEAGE_RETAINED": "True when at least one historical observation contributed lineage.",
    "FORWARD_LINEAGE_RETAINED": "True when at least one forward observation contributed lineage.",
    "IS_SELECTED_OBSERVATION": "True for the lineage row that won the deterministic reduction.",
    "PLANNED_ORIGIN_STATION_CODE_IATA": "Planned origin raw code of the canonical passenger flight.",
    "PLANNED_DESTINATION_STATION_CODE_IATA": "Planned destination raw code of the canonical passenger flight.",
    "PLANNED_ORIGIN_AIRPORT_ID": "Exact resolved planned origin airport identity.",
    "PLANNED_ORIGIN_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the planned origin code resolution.",
    "PLANNED_DESTINATION_AIRPORT_ID": "Exact resolved planned destination airport identity.",
    "PLANNED_DESTINATION_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the planned destination code resolution.",
    # planned legs
    "LEG_INDEX": "Zero-based index of this consecutive leg inside the ordered planned station sequence.",
    "STATION_COUNT": "Number of stations in the ordered planned sequence, origin plus stops plus destination.",
    "FROM_STATION_CODE_IATA": "Planned departure station of this consecutive leg, parsed in contracted source order.",
    "TO_STATION_CODE_IATA": "Planned arrival station of this consecutive leg, parsed in contracted source order.",
    "FROM_AIRPORT_ID": "Exact resolved airport identity of the planned leg departure station.",
    "FROM_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the planned leg departure station resolution.",
    "TO_AIRPORT_ID": "Exact resolved airport identity of the planned leg arrival station.",
    "TO_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the planned leg arrival station resolution.",
    # actual flights
    "NORMALIZED_FLIGHT_NUMBER": "DV-38 normalized actual flight number: trimmed AF-05, ASCII digits only, cast to NUMBER(38,0).",
    "FLIGHT_NUMBER_STATUS": "NORMALIZED or INVALID_FLIGHT_NUMBER; invalid values keep the raw AF-05 and are ineligible for matching.",
    "ACTUAL_CONTINUITY_ARRIVAL_CODE": "DV-45, exactly AF-09. AF-10 and DV-53 never repair it.",
    "IS_CANCELLED_BOOLEAN": "DV-52 normalized cancellation flag; null when AF-11 is null or not 0/1.",
    "CANCELLATION_FLAG_STATUS": "NORMALIZED or UNKNOWN_OR_INVALID_CANCELLATION_FLAG; invalid rows stay visible but leave the strict operated chain.",
    "IS_DIVERTED_BOOLEAN": "DV-53 normalized diversion flag; null when AF-12 is null or not 0/1.",
    "DIVERSION_FLAG_STATUS": "NORMALIZED or UNKNOWN_OR_INVALID_DIVERSION_FLAG; it can never override DV-45.",
    "DIVERSION_ENDPOINT_CONFLICT": "True when a non-null AF-10 disagrees with AF-09; emits DIVERSION_ENDPOINT_CONFLICT and terminates continuity.",
    "ACTUAL_SOURCE_AIRCRAFT_TYPE": "Field AF-17 actual-source descriptive observation; never aircraft-history authority.",
    "ACTUAL_SOURCE_AIRCRAFT_CODE_IATA": "Field AF-18 actual-source descriptive observation.",
    "ACTUAL_SOURCE_AIRCRAFT_FAMILY": "Field AF-19 actual-source descriptive observation.",
    "ACTUAL_ORIGIN_AIRPORT_ID": "Exact resolved actual departure airport identity from AF-08.",
    "ACTUAL_ORIGIN_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the AF-08 internal-ID resolution.",
    "ACTUAL_DESTINATION_AIRPORT_ID": "Exact resolved actual arrival airport identity from AF-09.",
    "ACTUAL_DESTINATION_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the AF-09 internal-ID resolution.",
    "DIVERTED_AIRPORT_ID": "Exact resolved diversion airport identity from AF-10; reconciliation evidence only.",
    "DIVERTED_AIRPORT_RESOLUTION_STATUS": "DV-10 status of the AF-10 internal-ID resolution.",
    # rotation
    "TARGET_TOKEN": "AF-20 rendered as text, or the literal NO_TARGET so a null next link has no nullable identity.",
    "SELECTED_LOCAL_DATE": "Field AF-06, the source local selected-day basis. AF-07 UTC lineage never substitutes for it.",
    "SELECTED_DATE_BASIS": "Which source field supplied the selected local date.",
    "ROTATION_LINK_STATUS": "DV-24: ACCEPTED, TERMINAL_NO_TARGET, REJECTED or EXCLUDED.",
    "ROTATION_ANOMALY_CLASS": "DV-25 typed anomaly reason, null for an accepted or terminal link.",
    "IS_ACCEPTED_LINK": "True only when every rotation validation condition passed.",
    "CYCLE_COMPONENT_ID": "Minimum flight ID of the directed cycle this leg belongs to; null when the leg is not on a cycle.",
    "IS_CYCLE_REPRESENTATIVE": "True for the minimum flight ID of a cycle component, so a consumer emits exactly one component-level CYCLE row.",
    "IS_SELF_LOOP_LINK": "D-0022: the degenerate structural case AF-20 = AF-01, kept auditable here instead of through the cycle-component columns, because DV-25 ranks SELF_LOOP above CYCLE to keep the two classes disjoint.",
    "ACTUAL_ORIGIN_CODE": "Field AF-08 raw actual departure airport code.",
    "TARGET_FLIGHT_ID": "AF-01 of the resolved next leg; null when the target is missing.",
    "TARGET_AIRCRAFT_ID": "AF-02 of the resolved next leg, used for the same-aircraft continuity test.",
    "TARGET_SELECTED_LOCAL_DATE": "AF-06 of the resolved next leg, used for the selected-day test.",
    "TARGET_DEPARTURE_TIME_UTC": "AF-13 of the resolved next leg, used for the nondecreasing-time test.",
    "TARGET_ORIGIN_CODE": "AF-08 of the resolved next leg, used for the actual airport continuity test.",
    "TARGET_IS_CANCELLED_BOOLEAN": "DV-52 of the resolved next leg.",
    # fulfillment
    "EXACT_FULFILLMENT_ID": "DV-39 identity: SHA-256 over AF-01, DV-20 and the literal EXACT.",
    "ACTUAL_FLIGHT_ID": "AF-01 of the actual leg participating in this fulfillment evidence.",
    "PASSENGER_SOURCE_SYSTEM": "Source system of the passenger lineage row that carried the direct shared ID.",
    "PASSENGER_SOURCE_ROW_TOKEN": "DV-46 token of the passenger lineage row that carried the direct shared ID.",
    "PASSENGER_STABLE_SOURCE_ROW_ID": "PH-01 of the passenger lineage row; equal to AF-01 for an exact link.",
    "FULFILLMENT_CLASS": "DV-23: EXACT_FULFILLMENT, HEURISTIC_CANDIDATE, AMBIGUOUS_GROUP_MEMBER, UNMATCHED_ACTUAL or UNMATCHED_PASSENGER.",
    "EXACT_LINK_BASIS": "Which contracted mechanism justified the exact link.",
    "CONFIRMED_LINK": "True only for exact fulfillment; heuristic evidence never becomes confirmed fulfillment.",
    "ACTUAL_OPERATING_DATE": "AF-06 of the actual leg, compared with the planned operating date.",
    "PLANNED_OPERATING_DATE": "Operating date of the canonical passenger flight.",
    "ACTUAL_MARKETING_AIRLINE_ID": "Exact resolved marketing airline of the actual leg.",
    "PLANNED_MARKETING_AIRLINE_ID": "Exact resolved marketing airline of the canonical passenger flight.",
    "ACTUAL_OPERATING_AIRLINE_ID": "Exact resolved operating airline of the actual leg.",
    "PLANNED_OPERATING_AIRLINE_ID": "Exact resolved operating airline of the canonical passenger flight.",
    "PLANNED_FLIGHT_NUMBER": "Flight number of the canonical passenger flight.",
    "MARKETING_ROLE_AGREES": "True when the marketing role resolves exactly and identically on both sides.",
    "OPERATING_ROLE_AGREES": "True when the operating role resolves exactly and identically on both sides.",
    "FULFILLMENT_CANDIDATE_ID": "DV-40 identity: SHA-256 over AF-01, DV-20 and the literal HEURISTIC.",
    "CONFIDENCE": "Match confidence; MEDIUM for a unique heuristic candidate, LOW for an ambiguous member, NONE for unmatched.",
    "PLANNED_SERVICE_HAS_STOPOVERS": "True when the planned station sequence has more than two stations.",
    "FULFILLMENT_GROUP_ID": "DV-41 identity: SHA-256 over the sorted actual IDs and passenger keys of an ambiguous compatibility component.",
    "FULFILLMENT_GROUP_MEMBER_ID": "DV-42 member identity, or a deterministic unmatched identity when no group exists.",
    "MEMBER_IDENTITY": "AF-01 for an actual member, DV-20 for a passenger member.",
    "ACTUAL_MEMBER_COUNT": "Number of actual legs in the ambiguous component.",
    "PASSENGER_MEMBER_COUNT": "Number of passenger flights in the ambiguous component.",
    "UNMATCHED_REASON": "Why the observation is unmatched; unmatched rows remain first-class results.",
}


# ------------------------------------------------------------------------------------------------
# Snowflake access.  Every call is pinned; there is no caller override.
# ------------------------------------------------------------------------------------------------


def sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def run_snow(sql: str, *, label: str) -> list[Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".sql",
                                     prefix="model-input-") as handle:
        handle.write(f"ALTER SESSION SET QUERY_TAG={sql_string('AVIATION_TEMPORAL|DATA-04a|' + label)};\n")
        handle.write(sql)
        handle.flush()
        command = [
            "snow", "sql", "-c", CONNECTION, "--role", ROLE, "--warehouse", WAREHOUSE,
            "--database", DATABASE, "--format", "JSON", "--filename", handle.name,
        ]
        process = subprocess.run(command, cwd=ROOT, check=False,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        raise GateError(f"{label} failed ({process.returncode}): "
                        f"{process.stderr[-4000:]}\n{process.stdout[-4000:]}")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise GateError(f"{label} did not return JSON: {process.stdout[-2000:]}") from exc


def query(sql: str, *, label: str) -> list[dict[str, Any]]:
    """Run one statement and return its rows."""
    payload = run_snow(sql.rstrip().rstrip(";") + ";", label=label)
    for block in reversed(payload):
        if isinstance(block, list):
            return block
    raise GateError(f"{label} returned no result set")


# ------------------------------------------------------------------------------------------------
# Column lineage.  Every MODEL_INPUT column must trace to a SOURCE_CONTRACT.md Field ID inside its
# table's declared source-prefix scope, or to a DERIVED_COLUMNS entry.  Otherwise the build fails.
# ------------------------------------------------------------------------------------------------


def parse_contract_fields() -> dict[str, list[tuple[str, str]]]:
    """Return {UPPER_COLUMN_NAME: [(field_id, canonical_role), ...]} from SOURCE_CONTRACT.md."""
    text = (ROOT / "SOURCE_CONTRACT.md").read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| ((?:AM|AH|AC|SS|SC|PF|PH|AF|AP|AL)-\d{2}) \| `([^`]+)` \| "
        r"([A-Z][A-Z0-9_]*(?:\([^)]*\))?) \| (?:yes|no) \| ([^|]+)\|",
        text, flags=re.MULTILINE,
    )
    if len(rows) != 195:
        raise GateError(f"expected 195 contract field rows, parsed {len(rows)}")
    by_column: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for field_id, column, _type_tag, role in rows:
        by_column[column.upper()].append((field_id, role.strip()))
    return by_column


def column_comment(table: str, column: str,
                   contract: dict[str, list[tuple[str, str]]]) -> str:
    prefixes = TABLE_SOURCE_PREFIXES.get(table, ())
    for prefix in prefixes:
        for field_id, role in contract.get(column, []):
            if field_id.startswith(prefix):
                return f"Field {field_id}: {role}"
    if column in DERIVED_COLUMNS:
        return DERIVED_COLUMNS[column]
    # A column whose name matches a source column outside the declared prefix scope still traces,
    # but the scope is wrong, so say so loudly rather than guessing.
    if column in contract:
        ids = "/".join(fid for fid, _ in contract[column])
        raise GateError(
            f"{table}.{column} matches source field(s) {ids} outside the declared prefix scope "
            f"{prefixes}; fix TABLE_SOURCE_PREFIXES or add a DERIVED_COLUMNS entry")
    raise GateError(f"{table}.{column} traces to no Field ID and no declared derivation")


def annotate_columns() -> dict[str, Any]:
    contract = parse_contract_fields()
    rows = query(
        f"SELECT table_name, column_name FROM {DATABASE}.INFORMATION_SCHEMA.COLUMNS "
        f"WHERE table_schema = '{SCHEMA}' ORDER BY table_name, ordinal_position",
        label="column_inventory")
    per_table: dict[str, list[str]] = defaultdict(list)
    traced_to_field = 0
    total = 0
    for row in rows:
        table, column = row["TABLE_NAME"], row["COLUMN_NAME"]
        comment = column_comment(table, column, contract)
        if comment.startswith("Field "):
            traced_to_field += 1
        total += 1
        per_table[table].append(f'"{column}" COMMENT {sql_string(comment)}')
    # One ALTER per table keeps the round trips proportional to tables, not columns.
    statements = [f"ALTER TABLE {DATABASE}.{SCHEMA}.{table} ALTER (\n  "
                  + ",\n  ".join(clauses) + "\n);"
                  for table, clauses in sorted(per_table.items())]
    run_snow("\n".join(statements), label="comment_columns")
    return {"columns_commented": total,
            "tables_annotated": len(statements),
            "traced_to_source_field_id": traced_to_field,
            "traced_to_declared_derivation": total - traced_to_field}


# ------------------------------------------------------------------------------------------------
# plan / apply
# ------------------------------------------------------------------------------------------------


def plan() -> str:
    parts = []
    for name in SQL_FILES:
        path = SQL_DIR / name
        if not path.exists():
            raise GateError(f"missing SQL file {path}")
        parts.append(f"-- ===== {name} " + "=" * (80 - len(name)))
        parts.append(path.read_text(encoding="utf-8").rstrip())
    return "\n\n".join(parts) + "\n"


def apply() -> dict[str, Any]:
    timings: dict[str, float] = {}
    for name in SQL_FILES:
        started = time.monotonic()
        run_snow((SQL_DIR / name).read_text(encoding="utf-8"), label=name)
        timings[name] = round(time.monotonic() - started, 3)
    started = time.monotonic()
    annotation = annotate_columns()
    timings["annotate_columns"] = round(time.monotonic() - started, 3)
    return {"timings_seconds": timings, "annotation": annotation}


# ------------------------------------------------------------------------------------------------
# Gates.  Each entry is (gate_id, description, scalar SQL, expected).  `expected` is either an
# exact string or a callable predicate over the returned string.
# ------------------------------------------------------------------------------------------------

MI = f"{DATABASE}.{SCHEMA}"
SRC = f"{DATABASE}.SOURCE"

GATES: tuple[tuple[str, str, str, Any], ...] = (
    # ---- multiplicity and integrity gates from SOURCE_CONTRACT.md -------------------------------
    ("MG-01", "Aircraft master to Aircraft: duplicate AM-01 is a hard source gate failure",
     f"SELECT COUNT(*) FROM (SELECT aircraft_id FROM {SRC}.AIRCRAFT_MASTER "
     f"WHERE aircraft_id IS NOT NULL GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-02", "AIRCRAFT_ELIGIBLE is one row per AM-01",
     f"SELECT COUNT(*) FROM (SELECT aircraft_id FROM {MI}.AIRCRAFT_ELIGIBLE GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-03", "AIRCRAFT_EVENT_ELIGIBLE is one row per AH-01",
     f"SELECT COUNT(*) FROM (SELECT aircraft_history_id FROM {MI}.AIRCRAFT_EVENT_ELIGIBLE GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-04", "DV-04 audit assignment identity is unique",
     f"SELECT COUNT(*) FROM (SELECT audit_assignment_id FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-05", "DV-05 daily assignment identity is unique",
     f"SELECT COUNT(*) FROM (SELECT daily_assignment_id FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-06", "Exactly one final relevant observation per (aircraft, dimension, date)",
     f"SELECT COUNT(*) FROM (SELECT dimension, aircraft_id, event_date FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT "
     f"WHERE is_final_relevant_observation_of_day GROUP BY 1,2,3 HAVING COUNT(*) > 1)", "0"),
    ("MG-07", "At most one daily assignment per (dimension, aircraft, valid_from)",
     f"SELECT COUNT(*) FROM (SELECT dimension, aircraft_id, valid_from FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT GROUP BY 1,2,3 HAVING COUNT(*) > 1)", "0"),
    ("MG-08", "AircraftType definition FD holds for every non-null AC-05",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_TYPE_DEFINITION WHERE definition_status <> 'EXACT'", "0"),
    ("MG-09", "EngineType definition FD holds for every non-null AC-14 (AC-08/AC-09 excluded)",
     f"SELECT COUNT(*) FROM {MI}.ENGINE_TYPE_DEFINITION WHERE definition_status <> 'EXACT'", "0"),
    ("MG-10", "AIRPORT_CURRENT is one row per AP-01",
     f"SELECT COUNT(*) FROM (SELECT airport_id FROM {MI}.AIRPORT_CURRENT GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-11", "AIRLINE_CURRENT is one row per AL-01",
     f"SELECT COUNT(*) FROM (SELECT airline_id FROM {MI}.AIRLINE_CURRENT GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-12", "CODE_RESOLUTION resolution_id is unique",
     f"SELECT COUNT(*) FROM (SELECT resolution_id FROM {MI}.CODE_RESOLUTION GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-13", "Raw code to reference identity: zero/one/many maps to unresolved/exact/ambiguous and only one creates a link",
     f"SELECT COUNT(*) FROM {MI}.CODE_RESOLUTION WHERE NOT ("
     f"(resolution_status = 'INVALID_INPUT' AND (raw_code IS NULL OR raw_code = '') AND candidate_count = 0 AND resolved_identity_id IS NULL) "
     f"OR (resolution_status = 'UNRESOLVED' AND raw_code IS NOT NULL AND candidate_count = 0 AND resolved_identity_id IS NULL) "
     f"OR (resolution_status = 'EXACT' AND candidate_count = 1 AND resolved_identity_id IS NOT NULL) "
     f"OR (resolution_status = 'AMBIGUOUS' AND candidate_count > 1 AND resolved_identity_id IS NULL))", "0"),
    ("MG-14", "CODE_RESOLUTION_CANDIDATE row count equals DV-11 candidate_count per resolution",
     f"SELECT COUNT(*) FROM (SELECT r.resolution_id FROM {MI}.CODE_RESOLUTION r "
     f"LEFT JOIN {MI}.CODE_RESOLUTION_CANDIDATE c ON c.resolution_id = r.resolution_id "
     f"GROUP BY r.resolution_id, r.candidate_count HAVING COUNT(c.candidate_id) <> r.candidate_count)", "0"),
    ("MG-15", "SCHEDULE_CANONICAL_OBSERVATION is at most one row per (SS-01, SS-03)",
     f"SELECT COUNT(*) FROM (SELECT schedule_key, publish_date FROM {MI}.SCHEDULE_CANONICAL_OBSERVATION GROUP BY 1,2 HAVING COUNT(*) > 1)", "0"),
    ("MG-16", "DV-13 route_state_key is unique",
     f"SELECT COUNT(*) FROM (SELECT route_state_key FROM {MI}.ROUTE_STATE GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-17", "SCHEDULE_EXACT_CHANGE grain (DV-34, SS-01, change_kind, field_name) is unique",
     f"SELECT COUNT(*) FROM (SELECT comparison_id, schedule_key, change_kind, field_name FROM {MI}.SCHEDULE_EXACT_CHANGE GROUP BY 1,2,3,4 HAVING COUNT(*) > 1)", "0"),
    ("MG-18", "DV-20 passenger_flight_key is unique",
     f"SELECT COUNT(*) FROM (SELECT passenger_flight_key FROM {MI}.PASSENGER_FLIGHT_CANONICAL GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-19", "PASSENGER_SOURCE_LINEAGE grain (DV-20, source_system, DV-46) is unique",
     f"SELECT COUNT(*) FROM (SELECT passenger_flight_key, source_system, source_row_token FROM {MI}.PASSENGER_SOURCE_LINEAGE GROUP BY 1,2,3 HAVING COUNT(*) > 1)", "0"),
    ("MG-20", "PASSENGER_FLIGHT_INVALID grain (source_system, stable_source_row_id) is unique and never null",
     f"SELECT (SELECT COUNT(*) FROM (SELECT source_system, stable_source_row_id FROM {MI}.PASSENGER_FLIGHT_INVALID "
     f"WHERE stable_source_row_id IS NOT NULL GROUP BY 1,2 HAVING COUNT(*) > 1)) "
     f"+ (SELECT COUNT(*) FROM {MI}.PASSENGER_FLIGHT_INVALID WHERE stable_source_row_id IS NULL)", "0"),
    ("MG-21", "AIRCRAFT_FLIGHT is one row per AF-01",
     f"SELECT COUNT(*) FROM (SELECT flight_id FROM {MI}.AIRCRAFT_FLIGHT GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-22", "ROTATION_LINK_VALIDATION grain (AF-01, target_token) is unique with no nullable identity",
     f"SELECT (SELECT COUNT(*) FROM (SELECT flight_id, target_token FROM {MI}.ROTATION_LINK_VALIDATION GROUP BY 1,2 HAVING COUNT(*) > 1)) "
     f"+ (SELECT COUNT(*) FROM {MI}.ROTATION_LINK_VALIDATION WHERE target_token IS NULL)", "0"),
    ("MG-23", "Actual flight to passenger flight: zero-or-one confirmed plan in v1",
     f"SELECT COUNT(*) FROM (SELECT actual_flight_id FROM {MI}.FULFILLMENT_EXACT GROUP BY 1 HAVING COUNT(*) > 1)", "0"),
    ("MG-24", "Exact and heuristic fulfillment never cover the same actual leg",
     f"SELECT COUNT(*) FROM {MI}.FULFILLMENT_CANDIDATE c WHERE EXISTS "
     f"(SELECT 1 FROM {MI}.FULFILLMENT_EXACT e WHERE e.actual_flight_id = c.actual_flight_id)", "0"),
    ("MG-25", "DV-39 / DV-40 / DV-42 identities are unique",
     f"SELECT (SELECT COUNT(*) FROM (SELECT exact_fulfillment_id FROM {MI}.FULFILLMENT_EXACT GROUP BY 1 HAVING COUNT(*) > 1)) "
     f"+ (SELECT COUNT(*) FROM (SELECT fulfillment_candidate_id FROM {MI}.FULFILLMENT_CANDIDATE GROUP BY 1 HAVING COUNT(*) > 1)) "
     f"+ (SELECT COUNT(*) FROM (SELECT fulfillment_group_member_id FROM {MI}.FULFILLMENT_AMBIGUOUS_GROUP GROUP BY 1 HAVING COUNT(*) > 1))", "0"),
    ("MG-26", "DV-35 / DV-36 / DV-37 identities are unique",
     f"SELECT (SELECT COUNT(*) FROM (SELECT amendment_candidate_id FROM {MI}.SCHEDULE_AMENDMENT_CANDIDATE GROUP BY 1 HAVING COUNT(*) > 1)) "
     f"+ (SELECT COUNT(*) FROM (SELECT amendment_group_id FROM {MI}.SCHEDULE_AMENDMENT_GROUP GROUP BY 1 HAVING COUNT(*) > 1)) "
     f"+ (SELECT COUNT(*) FROM (SELECT amendment_group_member_id FROM {MI}.SCHEDULE_AMENDMENT_GROUP_MEMBER GROUP BY 1 HAVING COUNT(*) > 1))", "0"),
    ("MG-27", "MONTH_END_CALENDAR has 600 distinct real month ends",
     f"SELECT COUNT(DISTINCT month_end) FROM {MI}.MONTH_END_CALENDAR "
     f"WHERE month_end = LAST_DAY(month_end)", "600"),
    ("MG-28", "DV-44 quarantine keys are unique in both quarantine tables",
     f"SELECT (SELECT COUNT(*) FROM (SELECT quarantine_id FROM {MI}.AIRCRAFT_EVENT_QUARANTINE GROUP BY 1 HAVING COUNT(*) > 1)) "
     f"+ (SELECT COUNT(*) FROM (SELECT quarantine_id FROM {MI}.PASSENGER_SOURCE_QUARANTINE GROUP BY 1 HAVING COUNT(*) > 1))", "0"),

    # ---- temporal integrity ---------------------------------------------------------------------
    ("TG-01", "Every daily assignment interval has positive width",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE valid_from >= valid_to", "0"),
    ("TG-02", "Daily assignment intervals never overlap inside (dimension, aircraft)",
     f"SELECT COUNT(*) FROM (SELECT dimension, aircraft_id, valid_to, "
     f"LEAD(valid_from) OVER (PARTITION BY dimension, aircraft_id ORDER BY valid_from) AS nxt "
     f"FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT) WHERE nxt IS NOT NULL AND nxt < valid_to", "0"),
    ("TG-03", "No daily assignment escapes its aircraft existence interval",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT d JOIN {MI}.AIRCRAFT_ELIGIBLE a "
     f"ON a.aircraft_id = d.aircraft_id WHERE d.valid_from < a.existence_from OR d.valid_to > a.existence_to", "0"),
    ("TG-04", "Every RouteState knowledge interval has positive width",
     f"SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE knowledge_valid_from >= knowledge_valid_to", "0"),
    ("TG-05", "RouteState knowledge intervals never overlap inside one SS-01",
     f"SELECT COUNT(*) FROM (SELECT schedule_key, knowledge_valid_to, "
     f"LEAD(knowledge_valid_from) OVER (PARTITION BY schedule_key ORDER BY knowledge_valid_from) AS nxt "
     f"FROM {MI}.ROUTE_STATE) WHERE nxt IS NOT NULL AND nxt < knowledge_valid_to", "0"),
    ("TG-06", "Source unknown-future sentinel 9999-12-31 never reaches a derived bound",
     f"SELECT (SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE valid_from = DATE '{SOURCE_UNKNOWN_FUTURE}' OR valid_to = DATE '{SOURCE_UNKNOWN_FUTURE}') "
     f"+ (SELECT COUNT(*) FROM {MI}.AIRCRAFT_ELIGIBLE WHERE existence_from = DATE '{SOURCE_UNKNOWN_FUTURE}' OR existence_to = DATE '{SOURCE_UNKNOWN_FUTURE}') "
     f"+ (SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE knowledge_valid_from = DATE '{SOURCE_UNKNOWN_FUTURE}' OR knowledge_valid_to = DATE '{SOURCE_UNKNOWN_FUTURE}')", "0"),
    ("TG-07", "Model open sentinel 9999-01-01 is used for open daily assignments",
     f"SELECT IFF(COUNT(*) > 0, 'PRESENT', 'ABSENT') FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT "
     f"WHERE valid_to = DATE '{MODEL_OPEN_SENTINEL}'", "PRESENT"),
    ("TG-08", "The model open sentinel never appears as an interval start",
     f"SELECT (SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE valid_from = DATE '{MODEL_OPEN_SENTINEL}') "
     f"+ (SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE knowledge_valid_from = DATE '{MODEL_OPEN_SENTINEL}')", "0"),
    ("TG-09", "No RouteState or exact change references an ineligible snapshot date",
     f"SELECT (SELECT COUNT(*) FROM {MI}.ROUTE_STATE r WHERE NOT EXISTS (SELECT 1 FROM {SRC}.SCHEDULE_SNAPSHOT_CALENDAR c "
     f"WHERE c.expected_publish_date = r.knowledge_valid_from AND c.is_present AND c.is_complete)) "
     f"+ (SELECT COUNT(*) FROM {MI}.SCHEDULE_COMPARISON s WHERE NOT EXISTS (SELECT 1 FROM {SRC}.SCHEDULE_SNAPSHOT_CALENDAR c "
     f"WHERE c.expected_publish_date = s.comparison_date AND c.is_present AND c.is_complete) "
     f"OR NOT EXISTS (SELECT 1 FROM {SRC}.SCHEDULE_SNAPSHOT_CALENDAR c2 "
     f"WHERE c2.expected_publish_date = s.previous_knowledge_date AND c2.is_present AND c2.is_complete))", "0"),
    ("TG-10", "Operating bounds stay inclusive and are never converted to an exclusive model bound",
     f"SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE operating_effective_date IS NOT NULL "
     f"AND operating_discontinue_date IS NOT NULL AND operating_effective_date > operating_discontinue_date", "0"),

    # ---- one-open-per-route is PROHIBITED: prove concurrency is preserved ------------------------
    ("XG-01", "Concurrent open RouteStates on one route are preserved, not collapsed",
     f"SELECT MAX(c) FROM (SELECT route_id, COUNT(*) c FROM {MI}.ROUTE_STATE "
     f"WHERE knowledge_valid_from <= DATE '2026-08-31' AND DATE '2026-08-31' < knowledge_valid_to GROUP BY 1)",
     lambda v: int(v) > 1),
    ("XG-02", "More than one route carries concurrent states at the same knowledge date",
     f"SELECT COUNT(*) FROM (SELECT route_id FROM {MI}.ROUTE_STATE "
     f"WHERE knowledge_valid_from <= DATE '2026-08-31' AND DATE '2026-08-31' < knowledge_valid_to "
     f"GROUP BY 1 HAVING COUNT(*) > 1)", lambda v: int(v) > 0),

    # ---- DV-43 known answers and canonical encoding ----------------------------------------------
    ("HG-01", "DV-43 grammar reproduces every SS-40 normalized row hash in SOURCE",
     f"SELECT COUNT(*) FROM {SRC}.SCHEDULE_SNAPSHOT s JOIN {MI}.CODE_RESOLUTION_CODE dummy ON 1=0 "
     f"UNION ALL SELECT COUNT(*) FROM (SELECT 1)", None),  # replaced below
    ("HG-02", "DV-43 of the frozen null-ID forward observation matches the frozen known answer",
     f"SELECT typed_normalized_row_hash FROM {MI}.PASSENGER_SOURCE_OBSERVATION "
     f"WHERE source_system = 'FORWARD' AND stable_source_row_id IS NULL AND key_flight_number = 726",
     "a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7"),
    ("HG-03", "Every contracted FLOAT input to DV-43 is integral, so CANON_FLOAT is exact here",
     f"SELECT (SELECT COUNT(*) FROM {SRC}.PASSENGER_HISTORICAL WHERE "
     f"(departure_utc_offset_minutes IS NOT NULL AND departure_utc_offset_minutes <> TRUNC(departure_utc_offset_minutes)) "
     f"OR (arrival_utc_offset_minutes IS NOT NULL AND arrival_utc_offset_minutes <> TRUNC(arrival_utc_offset_minutes)) "
     f"OR (total_seats IS NOT NULL AND total_seats <> TRUNC(total_seats))) "
     f"+ (SELECT COUNT(*) FROM {SRC}.AIRCRAFT_HISTORY WHERE aircraft_width_m IS NOT NULL AND aircraft_width_m <> TRUNC(aircraft_width_m))", "0"),
    ("HG-04", "No contracted TIME or TIMESTAMP_NTZ input carries a sub-second component",
     f"SELECT (SELECT COUNT(*) FROM {SRC}.PASSENGER_HISTORICAL WHERE TO_VARCHAR(passenger_departure_local_time,'FF9') <> '000000000' "
     f"OR TO_VARCHAR(passenger_arrival_local_time,'FF9') <> '000000000') "
     f"+ (SELECT COUNT(*) FROM {SRC}.PASSENGER_FORWARD WHERE TO_VARCHAR(passenger_departure_time_local,'FF9') <> '000000000' "
     f"OR TO_VARCHAR(passenger_arrival_time_utc,'FF9') <> '000000000')", "0"),
    ("HG-05", "DV-46 is never built from an unqualified nullable ID",
     f"SELECT COUNT(*) FROM {MI}.PASSENGER_SOURCE_OBSERVATION WHERE source_row_token IS NULL "
     f"OR NOT (source_row_token LIKE 'FORWARD|%' OR source_row_token LIKE 'HISTORICAL|%')", "0"),

    # ---- adversarial temporal probes ---------------------------------------------------------------
    ("AT-01", "Before first event: no dimension is date-visible for aircraft 1004 on 2019-06-30",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE aircraft_id = 1004 "
     f"AND valid_from <= DATE '2019-06-30' AND DATE '2019-06-30' < valid_to", "0"),
    ("AT-02", "Before first event: aircraft 1004 nonetheless exists on 2019-06-30",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_ELIGIBLE WHERE aircraft_id = 1004 "
     f"AND existence_from <= DATE '2019-06-30' AND DATE '2019-06-30' < existence_to", "1"),
    ("AT-03", "End-of-life boundary is exclusive: nothing is date-visible for 1002 on 2024-07-01",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE aircraft_id = 1002 "
     f"AND valid_from <= DATE '2024-07-01' AND DATE '2024-07-01' < valid_to", "0"),
    ("AT-04", "The day before end of life stays fully covered for 1002",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE aircraft_id = 1002 "
     f"AND valid_from <= DATE '2024-06-30' AND DATE '2024-06-30' < valid_to", "4"),
    ("AT-05", "Same-day ordering: four ordered status audit observations for 1001 on 2020-06-01",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT WHERE aircraft_id = 1001 "
     f"AND dimension = 'aircraft_status' AND event_date = DATE '2020-06-01'", "4"),
    ("AT-06", "Date-visible state is the final same-day observation (AH-01 101011)",
     f"SELECT aircraft_history_id FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE aircraft_id = 1001 "
     f"AND dimension = 'aircraft_status' AND valid_from = DATE '2020-06-01'", "101011"),
    ("AT-07", "An irrelevant event (AH-01 101020) mints no assignment in any dimension",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT WHERE aircraft_history_id = 101020", "0"),
    ("AT-08", "Missing configuration opens dimension-specific UNKNOWN_STATE gaps for 1002",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE aircraft_id = 1002 "
     f"AND dimension IN ('aircraft_type','engine_type') AND dimension_query_status = 'UNKNOWN_STATE'", "4"),
    ("AT-09", "A -> B -> A survives: two adjacent Storage to In Service audit pairs for 1001",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT a "
     f"JOIN {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT b ON b.aircraft_id = a.aircraft_id "
     f"AND b.dimension = 'aircraft_status' AND b.dimension_sequence = a.dimension_sequence + 1 "
     f"WHERE a.dimension = 'aircraft_status' AND a.aircraft_id = 1001 "
     f"AND a.aircraft_status_code = 'Storage' AND b.aircraft_status_code = 'In Service'", "2"),
    ("AT-10", "One of those spells is same-day with zero duration",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT a "
     f"JOIN {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT b ON b.aircraft_id = a.aircraft_id "
     f"AND b.dimension = 'aircraft_status' AND b.dimension_sequence = a.dimension_sequence + 1 "
     f"WHERE a.dimension = 'aircraft_status' AND a.aircraft_id = 1001 "
     f"AND a.aircraft_status_code = 'Storage' AND b.aircraft_status_code = 'In Service' "
     f"AND a.event_date = b.event_date", "1"),
    ("AT-11", "A null-to-value watched transition remains an audit assignment (AH-01 101021)",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT "
     f"WHERE aircraft_history_id = 101021 AND dimension = 'aircraft_state'", "1"),
    ("AT-12", "A value-to-null watched transition remains an audit assignment (AH-01 101023)",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT "
     f"WHERE aircraft_history_id = 101023 AND dimension = 'aircraft_state' AND apu_type IS NULL", "1"),
    ("AT-13", "A same-day repeat of the previous value mints nothing (AH-01 101022)",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT "
     f"WHERE aircraft_history_id = 101022 AND dimension = 'aircraft_state'", "0"),
    ("AT-14", "An intraday null followed by a same-day value invents no daily unknown gap",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE aircraft_id = 1001 "
     f"AND dimension = 'aircraft_state' AND dimension_query_status = 'UNKNOWN_STATE'", "0"),
    ("AT-15", "Incomplete and missing snapshots create zero exact changes and zero route states",
     f"SELECT (SELECT COUNT(*) FROM {MI}.SCHEDULE_EXACT_CHANGE e JOIN {MI}.SCHEDULE_COMPARISON c USING (comparison_id) "
     f"WHERE c.comparison_date IN (DATE '2026-10-12', DATE '2026-10-19') "
     f"OR c.previous_knowledge_date IN (DATE '2026-10-12', DATE '2026-10-19')) "
     f"+ (SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE knowledge_valid_from IN (DATE '2026-10-12', DATE '2026-10-19'))", "0"),
    ("AT-16", "Reappearance after a proven absence is labelled on the RouteState segment",
     f"SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE is_reappearance", "1"),
    ("AT-17", "Reappearance is also labelled on the exact presence addition",
     f"SELECT COUNT(*) FROM {MI}.SCHEDULE_EXACT_CHANGE WHERE is_reappearance", "1"),
    ("AT-18", "Repeated unchanged complete snapshots coalesce into one RouteState",
     f"SELECT contributing_snapshot_count FROM {MI}.ROUTE_STATE WHERE schedule_key = 'SYN-SK-STABLE_010'", "5"),
    ("AT-19", "A post-gap comparison exposes the skipped calendar dates and invents no date inside them",
     f"SELECT skipped_calendar_dates FROM {MI}.SCHEDULE_COMPARISON WHERE crosses_snapshot_gap",
     "2026-10-12,2026-10-19"),
    ("AT-20", "A unique candidate pair is never also an ambiguous group member",
     f"SELECT COUNT(*) FROM {MI}.SCHEDULE_AMENDMENT_CANDIDATE a JOIN {MI}.SCHEDULE_AMENDMENT_GROUP_MEMBER m "
     f"ON m.comparison_id = a.comparison_id AND m.member_class = 'AMBIGUOUS_GROUP_MEMBER' "
     f"AND m.member_schedule_key IN (a.removed_schedule_key, a.added_schedule_key)", "0"),
    ("AT-21", "Quarantine invents no identity: no quarantined passenger row had a stable source ID",
     f"SELECT COUNT(*) FROM {MI}.PASSENGER_SOURCE_OBSERVATION WHERE passenger_key_status = 'QUARANTINED' "
     f"AND stable_source_row_id IS NOT NULL", "0"),
    ("AT-22", "Invalid passenger observations never become canonical passenger flights",
     f"SELECT COUNT(*) FROM {MI}.PASSENGER_FLIGHT_INVALID i JOIN {MI}.PASSENGER_SOURCE_LINEAGE l "
     f"ON l.source_system = i.source_system AND l.stable_source_row_id = i.stable_source_row_id", "0"),
    ("AT-23", "Every accepted rotation link independently satisfies all five validation conditions",
     f"SELECT COUNT(*) FROM {MI}.ROTATION_LINK_VALIDATION v JOIN {MI}.AIRCRAFT_FLIGHT f ON f.flight_id = v.flight_id "
     f"LEFT JOIN {MI}.AIRCRAFT_FLIGHT t ON t.flight_id = v.next_flight_id "
     f"WHERE v.is_accepted_link AND NOT (t.flight_id IS NOT NULL AND t.flight_id <> f.flight_id "
     f"AND t.aircraft_id = f.aircraft_id AND t.flight_departure_date = f.flight_departure_date "
     f"AND t.actual_gate_departure_time_utc >= f.actual_gate_arrival_time_utc "
     f"AND t.departure_airport_code = f.actual_continuity_arrival_code "
     f"AND f.is_cancelled_boolean = FALSE AND t.is_cancelled_boolean = FALSE "
     f"AND f.actual_gate_departure_time_utc IS NOT NULL AND f.actual_gate_arrival_time_utc IS NOT NULL "
     f"AND NOT f.diversion_endpoint_conflict)", "0"),
    ("AT-24", "Every typed rotation anomaly class is exercised by the 1099 fixture day",
     f"SELECT COUNT(DISTINCT rotation_anomaly_class) FROM {MI}.ROTATION_LINK_VALIDATION "
     f"WHERE aircraft_id = 1099 AND selected_local_date = DATE '2026-08-31' "
     f"AND rotation_anomaly_class IS NOT NULL", "11"),
    ("AT-25", "Each cycle component has exactly one representative row",
     f"SELECT COUNT(*) FROM (SELECT cycle_component_id FROM {MI}.ROTATION_LINK_VALIDATION "
     f"WHERE cycle_component_id IS NOT NULL GROUP BY 1 HAVING SUM(IFF(is_cycle_representative,1,0)) <> 1)", "0"),
    ("AT-33", "D-0022: a self-loop is not a cycle component",
     f"SELECT COUNT(*) FROM {MI}.ROTATION_LINK_VALIDATION "
     f"WHERE is_self_loop_link AND cycle_component_id IS NOT NULL", "0"),
    ("AT-34", "D-0022: the self-loop stays classified SELF_LOOP and auditable through its own flag",
     f"SELECT COUNT(*) FROM {MI}.ROTATION_LINK_VALIDATION "
     f"WHERE is_self_loop_link AND rotation_anomaly_class = 'SELF_LOOP'", "1"),
    ("AT-35", "D-0022: every cycle edge stays inside one selected (aircraft, AF-06) chain",
     f"SELECT COUNT(*) FROM {MI}.ROTATION_LINK_VALIDATION v "
     f"JOIN {MI}.AIRCRAFT_FLIGHT t ON t.flight_id = v.next_flight_id "
     f"WHERE v.cycle_component_id IS NOT NULL "
     f"AND (t.aircraft_id IS DISTINCT FROM v.aircraft_id "
     f"OR t.flight_departure_date IS DISTINCT FROM v.selected_local_date)", "0"),
    ("AT-36", "D-0022: exactly one cycle component with two members survives the scoped rule",
     f"SELECT TO_VARCHAR(COUNT(DISTINCT cycle_component_id)) || '/' || TO_VARCHAR(COUNT(*)) "
     f"FROM {MI}.ROTATION_LINK_VALIDATION WHERE cycle_component_id IS NOT NULL", "1/2"),
    ("AT-26", "Exact fulfillment stays separate from heuristic and ambiguous evidence",
     f"SELECT (SELECT COUNT(*) FROM {MI}.FULFILLMENT_EXACT WHERE NOT confirmed_link) "
     f"+ (SELECT COUNT(*) FROM {MI}.FULFILLMENT_CANDIDATE WHERE confirmed_link) "
     f"+ (SELECT COUNT(*) FROM {MI}.FULFILLMENT_AMBIGUOUS_GROUP WHERE confirmed_link)", "0"),
    ("AT-27", "One passenger service can be fulfilled by many actual legs",
     f"SELECT MAX(c) FROM (SELECT passenger_flight_key, COUNT(*) c FROM {MI}.FULFILLMENT_EXACT GROUP BY 1)",
     lambda v: int(v) >= 2),
    ("AT-28", "Marketing and operating carrier roles stay separate on RouteState",
     f"SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE marketing_carrier_internal IS DISTINCT FROM operating_carrier_internal "
     f"AND marketing_airline_id IS NOT DISTINCT FROM operating_airline_id AND marketing_airline_id IS NOT NULL",
     lambda v: int(v) >= 0),
    ("AT-29", "Codeshare-only physical service is visibly unresolved, never guessed",
     f"SELECT physical_service_status FROM {MI}.ROUTE_STATE WHERE schedule_key = 'SYN-SK-CSH_ONLY_900' "
     f"AND knowledge_valid_from = DATE '2026-08-31'", "UNRESOLVED_PHYSICAL_SERVICE"),
    ("AT-30", "An INVALID_ROUTE_KEY observation yields no RouteState: only the one route-valid snapshot does",
     f"SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE schedule_key = 'SYN-SK-CLOCK_BOUNDARY_001'", "1"),
    ("AT-31", "An INVALID_ROUTE_KEY observation still produces exact schedule-key change evidence",
     f"SELECT COUNT(*) FROM {MI}.SCHEDULE_EXACT_CHANGE WHERE schedule_key = 'SYN-SK-CLOCK_BOUNDARY_001' "
     f"AND field_name = 'arrival_station_code_iata'", "2"),
    ("AT-32", "Five raw observations carry an INVALID_ROUTE_KEY and none of them mint a Route",
     f"SELECT (SELECT COUNT(*) FROM {MI}.SCHEDULE_CANONICAL_OBSERVATION WHERE route_key_status = 'INVALID_ROUTE_KEY') * 1000 "
     f"+ (SELECT COUNT(*) FROM {MI}.ROUTE WHERE route_id IS NULL)", "5000"),
)

# HG-01 needs the full DV-43 recomputation; keep it readable rather than inline in the tuple.
HG01_SQL = f"""
SELECT COUNT(*) FROM (
  SELECT s.normalized_row_hash, SHA2(
      MODEL_INPUT.DV43_FIELD('SS-01','VARCHAR',      s.schedule_key)
   || MODEL_INPUT.DV43_FIELD('SS-02','VARCHAR',      s.schedule_key_readable)
   || MODEL_INPUT.DV43_FIELD('SS-03','DATE',         MODEL_INPUT.CANON_DATE(s.publish_date))
   || MODEL_INPUT.DV43_FIELD('SS-04','VARCHAR',      s.marketing_carrier_internal)
   || MODEL_INPUT.DV43_FIELD('SS-05','VARCHAR',      s.operating_carrier_internal)
   || MODEL_INPUT.DV43_FIELD('SS-06','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(s.flight_number))
   || MODEL_INPUT.DV43_FIELD('SS-07','VARCHAR',      s.service_type_iata)
   || MODEL_INPUT.DV43_FIELD('SS-08','DATE',         MODEL_INPUT.CANON_DATE(s.effective_date))
   || MODEL_INPUT.DV43_FIELD('SS-09','DATE',         MODEL_INPUT.CANON_DATE(s.discontinue_date))
   || MODEL_INPUT.DV43_FIELD('SS-10','VARCHAR',      s.departure_station_code_iata)
   || MODEL_INPUT.DV43_FIELD('SS-11','VARCHAR',      s.arrival_station_code_iata)
   || MODEL_INPUT.DV43_FIELD('SS-12','VARCHAR',      s.departure_terminal)
   || MODEL_INPUT.DV43_FIELD('SS-13','VARCHAR',      s.arrival_terminal)
   || MODEL_INPUT.DV43_FIELD('SS-14','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_operating_monday))
   || MODEL_INPUT.DV43_FIELD('SS-15','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_operating_tuesday))
   || MODEL_INPUT.DV43_FIELD('SS-16','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_operating_wednesday))
   || MODEL_INPUT.DV43_FIELD('SS-17','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_operating_thursday))
   || MODEL_INPUT.DV43_FIELD('SS-18','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_operating_friday))
   || MODEL_INPUT.DV43_FIELD('SS-19','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_operating_saturday))
   || MODEL_INPUT.DV43_FIELD('SS-20','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_operating_sunday))
   || MODEL_INPUT.DV43_FIELD('SS-21','VARCHAR',      s.days_pattern)
   || MODEL_INPUT.DV43_FIELD('SS-22','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(s.weekly_frequency))
   || MODEL_INPUT.DV43_FIELD('SS-23','TIME',         MODEL_INPUT.CANON_TIME(s.passenger_departure_utc_time))
   || MODEL_INPUT.DV43_FIELD('SS-24','TIME',         MODEL_INPUT.CANON_TIME(s.passenger_arrival_utc_time))
   || MODEL_INPUT.DV43_FIELD('SS-25','TIME',         MODEL_INPUT.CANON_TIME(s.passenger_departure_local_time))
   || MODEL_INPUT.DV43_FIELD('SS-26','TIME',         MODEL_INPUT.CANON_TIME(s.passenger_arrival_local_time))
   || MODEL_INPUT.DV43_FIELD('SS-27','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(s.arrival_day_indicator))
   || MODEL_INPUT.DV43_FIELD('SS-28','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(s.scheduled_block_minutes))
   || MODEL_INPUT.DV43_FIELD('SS-29','VARCHAR',      s.equipment_subtype_code_iata)
   || MODEL_INPUT.DV43_FIELD('SS-30','FLOAT',        MODEL_INPUT.CANON_FLOAT(s.total_seats))
   || MODEL_INPUT.DV43_FIELD('SS-31','FLOAT',        MODEL_INPUT.CANON_FLOAT(s.first_class_seats))
   || MODEL_INPUT.DV43_FIELD('SS-32','FLOAT',        MODEL_INPUT.CANON_FLOAT(s.business_class_seats))
   || MODEL_INPUT.DV43_FIELD('SS-33','FLOAT',        MODEL_INPUT.CANON_FLOAT(s.premium_economy_seats))
   || MODEL_INPUT.DV43_FIELD('SS-34','FLOAT',        MODEL_INPUT.CANON_FLOAT(s.economy_class_seats))
   || MODEL_INPUT.DV43_FIELD('SS-35','BOOLEAN',      MODEL_INPUT.CANON_BOOL(s.is_codeshare))
   || MODEL_INPUT.DV43_FIELD('SS-36','VARCHAR',      s.codeshare_carrier_internal)
   || MODEL_INPUT.DV43_FIELD('SS-37','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(s.number_of_intermediate_stops))
   || MODEL_INPUT.DV43_FIELD('SS-38','VARCHAR',      s.intermediate_stop_station_codes_iata)
   || MODEL_INPUT.DV43_FIELD('SS-39','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(s.itinerary_variation_identifier))
  , 256) AS recomputed
  FROM {SRC}.SCHEDULE_SNAPSHOT s
) WHERE normalized_row_hash <> recomputed
"""

FINGERPRINT_TABLES: tuple[str, ...] = tuple(sorted(
    set(CONTRACT_OBJECTS.values()) | set(ADDITIONAL_OBJECTS.keys())))


# Non-oracle consistency diagnostics.  These are NOT answers to the eight golden questions and are
# NOT compared to EXPECTED_ANSWERS.yaml as a gate; they are shape checks that tell the orchestrator
# whether the canonical inputs can still carry the frozen manifest.  The independent SQL oracles
# and the RAI queries own the actual comparison.
DIAGNOSTICS: tuple[tuple[str, str], ...] = (
    ("q05_window_exact_change_rows",
     f"SELECT COUNT(*) FROM {MI}.SCHEDULE_EXACT_CHANGE e JOIN {MI}.SCHEDULE_COMPARISON c USING (comparison_id) "
     f"WHERE c.comparison_date BETWEEN DATE '2026-08-10' AND DATE '2026-08-31'"),
    ("q05_window_candidate_evidence_rows",
     f"SELECT (SELECT COUNT(*) FROM {MI}.SCHEDULE_AMENDMENT_CANDIDATE a JOIN {MI}.SCHEDULE_COMPARISON c "
     f"USING (comparison_id) WHERE c.comparison_date BETWEEN DATE '2026-08-10' AND DATE '2026-08-31') "
     f"+ (SELECT COUNT(*) FROM {MI}.SCHEDULE_AMENDMENT_GROUP g JOIN {MI}.SCHEDULE_COMPARISON c "
     f"USING (comparison_id) WHERE c.comparison_date BETWEEN DATE '2026-08-10' AND DATE '2026-08-31') "
     f"+ (SELECT COUNT(*) FROM {MI}.SCHEDULE_AMENDMENT_GROUP_MEMBER m JOIN {MI}.SCHEDULE_COMPARISON c "
     f"USING (comparison_id) WHERE c.comparison_date BETWEEN DATE '2026-08-10' AND DATE '2026-08-31')"),
    ("q03_month_ends_2015_2024",
     f"SELECT COUNT(*) FROM {MI}.MONTH_END_CALENDAR WHERE month_end BETWEEN DATE '2015-01-31' AND DATE '2024-12-31'"),
    ("q07_both_clock_eligible_states",
     f"SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE knowledge_valid_from <= DATE '2026-08-31' "
     f"AND DATE '2026-08-31' < knowledge_valid_to AND operating_effective_date <= DATE '2026-09-07' "
     f"AND DATE '2026-09-07' <= operating_discontinue_date AND is_operating_monday"),
    ("inner_join_loss_events",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_EVENT_ELIGIBLE WHERE would_be_lost_by_inner_join"),
    ("concurrent_route_states_sfo_lax_20260831",
     f"SELECT COUNT(*) FROM {MI}.ROUTE_STATE WHERE route_id = 'SFO->LAX' "
     f"AND knowledge_valid_from <= DATE '2026-08-31' AND DATE '2026-08-31' < knowledge_valid_to"),
    ("open_daily_assignments_using_model_sentinel",
     f"SELECT COUNT(*) FROM {MI}.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT WHERE valid_to = DATE '9999-01-01'"),
)

# Reversible semantic ambiguities resolved here.  Each is visible in the output through a status or
# confidence column and is proposed to the orchestrator as a DECISION_LOG entry.
DECLARED_AMBIGUITIES: tuple[dict[str, str], ...] = (
    {"id": "A1",
     "question": "Is the per-dimension DV-08 resolution status token itself part of the watched set, "
                 "or only the resolved target?",
     "chosen": "The full status token is watched, so UNRESOLVED_NULL_CONFIGURATION -> "
               "UNRESOLVED_MISSING_CONFIGURATION mints a second assignment.",
     "why": "SOURCE_CONTRACT.md says the watched set includes 'the type-resolution outcome of "
            "AH-13'. Both readings leave DV-33 as UNKNOWN_STATE, so no as-of answer changes.",
     "visible_as": "AIRCRAFT_DIMENSION_*_ASSIGNMENT.dimension_resolution_status"},
    {"id": "A2",
     "question": "When is the multi-attribute aircraft_state dimension UNKNOWN_STATE?",
     "chosen": "Only when every one of AH-17..AH-31 is null on the date-visible observation.",
     "why": "DV-33 is defined per dimension, not per attribute; a partially populated state is a "
            "known state with absent facts.",
     "visible_as": "AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.dimension_query_status"},
    {"id": "A3",
     "question": "How are key-shift compatibility components scoped?",
     "chosen": "Signature-scoped: all removals and additions sharing one (SS-04, SS-06, SS-10, "
               "SS-11) signature and participating in at least one overlapping-range pair form one "
               "component.",
     "why": "DV-36 defines its own identity as (comparison, typed signature, sorted removed keys, "
            "sorted added keys). The rule can only over-merge into a LOW-confidence ambiguous "
            "group; it can never assert a false CANDIDATE_UNIQUE.",
     "visible_as": "SCHEDULE_AMENDMENT_GROUP.amendment_candidate_class / amendment_confidence"},
    {"id": "A4",
     "question": "Does a definition-FD violation drop the subseries or keep an attribute-free row?",
     "chosen": "Keep one row per subseries with definition_status = AMBIGUOUS_DEFINITION and null "
               "definition fields, so no definition is invented and no identity disappears.",
     "why": "The contract forbids an invented node link, not the identity itself. Zero rows are "
            "ambiguous in the shipped fixtures, so this branch is currently unexercised.",
     "visible_as": "AIRCRAFT_TYPE_DEFINITION.definition_status / ENGINE_TYPE_DEFINITION.definition_status"},
    {"id": "A5",
     "question": "What happens when a rotation target leg is itself cancelled or missing times?",
     "chosen": "A new typed anomaly TARGET_NOT_OPERATED, ranked last, below the whole DV-25 "
               "vocabulary.",
     "why": "P0-11.3 keeps cancelled and missing-time legs out of the strict operated chain; the "
            "contract's five link conditions do not name the target's own operability. Zero rows "
            "hit this branch in the shipped fixtures.",
     "visible_as": "ROTATION_LINK_VALIDATION.rotation_anomaly_class",
     "status": "implemented but unexercised by the shipped fixtures",
     "cross_reference": "D-0021 R5. TARGET_NOT_OPERATED is outside the DV-25 vocabulary and the "
                        "independent DATA-04b oracle has no branch for it, so a QUERY-ROT versus "
                        "oracle conformance harness will diverge the first time a rotation target "
                        "is cancelled or loses its times. Either add the class to the oracle or "
                        "fence it behind an explicit beyond-the-frozen-vocabulary flag before that "
                        "harness is trusted."},
    {"id": "A6",
     "question": "Where do unmatched actual and passenger observations live?",
     "chosen": "In FULFILLMENT_AMBIGUOUS_GROUP at member grain with a null group_id, member_class "
               "UNMATCHED_ACTUAL / UNMATCHED_PASSENGER and a reason.",
     "why": "SOURCE_CONTRACT.md attaches 'unmatched observations retain a deterministic "
            "source/business identity plus reason' to that same contract row.",
     "visible_as": "FULFILLMENT_AMBIGUOUS_GROUP.member_class / unmatched_reason"},
    {"id": "A7",
     "question": "Does an event whose AH-32 not_for_use is true or null stay eligible?",
     "chosen": "No. It is quarantined with reason NOT_FOR_USE_EVENT or UNKNOWN_ELIGIBILITY_FLAG, "
               "mirroring the explicit AM-15 rule.",
     "why": "AH-32 is contracted as an 'event eligibility/quality flag' and AM-15 states that null "
            "is not silently treated as false. Zero rows hit this branch in the shipped fixtures.",
     "visible_as": "AIRCRAFT_EVENT_QUARANTINE.quarantine_reason"},
    {"id": "A8",
     "question": "Over what scope is a rotation cycle detected?",
     "chosen": "RESOLVED by D-0022: scoped to the selected (AF-02 aircraft, AF-06 local date). "
               "Previously detected globally, which was declared here as a difference; that is "
               "superseded.",
     "why": "Q08 reconstructs one aircraft's chain for one local date, so a cycle is a property of "
            "that chain. A link to a different aircraft or date is DIFFERENT_AIRCRAFT (DV-25 rank "
            "4) or OUTSIDE_SELECTED_DAY (rank 5), which is the actionable diagnosis; because CYCLE "
            "outranks both, global detection could silently mask them. This also aligns with the "
            "independent DATA-04b oracle, but D-0022 decides it on the principle, not on "
            "provenance.",
     "visible_as": "ROTATION_LINK_VALIDATION.cycle_component_id / rotation_anomaly_class",
     "status": "RESOLVED by D-0022, not a declared difference. Implemented and proven zero-movement; "
               "the scoping itself remains unexercised because the shipped fixtures contain no "
               "cross-aircraft or cross-day cycle, so REDTEAM-01 should treat the decision as "
               "reasoned rather than tested.",
     "cross_reference": "D-0022 (supersedes the A8 declaration made under D-0021 R4). Rollback: "
                        "widen the two join predicates on the `edges` CTE in "
                        "data/model_input/60_actual_flight.sql."},
    {"id": "A9",
     "question": "Is a self-loop a cycle component?",
     "chosen": "RESOLVED by D-0022: no. The self-edge is excluded from the cycle graph, so a "
               "self-referencing leg gets no cycle_component_id and is not a representative. The "
               "degenerate case stays queryable through the new is_self_loop_link Boolean.",
     "why": "DV-25 ranks SELF_LOOP above CYCLE precisely to keep the classes disjoint, so counting "
            "a self-edge as a length-one component double-reports one defect under two structural "
            "headings. This was the one live disagreement with the independent oracle: a consumer "
            "counting cycle components previously got 2 here and 1 from the oracle. It now gets 1 "
            "from both.",
     "visible_as": "ROTATION_LINK_VALIDATION.is_self_loop_link (new) / cycle_component_id / "
                   "is_cycle_representative",
     "status": "RESOLVED by D-0022. Exercised by fixture 8101 and no longer divergent: "
               "cycle_component_id and is_cycle_representative moved for exactly that one row, and "
               "the classification projection over all 3900 rows is unchanged.",
     "cross_reference": "D-0022 (supersedes the A9 declaration made under D-0021 R4). Rollback: "
                        "drop the `f.next_flight_id <> f.flight_id` predicate on the `edges` CTE."},
    {"id": "A10",
     "question": "Where does DIVERSION_ENDPOINT_CONFLICT rank?",
     "chosen": "DV-25 rank 8, after BROKEN_CONTINUITY, per the D-0021 R3 decision. Evaluated "
               "whether or not a next link exists, so a diverted leg with a null AF-20 still "
               "reports the conflict rather than a silent TERMINAL_NO_TARGET.",
     "why": "An earlier revision of this layer hoisted the conflict above every link class because "
            "SOURCE_CONTRACT.md:358-359 says the mismatch terminates continuity, which reads as a "
            "property of the leg rather than of the link. That hoist was not contract-forced, it "
            "disagreed with both DV-25 and the oracle, and D-0021 R1 made DV-25 the ordering "
            "authority. Zero fixture movement: 8109 clears all seven higher classes either way, "
            "and the raw evidence survives regardless because diversion_endpoint_conflict is a "
            "standalone Boolean on AIRCRAFT_FLIGHT and ROTATION_LINK_VALIDATION.",
     "visible_as": "ROTATION_LINK_VALIDATION.rotation_anomaly_class / diversion_endpoint_conflict",
     "status": "implemented; the ranking itself is unexercised because nothing competes with it in "
               "the shipped fixtures",
     "cross_reference": "D-0021 R3 / REVIEW-D0021 Axis 4 and U1. Rollback: move the single WHEN "
                        "branch back into the leg tier and realign the oracle."},
)


def verify() -> dict[str, Any]:
    started = time.monotonic()
    gates = [g for g in GATES if g[0] != "HG-01"]
    gates.insert(0, ("HG-01",
                     "DV-43 grammar reproduces every SS-40 normalized row hash in SOURCE",
                     HG01_SQL, "0"))

    union_sql = "\nUNION ALL\n".join(
        f"SELECT {sql_string(gate_id)} AS gate_id, TO_VARCHAR(({sql.strip().rstrip(';')})) AS metric_value"
        for gate_id, _desc, sql, _expected in gates
    )
    rows = query(union_sql, label="gates")
    observed = {row["GATE_ID"]: row["METRIC_VALUE"] for row in rows}

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for gate_id, description, _sql, expected in gates:
        value = observed.get(gate_id)
        if callable(expected):
            ok = value is not None and expected(value)
            expected_text = "predicate"
        else:
            ok = value == expected
            expected_text = expected
        if not ok:
            failures.append(f"{gate_id} ({description}): expected {expected_text}, observed {value!r}")
        results.append({"gate_id": gate_id, "description": description,
                        "expected": expected_text, "observed": value,
                        "status": "passed" if ok else "FAILED"})

    fingerprint_sql = "\nUNION ALL\n".join(
        f"SELECT {sql_string(table)} AS object_name, COUNT(*) AS row_count, "
        f"TO_VARCHAR(HASH_AGG(*)) AS content_fingerprint FROM {MI}.{table}"
        for table in FINGERPRINT_TABLES)
    fingerprints = query(fingerprint_sql + " ORDER BY 1", label="fingerprints")

    metadata = query(
        f"SELECT (SELECT COUNT(*) FROM {DATABASE}.INFORMATION_SCHEMA.COLUMNS "
        f"WHERE table_schema = '{SCHEMA}') AS total_columns, "
        f"(SELECT COUNT(*) FROM {DATABASE}.INFORMATION_SCHEMA.COLUMNS "
        f"WHERE table_schema = '{SCHEMA}' AND comment IS NOT NULL AND comment <> '') AS commented_columns",
        label="metadata")[0]
    if metadata["TOTAL_COLUMNS"] != metadata["COMMENTED_COLUMNS"]:
        failures.append(
            f"MD-01 (every MODEL_INPUT column carries a lineage comment): "
            f"{metadata['COMMENTED_COLUMNS']} of {metadata['TOTAL_COLUMNS']}")
    results.append({"gate_id": "MD-01",
                    "description": "Every MODEL_INPUT column carries a Field-ID or declared-derivation comment",
                    "expected": str(metadata["TOTAL_COLUMNS"]),
                    "observed": str(metadata["COMMENTED_COLUMNS"]),
                    "status": "passed" if metadata["TOTAL_COLUMNS"] == metadata["COMMENTED_COLUMNS"] else "FAILED"})

    tracking = query(f"SHOW TABLES IN SCHEMA {MI}", label="show_tables")
    untracked = sorted(r["name"] for r in tracking if r.get("change_tracking") != "ON")
    if untracked:
        failures.append(f"MD-02 (change tracking on every MODEL_INPUT table): off for {untracked}")
    results.append({"gate_id": "MD-02",
                    "description": "Change tracking is ON for every MODEL_INPUT table bound by MODEL-01",
                    "expected": "0 untracked", "observed": f"{len(untracked)} untracked",
                    "status": "passed" if not untracked else "FAILED"})

    diagnostics_sql = "\nUNION ALL\n".join(
        f"SELECT {sql_string(name)} AS diagnostic, TO_VARCHAR(({sql.strip().rstrip(';')})) AS value"
        for name, sql in DIAGNOSTICS)
    diagnostics = {row["DIAGNOSTIC"]: row["VALUE"]
                   for row in query(diagnostics_sql, label="diagnostics")}

    return {
        "gates": results,
        "failures": failures,
        "consistency_diagnostics": diagnostics,
        "row_counts_and_fingerprints": fingerprints,
        "column_metadata": metadata,
        "verify_seconds": round(time.monotonic() - started, 3),
    }


# Honest notes that are NOT failures but that the orchestrator must see.
BUILD_NOTES: tuple[str, ...] = (
    "CODE_RESOLUTION is row-scoped as the contract requires (resolution_id includes the DV-46 "
    "source row token), so it is by far the largest object at ~546k rows, of which ~122k are "
    "INVALID_INPUT results for legitimately null raw codes. MODEL-01 should decide deliberately "
    "whether to bind it at full grain or to bind CODE_RESOLUTION_CODE plus the per-object resolved "
    "id/status columns that every other table already carries.",
    "AIRCRAFT_EVENT_QUARANTINE is empty. Every quarantine branch is implemented "
    "(MISSING_REQUIRED_FIELD, UNKNOWN_FUTURE_EVENT_DATE, UNKNOWN_ELIGIBILITY_FLAG, "
    "NOT_FOR_USE_EVENT, INELIGIBLE_OR_UNKNOWN_AIRCRAFT, EVENT_BEFORE_EXISTENCE, "
    "EVENT_ON_OR_AFTER_END_OF_LIFE) but the shipped fixtures contain no ineligible aircraft event, "
    "so those branches are unexercised by data. The passenger quarantine path is exercised (1 row).",
    "No ROUTE_STATE is open. The final eligible snapshot 2026-10-26 is declared present and "
    "complete with zero rows, which proves absence for every schedule key, so every knowledge "
    "segment closes. This is a fixture consequence, not a derivation defect: HT-18 multi-open is "
    "demonstrated at a knowledge date (1339 concurrent states on SFO->LAX at 2026-08-31), and the "
    "model open sentinel is exercised by 3992 open daily aircraft assignments.",
    "D-0021: rotation anomaly precedence is NOT derived in this layer. It is contracted by "
    "ATTRIBUTE_AUTHORITY.md:338 (DV-25) and SOURCE_CONTRACT.md:363-366, both shipped in commit "
    "15d8f35 before EXPECTED_ANSWERS.yaml existed, and 8103's suppression is fully determined by "
    "DEMO_QUESTIONS.md:312. An earlier DATA-04a disclosure claimed the contract did not order the "
    "classes and that CYCLE over BACKWARD_TIME was the only ordering yielding an 11-row Q08. Both "
    "claims were false and are retracted: pairing BACKWARD_TIME over CYCLE with component-gated "
    "rather than class-gated suppression gives byte-identical output, so the row count "
    "discriminates neither degree of freedom. The shipped classification is unchanged and correct.",
    "D-0022: cycle detection is scoped to the selected (AF-02, AF-06) chain and a self-loop is not "
    "a cycle component, because Q08 reconstructs one aircraft's chain for one date and DV-25 keeps "
    "SELF_LOOP and CYCLE disjoint. This supersedes the A8 and A9 declarations: they are resolved, "
    "not declared. Measured movement: the classification projection (flight_id, target_token, "
    "rotation_link_status, rotation_anomaly_class, is_accepted_link) over all 3900 rows is "
    "unchanged; cycle_component_id and is_cycle_representative moved for exactly one row (8101); "
    "cycle members went 3 -> 2, distinct components 2 -> 1, representatives 2 -> 1; one new column "
    "is_self_loop_link was added. No frozen result set moved.",
    "Filler schedules disappear at 2026-09-07, which is a complete snapshot carrying only four "
    "rows. That produces 12012 exact presence removals and 12012 unpaired removals at that "
    "comparison. It is outside every frozen Q05 and Q06 window and is the contract-correct reading "
    "of a complete snapshot.",
)


def build_report(apply_result: dict[str, Any] | None,
                 verify_result: dict[str, Any] | None,
                 commands: Sequence[str],
                 wall_seconds: float) -> dict[str, Any]:
    failures = list(verify_result["failures"]) if verify_result else []
    status = "passed" if verify_result is not None and not failures else "failed"
    counts = {row["OBJECT_NAME"]: row["ROW_COUNT"]
              for row in (verify_result or {}).get("row_counts_and_fingerprints", [])}
    return {
        "task_id": "DATA-04a",
        "status": status,
        "build_version": BUILD_VERSION,
        "summary": (
            "Canonical temporal model-input layer in PK_AVIATION_TEMPORAL.MODEL_INPUT: "
            f"{len(CONTRACT_OBJECTS)} SOURCE_CONTRACT.md canonical objects plus "
            f"{len(ADDITIONAL_OBJECTS)} declared derivations, built idempotently with "
            "CREATE OR REPLACE and proven live."),
        "commands": list(commands),
        "artifacts": (
            [f"data/model_input/{name}" for name in SQL_FILES]
            + ["data/build_model_input.py", "data/test_model_input.py",
               "build/task_reports/DATA-04a.json"]),
        "contract_objects_built": {name: {"table": table, "row_count": counts.get(table)}
                                   for name, table in sorted(CONTRACT_OBJECTS.items())},
        "contract_objects_not_built": {},
        "additional_objects": {name: {"reason": reason, "row_count": counts.get(name)}
                               for name, reason in sorted(ADDITIONAL_OBJECTS.items())},
        "evidence": {
            "gates": (verify_result or {}).get("gates", []),
            "row_counts_and_fingerprints": (verify_result or {}).get("row_counts_and_fingerprints", []),
            "column_metadata": (verify_result or {}).get("column_metadata", {}),
            "annotation": (apply_result or {}).get("annotation", {}),
            "consistency_diagnostics": (verify_result or {}).get("consistency_diagnostics", {}),
        },
        "declared_ambiguities": [dict(entry) for entry in DECLARED_AMBIGUITIES],
        "timings_seconds": {
            **((apply_result or {}).get("timings_seconds", {})),
            "verify": (verify_result or {}).get("verify_seconds"),
            "wall_total": round(wall_seconds, 3),
        },
        "open_issues": failures,
        "notes": list(BUILD_NOTES),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", action="store_true", help="print the ordered DDL, no connection")
    parser.add_argument("--apply", action="store_true", help="execute the DDL live and annotate")
    parser.add_argument("--verify", action="store_true", help="run the live gates")
    parser.add_argument("--report", action="store_true",
                        help="write build/task_reports/DATA-04a.json")
    args = parser.parse_args(argv)
    if not (args.plan or args.apply or args.verify or args.report):
        parser.error("choose at least one of --plan, --apply, --verify, --report")

    started = time.monotonic()
    apply_result: dict[str, Any] | None = None
    verify_result: dict[str, Any] | None = None
    commands: list[str] = []

    if args.plan:
        sys.stdout.write(plan())
        commands.append(".venv/bin/python data/build_model_input.py --plan")

    if args.apply:
        commands.append(".venv/bin/python data/build_model_input.py --apply")
        apply_result = apply()
        print(f"apply: {len(SQL_FILES)} SQL files executed; "
              f"{apply_result['annotation']['columns_commented']} columns annotated "
              f"({apply_result['annotation']['traced_to_source_field_id']} to a Field ID, "
              f"{apply_result['annotation']['traced_to_declared_derivation']} to a declared derivation)")

    if args.verify:
        commands.append(".venv/bin/python data/build_model_input.py --verify")
        verify_result = verify()
        for gate in verify_result["gates"]:
            marker = "PASS" if gate["status"] == "passed" else "FAIL"
            print(f"{marker} {gate['gate_id']}  {gate['description']}  "
                  f"expected={gate['expected']} observed={gate['observed']}")
        print(f"\n{sum(1 for g in verify_result['gates'] if g['status'] == 'passed')}"
              f"/{len(verify_result['gates'])} gates passed")

    if args.report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        report = build_report(apply_result, verify_result, commands, time.monotonic() - started)
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        print(f"report written to {REPORT_PATH}")

    if verify_result is not None and verify_result["failures"]:
        for failure in verify_result["failures"]:
            print(f"GATE FAILURE: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
