"""_parity_check.py - MODEL-02 evidence: the standalone file IS the package.

Prints one JSON line on stdout with the verdict, and exits non-zero on any difference.
``tests/test_model.py::test_standalone_file_matches_the_package`` runs this as a subprocess.

Why a subprocess per artifact. Both the package and the standalone file construct a
``Model("aviation_temporal")``, and PROBE N-02 showed the free ``distinct(...)`` raises
``[Ambiguous model]`` the moment two ``Model`` objects exist in one interpreter. So each form is
loaded in its own child process, dumps its ``inspect.schema`` inventory and its smoke-query
results to a temp file, and the parent diffs the two payloads.

The comparison is deliberately two-sided:

* **Inventory.** The full ``inspect.schema`` dump - every concept, identity, property,
  relationship, alt reading, table and declared column - sorted, so the diff is about content
  and not about the order in which two differently organised programs happened to register the
  same elements. Rule *texts* are excluded because they embed frontend object ids that differ
  per process; the rule *counts* are compared instead.
* **Smoke queries.** Identical inventories would still allow a broken ``define()``, so a set of
  live queries runs against both forms and the results must match exactly - concept counts, the
  1,339-state multi-open beat, the Q03 month-end cardinality, the rotation chain, and the Q08
  as-of enrichment.

Both forms bind the same ``Model`` name against the same account by design: an identical
re-define mints zero new entities (PROBE U-08 / HT-01), so this test does not create a second
copy of anything.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO_ROOT / "rai_code"
STANDALONE_PATH = REPO_ROOT / "rai_code" / "manual" / "aviation_temporal.py"

# Executed inside each child process. ``load`` returns the module-like namespace to probe.
_CHILD = r'''
import datetime as dt, json, sys

MODE = sys.argv[1]
OUT = sys.argv[2]

if MODE == "package":
    sys.path.insert(0, %(package_path)r)
    import aviation_model as ns
    from aviation_model.inventory import build_inventory
    from aviation_model.computed_schedule import (
        CabinDerivationDisagreement, PhysicalServiceDisagreement, RouteStateOperatesOnWeekday,
    )
else:
    import importlib.util
    spec = importlib.util.spec_from_file_location("aviation_temporal_standalone", %(standalone_path)r)
    ns = importlib.util.module_from_spec(spec)
    sys.modules["aviation_temporal_standalone"] = ns
    spec.loader.exec_module(ns)
    build_inventory = ns.build_inventory
    CabinDerivationDisagreement = ns.CabinDerivationDisagreement
    PhysicalServiceDisagreement = ns.PhysicalServiceDisagreement
    RouteStateOperatesOnWeekday = ns.RouteStateOperatesOnWeekday

from relationalai.semantics import distinct
from relationalai.semantics.std import aggregates as aggs

model = ns.model
KD = dt.date(2026, 8, 31)
OP = dt.date(2026, 9, 7)


def scalar(df):
    if df.shape[1] == 0 or df.shape[0] == 0:
        return None
    return df.iloc[0, 0]


def count(concept):
    v = scalar(model.select(aggs.count(concept).alias("n")).to_df())
    return None if v is None else int(v)


smoke = {}

for name in ("Aircraft", "AircraftEvent", "AircraftDimensionDailyAssignment",
             "AircraftDimensionAuditAssignment", "RouteState", "Route", "Schedule",
             "ScheduleObservation", "PassengerFlight", "AircraftFlight",
             "RotationLinkValidation", "MonthEnd", "SnapshotDate", "Airport", "Airline"):
    smoke["count_" + name] = count(getattr(ns, name))

# the multi-open beat
per_route = model.select(
    ns.Route.route_id.alias("route_id"),
    aggs.count(ns.RouteState).per(ns.Route).alias("n"),
).where(ns.RouteState.route == ns.Route, *ns.known_on(ns.RouteState, KD)).to_df()
smoke["multi_open"] = {r: int(n) for r, n in zip(per_route["route_id"], per_route["n"])}

# Q03
q03 = model.select(
    ns.MonthEnd.month_end.alias("month_end"),
    ns.AircraftType.subseries.alias("t"),
    aggs.count(ns.Aircraft).per(ns.MonthEnd, ns.AircraftType).alias("n"),
).where(
    ns.InServiceOnMonthEnd(ns.Aircraft, ns.MonthEnd, ns.AircraftType),
    ns.MonthEnd.month_end >= dt.date(2015, 1, 31),
    ns.MonthEnd.month_end <= dt.date(2024, 12, 31),
).to_df()
smoke["q03_rows"] = len(q03)
smoke["q03_month_ends"] = int(q03["month_end"].nunique())
smoke["q03_cells"] = sorted(
    f"{m}|{t}|{int(n)}" for m, t, n in zip(q03["month_end"], q03["t"], q03["n"])
)

# Q04
q04 = model.select(
    ns.DailyAssignment.dimension.alias("dimension"),
    ns.DailyAssignment.daily_assignment_id.alias("assignment_id"),
    ns.DailyAssignment.previous_definition_id.alias("prev"),
    ns.DailyAssignment.is_type_change.alias("chg"),
).where(
    ns.Aircraft.id == 1001, ns.DailyAssignment.aircraft == ns.Aircraft,
    ns.DailyAssignment.dimension.in_(["aircraft_type", "engine_type"]),
).to_df()
smoke["q04"] = sorted(
    f"{d}|{a}|{p}|{c}" for d, a, p, c in
    zip(q04["dimension"], q04["assignment_id"], q04["prev"].astype(str), q04["chg"].astype(str))
)

# rotation chain and Q08 enrichment
head = ns.AircraftFlight.ref("head")
chain = model.select(
    head.flight_id.alias("segment_id"),
    ns.AircraftFlight.flight_id.alias("flight_id"),
    (ns.rotation_leg_distance(head, ns.AircraftFlight) + 1).alias("leg_order"),
).where(
    ns.RotationSegmentHead(head),
    ns.rotation_leg_distance(head, ns.AircraftFlight),
    ns.AircraftFlight.aircraft == ns.Aircraft, ns.Aircraft.id == 1001,
    ns.AircraftFlight.flight_departure_date == dt.date(2026, 8, 31),
).to_df()
smoke["rotation"] = sorted(
    f"{int(s)}|{int(f)}|{int(o)}"
    for s, f, o in zip(chain["segment_id"], chain["flight_id"], chain["leg_order"])
)

enrich = model.select(
    ns.AircraftFlight.flight_id.alias("flight_id"),
    ns.AircraftFlight.as_of_aircraft_type.subseries.alias("t"),
    ns.AircraftFlight.as_of_engine_type.subseries.alias("e"),
    ns.AircraftFlight.type_discrepancy.alias("d"),
).where(
    ns.AircraftFlight.aircraft == ns.Aircraft, ns.Aircraft.id == 1001,
    ns.AircraftFlight.flight_departure_date == dt.date(2026, 8, 31),
).to_df()
smoke["q08"] = sorted(
    f"{int(i)}|{t}|{e}|{d}"
    for i, t, e, d in zip(enrich["flight_id"], enrich["t"], enrich["e"], enrich["d"])
)

# two-clock Q07
q07 = model.select(distinct(
    ns.Airline.airline_id.alias("airline_id"),
    ns.Route.route_id.alias("route_id"),
    aggs.count(ns.Schedule).per(ns.Airline, ns.Route).alias("n"),
    aggs.sum(ns.RouteState.weekly_frequency).per(ns.Airline, ns.Route).alias("f"),
)).where(
    *ns.known_on(ns.RouteState, KD),
    *ns.operates_on(ns.RouteState, OP, RouteStateOperatesOnWeekday),
    ns.RouteState.marketing_airline == ns.Airline,
    ns.RouteState.route == ns.Route,
    ns.RouteState.schedule == ns.Schedule,
).to_df()
smoke["q07_marketing"] = sorted(
    f"{a}|{r}|{int(n)}|{int(f)}"
    for a, r, n, f in zip(q07["airline_id"], q07["route_id"], q07["n"], q07["f"])
)

# guards
for name, (flag, concept) in {
    "SentinelLeak": (ns.SentinelLeak, ns.DailyAssignment),
    "EndEventDisagreement": (ns.EndEventDisagreement, ns.DailyAssignment),
    "CabinDerivationDisagreement": (CabinDerivationDisagreement, ns.RouteState),
    "PhysicalServiceDisagreement": (PhysicalServiceDisagreement, ns.RouteState),
}.items():
    v = scalar(model.select(aggs.count(concept).alias("n")).where(flag(concept)).to_df())
    smoke["guard_" + name] = None if v is None else int(v)

inventory = build_inventory()
# Rule texts embed per-process frontend object ids, so compare the counts and drop the texts.
payload = {"inventory": inventory, "smoke": smoke}
with open(OUT, "w") as fh:
    json.dump(payload, fh, indent=1, sort_keys=True, default=str)
print("child ok:", MODE, file=sys.stderr)
''' % {"package_path": str(PACKAGE_PATH), "standalone_path": str(STANDALONE_PATH)}


def _run(mode: str, out: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(_CHILD)
        script = fh.name
    proc = subprocess.run(
        [sys.executable, script, mode, str(out)], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"{mode} child failed:\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )


def _first_diff(a, b, path="") -> str | None:
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                return f"{path}.{key}: missing in package"
            if key not in b:
                return f"{path}.{key}: missing in standalone"
            diff = _first_diff(a[key], b[key], f"{path}.{key}")
            if diff:
                return diff
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for index, (left, right) in enumerate(zip(a, b)):
            diff = _first_diff(left, right, f"{path}[{index}]")
            if diff:
                return diff
        return None
    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        package_out = Path(tmp) / "package.json"
        standalone_out = Path(tmp) / "standalone.json"
        _run("package", package_out)
        _run("standalone", standalone_out)
        package = json.loads(package_out.read_text())
        standalone = json.loads(standalone_out.read_text())

    inventory_diff = _first_diff(package["inventory"], standalone["inventory"], "inventory")
    smoke_diff = _first_diff(package["smoke"], standalone["smoke"], "smoke")

    report = {
        "inventory_identical": inventory_diff is None,
        "smoke_identical": smoke_diff is None,
        "inventory_first_diff": inventory_diff,
        "smoke_first_diff": smoke_diff,
        "concept_count": package["inventory"]["concept_count"],
        "table_count": package["inventory"]["table_count"],
        "property_count": package["inventory"]["property_count"],
        "declared_column_count": package["inventory"]["declared_column_count"],
        "define_rule_count": package["inventory"]["define_rule_count"],
        "require_rule_count": package["inventory"]["require_rule_count"],
        "smoke_keys": sorted(package["smoke"]),
        "sfo_lax_multi_open": package["smoke"]["multi_open"].get("SFO->LAX"),
        "q03_rows": package["smoke"]["q03_rows"],
        "q03_month_ends": package["smoke"]["q03_month_ends"],
    }
    print(json.dumps(report))
    return 0 if inventory_diff is None and smoke_diff is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
