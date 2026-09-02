# PyRel query cookbook for aviation_temporal

Target runtime: **relationalai 1.20.1** (the installed SDK, which is what will actually run).

This file exists so the orchestrator and the query-implementation agents code against quoted,
current source rather than recalled syntax. Every entry carries a citation and a verification
label. Read the "Verification status" section before trusting anything here.

## Path shorthand used in citations

| Shorthand | Absolute path |
|---|---|
| `SDK/` | `/Users/piotrkraus/rai-repos/rai-demos/aviation_temporal_demo/.venv/lib/python3.13/site-packages/relationalai/` |
| `CO/` | `/Users/piotrkraus/rai-repos/PyRel/` |
| `SC/` | `/Users/piotrkraus/rai-repos/rai-demos/supply_chain_demo/` |

## Verification status (read this first)

I could not execute a single PyRel query while writing this file. Three labels are used, and
they mean exactly what they say:

- **[SRC]** — signature, default, or docstring read directly out of the installed 1.20.1
  source at the cited `file:line`. Strong: this is the code that will run.
- **[TEST]** — the construct appears in a runnable test or example in the PyRel checkout.
  Weaker than it looks: the checkout is version **1.2.2**, four months stale (see Drift).
  Treat as "this shape was correct recently", not "this shape is correct now".
- **[UNVERIFIED]** — I am reasoning about behaviour I could not read off a signature or find
  in a test. Every one of these carries a concrete smoke test. Run it before building on it.

**Why nothing is execution-verified.** I attempted a local run to verify these patterns for
real. The SDK does ship a DuckDB connection (`SDK/config/connections/duckdb.py:47`), but it is
explicitly gated as unreleased: `# TODO: uncomment when we release deploy-mode`
(`SDK/config/connections/duckdb.py:44`). In practice `create_config(connections={"db":
{"type": "duckdb", "path": ":memory:"}})` still routes the LQP executor at the Snowflake
resource class and dies asking for `account, password, user, warehouse`. The `local`
connection type wants a RAI server on `localhost:8010`, which is not running. So there is no
offline execution path in 1.20.1, and the orchestrator (which has a live account) is the only
party that can turn a [TEST] or [UNVERIFIED] into a verified fact.

A "run this to confirm" beats my confident guess. Section 17 collects every smoke test into one
runnable script.

---

## 1. Version drift: the checkout is NOT the runtime

This is the single most important fact in this document.

| | Version | Evidence |
|---|---|---|
| Installed SDK (runs) | **1.20.1** | `relationalai-1.20.1.dist-info`; `relationalai.__version__` == `1.20.1` |
| `CO/` checkout (docs) | **1.2.2** | `CO/pyproject.toml` `version = '1.2.2'` |
| Checkout last commit | **2026-05-08** | `git -C CO log -1 --format=%ci` |

1.2.2 < 1.20.1. The checkout is roughly four months behind the runtime. CLAUDE.md calls the
checkout "ground truth"; for 1.20.1 that is no longer safe. Prefer `SDK/` for signatures and
use `CO/` only for runnable examples and prose.

**Confirmed drift, not hypothetical.** The path library was renamed between the two:

```
SDK/semantics/std/paths/__init__.py    # 1.20.1: a deprecation shim, 15 lines
SDK/semantics/std/path/                # 1.20.1: the real module
CO/src/relationalai/semantics/std/paths/  # 1.2.2: the real module (api.py, algorithms/, README.md)
```

`SDK/semantics/std/paths/__init__.py:6-10`:

```python
warnings.warn(
    "relationalai.semantics.std.paths is deprecated; use relationalai.semantics.std.path instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

I ran that import. It emits exactly that warning. **[SRC + executed]** — this one I did verify,
because importing needs no engine.

Consequence: CLAUDE.md's instruction to use `relationalai.semantics.std.paths` and to copy
`supply_chain_demo/.claude/skills/rai-pathfinder/SKILL.md` will produce deprecated-import
warnings. Use `relationalai.semantics.std.path`. Also note that
`SC/.claude/skills/rai-pathfinder/` exists as a directory but I did not confirm a `SKILL.md`
inside it; check before relying on the copy step.

Other directory-level drift: `SDK/semantics/util/` exists, `CO/.../semantics/util/` does not.

---

## 2. Config: `_build_config()` that works locally and in Snowsight

The working version, quoted verbatim from `SC/rai_code/manual/supply_chain.py:27-46`. **[TEST]**
(it is a shipped reference demo, not a PyRel test). The APIs it calls are **[SRC]**-verified
present in 1.20.1 — I imported them and read the attributes back.

```python
_LOGIC_NAME, _LOGIC_SIZE = "supply_chain_logic_l", "HIGHMEM_X64_L"
_PRESC_NAME, _PRESC_SIZE = "supply_chain_prescriptive_m", "HIGHMEM_X64_M"


def _build_config():
    """Auto-discover config (active Snowpark session inside Snowflake, or the
    snow CLI's connections.toml locally), then pin reasoners to the biggest
    named engines."""
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore
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

The dual-path trick is the `get_active_session()` probe: inside a Snowsight notebook it
succeeds and you take `ConfigFromActiveSession`; locally it raises and you fall through to
`create_config()`, which discovers `~/.snowflake/connections.toml`.

Verified present in 1.20.1 by import **[SRC]**:

- `relationalai.config.ConfigFromActiveSession` → `relationalai.config.config.ConfigFromActiveSession`
- `relationalai.config.create_config` → function
- `cfg.reasoners.logic.name` / `.size` are real settable attributes.

Reading back a default `create_config()` gives:

```
connection=None name=None size='HIGHMEM_X64_S' query_timeout_mins=None settings=None
use_lqp=True incremental_maintenance='off' emit_constraints=False readonly_queries=False
lqp=ReasonerLogicLqpConfig(semantics_version=None, compiler='legacy')
```

For this demo, drop the prescriptive lines — there is no LP/MIP in the eight golden questions —
and set only `cfg.reasoners.logic.*` to `aviation_temporal_logic_s` / `HIGHMEM_X64_S`.

### Data-layer config knobs worth knowing [SRC]

`cfg.data` reads back as:

```
wait_for_stream_sync=True ensure_change_tracking=False data_freshness_mins=None
query_timeout_mins=None download_url_type=None check_column_types=True
```

`ensure_change_tracking` (`SDK/config/config_fields.py:172`, default `False`) is the switch that
makes the SDK enable change tracking for you instead of erroring. See section 4.

---

## 3. Named logic reasoner: create and size

### CLI [SRC — read from `--help` on the installed `rai`]

```bash
.venv/bin/rai reasoners create --type Logic --name aviation_temporal_logic_s \
    --size HIGHMEM_X64_S --auto-suspend-mins 5 --wait --timeout-s 900
```

`create` flags: `--type`, `--name`, `--size`, `--auto-suspend-mins`,
`--await-storage-vacuum/--no-await-storage-vacuum`, `--wait/--no-wait`, `--timeout-s`.

Other subcommands: `alter`, `delete`, `get`, `list`, `sizes`, `suspend`, `resume`, `wait`.

### Two CLAUDE.md instructions that are wrong for 1.20.1

**(a) `rai reasoners alter` has no `--size` flag.** Its complete option set is `--name`,
`--type`, `--auto-suspend-mins`. CLAUDE.md says to resize with
`.venv/bin/rai reasoners alter <name> --size HIGHMEM_X64_S`. That fails twice over: there is no
`--size`, and `--name` is an option rather than a positional, so the bare `<name>` is also
wrong. Auto-suspend is the only thing `alter` changes:

```bash
.venv/bin/rai reasoners alter --type Logic --name aviation_temporal_logic_s --auto-suspend-mins 5
```

To actually resize, set `cfg.reasoners.logic.size` in `_build_config()` (the reference-demo
pattern), or `delete` and `create` at the new size.

**(b) `HIGHMEM_X64_XS` does not exist.** `rai reasoners sizes` is a pure local/config lookup
(its help says so: "does not open a Snowflake session"), so this output cost nothing:

| Reasoner type | Allowed sizes |
|---|---|
| Logic | `HIGHMEM_X64_S`, `HIGHMEM_X64_M`, `HIGHMEM_X64_L` (AWS), `HIGHMEM_X64_SL` (Azure) |
| Prescriptive | `HIGHMEM_X64_S`, `HIGHMEM_X64_M` |
| Predictive | `HIGHMEM_X64_S`, `HIGHMEM_X64_M`, `HIGHMEM_X64_L`, `GPU_NV_S`, `GPU_NV_SM` |

The smallest Logic size is `S`. CLAUDE.md's "both engines default to `HIGHMEM_X64_XS` while the
agent is iterating" is unachievable. `BRIEF.md` already records this under Locked names
("XS is not offered for Logic in SDK 1.20.1"), so the demo is already on `aviation_temporal_logic_s`
— this note just adds the `alter --size` half, which is new.

The account is on AWS (`RAI_SALES_ENGINEERING_AWS_US_WEST_2` per `BRIEF.md`), so `L` is the
large option and `SL` is irrelevant.

---

## 4. Binding a Snowflake table with `model.Table()`

### Signature [SRC] `SDK/semantics/frontend/base.py:6650`

```python
def Table(self, path: str, schema: dict[str, Concept] = {}, type: Iceberg | Native | None = None) -> Table:
```

- `path` — fully qualified name as a plain string, e.g. `"PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_VERSION"`.
  There is no separate database/schema argument; the FQN goes in the one string.
- `schema` — optional `{column_name: Concept}` map. Omit it and columns are discovered from
  Snowflake metadata. Supply it when you want types checked or the table does not exist yet
  (export targets).
- `type` — `Iceberg()` / `Native()`. Not needed here.

Docstring examples (same location) cover both directions:

```python
source = m.Table("DB.SCHEMA.CUSTOMERS", schema={"id": Integer, "name": String})
m.define(Customer.new(source.to_schema()))

out = m.Table("DB.SCHEMA.PERSONS_EXPORT")
m.select(Person.id, Person.name).into(out).exec()
```

### The `Sources` class idiom [TEST] `SC/rai_code/manual/supply_chain.py:283-302`

```python
DB = "PK_AVIATION_TEMPORAL.SOURCE"


class Sources:
    aircraft          = model.Table(f"{DB}.AIRCRAFT")
    aircraft_version  = model.Table(f"{DB}.AIRCRAFT_VERSION")
    schedule_version  = model.Table(f"{DB}.SCHEDULE_VERSION")
```

Keeping the DB as a module constant is what makes the same file work against a renamed database
without edits.

### How columns become properties

Three access forms, all **[SRC]**:

1. **Attribute access by physical column name** — `Sources.aircraft_version.VALID_FROM`. This is
   what the reference demo uses throughout (`SC/rai_code/manual/supply_chain.py:307-312`).
   Unquoted Snowflake identifiers are folded to upper case, so write the attribute in upper
   case unless the DDL quoted it.
2. **Index by name or position** — `t["name"]`, `t[0]`. `SDK/semantics/frontend/base.py:2405,2434`
   (`Table.__getitem__`): a bad name raises `KeyError` listing the valid column names, and a bad
   index raises `IndexError` with the column count. Both fail loudly, which makes them safe to
   probe with.
3. **Splat all columns** — `model.select(*t)`. `Table.__iter__` at `SDK/.../base.py:2390`.

**`to_schema()`** `SDK/semantics/frontend/base.py:2630`:

```python
def to_schema(self, *, exclude: list[str] = []) -> TableSchema:
```

`exclude` is keyword-only and matched case-insensitively — the constructor lowercases it
(`SDK/.../base.py:2705`) and `get_columns` compares `col._short_name.lower()`
(`SDK/.../base.py:2718`). `to_schema()` auto-maps columns onto identically named properties;
use it when names line up, and fall back to explicit `.new(...)` + per-property calls when they
do not.

Explicit form, with an FK resolved through `filter_by`
(`SC/rai_code/manual/supply_chain.py:344-358`):

```python
model.define(
    loc := Location.new(location_id=Sources.locations.LOCATION_ID),
    loc.name(Sources.locations.NAME),
    loc.region(Region.filter_by(region_code=Sources.locations.REGION)),
)
```

And a boolean unary flag set from a column
(`SC/rai_code/manual/supply_chain.py:337-340`):

```python
model.where(
    Week.filter_by(yearweek=Sources.calendar.YEARWEEK),
    Sources.calendar.IS_HOLIDAY_WEEK == True,  # noqa: E712
).define(Week.is_holiday())
```

Note `== True` rather than a bare truth test — a bare `if` on a PyRel expression raises (see §5).

### Change tracking

RAI reads Snowflake tables through streams, so every source table needs
`CHANGE_TRACKING = TRUE`. This is **not** a `model.Table()` argument — it is Snowflake DDL.

Two routes:

1. **DDL in the loader**, the reference-demo way
   (`/Users/piotrkraus/rai-repos/rai-demos/bmw_demo/data/build_cars_demo_data.py:1274-1287`):
   ```sql
   ALTER TABLE <table> SET CHANGE_TRACKING = TRUE;
   ```
2. **Let the SDK do it** — set `cfg.data.ensure_change_tracking = True` in `_build_config()`
   (`SDK/config/config_fields.py:172`, default `False`). Requires the demo role to hold ALTER on
   the tables, which `RAI_DEMO_AVIATION_TEMPORAL` does inside its own DB.

If it is missing, the error is self-remediating: `v0/relationalai/errors.py:1698` builds the
exact `ALTER <TYPE> <FQN> SET CHANGE_TRACKING = TRUE;` statement into the message. Paste and run.

Related knob: `cfg.data.wait_for_stream_sync` defaults `True`, which is what you want — queries
block until the stream has caught up rather than silently reading stale data.

---

## 5. Half-open interval filtering: `valid_from <= d < valid_to`

**Two separate predicates. Never a Python chained comparison.**

```python
import datetime as dt

AS_OF = dt.date(2024, 6, 30)

model.where(
    AircraftVersion.valid_from <= AS_OF,
    AircraftVersion.valid_to   >  AS_OF,
).select(...)
```

Multiple arguments to `where()` are conjunction, so this is exactly `valid_from <= d AND d < valid_to`.

### Why chained comparison is a trap [SRC]

`AircraftVersion.valid_from <= AS_OF < AircraftVersion.valid_to` is Python-chained, which
desugars to `(a <= x) and (x < b)`, and `and` calls `__bool__` on the expression.
`SDK/semantics/frontend/base.py:1166-1173`:

```python
def __bool__(self) -> NoReturn:
    cur_source = self._source.block.source or ""
    invalid = next((bool_check for bool_check in ["if ", "while ", " and ", " or "] if bool_check in cur_source), "bool check").strip()
    mapped = {"and": "`&` or `,`", "or": "`|`", "if": "`where`"}
    if m := mapped.get(invalid):
        exc("Invalid operator", f"Cannot use python's `{invalid}` in model expressions. Use {m} instead.", [source(self)])
```

Good news: this fails **loudly** at build time with a message naming the fix. It cannot silently
produce a wrong answer. Same for `and` / `or` / `if` anywhere in a predicate — use `&`, `|`,
`,`, and `model.not_()`.

### Date literals are plain `datetime.date` [TEST]

No wrapper, no parameter-binding ceremony. Straight from the PyRel test suite:

- `CO/tests/end2end/unified/tests/dates.py:22`
  `select(Thing.name).where(Thing.when <= dt.date(2024, 1, 2)).to_df()`
- `CO/tests/end2end/tpch/tests/q08.py:88-89`
  `o.o_orderdate >= dt.date(1995, 1, 1), o.o_orderdate <= dt.date(1996, 12, 31)`
- `CO/tests/end2end/inactive/tables/simple_column_filters.py:31`
  `snapshot_event_source.AS_OF_DATE >= date(2023, 1, 9)` — literal compared against a **table
  column**, which is the aviation case.

So "passing a Python date as a query parameter" is just closing over a Python variable. The
parameterised-function form (§13) is how you expose it to callers.

### The open-interval sentinel

`BRIEF.md` fixes model open intervals at `9999-01-01`, kept distinct from the source's
`9999-12-31` "unknown future". Since the sentinel is a real comparable date, `valid_to > AS_OF`
handles open rows with no special case and no NULL logic. Keep it that way; do not introduce a
nullable `valid_to`, because a missing property in PyRel silently fails to match rather than
raising (this is called out in `rai-rules-authoring` under Handling Missing Data), which would
drop open rows from every as-of query without an error.

---

## 6. As-of resolution of several INDEPENDENTLY versioned dimensions (Q01)

The core pattern, and the one worth getting right first.

**The key insight: you do not align the intervals. You never compute an interval intersection.**
Each dimension is filtered independently against the same scalar date, and they meet on the
entity. Misaligned boundaries are irrelevant because no dimension ever looks at another
dimension's boundaries.

### Case A — dimensions live in separate version tables/concepts

```python
import datetime as dt

AS_OF = dt.date(2024, 6, 30)

model.where(
    # anchor
    TypeVersion.aircraft(Aircraft),
    TypeVersion.valid_from <= AS_OF,
    TypeVersion.valid_to    > AS_OF,

    EngineVersion.aircraft(Aircraft),
    EngineVersion.valid_from <= AS_OF,
    EngineVersion.valid_to    > AS_OF,

    StatusVersion.aircraft(Aircraft),
    StatusVersion.valid_from <= AS_OF,
    StatusVersion.valid_to    > AS_OF,
).select(
    Aircraft.tail.alias("tail"),
    TypeVersion.aircraft_type.alias("aircraft_type"),
    EngineVersion.engine.alias("engine"),
    StatusVersion.status.alias("status"),
).to_df()
```

Each block is an independent half-open filter; `Aircraft` is the single shared free variable
that joins them. Per `rai-pyrel-coding` (Free-Variable Scoping), one `model.where(...)` chain is
one scope, so the bare `Aircraft` symbol is the *same* variable in all three applications — that
is what makes this a join rather than a cross product.

**Alias every column.** `rai-querying` Silent Corruption #1: when two concepts in a `select()`
share a property name, `to_df()` silently appends `_2`. With four versioned dimensions this is a
live risk.

### Case B — one tall version table keyed by attribute [UNVERIFIED]

If the aviation schema puts all attributes in one `AIRCRAFT_VERSION` table with an
`ATTRIBUTE` / `VALUE` shape, the same concept appears three times and each occurrence needs its
own `.ref()`:

```python
tv, ev, sv = AircraftVersion.ref(), AircraftVersion.ref(), AircraftVersion.ref()

model.where(
    tv.aircraft(Aircraft), tv.attribute == "TYPE",
    tv.valid_from <= AS_OF, tv.valid_to > AS_OF,

    ev.aircraft(Aircraft), ev.attribute == "ENGINE",
    ev.valid_from <= AS_OF, ev.valid_to > AS_OF,

    sv.aircraft(Aircraft), sv.attribute == "STATUS",
    sv.valid_from <= AS_OF, sv.valid_to > AS_OF,
).select(
    Aircraft.tail.alias("tail"),
    tv.value.alias("aircraft_type"),
    ev.value.alias("engine"),
    sv.value.alias("status"),
).to_df()
```

`.ref()` for repeated concepts is documented in `rai-querying` (Multi-Concept Joins) and shown
at `SC` scale, so the mechanism is solid; what is **[UNVERIFIED]** is that three independent
refs of the same concept, each with its own interval filter, join cleanly on one shared
`Aircraft` without inflation.

**Smoke test.** Run Case B, then run three separate one-dimension queries, and check the row
count matches the aircraft count in all four:

```python
n_ac = model.select(aggs.count(Aircraft).alias("n")).to_df()["n"].astype(int).iloc[0]
assert len(df) == n_ac, f"as-of join inflated: {len(df)} rows for {n_ac} aircraft"
```

If it inflates, the cause is `rai-querying` Silent Corruption #4 (multi-relationship cartesian
through a shared concept), and the fix is one query per dimension merged in pandas on `tail`.

Also worth asserting: exactly one row per aircraft per dimension. If a version table has
overlapping intervals for one aircraft — a real data bug that half-open intervals are supposed
to prevent — this query silently returns two rows for that aircraft rather than erroring.

Note also the string literals `"TYPE"` / `"ENGINE"`. `rai-querying` Silent Corruption #6: an
`==` against a string that came from a question, not from the data, returns zero rows with no
error. Run `model.select(distinct(AircraftVersion.attribute)).to_df()` once and use the exact
spellings.

---

## 7. A series across many dates without writing the query N times (Q03)

Q03 is ten years of month-end fleet composition, 120+ dates. The customer explicitly rejects an
approach that only works because the interval is regular, so the shape must be
"cross-join the entity set against a set of dates", not "loop in Python" and not "exploit
monthly spacing".

### The shape

```python
model.where(
    MonthEnd.date(d),                       # d ranges over the date set
    AircraftVersion.valid_from <= d,
    AircraftVersion.valid_to    >  d,
    AircraftVersion.aircraft(Aircraft),
    AircraftVersion.status == "In Service",
).select(
    distinct(
        d.alias("as_of"),
        AircraftVersion.aircraft_type.alias("aircraft_type"),
        aggs.count(Aircraft).per(d, AircraftVersion.aircraft_type).alias("n"),
    )
).to_df()
```

The interval predicates now compare against a *variable* `d` instead of a literal, and the same
half-open logic evaluates once per date. Nothing about the query knows or cares that the dates
are month-ends, or that they are evenly spaced — feed it an arbitrary set of dates and it still
works. That is the property the customer is testing for.

`distinct()` is **required** here: the grouping keys are property values (a date and a string),
not entities. `rai-querying` Silent Corruption #2 — without it you get one row per aircraft with
the count repeated, not one row per group.

### Where the dates come from — three options, in order of preference

**Option 1 (recommended): a Snowflake calendar table.** `BRIEF.md` gives the demo a
`MODEL_INPUT` schema; a `MONTH_END` table of 120 rows is trivial to generate in the Phase 2
loader, is inspectable in SQL, is trivially explainable on stage ("here are the dates, nothing
up my sleeve"), and sidesteps every semantic question below. Bind it like any other table (§4)
and make it a `MonthEnd` concept. **This is the option I would ship.**

**Option 2: `std.datetime.date.range()`.** [SRC] `SDK/semantics/std/datetime.py:409`

```python
@classmethod
def range(cls, start: DateValue | None = None, end: DateValue | None = None,
          periods: IntegerValue = 1, freq: Frequency = "D") -> Variable:
```

`freq` is one of `"D"`, `"W"`, `"M"`, `"Y"` (plus `"ms"`, `"s"`, `"m"`, `"H"` for datetimes);
`end` is inclusive; the return is a `Variable` you can bind in a `where()`. [TEST]
`CO/tests/end2end/unified/tests/date_ranges.py:11-14,23-34`:

```python
select(std.datetime.date.range(dt.date(2024, 1, 1), dt.date(2024, 1, 7))).to_df()
select(std.datetime.date.range(dt.date(2024, 1, 30), periods=3, freq="M")).to_df()
select(std.datetime.date.range(dt.date(2020, 1, 1), Foo.date, freq="M"))   # line 28: DSL-variable end
```

**The month-end trap.** `freq="M"` is implemented as `start + months(i)`
(`SDK/semantics/std/datetime.py:478`, `_periods["M"] = months` at
`SDK/semantics/std/datetime.py:1430`). That is "same day-of-month, i months later" — **not**
month-end. Starting a range at `2016-01-31` and stepping by month asks the engine what
`2016-01-31 + 1 month` is, and the answer for February is implementation-defined. **[UNVERIFIED]**
and genuinely risky.

Safe month-end recipe: build first-of-month (day 1 exists in every month, so the arithmetic is
unambiguous), then subtract a day from the following month.

```python
from relationalai.semantics.std.datetime import date, months, days

first_of_month = date.range(dt.date(2016, 1, 1), dt.date(2025, 12, 1), freq="M")
month_end = date.subtract(date.add(first_of_month, months(1)), days(1))
```

`date.add` / `date.subtract` at `SDK/semantics/std/datetime.py:362,390`; `months` / `days` at
`:1321,:1280`. Composition is **[UNVERIFIED]**.

Second `date.range` caveat, straight from the source comment at
`SDK/semantics/std/datetime.py:462-468`: with a **literal** `end` the implementation
over-approximates the period count and returns `select(_date).where(Date(end) >= _date)` — a
Fragment. With a **DSL-variable** `end` it uses `date.diff` and returns a bare expression,
because "Avoiding the select().where() Fragment means the outer select's find_keys can see
grounding variables like Foo directly." That is an explicit warning that the literal-`end`
Fragment form may not expose grounding variables to an enclosing query — exactly what a
cross-join against `Aircraft` needs. Another reason Option 1 wins.

**Option 3: `std.common.range()` + arithmetic.** [SRC] `SDK/semantics/std/common.py:26`.
`range(stop)` / `range(start, stop)` / `range(start, stop, step)`, start inclusive, stop
exclusive. Gives an integer index you can map to dates yourself. Most control, most rope.

**Smoke test for Option 2, before building Q03 on it:**

```python
df = model.select(std.datetime.date.range(dt.date(2016, 1, 31), periods=4, freq="M")).to_df()
print(df)   # is row 2 2016-02-29, 2016-03-02, or an error?
```

If that does not print clean month-ends, take Option 1 and move on. Do not spend the afternoon.

---

## 8. Ordering, ranking, and first/last of day

All **[SRC]** from `SDK/semantics/std/aggregates.py`, with docstring examples quoted from the
same file.

```python
from relationalai.semantics.std.aggregates import rank, rank_asc, rank_desc, asc, desc, top, bottom, limit
```

| Function | Line | Purpose |
|---|---|---|
| `rank(*args)` | `:372` | Dense ordering; takes `asc()`/`desc()` wrappers |
| `rank_asc` / `rank_desc` | `:430` / `:454` | Shorthand, no wrapper needed |
| `asc(*args)` / `desc(*args)` | `:322` / `:345` | Return an `Ordering` |
| `top(n, *args)` / `bottom(n, *args)` | `:478` / `:507` | N highest / lowest |
| `limit(n, *args)` | `:400` | N rows under an explicit ordering |

### Ranking within a group

The docstring example at `SDK/semantics/std/aggregates.py:393`:

```python
select(Product, aggregates.rank(aggregates.asc(Product.price)).per(Category).where(Product.category == Category))
```

So `rank(...).per(K).where(...)` is the sanctioned form. `.per()` and `.where()` on an
`Aggregate` are real methods (`SDK/semantics/frontend/base.py:5228`, `:5191`).

### Composite (date, sequence, id) ordering [SRC]

`BRIEF.md` requires ordering aircraft events by date **and** sequence, never date alone. `rank`
accepts several ordering args and flattens them in order — `Ordering.get_ordering_args` /
`Ordering.handle_arg` at `SDK/semantics/std/aggregates.py:298-319` walk the args and append one
direction flag per value, so each arg keeps its own direction:

```python
rank(asc(Event.event_date), asc(Event.event_seq), asc(Event.event_id)).per(Aircraft)
```

Mixed directions work the same way: `rank(desc(Event.event_date), asc(Event.event_id))`.

Because `handle_arg` recurses into an `Ordering`'s values, `asc(a, b)` applies ascending to both
— so `rank(asc(Event.event_date, Event.event_seq))` is equivalent to the two-wrapper form above.

### First / last event of a day

```python
# rank within (aircraft, day), then keep rank 1
model.where(
    r := rank(asc(Event.event_seq), asc(Event.event_id)).per(Aircraft, Event.event_date),
    r == 1,
).select(
    Aircraft.tail.alias("tail"),
    Event.event_date.alias("day"),
    Event.event_id.alias("first_event"),
).to_df()
```

Binding the aggregate with `:=` in `where()` and then filtering on it is the HAVING idiom from
`rai-querying` (Recipe Card). Last-of-day is the same with `desc(...)`.

Alternative using `top`, per its `:499` docstring example
(`select(Product).where(aggregates.top(3, Product.revenue).per(Store).where(Product.store == Store))`):

```python
model.where(top(1, Event.event_seq).per(Aircraft, Event.event_date)).select(...)
```

`top`/`bottom` take bare values, not `asc`/`desc` wrappers — direction is fixed by which
function you call (`top` = descending, `bottom` = ascending;
`SDK/semantics/std/aggregates.py:504,531`).

**[UNVERIFIED]:** whether `rank` ties are dense or produce duplicate 1s on identical composite
keys. With `(date, seq, id)` and a unique `id` there should be no ties, which is precisely why
`BRIEF.md` insists on the composite key. Smoke test: rank one aircraft's events and assert
`df["rank"].is_unique`.

**Row order out of `to_df()` is not guaranteed** — see §13. Rank inside the query; sort in pandas
for presentation.

---

## 9. Previous/next version and A -> B -> A spells (Q02)

`BRIEF.md` requires preserving A -> B -> A as three assignments, so the model must not collapse
consecutive equal states. Detection is then a three-version window over one aircraft.

### Adjacency join: the half-open interval does the work

With contiguous half-open intervals, "the next version" is not an argmax — it is an equality
join, because one version's `valid_to` **is** the next one's `valid_from`:

```python
cur, nxt = StatusVersion.ref(), StatusVersion.ref()

model.where(
    cur.aircraft(Aircraft),
    nxt.aircraft(Aircraft),
    nxt.valid_from == cur.valid_to,      # adjacency
).select(...)
```

This is cheap and exact. It assumes the version history is gapless per aircraft — which
half-open contiguous intervals are supposed to guarantee. **Verify that assumption on the real
data before relying on it** (§17 has the check); if there are gaps, fall back to the argmax form
below.

### Full A -> B -> A spell

```python
from relationalai.semantics.std.datetime import date as rdate

a1, b, a2 = StatusVersion.ref(), StatusVersion.ref(), StatusVersion.ref()

model.where(
    a1.aircraft(Aircraft),
    b.aircraft(Aircraft),
    a2.aircraft(Aircraft),

    b.valid_from  == a1.valid_to,        # a1 -> b
    a2.valid_from == b.valid_to,         # b  -> a2

    a1.status == "In Service",
    b.status  == "Storage",
    a2.status == "In Service",
).select(
    Aircraft.tail.alias("tail"),
    b.valid_from.alias("spell_start"),
    b.valid_to.alias("spell_end"),
    rdate.diff("day", b.valid_from, b.valid_to).alias("spell_days"),
).to_df()
```

`date.diff(part, start, end)` at `SDK/semantics/std/datetime.py:507`; `part` is one of
`"year"`, `"quarter"`, `"month"`, `"week"`, `"day"`. Docstring example at `:527`:
`datetime.date.diff("day", Order.start_date, Order.end_date)`.
`date.period_days(start, end)` at `:487` is the day-only equivalent.

**[UNVERIFIED]** as a whole — three refs of one concept joined pairwise on date equality is a
shape I could not find in a test. The mechanisms (multiple `.ref()`, equality joins on
properties, `date.diff`) are each **[SRC]**/**[TEST]**; the composition is not.

**Smoke test.** Pick one tail known to have a storage spell from `EXPECTED_ANSWERS.yaml`, run
the query filtered to it, and check the spell dates and duration against the frozen expected
value. That validates adjacency, ref independence, and `date.diff` in one shot.

### Fallback if the history has gaps

Replace the adjacency equality with an argmax over earlier versions:

```python
nxt_from := aggs.min(later.valid_from).per(cur).where(
    later.aircraft(Aircraft), cur.aircraft(Aircraft), later.valid_from >= cur.valid_to,
),
nxt.valid_from == nxt_from,
```

**[UNVERIFIED]**, and more fragile — `rai-pyrel-coding` warns that mixing a bare concept with
`.ref()` in one scope cross-products unless an equality binds them. Prefer adjacency.

### Do not let A -> B -> A collapse

If the loader ever "compresses" adjacent equal-status rows, Q02 returns nothing and the demo's
headline claim dies. The generator is the place to guarantee this, not the query. Assert it:

```python
# every aircraft with a storage spell must show >= 3 status versions
```

---

## 10. Self-reference chains, and `std.path` in 1.20.1 (Q08)

Q08 reconstructs an aircraft's rotation: legs in a chain, each leg's arrival feeding the next
leg's departure, enriched with as-of type and engine.

### The ordinary self-reference formulation — use this

Quoted from `CO/src/relationalai/semantics/std/paths/README.md:26-36`, the paths library's own
"you don't need this library for fixed-length paths" section:

```python
Person = m.Concept("Person", identify_by={"name": String})
Person.follows = m.Relationship(f"{Person:a} follows {Person:b}")

# 2-hop path
x, y, z = Person.ref(), Person.ref(), Person.ref()
m.where(x.name == "Alice", x.follows(y), y.follows(z)).select(x.name, y.name, z.name)

# 3-hop, endpoints only
m.where(Person.name == "Alice").select(Person.name, Person.follows.follows.follows.name)
```

Applied to rotation, where the chain link is "next leg by the same aircraft":

```python
leg, nxt = FlightLeg.ref(), FlightLeg.ref()

model.where(
    leg.aircraft(Aircraft),
    nxt.aircraft(Aircraft),
    nxt.departure_airport == leg.arrival_airport,
    nxt.departure_time    >= leg.arrival_time,
    r := rank(asc(leg.departure_time)).per(Aircraft),
).select(
    Aircraft.tail.alias("tail"),
    r.alias("leg_no"),
    leg.flight_number.alias("flight"),
    leg.departure_airport.alias("from"),
    leg.arrival_airport.alias("to"),
).to_df()
```

Then enrich each leg with as-of type/engine by adding the §6 interval predicates against
`leg.departure_date`. That is the whole of Q08, and it needs no path library: the rotation is
an ordered sequence you rank, not a variable-length reachability question.

**Recommendation: build Q08 with `rank` + self-ref, not `std.path`.** Reasons: the chain is
totally ordered by time, you want per-leg enrichment (which the path library's node/edge
indexing makes awkward), and `std.path` is explicitly pre-GA.

### `std.path`: does it exist in 1.20.1, and what would it add

**Yes, and it is importable.** I verified this by import (no engine needed):

```python
from relationalai.semantics.std.path import path, PathTraversal, undirected, reverse   # OK
```

Module: `SDK/semantics/std/path/` (`__init__.py`, `api.py`, `translate.py`, `algorithms/`, `rpq/`).
`relationalai.semantics.std.paths` still imports but warns (§1).

There is also a model method — `SDK/semantics/frontend/base.py:7313`:

```python
def path(self, *args: PathSegment) -> PathPattern:
```

so `model.path(...)` and the free `path(...)` (`SDK/semantics/std/path/api.py:69`) both work;
the free function resolves the active model via `_check_model()` and therefore breaks with
multiple models. **Prefer `model.path(...)`.**

**API surface** [SRC] `SDK/semantics/std/path/api.py`:

| Member | Line | Status in 1.20.1 |
|---|---|---|
| `path(*segments)` → `PathPattern` | `:69` | works |
| `PathPattern.where(*filters)` | `:118` | works |
| `PathPattern.repeat(min_or_exact, max, *, min)` | `:122` | works |
| `PathPattern.all_paths()` → `DerivedColumn` | `:141` | works |
| `PathPattern.shortest_paths()` | `:186` | **raises `NotImplementedError`** |
| `undirected(expr)` | `:215` | **raises `NotImplementedError`** |
| `reverse(expr)` | `:219` | **raises `NotImplementedError`** |

The three unimplemented ones go through `throw_if_not_implemented`
(`SDK/semantics/std/path/api.py:23`), gated by `ALLOW_UNIMPLEMENTED = False` at `:21`. I called
`undirected(None)` and `reverse(None)` and got:

```
NotImplementedError: undirected(Concept.relationship) is not implemented yet.
NotImplementedError: reverse(Concept.relationship) is not implemented yet.
```

So: **only `all_paths()` is usable.** No shortest paths, no undirected traversal, no reverse
edges. If a question needs "shortest rotation" or "treat legs as undirected", the library will
not do it in 1.20.1.

`repeat` conventions (`:129-137`): `repeat(3)` = exactly 3; `repeat(1, 20)` = 1..20;
`repeat(min=1, max=20)` = same; `repeat(max=20)` and `repeat(min=1)` both raise `ValueError` —
an explicit pair is required.

Subtle semantic difference worth knowing (`:101-103`):

- `path(C.r.repeat(N))` — only the **source** must be of type `C`.
- `path(C.r).repeat(N)` — **every intermediate node** must be of type `C`.

**Result shape** `SDK/semantics/std/path/api.py:224-232`:

```python
PathTraversal.length              # Integer: hop count
PathTraversal.nodes               # (index) -> entity
PathTraversal.relationships       # (index) -> String relationship name
PathTraversal.relationship_fields # (edge index, field index) -> value
```

Usage, from `CO/src/relationalai/semantics/std/paths/README.md:47-53` [TEST, 1.2.2-era]:

```python
df = m.where(
    p := m.path(Person, Person.follows.repeat(1, 3)).where(Person.name == "Alice").all_paths(),
).select(
    p, p.length, p.nodes["index"], Person(p.nodes).name.alias("node")
).to_df()
```

Output is one row per (path, node index) — a path of length 2 yields 3 rows. Re-assembling that
into "leg 1, leg 2, leg 3 with type and engine" is more work than the `rank` version, which
reinforces the recommendation.

**What it would add if used:** variable-length rotation chains (`repeat(1, 10)` for "up to ten
legs") without writing ten self-joins, and full enumeration of each traversal's nodes and edges.
Only worth it if a question genuinely needs unbounded chain length.

**Big caveat** `SDK/semantics/std/path/api.py:175-183`: `all_paths()` registers a compile hook
that **raises** if an enclosing `where`/`select`/`define` touches a binding that appears inside
the `PathPattern` or its attached `.where()`. Those bindings do not unify across the boundary.
This directly blocks the Q08 enrichment pattern — you cannot reach into a path from the outer
query to attach as-of type/engine to each leg. **[UNVERIFIED]** in detail but the intent of the
code is unambiguous, and it is the strongest argument for the `rank` approach.

Header on the 1.2.2 README, still accurate given the pre-GA gating:
"This library is under active development and is currently intended for RAI-internal use only."
(`CO/src/relationalai/semantics/std/paths/README.md:3-4`)

---

## 11. Aggregation, grouping, and conditional aggregation

```python
from relationalai.semantics import distinct
from relationalai.semantics.std import aggregates as aggs
```

Available [SRC] `SDK/semantics/std/aggregates.py`: `sum` `:30`, `count` `:59`, `min` `:88`,
`max` `:117`, `avg` `:147`, `stddev_samp` `:177`, `product` `:207`, `string_join` `:244`,
`cumsum_asc` `:536`.

### Group by entity vs group by property value

The rule that causes the most wrong numbers (`rai-querying` Silent Corruption #2):

- group by **entity** — `.per(Aircraft)` — `distinct()` usually unnecessary
- group by **property value** — `.per(AircraftVersion.aircraft_type)` — **`distinct()` required**
- group by a **mix** — treat as property value, use `distinct()`

```python
model.select(distinct(
    AircraftVersion.aircraft_type.alias("aircraft_type"),
    aggs.count(Aircraft).per(AircraftVersion.aircraft_type).alias("n"),
)).to_df()
```

### Multiple grouping keys

```python
aggs.sum(ScheduleVersion.seats).per(Route, ScheduleVersion.cabin).alias("seats")
```

### Distinct count [TEST]

`count(distinct(...))`, from `CO/tests/end2end/unified/tests/aggregate.py:59`:

```python
select(count(distinct(Person.name)).alias("set-count")).to_df()  # Chris, Chris, Joe = 2
```

Multi-column distinct count, `CO/tests/end2end/unified/tests/unary_relationships.py:21`:

```python
m.select(count(distinct(Transaction.send_year, Transaction.is_send_staged))).to_df()
```

Confirmed in the `Aggregate` docstring at `SDK/semantics/frontend/base.py:5115-5117`:
"To aggregate over unique values, wrap arguments with `Model.distinct`."

### Conditional aggregation — seats split by cabin

`.where()` on the aggregate restricts which bindings contribute
(`SDK/semantics/frontend/base.py:5191`):

```python
model.select(distinct(
    Route.code.alias("route"),
    aggs.sum(ScheduleVersion.seats).per(Route).where(ScheduleVersion.cabin == "J").alias("business_seats"),
    aggs.sum(ScheduleVersion.seats).per(Route).where(ScheduleVersion.cabin == "Y").alias("economy_seats"),
    aggs.sum(ScheduleVersion.seats).per(Route).alias("total_seats"),
)).to_df()
```

This is the "split by cabin without three queries" idiom. Two traps:

1. **Empty groups return no row, not zero.** A route with no business cabin drops out entirely
   rather than showing 0. Coalesce: `... .alias("business_seats") | 0`. `rai-rules-authoring`
   flags the sparse-property version of this as a silent-wrong-answer source.
2. **String literals must match the data.** Run `model.select(distinct(ScheduleVersion.cabin)).to_df()`
   first; `"J"` vs `"BUSINESS"` vs `"Business"` returns zero rows with no error.

### Standalone `per()` [TEST]

`per()` at `SDK/semantics/std/aggregates.py:913`. Bind it and call the aggregate on it —
`CO/tests/end2end/unified/tests/correlated_exists_negation.py:44,48`:

```python
g := per(s.name),
...
g.count(li).alias("numwait"),
```

### Integer aggregates come back as `Int128Array`

`aggs.count()` is Integer, and pandas reductions on the result raise
`TypeError: 'Int128Array' with dtype Int128 does not support reduction 'sum'`. Cast on arrival:

```python
df["n"] = df["n"].astype(int)
```

### Two more inflation traps

- **`.per(FK_property)` while selecting the bare concept** cross-products
  (`rai-querying` Silent Corruption #5). Given `where(Version.aircraft(Aircraft))`, write
  `.per(Aircraft)`, never `.per(Version.aircraft)`. `distinct()` does **not** fix this one.
- **Two relationships through one shared concept in a single aggregating select** multiplies
  counts (Silent Corruption #4). Split into separate queries.

---

## 12. Set difference / anti-join: present at one date, absent at another (Q05/Q06)

Q05 classifies schedule additions/removals/modifications; Q06 compares market entries and exits
between the latest snapshot and seven days earlier. Both are "in A, not in B".

### The correlated NOT EXISTS pattern [TEST]

This is the one to copy. `CO/tests/end2end/unified/tests/correlated_exists_negation.py:29-50`,
quoted in full because the shape matters:

```python
s, li, o = Supplier, LineItem, Order
where(
    li.supplier == s,
    li.order == o,
    o.status == "closed",
    li.late == True,  # noqa: E712
    li2 := LineItem.ref(),
    li2.order == o,
    li2.supplier != s,
    not_(where(
        li3 := LineItem.ref(),
        li3.order == o,
        li3.supplier != s,
        li3.late == True,  # noqa: E712
    )),
    g := per(s.name),
).select(
    distinct(
        s.name,
        g.count(li).alias("numwait"),
    )
).to_df()
```

`not_(where(ref := Concept.ref(), <correlation predicates>))` is a correlated NOT EXISTS: the
inner `where` is a subquery, the inner ref is fresh, and it correlates to the outer query
through the shared `o`.

### Applied to Q06 — markets present at T, absent at T-7

```python
import datetime as dt
from relationalai.semantics import distinct

T     = dt.date(2026, 9, 1)
T_M7  = dt.date(2026, 8, 25)

# entries: live at T, not live at T-7
model.where(
    cur := ScheduleVersion.ref(),
    cur.market(Market),
    cur.valid_from <= T,
    cur.valid_to    > T,
    model.not_(model.where(
        prev := ScheduleVersion.ref(),
        prev.market(Market),
        prev.valid_from <= T_M7,
        prev.valid_to    > T_M7,
    )),
).select(distinct(Market.code.alias("market"))).to_df()
```

Exits are the same with `T` and `T_M7` swapped. **[UNVERIFIED]** as written — the mechanism is
[TEST]-backed but this exact correlation (through `Market` rather than an explicit shared
variable) is not.

**Smoke test.** Entries and exits must partition against the two one-sided counts:

```python
n_T    = <distinct markets live at T>
n_T7   = <distinct markets live at T-7>
assert n_T - len(entries) == n_T7 - len(exits)   # both sides equal the intersection
```

If it fails, the correlation is not binding — the `not_()` is testing "no such row anywhere"
rather than "no such row for this market". That is the classic failure of this pattern.

### Simpler `not_()` forms [TEST]

`CO/tests/end2end/unified/tests/containers_with_negation.py:13-27` — "entities with no related
row at all", all four placements equivalent:

```python
select(count(Person.name)).where(not_(Person.brother)).to_df()          # 2
select(count(Person.name)).where(Person, not_(Person.brother)).to_df()  # 2
select(count(Person.name).where(not_(Person.brother))).to_df()          # 2
```

And the ref-bound form from `rai-querying`, needed when you want to *select* the negated entity:

```python
model.where(sched := Schedule.ref(), model.not_(sched.version)).select(sched.id.alias("orphan"))
```

### `not_()` semantics — one call or two

From `rai-querying`:

```python
model.not_(A, B)              # NOT (A AND B)
model.not_(A), model.not_(B)  # (NOT A) AND (NOT B)
```

Different meanings. For "live at T-7" the predicates belong inside **one** `not_(where(...))`,
because you want "there is no row that is both this market and live at T-7", not "no row for
this market" AND "no row live at T-7".

Never use `~` — `TypeError: bad operand type for unary ~`. Always `model.not_()`.

### Modifications (Q05's third bucket)

Not an anti-join: it is a join on the key plus an inequality on the payload.

```python
model.where(
    cur.schedule_key == prev.schedule_key,
    cur.valid_from <= T,     cur.valid_to    > T,
    prev.valid_from <= T_M7, prev.valid_to    > T_M7,
    cur.departure_time != prev.departure_time,
).select(...)
```

`BRIEF.md` is explicit that key-changing amendments are reported as **candidate matches with
confidence/evidence, never silently asserted**. Keep that out of the anti-join: additions and
removals are exact set operations; fuzzy matching is a separate, clearly-labelled query.

---

## 13. Getting results out

### `to_df()` [SRC] `SDK/semantics/frontend/base.py:3465`

```python
def to_df(self) -> DataFrame
```

Terminal call on a Fragment. Returns pandas.

**Column names.** Controlled solely by `.alias()`. Without it, two same-named properties collide
and the second silently becomes `name_2` (`rai-querying` Silent Corruption #1). **Alias every
column in every multi-concept query** — which is all eight aviation questions.

**Column order** follows `select()` argument order. **[UNVERIFIED]** but consistent with every
example I read; cheap to confirm and cheap to defend against — reindex explicitly before
comparing against `EXPECTED_ANSWERS.yaml`:

```python
df = df[["tail", "aircraft_type", "engine", "status"]]
```

**Row order is NOT guaranteed.** Nothing in the API promises one, and the engine is a relational
reasoner. Rank inside the query when order is semantic; sort in pandas for presentation:

```python
df = df.sort_values(["tail", "as_of"]).reset_index(drop=True)
```

For a frozen-expected-answers comparison, sort both sides on a stable key first, or compare as
sets. Do not let a passing test depend on incidental row order.

### Parameters from Python

Two levels. Closing over a Python variable (§5) is the mechanism; wrapping the query in a
function is how you expose it. From `rai-querying`'s joins-and-export reference:

```python
def fleet_as_of(model, as_of: dt.date) -> rai.Fragment:
    return model.where(
        AircraftVersion.valid_from <= as_of,
        AircraftVersion.valid_to    > as_of,
    ).select(
        Aircraft.tail.alias("tail"),
        AircraftVersion.aircraft_type.alias("aircraft_type"),
    )

df = fleet_as_of(model, dt.date(2024, 6, 30)).to_df()
```

Returning the Fragment rather than the DataFrame keeps it composable and testable — and
`EXPECTED_ANSWERS.yaml` has 24 parameterized result sets across 8 questions, so parameterized
functions are the natural unit. One function per question, date(s) as arguments.

### Export to a Snowflake table [SRC]

`Fragment.into(table, update=False)` at `SDK/semantics/frontend/base.py:5929`; `.exec()` at
`:5961`.

```python
out = model.Table("PK_AVIATION_TEMPORAL.VALIDATION.Q01_RESULTS")
model.select(
    Aircraft.tail.alias("TAIL"),
    AircraftVersion.aircraft_type.alias("AIRCRAFT_TYPE"),
).into(out).exec()
```

`update=False` (default) replaces the table; `update=True` merges. `.exec()` is idempotent —
repeat calls are no-ops. Useful for landing results in the `VALIDATION` schema for SQL-side
checking against the frozen answers.

---

## 14. Derived properties: what belongs in the model

The boundary, per `rai-querying`'s own description: **`rai-querying` cannot create derived
properties**. If several questions need the same computed value, it must be authored as a
`model.Property()` / `model.Relationship()` with `rai-rules-authoring` first.

### Declaring one

```python
# 1. declare the output
AircraftVersion.duration_days = model.Property(
    f"{AircraftVersion} has {Integer:duration_days}"
)

# 2. define it
model.define(
    AircraftVersion.duration_days(
        rdate.diff("day", AircraftVersion.valid_from, AircraftVersion.valid_to)
    )
)
```

Boolean flags are **unary Relationships**, not Properties:

```python
AircraftVersion.is_open = model.Relationship(f"{AircraftVersion} is open")
model.where(AircraftVersion.valid_to == dt.date(9999, 1, 1)).define(AircraftVersion.is_open())
```

Unary relationships are **filter-only** — using one as a `select()` column raises `TyperError`.
To surface a flag in a DataFrame, query the flagged ids separately and merge (the pattern is
spelled out in `rai-rules-authoring`).

### Where to draw the line for this demo

Put in the **model** anything shared across questions or that is a semantic commitment:

- the half-open validity predicate as a reusable relationship, if more than two questions need it
- `is_open` / open-interval sentinel handling
- version duration
- in-service classification (Q02, Q03, Q07 all need "In Service")

Keep in the **query module** anything question-specific: the as-of date, ranking, the
Q05 addition/removal split, presentation aliases.

### Two rules that bite

- **The model is append-only.** There is no API to remove or replace a `define()`, `Property()`,
  `Concept()`, or `Relationship()`. A "corrected" rule does not supersede the original — both
  stay active. To change one, rebuild the model. This matters in notebooks: re-running a cell
  that declares a property adds a second one.
- **Never compute a rule's output in pandas.** `rai-rules-authoring` is explicit. A derived
  classification computed with `.apply()` on a merged DataFrame is the same mistake as
  computing it in SQL — it is invisible to the ontology and to the Cortex agent, which is the
  whole point of the demo.

### Naming

Avoid reserved attribute names on Concept — `ref`, `new`, `select`, `where`, `define`,
`filter_by`, `identify_by` — which raise `[Reserved relationship name]` at declaration.
`ref` is a realistic collision in aviation data. Rename the Concept-side attribute; the source
column need not change.

Do **not** pass `short_name=` to `model.Property()`. PyRel derives it from the LHS attribute
name, and a mismatch fails immediately. Worse, invoking a property under an alternate name
creates a parallel implicit Property that reads NaN everywhere.

---

## 15. Checking the model compiled clean

### Turn typos into errors

Set `implicit_properties: false` (flagged in `rai-pyrel-coding` Debugging). With implicit
properties on, a typo'd property name silently creates a new empty property and every read is
NaN. **[UNVERIFIED]** exactly where this lives in the 1.20.1 config tree — `cfg.data` does not
carry it. Find it with:

```python
from relationalai.config import create_config
c = create_config()
print(c.model_dump())          # search the dump for 'implicit'
```

### Surface warnings that the spinner eats

`rai-pyrel-coding` notes that error detail "can be swallowed by spinner — set `TERM=dumb` to see
full output." Run every smoke test as:

```bash
TERM=dumb .venv/bin/python rai_code/manual/demo_queries.py
```

Deprecation warnings (notably `std.paths`) are Python warnings, so make them visible:

```bash
TERM=dumb .venv/bin/python -W error::DeprecationWarning rai_code/manual/demo_queries.py
```

That turns any surviving deprecated import into a hard failure — a good Phase 4 gate.

### Introspect before authoring

`inspect` is present in 1.20.1. I imported it and read its exports:

```
Any, Chain, ConceptInfo, CoreConcepts, EnumInfo, Expression, Field, FieldInfo, FieldRef,
Fragment, Iterator, Model, ModelSchema, New, Property, Reading, Relationship,
RelationshipInfo, RuleInfo, TableInfo, TypeVar, Variable, annotations, dataclass,
dataclasses, fields, overload, schema, to_concept
```

```python
from relationalai.semantics import inspect
schema = inspect.schema(model)
print(schema["AircraftVersion"].properties)
inspect.fields(AircraftVersion.some_multiarg_relationship)
```

Both `rai-querying` and `rai-rules-authoring` insist on running this before writing queries
against a model you did not just author — it catches hallucinated property names, duplicates,
and wrong-type inference. After a `/compact`, re-run it rather than trusting recall.

### Other diagnostics

- `print(expr)` renders the AST **without executing** — `print(aggs.sum(X.v).per(Y))` →
  `(sum X.v (per Y))`. Cheapest possible check that `.per()` has the right key.
- `Concept.relationship.inspect()` executes and prints the result DataFrame.
- `/rai-health` for engine state, `/rai-setup` for connection state.

---

## 16. Gotcha index

| # | Gotcha | Where it bites | Label |
|---|---|---|---|
| 1 | `std.paths` deprecated → use `std.path` | every path import; CLAUDE.md says the old one | [SRC, executed] |
| 2 | `undirected()`, `reverse()`, `shortest_paths()` raise `NotImplementedError` | Q08 if you reach for the path library | [SRC, executed] |
| 3 | `rai reasoners alter` has **no** `--size`; `--name` is an option not a positional | CLAUDE.md's resize instruction | [SRC, `--help`] |
| 4 | `HIGHMEM_X64_XS` does not exist; smallest Logic size is `S` | CLAUDE.md's "start at XS"; already noted in BRIEF.md | [SRC, `rai reasoners sizes`] |
| 5 | Checkout is 1.2.2 / 4 months stale; not ground truth for 1.20.1 | any signature taken from `CO/` | [SRC] |
| 6 | `a <= x < b` chained comparison raises `[Invalid operator]` | every interval filter | [SRC] |
| 7 | `date.range(freq="M")` is `start + months(i)`, **not** month-end | Q03 | [SRC] |
| 8 | `date.range` with a **literal** `end` returns a Fragment that may hide grounding vars | Q03 cross-join | [SRC comment] |
| 9 | Property-value grouping without `distinct()` returns N rows, not one per group | Q03, Q05, Q07 | skill |
| 10 | Missing `.alias()` silently yields `name_2` columns | every multi-concept select | skill |
| 11 | Empty aggregation groups return **no row**, not zero | Q07 cabin split | skill |
| 12 | `.per(FK_property)` cross-products; use `.per(BareConcept)` | any grouped as-of query | skill |
| 13 | Integer aggregates return `Int128Array`; pandas reductions raise | every count | skill |
| 14 | `==` against an unverified string literal returns 0 rows, no error | status/cabin/attribute filters | skill |
| 15 | Unary boolean Relationships cannot appear in `select()` (`TyperError`) | any flag you want to display | skill |
| 16 | The model is append-only; re-running a declaration cell duplicates it | Phase 5/6 notebooks | skill |
| 17 | Missing properties silently fail to match rather than raising | nullable `valid_to` would drop open rows | skill |
| 18 | `~` for negation raises `TypeError`; use `model.not_()` | Q05/Q06 | skill |
| 19 | `not_(A, B)` is `NOT(A AND B)`; `not_(A), not_(B)` is `(NOT A) AND (NOT B)` | Q06 correlation | skill |
| 20 | Reserved attribute names (`ref`, `new`, `select`, …) raise at declaration | `ref` is plausible in aviation data | skill |
| 21 | Row order out of `to_df()` is not guaranteed | comparing to EXPECTED_ANSWERS.yaml | [UNVERIFIED] |
| 22 | `all_paths()` compile hook rejects outer-query unification with path interior | Q08 enrichment via path library | [SRC] |
| 23 | Change tracking is Snowflake DDL, not a `Table()` arg | Phase 2 loader | [SRC] |
| 24 | No offline execution path in 1.20.1 (DuckDB is gated pre-release) | you cannot test without the account | [SRC, attempted] |

Items marked "skill" come from the three loaded skills (`rai-querying` Silent Corruptions,
`rai-pyrel-coding` Common Pitfalls, `rai-rules-authoring` Common Pitfalls) rather than from
source I read directly. They are well-attested but not 1.20.1-line-cited.

---

## 17. The smoke-test script

Everything above that is [UNVERIFIED], in dependency order, in one file. The orchestrator has a
live account; I do not. Run this before the three query agents start, and the cookbook stops
being provisional.

```python
"""build/design/smoke.py - settle every [UNVERIFIED] entry in PYREL_QUERY_NOTES.md.
Run: TERM=dumb .venv/bin/python -W error::DeprecationWarning build/design/smoke.py
"""
import datetime as dt
import pandas as pd
from relationalai.semantics import distinct, inspect
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import datetime as rdt
from relationalai.semantics.std.aggregates import rank, asc

from rai_code.manual.aviation_temporal import model, Aircraft, AircraftVersion  # adjust

def check(label, fn):
    try:
        print(f"\n=== {label} ===")
        print(fn())
    except Exception as e:
        print(f"FAIL {label}: {type(e).__name__}: {e}")

# -- 0. model surface (do this first; everything else assumes the names)
check("inspect.schema", lambda: inspect.schema(model)["AircraftVersion"].properties)

# -- 1. gotcha 7: does freq="M" from a month-end give month-ends?
check("date.range month-end", lambda: model.select(
    rdt.date.range(dt.date(2016, 1, 31), periods=4, freq="M")).to_df())

# -- 2. safe month-end recipe (first-of-month + 1 month - 1 day)
def month_end_recipe():
    fom = rdt.date.range(dt.date(2016, 1, 1), dt.date(2016, 4, 1), freq="M")
    return model.select(
        rdt.date.subtract(rdt.date.add(fom, rdt.months(1)), rdt.days(1))).to_df()
check("month-end recipe", month_end_recipe)

# -- 3. gotcha 8: does a date.range cross-join against an entity ground correctly?
def cross_join():
    d = rdt.date.range(dt.date(2024, 1, 31), periods=3, freq="M")
    return model.where(
        AircraftVersion.valid_from <= d,
        AircraftVersion.valid_to    > d,
        AircraftVersion.aircraft(Aircraft),
    ).select(distinct(d.alias("as_of"), aggs.count(Aircraft).per(d).alias("n"))).to_df()
check("entity x date cross-join", cross_join)

# -- 4. discover real string values before any == filter (gotcha 14)
check("distinct status", lambda: model.select(distinct(AircraftVersion.status)).to_df())

# -- 5. Q01 multi-dimension as-of: must not inflate
def as_of_no_inflation():
    AS_OF = dt.date(2024, 6, 30)
    df = model.where(
        AircraftVersion.aircraft(Aircraft),
        AircraftVersion.valid_from <= AS_OF,
        AircraftVersion.valid_to    > AS_OF,
    ).select(
        Aircraft.tail.alias("tail"),
        AircraftVersion.aircraft_type.alias("aircraft_type"),
    ).to_df()
    assert df["tail"].is_unique, f"INFLATED: {len(df)} rows, {df['tail'].nunique()} tails"
    return f"{len(df)} rows, unique tails OK"
check("as-of no inflation", as_of_no_inflation)

# -- 6. is the version history gapless? (decides adjacency join vs argmax, section 9)
def gapless():
    cur, nxt = AircraftVersion.ref(), AircraftVersion.ref()
    joined = model.where(
        cur.aircraft(Aircraft), nxt.aircraft(Aircraft),
        nxt.valid_from == cur.valid_to,
    ).select(aggs.count(cur).alias("n")).to_df()["n"].astype(int).iloc[0]
    total = model.select(aggs.count(AircraftVersion).alias("n")).to_df()["n"].astype(int).iloc[0]
    tails = model.select(aggs.count(Aircraft).alias("n")).to_df()["n"].astype(int).iloc[0]
    # every version except each aircraft's last should have a successor
    print(f"versions={total} tails={tails} adjacency_pairs={joined} expected={total - tails}")
    return "GAPLESS" if joined == total - tails else "HAS GAPS -> use argmax form"
check("gapless history", gapless)

# -- 7. composite rank has no ties (section 8)
def rank_unique():
    df = model.where(AircraftVersion.aircraft(Aircraft)).select(
        Aircraft.tail.alias("tail"),
        rank(asc(AircraftVersion.valid_from)).per(Aircraft).alias("rk"),
    ).to_df()
    dup = df.duplicated(["tail", "rk"]).sum()
    return f"tie rows: {dup} (expect 0)"
check("rank ties", rank_unique)

# -- 8. correlated anti-join partitions correctly (section 12)
#    fill in with the real Market/ScheduleVersion concepts, then assert:
#    n_T - len(entries) == n_T7 - len(exits)

# -- 9. column order out of to_df matches select order (gotcha 21)
def col_order():
    df = model.select(
        Aircraft.tail.alias("c1"),
        AircraftVersion.status.alias("c2"),
    ).where(AircraftVersion.aircraft(Aircraft)).to_df()
    return list(df.columns)   # expect ['c1', 'c2']
check("column order", col_order)

# -- 10. integer aggregate dtype (gotcha 13)
check("agg dtype", lambda: model.select(
    aggs.count(Aircraft).alias("n")).to_df().dtypes.to_dict())
```

Results worth writing back into `BRIEF.md` under Design decisions, per CLAUDE.md's
"document any failure you fix so the next session inherits the gotcha":

- gapless or not (decides §9's adjacency vs argmax)
- month-end approach chosen (§7 Option 1 vs 2)
- whether the date cross-join grounds (decides whether Q03 needs a calendar table)

---

## Quick reference: imports

```python
import datetime as dt

from relationalai.semantics import (
    Model, Concept, Property, Relationship,
    Integer, Float, String, Date, DateTime, Boolean, Number,
    distinct, inspect,
)
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.aggregates import rank, rank_asc, rank_desc, asc, desc, top, bottom, limit, per
from relationalai.semantics.std import datetime as rdt          # rdt.date, rdt.datetime, rdt.days, rdt.months
from relationalai.semantics.std import strings, math, numbers, floats
from relationalai.semantics.std.path import path, PathTraversal  # NOT std.paths
from relationalai.config import create_config, ConfigFromActiveSession
```

Use `model.where()` / `model.select()` / `model.define()` / `model.not_()` / `model.union()`
rather than the standalone functions — the standalone forms raise
`"Multiple Models have been defined."` when more than one Model exists in the process, which is
exactly what happens once the notebook imports both the ontology and a test module.

`Number` must always be `Number.size(p, s)` — bare `Number` causes type-inference failures.
For Snowflake `NUMBER` columns, `Number.size(38, 4)`.
