"""build_notebook.py - generate ``aviation_temporal_demo.ipynb``.

The notebook is generated rather than hand-edited for the same reason
``rai_code/manual/aviation_temporal.py`` is: a .ipynb is JSON with embedded outputs, and a
hand edit to one is unreviewable in a diff. Everything a reader needs to change lives here as
ordinary Python, and the .ipynb is a build artifact.

Run it with the project interpreter:

    .venv/bin/python rai_code/notebooks/build_notebook.py
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "aviation_temporal_demo.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text: str, name: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": name,
        "metadata": {"language": "python", "name": name},
        "outputs": [],
        "source": text.strip("\n").splitlines(True),
    }


CELLS: list[dict] = []

CELLS.append(md("""
# Aviation temporal demo - the ontology and all nine questions

This notebook runs the whole demo against the live `PK_AVIATION_TEMPORAL` database through the
`aviation_temporal_logic_s` reasoner. It opens with the ontology drawn as a graph, then answers
every question in both use cases and draws the answer.

**Use case 1 - what was true, and when.** Q01 reconstructs one aircraft at one instant across
four independent dimension clocks. Q02 and Q02F find storage spells on the audit stream, where
the same-day reversions that the daily projection silently drops still exist. Q03 answers 120
month ends with one query. Q04 puts the type clock and the engine clock side by side and refuses
to align them.

**Use case 2 - what was known, and when.** Q05 classifies schedule changes between weekly
publish snapshots into eight visibly separate event classes. Q06 finds market entries and exits
between two exact knowledge endpoints. Q07 asks for route capacity under the knowledge clock and
the operating clock at once.

**Rotation.** Q08 reconstructs one aircraft's actual flying day and names every way the chain
can break.

Everything below reads from the ontology; nothing is precomputed and nothing is hard-coded.
Expect roughly eight to twelve minutes end to end on a warm reasoner. Q01 is the slowest
question in the notebook and it runs first, so start it and let it settle.
"""))

CELLS.append(code(
    """
# Packages, in two steps, and both are load-bearing.
#
# Step one is the ordinary install. The container does not ship relationalai, and the `!pip`
# magic is also what Snowflake's notebook dependency scanner reads - drop this line and the
# container is built without the package, and the ontology cell fails with
# `Module Not Found: relationalai` before a single query runs.
# EXTERNAL_ACCESS_INTEGRATIONS = (PYPI_ACCESS) on the notebook is what gives this cell PyPI
# egress; without it a fresh container has none and this is where the notebook stops.
!pip install --quiet "relationalai==1.20.1" "plotly>=6.0"

# Step two repairs protobuf, and it is the difference between a notebook that works and one
# that loads the whole ontology and then dies on its first query. `google.protobuf` resolves
# out of the *system* interpreter's site-packages, not the venv pip just installed into, at a
# version below 5.27 - and 5.27 is where `google.protobuf.runtime_version` was introduced.
# Step one does not fix it, because pip sees a protobuf on the path and calls the requirement
# satisfied. RelationalAI's query executor reaches that import lazily, the first time a query
# is actually run rather than when the Model is built, so the failure surfaces several cells
# later as `ImportError: cannot import name 'runtime_version' from 'google.protobuf'`.
#
# The repair is deliberately narrow: protobuf alone, into a directory of its own that is
# forced to the front of sys.path, with `google.*` dropped from sys.modules so the namespace
# package is rebuilt against the new location.
#
# Both installs go through the `!pip` magic rather than `sys.executable -m pip`, because the
# kernel's sys.executable is not necessarily the interpreter whose site-packages `!pip` writes
# to, and step one proves which pip actually reaches the import path.
!pip install --quiet --upgrade --target /tmp/nblibs "protobuf>=5.29,<6"

import sys

NB_LIBS = "/tmp/nblibs"
if NB_LIBS not in sys.path:
    sys.path.insert(0, NB_LIBS)
for _mod in [m for m in list(sys.modules) if m == "google" or m.startswith("google.")]:
    del sys.modules[_mod]

import google.protobuf
from google.protobuf import runtime_version  # the import that fails without the repair

print("protobuf", google.protobuf.__version__, "from", google.protobuf.__file__)

# Report what step one actually resolved. The figure layer needs plotly 6 or newer for the
# pattern fills Q04 and Q07 use to mark an open interval and an unreconciled cabin split.
import plotly

print("plotly", plotly.__version__, "from", plotly.__file__)
""",
    "packages",
))

CELLS.append(code(
    """
# Locate the staged sibling files. In Snowsight the notebook's own folder is the working
# directory; running the same notebook from a checkout puts them one level down.
import os, sys, time, json, warnings

_HERE = next(
    (d for d in (os.getcwd(),
                 os.path.join(os.getcwd(), "rai_code", "notebooks"),
                 os.path.dirname(os.path.abspath("__file__")))
     if os.path.isfile(os.path.join(d, "aviation_temporal.py"))),
    None,
)
if _HERE is None:
    raise ImportError(
        "aviation_temporal.py is not beside this notebook - re-run the deploy script"
    )
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
warnings.filterwarnings("ignore")
print("sources:", _HERE)
""",
    "locate_sources",
))

CELLS.append(code(
    """
# Load the ontology. aviation_temporal.py is the generated standalone artifact: one flat
# module, no relative imports, and a _build_config() that picks ConfigFromActiveSession here
# and create_config() on a laptop. Building the Model is the slow part of this cell.
_t = time.time()
import aviation_temporal

# The three query modules were written against the aviation_model *package*, which cannot be
# imported here because a package of relative imports does not survive the trip to a stage.
# The standalone file is that package flattened, so aliasing it under both names the query
# modules ask for gives them exactly the objects they expect - including the one submodule
# import, aviation_model.computed_schedule. This is an alias, not a copy: there is still
# precisely one Model in the interpreter, which matters because a second one makes the free
# distinct(...) raise [Ambiguous model].
sys.modules["aviation_model"] = aviation_temporal
sys.modules["aviation_model.computed_schedule"] = aviation_temporal

import rotation, uc1, uc2
import aviation_viz as viz

import relationalai

print(f"ontology loaded in {time.time() - _t:.1f}s")
print(f"relationalai {getattr(relationalai, '__version__', '?')} from {relationalai.__file__}")
print(f"reasoner: {aviation_temporal.LOGIC_REASONER}   database: {aviation_temporal.DB}")
""",
    "load_model",
))

CELLS.append(code(
    """
# Wake the reasoner with a trivial query before the demo questions start. warm_model retries
# on 'model is currently locked', which is what a concurrent reader sees while another process
# is still writing the model index.
_t = time.time()
uc1.warm_model()
print(f"reasoner warm in {time.time() - _t:.1f}s")

import plotly.io as pio

# Emit both the plotly mimetype and a self-contained script tag. Snowsight renders the first;
# the second is the fallback for any frontend that does not know the mimetype.
pio.renderers.default = "plotly_mimetype+notebook_connected"
""",
    "warm",
))

CELLS.append(md("""
---
## The ontology

Forty-six concepts, and the shape of the demo is visible in them before a single question is
asked. Node area is how many properties a concept carries; node colour is which of the four
domains it belongs to; edge width and edge colour are both how many separate declarations relate
the two concepts, so the structural spine stands out from the property web.

The dense yellow cluster on the right is the answer to "why is this demo about time" - `Aircraft`
itself carries thirty properties, but the ten `*DailyAssignment` and `*AuditAssignment` concepts
around it carry sixty-three to seventy each, because every one of them is a fact with a validity
interval attached. The pink cluster is the same idea applied to knowledge rather than state:
`RouteState` at seventy-five properties is a schedule as understood on one publish date.

Hover any node for its property count and degree; hover any edge for the actual relationship
readings behind it.
"""))

CELLS.append(code(
    """
with open(os.path.join(_HERE, "ontology_inventory.json"), encoding="utf-8") as fh:
    INVENTORY = json.load(fh)

viz.show(viz.fig_ontology(INVENTORY))
""",
    "ontology_graph",
))

CELLS.append(code(
    """
# The table view. Two of the four domain colours sit below 3:1 contrast on the chart surface,
# so the method's relief rule applies: the same information has to be available without colour.
# Every node is directly labelled in the figure above, and this is the second discharge.
viz.ontology_table(INVENTORY, top=12)
""",
    "ontology_table",
))

CELLS.append(md("""
---
# Use case 1 - what was true, and when

## Q01 - one aircraft at one instant

Four dimension streams - aircraft state, aircraft type, engine type and lifecycle status - are
resolved independently against the same scalar date. No interval is ever intersected with
another interval, which is exactly why the misaligned type and engine boundaries you will see in
Q04 are irrelevant here.

The point of the chart is that **absence is not one thing**. Asking about an aircraft before it
existed, asking inside a genuine hole in its recorded history, and asking after its end of life
are three different facts, and a system that returns an empty row for all three has thrown away
the difference. The mixed row is the proof the four streams really are independent: two say OK
and two say the state is unknown, on the same aircraft on the same day.

Q01 costs up to nine round trips for its single row, so this cell is the slow one.
"""))

CELLS.append(code(
    """
_t = time.time()
Q01 = [
    ("1001 on 2026-08-31 (fully known)", uc1.aircraft_as_of(1001, "2026-08-31")),
    ("1004 on 2019-06-30 (before it existed)", uc1.aircraft_as_of(1004, "2019-06-30")),
    ("1002 on 2022-05-15 (a hole in the history)", uc1.aircraft_as_of(1002, "2022-05-15")),
    ("1556 on 2031-06-30 (mid storage)", uc1.aircraft_as_of(1556, "2031-06-30")),
    ("1000 on 2032-06-30 (after end of life)", uc1.aircraft_as_of(1000, "2032-06-30")),
]
print(f"5 as-of reconstructions in {time.time() - _t:.1f}s")
viz.show(viz.fig_q01(Q01))
""",
    "q01",
))

CELLS.append(code(
    """
import pandas as pd

pd.concat([df.assign(case=name) for name, df in Q01], ignore_index=True)[
    ["case", "aircraft_id", "as_of_date", "is_complete", "aircraft_type",
     "engine_type", "engine_count", "lifecycle_status", "registration_number"]
]
""",
    "q01_table",
))

CELLS.append(md("""
## Q02 - every storage spell, on the audit stream

An `In Service -> Storage -> In Service` round trip. Reading the *daily* projection here is the
fatal mistake: it keeps only the final relevant observation per aircraft, dimension and date, so
aircraft 1001's four same-day observations on 2020-06-01 collapse to one and the zero-day spell
between them disappears with no error at all.

Aircraft 1859 below is the case that proves the point. Its same-day reversion is drawn as a
diamond rather than a bar because it has zero width - and zero width is exactly why the daily
stream loses it.
"""))

CELLS.append(code(
    """
_t = time.time()
Q02_1860 = uc1.status_reversion_spells(1860)
Q02_1859 = uc1.status_reversion_spells(1859)
print(f"2 spell histories in {time.time() - _t:.1f}s")
viz.show(viz.fig_q02(Q02_1860, 1860))
viz.show(viz.fig_q02(Q02_1859, 1859))
Q02_1859
""",
    "q02",
))

CELLS.append(md("""
## Q02F - the same spell definition, over the whole fleet

One query, no per-aircraft loop, and deliberately its own question rather than a widening of
Q02: Q02's parameter schema takes a non-nullable `aircraft_id` and is frozen.

The two bars are a built-in check rather than decoration. `spell_count` counts spells and
`aircraft_count` counts distinct aircraft, and they differ in three of the seven buckets because
one aircraft can contribute several spells to the same bucket. If they were equal in every
bucket, the distinct wrapper would have been lost somewhere and the aggregate would be counting
spell tuples while the column header claims aircraft.
"""))

CELLS.append(code(
    """
_t = time.time()
Q02F = uc1.fleet_storage_spell_distribution("FLEET")
print(f"fleet spell distribution in {time.time() - _t:.1f}s")
viz.show(viz.fig_q02f(Q02F))
Q02F
""",
    "q02f",
))

CELLS.append(md("""
## Q03 - the fleet at 120 month ends, in one query

The calendar is a joined dimension, not a parameter sweep. `MonthEnd` is a materialised concept
over `MODEL_INPUT.MONTH_END_CALENDAR` and the join predicate is a pure inequality, so the
identical query answers an irregular set of dates just as happily. Writing this query 120 times
is one failure mode; writing one that only works because the interval happens to be regular is
the subtler one.

985 rows come back in a few seconds. The line is the fleet total; the heatmap is the same answer
per exact type, and the generational turnover is the thing to look at - narrowbody generation 1
darkest at the start and fading out, generations 2 and 3 darkening as they take over.
"""))

CELLS.append(code(
    """
_t = time.time()
Q03 = uc1.month_end_fleet_composition("2025-01-31", "2034-12-31")
print(f"{len(Q03)} rows over {Q03['month_end'].nunique()} month ends in {time.time() - _t:.1f}s")
viz.show(viz.fig_q03_total(Q03))
viz.show(viz.fig_q03_heat(Q03))
""",
    "q03",
))

CELLS.append(md("""
## Q04 - the type clock and the engine clock, never aligned

One concept plus a `dimension` discriminator, filtered - not two concepts unioned. The contract
keys the daily assignment by `(dimension, aircraft, valid_from, assignment)`, so type and engine
are two slices of one relation.

The independence *is* the answer. Aircraft 1107's type stream breaks where its engine stream does
not, and neither boundary appears in the other; aircraft 1307 is the contrast case where a
regional-jet generation change and an engine change happen to land on the same date. Any join of
the two streams on overlapping validity, any merged timeline, any "as of both" reconstruction
returns the wrong number of rows.
"""))

CELLS.append(code(
    """
_t = time.time()
Q04_1107 = uc1.type_engine_histories(1107)
Q04_1307 = uc1.type_engine_histories(1307)
print(f"2 dimension histories in {time.time() - _t:.1f}s")
viz.show(viz.fig_q04([("aircraft 1107", Q04_1107), ("aircraft 1307", Q04_1307)]))
Q04_1107[["dimension", "valid_from", "valid_to", "definition_label", "engine_count", "is_type_change"]]
""",
    "q04",
))

CELLS.append(md("""
---
# Use case 2 - what was known, and when

## Q05 - schedule changes between weekly publish snapshots

Eight visibly separate event classes in two strictly separated layers. The three `EXACT_*`
classes are a presence-and-content fact set that stands on its own. The five evidence classes
above them say what the exact layer cannot: which removal-and-addition pairs *might* be one
carrier amending one service.

**The trap this question exists for.** `schedule_key` hashes the effective and discontinue dates,
so a carrier shifting either date mints a new key and one amendment arrives looking like a
removal plus an unrelated addition. That is not a bug to be fixed by rewriting the key - it is
what the source does. Recognising the pair needs a match on carrier, flight number, origin and
destination with overlapping date ranges, and where several candidates match, the model says
`AMBIGUOUS` rather than picking one.

The gaps along the x axis are real: an ineligible snapshot is never substituted, so the
comparison simply spans further. The second chart shows what that costs.
"""))

CELLS.append(code(
    """
_t = time.time()
Q05 = uc2.schedule_four_week_changes("2027-01-04", "2027-06-28", 7)
print(f"{len(Q05)} events in {time.time() - _t:.1f}s")
viz.show(viz.fig_q05(Q05))
viz.show(viz.fig_q05_mix(Q05))
""",
    "q05",
))

CELLS.append(code(
    """
# The ambiguous groups, which are the rows the evidence layer refuses to resolve.
Q05[Q05["event_class"].str.startswith("AMBIGUOUS")][
    ["comparison_date", "event_class", "group_id", "member_side", "member_schedule_key",
     "confidence", "crosses_snapshot_gap"]
].head(12)
""",
    "q05_table",
))

CELLS.append(md("""
## Q06 - who entered and who left the market in one week

Grain is carrier role, exact resolved airline, directional route; the measure is the count of
distinct eligible schedule keys. `ENTRY` is zero to positive and `EXIT` is positive to zero.
Every other transition is deliberately *not* an event - a carrier going from one schedule to two
has changed something, but it has not entered a market, and the stable positive shadows in the
data exist to catch a predicate that disagrees.

Both endpoints must be eligible complete snapshots and neither is ever substituted. Marketing and
operating are asked separately because the same flight has two carriers and they are not the same
market.
"""))

CELLS.append(code(
    """
_t = time.time()
Q06_MKT = uc2.market_latest_vs_seven_days("2027-06-28", "2027-06-21", "marketing")
Q06_OP = uc2.market_latest_vs_seven_days("2027-06-28", "2027-06-21", "operating")
print(f"{len(Q06_MKT)} marketing and {len(Q06_OP)} operating events in {time.time() - _t:.1f}s")
viz.show(viz.fig_q06([("marketing", Q06_MKT), ("operating", Q06_OP)]))
""",
    "q06",
))

CELLS.append(md("""
## Q07 - route capacity under both clocks at once

Knowledge validity is half-open and the operating window is inclusive at both ends. Both matter
and dropping either fails quietly: filter on knowledge alone and you get states that are known
but not operating on the operating date; filter on operating alone and you get states as
understood today rather than as understood on the knowledge date. Both give a plausible,
well-formed, wrong answer.

The first chart is the cabin mix. Three of these rows come back `UNRECONCILED` - the four cabin
measures do not sum to the total the source also states, and `SFO->BOS` is off badly enough that
its economy residual is negative. Those rows are drawn as a single hatched total instead of a
stack, because stacking a negative segment would draw a bar that lies about the data.

The second chart is the two-clock claim itself: the same operating week asked from two knowledge
dates a week apart. Eight of these routes are visible from only one of the two. Nothing about the
world changed in between; only what had been published had.
"""))

CELLS.append(code(
    """
_t = time.time()
Q07_LATE = uc2.route_capacity_two_clocks("2027-06-28", "2027-07-05", "marketing")
Q07_EARLY = uc2.route_capacity_two_clocks("2027-06-21", "2027-07-05", "marketing")
print(f"{len(Q07_LATE)} and {len(Q07_EARLY)} rows in {time.time() - _t:.1f}s")
viz.show(viz.fig_q07_cabin(Q07_LATE))
viz.show(viz.fig_q07_clocks([("known on 2027-06-28", Q07_LATE), ("known on 2027-06-21", Q07_EARLY)]))
""",
    "q07",
))

CELLS.append(code(
    """
# The nine-row truth table the two predicates are held to. Exactly two of the nine
# (knowledge_date, operating_date) combinations against one fixture state are eligible.
# Applying half-open semantics to the operating upper bound, or inclusive semantics to the
# knowledge upper bound, changes which - which is the point of freezing it.
_t = time.time()
TT = uc2.both_clocks_truth_table()
print(f"truth table in {time.time() - _t:.1f}s")
TT
""",
    "q07_truth_table",
))

CELLS.append(md("""
---
# Q08 - the rotation, and every way it breaks

An aircraft's actual flying day is a chain: each leg's arrival airport has to be the next leg's
departure airport, the next departure has to be after the previous arrival, and every leg has to
belong to the same aircraft on the same local day. Q08 walks that chain and validates every link.

The first chart is a clean day - five legs, four turnarounds, the ground time falling out between
an arrival and the next departure. The second is the same question asked of an aircraft whose day
is a mess: eleven distinct named failure modes, drawn as the links they are. Arcs above the line
point forward in the sequence and arcs below point backward, so `SELF_LOOP` is a small circle over
one flight and `BACKWARD_TIME` hangs beneath the axis. A ring on a flight is a failure with no
successor to point at.

Eleven named codes, not one generic "invalid". Naming them is what lets an operations analyst act
on the answer instead of just distrusting it.
"""))

CELLS.append(code(
    """
_t = time.time()
Q08_CLEAN = rotation.actual_rotation_enriched(1072, "2027-06-08")
Q08_BROKEN = rotation.actual_rotation_enriched(1035, "2027-07-06")
print(f"2 rotations in {time.time() - _t:.1f}s")
viz.show(viz.fig_q08_rotation(Q08_CLEAN, 1072, "2027-06-08"))
viz.show(viz.fig_q08_anomaly_graph(Q08_BROKEN, 1035, "2027-07-06"))
""",
    "q08",
))

CELLS.append(code(
    """
Q08_BROKEN[["row_kind", "segment_id", "flight_id", "next_flight_id",
            "link_outcome", "anomaly_code", "actual_origin", "actual_destination"]]
""",
    "q08_table",
))

CELLS.append(md("""
---
## What this notebook demonstrated

Nine questions, two clocks, one ontology.

The state clock is what was true. Q01 shows four dimension streams resolved independently at one
instant, with three different kinds of absence kept apart. Q02 and Q02F show that the stream you
read decides the answer - the audit stream keeps same-day reversions that the daily projection
drops without an error. Q03 answers 120 month ends with one query because the calendar is a
joined dimension. Q04 refuses to align two clocks that the data never aligned.

The knowledge clock is what was known. Q05 keeps an exact fact layer and an evidence layer
strictly apart, and says `AMBIGUOUS` where a schedule key change makes an amendment
indistinguishable from an unrelated removal and addition. Q06 refuses to substitute an ineligible
snapshot endpoint. Q07 holds both clocks at once and shows how far the answer moves when only the
knowledge date changes.

Q08 walks the rotation chain and names eleven distinct reasons a link can fail.

None of these answers is stored. Every one is derived from the ontology at query time, which is
why changing the question is a parameter change rather than a new pipeline.
"""))

NB = {
    "cells": CELLS,
    "metadata": {
        # The notebook is deployed on SYSTEM$BASIC_RUNTIME, which is a container runtime with a
        # plain python3 kernel - that is what makes the `!pip install` cell legal.
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def main() -> None:
    TARGET.write_text(json.dumps(NB, indent=1) + "\n", encoding="utf-8")
    n_code = sum(1 for c in CELLS if c["cell_type"] == "code")
    print(f"wrote {TARGET} - {len(CELLS)} cells ({n_code} code, {len(CELLS) - n_code} markdown)")


if __name__ == "__main__":
    main()
