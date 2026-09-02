# SPEC-03 scoped Neo4j-to-RAI parity matrix

## Claim boundary

This matrix defines what the release may claim after, and only after, the named live gates pass. It
does not claim a universal Neo4j replacement, production sizing, performance, cost, or security
superiority. It covers the supplied identity/state, temporal, multi-open schedule, two-clock,
multi-hop, and rotation workloads on deterministic representative-shape data.

All operational rows are explicitly synthetic under D-0009. Named routes are U.S.-domestic
scenarios whose endpoints come from the closed `SFO/LAX/LAS/SEA/DEN/ORD/PHX/BOS/MIA` public-airport
whitelist. Public airport codes, names, and IANA time-zone names are geography labels, not observed
facts. Planned endpoints use public IATA labels; actual endpoints use `SYN-AP-*` internal IDs.
Carriers, registrations, schedules, aircraft display identities, passenger tokens, capacities,
times, and actual-flight facts are fictional. The ontology does not derive country or domestic
classification.

Under D-0010/D-0011, the schedule questions share one unfiltered source universe. Q05 must expose
every exact change forced by Q06/Q07 fixtures; no fixture-family filter or question-private universe
is allowed. The five August weekly dates are the only eligible complete dates in the Q05 window.
The missing/incomplete control is isolated to October 5/12/19/26 so it cannot violate adjacency.

Under D-0012, manifest v1.1.1 also binds the null-source-ID passenger lineage to the 610-byte
`dv43-lp-v1` known-answer. Its DV-46 identity is `FORWARD|` plus the independently verified
64-lowercase-hex SHA-256 digest; `SYN-PAX-VALID-NULL-ID-01` remains presentation-only. This narrow
repair changes no business result, row ID, cardinality, schedule event, or Q05/Q06/Q07 result set.

`EXPECTED_ANSWERS.yaml` version `1.1.1` is the independent authority. A row below becomes `PROVEN`
only when its complete SQL and RAI result sets independently equal the frozen result sets and every
named boundary/negative assertion passes. Before that, status is `DESIGNED_NOT_YET_EXECUTED`.

**Status column advanced 2026-09-02 (TRUTH-01).** All eight rows read
`DESIGNED_NOT_YET_EXECUTED` until today, months of work after they were in fact executed. Read
literally, that column forbade saying any of this matrix's own "Allowed parity statement"
sentences, while the rest of the repository recorded the questions as answering live. A gating
column nobody advances is not a conservative gate, it is a dead one, and the gap between it and
`BRIEF.md` was the finding. Every row is now `RAI_PROVEN`, against the live evidence below, and
**no row is `PROVEN`** - see the two paragraphs after the evidence state machine for exactly what
is missing and why.

Evidence for the advance, all rerun by the orchestrator today rather than accepted from a
sub-agent's report:

| Rows | Live evidence | Source |
|---|---|---|
| Q01-Q04 | 23/23 frozen result sets reproduced cell for cell, 46 tests passed | `build/task_reports/QUERY-UC1.json`, `tests/test_uc1.py` |
| Q05-Q07 | 21/21 checks, 20/20 result sets in declared order | `build/task_reports/QUERY-UC2.json`, `tests/test_uc2.py` |
| Q08 | 6/6 result sets, including the empty and typed-error cases | `build/task_reports/QUERY-ROT.json`, `tests/test_rotation.py` |
| All eight, independently | 49/49 SQL oracle result sets, `all_green=True` | independent Snowflake SQL oracle |
| Ontology under all of them | 93/93 live gates | `tests/test_model.py` |

## Workload matrix

| Query | Supplied capability in scope | RAI representation and execution shape | Frozen evidence | Allowed parity statement after G6 | Snowflake-native differentiation after evidence | Required limitation | Current status |
|---|---|---|---|---|---|---|---|
| Q01 `aircraft_as_of` | Point-in-time aircraft state across type, engine, lifecycle status, registration, and base | `Aircraft` plus four independent `AircraftDimensionDailyAssignment` association streams, half-open point predicates, existence clipping, and per-dimension DV-33 status | `Q01-CANONICAL`, `Q01-BEFORE-FIRST`, `Q01-UNKNOWN-GAP`, `Q01-EOL-BOUNDARY`; HT-02/05-10/39/40 | “For the frozen aircraft/date and boundary fixtures, RAI reconstructs the same complete results as the independent manifest and SQL oracle.” | Source-resident history, RBAC, source lineage, and SQL/RAI comparison use the same Snowflake security boundary | EOL exclusivity is provisional; master-only current values do not backfill history; exact mixed fitment is unsupported | `RAI_PROVEN` |
| Q02 `status_reversion_spells` | Temporal sequence traversal over repeated status assignments | Ordered `AircraftStatusAuditAssignment` associations preserve source event identity/sequence; deterministic derivation pairs every Storage assignment with the next qualifying return | `Q02-CANONICAL`, `Q02-NO-SPELLS`; HT-01/03/04/05 | “For the frozen ordered status fixtures, RAI returns every supplied reversion spell, including the same-day zero-calendar-day occurrence.” | Audit lineage and SQL sequence evidence remain beside reusable semantic rules | Date-plus-sequence gives order, not intraday duration | `RAI_PROVEN` |
| Q03 `month_end_fleet_composition` | Long-range temporal aggregation by aircraft type and status | Month calendar joined to independent type/status daily assignments and Aircraft existence, grouped at `(month_end,type)` | `Q03-CANONICAL`: 132 rows, 120 distinct month ends; HT-02/05/08/09/42 | “For the frozen ten-year synthetic population, RAI and SQL independently reproduce all 120 month-end composition points.” | Governed source, calendar, model rule, SQL baseline, and visualization can coexist in Snowflake | Representative-shape functional evidence only; no production-scale or performance inference | `RAI_PROVEN` |
| Q04 `type_engine_histories` | Independently temporal aircraft-to-type and aircraft-to-engine relationships | Separate type and engine daily association concepts with independent validity, resolution, count/completeness payload, and type-change derivation | `Q04-CANONICAL`; HT-04/05/39/40 | “For the frozen aircraft, RAI reproduces the independent type and engine histories without forcing their boundaries to align.” | Source configuration lineage and relationship payload are inspectable beside SQL validation | Only one reported engine type and count are available; second type/fitment is never fabricated | `RAI_PROVEN` |
| Q05 `schedule_four_week_changes` | Snapshot-to-snapshot additions, removals, and modifications | `ScheduleExactChange` preserves exact key/content facts; separate `ScheduleAmendmentEvidence` preserves medium candidates, low ambiguous groups, members, and unpaired facts over one unfiltered universe | `Q05-CANONICAL` 35 rows (22 exact + 13 evidence) plus October `Q05-INELIGIBLE-ENDPOINT`; `CROSS-QUESTION-EVENT-CLOSURE-V1.1`; HT-12/13/15-22/49; D-0010/D-0011 | “For the four frozen adjacent complete weekly comparisons, RAI matches all 35 exact/evidence rows and preserves bounded candidate/ambiguity classifications without promoting them.” | Snowflake completeness controls, deterministic reduction, SQL reconciliation, RAI rules, and lineage are jointly governed | No stable amendment ID; non-overlapping key shifts may remain unpaired; missing/incomplete snapshots prove no absence; functional synthetic scope is not a performance claim | `RAI_PROVEN` |
| Q06 `market_latest_vs_seven_days` | Market entry/exit set difference across schedule snapshots | Eligible endpoint filtering and deterministic classification at `(carrier_role, exact airline, directional route)` over the same unfiltered universe | `Q06-CANONICAL` exactly 2 rows, October `Q06-INCOMPLETE-ENDPOINT`, `Q06-MISSING-CARRIER-ROLE`; Q06 canonical v1.0 hash preserved; HT-12/14/26/29/38/48; D-0010/D-0011 | “For the frozen exact endpoints and marketing role, RAI returns the same two-row entry/exit set as the manifest and SQL oracle and refuses ineligible endpoints.” | Completeness evidence and exact resolution status remain visible with the semantic result | Ambiguous carrier resolution cannot create an exact airline market; this is a knowledge-clock comparison; stable positive market shadows deliberately prevent unrelated zero-crossings | `RAI_PROVEN` |
| Q07 `route_capacity_two_clocks` | Active route-state frequency/capacity under knowledge and operating time | Multi-open `RouteState` associations, required DV-30/DV-31 clocks, weekday predicate, separate marketing/operating Airline roles, D-0007 physical representative, and cabin-quality derivations | All Q07 v1.0 result sets/hash unchanged: 3 marketing + 2 operating canonical rows, knowledge-end empty, and typed errors; four terminal deltas, clock null→`PHX`→null, operating-ineligible shadow; truth tables; HT-18/23-29/38/48; D-0010 | “For the frozen clock/carrier scenarios, RAI reproduces the unchanged five canonical route-frequency/capacity rows, keeps marketing and operating results distinct, and does not double-count the proven physical representative.” | Shared governed schedules, quality evidence, reusable clock rules, SQL oracle, and curated agent parameters are one Snowflake workflow | Codeshare-only physical service is unresolved and excluded without a stable service-group ID; UTC `TIME` alone remains unresolved; the clock shadow is construction evidence, not an additional target row | `RAI_PROVEN` |
| Q08 `actual_rotation_enriched` | Multi-hop actual aircraft rotation and aircraft-history enrichment | Validated AF-20 `next_flight` self-reference with visited set/step bound, actual continuity/time/date rules, typed anomalies, and per-leg type/engine as-of joins | `Q08-CANONICAL`, `Q08-ANOMALIES`, `Q08-NOT-FOUND`; `TT-US-CLOCK-AUTHORITY`; `TT32-R11` D-0012 lineage known-answer; HT-30-40/42/49 | “For the frozen actual-leg chain and anomaly fixtures, ordinary RAI self-reference traversal reproduces the supplied rotation workload and enriches each valid leg from independent aircraft history.” | Actual operations, plan/actual distinction, history, SQL validation, semantic traversal, and agent access remain governed together | This is not arbitrary path analytics; actual endpoints/times never borrow plan values; optional graph paths require live equality and added value; passenger presentation labels never substitute for lineage identity | `RAI_PROVEN` |

## Representation-level parity

| Supplied graph shape used by the eight questions | RAI equivalent | Parity treatment | Intentional evidence-preserving difference |
|---|---|---|---|
| `AIRCRAFT` identity | `Aircraft` identified only by AM-01 | Direct identity parity after eligibility/uniqueness proof | Existence bounds and source lineage are explicit; registration/type/status are not identity |
| `AIRCRAFT-[:HAS]->AIRCRAFT_STATE` | state audit and daily assignment associations | Daily point-in-time projection plus full ordered audit stream | Avoids date-key collision and preserves earlier same-day facts |
| `AIRCRAFT-[:CONFORMED]->AIRCRAFT_TYPE` | type audit/daily association to optional exact `AircraftType` | Temporal relationship parity | Missing configuration opens an unresolved gap rather than dropping history |
| `AIRCRAFT-[:EQUIPPED]->ENGINE_TYPE` | engine audit/daily association to optional exact `EngineType` | Temporal relationship parity for the one reported type | Count/completeness stay on assignment; no complete mixed set is asserted |
| `AIRCRAFT-[:ASSIGNED]->AIRCRAFT_STATUS` | status audit/daily assignments | Date-visible parity plus sequence/spell semantics | Same-day reversion remains auditable even when daily state begins/ends equal |
| `ROUTE-[:HAS]->ROUTE_STATE` | Route-to-RouteState one-to-many association | Direct multi-open parity | Version partition is Schedule, preventing false one-open-per-route constraint |
| route `STARTS`/`ENDS` | labeled Route origin/destination relationships | Exact link only at cardinality one | Raw planned IATA and resolution candidates remain visible when unresolved |
| airline `OPERATES`/`COMMERCIALIZES` | separate operating/marketing relationships | Direct role parity | Missing role is an error/clarification, never a default |
| `ROUTE_STATE-[:SCHEDULES]->PASSENGER_FLIGHT` | `RouteStateSchedules` clock-qualified scheduling relationship, derived in `computed_schedule.py:155-169` | Bounded plan-link parity, **declared, evaluated and populated: 7,950 live pairs**, but read by no frozen fixture | Typed historical/forward union and source precedence are explicit. *Revised 2026-09-02 (TRUTH-01): this cell read "**declared and evaluated but unexercised by the shipped fixture: zero live pairs**... `schedule_key` is non-null on 1 of 19,996 canonical passenger flights and that key has no route state. Do not present this row as demonstrated parity until the fixture populates it." The D-0023 enrichment populated it on purpose; the cell was never updated.* Measured 2026-09-02 by a SQL replica of the rule: `schedule_key` is non-null on 7,951 of 19,446 canonical passenger flights and 7,950 of those satisfy the full four-clause conjunction, over 2,000 distinct route states. The remaining limitation is coverage, not population: no `EXPECTED_ANSWERS.yaml` scenario reads a value through this relationship, so present it as **implemented and populated, not graded by a golden-question fixture** |
| `AIRCRAFT_FLIGHT-[:FULFILLED]->PASSENGER_FLIGHT` | `ExactFulfillment` association | Optional one-to-many parity where shared source ID proves it | Heuristic and ambiguous candidates are separate and never satisfy the exact edge; null source IDs use D-0012 `FORWARD|<DV-43>` lineage rather than a display alias |
| actual flight `STARTED`/`ENDED` | labeled actual-origin/destination links to `SYN-AP-*` Airport identities | Direct actual-endpoint parity | Planned IATA never repairs or overwrites actual endpoints |
| actual flight `NEXT_FLIGHT_ID` path | validated same-type self-reference | Required Q08 parity baseline | Invalid edges become typed anomaly evidence; graph path enumeration is optional |

## Evidence state machine

1. `SPECIFIED`: this contract and the frozen manifest exist and parse; the D-0012 610-byte
   `dv43-lp-v1` known-answer yields the exact 64-lowercase-hex DV-43/DV-46 token.
2. `EVENT_CLOSED`: one-universe materialization independently recomputes Q05 counts `7,5,9,14`,
   accounts for every exact addition/removal exactly once, returns only the two Q06 market
   zero-crossings, preserves the Q06 canonical hash, and preserves the full Q07 result-set hash.
3. `SQL_PROVEN`: the independent raw-fixture SQL oracle returns the exact manifest rows.
4. `RAI_PROVEN`: the live RAI query returns the exact manifest rows under the demo role.
5. `PROVEN`: all prior states, all named hard tests, freshness, and claim scans pass.

No UI, notebook, agent, or HTML may present a row as proven before state 5. SQL/RAI agreement without
manifest equality is insufficient. Missing/incomplete endpoints, unknown configuration gaps,
unresolved code/capacity cases, anomalies, and exact empty results remain part of the evidence.

**Why every row stops at `RAI_PROVEN` and not `PROVEN`, 2026-09-02 (TRUTH-01).** States 1 through
4 are satisfied for all eight rows: the manifest parses, the one-universe materialization closed,
the independent SQL oracle returns 49/49 result sets green, and the live RAI queries return the
frozen rows cell for cell. State 5 additionally requires "all named hard tests, freshness, and
claim scans". Two of those are not satisfied:

* **Claim scans.** `CLAIMS_AUDIT.md` found six false and one overbroad customer-facing claim in
  this repository on 2026-09-02, including two in this very file. They are corrected now, but a
  claim scan that has just failed and been repaired is not a claim scan that has passed clean;
  the next one has to run against the corrected text before state 5 is honest.
* **The descoped delivery surface.** `BRIEF.md` records that the notebooks, the Snowflake
  Intelligence agent, the HTML runbook and `prep_demo.py` were descoped mid-run. The rule above
  says no UI, notebook, agent or HTML may present a row as proven before state 5; with none of
  them built, state 5's freshness and end-to-end conditions are not merely unmet, they are
  unmeasurable.

`RAI_PROVEN` is therefore the highest state the evidence supports, and it is a real one: for the
frozen, named parameters, the live RAI query and an independent SQL oracle both return the frozen
rows. Say that. Do not say `PROVEN`, and do not read `RAI_PROVEN` as a general claim.

**Scope limit on the oracle-agreement sentences.** Every "Allowed parity statement" above is
scoped to "the frozen fixtures" and must stay scoped that way in the room. Three precedence and
scope divergences between `MODEL_INPUT` and the independent SQL oracle are known and recorded in
`DECISION_LOG.md` D-0021, D-0022 and D-0030: rotation anomaly precedence for a cancelled target,
cycle-detection scope, and the `TARGET_NOT_OPERATED` anomaly class, which is live with four rows
and has no oracle branch at all. None is exercised by any frozen fixture, which is why the
statements above survive. If a live question strays outside the frozen parameters - a rotation
whose next leg is itself cancelled, for example - say that the oracle has no branch there rather
than extending the agreement claim to cover it.

## Differentiation allowed after proof

- Data residence in the scoped Snowflake database and execution under the reviewed demo-role graph.
- Snowflake RBAC/governance applied to source, canonical inputs, SQL validation, notebook, and agent.
- One reusable semantic model for the eight bounded workloads instead of query-local temporal rules.
- Complete independent expected-manifest and Snowflake-SQL comparison of every RAI result.
- The same curated query catalog callable from Python, notebooks, and Snowflake Intelligence.
- Source lineage, resolution ambiguity, snapshot completeness, candidate confidence, quality flags,
  and plan/actual separation remaining queryable rather than being flattened from the narrative.

These are architectural/workflow differences, not claims that one database is universally faster,
more scalable, cheaper, more secure, or better.

## Prohibited statements

- “RAI replaces every Neo4j workload.”
- “RAI is faster, cheaper, more scalable, or more secure.”
- “Synthetic timings establish production sizing.”
- “A candidate key shift is an exact schedule amendment.”
- “Codeshare-only capacity is the exact physical capacity.”
- “The supplied schema identifies a complete mixed-engine set.”
- “The ontology inferred that a flight is domestic” or that any synthetic row describes a real
  carrier's operation.
- “A passenger presentation token is a DV-43 digest or source-row identity.”
- “Graph path enumeration is required or proven” before the optional installed-runtime equality gate.
