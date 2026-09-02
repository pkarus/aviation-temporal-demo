# REFERENCE_PATTERNS.md - mined patterns for Phases 5-9

Source repos (read-only, never modified):
- `/Users/piotrkraus/rai-repos/rai-demos/supply_chain_demo` (10 questions, LP + knapsack, the
  older/lighter reference)
- `/Users/piotrkraus/rai-repos/rai-demos/airplanes_demo` (5 acts, MIP + persistent rule, newer
  and more polished per this repo's `REFERENCES.md`)

This demo (`aviation_temporal_demo`) has finished its ontology and all eight queries
(`rai_code/aviation_model/`, `rai_code/manual/aviation_temporal.py`, `rai_code/queries/{uc1,uc2,
rotation}.py`). Remaining phases: local Jupyter notebook (5), Snowsight notebook (6), Cortex
agent (7), HTML runbook + prep gate (8), talk track + handoff (9). This document mines the two
reference demos so those phases copy proven code instead of reinventing it.

Status key used throughout: **CONFIRMED 1.20.1** (checked against this repo's
`.venv/lib/python3.13/site-packages/relationalai`), **UNVERIFIED** (not checked, treat as
suspect), **DROP** (do not port - assumes a solver/optimization this demo does not have).

---

## 0. The two caveats that shape every section below

### 0.1 Both references are prescriptive; this demo has none

`airplanes_demo` is a 5-act MIP demo (assignment + persistent-rule re-solve). `supply_chain_demo`
is a 10-question demo with an LP (Q7) and a knapsack (Q8). **This demo (`aviation_temporal_demo`)
has zero optimization and zero prediction** - BRIEF.md is explicit: "Not forced into v1:
prescriptive optimization and predictive GNNs; the supplied questions do not define a decision
problem or prediction target." Its eight questions are rules, temporal reasoning, relational
aggregation, and one graph traversal (Q08 rotation).

Practical effect on every section below:
- Notebook, runbook, and gate structure (cell layout, HTML shell, check-list pattern) are
  **reusable as-is** - they don't care what kind of query they're wrapping.
- Anything that reads a **solver status** (`OPTIMAL`/`INFEASIBLE`), a **solve duration**, an
  **objective value**, or that resizes a **prescriptive engine** is **DROP** - there is no
  prescriptive engine (`aviation_temporal_prescriptive_*`) in this demo's `BRIEF.md` locked
  names table, only `aviation_temporal_logic_s`.
- Anything that assumes a **persistent-rule re-solve** (Act 5 in airplanes_demo: add a rule,
  re-run the MIP, diff the two solutions) is **DROP** unless this demo grows one - it currently
  has none of the eight questions shaped that way.
- The Cortex agent's `QueryCatalog` chart-hint pattern and the `agent/deploy.py` CLI shape are
  reusable; the parts of `queries.py` that format a solver's objective/status are DROP.

Do not copy a prescriptive scaffold (solver classification, HiGHS/Gurobi selection,
pre-solve validation) into this demo. There is no problem for it to formulate.

### 0.2 SDK drift: 1.2.2 (both references) vs 1.20.1 (this demo)

Confirmed by reading `.dist-info` directly, not by import (importing the model would lock it):

| Repo | relationalai version | Source |
|---|---|---|
| `supply_chain_demo` | **1.2.2** | `.venv/lib/python3.13/site-packages/relationalai-1.2.2.dist-info` |
| `airplanes_demo` | **1.2.2** | `.venv/lib/python3.13/site-packages/relationalai-1.2.2.dist-info` |
| `aviation_temporal_demo` (this repo) | **1.20.1** | `.venv/lib/python3.13/site-packages/relationalai-1.20.1.dist-info` |

That is an 18-minor-version gap. CLAUDE.md's warning ("the reference may be as old as 1.2.2") is
accurate, not conservative. **Every API call quoted from either reference demo in this document
is marked CONFIRMED 1.20.1 only if I independently found the same symbol in this repo's
installed `relationalai` package; everything else is marked UNVERIFIED and must be re-checked
against `rai-querying`/`rai-pyrel-coding` skills or the PyRel checkout before use.** Config-layer
symbols (`create_config`, `ConfigFromActiveSession`, `model.implicit_properties`,
`reasoners.logic.name`) are already confirmed working in this demo's own `rai_code/aviation_model/
config.py` - that file is ground truth for the config pattern, not the reference demos.

### 0.3 No parallel execution

This demo's query modules cannot run concurrently: importing `rai_code/aviation_model` (or the
generated `rai_code/manual/aviation_temporal.py`) is a write transaction that locks the model, and
a concurrent import/read fails with `prepareIndex: model is currently locked` (documented in
`rai_code/queries/uc1.py` module docstring: "Do not run two query modules against this model
concurrently... `warm_model` retries through it; `main()` calls it first."). Any combined
notebook, gate script, or agent process that touches more than one of `uc1`, `uc2`, `rotation`
must **serialize** them - import once, reuse the one `Model`/session, never spawn parallel
workers or async-gather multiple query modules. Flagged inline below wherever a reference
pattern assumes parallel or independent-process execution.

---

## Table of contents

1. Local Jupyter notebook (Phase 5)
2. Snowsight notebook upload + execution (Phase 6)
3. Cortex agent deployment (Phase 7)
4. `prep_demo.py` gate (Phase 8)
5. HTML runbook generator (Phase 8)
6. `_build_config()` dual-runtime comparison (Phase 3, already done here)

---

## 1. Local Jupyter notebook (Phase 5)

Reference: `airplanes_demo/rai_code/manual/eham_acdm_demo.ipynb` (23 cells, the more mature
shape - use this one; `supply_chain_demo/rai_code/manual/supply_chain_demo.ipynb` is the same
idea at 10 questions but its committed copy is a post-execution dump with megabytes of embedded
Plotly JSON, harder to read as a pattern).

### 1.1 Cell layout (confirmed by reading the notebook JSON directly)

`airplanes_demo/rai_code/manual/eham_acdm_demo.ipynb` - 23 cells total, one markdown intro, one
imports cell, then a strict per-act rhythm of (markdown lead-in -> code: run query -> code: plot)
repeated once per act, closed by a markdown wrap-up:

```
  0 markdown  # EHAM A-CDM Decision Hub - Demo Notebook
  1 code      import sys, os ... (imports + event-loop guard, see 1.2)
  2 markdown  ## Act 1 - Rules: TOBT compliance audit
  3 code      df1 = q1_tobt_violations_by_handler()
  4 code      fig = px.bar(...)
  5 markdown  **What the chart shows.** KLG and AGS are running positive ARDT-vs-TOBT deviations...
  6 markdown  ## Act 2 - Graph: KL1234 rotation cascade
  7 code      df2 = q2_rotation_cascade_from('KL1234')
  8 code      # Visualize the cascade as a directed graph ... (networkx + go.Scatter)
  9 markdown  **What the chart shows.** From a single late ALDT input (KL1234), the agent reaches six...
 10 markdown  ## Act 3 - Heuristic: MS5 gate-conflict ranking
 11 code      df3 = q3_ms5_conflict_ranking()
 12 code      df3_sorted = df3.copy() ... (px.bar horizontal ranking)
 13 markdown  **What the chart shows.** Eleven arrival candidates ranked by their MS5 fit...
 14 markdown  ## Act 4 - Prescriptive: TSAT re-sequence under storm         <- DROP (no solver here)
 15 code      df4, si4 = q4_tsat_resequence_under_storm()                  <- DROP
 16 code      # Gantt: each flight as a bar on the storm window timeline   <- DROP
 17 code      # Delay distribution                                        <- DROP
 18 markdown  ## Act 5 - Persistent rule: operator adds a preservation rule <- DROP
 19 code      df5, si5 = q5_tsat_resequence_with_preservation()            <- DROP
 20 code      # Side-by-side: Q4 vs Q5 delays                              <- DROP
 21 code      fig = make_subplots(rows=1, cols=2, ...)                     <- DROP
 22 markdown  **Closing.** Four questions, four reasoners, one semantic model...
```
(cell listing produced by iterating `nb['cells']` from the `.ipynb` JSON; not a paraphrase)

**Reusable as-is:** the intro/imports/per-question-triplet/closing skeleton. Map this demo's
eight questions (`aircraft_as_of`, `status_reversion_spells`, `month_end_fleet_composition`,
`type_engine_histories`, `schedule_four_week_changes`, `market_latest_vs_seven_days`,
`route_capacity_two_clocks`, `actual_rotation_enriched`) onto eight act-blocks in this shape,
14 cells of narrative markdown for the recommended five-question live path if that is what the
talk track wants, or 24 for all eight.

**DROP:** cells 14-21 (Acts 4-5) are the entire prescriptive/persistent-rule half of the
airplanes_demo notebook - the LP solve, `Problem.solve()` call, the Gantt of `minute_offset`
delay, and the before/after re-solve comparison. Nothing in this demo's eight questions has an
`si4`/`si5`-shaped solver-status return value; do not build a cell that expects one.

### 1.2 The event-loop guard (needed to run `Problem.solve()` synchronously inside Jupyter)

Cell 1 of the airplanes_demo notebook, quoted in full - `airplanes_demo/rai_code/manual/
eham_acdm_demo.ipynb` cell index 1:

```python
import sys, os
sys.path.insert(0, os.path.abspath("../.."))

# Disarm PyRel's running-loop guard so synchronous Problem.solve() works
# inside Jupyter (mirrors supply_chain_demo.demo_helpers.setup_jupyter_compat).
import relationalai.client as _ra_client
import relationalai.services.reasoners.client as _ra_reasoners_client
_noop = lambda *a, **k: None
_ra_client.raise_if_running_event_loop = _noop
_ra_reasoners_client.raise_if_running_event_loop = _noop
```

There is **no `nest_asyncio.apply()` anywhere in either reference demo** - grepped both repos,
zero hits. PIPELINE.md's Phase 5 step 2 mentions `nest_asyncio.apply()` as an example fix; the
reference demos actually use this narrower monkeypatch instead. Copy the monkeypatch, not
`nest_asyncio`.

**SDK-drift check, CONFIRMED 1.20.1.** The comment says the patch exists because a *synchronous
solve* needs it; this demo has no solver, but the same guard also fires from `connect_sync` and
`from_session_sync`, which every query path goes through. I read this demo's own installed
package rather than trusting the comment:

- `relationalai/client/__init__.py:27` imports `raise_if_running_event_loop` from
  `relationalai.util.asyncio`, and calls it at line 194 (`connect_sync`) and line 249
  (`from_session_sync`).
- `relationalai/services/reasoners/client.py:14` imports the same symbol and calls it at line
  737 inside the sync `ReasonersClient` wrapper.
- These are the **only three call sites in the whole 1.20.1 package** (grepped
  `raise_if_running_event_loop(` across the installed tree). Both attribute paths the reference
  demos monkeypatch - `relationalai.client.raise_if_running_event_loop` and `relationalai.
  services.reasoners.client.raise_if_running_event_loop` - still resolve to real, still-called
  symbols in 1.20.1, even though `relationalai.client` changed from a flat module to a package
  (`relationalai/client/client.py` plus `relationalai/client/__init__.py`) between 1.2.2 and
  1.20.1. `import relationalai.client as _ra_client` still imports the package and the
  monkeypatch still lands on the name Python resolves at call time, so the patch is CONFIRMED
  to still apply mechanically.
- **UNVERIFIED that it is still *necessary*.** This demo's own `rai_code/queries/*.py` never
  imports `nest_asyncio` or touches `raise_if_running_event_loop` - grepped, zero hits - because
  every one of its three query modules is run today as a plain script (`python rai_code/queries/
  uc1.py`), which has no running event loop. Jupyter's ipykernel does have one. The first time
  this demo runs a query cell inside Jupyter is the first time this guard gets exercised; paste
  the two-line monkeypatch into the imports cell before assuming it is needed, and delete it only
  if a query cell runs clean without it.

### 1.3 Imports cell, the rest of it

Same cell (`eham_acdm_demo.ipynb` cell 1), after the guard:

```python
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import networkx as nx

# Importing the ontology triggers all model.define() statements.
from rai_code.manual.eham_acdm import (
    Flight, Stand, Operator, GroundHandler, model,
    feeds_callsign, slot_blocks, shares_stand,
    Departure, Arrival, TOBTViolation, StormWindowDeparture, PreservedFlight,
)
from rai_code.manual.demo_queries import (
    q1_tobt_violations_by_handler, q2_rotation_cascade_from,
    q3_ms5_conflict_ranking, q4_tsat_resequence_under_storm,
    q5_tsat_resequence_with_preservation,
)
print("imports ok")
```

Adapt for this demo: import the eight query functions from `rai_code.queries.uc1`, `.uc2`, and
`.rotation` in one cell, all in the same process. Because this demo's own docstrings say uc1,
uc2, and rotation all import the *same* singleton `aviation_model.model` (never build their
own), importing all three in one Jupyter kernel is safe and pays the ~130s model-sync cost only
once, on whichever import statement runs first - see 0.3 above and section 4 below for why this
guarantee breaks the moment two of these modules run as **separate processes** instead of one
kernel.

`networkx` is used for the graph question (Act 2 in airplanes_demo -> this demo's Q08 rotation
traversal is the closest analogue, though it is a chain/component walk, not a cascade
reachability query - adapt the visualization, not the underlying graph algorithm).

### 1.4 Figure code: Plotly, both express and graph_objects

Bar chart (Act 1, rules question) - `eham_acdm_demo.ipynb` cell 4:
```python
fig = px.bar(
    df1, x='handler', y='violations', color='avg_deviation_min',
    color_continuous_scale='RdBu_r', color_continuous_midpoint=0,
    title='TOBT violations by handler (4h window before 14:30; |ARDT - TOBT| > 5 min)',
    labels={'avg_deviation_min': 'avg deviation (min)'}, text='violations',
)
fig.update_traces(textposition='outside')
fig.update_layout(height=380, xaxis_title='handler', yaxis_title='violation count')
fig.show()
```
Graph cascade (Act 2) builds a `networkx.DiGraph` from `(src, dst)` edge pairs returned by the
query, then renders it as a `go.Scatter` node/edge trace - the pattern to reuse for this demo's
Q08 rotation-chain visualization (a directed chain/cycle over `AircraftFlight` legs, not a
reachability fan-out, so the layout should be a left-to-right sequence, not `nx.spring_layout`).
Both are UNVERIFIED against 1.20.1 in the sense that neither uses any `relationalai` API - Plotly
and networkx are independent of the SDK version, so nothing here is SDK-drift-sensitive.

### 1.5 `nbconvert --execute` command

**Not found verbatim in either reference demo** - grepped both repos for `nbconvert` and
`papermill`; zero hits outside a comment in `supply_chain_demo/rai_code/manual/demo_helpers.py`
(`bootstrap_path()` docstring mentions "when nbclient/papermill" runs the notebook, but no
invocation is scripted anywhere, and `demo_helpers.py` is not imported by
`eham_acdm_demo.ipynb`). Both reference demos verify their local notebook by opening it
interactively (`README.md`/`CLAUDE.md`: `.venv/bin/python -m jupyter lab rai_code/manual/
eham_acdm_demo.ipynb`), not by a scripted headless run. This demo's own PIPELINE.md Phase 5 exit
criterion is explicit and is the one to follow instead:

```
.venv/bin/jupyter nbconvert --execute --to notebook --inplace rai_code/manual/<domain>_demo.ipynb
```

Treat this as this demo's own requirement, not a mined pattern - there is nothing to adapt from
the references here, only to note that they skipped this check and paid for it with a manual
step; the `--execute --inplace` invocation is the more rigorous of the two options PIPELINE.md
Phase 5 offers (`papermill` is the other) and matches the same Phase 8 gate philosophy used
everywhere else in this repo (script-verified, not eyeballed).

---

## 2. Snowsight notebook upload + execution (Phase 6)

Reference: `airplanes_demo/rai_code/manual/eham_acdm_demo_snowsight.ipynb` +
`airplanes_demo/prep_demo.py::check_snowsight_notebook()` (the only place the upload flow is
scripted in either reference demo - `supply_chain_demo` has separate `_local.ipynb` /
`_snowsight.ipynb` files but no scripted upload path was found; its notebook is pushed by hand).

### 2.1 Stage + notebook creation SQL, quoted exactly

`airplanes_demo/prep_demo.py:511-563` (`check_snowsight_notebook`):

```python
_snow_exec(
    f"CREATE SCHEMA IF NOT EXISTS {DB}.{NB_SCHEMA}; "
    f"CREATE STAGE IF NOT EXISTS {DB}.{NB_SCHEMA}.{NB_STAGE} "
    f"DIRECTORY = (ENABLE = TRUE) "
    f"ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');"
)

put_stmt = ";\n".join(
    f"PUT file://{p.absolute()} @{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}/ "
    f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
    for p in NB_SOURCES
)
_snow_exec(put_stmt + ";")

_snow_exec(
    f"CREATE OR REPLACE NOTEBOOK {DB}.{NB_SCHEMA}.{NB_NAME} "
    f"FROM '@{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}' "
    f"MAIN_FILE = '{NB_MAIN}' "
    f"QUERY_WAREHOUSE = RAI_XS "
    f"RUNTIME_NAME = 'SYSTEM$BASIC_RUNTIME' "
    f"EXTERNAL_ACCESS_INTEGRATIONS = (PYPI_ACCESS_INTEGRATION) "
    f"COMMENT = 'EHAM A-CDM Decision Hub - 5-act PyRel demo. Stage folder: {NB_FOLDER}/';"
)
_snow_exec(
    f"ALTER NOTEBOOK {DB}.{NB_SCHEMA}.{NB_NAME} "
    f"ADD LIVE VERSION FROM LAST;"
)
```
with `NB_SCHEMA = "NOTEBOOKS"`, `NB_STAGE = "ACDM_NOTEBOOK_STAGE"`, `NB_FOLDER = "planes"`,
`NB_NAME = "EHAM_ACDM_DEMO"`, `NB_MAIN = "eham_acdm_demo_snowsight.ipynb"` (`prep_demo.py:40-44`).
`AUTO_COMPRESS=FALSE` on the PUT matters - Snowsight needs to read the `.ipynb` as a plain file,
not a `.gz`. The whole block is idempotent (`CREATE SCHEMA/STAGE IF NOT EXISTS`, `CREATE OR
REPLACE NOTEBOOK`, `PUT ... OVERWRITE=TRUE`), which is exactly the shape PIPELINE.md Phase 6
wants and maps directly onto this demo's locked `PK_AVIATION_TEMPORAL.NOTEBOOKS` schema name.

`EXTERNAL_ACCESS_INTEGRATIONS = (PYPI_ACCESS_INTEGRATION)` is present in the statement itself
(not set later via ALTER or the UI), which is the whole point per this demo's own CLAUDE.md: `
CREATE OR REPLACE` does not carry over a UI-set integration, so a redeploy that omits this clause
silently re-breaks the first cell's `pip install` on the next fresh container. This is the exact
code that avoids that failure mode - copy the clause verbatim into whatever DDL-builder this
demo's Phase 6 writes.

### 2.2 What is NOT in the reference demos: `COMPUTE_POOL` and headless `snow notebook execute`

Grepped both repos for `COMPUTE_POOL`, `compute_pool`, and `"notebook execute"` - **zero hits in
either reference demo.** `airplanes_demo` never calls `snow notebook execute`; its gate only PUTs
files and runs `ALTER NOTEBOOK ... ADD LIVE VERSION FROM LAST`, then tells the operator to open it
manually (`prep_demo.py`'s success banner literally says "Open the Snowsight notebook (first run
only: click 'Packages' and add relationalai==1.2.2...)" and links the URL - see 2.4). The
`RUNTIME_NAME = 'SYSTEM$BASIC_RUNTIME'` value they use is a warehouse-backed runtime, which is
presumably why they never needed a compute pool - `SYSTEM$BASIC_RUNTIME` notebooks provision
their own runtime on open and were never run headlessly.

This demo's own `CLAUDE.md` (this repo) independently documents a **different, container-backed
failure mode**: "headless `snow notebook execute` also needs a `COMPUTE_POOL` set (interactive
open provisions one automatically; headless does not)" and the exact error text "Notebook runtime
is set, but no compute pool is specified to run in." **There is nothing to mine from either
reference for this** - confirmed locally: `snow notebook --help` lists `execute` as "Executes a
notebook in a headless mode" (a real, current CLI subcommand - `snow notebook execute IDENTIFIER
-c <conn>`), but the SQL that attaches a compute pool (`ALTER NOTEBOOK ... SET COMPUTE_POOL =
'<pool>'`) is not demonstrated anywhere in either demo. Phase 6 of this demo is breaking new
ground here relative to the references: write the `ALTER NOTEBOOK ... SET COMPUTE_POOL` step
fresh, using this repo's own CLAUDE.md as the spec, and verify with `snow notebook execute` (not
just PUT + ADD LIVE VERSION) since that is the stronger Phase 6 exit criterion PIPELINE.md
actually asks for. Do not skip the manual Snowsight re-open check either - PIPELINE.md is explicit
that CLI success can mask a silently-failed chart render, which is exactly the failure mode the
references never caught because they never ran headlessly at all.

### 2.3 First cell: `pip install relationalai`, PyPI egress, protobuf pin

`airplanes_demo/rai_code/manual/eham_acdm_demo_snowsight.ipynb` cell 0, quoted in full:

```python
# Snowsight's Anaconda channel doesn't ship relationalai, so pip install it.
# relationalai 1.2.2 needs protobuf >= 5.27 (for `runtime_version`), but the
# Snowsight runtime pre-imports an older protobuf from /opt/python. Force-
# upgrade protobuf alongside relationalai, then clear any pre-imported
# google.* from sys.modules so the next import picks the new version.
import subprocess, sys, importlib
subprocess.check_call([
    sys.executable, '-m', 'pip', 'install', '--quiet', '--upgrade',
    'protobuf>=5.27,<6', 'relationalai==1.2.2',
])
for _name in list(sys.modules):
    if _name == 'google' or _name.startswith('google.'):
        del sys.modules[_name]
importlib.invalidate_caches()
```

**UNVERIFIED for this demo's version.** The pinned `protobuf>=5.27,<6` and `relationalai==1.2.2`
are specific to the reference demos' SDK version; this demo must `pip install relationalai==
1.20.1` (matching its `.venv`) and re-derive whatever protobuf floor 1.20.1 actually needs by
running the cell live rather than copying the version numbers - I did not find a protobuf pin
requirement documented anywhere in this repo's own code, so this may or may not still be a live
issue at 1.20.1; treat the `sys.modules` eviction trick as reusable defensive code regardless (it
is harmless if the pin turns out to be unnecessary).

### 2.4 Session/import bootstrap: `get_active_session`, sibling-file fallback, Int128 patch

`airplanes_demo/rai_code/manual/eham_acdm_demo_snowsight.ipynb` cell 2 (abridged; full text
already pulled into this session):

```python
# Sibling .py modules travel with this notebook in the Snowsight version snapshot
# AND on the backing stage, so probe common locations and fall back to GET'ing
# them from the stage if needed.
_CANDIDATES = [os.getcwd(), os.path.join(os.getcwd(), "rai_code", "manual"),
               "/home/udf", "/snowflake/notebook", ...]
_HERE = next((d for d in _CANDIDATES if d and os.path.isfile(os.path.join(d, "eham_acdm.py"))), None)
if _HERE is None:
    from snowflake.snowpark.context import get_active_session
    _session = get_active_session()
    _HERE = tempfile.mkdtemp(prefix="acdm_planes_")
    for _name in ("eham_acdm.py", "demo_queries.py"):
        _session.file.get(f"@ACDM_DEMO.NOTEBOOKS.ACDM_NOTEBOOK_STAGE/planes/{_name}", _HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Disarm PyRel's running-loop guard (Snowsight kernel always has an active event loop) - same
# two-line patch as the local notebook, see section 1.2.
import relationalai.client as _ra_client
import relationalai.services.reasoners.client as _ra_reasoners_client
_ra_client.raise_if_running_event_loop = lambda *a, **k: None
_ra_reasoners_client.raise_if_running_event_loop = lambda *a, **k: None

# Snowsight's pyarrow chokes on RAI's Int128Array because the class doesn't
# implement __array__. Add one that downcasts to int64.
try:
    from v0.relationalai.clients.result_helpers import Int128Array
    def _int128_to_int64(self, *_a, **_k):
        return np.array([0 if v is pd.NA else int(v) for v in self._data], dtype='int64')
    Int128Array.__array__ = _int128_to_int64
except Exception as _patch_err:
    print(f'Int128Array patch skipped: {_patch_err}')

import streamlit as st   # Snowsight notebooks render via Streamlit
...
st.plotly_chart(fig, use_container_width=True)   # NOT fig.show()
```

Three things to carry over, each independently corroborated by this demo's own code rather than
taken on faith:

- **`get_active_session()` + stage fallback for sibling files is reusable as-is** - this demo's
  `rai_code/aviation_model/config.py::_active_snowpark_session()` already does the
  `get_active_session()` probe (confirmed - I read the file directly, quoted in section 6 below),
  so the runtime-detection half of this pattern is already proven inside this repo. The
  stage-`.file.get()` fallback for the sibling `.py` modules is new work for this demo's Phase 6
  (it uploads a generated standalone file, `rai_code/manual/aviation_temporal.py`, plus whichever
  query modules Phase 6 needs, to `PK_AVIATION_TEMPORAL.NOTEBOOKS.<stage>/<folder>/`) but the
  probe-then-GET shape is directly portable.
- **The Int128Array patch is CONFIRMED still relevant, independently** - not by reading
  airplanes_demo, but because this demo's own `rai_code/queries/uc1.py`, `uc2.py`, and
  `rotation.py` all independently discovered and documented the exact same fact against 1.20.1:
  "RAI Integer / Int128Array cell to int. Pandas reductions on Int128 raise" (`uc1.py:237`) and
  "RAI Date properties arrive as pandas Timestamp and integer aggregates as Int128; comparing
  either to a frozen datetime.date or int fails" (`uc2.py:405-406`). Both projects hit the same
  pyarrow/Int128 interaction from opposite directions eighteen minor versions apart - strong
  cross-confirmation that it is a structural property of the RAI result-materialization path, not
  a 1.2.2-only bug. This demo's query layer already normalizes at the DataFrame-cell level (its
  own `_cell()` helpers); the Snowsight notebook only needs the `Int128Array.__array__` patch if
  a raw un-normalized RAI DataFrame is ever displayed directly (e.g. `model.select(...).to_df()`
  in a scratch cell) rather than through this demo's own query functions, which already return
  normalized frames. Likely unnecessary if every notebook cell only ever calls `uc1.py`/`uc2.py`/
  `rotation.py` functions; UNVERIFIED either way until a raw `.to_df()` is actually displayed in
  1.20.1's Snowsight runtime.
- **`import streamlit as st` and `st.plotly_chart(...)` instead of `fig.show()` is
  Snowsight-specific and UNVERIFIED against 1.20.1** in the sense that it has nothing to do with
  the `relationalai` version - Snowsight notebooks are Streamlit-backed regardless of PyRel
  version, so this should still be the correct rendering call, but it was not independently
  confirmed from this demo's own code (this demo has not built a Snowsight notebook yet). Use
  `st.plotly_chart(fig, use_container_width=True)`, not `fig.show()`, in every Snowsight cell.

### 2.5 Packages: declared via `Packages` UI click, not in the notebook or CREATE statement

Neither `CREATE OR REPLACE NOTEBOOK` nor any cell declares `plotly`/`networkx`/`pandas` as
Snowflake Anaconda packages - `prep_demo.py`'s success-path warning says it outright:
`"first open: click 'Packages' in the toolbar and add relationalai==1.2.2, plotly, networkx"`
(`prep_demo.py:475`, the `warnings=[...]` list on the passing `check_snowsight_notebook`
`CheckResult`). This is a manual, one-time, per-notebook UI step that the reference demos do not
automate - `relationalai` itself is `pip install`-ed in cell 0 (see 2.3) because it is not on
Anaconda at all, but `plotly`/`networkx`/`pandas` are on Anaconda and are added via the UI
Packages picker, not scripted. Document this as a manual first-open step in this demo's Phase 6
notes rather than looking for automation that does not exist in either reference.

---

## 3. Cortex agent deployment (Phase 7)

Reference: `airplanes_demo/agent/deploy.py` (193 lines) + `airplanes_demo/agent/queries.py`
(168 lines). **This is the strongest-confirmed section in this document** - every symbol quoted
below was independently found, by file path and line number, inside this demo's own installed
`relationalai==1.20.1` package (not inferred, not assumed carried-over from 1.2.2).

### 3.1 The whole shape is CONFIRMED to still exist in 1.20.1

```
.venv/lib/python3.13/site-packages/relationalai/agent/cortex/__init__.py
.venv/lib/python3.13/site-packages/relationalai/agent/cortex/cortex_agent_manager.py
.venv/lib/python3.13/site-packages/relationalai/agent/cortex/deployment_config.py
.venv/lib/python3.13/site-packages/relationalai/agent/cortex/queries.py
.venv/lib/python3.13/site-packages/relationalai/agent/cortex/verbalize.py
.venv/lib/python3.13/site-packages/relationalai/agent/cortex/tool.py
.venv/lib/python3.13/site-packages/relationalai/agent/cortex/discover_imports.py
```
`relationalai/agent/cortex/__init__.py`'s module docstring even ships its own quickstart, and it
is the same shape airplanes_demo hand-wrote:
```python
from relationalai.config import create_config, SnowflakeConnection
from relationalai.agent.cortex import CortexAgentManager, DeploymentConfig, discover_imports, ToolRegistry

session = create_config().get_session(SnowflakeConnection)
manager = CortexAgentManager(
    session=session,
    config=DeploymentConfig(agent_name="MY_ASSISTANT", database="MY_DB",
                             schema="MY_SCHEMA", warehouse="COMPUTE_WH"))

def init_tools():
    from my_project.model import core
    return ToolRegistry().add(model=core.model, description="...")

manager.deploy(init_tools=init_tools, imports=discover_imports())
print(manager.status())
```
`CortexAgentManager` methods, grepped directly from `cortex_agent_manager.py`:
`__init__`, `preflight`, `print_setup_sql`, `deploy`, `update`, `chat` (returns
`CortexAgentChat`), `status` (returns `DeploymentStatus`), `cleanup`. `deploy`/`update`/`status`/
`chat`/`cleanup` are exactly the five airplanes_demo's CLI wraps as `deploy`/`update`/`status`/
`chat`/`teardown`. `preflight` is new relative to what airplanes_demo uses - worth adopting for
this demo's Phase 7 since it is a pre-deploy dry-run check, not present in the 1.2.2-era pattern.

### 3.2 `agent/deploy.py` structure, quoted (adapt names, keep shape)

`airplanes_demo/agent/deploy.py:29-107`:
```python
AGENT_NAME = "acdm"
DATABASE = "ACDM_DEMO"
SCHEMA = "RAI_AGENT"
AGENT_SCHEMA = "SNOWFLAKE_INTELLIGENCE.AGENTS"  # agent must live here to appear in the Snowflake Intelligence picker; sprocs stay in {DATABASE}.{SCHEMA}
WAREHOUSE = "RAI_XS"


def _agent_location() -> str:
    return AGENT_SCHEMA or f"{DATABASE}.{SCHEMA}"


def _build_manager() -> CortexAgentManager:
    session: snowpark.Session = create_config().get_session(SnowflakeConnection)
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}").collect()
    return CortexAgentManager(
        session=session,
        config=DeploymentConfig(
            agent_name=AGENT_NAME, database=DATABASE, schema=SCHEMA,
            agent_schema=AGENT_SCHEMA, warehouse=WAREHOUSE,
            allow_preview=True,  # required for QueryCatalog (PREVIEW)
        ),
    )


def init_tools():
    from rai_code.manual import demo_queries, eham_acdm
    from . import queries
    return ToolRegistry().add(
        model=eham_acdm.model,
        description="... (one paragraph naming every concept + derived relationship + the "
                     "CHART HINTS instruction block, see 3.4) ...",
        verbalizer=SourceCodeVerbalizer(eham_acdm.model, eham_acdm, demo_queries),
        queries=QueryCatalog(
            queries.tobt_violations_by_handler, queries.tobt_violations_by_handler_chart,
            queries.rotation_cascade_from_kl1234, queries.ms5_conflict_ranking,
            queries.ms5_conflict_ranking_chart, queries.tsat_resequence_under_storm,
            queries.tsat_resequence_under_storm_chart, queries.tsat_resequence_with_preservation,
            queries.tsat_act4_vs_act5_chart,
        ),
    )
```
Note `init_tools()` imports the ontology and `agent.queries` **inside the function body**, not
at module scope - the docstring in `relationalai/agent/cortex/__init__.py` explains why: "This
function is executed during each sproc invocation. It must be self-contained - don't close over
local runtime state (sessions, connections, dataframes, etc.)." Keep that discipline for this
demo: `init_tools()` must import `rai_code.manual.aviation_temporal` (or the package) and
`agent.queries` from inside the function, never at the top of `agent/deploy.py`.

**DROP for this demo:** `tsat_resequence_under_storm`, `tsat_resequence_under_storm_chart`,
`tsat_resequence_with_preservation`, and `tsat_act4_vs_act5_chart` are the solver
(Act 4)/persistent-rule-resolve (Act 5) tools - there is no analogue among this demo's eight
questions. `allow_preview=True` is kept only because `QueryCatalog` itself is marked PREVIEW in
this SDK version (confirmed: `airplanes_demo`'s own comment says so, and it is unrelated to
whether the underlying queries are prescriptive) - keep this flag regardless of dropping the
solver tools.

### 3.3 CLI verbs: `deploy` / `update` / `status` / `chat` / `teardown`

`airplanes_demo/agent/deploy.py:120-193`, argparse subcommands wired 1:1 to `CortexAgentManager`
methods:
```python
sub.add_parser("deploy", ...)     # manager.deploy(init_tools=..., imports=discover_imports(), extra_packages=["httpx"])
sub.add_parser("update", ...)     # manager.update(init_tools=..., imports=discover_imports(), extra_packages=["httpx"])
sub.add_parser("status", ...)     # manager.status()
chat_p = sub.add_parser("chat", ...); chat_p.add_argument("message")   # manager.chat().send(message).full_text()
sub.add_parser("teardown", ...)   # manager.cleanup(); prints a WARNING about deleting SI conversation history
```
`extra_packages=["httpx"]` is airplanes_demo-specific (its tools happen to need `httpx` at sproc
runtime) - keep the kwarg shape, drop or replace the package list based on what this demo's own
query modules actually import beyond what `discover_imports()` walks automatically.

### 3.4 The `agent_schema` requirement, quoted exactly (this is the header-line finding)

This demo's own `CLAUDE.md` already states the rule; here is the code that implements it,
confirmed live in both the 1.2.2 reference and the 1.20.1 installed package:

Reference usage - `airplanes_demo/agent/deploy.py:34`:
```python
AGENT_SCHEMA = "SNOWFLAKE_INTELLIGENCE.AGENTS"  # agent must live here to appear in the Snowflake Intelligence picker; sprocs stay in {DATABASE}.{SCHEMA}
```
1.20.1 SDK docstring, `deployment_config.py` (`DeploymentConfig.agent_schema` field), quoted in
full:
```
agent_schema : str, optional
    Fully-qualified ``DATABASE.SCHEMA`` where the agent is created.
    Sprocs and stage remain in ``database``/``schema``. Use
    ``SNOWFLAKE_INTELLIGENCE.AGENTS`` to expose the agent in the
    Snowflake Intelligence UI. Agents created outside that schema
    can still be promoted through the UI. Default: ``None`` (agent
    is created alongside sprocs in ``database``/``schema``).
```
and the implementation that reads it back apart, `deployment_config.py`:
```python
@property
def agent_database(self) -> str:
    """Database where the agent is created."""
    if self.agent_schema is not None:
        return self.agent_schema.split(".")[0]
    return self.database

@property
def agent_schema_name(self) -> str:
    """Schema where the agent is created."""
    if self.agent_schema is not None:
        return self.agent_schema.split(".")[1]
    return self.schema
```
CONFIRMED 1.20.1 both ways: the field exists with the same name and same semantics as the
version airplanes_demo targets, and this demo's own `BRIEF.md` locked-names table already commits
to it (`Agent procedure schema: PK_AVIATION_TEMPORAL.RAI_AGENT`, `Cortex agent: AVIATION_TEMPORAL`
- pair that agent name with `agent_schema="SNOWFLAKE_INTELLIGENCE.AGENTS"` exactly as
airplanes_demo does, sprocs staying in `PK_AVIATION_TEMPORAL.RAI_AGENT`).

### 3.5 `QueryCatalog` / chart-hint pattern (`agent/queries.py`)

`airplanes_demo/agent/queries.py` full pattern, reusable as-is (nothing prescriptive-specific
about the *mechanism*, only about which questions get the `_chart` treatment):
```python
def _wrap_chart(df, *, chart_type, x, y, title, color=None):
    """Wrap a DataFrame with a chart hint the agent can mention in its text reply."""
    hint = {"type": chart_type, "x": x, "y": y, "title": title}
    if color:
        hint["color"] = color
    return {"records": df.to_dict(orient="records"), "chart_hint": hint}

def tobt_violations_by_handler_chart():
    """... When called, the agent will propose 'show this as a bar chart by handler' ..."""
    df = q1_tobt_violations_by_handler()[["handler", "violations"]]
    return _wrap_chart(df, chart_type="bar", x="handler", y="violations",
                        title="TOBT violations by handler (4h before 14:30)")
```
Every tool function is module-level, zero-argument, and returns either a plain `pandas.DataFrame`
or this `{"records": [...], "chart_hint": {...}}` dict - `QueryCatalog`'s generic-tool path
accepts either (confirmed structurally: `relationalai/agent/cortex/queries.py` defines
`QueryCatalog(Queries)` at line 165, in the same file `Queries(ABC)` at line 86 - the abstract
base whose contract both shapes satisfy). Wire one `_chart` variant per question that is
"visualisation-shaped" (rankings, comparisons, before/after) - for this demo's eight questions
that likely means Q03 (month-end fleet composition - a time series), Q02F (spell-duration
distribution), and Q06/Q07 (market entries/exits, capacity) are the natural `_chart` candidates;
Q01 (point-in-time reconstruction) and Q08 (rotation chain) are table/graph-shaped and better
left as plain-table tools, matching how airplanes_demo left its own graph question (Q2, no
`_chart` variant) as plain.

**DROP:** `tsat_resequence_under_storm_chart` and `tsat_act4_vs_act5_chart` - both are
solver-result and before/after-resolve visualizations with no counterpart in this demo.

### 3.6 The `init_tools` model-import constraint, cross-checked against this demo's own lock warning

`init_tools()` runs inside a stored procedure - a fresh Python process - so it does its own
`import rai_code.manual.eham_acdm` (or, for this demo, `import rai_code.aviation_model` /
`rai_code.manual.aviation_temporal`), which is itself a full model-sync write transaction (see
section 0.3). This has a direct consequence for Phase 7 that neither reference demo had to think
about, because neither has a "don't run two of these at once" constraint: **the agent's sproc,
`demo_queries.py`'s smoke test, and a warm Jupyter kernel are three separate processes that each
do their own model import.** As long as they run one at a time (never overlapping in wall-clock
time against the same live model), each pays its own model-sync cost independently and none of
them collide - the lock only bites when two imports race. Sequence Phase 7's `deploy`/`chat`
smoke tests so they never run concurrently with a live `demo_queries.py` or notebook execution
against the same Snowflake database.

---

## 4. `prep_demo.py` gate (Phase 8)

Reference: `airplanes_demo/prep_demo.py` (715 lines - the file REFERENCES.md calls "the
reference"; `supply_chain_demo` has no equivalent gate script).

### 4.1 Shape: `CheckResult` dataclass + `_run_check` wrapper + ordered checks + summary

`airplanes_demo/prep_demo.py:58-92`, quoted:
```python
@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    duration_s: float = 0.0
    warnings: List[str] = field(default_factory=list)

def _run_check(name: str, fn: Callable[[], CheckResult]) -> CheckResult:
    t0 = time.time()
    try:
        result = fn()
    except Exception as e:  # noqa: BLE001
        result = CheckResult(name=name, passed=False, detail=f"exception: {e}")
    result.duration_s = time.time() - t0
    if not result.name:
        result.name = name
    _emit(result)
    return result
```
Every check function returns a `CheckResult` and never raises past `_run_check` - a check that
throws becomes a `passed=False` result with the exception text as `detail`, so one broken check
never aborts the run and every check gets a duration. This is the confirmed-reusable skeleton;
CONFIRMED nothing about it is `relationalai`-version-sensitive (it is plain Python + subprocess +
`snow` CLI calls).

### 4.2 Check order (8 numbered + 2 bonus), and which are DROP for this demo

`airplanes_demo/prep_demo.py:634-664`, the `main()` driver, in order:
```
[1/8] Snowflake CLI + connection           -> check_snow_cli
[2/8] ACDM_DEMO.EHAM schema state          -> check_schema_loaded
[3/8] Talk-track numbers reproduce (SQL)   -> check_validation_numbers
[4/8] Change tracking on every source table -> check_change_tracking
[5/8] RAI reasoner engines READY           -> check_engines_ready       <- ADAPT (see 4.3)
[6/8] End-to-end smoke test (PyRel+HiGHS)  -> check_smoke_demo_queries  <- ADAPT (see 4.4, drop "HiGHS")
[7/8] SI agent deployed                    -> check_agent_deployed
[8/8] Live agent chat (Q1 round-trip)      -> check_agent_chat
[bonus] Demo figures regenerated           -> check_figures
[bonus] Snowsight notebook synced          -> check_snowsight_notebook
```
Reusable as-is: 1, 2, 3, 4, 7, 8, and both bonus checks - none of these touch a solver or a
persistent-rule re-solve; they are generically "is Snowflake state and the deployed artifacts
correct." Adapt only 5 and 6.

### 4.3 `check_engines_ready` - ADAPT: one engine, not two, and the size string differs

`airplanes_demo/prep_demo.py:295-333`, quoted (abridged to the shape):
```python
def check_engines_ready() -> CheckResult:
    engines = _rai_engines_list()
    wanted = {"acdm_logic_l": "Logic", "acdm_prescriptive_m": "Prescriptive"}
    ...
    for name, rtype in wanted.items():
        state = (found[name].get("state") or "").upper()
        if state != "READY":
            new_state = _rai_engine_resume(name, rtype)   # .venv/bin/rai reasoners resume --name --type --wait --timeout-s 600
            ...
```
with the resume helper:
```python
def _rai_engine_resume(name: str, rtype: str) -> str:
    rai = ROOT / ".venv" / "bin" / "rai"
    r = subprocess.run(
        [str(rai), "reasoners", "resume", "--name", name, "--type", rtype,
         "--wait", "--timeout-s", "600"],
        capture_output=True, text=True, timeout=620,
    )
    return "READY" if r.returncode == 0 else f"resume failed: {r.stderr.strip()[:200]}"
```
and the engine-listing helper, which shells into a snippet instead of importing the client
directly (deliberately, to keep `prep_demo.py` import-light and isolate `connect_sync` side
effects from the gate script's own process):
```python
snippet = (
    "from relationalai.config import create_config;"
    "from relationalai.client import connect_sync;"
    "import json;"
    "c = connect_sync(config=create_config());"
    "out = [{'name': r.name, 'state': r.state, 'type': r.type} for r in c.reasoners.list()];"
    "print(json.dumps(out))"
)
```
**CONFIRMED 1.20.1**, checked locally without touching Snowflake: `.venv/bin/rai reasoners
--help` lists `resume` among `create/list/get/sizes/alter/delete/suspend/resume/wait`, and
`.venv/bin/rai reasoners resume --help` shows the identical flag set airplanes_demo uses -
`--name`, `--type`, `--wait/--no-wait`, `--timeout-s` (default now 900, was implicitly whatever
the reference passed - `--timeout-s 600` explicitly overrides it either way). The CLI-shape
half of this pattern is fully portable.

**ADAPT, not drop:** this demo has exactly one engine per its locked names table -
`aviation_temporal_logic_s` - and **no prescriptive engine at all**. Rewrite `wanted` as a
single-entry dict `{"aviation_temporal_logic_s": "Logic"}`, delete the `acdm_prescriptive_m`
line entirely (do not substitute a same-named engine that does not exist - inventing a
prescriptive engine here would silently violate BRIEF.md's "no optimization" scope). Also note
the size-name gotcha this demo's own `config.py` already discovered and airplanes_demo could not
have known (it targets a different SDK version): "SDK 1.20.1 refuses `HIGHMEM_X64_XS` for Logic
reasoners" - so the engine name carries the `_s` suffix (`aviation_temporal_logic_s`), not `_xs`,
and the gate must check for that literal name, not the demo-template's default `<domain>
_logic_xs` pattern REFERENCES.md describes elsewhere.

### 4.4 `check_smoke_demo_queries` - ADAPT: sentinel strings, and no `si4`/`si5` solver status

`airplanes_demo/prep_demo.py:338-368`:
```python
def check_smoke_demo_queries() -> CheckResult:
    r = subprocess.run(
        [str(VENV_PY), "-u", str(ROOT / "rai_code" / "manual" / "demo_queries.py")],
        capture_output=True, text=True, timeout=600, cwd=str(ROOT),
    )
    if r.returncode != 0:
        return CheckResult(name="end-to-end smoke test (demo_queries.py)", passed=False,
                            detail=f"exit={r.returncode}\n{r.stderr.strip()[-500:]}")
    text = r.stdout
    sentinels = {
        "Q1 KLG row": "KLG" in text and "7" in text.split("KLG", 1)[1][:20],
        "Q2 cascade size": "flights at risk: 7" in text,
        "Q4 LP ran": "callsign op pier" in text,
        "Q5 ran": "KL691 delay" in text,
    }
    ...
```
Reusable mechanism: run the smoke script as a subprocess with a timeout, grep stdout for known
anchored-number substrings, fail on any missing sentinel. **DROP** `"Q4 LP ran"` (checks solver
output text) entirely - there is no LP.

**Serialization warning specific to this demo, not present in either reference.** Both reference
demos have exactly one query module (`demo_queries.py`) with all N questions as functions in one
file, so `subprocess.run([VENV_PY, "demo_queries.py"])` is inherently one process, one model
import, no lock risk. **This demo has three separate query modules** - `rai_code/queries/uc1.py`,
`uc2.py`, `rotation.py` - each independently runnable via `PYTHONPATH=rai_code .venv/bin/python
rai_code/queries/uc1.py` and each with its own `main()` / `warm_model()` (confirmed: grepped `def
main` and `def warm_model` in all three files - `uc1.py:1359`/`89`, `uc2.py:1848`/`1806`,
`rotation.py:1000`/`443`). `uc1.py`'s own module docstring is explicit about the consequence:
*"Do not run two query modules against this model concurrently. Building the model is a write
transaction and a concurrent reader errors rather than waiting, with `prepareIndex: model is
currently locked`."* Whatever this demo's Phase 8 gate does in place of `check_smoke_demo_queries`
must invoke `uc1.py`, `uc2.py`, and `rotation.py` as **three sequential subprocess calls, never
via `concurrent.futures`, `multiprocessing`, or backgrounded `subprocess.Popen` calls that
overlap in wall-clock time.** Running them sequentially is safe and is exactly what each script's
own `warm_model()` retry loop is defending against if that guarantee is ever violated (it retries
through the lock rather than failing outright, but paying that retry cost on every gate run is a
sign the gate is invoking them wrong, not a feature to rely on).

### 4.5 Talk-track number validation and change tracking: reusable as-is

`airplanes_demo/prep_demo.py:169-215` (`check_validation_numbers`) runs raw SQL through a
`_snow_sql_json` helper (not shown above but structurally: `snow sql -q ... --format json`-style)
and compares to hard-coded expected values (`{"KLG": 7, "AGS": 5, ...}`, `storm_n == 47`, etc.) -
directly portable pattern: point it at this demo's own anchored numbers and validation SQL
instead (this demo's equivalent of `data/<domain>_demo_validation.sql` from Phase 2, if written).
`check_change_tracking` (`prep_demo.py:222-247`) runs `SHOW TABLES IN SCHEMA {DB}.{SCHEMA}` and
asserts `CHANGE_TRACKING = 'ON'` for a hard-coded table-name set - adapt the table-name set to
this demo's `SOURCE` and `MODEL_INPUT` schema tables.

### 4.6 Exit code and summary banner

`airplanes_demo/prep_demo.py:664-712`: `main()` returns `0` only if every `CheckResult.passed` is
`True` (prints a green "DEMO IS READY" banner with next-step instructions and the Snowsight
notebook URL), else returns `1` (prints a red "DEMO NOT READY" banner listing which checks
failed by name) - `sys.exit(main())` at the bottom. Directly reusable; no SDK dependency.

---

## 5. HTML runbook generator (Phase 8)

Reference: `airplanes_demo/build/generate_demo_figures.py` (384 lines, produces the PNGs) +
`airplanes_demo/RUNNING.html` (1238 lines, the actual runbook) + this repo's own
`RUNBOOK.template.html` (already exists at repo root, 248 lines - part of the demo-agent-template,
not authored by either reference demo).

### 5.1 Figure generation: matplotlib vs Plotly - it is Plotly + kaleido, confirmed

`airplanes_demo/build/generate_demo_figures.py:66-70`, the shared export helper every
`fig_actN()` function calls:
```python
def _write(fig: go.Figure, name: str, *, w: int = 920, h: int = 460):
    path = OUT / name
    fig.write_image(str(path), width=w, height=h, scale=2)
    print(f"  wrote {path.relative_to(ROOT)} ({os.path.getsize(path):,} bytes)")
```
`fig.write_image(...)` is Plotly's kaleido-backed static export (`scale=2` for retina-sharp PNGs
at demo-room-projector resolution). One `fig_actN()` function per act, each building its own
`px.bar` / `go.Figure` with demo-specific styling (`plot_bgcolor="white"`, a fixed font family,
gridline colors) tuned for embedding in a dark-themed HTML page rather than for on-screen Jupyter
viewing - notice the reference explicitly sets `plot_bgcolor`/`paper_bgcolor` to white even though
`RUNNING.html` itself is dark-themed (`RUNBOOK.template.html`'s own `:root` palette is
`--bg: #0f1115`), so the PNG reads correctly against the runbook's `.card .figure` white-ish
figure area rather than blending into the page background. `main()` just calls each
`fig_actN()` in sequence (`generate_demo_figures.py`, tail):
```python
def main():
    fig_act1(); fig_act2(); fig_act3(); fig_act4(); fig_act5()
if __name__ == "__main__":
    main()
```
**No matplotlib anywhere** - grepped, zero hits in either reference demo's figure generator.
DROP `fig_act4`/`fig_act5` (Gantt/solver-delay-distribution/before-after) outright; adapt
`fig_act1`-style bar charts and `fig_act2`-style `networkx`-composited graph figures for this
demo's eight questions (Q02F's spell-duration histogram and Q03's month-end time series are the
closest analogues to `fig_act1`'s bar-chart shape; Q08's rotation chain is the closest analogue
to `fig_act2`'s edge-composited graph figure).

### 5.2 Self-contained, no network dependency: base64 data URIs, not relative paths

**This is a live discrepancy worth flagging rather than silently resolving.** This repo's own
`RUNBOOK.template.html` (already checked into this repo, part of the template, not written by
either reference demo) uses **relative-path `<img>` tags**:
```html
<img src="build/figures/act1_{{ACT1_SLUG}}.png" alt="{{ACT1_TITLE}}">
```
but `airplanes_demo`'s actual, final `RUNNING.html` embeds every figure as an **inline base64
data URI** instead:
```html
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAB4AAAAQQCAYAAAADLEYYAAAQ...">
```
(confirmed by grepping `RUNNING.html` directly - `grep -c "data:image/png;base64" RUNNING.html`
returns a non-zero count, one per embedded figure, and zero `{{...}}` placeholders remain
anywhere in the file). **No script in either reference demo performs this base64 encoding** -
grepped both repos for `base64`, zero hits in any `.py` file. `RUNNING.html` was authored
directly (by an editor or agent) rather than templated from `RUNBOOK.template.html`'s
placeholder mechanism, reading each PNG from `build/figures/` and inlining it by hand/script at
authoring time, not at gate-run time.

Both approaches satisfy PIPELINE.md's own Phase 8 instruction ("Embed each figure either as a
base64 data URI or as a relative path") - they are not in conflict, but they are two different
choices and this demo's own template already picked one (relative path) while the more mature
reference picked the other (base64). Base64 is the stronger choice for "opens in a browser with
no network dependency and no directory structure to preserve" (the file can be moved, emailed, or
opened via `file://` from anywhere and still renders every figure) - relative paths require
`build/figures/` to travel alongside `RUNNING.html` and break if the file is moved on its own.
**Recommendation:** prefer base64 for this demo (matches the more mature reference and the
"self-contained" requirement in this task's own instructions); if relative paths are kept instead
(matching the existing template unmodified), document that `build/figures/` must ship alongside
`RUNNING.html` and never be `.gitignore`'d out from under it. Either way, write a small
`build/embed_figures.py`-style step (not present in either reference; this demo would be first)
that reads `build/figures/*.png`, base64-encodes each, and substitutes it into the
`{{ACT{N}_SLUG}}`-style placeholder already present in this repo's `RUNBOOK.template.html`,
rather than hand-editing the HTML per regeneration the way airplanes_demo evidently did.

### 5.3 `supply_chain_demo/RUNNING.html`: the checklist-only alternative, no figures at all

Confirmed by direct inspection: `supply_chain_demo/RUNNING.html` (1541 lines) contains **zero**
`<img>` tags and **zero** `data:image` strings - it is pure narrative HTML (headers like "The
three RAI brains we light up in this demo", "Confirm the room is set", "Run the notebook
end-to-end to warm every engine you'll use") with no embedded figures at all, matching
REFERENCES.md's description ("less visual, more checklist"). This is a legitimate lighter-weight
alternative if this demo's Phase 8 chooses not to invest in Plotly-PNG generation for the
runbook - the HTML page itself can carry the talk track, the anchored numbers table, and
click-through Snowsight instructions with no figures at all. Given this demo's `BRIEF.md` already
commits to "HTML runbook and narrative: yes" without committing to embedded charts specifically,
either shape satisfies the brief; the airplanes_demo shape (figures) is more compelling for a
customer-facing 30-minute demo, matching this demo's stated audience and depth.

### 5.4 The template shell already in this repo

`RUNBOOK.template.html` (this repo, root) already has the dark-theme CSS variables, reasoner
color-coded badges (`.badge.rules`, `.badge.graph`, `.badge.heuristic`, `.badge.solver`,
`.badge.rule5`), and a `.card` layout with `.card .figure img` styling - **all five badge classes
are prescriptive/persistent-rule-shaped names inherited from the airplanes_demo 5-act arc**
(`rules`/`graph`/`heuristic`/`solver`/`rule5`). This demo has no solver and no persistent-rule
act; rename or repurpose the badge classes to this demo's actual reasoner mix (rules, temporal,
relational/aggregation, graph/path traversal) rather than leaving `.badge.solver` styling
dangling unused or, worse, mislabeling a temporal-reasoning question as "solver" just because the
CSS class already exists.

---

## 6. `_build_config()` dual-runtime comparison

This demo already has a working, live-proven version at `rai_code/aviation_model/config.py`
(Phase 3 is done). This section compares it against the reference pattern only to flag
differences that matter - it is not a rewrite recommendation. Read directly, not paraphrased:

### 6.1 This demo's version - `rai_code/aviation_model/config.py`, quoted in full

```python
def _active_snowpark_session() -> Any | None:
    """Return the ambient Snowpark session, or ``None`` when running locally."""
    try:
        from snowflake.snowpark.context import get_active_session
    except Exception:
        return None
    try:
        return get_active_session()
    except Exception:
        return None


def in_snowflake_runtime() -> bool:
    return _active_snowpark_session() is not None


def _build_config(**overrides: Any):
    """Strict-mode config pinned to the warm logic reasoner, for either runtime."""
    from relationalai.config.config import ConfigFromActiveSession, create_config

    settings: dict[str, Any] = {
        "model": {"implicit_properties": False},
        "reasoners": {"logic": {"name": LOGIC_REASONER}},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key] = {**settings[key], **value}
        else:
            settings[key] = value

    session = _active_snowpark_session()
    if session is not None:
        return ConfigFromActiveSession(**settings)
    return create_config(**settings)
```
with `LOGIC_REASONER = "aviation_temporal_logic_s"` in `constants.py`, and this crucial docstring
note already captured in the file's module header: *"SDK 1.20.1 refuses `HIGHMEM_X64_XS` for
Logic reasoners, so the locked `_xs` name in BRIEF.md does not exist and must not be used."*

### 6.2 Reference version - `supply_chain_demo/rai_code/manual/supply_chain.py:27-46`, quoted in full

```python
_LOGIC_NAME, _LOGIC_SIZE = "supply_chain_logic_l", "HIGHMEM_X64_L"
_PRESC_NAME, _PRESC_SIZE = "supply_chain_prescriptive_m", "HIGHMEM_X64_M"

def _build_config():
    """Auto-discover config (active Snowpark session inside Snowflake, or the
    snow CLI's connections.toml locally), then pin reasoners to the biggest
    named engines."""
    try:
        from snowflake.snowpark.context import get_active_session
        get_active_session()
        from relationalai.config import ConfigFromActiveSession
        cfg = ConfigFromActiveSession()
    except Exception:
        from relationalai.config import create_config
        cfg = create_config()
    cfg.reasoners.logic.name = _LOGIC_NAME
    cfg.reasoners.logic.size = _LOGIC_SIZE
    cfg.reasoners.prescriptive.name = _PRESC_NAME
    cfg.reasoners.prescriptive.size = _PRESC_SIZE
    return cfg

model = Model("supply_chain", config=_build_config())
```
(`airplanes_demo/rai_code/manual/eham_acdm.py:30-40` uses the same `try/get_active_session/
except -> create_config` shape with no `**overrides` kwargs handling, confirmed by the grep
already in this session: `from snowflake.snowpark.context import get_active_session`,
`get_active_session()`, `from relationalai.config import ConfigFromActiveSession`.)

### 6.3 Differences that matter

- **Runtime-detection branch is identical in spirit, safer in this demo's version.** Both do
  `get_active_session()` inside a `try` and fall back to local `create_config()`/`create_config`
  on any exception. This demo's version separates the *probe* (`_active_snowpark_session()`,
  itself double-try/excepted so an import failure and a "no session" `SnowparkSessionException`
  are both silently `None`) from the *build* (`_build_config`), which is a cleaner factoring than
  the reference's single try/except around both the import and the session call, but produces
  the same runtime decision.
- **Attribute mutation (reference) vs constructor kwargs (this demo) - CONFIRMED both still
  work, but the demo's own choice is worth keeping.** The reference sets `cfg.reasoners.
  logic.name = ...` *after* construction; this demo passes `reasoners={"logic": {"name": ...}}`
  as `**settings` into the constructor itself. I did not find independent confirmation in this
  session that post-construction attribute assignment (`cfg.reasoners.logic.name = X`) still
  works identically in 1.20.1's config object - it is plausible either shape still works, since
  neither was contradicted by anything read here, but this demo's own file is the one with a
  PROBE-numbered comment trail ("PROBE-01 confirmed the merge works... even though the docstring
  implies it is required") proving its own shape was actually tested against 1.20.1 live. Trust
  the tested shape over the untested one; do not "fix" `config.py` to match the reference's
  attribute-mutation style.
- **Strict mode (`implicit_properties: False`) has no counterpart in either reference demo** -
  grepped both repos for `implicit_properties`, zero hits. This is not a case of the reference
  demos doing something this demo dropped; it is the reverse - this demo's config is *stricter*
  than either reference, deliberately (its own docstring: "Strict mode does not protect a
  `model.Table()` from a column typo... but it does stop an undeclared Concept property from
  being invented silently"). Nothing to port from the references here; this demo is already ahead
  of them on this axis.
- **Engine sizing is out-of-band in this demo, in-band in the reference.** The reference hardcodes
  `_LOGIC_SIZE = "HIGHMEM_X64_L"` / `_PRESC_SIZE = "HIGHMEM_X64_M"` directly into the config
  object at every model build. This demo's `_build_config()` has no `size` key at all - sizing is
  managed exclusively via the `.venv/bin/rai reasoners alter <name> --size ...` CLI (per this
  repo's own CLAUDE.md "Engine sizing" section), not in code. This is a deliberate difference
  (CLAUDE.md's guidance to "start small... size up only when measured" fits a CLI-driven,
  out-of-band sizing story better than a hardcoded-in-source one) - not a gap to close, but worth
  naming so a future edit doesn't "helpfully" add a `size` key to `constants.py` and reintroduce
  the reference's in-code coupling.
- **No `overrides` kwarg in either reference `_build_config()`.** This demo's version accepts
  `**overrides` and deep-merges them over the two pinned defaults - a capability neither
  reference needed because neither demo's `_build_config()` is called with anything other than
  zero arguments anywhere in either repo (confirmed: `model = Model("supply_chain",
  config=_build_config())` and `eham_acdm.py`'s equivalent both call it bare). This is pure
  addition, not a divergence to reconcile - keep it, it costs nothing and the reference pattern
  simply never needed it.

**Net assessment: this demo's `config.py` is not behind the reference pattern on any axis found
in this review - it is a superset (strict mode, override merging, PROBE-verified against the
actual installed 1.20.1 package) rather than a port of an older pattern. No changes recommended
to `rai_code/aviation_model/config.py` from this comparison.**

---

## Summary: reusable / adapt / drop, one line per file

| Reference file | Verdict | Why |
|---|---|---|
| `airplanes_demo/rai_code/manual/eham_acdm_demo.ipynb` cells 0-13, 22 | REUSABLE (shape) | intro/imports/per-question triplet/closing skeleton; no solver |
| `airplanes_demo/rai_code/manual/eham_acdm_demo.ipynb` cells 14-21 | DROP | Acts 4-5, LP + persistent-rule re-solve |
| event-loop guard (`raise_if_running_event_loop` monkeypatch) | REUSABLE, CONFIRMED 1.20.1 | same 3 call sites still exist; untested whether still *needed* without a solver |
| `nbconvert --execute --to notebook --inplace` | NOT FROM REFERENCE | neither demo scripts this; it's this repo's own PIPELINE.md requirement |
| `airplanes_demo/prep_demo.py::check_snowsight_notebook` (stage+CREATE NOTEBOOK SQL) | REUSABLE (SQL shape), gap on COMPUTE_POOL | idempotent PUT+CREATE OR REPLACE+ADD LIVE VERSION; neither demo does headless `snow notebook execute` or COMPUTE_POOL - new ground |
| Snowsight notebook cell 0 (`pip install relationalai==1.2.2`, protobuf pin) | ADAPT version pins | re-derive against 1.20.1 live, don't copy version numbers |
| Snowsight notebook cell 2 (`get_active_session` fallback, Int128 patch, `streamlit`) | REUSABLE, Int128 independently CONFIRMED by this demo's own `_cell()` helpers | `st.plotly_chart` not `fig.show()` |
| `airplanes_demo/agent/deploy.py` (`CortexAgentManager`/`DeploymentConfig`/`agent_schema`) | REUSABLE, CONFIRMED 1.20.1 at symbol level | strongest-confirmed section in this doc |
| `airplanes_demo/agent/queries.py` (`QueryCatalog`, `_wrap_chart`) | REUSABLE (mechanism) | drop only the 4 solver/resolve tool functions |
| `airplanes_demo/prep_demo.py` (`CheckResult`, check order 1-4/7/8/bonus) | REUSABLE | no SDK dependency, plain Python + `snow` CLI |
| `airplanes_demo/prep_demo.py::check_engines_ready` | ADAPT | one engine (`aviation_temporal_logic_s`), not two; CLI flags CONFIRMED 1.20.1 |
| `airplanes_demo/prep_demo.py::check_smoke_demo_queries` | ADAPT + serialize | 3 query modules, not 1; must run sequentially, never concurrently |
| `airplanes_demo/build/generate_demo_figures.py` | REUSABLE (Plotly+kaleido shape) | drop `fig_act4`/`fig_act5` |
| `airplanes_demo/RUNNING.html` (base64 embedding) | REUSABLE (recommended over this repo's own relative-path template) | no encoding script exists in either reference; would be new work either way |
| `supply_chain_demo/RUNNING.html` (checklist-only, no figures) | ALTERNATIVE, lighter-weight | zero images; valid if figure generation is skipped |
| `supply_chain_demo/rai_code/manual/supply_chain.py::_build_config` | ALREADY SUPERSEDED | this demo's own `config.py` is a superset; no changes recommended |

