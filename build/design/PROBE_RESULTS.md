# PROBE_RESULTS - live resolution of ONTOLOGY_DESIGN section 8 (U-01..U-12) and section 4.3 (G-01..G-06)

Owner: PROBE-01. Consumer: the orchestrator, MODEL-01, DATA-04, QUERY-UC1/UC2/ROT.

Every verdict below is backed by live execution against `PK_AVIATION_TEMPORAL` under role
`RAI_DEMO_AVIATION_TEMPORAL`, on the real logic reasoner `aviation_temporal_logic_s`
(`HIGHMEM_X64_S`), with `relationalai 1.20.1`. Nothing here is inferred from source reading alone;
where source reading is quoted it is corroboration for a live result, never a substitute.

Probe scripts and raw logs live under `build/probes/`:

| Artifact | Contents |
|---|---|
| `build/probes/g_fd_probes.sql` | G-01..G-06 plus detail and grain queries |
| `build/probes/probe_a_tables.py` / `out_probe_a.log` | U-12 cold start, U-01, U-02, U-03 first pass |
| `build/probes/probe_b.py` / `out_probe_b1.log`, `out_probe_b2.log`, `out_probe_b3.log` | U-04..U-10 |
| `build/probes/probe_c_time.py` / `out_probe_c.log` | U-03 definitive |
| `build/probes/probe_d_absence.py` / `out_probe_d.log`, `out_probe_d2.log` | U-09 follow-up |
| `build/probes/probe_e_nulls.py` / `out_probe_e.log` | N-01, discovered while running U-09 |

## Substitutions the probe had to make

`PK_AVIATION_TEMPORAL.MODEL_INPUT` was **empty** when the probe run began (zero tables in
`INFORMATION_SCHEMA.TABLES`), because DATA-04 was still building it. Every probe that the brief wrote
against a `MODEL_INPUT` table was therefore rebound to the `SOURCE` table with the same relevant
column shape. **DATA-04 finished during the run and every substituted probe was re-run against the
real tables with no change in verdict** - see the addendum at the end of this file.

| Brief's binding | Probe's substitute | Why it is equivalent |
|---|---|---|
| `MODEL_INPUT.AIRCRAFT_ELIGIBLE` (U-01, U-02) | `SOURCE.AIRCRAFT_MASTER` | Same `AIRCRAFT_ID NUMBER(38,0)` identity column, 999 rows |
| `MODEL_INPUT.PASSENGER_SOURCE_LINEAGE` (G-05) | `SOURCE.PASSENGER_HISTORICAL` with the DV-20 canonical key reconstructed inline from PH-05/PH-07/PH-10/PH-11/PH-04 per `SOURCE_CONTRACT.md:454` | PH is the only side of the union carrying PH-02 `schedule_key`; PF has none |
| `MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT` (U-08) | `SOURCE.AIRCRAFT_HISTORY` joined to a deliberately restricted `Aircraft` extension | The live fixture has **zero** orphan history rows, so the negative case was manufactured by restricting the parent to `aircraft_id <= 1500`; the code path is identical |

Nothing was written to `MODEL_INPUT`. Nothing outside `SOURCE` was read. No model named
`aviation_temporal` was created; every probe model is `probe_*`.

---

## Verdict table

| Probe | Verdict | One line |
|---|---|---|
| **U-01** strict-mode attribute access on `Table` | **REFUTED** | Attribute access works with no `schema=`, and a *typo* also works, silently, returning an `Any`-typed column |
| **U-02** `NUMBER(38,0)` -> `Integer` | **CONFIRMED** | Discovers as `Integer`, binds cleanly, arithmetic works. But a wrong declared type is a silent NaN column, not a `TyperError` |
| **U-03** Snowflake `TIME` | **CONFIRMED that `TIME` is broken; REFUTED on the fix** | `TIME` yields 100% NULL as `DateTime`; declaring the raw column `String` recovers full fidelity. **DATA-04 needs no change** |
| **U-04** `require(unique(...))` | **CONFIRMED, and worse than feared** | A violated `require(unique(...))` is a silent no-op **both with and without** `emit_constraints: True` |
| **U-05** `date.range(freq="M")` | **CONFIRMED, brief's caution unnecessary** | Exactly 120 real month ends 2015-01-31..2024-12-31, leap day included, no clamping |
| **U-06** `.alt()` on a `Property` | **CONFIRMED** | Works; three concurrent open states on one route return three rows and raise nothing |
| **U-07** recursion at 1.20.1 | **CONFIRMED** | The 1.2.2 idiom compiles and terminates on a deliberately cyclic edge set; no step bound needed |
| **U-08** compound identity with Concept components | **CONFIRMED** | Loads from Snowflake tables; an unresolvable parent yields no assignment and no error; re-define is stable |
| **U-09** absent-value semantics in `select` | **PARTIALLY REFUTED** | `\| None` raises outright and section 5.3's `\|` chain does not compile (`Unground Variable`); the plain dot-chain **does** preserve the row and renders absence as `NaN` |
| **U-10** four-key `rank` + `.per()` | **CONFIRMED** | Works, materialises as a `Property`, `seq + 1` spell pairing incl. the zero-day same-day spell is exact |
| **U-11** = G-01..G-06 | **G-03 and G-04 REFUTED** (they were expected to fail; they pass) | All six FD probes pass against live `SOURCE` |
| **U-12** cold CDC / change tracking | **CONFIRMED and quantified** | 631s cold, 2.8s warm; no change-tracking exception |
| **G-01** AircraftType defs on AC-05 | PASS | 0 violating keys |
| **G-02** EngineType defs on AC-14 | PASS | 0 violating keys; AC-08/AC-09 also happen to be functional here, but stay off `EngineType` anyway |
| **G-03** Airport attrs on AP-01 | **PASS (brief expected FAIL)** | 45 airport_ids, 45 rows, exactly one effective period each |
| **G-04** Airline attrs on AL-01 | **PASS (brief expected FAIL)** | 100 airline_ids, 100 rows, exactly one effective period each |
| **G-05** PassengerFlight.schedule_key on DV-20 | PASS, but vacuously | 0 violating keys; the one coalescing DV-20 key carries `NULL` PH-02 on both rows |
| **G-06** AircraftFlight.aircraft on AF-01 | PASS | 0 violating flight_ids; inverse is 1..13 flights per aircraft; 1 dangling `NEXT_FLIGHT_ID` |
| **N-01** *(new, not in the brief)* | **NEW RISK** | `model.data(df)` drops every row with a null **or empty string** in **any** column of the frame |
| **N-02** *(new, not in the brief)* | **NEW TRAP** | The free `distinct(...)` raises `[Ambiguous model]` when more than one `Model` exists in the process |

---

## U-01. Strict mode does not gate attribute access on a `model.Table()` - REFUTED

The brief's reading of `SD/frontend/base.py:1439/1508/2472/2537` predicted that
`Table.aircraft_id` would raise `RAIException "Implicit property"` under
`implicit_properties=False`, making binding-policy R1 mandatory. It does not.

Code run (`build/probes/probe_a_tables.py:89-118`):

```python
CFG = create_config(model={"implicit_properties": False},
                    reasoners={"logic": {"name": "aviation_temporal_logic_s"}})
m01 = Model("probe_u01", config=CFG)
t01 = m01.Table("PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER")   # NO schema=
t01.aircraft_id
t01["AIRCRAFT_ID"]
t01.no_such_column
```

Raw output:

```
--- U-01a  t01.aircraft_id  (attribute access, strict) ---
OK: PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER.aircraft_id

--- U-01b  t01['AIRCRAFT_ID']  (item access, triggers lazy fetch) ---
OK: PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER.AIRCRAFT_ID

--- U-01c  t01.aircraft_id AGAIN, after the lazy fetch was triggered ---
OK: PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER.AIRCRAFT_ID

--- U-01d  t01['aircraft_id']  (lowercase item access) ---
OK: PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER.AIRCRAFT_ID

--- U-01e  select through item access ---
OK: '  aircraft_id\n0        1000\n1        1001\n2        1002'

--- U-01f  t01.no_such_column  (typo under strict mode) ---
OK: PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER.no_such_column
```

Under `implicit_properties=True` the behaviour is identical (U-01g, U-01h both OK). So the strict
flag makes **no difference at all** to `Table` attribute access.

Worse, the typo persists into the model surface. `inspect.schema(m01)` afterwards contains:

```
FieldInfo(name='no_such_column', type_name='Any')
```

alongside the nineteen real columns. A misspelled column becomes an `Any`-typed relation that will
silently produce an empty or NaN result later.

**Design consequence.** R1 in section 1.1 stops being a correctness requirement and becomes a
*discipline* requirement, but a strong one, and the reason changes:

- R1 is **still mandatory**, because it is now the *only* defence against a column typo. Strict mode
  does not provide one for tables. Write the explicit `schema=` dict for every `model.Table()` and
  never touch a column that is not in it.
- R1 is **also mandatory for U-03**: the `schema=` dict is the mechanism that turns the eight `TIME`
  columns from all-NULL into usable strings. Lazy discovery cannot do that.
- Add an `inventory.py` assertion that no `FieldInfo.type_name == "Any"` appears anywhere in
  `inspect.schema(model).tables`. That single check catches every column typo in `sources.py` and
  costs nothing. This is a concrete addition to the MODEL-01 exit criterion.

---

## U-02. `NUMBER(38,0)` really is `Integer` - CONFIRMED

`inspect.schema(m01).tables` for `SOURCE.AIRCRAFT_MASTER`, live:

```
AIRCRAFT_ID                          Integer     <- NUMBER(38,0)
AIRCRAFT_SERIAL_NUMBER               String      <- TEXT
AIRCRAFT_ORDER_DATE                  Date        <- DATE
AIRCRAFT_WIDTH_M                     Float       <- FLOAT
OPERATING_MAXIMUM_TAKEOFF_WEIGHT_LB  Integer     <- NUMBER(38,0)
NOT_FOR_USE                          Bool        <- BOOLEAN
```

The full discovered map over `SOURCE.SCHEDULE_SNAPSHOT` and `SOURCE.PASSENGER_HISTORICAL`
(`out_probe_c.log` lines 5-72) gives the complete 1.20.1 mapping for this contract:

| Snowflake | Discovered RAI type |
|---|---|
| `NUMBER(38,0)` | `Integer` |
| `TEXT` / `VARCHAR` | `String` |
| `DATE` | `Date` |
| `FLOAT` | `Float` |
| `BOOLEAN` | `Bool` |
| `TIMESTAMP_NTZ` | `DateTime` |
| **`TIME`** | **`DateTime`** (and unusable - see U-03) |

Declaring `Integer` explicitly and loading through it works end to end:

```
--- U-02b  select Aircraft.id, Aircraft.serial_number ---
OK: id=1000 sn=SYN-SERIAL-1000 ...
--- U-02c  count of ProbeAircraft entities ---
OK: n = 999          (= the SOURCE row count)
--- U-02d  Integer arithmetic: where(Aircraft.id > 1000) ---
OK: 1001, 1002, 1004
```

**The important secondary finding.** A *wrong* declared type does not raise `TyperError`. It
produces a silently all-NaN column:

```
--- U-02e  WRONG type: declare NUMBER(38,0) column as String ---
OK: '   aircraft_id\n0          NaN\n1          NaN\n2          NaN'
```

and the same for `DATE`, `FLOAT` and `BOOLEAN` declared as `String` (U-03E1). The `rai-pyrel` skill
says a type mismatch "raises `TyperError` at query time that blocks all queries on the model". In
1.20.1 against a Snowflake `Table` that is **not** what happens; you get a NaN column and no error.

**Design consequence.** `sources.py` types must be checked against
`INFORMATION_SCHEMA.COLUMNS`, not eyeballed, and MODEL-01's exit gate must assert a non-null count
per bound column rather than only a row count. A wrong type in `sources.py` is invisible until an
`EXPECTED_ANSWERS.yaml` diff shows a null where a value belongs.

---

## U-03. Snowflake `TIME` - the definitive answer, and DATA-04 does NOT need to change

This is the item the brief flagged as a cross-task dependency. The answer is more clear-cut than the
brief expected, and it lands the other way.

### The eight affected columns

Exactly eight `TIME` columns exist in the live `SOURCE` schema and they are exactly the eight the
contract names. There are no others.

| Field ID | Table | Column |
|---|---|---|
| SS-23 | `SCHEDULE_SNAPSHOT` | `PASSENGER_DEPARTURE_UTC_TIME` |
| SS-24 | `SCHEDULE_SNAPSHOT` | `PASSENGER_ARRIVAL_UTC_TIME` |
| SS-25 | `SCHEDULE_SNAPSHOT` | `PASSENGER_DEPARTURE_LOCAL_TIME` |
| SS-26 | `SCHEDULE_SNAPSHOT` | `PASSENGER_ARRIVAL_LOCAL_TIME` |
| PH-12 | `PASSENGER_HISTORICAL` | `PASSENGER_DEPARTURE_LOCAL_TIME` |
| PH-13 | `PASSENGER_HISTORICAL` | `PASSENGER_ARRIVAL_LOCAL_TIME` |
| PH-14 | `PASSENGER_HISTORICAL` | `PASSENGER_DEPARTURE_UTC_TIME` |
| PH-15 | `PASSENGER_HISTORICAL` | `PASSENGER_ARRIVAL_UTC_TIME` |

`PASSENGER_FORWARD` PF-10..PF-13 are `TIMESTAMP_NTZ`, not `TIME`, and are unaffected.

### Snowflake ground truth, measured

```sql
SELECT COUNT(*), COUNT(passenger_departure_utc_time), COUNT(DISTINCT passenger_departure_utc_time),
       MIN(TO_VARCHAR(passenger_departure_utc_time)), MAX(TO_VARCHAR(passenger_departure_utc_time))
FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT;
-- 70000, 70000, 2, '16:00:00', '23:00:00'
```

All eight columns are **100% non-null**. `SCHEDULE_SNAPSHOT` = 70000 rows, `PASSENGER_HISTORICAL` =
10000 rows. Zero rows carry a non-zero sub-second fraction. Snowflake's `TO_VARCHAR` renders
`HH:MM:SS`.

### What RAI actually does

**(a) Discovered as `DateTime`, and every value comes back NULL.** Not "an invented date" as the
brief guessed - total, silent data loss.

```
--- U-03A1  select all four SS TIME columns as discovered ---
OK: n=70000  dtype=float64  non_null=0  null=70000  n_distinct=0
--- U-03A2  select all four PH TIME columns as discovered ---
OK: n=10000  non_null=0  null=10000
--- U-03A3  can a discovered TIME column be filtered at all? ---
OK: 0        (where(ss["PASSENGER_DEPARTURE_UTC_TIME"]) matches nothing)
```

**(b) Declaring `DateTime` explicitly does not help.** Same result, 70000/70000 NULL:

```
--- U-03B1  select the four SS TIME columns declared DateTime ---
OK: n=70000  dtype=float64  non_null=0  null=70000
```

**(c) Declaring the raw `TIME` column as `String` in the `schema=` dict recovers it completely.**

```python
ssC = mC.Table("PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT",
               schema={"schedule_key": String, "publish_date": Date,
                       "passenger_departure_utc_time": String,
                       "passenger_arrival_utc_time": String,
                       "passenger_departure_local_time": String,
                       "passenger_arrival_local_time": String})
```

```
--- U-03C1  SS: all four TIME columns declared String, full pull ---
n=70000  dtype=str  non_null=70000  null=0  n_distinct=2   ['16:00:00.000', '23:00:00.000']
n=70000  dtype=str  non_null=70000  null=0  n_distinct=2   ['01:00:00.000', '18:00:00.000']
n=70000  dtype=str  non_null=70000  null=0  n_distinct=2   ['09:00:00.000', '23:00:00.000']
n=70000  dtype=str  non_null=70000  null=0  n_distinct=2   ['01:00:00.000', '11:00:00.000']

--- U-03C2  PH: all four TIME columns declared String, full pull ---
n=10000  non_null=10000  n_distinct=5   ['01:30:00.000','03:30:00.000','09:00:00.000','12:00:00.000','23:30:00.000']
n=10000  non_null=10000  n_distinct=7
n=10000  non_null=10000  n_distinct=9
n=10000  non_null=10000  n_distinct=10
```

Row count, non-null count and distinct-value count all match the SQL ground truth exactly. The
values also round-trip onto a Concept `Property` and read back correctly (U-03D1).

**(d) The rendering is `HH:MM:SS.mmm`, not Snowflake's `HH:MM:SS`.** This is the one thing that
matters operationally:

```
--- U-03C4  where(t == "16:00:00.000") ---   OK: n = 69999
--- U-03C5  where(t == "16:00:00")     ---   OK: Empty DataFrame
```

A literal written in Snowflake's rendering silently matches nothing. This is Silent Corruption #6
from the `rai-pyrel` skill with a very sharp edge.

**(e) The `String` coercion is `TIME`-specific.** Declaring `NUMBER`, `DATE`, `FLOAT` or `BOOLEAN` as
`String` gives an all-NaN column (U-03E1). Do not generalise this trick.

### Verdict and the live branch

The brief said: *"My recommendation if it behaves as I expect: DATA-04 emits a canonical `VARCHAR`
ISO `HH:MM:SS` alongside the retained raw `TIME` column ... it does need a DATA-04 change so it
should be raised early."*

**That branch is NOT live. DATA-04 does not have to change.** The fix is entirely inside MODEL-01's
`sources.py`: declare the eight raw `TIME` columns as `String`. No new column, no new projection, no
change to any `MODEL_INPUT` table.

`SOURCE_CONTRACT.md:22` is satisfied as written: the raw `TIME` field is retained (it is the only
field there is), and the round-trip test compares the RAI-side string against
`TO_VARCHAR(<col>)` in SQL after normalising the millisecond suffix:

```sql
-- the round-trip assertion SOURCE_CONTRACT.md:22 demands
SELECT COUNT(*) FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT
WHERE TO_VARCHAR(passenger_departure_utc_time, 'HH24:MI:SS.FF3')
      <> <the value MODEL-01 read for the same row>;
```

**Optional, and worth doing anyway.** If DATA-04 has spare capacity, emitting a canonical
`VARCHAR(12)` `HH:MM:SS.mmm` column alongside each raw `TIME` would make the round-trip test a plain
byte equality and would insulate the demo from a change in how the SDK renders `TIME`. That is a
robustness nicety, not a requirement, and the orchestrator should only spend DATA-04 time on it if
DATA-04 is not on the critical path.

**Constraints MODEL-01 must honour either way.**

1. Every time-of-day literal in a query or in `EXPECTED_ANSWERS.yaml` comparison must be
   `HH:MM:SS.mmm`, or must be normalised before comparison.
2. `SS-23`/`SS-24` remain `UNRESOLVED_UTC_DATE` per `SOURCE_CONTRACT.md:325`; the string binding does
   not change that and must not be read as licence to build a timestamp.
3. DV-47..DV-50 (PH-04 plus PH-12/PH-13 plus offsets) are DATA-04's job and are unaffected: they are
   `TIMESTAMP`s, which discover as `DateTime` and work.

---

## U-04. `require(unique(...))` is a silent no-op, with or without `emit_constraints` - CONFIRMED

Fixture: a `Relationship` `Car.owned_by` with two owners for VIN `V1`, then a deliberately violated
`require(unique(Car.owned_by[Car]))`.

`emit_constraints = False`:

```
emit_constraints = False
--- U-04a[off]  baseline: Car.owned_by is 2-valued for V1 ---
OK:   V1 alice / V1 bob / V2 carol
--- U-04b[off]  m.require(unique(Car.owned_by[Car])) - VIOLATED ---
OK: (require (Field.unique_fields MetaRef()))
--- U-04c[off]  a query AFTER the violated require ---
OK:   V1 / V2
--- U-04d[off]  count(Car) after the violated require ---
OK: n = 2
```

`emit_constraints = True`:

```
emit_constraints = True
--- U-04b[on]  m.require(unique(Car.owned_by[Car])) - VIOLATED ---
OK: (require (Field.unique_fields MetaRef()))
--- U-04c[on]  a query AFTER the violated require ---
OK:   V1 / V2
--- U-04d[on]  count(Car) after the violated require ---
OK: n = 2
```

Identical. **Nothing was checked in either configuration.** The brief's fallback branch - "either
turn it on or downgrade them to documented zero-count test queries" - resolves to *downgrade them*,
because turning it on does not help.

Corroborating source, `relationalai/semantics/backends/legacy_lqp/rewrite/annotate_constraints.py`:

- lines 22-30: *"By default, all constraints are discharged"* - a discharged `Require` is
  *"removed from the IR in later passes"*.
- `_should_declare_constraint` (lines 78-94) additionally requires `fd is not None and not
  fd.is_structural`, so even with the flag on, a structural FD is never declared as a constraint.

### Side effects of `emit_constraints: True`

None observed on a valid model. `probe_u04_side` built the full multi-open route fixture with
`emit_constraints=True` and every query behaved identically to the `False` run, including the
three-concurrent-open-state `.alt()` select and a *satisfied*
`require(unique(RouteState.route[RouteState]))`.

### How a `Property` FD violation actually surfaces - a correction to section 3.3

The brief says the wrong `Route.current_state = model.Property(...)` *"raises it at define time,
before any query runs"*. It does not. `model.define(...)` returns normally; the error appears at the
**first query that evaluates the relation**, as a `RelQueryError`, after ~13-19 seconds of engine
work. Identical with `emit_constraints` on and off.

```
--- U-06g  WRONG: Property Route -> RouteState with 3 concurrent open states ---
--- Query warning ---
Found non-unique values: (0x005ebff95a2270fc958af4c89adb1180,) != (0x1be9aefab4c993c5fff8fc74586529cc,)
        FDError: The relationship violates functional dependency guarantees. The exception was
        thrown during the evaluation of route_current_state_UINT128_UINT128.
ABORTED (runtime error)  13s   |  Evaluated relations: 20 / 22 (6 cached)
RAISED RelQueryError: Query error
```

**Design consequences.**

1. `constraints.py` keeps the `require(unique(...))` calls **only as documentation**, with a comment
   saying in plain words that 1.20.1 does not enforce them. Do not let a reviewer believe they are
   live checks.
2. Every multiplicity gate that actually needs enforcing becomes a zero-count assertion query in the
   MODEL-01 test suite - the same shape as the `SentinelLeak` pattern the brief already uses in
   section 5.2. That pattern is the right one; extend it to the four route/schedule gates.
3. The section 3.3 demo beat still works and is still good, but the narration must say **"fails
   loudly at the first evaluation, with the offending hash pair and the relation name"**, not "at
   define time". Saying "define time" in front of the customer would be a factual error they can
   check on screen.
4. The error surfaces as `FDError ... during the evaluation of <relation_name>`, which names the
   offending relation. That is the genuinely good part of the beat and should be shown.

---

## U-05. `date.range(freq="M")` is exact - CONFIRMED, the calendar table is optional

```
--- U-05a  range(2015-01-31, 2024-12-31, freq='M') ---
n=120  first=2015-01-31  last=2024-12-31
all_month_end=True  n_month_end=120
2015-02-28 present=True  2016-02-29 present=True  2015-01-31 present=True
first 6=['2015-01-31','2015-02-28','2015-03-31','2015-04-30','2015-05-31','2015-06-30']
last 4=['2024-09-30','2024-10-31','2024-11-30','2024-12-31']
```

Exactly the 120 rows `DEMO_QUESTIONS.md:142` requires, every one a real month end, February 2015 and
the 2016 leap day both correct. **No clamping bug.** The anchor is honoured: starting from
`2015-01-01` gives firsts-of-month, not month ends (U-05b), so `freq="M"` steps by calendar month
preserving the anchor's day-position and clamping only where the month is short.

`freq="D"` over the same window gives 3653 rows, which is the correct day count for 2015-2024
inclusive of three leap days.

**Design consequence.** `calendar.py` can generate `MonthEnd` from `std.datetime.date.range` and
DATA-04 does not owe a `MODEL_INPUT.MONTH_END_CALENDAR` table. The brief's preference for a table
was hedged on a clamping risk that does not exist. Either is defensible; the cheaper one is now
proven correct. If DATA-04 has already built the table, keep it and use `date.range` as the notebook
cross-check exactly as the brief suggests - that is a nice demo beat and costs nothing.

---

## U-06. `.alt()` on a `Property` works, and multi-open is free - CONFIRMED

Fixture: route `SFO->LAS` with **three** concurrent open `RouteState`s (schedule keys SK-A, SK-B,
SK-C, all `knowledge_valid_to = 9999-01-01`) plus one closed prior state, and route `JFK->LAX` with
one.

```python
_state_route = m.Property(f"{RouteState:state} covers {Route:route}")
RouteState.route = _state_route
Route.states = _state_route.alt(f"{Route:route} has state {RouteState:state}")
```

`.alt()` on a `Property` returns a `Reading` and is accepted:

```
--- U-06a  _state_route.alt(...) on a Property ---
OK: {Route#1021:route} has state {RouteState#1035:state}
```

The critical select returns every state through the inverse reading, with no FD error:

```
--- U-06c  select(Route.route_id, Route.states.route_state_key) ---
      route            state
0  JFK->LAX  SK-D|2026-08-01
1  SFO->LAS  SK-A|2026-07-01
2  SFO->LAS  SK-A|2026-08-01
3  SFO->LAS  SK-B|2026-08-01
4  SFO->LAS  SK-C|2026-08-05
```

HT-18 holds by construction:

```
--- U-06d  open state count per route ---
      route open_states
0  JFK->LAX           1
1  SFO->LAS           3
```

`Schedule.states` (the second `.alt()`) behaves the same. A **satisfied**
`require(unique(RouteState.route[RouteState]))` is accepted and does not disturb later queries -
though per U-04 it is not actually checked.

**Design consequence.** Section 2 and section 3 of the brief stand unchanged. This is the demo's
centrepiece and it works exactly as designed. Note for the talk track: the multi-open result and the
`FDError` from the mirror-image mistake (U-06g) are two queries seconds apart in the same fixture,
which makes an unusually crisp before/after beat.

---

## U-07. Recursion at 1.20.1, including a cyclic edge set - CONFIRMED

The 1.2.2 `union` + `per(u, v).min(...)` idiom compiles and runs unchanged. Fixture: a path
`1->2->3->4` plus a deliberate 3-cycle `10->11->12->10`.

```python
u, v, n = Node.ref(), Node.ref(), Node.ref()
m.define(distance(u, v, aggs.per(u, v).min(m.union(
    m.select(0).where(u == v),
    m.select(distance(u, n) + 1).where(edge(n, v)),
))))
```

```
     u   v dist            (19 rows)
0    1   1    0
1    1   2    1
2    1   3    2
3    1   4    3
...
10  10  10    0
11  10  11    1
12  10  12    2
13  11  10    2
14  11  11    0
15  11  12    1
16  12  10    1
17  12  11    2
18  12  12    0
```

The cycle members produce a complete, correct, finite closure in 3.6s. The fixpoint terminates
without any visited set or step bound, because `min` over the `u == v` base case caps every
self-distance at 0 and the lattice is finite.

**Design consequence.** Section 2.12 is safe. `P0-11.5`'s "visited set and a finite step bound" has
no API surface in 1.20.1 and needs none: the semi-naive fixpoint terminates on cyclic input by
construction. Record the mechanism difference in `DECISION_LOG.md` as section 9 item 6 asks, but
downgrade it from a risk to a note - the `next_flight` acceptance rule that excludes cycles is a
*semantic* choice about what a rotation is, not a termination guard.

---

## U-08. Compound identity with Concept-valued components - CONFIRMED

```python
Assignment = m.Concept("Assignment", identify_by={
    "dimension": String, "aircraft": Aircraft, "event_date": Date,
    "row_sequence": Integer, "event": AircraftEvent})

m.where(am.aircraft_id <= 1500).define(Aircraft.new(id=am.aircraft_id))   # restricted parent
m.define(AircraftEvent.new(id=ah.aircraft_history_id))                    # all 48000
m.define(Assignment.new(
    dimension="aircraft_status",
    aircraft=Aircraft.lookup(id=ah.aircraft_id),
    event_date=ah.start_event_date,
    row_sequence=ah.row_sequence_number,
    event=AircraftEvent.lookup(id=ah.aircraft_history_id)))
```

```
--- U-08a  parent counts ---            n_aircraft = 500     n_events = 48000
--- U-08b  Assignment.new with TWO Concept-valued identity components ---
                                        n_assignments = 24048
--- U-08c  sample, read back through the Concept components ---
   aircraft_id  event_id  event_date  row_sequence  dimension
0         1000    101000  2025-05-01             1  aircraft_status
1         1000    101002  2025-05-02             2  aircraft_status
...
--- U-08d  max/min aircraft_id reachable through Assignment ---
                                        max = 1500   min = 1000
--- U-08e  HT-01: identical re-define does not mint new entities ---
                        before=24048  after_identical_redefine=24048  stable=True
```

Every claim in the brief holds:

- Two Concept-valued identity components resolve in one `.new()`.
- A row whose `aircraft_id` matches no `Aircraft` produces **no assignment and no error** - 23952 of
  the 48000 history rows silently produced nothing. That is exactly the quarantine semantics section
  1.3 depends on.
- Identity is a stable hash of the components: an identical second `define()` mints zero new
  entities. HT-01 holds.
- The components read back correctly through `Assignment.aircraft == Aircraft` and
  `Assignment.event == AircraftEvent`.

Note the API name: the brief writes `filter_by`; the current idiom is `Concept.lookup(**kwargs)`,
which the `rai-pyrel` skill states supersedes the deprecated `filter_by`. Both exist on `Concept` in
1.20.1; the probes used `lookup` throughout and it works. **MODEL-01 should write `lookup`.**

**Design consequence.** Section 1.3's compound identities and section 2.11's chained-lookup pattern
are both green. Because a missing parent is silent, MODEL-01 must add a per-association count
assertion (`count(Assignment)` vs the SQL row count of the eligible source rows) or a quarantine
count will be invisible.

---

## U-10. Four ordering keys plus `.per()` - CONFIRMED

```python
m.define(Audit.seq(
    aggs.rank(aggs.asc(Audit.event_date), aggs.asc(Audit.row_sequence),
              aggs.asc(Audit.event_sequence), aggs.asc(Audit.event_id))
    .per(Audit.aircraft)))
```

```
      k seq          d rs es   eid
0  a1-1   1 2020-01-01  1  1  1001
1  a1-2   2 2020-01-01  2  1  1002
2  a1-3   3 2020-01-01  2  2  1003
3  a1-4   4 2020-06-01  1  1  1004
4  a2-1   1 2021-03-03  1  1  2001
5  a2-2   2 2021-09-09  1  1  2002
```

Three same-day observations for aircraft 1 get ranks 1, 2, 3 in the correct four-key order, and the
per-aircraft partition resets for aircraft 2. `.per(Ac)` with the bare Concept bound in `where()`
gives the same answer (U-10c), so either form is safe here.

The Q02 spell pairing on `seq + 1` works exactly as section 5.4 designs it, **including the zero-day
same-day spell** that P0-01.8 / NF-A02 require:

```
  storage_k storage_date storage_rs return_k return_date  storage_days  same_day
0      a1-2   2020-01-01          2     a1-3  2020-01-01             0      True
1      a2-1   2021-03-03          1     a2-2  2021-09-09           190     False
```

`std.datetime.date.diff("day", ...)` returns 0 for the same-day pair and 190 for the real spell.
`(Audit.event_date == nxt.event_date)` projects as a real boolean column.

**Design consequence.** Section 5.4 is green as written. No change.

---

## U-09. Absent-value semantics in a `select` - PARTIALLY REFUTED, and section 5.3's code does not compile

The first run of this probe used a fixture that N-01 (below) silently corrupted, so it was re-run
with a null-free fixture. Both logs are kept: `out_probe_d.log` (corrupted fixture) and
`out_probe_d2.log` (correct). Everything below is from the correct run.

Fixture: `Ac` 1, 2, 3, 4 all exist; only 1 and 2 have an `Ac.the_type` link. Every candidate shape
must return **four** rows.

| # | Shape | Rows | Result |
|---|---|---|---|
| D1 | `select(Ac.id, Ac.the_type.subseries)` | **4** | 1, 2 have values; 3, 4 come back as pandas `NaN` in a `StringDtype` column |
| D2 | `select(Ac.id, Ac.the_type.subseries \| "__NULL__")` | **4** | 3, 4 carry the literal token |
| D3 | `where(Ac.the_type == Ty).select(Ac.id, Ty.subseries \| "__NULL__")` | **2** | the `where` binding filters first; the fallback cannot rescue the dropped rows |
| D5 | `m.union(frag_a, frag_b).to_df()` | - | raises `[Missing arg] Expression Union[1].to_df() cannot be used without an argument` |
| D6 | `(frag_a \| frag_b).to_df()` | - | raises `[Missing arg] Expression Match[1].to_df() ...` |
| D7 | **section 5.3's exact shape**: `status, = (m.where(...).select(...) \| m.select(...))` then select it | - | raises `[Unground Variable] Variable 'ty' is unground` |
| D8 | `String.ref()` bound through `m.where(m.union(branch_a, branch_b))` | **4** | correct |
| D9 | total derived `Property` from two mutually-exclusive `define()` rules | **4** | correct |
| D10 | DV-33 as three mutually-exclusive `define()` rules | **4** | `OK`, `OK`, `NO_RECORDED_STATE`, `NO_RECORDED_STATE` |
| D11 | `m.where(a := Ac.ref(), m.not_(a.the_type)).select(a.id.alias("acid"))` | 2 | correct; note an empty result returns a DataFrame with **no columns at all**, so `df["x"]` raises `KeyError` rather than giving an empty column |
| D12 | `(aggs.count(Ty).per(Ac).where(Ac.the_type == Ty) \| 0)` | **4** | 1, 1, 0, 0 - sparse aggregate coalesces correctly |

Raw evidence for the two that matter most:

```
--- D1  select(Ac.id, Ac.the_type.subseries)  [dot-chain, no fallback] ---
n_rows=4  columns=['id', 'sub']
  id       sub
0  1  A320-200
1  2  B738-800
2  3       NaN
3  4       NaN
isna_per_col={'id': 0, 'sub': 2}

--- D10  DV-33 as mutually-exclusive define() rules ---
n_rows=4  columns=['id', 'status']
  id             status
0  1                 OK
1  2                 OK
2  3  NO_RECORDED_STATE
3  4  NO_RECORDED_STATE
```

### What is refuted

1. **`| None` is not supported at all.** It raises before any query is sent:
   `AttributeError: 'NoneType' object has no attribute '_source'` at
   `relationalai/semantics/frontend/front_compiler.py:1673`. The brief's primary recommendation for
   the nine null columns in `EXPECTED_ANSWERS.yaml:484-492` does not exist.
2. **Section 5.3's DV-33 `|` chain does not compile.** The written form
   ```python
   status, = (
       model.where(model.not_(*within_existence(Aircraft, d))).select("OUTSIDE_EXISTENCE") |
       model.where(*visible_on(AircraftTypeDaily, d), ...).select("OK") | ...
   )
   ```
   fails with `[Unground Variable]` as soon as a branch mentions a concept that the final `select`
   does not itself bind. The `|` operator does work (the checkout example is real), but only when
   every branch grounds the same variables - which the four DV-33 branches deliberately do not.

### What is confirmed, and the shape MODEL-01 should use

3. **The dot-chain already gives left-join semantics.** `select(Ac.id, Ac.the_type.subseries)`
   keeps the row and renders absence as `NaN`. The brief (and `rai-pyrel` Silent Corruption #3)
   warn that dot-chains "drop `where`-bindings"; here that is precisely the property you want,
   because there is no `where` binding to preserve. D3 shows the opposite: bind the concept in
   `where()` and you lose the gap rows, fallback or not.
4. **`| "<token>"` works on a dot-chain** and is the right choice where
   `EXPECTED_ANSWERS.yaml` expects a token rather than a null.
5. **The DV-33 status chain must be authored as mutually-exclusive `define()` rules**, not as a `|`
   chain in the query. This is exactly what `QUERY_ROUTING.md` already predicted for all eight
   questions ("Every question answers Yes to rules-authoring-first"), so it is not new work, but
   section 5.3 of the design brief must be rewritten before MODEL-01 codes it.

**Design consequences.**

- **MODEL-01 / section 5.3:** replace the `|` chain with four `model.where(...).define(Ac.dv33(...))`
  rules per dimension, with mutually exclusive conditions (`<` on one boundary, `>=` on the other) or
  it will `FDError`. `computed_aircraft.py` is the right home.
- **QUERY-UC1 (Q01):** the nine null cells come from D1's dot-chain, arriving as pandas `NaN` in a
  `StringDtype` column. Whatever compares against `EXPECTED_ANSWERS.yaml` must treat `NaN` as the
  frozen `null`. Do not reach for `| None`.
- **All QUERY-*:** an empty RAI result is a **zero-column** DataFrame, not a zero-row DataFrame with
  the expected columns. `Q02-NO-SPELLS`, `Q07-KNOWLEDGE-END-EMPTY` and `Q08-NOT-FOUND` are frozen
  empty results, so the comparison harness must construct the expected columns itself rather than
  read them off the returned frame.

---

## U-11 = G-01 .. G-06. All six pass; G-03 and G-04 refute the brief

Run: `snow sql -c rai --role RAI_DEMO_AVIATION_TEMPORAL -f build/probes/g_fd_probes.sql`.
Every probe counts **violating keys**, so zero is a pass.

```
G-01                     violating_keys = 0
G-02                     violating_keys = 0
G-02-control-AC08-AC09   violating_keys = 0
G-03                     violating_keys = 0
G-04                     violating_keys = 0
G-05                     violating_keys = 0
G-06                     violating_flight_ids = 0
```

### G-01 / G-02 - pass, but note the fixture cardinality

`SOURCE.AIRCRAFT_CONFIGURATION` has 2000 rows, 1999 distinct `AIRCRAFT_SUBSERIES` and 1999 distinct
`ENGINE_SUBSERIES`, with zero nulls in either. So the definition tables are all but a bijection with
the configuration rows and the FD is satisfied nearly trivially. `Property` is safe.

`G-02-control` additionally shows that AC-08 `ENGINE_COUNT` and AC-09 `HAS_MULTIPLE_ENGINE_TYPES`
*also* happen to be functional on `ENGINE_SUBSERIES` in this fixture. **Do not move them onto
`EngineType`.** They are `ENGINE_ASSIGNMENT_ATTRIBUTE` per `ATTRIBUTE_AUTHORITY.md:130-131`, they are
functional here only by accident of a near-bijective fixture, and section 2.3's argument is a
semantic one, not a data one.

### G-03 / G-04 - the brief expected these to FAIL. They pass, and the reason matters

```
G-03-grain     distinct_airport_ids=45   ids_with_multiple_periods=0  max_periods_per_id=1  total_rows=45
G-03-is-current  n_current=1 for all 45 airport_ids
G-04-grain     distinct_airline_ids=100  ids_with_multiple_periods=0  max_periods_per_id=1  total_rows=100
G-04-is-current  n_current=1 for all 100 airline_ids
```

Additionally every row has `EFFECTIVE_START_DATE = 2000-01-01` and `EFFECTIVE_END_DATE IS NULL`.

The brief's reasoning was sound - `SOURCE_CONTRACT.md:376` does declare the source grain as
`(airport_id, effective_start_date)` - but DATA-01/DATA-03 generated **exactly one effective period
per reference entity**. The multi-period case the brief feared simply is not in the data.

**Design consequence, and this is the DATA-04 answer the orchestrator asked for.**

- **DATA-04 does not need to build `MODEL_INPUT.AIRPORT_CURRENT` or `MODEL_INPUT.AIRLINE_CURRENT`.**
  The brief's "recommended fix regardless of the result" is not required. `Airport` and `Airline` can
  bind directly from `SOURCE.AIRPORT_REFERENCE` / `SOURCE.AIRLINE_REFERENCE` with `airport_id` /
  `airline_id` identity, and `Property` for every attribute, and it will not `FDError`.
- The safety is **fixture-dependent, not structural.** If DATA-01 ever emits a second effective
  period for one reference entity, `Airport.name` becomes non-functional and MODEL-01 raises
  `FDError` at first evaluation (per U-04's timing). Two cheap mitigations, in order of preference:
  1. Add the G-03/G-04 queries to the MODEL-01 / `prep_demo.py` gate as zero-count assertions. They
     run in under a second and turn a silent regression into a named failure.
  2. If DATA-04 has spare capacity anyway, build the two `*_CURRENT` projections with a **declared
     deterministic order** (not `WHERE is_current`, per `ATTRIBUTE_AUTHORITY.md:301-303`) and keep
     the full multi-period rows as an `AirportReferenceLineage` association. This is strictly more
     robust and costs one small view each.
- `is_current` is currently exactly one row per entity for all 145 reference rows, so if a
  projection *is* built, `is_current` happens to be deterministic today - but the contract forbids
  relying on it, and the deterministic-order rule should still be written explicitly.

### G-05 - passes, but only vacuously

```
G-05             violating_keys = 0
G-05-coalescing  distinct_dv20_keys=9999  dv20_keys_with_multiple_ph_rows=1  max_ph_rows_per_dv20=2
G-05-dup-detail  SYN-MKT-FUL / 721 / SFO / LAS / 2026-08-31  n_rows=2  n_keys=0  n_null_keys=2
                 (historical_source_row_id 5102, 5103)
```

The coalescing case the brief worried about **does** exist - one DV-20 key absorbs two PH lineage
rows - but both of those rows carry `SCHEDULE_KEY IS NULL`, so there is no conflicting PH-02 to
violate the FD. The FD is therefore unexercised rather than proven.

**Design consequence.** Take the brief's own preferred option and do not rely on the vacuous pass:
bind `PassengerFlight.schedule_key` as a `Property` **only from the DV-21 precedence-winning lineage
row**, which is what P0-10.3 requires anyway. Then the FD is guaranteed by construction rather than
by a fixture accident. Re-run G-05 against `MODEL_INPUT.PASSENGER_SOURCE_LINEAGE` once DATA-04 has
built it.

### G-06 - passes, plus one deliberate anomaly

```
G-06              violating_flight_ids = 0        (flight_id is unique and single-aircraft)
G-06-inverse      distinct_aircraft_ids=996  max_flights_per_aircraft=13  min=1
G-06-next-flight  flight_ids_with_multiple_next=0  dangling_next_flight_targets=1
```

`AircraftFlight.aircraft` is functional; `Aircraft.actual_flights` must be a `Relationship`
(1..13 per aircraft), exactly as section 4.3 G-06 says. `next_flight_id` is functional per
`flight_id`, so `AircraftFlight.next_flight_raw` is correctly a `Property`.

The single dangling `NEXT_FLIGHT_ID` is the `MISSING_TARGET` fixture. Section 2.11's two-`lookup`
binding will silently produce no fact for it, which is the intended behaviour, and
`RotationLinkValidation` must be the thing that surfaces it.

---

## U-12. Cold start, warm start, change tracking - CONFIRMED and quantified

Measured on `aviation_temporal_logic_s` (`HIGHMEM_X64_S`) starting from `SUSPENDED`, binding
`SOURCE.SCHEDULE_SNAPSHOT_CALENDAR` (10 rows) and running one `select`:

```
[    0.63s] imports done
[    0.64s] create_config(strict, pinned engine)
[    0.64s] Model('probe_u12') constructed
[    0.64s] m12.Table(SCHEDULE_SNAPSHOT_CALENDAR) declared

 Parallel init finished in  10m18s
  -> Indexing                 25.3s
  -> Provisioning             9m14s
  -> Status                    1.6s
  -> Validation                3.3s

Query COMPLETED 3.6s
[  631.97s] FIRST to_df() returned (631.34s for the select alone)
[  634.74s] WARM second to_df() (2.76s)
```

| Measure | Value |
|---|---|
| **Cold start, suspended engine to first DataFrame** | **631.3 s (10 min 31 s)** |
| of which engine provisioning | 9 min 14 s |
| of which first-model indexing | 25.3 s |
| of which the query itself | 3.6 s |
| **Warm second query, same model** | **2.76 s** |
| **New `Model` on an already-warm engine** | 25 - 60 s indexing, then 2.5 - 5 s per query |

Per-model indexing observed across the run: 25.3s, 34.3s, 31.0s, 45.9s, 48.3s, 57.2s, 60s. It scales
with the number of bound tables and rules, not with row count - the 48000-row
`AIRCRAFT_HISTORY` model indexed in 34.3s.

No `SnowflakeChangeTrackingNotEnabledException` and no change-tracking warning of any kind. DATA-03's
`CHANGE_TRACKING = ON` on all ten `SOURCE` tables is confirmed working end to end from the demo role.
Query latencies over the whole run: 2.5 - 6 s typical; 11 - 19 s for the ranked/recursive/FD-error
cases; 12 - 26 s for full 70000-row column pulls.

**Design consequences.**

- The 5-minute auto-suspend is the dominant cost driver for the demo, not query time. A 10.5-minute
  cold start is far outside any acceptable live-demo budget, so `prep_demo.py` **must** resume and
  warm the engine as its first action, and the runbook must tell the presenter to run it well before
  the session.
- MODEL-01's own iteration loop should keep one long-lived process, because every fresh process that
  builds a fresh `Model` pays 25-60s of indexing before its first query.
- The brief's config note names `aviation_temporal_logic_xs`. That engine does not exist and SDK
  1.20.1 refuses `HIGHMEM_X64_XS` for Logic reasoners. `config.py` must pin
  `reasoners.logic.name = "aviation_temporal_logic_s"`. Confirmed working:
  `create_config(model={"implicit_properties": False}, reasoners={"logic": {"name": "aviation_temporal_logic_s"}})`
  merges cleanly over the auto-discovered `~/.snowflake` connection - `connections` does **not** have
  to be passed explicitly even though the `create_config` docstring implies it is required.

---

## N-01 (new, not in the brief). `model.data(df)` drops every row with a null anywhere in the frame

Discovered while running U-09: a four-row frame produced only two entities.

```python
two_col = pd.DataFrame([(1, "x"), (2, "y"), (3, None), (4, None)], columns=["id", "other"])
m1.define(A.new(id=two_col_data.id))       # `other` is never referenced
```

```
E1a  count(A)  [null in an UNUSED second column]           = 2     (expected 4)
E1b  count(B)  [control, single column, no nulls]          = 4
E1c  count(C)  [3 columns, nulls in two different rows]    = 2     (expected 4)
E1d  A ids = [1, 2]        E1e  C ids = [1, 2]
E2a  count(D)  [float column with NaN in rows 3, 4]        = 2
E2b  count(E)  [string column with EMPTY STRING "" in 3,4] = 2     <-- empty string counts as null
```

The drop is per-**frame**, not per-`.new()`-argument, and an empty string behaves as a null.

**Snowflake `Table` sources do NOT behave this way**, which is the good news:

```
E3a  count(Ev1)  schema declares ONLY the never-null key                     = 48000
E3b  count(Ev2)  schema ALSO declares three ~always-null columns             = 48000
E3c  Ev2 carrying end_event_date   (SQL: 1 non-null of 48000)                = 1
E3d  Ev2 carrying start_event_date (SQL: 48000 non-null)                     = 48000
E3e  count(Ev2) after both attribute loads                                   = 48000
E3f  count(Ev3)  compound identity INCLUDING the 1-of-48000 column           = 1
```

**Design consequences.**

- Binding-policy **R2 is correct but its stated reason is half right.** For a `model.Table()`,
  declaring an always-null column in the `schema=` dict does **not** drop rows (E3b); only columns
  actually passed into `.new()` gate entity creation (E3f). So the danger `to_schema()` poses is
  narrower than the brief describes - but `to_schema()` passes *every* column into `.new()`, so R2's
  conclusion ("never `to_schema()` inside `.new()` on these tables") stands, and E3f is the live
  proof: one always-null column in the identity took 48000 rows down to 1.
- The per-attribute `.lookup(...).prop(col)` pattern is exactly right and produces correctly sparse
  facts (E3c: 1 of 48000). Absence of a value really is absence of a fact, which is P0-02.8.
- **New rule for MODEL-01 and for the notebooks:** never use `model.data(pandas_df)` for anything
  that has a nullable column. Every fixture, every notebook cross-check, every test frame must be
  null-free and empty-string-free, or it must be split into several narrow null-free frames. This
  silently changes row counts with no warning, and it will corrupt a Phase-5 notebook cell that looks
  correct.

## N-02 (new, not in the brief). The free `distinct(...)` fails when several `Model`s exist

```
RAIException: [Ambiguous model] Multiple Models have been defined. Please use functions on the
specific Model.
```

`from relationalai.semantics import distinct` is a module-level function and cannot pick a model.
Every probe script that built more than one `Model` in one process hit this. `MODEL-01` builds one
model, so this is not a blocker there, but `prep_demo.py`, the parity test in `inventory.py`, and any
notebook cell that imports the standalone MODEL-02 file alongside the package will trip it.

**Design consequence.** Prefer `model.select(...)` composition that avoids the free `distinct`, or
confine multi-model code to one model per process. `QUERY_ROUTING.md`'s standing rule 3
(`model.select(distinct(Concept.prop)).to_df()` for string discovery) is fine in a single-model
process and will break in a two-model one.

---

## Consolidated design consequences

### DATA-04 (raise first - another agent is still working)

| # | Consequence | Change needed |
|---|---|---|
| 1 | **U-03: no canonical `VARCHAR` time column is required.** MODEL-01 declares the raw `TIME` columns as `String` and gets full fidelity | **None.** The brief's DATA-04 change is cancelled |
| 2 | **G-03 / G-04: `MODEL_INPUT.AIRPORT_CURRENT` and `AIRLINE_CURRENT` are not required.** The fixture has exactly one effective period per reference entity | **None required.** Optional hardening if capacity allows |
| 3 | G-05 passes only vacuously | No new table. `PASSENGER_SOURCE_LINEAGE` must carry DV-21 precedence so MODEL-01 can bind `schedule_key` from the winner only. That is already in the contract |
| 4 | U-05: `date.range(freq="M")` is exact | `MODEL_INPUT.MONTH_END_CALENDAR` becomes **optional**. Keep it if already built; do not start it if not |
| 5 | N-01 | Not a DATA-04 concern (Snowflake tables are unaffected), but worth knowing if DATA-04 stages anything through pandas |

**Net: DATA-04 needs no redirection.** Two of the three changes the brief anticipated are cancelled
and one was never a table.

### MODEL-01

| # | Consequence |
|---|---|
| 1 | `sources.py` declares the **eight `TIME` columns as `String`**: SS-23..SS-26 on `SCHEDULE_SNAPSHOT`, PH-12..PH-15 on `PASSENGER_HISTORICAL`. Values arrive as `HH:MM:SS.mmm` |
| 2 | `config.py` pins `reasoners.logic.name = "aviation_temporal_logic_s"` (not `_xs`, which does not exist) |
| 3 | R1 stays mandatory, for a new reason: strict mode gives **no** typo protection on a `Table`. Add an `inventory.py` assertion that no discovered column has `type_name == "Any"` |
| 4 | A wrong type in `sources.py` yields a silent NaN column, not a `TyperError`. The MODEL-01 gate must assert per-column non-null counts against SQL, not just row counts |
| 5 | **Section 5.3 must be rewritten.** The DV-33 `\|` chain does not compile. Author DV-33 as mutually-exclusive `define()` rules in `computed_aircraft.py` |
| 6 | `constraints.py` keeps `require(unique(...))` as documentation only, with a comment stating 1.20.1 does not enforce it. Real gates become zero-count assertion queries |
| 7 | Write `Concept.lookup(**kwargs)`, not `filter_by` (deprecated) |
| 8 | Sections 1.3, 2.x, 2.11, 2.12, 4.x, 5.4, 6.x are all **green as written** |
| 9 | `Airport` / `Airline` bind straight from `SOURCE`, `Property` for every attribute; add the G-03/G-04 zero-count assertions to the gate |
| 10 | `calendar.py` may generate `MonthEnd` from `std.datetime.date.range(dt.date(2015,1,31), dt.date(2024,12,31), freq="M")` - proven to give exactly 120 correct month ends |
| 11 | Never `model.data(pandas_df)` on a frame containing a null or an empty string |
| 12 | Every association loaded through `Concept.lookup(...)` needs a count assertion, because an unresolvable parent produces nothing and raises nothing |

### QUERY-UC1 / UC2 / ROT

| # | Consequence |
|---|---|
| 1 | Q01's null cells come from the plain dot-chain `select(Aircraft.id, X.the_type.subseries)` and arrive as pandas `NaN`. `\| None` **raises**; do not use it |
| 2 | Do not bind the optional target in `where()` and expect a fallback to rescue the gap rows (probe D3: 4 rows became 2) |
| 3 | An empty result is a **zero-column** DataFrame. The `EXPECTED_ANSWERS.yaml` harness must supply the expected column list for `Q02-NO-SPELLS`, `Q07-KNOWLEDGE-END-EMPTY`, `Q08-NOT-FOUND` |
| 4 | Any time-of-day literal must be `'HH:MM:SS.mmm'`. `'16:00:00'` silently matches zero rows |
| 5 | Q02's `seq + 1` spell pairing is proven exact, including the zero-day same-day spell |
| 6 | Q08's recursion is proven to terminate on cyclic input; no step bound available or needed |
| 7 | Avoid the free `distinct(...)` in any process that constructs more than one `Model` |
| 8 | `.per(FK_property)` and `.per(BareConcept)` both gave correct answers in the single-clause rank case, but prefer the bare Concept per the skill |

### Talk track / narrative

| # | Consequence |
|---|---|
| 1 | The multi-open route beat is fully proven: three concurrent open states, one query, no error (U-06d) |
| 2 | The mirror-image `FDError` beat is real but happens at **first evaluation** (13-19 s), not at define time. Do not say "define time" on stage |
| 3 | The `FDError` message names the offending relation and prints the two conflicting hashes, which is the strong part of the beat |
| 4 | Cold start is 10.5 minutes. `prep_demo.py` must warm the engine long before the session |
| 5 | Add to the honest-limitations list in section 9: `require(unique(...))` is not enforced in 1.20.1, and Snowflake `TIME` cannot round-trip except as a string |

---

## Addendum, same session: `MODEL_INPUT` landed while the probes were running

`PK_AVIATION_TEMPORAL.MODEL_INPUT` was empty when the probe run began and had **37 tables** by the
time it finished. Every substituted probe was re-run against the real tables. **Nothing changed.**

```
G-03-real   (MODEL_INPUT.AIRPORT_CURRENT, 45 rows)            violating_keys = 0
G-04-real   (MODEL_INPUT.AIRLINE_CURRENT, 100 rows)           violating_keys = 0
G-05-real   (MODEL_INPUT.PASSENGER_SOURCE_LINEAGE, 19998 rows)
            violating_dv20_keys = 0
            19996 distinct DV-20 keys; 2 keys carry 2 lineage rows; max 2
G-05-real-selected  (restricted to IS_SELECTED_OBSERVATION)   violating_keys = 0
MEC-q03-window  (MODEL_INPUT.MONTH_END_CALENDAR)              month_ends 2015-01-01..2024-12-31 = 120
```

DATA-04 has **already built** the two projections the brief wanted (`AIRPORT_CURRENT` with
`REFERENCE_PERIOD_COUNT` and `PROJECTION_RULE` provenance columns, and `AIRLINE_CURRENT`) and the
month-end calendar (600 rows, 2000-01-31 to 2049-12-31, of which exactly **120** fall in the Q03
window). None of that is wasted and none of it should be torn out:

- `AIRPORT_CURRENT` / `AIRLINE_CURRENT` carry a `PROJECTION_RULE` column, which is exactly the
  "declared deterministic order rather than `WHERE is_current`" that `ATTRIBUTE_AUTHORITY.md:301-303`
  demands. Binding `Airport` and `Airline` from these is now the *better* option than binding from
  `SOURCE`, because the projection rule is recorded in the data. **Recommendation: MODEL-01 binds the
  projections.** The G-03/G-04 refutation stands - they were not *required* - but since they exist,
  use them.
- `MONTH_END_CALENDAR` is correct and Q03-exact. Bind it. Keep `std.datetime.date.range(freq="M")` as
  the notebook cross-check, which U-05 has now proven agrees exactly (120 rows, same endpoints).
- `PASSENGER_SOURCE_LINEAGE` carries `IS_SELECTED_OBSERVATION`, `SOURCE_PRECEDENCE_RANK` and
  `SELECTION_RANK`, so the G-05 mitigation ("bind `schedule_key` from the DV-21 precedence winner
  only") is directly expressible: filter on `IS_SELECTED_OBSERVATION`. Zero violations either way.

**The only DATA-04 item that was genuinely in question - the canonical `VARCHAR` time column for
U-03 - is confirmed NOT needed.** DATA-04 needs no redirection and no rework.

## Exact `TIME` round-trip proof (closes `SOURCE_CONTRACT.md:22`)

The RAI String rendering is byte-identical to Snowflake `TO_VARCHAR(<time>, 'HH24:MI:SS.FF3')`:

```sql
SELECT TO_VARCHAR(passenger_departure_utc_time, 'HH24:MI:SS.FF3') AS fmt3, COUNT(*)
FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT GROUP BY 1;
-- '16:00:00.000'  69999
-- '23:00:00.000'      1
```

RAI, same column declared `String`:

```
where(t == "16:00:00.000")  ->  n = 69999
distinct                    ->  ['16:00:00.000', '23:00:00.000']
```

and for PH-12:

```sql
-- SQL: '01:30:00.000' 3, '03:30:00.000' 1, '09:00:00.000' 9992, '12:00:00.000' 2, '23:30:00.000' 2
```
```
-- RAI: ['01:30:00.000','03:30:00.000','09:00:00.000','12:00:00.000','23:30:00.000']
```

Counts, distinct sets and endpoints all agree exactly. The round-trip test
`SOURCE_CONTRACT.md:22` requires is therefore a plain equality against
`TO_VARCHAR(<col>, 'HH24:MI:SS.FF3')`, with no normalisation needed.
