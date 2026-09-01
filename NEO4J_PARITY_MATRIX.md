# SPEC-03 scoped Neo4j-to-RAI parity matrix

## Claim boundary

This matrix defines what the release may claim after—and only after—the named live gates pass. It
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

`EXPECTED_ANSWERS.yaml` version `1.0.0` is the independent authority. A row below becomes `PROVEN`
only when its complete SQL and RAI result sets independently equal the frozen result sets and every
named boundary/negative assertion passes. Before that, status is `DESIGNED_NOT_YET_EXECUTED`.

## Workload matrix

| Query | Supplied capability in scope | RAI representation and execution shape | Frozen evidence | Allowed parity statement after G6 | Snowflake-native differentiation after evidence | Required limitation | Current status |
|---|---|---|---|---|---|---|---|
| Q01 `aircraft_as_of` | Point-in-time aircraft state across type, engine, lifecycle status, registration, and base | `Aircraft` plus four independent `AircraftDimensionDailyAssignment` association streams, half-open point predicates, existence clipping, and per-dimension DV-33 status | `Q01-CANONICAL`, `Q01-BEFORE-FIRST`, `Q01-UNKNOWN-GAP`, `Q01-EOL-BOUNDARY`; HT-02/05-10/39/40 | “For the frozen aircraft/date and boundary fixtures, RAI reconstructs the same complete results as the independent manifest and SQL oracle.” | Source-resident history, RBAC, source lineage, and SQL/RAI comparison use the same Snowflake security boundary | EOL exclusivity is provisional; master-only current values do not backfill history; exact mixed fitment is unsupported | `DESIGNED_NOT_YET_EXECUTED` |
| Q02 `status_reversion_spells` | Temporal sequence traversal over repeated status assignments | Ordered `AircraftStatusAuditAssignment` associations preserve source event identity/sequence; deterministic derivation pairs every Storage assignment with the next qualifying return | `Q02-CANONICAL`, `Q02-NO-SPELLS`; HT-01/03/04/05 | “For the frozen ordered status fixtures, RAI returns every supplied reversion spell, including the same-day zero-calendar-day occurrence.” | Audit lineage and SQL sequence evidence remain beside reusable semantic rules | Date-plus-sequence gives order, not intraday duration | `DESIGNED_NOT_YET_EXECUTED` |
| Q03 `month_end_fleet_composition` | Long-range temporal aggregation by aircraft type and status | Month calendar joined to independent type/status daily assignments and Aircraft existence, grouped at `(month_end,type)` | `Q03-CANONICAL`: 132 rows, 120 distinct month ends; HT-02/05/08/09/42 | “For the frozen ten-year synthetic population, RAI and SQL independently reproduce all 120 month-end composition points.” | Governed source, calendar, model rule, SQL baseline, and visualization can coexist in Snowflake | Representative-shape functional evidence only; no production-scale or performance inference | `DESIGNED_NOT_YET_EXECUTED` |
| Q04 `type_engine_histories` | Independently temporal aircraft-to-type and aircraft-to-engine relationships | Separate type and engine daily association concepts with independent validity, resolution, count/completeness payload, and type-change derivation | `Q04-CANONICAL`; HT-04/05/39/40 | “For the frozen aircraft, RAI reproduces the independent type and engine histories without forcing their boundaries to align.” | Source configuration lineage and relationship payload are inspectable beside SQL validation | Only one reported engine type and count are available; second type/fitment is never fabricated | `DESIGNED_NOT_YET_EXECUTED` |
| Q05 `schedule_four_week_changes` | Snapshot-to-snapshot additions, removals, and modifications | `ScheduleExactChange` preserves exact key/content facts; separate `ScheduleAmendmentEvidence` preserves medium candidates, low ambiguous groups, members, and unpaired facts | `Q05-CANONICAL` 19 rows plus `Q05-INELIGIBLE-ENDPOINT`; HT-12/13/15-22/49 | “For four frozen complete weekly comparisons, RAI matches exact schedule change facts and preserves bounded candidate/ambiguity classifications without promoting them.” | Snowflake completeness controls, deterministic reduction, SQL reconciliation, RAI rules, and lineage are jointly governed | No stable amendment ID; non-overlapping key shifts may remain unpaired; missing/incomplete snapshots prove no absence | `DESIGNED_NOT_YET_EXECUTED` |
| Q06 `market_latest_vs_seven_days` | Market entry/exit set difference across schedule snapshots | Eligible endpoint filtering and deterministic classification at `(carrier_role, exact airline, directional route)` | `Q06-CANONICAL`, `Q06-INCOMPLETE-ENDPOINT`, `Q06-MISSING-CARRIER-ROLE`; HT-12/14/26/29/38/48 | “For the frozen exact endpoints and marketing role, RAI returns the same entry/exit set as the manifest and SQL oracle and refuses ineligible endpoints.” | Completeness evidence and exact resolution status remain visible with the semantic result | Ambiguous carrier resolution cannot create an exact airline market; this is a knowledge-clock comparison | `DESIGNED_NOT_YET_EXECUTED` |
| Q07 `route_capacity_two_clocks` | Active route-state frequency/capacity under knowledge and operating time | Multi-open `RouteState` associations, required DV-30/DV-31 clocks, weekday predicate, separate marketing/operating Airline roles, D-0007 physical representative, and cabin-quality derivations | `Q07-MARKETING`, `Q07-OPERATING`, knowledge-end empty, and missing-knowledge-date/missing-operating-date/missing-carrier-role errors; `TT-BOTH-CLOCKS`, `TT-UTC-OFFSETS`, `TT-US-CLOCK-AUTHORITY`, `TT-CABIN-QUALITY`; HT-18/23-29/38/48 | “For the frozen clock/carrier scenarios, RAI reproduces route frequency and capacity, keeps marketing and operating results distinct, and does not double-count the proven physical representative.” | Shared governed schedules, quality evidence, reusable clock rules, SQL oracle, and curated agent parameters are one Snowflake workflow | Codeshare-only physical service is unresolved and excluded without a stable service-group ID; UTC `TIME` alone remains unresolved | `DESIGNED_NOT_YET_EXECUTED` |
| Q08 `actual_rotation_enriched` | Multi-hop actual aircraft rotation and aircraft-history enrichment | Validated AF-20 `next_flight` self-reference with visited set/step bound, actual continuity/time/date rules, typed anomalies, and per-leg type/engine as-of joins | `Q08-CANONICAL`, `Q08-ANOMALIES`, `Q08-NOT-FOUND`; `TT-US-CLOCK-AUTHORITY`; HT-30-40/49 | “For the frozen actual-leg chain and anomaly fixtures, ordinary RAI self-reference traversal reproduces the supplied rotation workload and enriches each valid leg from independent aircraft history.” | Actual operations, plan/actual distinction, history, SQL validation, semantic traversal, and agent access remain governed together | This is not arbitrary path analytics; actual endpoints/times never borrow plan values; optional graph paths require live equality and added value | `DESIGNED_NOT_YET_EXECUTED` |

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
| `ROUTE_STATE-[:SCHEDULES]->PASSENGER_FLIGHT` | clock-qualified scheduling relationship | Bounded plan-link parity | Typed historical/forward union and source precedence are explicit |
| `AIRCRAFT_FLIGHT-[:FULFILLED]->PASSENGER_FLIGHT` | `ExactFulfillment` association | Optional one-to-many parity where shared source ID proves it | Heuristic and ambiguous candidates are separate and never satisfy the exact edge |
| actual flight `STARTED`/`ENDED` | labeled actual-origin/destination links to `SYN-AP-*` Airport identities | Direct actual-endpoint parity | Planned IATA never repairs or overwrites actual endpoints |
| actual flight `NEXT_FLIGHT_ID` path | validated same-type self-reference | Required Q08 parity baseline | Invalid edges become typed anomaly evidence; graph path enumeration is optional |

## Evidence state machine

1. `SPECIFIED`: this contract and the frozen manifest exist and parse.
2. `SQL_PROVEN`: the independent raw-fixture SQL oracle returns the exact manifest rows.
3. `RAI_PROVEN`: the live RAI query returns the exact manifest rows under the demo role.
4. `PROVEN`: both prior states, all named hard tests, freshness, and claim scans pass.

No UI, notebook, agent, or HTML may present a row as proven before state 4. SQL/RAI agreement without
manifest equality is insufficient. Missing/incomplete endpoints, unknown configuration gaps,
unresolved code/capacity cases, anomalies, and exact empty results remain part of the evidence.

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
- “Graph path enumeration is required or proven” before the optional installed-runtime equality gate.
