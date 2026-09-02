"""_regen_sources.py - regenerate ``sources.py`` from the live ``INFORMATION_SCHEMA``.

Run as a module to rewrite ``sources.py``::

    .venv/bin/python -m aviation_model._regen_sources     # with rai_code on sys.path

``tests/test_model.py::test_declared_types_match_information_schema`` imports
:func:`load_columns` and :func:`derive_type` from here and re-derives the mapping live, so a
DATA-04 schema change fails a named test instead of producing a silent NaN column.

Why generate rather than hand-write. PROBE U-01 established that strict mode gives **zero**
typo protection on a ``model.Table()``: a misspelled column binds as an ``Any``-typed relation
with no error and yields an empty or NaN result several phases later. PROBE U-02 established
that a *wrongly typed* column is a silent all-NaN column rather than a ``TyperError``. With 749
contracted columns, hand-writing the dicts would be 749 opportunities for exactly those two
failures. Deriving them from ``INFORMATION_SCHEMA`` makes both structurally impossible, and the
result is still an explicit literal dict a reviewer can read.
"""

from __future__ import annotations

import collections
import json
import subprocess
from pathlib import Path
from typing import Any

DB = "PK_AVIATION_TEMPORAL"
ROLE = "RAI_DEMO_AVIATION_TEMPORAL"

# The 34 objects MODEL-01 binds, in load order.
#
# D-0019: the row-scoped ``CODE_RESOLUTION`` (546,494 rows), ``CODE_RESOLUTION_CANDIDATE``
# (424,605) and ``CODE_RESOLUTION_INPUT`` (546,494) are absent by decision, not by oversight.
# Link semantics need only the distinct-code projection, and the measurement that settled it is
# in ``build/task_reports/MODEL-01.json``.
BOUND_OBJECTS: list[tuple[str, str]] = [
    ("SOURCE", "SCHEDULE_SNAPSHOT_CALENDAR"),
    ("SOURCE", "AIRCRAFT_CONFIGURATION"),
    ("MODEL_INPUT", "AIRCRAFT_ELIGIBLE"),
    ("MODEL_INPUT", "AIRCRAFT_EVENT_ELIGIBLE"),
    ("MODEL_INPUT", "AIRCRAFT_EVENT_QUARANTINE"),
    ("MODEL_INPUT", "AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT"),
    ("MODEL_INPUT", "AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT"),
    ("MODEL_INPUT", "AIRCRAFT_TYPE_DEFINITION"),
    ("MODEL_INPUT", "ENGINE_TYPE_DEFINITION"),
    ("MODEL_INPUT", "AIRPORT_CURRENT"),
    ("MODEL_INPUT", "AIRLINE_CURRENT"),
    ("MODEL_INPUT", "CODE_RESOLUTION_CODE"),
    ("MODEL_INPUT", "CODE_RESOLUTION_CODE_CANDIDATE"),
    ("MODEL_INPUT", "MONTH_END_CALENDAR"),
    ("MODEL_INPUT", "ROUTE"),
    ("MODEL_INPUT", "ROUTE_STATE"),
    ("MODEL_INPUT", "ROUTE_STATE_LINEAGE"),
    ("MODEL_INPUT", "SCHEDULE_CANONICAL_OBSERVATION"),
    ("MODEL_INPUT", "SCHEDULE_COMPARISON"),
    ("MODEL_INPUT", "SCHEDULE_EXACT_CHANGE"),
    ("MODEL_INPUT", "SCHEDULE_AMENDMENT_SIDE"),
    ("MODEL_INPUT", "SCHEDULE_AMENDMENT_CANDIDATE"),
    ("MODEL_INPUT", "SCHEDULE_AMENDMENT_GROUP"),
    ("MODEL_INPUT", "SCHEDULE_AMENDMENT_GROUP_MEMBER"),
    ("MODEL_INPUT", "PASSENGER_FLIGHT_CANONICAL"),
    ("MODEL_INPUT", "PASSENGER_FLIGHT_INVALID"),
    ("MODEL_INPUT", "PASSENGER_SOURCE_LINEAGE"),
    ("MODEL_INPUT", "PASSENGER_SOURCE_QUARANTINE"),
    ("MODEL_INPUT", "PASSENGER_PLANNED_LEG"),
    ("MODEL_INPUT", "AIRCRAFT_FLIGHT"),
    ("MODEL_INPUT", "ROTATION_LINK_VALIDATION"),
    ("MODEL_INPUT", "FULFILLMENT_EXACT"),
    ("MODEL_INPUT", "FULFILLMENT_CANDIDATE"),
    ("MODEL_INPUT", "FULFILLMENT_AMBIGUOUS_GROUP"),
]

_COLUMN_QUERY = f"""
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, DATA_TYPE,
       IS_NULLABLE, NUMERIC_PRECISION, NUMERIC_SCALE
FROM {DB}.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA IN ('MODEL_INPUT', 'SOURCE')
ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
"""


def load_columns() -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Read the live column inventory as the demo role, grouped by ``(schema, table)``."""
    proc = subprocess.run(
        ["snow", "sql", "-c", "rai", "--role", ROLE, "--format", "json", "-q", _COLUMN_QUERY],
        capture_output=True,
        text=True,
        check=True,
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in json.loads(proc.stdout):
        grouped[(row["TABLE_SCHEMA"], row["TABLE_NAME"])].append(row)
    return dict(grouped)


def derive_type(column: dict[str, Any]) -> str:
    """The Snowflake-to-RAI mapping this contract needs, as a textual type expression.

    Two entries are not the obvious ones and both are load-bearing:

    * ``TIME -> String``. ``relationalai/util/schema.py`` maps ``TIME`` to ``DateTime`` and
      there is no RAI ``Time`` type, so a ``TIME`` column bound as discovered returns 100% NULL
      (PROBE U-03). Declared ``String`` it is byte-identical to
      ``TO_VARCHAR(t, 'HH24:MI:SS.FF3')``. The coercion is ``TIME``-specific - declaring a
      ``NUMBER``, ``DATE``, ``FLOAT`` or ``BOOLEAN`` column as ``String`` gives an all-NaN
      column - so it must not be generalised.
    * ``NUMBER(p, 0)`` maps to exactly **two** RAI types, not to ``Number.size(p, 0)``. The
      SDK's own CDC mapping buckets integer precision by bit width
      (``relationalai/util/schema.py``: ``digits_to_bits`` then ``sf_numeric_to_type_str``),
      so ``p <= 18`` becomes ``Decimal(18,0)`` - which is ``Number.size(18, 0)`` - and
      ``19 <= p <= 38`` becomes ``Decimal(38,0)``, which is ``Integer``.

      Declaring the faithful per-column precision is therefore *wrong*, and wrong in the
      silent way. It was caught live: ``MONTH_END_CALENDAR.MONTH_INDEX`` is ``NUMBER(19,0)``,
      was declared ``Number.size(19, 0)`` (which is ``Int64``), and returned **600 rows with
      0 non-null values** and no error - while the identical column declared ``Integer``
      returned 600 of 600. ``inspect.schema`` confirms the discovered type is ``Integer``.
      Narrower declarations (``Number.size(4, 0)`` against ``NUMBER(4,0)``) happen to bind, but
      relying on that is relying on an undocumented leniency; matching the SDK's own bucketing
      makes declared and discovered types identical for every column.

      Only ``tests/test_model.py::test_per_column_non_null_matches_sql`` catches this class of
      bug. A row-count check passes with an all-NaN column.
    """
    data_type = column["DATA_TYPE"]
    precision = column["NUMERIC_PRECISION"]
    scale = column["NUMERIC_SCALE"]

    if data_type in ("TEXT", "VARCHAR", "STRING"):
        return "String"
    if data_type == "DATE":
        return "Date"
    if data_type.startswith("TIMESTAMP"):
        return "DateTime"
    if data_type == "TIME":
        return "String"
    if data_type in ("FLOAT", "DOUBLE", "REAL"):
        return "Float"
    if data_type == "BOOLEAN":
        return "Bool"
    if data_type == "NUMBER":
        if scale:
            return f"Number.size({precision}, {scale})"
        # Mirror relationalai/util/schema.py exactly: integer precision is bucketed by bit
        # width, so 1..18 digits land on Decimal(18,0) and 19..38 on Decimal(38,0) = Integer.
        return "Number.size(18, 0)" if precision <= 18 else "Integer"
    raise ValueError(f"unmapped Snowflake type {data_type} on {column['COLUMN_NAME']}")


_HEADER = '''"""sources.py - every ``model.Table()`` binding, with an explicit ``schema=`` dict.

GENERATED from ``PK_AVIATION_TEMPORAL.INFORMATION_SCHEMA.COLUMNS``, then checked in.
Regenerate with ``python -m aviation_model._regen_sources``;
``tests/test_model.py::test_declared_types_match_information_schema`` re-derives the mapping
live and fails on any drift.

Three rules this file exists to enforce, all from ``build/design/PROBE_RESULTS.md``:

* **R1 - an explicit ``schema=`` dict everywhere.** Strict mode gives *zero* typo protection
  on a ``model.Table()`` (PROBE U-01): a misspelled column binds silently as an ``Any``-typed
  relation and produces an empty or NaN result later. The dict is the only defence, and
  ``inventory.py`` asserts that no discovered column is ``Any``.
* **U-03 - the 26 Snowflake ``TIME`` columns are declared ``String``.** Discovered *or*
  explicitly declared as ``DateTime`` they come back 100% NULL with no error. Declared
  ``String`` the value is byte-identical to ``TO_VARCHAR(t, 'HH24:MI:SS.FF3')``, so every
  time-of-day literal must be written ``'HH:MM:SS.mmm'``; ``'16:00:00'`` matches zero rows.
* **U-02 - a wrong declared type is a silent all-NaN column, not a ``TyperError``.** Types are
  therefore derived from ``INFORMATION_SCHEMA`` rather than eyeballed, and the integer mapping
  mirrors the SDK's own CDC bucketing rather than the column's declared precision:
  ``NUMBER(p,0)`` with ``p <= 18`` is ``Number.size(18, 0)`` and with ``19 <= p <= 38`` is
  ``Integer``. Declaring the faithful ``Number.size(19, 0)`` for a ``NUMBER(19,0)`` column
  returned 600 rows and 0 non-null values, silently - see :func:`derive_type`. The MODEL-01
  gate asserts per-column non-null counts against SQL, not just row counts, which is the only
  check that catches it.

D-0019: the row-scoped ``CODE_RESOLUTION`` (546,494 rows), ``CODE_RESOLUTION_CANDIDATE``
(424,605) and ``CODE_RESOLUTION_INPUT`` (546,494) are deliberately NOT bound. Link semantics
need only the distinct-code projection ``CODE_RESOLUTION_CODE`` (390 rows), and every other
MODEL_INPUT object already carries its own resolved target id plus resolution status. The
timed experiment that settled it is recorded in ``build/task_reports/MODEL-01.json``; the
tables stay materialized and reachable from SQL.
"""

from relationalai.semantics import (
    Bool,
    Date,
    DateTime,
    Float,
    Integer,
    Number,
    String,
)

from .constants import DB
from .model import model

'''


def render(columns_by_object: dict[tuple[str, str], list[dict[str, Any]]]) -> str:
    """Render the whole ``sources.py`` body."""
    blocks, names = [], []
    for schema_name, table_name in BOUND_OBJECTS:
        columns = columns_by_object.get((schema_name, table_name))
        if not columns:
            raise ValueError(f"{schema_name}.{table_name} not found in INFORMATION_SCHEMA")
        alias = ("SRC_" if schema_name == "SOURCE" else "MI_") + table_name
        lines = []
        for column in columns:
            rai_type = derive_type(column)
            note = "  # TIME -> String (PROBE U-03)" if column["DATA_TYPE"] == "TIME" else ""
            lines.append(f'    "{column["COLUMN_NAME"].lower()}": {rai_type},{note}')
        body = "\n".join(lines)
        blocks.append(
            f"SCHEMA_{alias} = {{\n{body}\n}}\n\n"
            f'{alias} = model.Table(f"{{DB}}.{schema_name}.{table_name}", schema=SCHEMA_{alias})'
        )
        names.append((alias, schema_name, table_name))

    tail = '\n\n\n# alias -> (Table, "SCHEMA.TABLE", declared column -> RAI type)\nTABLE_INVENTORY = {\n'
    tail += "".join(
        f'    "{alias}": ({alias}, "{schema_name}.{table_name}", SCHEMA_{alias}),\n'
        for alias, schema_name, table_name in names
    )
    tail += "}\n"
    return _HEADER + "\n\n".join(blocks) + tail


def main() -> None:
    target = Path(__file__).with_name("sources.py")
    columns_by_object = load_columns()
    target.write_text(render(columns_by_object))
    total = sum(
        len(columns_by_object[(s, t)]) for s, t in BOUND_OBJECTS
    )
    print(f"wrote {target} - {len(BOUND_OBJECTS)} tables, {total} columns")


if __name__ == "__main__":  # pragma: no cover - operational entry point
    main()
