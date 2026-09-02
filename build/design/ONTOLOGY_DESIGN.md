# ONTOLOGY_DESIGN - authoritative design brief for MODEL-01

Owner: design task. Consumer: the orchestrator, who hand-writes `rai_code/aviation_model/`.
This file does not create the ontology. It fixes the shape, names the PyRel construct for every
decision, and lists what must be smoke-tested live before the orchestrator commits to it.

Inputs read in full: `SOURCE_CONTRACT.md`, `ATTRIBUTE_AUTHORITY.md`, `NEO4J_RAI_MAPPING.md`,
`SEMANTIC_DECISIONS.md`, `DEMO_QUESTIONS.md`, `EXPECTED_ANSWERS.yaml` output schemas,
`BRIEF.md` non-negotiables, `TASK_GRAPH.md` MODEL-01/MODEL-02 definitions.

> ## PARTIALLY SUPERSEDED - read `PROBE_RESULTS.md` first
>
> This brief was written by an agent that could not execute code. Its section 8 listed twelve
> uncertainties; PROBE-01 has now run all twelve live against SDK 1.20.1 plus the six section 4.3
> FD probes, and **`build/design/PROBE_RESULTS.md` is the authority wherever the two disagree.**
> Live evidence beats a careful reading. The corrections that change code:
>
> - **Section 5.3 does not compile.** The DV-33 status `|` fallback chain raises `[Unground
>   Variable]`, and `| None` raises outright. Author DV-33 as mutually exclusive `define()` rules.
> - **Snowflake `TIME` must be declared `String`** in the `schema=` dict, for exactly eight columns
>   (SS-23..SS-26, PH-12..PH-15). Discovered as `DateTime` it silently returns 100% NULL. Declared
>   `String` it is byte-identical to `TO_VARCHAR(t,'HH24:MI:SS.FF3')`. No DATA-04 change is needed;
>   the canonical-VARCHAR recommendation in U-03 is withdrawn.
> - **`require(unique(...))` is a silent no-op**, with and without `emit_constraints: True`. Real
>   gates are zero-count assertion queries; keep the `require` calls as documentation only.
> - **Strict mode gives zero typo protection on a `model.Table()`.** A misspelled column binds
>   silently as `Any`, and a wrongly declared type yields a silent all-NaN column. R1 is mandatory,
>   and `inventory.py` must assert no discovered column is `Any` and check per-column non-null
>   counts against SQL, not just row counts.
> - Use `Concept.lookup(**kwargs)`; `filter_by` as used throughout this brief is deprecated.
> - The engine is **`aviation_temporal_logic_s`**, not `aviation_temporal_logic_xs`. Cold start from
>   SUSPENDED measured at 631s; `prep_demo.py` must warm it as its first action.
> - Never call `model.data(pandas_df)` on a frame containing a null or empty string: it silently
>   drops the whole row. Snowflake `Table` sources are unaffected.
> - G-03 and G-04 **pass**, contrary to this brief's expectation of failure. No DATA-04 rework.
>
> Sections 1.3, 2.x, 4.x, 5.4, 6.x and 7 are confirmed green as written.

---

## 0. Ground-truth correction before anything else

**The PyRel checkout is older than the installed SDK. Do not use it as the API authority.**

- `/Users/piotrkraus/rai-repos/PyRel/pyproject.toml:3` declares `version = '1.2.2'`.
- The demo venv has `relationalai 1.20.1` at
  `/Users/piotrkraus/rai-repos/rai-demos/aviation_temporal_demo/.venv/lib/python3.13/site-packages/relationalai/`.

`CLAUDE.md` says to treat the checkout as ground truth when the marketplace skills are thin. For this
demo that instruction is inverted: 1.20.1 is eighteen minor versions ahead of the checkout, and the
installed package ships complete numpydoc docstrings, so **the installed `site-packages` source is the
API authority**. The checkout stays useful for one thing only: runnable *idiom shape* in
`PyRel/tests/end2end/unified/tests/`. Every signature quoted below is from the installed 1.20.1 tree
unless the path says otherwise. Where a marketplace skill disagrees with 1.20.1, the note says so
explicitly.

Shorthand used below: `SD = .venv/lib/python3.13/site-packages/relationalai/semantics`.

### 0.1 Signatures the whole design rests on

```
SD/frontend/base.py:6318
    def __init__(self, name: str = "", exclude_core: bool = False, is_library: bool = False, config:Config|None=None):
```
`Model` takes only these four. There is no `dry_run`, no `format`, no `ensure_change_tracking`.

```
SD/frontend/base.py:6582
    def Concept(self, name: str, extends: list[Concept] = [], identify_by: dict[str, Property|Concept] = {}, identity_includes_type: bool = False) -> Concept:
```
`identify_by` values may be Concepts, so compound identities may include other concepts. Confirmed by
the docstring at `SD/frontend/base.py:6602`: *"The keys are identity attribute names and the values
specify their types (most commonly a Concept ...)"*.

```
SD/frontend/base.py:6650
    def Table(self, path: str, schema: dict[str, Concept] = {}, type: Iceberg | Native | None = None) -> Table:
```

```
SD/frontend/base.py:6780
    def Property(self, reading: str = "", fields: list[Field] = [], short_name: str = "") -> Property:
SD/frontend/base.py:6705
    def Relationship(self, reading: str = "", fields: list[Field] = [], short_name: str = "") -> Relationship:
```
`Property(Relationship)` at `SD/frontend/base.py:3795`. The only difference is the compiler-enforced
functional dependency: all fields except the last are keys.

```
SD/frontend/base.py:1641   def new(self, *args: StatementAndSchema, **kwargs: Any) -> New:
SD/frontend/base.py:1734   def to_identity(self, *args: Any, unsafe: bool = False, **kwargs: Any) -> New:
SD/frontend/base.py:1783   def identify_by(self, *properties: Property|Chain) -> Concept:
SD/frontend/base.py:1856   def filter_by(self, **kwargs: Any) -> FilterBy:
SD/frontend/base.py:1976   def ref(self, name="") -> Ref:
SD/frontend/base.py:3365   def alt(self, reading_str: str) -> Reading:          # on Relationship, inherited by Property
SD/frontend/base.py:2630   def to_schema(self, *, exclude: list[str] = []) -> TableSchema:
SD/frontend/base.py:7013   def define(self, *args: Statement) -> Fragment:
SD/frontend/base.py:6896   def where(self, *args: Statement) -> Fragment:
SD/frontend/base.py:6848   def select(self, *args: StatementAndSchema | None) -> Fragment:
SD/frontend/base.py:6934   def require(self, *args: Statement) -> Fragment:
SD/frontend/base.py:7057   def union(self, *items: Value) -> Union:
SD/frontend/base.py:7189   def not_(self, *items: Statement) -> Not:
SD/inspect.py:943          def schema(model: Model) -> ModelSchema:
```

Constraints, needed for the multiplicity gates in section 4:
```
SD/std/constraints.py:33   def unique(*args: Variable) -> Expression:
SD/std/constraints.py:57   def exclusive(*args: Concept|Ref) -> Expression:
SD/std/constraints.py:93   def oneof(*args: Concept | Ref) -> Fragment:
```

Ordering, needed for same-day sequence and spell pairing in sections 2 and 5:
```
SD/std/aggregates.py:322   def asc(*args: AggValue) -> Ordering:
SD/std/aggregates.py:345   def desc(*args: AggValue) -> Ordering:
SD/std/aggregates.py:372   def rank(*args: AggValue|Ordering) -> Aggregate:
SD/std/aggregates.py:430   def rank_asc(*args: AggValue) -> Aggregate:
SD/std/aggregates.py:913   def per(*args: Value) -> Per:
SD/std/aggregates.py:5191  (Aggregate) def where(self, *args: Statement) -> Aggregate:
```

Dates:
```
SD/std/datetime.py:108     class date:  __new__(cls, year, month, day) -> Expression
SD/std/datetime.py:410     def range(cls, start=None, end=None, periods=1, freq="D") -> Variable   # freq in D|W|M|Y
SD/std/datetime.py:1280    def days(period: IntegerValue) -> Expression
SD/std/datetime.py:1321    def months(period: IntegerValue) -> Expression
```
Python `datetime.date` literals go straight into rules. Evidence:
`PyRel/tests/end2end/unified/tests/date_diff.py:18` `new_year_2024.start_date(dt.date(2024, 1, 1))`
and `PyRel/tests/end2end/unified/tests/date_ranges.py:11`
`select(std.datetime.date.range(dt.date(2024, 1, 1), dt.date(2024, 1, 7))).to_df()`.

### 0.2 Three 1.20.1 facts that change the design

**(a) There is no temporal support in the API. None.** A search of the whole `semantics` tree for
`valid_from`, `bitemporal`, `as_of`, `effective_from`, `interval` returns nothing. There is no
interval type, no validity-annotated relationship, no as-of operator. Every half-open predicate in
this demo is a hand-written two-clause conjunction over two `Date` Properties. That is the honest
parity statement, and it is also the good news for the pitch: because there is no built-in SCD
machinery, there is also no built-in "one open version per parent" assumption to fight (section 3).

**(b) Snowflake `TIME` has no RAI type. It is discovered as `DateTime`.**
```
relationalai/util/schema.py:133-138
    "DATE": "Date",
    "TIME": "DateTime",
    "TIMESTAMP": "DateTime",
    ...
```
This bites SS-23 through SS-26 and PH-12 through PH-15, which `SOURCE_CONTRACT.md:22` requires to stay
`TIME`. Binding a raw `TIME` column will type it `DateTime` and attach an invented date. See section 5.4
for the fix and section 8 item U-03 for the test.

**(c) `NUMBER(38,0)` maps to `Integer` after all, but only because of an alias identity.**
`relationalai/util/schema.py:464-468` maps a scale-0 `FIXED` with precision > 18 to the type string
`"Decimal(38,0)"`; `SD/frontend/base.py:127-128` parses that through `Number.parse`; and
`SD/frontend/core.py:314` declares `Integer = Number.size(38, 0)`, with the docstring at
`SD/frontend/core.py:118` asserting `Number.size(38, 0) is Integer` is `True`.
So `Integer` is correct for every `NUMBER(38,0)` column in the contract. **But** a `NUMBER(18,0)`
column becomes `Number.size(18,0)`, which is neither `Integer` (38,0) nor `Int64` (`SD/frontend/core.py:323`,
`Number.size(19,0)`). The contract only uses `NUMBER(38,0)`, so declare `Integer`; if DATA-03 ever emits
a narrower NUMBER, that column needs an explicit `Number.size(p, s)`.

The marketplace skills' type table ("NUMBER, INT (scale = 0) -> `Integer`") is right for this contract
by coincidence of the alias, not by rule. Do not generalise it.

---

## 1. Concept inventory

### 1.1 Binding policy (applies to every row in the tables below)

Four rules, each with its evidence, that constrain how bindings are written.

**R1. Every `model.Table()` gets an explicit `schema=` dict. No lazy discovery.**
MODEL-01 requires strict mode. In strict mode, attribute access on a table whose columns have not been
fetched raises. `Table` does not override `__getattr__`; `Concept.__getattr__`
(`SD/frontend/base.py:1531`) calls `_dot(..., allow_implicit=False)`, which returns `None` at
`SD/frontend/base.py:1439` when `implicit_properties` is false, and `_dot` then raises
`"Implicit property"` at `SD/frontend/base.py:1508`. The lazy `_columns` fetch
(`SD/frontend/base.py:2472`) is only triggered by `__getitem__` (`:2537`) or `__iter__` (`:2565`),
never by attribute access. An explicit schema also pins types from the contract instead of from
`SHOW COLUMNS`, which is what `SOURCE_CONTRACT.md:20-22` asks for.
Column keys are folded to uppercase Snowflake identifiers (`SD/frontend/base.py:2450-2452`) and
registered lowercase in `_relationships` (`SD/frontend/base.py:1472`), so `SRC.aircraft_id` resolves
to stored `AIRCRAFT_ID`. Write the schema keys in lowercase for readability.

**R2. Never use `to_schema()` inside `.new()` on these tables.**
Two reasons. First, `rai-pyrel-coding/references/data-loading.md` states: *"All columns passed to
`.new()` in a single call are required, the entity is only created when ALL values are non-null."*
Virtually every column in `SOURCE_CONTRACT.md` is declared source-nullable, so a `to_schema()` load
would silently drop most rows. Second, the same reference documents a known bug: *"`to_schema()`
clobbers previously set properties"*. Bind identity in `.new()` and every attribute separately through
`Concept.filter_by(...)`:
```python
model.define(Aircraft.new(id=AIRCRAFT_ELIGIBLE.aircraft_id))
model.define(Aircraft.filter_by(id=AIRCRAFT_ELIGIBLE.aircraft_id)
             .serial_number(AIRCRAFT_ELIGIBLE.aircraft_serial_number))
```
Absence of a value is then modelled as absence of a fact, which is exactly the P0-02.8 semantics
("null values are observations, not an excuse to carry a previous value forward").

**R3. Sources are MODEL_INPUT canonical tables, not raw SOURCE, wherever DATA-04 produces one.**
`SEMANTIC_DECISIONS.md` P0-13.1/13.2 splits responsibility: Snowflake owns de-duplication, typed
union, resolution candidates, snapshot completeness and *interval candidates*; RAI owns semantic
identities and associations, per-dimension validity, the two-clock predicates, the status-sequence
semantics, multi-open route associations, cross-domain enrichment and query logic. The daily
`valid_from`/`valid_to` pair is an interval *candidate* produced by DATA-04
(`SOURCE_CONTRACT.md:441`); RAI consumes it and owns the half-open *evaluation*. That is the correct
line and MODEL-01 must not redo the window functions.

**R4. `AIRCRAFT_CONFIGURATION`, `AIRPORT_REFERENCE`, `AIRLINE_REFERENCE` and
`SCHEDULE_SNAPSHOT_CALENDAR` are bound from `SOURCE` only if DATA-03 has materialised them as
physical, change-tracked tables under the demo role** (P0-13.3). They already are physical source
tables. The reference tables need a projection first, see section 4.4.

### 1.2 Identity and reference concepts

| Concept | `identify_by` | Bound source table | Notes |
|---|---|---|---|
| `Aircraft` | `{"id": Integer}` | `MODEL_INPUT.AIRCRAFT_ELIGIBLE` (AM-01) | Carries DV-01 `existence_from`, DV-02 `existence_to`. Registration/type/engine/status are never identity (P0-01.1). |
| `AircraftEvent` | `{"id": Integer}` | `MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE` (AH-01) | Ordered fact. Never carries a date interval (P0-01.4). |
| `AircraftConfiguration` | `{"id": Integer}` | `SOURCE.AIRCRAFT_CONFIGURATION` (AC-01) | Join target only. Left-preserves every event (P0-12.3). |
| `AircraftType` | `{"subseries": String}` | `MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION` (AC-05) | Definition attributes only after the FD proof, section 4.3. |
| `EngineType` | `{"subseries": String}` | `MODEL_INPUT.ENGINE_TYPE_DEFINITION` (AC-14) | AC-08/AC-09 do **not** live here. |
| `AircraftStatus` | `{"code": String}` | derived from `AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT` where `dimension='aircraft_status'` | Exact raw AH-09 value, no trim or case fold (`NEO4J_RAI_MAPPING.md:37`). |
| `Route` | `{"route_id": String}` | `MODEL_INPUT.ROUTE` (DV-12) | Carrier-agnostic, directional. |
| `Schedule` | `{"schedule_key": String}` | derived from `MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION` (SS-01) | Identity only. No attributes, see section 4.4. |
| `PassengerFlight` | `{"passenger_flight_key": String}` | `MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL` (DV-20) | Plan side. |
| `AircraftFlight` | `{"flight_id": Integer}` | `MODEL_INPUT.AIRCRAFT_FLIGHT` (AF-01) | Actual side. |
| `Airport` | `{"airport_id": String}` | `MODEL_INPUT.AIRPORT_CURRENT` projection (AP-01) | See section 4.4: the raw source grain is `(AP-01, AP-02)` and will FDError. |
| `Airline` | `{"airline_id": String}` | `MODEL_INPUT.AIRLINE_CURRENT` projection (AL-01) | Same problem, same fix. |
| `SnapshotDate` | `{"expected_publish_date": Date}` | `SOURCE.SCHEDULE_SNAPSHOT_CALENDAR` (SC-01) | Eligibility control (P0-05.1). |
| `MonthEnd` | `{"month_end": Date}` | `MODEL_INPUT.MONTH_END_CALENDAR` | New. Required by Q03, see section 5.5. |

Two concepts from `NEO4J_RAI_MAPPING.md` are **not** modelled as Concepts. Both are flagged, argued,
and reversible by the orchestrator.

- **`QueryExecutionContext`** (`NEO4J_RAI_MAPPING.md:68`). Its identity is "query invocation ID", so a
  model Concept would need a `model.define()` per invocation. The model is append-only
  (`rai-pyrel-coding` SKILL, "The model is append-only ... there is no API to remove, replace, or
  modify an existing element"), and PyRel warns after fifty `define()` calls from the same call site
  (`SD/frontend/base.py:6338-6340`, `_rule_source_counts` / `_rule_loop_warned`). Recommendation: make
  it a frozen Python dataclass at the query API boundary carrying DV-29/30/31, validated before any
  RAI call, echoed verbatim into every result frame. HT-24 ("Capacity execution fails parameter
  validation if either required clock is absent") is a *parameter validation* test, which this
  satisfies exactly. Contract parity is preserved; only the storage location changes.
- **`ScheduleComparison`** (DV-34) is a Concept, not a parameter, because Q05 must emit
  `comparison_date`, `previous_knowledge_date` and `crosses_snapshot_gap` per comparison and those are
  facts derived from the eligible `SnapshotDate` sequence, not per-invocation inputs.

### 1.3 Association, version and evidence concepts

Every row here is an association concept because it carries validity, provenance, resolution status
or multiplicity that cannot be collapsed into a scalar (`NEO4J_RAI_MAPPING.md:70-72`).

| Concept | `identify_by` | Bound source table |
|---|---|---|
| `AircraftDimensionAuditAssignment` | `{"dimension": String, "aircraft": Aircraft, "event_date": Date, "row_sequence": Integer, "event": AircraftEvent}` | `MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT` (DV-04) |
| `AircraftDimensionDailyAssignment` | `{"dimension": String, "aircraft": Aircraft, "valid_from": Date, "event": AircraftEvent}` | `MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT` (DV-05) |
| `CodeResolution` | `{"resolution_id": String}` | `MODEL_INPUT.CODE_RESOLUTION` |
| `CodeResolutionCandidate` | `{"resolution": CodeResolution, "candidate_id": String}` | `MODEL_INPUT.CODE_RESOLUTION_CANDIDATE` |
| `RouteState` | `{"route_state_key": String}` | `MODEL_INPUT.ROUTE_STATE` (DV-13) |
| `RouteStateSnapshotLineage` | `{"route_state": RouteState, "publish_date": Date, "row_hash": String}` | `MODEL_INPUT.ROUTE_STATE_LINEAGE` |
| `ScheduleComparison` | `{"comparison_id": String}` | derived from `MODEL_INPUT.SCHEDULE_EXACT_CHANGE` DV-34 (or its own DATA-04 table) |
| `ScheduleExactChange` | `{"comparison": ScheduleComparison, "schedule_key": String, "change_kind": String, "field_name": String}` | `MODEL_INPUT.SCHEDULE_EXACT_CHANGE` |
| `ScheduleAmendmentCandidate` | `{"candidate_id": String}` (DV-35) | `MODEL_INPUT.SCHEDULE_AMENDMENT_CANDIDATE` |
| `ScheduleAmendmentGroup` | `{"group_id": String}` (DV-36) | `MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP` |
| `ScheduleAmendmentGroupMember` | `{"group": ScheduleAmendmentGroup, "side": String, "schedule_key": String}` (DV-37) | `MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP_MEMBER` |
| `PassengerSourceLineage` | `{"passenger_flight": PassengerFlight, "source_system": String, "source_row_token": String}` | `MODEL_INPUT.PASSENGER_SOURCE_LINEAGE` |
| `InvalidPassengerObservation` | `{"source_system": String, "stable_source_row_id": Integer}` | `MODEL_INPUT.PASSENGER_FLIGHT_INVALID` |
| `PassengerSourceQuarantine` | `{"quarantine_id": String}` (DV-44) | `MODEL_INPUT.PASSENGER_SOURCE_QUARANTINE` |
| `AircraftEventQuarantine` | `{"quarantine_id": String}` (DV-44) | `MODEL_INPUT.AIRCRAFT_EVENT_QUARANTINE` |
| `ExactFulfillment` | `{"exact_fulfillment_id": String}` (DV-39) | `MODEL_INPUT.FULFILLMENT_EXACT` |
| `FulfillmentCandidate` | `{"candidate_id": String}` (DV-40) | `MODEL_INPUT.FULFILLMENT_CANDIDATE` |
| `FulfillmentAmbiguousGroup` | `{"group_id": String}` (DV-41) | `MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP` |
| `FulfillmentGroupMember` | `{"group": FulfillmentAmbiguousGroup, "side": String, "member_id": String}` (DV-42) | same table |
| `RotationLinkValidation` | `{"flight": AircraftFlight, "target_token": String}` | `MODEL_INPUT.ROTATION_LINK_VALIDATION` |

**Why compound identity rather than the DV-04/DV-05 string key for the two aircraft assignment
concepts.** `BRIEF.md:87` and `AGENTS.md:90` both say "aircraft event identity includes date, sequence,
and source history ID" and "do not identify a version by date alone". Putting those components into
`identify_by` makes that rule structural: two same-day audit observations are two different entities
because their `row_sequence` differs, and no downstream rule can accidentally collapse them.
A string key would make the same rule a convention that lives only in the DATA-04 SQL. That said,
`EXPECTED_ANSWERS.yaml:1279` expects the literal `assignment_id` value
`"aircraft_type|1001|2015-01-01|101001"` in Q04 output, so **also carry a non-identity
`assignment_id: String` Property** bound straight from the DV-05 column, and select that for output.
Do not have RAI re-derive the string; the frozen manifest owns its spelling.

### 1.4 Dimension subtypes

`AIRCRAFT_DIMENSION_*_ASSIGNMENT` is one physical table with a `dimension` discriminator, but every
query works within one dimension and P0-01.5 says change detection is per dimension. Declare four
subtypes of each, using `extends` and the standard membership rule
(`rai-pyrel-coding` SKILL, Concepts section):

```python
AircraftStateDaily  = model.Concept("AircraftStateDailyAssignment",  extends=[DailyAssignment])
AircraftTypeDaily   = model.Concept("AircraftTypeDailyAssignment",   extends=[DailyAssignment])
EngineTypeDaily     = model.Concept("EngineTypeDailyAssignment",     extends=[DailyAssignment])
AircraftStatusDaily = model.Concept("AircraftStatusDailyAssignment", extends=[DailyAssignment])

model.define(AircraftTypeDaily(DailyAssignment)).where(DailyAssignment.dimension == "aircraft_type")
```
Same four for `AuditAssignment`. `identity_includes_type` stays `False` (the default), so the subtype
instance is the same entity as its parent, which is what the contract wants: one assignment, viewed
through its dimension. The subtypes buy two things. Q02 can rank status audit assignments with
`.per(Aircraft)` instead of `.per(Aircraft, dimension)`. And the four independent clocks in Q01 become
four independent joins that are visibly independent in the code, which is the point of the demo.

---

## 2. Every temporal association, with the PyRel construct named

The general shape: **the state is a Concept; the interval is two functional `Date` Properties on that
Concept; the Neo4j edge to the parent is a functional `Property` pointing from the state to the parent;
the Neo4j edge direction is recovered with `.alt()`, which adds a reading, not a constraint.**

`SD/frontend/base.py:3365` on `.alt()`: *"An alternative reading is a `Reading` that refers to the same
underlying relationship fields but uses a different human-readable reading string. This is commonly
used to introduce inverse names ... The returned `Reading` can be used anywhere a relationship can."*
The critical property for this design is in that first clause: same underlying fields. The FD lives on
the underlying `Property` and points one way only. Adding an inverse reading never adds an inverse FD.

Declare inverses off the `Property` object, not off the attribute (attribute access returns a `Chain`,
and `Chain.alt` at `SD/frontend/base.py:4120` is a wrapper; keeping the object is clearer):

```python
_state_of = model.Property(f"{AircraftStateDaily:assignment} applies to {Aircraft:aircraft}")
AircraftStateDaily.aircraft = _state_of
Aircraft.state_assignments  = _state_of.alt(f"{Aircraft:aircraft} has state {AircraftStateDaily:assignment}")
```

### 2.1 `(AIRCRAFT)-[:HAS]->(AIRCRAFT_STATE)`

Two RAI facts, per `NEO4J_RAI_MAPPING.md:99`: the daily projection carries the interval, the audit
sequence carries the same-day truth.

```python
# daily: carries the interval
AircraftStateDaily.aircraft    = model.Property(f"{AircraftStateDaily:a} applies to {Aircraft:aircraft}")
DailyAssignment.valid_from     = model.Property(f"{DailyAssignment:a} valid from {Date:valid_from}")   # DV-06
DailyAssignment.valid_to       = model.Property(f"{DailyAssignment:a} valid to {Date:valid_to}")       # DV-07
AircraftStateDaily.registration_number = model.Property(f"{AircraftStateDaily:a} has {String:registration_number}")   # AH-17
# ... AH-18 through AH-31, one Property each (anti-bundle rule)
Aircraft.state_assignments = AircraftStateDaily.aircraft.alt(f"{Aircraft:aircraft} has state {AircraftStateDaily:a}")

# audit: no interval, ever
AircraftStateAudit.aircraft       = model.Property(f"{AircraftStateAudit:a} observed on {Aircraft:aircraft}")
AuditAssignment.event_date        = model.Property(f"{AuditAssignment:a} observed on {Date:event_date}")   # AH-05
AuditAssignment.row_sequence      = model.Property(f"{AuditAssignment:a} has row sequence {Integer:row_sequence}")   # AH-03
AuditAssignment.event_sequence    = model.Property(f"{AuditAssignment:a} has event sequence {Integer:event_sequence}") # AH-04
AuditAssignment.event             = model.Property(f"{AuditAssignment:a} came from {AircraftEvent:event}")  # AH-01
```
Multiplicity: `Aircraft -> assignments` is one-to-many and unconstrained. `assignment -> Aircraft` is
functional and enforced. Matches `SOURCE_CONTRACT.md:508` ("Aircraft to audit assignments,
one-to-many, association concept; never a functional property") because the *Aircraft-side* is the
one-to-many side and it is the `.alt()` reading, which adds no FD.

The AH-17 through AH-31 payload is eighteen separate Properties, not one bundle.
`rai-build-starter-ontology` SKILL, step 4: *"Each scalar attribute should be its own `Property` ...
Bundles become un-queryable: you can't filter or aggregate on a single field."*

### 2.2 `(AIRCRAFT)-[:CONFORMED]->(AIRCRAFT_TYPE)`

```python
AircraftTypeDaily.aircraft      = model.Property(f"{AircraftTypeDaily:a} applies to {Aircraft:aircraft}")
AircraftTypeDaily.aircraft_type = model.Property(f"{AircraftTypeDaily:a} conformed to {AircraftType:type}")
Aircraft.type_assignments = AircraftTypeDaily.aircraft.alt(f"{Aircraft:aircraft} has type assignment {AircraftTypeDaily:a}")
AircraftType.assignments  = AircraftTypeDaily.aircraft_type.alt(f"{AircraftType:type} assigned by {AircraftTypeDaily:a}")
```
`aircraft_type` is a `Property` and not a `Relationship` because the contract proved zero-or-one exact
target per dimension (`SOURCE_CONTRACT.md:510`). A `Property` is *at most one*, not exactly one, so an
unresolved gap is simply the absence of a value. That is precisely what P0-12.3 requires: the gap
opens without a fabricated node. Section 5.3 shows how the absence becomes `UNKNOWN_STATE`.

### 2.3 `(AIRCRAFT)-[:EQUIPPED]->(ENGINE_TYPE)`

Identical shape plus the two assignment-level payloads that must not migrate to the definition:
```python
EngineTypeDaily.engine_type               = model.Property(f"{EngineTypeDaily:a} equipped with {EngineType:engine}")
EngineTypeDaily.engine_count              = model.Property(f"{EngineTypeDaily:a} reports {Integer:engine_count}")            # AC-08
EngineTypeDaily.mixed_engine_set_complete = model.Property(f"{EngineTypeDaily:a} has complete mixed set {Boolean:mixed_engine_set_complete}")  # DV-09
```
`ATTRIBUTE_AUTHORITY.md:130-131` types AC-08 and AC-09 as `ENGINE_ASSIGNMENT_ATTRIBUTE`, and
`SOURCE_CONTRACT.md:146-147` explains why: they are configuration payload, not functional properties of
an engine-subseries identity. Putting `engine_count` on `EngineType` is a named failure mode; it would
also FDError as soon as two configurations report different counts for one subseries.

### 2.4 `(AIRCRAFT)-[:ASSIGNED]->(AIRCRAFT_STATUS)` plus provenance

```python
AircraftStatusDaily.status  = model.Property(f"{AircraftStatusDaily:a} assigned status {AircraftStatus:status}")
AircraftStatusAudit.status  = model.Property(f"{AircraftStatusAudit:a} observed status {AircraftStatus:status}")
AircraftStatusAudit.start_event  = model.Property(f"{AircraftStatusAudit:a} started by {String:start_event}")   # AH-08
AircraftStatusAudit.event_source = model.Property(f"{AircraftStatusAudit:a} sourced from {String:event_source}")# AH-12
```
The provenance stays on the assignment. This is the "edge carries provenance" case that a property
graph handles with edge attributes; in RAI the assignment concept is the edge, so provenance is just
two more Properties on it. No modelling loss.

### 2.5 `(ROUTE)-[:HAS]->(ROUTE_STATE)` - the multi-open case

```python
_state_route    = model.Property(f"{RouteState:state} covers {Route:route}")
_state_schedule = model.Property(f"{RouteState:state} versions {Schedule:schedule}")
RouteState.route    = _state_route
RouteState.schedule = _state_schedule
Route.states    = _state_route.alt(f"{Route:route} has state {RouteState:state}")
Schedule.states = _state_schedule.alt(f"{Schedule:schedule} has version {RouteState:state}")
```
Full argument in section 3.

### 2.6 `(ROUTE)-[:STARTS]->(AIRPORT)` and `(ROUTE)-[:ENDS]->(AIRPORT)`

Two same-type slots. Declare **two separate role-labelled Properties**, not one two-slot Relationship:
```python
Route.origin_airport      = model.Property(f"{Route:route} starts at {Airport:origin}")
Route.destination_airport = model.Property(f"{Route:route} ends at {Airport:destination}")
Route.origin_code_raw      = model.Property(f"{Route:route} has origin code {String:origin_code}")        # SS-10 raw
Route.destination_code_raw = model.Property(f"{Route:route} has destination code {String:destination_code}") # SS-11 raw
```
`rai-build-starter-ontology` SKILL, step 4, "Same-type-slot disambiguation": *"Without this,
`model.define(...)` will silently bind both slots to whichever column you list first, collapsing source
and destination into the same entity."* Two named Properties eliminate the risk entirely. The raw codes
stay as separate `String` Properties so a failed resolution still shows the code
(`SOURCE_CONTRACT.md:514`).

### 2.7 `(AIRLINE)-[:OPERATES]->(ROUTE_STATE)` and `(AIRLINE)-[:COMMERCIALIZES]->(ROUTE_STATE)`

```python
_op  = model.Property(f"{RouteState:state} operated by {Airline:operating_airline}")
_mkt = model.Property(f"{RouteState:state} marketed by {Airline:marketing_airline}")
RouteState.operating_airline = _op
RouteState.marketing_airline = _mkt
Airline.operates       = _op.alt(f"{Airline:operating_airline} operates {RouteState:state}")
Airline.commercializes = _mkt.alt(f"{Airline:marketing_airline} commercializes {RouteState:state}")
RouteState.operating_carrier_code_raw = model.Property(f"{RouteState:state} has operating code {String:operating_code}")  # SS-05
RouteState.marketing_carrier_code_raw = model.Property(f"{RouteState:state} has marketing code {String:marketing_code}")  # SS-04
```
Two Properties, never one `airline`. `ATTRIBUTE_AUTHORITY.md:376`: *"SS-04 and SS-05 are separate
carrier roles. No generic airline owner exists."* The `carrier_role` query parameter then selects which
Property a query traverses, and a missing role is a clarification state at the API boundary (P0-09.1).

### 2.8 `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)`

This one is a `Relationship`, not a `Property`:
```python
RouteState.schedules = model.Relationship(f"{RouteState:state} schedules {PassengerFlight:flight}")
```
`NEO4J_RAI_MAPPING.md:108` calls it "Potential one-to-many; no functional claim". One route state can
schedule many operating dates, and one passenger flight can be reachable from more than one knowledge
version of the same schedule key. Neither direction is functional, so `Relationship` is correct and a
`Property` here would FDError.

Derive it, do not import it. The rule is the conjunction P0-08 already specifies: exact schedule
identity where available (PH-02 = SS-01), passenger operating date inside inclusive SS-08/SS-09, and
matching weekday. Anything that fails the conjunction stays unlinked and visible.

### 2.9 `(AIRCRAFT_FLIGHT)-[:FULFILLED]->(PASSENGER_FLIGHT)`

The subtle one. `SOURCE_CONTRACT.md:515-516` gives asymmetric cardinality: passenger to actual is
zero-to-many, actual to passenger is zero-or-one in v1. So:
```python
_fulfils = model.Property(f"{AircraftFlight:leg} fulfilled {PassengerFlight:plan}")
AircraftFlight.fulfils   = _fulfils
PassengerFlight.fulfilled_by = _fulfils.alt(f"{PassengerFlight:plan} fulfilled by {AircraftFlight:leg}")
```
The FD `leg -> plan` is enforced. The inverse reading `plan -> legs` is unconstrained, so the stopover
case (one passenger flight, two aircraft flights) loads without error. This is the single cleanest
demonstration in the whole model that a `Property` plus `.alt()` gives you a directed FD with a free
inverse, which a property-graph edge cannot express without an out-of-band constraint.

Keep `ExactFulfillment` as a separate association concept anyway. It carries DV-39, the evidence, and
the sanity-check outcome, and P0-10.6 requires candidates to be stored separately from confirmed
fulfilment. The `_fulfils` Property is derived from `ExactFulfillment` only:
```python
model.define(AircraftFlight.fulfils(PassengerFlight)).where(
    ExactFulfillment.actual_flight == AircraftFlight,
    ExactFulfillment.passenger_flight == PassengerFlight,
)
```
`FulfillmentCandidate` never feeds `_fulfils`. That is the exact/heuristic separation, made structural.

### 2.10 `(AIRCRAFT_FLIGHT)-[:STARTED]->(AIRPORT)` and `[:ENDED]->(AIRPORT)`

Same two-role treatment as 2.6:
```python
AircraftFlight.actual_origin      = model.Property(f"{AircraftFlight:leg} started at {Airport:actual_origin}")
AircraftFlight.actual_destination = model.Property(f"{AircraftFlight:leg} ended at {Airport:actual_destination}")
AircraftFlight.actual_origin_code_raw      = model.Property(f"{AircraftFlight:leg} departed from code {String:origin_code}")      # AF-08
AircraftFlight.actual_continuity_arrival_code = model.Property(f"{AircraftFlight:leg} arrived at code {String:continuity_code}")  # DV-45 = AF-09
```
DV-45 is exactly AF-09 (`SOURCE_CONTRACT.md:358`). AF-10 and DV-53 are separate evidence Properties on
`RotationLinkValidation`; they never repair AF-09.

### 2.11 Next-flight self-reference

```python
AircraftFlight.next_flight_raw = model.Property(f"{AircraftFlight:leg} points to next {AircraftFlight:next_leg}")   # AF-20
AircraftFlight.next_flight     = model.Property(f"{AircraftFlight:leg} continues to {AircraftFlight:next_leg}")     # accepted only
```
Both are functional: `SOURCE_CONTRACT.md:517` says "Actual flight to next actual flight: zero-or-one
raw reference", and the accepted link is a subset of the raw one. In a `Property`, all fields except
the last are keys, so the FD is `leg -> next_leg`, which is what we want.

The two same-type slots **must** be role-labelled. Idiom confirmed in the checkout:
`PyRel/tests/end2end/unified/tests/recursion.py:6`
`edge = m.Relationship(f"{Node:src} has an edge to {Node:dst}")`, and
`PyRel/tests/end2end/unified/tests/containers_with_negation.py:5`
`Person.brother = m.Relationship(f"{Person:p} has {Person:brother}")`.

Bind the raw link with two `filter_by` lookups from the same source row so the target must already
exist (a missing target then produces no fact, which is the `MISSING_TARGET` anomaly, retained on
`RotationLinkValidation`):
```python
model.define(AircraftFlight.next_flight_raw(AircraftFlight.ref())).where(...)
```
Better, avoid `.ref()` ambiguity and go through `filter_by` on both ends:
```python
model.define(
    AircraftFlight.filter_by(flight_id=AF.flight_id)
        .next_flight_raw(AircraftFlight.filter_by(flight_id=AF.next_flight_id))
)
```
This is the `rai-pyrel-coding/references/data-loading.md` "Chained `filter_by`" pattern.

Then the accepted link is a rule, not a load:
```python
model.define(AircraftFlight.next_flight(nxt := AircraftFlight.ref())).where(
    AircraftFlight.next_flight_raw == nxt,
    AircraftFlight != nxt,
    AircraftFlight.aircraft == nxt.aircraft,
    AircraftFlight.flight_departure_date == nxt.flight_departure_date,
    nxt.actual_gate_departure_utc >= AircraftFlight.actual_gate_arrival_utc,
    nxt.actual_origin_code_raw == AircraftFlight.actual_continuity_arrival_code,
    model.not_(AircraftFlight.is_cancelled), model.not_(nxt.is_cancelled),
)
```
That is P0-11.4 transcribed one clause per line. This is the reusable rule the demo should show on
screen.

### 2.12 Rotation segments and leg order

Q08 needs `segment_id` and `leg_order`. The recursion idiom is in the checkout at
`PyRel/tests/end2end/unified/tests/recursion.py:19-25`:
```python
u, v, n = Node.ref(), Node.ref(), Node.ref()
define(
    distance(u, v, per(u, v).min(union(
        select(0).where(u == v),
        select(distance(u, n) + 1).where(edge(n, v)),
    ))),
)
```
Apply it directly. A segment head is a leg with no accepted predecessor; `leg_order` is the minimum
distance from that head over `next_flight`; `segment_id` is the head's `flight_id`. Because
`next_flight` is functional and validated (no self-loop, no cycle, same aircraft, same local date),
the closure terminates. `SEMANTIC_DECISIONS.md` P0-11.5 also requires a visited set and a finite step
bound; if the 1.20.1 recursion has no bound parameter, the guard is that cycles are excluded at the
`next_flight` acceptance rule, which is stronger. Cycle members still surface, from
`RotationLinkValidation` rows carrying DV-25, normalised to one `CYCLE` row per component at the
minimum `flight_id` (`DEMO_QUESTIONS.md:307`).

### 2.13 Summary table

| Neo4j edge | RAI construct | FD direction | Inverse |
|---|---|---|---|
| `AIRCRAFT -[:HAS]-> AIRCRAFT_STATE` | `Property` on daily assignment | assignment -> Aircraft | `.alt()` |
| `AIRCRAFT -[:CONFORMED]-> AIRCRAFT_TYPE` | `Property` on type daily assignment | assignment -> AircraftType | `.alt()` |
| `AIRCRAFT -[:EQUIPPED]-> ENGINE_TYPE` | `Property` on engine daily assignment | assignment -> EngineType | `.alt()` |
| `AIRCRAFT -[:ASSIGNED]-> AIRCRAFT_STATUS` | `Property` on status daily + audit assignment | assignment -> AircraftStatus | `.alt()` |
| `ROUTE -[:HAS]-> ROUTE_STATE` | `Property` `RouteState.route` | RouteState -> Route | `.alt()`, multi-open |
| `ROUTE -[:STARTS]-> AIRPORT` | `Property` `Route.origin_airport` | Route -> Airport | not needed |
| `ROUTE -[:ENDS]-> AIRPORT` | `Property` `Route.destination_airport` | Route -> Airport | not needed |
| `AIRLINE -[:OPERATES]-> ROUTE_STATE` | `Property` `RouteState.operating_airline` | RouteState -> Airline | `.alt()` |
| `AIRLINE -[:COMMERCIALIZES]-> ROUTE_STATE` | `Property` `RouteState.marketing_airline` | RouteState -> Airline | `.alt()` |
| `ROUTE_STATE -[:SCHEDULES]-> PASSENGER_FLIGHT` | `Relationship` | none | symmetric |
| `AIRCRAFT_FLIGHT -[:FULFILLED]-> PASSENGER_FLIGHT` | `Property` `AircraftFlight.fulfils` | leg -> plan | `.alt()`, one-to-many inverse |
| `AIRCRAFT_FLIGHT -[:STARTED]-> AIRPORT` | `Property` `actual_origin` | leg -> Airport | not needed |
| `AIRCRAFT_FLIGHT -[:ENDED]-> AIRPORT` | `Property` `actual_destination` | leg -> Airport | not needed |
| next-flight self-reference | `Property` with two labelled same-type slots | leg -> next_leg | not needed |

---

## 3. The multi-open route question

This is the demo's centrepiece, so the answer needs to be sharp rather than diplomatic.

### 3.1 What the customer is actually asking

Their model versions state by `(schedule_key, valid_from)` but hangs it off `ROUTE` via
`(ROUTE)-[:HAS]->(ROUTE_STATE)`. A generic SCD Type 2 builder has exactly one structural assumption:
for each parent key there is at most one row with an open `valid_to`. Their builder therefore has to
be made *grain-aware*: told that the partition is `schedule_key`, not the parent `route`. That is
configuration they have to get right, per relationship, and nothing in the graph schema records it.
Get it wrong and you either close states that should stay open, or you emit an integrity error on a
route that legitimately has six concurrent open schedules.

### 3.2 The answer

**In RAI there is nothing to relax, because there was never a constraint to relax.** The multi-open
shape is what you get by default; the single-open shape is what you would have to opt into. This
follows from two facts about 1.20.1 established in section 0.2:

1. There is no temporal or SCD machinery in the API at all, so no builder holds a
   one-open-per-parent invariant on your behalf.
2. Cardinality is declared per relationship and points one way. `Property` enforces "all fields except
   the last are keys" (`SD/frontend/base.py:3795`, `Property(Relationship)`). Nothing enforces the
   converse unless you write it.

The versioning partition is therefore not configuration at all. It is the identity of the state
concept:

```python
RouteState = model.Concept("RouteState", identify_by={"route_state_key": String})   # DV-13 = SS-01 || '|' || valid_from
```
`Route` does not appear in that identity. `Schedule` and the segment-opening knowledge date do. So the
partition is a structural, readable property of the ontology, sitting in one line that a reviewer can
check, rather than a parameter passed to a builder.

The interval is two functional scalars on the state, not attributes of an edge:
```python
RouteState.knowledge_valid_from = model.Property(f"{RouteState:state} known from {Date:knowledge_valid_from}")  # DV-14
RouteState.knowledge_valid_to   = model.Property(f"{RouteState:state} known to {Date:knowledge_valid_to}")      # DV-15
```
Both are `Property` because each state has exactly one of each. That FD is correct and desirable and
has nothing to do with how many states a route has.

And the parent link points from the state to the route, which is the functional direction:
```python
_state_route = model.Property(f"{RouteState:state} covers {Route:route}")
RouteState.route = _state_route
Route.states     = _state_route.alt(f"{Route:route} has state {RouteState:state}")
```
`Route.states` is the Neo4j `HAS` edge, recovered exactly, and it carries **no** cardinality claim,
because `.alt()` adds a reading over the same fields (`SD/frontend/base.py:3365`).

"How many states are open on this route right now" is then a query, not a schema decision:
```python
from relationalai.semantics.std import aggregates as aggs
OPEN = dt.date(9999, 1, 1)

open_per_route = model.where(
    RouteState.route == Route,
    RouteState.knowledge_valid_to == OPEN,
).select(
    Route.route_id,
    aggs.count(RouteState).per(Route).alias("open_states"),
).to_df()
```
This returns rows with `open_states > 1` and raises nothing. That is HT-18
(`SEMANTIC_DECISIONS.md:458`, "One route has multiple valid concurrent states without uniqueness
failure") satisfied by construction rather than by exception handling.

### 3.3 The mirror-image failure, and why the demo should show it

The failure the customer fights is one line away, and it is worth showing on screen in a throwaway
model:
```python
# WRONG. Do not put this in the ontology.
Route.current_state = model.Property(f"{Route:route} has state {RouteState:state}")
```
That declares `Route -> RouteState` functional. `rai-ontology-design` SKILL, Common Pitfalls:
*"`FDError: Found non-unique values` ... Used `Property` for a many-to-many association"*. The very
first route with two concurrent open states raises it at define time, before any query runs. That is
the same class of bug as an over-eager SCD builder, but RAI surfaces it as a named error at model
build with the offending values, instead of as silently closed rows in a warehouse table.

The demo beat is: same mistake possible in both systems, but here it fails loudly and locally, and the
correct declaration is a single reversed arrow rather than a builder configuration.

### 3.4 What we do assert, and where

The contract does have real uniqueness claims, and they should be asserted rather than assumed.
`SD/std/constraints.py:33` `unique(*args)`; the idiom for "this slot determines the rest" is in the
checkout at `PyRel/tests/end2end/unified/tests/functional_dependencies.py:34`
`require(unique(Car.owner[Car]))`.

```python
from relationalai.semantics.std.constraints import unique
model.require(unique(RouteState.route[RouteState]))              # a state has one route
model.require(unique(RouteState.schedule[RouteState]))           # a state has one schedule
model.require(unique(RouteState.marketing_airline[RouteState]))  # zero-or-one exact marketing link
model.require(unique(RouteState.operating_airline[RouteState]))  # zero-or-one exact operating link
# DELIBERATELY ABSENT, and this comment must survive into the source file:
#   there is no unique(...) over the Route slot of Route.states.
#   SOURCE_CONTRACT.md:511 - "one-open-per-route constraint is prohibited".
```
Note that these `require(unique(...))` calls are redundant with the FD that `Property` already
enforces. Their value is documentary: they put the multiplicity gate from `SOURCE_CONTRACT.md:505-518`
into the model where a reviewer sees it, and the absent one is as informative as the present ones.
See section 8 item U-06: they may need `emit_constraints: True` on the logic reasoner to be checked at
runtime.

### 3.5 One honest limitation

RAI cannot *express* "this route may have many concurrent open states" as a positive assertion. There
is no negative-constraint or minimum-cardinality vocabulary in `SD/std/constraints.py` (`unique`,
`exclusive`, `anyof`, `oneof` are the whole set). The property is proved by a query returning
`open_states > 1`, which is what HT-18 asks for, not by a declaration. Say so plainly rather than
implying RAI declares something Neo4j cannot.

---

## 4. Functional versus multi-valued, with the evidence for each

The rule: `Property` when the association is many-to-one, `Relationship` when it is many-to-many.
`Property` is strictly better where it is true (it enforces the FD at define time and is faster), and
strictly wrong where it is not (it FDErrors). `SOURCE_CONTRACT.md:546` is binding here: *"MODEL-01 may
use a functional Property only after the multiplicity gate above passes."*

### 4.1 Safe as `Property` today, gate already in the contract

| Association | Gate |
|---|---|
| `Aircraft.*` master scalars, `existence_from`, `existence_to` | `SOURCE_CONTRACT.md:507` "Duplicate AM-01 is a hard source gate failure" |
| `AircraftEvent.*` scalars | AH-01 declared key, `SOURCE_CONTRACT.md:63` |
| `DailyAssignment.aircraft`, `.dimension`, `.valid_from`, `.valid_to`, `.assignment_id`, `.resolution_status`, `.query_status` | `SOURCE_CONTRACT.md:509` "zero-or-one final relevant observation ... duplicate winner is a hard failure" |
| `AuditAssignment.*` scalars and `.event` | DV-04 is the declared grain, `SOURCE_CONTRACT.md:440` |
| `AircraftTypeDaily.aircraft_type`, `EngineTypeDaily.engine_type` | `SOURCE_CONTRACT.md:510` "zero-or-one exact target per dimension" |
| `EngineTypeDaily.engine_count`, `.mixed_engine_set_complete` | one configuration per assignment |
| `RouteState.route`, `.schedule`, all four clock dates, all SS-04..SS-38 watched content | `ROUTE_STATE` grain is `route_state_key`, `SOURCE_CONTRACT.md:448` |
| `RouteState.marketing_airline`, `.operating_airline` | `SOURCE_CONTRACT.md:512-513` |
| `Route.origin_airport`, `.destination_airport`, raw codes | `SOURCE_CONTRACT.md:514` |
| `AircraftFlight.*` actual scalars, `.aircraft`, `.actual_origin`, `.actual_destination`, `.next_flight_raw`, `.next_flight`, `.fulfils` | AF-01 grain, `SOURCE_CONTRACT.md:516-517` |
| `PassengerFlight.*` plan scalars | DV-20 grain, `SOURCE_CONTRACT.md:454` |
| `CodeResolution.*` scalars incl. DV-10, DV-11 | `resolution_id` grain, `SOURCE_CONTRACT.md:444` |
| `RotationLinkValidation.*` DV-24, DV-25 evidence | `(AF-01, target_token)` grain, `SOURCE_CONTRACT.md:462` |

### 4.2 Must be `Relationship`, multi-valued

| Association | Why |
|---|---|
| `Route.states` (`.alt()` of `RouteState.route`) | many concurrent open, `SOURCE_CONTRACT.md:511`. Not a separate declaration, just an inverse reading with no FD. |
| `Schedule.states` | one schedule key, many knowledge versions over time |
| `Aircraft.state_assignments`, `.type_assignments`, `.engine_assignments`, `.status_assignments`, `.audit_assignments` | one-to-many, `SOURCE_CONTRACT.md:508`. Inverse readings. |
| `PassengerFlight.fulfilled_by` | zero-to-many confirmed legs, `SOURCE_CONTRACT.md:515`. Inverse reading. |
| `RouteState.schedules` (`SCHEDULES` edge) | genuinely many-to-many, `NEO4J_RAI_MAPPING.md:108`. Real `Relationship`. |
| `CodeResolution.candidates` | zero/one/many, `SOURCE_CONTRACT.md:518`. Real `Relationship` to `CodeResolutionCandidate`. |
| `RouteState.lineage` | many contributing snapshots per coalesced state, `SOURCE_CONTRACT.md:449` |
| `RouteState.operates_on_weekday` | up to seven values per state, section 6.2. Real `Relationship`. |
| `ScheduleAmendmentGroup.members`, `FulfillmentAmbiguousGroup.members` | many members by definition |
| `PassengerFlight.lineage` | historical and forward lineage both retained, `SOURCE_CONTRACT.md:455` |
| `AircraftEvent.audit_assignments` | one event can mint assignments in several dimensions |

### 4.3 Needs a proof before the `Property` is written

These are the ones that will bite. Each has its exact test.

**G-01. `AircraftType` definition attributes (AC-02, AC-03, AC-04, AC-06, AC-07) keyed on AC-05.**
`SOURCE_CONTRACT.md:144-146` explicitly requires this proof and it is not yet run.
```sql
SELECT aircraft_subseries, COUNT(*) AS defs
FROM (SELECT DISTINCT aircraft_subseries, aircraft_family, aircraft_type,
                      aircraft_series, aircraft_manufacturer, aircraft_design_class
      FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_CONFIGURATION
      WHERE aircraft_subseries IS NOT NULL)
GROUP BY 1 HAVING COUNT(*) > 1;
```
Zero rows means `Property` is safe. Any row means those five become `Relationship` and Q01's
`aircraft_type` label becomes ambiguous, which is a DATA-01 fixture bug, not a modelling choice.

**G-02. `EngineType` definition attributes (AC-10..AC-13, AC-15) keyed on AC-14.** Same query over the
engine columns. Note AC-08 and AC-09 are deliberately *excluded* from this proof, per section 2.3.

**G-03. `Airport` attributes keyed on AP-01.** This one will fail as written.
`SOURCE_CONTRACT.md:376` gives the source grain as `(airport_id, effective_start_date)`, but
`NEO4J_RAI_MAPPING.md:42` sets v1 identity to `airport_id` alone. Two effective periods with different
`airport_name` or `airport_code_iata` for the same `airport_id` make `Airport.name` non-functional and
it will FDError at define time.
```sql
SELECT airport_id, COUNT(DISTINCT airport_name), COUNT(DISTINCT airport_code_iata),
       COUNT(DISTINCT airport_code_icao), COUNT(DISTINCT time_zone_name)
FROM PK_AVIATION_TEMPORAL.SOURCE.AIRPORT_REFERENCE
GROUP BY 1 HAVING MAX(1) = 1 AND (COUNT(DISTINCT airport_name) > 1
   OR COUNT(DISTINCT airport_code_iata) > 1 OR COUNT(DISTINCT airport_code_icao) > 1
   OR COUNT(DISTINCT time_zone_name) > 1);
```
Recommended fix regardless of the result, because it is robust to a later fixture change: **DATA-04
materialises `MODEL_INPUT.AIRPORT_CURRENT`, one deterministically chosen row per AP-01**, and the full
multi-period rows stay as a separate `AirportReferenceLineage` association bound from
`SOURCE.AIRPORT_REFERENCE`. `ATTRIBUTE_AUTHORITY.md:301-303` already licenses this: reference effective
periods are retained for provenance, identity is `airport_id`, and `is_current`/`is_active` never
silently pick a winner, so the projection rule must be a declared deterministic order rather than
`WHERE is_current`.

**G-04. `Airline` attributes keyed on AL-01.** Identical, over AL-04 through AL-07 and AL-08.
Same `MODEL_INPUT.AIRLINE_CURRENT` fix.

**G-05. `PassengerFlight.schedule_key` (PH-02).** One canonical `PassengerFlight` (DV-20) can absorb
several PH lineage rows (`SOURCE_CONTRACT.md:458`, "Multiple historical lineage rows coalescing to one
DV-20"). If two of them carry different PH-02, a `Property` FDErrors.
```sql
SELECT passenger_flight_key, COUNT(DISTINCT schedule_key)
FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.PASSENGER_SOURCE_LINEAGE
WHERE schedule_key IS NOT NULL GROUP BY 1 HAVING COUNT(DISTINCT schedule_key) > 1;
```
Until this is green, declare `PassengerFlight.schedule_key` as a `Relationship` and select through it
with an explicit `distinct`. Alternatively bind the `Property` only from the precedence-winning
lineage row (DV-21), which is the option I recommend because it matches P0-10.3.

**G-06. `AircraftFlight.aircraft` (AF-02).** Functional by construction, but the *inverse*
`Aircraft.actual_flights` must be a `Relationship`. Cheap to confirm, easy to get backwards.

**G-07. `AircraftStatus` has no attributes at all.** Do not add a display label. The identity is the
raw AH-09 string with no normalisation (`NEO4J_RAI_MAPPING.md:37`), and adding a normalised label
would be the first step toward the trim-and-case-fold the contract forbids.

### 4.4 `Schedule` is identity-only

Tempting to hang SS-02 `schedule_key_readable` on it. Do not. SS-02 is per-observation lineage
(`ATTRIBUTE_AUTHORITY.md:145`) and can legitimately differ across snapshots for the same key, so a
`Property` on `Schedule` would FDError. It belongs on `RouteState` or on the lineage association.

### 4.5 The single generic rule for the orchestrator

When multiplicity is genuinely unknown at write time, declare a `Relationship`, run the model, then
run the FD probe and *tighten* to `Property`. Going the other way is expensive: the model is
append-only (`rai-pyrel-coding` SKILL), so you cannot demote a `Property` in place; you rebuild the
model under a fresh name. Tighten late, never loosen.

---

## 5. Half-open intervals, sentinels, and same-day ordering

### 5.1 The half-open predicate

There is no interval type (section 0.2a). Every point-in-time test is literally two comparisons:

```python
# rai_code/aviation_model/temporal.py
def visible_on(assignment, d):
    """Half-open validity: valid_from <= d < valid_to.  P0-02.1 / BRIEF.md:85."""
    return (assignment.valid_from <= d, d < assignment.valid_to)

def within_existence(aircraft, d):
    """P0-03.2: existence_from <= d < existence_to, EOL exclusive under D-0003."""
    return (aircraft.existence_from <= d, d < aircraft.existence_to)
```
Used as `model.where(*visible_on(AircraftTypeDaily, as_of), *within_existence(Aircraft, as_of))`.

Two things make this safe. First, DATA-04 guarantees `valid_to` is never null: `SOURCE_CONTRACT.md:437`
and `:441` both say the open case is written as the model sentinel, not as NULL. So the `<` needs no
null guard, and a missing upper bound cannot silently drop a row. Second, `visible_on` is a Python
helper, not a model rule, so it cannot materialise a cross product of assignments and dates.

Do **not** try to make `visible_on` a model `Relationship` over `(assignment, Date)`. `Date` is a core
concept with an unbounded extension; the rule would be ungrounded or explode. The one place a
materialised as-of rule is correct is where the date set is already bounded by an entity, and there
that rule should absolutely live in the model. Section 5.5 and section 2.12 give the two cases.

### 5.2 Sentinel separation

```python
# rai_code/aviation_model/constants.py
import datetime as dt
MODEL_OPEN_INTERVAL   = dt.date(9999, 1, 1)   # derived only. BRIEF.md:86, P0-02.6
SOURCE_UNKNOWN_FUTURE = dt.date(9999, 12, 31) # must never reach the model. P0-02.5
```
The separation is enforced by construction, not by convention:

- `9999-12-31` is normalised away by DATA-04 before RAI sees it. A source date equal to the sentinel
  becomes NULL plus a companion `*_is_unknown_future BOOLEAN` column.
- In RAI, "unknown future" therefore appears as **absence of a value** plus a unary flag:
  ```python
  Aircraft.order_date = model.Property(f"{Aircraft:ac} was ordered on {Date:order_date}")
  Aircraft.order_date_unknown_future = model.Relationship(f"{Aircraft:ac} has unknown-future order date")
  ```
  Unary `Relationship` for the flag follows `rai-ontology-design` SKILL Quick Reference
  ("Boolean flag? Unary Relationship").
- `9999-01-01` appears only as a derived `valid_to` / `knowledge_valid_to`, always bound from the
  DATA-04 column, and is referenced in RAI only through `MODEL_OPEN_INTERVAL`.
- The guard against leakage is a derived flag plus a zero-count assertion, since RAI has no negative
  constraint vocabulary:
  ```python
  SentinelLeak = model.Relationship(f"{DailyAssignment:a} leaked source sentinel")
  model.define(SentinelLeak(DailyAssignment)).where(
      DailyAssignment.valid_to == SOURCE_UNKNOWN_FUTURE)
  # test asserts model.select(aggs.count(DailyAssignment).where(SentinelLeak(DailyAssignment))) is empty
  ```
  This is HT-06 (`SEMANTIC_DECISIONS.md:446`) in RAI form.
- `AH-06 end_event_date` is bound as a plain provenance `Property` on `AuditAssignment` and never
  participates in any interval predicate. HT-07 compares it to the derived `valid_to` and surfaces
  disagreement without changing anything, which is one derived flag:
  ```python
  EndEventDisagreement = model.Relationship(f"{DailyAssignment:a} disagrees with source end date")
  ```

### 5.3 DV-33 query status as an ordered match chain

`SOURCE_CONTRACT.md:466-470` fixes four mutually exclusive outcomes in a strict order. The 1.20.1
construct is the ordered `|` fallback, whose semantics are documented in
`rai-pyrel-coding` SKILL, RAI Expression Syntax: *"The `|` operator is an ordered fallback (picks the
first branch that succeeds, if-then-else semantics)"*, with a worked multi-value example at
`PyRel/tests/end2end/unified/tests/conditions.py:80-85`:
```python
age_group, coolness = (
    where(Person.age >= 65).select("Senior", 1000) |
    where(Person.age >= 18).select("Adult", 0) |
    select("Child", 10000000)
)
```
Applied, for one dimension and one as-of date, inside a query function:
```python
status, = (
    model.where(model.not_(*within_existence(Aircraft, d))).select("OUTSIDE_EXISTENCE") |
    model.where(*visible_on(AircraftTypeDaily, d),
                AircraftTypeDaily.aircraft == Aircraft,
                AircraftTypeDaily.aircraft_type == AircraftType).select("OK") |
    model.where(*visible_on(AircraftTypeDaily, d),
                AircraftTypeDaily.aircraft == Aircraft).select("UNKNOWN_STATE") |
    model.select("NO_RECORDED_STATE")
)
```
The third branch is reached when a daily assignment covers the date but has no resolved
`aircraft_type`, which is exactly P0-02.8's `UNKNOWN_STATE` gap, and it works precisely because
`aircraft_type` is a `Property` (at most one, possibly zero) rather than a required field. The
fourth branch is the inside-existence, before-first-assignment case.
All four `|` branches return one value, satisfying the "same shape" rule in
`rai-pyrel-coding` SKILL (*"All `union()` branches must return the same number of values"*).

Q01's `is_complete` is then `all four statuses == "OK"`, computed at the query layer from those four
values. Do not materialise a composite completeness Property on `Aircraft`; it is date-dependent.

### 5.4 Same-day ordering: date plus sequence plus source history ID, never date alone

Three layers.

**Structural.** `AuditAssignment`'s compound identity (section 1.3) contains `event_date`,
`row_sequence` and `event`. Two same-day observations are two entities, permanently. HT-01
(`SEMANTIC_DECISIONS.md:441`, "Three same-day events yield three stable audit keys after two clean
generations/reloads") holds because `identify_by` hashes the same components on every load
(`SD/frontend/base.py:6602`, "entities with the same key values are the same instance").

**Ordering.** `aggregates.rank` with multiple `asc()` keys, per aircraft, within a dimension subtype:
```python
from relationalai.semantics.std import aggregates as aggs
AircraftStatusAudit.seq = model.Property(f"{AircraftStatusAudit:a} has sequence {Integer:seq}")
model.define(AircraftStatusAudit.seq(
    aggs.rank(aggs.asc(AircraftStatusAudit.event_date),
              aggs.asc(AircraftStatusAudit.row_sequence),
              aggs.asc(AircraftStatusAudit.event_sequence),
              aggs.asc(AircraftStatusAudit.event.id))
        .per(AircraftStatusAudit.aircraft)))
```
That is DV-03 (`ATTRIBUTE_AUTHORITY.md:316`) as a materialised model Property. Idiom confirmed at
`PyRel/tests/end2end/unified/tests/rank1.py:45` `rank(Person.name, Person.age).per(Person.team)` and
`rank1.py:112` `m.where(rank := rank(asc(...))).define(Item.dense_rank1(rank))`.

Once `seq` exists, Q02's spell pairing is a self-join on adjacent ranks, and because the audit stream
is already consecutive-equality-suppressed by DATA-04 (`SOURCE_CONTRACT.md:116`), "the next qualifying
In Service" is exactly `seq + 1`:
```python
nxt = AircraftStatusAudit.ref()
model.where(
    AircraftStatusAudit.status.code == "Storage",
    nxt.aircraft == AircraftStatusAudit.aircraft,
    nxt.seq == AircraftStatusAudit.seq + 1,
    nxt.status.code == "In Service",
).select(
    AircraftStatusAudit.event.id.alias("storage_event_id"),
    AircraftStatusAudit.event_date.alias("storage_start_date"),
    AircraftStatusAudit.row_sequence.alias("storage_start_sequence"),
    nxt.event.id.alias("return_event_id"),
    nxt.event_date.alias("return_date"),
    nxt.row_sequence.alias("return_sequence"),
    std.datetime.date.diff("day", AircraftStatusAudit.event_date, nxt.event_date).alias("storage_days"),
    (AircraftStatusAudit.event_date == nxt.event_date).alias("same_day"),
)
```
`date.diff` idiom at `PyRel/tests/end2end/unified/tests/date_diff.py:40`. The zero-day same-day spell
(P0-01.8, NF-A02) survives because `same_day` is computed from the two dates and `storage_days` comes
out 0, and because the two audit entities are distinct even though their dates match.
`.ref()` here is genuinely required: two independent variables over the same concept
(`rai-pyrel-coding` SKILL, "When `.ref()` is genuinely needed: ... self-joins inside aggregates").

**Date visibility.** The daily projection is selected upstream by DATA-04
(`SOURCE_CONTRACT.md:441`, "Final relevant observation for aircraft/dimension/date"). RAI does not
re-derive it. HT-02 then becomes a comparison between the audit stream's maximum-`seq` row on a date
and the daily assignment for that date, which is a test, not a rule.

### 5.5 Bounded as-of joins that *should* be model rules

Two, and only two.

**Q03 month ends.** Bind `MODEL_INPUT.MONTH_END_CALENDAR` to a `MonthEnd` concept and materialise:
```python
InServiceOnMonthEnd = model.Relationship(
    f"{Aircraft:ac} is in service on {MonthEnd:m} as {AircraftType:type}")
model.define(InServiceOnMonthEnd(Aircraft, MonthEnd, AircraftType)).where(
    Aircraft.existence_from <= MonthEnd.month_end, MonthEnd.month_end < Aircraft.existence_to,
    AircraftStatusDaily.aircraft == Aircraft,
    AircraftStatusDaily.valid_from <= MonthEnd.month_end, MonthEnd.month_end < AircraftStatusDaily.valid_to,
    AircraftStatusDaily.status.code == "In Service",
    AircraftTypeDaily.aircraft == Aircraft,
    AircraftTypeDaily.valid_from <= MonthEnd.month_end, MonthEnd.month_end < AircraftTypeDaily.valid_to,
    AircraftTypeDaily.aircraft_type == AircraftType,
)
```
This is the demo's headline reusable temporal rule: the type clock and the status clock are two
independent half-open joins in one rule, visibly not aligned to each other. Q03 is then
`aggs.count(Aircraft).per(MonthEnd, AircraftType)`.

Prefer a DATA-04 table over `std.datetime.date.range(..., freq="M")` for the calendar. The range
function exists (`SD/std/datetime.py:410`) and `freq="M"` is supported, and
`PyRel/tests/end2end/unified/tests/date_ranges.py:30` shows month stepping, but month-end arithmetic
from a 31st anchor depends on clamping behaviour I have not been able to verify offline, and Q03
requires exactly 120 rows (`DEMO_QUESTIONS.md:142`). A table is deterministic and testable in SQL.
Keep `date.range` as an independent cross-check in the notebook, which is a nice demo beat in itself.

**Q08 leg enrichment.** The date set is bounded by `AircraftFlight` rows, so no calendar is needed:
```python
model.define(AircraftFlight.as_of_aircraft_type(AircraftType)).where(
    AircraftFlight.aircraft == Aircraft,
    AircraftTypeDaily.aircraft == Aircraft,
    AircraftTypeDaily.valid_from <= AircraftFlight.flight_departure_date,
    AircraftFlight.flight_departure_date < AircraftTypeDaily.valid_to,
    AircraftTypeDaily.aircraft_type == AircraftType,
)
```
Same for `as_of_engine_type`. `AircraftFlight.flight_departure_date` is AF-06, the *local* selected-day
basis (`ATTRIBUTE_AUTHORITY.md:261`), never AF-07. `type_discrepancy` is then a derived flag comparing
`as_of_aircraft_type` against AF-17, which stays `ACTUAL_DESCRIPTION` and never overwrites
(`ATTRIBUTE_AUTHORITY.md:272`).

Both of these should be `Property` where the FD holds. `as_of_aircraft_type` is functional per leg
(one leg, one date, one aircraft, one type), so declare it `Property` and let RAI check it. If it
FDErrors, the daily assignments overlap and that is a DATA-04 bug the model has just found for you.

---

## 6. Keeping both schedule clocks separately queryable

### 6.1 Four scalars, two pairs, never merged

```python
RouteState.knowledge_valid_from      = model.Property(f"{RouteState:s} known from {Date:knowledge_valid_from}")   # DV-14, inclusive
RouteState.knowledge_valid_to        = model.Property(f"{RouteState:s} known to {Date:knowledge_valid_to}")       # DV-15, EXCLUSIVE
RouteState.operating_effective_date  = model.Property(f"{RouteState:s} effective from {Date:effective_date}")     # SS-08, inclusive
RouteState.operating_discontinue_date= model.Property(f"{RouteState:s} discontinued on {Date:discontinue_date}")  # SS-09, INCLUSIVE
```
The asymmetry is the point and must be visible in the property names and in a comment beside them.
P0-02.3/02.4 and `SOURCE_CONTRACT.md:26-27`: knowledge is half-open, operating is inclusive on both
ends. `SEMANTIC_DECISIONS.md:246`: *"Knowledge `valid_to` is excluded; source operating
`discontinue_date` is included."* A single generic `visible_on` helper applied to both would silently
convert the operating upper bound to exclusive and break nine of the HT-23 truth-table rows. Give them
two distinct helpers with different names:
```python
def known_on(state, knowledge_date):
    return (state.knowledge_valid_from <= knowledge_date, knowledge_date < state.knowledge_valid_to)

def operates_on(state, operating_date, weekday):
    return (state.operating_effective_date <= operating_date,
            operating_date <= state.operating_discontinue_date,      # inclusive, deliberately
            state.operates_on_weekday(weekday))
```

### 6.2 The weekday predicate

Declare the weekday as a multi-valued `Relationship` derived from the seven booleans, so the predicate
is one join instead of a seven-branch match:
```python
RouteState.operates_on_weekday = model.Relationship(f"{RouteState:s} operates on weekday {Integer:weekday}")
model.define(RouteState.operates_on_weekday(1)).where(RouteState.is_operating_monday)
# ... 2..7 for Tuesday through Sunday, ISO numbering
```
Keep the seven raw booleans as unary `Relationship`s as well (SS-14..SS-20 are watched content, so
Q05 must emit them field by field with old and new values). This is not redundancy for its own sake:
one form serves change detection, the other serves the operating predicate.

Compute the weekday integer in Python from the query parameter, `operating_date.isoweekday()`, not in
RAI. It removes any doubt about the day-numbering convention of a RAI date part function, and
`operating_date` is a required typed parameter anyway.

### 6.3 Both clocks required, enforced where RAI cannot

RAI has no notion of a required query parameter. P0-08.3, HT-24 and `SOURCE_CONTRACT.md:494` all
demand that capacity and frequency fail when either clock is missing. The enforcement point is the
query function signature plus an explicit validation step:
```python
@dataclass(frozen=True)
class QueryExecutionContext:
    carrier_role: Literal["marketing", "operating"]   # DV-29
    knowledge_date: dt.date                            # DV-30
    operating_date: dt.date                            # DV-31
```
No defaults anywhere in the chain, validated before the first RAI call, and echoed into every result
frame so `EXPECTED_ANSWERS.yaml`'s Q07 `knowledge_date` / `operating_date` / `carrier_role` output
columns come from the same object that gated execution. Flagged as the deliberate deviation from
`NEO4J_RAI_MAPPING.md:68` in section 1.2.

### 6.4 The Q07 capacity chain

Carrier role selects which Property to traverse:
```python
airline_link = RouteState.marketing_airline if ctx.carrier_role == "marketing" else RouteState.operating_airline
```
For `operating`, add the D-0007 base-representative filter (`SOURCE_CONTRACT.md:496-498`): non-codeshare
and marketing carrier resolving to the same airline as operating. Everything else is
`UNRESOLVED_PHYSICAL_SERVICE`, kept and excluded, never guessed. Model that as a derived unary flag on
`RouteState` so the rule lives in the ontology rather than in eight query functions:
```python
RouteState.is_physical_representative = model.Relationship(f"{RouteState:s} is physical service representative")
model.define(RouteState.is_physical_representative()).where(
    model.not_(RouteState.is_codeshare),
    RouteState.marketing_airline == RouteState.operating_airline,
)
```
Cabin derivation DV-26 is also a model rule, with DV-27 as its quality flag:
```python
RouteState.economy_excluding_premium = model.Property(f"{RouteState:s} has {Float:economy_excluding_premium}")
model.define(RouteState.economy_excluding_premium(
    RouteState.economy_class_seats - RouteState.premium_economy_seats))
```
Raw SS-30 through SS-34 stay bound and untouched (P0-09.6, "Source totals are never silently
overwritten").

---

## 7. Module layout and build order

Directory name `aviation_model/` deliberately differs from the `model` variable, per
`rai-build-starter-ontology` SKILL: *"Never name the directory `model/` if your `Model` variable is
also called `model`."*

```
rai_code/aviation_model/
    __init__.py            re-exports `model` and every Concept. No logic.
    config.py              _build_config(): strict mode, local vs Snowsight
    constants.py           sentinels, dimension tokens, status tokens, carrier roles, DB path
    sources.py             every model.Table() with an explicit schema= dict
    core_reference.py      Airport, Airline, CodeResolution, CodeResolutionCandidate, SnapshotDate
    core_aircraft.py       Aircraft, AircraftEvent, AircraftConfiguration, AircraftType,
                           EngineType, AircraftStatus, audit + daily assignments, quarantine
    core_schedule.py       Schedule, Route, RouteState, lineage, ScheduleComparison,
                           ScheduleExactChange, amendment candidate/group/member
    core_flight.py         PassengerFlight, lineage, invalid, quarantine, AircraftFlight,
                           ExactFulfillment, FulfillmentCandidate, ambiguous group + member,
                           RotationLinkValidation
    calendar.py            MonthEnd
    temporal.py            visible_on, within_existence, known_on, operates_on. Pure helpers.
    computed_aircraft.py   dimension subtypes, DV-03 seq ranks, sentinel/AH-06 guards
    computed_schedule.py   weekday relationship, physical representative, DV-26/27, market grain
    computed_rotation.py   accepted next_flight, segments, leg_order, as-of type/engine enrichment
    constraints.py         require(unique(...)) gates + the documented absent one
    inventory.py           inspect.schema(model) dump for MODEL-01 exit and MODEL-02 parity
```

Build in this order, and get each step green before starting the next.

1. **`config.py`.** Strict mode is a hard MODEL-01 requirement and must be on from the first line of
   code, because implicit properties would otherwise mask every typo silently. Set it programmatically
   rather than through `raiconfig.yaml`, because MODEL-02 needs a standalone file that runs in
   Snowsight where no yaml is discoverable:
   ```python
   cfg = create_config(model={"implicit_properties": False})     # relationalai/config/config_fields.py:322
   ```
   `create_config` signature at `relationalai/config/config.py:794`; the `ModelConfig.implicit_properties`
   field defaults to `True` at `relationalai/config/config_fields.py:322`, so it must be set explicitly.
   Also pin `reasoners.logic.name` to the warm `aviation_temporal_logic_xs` engine, per the
   `rai-build-starter-ontology` SKILL pitfall about a five-to-ten-minute cold start. Handle both
   runtimes in one function: `ConfigFromActiveSession`
   (`relationalai/config/config.py:665`) when a Snowpark active session exists, `create_config()`
   otherwise.

2. **`constants.py`.** Nothing depends on a database call. Freeze the two sentinels, the four dimension
   tokens, the four DV-33 status tokens, the two carrier roles, and the fully qualified schema prefix
   as one constant so MODEL-02's standalone generation has one string to rewrite.

3. **`sources.py`.** Every `model.Table()` with an explicit `schema=` dict, types taken from the
   `Snowflake type` column of `SOURCE_CONTRACT.md` through the 1.20.1 mapping in section 0.2. This is
   the file that fails first and loudest if DATA-03 drifted, which is what you want.

4. **`core_reference.py` before `core_aircraft.py` and `core_schedule.py`.** `Airport` and `Airline`
   are the targets of exact links from three other modules, and Python needs the Concept objects to
   exist before the f-string readings interpolate them.

5. **`core_aircraft.py`.** UC1 is the independently runnable fallback (`AGENTS.md:50`, HT-46). Get
   Aircraft, events, definitions and both assignment layers loading and counting before touching UC2 at
   all. If UC2 is red at the end, this module plus `temporal.py` and `computed_aircraft.py` still
   ships.

6. **`core_schedule.py`, then `core_flight.py`.** Schedule first because `PassengerFlight` links to
   `Schedule` via PH-02.

7. **`calendar.py`, `temporal.py`.** Pure, no dependencies beyond constants and the concepts.

8. **`computed_*.py`.** Subtypes, ranks, derived flags, as-of enrichment. This is where the demo's
   actual RAI content lives; everything above it is plumbing.

9. **`constraints.py` last**, because a `require` over a concept that has not loaded yet gives a
   confusing error, and because the FD probes in section 4.3 should have run against live data by now.

10. **`inventory.py`.** `inspect.schema(model)` (`SD/inspect.py:943`) dumped to
    `build/design/ontology_inventory.json`. MODEL-01's exit criterion names it, and MODEL-02's parity
    test diffs the package's dump against the standalone file's dump.

Two structural rules to hold throughout. Define every model object at module scope, not inside a
function (`rai-pyrel-coding` SKILL, Code Structure). And never call `model.define()` inside a Python
loop over rows; PyRel warns after fifty calls from one call site (`SD/frontend/base.py:6338`). The only
legitimate loops are over the seven weekday booleans and the four dimension tokens, which are seven and
four, not fifty.

---

## 8. What I am not sure about, and the exact test for each

I cannot run live code. Each item below is a small script the orchestrator can run in minutes, and each
one changes the design if it comes back the wrong way. Run U-01 through U-04 before writing any
ontology code; they are cheap and two of them are structural.

**U-01. Does attribute access on a `model.Table()` work under strict mode without an explicit schema?**
My reading of `SD/frontend/base.py:2472` (lazy `_columns`), `:2537` (`__getitem__` triggers it), `:1531`
(`Concept.__getattr__` does not) and `:1439` (strict mode returns `None`, then `:1508` raises) says no.
If I am right, R1 in section 1.1 is mandatory rather than merely preferred.
```python
cfg = create_config(model={"implicit_properties": False})
m = Model("probe_u01", config=cfg)
t = m.Table("PK_AVIATION_TEMPORAL.MODEL_INPUT.AIRCRAFT_ELIGIBLE")   # no schema=
print(t.aircraft_id)        # expect: RAIException "Implicit property"
print(t["AIRCRAFT_ID"])     # expect: works, triggers lazy fetch
```
If attribute access does work, explicit schemas are still recommended for type pinning, but the risk
level drops.

**U-02. Does `NUMBER(38,0)` really land as `Integer`, and does `Integer` bind against it cleanly?**
Section 0.2c derives yes from three source locations, but the chain goes through an alias identity and
deserves one live confirmation, because a type mismatch blocks *every* query on the model with no
indication of which property failed.
```python
m.Table("...AIRCRAFT_ELIGIBLE")      # lazy, then:
print(inspect.schema(m).tables)      # read back the discovered type for AIRCRAFT_ID
Aircraft.id  # declared Integer; run one select and confirm no TyperError
```
If it comes back `Number(18,0)` for any column, that column needs `Number.size(18, 0)` explicitly.

**U-03. What does a Snowflake `TIME` column do?** `relationalai/util/schema.py:134` maps `TIME` to
`DateTime`, and there is no RAI `Time` type in `SD/__init__.py:715`'s `__all__`. That means SS-23
through SS-26 and PH-12 through PH-15 cannot round-trip as `TIME`, which `SOURCE_CONTRACT.md:22`
requires.
```sql
-- confirm the discovered type
SHOW COLUMNS IN TABLE PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT;
```
```python
t = m.Table("PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT")
print(inspect.schema(m))   # look at PASSENGER_DEPARTURE_UTC_TIME
m.select(t["PASSENGER_DEPARTURE_UTC_TIME"]).to_df()   # what date does it invent?
```
My recommendation if it behaves as I expect: DATA-04 emits a canonical `VARCHAR` ISO `HH:MM:SS`
alongside the retained raw `TIME` column, RAI binds the `String`, and the round-trip test that
`SOURCE_CONTRACT.md:22` already demands compares the two in SQL. This is a contract-anticipated
addition, not a semantic change, but it does need a DATA-04 change so it should be raised early.

**U-04. Does `require(unique(...))` actually check anything without `emit_constraints: True`?**
The checkout's FD test builds its model with
`create_config(reasoners={"logic": {"emit_constraints": True}})` at
`PyRel/tests/end2end/unified/tests/functional_dependencies.py:5-6`, and 1.20.1 defaults it to `False`
(`relationalai/config/config_reasoners_fields.py:278-281`). If the constraints in section 3.4 are
silently no-ops without it, either turn it on or downgrade them to documented zero-count test queries.
Turning it on may also change how a `Property` FD violation surfaces, which matters for the section 3.3
demo beat.
```python
cfg = create_config(model={"implicit_properties": False},
                    reasoners={"logic": {"emit_constraints": True}})
# then deliberately violate a Property FD and confirm the error text and timing
```

**U-05. Does the Q03 month-end calendar need a table, or is `date.range(freq="M")` exact?**
```python
m.select(std.datetime.date.range(dt.date(2015, 1, 31), dt.date(2024, 12, 31), freq="M")).to_df()
# expect exactly 120 rows, every one a real month end, 2015-02-28 present, 2016-02-29 present
```
If it returns 120 correct month ends, `calendar.py` can generate them and DATA-04 saves a table. If it
clamps 2015-01-31 forward and then loses the 31sts, use the table. Either way keep the other as the
notebook cross-check.

**U-06. Does `.alt()` work on a `Property`, or only on a `Relationship`?**
`Property(Relationship)` at `SD/frontend/base.py:3795` says it inherits `Relationship.alt`
(`:3365`), and the whole inverse-reading design in section 2 depends on it. The checkout only
demonstrates `.alt()` on a `Relationship`
(`PyRel/tests/end2end/unified/tests/functional_dependencies.py:33`).
```python
_p = m.Property(f"{RouteState:state} covers {Route:route}")
Route.states = _p.alt(f"{Route:route} has state {RouteState:state}")
m.select(Route.route_id, Route.states.route_state_key).to_df()
```
Then confirm the critical part: with two concurrent open states on one route, this select returns two
rows and raises nothing. That single result *is* the section 3 demo.

**U-07. Recursion at 1.20.1.** The `union` plus `per(u, v).min(...)` idiom at
`PyRel/tests/end2end/unified/tests/recursion.py:19-25` is from the 1.2.2 tree. Confirm it still
compiles, and confirm what happens with a deliberately cyclic edge set, since P0-11.5 wants a visited
set and a finite step bound and I could not find either as an API parameter.

**U-08. Compound identity with Concept-valued components loaded from a table.**
`identify_by={"aircraft": Aircraft, "event": AircraftEvent, ...}` is documented
(`SD/frontend/base.py:6602`), but I have not seen it loaded from a Snowflake table via chained
`filter_by`. Confirm that an entity is created only when both referenced entities resolve, and that a
row whose `aircraft_id` does not match any `Aircraft` produces no assignment rather than an error.
That behaviour is what makes the quarantine semantics work.

**U-09. Left-join semantics for an absent `Property` in a `select`.** Section 5.3's `UNKNOWN_STATE`
branch and Q01's null-heavy `Q01-BEFORE-FIRST` row both need "row present, value absent". Confirm that
`select(Aircraft.id, AircraftTypeDaily.aircraft_type.subseries | None)` keeps the row, and what the
null renders as in the DataFrame, since `EXPECTED_ANSWERS.yaml:484-492` expects literal `null` in nine
Q01 columns. If `| None` is not accepted, the fallback is `| "__NULL__"` plus a post-select mapping,
which is uglier and needs recording in `DECISION_LOG.md`.

**U-10. Does `aggregates.rank` accept four ordering keys and a `.per()` in one expression?**
`rank1.py:38-44` shows three keys and a `.per()`, but DV-03 needs four. Cheap to confirm, and section
5.4's whole Q02 approach depends on `seq + 1` adjacency being exactly right.

**U-11. FD probes G-01 through G-06 in section 4.3.** All six are SQL, all six run against DATA-03
output, none of them can run yet. G-03 and G-04 are the ones I expect to fail, and if they do, DATA-04
needs two new `MODEL_INPUT` projections, which is a dependency on a task that is currently green. Raise
it before MODEL-01 starts rather than discovering it at first `model.define()`.

**U-12. Change tracking and cold CDC under the demo role.** One `model.Table()` bind plus one
`select` against one small table, timed, before binding all twenty. The
`rai-build-starter-ontology` SKILL pitfall table calls out both
`SnowflakeChangeTrackingNotEnabledException` and a five-to-ten-minute combined cold start when
`reasoners.logic.name` is unset. HT-41 (`SEMANTIC_DECISIONS.md:481`) is exactly this test, so it is
already owed.

---

## 9. Places where RAI cannot express what the Neo4j model does

Stated plainly, because the demo's credibility depends on the limitations list being real.

1. **No temporal type.** Every half-open interval is two `Date` Properties and a two-clause predicate
   written by hand. Neo4j does not have one either, so this is parity, not a gap, but neither system
   should be described as having temporal support.
2. **No `TIME` type.** Snowflake `TIME` is discovered as `DateTime`
   (`relationalai/util/schema.py:134`). A recurring time-of-day with no date cannot round-trip through
   the model without a canonical representation. See U-03.
3. **No minimum-cardinality or negative constraint vocabulary.** `SD/std/constraints.py` offers
   `unique`, `exclusive`, `anyof`, `oneof`. "This route may have many concurrent open states" is
   provable by query but not declarable. Section 3.5.
4. **No per-invocation entity without polluting the model.** The model is append-only, so
   `QueryExecutionContext` moves to the query API boundary. Section 1.2.
5. **No required-parameter enforcement inside the model.** The both-clocks requirement is enforced in
   Python. Section 6.3.
6. **No declared bound on recursion depth that I could find.** Section 2.12 relies on the
   `next_flight` acceptance rule excluding cycles, which is stronger than a step bound but is a
   different mechanism from the one P0-11.5 describes. Confirm with U-07 and record the difference.
7. **Absence is absence, not null.** RAI has no null; a missing `Property` value is a missing fact. That
   maps cleanly onto P0-02.8 and is arguably better than a graph property set to null, but it means
   every "return null here" cell in `EXPECTED_ANSWERS.yaml` is produced by an explicit `|` default at
   the query layer, not by the model. Section 5.3 and U-09.

None of these blocks any of the eight golden questions.
