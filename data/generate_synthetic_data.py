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
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
SEED = "20260901"
GENERATION_DATE = "2026-09-01"
GENERATION_TIMESTAMP = "2026-09-01T00:00:00Z"
SPEC_VERSION = "2.0.0"
EXPECTED_VERSION = "1.2.0"
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
        "AIRCRAFT_HISTORY": 30_233,
        "AIRCRAFT_CONFIGURATION": 2_000,
        "SCHEDULE_SNAPSHOT": 124_636,
        "SCHEDULE_SNAPSHOT_CALENDAR": 36,
        "PASSENGER_FORWARD": 10_000,
        "PASSENGER_HISTORICAL": 10_000,
        "AIRCRAFT_FLIGHT": 3_900,
        "AIRPORT_REFERENCE": 45,
        "AIRLINE_REFERENCE": 190,
    },
}
WHITELIST = ("SFO", "LAX", "LAS", "SEA", "DEN", "ORD", "PHX", "BOS", "MIA")
ANCHOR_AIRCRAFT = {1001, 1002, 1004, 1005, 1098, 1099}

# --- specification 2.0.0 enrichment constants ----------------------------------------------------
DATA_HORIZON = "2035-01-01"          # exclusive; no filler event is emitted at or after service_end
ENRICHED_FLOOR = "2025-01-01"        # every filler AM-07 and AH-05 is at or after this date
W27_FIRST = "2027-01-04"             # first 2027 weekly snapshot date
W27_WEEKS = 26
W27_INCOMPLETE_INDEX = 10            # 2027-03-15, PRESENT_INCOMPLETE
W27_MISSING_INDEX = 15               # 2027-04-19, MISSING_DECLARED

# AC-01, AC-05 subseries, AC-03 type label, AC-07 design class, AC-08 engine count,
# AC-14 engine subseries, AC-12 engine label.
FLEET_DEFINITIONS = (
    (300000, "SYN-TYPE-NB1", "Synthetic narrowbody generation 1", "SYN-CLASS-NB", 2, "SYN-ENGINE-N1A", "Synthetic turbofan N1A"),
    (300001, "SYN-TYPE-NB1", "Synthetic narrowbody generation 1", "SYN-CLASS-NB", 2, "SYN-ENGINE-N1B", "Synthetic turbofan N1B"),
    (300002, "SYN-TYPE-NB2", "Synthetic narrowbody generation 2", "SYN-CLASS-NB", 2, "SYN-ENGINE-N1A", "Synthetic turbofan N1A"),
    (300003, "SYN-TYPE-NB2", "Synthetic narrowbody generation 2", "SYN-CLASS-NB", 2, "SYN-ENGINE-N2A", "Synthetic turbofan N2A"),
    (300004, "SYN-TYPE-NB3", "Synthetic narrowbody generation 3", "SYN-CLASS-NB", 2, "SYN-ENGINE-N3A", "Synthetic turbofan N3A"),
    (300005, "SYN-TYPE-NB3", "Synthetic narrowbody generation 3", "SYN-CLASS-NB", 2, "SYN-ENGINE-N3B", "Synthetic turbofan N3B"),
    (300006, "SYN-TYPE-WB1", "Synthetic widebody generation 1", "SYN-CLASS-WB", 2, "SYN-ENGINE-W1A", "Synthetic turbofan W1A"),
    (300007, "SYN-TYPE-WB1", "Synthetic widebody generation 1", "SYN-CLASS-WB", 2, "SYN-ENGINE-W1B", "Synthetic turbofan W1B"),
    (300008, "SYN-TYPE-WB2", "Synthetic widebody generation 2", "SYN-CLASS-WB", 4, "SYN-ENGINE-W2A", "Synthetic turbofan W2A"),
    (300009, "SYN-TYPE-RJ1", "Synthetic regional jet generation 1", "SYN-CLASS-RJ", 2, "SYN-ENGINE-R1A", "Synthetic turbofan R1A"),
    (300010, "SYN-TYPE-RJ2", "Synthetic regional jet generation 2", "SYN-CLASS-RJ", 2, "SYN-ENGINE-R2A", "Synthetic turbofan R2A"),
    (300011, "SYN-TYPE-FRT1", "Synthetic freighter generation 1", "SYN-CLASS-FRT", 2, "SYN-ENGINE-F1A", "Synthetic turbofan F1A"),
    (300012, "SYN-TYPE-NB2", "Synthetic narrowbody generation 2", "SYN-CLASS-NB", 2, "SYN-ENGINE-N1B", "Synthetic turbofan N1B"),
)
FLEET_BY_ID = {row[0]: row for row in FLEET_DEFINITIONS}
NOISE_BY_ENGINE = {
    "N1A": "SYN-NOISE-CH3", "R1A": "SYN-NOISE-CH3", "W1A": "SYN-NOISE-CH3", "F1A": "SYN-NOISE-CH3",
    "N1B": "SYN-NOISE-CH4", "N2A": "SYN-NOISE-CH4", "R2A": "SYN-NOISE-CH4", "W1B": "SYN-NOISE-CH4",
    "N3A": "SYN-NOISE-CH14", "N3B": "SYN-NOISE-CH14", "W2A": "SYN-NOISE-CH14",
}
WEIGHTS_BY_CLASS = {"NB": (142_000, 92_000), "WB": (210_000, 138_000), "RJ": (84_000, 52_000), "FRT": (146_000, 88_000)}
BASE_STATE_BY_IATA = {
    "SFO": "SYN-ST-CA", "LAX": "SYN-ST-CA", "LAS": "SYN-ST-NV", "SEA": "SYN-ST-WA", "DEN": "SYN-ST-CO",
    "ORD": "SYN-ST-IL", "PHX": "SYN-ST-AZ", "BOS": "SYN-ST-MA", "MIA": "SYN-ST-FL",
}
BASE_REGION_BY_IATA = {
    "SFO": "SYN-RGN-WEST", "LAX": "SYN-RGN-WEST", "LAS": "SYN-RGN-WEST", "SEA": "SYN-RGN-WEST",
    "PHX": "SYN-RGN-WEST", "DEN": "SYN-RGN-MOUNTAIN", "ORD": "SYN-RGN-CENTRAL",
    "BOS": "SYN-RGN-EAST", "MIA": "SYN-RGN-EAST",
}
# Cohort name, inclusive i range, base configuration id.
COHORTS = (
    ("C1_FOUNDING_NB1", 0, 299, 300000),
    ("C2_LEGACY_RJ1", 300, 449, 300009),
    ("C3_MIDLIFE_WB1", 450, 549, 300006),
    ("C4_RENEWAL_NB3", 550, 749, 300004),
    ("C5_RENEWAL_WB2", 750, 799, 300008),
    ("C6_FREIGHT_FRT1", 800, 849, 300011),
    ("C7_CHURN_NB2", 850, 959, 300002),
    ("C8_SHORT_LIFE_RJ2", 960, 992, 300010),
)
C7_DURATIONS = (0, 1, 3, 14, 45, 90, 180, 365, 450)
# Event ordinal -> AH-03 row_sequence_number.  Ordinal 1 is storage/maintenance and ordinal 2 the
# return, so a zero-day spell lands on 20 and 30 exactly like the anchored 101010/101011 pair.
EVENT_ORDINALS = {"entry": 0, "hold": 1, "return": 2, "fleet": 3, "identity": 4, "periodic": 5}
STATE_FIELD_NUMBERS = tuple(range(17, 32)) + tuple(range(34, 43))
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
    assert sum(map(len, result.values())) == 204
    assert {name: len(result[name]) for name in TABLE_ORDER} == {
        "AIRCRAFT_MASTER": 19,
        "AIRCRAFT_HISTORY": 42,
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


def filler_aircraft_ids() -> list[int]:
    """The 993 sorted filler aircraft identifiers; ``a_i`` in specification 2.0.0."""
    values = sorted(set(range(1000, 2000)) - {1003} - ANCHOR_AIRCRAFT)
    assert len(values) == 993
    return values


def cohort_of(index: int) -> tuple[str, int, int, int]:
    for entry in COHORTS:
        if entry[1] <= index <= entry[2]:
            return entry
    raise AssertionError(index)


def service_start(index: int) -> str:
    """Specification 7.2 cohort entry-into-service date."""
    name, low, _high, _config = cohort_of(index)
    j = index - low
    if name in {"C1_FOUNDING_NB1", "C2_LEGACY_RJ1", "C3_MIDLIFE_WB1", "C6_FREIGHT_FRT1"}:
        return "2025-01-01"
    if name == "C4_RENEWAL_NB3":
        return plus_days("2028-01-03", 9 * j)
    if name == "C5_RENEWAL_WB2":
        return plus_days("2030-01-07", 21 * j)
    if name == "C7_CHURN_NB2":
        return plus_days("2026-01-05", 7 * j)
    if name == "C8_SHORT_LIFE_RJ2":
        return "2025-07-01"
    raise AssertionError(name)


def end_of_life(index: int) -> str | None:
    """Specification 7.2 cohort AM-08; None means the aircraft is still in the fleet."""
    name, low, _high, _config = cohort_of(index)
    j = index - low
    if name == "C1_FOUNDING_NB1":
        return plus_days("2032-01-05", 7 * index) if index < 100 else None
    if name == "C2_LEGACY_RJ1":
        return plus_days("2028-01-03", 7 * j)
    if name == "C8_SHORT_LIFE_RJ2":
        return plus_days("2027-07-05", 14 * j)
    return None


def service_end(index: int) -> str:
    return end_of_life(index) or DATA_HORIZON


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
        # Specification 7.1/7.2.  Every milestone is floored at 2025-01-01 so that no filler
        # aircraft can be visible at any Q03-CANONICAL month end (2015-01-31..2024-12-31).  The
        # resulting order-to-delivery compression for the 2025-01-01 cohorts is a declared
        # synthetic artifact; relaxing the floor would break the isolation argument silently.
        def floored(start: str, back: int) -> str:
            candidate = plus_days(start, -back)
            return max(ENRICHED_FLOOR, candidate)

        for i, aircraft_id in enumerate(filler_aircraft_ids()):
            row = base(aircraft_id)
            start = service_start(i)
            row.update({
                "aircraft_order_date": floored(start, 540),
                "aircraft_build_date": floored(start, 120),
                "aircraft_delivery_date": floored(start, 30),
                "aircraft_roll_out_date": floored(start, 100),
                "aircraft_first_flight_date": floored(start, 60),
                "aircraft_start_of_life_date": start,
                "aircraft_end_of_life_date": end_of_life(i),
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
        # Specification 6: thirteen referenced fleet definitions replace the first thirteen v1
        # filler definitions.  Filler definitions 300013..301995 keep the v1 template verbatim and
        # are deliberately unreferenced, which is what a real definition table looks like.
        for config_id, subseries, type_label, design_class, engines, engine_subseries, engine_label in FLEET_DEFINITIONS:
            type_suffix = subseries.removeprefix("SYN-TYPE-")
            engine_suffix = engine_subseries.removeprefix("SYN-ENGINE-")
            rows.append(row_for("AIRCRAFT_CONFIGURATION", {
                "aircraft_configuration_id": config_id,
                "aircraft_family": f"SYN-FAMILY-{type_suffix}",
                "aircraft_type": type_label,
                "aircraft_series": f"SYN-SERIES-{type_suffix}",
                "aircraft_subseries": subseries,
                "aircraft_manufacturer": f"SYN-MFR-{design_class.removeprefix('SYN-CLASS-')}",
                "aircraft_design_class": design_class,
                "engine_count": engines,
                "has_multiple_engine_types": False,
                "engine_manufacturer": f"SYN-ENG-MFR-{engine_suffix}",
                "engine_family": f"SYN-ENG-FAM-{engine_suffix}",
                "engine_type": engine_label,
                "engine_series": f"SYN-ENG-SER-{engine_suffix}",
                "engine_subseries": engine_subseries,
                "engine_propulsion_type": "TURBOFAN",
                "publish_date": "2026-08-31",
            }))
        for i in range(len(FLEET_DEFINITIONS), 1996):
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
        # D-0024 AH-34..AH-42.  These template values are exactly the constants specification 8
        # freezes for the six anchored aircraft, so no anchored event can mint a state version.
        "base_state": "SYN-ST-CA",
        "base_region": "SYN-RGN-WEST",
        "storage_location_type": None,
        "noise_certification": "SYN-NOISE-CH3",
        "has_winglets": False,
        "aircraft_registration_country": "Synthetic United States",
        "transponder_miscode": False,
        "maximum_landing_weight_lb": 142_000,
        "operating_empty_weight_lb": 92_000,
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


QUARTER_DAYS = ((1, 1), (4, 1), (7, 1), (10, 1))


def periodic_dates() -> tuple[str, ...]:
    return tuple(
        date(year, month, day).isoformat()
        for year in range(2025, 2035)
        for month, day in QUARTER_DAYS
    )


def filler_events(index: int) -> list[dict[str, Any]]:
    """Specification 7.3 and 7.4 event stream for filler aircraft ``a_index``.

    Returns events ordered by ``(date, ordinal)``.  Every event carries the mutation it names;
    everything else carries forward from the immediately preceding event.
    """
    name, low, _high, base_config = cohort_of(index)
    i, j = index, index - low
    start, end = service_start(index), service_end(index)
    events: list[dict[str, Any]] = [{"date": start, "kind": "entry", "config": base_config}]

    def add(day: str, kind: str, **params: Any) -> None:
        # No event is emitted at or after service_end; this truncation is load bearing for the
        # predicted 1.20 type and 1.31 engine version means.
        if start <= day < end:
            events.append({"date": day, "kind": kind, **params})

    def spell(day: str, duration: int, *, hold: str = "storage") -> None:
        add(day, hold, duration=duration)
        add(plus_days(day, duration), "return")

    if name == "C1_FOUNDING_NB1":
        if i % 5 == 0:
            k = i // 5
            spell(plus_days("2026-03-02", 7 * k), 30 + 17 * (k % 11))
        if i < 150:
            add(plus_days("2028-03-01", 5 * i), "fleet", config=300001)
        if 100 <= i < 150:
            add(plus_days("2032-06-01", 10 * (i - 100)), "fleet", config=300012)
        if 200 <= i < 300:
            add(plus_days("2030-06-03", 15 * (i - 200)), "fleet", config=300002)
        if i % 7 == 3:
            add("2029-05-01", "base", iata=WHITELIST[(i + 4) % 9])
        if i % 11 == 5:
            add("2031-02-03", "registration")
    elif name == "C2_LEGACY_RJ1":
        spell(plus_days("2026-02-02", 5 * j), 21, hold="maintenance")
        if j % 3 == 0:
            add(plus_days("2027-01-04", 9 * (j // 3)), "fleet", config=300010)
    elif name == "C3_MIDLIFE_WB1":
        spell(plus_days("2025-09-01", 3 * j), 7 + 3 * j)
        spell(plus_days("2028-07-03", 9 * j), 200 + 9 * j)
        if j % 2 == 0:
            add("2031-03-03", "fleet", config=300007)
    elif name == "C4_RENEWAL_NB3":
        if j % 3 == 0:
            add(plus_days(start, 1095), "fleet", config=300005)
        if j % 4 == 1:
            spell(plus_days(start, 500), 18, hold="maintenance")
    elif name == "C7_CHURN_NB2":
        for s in range(1, (j % 4) + 1):
            spell(plus_days(start, 150 + 500 * (s - 1) + 13 * (j % 25)), C7_DURATIONS[(7 * j + 13 * s) % 9])
        if j % 3 == 0:
            spell(plus_days(start, 90), 12, hold="maintenance")
    elif name == "C8_SHORT_LIFE_RJ2":
        if j % 2 == 0:
            spell(plus_days("2026-03-02", 30 * j), 60)
    # C5 and C6 carry no lifecycle event after entry; C6 is the deliberate flat control.

    lifecycle_dates = {event["date"] for event in events}
    for day in periodic_dates():
        if start < day < end and day not in lifecycle_dates:
            events.append({"date": day, "kind": "periodic"})
    events.sort(key=lambda event: (event["date"], EVENT_ORDINALS[
        "hold" if event["kind"] in {"storage", "maintenance"} else
        "identity" if event["kind"] in {"base", "registration"} else event["kind"]]))
    return events


def fleet_payload(config_id: int) -> dict[str, Any]:
    """AH-13..AH-16, AH-37 and the weight pair implied by a fleet configuration."""
    _cid, subseries, _label, design_class, _count, engine_subseries, _engine_label = FLEET_BY_ID[config_id]
    type_suffix = subseries.removeprefix("SYN-TYPE-")
    engine_suffix = engine_subseries.removeprefix("SYN-ENGINE-")
    landing, empty = WEIGHTS_BY_CLASS[design_class.removeprefix("SYN-CLASS-")]
    return {
        "aircraft_configuration_id": config_id,
        "aircraft_code_iata": f"SYN-SERIES-{type_suffix}",
        "aircraft_code_icao": f"SYN-SUBTYPE-{type_suffix}",
        "aircraft_value_sub_series": subseries,
        "noise_certification": NOISE_BY_ENGINE[engine_suffix],
        "maximum_landing_weight_lb": landing,
        "operating_empty_weight_lb": empty,
    }


def base_payload(iata: str) -> dict[str, Any]:
    return {
        "base_airport": f"Synthetic base {iata}",
        "base_airport_code_iata": iata,
        "base_city": f"Synthetic city {iata}",
        "base_state": BASE_STATE_BY_IATA[iata],
        "base_region": BASE_REGION_BY_IATA[iata],
    }


def storage_class(duration: int) -> str:
    if duration >= 180:
        return "SYN-STG-LONG-TERM"
    return "SYN-STG-SHORT-TERM" if duration >= 1 else "SYN-STG-SAME-DAY"


def enriched_history(masters: Sequence[Mapping[str, Any]], available: Iterable[int]) -> list[dict[str, Any]]:
    """Specification 7.3 / 7.4 / 7.5 filler event stream for the 993 enriched aircraft."""
    ids = iter(available)
    rows: list[dict[str, Any]] = []
    for index, aircraft_id in enumerate(filler_aircraft_ids()):
        name, low, _high, base_config = cohort_of(index)
        j = index - low
        start = service_start(index)
        state = fleet_payload(base_config) | base_payload(WHITELIST[index % 9]) | {
            "start_aircraft_status": "In Service",
            "aircraft_registration_number": f"SYN-REG-{aircraft_id}",
            "aircraft_transponder_code": f"SYN-XPDR-{aircraft_id}",
            "aircraft_registration_country_code_iso": "US",
            "aircraft_registration_region": "SYN-US",
            "aircraft_cargo": "FREIGHTER" if name == "C6_FREIGHT_FRT1" else "PASSENGER",
            "storage_location": None,
            "storage_airport_code_iata": None,
            "storage_location_type": None,
            "base_country": "United States",
            "apu_type": None,
            "aircraft_width_m": 35.0,
            "operating_maximum_takeoff_weight_lb": 165_000,
            "certified_maximum_takeoff_weight_lb": 170_000,
            "has_winglets": name in {"C4_RENEWAL_NB3", "C5_RENEWAL_WB2", "C7_CHURN_NB2"},
            "aircraft_registration_country": "Synthetic United States",
            "transponder_miscode": name == "C7_CHURN_NB2" and j % 17 == 4,
        }
        miscode_clear_from = plus_days(start, 400)
        periodic_index = 0
        for event in filler_events(index):
            kind = event["kind"]
            if kind == "entry":
                provenance = ("SYN-ENTRY-INTO-SERVICE", "SYNTHETIC_LIFECYCLE")
            elif kind == "storage":
                state = state | {
                    "start_aircraft_status": "Storage",
                    "storage_location": f"SYN-AP-{WHITELIST[(index + 3) % 9]}",
                    "storage_airport_code_iata": WHITELIST[(index + 3) % 9],
                    "storage_location_type": storage_class(event["duration"]),
                }
                provenance = ("SYN-STORAGE-IN", "SYNTHETIC_LIFECYCLE")
            elif kind == "maintenance":
                state = state | {"start_aircraft_status": "Maintenance"}
                provenance = ("SYN-MAINTENANCE-IN", "SYNTHETIC_LIFECYCLE")
            elif kind == "return":
                state = state | {
                    "start_aircraft_status": "In Service",
                    "storage_location": None, "storage_airport_code_iata": None,
                    "storage_location_type": None,
                }
                provenance = ("SYN-RETURN-TO-SERVICE", "SYNTHETIC_LIFECYCLE")
            elif kind == "fleet":
                previous = state["aircraft_value_sub_series"]
                state = state | fleet_payload(event["config"])
                if name == "C1_FOUNDING_NB1" and index % 5 == 2 and event["config"] == 300001:
                    state = state | {"has_winglets": True}
                changed_type = state["aircraft_value_sub_series"] != previous
                provenance = ("SYN-TYPE-CHANGE" if changed_type else "SYN-ENGINE-CHANGE", "SYNTHETIC_LIFECYCLE")
            elif kind == "base":
                state = state | base_payload(event["iata"])
                provenance = ("SYN-BASE-CHANGE", "SYNTHETIC_LIFECYCLE")
            elif kind == "registration":
                state = state | {
                    "aircraft_registration_number": f"SYN-REG-{aircraft_id}-R2",
                    "aircraft_registration_country": "Synthetic United States (reregistered)",
                }
                provenance = ("SYN-REGISTRATION-CHANGE", "SYNTHETIC_LIFECYCLE")
            elif kind == "periodic":
                updates: dict[str, Any] = {}
                if periodic_index % 4 == 3:
                    updates["maximum_landing_weight_lb"] = state["maximum_landing_weight_lb"] + 250
                    updates["operating_empty_weight_lb"] = state["operating_empty_weight_lb"] + 150
                if state["transponder_miscode"] and event["date"] >= miscode_clear_from:
                    updates["transponder_miscode"] = False
                if name == "C3_MIDLIFE_WB1" and j % 3 == 1 and event["date"] == "2030-04-01":
                    updates["has_winglets"] = True
                state = state | updates
                periodic_index += 1
                provenance = ("SYN-OBSERVATION", "SYNTHETIC_PERIODIC")
            else:
                raise AssertionError(kind)
            ordinal = EVENT_ORDINALS[
                "hold" if kind in {"storage", "maintenance"} else
                "identity" if kind in {"base", "registration"} else kind]
            sequence = 10 * (ordinal + 1)
            row = history_template(next(ids), aircraft_id, sequence, event["date"])
            row.update(state)
            row["start_event"], row["event_source"] = provenance
            rows.append(row)
    return rows


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
            # row-local template values, so the deliberately irrelevant AH-12 cannot leak.  D-0024
            # widened the watched set to AH-17..AH-31 plus AH-34..AH-42.
            for field_number in STATE_FIELD_NUMBERS:
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
        used = {row["aircraft_history_id"] for row in rows}
        available = (value for value in range(101000, 200000) if value not in used)
        rows.extend(enriched_history(masters, available))
    return rows


ROUTES = tuple((WHITELIST[a], WHITELIST[b]) for a in range(9) for b in range(9) if a != b)
P_MKT = tuple(f"SYN-MKT-W27-{c:02d}" for c in range(16))
P_OP = tuple(f"SYN-OP-W27-{c:02d}" for c in range(16))
W27_CABIN = {
    100.0: (0.0, 10.0, 10.0, 90.0),
    180.0: (8.0, 20.0, 20.0, 152.0),
    240.0: (12.0, 28.0, 30.0, 200.0),
    320.0: (16.0, 44.0, 40.0, 260.0),
}
W27_FREQUENCIES = (2, 3, 5, 7, 10, 14)
W27_TOTALS = (100.0, 180.0, 240.0, 320.0)
W27_MOD_FIELDS = (
    "total_seats", "weekly_frequency", "departure_terminal", "arrival_terminal",
    "business_class_seats", "premium_economy_seats", "scheduled_block_minutes",
    "equipment_subtype_code_iata", "is_codeshare", "service_type_iata",
)
W27_MOD_NEW_VALUES = {
    "total_seats": 186.0, "weekly_frequency": 8, "departure_terminal": "SYN-T-W27-A2",
    "arrival_terminal": "SYN-T-W27-B2", "business_class_seats": 26.0,
    "premium_economy_seats": 26.0, "scheduled_block_minutes": 135,
    "equipment_subtype_code_iata": "SYN-EQ-WB", "is_codeshare": True, "service_type_iata": "F",
}


def w27_dates() -> tuple[str, ...]:
    return tuple(plus_days(W27_FIRST, 7 * k) for k in range(W27_WEEKS))


def w27_eligible() -> tuple[str, ...]:
    """The 24 eligible complete 2027 knowledge dates, ascending; ``E`` in specification 9.1."""
    return tuple(d for k, d in enumerate(w27_dates()) if k not in {W27_INCOMPLETE_INDEX, W27_MISSING_INDEX})


def w27_physical() -> tuple[str, ...]:
    """The 25 dates that physically carry 2027 rows: the 24 eligible plus the incomplete date."""
    return tuple(d for k, d in enumerate(w27_dates()) if k != W27_MISSING_INDEX)


def w27_defaults() -> dict[str, Any]:
    return {
        "service_type_iata": "J", "effective_date": "2027-08-01", "discontinue_date": "2027-12-31",
        "departure_terminal": "SYN-T-W27-A", "arrival_terminal": "SYN-T-W27-B",
        "is_operating_monday": True, "is_operating_tuesday": True, "is_operating_wednesday": True,
        "is_operating_thursday": True, "is_operating_friday": True, "is_operating_saturday": True,
        "is_operating_sunday": True, "days_pattern": "1234567", "weekly_frequency": 7,
        "passenger_departure_utc_time": "16:00:00", "passenger_arrival_utc_time": "18:00:00",
        "passenger_departure_local_time": "09:00:00", "passenger_arrival_local_time": "11:00:00",
        "arrival_day_indicator": 0, "scheduled_block_minutes": 120,
        "equipment_subtype_code_iata": "SYN-EQ-NB", "total_seats": 180.0, "first_class_seats": 8.0,
        "business_class_seats": 20.0, "premium_economy_seats": 20.0, "economy_class_seats": 152.0,
        "is_codeshare": False, "codeshare_carrier_internal": None,
        "number_of_intermediate_stops": 0, "intermediate_stop_station_codes_iata": None,
    }


def w27_route(index: int) -> dict[str, Any]:
    origin, destination = ROUTES[index % 72]
    return {"departure_station_code_iata": origin, "arrival_station_code_iata": destination}


def schedule_2027_plan() -> list[tuple[str, str, dict[str, Any]]]:
    """Specification 9.2 traversal of ``(cohort_rank, key_index, physical_date_index)``.

    Returns ``(schedule_key, publish_date, watched_values)`` in the exact order that allocates the
    PRF ordinal block ``400000 + m``.  Three specification defects are corrected here under section
    3.4 step 2, because the section 9.3 aggregate invariants are the authority when the prose and
    the aggregates disagree:

    * ``MOD`` field index 8 carries ``codeshare_carrier_internal`` on every date and transitions
      only ``is_codeshare``.  Transitioning both would emit two modification rows for one key and
      make ``EXACT_KEY_PRESERVING_MODIFICATION`` 76 rather than the frozen 69.
    * ``SHIFTOLD`` keeps the default operating range so that it overlaps ``SHIFTNEW``.  The
      literal contiguous non-overlapping ranges are exactly the conservative false negative
      ``SOURCE_CONTRACT.md`` names, and would yield zero ``CANDIDATE_UNIQUE`` rows instead of 23.
    * ``ADD``, ``REM`` and ``REAP`` take disjoint route offsets.  Under the literal "as for CORE"
      rule ``ADD`` and ``REM`` share a full candidate signature at the very pair where one is
      added and the other removed, which would silently pair them.
    """
    eligible, physical = w27_eligible(), w27_physical()
    base = w27_defaults()
    plan: list[tuple[str, str, dict[str, Any]]] = []

    def emit(key: str, dates: Sequence[str], values_for: Any) -> None:
        for day in dates:
            plan.append((key, day, dict(values_for(day))))

    def pool(index: int) -> dict[str, Any]:
        return {"marketing_carrier_internal": P_MKT[index % 16], "operating_carrier_internal": P_OP[index % 16]}

    # 1 CORE: always present, byte-identical content, and therefore the market protection every
    # other cohort relies on.  16 carriers x 72 routes = all 1,152 pool markets.
    for j in range(2000):
        values = base | pool(j) | {"flight_number": 1900 + j % 100} | w27_route(j // 16)
        emit(f"SYN-SK-W27-CORE-{j:05d}", physical, lambda _d, v=values: v)

    # 2 MOD: exactly one watched field changes at exactly one adjacent pair.
    for j in range(69):
        pair = (j // 3) + 1
        field = W27_MOD_FIELDS[j % 10]
        before = base | pool(j) | {"flight_number": 1900 + j % 100} | w27_route(j // 16)
        if field == "is_codeshare":
            before = before | {"codeshare_carrier_internal": P_MKT[(j + 1) % 16]}
        after = before | {field: W27_MOD_NEW_VALUES[field]}
        cutover = eligible[pair]
        emit(f"SYN-SK-W27-MOD-{j:03d}", physical, lambda d, b=before, a=after, c=cutover: a if d >= c else b)

    # 3 ADD / 4 REM: presence alone.  Disjoint route offsets keep them unpaired.
    for a in range(23):
        values = base | pool(a) | {"flight_number": 1900 + a} | w27_route(a + 24)
        emit(f"SYN-SK-W27-ADD-{a:03d}", eligible[a + 1:], lambda _d, v=values: v)
    for a in range(23):
        values = base | pool(a) | {"flight_number": 1900 + a} | w27_route(a + 48)
        emit(f"SYN-SK-W27-REM-{a:03d}", eligible[:a + 1], lambda _d, v=values: v)

    # 5 SHIFTOLD / 6 SHIFTNEW: one key-changing amendment per pair, resolvable to CANDIDATE_UNIQUE.
    for q in range(23):
        shared = base | {"marketing_carrier_internal": P_MKT[q % 16], "operating_carrier_internal": P_OP[q % 16],
                         "flight_number": 1900 + q} | w27_route(q)
        old = shared
        new = shared | {"effective_date": "2027-11-01", "discontinue_date": "2027-12-31"}
        emit(f"SYN-SK-W27-SHIFTOLD-{q:03d}", eligible[:q + 1], lambda _d, v=old: v)
        emit(f"SYN-SK-W27-SHIFTNEW-{q:03d}", eligible[q + 1:], lambda _d, v=new: v)

    # 7 AMBOLD / 8 AMBNEWA + AMBNEWB: two overlapping candidates, so the group stays ambiguous.
    for g in range(6):
        pair = 2 * g + 1
        shared = base | {"marketing_carrier_internal": P_MKT[(g + 8) % 16],
                         "operating_carrier_internal": P_OP[(g + 8) % 16],
                         "flight_number": 1950 + g} | w27_route(60 + g)
        emit(f"SYN-SK-W27-AMBOLD-{g:02d}", eligible[:pair], lambda _d, v=shared: v)
        for suffix, window in (("A", ("2027-11-01", "2027-12-31")), ("B", ("2027-11-08", "2028-01-07"))):
            values = shared | {"effective_date": window[0], "discontinue_date": window[1]}
            emit(f"SYN-SK-W27-AMBNEW{suffix}-{g:02d}", eligible[pair:], lambda _d, v=values: v)

    # 9 UNPOLD / 10 UNPNEW: removal and addition eight pairs apart, so they can never pair.
    for u in range(6):
        pair = u + 2
        shared = base | {"marketing_carrier_internal": P_MKT[(u + 4) % 16],
                         "operating_carrier_internal": P_OP[(u + 4) % 16],
                         "flight_number": 1980 + u} | w27_route(40 + u)
        emit(f"SYN-SK-W27-UNPOLD-{u:02d}", eligible[:pair], lambda _d, v=shared: v)
        emit(f"SYN-SK-W27-UNPNEW-{u:02d}", eligible[pair + 8:], lambda _d, v=shared: v)

    # 11 REAP: absent at exactly one eligible date, mirroring SYN-SK-REAPPEAR_400.
    for r in range(8):
        gap = 2 * r + 2
        values = base | pool(r) | {"flight_number": 1960 + r} | w27_route(r + 30)
        emit(f"SYN-SK-W27-REAP-{r:03d}", eligible[:gap] + eligible[gap + 1:], lambda _d, v=values: v)

    # 12 MKTENT / 13 MKTEXIT: genuine market entries and exits on carriers nothing else uses.
    for m in range(12):
        pair = 23 if m <= 3 else 2 * (m - 4) + 3
        operating = P_OP[m % 16] if m <= 1 else f"SYN-OP-W27-ENT-{m:02d}"
        values = base | {"marketing_carrier_internal": f"SYN-MKT-W27-ENT-{m:02d}",
                         "operating_carrier_internal": operating,
                         "flight_number": 1900 + m} | w27_route(m)
        emit(f"SYN-SK-W27-MKTENT-{m:02d}", eligible[pair:], lambda _d, v=values: v)
    for m in range(12):
        pair = 23 if m <= 2 else 2 * (m - 3) + 2
        values = base | {"marketing_carrier_internal": f"SYN-MKT-W27-EXIT-{m:02d}",
                         "operating_carrier_internal": f"SYN-OP-W27-EXIT-{m:02d}",
                         "flight_number": 1900 + m} | w27_route(20 + m)
        emit(f"SYN-SK-W27-MKTEXIT-{m:02d}", eligible[:pair], lambda _d, v=values: v)

    # 14-16 CLK: the two-clock cohort.  Markets are pool markets, so no Q06 event is produced.
    july = {"effective_date": "2027-07-01", "discontinue_date": "2027-07-31"}
    for c in range(4):
        values = base | pool(c) | {"flight_number": 1900 + c} | w27_route(8 + c) | july
        emit(f"SYN-SK-W27-CLK-{c:02d}", eligible[:23] + (w27_dates()[W27_INCOMPLETE_INDEX],), lambda _d, v=values: v)
    for c in range(4, 8):
        values = base | pool(c) | {"flight_number": 1900 + c} | w27_route(12 + c) | july
        emit(f"SYN-SK-W27-CLK-{c:02d}", eligible[23:], lambda _d, v=values: v)
    for c in (8, 9):
        values = base | pool(c) | {"flight_number": 1900 + c} | w27_route(20 + c) | {
            "effective_date": "2027-06-01", "discontinue_date": "2027-07-04"}
        emit(f"SYN-SK-W27-CLK-{c:02d}", physical, lambda _d, v=values: v)
    for c in (10, 11):
        values = base | pool(c) | {"flight_number": 1900 + c} | w27_route(20 + c) | july | {
            "is_operating_tuesday": False, "is_operating_wednesday": False,
            "is_operating_thursday": False, "is_operating_friday": False,
            "is_operating_saturday": False, "is_operating_sunday": False,
            "days_pattern": "1000000", "weekly_frequency": 1}
        emit(f"SYN-SK-W27-CLK-{c:02d}", physical, lambda _d, v=values: v)

    # 17 CAP: eight routes times three marketing identities.  The third block is codeshare-only;
    # four of its keys resolve to a physical service and four reproduce UNRESOLVED_PHYSICAL_SERVICE.
    for n in range(24):
        block, slot = n // 8, n % 8
        values = base | july | w27_route(slot)
        base_metal = f"SYN-CAR-W27-{slot:02d}"
        if block <= 1:
            total = W27_TOTALS[n % 4]
            first, business, premium, economy = W27_CABIN[total]
            # Block 0 is the physical base metal: marketing and operating resolve to one airline,
            # which is what SOURCE_CONTRACT.md requires before operating capacity may be counted.
            # Block 1 is a marketing-only identity on the same operating market, so the market has
            # sixteen keys and exactly eight counted operating representatives.
            values = values | {
                "marketing_carrier_internal": base_metal if block == 0 else P_MKT[n],
                "operating_carrier_internal": base_metal,
                "flight_number": (1900 if block == 0 else 1910) + slot,
                "weekly_frequency": W27_FREQUENCIES[n % 6], "total_seats": total,
                "first_class_seats": first, "business_class_seats": business,
                "premium_economy_seats": premium, "economy_class_seats": economy,
            }
        else:
            resolved = slot <= 3
            values = values | {
                "marketing_carrier_internal": f"SYN-MKT-W27-CSH-{slot:02d}",
                "operating_carrier_internal": base_metal if resolved else f"SYN-OP-W27-CSH-{slot - 4:02d}",
                "flight_number": (1900 + slot) if resolved else (1920 + slot - 4),
                "is_codeshare": True, "codeshare_carrier_internal": P_MKT[(n + 4) % 16],
            }
            if n == 20:
                values = values | {"total_seats": 181.0}
            if n == 21:
                values = values | {"first_class_seats": None}
            if n == 22:
                values = values | {"premium_economy_seats": 40.0, "economy_class_seats": 30.0}
        emit(f"SYN-SK-W27-CAP-{n:03d}", physical, lambda _d, v=values: v)

    # 18 INERT: physically retained at the incomplete date, semantically inert everywhere.
    incomplete = (w27_dates()[W27_INCOMPLETE_INDEX],)
    for n in range(200):
        values = base | pool(n) | {"flight_number": 1900 + n % 100} | w27_route(n)
        emit(f"SYN-SK-W27-INERT-{n:03d}", incomplete, lambda _d, v=values: v)
    return plan


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
        # D-0025: the 2027 knowledge block.  Ordinal block 400000 + m is disjoint from every v1
        # block, so no v1 row's PRF input changes.
        for m, (key, publish_date, watched) in enumerate(schedule_2027_plan()):
            rows.append(complete({"schedule_key":key,"publish_date":publish_date} | watched, 400000 + m))
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
    if scale == "demo":
        # D-0025: 26 weekly 2027 dates.  Every one is after 2026-10-26, which is what preserves
        # SYN-SK-GAP_CONTROL_001's previous-eligible-complete date and the ten v1 rows including
        # SC-05, since no v2 row is emitted at any v1 snapshot date.
        counts = defaultdict(int)
        for _key, publish_date, _watched in schedule_2027_plan():
            counts[publish_date] += 1
        for k, day in enumerate(w27_dates()):
            if k == W27_INCOMPLETE_INDEX:
                data.append((day, True, False, f"SC-{day.replace('-','')}-INCOMPLETE", 0, counts[day], "INCOMPLETE_RETAINED"))
            elif k == W27_MISSING_INDEX:
                data.append((day, False, False, f"SC-{day.replace('-','')}-MISSING", 0, 0, "MISSING_DECLARED"))
            else:
                data.append((day, True, True, f"SC-{day.replace('-','')}-COMPLETE", 0, counts[day], "COMPLETE_VALIDATED"))
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
        rows.extend(enriched_forward(anchors))
    return rows


def enriched_forward(anchors: set[int]) -> list[dict[str, Any]]:
    """Specification 10.2: HEUR-PF 400, SCHED-PF 8000, UNION-OVERLAP-PF 500, PLAIN-PF 1091."""
    assert HEURISTIC_LEGS, "aircraft_flights must run before passenger_forward"
    rows: list[dict[str, Any]] = []

    def forward(source_id: int | None, marketing: str, operating: str, number: int, day: str,
                origin: str, destination: str, publish: str) -> dict[str, Any]:
        row = forward_template(source_id)
        row.update({
            "marketing_carrier_internal": marketing, "operating_carrier_internal": operating,
            "flight_number": number, "operating_date": day, "publish_date": publish,
            "departure_station_code_iata": origin, "arrival_station_code_iata": destination,
            "passenger_departure_time_local": f"{day}T09:00:00", "passenger_arrival_time_local": f"{day}T11:00:00",
            "passenger_departure_time_utc": f"{day}T16:00:00", "passenger_arrival_time_utc": f"{day}T18:00:00",
        })
        return row

    # HEUR-PF: 340 legs get exactly one compatible plan; 30 legs get two, which is an ambiguous
    # candidate group of two members rather than a heuristic candidate.
    for m, actual in enumerate(HEURISTIC_LEGS[:370]):
        day = actual["flight_departure_date"]
        origin = actual["departure_airport_code"].removeprefix("SYN-AP-")
        destination = actual["arrival_airport_code"].removeprefix("SYN-AP-")
        number = int(actual["flight_number"])
        rows.append(forward(None, actual["marketing_carrier_code"], actual["operating_carrier_code"],
                            number, day, origin, destination, "2027-01-04"))
        if m >= 340:
            rows.append(forward(None, P_MKT[(m + 3) % 16], actual["operating_carrier_code"],
                                number, day, origin, destination, "2027-01-04"))

    def plan(index: int, key_index: int, offset: int, epoch: str = FUL_EPOCH) -> dict[str, Any]:
        facts = core_key_facts(key_index)
        return forward(None, facts["marketing_carrier_internal"], facts["operating_carrier_internal"],
                       facts["flight_number"], plus_days(epoch, offset),
                       facts["departure_station_code_iata"], facts["arrival_station_code_iata"],
                       eligible_knowledge_date(index))

    for n in range(8000):
        rows.append(plan(n, n % 2000, 7 * (n % 21) + 5))
    for n in range(500):
        rows.append(plan(n, n, 7 * (n % 21) + 3))
    # PLAIN-PF: forward-only 2027 plans, before the operating window, so no actual leg and no
    # historical row can share a canonical key with them.
    for n in range(1091):
        facts = core_key_facts((n + 900) % 2000)
        rows.append(forward(None, facts["marketing_carrier_internal"], facts["operating_carrier_internal"],
                            facts["flight_number"], plus_days("2027-04-01", n % 60),
                            facts["departure_station_code_iata"], facts["arrival_station_code_iata"],
                            "2027-01-04"))
    pool = iter(value for value in range(5000, 8000) if value not in anchors)
    for row in rows:
        row["forward_source_row_id"] = next(pool, None)
    assert len(rows) == 9991
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
        rows.extend(enriched_historical(anchors))
    return rows


def w27_plan_defaults() -> dict[str, Any]:
    """Shared 2027 passenger clock payload; specification 10.1."""
    return {"publish_date":"2027-01-04","effective_date":"2027-08-01",
            "passenger_departure_local_time":"09:00:00","passenger_arrival_local_time":"11:00:00",
            "passenger_departure_utc_time":"16:00:00","passenger_arrival_utc_time":"18:00:00",
            "departure_utc_offset_minutes":-420.0,"arrival_utc_offset_minutes":-420.0,
            "arrival_day_indicator":0,"equipment_subtype_code_iata":"SYN-EQ-NB","total_seats":180.0,
            "is_codeshare":False,"number_of_intermediate_stops":0,"intermediate_stop_station_codes_iata":None}


def core_key_facts(k: int) -> dict[str, Any]:
    """SS-04, SS-05, SS-06, SS-10 and SS-11 of ``SYN-SK-W27-CORE-{k:05d}``."""
    origin, destination = ROUTES[(k // 16) % 72]
    return {"schedule_key": f"SYN-SK-W27-CORE-{k:05d}", "marketing_carrier_internal": P_MKT[k % 16],
            "operating_carrier_internal": P_OP[k % 16], "flight_number": 1900 + k % 100,
            "departure_station_code_iata": origin, "arrival_station_code_iata": destination}


def eligible_knowledge_date(index: int) -> str:
    eligible = w27_eligible()
    return eligible[index % len(eligible)]


def enriched_historical(anchors: set[int]) -> list[dict[str, Any]]:
    """Specification 10.1: FUL-PH 700, SCHED-PH 6800, UNION-OVERLAP-PH 500, PLAIN-PH 1987."""
    assert len(FULFILMENT_LEGS) == 700, "aircraft_flights must run before passenger_historical"
    used = set(anchors) | {row["flight_id"] for row in FULFILMENT_LEGS}
    pool = iter(value for value in range(5000, 8000) if value not in used)
    rows: list[dict[str, Any]] = []
    base = w27_plan_defaults()

    # FUL-PH: PH-01 deliberately equals AF-01, which is what EXACT_FULFILLMENT is defined on.
    # The last 100 legs form 50 two-leg stopover plans that share one canonical key each.
    for m, actual in enumerate(FULFILMENT_LEGS):
        origin = actual["departure_airport_code"].removeprefix("SYN-AP-")
        destination = actual["arrival_airport_code"].removeprefix("SYN-AP-")
        stops, intermediate = 0, None
        if m >= 600:
            # The two legs of a stopover plan share one canonical key: both PH rows carry the
            # overall plan endpoints with the connecting airport as the single intermediate stop.
            pair = (m - 600) // 2
            origin, intermediate = WHITELIST[pair % 9], WHITELIST[(pair + 1) % 9]
            destination, stops = WHITELIST[(pair + 2) % 9], 1
        row = historical_template(actual["flight_id"])
        row.update(base | {
            "schedule_key": core_key_facts(m % 2000)["schedule_key"],
            "publish_date": eligible_knowledge_date(m),
            "operating_date": actual["flight_departure_date"],
            "marketing_carrier_internal": actual["marketing_carrier_code"],
            "operating_carrier_internal": actual["operating_carrier_code"],
            "flight_number": int(actual["flight_number"]),
            "departure_station_code_iata": origin, "arrival_station_code_iata": destination,
            "number_of_intermediate_stops": stops, "intermediate_stop_station_codes_iata": intermediate,
        })
        rows.append(row)

    def plan(index: int, key_index: int, offset: int, source_id: int | None, schedule_key: bool = True) -> dict[str, Any]:
        facts = core_key_facts(key_index)
        row = historical_template(source_id)
        row.update(base | {k: v for k, v in facts.items() if schedule_key or k != "schedule_key"} | {
            "publish_date": eligible_knowledge_date(index),
            "operating_date": plus_days("2027-08-01", offset)})
        if not schedule_key:
            row["schedule_key"] = None
        return row

    # SCHED-PH: operating dates on offsets congruent to 1 modulo 7, disjoint from every other block.
    for n in range(6800):
        rows.append(plan(n, n % 2000, 7 * (n % 21) + 1, None))
    # UNION-OVERLAP-PH: 500 canonical keys the forward side reproduces exactly.
    for n in range(500):
        rows.append(plan(n, n, 7 * (n % 21) + 3, None))
    # PLAIN-PH: deliberately schedule-keyless historical evidence.
    for n in range(1987):
        rows.append(plan(n, (n + 500) % 2000, 7 * (n % 21) + 4, None, schedule_key=False))
    for row in rows[700:]:
        row["historical_source_row_id"] = next(pool, None)
    assert len(rows) == 9987
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


ANCHOR_FLIGHT_IDS = frozenset({5101,5102,5103,7101,7102,7199,7200,8001,8002,8003,8101,8102,8103,8104,8105,8106,8107,8108,8109,8110,8111,8112,8205,8206})
PH_ANCHOR_IDS = frozenset({5001, 5101, 5102, 5103, 7200, 7301, 7302, 7303, 7304, 7305, 7306, 7309, 7310})
FULFILMENT_LEGS: list[dict[str, Any]] = []
HEURISTIC_LEGS: list[dict[str, Any]] = []


def aircraft_flights(scale: str, masters: Sequence[Mapping[str, Any]],
                     history: Sequence[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
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
        # AVAIL excludes the 24 anchored AF-01 values and the 13 anchored PH-01 values, so the
        # only place PH-01 and AF-01 deliberately coincide is the 700-row FUL fulfilment block.
        used={row["flight_id"] for row in rows} | PH_ANCHOR_IDS
        available=[value for value in range(5000,8999) if value not in used]
        assert len(available)==3966
        filler,fulfilment,heuristic=enriched_flights(masters,history,available)
        rows.extend(filler)
        FULFILMENT_LEGS.clear(); FULFILMENT_LEGS.extend(fulfilment)
        HEURISTIC_LEGS.clear(); HEURISTIC_LEGS.extend(heuristic)
    return rows


ANOMALY_CODES = (
    "SELF_LOOP", "CYCLE", "MISSING_TARGET", "DIFFERENT_AIRCRAFT", "OUTSIDE_SELECTED_DAY",
    "BACKWARD_TIME", "BROKEN_CONTINUITY", "DIVERSION_ENDPOINT_CONFLICT", "CANCELLED",
    "MISSING_TIME", "UNKNOWN_OR_INVALID_CANCELLATION_FLAG",
)
ANOMALY_AIRCRAFT_INDEXES = (30, 90, 150, 210, 270, 330, 390, 450, 510, 570)
ROTATION_COUNT = 609
ROTATION_FIRST_DATE = "2027-06-01"
FUL_EPOCH = "2027-08-01"


def rotation_leg_counts() -> list[int]:
    """300 four-leg, 120 three-leg, 60 five-leg and 129 single-leg rotations.

    Single-leg rotations avoid ``r mod 5 == 0`` so that all 122 late-departing rotations are
    multi-leg and their final leg genuinely crosses UTC midnight, and avoid ``r mod 20 == 13`` so
    that every anomaly-carrying rotation has a link to corrupt.
    """
    counts: list[int | None] = [None] * ROTATION_COUNT
    singles = [r for r in range(ROTATION_COUNT) if r % 5 and r % 20 != 13][:129]
    for r in singles:
        counts[r] = 1
    for position, r in enumerate(r for r in range(ROTATION_COUNT) if counts[r] is None):
        counts[r] = 4 if position < 300 else (3 if position < 420 else 5)
    assert Counter(counts) == {4: 300, 3: 120, 5: 60, 1: 129}
    return [value for value in counts if value is not None]


def aircraft_timeline(masters: Sequence[Mapping[str, Any]],
                      history: Sequence[Mapping[str, Any]]) -> dict[int, list[tuple[str, int, str, int | None]]]:
    """Per-aircraft ordered ``(date, row_sequence, status, configuration)`` for as-of resolution."""
    timeline: dict[int, list[tuple[str, int, str, int | None]]] = defaultdict(list)
    for row in history:
        timeline[row["aircraft_id"]].append((row["start_event_date"], row["row_sequence_number"],
                                             row["start_aircraft_status"], row["aircraft_configuration_id"]))
    for entries in timeline.values():
        entries.sort()
    return timeline


def visible_state(entries: Sequence[tuple[str, int, str, int | None]], day: str) -> tuple[str, int | None] | None:
    eligible = [entry for entry in entries if entry[0] <= day]
    return (eligible[-1][2], eligible[-1][3]) if eligible else None


def enriched_flights(masters: Sequence[Mapping[str, Any]], history: Sequence[Mapping[str, Any]],
                     available: Sequence[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Specification 11.  Returns ``(rows, fulfilment_legs)``; the second feeds ``FUL-PH``."""
    ids = filler_aircraft_ids()
    timeline = aircraft_timeline(masters, history)
    master_by_id = {row["aircraft_id"]: row for row in masters}
    configs = {config_id: FLEET_BY_ID[config_id] for config_id in FLEET_BY_ID}
    rot, ful, heur, anom, unm = (available[0:1989], available[1989:2689], available[2689:3089],
                                 available[3089:3229], available[3229:3876])
    heuristic: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    def labels(aircraft_id: int, day: str) -> dict[str, Any]:
        state = visible_state(timeline.get(aircraft_id, ()), day)
        config = FLEET_BY_ID.get(state[1]) if state else None
        if config is None:
            return {"aircraft_type": "Synthetic narrowbody B", "aircraft_code_iata": "SB1", "aircraft_family": "SYN-FAMILY-B"}
        suffix = config[1].removeprefix("SYN-TYPE-")
        return {"aircraft_type": config[2], "aircraft_code_iata": f"SYN-SERIES-{suffix}",
                "aircraft_family": f"SYN-FAMILY-{suffix}"}

    def leg(flight_id: int, aircraft_id: int, carrier: int, number: int, local_day: str,
            origin: str, destination: str, depart: datetime | None, arrive: datetime | None,
            next_id: int | None, **overrides: Any) -> dict[str, Any]:
        row = actual_template(flight_id)
        row.update({
            "aircraft_id": aircraft_id,
            "operating_carrier_code": P_OP[carrier % 16], "marketing_carrier_code": P_MKT[carrier % 16],
            "flight_number": str(number), "flight_departure_date": local_day,
            "flight_departure_date_utc": local_day if depart is None else depart.date().isoformat(),
            "departure_airport_code": f"SYN-AP-{origin}", "arrival_airport_code": f"SYN-AP-{destination}",
            "actual_gate_departure_time_utc": None if depart is None else depart.isoformat(),
            "actual_gate_arrival_time_utc": None if arrive is None else arrive.isoformat(),
            "next_flight_id": next_id,
        })
        row.update(labels(aircraft_id, local_day))
        row.update(overrides)
        return row

    # --- 11.3 rotations -------------------------------------------------------------------------
    counts = rotation_leg_counts()
    assigned: dict[str, set[int]] = defaultdict(set)
    cursor = 0
    rotations: list[dict[str, Any]] = []
    for r in range(ROTATION_COUNT):
        day = plus_days(ROTATION_FIRST_DATE, r % 30)
        index = (7 * r) % 993
        for _step in range(993):
            aircraft_id = ids[index]
            master = master_by_id[aircraft_id]
            state = visible_state(timeline.get(aircraft_id, ()), day)
            existing = (master["aircraft_start_of_life_date"] <= day
                        and (master["aircraft_end_of_life_date"] is None or day < master["aircraft_end_of_life_date"]))
            if existing and state and state[0] == "In Service" and state[1] in configs and aircraft_id not in assigned[day]:
                break
            index = (index + 1) % 993
        else:
            raise AssertionError(f"no assignable aircraft for rotation {r}")
        assigned[day].add(aircraft_id)
        legs = counts[r]
        start = datetime.fromisoformat(f"{day}T{'21:30:00' if r % 5 == 0 else '13:00:00'}")
        rotation = {"r": r, "date": day, "aircraft_id": aircraft_id, "legs": [],
                    "anomaly": ANOMALY_CODES[(r // 20) % 11] if r % 20 == 13 else None}
        clock = start
        for l in range(legs):
            if l:
                clock = clock + timedelta(minutes=45 + 15 * (l % 3))
            block = timedelta(minutes=90 + 30 * (l % 4))
            rotation["legs"].append({
                "flight_id": rot[cursor + l], "origin": WHITELIST[(r + l) % 9],
                "destination": WHITELIST[(r + l + 1) % 9], "depart": clock, "arrive": clock + block,
                "number": 1900 + (r + l) % 100,
            })
            clock = clock + block
        cursor += legs
        rotations.append(rotation)
    assert cursor == 1989
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rotation in rotations:
        by_date[rotation["date"]].append(rotation)
    for rotation in rotations:
        r, day, legs = rotation["r"], rotation["date"], rotation["legs"]
        anomaly = rotation["anomaly"]
        target = len(legs) - 2 if len(legs) > 1 else 0
        for l, item in enumerate(legs):
            overrides: dict[str, Any] = {}
            next_id = legs[l + 1]["flight_id"] if l + 1 < len(legs) else None
            depart, arrive = item["depart"], item["arrive"]
            origin, destination = item["origin"], item["destination"]
            if (r + l) % 12 == 5:
                # Deliberate plan/actual type discrepancy on roughly 8% of legs.
                overrides["aircraft_type"] = FLEET_DEFINITIONS[(r + l) % len(FLEET_DEFINITIONS)][2]
            if anomaly and l == target:
                if anomaly == "SELF_LOOP":
                    next_id = item["flight_id"]
                elif anomaly == "CYCLE" and l + 1 < len(legs):
                    next_id = legs[l + 1]["flight_id"]
                    legs[l + 1]["cycle_back"] = item["flight_id"]
                elif anomaly == "MISSING_TARGET":
                    next_id = 8999
                elif anomaly == "DIFFERENT_AIRCRAFT":
                    other = next((o for o in by_date[day] if o["aircraft_id"] != rotation["aircraft_id"]), None)
                    if other: next_id = other["legs"][0]["flight_id"]
                elif anomaly == "OUTSIDE_SELECTED_DAY":
                    later = next((o for o in by_date[plus_days(day, 1)] if o["r"] != r), None) if plus_days(day, 1) in by_date else None
                    if later: next_id = later["legs"][0]["flight_id"]
                elif anomaly == "BACKWARD_TIME":
                    next_id = legs[0]["flight_id"] if l else item["flight_id"]
                elif anomaly == "BROKEN_CONTINUITY":
                    destination = WHITELIST[(r + l + 5) % 9]
                    if destination == origin: destination = WHITELIST[(r + l + 6) % 9]
                elif anomaly == "DIVERSION_ENDPOINT_CONFLICT":
                    overrides.update({"is_diverted": 1, "diverted_airport_code": f"SYN-AP-{WHITELIST[(r + l + 4) % 9]}"})
                elif anomaly == "CANCELLED":
                    overrides["is_cancelled"] = 1
                elif anomaly == "MISSING_TIME":
                    depart = arrive = None
                elif anomaly == "UNKNOWN_OR_INVALID_CANCELLATION_FLAG":
                    overrides["is_cancelled"] = 2
            if item.get("cycle_back") is not None:
                next_id = item["cycle_back"]
            rows.append(leg(item["flight_id"], rotation["aircraft_id"], r, item["number"], day,
                            origin, destination, depart, arrive, next_id, **overrides))

    # --- 11.1 FUL: 700 exact-fulfilment legs, identifiers deliberately shared with PH-01 ---------
    # Every passenger and actual block sits on its own residue of the operating-date offset modulo
    # 7, so no two blocks can accidentally share a canonical passenger key or an exact fulfilment.
    fulfilment: list[dict[str, Any]] = []
    for m, flight_id in enumerate(ful):
        if m < 600:
            carrier, number, day = m, 1990 + m % 10, plus_days(FUL_EPOCH, 7 * (m % 21))
            origin, destination = ROUTES[m % 72]
        else:
            p, second = (m - 600) // 2, (m - 600) % 2
            carrier, number, day = p, 1980 + p % 10, plus_days(FUL_EPOCH, 7 * (p % 21))
            origin = WHITELIST[(p + second) % 9]
            destination = WHITELIST[(p + second + 1) % 9]
        aircraft_id = ids[(11 * m) % 993]
        depart = datetime.fromisoformat(f"{day}T12:00:00")
        row = leg(flight_id, aircraft_id, carrier, number, day, origin, destination,
                  depart, depart + timedelta(minutes=120), None)
        rows.append(row)
        fulfilment.append(row)

    # --- HEUR: candidate-only evidence ----------------------------------------------------------
    for m, flight_id in enumerate(heur):
        day = plus_days(FUL_EPOCH, 7 * (m % 21) + 2)
        aircraft_id = ids[(13 * m) % 993]
        origin, destination = ROUTES[(m + 7) % 72]
        depart = datetime.fromisoformat(f"{day}T12:00:00")
        row = leg(flight_id, aircraft_id, m, 1970 + m % 10, day, origin, destination,
                  depart, depart + timedelta(minutes=120), None)
        rows.append(row)
        heuristic.append(row)

    # --- 11.4 the ten dedicated anomaly aircraft ------------------------------------------------
    pattern = [
        ("SELF_LOOP", 0, 1, "13:00", 90, "self"), ("CYCLE_A", 0, 1, "13:00", 90, "next"),
        ("CYCLE_B", 1, 0, "15:00", 90, "back"), ("MISSING_TARGET", 3, 4, "14:00", 180, "absent"),
        ("DIFFERENT_AIRCRAFT", 1, 2, "15:00", 60, "other_aircraft"),
        ("OUTSIDE_SELECTED_DAY", 2, 0, "17:00", 90, "next_day"),
        ("BACKWARD_TIME", 0, 1, "19:00", 90, "first"), ("BROKEN_CONTINUITY", 0, 1, "13:00", 90, "prior"),
        ("DIVERSION", 0, 2, "13:00", 120, "none"), ("CANCELLED", 0, 1, "13:00", 90, "none"),
        ("MISSING_TIME", 0, 1, None, 0, "none"), ("BAD_FLAG", 0, 1, "21:00", 90, "none"),
    ]
    for n, aircraft_index in enumerate(ANOMALY_AIRCRAFT_INDEXES):
        aircraft_id, day = ids[aircraft_index], plus_days("2027-07-06", 2 * n)
        block = anom[14 * n:14 * (n + 1)]
        source, targets = block[:12], block[12:]
        rows.append(leg(targets[0], ids[(aircraft_index + 1) % 993], n, 1965, day,
                        WHITELIST[1], WHITELIST[2], datetime.fromisoformat(f"{day}T18:00:00"),
                        datetime.fromisoformat(f"{day}T19:00:00"), None))
        later = plus_days(day, 1)
        rows.append(leg(targets[1], aircraft_id, n, 1966, later, WHITELIST[0], WHITELIST[1],
                        datetime.fromisoformat(f"{later}T15:00:00"),
                        datetime.fromisoformat(f"{later}T16:30:00"), None))
        for k, (code, origin_index, destination_index, start_time, minutes, link) in enumerate(pattern):
            depart = None if start_time is None else datetime.fromisoformat(f"{day}T{start_time}:00")
            arrive = None if depart is None else depart + timedelta(minutes=minutes)
            next_id = {"self": source[k], "next": source[2], "back": source[1], "absent": 8999,
                       "other_aircraft": targets[0], "next_day": targets[1], "first": source[0],
                       "prior": source[6], "none": None}[link]
            overrides = {}
            if code == "DIVERSION":
                overrides = {"is_diverted": 1, "diverted_airport_code": f"SYN-AP-{WHITELIST[1]}"}
                destination_index = 2
            if code == "CANCELLED": overrides = {"is_cancelled": 1}
            if code == "BAD_FLAG": overrides = {"is_cancelled": 2}
            rows.append(leg(source[k], aircraft_id, n, 1930 + k, day, WHITELIST[origin_index],
                            WHITELIST[destination_index], depart, arrive, next_id, **overrides))

    # --- UNM: deliberately unmatched actual legs ------------------------------------------------
    for m, flight_id in enumerate(unm):
        day = plus_days(FUL_EPOCH, 7 * (m % 21) + 6)
        aircraft_id = ids[(17 * m) % 993]
        origin, destination = ROUTES[(m + 31) % 72]
        depart = datetime.fromisoformat(f"{day}T08:00:00")
        rows.append(leg(flight_id, aircraft_id, m, 1940 + m % 20, day, origin, destination,
                        depart, depart + timedelta(minutes=120), None))
    return rows, fulfilment, heuristic


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
    # 65 v1 carriers plus the 90 the 2027 block introduces: 32 pool, 12 MKTENT and 12 MKTEXIT
    # marketing, 10 SYN-OP-W27-ENT and 12 SYN-OP-W27-EXIT operating, 8 codeshare marketing and 4
    # codeshare-only operating identities.
    expected_count=33 if scale=="smoke" else 163
    assert len(required)==expected_count, (scale,len(required),sorted(required))
    rows=[airline_row(carrier) for carrier in sorted(required)]
    for suffix in ("A","B"):
        row=airline_row(f"SYN-MKT-DUP-{suffix}"); row["carrier_code_iata"]="SYN-DUP"; row["carrier_code_icao"]=f"SYN-ICAO-DUP-{suffix}"; rows.append(row)
    # Demo padding must be at least the smoke padding, or the demo scale stops being a strict
    # semantic superset of smoke. The exact-required union grew from 65 to 163 because
    # specification 9.2 needs eight CAP base-metal carriers, eight codeshare marketing
    # identities and four codeshare-only operating identities that the "+80" estimate in
    # section 4 did not count, so the table lands at 190 rather than 180.
    padding=25
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


def compute_q05(tables: Mapping[str, Sequence[Mapping[str, Any]]], dates: Sequence[str] | None=None) -> list[dict[str,Any]]:
    selected=selected_schedules(tables)
    watched=[field.column for field in FIELDS["SCHEDULE_SNAPSHOT"] if "SS-04" <= field.field_id <= "SS-38"]
    if dates is None: dates=("2026-08-03","2026-08-10","2026-08-17","2026-08-24","2026-08-31")
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


def compute_q06(tables: Mapping[str, Sequence[Mapping[str, Any]]], latest: str="2026-08-31",
                comparison: str="2026-08-24", role: str="marketing") -> list[dict[str,Any]]:
    selected=selected_schedules(tables)
    carrier_column="marketing_carrier_internal" if role=="marketing" else "operating_carrier_internal"
    def counts(d: str) -> dict[tuple[str,str],int]:
        result=defaultdict(int)
        for (publish,key),row in selected.items():
            if publish!=d or row[carrier_column] is None or row["departure_station_code_iata"] is None or row["arrival_station_code_iata"] is None: continue
            result[(row[carrier_column],f"{row['departure_station_code_iata']}->{row['arrival_station_code_iata']}")]+=1
        return result
    before,after=counts(comparison),counts(latest)
    result=[]
    for market in sorted(set(before)|set(after)):
        b,a=before[market],after[market]
        if b==0<a: result.append({"airline_id":market[0],"route_id":market[1],"change_kind":"ENTRY","before_schedule_count":b,"after_schedule_count":a})
        if a==0<b: result.append({"airline_id":market[0],"route_id":market[1],"change_kind":"EXIT","before_schedule_count":b,"after_schedule_count":a})
    return result


WEEKDAY_COLUMNS=("is_operating_monday","is_operating_tuesday","is_operating_wednesday","is_operating_thursday","is_operating_friday","is_operating_saturday","is_operating_sunday")


def compute_q07(tables: Mapping[str, Sequence[Mapping[str, Any]]], knowledge: str="2026-08-31",
                operating: str="2026-09-07", weekday_filter: bool=False) -> list[dict[str,Any]]:
    selected=selected_schedules(tables)
    weekday=WEEKDAY_COLUMNS[date.fromisoformat(operating).weekday()]
    active=[row for (publish,_),row in selected.items() if publish==knowledge and row["effective_date"] <= operating <= row["discontinue_date"] and row["departure_station_code_iata"] and row["arrival_station_code_iata"] and (not weekday_filter or row[weekday])]
    physical=[row for row in active if not row["is_codeshare"]]
    def weighted(rows: Sequence[Mapping[str,Any]], value: Any) -> Any:
        # Null-safe: a null cabin figure makes the whole weekly metric unknown rather than zero,
        # which is what the CAP-021 null-cabin defect is there to exercise.
        total=0
        for row in rows:
            item=value(row)
            if item is None: return None
            total+=row["weekly_frequency"]*item
        return total
    def metrics(rows: Sequence[Mapping[str,Any]]) -> dict[str,Any]:
        return {"active_schedule_count":len(rows),"weekly_frequency":sum(row["weekly_frequency"] for row in rows),
            "weekly_total_seats":weighted(rows,lambda row:row["total_seats"]),
            "weekly_first_seats":weighted(rows,lambda row:row["first_class_seats"]),
            "weekly_business_seats":weighted(rows,lambda row:row["business_class_seats"]),
            "weekly_premium_economy_seats":weighted(rows,lambda row:row["premium_economy_seats"]),
            "weekly_economy_excluding_premium_seats":weighted(rows,lambda row:None if row["economy_class_seats"] is None or row["premium_economy_seats"] is None else row["economy_class_seats"]-row["premium_economy_seats"])}
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


def frozen_result_sets(expected: Mapping[str,Any]) -> list[Mapping[str,Any]]:
    """The 1.1.1 result sets.  D-0023 additions carry manifest_version and are excluded here."""
    return [result_set for question in expected["questions"] for result_set in question["result_sets"]
            if "manifest_version" not in result_set]


def added_result_sets(expected: Mapping[str,Any]) -> list[Mapping[str,Any]]:
    return [result_set for question in expected["questions"] for result_set in question["result_sets"]
            if result_set.get("manifest_version")=="1.2.0"]


def expected_rows(expected: Mapping[str,Any]) -> list[dict[str,Any]]:
    result=[]
    for result_set in frozen_result_sets(expected): result.extend(result_set["rows"])
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
    assert all(row["aircraft_registration_number"] in {f"SYN-REG-{row['aircraft_id']}", f"SYN-REG-{row['aircraft_id']}-R2"} and row["aircraft_transponder_code"]==f"SYN-XPDR-{row['aircraft_id']}" for row in ah)
    assert all(row["aircraft_code_iata"] is None or row["aircraft_code_iata"] in {"SA1","SB1","SM1"} or row["aircraft_code_iata"].startswith("SYN-") for row in ah)
    assert all(row["aircraft_code_icao"] is None or row["aircraft_code_icao"].startswith("SYN") for row in ah)
    assert all(row["aircraft_value_sub_series"] is None or row["aircraft_value_sub_series"].startswith("SYN-") for row in ah)
    assert all(row["storage_location"] is None or row["storage_location"] in ap_ids for row in ah)
    assert all(row["aircraft_configuration_id"] in {2001,2002,2003,2005} or 300000<=row["aircraft_configuration_id"]<=301995 for row in ac)
    assert all(row["base_state"].startswith("SYN-ST-") and row["base_region"].startswith("SYN-RGN-") for row in ah)
    assert all(row["storage_location_type"] is None or row["storage_location_type"].startswith("SYN-STG-") for row in ah)
    assert all(row["noise_certification"].startswith("SYN-NOISE-") for row in ah)
    assert all(row["aircraft_registration_country"].startswith("Synthetic United States") for row in ah)
    assert all(50_000<=row["maximum_landing_weight_lb"]<=400_000 and 30_000<=row["operating_empty_weight_lb"]<=300_000 for row in ah)
    for row in ac:
        for column in ("aircraft_family","aircraft_series","aircraft_subseries","aircraft_manufacturer","aircraft_design_class","engine_manufacturer","engine_family","engine_series","engine_subseries"):
            assert row[column].startswith("SYN-")
        assert row["aircraft_type"].startswith("Synthetic ") and row["engine_type"].startswith("Synthetic ")
    assert all(row["schedule_key"].startswith("SYN-SK-") and row["schedule_key_readable"].startswith("SYN-READABLE|") for row in ss)
    assert all(row[column] is None or row[column].startswith("SYN-") for row in ss for column in ("marketing_carrier_internal","operating_carrier_internal","codeshare_carrier_internal"))
    assert all(700<=row["flight_number"]<=799 or 1700<=row["flight_number"]<=1999 for row in ss)
    assert all(9000<=row["itinerary_variation_identifier"]<=9999 and re.fullmatch(r"[0-9a-f]{64}",row["normalized_row_hash"]) for row in ss)
    assert all(row["equipment_subtype_code_iata"].startswith("SYN-") for row in ss)
    for rows,id_column,filler_range in ((pf,"forward_source_row_id",range(1900,2000)),(ph,"historical_source_row_id",range(1900,2000))):
        assert all(row[id_column] is None or 5000<=row[id_column]<=7999 for row in rows)
        assert all(row["marketing_carrier_internal"].startswith("SYN-") and row["operating_carrier_internal"].startswith("SYN-") for row in rows)
        assert all(700<=row["flight_number"]<=799 or row["flight_number"] in filler_range for row in rows)
        assert all(row["equipment_subtype_code_iata"].startswith("SYN-") for row in rows)
    assert all(5000<=row["flight_id"]<=8998 and 1000<=row["aircraft_id"]<=1999 for row in af)
    assert all(row["operating_carrier_code"].startswith("SYN-") and row["marketing_carrier_code"].startswith("SYN-") for row in af)
    assert all((700<=int(row["flight_number"])<=799) or (1900<=int(row["flight_number"])<=1999) for row in af)
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
    assert sum(counts.values())==(249 if scale=="smoke" else 182_039)
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
    # Specification 2.1 requires a second known-answer vector for the 2027 ordinal block.
    vector_2027=f"{SEED}|{SOURCE_TOKEN['SCHEDULE_SNAPSHOT']}|400000|SS-39".encode("ascii")
    assert len(vector_2027)==46 and sha256_bytes(vector_2027)=="462b1a2f2ab0a15afb0464736986f1bbde121ce5b4310b8933c193943f48fd16"
    assert 9000+int.from_bytes(hashlib.sha256(vector_2027).digest()[:2],"big")%1000==9963
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
        # D-0023 replaced the 2035/2036/2040 filler blocks with 2027 populations, so the v1
        # "filler cannot interact" assertion becomes a controlled-interaction assertion: the
        # canonical passenger key overlap is exactly the 500 rows section 10.2 asks for.
        def canonical_key(row: Mapping[str,Any], carrier: str) -> tuple[Any,...]:
            return (row[carrier],row["flight_number"],row["departure_station_code_iata"],row["arrival_station_code_iata"],row["operating_date"])
        pf_keys={canonical_key(row,"marketing_carrier_internal") for row in tables["PASSENGER_FORWARD"]}
        ph_keys={canonical_key(row,"marketing_carrier_internal") for row in tables["PASSENGER_HISTORICAL"]}
        # 500 enriched overlaps plus the one anchored TT-PASSENGER-UNION fixture (PH-5001/PF-6001).
        assert len(pf_keys & ph_keys)==501, len(pf_keys & ph_keys)
        assert ("SYN-MKT-A",700,"SFO","LAX","2026-08-31") in (pf_keys & ph_keys)
        # 8,000 enriched plus the one anchored SYN-SK-HIST_700 row.
        assert sum(row["schedule_key"] is not None for row in tables["PASSENGER_HISTORICAL"])==8_001
        assert all(row["flight_departure_date"][:4]=="2027" for row in tables["AIRCRAFT_FLIGHT"] if row["flight_id"] not in ANCHOR_FLIGHT_IDS)
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
    history=aircraft_history(scale,masters)
    # Actual flights are constructed first: the FUL block deliberately shares its identifiers with
    # PH-01, and the HEUR block is what the forward candidate plans mirror.
    flights=aircraft_flights(scale,masters,history)
    tables: dict[str,list[dict[str,Any]]]={
        "AIRCRAFT_MASTER":masters,
        "AIRCRAFT_HISTORY":history,
        "AIRCRAFT_CONFIGURATION":aircraft_configuration(scale),
        "SCHEDULE_SNAPSHOT":schedule_rows(scale,expected),
        "SCHEDULE_SNAPSHOT_CALENDAR":snapshot_calendar(scale),
        "PASSENGER_FORWARD":passenger_forward(scale),
        "PASSENGER_HISTORICAL":passenger_historical(scale),
        "AIRCRAFT_FLIGHT":flights,
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
    # D-0017: DECISION_LOG.md is governance prose, not a determinant of the generated data, so it
    # is not bound here.  These five inputs do determine the data.
    names=("EXPECTED_ANSWERS.yaml","SOURCE_CONTRACT.md","ATTRIBUTE_AUTHORITY.md","data/SYNTHETIC_DATA_SPEC.md","data/SYNTHETIC_DATA_SPEC_V2.md","build/task_reports/DATA-01.json")
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
        "manifest_version":"1.2.0","scale":scale,"claim_scope":"synthetic U.S.-domestic representative functional shape; non-production",
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
            "schedule_prf_2027_sha256":"462b1a2f2ab0a15afb0464736986f1bbde121ce5b4310b8933c193943f48fd16","schedule_prf_2027_ss39":9963,
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
