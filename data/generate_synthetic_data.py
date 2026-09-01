#!/usr/bin/env python3
"""Generate the deterministic synthetic U.S.-domestic aviation source package.

The generator is deliberately a pure local build step.  It reads the reviewed repository
authorities, validates all fixture invariants, writes into a temporary sibling directory, and
publishes only a complete package under build/generated_data/<scale>.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
SEED = "20260901"
GENERATION_DATE = "2026-09-01"
GENERATION_TIMESTAMP = "2026-09-01T00:00:00Z"
SPEC_VERSION = "1.0.0"
EXPECTED_VERSION = "1.1.1"
SERIALIZER_VERSION = "sf-csv-v1"
TYPED_ROW_VERSION = "typed-row-lp-v1"
DV43_VERSION = "dv43-lp-v1"

TABLE_ORDER = (
    "AIRCRAFT_MASTER",
    "AIRCRAFT_HISTORY",
    "AIRCRAFT_CONFIGURATION",
    "SCHEDULE_SNAPSHOT",
    "SCHEDULE_SNAPSHOT_CALENDAR",
    "PASSENGER_FORWARD",
    "PASSENGER_HISTORICAL",
    "AIRCRAFT_FLIGHT",
    "AIRPORT_REFERENCE",
    "AIRLINE_REFERENCE",
)
PREFIX = {
    "AIRCRAFT_MASTER": "AM",
    "AIRCRAFT_HISTORY": "AH",
    "AIRCRAFT_CONFIGURATION": "AC",
    "SCHEDULE_SNAPSHOT": "SS",
    "SCHEDULE_SNAPSHOT_CALENDAR": "SC",
    "PASSENGER_FORWARD": "PF",
    "PASSENGER_HISTORICAL": "PH",
    "AIRCRAFT_FLIGHT": "AF",
    "AIRPORT_REFERENCE": "AP",
    "AIRLINE_REFERENCE": "AL",
}
SOURCE_TOKEN = {name: f"SOURCE.{name}" for name in TABLE_ORDER}
EXPECTED_COUNTS = {
    "smoke": {
        "AIRCRAFT_MASTER": 6,
        "AIRCRAFT_HISTORY": 24,
        "AIRCRAFT_CONFIGURATION": 4,
        "SCHEDULE_SNAPSHOT": 88,
        "SCHEDULE_SNAPSHOT_CALENDAR": 10,
        "PASSENGER_FORWARD": 9,
        "PASSENGER_HISTORICAL": 13,
        "AIRCRAFT_FLIGHT": 24,
        "AIRPORT_REFERENCE": 11,
        "AIRLINE_REFERENCE": 60,
    },
    "demo": {
        "AIRCRAFT_MASTER": 999,
        "AIRCRAFT_HISTORY": 48_000,
        "AIRCRAFT_CONFIGURATION": 2_000,
        "SCHEDULE_SNAPSHOT": 70_000,
        "SCHEDULE_SNAPSHOT_CALENDAR": 10,
        "PASSENGER_FORWARD": 10_000,
        "PASSENGER_HISTORICAL": 10_000,
        "AIRCRAFT_FLIGHT": 3_900,
        "AIRPORT_REFERENCE": 45,
        "AIRLINE_REFERENCE": 100,
    },
}
WHITELIST = ("SFO", "LAX", "LAS", "SEA", "DEN", "ORD", "PHX", "BOS", "MIA")
ANCHOR_AIRCRAFT = {1001, 1002, 1004, 1005, 1098, 1099}
NEGATIVE_FIXTURE_CLASSES = (
    "NF-A01", "NF-A02", "NF-A03", "NF-A04", "NF-A05",
    "NF-S01", "NF-S02", "NF-S03", "NF-S04", "NF-S05", "NF-S06", "NF-S07", "NF-S08", "NF-S09", "NF-S10",
    "NF-F01", "NF-F02", "NF-R01", "NF-R02", "NF-X01", "NF-X02", "NF-E01",
)


@dataclass(frozen=True)
class Field:
    field_id: str
    column: str
    type_tag: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def lp(value: str | bytes) -> bytes:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return str(len(raw)).encode("ascii") + b":" + raw


def canonical_scalar(value: Any, type_tag: str) -> str:
    """Versioned scalar formatter shared by CSV and typed hashes."""
    if value is None:
        raise ValueError("null has no scalar representation")
    base = type_tag.split("(", 1)[0]
    if base == "BOOLEAN":
        if not isinstance(value, bool):
            raise TypeError(f"expected BOOLEAN, got {value!r}")
        return "true" if value else "false"
    if base == "NUMBER":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"expected integral NUMBER, got {value!r}")
        return str(value)
    if base == "FLOAT":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"expected FLOAT, got {value!r}")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite FLOAT is forbidden")
        return repr(number)
    if base == "DATE":
        if isinstance(value, date) and not isinstance(value, datetime):
            value = value.isoformat()
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise TypeError(f"expected ISO DATE, got {value!r}")
        date.fromisoformat(value)
        return value
    if base == "TIME":
        if isinstance(value, time):
            value = value.isoformat()
        if not isinstance(value, str):
            raise TypeError(f"expected ISO TIME, got {value!r}")
        time.fromisoformat(value)
        return value
    if base == "TIMESTAMP_NTZ":
        if isinstance(value, datetime):
            value = value.isoformat()
        if not isinstance(value, str):
            raise TypeError(f"expected ISO TIMESTAMP_NTZ, got {value!r}")
        datetime.fromisoformat(value)
        return value.replace(" ", "T")
    if base == "VARCHAR":
        if not isinstance(value, str):
            raise TypeError(f"expected VARCHAR, got {value!r}")
        if value == "":
            raise ValueError("non-null empty VARCHAR is forbidden by D-0013")
        return value
    raise ValueError(f"unsupported Snowflake type {type_tag}")


def typed_payload(fields: Sequence[Field], row: Mapping[str, Any], source: str | None = None) -> bytes:
    payload = bytearray()
    if source is not None:
        payload.extend(lp(source))
    for field in fields:
        payload.extend(lp(field.field_id))
        payload.extend(lp(field.type_tag))
        value = row[field.column]
        if value is None:
            payload.extend(lp("N"))
        else:
            payload.extend(lp("V"))
            payload.extend(lp(canonical_scalar(value, field.type_tag)))
    return bytes(payload)


def typed_hash(fields: Sequence[Field], row: Mapping[str, Any], source: str | None = None) -> str:
    return sha256_bytes(typed_payload(fields, row, source))


def prf(source_object: str, ordinal: int, field_id: str) -> bytes:
    if not 0 <= ordinal <= 999_999:
        raise ValueError("constructor ordinal outside six-digit namespace")
    token = f"{SEED}|{SOURCE_TOKEN[source_object]}|{ordinal:06d}|{field_id}"
    return hashlib.sha256(token.encode("ascii")).digest()


def parse_contract_fields() -> dict[str, tuple[Field, ...]]:
    text = (ROOT / "SOURCE_CONTRACT.md").read_text(encoding="utf-8")
    matches = re.findall(
        r"^\| ((?:AM|AH|AC|SS|SC|PF|PH|AF|AP|AL)-\d{2}) \| `([^`]+)` \| ([A-Z][A-Z0-9_]*(?:\([^)]*\))?) \|",
        text,
        flags=re.MULTILINE,
    )
    by_prefix: dict[str, dict[str, Field]] = defaultdict(dict)
    for field_id, column, type_tag in matches:
        field = Field(field_id, column, type_tag)
        prior = by_prefix[field_id[:2]].get(field_id)
        if prior is not None and prior != field:
            raise AssertionError(f"conflicting contract row for {field_id}")
        by_prefix[field_id[:2]][field_id] = field
    result = {}
    for table in TABLE_ORDER:
        prefix = PREFIX[table]
        fields = tuple(sorted(by_prefix[prefix].values(), key=lambda field: field.field_id))
        result[table] = fields
    assert sum(map(len, result.values())) == 195
    assert {name: len(result[name]) for name in TABLE_ORDER} == {
        "AIRCRAFT_MASTER": 19,
        "AIRCRAFT_HISTORY": 33,
        "AIRCRAFT_CONFIGURATION": 16,
        "SCHEDULE_SNAPSHOT": 40,
        "SCHEDULE_SNAPSHOT_CALENDAR": 6,
        "PASSENGER_FORWARD": 19,
        "PASSENGER_HISTORICAL": 23,
        "AIRCRAFT_FLIGHT": 20,
        "AIRPORT_REFERENCE": 9,
        "AIRLINE_REFERENCE": 10,
    }
    return result


FIELDS = parse_contract_fields()
FIELD_BY_ID = {field.field_id: field for fields in FIELDS.values() for field in fields}


def row_for(table: str, values: Mapping[str, Any]) -> dict[str, Any]:
    columns = {field.column for field in FIELDS[table]}
    unknown = set(values) - columns
    if unknown:
        raise AssertionError(f"unknown {table} columns: {sorted(unknown)}")
    row = {field.column: None for field in FIELDS[table]}
    row.update(values)
    if set(row) != columns:
        raise AssertionError(f"incomplete {table} row")
    return row


def plus_days(value: str, days: int) -> str:
    return (date.fromisoformat(value) + timedelta(days=days)).isoformat()


def load_expected() -> dict[str, Any]:
    result = yaml.safe_load((ROOT / "EXPECTED_ANSWERS.yaml").read_text(encoding="utf-8"))
    assert result["schema_version"] == EXPECTED_VERSION
    return result


def aircraft_master(scale: str) -> list[dict[str, Any]]:
    def base(aircraft_id: int) -> dict[str, Any]:
        return row_for("AIRCRAFT_MASTER", {
            "aircraft_id": aircraft_id,
            "aircraft_serial_number": f"SYN-SERIAL-{aircraft_id}",
            "aircraft_line_number": f"SYN-LINE-{aircraft_id}",
            "aircraft_order_date": "2014-01-01",
            "aircraft_build_date": "2014-06-01",
            "aircraft_delivery_date": "2014-12-01",
            "aircraft_start_of_life_date": "2025-01-01",
            "aircraft_end_of_life_date": None,
            "aircraft_build_airport_code_iata": "SEA",
            "original_delivery_operator": "SYN-OP-ORIGINAL",
            "apu_type": "SYN-APU-CURRENT",
            "aircraft_width_m": 35.8,
            "operating_maximum_takeoff_weight_lb": 170000,
            "certified_maximum_takeoff_weight_lb": 175000,
            "not_for_use": False,
            "aircraft_roll_out_date": "2014-06-15",
            "aircraft_first_flight_date": "2014-07-01",
            "aircraft_build_airport": "Seattle synthetic build label",
            "original_delivery_operator_category": "SYNTHETIC_DELIVERY",
        })

    overrides = {
        1001: ("2014-01-01", "2014-06-01", "2014-12-01", "2015-01-01", None, "SEA", "Seattle synthetic build label"),
        1002: ("2015-01-01", "2015-06-01", "2015-12-01", "2016-01-01", "2024-07-01", "ORD", "Chicago synthetic build label"),
        1004: ("2018-01-01", "2018-06-01", "2018-12-01", "2019-01-01", None, "DEN", "Denver synthetic build label"),
        1005: ("2024-01-01", "2024-06-01", "2024-12-01", "2025-01-01", None, "SEA", "Seattle synthetic build label"),
        1098: ("2024-01-01", "2024-06-01", "2024-12-01", "2025-01-01", None, "SEA", "Seattle synthetic build label"),
        1099: ("2024-01-01", "2024-06-01", "2024-12-01", "2025-01-01", None, "LAX", "Los Angeles synthetic build label"),
    }
    rows = []
    for aircraft_id, values in overrides.items():
        row = base(aircraft_id)
        for column, value in zip(("aircraft_order_date", "aircraft_build_date", "aircraft_delivery_date", "aircraft_start_of_life_date", "aircraft_end_of_life_date", "aircraft_build_airport_code_iata", "aircraft_build_airport"), values):
            row[column] = value
        rows.append(row)
    if scale == "demo":
        filler = sorted(set(range(1000, 2000)) - {1003} - ANCHOR_AIRCRAFT)
        assert len(filler) == 993
        for i, aircraft_id in enumerate(filler):
            row = base(aircraft_id)
            p = plus_days("2025-01-01", i % 365)
            row.update({
                "aircraft_order_date": p,
                "aircraft_build_date": plus_days(p, 30),
                "aircraft_delivery_date": plus_days(p, 60),
                "aircraft_roll_out_date": plus_days(p, 75),
                "aircraft_first_flight_date": plus_days(p, 90),
                "aircraft_start_of_life_date": plus_days(p, 120),
                "aircraft_build_airport_code_iata": WHITELIST[i % 9],
                "aircraft_build_airport": f"Synthetic build label {WHITELIST[i % 9]}",
            })
            rows.append(row)
    return rows


def aircraft_configuration(scale: str) -> list[dict[str, Any]]:
    anchors = [
        (2001, "SYN-FAMILY-A", "Synthetic narrowbody A", "SYN-SERIES-A", "SYN-TYPE-A", "SYN-MFR-A", "SYN-CLASS-NB", 2, False, "SYN-ENG-MFR-A", "SYN-ENG-FAM-A", "Synthetic turbofan A", "SYN-ENG-SER-A", "SYN-ENGINE-A", "TURBOFAN"),
        (2002, "SYN-FAMILY-B", "Synthetic narrowbody B", "SYN-SERIES-B", "SYN-TYPE-B", "SYN-MFR-B", "SYN-CLASS-NB", 2, False, "SYN-ENG-MFR-A", "SYN-ENG-FAM-A", "Synthetic turbofan A", "SYN-ENG-SER-A", "SYN-ENGINE-A", "TURBOFAN"),
        (2003, "SYN-FAMILY-B", "Synthetic narrowbody B", "SYN-SERIES-B", "SYN-TYPE-B", "SYN-MFR-B", "SYN-CLASS-NB", 2, False, "SYN-ENG-MFR-B", "SYN-ENG-FAM-B", "Synthetic turbofan B", "SYN-ENG-SER-B", "SYN-ENGINE-B", "TURBOFAN"),
        (2005, "SYN-FAMILY-M", "Synthetic mixed-engine test aircraft", "SYN-SERIES-M", "SYN-TYPE-MIXED", "SYN-MFR-M", "SYN-CLASS-WB", 4, True, "SYN-ENG-MFR-M", "SYN-ENG-FAM-M", "Synthetic reported mixed engine", "SYN-ENG-SER-M", "SYN-ENGINE-MIXED-REPORTED", "TURBOFAN"),
    ]
    columns = [field.column for field in FIELDS["AIRCRAFT_CONFIGURATION"][:-1]]
    rows = [row_for("AIRCRAFT_CONFIGURATION", dict(zip(columns, values)) | {"publish_date": "2026-08-31"}) for values in anchors]
    if scale == "demo":
        for i in range(1996):
            rows.append(row_for("AIRCRAFT_CONFIGURATION", {
                "aircraft_configuration_id": 300000 + i,
                "aircraft_family": f"SYN-FAMILY-FILL-{i}",
                "aircraft_type": f"Synthetic filler aircraft type {i}",
                "aircraft_series": f"SYN-SERIES-FILL-{i}",
                "aircraft_subseries": f"SYN-TYPE-FILL-{i}",
                "aircraft_manufacturer": f"SYN-MFR-FILL-{i}",
                "aircraft_design_class": "SYN-CLASS-FILL",
                "engine_count": 2,
                "has_multiple_engine_types": False,
                "engine_manufacturer": f"SYN-ENG-MFR-FILL-{i}",
                "engine_family": f"SYN-ENG-FAM-FILL-{i}",
                "engine_type": f"Synthetic filler engine type {i}",
                "engine_series": f"SYN-ENG-SER-FILL-{i}",
                "engine_subseries": f"SYN-ENGINE-FILL-{i}",
                "engine_propulsion_type": "TURBOFAN",
                "publish_date": "2026-08-31",
            }))
    return rows


def history_template(history_id: int, aircraft_id: int, sequence: int, event_date: str) -> dict[str, Any]:
    return row_for("AIRCRAFT_HISTORY", {
        "aircraft_history_id": history_id,
        "aircraft_id": aircraft_id,
        "row_sequence_number": sequence,
        "event_sequence_number": sequence,
        "start_event_date": event_date,
        "end_event_date": None,
        "is_current": False,
        "start_event": "SYN-OBSERVATION",
        "start_aircraft_status": "In Service",
        "end_event": None,
        "end_aircraft_status": None,
        "event_source": "SYNTHETIC_FIXTURE",
        "aircraft_configuration_id": 2001,
        "aircraft_code_iata": "SA1",
        "aircraft_code_icao": "SYN1",
        "aircraft_value_sub_series": "SYN-TYPE-A",
        "aircraft_registration_number": f"SYN-REG-{aircraft_id}",
        "aircraft_transponder_code": f"SYN-XPDR-{aircraft_id}",
        "aircraft_registration_country_code_iso": "US",
        "aircraft_registration_region": "SYN-US",
        "aircraft_cargo": "PASSENGER",
        "storage_location": None,
        "storage_airport_code_iata": None,
        "base_airport": "Synthetic base",
        "base_airport_code_iata": "SFO",
        "base_city": "Synthetic city",
        "base_country": "United States",
        "apu_type": None,
        "aircraft_width_m": 35.0,
        "operating_maximum_takeoff_weight_lb": 165000,
        "certified_maximum_takeoff_weight_lb": 170000,
        "not_for_use": False,
        "publish_date": "2026-08-31",
    })


def apply_variant(row: dict[str, Any], variant: str) -> None:
    variants = {
        "A/A": (2001, "SA1", "SYN1", "SYN-TYPE-A"),
        "B/A": (2002, "SB1", "SYN2", "SYN-TYPE-B"),
        "B/B": (2003, "SB1", "SYN2", "SYN-TYPE-B"),
        "MIXED": (2005, "SM1", "SYN5", "SYN-TYPE-MIXED"),
        "GAP_NULL": (None, None, None, None),
        "GAP_MISSING": (999999, None, None, None),
    }
    for column, value in zip(("aircraft_configuration_id", "aircraft_code_iata", "aircraft_code_icao", "aircraft_value_sub_series"), variants[variant]):
        row[column] = value


def aircraft_history(scale: str, masters: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    inventory = [
        (101001,1001,"2015-01-01",10,"A/A","In Service"), (101003,1001,"2018-03-01",10,"A/A","Storage"),
        (101004,1001,"2018-04-15",10,"A/A","In Service"), (101005,1001,"2019-01-01",10,"B/A","In Service"),
        (101008,1001,"2020-06-01",5,"B/A","Maintenance"), (101009,1001,"2020-06-01",10,"B/A","In Service"),
        (101010,1001,"2020-06-01",20,"B/A","Storage"), (101011,1001,"2020-06-01",30,"B/A","In Service"),
        (101020,1001,"2020-06-01",40,"B/A","In Service"), (101021,1001,"2021-02-01",10,"B/A","In Service"),
        (101022,1001,"2021-03-01",10,"B/A","In Service"), (101023,1001,"2021-03-01",20,"B/A","In Service"),
        (101024,1001,"2021-03-01",30,"B/A","In Service"), (101007,1001,"2021-07-01",10,"B/B","In Service"),
        (102001,1002,"2016-01-01",10,"A/A","In Service"), (102002,1002,"2020-01-01",10,"A/A","Storage"),
        (102004,1002,"2022-05-01",10,"GAP_NULL","Storage"), (102005,1002,"2022-06-01",10,"GAP_MISSING","Storage"),
        (102006,1002,"2022-07-01",10,"A/A","Storage"), (102099,1002,"2023-01-01",10,"A/A","Storage"),
        (104001,1004,"2020-01-01",10,"A/A","Maintenance"), (105001,1005,"2025-01-01",10,"MIXED","In Service"),
        (109801,1098,"2025-01-01",10,"B/B","In Service"), (109901,1099,"2025-01-01",10,"B/B","In Service"),
    ]
    rows: list[dict[str, Any]] = []
    prior: dict[int, dict[str, Any]] = {}
    base_codes = {1001:"SFO",1002:"SEA",1004:"PHX",1005:"ORD",1098:"LAX",1099:"SFO"}
    for history_id, aircraft_id, event_date, seq, variant, status in inventory:
        row = history_template(history_id, aircraft_id, seq, event_date)
        if aircraft_id in prior:
            # Only the contracted state payload carries forward.  Provenance and audit fields are
            # row-local template values, so the deliberately irrelevant AH-12 cannot leak.
            for field_number in range(17, 32):
                column = FIELD_BY_ID[f"AH-{field_number:02d}"].column
                row[column] = prior[aircraft_id][column]
        row.update({"start_aircraft_status":status})
        row["base_airport_code_iata"] = base_codes[aircraft_id]
        apply_variant(row, variant)
        if history_id == 101003: row.update(storage_location="SYN-AP-LAX", storage_airport_code_iata="LAX")
        if history_id == 101004: row.update(storage_location=None, storage_airport_code_iata=None)
        if history_id == 101020: row["event_source"] = "SYNTHETIC_IRRELEVANT"
        if history_id in {101021,101022,101024}: row["apu_type"] = "SYN-APU-B"
        if history_id == 101023: row["apu_type"] = None
        if history_id == 102002: row.update(storage_location="SYN-AP-DEN", storage_airport_code_iata="DEN")
        if history_id == 102099: row["end_event_date"] = "9999-12-31"
        prior[aircraft_id] = dict(row)
        rows.append(row)
    if scale == "demo":
        master_by_id = {row["aircraft_id"]: row for row in masters}
        filler = sorted(set(master_by_id) - ANCHOR_AIRCRAFT)
        used = {row["aircraft_history_id"] for row in rows}
        available = iter(value for value in range(101000, 200000) if value not in used)
        for i, aircraft_id in enumerate(filler):
            count = 49 if i < 312 else 48
            for j in range(count):
                history_id = next(available)
                row = history_template(history_id, aircraft_id, j + 1, plus_days(master_by_id[aircraft_id]["aircraft_start_of_life_date"], j))
                config_index = (i + j) % 1996
                row.update({
                    "aircraft_configuration_id": 300000 + config_index,
                    "aircraft_code_iata": f"SYN-SERIES-FILL-{config_index}",
                    "aircraft_code_icao": f"SYN-SUBTYPE-FILL-{config_index}",
                    "aircraft_value_sub_series": f"SYN-TYPE-FILL-{config_index}",
                })
                rows.append(row)
    return rows


def schedule_rows(scale: str, expected: Mapping[str, Any]) -> list[dict[str, Any]]:
    universe = expected["scope"]["schedule_source_universe"]
    route_by_key = {row["schedule_key"]: row for row in expected["scope"]["anchored_schedule_routes"]}
    field_by_column = {field.column: field for field in FIELDS["SCHEDULE_SNAPSHOT"]}
    rows: list[dict[str, Any]] = []

    def complete(values: Mapping[str, Any], ordinal: int, *, variation: int | None = None) -> dict[str, Any]:
        row = row_for("SCHEDULE_SNAPSHOT", values)
        row["schedule_key_readable"] = f"SYN-READABLE|{row['schedule_key']}|{row['publish_date']}"
        if variation is None:
            digest = prf("SCHEDULE_SNAPSHOT", ordinal, "SS-39")
            variation = 9000 + int.from_bytes(digest[:2], "big") % 1000
        row["itinerary_variation_identifier"] = variation
        hash_fields = FIELDS["SCHEDULE_SNAPSHOT"][:-1]
        row["normalized_row_hash"] = typed_hash(hash_fields, row)
        return row

    canonical: list[dict[str, Any]] = []
    for anchor in universe["source_anchors"]:
        route = route_by_key[anchor["schedule_key"]]
        for publish_date, present in anchor["presence_by_complete_snapshot"].items():
            if not present:
                continue
            watched = dict(universe["common_ss04_through_ss38"])
            watched.update({
                "flight_number": route["flight_number"],
                "departure_station_code_iata": route["planned_origin_iata"],
                "arrival_station_code_iata": route["planned_destination_iata"],
            })
            watched.update(anchor["fixed_overrides"])
            for transition in sorted(anchor["content_transitions"], key=lambda item: item["effective_publish_date"]):
                if transition["effective_publish_date"] <= publish_date:
                    watched[transition["field_name"]] = transition["new_value"]
            values = {"schedule_key": anchor["schedule_key"], "publish_date": publish_date} | watched
            ordinal = len(canonical)
            canonical.append(complete(values, ordinal, variation=9000 + ordinal))
    assert len(canonical) == 81
    rows.extend(canonical)

    base = next(row for row in canonical if row["schedule_key"] == "SYN-SK-BASE_100" and row["publish_date"] == "2026-08-03")
    v02 = dict(base)
    v02["weekly_frequency"] = 0
    v02["itinerary_variation_identifier"] = 9998
    v02["normalized_row_hash"] = typed_hash(FIELDS["SCHEDULE_SNAPSHOT"][:-1], v02)
    rows.extend((v02, dict(base)))

    common = dict(universe["common_ss04_through_ss38"])
    diagnostics = [
        ("SYN-SK-DIAG-TOTAL-MISMATCH","SYN-MKT-DIAG",790,"SFO","LAX",{"total_seats":181.0,"first_class_seats":8.0,"business_class_seats":20.0,"premium_economy_seats":20.0,"economy_class_seats":152.0}),
        ("SYN-SK-DIAG-NULL-CABIN","SYN-ZZZ",791,"LAX","LAS",{"total_seats":180.0,"first_class_seats":None,"business_class_seats":20.0,"premium_economy_seats":20.0,"economy_class_seats":152.0}),
        ("SYN-SK-DIAG-NEGATIVE-CABIN","SYN-DUP",792,"SEA","DEN",{"total_seats":180.0,"first_class_seats":-1.0,"business_class_seats":20.0,"premium_economy_seats":20.0,"economy_class_seats":152.0}),
        ("SYN-SK-DIAG-PREMIUM-EXCEEDS",None,793,"BOS","MIA",{"total_seats":180.0,"first_class_seats":8.0,"business_class_seats":20.0,"premium_economy_seats":40.0,"economy_class_seats":30.0}),
        ("SYN-SK-UTC-UNRESOLVED","SYN-MKT-DIAG",794,"ORD","MIA",{"passenger_departure_utc_time":"23:00:00","passenger_arrival_utc_time":"01:00:00","passenger_departure_local_time":"23:00:00","passenger_arrival_local_time":"01:00:00","arrival_day_indicator":1}),
    ]
    for offset, (key, marketing, flight, origin, destination, overrides) in enumerate(diagnostics):
        watched = common | {
            "marketing_carrier_internal": marketing,
            "operating_carrier_internal": "SYN-OP-DIAG",
            "flight_number": flight,
            "effective_date": "2026-09-01",
            "discontinue_date": "2026-09-06",
            "departure_station_code_iata": origin,
            "arrival_station_code_iata": destination,
        } | overrides
        rows.append(complete({"schedule_key":key,"publish_date":"2026-10-19"} | watched, 83 + offset))

    if scale == "demo":
        august = ("2026-08-03","2026-08-10","2026-08-17","2026-08-24","2026-08-31")
        for i in range(12_000):
            watched = common | {
                "marketing_carrier_internal": f"SYN-MKT-FILL-{i % 16:02d}",
                "operating_carrier_internal": f"SYN-OP-FILL-{i % 16:02d}",
                "flight_number": 1700 + i % 100,
                "effective_date": "2035-01-01",
                "discontinue_date": "2035-12-31",
                "departure_station_code_iata": WHITELIST[i % 9],
                "arrival_station_code_iata": WHITELIST[(i + 1) % 9],
            }
            for d, publish_date in enumerate(august):
                ordinal = 100000 + 5 * i + d
                rows.append(complete({"schedule_key":f"SYN-SK-FILL-{i:05d}","publish_date":publish_date} | watched, ordinal))
        for i in range(9_912):
            watched = common | {
                "marketing_carrier_internal": f"SYN-MKT-FILL-{i % 16:02d}",
                "operating_carrier_internal": f"SYN-OP-FILL-{i % 16:02d}",
                "flight_number": 1800 + i % 100,
                "departure_station_code_iata": WHITELIST[i % 9],
                "arrival_station_code_iata": WHITELIST[(i + 1) % 9],
            }
            rows.append(complete({"schedule_key":f"SYN-SK-INCOMPLETE-{i:04d}","publish_date":"2026-10-19"} | watched, 200000 + i))
    assert all(field.column in row for row in rows for field in FIELDS["SCHEDULE_SNAPSHOT"])
    assert set(field_by_column) == set(rows[0])
    return rows


def snapshot_calendar(scale: str) -> list[dict[str, Any]]:
    data = [
        ("2026-08-03",True,True,"SC-20260803-COMPLETE",17,12017,"COMPLETE_VALIDATED"),
        ("2026-08-10",True,True,"SC-20260810-COMPLETE",14,12014,"COMPLETE_VALIDATED"),
        ("2026-08-17",True,True,"SC-20260817-COMPLETE",15,12015,"COMPLETE_VALIDATED"),
        ("2026-08-24",True,True,"SC-20260824-COMPLETE",16,12016,"COMPLETE_VALIDATED"),
        ("2026-08-31",True,True,"SC-20260831-COMPLETE",16,12016,"COMPLETE_VALIDATED"),
        ("2026-09-07",True,True,"SC-20260907-COMPLETE",4,4,"COMPLETE_VALIDATED"),
        ("2026-10-05",True,True,"SC-20261005-COMPLETE",1,1,"COMPLETE_VALIDATED"),
        ("2026-10-12",False,False,"SC-20261012-MISSING",0,0,"MISSING_DECLARED"),
        ("2026-10-19",True,False,"SC-20261019-INCOMPLETE",5,9917,"INCOMPLETE_RETAINED"),
        ("2026-10-26",True,True,"SC-20261026-COMPLETE",0,0,"COMPLETE_VALIDATED"),
    ]
    rows = []
    for expected_date, present, complete, lineage, smoke_count, demo_count, status in data:
        rows.append(row_for("SCHEDULE_SNAPSHOT_CALENDAR", {
            "expected_publish_date": expected_date,
            "is_present": present,
            "is_complete": complete,
            "source_lineage_id": lineage,
            "observed_row_count": smoke_count if scale == "smoke" else demo_count,
            "validation_status": status,
        }))
    return rows


def forward_template(source_id: int | None) -> dict[str, Any]:
    return row_for("PASSENGER_FORWARD", {
        "forward_source_row_id": source_id,
        "marketing_carrier_internal":"SYN-MKT-FUL", "operating_carrier_internal":"SYN-OP-FUL",
        "flight_number":700, "operating_date":"2026-08-31", "publish_date":"2026-08-01",
        "service_type_iata":"J", "departure_station_code_iata":"SFO", "arrival_station_code_iata":"LAX",
        "passenger_departure_time_local":"2026-08-31T09:00:00", "passenger_arrival_time_local":"2026-08-31T11:00:00",
        "passenger_departure_time_utc":"2026-08-31T16:00:00", "passenger_arrival_time_utc":"2026-08-31T18:00:00",
        "arrival_day_indicator":0, "equipment_subtype_code_iata":"SYN-EQ-NB", "total_seats":180,
        "is_codeshare":False, "number_of_intermediate_stops":0, "intermediate_stop_station_codes_iata":None,
    })


def passenger_forward(scale: str) -> list[dict[str, Any]]:
    definitions = [
        (6001,{"marketing_carrier_internal":"SYN-MKT-A","operating_carrier_internal":"SYN-OP-A","flight_number":700}),
        (6002,{"marketing_carrier_internal":"SYN-MKT-A","operating_carrier_internal":"SYN-OP-A","flight_number":701,"departure_station_code_iata":"LAX","arrival_station_code_iata":"LAS"}),
        (6101,{"flight_number":722,"departure_station_code_iata":"SEA","arrival_station_code_iata":"DEN"}),
        (6102,{"flight_number":723,"departure_station_code_iata":"BOS","arrival_station_code_iata":"MIA"}),
        (6103,{"flight_number":723,"departure_station_code_iata":"ORD","arrival_station_code_iata":"MIA","number_of_intermediate_stops":1,"intermediate_stop_station_codes_iata":"BOS"}),
        (6199,{"flight_number":727,"departure_station_code_iata":"SFO","arrival_station_code_iata":None}),
        (None,{"flight_number":726,"departure_station_code_iata":"MIA","arrival_station_code_iata":"BOS"}),
        (None,{"flight_number":728,"departure_station_code_iata":"MIA","arrival_station_code_iata":None}),
        (6201,{"marketing_carrier_internal":"SYN-MKT-CLOCK","operating_carrier_internal":"SYN-OP-CLOCK","flight_number":730,"operating_date":"2026-09-07","departure_station_code_iata":"SFO","arrival_station_code_iata":"LAX","passenger_departure_time_local":"2026-09-07T08:00:00","passenger_arrival_time_local":"2026-09-07T10:00:00","passenger_departure_time_utc":"2026-09-07T15:00:00","passenger_arrival_time_utc":"2026-09-07T17:00:00"}),
    ]
    rows = []
    for source_id, overrides in definitions:
        row = forward_template(source_id)
        row.update(overrides)
        rows.append(row)
    if scale == "demo":
        anchors = {row["forward_source_row_id"] for row in rows if row["forward_source_row_id"] is not None}
        ids = iter(value for value in range(5000,8000) if value not in anchors)
        for i in range(9_991):
            c, f, d = i % 16, (i // 16) % 100, i // 1600
            source_id = next(ids) if i < 2_993 else None
            operating_date = plus_days("2035-01-01", d)
            row = forward_template(source_id)
            row.update({
                "marketing_carrier_internal":f"SYN-MKT-FILL-{c:02d}", "operating_carrier_internal":f"SYN-OP-FILL-{c:02d}",
                "flight_number":2700+f, "operating_date":operating_date, "publish_date":"2034-12-01",
                "departure_station_code_iata":WHITELIST[d % 9], "arrival_station_code_iata":WHITELIST[(d+1) % 9],
                "passenger_departure_time_local":f"{operating_date}T09:00:00", "passenger_arrival_time_local":f"{operating_date}T11:00:00",
                "passenger_departure_time_utc":f"{operating_date}T16:00:00", "passenger_arrival_time_utc":f"{operating_date}T18:00:00",
            })
            rows.append(row)
    return rows


def historical_template(source_id: int | None) -> dict[str, Any]:
    return row_for("PASSENGER_HISTORICAL", {
        "historical_source_row_id":source_id, "schedule_key":None, "publish_date":"2026-08-01", "operating_date":"2026-08-31",
        "marketing_carrier_internal":"SYN-MKT-FUL", "operating_carrier_internal":"SYN-OP-FUL", "flight_number":700,
        "service_type_iata":"J", "effective_date":"2026-08-01", "departure_station_code_iata":"SFO", "arrival_station_code_iata":"LAX",
        "passenger_departure_local_time":"09:00:00", "passenger_arrival_local_time":"11:00:00",
        "passenger_departure_utc_time":"16:00:00", "passenger_arrival_utc_time":"18:00:00",
        "departure_utc_offset_minutes":-420.0, "arrival_utc_offset_minutes":-420.0, "arrival_day_indicator":0,
        "equipment_subtype_code_iata":"SYN-EQ-NB", "total_seats":180.0, "is_codeshare":False,
        "number_of_intermediate_stops":0, "intermediate_stop_station_codes_iata":None,
    })


def passenger_historical(scale: str) -> list[dict[str, Any]]:
    definitions = [
        (5001,{"schedule_key":"SYN-SK-HIST_700","marketing_carrier_internal":"SYN-MKT-A","operating_carrier_internal":"SYN-OP-A","flight_number":700}),
        (5101,{"flight_number":720}),
        (5102,{"flight_number":721,"arrival_station_code_iata":"LAS","number_of_intermediate_stops":1,"intermediate_stop_station_codes_iata":"LAX"}),
        (5103,{"flight_number":721,"arrival_station_code_iata":"LAS","number_of_intermediate_stops":1,"intermediate_stop_station_codes_iata":"LAX"}),
        (7200,{"flight_number":725}),
        (7301,{"operating_date":"2026-03-08","marketing_carrier_internal":"SYN-MKT-CLOCK","operating_carrier_internal":"SYN-OP-CLOCK","flight_number":731,"passenger_departure_local_time":"01:30:00","passenger_arrival_local_time":"01:55:00","passenger_departure_utc_time":"09:30:00","passenger_arrival_utc_time":"09:55:00","departure_utc_offset_minutes":-480.0,"arrival_utc_offset_minutes":-480.0}),
        (7302,{"operating_date":"2026-03-08","marketing_carrier_internal":"SYN-MKT-CLOCK","operating_carrier_internal":"SYN-OP-CLOCK","flight_number":732,"passenger_departure_local_time":"03:30:00","passenger_arrival_local_time":"03:55:00","passenger_departure_utc_time":"10:30:00","passenger_arrival_utc_time":"10:55:00"}),
        (7303,{"operating_date":"2026-11-01","marketing_carrier_internal":"SYN-MKT-CLOCK","operating_carrier_internal":"SYN-OP-CLOCK","flight_number":733,"departure_station_code_iata":"BOS","arrival_station_code_iata":"MIA","passenger_departure_local_time":"01:30:00","passenger_arrival_local_time":"01:50:00","passenger_departure_utc_time":"05:30:00","passenger_arrival_utc_time":"05:50:00","departure_utc_offset_minutes":-240.0,"arrival_utc_offset_minutes":-240.0}),
        (7304,{"operating_date":"2026-11-01","marketing_carrier_internal":"SYN-MKT-CLOCK","operating_carrier_internal":"SYN-OP-CLOCK","flight_number":734,"departure_station_code_iata":"BOS","arrival_station_code_iata":"MIA","passenger_departure_local_time":"01:30:00","passenger_arrival_local_time":"01:50:00","passenger_departure_utc_time":"06:30:00","passenger_arrival_utc_time":"06:50:00","departure_utc_offset_minutes":-300.0,"arrival_utc_offset_minutes":-300.0}),
        (7305,{"operating_date":"2026-07-15","marketing_carrier_internal":"SYN-MKT-CLOCK","operating_carrier_internal":"SYN-OP-CLOCK","flight_number":735,"departure_station_code_iata":"PHX","arrival_station_code_iata":"DEN","passenger_departure_local_time":"12:00:00","passenger_arrival_local_time":"13:00:00","passenger_departure_utc_time":"19:00:00","passenger_arrival_utc_time":"20:00:00"}),
        (7306,{"operating_date":"2026-09-07","marketing_carrier_internal":"SYN-MKT-CLOCK","operating_carrier_internal":"SYN-OP-CLOCK","flight_number":736,"passenger_departure_local_time":"23:30:00","passenger_arrival_local_time":"01:15:00","passenger_departure_utc_time":"06:30:00","passenger_arrival_utc_time":"08:15:00","arrival_day_indicator":1}),
        (7309,{"operating_date":"2026-09-07","marketing_carrier_internal":"SYN-MKT-UNIT","operating_carrier_internal":"SYN-OP-UNIT","flight_number":739,"departure_station_code_iata":"ORD","arrival_station_code_iata":"DEN","passenger_departure_local_time":"12:00:00","passenger_arrival_local_time":"14:00:00","passenger_departure_utc_time":"12:00:00","passenger_arrival_utc_time":"14:00:00","departure_utc_offset_minutes":0.0,"arrival_utc_offset_minutes":0.0}),
        (7310,{"operating_date":"2026-09-07","marketing_carrier_internal":"SYN-MKT-UNIT","operating_carrier_internal":"SYN-OP-UNIT","flight_number":740,"passenger_departure_local_time":"23:30:00","passenger_arrival_local_time":"01:15:00","passenger_departure_utc_time":"21:30:00","passenger_arrival_utc_time":"23:15:00","departure_utc_offset_minutes":120.0,"arrival_utc_offset_minutes":120.0,"arrival_day_indicator":1}),
    ]
    rows=[]
    for source_id, overrides in definitions:
        row=historical_template(source_id); row.update(overrides); rows.append(row)
    if scale == "demo":
        anchors={row["historical_source_row_id"] for row in rows if row["historical_source_row_id"] is not None}
        ids=iter(value for value in range(5000,8000) if value not in anchors)
        for i in range(9_987):
            c,f,d=i%16,(i//16)%100,i//1600
            source_id=next(ids) if i<2_987 else None
            operating_date=plus_days("2036-01-01",d)
            row=historical_template(source_id)
            row.update({"publish_date":"2035-12-01","effective_date":"2036-01-01","operating_date":operating_date,
                "marketing_carrier_internal":f"SYN-MKT-FILL-{c:02d}","operating_carrier_internal":f"SYN-OP-FILL-{c:02d}","flight_number":2800+f,
                "departure_station_code_iata":WHITELIST[d%9],"arrival_station_code_iata":WHITELIST[(d+1)%9],
                "passenger_departure_local_time":"09:00:00","passenger_arrival_local_time":"11:00:00","passenger_departure_utc_time":"09:00:00","passenger_arrival_utc_time":"11:00:00",
                "departure_utc_offset_minutes":0.0,"arrival_utc_offset_minutes":0.0,"arrival_day_indicator":0})
            rows.append(row)
    return rows


def actual_template(flight_id: int) -> dict[str, Any]:
    return row_for("AIRCRAFT_FLIGHT", {
        "flight_id":flight_id, "aircraft_id":1100, "operating_carrier_code":"SYN-OP-FUL", "marketing_carrier_code":"SYN-MKT-FUL",
        "flight_number":"700", "flight_departure_date":"2026-08-31", "flight_departure_date_utc":"2026-08-31",
        "departure_airport_code":"SYN-AP-SFO", "arrival_airport_code":"SYN-AP-LAX", "diverted_airport_code":None,
        "is_cancelled":0, "is_diverted":0, "actual_gate_departure_time_utc":"2026-08-31T14:00:00",
        "actual_gate_arrival_time_utc":"2026-08-31T15:00:00", "actual_gate_departure_time_local":None,
        "actual_gate_arrival_time_local":None, "aircraft_type":"Synthetic narrowbody B", "aircraft_code_iata":"SB1",
        "aircraft_family":"SYN-FAMILY-B", "next_flight_id":None,
    })


def aircraft_flights(scale: str, masters: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    definitions = [
        (5101,1100,"720","2026-08-31","2026-08-31","SFO","LAX","14:00:00","15:30:00",None,{}),
        (5102,1100,"721","2026-08-31","2026-08-31","SFO","LAX","14:00:00","15:30:00",None,{}),
        (5103,1100,"721","2026-08-31","2026-08-31","LAX","LAS","16:00:00","17:00:00",None,{}),
        (7101,1100,"722","2026-08-31","2026-08-31","SEA","DEN","14:00:00","17:00:00",None,{}),
        (7102,1100,"723","2026-08-31","2026-08-31","BOS","MIA","14:00:00","17:00:00",None,{}),
        (7199,1100,"724","2026-08-31","2026-08-31","ORD","PHX","14:00:00","17:00:00",None,{}),
        (7200,1100,"725","2026-08-31","2026-08-31","SFO","LAS","14:00:00","16:00:00",None,{"diverted_airport_code":"SYN-AP-LAS","is_diverted":1}),
        (8001,1001,"741","2026-08-31","2026-09-01","SFO","LAX","00:30:00","02:00:00",8002,{}),
        (8002,1001,"742","2026-08-31","2026-09-01","LAX","LAS","02:45:00","04:00:00",8003,{"aircraft_type":"Synthetic narrowbody A"}),
        (8003,1001,"743","2026-08-31","2026-09-01","LAS","SFO","04:45:00","06:15:00",None,{}),
        (8101,1099,"751","2026-08-31","2026-08-31","SFO","LAX","14:00:00","15:00:00",8101,{}),
        (8102,1099,"752","2026-08-31","2026-08-31","SFO","LAX","14:00:00","15:00:00",8103,{}),
        (8103,1099,"753","2026-08-31","2026-08-31","LAX","SFO","16:00:00","17:30:00",8102,{}),
        (8104,1099,"754","2026-08-31","2026-08-31","SEA","DEN","15:00:00","18:00:00",8999,{}),
        (8105,1099,"755","2026-08-31","2026-08-31","LAX","LAS","16:00:00","17:00:00",8205,{}),
        (8106,1099,"756","2026-08-31","2026-08-31","LAS","SFO","18:00:00","19:30:00",8206,{}),
        (8107,1099,"757","2026-08-31","2026-08-31","SFO","LAX","20:00:00","21:30:00",8101,{}),
        (8108,1099,"758","2026-08-31","2026-08-31","SFO","LAX","14:00:00","15:30:00",8107,{}),
        (8109,1099,"759","2026-08-31","2026-08-31","SFO","LAS","14:00:00","16:00:00",8106,{"diverted_airport_code":"SYN-AP-LAX","is_diverted":1}),
        (8110,1099,"760","2026-08-31","2026-08-31","SFO","LAX","14:00:00","15:30:00",None,{"is_cancelled":1}),
        (8111,1099,"761","2026-08-31","2026-08-31","SFO","LAX",None,None,None,{}),
        (8112,1099,"762","2026-08-31","2026-08-31","SFO","LAX","22:00:00","23:30:00",None,{"is_cancelled":2}),
        (8205,1098,"765","2026-08-31","2026-08-31","LAX","LAS","18:00:00","19:00:00",None,{}),
        (8206,1099,"766","2026-09-01","2026-09-01","SFO","LAX","15:00:00","16:30:00",None,{}),
    ]
    rows=[]
    for flight_id,aircraft_id,number,local_date,utc_date,origin,destination,depart,arrive,next_id,overrides in definitions:
        row=actual_template(flight_id)
        timestamp_date=utc_date
        row.update({"aircraft_id":aircraft_id,"flight_number":number,"flight_departure_date":local_date,"flight_departure_date_utc":utc_date,
            "departure_airport_code":f"SYN-AP-{origin}","arrival_airport_code":f"SYN-AP-{destination}",
            "actual_gate_departure_time_utc":None if depart is None else f"{timestamp_date}T{depart}",
            "actual_gate_arrival_time_utc":None if arrive is None else f"{timestamp_date}T{arrive}","next_flight_id":next_id})
        if flight_id >= 8001:
            row.update({"operating_carrier_code":"SYN-OP-ROT","marketing_carrier_code":"SYN-MKT-ROT"})
        row.update(overrides); rows.append(row)
    if scale == "demo":
        used={row["flight_id"] for row in rows}
        ids=iter(value for value in range(5000,8999) if value not in used)
        filler_aircraft=sorted({row["aircraft_id"] for row in masters}-ANCHOR_AIRCRAFT)
        for i in range(3_876):
            flight_id=next(ids); local_date=plus_days("2040-01-01",i//100)
            row=actual_template(flight_id)
            row.update({"aircraft_id":filler_aircraft[i%993],"operating_carrier_code":f"SYN-OP-FILL-{i%16:02d}","marketing_carrier_code":f"SYN-MKT-FILL-{i%16:02d}",
                "flight_number":str(3700+i%100),"flight_departure_date":local_date,"flight_departure_date_utc":local_date,
                "departure_airport_code":f"SYN-AP-{WHITELIST[i%9]}","arrival_airport_code":f"SYN-AP-{WHITELIST[(i+1)%9]}",
                "actual_gate_departure_time_utc":f"{local_date}T09:00:00","actual_gate_arrival_time_utc":f"{local_date}T11:00:00","next_flight_id":None})
            rows.append(row)
    return rows


def airport_reference(scale: str, expected: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows=[]
    for item in expected["scope"]["airport_whitelist"]:
        rows.append(row_for("AIRPORT_REFERENCE", {
            "airport_id":item["airport_internal_id"],"effective_start_date":"2000-01-01","effective_end_date":None,
            "airport_code_iata":item["iata"],"airport_code_icao":item["icao"],"airport_name":item["public_name_label"],
            "is_active":True,"is_current":True,"time_zone_name":item["time_zone_name"],
        }))
    for suffix in ("A","B"):
        rows.append(row_for("AIRPORT_REFERENCE", {"airport_id":f"SYN-AP-DUP-{suffix}","effective_start_date":"2000-01-01","effective_end_date":None,
            "airport_code_iata":"SYN-DUP","airport_code_icao":f"SYN-ICAO-DUP-{suffix}","airport_name":f"Synthetic ambiguity {suffix}",
            "is_active":True,"is_current":True,"time_zone_name":None}))
    if scale == "demo":
        for i in range(34):
            rows.append(row_for("AIRPORT_REFERENCE", {"airport_id":f"SYN-AP-REF-FILL-{i:03d}","effective_start_date":"2000-01-01","effective_end_date":None,
                "airport_code_iata":f"SYN-IATA-FILL-{i:03d}","airport_code_icao":f"SYN-ICAO-REF-FILL-{i:03d}",
                "airport_name":f"Synthetic non-operational airport reference filler {i:03d}","is_active":True,"is_current":True,"time_zone_name":None}))
    return rows


def airline_row(carrier: str) -> dict[str, Any]:
    code=hashlib.sha256(carrier.encode()).hexdigest()[:12].upper()
    return row_for("AIRLINE_REFERENCE", {"airline_id":carrier,"effective_start_date":"2000-01-01","effective_end_date":None,
        "carrier_code_iata":carrier,"carrier_code_icao":f"SYN-ICAO-{code}","carrier_short_name":carrier,
        "carrier_full_name":f"Synthetic airline {carrier}","is_iata_controlled_duplicate":False,"is_active":True,"is_current":True})


def airline_reference(scale: str, tables: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    fields = {
        "SCHEDULE_SNAPSHOT": ("marketing_carrier_internal","operating_carrier_internal","codeshare_carrier_internal"),
        "PASSENGER_FORWARD": ("marketing_carrier_internal","operating_carrier_internal"),
        "PASSENGER_HISTORICAL": ("marketing_carrier_internal","operating_carrier_internal"),
        "AIRCRAFT_FLIGHT": ("operating_carrier_code","marketing_carrier_code"),
    }
    required=set()
    for table, columns in fields.items():
        for row in tables[table]:
            if table == "SCHEDULE_SNAPSHOT" and (row["schedule_key"].startswith("SYN-SK-FILL-") or row["schedule_key"].startswith("SYN-SK-INCOMPLETE-")) and scale == "smoke":
                continue
            for column in columns:
                value=row[column]
                if value not in {None,"SYN-DUP","SYN-ZZZ"}: required.add(value)
    expected_count=33 if scale=="smoke" else 65
    assert len(required)==expected_count, (scale,len(required),sorted(required))
    rows=[airline_row(carrier) for carrier in sorted(required)]
    for suffix in ("A","B"):
        row=airline_row(f"SYN-MKT-DUP-{suffix}"); row["carrier_code_iata"]="SYN-DUP"; row["carrier_code_icao"]=f"SYN-ICAO-DUP-{suffix}"; rows.append(row)
    padding=25 if scale=="smoke" else 33
    rows.extend(airline_row(f"SYN-MKT-REF-FILL-{i:03d}") for i in range(padding))
    return rows


def canonical_rows(table: str, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    def null_last(value: Any) -> tuple[bool, Any]:
        return value is None, value

    def key(row: Mapping[str, Any]) -> Any:
        if table == "AIRCRAFT_MASTER": return null_last(row["aircraft_id"])
        if table == "AIRCRAFT_HISTORY": return tuple(null_last(row[name]) for name in ("aircraft_id","start_event_date","row_sequence_number","event_sequence_number","aircraft_history_id"))
        if table == "AIRCRAFT_CONFIGURATION": return null_last(row["aircraft_configuration_id"])
        if table == "SCHEDULE_SNAPSHOT": return tuple(null_last(row[name]) for name in ("publish_date","schedule_key","itinerary_variation_identifier","normalized_row_hash"))
        if table == "SCHEDULE_SNAPSHOT_CALENDAR": return null_last(row["expected_publish_date"])
        if table == "PASSENGER_FORWARD":
            return null_last(row["forward_source_row_id"]), typed_hash(FIELDS[table], row, "FORWARD")
        if table == "PASSENGER_HISTORICAL":
            return null_last(row["historical_source_row_id"]), typed_hash(FIELDS[table], row, "HISTORICAL")
        if table == "AIRCRAFT_FLIGHT": return null_last(row["flight_id"])
        if table == "AIRPORT_REFERENCE": return tuple(null_last(row[name]) for name in ("airport_id","effective_start_date"))
        if table == "AIRLINE_REFERENCE": return tuple(null_last(row[name]) for name in ("airline_id","effective_start_date"))
        raise AssertionError(table)
    return [dict(row) for row in sorted(rows, key=key)]


def selected_schedules(tables: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    calendar={row["expected_publish_date"]:row for row in tables["SCHEDULE_SNAPSHOT_CALENDAR"]}
    groups: dict[tuple[str,str],list[Mapping[str,Any]]]=defaultdict(list)
    for row in tables["SCHEDULE_SNAPSHOT"]:
        control=calendar.get(row["publish_date"])
        if row["schedule_key"] is not None and control and control["is_present"] and control["is_complete"]:
            groups[(row["publish_date"],row["schedule_key"])].append(row)
    def rank(row: Mapping[str,Any]) -> tuple[Any,...]:
        def desc(value: Any) -> float: return float("inf") if value is None else -float(value)
        return desc(row["weekly_frequency"]),desc(row["total_seats"]),null_sort(row["itinerary_variation_identifier"]),row["normalized_row_hash"]
    def null_sort(value: Any) -> tuple[bool,Any]: return value is None,value
    return {key:sorted(rows,key=rank)[0] for key,rows in groups.items()}


def result_value(value: Any) -> str | None:
    if value is None: return None
    if isinstance(value,bool): return "true" if value else "false"
    if isinstance(value,float) and value.is_integer(): return str(int(value))
    return str(value)


def compute_q05(tables: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str,Any]]:
    selected=selected_schedules(tables)
    watched=[field.column for field in FIELDS["SCHEDULE_SNAPSHOT"] if "SS-04" <= field.field_id <= "SS-38"]
    dates=("2026-08-03","2026-08-10","2026-08-17","2026-08-24","2026-08-31")
    results=[]
    for before,after in zip(dates,dates[1:]):
        old={key:row for (d,key),row in selected.items() if d==before}
        new={key:row for (d,key),row in selected.items() if d==after}
        for key in sorted(old.keys() & new.keys()):
            for field in watched:
                if old[key][field] != new[key][field]:
                    results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"EXACT_KEY_PRESERVING_MODIFICATION","schedule_key":key,"field_name":field,"old_value":result_value(old[key][field]),"new_value":result_value(new[key][field])})
        removed=sorted(old.keys()-new.keys()); added=sorted(new.keys()-old.keys())
        for key in added:
            results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"EXACT_ADDITION","schedule_key":key,"field_name":"__presence__","old_value":"ABSENT","new_value":"PRESENT"})
        for key in removed:
            results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"EXACT_REMOVAL","schedule_key":key,"field_name":"__presence__","old_value":"PRESENT","new_value":"ABSENT"})
        def compatible(left: Mapping[str,Any],right: Mapping[str,Any]) -> bool:
            signature=("marketing_carrier_internal","flight_number","departure_station_code_iata","arrival_station_code_iata")
            if any(left[name] is None or right[name] is None or left[name]!=right[name] for name in signature): return False
            if left["effective_date"] is None or left["discontinue_date"] is None or right["effective_date"] is None or right["discontinue_date"] is None: return False
            return max(left["effective_date"],right["effective_date"]) <= min(left["discontinue_date"],right["discontinue_date"])
        edges={(r,a) for r in removed for a in added if compatible(old[r],new[a])}
        nodes={("R",key) for key in removed}|{("A",key) for key in added}
        seen=set()
        for node in sorted(nodes):
            if node in seen: continue
            component={node}; frontier=[node]; seen.add(node)
            while frontier:
                side,key=frontier.pop()
                neighbours={("A",a) for r,a in edges if side=="R" and r==key}|{("R",r) for r,a in edges if side=="A" and a==key}
                for neighbour in neighbours:
                    if neighbour not in seen: seen.add(neighbour); component.add(neighbour); frontier.append(neighbour)
            rem=sorted(key for side,key in component if side=="R"); add=sorted(key for side,key in component if side=="A")
            if len(rem)==len(add)==1 and (rem[0],add[0]) in edges:
                results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"CANDIDATE_UNIQUE","schedule_key":rem[0],"related_schedule_key":add[0]})
            elif edges and rem and add and any((r,a) in edges for r in rem for a in add):
                results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"AMBIGUOUS_CANDIDATE_GROUP","members":tuple(("REMOVED",r) for r in rem)+tuple(("ADDED",a) for a in add)})
                for side,key in tuple(("REMOVED",r) for r in rem)+tuple(("ADDED",a) for a in add):
                    results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"AMBIGUOUS_GROUP_MEMBER","member_side":side,"member_schedule_key":key})
            else:
                for key in rem: results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"UNPAIRED_REMOVAL","schedule_key":key,"member_side":"REMOVED","member_schedule_key":key})
                for key in add: results.append({"comparison_date":after,"previous_knowledge_date":before,"event_class":"UNPAIRED_ADDITION","schedule_key":key,"member_side":"ADDED","member_schedule_key":key})
    return results


def compute_q06(tables: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str,Any]]:
    selected=selected_schedules(tables)
    def counts(d: str) -> dict[tuple[str,str],int]:
        result=defaultdict(int)
        for (publish,key),row in selected.items():
            if publish!=d or row["marketing_carrier_internal"] is None or row["departure_station_code_iata"] is None or row["arrival_station_code_iata"] is None: continue
            result[(row["marketing_carrier_internal"],f"{row['departure_station_code_iata']}->{row['arrival_station_code_iata']}")]+=1
        return result
    before,after=counts("2026-08-24"),counts("2026-08-31")
    result=[]
    for market in sorted(set(before)|set(after)):
        b,a=before[market],after[market]
        if b==0<a: result.append({"airline_id":market[0],"route_id":market[1],"change_kind":"ENTRY","before_schedule_count":b,"after_schedule_count":a})
        if a==0<b: result.append({"airline_id":market[0],"route_id":market[1],"change_kind":"EXIT","before_schedule_count":b,"after_schedule_count":a})
    return result


def compute_q07(tables: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str,Any]]:
    selected=selected_schedules(tables)
    active=[row for (publish,_),row in selected.items() if publish=="2026-08-31" and row["effective_date"] <= "2026-09-07" <= row["discontinue_date"] and row["departure_station_code_iata"] and row["arrival_station_code_iata"]]
    physical=[row for row in active if not row["is_codeshare"]]
    def metrics(rows: Sequence[Mapping[str,Any]]) -> dict[str,Any]:
        return {"active_schedule_count":len(rows),"weekly_frequency":sum(row["weekly_frequency"] for row in rows),
            "weekly_total_seats":sum(row["weekly_frequency"]*row["total_seats"] for row in rows),
            "weekly_first_seats":sum(row["weekly_frequency"]*row["first_class_seats"] for row in rows),
            "weekly_business_seats":sum(row["weekly_frequency"]*row["business_class_seats"] for row in rows),
            "weekly_premium_economy_seats":sum(row["weekly_frequency"]*row["premium_economy_seats"] for row in rows),
            "weekly_economy_excluding_premium_seats":sum(row["weekly_frequency"]*(row["economy_class_seats"]-row["premium_economy_seats"]) for row in rows)}
    result=[]
    marketing=defaultdict(list)
    for row in active:
        service=row
        if row["is_codeshare"]:
            matches=[candidate for candidate in physical if candidate["operating_carrier_internal"]==row["operating_carrier_internal"] and candidate["flight_number"]==row["flight_number"] and candidate["departure_station_code_iata"]==row["departure_station_code_iata"] and candidate["arrival_station_code_iata"]==row["arrival_station_code_iata"]]
            if len(matches)==1: service=matches[0]
        marketing[(row["marketing_carrier_internal"],f"{row['departure_station_code_iata']}->{row['arrival_station_code_iata']}")].append(service)
    for (carrier,route),rows in marketing.items(): result.append({"carrier_role":"marketing","airline_id":carrier,"route_id":route,"result_status":"COUNTED"}|metrics(rows))
    operating=defaultdict(list)
    for row in physical: operating[(row["operating_carrier_internal"],f"{row['departure_station_code_iata']}->{row['arrival_station_code_iata']}")].append(row)
    for (carrier,route),rows in operating.items(): result.append({"carrier_role":"operating","airline_id":carrier,"route_id":route,"result_status":"COUNTED"}|metrics(rows))
    for row in active:
        if row["is_codeshare"] and not any(candidate["operating_carrier_internal"]==row["operating_carrier_internal"] and candidate["flight_number"]==row["flight_number"] and candidate["departure_station_code_iata"]==row["departure_station_code_iata"] and candidate["arrival_station_code_iata"]==row["arrival_station_code_iata"] for candidate in physical):
            result.append({"carrier_role":"operating","airline_id":row["operating_carrier_internal"],"route_id":f"{row['departure_station_code_iata']}->{row['arrival_station_code_iata']}","result_status":"UNRESOLVED_PHYSICAL_SERVICE","unresolved_service_key":row["schedule_key"]})
    return result


def expected_rows(expected: Mapping[str,Any]) -> list[dict[str,Any]]:
    result=[]
    for question in expected["questions"]:
        for result_set in question["result_sets"]: result.extend(result_set["rows"])
    for table in expected["contract_truth_tables"]: result.extend(table["rows"])
    return result


def ownership_map(expected: Mapping[str,Any]) -> dict[str,dict[str,Any]]:
    text=(ROOT/"data"/"SYNTHETIC_DATA_SPEC.md").read_text(encoding="utf-8")
    match=re.search(r"```yaml\n(expected_row_ownership:.*)\n```",text,flags=re.DOTALL)
    assert match
    entries=yaml.safe_load(match.group(1))["expected_row_ownership"]
    result={}
    for entry in entries:
        ids=entry.get("ids")
        if ids is None:
            spec=entry["range"]
            ids=[f"{spec['prefix']}{index:0{spec['width']}d}" for index in range(spec["start"],spec["end"]+1)]
        for row_id in ids:
            assert row_id not in result
            result[row_id]={"source":entry["source"],**({"rule":entry["rule"]} if "rule" in entry else {})}
    manifest_ids={row["row_id"] for row in expected_rows(expected)}
    assert len(manifest_ids)==253 and set(result)==manifest_ids
    return result


def validate_ownership_sources(owners: Mapping[str,Mapping[str,Any]], tables: Mapping[str,Sequence[Mapping[str,Any]]]) -> int:
    ids={
        "AM":{row["aircraft_id"] for row in tables["AIRCRAFT_MASTER"]},
        "AH":{row["aircraft_history_id"] for row in tables["AIRCRAFT_HISTORY"]},
        "AC":{row["aircraft_configuration_id"] for row in tables["AIRCRAFT_CONFIGURATION"]},
        "PF":{row["forward_source_row_id"] for row in tables["PASSENGER_FORWARD"] if row["forward_source_row_id"] is not None},
        "PH":{row["historical_source_row_id"] for row in tables["PASSENGER_HISTORICAL"] if row["historical_source_row_id"] is not None},
        "AF":{row["flight_id"] for row in tables["AIRCRAFT_FLIGHT"]},
    }
    schedule={(row["schedule_key"],row["publish_date"]) for row in tables["SCHEDULE_SNAPSHOT"]}
    calendar={row["expected_publish_date"] for row in tables["SCHEDULE_SNAPSHOT_CALENDAR"]}
    airports={row["airport_id"] for row in tables["AIRPORT_REFERENCE"]}
    airlines={row["airline_id"] for row in tables["AIRLINE_REFERENCE"]}
    abstract={"SS-81-golden-observations","SC-five-August-complete-dates","CROSS-QUESTION-EVENT-CLOSURE-V1.1",
        "raw-SYN-ZZZ","null-airport-raw-code","null-airline-raw-code"}
    validated=0
    for owner in owners.values():
        for token in owner["source"]:
            ok=False
            numeric=re.fullmatch(r"(AM|AH|AC|PF|PH|AF)-(\d+)",str(token))
            if numeric: ok=int(numeric.group(2)) in ids[numeric.group(1)]
            elif token.startswith("AP-"): ok=token[3:] in airports
            elif token.startswith("AL-"): ok=token[3:] in airlines
            elif re.fullmatch(r"SC-\d{8}",token):
                compact=token[3:]; ok=f"{compact[:4]}-{compact[4:6]}-{compact[6:]}" in calendar
            elif token.startswith("SS-SYN-SK-"):
                raw=token[3:]
                if "-at-incomplete-" in raw:
                    key,compact=raw.split("-at-incomplete-"); expected_date=f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"; ok=(key,expected_date) in schedule
                elif re.search(r"-at-\d{8}$",raw):
                    key,compact=raw.rsplit("-at-",1); expected_date=f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"; ok=(key,expected_date) in schedule
                else: ok=any(key==raw for key,_ in schedule)
            elif re.fullmatch(r"PH-\d+\.\.PH-\d+",token):
                start,end=map(int,re.findall(r"\d+",token)); ok=all(value in ids["PH"] for value in range(start,end+1))
            elif token=="PF-null-quarantine": ok=any(row["forward_source_row_id"] is None and row["arrival_station_code_iata"] is None for row in tables["PASSENGER_FORWARD"])
            elif token.startswith("PF-null-valid-DV43-"):
                digest=token.removeprefix("PF-null-valid-DV43-"); ok=any(row["forward_source_row_id"] is None and typed_hash(FIELDS["PASSENGER_FORWARD"],row,"FORWARD")==digest for row in tables["PASSENGER_FORWARD"])
            elif token=="absent-AF-8999": ok=8999 not in ids["AF"]
            elif token=="absent-AP-SYN-ZZZ": ok="SYN-ZZZ" not in airports
            elif token=="absent-AL-SYN-ZZZ": ok="SYN-ZZZ" not in airlines
            elif token in abstract: ok=True
            assert ok,f"unrealized ownership source {token}"
            validated+=1
    return validated


def find_result_set(expected: Mapping[str,Any], result_set_id: str) -> list[dict[str,Any]]:
    for question in expected["questions"]:
        for result_set in question["result_sets"]:
            if result_set["result_set_id"]==result_set_id: return result_set["rows"]
    raise KeyError(result_set_id)


def validate_q03(tables: Mapping[str,Sequence[Mapping[str,Any]]], expected: Mapping[str,Any]) -> str:
    masters={row["aircraft_id"]:row for row in tables["AIRCRAFT_MASTER"]}
    configs={row["aircraft_configuration_id"]:row for row in tables["AIRCRAFT_CONFIGURATION"]}
    history=defaultdict(list)
    for row in tables["AIRCRAFT_HISTORY"]: history[row["aircraft_id"]].append(row)
    month_ends=[]
    cursor=date(2015,1,1)
    while cursor<=date(2024,12,1):
        next_month=date(cursor.year+1,1,1) if cursor.month==12 else date(cursor.year,cursor.month+1,1)
        month_ends.append((next_month-timedelta(days=1)).isoformat()); cursor=next_month
    materialized=[]
    for month_end in month_ends:
        counts=defaultdict(int)
        for aircraft_id,master in masters.items():
            if not (master["aircraft_start_of_life_date"] <= month_end and (master["aircraft_end_of_life_date"] is None or month_end < master["aircraft_end_of_life_date"])): continue
            eligible=[row for row in history.get(aircraft_id,[]) if row["start_event_date"]<=month_end]
            if not eligible: continue
            visible=max(eligible,key=lambda row:(row["start_event_date"],row["row_sequence_number"],row["event_sequence_number"],row["aircraft_history_id"]))
            if visible["start_aircraft_status"]!="In Service": continue
            config=configs.get(visible["aircraft_configuration_id"])
            if config: counts[(config["aircraft_subseries"],config["aircraft_type"])]+=1
        for (type_id,type_name),count in sorted(counts.items()):
            materialized.append({"month_end":month_end,"aircraft_type_id":type_id,"aircraft_type":type_name,"in_service_aircraft_count":count})
    frozen=[{key:value for key,value in row.items() if key!="row_id"} for row in find_result_set(expected,"Q03-CANONICAL")]
    assert materialized==frozen, (len(materialized),len(frozen))
    return sha256_bytes(canonical_json_bytes(materialized))


def validate_schedule_results(tables: Mapping[str,Sequence[Mapping[str,Any]]], expected: Mapping[str,Any]) -> dict[str,Any]:
    computed=compute_q05(tables); frozen=find_result_set(expected,"Q05-CANONICAL")
    assert len(computed)==len(frozen)==35
    keys_by_class={
        "EXACT_KEY_PRESERVING_MODIFICATION":("comparison_date","previous_knowledge_date","event_class","schedule_key","field_name","old_value","new_value"),
        "EXACT_ADDITION":("comparison_date","previous_knowledge_date","event_class","schedule_key","field_name","old_value","new_value"),
        "EXACT_REMOVAL":("comparison_date","previous_knowledge_date","event_class","schedule_key","field_name","old_value","new_value"),
        "CANDIDATE_UNIQUE":("comparison_date","previous_knowledge_date","event_class","schedule_key","related_schedule_key"),
        "AMBIGUOUS_GROUP_MEMBER":("comparison_date","previous_knowledge_date","event_class","member_side","member_schedule_key"),
        "UNPAIRED_REMOVAL":("comparison_date","previous_knowledge_date","event_class","member_side","member_schedule_key"),
        "UNPAIRED_ADDITION":("comparison_date","previous_knowledge_date","event_class","member_side","member_schedule_key"),
    }
    unmatched=list(computed)
    for row in frozen:
        cls=row["event_class"]
        if cls=="AMBIGUOUS_CANDIDATE_GROUP":
            matches=[item for item in unmatched if item["event_class"]==cls and item["comparison_date"]==row["comparison_date"]]
        else:
            fields=keys_by_class[cls]
            matches=[item for item in unmatched if all(item.get(field)==row.get(field) for field in fields)]
        assert len(matches)==1,(row,matches)
        unmatched.remove(matches[0])
    assert not unmatched
    q06=compute_q06(tables); frozen06=find_result_set(expected,"Q06-CANONICAL")
    fields06=("airline_id","route_id","change_kind","before_schedule_count","after_schedule_count")
    assert sorted(tuple(row[field] for field in fields06) for row in q06)==sorted(tuple(row[field] for field in fields06) for row in frozen06)
    q07=compute_q07(tables); frozen07=find_result_set(expected,"Q07-MARKETING")+find_result_set(expected,"Q07-OPERATING")
    assert len(q07)==len(frozen07)==5
    for row in frozen07:
        matches=[item for item in q07 if all(item.get(field)==row.get(field) for field in ("carrier_role","airline_id","route_id","result_status"))]
        assert len(matches)==1,(row,matches)
        item=matches[0]
        for field in ("active_schedule_count","weekly_frequency","weekly_total_seats","weekly_first_seats","weekly_business_seats","weekly_premium_economy_seats","weekly_economy_excluding_premium_seats","unresolved_service_key"):
            assert item.get(field)==row.get(field),(row["row_id"],field,item.get(field),row.get(field))
    return {"q05_rows":35,"q05_adjacent_counts":[sum(row["comparison_date"]==date_value for row in computed) for date_value in ("2026-08-10","2026-08-17","2026-08-24","2026-08-31")],
        "q05_source_materialization_sha256":sha256_bytes(canonical_json_bytes(sorted(computed,key=lambda row:canonical_json_bytes(row)))),
        "q06_rows":2,"q06_source_materialization_sha256":sha256_bytes(canonical_json_bytes(sorted(q06,key=lambda row:canonical_json_bytes(row)))),
        "q07_rows":5,"q07_source_materialization_sha256":sha256_bytes(canonical_json_bytes(sorted(q07,key=lambda row:canonical_json_bytes(row))))}


def validate_identity_namespaces(tables: Mapping[str,Sequence[Mapping[str,Any]]]) -> dict[str,Any]:
    am=tables["AIRCRAFT_MASTER"]; ah=tables["AIRCRAFT_HISTORY"]; ac=tables["AIRCRAFT_CONFIGURATION"]
    ss=tables["SCHEDULE_SNAPSHOT"]; pf=tables["PASSENGER_FORWARD"]; ph=tables["PASSENGER_HISTORICAL"]
    af=tables["AIRCRAFT_FLIGHT"]; ap=tables["AIRPORT_REFERENCE"]; al=tables["AIRLINE_REFERENCE"]
    am_ids={row["aircraft_id"] for row in am}; ac_ids={row["aircraft_configuration_id"] for row in ac}
    ap_ids={row["airport_id"] for row in ap}; al_ids={row["airline_id"] for row in al}; af_ids={row["flight_id"] for row in af}
    assert all(1000<=value<=1999 for value in am_ids) and 1003 not in am_ids
    assert all(row["aircraft_serial_number"]==f"SYN-SERIAL-{row['aircraft_id']}" and row["aircraft_line_number"]==f"SYN-LINE-{row['aircraft_id']}" for row in am)
    assert all(row["original_delivery_operator"].startswith("SYN-") and row["apu_type"].startswith("SYN-") for row in am)
    assert all(101000<=row["aircraft_history_id"]<=199999 and row["aircraft_id"] in am_ids for row in ah)
    assert all(row["aircraft_configuration_id"] in ac_ids|{None,999999} for row in ah)
    assert all(row["aircraft_registration_number"]==f"SYN-REG-{row['aircraft_id']}" and row["aircraft_transponder_code"]==f"SYN-XPDR-{row['aircraft_id']}" for row in ah)
    assert all(row["aircraft_code_iata"] is None or row["aircraft_code_iata"] in {"SA1","SB1","SM1"} or row["aircraft_code_iata"].startswith("SYN-") for row in ah)
    assert all(row["aircraft_code_icao"] is None or row["aircraft_code_icao"].startswith("SYN") for row in ah)
    assert all(row["aircraft_value_sub_series"] is None or row["aircraft_value_sub_series"].startswith("SYN-") for row in ah)
    assert all(row["storage_location"] is None or row["storage_location"] in ap_ids for row in ah)
    assert all(row["aircraft_configuration_id"] in {2001,2002,2003,2005} or 300000<=row["aircraft_configuration_id"]<=301995 for row in ac)
    for row in ac:
        for column in ("aircraft_family","aircraft_series","aircraft_subseries","aircraft_manufacturer","aircraft_design_class","engine_manufacturer","engine_family","engine_series","engine_subseries"):
            assert row[column].startswith("SYN-")
        assert row["aircraft_type"].startswith("Synthetic ") and row["engine_type"].startswith("Synthetic ")
    assert all(row["schedule_key"].startswith("SYN-SK-") and row["schedule_key_readable"].startswith("SYN-READABLE|") for row in ss)
    assert all(row[column] is None or row[column].startswith("SYN-") for row in ss for column in ("marketing_carrier_internal","operating_carrier_internal","codeshare_carrier_internal"))
    assert all(700<=row["flight_number"]<=799 or 1700<=row["flight_number"]<=1899 for row in ss)
    assert all(9000<=row["itinerary_variation_identifier"]<=9999 and re.fullmatch(r"[0-9a-f]{64}",row["normalized_row_hash"]) for row in ss)
    assert all(row["equipment_subtype_code_iata"].startswith("SYN-") for row in ss)
    for rows,id_column,filler_range in ((pf,"forward_source_row_id",range(2700,2800)),(ph,"historical_source_row_id",range(2800,2900))):
        assert all(row[id_column] is None or 5000<=row[id_column]<=7999 for row in rows)
        assert all(row["marketing_carrier_internal"].startswith("SYN-") and row["operating_carrier_internal"].startswith("SYN-") for row in rows)
        assert all(700<=row["flight_number"]<=799 or row["flight_number"] in filler_range for row in rows)
        assert all(row["equipment_subtype_code_iata"].startswith("SYN-") for row in rows)
    assert all(5000<=row["flight_id"]<=8998 and 1000<=row["aircraft_id"]<=1999 for row in af)
    assert all(row["operating_carrier_code"].startswith("SYN-") and row["marketing_carrier_code"].startswith("SYN-") for row in af)
    assert all((700<=int(row["flight_number"])<=799) or (3700<=int(row["flight_number"])<=3799) for row in af)
    assert all(row["next_flight_id"] is None or row["next_flight_id"] in af_ids or row["next_flight_id"]==8999 for row in af)
    assert all(row["departure_airport_code"] in ap_ids and row["arrival_airport_code"] in ap_ids and (row["diverted_airport_code"] is None or row["diverted_airport_code"] in ap_ids) for row in af)
    assert all(row["airport_id"].startswith("SYN-AP-") for row in ap)
    assert all(row["airport_code_iata"] in WHITELIST or row["airport_code_iata"].startswith("SYN-") for row in ap)
    assert all(row["airport_code_icao"].startswith("K") or row["airport_code_icao"].startswith("SYN-") for row in ap)
    assert all(row["airline_id"].startswith("SYN-") and row["carrier_code_iata"].startswith("SYN-") and row["carrier_code_icao"].startswith("SYN-") for row in al)
    exact_carrier_exceptions={None,"SYN-DUP","SYN-ZZZ"}
    for row in ss:
        for column in ("marketing_carrier_internal","operating_carrier_internal","codeshare_carrier_internal"):
            assert row[column] in exact_carrier_exceptions or row[column] in al_ids
    for rows,columns in ((pf,("marketing_carrier_internal","operating_carrier_internal")),(ph,("marketing_carrier_internal","operating_carrier_internal")),(af,("operating_carrier_code","marketing_carrier_code"))):
        assert all(row[column] in al_ids for row in rows for column in columns)
    return {"status":"passed","negative_fixture_classes":list(NEGATIVE_FIXTURE_CLASSES),"negative_fixture_class_count":len(NEGATIVE_FIXTURE_CLASSES),
        "numeric_namespaces":{"aircraft":"1000..1999 excluding 1003","aircraft_history":"101000..199999","passenger_source":"5000..7999 or null DV-43 fallback","actual_flight":"5000..8998; 8999 reserved absent"}}


def validate_tables(scale: str, tables: Mapping[str,Sequence[Mapping[str,Any]]], expected: Mapping[str,Any]) -> dict[str,Any]:
    assert tuple(tables)==TABLE_ORDER
    counts={table:len(rows) for table,rows in tables.items()}
    assert counts==EXPECTED_COUNTS[scale]
    assert sum(counts.values())==(249 if scale=="smoke" else 145_054)
    for table,rows in tables.items():
        columns={field.column for field in FIELDS[table]}
        for row in rows:
            assert set(row)==columns
            for field in FIELDS[table]:
                if row[field.column] is not None: canonical_scalar(row[field.column],field.type_tag)
    for table,key in (("AIRCRAFT_MASTER","aircraft_id"),("AIRCRAFT_HISTORY","aircraft_history_id"),("AIRCRAFT_CONFIGURATION","aircraft_configuration_id"),("SCHEDULE_SNAPSHOT_CALENDAR","expected_publish_date"),("AIRCRAFT_FLIGHT","flight_id")):
        values=[row[key] for row in tables[table]]
        assert None not in values and len(values)==len(set(values))
    for table,key in (("PASSENGER_FORWARD","forward_source_row_id"),("PASSENGER_HISTORICAL","historical_source_row_id")):
        values=[row[key] for row in tables[table] if row[key] is not None]
        assert len(values)==len(set(values))
        null_hashes=[typed_hash(FIELDS[table],row,"FORWARD" if table=="PASSENGER_FORWARD" else "HISTORICAL") for row in tables[table] if row[key] is None]
        assert len(null_hashes)==len(set(null_hashes)) and all(re.fullmatch(r"[0-9a-f]{64}",value) for value in null_hashes)
    for table,keys in (("AIRPORT_REFERENCE",("airport_id","effective_start_date")),("AIRLINE_REFERENCE",("airline_id","effective_start_date"))):
        values=[tuple(row[key] for key in keys) for row in tables[table]]
        assert len(values)==len(set(values))
    # Hash known answers.
    vector=f"{SEED}|{SOURCE_TOKEN['SCHEDULE_SNAPSHOT']}|100000|SS-39".encode("ascii")
    assert len(vector)==46 and sha256_bytes(vector)=="491861981a7e9e11dd9d7f5650a019f5cd99b2eff006d88f74b9b18081ded65d"
    assert 9000+int.from_bytes(hashlib.sha256(vector).digest()[:2],"big")%1000==9712
    valid_null=next(row for row in tables["PASSENGER_FORWARD"] if row["forward_source_row_id"] is None and row["flight_number"]==726)
    payload=typed_payload(FIELDS["PASSENGER_FORWARD"],valid_null,"FORWARD")
    assert len(payload)==610 and sha256_bytes(payload)=="a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7"
    # Calendar counts and deterministic de-duplication.
    by_date=defaultdict(int)
    for row in tables["SCHEDULE_SNAPSHOT"]: by_date[row["publish_date"]]+=1
    for row in tables["SCHEDULE_SNAPSHOT_CALENDAR"]: assert row["observed_row_count"]==by_date[row["expected_publish_date"]]
    assert sum(row["event_source"]=="SYNTHETIC_IRRELEVANT" for row in tables["AIRCRAFT_HISTORY"])==1
    assert next(row for row in tables["AIRCRAFT_HISTORY"] if row["aircraft_history_id"]==101020)["event_source"]=="SYNTHETIC_IRRELEVANT"
    ss_fields=FIELDS["SCHEDULE_SNAPSHOT"][:-1]
    assert all(row["normalized_row_hash"]==typed_hash(ss_fields,row) for row in tables["SCHEDULE_SNAPSHOT"])
    base=[row for row in tables["SCHEDULE_SNAPSHOT"] if row["schedule_key"]=="SYN-SK-BASE_100" and row["publish_date"]=="2026-08-03"]
    assert len(base)==3 and len({row["normalized_row_hash"] for row in base})==2
    same_day=[row for row in tables["AIRCRAFT_HISTORY"] if row["aircraft_id"]==1001 and row["start_event_date"]=="2020-06-01"]
    assert [(row["row_sequence_number"],row["start_aircraft_status"]) for row in same_day]==[(5,"Maintenance"),(10,"In Service"),(20,"Storage"),(30,"In Service"),(40,"In Service")]
    assert next(row for row in tables["AIRCRAFT_HISTORY"] if row["aircraft_history_id"]==101021)["apu_type"]=="SYN-APU-B"
    assert next(row for row in tables["AIRCRAFT_HISTORY"] if row["aircraft_history_id"]==101023)["apu_type"] is None
    # Exact resolution controls.
    airport_candidates=defaultdict(set)
    for row in tables["AIRPORT_REFERENCE"]:
        for column in ("airport_code_iata","airport_code_icao","airport_id"):
            if row[column] is not None: airport_candidates[row[column]].add(row["airport_id"])
    airline_candidates=defaultdict(set)
    for row in tables["AIRLINE_REFERENCE"]:
        for column in ("airline_id","carrier_code_iata","carrier_code_icao"):
            if row[column] is not None: airline_candidates[row[column]].add(row["airline_id"])
    assert [len(airport_candidates[value]) if value is not None else 0 for value in ("SFO","SYN-ZZZ","SYN-DUP",None)]==[1,0,2,0]
    assert [len(airline_candidates[value]) if value is not None else 0 for value in ("SYN-MKT-DIAG","SYN-ZZZ","SYN-DUP",None)]==[1,0,2,0]
    golden_airport_raw=set(WHITELIST)|{f"SYN-AP-{code}" for code in WHITELIST}|{"SYN-DUP","SYN-ZZZ"}
    airport_filler_aliases={row[column] for row in tables["AIRPORT_REFERENCE"] if row["airport_id"].startswith("SYN-AP-REF-FILL-") for column in ("airport_id","airport_code_iata","airport_code_icao")}
    assert golden_airport_raw.isdisjoint(airport_filler_aliases)
    airline_padding_aliases={row[column] for row in tables["AIRLINE_REFERENCE"] if row["airline_id"].startswith("SYN-MKT-REF-FILL-") for column in ("airline_id","carrier_code_iata","carrier_code_icao")}
    operational_carriers={row[column] for table,columns in (("SCHEDULE_SNAPSHOT",("marketing_carrier_internal","operating_carrier_internal","codeshare_carrier_internal")),("PASSENGER_FORWARD",("marketing_carrier_internal","operating_carrier_internal")),("PASSENGER_HISTORICAL",("marketing_carrier_internal","operating_carrier_internal")),("AIRCRAFT_FLIGHT",("operating_carrier_code","marketing_carrier_code"))) for row in tables[table] for column in columns if row[column] is not None}
    assert operational_carriers.isdisjoint(airline_padding_aliases)
    # Filler isolation and U.S.-domestic endpoint controls.
    assert 8999 not in {row["flight_id"] for row in tables["AIRCRAFT_FLIGHT"]}
    assert all(row["aircraft_id"] not in ANCHOR_AIRCRAFT for row in tables["AIRCRAFT_HISTORY"] if row["aircraft_history_id"] not in {101001,101003,101004,101005,101008,101009,101010,101011,101020,101021,101022,101023,101024,101007,102001,102002,102004,102005,102006,102099,104001,105001,109801,109901})
    assert all(row["aircraft_start_of_life_date"]>"2024-12-31" for row in tables["AIRCRAFT_MASTER"] if row["aircraft_id"] not in ANCHOR_AIRCRAFT)
    assert all(row["aircraft_build_airport_code_iata"] in WHITELIST for row in tables["AIRCRAFT_MASTER"])
    for row in tables["AIRCRAFT_HISTORY"]:
        assert row["storage_airport_code_iata"] is None or row["storage_airport_code_iata"] in WHITELIST
        assert row["base_airport_code_iata"] is None or row["base_airport_code_iata"] in WHITELIST
        assert (row["storage_location"] is None and row["storage_airport_code_iata"] is None) or row["storage_location"]==f"SYN-AP-{row['storage_airport_code_iata']}"
    if scale=="demo":
        filler=[row for row in tables["SCHEDULE_SNAPSHOT"] if row["schedule_key"].startswith("SYN-SK-FILL-")]
        assert len(filler)==60_000
        grouped=defaultdict(list)
        for row in filler: grouped[row["schedule_key"]].append(row)
        watched=[field.column for field in FIELDS["SCHEDULE_SNAPSHOT"] if "SS-04"<=field.field_id<="SS-38"]
        assert len(grouped)==12_000 and all(len(rows)==5 and len({tuple(row[column] for column in watched) for row in rows})==1 for rows in grouped.values())
        assert all(not (row["effective_date"]<="2026-09-07"<=row["discontinue_date"]) for row in filler)
        pf_filler=[row for row in tables["PASSENGER_FORWARD"] if row["operating_date"]>="2035-01-01"]
        ph_filler=[row for row in tables["PASSENGER_HISTORICAL"] if row["operating_date"]>="2036-01-01"]
        af_filler=[row for row in tables["AIRCRAFT_FLIGHT"] if row["flight_departure_date"]>="2040-01-01"]
        pf_keys={(row["marketing_carrier_internal"],row["flight_number"],row["departure_station_code_iata"],row["arrival_station_code_iata"],row["operating_date"]) for row in pf_filler}
        ph_keys={(row["marketing_carrier_internal"],row["flight_number"],row["departure_station_code_iata"],row["arrival_station_code_iata"],row["operating_date"]) for row in ph_filler}
        assert pf_keys.isdisjoint(ph_keys)
        passenger_match={(row["operating_carrier_internal"],str(row["flight_number"]),row["operating_date"]) for row in pf_filler+ph_filler}
        actual_match={(row["operating_carrier_code"],row["flight_number"],row["flight_departure_date"]) for row in af_filler}
        assert passenger_match.isdisjoint(actual_match)
    for row in tables["SCHEDULE_SNAPSHOT"]:
        # The CLOCK_BOUNDARY negative fixture intentionally opens/closes a route with a null
        # destination.  Every supplied (non-null) endpoint remains in the public whitelist.
        assert row["departure_station_code_iata"] is None or row["departure_station_code_iata"] in WHITELIST
        assert row["arrival_station_code_iata"] is None or row["arrival_station_code_iata"] in WHITELIST
    null_schedule_endpoints=[(row["schedule_key"],row["publish_date"],row["departure_station_code_iata"],row["arrival_station_code_iata"]) for row in tables["SCHEDULE_SNAPSHOT"] if row["departure_station_code_iata"] is None or row["arrival_station_code_iata"] is None]
    assert null_schedule_endpoints==[("SYN-SK-CLOCK_BOUNDARY_001",publish_date,"ORD",None) for publish_date in ("2026-08-03","2026-08-10","2026-08-17","2026-08-31","2026-09-07")]
    assert all(route["planned_origin_iata"] in WHITELIST and route["planned_destination_iata"] in WHITELIST for route in expected["scope"]["anchored_schedule_routes"])
    for table,columns in (("PASSENGER_FORWARD",("departure_station_code_iata","arrival_station_code_iata")),("PASSENGER_HISTORICAL",("departure_station_code_iata","arrival_station_code_iata"))):
        for row in tables[table]:
            for column in columns:
                assert row[column] is None or row[column] in WHITELIST
    for row in tables["AIRCRAFT_FLIGHT"]:
        for column in ("departure_airport_code","arrival_airport_code","diverted_airport_code"):
            assert row[column] is None or row[column] in {f"SYN-AP-{code}" for code in WHITELIST}
    # Named codeshare, stopover, diversion, fulfillment, union-precedence, and anomaly fixtures.
    schedule_by_key=defaultdict(list)
    for row in tables["SCHEDULE_SNAPSHOT"]: schedule_by_key[row["schedule_key"]].append(row)
    assert any(row["is_codeshare"] for row in schedule_by_key["SYN-SK-MKT_COPY_702"])
    assert any(row["is_codeshare"] for row in schedule_by_key["SYN-SK-CSH_ONLY_900"])
    pf_by_id={row["forward_source_row_id"]:row for row in tables["PASSENGER_FORWARD"] if row["forward_source_row_id"] is not None}
    ph_by_id={row["historical_source_row_id"]:row for row in tables["PASSENGER_HISTORICAL"] if row["historical_source_row_id"] is not None}
    af_by_id={row["flight_id"]:row for row in tables["AIRCRAFT_FLIGHT"]}
    assert (ph_by_id[5001]["marketing_carrier_internal"],ph_by_id[5001]["flight_number"],ph_by_id[5001]["operating_date"])==(pf_by_id[6001]["marketing_carrier_internal"],pf_by_id[6001]["flight_number"],pf_by_id[6001]["operating_date"])
    assert ph_by_id[5102]["number_of_intermediate_stops"]==ph_by_id[5103]["number_of_intermediate_stops"]==1
    assert pf_by_id[6103]["number_of_intermediate_stops"]==1
    assert af_by_id[7200]["is_diverted"]==1 and af_by_id[7200]["diverted_airport_code"]==af_by_id[7200]["arrival_airport_code"]
    assert af_by_id[8109]["is_diverted"]==1 and af_by_id[8109]["diverted_airport_code"]!=af_by_id[8109]["arrival_airport_code"]
    assert af_by_id[8101]["next_flight_id"]==8101 and af_by_id[8102]["next_flight_id"]==8103 and af_by_id[8103]["next_flight_id"]==8102
    assert af_by_id[8104]["next_flight_id"]==8999 and 8999 not in af_by_id
    q03_hash=validate_q03(tables,expected)
    schedule_validation=validate_schedule_results(tables,expected)
    namespace_validation=validate_identity_namespaces(tables)
    owners=ownership_map(expected)
    ownership_source_references=validate_ownership_sources(owners,tables)
    owner_bytes=canonical_json_bytes(owners)
    output_text="\n".join(canonical_scalar(row[field.column],field.type_tag) for table,rows in tables.items() for row in rows for field in FIELDS[table] if row[field.column] is not None).casefold()
    assert all(token not in output_text for token in ("confidential","customer proprietary","neo4j.com"))
    frozen_rows=sorted(expected_rows(expected),key=lambda row:row["row_id"])
    return {"counts":counts,"total_rows":sum(counts.values()),"expected_rows_owned":len(owners),"ownership_source_references_validated":ownership_source_references,"ownership_sha256":sha256_bytes(owner_bytes),
        "frozen_expected_rows_sha256":sha256_bytes(canonical_json_bytes(frozen_rows)),"schedule_result_validation":schedule_validation,
        "q03_rows":132,"q03_source_materialization_sha256":q03_hash,"identity_namespace_validation":namespace_validation,"customer_data_scan":"passed"}


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode("utf-8")


def csv_bytes(table: str, rows: Sequence[Mapping[str,Any]]) -> bytes:
    buffer=io.StringIO(newline="")
    writer=csv.writer(buffer,delimiter=",",quotechar='"',lineterminator="\n",quoting=csv.QUOTE_MINIMAL,doublequote=True)
    fields=FIELDS[table]
    writer.writerow([field.column for field in fields])
    for row in rows:
        writer.writerow(["" if row[field.column] is None else canonical_scalar(row[field.column],field.type_tag) for field in fields])
    return buffer.getvalue().encode("utf-8")


def validate_lf_record_separators(content: bytes) -> None:
    """Reject CR record separators while allowing CR/LF bytes inside quoted values."""
    quoted=False
    index=0
    while index<len(content):
        byte=content[index]
        if byte==0x22:
            if quoted and index+1<len(content) and content[index+1]==0x22:
                index+=2
                continue
            quoted=not quoted
        elif byte==0x0D and not quoted:
            raise AssertionError("CSV record separators must be LF, never CR or CRLF")
        index+=1
    assert not quoted and content.endswith(b"\n")


def validate_csv_roundtrip(table: str, rows: Sequence[Mapping[str,Any]], content: bytes) -> None:
    text=content.decode("utf-8")
    validate_lf_record_separators(content)
    parsed=list(csv.reader(io.StringIO(text,newline=""),delimiter=",",quotechar='"',doublequote=True))
    fields=FIELDS[table]
    assert parsed[0]==[field.column for field in fields]
    assert len(parsed)==len(rows)+1 and all(len(row)==len(fields) for row in parsed)
    expected=[["" if row[field.column] is None else canonical_scalar(row[field.column],field.type_tag) for field in fields] for row in rows]
    assert parsed[1:]==expected


def ordered_row_hash(table: str, rows: Sequence[Mapping[str,Any]]) -> str:
    payload=bytearray(lp(TYPED_ROW_VERSION)); payload.extend(lp(SOURCE_TOKEN[table]))
    for row in rows: payload.extend(lp(typed_payload(FIELDS[table],row)))
    return sha256_bytes(bytes(payload))


def construct_tables(scale: str, *, reordered_input: bool=False) -> tuple[dict[str,list[dict[str,Any]]],dict[str,Any]]:
    if scale not in EXPECTED_COUNTS: raise ValueError("scale must be smoke or demo")
    expected=load_expected()
    masters=aircraft_master(scale)
    tables: dict[str,list[dict[str,Any]]]={
        "AIRCRAFT_MASTER":masters,
        "AIRCRAFT_HISTORY":aircraft_history(scale,masters),
        "AIRCRAFT_CONFIGURATION":aircraft_configuration(scale),
        "SCHEDULE_SNAPSHOT":schedule_rows(scale,expected),
        "SCHEDULE_SNAPSHOT_CALENDAR":snapshot_calendar(scale),
        "PASSENGER_FORWARD":passenger_forward(scale),
        "PASSENGER_HISTORICAL":passenger_historical(scale),
        "AIRCRAFT_FLIGHT":aircraft_flights(scale,masters),
        "AIRPORT_REFERENCE":airport_reference(scale,expected),
    }
    tables["AIRLINE_REFERENCE"]=airline_reference(scale,tables)
    if reordered_input:
        for table,rows in tables.items():
            original=[typed_payload(FIELDS[table],row) for row in rows]
            rows.sort(key=lambda row:hashlib.sha256(lp("reordered-input-v1")+typed_payload(FIELDS[table],row)).digest(),reverse=True)
            if len(rows)>1 and [typed_payload(FIELDS[table],row) for row in rows]==original:
                rows.reverse()
    return tables,expected


def raw_order_hashes(tables: Mapping[str,Sequence[Mapping[str,Any]]]) -> dict[str,str]:
    result={}
    for table,rows in tables.items():
        payload=bytearray(lp("raw-constructor-order-v1")); payload.extend(lp(SOURCE_TOKEN[table]))
        for row in rows: payload.extend(lp(typed_payload(FIELDS[table],row)))
        result[table]=sha256_bytes(bytes(payload))
    return result


def build_tables(scale: str, *, reordered_input: bool=False) -> tuple[dict[str,list[dict[str,Any]]],dict[str,Any]]:
    tables,expected=construct_tables(scale,reordered_input=reordered_input)
    tables={table:canonical_rows(table,tables[table]) for table in TABLE_ORDER}
    validation=validate_tables(scale,tables,expected)
    return tables,validation


def authority_hashes() -> dict[str,str]:
    names=("DECISION_LOG.md","EXPECTED_ANSWERS.yaml","SOURCE_CONTRACT.md","ATTRIBUTE_AUTHORITY.md","data/SYNTHETIC_DATA_SPEC.md","build/task_reports/DATA-01.json")
    return {name:sha256_file(ROOT/name) for name in names}


def stage_package(scale: str, directory: Path, *, reordered_input: bool=False) -> dict[str,Any]:
    tables,validation=build_tables(scale,reordered_input=reordered_input)
    table_manifest={}
    for table,rows in tables.items():
        filename=f"{table.lower()}.csv"; content=csv_bytes(table,rows)
        validate_csv_roundtrip(table,rows,content)
        (directory/filename).write_bytes(content)
        table_manifest[table]={"file":filename,"rows":len(rows),"field_ids":[field.field_id for field in FIELDS[table]],
            "columns":[field.column for field in FIELDS[table]],"snowflake_types":[field.type_tag for field in FIELDS[table]],
            "file_sha256":sha256_bytes(content),"ordered_typed_rows_sha256":ordered_row_hash(table,rows)}
    manifest={
        "manifest_version":"1.0.0","scale":scale,"claim_scope":"synthetic U.S.-domestic representative functional shape; non-production",
        "seed":int(SEED),"generation_date":GENERATION_DATE,"generation_timestamp":GENERATION_TIMESTAMP,
        "specification_version":SPEC_VERSION,"expected_manifest_version":EXPECTED_VERSION,
        "serializer":{"version":SERIALIZER_VERSION,"encoding":"UTF-8","line_ending":"LF","delimiter":",","quote_char":"\"","double_quote":True,
            "null":"unquoted empty field","nonnull_empty_string":"rejected","number":"base-10 integer without padding","float":"finite Python shortest round-trip decimal including .0 for integral floats","boolean":["false","true"],"date":"YYYY-MM-DD","time":"ISO TIME source precision","timestamp_ntz":"ISO date T time source precision"},
        "snowflake_file_format":{"type":"CSV","compression":"NONE","record_delimiter":"\n","field_delimiter":",","skip_header":1,
            "parse_header":False,"field_optionally_enclosed_by":"\"","escape":"NONE","escape_unenclosed_field":"NONE","multi_line":True,
            "empty_field_as_null":True,"null_if":[""],"trim_space":False,"skip_blank_lines":False,"replace_invalid_characters":False,
            "error_on_column_count_mismatch":True,"encoding":"UTF8"},
        "typed_row_hash_version":TYPED_ROW_VERSION,"dv43_version":DV43_VERSION,"authority_sha256":authority_hashes(),
        "tables":table_manifest,"validation":validation,
        "known_answers":{"schedule_prf_sha256":"491861981a7e9e11dd9d7f5650a019f5cd99b2eff006d88f74b9b18081ded65d","schedule_prf_ss39":9712,
            "pf_valid_null_id_payload_bytes":610,"pf_valid_null_id_dv43":"a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7",
            "pf_valid_null_id_dv46":"FORWARD|a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7"},
    }
    assert all("manifest_sha" not in key.casefold() and "self_hash" not in key.casefold() for key in manifest)
    (directory/"manifest.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def generate(scale: str, output_root: Path | None=None, *, reordered_input: bool=False, fail_before_publish: bool=False) -> dict[str,Any]:
    output_root=(ROOT/"build"/"generated_data") if output_root is None else Path(output_root)
    output_root.mkdir(parents=True,exist_ok=True)
    target=output_root/scale
    temp=Path(tempfile.mkdtemp(prefix=f".{scale}.tmp-",dir=output_root))
    backup=output_root/f".{scale}.backup"
    try:
        manifest=stage_package(scale,temp,reordered_input=reordered_input)
        if fail_before_publish: raise RuntimeError("injected pre-publication failure")
        if backup.exists(): shutil.rmtree(backup)
        if target.exists(): os.replace(target,backup)
        try:
            os.replace(temp,target)
        except BaseException:
            if backup.exists(): os.replace(backup,target)
            raise
        if backup.exists(): shutil.rmtree(backup)
        return manifest
    finally:
        if temp.exists(): shutil.rmtree(temp)


def main(argv: Sequence[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale",choices=("smoke","demo"),required=True)
    parser.add_argument("--output-root",type=Path,default=ROOT/"build"/"generated_data")
    parser.add_argument("--reordered-input",action="store_true",help="construct in a deterministic non-canonical order before canonical publication")
    parser.add_argument("--fail-before-publish",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    manifest=generate(args.scale,args.output_root,reordered_input=args.reordered_input,fail_before_publish=args.fail_before_publish)
    print(json.dumps({"scale":args.scale,"rows":manifest["validation"]["total_rows"],"output":str(args.output_root/args.scale)},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
