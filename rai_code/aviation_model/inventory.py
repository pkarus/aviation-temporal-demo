"""inventory.py - ``inspect.schema(model)`` dumped to JSON, plus the two assertions that matter.

Two jobs:

* **MODEL-01's exit artifact.** ``build/design/ontology_inventory.json`` is what the gate, the
  runbook and the notebook read to describe the ontology, and it is what MODEL-02's parity test
  diffs the standalone file against.
* **The only defence against two silent failure modes**, both measured live by PROBE-01 and
  neither of which raises anything:

  1. ``no_any_columns`` - a mistyped column in a ``model.Table()`` ``schema=`` dict binds
     *silently* as an ``Any``-typed relation (U-01). Strict mode does not stop it. It then
     produces an empty or NaN result in a query three phases later. One assertion over
     ``inspect.schema(model).tables`` catches every column typo in ``sources.py`` and costs
     nothing.
  2. ``per_column_non_null`` - a *wrongly declared type* yields an all-NaN column rather than a
     ``TyperError`` (U-02). A row-count check passes happily. So the gate compares the non-null
     count of every bound column against ``COUNT(<col>)`` in SQL.

``inspect.schema`` is also the "here is what actually registered" artifact, which is a different
thing from "here is what I intended to build" - the second assertion exists because the two
diverged silently in the probe run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from relationalai.semantics import inspect

from .model import model
from .sources import TABLE_INVENTORY

def default_inventory_path() -> Path:
    """Repo-relative artifact path, resolved lazily.

    Lazily because MODEL-02's standalone file has to import cleanly inside a Snowsight or
    Workspace runtime where ``__file__`` may not point anywhere useful and where there is no
    repo to write into. Nothing here touches the filesystem at import time.
    """
    return Path(__file__).resolve().parents[2] / "build" / "design" / "ontology_inventory.json"


INVENTORY_PATH = default_inventory_path()


def _rel(info: Any) -> dict[str, Any]:
    return {
        "name": info.name,
        "type_name": info.type_name,
        "reading": info.reading,
        "is_property": info.is_property,
        "is_identity": info.is_identity,
        "fields": [{"name": f.name, "type_name": f.type_name} for f in info.fields],
        "alt_readings": sorted(info.alt_readings),
    }


def build_inventory() -> dict[str, Any]:
    """Serialise ``inspect.schema(model)`` into a stable, diffable JSON structure.

    Sorted everywhere. ``inspect.schema`` guarantees deterministic *declaration* order, which
    is not the same as being stable across two differently-organised programs - the MODEL-02
    standalone file concatenates the package's modules and so declares in a different order.
    Sorting makes the parity diff compare content rather than sequence.

    Rule texts are excluded on purpose: they embed frontend object ids that differ between
    processes, so including them would make an identical model look different.
    """
    schema = inspect.schema(model)

    concepts = {
        c.name: {
            "extends": sorted(c.extends),
            "identify_by": [_rel(p) for p in c.identify_by],
            "properties": sorted((_rel(p) for p in c.properties), key=lambda d: d["name"]),
            "relationships": sorted(
                (_rel(r) for r in c.relationships), key=lambda d: (d["name"], d["reading"])
            ),
            "data_sources": sorted(c.data_sources),
        }
        for c in schema.concepts
    }

    tables = {
        t.name: {
            "columns": sorted(
                ({"name": col.name, "type_name": col.type_name} for col in t.columns),
                key=lambda d: d["name"],
            ),
            "loads": sorted(t.loads),
        }
        for t in schema.tables
    }

    bare = sorted(
        (_rel(r) for r in schema.bare_relationships), key=lambda d: (d["name"], d["reading"])
    )

    declared = {
        alias: {"object": qualified, "columns": {c: str(t) for c, t in cols.items()}}
        for alias, (_tbl, qualified, cols) in TABLE_INVENTORY.items()
    }

    return {
        "model": schema.name,
        "sdk_version": _sdk_version(),
        "concept_count": len(concepts),
        "table_count": len(tables),
        "property_count": sum(len(v["properties"]) + len(v["identify_by"]) for v in concepts.values()),
        "relationship_count": sum(len(v["relationships"]) for v in concepts.values()),
        "bare_relationship_count": len(bare),
        "define_rule_count": len(schema.defines),
        "require_rule_count": len(schema.requires),
        "declared_source_count": len(declared),
        "declared_column_count": sum(len(v["columns"]) for v in declared.values()),
        "concepts": dict(sorted(concepts.items())),
        "tables": dict(sorted(tables.items())),
        "bare_relationships": bare,
        "declared_sources": dict(sorted(declared.items())),
    }


def _sdk_version() -> str:
    try:
        import relationalai

        return getattr(relationalai, "__version__", "unknown")
    except Exception:  # pragma: no cover - version reporting must never break the dump
        return "unknown"


def assert_no_any_columns(inventory: dict[str, Any]) -> list[str]:
    """Every discovered table column must have a concrete type. Returns the offenders.

    An ``Any`` here means a column name in a ``sources.py`` ``schema=`` dict does not exist in
    Snowflake. PROBE U-01: ``t.no_such_column`` binds without error and shows up as
    ``FieldInfo(name='no_such_column', type_name='Any')``.
    """
    offenders = []
    for table_name, table in inventory["tables"].items():
        for column in table["columns"]:
            if column["type_name"] == "Any":
                offenders.append(f"{table_name}.{column['name']}")
    return sorted(offenders)


def write_inventory(path: Path | None = None) -> dict[str, Any]:
    """Build the inventory, assert no ``Any`` column, and write the JSON artifact."""
    inventory = build_inventory()
    offenders = assert_no_any_columns(inventory)
    if offenders:
        raise AssertionError(
            "Any-typed table columns found, which means a column name in sources.py does not "
            f"exist in Snowflake: {offenders}"
        )
    target = path or INVENTORY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(inventory, indent=1, sort_keys=True, default=str) + "\n")
    return inventory


if __name__ == "__main__":  # pragma: no cover - operational entry point
    inv = write_inventory()
    print(
        f"wrote {INVENTORY_PATH} - {inv['concept_count']} concepts, "
        f"{inv['table_count']} tables, {inv['declared_column_count']} declared columns"
    )
