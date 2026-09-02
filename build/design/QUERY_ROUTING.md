# QUERY_ROUTING - per-question classification and implementation hints

## What this document is

This is the `rai:rai-discovery` classification-and-hints pass (not the ideation pass) for the eight
frozen questions in `DEMO_QUESTIONS.md` / `EXPECTED_ANSWERS.yaml` v1.1.1. For each question it fixes
the reasoner family and sub-pattern, the exact ontology surface the query depends on, whether
`rai:rai-rules-authoring` must run before `rai:rai-querying`, the PyRel query shape in current idiom,
the specific traps, and the frozen cardinality the implementer is aiming at.

It is a routing document, not an implementation. `QUERY-UC1`, `QUERY-UC2`, and `QUERY-ROT` own their
own files and remain free to differ, but a deviation from a routing decision here should be recorded
in `DECISION_LOG.md` rather than made silently.

Grounding used: `rai:rai-discovery` SKILL.md plus its `rules.md` and `graph.md` reference files;
`rai:rai-querying` SKILL.md; `DEMO_QUESTIONS.md`; `EXPECTED_ANSWERS.yaml` (parsed, not read by eye);
`NEO4J_PARITY_MATRIX.md`; `SOURCE_CONTRACT.md`; `NEO4J_RAI_MAPPING.md`; `ATTRIBUTE_AUTHORITY.md` DV
table; and the installed `relationalai` 1.20.1 package in `.venv/`.

## Standing rules for every implementer

Four rules apply to all eight questions and are not repeated in each section.

1. **Ground before writing.** Run `inspect.schema(model)` and confirm concept and property names
   against the live model. Where a relationship packs several positional typed fields, run
   `inspect.fields(Concept.relationship)` first; the prose words in a reading string are not field
   names. Recall of a model surface drifts, and every question below is a multi-concept join where a
   wrong name produces an empty frame rather than an error.
2. **Alias every column in every query.** Several output schemas below put two `*_id` or two
   `*_status` columns side by side, and `to_df()` silently appends `_2` on a collision. The frozen
   comparison is by column name, so an unaliased column is a guaranteed diff.
3. **String literals are a discovery step, not a guess.** `status == "In Service"` (Q03),
   `carrier_role == "marketing"` (Q06/Q07), `dimension == "aircraft_type"` (Q01/Q04/Q08),
   `event_class == "EXACT_ADDITION"` (Q05) are all exact-match filters against source-preserving
   values. `SOURCE_CONTRACT.md` states no trim or case normalization is applied to AH-09. Run
   `model.select(distinct(Concept.prop)).to_df()` once per such property before filtering.
4. **Empty is an answer.** `Q02-NO-SPELLS`, `Q07-KNOWLEDGE-END-EMPTY`, and `Q08-NOT-FOUND` are frozen
   zero-row results. Do not add `| 0` fallbacks or synthetic filler rows to "make the query return
   something". Conversely `Q05-INELIGIBLE-ENDPOINT`, `Q06-INCOMPLETE-ENDPOINT`, and the seven typed
   parameter errors are zero rows plus a non-`OK` invocation status; the catalog layer must be able to
   tell those apart from a legitimately empty result set.

Common imports assumed in all pseudocode below:

```python
from relationalai.semantics import distinct, inspect
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.aggregates import rank, asc, desc
```

## Family summary

None of the eight questions defines an objective, a decision variable, or a prediction target. All
eight ask what is true of known facts. Prescriptive and predictive reasoners are therefore out of
scope, and `DEMO_QUESTIONS.md` and `AGENTS.md` both say so; inventing one would be a scope breach,
not an enhancement. This matches the `rai:rai-discovery` disambiguation rules: "Is this correct /
does this comply?" and "What follows from these facts?" both route to rules.

| Q | Family | Sub-pattern | Rules-authoring first? | Frozen cardinality |
|---|---|---|---|---|
| Q01 | rules | derivation + validation (point-in-time reconstruction with per-dimension status) | Yes | 1 / 1 / 1 / 1 / 0-error |
| Q02 | rules | derivation (ordered sequence pairing over an audit stream) | Yes | 2 / 0 |
| Q03 | rules | derivation (calendar join plus grouped aggregation) | Yes | 132 rows, 120 distinct month ends |
| Q04 | rules | reconciliation (two independent streams, side by side) | Yes | 4 |
| Q05 | rules | reconciliation + classification (snapshot set difference plus conservative evidence) | Yes | 35 / 0-`ENDPOINT_MISSING` |
| Q06 | rules | classification (zero-crossing set difference on one clock) | Yes | 2 / 0 / 0 / 0 |
| Q07 | rules | derivation + validation (two-clock predicate plus grouped aggregation) | Yes | 3 / 2 / 0 / 0 / 0 / 0 |
| Q08 | rules | validation then derivation over an ordinary typed self-reference | Yes | 3 / 11 / 0 |

Every question is `MODEL_GAP` today and becomes `READY` when `MODEL-01` / `MODEL-02` land. The gap is
never data: `SOURCE_CONTRACT.md` contracts every field, and `DATA-04` materializes the canonical
`MODEL_INPUT` objects. The gap is mapping plus the derived properties listed per question.

Every question answers "Yes" to rules-authoring-first, for the same structural reason:
`rai:rai-querying` cannot create derived properties, and each of the eight needs at least one
classification, flag, or ordinal that does not exist on the raw tables. Do not treat this as a
formality; the derived-property list under each question is the actual gating work, and a query
module that reimplements those derivations inline will diverge between modules and will not survive
`QUERY-INT`.

## The `MODEL_INPUT` boundary

`SOURCE_CONTRACT.md` materializes derivations such as DV-05/06/07 daily-assignment intervals,
DV-13/14/15 route-state validity, DV-34 through DV-37 amendment evidence, and
`ROTATION_LINK_VALIDATION` as physical tables. Those arrive in the ontology through `model.Table()`
and should not be recomputed in PyRel.

What must nonetheless be authored as PyRel derived properties is the reusable *predicate and
classification* layer: the as-of point predicate, the DV-33 status, the two-clock eligibility
predicate, the accepted-rotation-link relationship, and the snapshot eligibility flag. `MODEL-01`'s
instruction to "keep temporal predicates and cross-use-case enrichment visible in RAI" and the
parity matrix's differentiation claim of "one reusable semantic model for the eight bounded workloads
instead of query-local temporal rules" both depend on that layer living in the ontology. If those
predicates end up copy-pasted into `uc1.py`, `uc2.py`, and `rotation.py`, the demo's central
differentiation claim is no longer true.

## Q01 - `aircraft_as_of`

**Family and sub-pattern.** Rules, derivation with a validation overlay. Four independently versioned
dimension streams are resolved at one instant and each carries its own DV-33 status; the composite
`is_complete` is a validation over those four statuses.

**Ontology surface required.**

- `Aircraft` identified by AM-01, with `existence_from` (DV-01) and `existence_to` (DV-02).
- `AircraftDimensionDailyAssignment` identified by DV-05, with `dimension`, `valid_from` (DV-06),
  `valid_to` (DV-07), `dimension_resolution_status` (DV-08), the watched payload, and the optional
  exact target. One concept with a `dimension` discriminator, per the contract key
  `(dimension, AH-02, AH-05, AH-01)`; the four named streams are subtypes or filters of it, not four
  separate concepts.
- Optional exact targets `AircraftType` (AC-05) and `EngineType` (AC-14), plus assignment-level
  `engine_count` (AC-08) and `mixed_engine_set_complete` (DV-09). Note that count and completeness sit
  on the assignment, not on the `EngineType` identity.
- `aircraft_state` payload fields `registration_number` (AH-17) and `base_airport_code_iata` (AH-25);
  `aircraft_status` payload `lifecycle_status` (AH-09).

**Rules-authoring first: yes.** Three derived properties, all shared beyond Q01:

- `Aircraft.exists_at(date)` as the half-open existence predicate `DV-01 <= d < DV-02`. The finite EOL
  date is excluded under D-0003.
- `AircraftDimensionDailyAssignment.covers(date)` as `valid_from <= d < valid_to`.
- `dimension_query_status` (DV-33) as the four-value classification. Two of the four values are the
  presence of a row (`OK`, `UNKNOWN_STATE`, the latter being an explicit null-payload interval that
  `MODEL_INPUT` already materializes) and two are the absence of one (`NO_RECORDED_STATE` inside
  existence with no covering assignment, `OUTSIDE_EXISTENCE` outside the bounds). Authoring this as a
  classification rule, rather than as four ad-hoc query branches, is what makes Q01, Q03, and Q08
  agree.

**Query shape.**

```python
def aircraft_as_of(model, Aircraft, DailyAsgn, aircraft_id: int, as_of: str):
    # Branch guard first: outside existence returns one all-null row with four
    # OUTSIDE_EXISTENCE statuses (Q01-R004), not zero rows.
    typ = DailyAsgn.ref("typ")
    eng = DailyAsgn.ref("eng")
    sta = DailyAsgn.ref("sta")
    st8 = DailyAsgn.ref("st8")
    return model.where(
        Aircraft.aircraft_id == aircraft_id,
        # each ref independently bound and independently optional
        ...
    ).select(
        Aircraft.aircraft_id.alias("aircraft_id"),
        (typ.definition_id | None).alias("aircraft_type_id"),
        (typ.query_status  | "NO_RECORDED_STATE").alias("aircraft_type_status"),
        (eng.definition_id | None).alias("engine_type_id"),
        ...
    ).to_df()
```

The four dimension refs must each be **separately named** (`.ref("typ")`, `.ref("eng")`, ...). A bare
`DailyAssignment` reused across four independent lookups is the documented cause of
`ValidationError: Unused variable`, and reusing one ref would also unify the four dimensions into one.

**The one genuine syntax risk in UC1.** Q01 needs left-join semantics: `Q01-UNKNOWN-GAP` and
`Q01-BEFORE-FIRST` both expect exactly one row in which some or all dimensions are null. An inner
join over four dimension refs drops the whole row the moment one dimension has no covering
assignment, and the query then returns zero rows instead of one. The fallback operator `|` is the
documented PyRel mechanism for "left side if present, right side otherwise", but its behaviour over a
*bound concept ref* rather than a property on the anchor entity is the thing to prove. Prototype this
shape first, before anything else in `QUERY-UC1`; if `|` over a ref does not give optionality,
the fallback design is to make the assignment stream total by materialising `NO_RECORDED_STATE`
intervals in `MODEL_INPUT` as well (which reduces all four dimensions to inner joins), and that is a
`DATA-04`/`MODEL-01` change, so it needs to be discovered early rather than at integration.

**Traps.**

- *Backfilling from master.* AM-11 through AM-14 are `CURRENT_ONLY` under D-0005 and are prohibited
  from historical reconstruction. `SOURCE_CONTRACT.md`'s oracle shape says explicitly: do not backfill
  from master or current fields. A query that coalesces a null historical value to the master value
  will look more complete and be wrong.
- *EOL boundary.* `Q01-EOL-BOUNDARY` is aircraft 1002 at 2024-07-01, and expects all four statuses
  `OUTSIDE_EXISTENCE`. The bound is exclusive under D-0003, so `d < DV-02` and not `d <= DV-02`.
- *Confusing the two absence statuses.* `Q01-BEFORE-FIRST` (1004 at 2019-06-30) is
  `NO_RECORDED_STATE` on all four; `Q01-UNKNOWN-GAP` (1002 at 2022-05-15) is `OK` on state and status
  but `UNKNOWN_STATE` on type and engine, with `is_complete = false`. These are different facts and
  collapsing them to one "missing" value fails two result sets.
- *`is_complete`.* True only when all four requested dimensions are `OK`. `Q01-R001` is the only true.

**Frozen cardinality.** `Q01-CANONICAL` 1 row; `Q01-BEFORE-FIRST` 1; `Q01-UNKNOWN-GAP` 1;
`Q01-EOL-BOUNDARY` 1; `Q01-INVALID-AIRCRAFT-ID` 0 rows with `PARAMETER_ERROR` /
`INVALID_AIRCRAFT_ID`. Output schema is 17 columns. Order `aircraft_id, as_of_date`.

## Q02 - `status_reversion_spells`

**Family and sub-pattern.** Rules, derivation by ordered sequence pairing. This is a self-join over
one ordered stream, picking the minimal qualifying successor.

**Ontology surface required.**

- `AircraftStatusAuditAssignment` (the `dimension = 'aircraft_status'` slice of
  `AircraftDimensionAuditAssignment`, DV-04), carrying `aircraft_history_id` (AH-01),
  `start_event_date` (AH-05), `row_sequence_number` (AH-03), `event_sequence_number` (AH-04), and the
  watched `lifecycle_status` (AH-09). **No date interval**; the audit stream deliberately has none.
- A dense integer ordinal per `(aircraft, dimension)` over the canonical DV-03 order tuple
  `(AH-05, AH-03, AH-04, AH-01)`. See the cross-cutting section; this is the single highest-value
  shared derived property in the build.

**Rules-authoring first: yes.** `AircraftDimensionAuditAssignment.event_ordinal` (the dense ordinal),
plus the derivation rule that flags a Storage assignment whose immediately preceding assignment in the
same aircraft's stream is `In Service`, and pairs it with the minimal later `In Service` assignment.

**Query shape.**

```python
S = AuditAsgn.ref("storage")     # the Storage assignment
P = AuditAsgn.ref("prior")       # its immediate predecessor, must be In Service
R = AuditAsgn.ref("ret")         # the chosen return assignment

model.where(
    S.aircraft == Aircraft, Aircraft.aircraft_id == aircraft_id,
    S.dimension == "aircraft_status", S.lifecycle_status == "Storage",
    P.aircraft == Aircraft, P.dimension == "aircraft_status",
    P.event_ordinal == S.event_ordinal - 1,
    P.lifecycle_status == "In Service",
    R.aircraft == Aircraft, R.dimension == "aircraft_status",
    R.lifecycle_status == "In Service",
    R.event_ordinal > S.event_ordinal,
    # minimal qualifying successor, bound in where() so it can be compared
    first_return := aggs.min(R.event_ordinal).per(S),
    R.event_ordinal == first_return,
).select(
    Aircraft.aircraft_id.alias("aircraft_id"),
    S.aircraft_history_id.alias("storage_event_id"),
    S.start_event_date.alias("storage_start_date"),
    S.row_sequence_number.alias("storage_start_sequence"),
    R.aircraft_history_id.alias("return_event_id"),
    R.start_event_date.alias("return_date"),
    R.row_sequence_number.alias("return_sequence"),
    (R.start_event_date - S.start_event_date).alias("storage_days"),
    (R.start_event_date == S.start_event_date).alias("same_day"),
).to_df()
```

The `aggs.min(...).per(S)` bound with `:=` in `where()` then compared is the documented HAVING-style
pattern, and is the right way to express "next" without dropping into pandas.

**Traps.**

- *Reading the daily stream.* This is the fatal one. `Q02-R002` is a same-day spell: storage event
  101010 at sequence 20 and return event 101011 at sequence 30, both on 2020-06-01, `storage_days = 0`,
  `same_day = true`. The daily projection keeps only the final relevant observation per aircraft,
  dimension, and date, so on the daily stream the Storage assignment does not exist at all and the
  spell silently disappears. Q02 must read `AircraftDimensionAuditAssignment` and never
  `AircraftDimensionDailyAssignment`. `NEO4J_PARITY_MATRIX.md` sells this row as the differentiator
  over a coarse aircraft-plus-date state key, so losing it loses the demo beat.
- *De-duplicating `A -> B -> A`.* `SOURCE_CONTRACT.md` is explicit: consecutive equality is suppressed,
  global equality is not, so `In Service -> Storage -> In Service` remains three assignments. Any
  `distinct()` over the watched status value, or any "collapse repeated states" step, destroys the
  second `In Service` and with it the spell. `distinct()` in this query should appear nowhere.
- *Pairing greedily across spells.* Pairing each Storage with the *minimal* later `In Service`, rather
  than with any later one, is what prevents the first Storage from also pairing with the second
  spell's return and inflating the result to more than two rows.
- *Order without duration.* Dates plus source sequence establish order, not intraday elapsed time.
  `storage_days` is a calendar-day difference, hence 0 for the same-day spell. Do not derive it from
  timestamps; there are none on the audit stream.

**Frozen cardinality.** `Q02-CANONICAL` (aircraft 1001) exactly 2 rows: `(101003, 2018-03-01, seq 10)`
to `(101004, 2018-04-15, seq 10)` with `storage_days = 45`; and `(101010, 2020-06-01, seq 20)` to
`(101011, 2020-06-01, seq 30)` with `storage_days = 0` and `same_day = true`. `Q02-NO-SPELLS`
(aircraft 1004) exactly 0 rows. Order `storage_start_date, storage_start_sequence, storage_event_id,
return_event_id`.

## Q03 - `month_end_fleet_composition`

**Family and sub-pattern.** Rules, derivation: an inequality join from a calendar concept onto two
independent daily-assignment streams, then a grouped count.

**Ontology surface required.**

- A `MonthEnd` (or `CalendarMonthEnd`) concept with one instance per month end, identified by its
  date. This must be a **materialized concept**, not a Python range.
- `Aircraft` with existence bounds.
- `AircraftDimensionDailyAssignment` filtered to `dimension = 'aircraft_status'` and to
  `dimension = 'aircraft_type'`, each with its own interval.
- `AircraftType` (AC-05) with `aircraft_type_id` and its label.

**Rules-authoring first: yes.** Reuses `Aircraft.exists_at` and `DailyAssignment.covers` from Q01. If
those are query-local in `uc1.py` rather than ontology-level, Q01 and Q03 will drift on the boundary
semantics and only one of them will match the manifest.

**Query shape.** One query. Not 120.

```python
sta = DailyAsgn.ref("sta")
typ = DailyAsgn.ref("typ")

model.select(distinct(
    MonthEnd.date.alias("month_end"),
    AircraftType.aircraft_type_id.alias("aircraft_type_id"),
    AircraftType.label.alias("aircraft_type"),
    aggs.count(Aircraft).per(MonthEnd, AircraftType).alias("in_service_aircraft_count"),
)).where(
    Aircraft.existence_from <= MonthEnd.date, MonthEnd.date < Aircraft.existence_to,
    sta.aircraft == Aircraft, sta.dimension == "aircraft_status",
    sta.valid_from <= MonthEnd.date, MonthEnd.date < sta.valid_to,
    sta.lifecycle_status == "In Service",
    typ.aircraft == Aircraft, typ.dimension == "aircraft_type",
    typ.valid_from <= MonthEnd.date, MonthEnd.date < typ.valid_to,
    typ.aircraft_type(AircraftType),
    MonthEnd.date >= start_month_end, MonthEnd.date <= end_month_end,
).to_df()
```

Then cast the count: integer aggregates come back as `Int128Array` and pandas reductions on that
dtype raise. `df["in_service_aircraft_count"] = df["in_service_aircraft_count"].astype(int)`.

**Traps.**

- *Writing the query 120 times.* An explicit fail. The interval-to-calendar inequality join replaces
  the loop; the calendar is a joined dimension, not a parameter sweep.
- *An approach that only works because the interval is regular.* Also an explicit fail. Do not derive
  month ends by adding 30 or 31 days, by `date + n*interval` arithmetic, or by any generated series
  that assumes even spacing. The join predicate is a pure inequality and is indifferent to whether the
  calendar is monthly, weekly, or irregular; the calendar concept must be materialized from a real
  month-end calendar so that the same query works for any set of dates.
- *Cartesian inflation.* Binding both `sta` and `typ` through the same `Aircraft` inside one query is
  a multi-relationship join through a shared concept, which is the documented cause of silent
  aggregation inflation. Here the product is intended and correct, but only because the contract's
  multiplicity gate guarantees "zero-or-one final relevant observation" per aircraft, dimension, and
  date. That gate is `DATA-03`/`DATA-04`'s job. Add a cheap guard in the test: assert that no
  `(aircraft, dimension, month_end)` triple matches more than one assignment. If the gate ever
  regresses, this query inflates counts silently and the failure will look like a data bug three
  phases downstream.
- *Fabricating zero rows.* 120 month ends and two types give 240 possible cells, but only 132 are
  nonzero and the manifest omits the zeros. The inner-join semantics above already omit them. Do not
  add `| 0`, do not left-join the calendar to the type list, do not "complete the grid".
- *Aggregating the wrong key.* Use `.per(MonthEnd, AircraftType)` with bare concepts. Using
  `.per(typ.aircraft_type)` instead of the bound `AircraftType` introduces a second anonymous
  iterator and cartesian-multiplies the rows; `distinct()` will not fix that.

**Frozen cardinality.** `Q03-CANONICAL` exactly 132 rows over exactly 120 distinct month ends,
2015-01-31 through 2024-12-31, with only `SYN-TYPE-A` and `SYN-TYPE-B` appearing and counts in
`{1, 2}`. Order `month_end, aircraft_type_id`.

## Q04 - `type_engine_histories`

**Family and sub-pattern.** Rules, reconciliation. Two independently clocked streams are placed side
by side without being aligned, and one derived flag is computed strictly within one of them.

**Ontology surface required.** Same `AircraftDimensionDailyAssignment` concept as Q01/Q03, restricted
to `dimension in ("aircraft_type", "engine_type")`, plus its `assignment_id` (DV-05), `valid_from`,
`valid_to`, the optional exact `AircraftType` / `EngineType` target and its label, and the
assignment-level `engine_count` / `mixed_engine_set_complete`.

**Rules-authoring first: yes.** Two derived properties:

- The dense per-`(aircraft, dimension)` ordinal again, this time over the *daily* stream ordered by
  `valid_from`, so that "the preceding assignment" is expressible.
- `previous_definition_id` and `is_type_change`, derived only within the `aircraft_type` stream.
  `is_type_change` is `false` for the first assignment (previous is null) and `null` for every engine
  row. Three-valued, which is exactly why it belongs in a rule rather than in a `select` expression.

**Query shape.** Because the contract keys the daily assignment by `(dimension, AH-02, AH-05, AH-01)`,
type and engine are two slices of **one concept**, and Q04 is a filter over that concept, not a union
of two queries.

```python
model.where(
    DailyAsgn.aircraft == Aircraft, Aircraft.aircraft_id == aircraft_id,
    DailyAsgn.dimension.in_(["aircraft_type", "engine_type"]),
).select(
    Aircraft.aircraft_id.alias("aircraft_id"),
    DailyAsgn.dimension.alias("dimension"),
    DailyAsgn.assignment_id.alias("assignment_id"),
    DailyAsgn.valid_from.alias("valid_from"),
    DailyAsgn.valid_to.alias("valid_to"),
    DailyAsgn.definition_id.alias("definition_id"),
    DailyAsgn.definition_label.alias("definition_label"),
    DailyAsgn.engine_count.alias("engine_count"),
    DailyAsgn.mixed_engine_set_complete.alias("mixed_engine_set_complete"),
    DailyAsgn.previous_definition_id.alias("previous_definition_id"),
    DailyAsgn.is_type_change.alias("is_type_change"),
).to_df()
```

If `MODEL-01` instead exposes `AircraftTypeDailyAssignment` and `EngineTypeDailyAssignment` as PyRel
**subtypes**, remember the subtype rule: they cannot be selected from or counted directly. Bind the
parent and constrain with the subtype, `model.where(AircraftTypeDailyAssignment(DailyAsgn))`, or the
query raises `TyperError`.

**Traps.**

- *Forcing the intervals to align.* The expected rows make the independence visible: the type stream
  breaks at 2019-01-01 and the engine stream at 2021-07-01, and neither boundary appears in the other.
  Any join of the two streams on overlapping validity, any `full outer join` producing a merged
  timeline, any "as-of both" reconstruction produces more or fewer than four rows. The two streams
  are simply filtered and emitted; they are never joined to each other.
- *Union machinery you do not need.* Reaching for `model.union()` to stitch two separately modelled
  concepts back together is the most likely over-engineering here, and it invites divergent payload
  handling between the branches. One concept plus a `dimension` discriminator is both simpler and what
  the source contract already specifies.
- *Payload on the wrong entity.* `engine_count` (AC-08) and `mixed_engine_set_complete` (DV-09) belong
  to the assignment, not to `EngineType`. The contract is explicit that asserting one engine count per
  engine-subseries identity would be wrong. Type rows carry null in both columns.
- *Fabricating a mixed-engine set.* Only one reported engine definition plus a count is available.
  `mixed_engine_set_complete` is `false` when AC-09 is true. Never derive a second engine type.
- *`is_type_change` on engine rows.* Null, not false. The order clause sorts `aircraft_type` before
  `engine_type` alphabetically, which is what the frozen order relies on.

**Frozen cardinality.** `Q04-CANONICAL` exactly 4 rows: two `aircraft_type`
(2015-01-01 to 2019-01-01, `SYN-TYPE-A`, `is_type_change = false`; 2019-01-01 to 9999-01-01,
`SYN-TYPE-B`, `previous_definition_id = SYN-TYPE-A`, `is_type_change = true`) and two `engine_type`
(2015-01-01 to 2021-07-01, `SYN-ENGINE-A`; 2021-07-01 to 9999-01-01, `SYN-ENGINE-B`; both
`engine_count = 2`, `mixed_engine_set_complete = true`, `is_type_change = null`). Order
`dimension, valid_from, assignment_id`. Note the model open sentinel is `9999-01-01`, not the source
`9999-12-31`.

## Q05 - `schedule_four_week_changes`

**Family and sub-pattern.** Rules, reconciliation with a classification layer on top. Exact
presence-and-content facts are computed first and stand on their own; conservative amendment evidence
is classified separately and never replaces them.

**Ontology surface required.**

- `SnapshotDate` (SC-01) with `is_present` (SC-02) and `is_complete` (SC-03).
- `Schedule` (SS-01) and `SCHEDULE_CANONICAL_OBSERVATION` keyed `(SS-01, SS-03)` with the watched
  SS-04 through SS-38 payload.
- `ScheduleExactChange` with `comparison_date`, `previous_knowledge_date`, `event_id`, `event_class`,
  `field_name`, `old_value`, `new_value`, and `crosses_snapshot_gap` (DV-16).
- `ScheduleAmendmentEvidence` covering DV-35 candidates, DV-36 groups, and DV-37 members, with
  `schedule_key`, `related_schedule_key`, `group_id`, `member_side`, `member_schedule_key`,
  `amendment_candidate_class` (DV-18), and `amendment_confidence` (DV-19).

**Rules-authoring first: yes**, and this is the heaviest rules-authoring load of the eight.

- `SnapshotDate.is_eligible` as `is_present AND is_complete`. Nothing else may be used; row counts
  (SC-05) are validation evidence and never completeness by themselves.
- The adjacency relation over eligible snapshot dates: each comparison pairs a date with the
  *previous eligible* date, which is not necessarily the previous calendar date.
- `event_class_rank`, materializing the manifest's `enum_sort_ranks.Q05_event_class`
  (`EXACT_KEY_PRESERVING_MODIFICATION` 10, `EXACT_ADDITION` 20, `EXACT_REMOVAL` 30,
  `CANDIDATE_UNIQUE` 40, `AMBIGUOUS_CANDIDATE_GROUP` 50, `AMBIGUOUS_GROUP_MEMBER` 60,
  `UNPAIRED_ADDITION` 70, `UNPAIRED_REMOVAL` 80). The frozen order is by this rank, not alphabetical.
- A normalized `ScheduleChangeEvent` view carrying all 16 output columns with nulls where a column
  does not apply to a branch. Authoring this in the ontology is strongly preferred over assembling two
  differently shaped frames in the query module, because the exactness/confidence labelling is a
  semantic guarantee the parity matrix depends on and it should be stated once.

**Query shape.** Two logical branches feeding one normalized concept, then a single filtered select.

```python
model.where(
    ChangeEvent.comparison_date > start_knowledge_date,
    ChangeEvent.comparison_date <= end_knowledge_date,
).select(
    ChangeEvent.comparison_date.alias("comparison_date"),
    ChangeEvent.previous_knowledge_date.alias("previous_knowledge_date"),
    ChangeEvent.event_id.alias("event_id"),
    ChangeEvent.event_class.alias("event_class"),
    ChangeEvent.exactness.alias("exactness"),
    ChangeEvent.confidence.alias("confidence"),
    ChangeEvent.schedule_key.alias("schedule_key"),
    ChangeEvent.related_schedule_key.alias("related_schedule_key"),
    ChangeEvent.field_name.alias("field_name"),
    ChangeEvent.old_value.alias("old_value"),
    ChangeEvent.new_value.alias("new_value"),
    ChangeEvent.group_id.alias("group_id"),
    ChangeEvent.member_side.alias("member_side"),
    ChangeEvent.member_schedule_key.alias("member_schedule_key"),
    ChangeEvent.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
    ChangeEvent.event_class_rank.alias("_rank"),   # order key, dropped before comparison
).to_df()
```

Eligibility is checked by a **separate small query** over `SnapshotDate` before this one runs. If
either endpoint is ineligible the catalog returns zero rows with `ENDPOINT_MISSING`; it does not run
the change query and report a natural empty result.

**Traps.**

- *The `schedule_key` hash trap.* SS-01 hashes SS-08/SS-09, the effective and discontinue dates, so a
  date shift on an existing schedule mints a new key. Presence comparison then sees one removal of the
  old key and one unrelated addition of the new key. This is not a bug to be fixed; it is the exact
  behaviour the manifest freezes. `SYN-SK-SHIFT_OLD` and `SYN-SK-SHIFT_NEW` are recognised as a pair
  only by matching on the typed signature `(SS-04 marketing carrier, SS-06 flight number,
  SS-10 origin, SS-11 destination)` with **overlapping** SS-08/SS-09 ranges, and every component plus
  both bounds must be non-null and valid.
- *Promoting a candidate to exact.* The pair must be reported as `CANDIDATE_UNIQUE` with
  `exactness = CANDIDATE` and `confidence = MEDIUM`, never as a modification. `NEO4J_PARITY_MATRIX.md`
  lists "A candidate key shift is an exact schedule amendment" as a prohibited statement. The exact
  addition and removal rows survive alongside the candidate; they are not consumed by it.
- *Ambiguity resolution.* Where one removal is compatible with two additions
  (`SYN-SK-AMB_OLD` against `SYN-SK-AMB_NEW_A` and `_NEW_B`), the answer is one
  `AMBIGUOUS_CANDIDATE_GROUP` row plus three `AMBIGUOUS_GROUP_MEMBER` rows at `LOW` confidence, with
  `schedule_key` and `related_schedule_key` both null and no pair chosen. Picking a winner by any
  tie-break is wrong.
- *Question-private filtering.* D-0010/D-0011 forbid a fixture-family filter. Q05 runs over the whole
  `SYN-SCHEDULE-UNIVERSE-01` and must surface every exact change forced by the Q06 and Q07 fixtures.
  `SYN-SK-MKT_ENTRY_714` and `SYN-SK-MKT_EXIT_715` therefore appear in Q05 as exact addition and exact
  removal *and* as unpaired evidence, four rows in total, even though they exist for Q06.
- *Semantic duplicates.* Identical `normalized_row_hash` (SS-40) values within a `(SS-01, SS-03)` are
  duplicates and are collapsed by the canonical selection ranking, not by the query. A repeated
  unchanged eligible observation contributes lineage and must not mint a change event.
- *Reappearance.* `SYN-SK-REAPPEAR_400` is removed on 2026-08-10 and added back on 2026-08-17. That is
  an exact removal followed by an exact addition, labelled `REAPPEARANCE` in the state layer, not a
  no-op and not a modification.
- *Sorting by the class name.* Alphabetical ordering of `event_class` puts `AMBIGUOUS_*` first and
  fails the frozen order. Use the rank.

**Frozen cardinality.** `Q05-CANONICAL` exactly 35 rows: 22 `EXACT` (9
`EXACT_KEY_PRESERVING_MODIFICATION`, 7 `EXACT_ADDITION`, 6 `EXACT_REMOVAL`) plus 13 evidence rows
(4 `UNPAIRED_ADDITION`, 4 `UNPAIRED_REMOVAL`, 3 `AMBIGUOUS_GROUP_MEMBER`, 1
`AMBIGUOUS_CANDIDATE_GROUP`, 1 `CANDIDATE_UNIQUE`). Distribution by comparison date is exactly
7 / 5 / 9 / 14 for 2026-08-10, -17, -24, -31, and the closure section names the row IDs in each
bucket, so a per-pair count check is the cheapest early diagnostic. `Q05-INELIGIBLE-ENDPOINT`
(2026-10-12 to 2026-10-19) is 0 rows with `ENDPOINT_MISSING`.

## Q06 - `market_latest_vs_seven_days`

**Family and sub-pattern.** Rules, classification. A zero-crossing set difference at
`(carrier_role, airline_id, route_id)` grain between two exact knowledge endpoints.

**Ontology surface required.** `SnapshotDate` with eligibility; `RouteState` (DV-13) with
`knowledge_valid_from` (DV-14) and `knowledge_valid_to` (DV-15); `Route` (DV-12) with its directional
`route_id`; the separate `marketing_airline` and `operating_airline` exact links to `Airline` (AL-01);
`Schedule` (SS-01) for the distinct count.

**Rules-authoring first: yes.** Reuse `SnapshotDate.is_eligible` from Q05. Add the knowledge-clock
visibility predicate `RouteState.visible_at(knowledge_date)` as
`DV-14 <= knowledge_date < DV-15`, and the market-grain classification `ENTRY` (before 0, after > 0)
versus `EXIT` (before > 0, after 0).

**Query shape.** Two counts per market at the two endpoints, then a `|` fallback to zero on the side
where the group is absent, then the classification filter.

```python
before := aggs.count(Schedule).per(Airline, Route).where(
    RouteState.knowledge_valid_from <= comparison_date,
    comparison_date < RouteState.knowledge_valid_to,
) | 0
after := aggs.count(Schedule).per(Airline, Route).where(
    RouteState.knowledge_valid_from <= latest_date,
    latest_date < RouteState.knowledge_valid_to,
) | 0
# then filter (before == 0 and after > 0) or (before > 0 and after == 0)
```

This is one of the two places in the eight where `| 0` is correct: a market that is absent at one
endpoint genuinely has count zero there, and the whole question is about that zero. Contrast Q03,
where `| 0` would fabricate rows.

**Traps.**

- *Reaching for the operating clock.* Q06 is a **knowledge-clock-only** comparison. There is no
  operating date and no weekday predicate. The question says when knowledge changed, not which service
  operates on some other date. Adding an operating filter changes the counts and is a
  category error, not a refinement.
- *Silently substituting an ineligible endpoint.* `Q06-INCOMPLETE-ENDPOINT` compares 2026-10-26 with
  2026-10-19, where 2026-10-19 is present but incomplete. The frozen answer is 0 rows with
  `ENDPOINT_INCOMPLETE`. Falling back to the previous eligible date (2026-10-05) and returning rows is
  wrong; latest-versus-seven-days requires both *exact* calendar endpoints to be eligible.
- *Inexact carrier resolution.* Only `EXACT` cardinality-one resolution creates the airline link. An
  ambiguous or unresolved carrier code cannot produce an airline-level market at all. Do not
  substitute the raw code as an identity.
- *Merging the two carrier roles.* `carrier_role` is a required parameter with no default; marketing
  and operating never collapse. `Q06-MISSING-CARRIER-ROLE` freezes a `PARAMETER_ERROR` for the null
  case rather than a default.
- *Counting lineage rows.* `before_schedule_count` and `after_schedule_count` count distinct eligible
  schedule keys, not `ROUTE_STATE_LINEAGE` contributions. Both are 0 or 1 in the canonical answer, so
  an inflation bug shows up immediately, which makes this a useful early check.
- *Expecting spurious zero-crossings.* The universe deliberately contains stable positive market
  shadows so that unrelated schedules do not cross zero. If more than two rows come back, the cause is
  almost certainly a clock predicate that is too narrow rather than a missing filter.

**Frozen cardinality.** `Q06-CANONICAL` exactly 2 rows: `ENTRY` for `SYN-MKT-ENTRY` on `SEA->DEN`
(0 to 1), `EXIT` for `SYN-MKT-EXIT` on `BOS->MIA` (1 to 0). `Q06-INCOMPLETE-ENDPOINT` 0 rows with
`ENDPOINT_INCOMPLETE`; `Q06-MISSING-CARRIER-ROLE` and `Q06-INVALID-DATE` 0 rows with
`PARAMETER_ERROR`. Order `change_kind` (`ENTRY` before `EXIT`), `airline_id`, `route_id`.

## Q07 - `route_capacity_two_clocks`

**Family and sub-pattern.** Rules, derivation with validation. Both clocks gate the state set, then a
grouped aggregation produces frequency and cabin capacity, with a validation status per output row.

**Ontology surface required.** `RouteState` with knowledge validity DV-14/DV-15 **and** operating
bounds SS-08/SS-09 plus the seven weekday flags SS-14 through SS-20; `weekly_frequency` (SS-22); raw
capacity SS-30 through SS-34; `is_codeshare` (SS-35) and `codeshare_carrier_internal` (SS-36); the
separate marketing and operating `Airline` links; `Route`; `Schedule`; and `QueryExecutionContext`
carrying DV-29 `carrier_role`, DV-30 `knowledge_date`, DV-31 `operating_date`.

**Rules-authoring first: yes.** Four derived properties, none of which belongs in a query module:

- The two-clock eligibility predicate: knowledge is **half-open** `DV-14 <= k < DV-15`; operating is
  **inclusive** `SS-08 <= o <= SS-09` **and** the weekday flag for `o` is true. Nine-row truth table
  `TT-BOTH-CLOCKS` freezes it.
- `economy_excluding_premium` (DV-26) as SS-34 minus SS-33, since premium economy is a subset of
  economy.
- `cabin_quality_status` (DV-27), the five-row `TT-CABIN-QUALITY` classification over null, negative,
  mismatch, and premium-over-economy inputs.
- `physical_service_status` (DV-28), the D-0007 base-representative rule: for the operating role,
  count only a state whose marketing and operating carriers resolve to the same airline and which is
  not a codeshare; a codeshare-only service becomes `UNRESOLVED_PHYSICAL_SERVICE`.

**Query shape.** Weekly measures are per-flight seats multiplied by `weekly_frequency`, summed over
the active states in the group. Confirmed against the frozen rows: `Q07-R002` is 7 x 180 = 1260 total
with 8 / 20 / 20 / 132 per flight, and `Q07-R001` is the sum of a 7 x 180 and a 3 x 100 state giving
10 frequency and 1560 seats.

```python
model.select(distinct(
    RouteState.result_status.alias("result_status"),
    Airline.airline_id.alias("airline_id"),
    Route.route_id.alias("route_id"),
    aggs.count(Schedule).per(Airline, Route).alias("active_schedule_count"),
    aggs.sum(RouteState.weekly_frequency).per(Airline, Route).alias("weekly_frequency"),
    aggs.sum(RouteState.total_seats * RouteState.weekly_frequency)
        .per(Airline, Route).alias("weekly_total_seats"),
    aggs.sum(RouteState.economy_excluding_premium * RouteState.weekly_frequency)
        .per(Airline, Route).alias("weekly_economy_excluding_premium_seats"),
    ...
)).where(
    RouteState.visible_at_knowledge(knowledge_date),
    RouteState.operates_on(operating_date),
    RouteState.carrier_link_for_role(carrier_role, Airline),
    RouteState.route(Route),
).to_df()
```

Seats are FLOAT, so no integer-division trap; `active_schedule_count` and `weekly_frequency` are
integer aggregates and need the `astype(int)` cast before any pandas reduction.

**Traps.**

- *Dropping either clock.* This is the headline trap and it fails quietly. Filtering on knowledge
  alone returns states that are known but not operating on 2026-09-07; filtering on operating alone
  returns states as understood today rather than as understood on the knowledge date. Both give a
  plausible, well-formed, wrong answer. `TT-BOTH-CLOCKS` exists precisely to catch this: only
  `TT23-R05` and `TT23-R06` are eligible out of nine combinations, and note that
  `knowledge_position = AT_END` is ineligible in all three of its rows because the knowledge bound is
  exclusive at the top.
- *Mixing the two interval conventions.* Knowledge is half-open, operating is inclusive at both ends.
  Applying half-open semantics to SS-09 loses the last operating day; applying inclusive semantics to
  DV-15 admits a superseded state. They are different on purpose and both appear in the same
  `where()`.
- *Assuming one open state per route.* Schedule versioning partitions by SS-01, never by route, so one
  `Route` can have many concurrently open `RouteState` rows. `SYN-OP-A` on `SFO->LAX` has
  `active_schedule_count = 2`, and the parity matrix explicitly prohibits a one-open-per-route
  constraint. Any `argmax`, "latest state per route", or unique-state assumption collapses this row.
- *Treating the same airline in both roles as a duplicate.* `SYN-OP-A` appears in the marketing result
  set (as marketing carrier of its own schedules) and in the operating result set with identical
  numbers. That is two correct rows in two different result sets, not double counting.
- *Filtering codeshares away.* `Q07-OPERATING` contains `Q07-R004`, a
  `UNRESOLVED_PHYSICAL_SERVICE` row for `SYN-OP-X` on `SFO->SEA` with every measure null,
  `cabin_quality = NOT_COUNTED`, and `unresolved_service_key = SYN-SK-CSH_ONLY_900`. Codeshare-only
  service must be *emitted as visibly unresolved*, not excluded and not guessed into a number. Its
  absence is a two-row result where three are expected.
- *Economy double-counting.* SS-34 already includes SS-33. The exclusive bucket is the difference, and
  the four cabin buckets must sum to the per-flight total (8 + 20 + 132 + 20 = 180 in `Q07-R002`).
- *Treating the empty result as an error.* `Q07-KNOWLEDGE-END-EMPTY` at knowledge 2026-09-07 is 0 rows
  with `invocation_status = OK`. That is different from the four `PARAMETER_ERROR` scenarios.
- *Defaulting a missing parameter.* All three of `knowledge_date`, `operating_date`, and
  `carrier_role` are required with no default; each has its own frozen typed error.

**Frozen cardinality.** `Q07-MARKETING` 3 rows (`SYN-MKT-B` `SFO->LAX`, `SYN-MKT-X` `SFO->SEA`,
`SYN-OP-A` `SFO->LAX`), all `COUNTED` and `RECONCILED`. `Q07-OPERATING` 2 rows (`SYN-OP-A`
`SFO->LAX` `COUNTED`; `SYN-OP-X` `SFO->SEA` `UNRESOLVED_PHYSICAL_SERVICE`).
`Q07-KNOWLEDGE-END-EMPTY` 0 rows, status `OK`. Three parameter-error scenarios, 0 rows each. Order
`result_status` (`COUNTED` before unresolved), `airline_id`, `route_id`.

## Q08 - `actual_rotation_enriched`

**Family and sub-pattern.** Rules: validation first, then derivation, over an **ordinary typed
self-reference**. Every candidate `next_flight_id` edge is validated into accepted or a typed anomaly,
the accepted edges form a chain, chain position is derived from the link structure, and each accepted
leg is then enriched by a point-in-time join into the independent type and engine streams. See the
explicit graph verdict at the end of this document.

**Ontology surface required.**

- `AircraftFlight` (AF-01) with `aircraft` (AF-02), `flight_departure_date` (AF-06, **local**),
  `flight_departure_date_utc` (AF-07, lineage only), actual origin (AF-08) and actual destination
  (AF-09, which is DV-45), `actual_gate_departure_time_utc` (AF-13),
  `actual_gate_arrival_time_utc` (AF-14), `diverted_airport_code` (AF-10),
  `is_cancelled_boolean` (DV-52), `is_diverted_boolean` (DV-53), the raw `next_flight_id` (AF-20),
  and the descriptive AF-17 through AF-19.
- `RotationLinkValidation` keyed `(AF-01, target_token)` where the terminal token is the literal
  `NO_TARGET`, carrying `rotation_link_status` (DV-24) and `rotation_anomaly_class` (DV-25).
- `Airport` (AP-01) for the `SYN-AP-*` internal-ID endpoints.
- `AircraftDimensionDailyAssignment` for the type and engine enrichment, the same concept Q01/Q03/Q04
  use.

**Rules-authoring first: yes**, and this is the question where it matters most.

- `AircraftFlight.accepted_next_flight`, a derived same-type relationship that exists only when the
  target exists, is a different flight, shares the aircraft and AF-06, departs no earlier than the
  current actual arrival, and departs **from the current actual arrival airport (DV-45 = AF-09)**.
  Authoring this once means the traversal, the anomaly query, and any future path experiment all walk
  the identical edge set.
- The typed anomaly classification with the frozen precedence order `SELF_LOOP`, `CYCLE`,
  `MISSING_TARGET`, `DIFFERENT_AIRCRAFT`, `OUTSIDE_SELECTED_DAY`, `DIVERSION_ENDPOINT_CONFLICT`,
  `BACKWARD_TIME`, `BROKEN_CONTINUITY`, `CANCELLED`, `MISSING_TIME`,
  `UNKNOWN_OR_INVALID_CANCELLATION_FLAG`. Precedence matters because several fixture rows satisfy more
  than one condition.
- Transitive reachability over `accepted_next_flight`, from which come `segment_id`, `leg_order`, and
  cycle detection.
- `type_discrepancy` (DV-32), comparing the as-of type against AF-17.

**Query shape.**

```python
# 1. chain membership and order, from the link structure
Prev = AircraftFlight.ref("prev")
model.where(
    Prev.reaches(AircraftFlight),        # transitive closure over accepted_next_flight
    ...
).select(
    aggs.count(Prev).per(AircraftFlight).alias("_predecessors"),
)
# leg_order = 1 + count of accepted-chain predecessors
# segment start = a flight with no accepted inbound edge
# segment_id  = SYN-ROT-<aircraft_id>-<AF-06 compact>-<segment ordinal>

# 2. enrichment, point-in-time on AF-06 and NOT on AF-07
typ = DailyAsgn.ref("typ"); eng = DailyAsgn.ref("eng")
model.where(
    typ.aircraft == Aircraft, typ.dimension == "aircraft_type",
    typ.valid_from <= AircraftFlight.flight_departure_date,
    AircraftFlight.flight_departure_date < typ.valid_to,
    eng.aircraft == Aircraft, eng.dimension == "engine_type",
    eng.valid_from <= AircraftFlight.flight_departure_date,
    AircraftFlight.flight_departure_date < eng.valid_to,
).select(
    typ.definition_id.alias("as_of_aircraft_type_id"),
    eng.definition_id.alias("as_of_engine_type_id"),
    AircraftFlight.source_aircraft_type.alias("actual_source_aircraft_type"),
    (typ.definition_label != AircraftFlight.source_aircraft_type).alias("type_discrepancy"),
)

# 3. anomalies as a typed companion branch, row_kind = "ANOMALY",
#    leg_order null and every as_of_* column null.
```

**Traps.**

- *Filter-and-sort instead of a chain.* Sorting the day's legs by `actual_gate_departure_time_utc` and
  numbering them reproduces the canonical answer on this fixture and is explicitly a fail
  (`QUERY-ROT`: "No scheduled-arrival shortcut"; the task framing: "A genuine chain, not a
  filter-and-sort"). `leg_order` must come from the accepted-link structure. The cheapest honest
  implementation is `1 + count of accepted-chain predecessors` over the transitive closure.
- *Diversion breaking the endpoint assumption.* Continuity is on AF-09, the **actual** arrival, not on
  the scheduled arrival and not on AF-10. `SOURCE_CONTRACT.md` is explicit that AF-10 never repairs a
  null or conflicting AF-09, and a mismatch between a non-null AF-10 and AF-09 emits
  `DIVERSION_ENDPOINT_CONFLICT` and terminates continuity (flight 8109 in the anomaly fixture). A
  chain built on planned endpoints will look tidier and will be wrong.
- *Plan endpoints leaking into the actual side.* Actual endpoints are `SYN-AP-*` internal IDs resolved
  by `AIRPORT_INTERNAL_ID_EXACT` against AP-01. Planned endpoints are public IATA labels resolved
  against AP-04. They are different code systems; joining actual legs on IATA silently returns nothing.
- *Stopovers.* A single planned passenger service can be fulfilled by several actual legs, so the
  rotation legitimately has more legs than the schedule suggests, and `ExactFulfillment` is one
  passenger flight to many actual legs. Do not de-duplicate legs against the plan.
- *Enriching on the UTC date.* The single sharpest trap in Q08. All three canonical legs have
  AF-06 = 2026-08-31 while AF-07 = 2026-09-01, and their UTC departure timestamps are on
  2026-09-01 (00:30, 02:45, 04:45). Enrichment and day selection use AF-06. Using AF-07, or deriving
  the date from AF-13, shifts the as-of instant by one day and can silently pick the wrong
  type or engine interval. `TT-US-CLOCK-AUTHORITY` freezes this assertion.
- *Suppressing the type discrepancy.* `Q08-R002` has `as_of_aircraft_type_id = SYN-TYPE-B` from
  aircraft history while `actual_source_aircraft_type` reads "Synthetic narrowbody A", giving
  `type_discrepancy = true`. AF-17 through AF-19 are discrepancy evidence and are never aircraft
  history authority. Do not reconcile them; report the disagreement.
- *Cycle duplication.* Flights 8102 and 8103 form a cycle. Emit exactly one `CYCLE` row per cycle
  component, anchored at the minimum `flight_id` (8102), while retaining every member as evidence.
  Emitting one row per member gives 12 anomaly rows instead of 11.
- *Unbounded traversal.* The traversal needs a visited set and a finite step bound, or the cycle
  fixture will not terminate.
- *Losing excluded legs.* `CANCELLED`, `MISSING_TIME`, and
  `UNKNOWN_OR_INVALID_CANCELLATION_FLAG` rows have `link_outcome = EXCLUDED`: excluded from the
  operated chain but still visible as anomaly rows.
- *Ordering.* `row_kind DESC` puts `LEG` before `ANOMALY`. Ascending would invert it.

**Frozen cardinality.** `Q08-CANONICAL` (aircraft 1001, 2026-08-31) exactly 3 `LEG` rows in one
segment `SYN-ROT-1001-20260831-01`: 8001 `SYN-AP-SFO` to `SYN-AP-LAX`, 8002 to `SYN-AP-LAS`, 8003 back
to `SYN-AP-SFO`, the first two `ACCEPTED` and the third `TERMINAL_NO_TARGET`, all enriched to
`SYN-TYPE-B` / `SYN-ENGINE-B`, with `type_discrepancy` true only on 8002. `Q08-ANOMALIES` (aircraft
1099) exactly 11 `ANOMALY` rows and zero `LEG` rows, one per anomaly code, each in its own
`SYN-ANOM-nn` segment with `leg_order` null and all four enrichment columns null.
`Q08-NOT-FOUND` (aircraft 1999) 0 rows with `NOT_FOUND` / `NO_ACTUAL_FLIGHTS`. Order
`segment_id, row_kind DESC, leg_order, flight_id, anomaly_code`.

## Cross-cutting: shared derived properties

Six derivations are used by more than one question. Each belongs in the ontology package under
`MODEL-01`, not in a query module. If they end up duplicated across `uc1.py`, `uc2.py`, and
`rotation.py`, the modules will drift on boundary semantics, the three-module split will produce
inconsistent answers to overlapping questions, and the parity matrix's "one reusable semantic model"
differentiation claim stops being true.

**1. As-of dimension resolution (Q01, Q03, Q04, Q08).** The half-open point predicate
`valid_from <= d < valid_to` over `AircraftDimensionDailyAssignment`, plus `Aircraft.exists_at`, plus
the DV-33 four-value status. Four questions resolve the same type and engine streams at an instant:
Q01 at a parameter date, Q03 at 120 calendar month ends, Q04 across the whole stream, Q08 at each
leg's AF-06. Four independent implementations of one predicate is four chances to get the exclusive
upper bound wrong.

**2. The dense assignment ordinal (Q02, Q04).** A per-`(aircraft, dimension)` integer over the
canonical DV-03 order tuple `(AH-05, AH-03, AH-04, AH-01)` on the audit stream, and over `valid_from`
on the daily stream. Reduces "the previous assignment" and "the next qualifying assignment" from a
four-column lexicographic comparison to a single integer comparison. Q02's spell pairing and Q04's
`previous_definition_id` are the same mechanism at different grains. Best computed in `DATA-04`'s
`MODEL_INPUT` derivation and exposed as a property, since a dense rank is cheap in SQL and awkward to
express repeatedly in PyRel.

**3. Snapshot eligibility (Q05, Q06, and the Q07 universe).** `SnapshotDate.is_eligible` as
`is_present AND is_complete`, plus the previous-eligible-date adjacency relation. Q05 needs adjacency
over the whole window; Q06 needs exact endpoint eligibility with no fallback. One definition, two
consumers with different refusal behaviour, which is exactly why the definition must be shared and
the refusal policy must not.

**4. Schedule presence on the knowledge clock (Q05, Q06, Q07).** `RouteState.visible_at(knowledge)`
as `DV-14 <= k < DV-15`, and schedule-key presence at an eligible snapshot date. Q05 compares presence
across adjacent dates, Q06 compares counts across two dates seven days apart, Q07 uses it as one half
of the two-clock filter. The half-open convention has to be identical in all three or Q06's
zero-crossings and Q07's `active_schedule_count` will disagree about the same schedule.

**5. Carrier-role resolution (Q06, Q07).** The separate marketing and operating exact `Airline` links,
with the rule that only `EXACT` cardinality-one resolution creates a link, and the D-0007 physical
representative rule for the operating role. Both questions take `carrier_role` as a required parameter
with no default and the same typed error on null.

**6. Cabin and capacity derivation (Q07 only today, but stated once).** DV-26
`economy_excluding_premium`, DV-27 `cabin_quality_status`, DV-28 `physical_service_status`. Listed here
because these are the derivations most likely to be written inline as `select` arithmetic, which would
put a five-row frozen truth table (`TT-CABIN-QUALITY`) outside the semantic model.

Properties that should **not** be lifted into the ontology: the per-question output column names, the
result-set ordering, the `event_class_rank` to output-order mapping's application, and the invocation
status and error codes. Those are catalog-layer concerns owned by `QUERY-INT`. The exception is
`event_class_rank` itself, which is a semantic ordering of a semantic enum and belongs on the concept.

## Cross-cutting: recommended build order

The three query modules have disjoint files and can run in parallel once `MODEL-02` lands, but they
are not equally risky and the risk is not evenly distributed inside each module.

**Before any module: prove the optional-dimension shape.** The single highest-risk unknown across all
eight questions is Q01's left-join semantics (see Q01 above). It is a small spike, it determines
whether `MODEL_INPUT` needs to materialize `NO_RECORDED_STATE` intervals, and that answer changes
`DATA-04` and `MODEL-01`, not just `uc1.py`. Run it first, alone, against the live model.

**QUERY-UC1 (Q01 to Q04), in the order Q04, Q02, Q01, Q03.** Q04 is the simplest query in the build
and exercises the whole daily-assignment surface, so it validates the ontology mapping cheaply. Q02
then validates the audit stream and the ordinal, which is the shared derivation with the widest blast
radius. Q01 follows because it needs the optionality answer from the spike. Q03 last, because it is
the only one of the four that depends on the calendar concept and on the multiplicity gate holding,
and because a Q03 count inflation is easiest to diagnose once Q01's point predicate is already proven.

**QUERY-UC2 (Q05 to Q07), in the order Q06, Q07, Q05.** This inverts the numeric order deliberately.
Q06 is a two-row answer over the knowledge clock alone and is the cheapest possible validation that
snapshot eligibility, route-state knowledge validity, and exact carrier resolution all work. Q07 adds
the second clock, multi-open states, and the capacity derivations to a surface Q06 has already proven,
and its truth tables give fine-grained failure signals. Q05 last: it is 35 rows across eight event
classes over a normalized union with the most rules-authoring, and attempting it before the schedule
surface is proven means debugging the amendment classifier and the route-state mapping at the same
time. The Q05 closure section's per-pair row IDs (7 / 5 / 9 / 14) are the diagnostic to lean on.

**QUERY-ROT (Q08), after `ENV-01` and in parallel with UC2.** Q08 depends on UC1's as-of derivation
but not on UC1's queries, so it can start as soon as `MODEL-02` and the shared as-of property exist.
Build it in three stages, each independently checkable: first the validation layer and the 11 anomaly
rows (which need no chain at all and no enrichment, so they isolate the anomaly precedence); then the
accepted-link traversal and `leg_order` on the three canonical legs; then the enrichment join and
`type_discrepancy`. The optional path experiment, if it happens at all, comes strictly after all three
stages are green against the manifest.

**QUERY-INT last**, assembling the three modules without rewriting them, and owning parameter
validation, the typed error codes, the invocation statuses, and the frozen row ordering. Seven of the
24 result sets are parameter or endpoint errors that no RAI query produces; they are catalog behaviour
and they should not leak backwards into the query modules.

## Explicit verdict on Q08: graph reasoner or ordinary self-reference

**Verdict: ordinary typed self-reference is the correct baseline. Neither `rai:rai-graph-analysis` nor
the `std.path` pre-GA module is warranted on current evidence. Do not add
`rai:rai-graph-analysis` to `QUERY-ROT`'s skill list.** This agrees with `TASK_GRAPH.md`,
`SOURCE_CONTRACT.md`, `DEMO_QUESTIONS.md`, and `NEO4J_PARITY_MATRIX.md`, which all say the same thing;
what follows is the reasoning and the test that would be needed to overturn it.

**Why the graph reasoner is the wrong tool, not merely an unnecessary one.** `rai-discovery`'s
`graph.md` routes to `rai-graph-analysis` for centrality, community, components, reachability,
distance, and similarity. Every one of those returns an unordered or scalar result:
reachability gives `(source, target)` pairs, distance gives `(start, end, length)`, WCC gives
`(node, component_id_node)`, centrality gives `(node, score)`. Q08's output schema has 16 columns, of
which 12 are per-leg payload (actual endpoints, actual UTC times, `next_flight_id`, `link_outcome`,
`anomaly_code`, the two as-of enrichment IDs, `actual_source_aircraft_type`, `type_discrepancy`) and
one is `leg_order`. No graph algorithm in that catalogue produces a position within a path or carries
edge payload, so every one of them would have to be joined back to `AircraftFlight` to produce the
answer, which is the self-join the baseline already does. `graph.md`'s own feasibility criteria also
argue against it: the rotation graph is a set of short disjoint chains, so centrality and community
are trivial and multi-hop reachability spans three nodes.

WCC is the one algorithm with a plausible marginal use, for grouping legs into `segment_id` and for
spotting the 8102/8103 cycle. It is still redundant: the transitive closure over
`accepted_next_flight` that the baseline needs anyway for `leg_order` already yields both, and a cycle
is exactly "a node that reaches itself" in that same closure. Adding a `Graph` instance to obtain
facts the closure already gives is added surface for no added answer.

**Why `std.path` is the only real candidate, and why it is not proven.** `std.path` is the only
mechanism in the installed runtime that yields an ordered position, via
`PathTraversal.nodes` (a relationship over `(PathTraversal, Integer:index, AnyEntity:concept)`) and
`PathTraversal.length`. That is genuinely what `leg_order` wants. Four facts from the installed
`relationalai` 1.20.1 package temper it:

- `relationalai.semantics.std.paths` is **deprecated** in this version in favour of
  `relationalai.semantics.std.path`, and importing it emits a `DeprecationWarning`. Note that
  `CLAUDE.md` directs a Phase 4 path question to copy `supply_chain_demo/.claude/skills/rai-pathfinder/SKILL.md`,
  which is written against the deprecated module path; if that skill is ever copied into this repo it
  needs the import corrected first.
- Only `all_paths()` is implemented. `shortest_paths()`, `undirected()`, and `reverse()` all route
  through `throw_if_not_implemented` and raise.
- `all_paths()` enumerates every matching path, including proper prefixes and suffixes. For the
  canonical chain 8001 to 8002 to 8003 with `repeat(min=1, max=N)`, it returns the sub-paths as well as
  the full chain, so recovering the one maximal chain still requires the same "source has no accepted
  inbound edge, target has no accepted outbound edge" filter the baseline uses. The path library
  removes no work here; it adds a de-duplication step.
- `all_paths()` installs a compile hook (`_reject_invalid_unification`) that raises when an enclosing
  `where`, `select`, or `define` references a binder interior to the path pattern, and the source
  comments note that filters spanning multiple edges are handled as residual post-filters. Q08's
  per-edge validation is inherently two-endpoint (same aircraft, same AF-06, non-decreasing time,
  arrival airport equals next departure airport) and its per-leg enrichment is inherently
  interior-node-referencing. That is precisely the shape the hook constrains.

**The test that would justify adding it.** Run this only after all three Q08 stages are green against
the manifest, and treat it as optional throughout.

*Precondition.* `AircraftFlight.accepted_next_flight` already exists as a validated derived
relationship authored via `rai:rai-rules-authoring`, so both implementations traverse an identical
edge set and the comparison is about traversal only, not about validation.

*Procedure.* Against the live demo model under `RAI_DEMO_AVIATION_TEMPORAL`, on the installed
`relationalai` version, using the non-deprecated import:

```python
from relationalai.semantics.std.path import path
p = path(AircraftFlight.accepted_next_flight).repeat(min=1, max=10).all_paths()
```

then select `PathTraversal.length` and the indexed `PathTraversal.nodes`, restricted to maximal paths
and to aircraft 1001 with AF-06 2026-08-31.

*Pass conditions, all five required.*

1. It executes without error on the installed version against the demo engine. A `NotImplementedError`
   or a deprecation-removal failure ends the test.
2. The ordered node sequence is exactly `[8001, 8002, 8003]`, with `nodes` indices 0, 1, 2 mapping to
   `leg_order` 1, 2, 3, and the result contains exactly one maximal path for the segment.
3. Run against the aircraft 1099 fixture it returns no accepted path, and against the 8102/8103 cycle
   it terminates under the `repeat` bound without fabricating rows or hanging.
4. The per-leg enrichment (as-of type and engine on AF-06, actual times, `link_outcome`) and the
   `segment_id` derivation can be joined onto the path result **without** tripping the interior-binder
   hook, and without a workaround that reintroduces the self-join the path was meant to replace.
5. Warm-engine wall time is no worse than the baseline, measured by `QUERY-INT`'s timing harness.

*Value bar, applied after the pass conditions.* Passing is necessary but not sufficient. The path
implementation must **remove** code relative to the closure baseline. If the maximal-path filter plus
the interior-binder workaround make it longer or less legible than
`leg_order = 1 + count of accepted-chain predecessors`, the test has passed technically and failed on
value; keep the baseline. `NEO4J_PARITY_MATRIX.md` already prohibits stating that graph path
enumeration is required or proven before this gate, and both `SOURCE_CONTRACT.md` and `TASK_GRAPH.md`
require the optional implementation to return an identical fixture chain to the baseline if it ships
at all.

*On failure or on a value-bar miss.* Record the outcome in `DECISION_LOG.md` as an append-only entry,
keep the self-reference baseline, and narrow the demo narrative accordingly. Do not present a path
implementation as parity evidence.

## Out of scope, stated so it stays that way

None of the eight questions defines an optimization objective, a decision variable, a constraint over
contested resources, or a prediction target. `rai:rai-prescriptive-problem-formulation`,
`rai:rai-prescriptive-solver-management`, `rai:rai-prescriptive-results-interpretation`,
`rai:rai-predictive-modeling`, and `rai:rai-predictive-training` are therefore not part of any route
in this document. `AGENTS.md` states this as a standing instruction and
`DEMO_QUESTIONS.md`'s interface-wide negative behaviour requires curated callers to reject
optimization and prediction requests outright. Inventing a fleet-assignment MIP or a delay predictor
to "strengthen the demo" would break the frozen answer contract and the parity claim boundary at the
same time. If a real optimization or prediction target is ever wanted, it is a scope change through
`DECISION_LOG.md`, not an enhancement to one of these eight.
