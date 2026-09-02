#!/usr/bin/env python3
"""Load the synthetic aviation source package into the scoped Snowflake SOURCE schema.

Scope is pinned to connection `rai`, role RAI_DEMO_AVIATION_TEMPORAL, warehouse RAI_XS and
database PK_AVIATION_TEMPORAL; no caller override is accepted.  The ten SOURCE tables are empty
and unpublished, so this loader simply replaces them: local preflight, DDL, PUT, COPY, then a
post-load content verification against the DATA-02 manifest.

D-0016: Snowflake makes a PRIMARY KEY column physically NOT NULL even when the constraint is
declared NOT ENFORCED NORELY.  Eight SOURCE identity columns across six tables are contract
nullable, so those tables declare a named UNIQUE ... NOT ENFORCED NORELY instead of a PRIMARY
KEY.  Only SCHEDULE_SNAPSHOT_CALENDAR.expected_publish_date is contract non-null and keeps a
PRIMARY KEY.  RELY is never set.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time as time_value
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CONNECTION = "rai"
ROLE = "RAI_DEMO_AVIATION_TEMPORAL"
WAREHOUSE = "RAI_XS"
DATABASE = "PK_AVIATION_TEMPORAL"
LOADER_VERSION = "load-source-v1"
VERIFY_VERSION = "load-verify-v1"

FILE_FORMAT = f"{DATABASE}.SOURCE.D0013_CSV_FORMAT"
STAGE = f"{DATABASE}.VALIDATION.DATA03_CSV_STAGE"
MANIFEST_TABLE = f"{DATABASE}.VALIDATION.SOURCE_LOAD_MANIFEST"
ORPHAN_STAGING_PREFIX = "DATA03_COLD_20260901_01_"

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
# FK children are replaced first so that no surviving foreign key still references a parent table
# at the moment that parent is itself replaced.  The two foreign keys are re-added afterwards.
DDL_ORDER = (
    "AIRCRAFT_HISTORY",
    "SCHEDULE_SNAPSHOT",
    "AIRCRAFT_MASTER",
    "AIRCRAFT_CONFIGURATION",
    "SCHEDULE_SNAPSHOT_CALENDAR",
    "AIRPORT_REFERENCE",
    "AIRLINE_REFERENCE",
    "PASSENGER_FORWARD",
    "PASSENGER_HISTORICAL",
    "AIRCRAFT_FLIGHT",
)

TABLE_COMMENTS = {
    "AIRCRAFT_MASTER": "Synthetic non-production aircraft master observations; nullable raw identity is retained for audit.",
    "AIRCRAFT_HISTORY": "Synthetic non-production append-only aircraft events; unresolved configuration references are deliberate evidence.",
    "AIRCRAFT_CONFIGURATION": "Synthetic non-production aircraft and reported-engine configuration reference rows.",
    "SCHEDULE_SNAPSHOT": "Physical synthetic non-production schedule snapshot observations; semantic duplicate rows deliberately preclude a false raw PK.",
    "SCHEDULE_SNAPSHOT_CALENDAR": "Synthetic declared snapshot presence and completeness calendar; never inferred from row presence.",
    "PASSENGER_FORWARD": "Synthetic non-production forward planned-flight observations; nullable stable IDs are retained by contracted hash fallback.",
    "PASSENGER_HISTORICAL": "Synthetic non-production historical planned-flight observations with independent plan lineage.",
    "AIRCRAFT_FLIGHT": "Synthetic non-production actual flown-leg observations; missing next-flight targets are deliberate anomaly evidence.",
    "AIRPORT_REFERENCE": "Synthetic non-production effective-period airport reference observations; nine public U.S. IATA locations plus synthetic controls.",
    "AIRLINE_REFERENCE": "Synthetic non-production effective-period airline reference observations and exact ambiguity controls.",
}

# Inline constraints.  Only contracted identities that hold for the complete fixture are stated;
# deliberately unresolved configuration/rotation links and schedule semantic duplicates are not.
CONSTRAINTS = {
    "AIRCRAFT_MASTER": ("CONSTRAINT UQ_AIRCRAFT_MASTER_ID UNIQUE (aircraft_id) NOT ENFORCED NORELY",),
    "AIRCRAFT_HISTORY": ("CONSTRAINT UQ_AIRCRAFT_HISTORY_ID UNIQUE (aircraft_history_id) NOT ENFORCED NORELY",),
    "AIRCRAFT_CONFIGURATION": ("CONSTRAINT UQ_AIRCRAFT_CONFIGURATION_ID UNIQUE (aircraft_configuration_id) NOT ENFORCED NORELY",),
    "SCHEDULE_SNAPSHOT": (),
    "SCHEDULE_SNAPSHOT_CALENDAR": ("CONSTRAINT PK_SCHEDULE_SNAPSHOT_CALENDAR PRIMARY KEY (expected_publish_date) NOT ENFORCED NORELY",),
    "PASSENGER_FORWARD": ("CONSTRAINT UQ_PASSENGER_FORWARD_SOURCE_ID UNIQUE (forward_source_row_id) NOT ENFORCED NORELY",),
    "PASSENGER_HISTORICAL": ("CONSTRAINT UQ_PASSENGER_HISTORICAL_SOURCE_ID UNIQUE (historical_source_row_id) NOT ENFORCED NORELY",),
    "AIRCRAFT_FLIGHT": ("CONSTRAINT UQ_AIRCRAFT_FLIGHT_ID UNIQUE (flight_id) NOT ENFORCED NORELY",),
    "AIRPORT_REFERENCE": ("CONSTRAINT UQ_AIRPORT_REFERENCE_ID UNIQUE (airport_id, effective_start_date) NOT ENFORCED NORELY",),
    "AIRLINE_REFERENCE": ("CONSTRAINT UQ_AIRLINE_REFERENCE_ID UNIQUE (airline_id, effective_start_date) NOT ENFORCED NORELY",),
}
# Truthful references only, added after every table exists so replace order cannot break them.
FOREIGN_KEYS = (
    (
        "AIRCRAFT_HISTORY",
        "CONSTRAINT FK_AIRCRAFT_HISTORY_MASTER FOREIGN KEY (aircraft_id) "
        f"REFERENCES {DATABASE}.SOURCE.AIRCRAFT_MASTER (aircraft_id) NOT ENFORCED NORELY",
    ),
    (
        "SCHEDULE_SNAPSHOT",
        "CONSTRAINT FK_SCHEDULE_SNAPSHOT_CALENDAR FOREIGN KEY (publish_date) "
        f"REFERENCES {DATABASE}.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR (expected_publish_date) NOT ENFORCED NORELY",
    ),
)

EXPECTED_FILE_FORMAT = {
    "type": "CSV",
    "compression": "NONE",
    "record_delimiter": "\n",
    "field_delimiter": ",",
    "skip_header": 1,
    "parse_header": False,
    "field_optionally_enclosed_by": '"',
    "escape": "NONE",
    "escape_unenclosed_field": "NONE",
    "multi_line": True,
    "empty_field_as_null": True,
    "null_if": [""],
    "trim_space": False,
    "skip_blank_lines": False,
    "replace_invalid_characters": False,
    "error_on_column_count_mismatch": True,
    "encoding": "UTF8",
}


class GateError(RuntimeError):
    """A fail-closed package or live verification failure."""


@dataclass(frozen=True)
class Field:
    field_id: str
    column: str
    type_tag: str
    nullable: bool
    role: str


@dataclass
class Package:
    path: Path
    manifest: dict[str, Any]
    manifest_sha256: str
    fields: dict[str, tuple[Field, ...]]
    rows: dict[str, list[dict[str, str | None]]]
    evidence: dict[str, Any]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def parse_contract_fields(contract_path: Path | None = None) -> dict[str, tuple[Field, ...]]:
    """Parse the 195 contracted SOURCE fields out of SOURCE_CONTRACT.md."""
    text = (contract_path or ROOT / "SOURCE_CONTRACT.md").read_text(encoding="utf-8")
    matches = re.findall(
        r"^\| ((?:AM|AH|AC|SS|SC|PF|PH|AF|AP|AL)-\d{2}) \| `([^`]+)` \| "
        r"([A-Z][A-Z0-9_]*(?:\([^)]*\))?) \| (yes|no) \| ([^|]+) \|$",
        text,
        flags=re.MULTILINE,
    )
    by_prefix: dict[str, dict[str, Field]] = defaultdict(dict)
    for field_id, column, type_tag, nullable, role in matches:
        field = Field(field_id, column, type_tag, nullable == "yes", role.strip())
        previous = by_prefix[field_id[:2]].get(field_id)
        if previous is not None and previous != field:
            raise GateError(f"conflicting SOURCE_CONTRACT row for {field_id}")
        by_prefix[field_id[:2]][field_id] = field
    result = {
        table: tuple(sorted(by_prefix[PREFIX[table]].values(), key=lambda field: field.field_id))
        for table in TABLE_ORDER
    }
    if sum(map(len, result.values())) != 195:
        raise GateError("SOURCE_CONTRACT did not produce exactly 195 fields")
    return result


def validate_lf_record_separators(content: bytes) -> None:
    quoted = False
    index = 0
    while index < len(content):
        byte = content[index]
        if byte == 0x22:
            if quoted and index + 1 < len(content) and content[index + 1] == 0x22:
                index += 2
                continue
            quoted = not quoted
        elif byte == 0x0D and not quoted:
            raise GateError("CSV record separators must be LF, never CR or CRLF")
        index += 1
    if quoted or not content.endswith(b"\n"):
        raise GateError("CSV has an unterminated quote or missing final LF")


def read_csv(path: Path, fields: Sequence[Field]) -> list[dict[str, str | None]]:
    content = path.read_bytes()
    validate_lf_record_separators(content)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateError(f"{path.name} is not UTF-8") from exc
    parsed = list(csv.reader(text.splitlines(keepends=True), delimiter=",", quotechar='"', doublequote=True))
    header = [field.column for field in fields]
    if not parsed or parsed[0] != header:
        raise GateError(f"{path.name} header/order differs from SOURCE_CONTRACT")
    if any(len(row) != len(fields) for row in parsed[1:]):
        raise GateError(f"{path.name} has a column-count mismatch")
    # The generator rejects non-null empty strings, so an empty field is exclusively null here.
    return [dict(zip(header, (None if value == "" else value for value in row))) for row in parsed[1:]]


# --- typed-row hashing (manifest side) -------------------------------------------------------


def lp(value: str | bytes) -> bytes:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return str(len(raw)).encode("ascii") + b":" + raw


def canonical_scalar(value: Any, type_tag: str) -> str:
    if value is None:
        raise TypeError("null has no scalar representation")
    base = type_tag.split("(", 1)[0]
    if base == "BOOLEAN":
        if isinstance(value, bool):
            return "true" if value else "false"
        if value in ("true", "false"):
            return str(value)
        raise TypeError(value)
    if base == "NUMBER":
        if isinstance(value, bool):
            raise TypeError(value)
        return str(int(value))
    if base == "FLOAT":
        number = float(value)
        if not math.isfinite(number):
            raise TypeError(value)
        return repr(number)
    if base == "DATE":
        result = value.isoformat() if isinstance(value, date) and not isinstance(value, datetime) else str(value)
        date.fromisoformat(result)
        return result
    if base == "TIME":
        result = value.isoformat() if isinstance(value, time_value) else str(value)
        time_value.fromisoformat(result)
        if "." in result and set(result.split(".", 1)[1]) == {"0"}:
            result = result.split(".", 1)[0]
        return result
    if base == "TIMESTAMP_NTZ":
        result = value.isoformat() if isinstance(value, datetime) else str(value)
        datetime.fromisoformat(result.replace(" ", "T"))
        result = result.replace(" ", "T")
        if "." in result and set(result.split(".", 1)[1]) == {"0"}:
            result = result.split(".", 1)[0]
        return result
    if base == "VARCHAR":
        result = str(value)
        if not result:
            raise TypeError("non-null empty VARCHAR")
        return result
    raise TypeError(type_tag)


def typed_payload(fields: Sequence[Field], row: Mapping[str, Any], scalar=canonical_scalar) -> bytes:
    result = bytearray()
    for field in fields:
        result.extend(lp(field.field_id))
        result.extend(lp(field.type_tag))
        value = row[field.column]
        if value is None:
            result.extend(lp("N"))
        else:
            result.extend(lp("V"))
            result.extend(lp(scalar(value, field.type_tag)))
    return bytes(result)


def ordered_typed_rows_hash(table: str, fields: Sequence[Field], rows: Sequence[Mapping[str, Any]]) -> str:
    payload = bytearray(lp("typed-row-lp-v1"))
    payload.extend(lp(f"SOURCE.{table}"))
    for row in rows:
        payload.extend(lp(typed_payload(fields, row)))
    return sha256_bytes(bytes(payload))


# --- multiset content hashing (Snowflake side, reproduced in Python) --------------------------
#
# ordered_typed_rows_sha256 cannot be recomputed inside Snowflake: it is order sensitive and a
# SQL table has no row order, and the ordered payload for SCHEDULE_SNAPSHOT/AIRCRAFT_HISTORY
# exceeds Snowflake's 16 MB VARCHAR/LISTAGG ceiling anyway.  The post-load check therefore hashes
# the multiset of typed rows: each row is length-prefix encoded exactly as typed_payload does and
# SHA-256'd, then the sorted row digests are concatenated and SHA-256'd again.  Both sides of that
# construction are computed here and in SQL from the same encoding, so equality proves Snowflake
# holds exactly the CSV's typed values (row order excepted).  FLOAT uses a fixed nine-decimal
# rendering because Snowflake's TO_VARCHAR(FLOAT) is lossy; every value is checked to round-trip.


def verify_scalar(value: Any, type_tag: str) -> str:
    base = type_tag.split("(", 1)[0]
    if base == "FLOAT":
        number = float(value)
        if not math.isfinite(number) or abs(number) >= 10 ** 29:
            raise GateError(f"FLOAT {value!r} is outside the verifiable NUMBER(38,9) range")
        text = format(Decimal(number).quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP), "f")
        if float(text) != number:
            raise GateError(f"FLOAT {value!r} does not round-trip at nine decimals")
        return text
    result = canonical_scalar(value, type_tag)
    if base == "TIME" and not re.fullmatch(r"\d{2}:\d{2}:\d{2}", result):
        raise GateError(f"TIME {result} carries sub-second precision that SQL verification cannot mirror")
    if base == "TIMESTAMP_NTZ" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", result):
        raise GateError(f"TIMESTAMP_NTZ {result} carries sub-second precision that SQL verification cannot mirror")
    return result


def multiset_rows_hash(fields: Sequence[Field], rows: Sequence[Mapping[str, Any]]) -> str:
    digests = sorted(sha256_bytes(typed_payload(fields, row, verify_scalar)) for row in rows)
    return sha256_bytes("".join(digests).encode("ascii"))


def verify_value_sql(field: Field) -> str:
    base = field.type_tag.split("(", 1)[0]
    column = field.column
    rendering = {
        "NUMBER": f"TO_VARCHAR({column})",
        "FLOAT": f"TO_VARCHAR(CAST({column} AS NUMBER(38,9)))",
        "BOOLEAN": f"TO_VARCHAR({column})",
        "DATE": f"TO_VARCHAR({column},'YYYY-MM-DD')",
        "TIME": f"TO_VARCHAR({column},'HH24:MI:SS')",
        "TIMESTAMP_NTZ": f"TO_VARCHAR({column},'YYYY-MM-DD\"T\"HH24:MI:SS')",
        "VARCHAR": column,
    }.get(base)
    if rendering is None:
        raise GateError(f"no SQL verification rendering for type {field.type_tag}")
    constant = sql_string((lp(field.field_id) + lp(field.type_tag)).decode("ascii"))
    return (
        f"{constant} || IFF({column} IS NULL, '1:N', "
        f"'1:V' || TO_VARCHAR(OCTET_LENGTH({rendering})) || ':' || {rendering})"
    )


def content_hash_sql(table: str, fields: Sequence[Field], source: str | None = None) -> str:
    payload = " ||\n    ".join(verify_value_sql(field) for field in fields)
    return (
        f"SELECT {sql_string(table)} AS table_name, COUNT(*) AS row_count,\n"
        "  SHA2(COALESCE(LISTAGG(row_sha,'') WITHIN GROUP (ORDER BY row_sha),''),256) AS rows_digest\n"
        f"FROM (SELECT SHA2(\n    {payload}\n  ,256) AS row_sha FROM {source or f'{DATABASE}.SOURCE.{table}'})"
    )


# --- DDL ---------------------------------------------------------------------------------------


def column_sql(field: Field) -> str:
    nullable_sql = "" if field.nullable else " NOT NULL"
    return f"{field.column} {field.type_tag}{nullable_sql} COMMENT {sql_string(f'{field.field_id} | {field.role}')}"


def create_table_sql(table: str, fields: Mapping[str, Sequence[Field]]) -> str:
    parts = [column_sql(field) for field in fields[table]]
    parts.extend(CONSTRAINTS[table])
    return (
        f"CREATE OR REPLACE TABLE {DATABASE}.SOURCE.{table} (\n  "
        + ",\n  ".join(parts)
        + f"\n) CHANGE_TRACKING=TRUE COMMENT={sql_string(TABLE_COMMENTS[table])}"
    )


def file_format_sql() -> str:
    return f"""CREATE OR REPLACE FILE FORMAT {FILE_FORMAT}
TYPE=CSV
COMPRESSION=NONE
RECORD_DELIMITER='\\n'
FIELD_DELIMITER=','
SKIP_HEADER=1
PARSE_HEADER=FALSE
FIELD_OPTIONALLY_ENCLOSED_BY='"'
ESCAPE=NONE
ESCAPE_UNENCLOSED_FIELD=NONE
MULTI_LINE=TRUE
EMPTY_FIELD_AS_NULL=TRUE
NULL_IF=('')
TRIM_SPACE=FALSE
SKIP_BLANK_LINES=FALSE
REPLACE_INVALID_CHARACTERS=FALSE
ERROR_ON_COLUMN_COUNT_MISMATCH=TRUE
ENCODING='UTF8'
DATE_FORMAT='YYYY-MM-DD'
TIME_FORMAT='HH24:MI:SS'
TIMESTAMP_FORMAT='YYYY-MM-DD"T"HH24:MI:SS'
COMMENT='Exact synthetic CSV boundary: UTF-8/LF, no compression, no trimming, conversion errors fail.'"""


def manifest_table_sql() -> str:
    return f"""CREATE OR REPLACE TABLE {MANIFEST_TABLE} (
  manifest_sha256 VARCHAR NOT NULL COMMENT 'SHA-256 of the canonical DATA-02 manifest bytes.',
  scale VARCHAR NOT NULL COMMENT 'Generated package scale, demo or smoke.',
  total_rows NUMBER(38,0) NOT NULL COMMENT 'Total rows loaded across the ten SOURCE tables.',
  table_counts VARIANT NOT NULL COMMENT 'Per-table loaded row counts.',
  loader_version VARCHAR NOT NULL COMMENT 'Loader build that wrote this receipt.',
  loaded_at_utc TIMESTAMP_NTZ NOT NULL COMMENT 'UTC completion time of the load.'
) CHANGE_TRACKING=FALSE COMMENT='Receipt for the synthetic SOURCE package currently loaded.'"""


def ddl_statements(fields: Mapping[str, Sequence[Field]]) -> list[tuple[str, str]]:
    statements: list[tuple[str, str]] = [
        ("file_format", file_format_sql()),
        ("internal_stage", f"CREATE STAGE IF NOT EXISTS {STAGE} COMMENT='Scoped internal stage for reviewed synthetic SOURCE CSV packages only.'"),
        ("load_manifest", manifest_table_sql()),
    ]
    statements.extend((f"source_{table}", create_table_sql(table, fields)) for table in DDL_ORDER)
    statements.extend(
        (f"fk_{table}", f"ALTER TABLE {DATABASE}.SOURCE.{table} ADD {constraint}")
        for table, constraint in FOREIGN_KEYS
    )
    return statements


# --- Snowflake execution -------------------------------------------------------------------------


def tagged_sql(statements: Iterable[tuple[str, str]], query_tag: str) -> str:
    parts = [f"ALTER SESSION SET QUERY_TAG={sql_string(query_tag)};"]
    for label, statement in statements:
        parts.append(statement.rstrip(";") + ";")
        parts.append(f"SELECT {sql_string(label)} AS evidence_label, LAST_QUERY_ID() AS query_id;")
    return "\n".join(parts)


def snow_command(filename: Path) -> list[str]:
    return [
        "snow", "sql", "-c", CONNECTION, "--role", ROLE, "--warehouse", WAREHOUSE,
        "--database", DATABASE, "--format", "JSON", "--filename", str(filename),
    ]


def run_snow(sql: str, *, label: str) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".sql", prefix="load-source-") as handle:
        handle.write(sql)
        handle.flush()
        command = snow_command(Path(handle.name))
        started = time.monotonic()
        process = subprocess.run(command, cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        wall_seconds = round(time.monotonic() - started, 3)
    if process.returncode != 0:
        raise GateError(f"{label} failed ({process.returncode}): {process.stderr[-3000:]}\n{process.stdout[-3000:]}")
    try:
        parsed = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise GateError(f"{label} did not return JSON: {process.stdout[-3000:]}") from exc
    return {"label": label, "wall_seconds": wall_seconds, "results": parsed}


def query(sql: str, *, label: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    event = run_snow(tagged_sql(((label, sql),), f"AVIATION_TEMPORAL|DATA-03|{label}"), label=label)
    results = event["results"]
    if len(results) < 3 or not isinstance(results[-2], list):
        raise GateError(f"{label} returned an unexpected Snow CLI result shape")
    return results[-2], event


# --- local preflight -------------------------------------------------------------------------------


def package_dir(scale: str) -> Path:
    return ROOT / "build" / "generated_data" / scale


def preflight_package(manifest_path: Path, *, expect_manifest_sha256: str | None = None) -> Package:
    started = time.monotonic()
    raw_manifest = manifest_path.read_bytes()
    manifest_sha = sha256_bytes(raw_manifest)
    if expect_manifest_sha256 is not None and manifest_sha != expect_manifest_sha256:
        raise GateError(f"manifest SHA-256 mismatch: {manifest_sha} != {expect_manifest_sha256}")
    manifest = json.loads(raw_manifest)
    if raw_manifest != canonical_json_bytes(manifest):
        raise GateError("manifest is not canonical JSON with a final LF")
    # Pin the major version only: DATA-02 revises the minor version as it adds evidence blocks,
    # and every field this loader consumes is stable across the 1.x manifest series.
    if not re.fullmatch(r"1\.\d+\.\d+", str(manifest.get("manifest_version"))):
        raise GateError(f"unsupported manifest version {manifest.get('manifest_version')!r}")
    if manifest.get("typed_row_hash_version") != "typed-row-lp-v1":
        raise GateError("unsupported typed-row hash version")
    if manifest.get("serializer", {}).get("version") != "sf-csv-v1":
        raise GateError("unsupported serializer version")
    if manifest.get("snowflake_file_format") != EXPECTED_FILE_FORMAT:
        raise GateError("manifest Snowflake file-format boundary differs from the loader's file format")
    scale = manifest.get("scale")
    if scale not in ("demo", "smoke"):
        raise GateError(f"unsupported package scale {scale!r}")

    fields = parse_contract_fields()
    table_manifest = manifest.get("tables", {})
    if set(table_manifest) != set(TABLE_ORDER):
        raise GateError("manifest table inventory is not the exact ten-table SOURCE contract")
    expected_counts = manifest.get("validation", {}).get("counts", {})
    if set(expected_counts) != set(TABLE_ORDER):
        raise GateError("manifest validation counts do not cover the ten SOURCE tables")

    rows: dict[str, list[dict[str, str | None]]] = {}
    table_evidence: dict[str, Any] = {}
    for table in TABLE_ORDER:
        entry = table_manifest[table]
        expected_fields = fields[table]
        if entry.get("columns") != [field.column for field in expected_fields]:
            raise GateError(f"{table} columns/order mismatch")
        if entry.get("field_ids") != [field.field_id for field in expected_fields]:
            raise GateError(f"{table} field-ID order mismatch")
        if entry.get("snowflake_types") != [field.type_tag for field in expected_fields]:
            raise GateError(f"{table} type order mismatch")
        if entry.get("rows") != expected_counts[table]:
            raise GateError(f"{table} manifest row count disagrees with the validation block")
        if entry.get("file") != f"{table.lower()}.csv":
            raise GateError(f"{table} filename must be exactly {table.lower()}.csv")
        data_path = manifest_path.parent / entry["file"]
        file_hash = sha256_file(data_path)
        if file_hash != entry.get("file_sha256"):
            raise GateError(f"{table} file SHA-256 mismatch")
        table_rows = read_csv(data_path, expected_fields)
        if len(table_rows) != expected_counts[table]:
            raise GateError(f"{table} parsed row count mismatch")
        recomputed = ordered_typed_rows_hash(table, expected_fields, table_rows)
        if recomputed != entry.get("ordered_typed_rows_sha256"):
            raise GateError(f"{table} independently recomputed ordered typed-row SHA-256 mismatch")
        rows[table] = table_rows
        table_evidence[table] = {
            "file": entry["file"],
            "rows": len(table_rows),
            "file_sha256": file_hash,
            "ordered_typed_rows_sha256": recomputed,
            "multiset_rows_sha256": multiset_rows_hash(expected_fields, table_rows),
        }
    total_rows = sum(map(len, rows.values()))
    if total_rows != manifest.get("validation", {}).get("total_rows"):
        raise GateError(f"package total {total_rows} disagrees with the manifest validation total")

    evidence = {
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "scale": scale,
        "contract_fields": 195,
        "source_contract_sha256": sha256_file(ROOT / "SOURCE_CONTRACT.md"),
        "total_rows": total_rows,
        "tables": table_evidence,
        "wall_seconds": round(time.monotonic() - started, 3),
    }
    return Package(manifest_path, manifest, manifest_sha, fields, rows, evidence)


# --- apply ---------------------------------------------------------------------------------------


def stage_location(package: Package, table: str) -> str:
    return f"{package.manifest_sha256}/{table.lower()}"


def apply_load(package: Package) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    counts = {table: len(package.rows[table]) for table in TABLE_ORDER}

    events.append(run_snow(tagged_sql(ddl_statements(package.fields), "AVIATION_TEMPORAL|DATA-03|ddl"), label="ddl"))

    for table in TABLE_ORDER:
        path = (package.path.parent / package.manifest["tables"][table]["file"]).resolve()
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", str(path)):
            raise GateError(f"local package path is not injection safe: {path}")
        statement = (
            f"PUT file://{path} @{STAGE}/{stage_location(package, table)}/ "
            "AUTO_COMPRESS=FALSE OVERWRITE=TRUE PARALLEL=4"
        )
        events.append(run_snow(tagged_sql(((f"put_{table}", statement),), f"AVIATION_TEMPORAL|DATA-03|put|{table}"), label=f"put_{table}"))

    copy_statements = [
        (
            f"copy_{table}",
            f"COPY INTO {DATABASE}.SOURCE.{table} FROM @{STAGE}/{stage_location(package, table)}/ "
            f"FILES=({sql_string(package.manifest['tables'][table]['file'])}) "
            f"FILE_FORMAT=(FORMAT_NAME={FILE_FORMAT}) ON_ERROR=ABORT_STATEMENT PURGE=FALSE FORCE=TRUE",
        )
        for table in TABLE_ORDER
    ]
    copy_event = run_snow(tagged_sql(copy_statements, "AVIATION_TEMPORAL|DATA-03|copy"), label="copy")
    events.append(copy_event)
    loaded: dict[str, int] = {}
    for result in copy_event["results"]:
        if not isinstance(result, list) or not result or not isinstance(result[0], dict):
            continue
        row = {key.casefold(): value for key, value in result[0].items()}
        if "rows_loaded" not in row or "file" not in row:
            continue
        filename = Path(str(row["file"])).name
        table = next((name for name in TABLE_ORDER if package.manifest["tables"][name]["file"] == filename), None)
        if table is None:
            continue
        if int(row.get("errors_seen", 0)) != 0:
            raise GateError(f"{table} COPY reported errors: {row}")
        loaded[table] = int(row["rows_loaded"])
    if loaded != counts:
        raise GateError(f"COPY row evidence mismatch: {loaded} != {counts}")

    signature_rows, signature_event = query(
        "\nUNION ALL\n".join(content_hash_sql(table, package.fields[table]) for table in TABLE_ORDER),
        label="content_hash",
    )
    events.append(signature_event)
    observed = {str(row["TABLE_NAME"]): (int(row["ROW_COUNT"]), str(row["ROWS_DIGEST"])) for row in signature_rows}
    if set(observed) != set(TABLE_ORDER):
        raise GateError("content-hash query did not cover the ten SOURCE tables")
    for table in TABLE_ORDER:
        row_count, digest = observed[table]
        expected_digest = package.evidence["tables"][table]["multiset_rows_sha256"]
        if row_count != counts[table]:
            raise GateError(f"{table} loaded row count {row_count} != {counts[table]}")
        if digest != expected_digest:
            raise GateError(f"{table} in-Snowflake content hash {digest} != package {expected_digest}")

    receipt = (
        f"INSERT INTO {MANIFEST_TABLE} "
        "(manifest_sha256,scale,total_rows,table_counts,loader_version,loaded_at_utc) SELECT "
        f"{sql_string(package.manifest_sha256)},{sql_string(package.manifest['scale'])},"
        f"{sum(counts.values())},PARSE_JSON({sql_string(json.dumps(counts, sort_keys=True, separators=(',', ':')))}),"
        f"{sql_string(LOADER_VERSION)},SYSDATE()"
    )
    events.append(
        run_snow(
            tagged_sql(
                ((f"clear_manifest", f"DELETE FROM {MANIFEST_TABLE}"), ("write_manifest", receipt)),
                "AVIATION_TEMPORAL|DATA-03|manifest",
            ),
            label="manifest",
        )
    )

    tracking_rows, tracking_event = query(f"SHOW TABLES IN SCHEMA {DATABASE}.SOURCE", label="change_tracking")
    events.append(tracking_event)
    tracking = {
        str(row["name"]): str(row["change_tracking"]).upper()
        for row in ({str(k).casefold(): v for k, v in item.items()} for item in tracking_rows)
    }
    if set(tracking) != set(TABLE_ORDER) or any(state != "ON" for state in tracking.values()):
        raise GateError(f"CHANGE_TRACKING is not ON for every SOURCE table: {tracking}")

    return {
        "status": "PASSED",
        "operation": "apply",
        "loader_version": LOADER_VERSION,
        "verify_version": VERIFY_VERSION,
        "scope": {"connection": CONNECTION, "role": ROLE, "warehouse": WAREHOUSE, "database": DATABASE},
        "local_preflight": package.evidence,
        "copy_rows_loaded": loaded,
        "in_snowflake_content_hash": {table: observed[table][1] for table in TABLE_ORDER},
        "change_tracking": tracking,
        "timings": {event["label"]: event["wall_seconds"] for event in events},
    }


def drop_orphan_staging() -> dict[str, Any]:
    """Drop only the ten empty staging tables left behind by the failed cold run."""
    expected = {f"{ORPHAN_STAGING_PREFIX}{PREFIX[table]}_STAGE" for table in TABLE_ORDER}
    rows, _ = query(
        f"SELECT table_name,is_transient FROM {DATABASE}.INFORMATION_SCHEMA.TABLES "
        f"WHERE table_schema='VALIDATION' AND STARTSWITH(table_name,{sql_string(ORPHAN_STAGING_PREFIX)}) "
        "ORDER BY table_name",
        label="orphan_inventory",
    )
    found = {str(row["TABLE_NAME"]) for row in rows}
    if not found <= expected:
        raise GateError(f"refusing to drop unrecognized staging objects: {sorted(found - expected)}")
    if not found:
        return {"status": "PASSED", "operation": "drop_orphan_staging", "dropped": []}
    count_rows, _ = query(
        "\nUNION ALL\n".join(
            f"SELECT {sql_string(name)} AS table_name, COUNT(*) AS row_count FROM {DATABASE}.VALIDATION.{name}"
            for name in sorted(found)
        ),
        label="orphan_counts",
    )
    nonempty = [str(row["TABLE_NAME"]) for row in count_rows if int(row["ROW_COUNT"]) != 0]
    if nonempty:
        raise GateError(f"refusing to drop non-empty staging tables: {nonempty}")
    run_snow(
        tagged_sql(
            ((f"drop_{name.lower()}", f"DROP TABLE {DATABASE}.VALIDATION.{name}") for name in sorted(found)),
            "AVIATION_TEMPORAL|DATA-03|drop_orphan_staging",
        ),
        label="drop_orphan_staging",
    )
    remaining, _ = query(
        f"SELECT table_name FROM {DATABASE}.INFORMATION_SCHEMA.TABLES WHERE table_schema='VALIDATION' "
        f"AND STARTSWITH(table_name,{sql_string(ORPHAN_STAGING_PREFIX)})",
        label="orphan_postcheck",
    )
    if remaining:
        raise GateError(f"orphan staging tables remain: {remaining}")
    return {"status": "PASSED", "operation": "drop_orphan_staging", "dropped": sorted(found)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scale", choices=("demo", "smoke"), default="demo", help="generated package scale")
    parser.add_argument("--manifest", type=Path, default=None, help="manifest path (defaults to the --scale package)")
    parser.add_argument("--expect-manifest-sha256", default=None, help="optional pin for the manifest SHA-256")
    parser.add_argument("--preflight", action="store_true", help="run only the local fail-closed package checks")
    parser.add_argument("--apply", action="store_true", help="create the SOURCE tables, load them, and verify")
    parser.add_argument("--print-ddl", action="store_true", help="print the deterministic DDL without connecting")
    parser.add_argument("--drop-orphan-staging", action="store_true", help="drop the empty failed-run staging tables")
    args = parser.parse_args(argv)
    operations = (args.preflight, args.apply, args.print_ddl, args.drop_orphan_staging)
    if sum(map(bool, operations)) != 1:
        parser.error("choose exactly one of --preflight, --apply, --print-ddl, --drop-orphan-staging")
    try:
        if args.print_ddl:
            print(tagged_sql(ddl_statements(parse_contract_fields()), "AVIATION_TEMPORAL|DATA-03|ddl"))
            return 0
        if args.drop_orphan_staging:
            evidence = drop_orphan_staging()
        else:
            manifest_path = (args.manifest or package_dir(args.scale) / "manifest.json").resolve()
            package = preflight_package(manifest_path, expect_manifest_sha256=args.expect_manifest_sha256)
            if package.manifest["scale"] != args.scale and args.manifest is None:
                raise GateError(f"manifest scale {package.manifest['scale']!r} != requested {args.scale!r}")
            evidence = apply_load(package) if args.apply else {
                "status": "PASSED", "operation": "preflight", "local_preflight": package.evidence
            }
        print(json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
        return 0
    except GateError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
