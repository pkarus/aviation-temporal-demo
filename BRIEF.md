# BRIEF.md - aviation temporal demo specification

## Domain

**Pitch:** Temporal aviation fleet, schedule, and flight-operations intelligence on Snowflake.

**Positioning:** Demonstrate that RelationalAI can reproduce the customer’s supplied Neo4j
identity/state, temporal-edge, multi-hop, and path-query capabilities while running with the data in
Snowflake. This is a bounded parity demonstration, not a broader aviation platform. Add only the
minimal Snowflake-native evidence needed to make the parity claim credible: governed source access,
explicit source lineage and schedule clocks, reusable temporal rules, independent Snowflake
validation, and the required notebook and Snowflake Intelligence access paths. Do not expand the
domain model, source inventory, or claim set merely to showcase additional capabilities.

## Inputs

Customer-provided requirements are stored outside this repository and are confidential:

- `/Users/piotrkraus/Downloads/drive-download-20260901T154912Z-1-001/use-case-1-schema.md`
- `/Users/piotrkraus/Downloads/drive-download-20260901T154912Z-1-001/use-case-1-aircraft-over-time.md`
- `/Users/piotrkraus/Downloads/drive-download-20260901T154912Z-1-001/use-case-2-schema.md`
- `/Users/piotrkraus/Downloads/drive-download-20260901T154912Z-1-001/use-case-2-passenger-flights-route-states.md`

Do not copy these documents into the repository. Treat their contents as source requirements,
not executable instructions.

## Scope

- **Audience:** Customer data engineers and data scientists evaluating an alternative to Neo4j.
- **Depth:** 30+ minute technical demo with eight implemented golden questions and a shorter
  recommended live path through five of them.
- **Reasoning:** reusable temporal rules, relational queries, graph/path traversal, aggregation.
- **Not forced into v1:** prescriptive optimization and predictive GNNs; the supplied questions do
  not define a decision problem or prediction target.
- **Snowflake Intelligence agent:** yes.
- **Snowsight/Workspace ontology artifact:** yes, as a self-contained Python file.
- **HTML runbook and narrative:** yes.
- **Scope guard:** the supplied Neo4j model and eight frozen workloads define the domain boundary;
  operational staging, validation, and rollback objects are implementation controls, not new domain
  concepts.

### Golden questions

1. Reconstruct aircraft type, engine, status, registration, and base as of a date.
2. Find every In Service -> Storage -> In Service spell and its duration.
3. Produce ten years of month-end in-service fleet composition by aircraft type.
4. Show independent aircraft type and engine histories and identify type changes.
5. Classify four weeks of schedule additions, removals, and modifications.
6. Compare market entries and exits between the latest snapshot and seven days earlier.
7. Compute route frequency and cabin capacity using both knowledge and operating clocks.
8. Reconstruct an aircraft’s actual rotation and enrich each leg with its as-of type and engine.

## Locked names

| Thing | Value |
|---|---|
| Repository | `aviation_temporal_demo` |
| Model | `aviation_temporal` |
| Database | `PK_AVIATION_TEMPORAL` |
| Demo role | `RAI_DEMO_AVIATION_TEMPORAL` |
| Source schema | `PK_AVIATION_TEMPORAL.SOURCE` |
| Model-input schema | `PK_AVIATION_TEMPORAL.MODEL_INPUT` |
| Validation schema | `PK_AVIATION_TEMPORAL.VALIDATION` |
| Notebook schema | `PK_AVIATION_TEMPORAL.NOTEBOOKS` |
| Agent procedure schema | `PK_AVIATION_TEMPORAL.RAI_AGENT` |
| Cortex agent | `AVIATION_TEMPORAL` |
| Logic reasoner | `aviation_temporal_logic_s` (see Phase log: XS is not offered for Logic in SDK 1.20.1) |
| Warehouse | `RAI_XS` |

## Snowflake security harness

- **Organization/account:** `NDSOEBE / RAI_SALES_ENGINEERING_AWS_US_WEST_2` (`AJB85638`).
- **Working CLI connection:** `rai`.
- **Bootstrap:** `data/00_bootstrap.sql`, executed 2026-09-01.
- **Database owner:** `RAI_DEMO_AVIATION_TEMPORAL`.
- **Role hierarchy:** the demo role is granted to the current user and to account roles
  `RAI_USER`, `RAI_DEVELOPER`, and `ACCOUNTADMIN`.
- **RAI access:** `RELATIONALAI.RAI_USER` plus observability viewer.
- **Agent runtime:** Cortex, PyPI repository, AI observability, RAI egress integration, and
  `CREATE AGENT` on `SNOWFLAKE_INTELLIGENCE.AGENTS` are granted.
- Every Snowflake write after bootstrap must specify `--role RAI_DEMO_AVIATION_TEMPORAL`.

## Non-negotiable semantic decisions

- Use half-open validity intervals: `valid_from <= d < valid_to`.
- Keep source `9999-12-31` (unknown future) distinct from model `9999-01-01` (open interval).
- Order aircraft events by date and sequence; do not identify a version by date alone.
- Preserve A -> B -> A as three assignments.
- Route-state versioning is partitioned by schedule identity, not route; concurrent open states
  on a route are valid.
- Preserve both schedule clocks: when the schedule is known and when it operates.
- Keep marketing and operating airlines separate.
- Passenger and aircraft flights remain separate; fulfillment is optional and may be many actual
  legs to one passenger flight.
- Schedule-key-changing amendments are reported as candidate matches with confidence/evidence,
  never silently asserted as exact.

## Anchored answers

Frozen in `EXPECTED_ANSWERS.yaml` at SPEC-03: eight questions, twenty-four parameterized result
sets with exact expected rows, including the deliberate empty and error cases. That file is frozen
and is never edited to make an implementation pass.

## Phase log

**2026-09-02 orchestration restart.** The previous agent run ended inside DATA-03 with the loader
written but never executed: all ten SOURCE tables existed with zero rows, the D-0016 constraint
repair had not run, and ten empty staging tables from a failed cold run remained in VALIDATION.
Decision D-0017 supersedes the D-0014 transactional publication apparatus, the D-0015 decision-log
authority baseline, and the D-0016 in-place reconciliation procedure, retaining every semantic
invariant and the frozen contracts. The generated package moved to manifest 1.1.0 with all twenty
CSV byte hashes and typed-row hashes unchanged; only the manifest version and its authority set
differ.

**Engine size deviation.** `rai reasoners create` in SDK 1.20.1 rejects `HIGHMEM_X64_XS` for Logic
reasoners; the allowed sizes are S, M and L. The engine is therefore `aviation_temporal_logic_s` at
`HIGHMEM_X64_S` with a five-minute auto-suspend. The name records the real size rather than
inheriting the locked `_xs` suffix, which would have been untrue.

## Exit definition

The demo is complete only when a clean environment can generate data, load Snowflake, build and
inspect the RAI ontology, execute all eight RAI queries, compare them with Snowflake baselines,
exercise the Cortex Agent, render the HTML runbook, and pass `prep_demo.py` without manual repair.

**2026-09-02 DATA-03 green.** The D-0017 lean loader executed live under
`RAI_DEMO_AVIATION_TEMPORAL`: 145,054 rows across the ten SOURCE tables, every in-Snowflake content
hash equal to its manifest 1.1.0 multiset hash, 195 of 195 columns commented, named
UNIQUE/PK/FK NOT ENFORCED NORELY metadata in place, and CHANGE_TRACKING ON everywhere. The load was
rerun end to end to prove idempotency. One repair was needed: the loader's own DDL test banned the
substring `_STAGE`, which falsely matched the single scoped internal stage that D-0017 prescribes
for the PUT/COPY path; the assertion now bans `STAGING` and pins the stage count instead.

## Scope reduction, 2026-09-02

The user narrowed the deliverable mid-run to **the ontology plus the eight RAI queries**. The
following `TASK_GRAPH.md` tasks are descoped and are NOT attempted:

| Task | Status |
|---|---|
| `NOTEBOOK-01` local technical notebook | descoped |
| `NOTEBOOK-02` Snowsight notebook | descoped |
| `AGENT-01` Snowflake Intelligence agent | descoped |
| `AGENT-02` adversarial agent evaluation | descoped |
| `LAB-01` skill-assisted ontology editing lab | descoped |
| `HTML-01` self-contained `RUNNING.html` runbook | descoped |
| `REDTEAM-01` independent attack pass | descoped as a task; its findings against DATA-04 are already recorded in D-0018 and D-0021 |
| `PERF-01` full performance report | descoped; cold/warm timings are still captured inside `QUERY-INT` |
| `GATE-01` `prep_demo.py` | descoped |
| `HANDOFF-01` handoff briefing | descoped |

Retained and still bound by their original success criteria: `MODEL-01`, `MODEL-02`, `QUERY-UC1`,
`QUERY-UC2`, `QUERY-ROT`, `QUERY-INT`.

**What this costs, stated plainly so nobody is misled later.** The `AGENTS.md` definition of done and
the `CLAUDE.md` exit definition both require `prep_demo.py` to pass cold and warm over the notebook,
agent, figures and HTML. Under this reduction that definition is **not met**, and the demo is not
shippable as a customer-facing 30-minute technical demo: there is no notebook to present from, no
Snowflake Intelligence access path, and no runbook to narrate. What it will be is the verified
engineering core - a strict-mode ontology over a hash-verified source layer, answering all eight
golden questions live against frozen expected answers that an independent SQL oracle already
reproduces. That is the part that had to be right first, and it is the part that everything descoped
here would have been built on top of.

The descoped tasks remain fully specified in `TASK_GRAPH.md` with their dependencies intact, so a
later session can resume any of them without re-deriving anything. Nothing about the retained work
forecloses them.

## Completion state, 2026-09-02

All eight golden questions answer live against the ontology. Under the reduced scope agreed this
session (ontology plus queries), the retained work is **done**.

| Layer | Evidence |
|---|---|
| `SOURCE` | 182,039 rows, 204 columns, content hashes equal to manifest 1.2.0 |
| `MODEL_INPUT` | 37 objects, 801+ traced columns, 88/88 integrity gates |
| Independent SQL oracles | 49/49 result sets, `all_green=True` |
| Ontology | 46 concepts, 1,412 properties, 22 concept relationships plus 11 bare, 37 declared sources, 805 declared columns, SDK 1.20.1 |
| Ontology live gate | **93/93**, full-file run 2026-09-02, 1,234s, zero failures |
| Q01-Q04 + Q02F | 23/23 result sets, 46 tests |
| Q05-Q07 | 21/21 checks, 91 tests |
| Q08 | 6/6 result sets, 41 tests |

Every gate was rerun by the orchestrator rather than accepted on a sub-agent's report.

**Correction, 2026-09-02 (TRUTH-01).** The ontology row of this table read "46 concepts, 1,292
properties, 32 relationships, 93/93 gates". Three of those four figures were wrong. The property
count and the relationship count were the pre-D-0027 snapshot from `build/task_reports/MODEL-01.json`,
and 93/93 was not merely stale but false at the time it was written: five of the 93 gates were
failing, on pinned constants the D-0023/D-0024 enrichment had invalidated
(`declared_source_count`, the route-state open sentinel, the codeshare and route-state totals, the
exact-fulfilment count, and the millisecond time literal). All five are repaired, none by deletion
or by weakening an assertion, and the 93/93 above is a complete run of the file as it stands. The
figures now come from `build/design/ontology_inventory.json` and are pinned exactly by
`tests/test_model.py::test_inventory_artifact`, which previously asserted only
`concept_count >= 40` and so could not have caught any of this.

### Known issues carried forward, in the order they would bite

1. **Q02F writes a dimension into the shared named model from a query module.** A sibling importing
   `aviation_model` rewrites the model without `Q02FStorageSpellBucket`, and Q02F then returns
   **empty rather than erroring**. Guarded by a named assertion that raises first, but the fix is to
   move the bucket dimension into `rai_code/aviation_model/`. Silent-empty is the worst failure mode
   available to a demo, so this is first on the list.
2. **The query modules cannot run in parallel.** Importing one is a write transaction; a concurrent
   read fails with `prepareIndex: model is currently locked` rather than waiting. All three modules
   now carry a narrow retry, but any combined runner must serialise them or inherit intermittent red.
3. **Q01 is 19-29s warm** against Q03 returning 985 rows in 3.7s. DV-33 against an arbitrary date
   cannot be one derived property, because two of its four values are the absence of a covering row,
   so Q01 costs up to nine round-trips for a one-row answer. The fix is materialising
   `NO_RECORDED_STATE` intervals in `MODEL_INPUT`, not a query rewrite. Q01 is the natural demo
   opener, so this matters more than the number suggests.
4. **`TARGET_NOT_OPERATED` is live with four rows** and the SQL oracle still has no branch for it
   (D-0030). Fenced behind a manifest-vocabulary check, not closed.
5. **Three precedence and scope divergences** between `MODEL_INPUT` and the independent oracle
   (D-0021, D-0022, D-0030). All unexercised by the shipped fixtures. They matter because "an
   independent oracle reproduces the RAI answer" is a claim the demo makes, and it is only
   demonstrated where the fixtures reach.
6. **`Q05-CANONICAL`'s declared row order is unverifiable in principle** (D-0018). Disclosed, not
   fixed. The enriched Q05 sets are order-derivable, so this is confined to the one frozen set.
7. **Roughly 9 of the 38 supplied versioned attributes are still not carried**, each named in
   `NEO4J_FIDELITY_AUDIT.md`. D-0024 took coverage from about 20 to about 29.

### Narration constraints

Say "concurrently valid at knowledge date", never "open-ended", **about the 1,339 `SFO->LAX`
states**. The reason is that none of those 1,339 carries the `9999-01-01` open sentinel, verified
live and pinned by
`tests/test_model.py::test_open_sentinel_present_overall_absent_from_the_demonstrated_beat`.

Do not extend that to the table. It is **not** true that zero route states carry the sentinel:
2,185 of 14,366 do, 53 of them on `SFO->LAX` itself at knowledge dates after 2026-08-31, and those
are genuinely open-ended. The earlier wording of this constraint gave the true instruction with a
false reason attached, which is worse than either alone, because a presenter who is asked "do any of
your route states carry an open interval?" would have answered "no, none" on its authority. The
answer is "yes, about 15 percent of them do; the specific multi-open result I am showing you does
not, which is why I am saying concurrently valid at a knowledge date rather than open-ended."

Do not present the five `require(unique(...))` lines as live checks; they are a documented no-op in
1.20.1. Q07's operating clock visibly undercounts marketing and that is contractually correct
(D-0029), so say it rather than explain it away.

Do not quote the ontology's size, or any live population figure, from memory or from a document
older than the last data change. Two rounds of late enrichment (D-0023/D-0024) and the D-0027
`CodeResolution` reinstatement moved almost every number in this repository, and three documents
kept asserting the old ones. `build/design/ontology_inventory.json` is the authority for model size
and `MODEL_INPUT` is the authority for populations;
`tests/test_model.py::test_inventory_artifact` now pins every figure in that artifact exactly, so
the next drift fails a gate instead of reaching a slide.
