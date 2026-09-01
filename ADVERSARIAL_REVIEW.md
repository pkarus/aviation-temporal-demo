# Adversarial review

## Verdict

**Conditional GO.** Infrastructure gate G0 is complete. Implementation remains NO-GO until the
contract gate G1 freezes the ambiguous temporal and matching semantics below. The demo may prove
functional parity for the supplied workloads; it may not claim universal Neo4j replacement or
production-scale performance from synthetic data.

## Release-blocking findings

| Risk | Required treatment | Gate evidence |
|---|---|---|
| Same-day aircraft changes collide when identity contains only aircraft and date. Earlier changes can become zero-length. | Identify assignments with dimension, aircraft, event date, sequence, and source history ID. Preserve the full audit sequence and separately define date-visible state as the final event of a day. | Three same-day changes retain unique stable IDs after reload; the as-of-date result is unambiguous. |
| Customer prose conflicts on whether dimensions, APU, and weights are immutable or versioned. | Freeze an attribute-authority matrix before generation: source, owner, temporal treatment, change-detection participation, and query relevance. | Every in-scope column has exactly one semantic owner and temporal treatment. |
| A schedule date change changes `SCHEDULE_KEY`; exact amendment pairing is not derivable. | Separate exact key-preserving modifications, exact additions/removals, candidate key-shift amendments, ambiguous candidates, and unpaired events. Never force a candidate. | Ambiguous fixtures remain ambiguous; UI and agent label confidence and evidence. |
| Schedule queries can silently confuse knowledge time and operating time. | Require `knowledge_date` and `operating_date`. If a prompt supplies only one, ask which clock or explicitly state an agreed both-clock default. | Cross-product boundary truth table passes; agent never silently chooses the wrong clock. |
| A small synthetic dataset cannot establish production performance against sources as large as 284m flights. | Describe the result as a functional, representative-shape benchmark. Save exact row counts, engine/SDK versions, cold and warm timings, and materialization state. | Every performance claim links to a timing artifact; no extrapolated production claims. |
| `model.Table()` prerequisites and the source-view limitation were not hard gates. | Bind RAI only to physical demo-owned tables with change tracking. Verify account, role, app access, engine, and one-table smoke model first. | Smoke model loads and queries a change-tracked table under the demo role. |
| The all-or-nothing overnight scope had no useful fallback. | Deliver UC1 as an independent vertical slice; build UC2 separately; integrate only after both validate. Keep Snowflake mutations serialized. | UC1 remains runnable and has a truthful reduced HTML path if UC2 misses the window. |

## Important implementation risks

- Do not hide all temporal semantics in final Snowflake answer tables. Snowflake owns physical
  ingestion, canonicalization, snapshot de-duplication, and interval candidates. RAI must expose
  reusable identities, temporal associations, two-clock predicates, status sequence semantics,
  cross-domain enrichment, and query logic.
- Airport and airline code resolution is not guaranteed functional. Use resolution tables with
  provenance/status and prove cardinality before declaring concept-valued Properties.
- `FULFILLED` matching is optional and under-specified. Direct ID matches and heuristic composite
  matches must be separate, with one-to-many stopovers and unmatched rows retained.
- `NEXT_FLIGHT_ID` may answer rotation without a graph algorithm. Make path enumeration optional
  and version-gated; keep a stable self-reference query baseline.
- Schedule disappearance requires a complete snapshot calendar. An incomplete or missing snapshot
  must not produce a mass market exit.
- Itinerary variants require deterministic de-duplication before change detection, including a final
  stable tie-breaker.
- Capacity must declare operating versus marketing carrier. Physical capacity defaults to operating
  carrier and must not double-count codeshares. Cabin reconciliation must account for premium
  economy being a subset of economy in the forward source.
- Forward and historical flights need a typed canonical union, explicit source precedence, and
  retained source-system lineage.
- The supplied engine schema supports one engine type plus count and a multiple-types flag, not a
  complete mixed-engine fitment. The agent must not invent a second engine type.
- Aircraft assignment validity, aircraft existence/end-of-life bounds, and source `END_EVENT_DATE`
  provenance are separate semantics and require separate tests.
- A modular ontology and a hand-maintained upload file will drift. The standalone artifact must be
  generated from the canonical package or contract-tested for identical schema and answers.
- SQL cannot validate itself. Named expected rows must be hand-authored from fixtures before either
  Snowflake transformation or RAI query implementation.
- A general text-to-PyRel agent is too risky for the overnight path. Use a curated query catalog,
  safe ambiguity behavior, and unsupported-question responses.

## Required negative fixtures

- Null-to-value, value-to-null, and irrelevant aircraft events
- Several `A -> B -> A` spells, including same-day transitions
- Independent type and engine changes on different dates
- Missing configuration IDs and documented inner-join loss
- Duplicate itinerary variants and reordered raw input
- Unchanged, missing, incomplete, disappearance, and reappearance snapshots
- Key-preserving, key-shifting, ambiguous, and unpaired schedule changes
- Multiple concurrent schedules on one route
- Codeshare operating/marketing divergence and cabin inconsistencies
- Both-clock interval boundaries and midnight/arrival-day crossing
- Historical/forward overlap and forward-only null fields
- Matched, unmatched, one-to-many, null-key, and ambiguous fulfillment
- Rotation self-loop, cycle, diversion, cancellation, missing time, broken link, and broken continuity
- Cold start, warm runs, CDC initialization, and repeat-run idempotency

## Stage gates

1. **G0 Account/security — COMPLETE:** live Sales Engineering account proven; role, database,
   role hierarchy, RAI access, warehouse, and agent prerequisites verified.
2. **G1 Contract:** grains, keys, attribute ownership, same-day semantics, both clocks, carrier
   dimension, amendment confidence, end-of-life behavior, and data gaps frozen.
3. **G2 Fixtures:** deterministic data and independent expected-answer manifest exist for all eight
   questions and negative cases.
4. **G3 Snowflake source:** types, counts, keys, resolution cardinalities, snapshot completeness,
   change tracking, and rerun idempotency pass.
5. **G4 Temporal layer:** same-day ordering, independent aircraft dimensions, multi-open schedules,
   removals/reappearances, and both sentinels pass.
6. **G5 Ontology:** strict compilation, stable identities, functional-dependency checks, nonempty
   relationships, and saved `inspect.schema()` inventory pass.
7. **G6 Queries:** all eight complete RAI result sets equal independent expected manifests; heuristic
   outputs remain labeled.
8. **G7 Performance:** declared-scale cold/warm timings saved without production extrapolation.
9. **G8 Agent:** canonical/adversarial prompts choose the correct query, clocks, and carrier role;
   unsupported questions fail safely.
10. **G9 Release:** clean bootstrap-to-demo rerun passes; upload artifact, notebook, agent, and HTML
    agree with live evidence.

Failures in G0-G6 are release blockers. Failures in G7-G9 permit only a reduced demo whose HTML
and claims have been narrowed to the verified subset.

## Claim policy

The HTML may claim parity only for evidence-backed supplied workloads: identity/state modeling,
independently versioned dimensions, half-open temporal validity, multi-open route states, two-clock
queries, optional plan/actual links, and aircraft rotation. Differentiation may be claimed for
Snowflake-native data residence, governance, shared semantic rules, SQL-oracle comparison, and
Snowflake Intelligence access. “Faster,” “more scalable,” “cheaper,” “more secure,” and universal
“better than Neo4j” claims require separate evidence and are prohibited in this demo.
