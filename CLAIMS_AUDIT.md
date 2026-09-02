# CLAIMS-01 independent claims audit

Audit task CLAIMS-01. Written 2026-09-02 against the customer-facing documents named in the task
brief, checked against `build/task_reports/*.json`, `EXPECTED_ANSWERS.yaml`, the built code under
`rai_code/aviation_model/`, and live read-only SQL against `PK_AVIATION_TEMPORAL.MODEL_INPUT` under
`RAI_DEMO_AVIATION_TEMPORAL`. No file under `rai_code/queries/` was run and `rai_code/aviation_model`
was never imported, per the task's write-lock constraint; every ontology-level number below comes
from the already-materialized `build/design/ontology_inventory.json`, `build/task_reports/*.json`, or
a raw SQL SELECT that reproduces the ontology's join logic by hand.

This is an independent pass. Nothing here was assumed from prose; every verdict below traces to a
grep of the built code, a JSON task report, or a live query, all cited by file and line or by the
exact SQL run.

## Resolution state, 2026-09-02 (TRUTH-01)

The audit below is left as written. Task `TRUTH-01` then acted on it, and this section records
what changed so the document stays a ledger rather than a list of complaints that may or may not
have been answered. **All seven defects (six FALSE, one OVERBROAD) are corrected in the files that
carried them.** Each finding now ends with a `Resolution` line naming the file, what it says now,
and the measurement behind it. The "safe to say" and "must not be said" lists at the end are
rewritten against the corrected text and are the part to read if you are about to present.

One mechanical caveat: the `File:line` citations in the findings below were taken before the
corrections were applied, so the line numbers no longer resolve in the edited files. The quoted
text is still exact, and every corrected passage carries a dated `Revised 2026-09-02 (TRUTH-01)`
marker with the superseded wording quoted inside it, so search on the quote rather than the line.

| # | Verdict | File carrying the claim | Resolution |
|---|---|---|---|
| 1 | FALSE | `NEO4J_RAI_MAPPING.md`, `NEO4J_PARITY_MATRIX.md` | Corrected. Both rows now state 7,950 live pairs and "populated but ungraded" |
| 2 | FALSE | `NEO4J_FIDELITY_AUDIT.md` | Corrected. Edge verdict MISSING to RESHAPED, element-count `MISSING` column 1 to 0, A1 carries a "status: closed" note, original text preserved |
| 3 | FALSE | `NEO4J_FIDELITY_AUDIT.md` | Corrected. `FULFILLED` row now reads 704 of 3,900 |
| 4 | OVERBROAD | `BRIEF.md` | Corrected. Narration constraint now rests on the true, narrow reason and explicitly forbids the general denial |
| 5 | FALSE | `NEO4J_RAI_MAPPING.md` | Corrected. Both `CodeResolution` grains described as bound, D-0027 supersession recorded |
| 6 | FALSE | `NEO4J_FIDELITY_AUDIT.md`, `BRIEF.md` | Corrected. Both now read 46 / 1,412 / 22 + 11 / 37 / 805, and `test_inventory_artifact` pins all of them |
| 7 | FALSE | `NEO4J_PARITY_MATRIX.md` | Corrected. All eight gating cells advanced to `RAI_PROVEN` with per-row live evidence, plus an explicit note on why no row is `PROVEN` |
| 8 | CONDITIONALLY_TRUE | `NEO4J_PARITY_MATRIX.md` | Addressed. The fixture-scope limit and the three D-0021/D-0022/D-0030 divergences are now stated in the matrix itself, not only in `BRIEF.md` |

**Two defects TRUTH-01 found that this audit did not.** Both are in `NEO4J_FIDELITY_AUDIT.md` and
both are the same failure mode as finding 2, an audit finding that was acted on in code and never
retired in prose:

* Findings **A2(iii)** and **A3** said `Aircraft` has "exactly two outbound relationships, not
  eight" and that there is no direct `Aircraft -> AircraftType` / `EngineType` / `AircraftStatus`
  hop and no inverse from `AircraftStatus`. The live inventory shows **nine** outbound
  relationships on `Aircraft`, including the four dimension-scoped ones and the three direct
  one-hop readings, all built at `rai_code/aviation_model/computed_aircraft.py:109-190`, plus
  `AircraftStatus.daily_assignments` at lines 192-196. Section 3 defect 2, which criticised
  `NEO4J_RAI_MAPPING.md` for describing those very edges, was therefore criticising a document
  that had become right. All are corrected with status notes; the `AircraftConfiguration` half of
  A3 genuinely remains open.
* The **A7 density table** carried `ENRICH-02`'s generator-side counts over 993 filler aircraft
  (8.83 / 2.36 / 1.20 / 1.31, vocabulary 28,272 / 1,654 / 283). Re-measured from the shipped
  `MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT` over all 999 eligible aircraft the figures are
  8.770 / 2.337 / 1.204 / 1.309 and the vocabulary is 28,287 / 1,661 / 285. The difference is
  denominator and grain, not error, but the table now quotes the reproducible numbers and says so.

**Two stale comments in files TRUTH-01 was not permitted to edit**, reported rather than fixed:

* `rai_code/aviation_model/core_flight.py:86` says `PassengerFlight.schedule` is "Non-null on
  exactly one of 19,996 rows". Live: 7,951 of 19,446.
* `rai_code/aviation_model/sources.py:28` (and the same text at `_regen_sources.py:185`) says
  `CODE_RESOLUTION`, `CODE_RESOLUTION_CANDIDATE` and `CODE_RESOLUTION_INPUT` "are deliberately NOT
  bound". D-0027 bound all three; they are 3 of the 37 declared sources.

## Verdict counts

FALSE: 6. OVERBROAD: 1. CONDITIONALLY_TRUE: 1. SUPPORTED: 6. Total claims audited: 14.

The six FALSE and one OVERBROAD verdicts share one root cause: two rounds of late-session work,
the D-0023/D-0024 data enrichment (`ENRICH-01`/`ENRICH-02`) and the D-0027 reversal of D-0019's
row-scoped `CodeResolution` exclusion, changed the live ontology and the live data after
`NEO4J_RAI_MAPPING.md`, `NEO4J_PARITY_MATRIX.md`, and `NEO4J_FIDELITY_AUDIT.md` were written, and none
of the three was revised to match. `BRIEF.md`'s "Completion state" section is the one document that
was kept current on most of these numbers; the others were not. This is a staleness pattern, not
random noise, and it needs a single pass to fix rather than eight separate ones.

## Claims, worst first

### 1. FALSE - the `SCHEDULES` edge is claimed empty when it is not

**Quote:** "`RouteStateSchedules` / `RouteState.schedules`, a derived multi-valued `Relationship`...
**Live population is zero pairs**, and the cause is data rather than the rule:
`PASSENGER_FLIGHT_CANONICAL.schedule_key` is non-null on 1 of 19,996 rows, and that one key
(`SYN-SK-HIST_700`) has no `ROUTE_STATE` at all."
**File:line:** `NEO4J_RAI_MAPPING.md:108`

**Quote:** "Bounded plan-link parity, **declared and evaluated but unexercised by the shipped
fixture: zero live pairs**... The zero population is a data fact, not a rule fault: `schedule_key`
is non-null on 1 of 19,996 canonical passenger flights and that key has no route state. Do not
present this row as demonstrated parity until the fixture populates it."
**File:line:** `NEO4J_PARITY_MATRIX.md:57`

**Evidence:** Both sentences predate the D-0023 enrichment (`ENRICH-01`/`ENRICH-02`,
`build/task_reports/ENRICH-01.json:533`, `ENRICH-02.json:562-575`), which deliberately raised
schedule-key coverage on `PASSENGER_FLIGHT_CANONICAL` from 1 of 19,996 to 7,951 of 19,446 (measured:
`"actual": "7951 of 19446"`). A live SQL replica of the exact `computed_schedule.py:160-168`
conjunction (schedule identity match, half-open knowledge window, inclusive operating window,
matching weekday, all four clauses) against `MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL` joined to
`MODEL_INPUT.ROUTE_STATE` returns **7,950 of 7,951** eligible rows satisfying the full rule, not
zero. Query run 2026-09-02:
```sql
SELECT COUNT(*), COUNT(DISTINCT pf.PASSENGER_FLIGHT_KEY)
FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL pf
JOIN PK_AVIATION_TEMPORAL.MODEL_INPUT.ROUTE_STATE rs
  ON rs.SCHEDULE_KEY = pf.SCHEDULE_KEY
 AND rs.KNOWLEDGE_VALID_FROM <= pf.PUBLISH_DATE AND pf.PUBLISH_DATE < rs.KNOWLEDGE_VALID_TO
 AND rs.OPERATING_EFFECTIVE_DATE <= pf.OPERATING_DATE AND pf.OPERATING_DATE <= rs.OPERATING_DISCONTINUE_DATE
 AND (weekday match per IS_OPERATING_<DAY>)
WHERE pf.SCHEDULE_KEY IS NOT NULL;
-- 7950, 7950
```
It remains true that no named `EXPECTED_ANSWERS.yaml` scenario reads a value through this
relationship (grep for `schedules`/`scheduled_by`/`RouteStateSchedules` returns nothing), so "not
exercised by a graded golden-question fixture" is still accurate. "Zero live pairs" is not.

**Rewording:** "As of the D-0023 enrichment, 7,950 of 7,951 canonical passenger flights carrying a
schedule key satisfy the full `RouteStateSchedules` conjunction against live `MODEL_INPUT` data (SQL
verified 2026-09-02). No named `EXPECTED_ANSWERS.yaml` scenario asserts a value through this
relationship, so it is untested by any graded fixture, but it is not an empty relationship in the
live data and should not be narrated as such."

**Resolution 2026-09-02 (TRUTH-01): corrected.** `NEO4J_RAI_MAPPING.md`'s row now reads "Live
population is 7,950 pairs (7,950 distinct passenger flights, 2,000 distinct route states)" with the
superseded sentence quoted in place, and `NEO4J_PARITY_MATRIX.md`'s row now reads "declared,
evaluated and populated: 7,950 live pairs, but read by no frozen fixture". TRUTH-01 re-ran the
same SQL replica independently and got 7,950 pairs / 7,950 distinct passenger flights / 2,000
distinct route states. Both rows now say "implemented and populated, not graded by a
golden-question fixture", which is the honest form of the remaining caveat.

### 2. FALSE - the fidelity audit says the `SCHEDULES` edge does not exist

**Quote:** "**A1. `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)` does not exist.** This is the one
hard gap... We built neither half as a relationship."
**File:line:** `NEO4J_FIDELITY_AUDIT.md:97-100`, also the element-count table `MISSING | 0 | 1 | 1`
at `NEO4J_FIDELITY_AUDIT.md:24` and the row verdict `**MISSING**` at `NEO4J_FIDELITY_AUDIT.md:60`,
which literally states "grep for `SCHEDULES` / `schedules(` returns zero hits in both" repositories.

**Evidence:** Direct grep against the current tree contradicts this:
```
rai_code/aviation_model/computed_schedule.py:155:RouteStateSchedules = model.Relationship(...)
rai_code/aviation_model/computed_schedule.py:158:RouteState.schedules = RouteStateSchedules
rai_code/aviation_model/computed_schedule.py:160:model.define(RouteStateSchedules(RouteState, PassengerFlight)).where(...)
rai_code/manual/aviation_temporal.py:3727:RouteStateSchedules = model.Relationship(...)
```
`NEO4J_RAI_MAPPING.md:119-122` (in the same repo, same date) already records that this gap was
closed: "Corrected 2026-09-02 by MODEL-01 after the FIDELITY-01 audit... The claim is now true." The
audit document itself was never updated to match its own cited correction, unlike its own A4 and A7
findings a few paragraphs later, each of which carries an explicit "status: closed/partly closed"
update. A1 has no such update.

**Rewording:** Add an "A1 status: closed" note mirroring A4/A7's pattern: "`RouteStateSchedules` is
now implemented in `computed_schedule.py:155-169` and confirmed in the generated
`rai_code/manual/aviation_temporal.py:3727-3743`. Reclassify the edge verdict from MISSING to
RESHAPED/DERIVED and the element-count table's `MISSING` column from 1 to 0. Population caveats
belong here, not a nonexistence claim; see finding 1 above for the current population."

**Resolution 2026-09-02 (TRUTH-01): corrected.** `NEO4J_FIDELITY_AUDIT.md`'s element-count table
moves the edge from MISSING to RESHAPED and its `MISSING` column from 1 to 0; the section B row
carries the new verdict with the original "returns zero hits" text quoted as superseded; and
section 1 gains an "A1 status: closed" note in the A4/A7 pattern, covering both the structure and
the population. Section 3 defect 1 gains a matching "Status: closed" line. Verified before
editing: `RouteStateSchedules` at `computed_schedule.py:155-169` and in
`rai_code/manual/aviation_temporal.py`.

### 3. FALSE - a live-population figure in the same audit document is stale by two orders of magnitude

**Quote:** "it is populated on **4 of 3,900** aircraft flights live, so the edge exists but is
barely exercised."
**File:line:** `NEO4J_FIDELITY_AUDIT.md:61`

**Evidence:** Live SQL 2026-09-02: `SELECT COUNT(*) FROM MODEL_INPUT.AIRCRAFT_FLIGHT` = 3,900;
`SELECT COUNT(*) FROM MODEL_INPUT.FULFILLMENT_EXACT` = 704. That is 18 percent of aircraft flights,
not 0.1 percent. The same document's own Section 1 "A7 status: closed by D-0023" table
(`NEO4J_FIDELITY_AUDIT.md:181-200`) already carries the correct figure ("exact fulfilments | 4 |
**704**"). The earlier edge-table row was never reconciled against the later table in the same file.

**Rewording:** "As of the D-0023 enrichment, `AircraftFlight.fulfils` is populated on 704 of 3,900
aircraft flights (18 percent) live, per `FULFILLMENT_EXACT`; see Section 1's A7 table."

**Resolution 2026-09-02 (TRUTH-01): corrected.** The `FULFILLED` cell now reads "populated on
704 of 3,900 aircraft flights live (18 percent), over 653 distinct canonical passenger flights",
with the superseded text quoted. Re-verified: `FULFILLMENT_EXACT` 704 rows over 704 distinct
`ACTUAL_FLIGHT_ID` and 653 distinct `PASSENGER_FLIGHT_KEY`, `AIRCRAFT_FLIGHT` 3,900 rows, and the
live model returns 704 for `count(AircraftFlight) where fulfils == PassengerFlight`.

### 4. OVERBROAD - the narration rule against "open-ended" over-generalizes a true, narrower fact

**Quote:** 'Say "concurrently valid at knowledge date", never "open-ended": zero route states carry
the `9999-01-01` sentinel.'
**File:line:** `BRIEF.md:214-215`

**Evidence:** As an unscoped claim about all route states, this is false. Live SQL 2026-09-02:
```sql
SELECT COUNT(*), SUM(CASE WHEN KNOWLEDGE_VALID_TO='9999-01-01' THEN 1 ELSE 0 END)
FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.ROUTE_STATE;
-- 14366, 2185
```
2,185 of 14,366 route states (15 percent) do carry the model's own open-interval sentinel in
`KNOWLEDGE_VALID_TO`. However, the specific example the narration constraint exists to protect, the
1,339 concurrently valid `SFO->LAX` states at knowledge date 2026-08-31 that
`NEO4J_FIDELITY_AUDIT.md:55` and `core_schedule.py:26-27` cite, genuinely has zero sentinel rows:
```sql
SELECT COUNT(*), SUM(CASE WHEN rs.KNOWLEDGE_VALID_TO='9999-01-01' THEN 1 ELSE 0 END)
FROM MODEL_INPUT.ROUTE_STATE rs JOIN MODEL_INPUT.ROUTE r ON rs.ROUTE_ID = r.ROUTE_ID
WHERE r.ROUTE_ID = 'SFO->LAX'
  AND rs.KNOWLEDGE_VALID_FROM <= '2026-08-31' AND rs.KNOWLEDGE_VALID_TO > '2026-08-31';
-- 1339, 0
```
So the intended point (none of the demonstrated concurrent states is "open-ended" in the sense of
never closing) is true; the sentence as written asserts it of the whole table, which is not true.
This matters specifically because the constraint exists to police the demo's most attention-getting
number. If a Cirium engineer asks "do any of your route states carry an open, unbounded interval?"
and the presenter answers "no, none, ever" on the strength of this sentence, that answer is wrong;
15 percent of the table does.

**Rewording:** 'Say "concurrently valid at knowledge date", never "open-ended", for the demonstrated
`SFO->LAX` multi-open example: none of its 1,339 concurrently valid states carries the `9999-01-01`
sentinel (verified live). Do not generalize this to the whole `ROUTE_STATE` table: 2,185 of 14,366
rows overall do carry the open sentinel, and those are legitimately open-ended.'

**Resolution 2026-09-02 (TRUTH-01): corrected, and the guard rewritten rather than re-pinned.**
`BRIEF.md`'s narration section now states the instruction on its true reason (none of the 1,339
demonstrated `SFO->LAX` states carries the sentinel), explicitly forbids the general denial, and
gives the presenter the sentence to use when asked directly. Measured independently: 2,185 of
14,366 route states carry `9999-01-01`; 53 of those are on `SFO->LAX` at knowledge dates after
2026-08-31; **0** of the 1,339 concurrently valid at 2026-08-31 do.
`tests/test_model.py::test_no_route_state_carries_the_open_sentinel`, whose premise this finding
falsified, was **not** deleted and **not** softened: it is now
`test_open_sentinel_present_overall_absent_from_the_demonstrated_beat` and asserts both halves,
from the model and from SQL.

### 5. FALSE - a mapping-document claim about which `CodeResolution` grain is bound was superseded and never updated

**Quote:** "`CodeResolutionCode` (D-0019 supersedes the row-scoped `CodeResolution`)... **As built the
grain is the distinct raw code, not the source row.**"
**File:line:** `NEO4J_RAI_MAPPING.md:57`

**Evidence:** D-0019 (`DECISION_LOG.md`, "provisional, measurement-gated") excluded the row-scoped
`CODE_RESOLUTION` pending one timed measurement. D-0027 (`DECISION_LOG.md:1114-1136`) reports that
measurement ("Delta 0.18 seconds, inside the warm-query noise band") and concludes: "the premise is
refuted. By D-0019's own terms the exclusion does not stand... Binding it is now a follow-up, not a
decision still open." The current code has since implemented that follow-up:
```
rai_code/aviation_model/core_reference.py:150:CodeResolution = model.Concept("CodeResolution", identify_by={"resolution_id": String})
rai_code/aviation_model/core_reference.py:163:CodeResolutionCandidate = model.Concept("CodeResolutionCandidate", identify_by={"resolution": CodeResolution, "candidate_id": String})
rai_code/aviation_model/core_reference.py:146-147: "the exclusion does not stand. CodeResolutionCode above remains the grain link semantics read; CodeResolution adds the provenance grain..."
```
Both grains are bound as concepts today; the live `build/design/ontology_inventory.json` lists both
`CodeResolution` and `CodeResolutionCode` (and their candidate concepts) among its 46 concepts. The
mapping document's "supersedes" framing is stale.

**Rewording:** "As of D-0027, which supersedes D-0019's provisional exclusion, both grains are bound
as concepts: `CodeResolutionCode` at `(domain, method, raw_code)` for link semantics, and the
row-scoped `CodeResolution`/`CodeResolutionCandidate` at `(resolution_id[, candidate_id])` for
provenance. Neither supersedes the other in the shipped ontology."

**Resolution 2026-09-02 (TRUTH-01): corrected.** `NEO4J_RAI_MAPPING.md`'s row header now reads
"`CodeResolutionCode` (code grain) and the row-scoped `CodeResolution` / `CodeResolutionCandidate`,
both bound as of D-0027", with the superseded "supersedes" framing quoted and the D-0027
measurement recorded. `NEO4J_FIDELITY_AUDIT.md`'s B1 row and section 3 defect 4 carry the same
correction. Verified in the live inventory: all four of `CodeResolution`,
`CodeResolutionCandidate`, `CodeResolutionCode` and `CodeResolutionCodeCandidate` are among the 46
concepts, and `CODE_RESOLUTION`, `CODE_RESOLUTION_CANDIDATE` and `CODE_RESOLUTION_INPUT` are among
the 37 declared sources. One residual, noted in place rather than papered over: the mapping's
described key for `CodeResolution` (a hash over five fields) is still not the built identity
(`resolution_id`).

### 6. FALSE - ontology size figures are stale across two documents

**Quote:** "the live `inspect.schema()` dump: 44 concepts, 1,292 properties, 11 bare relationships,
SDK 1.20.1"
**File:line:** `NEO4J_FIDELITY_AUDIT.md:4-5`

**Quote:** "Ontology | 46 concepts, 1,292 properties, 32 relationships, 93/93 gates |"
**File:line:** `BRIEF.md:179`

**Evidence:** The current `build/design/ontology_inventory.json` (regenerated 2026-09-02, after both
of the above were written) reports `concept_count: 46`, `property_count: 1412`,
`relationship_count: 22`, `bare_relationship_count: 11`. `NEO4J_FIDELITY_AUDIT.md`'s count (44
concepts, 1,292 properties) matches `build/task_reports/MODEL-01.json`'s
`inventory_figures` (44/1,292/21 concept relationships), i.e. the pre-D-0027 snapshot, not the
current one. `BRIEF.md` independently landed on the correct concept count (46) but the same stale
property count (1,292) as the audit document, so it is a partial update rather than a full one.

**Rewording:** Both documents: "46 concepts, 1,412 properties, 22 concept relationships, 11 bare
relationships (33 total), SDK 1.20.1" and, in `NEO4J_FIDELITY_AUDIT.md`'s element-count table,
`MISSING` moves from 1 to 0 given finding 2 above.

**Resolution 2026-09-02 (TRUTH-01): corrected, and pinned so it cannot recur silently.**
`NEO4J_FIDELITY_AUDIT.md`'s header now reads 46 concepts / 1,412 properties / 22 concept
relationships / 11 bare relationships / 37 declared sources / 805 declared columns, and keeps the
old figures with the note that they were the pre-D-0027 snapshot. `BRIEF.md`'s completion table is
updated to the same figures. `tests/test_model.py::test_inventory_artifact` previously asserted
`concept_count >= 40`, which would have passed at 44, 46 or 60 and caught none of this drift; it
now pins all ten inventory figures exactly, so the next divergence fails a live gate.

### 7. FALSE - the parity matrix's own gating column contradicts the demo's recorded completion state

**Quote:** every one of the eight `Current status` cells in the workload matrix reads
`` `DESIGNED_NOT_YET_EXECUTED` ``.
**File:line:** `NEO4J_PARITY_MATRIX.md:36-43`

**Evidence:** The matrix's own claim boundary (`NEO4J_PARITY_MATRIX.md:3-6`) states its "Allowed
parity statement" column may be said only "after, and only after, the named live gates pass," and its
"Evidence state machine" (`NEO4J_PARITY_MATRIX.md:62-71`) defines five ordered states culminating in
`PROVEN`. `BRIEF.md`'s "Completion state, 2026-09-02" section (`BRIEF.md:169-184`), which is the
newest dated content in the repository on this question, records: "All eight golden questions answer
live against the ontology... Q01-Q04 + Q02F | 23/23 result sets... Q05-Q07 | 21/21 checks... Q08 |
6/6 result sets," plus "Independent SQL oracles | 49/49 result sets, `all_green=True`" and "Ontology |
... 93/93 gates." That is materially past `DESIGNED_NOT_YET_EXECUTED`, yet the column that is
supposed to gate what may be said to the customer was never advanced. Read literally, the matrix
currently forbids saying any of its own "Allowed parity statement" sentences; read against the
verified completion state, the team is almost certainly saying them anyway. Either the column is
simply unmaintained, or the specific state-5 conditions (named hard tests, freshness, claim scans)
have not actually all been rerun and the column is honest and the completion state is the one
overselling readiness. This audit cannot resolve which from the documents alone; both readings are
a problem, and the discrepancy itself is the finding.

**Rewording:** Update each `Current status` cell to the state actually reached (at minimum
`RAI_PROVEN` given the live 23/23, 21/21, 6/6, 49/49 evidence in `BRIEF.md`; `PROVEN` only once the
named hard tests, freshness check and claim scan referenced in the state machine have themselves been
rerun and recorded), or, if that evidence does not in fact satisfy the matrix's own criteria, say so
explicitly rather than leaving all eight rows at their pre-implementation value.

**Resolution 2026-09-02 (TRUTH-01): corrected, in the direction this finding could not resolve
from documents alone.** TRUTH-01 had the orchestrator's own reruns available and they are real:
49/49 SQL oracle result sets green, UC1 23/23, UC2 21/21, Q08 6/6, all eight questions answering
live, and the ontology gate at 93/93 after this task's repairs. All eight `Current status` cells
are now `RAI_PROVEN`, each backed by a named task report and test file in a new evidence table.
**No row is `PROVEN`**, and the matrix now says why in its own words: the claim scan has just
failed and been repaired rather than passed clean, and the notebook / agent / HTML / `prep_demo.py`
surface that state 5 refers to was descoped, so its conditions are unmeasurable rather than merely
unmet. So the finding's second reading was partly right - the completion state was ahead of the
gate - and the answer is a documented middle state, not a promotion to `PROVEN`.

### 8. CONDITIONALLY_TRUE - independent-oracle agreement is properly scoped per row, but the scope-limiting caveat lives in only one of four documents

**Quote (representative, repeated in substance across all eight rows):** "For the frozen aircraft/date
and boundary fixtures, RAI reconstructs the same complete results as the independent manifest and SQL
oracle."
**File:line:** `NEO4J_PARITY_MATRIX.md:36` (Q01), and similarly worded at lines 37-43 for Q02-Q08;
also `DEMO_QUESTIONS.md:103,127` and `NEO4J_RAI_MAPPING.md` throughout.

**Evidence:** Each individual sentence is true as scoped: it claims agreement "for the frozen...
fixtures," and `BRIEF.md`'s "Known issues carried forward" items 4 and 5 (`BRIEF.md:201-206`) confirm
that the specific divergences between `MODEL_INPUT` and the independent oracle (rotation anomaly
precedence for a cancelled target, cycle-detection scope, `TARGET_NOT_OPERATED` having no oracle
branch at all, per `DECISION_LOG.md` D-0021/D-0022/D-0030) are all "unexercised by the shipped
fixtures," so the frozen-fixture claim survives. But `NEO4J_PARITY_MATRIX.md`, `NEO4J_RAI_MAPPING.md`,
and `DEMO_QUESTIONS.md`, the three documents that state the oracle-agreement claim as a
customer-facing sentence, never mention that any such divergence exists; only `BRIEF.md` does. A
presenter working from the matrix's "Allowed parity statement" column alone, without also having read
`BRIEF.md`'s known-issues list, has no signal that the oracle-agreement claim is fixture-scoped
rather than general, and could extend it in live Q&A to a rotation scenario the fixtures do not cover
(for example, a target that is itself cancelled), where the oracle genuinely has no branch
(`DECISION_LOG.md` D-0030: "the SQL oracle still has no branch for it").

**Rewording:** Add one sentence to `NEO4J_PARITY_MATRIX.md`'s evidence state machine or claim
boundary section: "SQL/RAI agreement is demonstrated only for the named frozen result sets. Three
known precedence and scope divergences between `MODEL_INPUT` and the independent oracle (rotation
anomaly rank for a cancelled target, cycle-detection scope, and the `TARGET_NOT_OPERATED` anomaly
class) are recorded in `DECISION_LOG.md` D-0021/D-0022/D-0030 and are not exercised by any frozen
fixture; do not extend the oracle-agreement claim to a live scenario outside the frozen parameters
without checking this list first."

**Resolution 2026-09-02 (TRUTH-01): addressed.** `NEO4J_PARITY_MATRIX.md` now carries a "Scope
limit on the oracle-agreement sentences" paragraph immediately after its evidence state machine,
naming all three divergences (rotation anomaly precedence for a cancelled target, cycle-detection
scope, `TARGET_NOT_OPERATED` with four live rows and no oracle branch), citing D-0021/D-0022/D-0030,
and instructing the presenter to say the oracle has no branch there rather than extending the
agreement claim. `DEMO_QUESTIONS.md` and `NEO4J_RAI_MAPPING.md` were outside TRUTH-01's write
scope and still lack the caveat; a presenter working from either alone still has no signal.

## Checked and found sound

These were audited with the same rigor as the findings above and are reported because "checked, and
it is fine" is itself a result.

**9. SUPPORTED - no claim of native RAI temporal support.** `temporal.py:1-30` states plainly: "RAI
1.20.1 has no temporal support at all. A search of the whole `semantics` tree for `valid_from`,
`bitemporal`, `as_of`, `effective_from` and `interval` returns nothing... Every predicate here is
therefore a hand-written conjunction over two `Date` properties." The differentiation claimed is
narrow and matches the task's expected honest framing: the predicates are written once in
`temporal.py` and reused, rather than retyped per query. No document audited asserts native,
built-in, or first-class temporal support; the "native temporal support" and "out-of-the-box
temporal" search terms return zero hits across `NEO4J_PARITY_MATRIX.md`, `NEO4J_RAI_MAPPING.md`,
`BRIEF.md`, `README.md`, and `DEMO_QUESTIONS.md`.

**10. SUPPORTED - the multi-open route mechanism claim.** `core_schedule.py:1-31` and
`NEO4J_FIDELITY_AUDIT.md:55` both attribute the multi-open result to `RouteState` not naming `Route`
in its identity and `Route.states` being an `.alt()` reading with no inverse functional dependency,
not to any stronger mechanism. Live SQL 2026-09-02 reproduces the cited figure exactly: 1,339
concurrent `SFO->LAX` route states at knowledge date 2026-08-31, with the query completing without
an FD error. No document claims this generalizes beyond what the mechanism actually does.

**11. SUPPORTED - the `require(unique(...))` no-op disclosure.** `constraints.py:1-24` documents
PROBE U-04's finding that `require(unique(...))` is "a silent no-op in SDK 1.20.1" and states the
calls are "kept as documentation only... must not be presented to anyone as live checks."
`BRIEF.md:215-216`'s narration constraint repeats this instruction consistently: "Do not present the
five `require(unique(...))` lines as live checks; they are a documented no-op in 1.20.1." Both
documents agree and correctly identify the two mechanisms that do enforce (the `Property` FD, and
the zero-count assertion queries in `tests/test_model.py`).

**12. SUPPORTED - no production/performance/cost/security-superiority claim found.**
`NEO4J_PARITY_MATRIX.md:87-88,90-94` (the "Differentiation allowed after proof" and "Prohibited
statements" sections), `NEO4J_RAI_MAPPING.md:251-253`, `SOURCE_CONTRACT.md:552-553`,
`DEMO_QUESTIONS.md:153,331`, and `README.md:44-48` all explicitly disclaim production sizing,
performance superiority, cost advantage, and security superiority, and consistently attribute all
timing figures to synthetic, representative-shape data on one `HIGHMEM_X64_S` engine. No audited
document asserts RAI is faster, cheaper, more scalable, or more secure than Neo4j; the closest
figures found (Q01's 19-29s warm cost in `BRIEF.md`'s known issues, and the 13-19 second `Property`
FD evaluation window noted in `core_schedule.py` and `constraints.py`) are disclosed as measured
facts about this fixture, not framed as comparative claims.

**13. SUPPORTED - "no supplied node label is omitted."** `NEO4J_RAI_MAPPING.md:90`.
`NEO4J_FIDELITY_AUDIT.md`'s element-count table (`NEO4J_FIDELITY_AUDIT.md:19`) independently confirms
0 of 11 node labels are missing (all IDENTICAL, RESHAPED, or MERGED). Unlike the edge claim this
document corrects nearby, the node claim was true when written and remains true.

**14. SUPPORTED - the self-correction of the original "no supplied edge is omitted" defect is
accurate.** `NEO4J_RAI_MAPPING.md:119-122`: "Corrected 2026-09-02 by MODEL-01 after the FIDELITY-01
audit. The earlier text asserted 'no supplied edge is omitted' while `SCHEDULES` had no
implementation behind it. The claim is now true." Verified: `RouteStateSchedules` exists in the
current code (finding 2 above). The correction is accurate even though the paragraph immediately
preceding it (finding 1 above) still carries a stale population number; the fix that CLAUDE.md's task
description refers to is real.

## Safe to say out loud to Cirium's data engineers

Rewritten 2026-09-02 (TRUTH-01) against the corrected documents. Every number below was measured
today, either by this task or by the orchestrator's own reruns; none is copied from prose.

- RAI 1.20.1 has no interval type, no as-of operator, and no validity-annotated relationship. Every
  temporal predicate here is a hand-written conjunction over two `Date` properties, written once in
  `temporal.py` and reused by every question that needs it, rather than retyped per query. That is
  the differentiation; it is not native temporal support.
- The `SFO->LAX` multi-open result (1,339 concurrent route states at knowledge date 2026-08-31,
  returned without an FD error) falls out of one modeling choice: `RouteState`'s identity does not
  include `Route`, and the inverse reading `Route.states` is an `.alt()` over the same fields, so it
  carries no inverse functional dependency. There was never a constraint to relax. Say "concurrently
  valid at knowledge date" for this example: none of those 1,339 states carries the model's
  open-interval sentinel. If asked whether any route state is open-ended, the answer is yes -
  2,185 of 14,366, including 53 on `SFO->LAX` at later knowledge dates - and the reason the
  demonstrated result is not narrated that way is that these particular 1,339 all close.
- The five `require(unique(...))` lines in `constraints.py` are documentation, not live checks;
  `require(unique(...))` is a measured no-op in this SDK version. The real enforcement is the
  `Property` functional-dependency error and the zero-count assertion queries, and both of those do
  work.
- Every result quoted for the eight golden questions is measured against the frozen
  `EXPECTED_ANSWERS.yaml` manifest and an independent Snowflake SQL oracle, for the named frozen
  parameters. Results, timings, and data volumes all come from deterministic synthetic,
  enrichment-tuned fixtures on one `HIGHMEM_X64_S` engine; none of it is a production-scale,
  performance, cost, or security claim, and the repo's own prohibited-statements list says so in
  writing.
- The `(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)` edge and all twelve other supplied Neo4j
  edges are implemented in the ontology today, and no supplied node label or edge type is missing.
  This was not always true; the edge was built after an internal audit found it absent, and the fix
  is confirmed in the code, not just in prose. It is populated with 7,950 live pairs. It is read by
  no frozen golden-question fixture, so call it "implemented and populated, not graded".
- All four Neo4j aircraft dimensions are enterable as distinct one-hop readings:
  `Aircraft.state_assignments` / `.type_assignments` / `.engine_assignments` /
  `.status_assignments`, plus the direct `Aircraft.conformed_to` / `.equipped_with` /
  `.assigned_status` carrying both edge dates, and the inverse `AircraftStatus.daily_assignments`
  so "which aircraft were ever in Storage" starts from the status node as it does in Cypher. Nine
  outbound relationships on `Aircraft` in the live inventory. The one remaining missing inverse is
  from `AircraftConfiguration`.
- The enriched fixture genuinely exercises the temporal questions it demonstrates: 8.770
  `aircraft_state` versions per aircraft with 995 of 999 aircraft carrying more than one, 2.337
  `aircraft_status` versions with 470 of 999 multi-version, 202 aircraft converting type and 307
  re-engining, a status vocabulary of 28,287 In Service / 1,661 Storage / 285 Maintenance over
  30,233 history rows, and 704 exact fulfilments over 653 canonical passenger flights. That is a
  fact about the shipped fixture, not about any real fleet.
- The live ontology is 46 concepts, 1,412 properties, 22 concept relationships and 11 bare
  relationships over 37 declared sources and 805 declared columns, on SDK 1.20.1. Quote it from
  `build/design/ontology_inventory.json`; a live gate now pins every one of those figures.
- For the eight golden questions the evidence state is `RAI_PROVEN`, not `PROVEN`. That means the
  live RAI query and an independent Snowflake SQL oracle both return the frozen rows for the named
  frozen parameters. It does not mean the full state-5 gate passed, because the notebook, agent,
  HTML and `prep_demo.py` surface it refers to was descoped and the claim scan has just been
  repaired rather than passed clean.

## Must not be said

- "Zero live pairs", "unexercised", or "does not exist" for the `SCHEDULES` relationship. It
  exists at `computed_schedule.py:155-169` and 7,950 of the 7,951 eligible canonical passenger
  flights satisfy it live. It is fair, and accurate, to say no frozen golden-question fixture
  reads a value through it yet.
- "Zero route states carry an open sentinel" as an unqualified statement. It is true only of the
  demonstrated 1,339 `SFO->LAX` states at knowledge date 2026-08-31; 2,185 of 14,366 route states
  in the live table do carry it, and those are genuinely open-ended. This is the single highest-risk
  sentence in the repository because it was written into `BRIEF.md`'s narration constraints as the
  *reason* for a correct instruction, so a presenter could have said it in good faith.
- "Populated on 4 of 3,900" for `AircraftFlight.fulfils`, or any other pre-enrichment population
  figure. It is 704 of 3,900.
- "`PROVEN`" for any of the eight workloads, and by extension any sentence that implies the
  end-to-end demo gate passed. `RAI_PROVEN` is the supported state; see the parity matrix's own
  note on the difference.
- That `Aircraft` exposes only two unscoped relationships, or that the four Neo4j dimension edges
  and the direct one-hop type / engine / status hops are unavailable. `NEO4J_FIDELITY_AUDIT.md`
  said all of that before the code was written and the corrections are marked in place.
- Any claim that the independent Snowflake SQL oracle agrees with RAI beyond the frozen, named
  fixture parameters. Three specific divergences (rotation anomaly precedence for a cancelled
  target, cycle-detection scope, and the `TARGET_NOT_OPERATED` anomaly class, all in
  `DECISION_LOG.md` D-0021/D-0022/D-0030) are known, live in the enriched data, and have no oracle
  branch. If a question strays outside the frozen parameters, say that explicitly rather than
  extending the parity claim.
- Any of "universal Neo4j replacement," "faster," "cheaper," "more scalable," "more secure," or
  "this proves production sizing," none of which appear in the audited documents today and none of
  which should be added without measured evidence, per the repo's own prohibited-statements list.
- The ontology's own size from memory. Both `NEO4J_FIDELITY_AUDIT.md`'s header and `BRIEF.md`'s
  completion table are correct as of 2026-09-02 and are gate-pinned, but the reason they are
  correct is that they were wrong twice; check
  `build/design/ontology_inventory.json` if anything in the model has changed since.
- Any live population figure taken from a document rather than from `MODEL_INPUT`. Every false
  claim in this audit was a number that was true when it was written. Staleness, not invention, is
  this repository's failure mode, and the fix is to re-measure rather than to re-read.
