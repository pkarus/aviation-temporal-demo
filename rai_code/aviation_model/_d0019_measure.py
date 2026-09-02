"""_d0019_measure.py - the timed experiment D-0019 requires, and nothing else.

D-0019 left the ``CODE_RESOLUTION`` binding decision provisional and gated on a measurement:
MODEL-01 must bind the row-scoped table once, time it, and record the sync and indexing delta.
The decision is explicitly not to be settled by intuition in either direction.

Method. Two fresh models in two separate processes, each measured from an identical starting
point on the same warm reasoner:

* ``baseline`` binds the 34 objects the shipped ontology binds (749 columns), of which the only
  resolution object is the distinct-code projection ``CODE_RESOLUTION_CODE`` (390 rows).
* ``rowscoped`` binds those 34 **plus** the three row-scoped resolution objects:
  ``CODE_RESOLUTION`` (546,494 rows), ``CODE_RESOLUTION_CANDIDATE`` (424,605) and
  ``CODE_RESOLUTION_INPUT`` (546,494) - 1,517,593 extra rows, 3.8 times the whole SOURCE layer.

Each process records wall time to the first ``to_df()`` (which forces source sync plus model
indexing) and then two warm query times. Separate processes because a second ``Model`` in one
interpreter changes the measurement and breaks the free ``distinct(...)`` (PROBE N-02), and
fresh model names because re-using a name after changing the bindings triggers a stale-source
cleanup that would contaminate the timing.

Run::

    .venv/bin/python -m aviation_model._d0019_measure     # with rai_code on sys.path

Prints one JSON line with both measurements and the delta.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PACKAGE_PATH = str(Path(__file__).resolve().parents[1])

EXTRA_OBJECTS = [
    ("CODE_RESOLUTION", 546494),
    ("CODE_RESOLUTION_CANDIDATE", 424605),
    ("CODE_RESOLUTION_INPUT", 546494),
]

_CHILD = r'''
import json, sys, time
sys.path.insert(0, %(package_path)r)

MODE = sys.argv[1]
OUT = sys.argv[2]
STAMP = sys.argv[3]

t0 = time.time()
import importlib.util
from relationalai.semantics import Model, Integer, Number, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.config.config import create_config

# ``_regen_sources`` is loaded BY PATH and not as ``aviation_model._regen_sources``. Importing it
# through the package would execute ``aviation_model/__init__.py`` first, which builds the whole
# 44-concept ontology and would contaminate the very timing this script exists to measure.
_spec = importlib.util.spec_from_file_location("_regen_sources_isolated", %(regen_path)r)
_regen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_regen)
BOUND_OBJECTS = _regen.BOUND_OBJECTS
derive_type = _regen.derive_type
load_columns = _regen.load_columns


def _build_config():
    """The package's strict-mode, pinned-engine config, inlined to keep this measurement
    independent of the package import."""
    return create_config(
        model={"implicit_properties": False},
        reasoners={"logic": {"name": "aviation_temporal_logic_s"}},
    )


TYPES = {"String": String, "Integer": Integer}


def rai_type(spec):
    if spec in TYPES:
        return TYPES[spec]
    from relationalai.semantics import Bool, Date, DateTime, Float
    simple = {"Bool": Bool, "Date": Date, "DateTime": DateTime, "Float": Float}
    if spec in simple:
        return simple[spec]
    inner = spec[len("Number.size("):-1]
    p, s = (int(x) for x in inner.split(","))
    return Number.size(p, s)


columns = load_columns()
t_schema = time.time()

model = Model("d0019_" + MODE + "_" + STAMP, config=_build_config())

objects = list(BOUND_OBJECTS)
if MODE == "rowscoped":
    objects += [("MODEL_INPUT", n) for n in %(extra)r]

tables = {}
n_columns = 0
for schema_name, table_name in objects:
    cols = columns[(schema_name, table_name)]
    n_columns += len(cols)
    tables[table_name] = model.Table(
        "PK_AVIATION_TEMPORAL.%%s.%%s" %% (schema_name, table_name),
        schema={c["COLUMN_NAME"].lower(): rai_type(derive_type(c)) for c in cols},
    )
t_declared = time.time()

# One trivial concept per measured extreme so the model is not empty, then force the sync.
Probe = model.Concept("Probe", identify_by={"raw_code": String})
model.define(Probe.new(raw_code=tables["CODE_RESOLUTION_CODE"].raw_code))

first_t0 = time.time()
n = model.select(aggs.count(Probe).alias("n")).to_df().iloc[0, 0]
first = time.time() - first_t0

warm = []
for _ in range(2):
    w0 = time.time()
    model.select(aggs.count(Probe).alias("n")).to_df()
    warm.append(round(time.time() - w0, 3))

json.dump({
    "mode": MODE,
    "tables_bound": len(objects),
    "columns_bound": n_columns,
    "information_schema_read_s": round(t_schema - t0, 2),
    "declare_s": round(t_declared - t_schema, 2),
    "first_query_s": round(first, 2),
    "warm_query_s": warm,
    "probe_count": int(n),
}, open(OUT, "w"), indent=1)
''' % {
    "package_path": PACKAGE_PATH,
    "regen_path": str(Path(__file__).with_name("_regen_sources.py")),
    "extra": [n for n, _ in EXTRA_OBJECTS],
}


def _run(mode: str, stamp: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(_CHILD)
        script = fh.name
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as out:
        out_path = out.name
    proc = subprocess.run(
        [sys.executable, script, mode, out_path, stamp], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise SystemExit(f"{mode} failed:\n{proc.stdout}\n{proc.stderr}")
    return json.loads(Path(out_path).read_text())


def main() -> None:
    stamp = time.strftime("%H%M%S")
    baseline = _run("baseline", stamp)
    rowscoped = _run("rowscoped", stamp)
    report = {
        "extra_objects": {name: rows for name, rows in EXTRA_OBJECTS},
        "extra_rows": sum(rows for _, rows in EXTRA_OBJECTS),
        "baseline": baseline,
        "rowscoped": rowscoped,
        "first_query_delta_s": round(
            rowscoped["first_query_s"] - baseline["first_query_s"], 2
        ),
        "columns_delta": rowscoped["columns_bound"] - baseline["columns_bound"],
    }
    print(json.dumps(report, indent=1))


if __name__ == "__main__":  # pragma: no cover - operational entry point
    main()
