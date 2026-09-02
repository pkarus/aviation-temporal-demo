# REVIEW-D0021 — adversarial review of the DATA-04a rotation anomaly precedence claim

Reviewer: sub-agent REVIEW-D0021. Did not author `data/model_input/60_actual_flight.sql`,
`data/oracles/q08_actual_rotation_enriched.sql`, `EXPECTED_ANSWERS.yaml` or any spec document.
Read-only session. `EXPECTED_ANSWERS.yaml` not touched.

## Verdict

**DERIVABLE — no circularity.**

The `CYCLE` over `BACKWARD_TIME` ordering is derivable from three artifacts that all predate the
frozen manifest or were frozen alongside it, and it was independently reached 35 minutes earlier by
a different agent that had never seen `MODEL_INPUT`. The shipped behaviour is correct. Flight 8103
is correctly suppressed.

**The DATA-04a justification, however, is rejected.** It is wrong on its stated premise (the
contract does order the classes) and its supporting argument is factually false (the ordering is
**not** "the only ordering under which flight 8103 is suppressed" — I construct the counter-example
below). This is a documentation defect, not an implementation defect, and it must be repaired before
QUERY-ROT inherits it, because a customer engineer who checks the "only ordering" claim will find it
does not hold and will then distrust the rest of the disclosure.

Separately, the review surfaced **four items DATA-04a did not disclose at all**, three of which are
genuinely underdetermined and one of which is a live undisclosed manifest adoption in Q08. Those,
not the cycle precedence, are the real exposure.

---

## Axis 1 — Is the precedence genuinely underdetermined by the contract?

**No. The contract orders the classes, in two places, in a commit that predates the manifest.**

`ATTRIBUTE_AUTHORITY.md:338` (DV-25, `rotation_anomaly_class`):

> Typed self/cycle/missing/different/day/time/continuity/diversion-conflict/cancel/missing-time
> reason.

`SOURCE_CONTRACT.md:363-366`:

> Self-loop, cycle, missing target, different aircraft, `OUTSIDE_SELECTED_DAY`, backward time,
> broken airport continuity, cancellation, and missing time stay visible as typed anomalies.

Both sentences ship in commit `15d8f35` (2026-09-01 19:36, "Define aviation source and ontology
contracts"). `EXPECTED_ANSWERS.yaml` does not exist until `0d2feb3` (20:10). The enumeration
therefore cannot have been read off the manifest — the manifest was read off it.

DV-25 is a **single-valued** attribute ("rotation_anomaly_class", one class per link). A
single-valued classifier over an enumerated vocabulary in which a link can satisfy several
predicates *requires* a precedence to be well-defined. The contract supplies exactly one ordering of
that vocabulary and supplies it twice. Reading it as the precedence is the only reading under which
DV-25 is well-defined at all.

Three independent confirmations from the frozen manifest, all agreeing with the DV-25 order, zero
contradictions:

| Fixture | Competing classes | Manifest verdict | DV-25 order |
|---|---|---|---|
| 8101 -> 8101 | `SELF_LOOP` vs `CYCLE` (a self-loop is a 1-cycle under reachability) | `SELF_LOOP` | self(1) < cycle(2) |
| 8105 -> 8205 | `DIFFERENT_AIRCRAFT` (ac 1098) vs `BROKEN_CONTINUITY` (8105 arrives LAS, 8205 departs LAX) | `DIFFERENT_AIRCRAFT` | different(4) < continuity(7) |
| 8107 -> 8101 | `BACKWARD_TIME` (8101 dep 14:00 < 8107 arr 21:30) vs `BROKEN_CONTINUITY` (8107 arrives LAX, 8101 departs SFO) | `BACKWARD_TIME` | time(6) < continuity(7) |

And the manifest's own fixture numbering `SYN-ANOM-01` .. `SYN-ANOM-11` reproduces the DV-25
enumeration **exactly, all ten classes in order**, with DV-52's eleventh class appended:

```
DV-25:      self  cycle  missing  different  day  time  continuity  diversion-conflict  cancel  missing-time
SYN-ANOM-:   01     02      03        04      05    06      07              08             09        10        (+11 = UNKNOWN_OR_INVALID_CANCELLATION_FLAG)
```

That is not a coincidence. The frozen manifest was authored by walking the DV-25 list.

**Conclusion: the fitting was unnecessary. DATA-04a's premise — "rotation anomaly precedence is not
stated in the contract" — is false.**

There is one honest caveat. DV-25's list is presented as a vocabulary enumeration, not labelled
"precedence". Reading it as an ordering is an interpretive step. But it is the only ordering
statement in the corpus, it appears twice, it predates the manifest, three manifest fixtures confirm
it and none contradict it, and an independent agent read it the same way. That is a derivation, not
a fit.

## Axis 2 — Is `CYCLE` over `BACKWARD_TIME` independently justifiable on semantic grounds?

**Yes, and the argument runs one way only.**

1. **Cycle is not a per-link predicate.** `SOURCE_CONTRACT.md:361-363` states the acceptance
   predicate as an explicit conjunction: "A link is accepted only when the target exists, is
   different, has the same aircraft and AF-06, departs no earlier than the current arrival, and
   departs from the current actual arrival airport." Five conditions. Cycle is conspicuously **not
   among them** — it is named separately, in the anomaly enumeration, because it is a property of
   the link graph rather than of any one link. A structural defect and a link defect are different
   kinds of thing; the structural one is the diagnosis, the link one is a symptom of it.

2. **`BACKWARD_TIME` is a necessary consequence of `CYCLE`, never the reverse.** Gate times are
   totally ordered. Any directed cycle over timed legs must contain at least one link whose target
   departs before the source arrives. So every timed cycle *guarantees* at least one
   `BACKWARD_TIME` link. If `BACKWARD_TIME` outranked `CYCLE`, then in every 2-cycle exactly one
   member would be classed `BACKWARD_TIME` and the other `CYCLE`, and the two members of one
   indivisible structural defect would carry two different diagnoses. The subsumption direction is
   forced: the cause outranks its own necessary consequence.

3. **Actionability.** Telling an operator that 8103 has `BACKWARD_TIME` invites a timestamp
   correction. No timestamp correction can fix 8102 -> 8103 -> 8102; the component is unorderable
   for any assignment of times. Reporting the symptom as the finding sends the operator to repair
   something that is not broken.

This argument is independent of the manifest. It is derivation, and the manifest merely confirms it.

**Verified in the fixture.** 8102 -> 8103 satisfies all five acceptance conditions (target exists,
different, same aircraft 1099, same AF-06 2026-08-31, 8103 departs 16:00 >= 8102 arrives 15:00,
8103 departs LAX = 8102 arrives LAX). Its *only* defect is the cycle. 8103 -> 8102 additionally
violates the time condition. So this fixture is deliberately constructed to make cycle the sole
diagnosis on one arm and the joint diagnosis on the other — which is exactly the discriminator the
question needs.

## Axis 3 — How much of Q08 is circular? (D-0018-style accounting)

`Q08-CANONICAL` 3 rows x 16 columns = 48 cells. `Q08-ANOMALIES` 11 x 16 = 176 cells. Total 224.

| Bucket | Cells | Detail |
|---|---:|---|
| **Strictly derived** | 196 (87.5%) | Every cell of the 14 non-`row_id`/non-`segment_id` columns, recomputed from raw `SOURCE`. |
| **Supplied manifest labels** | 14 | `row_id` Q08-R001..R014. Already honestly flagged: `LABEL_COLUMNS["Q08"] = ["row_id"]` and `POSITIONAL_ROW_IDS` in `data/run_oracles.py`. |
| **Template-adopted (UNDISCLOSED)** | 14 | `segment_id`. See the finding below. |

**Cells whose value is determined by the `CYCLE` > `BACKWARD_TIME` ordering: zero.**

That is the sharp answer. The ordering does not set any emitted cell. It determines only *whether a
twelfth row exists*. 8102 is the emitted representative under either ordering (its link is
per-link-clean, so it can only ever be `CYCLE`); all eleven emitted rows and all their
classifications are fixed independently of the ordering. Downstream, if a twelfth row were emitted,
the ordinals `SYN-ANOM-03` .. `SYN-ANOM-11` would shift — but those nine cells are already inside
the template-adopted bucket.

Independently verified and untouched by this review: all eleven anomaly classifications including
the `BACKWARD_TIME` exemplar 8107 (not a cycle member — 8101's only out-edge is itself, so 8107 is
unreachable from 8101), the `EXCLUDED` vs `REJECTED` split, every endpoint, every timestamp, every
`next_flight_id`, the three enrichment columns and `type_discrepancy`, and the entire three-row
`Q08-CANONICAL` chain including the AF-06 vs AF-07 selected-day assertion.

**Comparison to D-0018:** D-0018's exposure was 65 supplied + 5 template-adopted of 560 (87.5%
strictly derived). Q08's is 14 supplied + 14 template-adopted of 224 (87.5% strictly derived). The
same shape, and none of it is attributable to the cycle precedence.

### New finding: Q08 `segment_id` is a manifest-adopted template and is currently undisclosed

`SYN-ANOM-<NN>` and `SYN-ROT-<aircraft_id>-<YYYYMMDD>-<NN>` appear in **no specification document**.
Grep of every `.md` and of `SOURCE_CONTRACT.md` / `ATTRIBUTE_AUTHORITY.md` / `DEMO_QUESTIONS.md` /
`data/SYNTHETIC_DATA_SPEC.md` returns nothing; the strings exist only in `EXPECTED_ANSWERS.yaml` and
in `data/oracles/q08_actual_rotation_enriched.sql:159,188`, which reproduces them. The prefixes, the
two-digit zero padding, the `ROW_NUMBER() OVER (ORDER BY flight_id)` ordinal rule for anomalies and
the `ORDER BY root_id` segment ordinal rule for legs were all adopted from the manifest.

This is precisely the D-0018 "template-adopted" class, and unlike Q05 it is **not** flagged:
`LABEL_COLUMNS["Q08"]` lists only `row_id`, so `segment_id` is currently counted as independently
derived in the conformance verdict. It is not. Fourteen cells.

This matters more than the cycle question, because `segment_id` is the **primary sort key** of
Q08's declared `order_by`. The Q08 row sequence is therefore supplied in the same way D-0018 found
Q05's row sequence to be supplied.

## Axis 4 — Does the independent Q08 oracle agree, and does the agreement mean anything?

**It agrees, it is genuinely independent, and it largely defuses the circularity concern — with one
divergence.**

Provenance checked, not assumed. `git log`:

```
9eec511  2026-09-02 10:38:24  DATA-04b  data/oracles/q08_actual_rotation_enriched.sql
e4b7db0  2026-09-02 11:13:43  DATA-04a  data/model_input/60_actual_flight.sql
```

The oracle predates `MODEL_INPUT` by 35 minutes and reads `PK_AVIATION_TEMPORAL.SOURCE.*` directly
(lines 35, 51) — it never touches `MODEL_INPUT`. Its independence from `MODEL_INPUT` is real. Note
the direction: DATA-04a *could* have read the oracle, so the corroboration is one-way. That is still
the useful direction: the ordering was established in this repo by an agent that had no
`MODEL_INPUT` to fit to.

`q08_actual_rotation_enriched.sql:17-21`, written by that agent:

> Every failure stays visible as a typed anomaly, in the frozen precedence
> SELF_LOOP, CYCLE, MISSING_TARGET, DIFFERENT_AIRCRAFT, OUTSIDE_SELECTED_DAY,
> DIVERSION_ENDPOINT_CONFLICT, BACKWARD_TIME, BROKEN_CONTINUITY, CANCELLED,
> MISSING_TIME, UNKNOWN_OR_INVALID_CANCELLATION_FLAG. Exactly one CYCLE row is
> emitted per cycle component, anchored at its minimum flight_id.

It did **not** sidestep precedence: it declared a full total order, put `CYCLE` at rank 2 and
`BACKWARD_TIME` at rank 7, and implemented the same class-gated representative suppression
(`WHERE anomaly_code <> 'CYCLE' OR component_anchor = flight_id`, line 146). Two agents, no shared
implementation, same answer.

Live re-verification this session: `.venv/bin/python data/run_oracles.py --question Q08` ->
`Q08-CANONICAL 3/3 PASS`, `Q08-ANOMALIES 11/11 PASS`, `Q08-NOT-FOUND 0/0 PASS`. (The one `FAIL` in
that run is `q05 cross-question closure`, unrelated to this review.)

**The divergence.** The two implementations do **not** agree on the placement of
`DIVERSION_ENDPOINT_CONFLICT`, and neither matches DV-25:

| Artifact | Position of `DIVERSION_ENDPOINT_CONFLICT` |
|---|---|
| `ATTRIBUTE_AUTHORITY.md` DV-25 | rank 8, after `BROKEN_CONTINUITY` |
| DATA-04b oracle | rank 6, between `OUTSIDE_SELECTED_DAY` and `BACKWARD_TIME` |
| DATA-04a `MODEL_INPUT` | leg tier, **above every link-level class** |

Three artifacts, three placements, zero fixture coverage (8109's link to 8106 is otherwise valid, so
nothing competes). QUERY-ROT will make a fourth choice unless this is pinned. See the required
changes.

## Axis 5 — Is flight 8103's suppression correct on the merits?

**Yes. Determined independently of the manifest, by a frozen specification rule that names the exact
mechanism.**

`DEMO_QUESTIONS.md:312-313`, shipped in `0d2feb3` before any generator, model or query existed:

> **Cycle normalization:** retain all member/link evidence but emit one `CYCLE` output row per cycle
> component at its minimum `flight_id`, preventing duplicate component-level anomalies.

That rule alone decides 8103: it is a member of the component anchored at `min(8102, 8103) = 8102`,
so 8102 is emitted and 8103 is not. `MODEL_INPUT` implements it column for column — I confirmed
against the live table that **both** members are retained with `rotation_anomaly_class = 'CYCLE'`,
`cycle_component_id = 8102`, and `is_cycle_representative` true for 8102 and false for 8103. Nothing
is dropped at the `MODEL_INPUT` layer; the suppression is a consumer-side presentation rule, exactly
as "retain all member/link evidence" requires. That is a better design than the reviewed claim
implies.

Corroborating, from `data/SYNTHETIC_DATA_SPEC.md`:

- line 521 declares 8103's fixture role as **"cycle target"** — a supporting fixture, not an anomaly
  exemplar. Every other 1099 leg's Override/purpose column names the anomaly class it demonstrates;
  8103's does not.
- line 622 anchors `{ids: [Q08-R005], source: [AF-8102, AF-8103]}` — one output row, two input legs,
  declared in the fixture-ownership map.

The eleven emitted rows are one exemplar per anomaly class. 8103 is the second half of the cycle
construction, in the same category as 8205 (different-aircraft target), 8206 (outside-day target)
and absent-8999 (missing target) — none of which produce rows either.

### Where the DATA-04a argument actually fails

DATA-04a claims the ordering is "the only ordering under which flight 8103 is suppressed ... and
`Q08-ANOMALIES` has exactly 11 rows". **That is false.** Counter-example, constructed and checked
against the fixture:

Take precedence `BACKWARD_TIME` > `CYCLE`, and gate the suppression on **component membership**
rather than on class. Then 8102 is still `CYCLE` (its link is per-link-clean, nothing else can
apply), still the min-flight-id representative, still emitted. 8103 becomes `BACKWARD_TIME`, is
still a non-representative member of component 8102, and is still suppressed. Result: **11 rows,
byte-identical output.**

So the row count does not discriminate the precedence at all. DATA-04a fitted against a test that
cannot fail. Two independent degrees of freedom (the precedence, and whether suppression is gated on
class or on component membership) were collapsed by one observation that constrains neither.

The genuine discriminator is not the count. It is:

1. The rule text is **class-gated on its face** — "emit one `CYCLE` output row per cycle component",
   and the duplicates it exists to prevent are component-level `CYCLE` duplicates. It does not
   license discarding a `BACKWARD_TIME` finding. The component-gated variant suppresses an anomaly
   the rule never authorized suppressing.
2. DV-25's pre-manifest enumeration puts cycle(2) ahead of time(6).
3. The subsumption argument in Axis 2.
4. DATA-04b's independent concurrence.

The conclusion is unchanged and the shipped output is right. The *reasoning that was written down*
is unsound, and it is the reasoning that ships to the customer.

## Axis 6 — What must QUERY-ROT do?

**Inherit the ordering, but inherit it from the contract citation, not from the `MODEL_INPUT`
comment; and expose the anomaly set order-free, applying the precedence and the dedup only at
presentation.**

Concretely:

1. **Do not re-derive.** The ordering is settled by DV-25 + `SOURCE_CONTRACT.md:363-366` +
   `DEMO_QUESTIONS.md:312`. Re-deriving invites a third answer. Cite those three lines in the PyRel
   rule docstring.
2. **Emit the anomaly set order-free.** Every leg gets its full predicate evidence
   (`is_self_loop`, `cycle_component_id`, `target_missing`, `different_aircraft`, `outside_day`,
   `backward_time`, `broken_continuity`, `diversion_endpoint_conflict`, the three exclusion flags)
   as independent derived properties. Collapse to the single DV-25 `rotation_anomaly_class` in one
   place, at the top, where the precedence is one readable ordered list. That way a reader can audit
   the precedence without reading a nested `CASE`, and a future precedence change touches one line.
3. **Apply the cycle dedup at presentation only**, gated on `rotation_anomaly_class = 'CYCLE'` and
   `is_cycle_representative`, per `DEMO_QUESTIONS.md:312`. Do not push it into the anomaly relation
   — "retain all member/link evidence" is a contract requirement and `MODEL_INPUT` currently honours
   it.
4. **Follow the D-0018 QUERY-UC2 binding for `segment_id`.** The `SYN-ANOM-<NN>` /
   `SYN-ROT-...-<NN>` templates are manifest-adopted. Keep them out of the PyRel model. Compare Q08
   as an order-free join on `(flight_id, anomaly_code)` for the semantic verdict; assert the
   declared sequence separately as a labelled presentation check; render the templates last, in the
   notebook and agent layer.
5. **Do not inherit `TARGET_NOT_OPERATED` silently.** `MODEL_INPUT` can emit a class the DATA-04b
   oracle has no branch for. Zero rows today, but a QUERY-ROT-vs-oracle conformance harness will
   diverge the first time a rotation target is cancelled. Either add the class to the oracle or
   fence it behind an explicit "beyond the frozen vocabulary" flag.
6. **Scope cycle detection to the selected `(aircraft_id, AF-06)`**, matching the oracle, not
   globally — see the finding below.

---

## Undisclosed items DATA-04a did not declare

None of these appear in `declared_ambiguities` in `build/task_reports/DATA-04a.json`, and none is
covered by D-0020. All are latent, all are zero-row today, all will be inherited by QUERY-ROT.

**U1 — Leg-tier hoisting inverts the DV-25 order.** `MODEL_INPUT` evaluates
`UNKNOWN_OR_INVALID_CANCELLATION_FLAG`, `CANCELLED`, `MISSING_TIME` and
`DIVERSION_ENDPOINT_CONFLICT` **above** every link-level class; DV-25 and the oracle put them at the
**bottom**. For the first three the hoist is contract-forced — DV-52 says an invalid flag "excludes
the leg from the strict operated chain", and the manifest's `link_outcome` `EXCLUDED` vs `REJECTED`
split cannot be produced otherwise. For `DIVERSION_ENDPOINT_CONFLICT` it is not forced, and it is
where the three artifacts disagree three ways (Axis 4). Unexercised: 8109's link is otherwise valid.

**U2 — Cycle detection scope is global, the oracle's is selected-day.**
`60_actual_flight.sql:104-108` builds `edges` over all 3,900 `AIRCRAFT_FLIGHT` rows;
`q08_actual_rotation_enriched.sql:64-70` restricts to `selected_leg` (same aircraft, same AF-06).
Because `MODEL_INPUT` ranks `CYCLE` above `DIFFERENT_AIRCRAFT` and `OUTSIDE_SELECTED_DAY`, a
two-leg cycle spanning two aircraft or two days would be `CYCLE` in `MODEL_INPUT` and
`DIFFERENT_AIRCRAFT` / `OUTSIDE_SELECTED_DAY` in the oracle. Verified zero such rows today
(`SELECT COUNT(*) ... WHERE cycle_component_id IS NOT NULL` = 3, all within aircraft 1099 on
2026-08-31). Real latent divergence.

**U3 — Self-loops are cycle components in `MODEL_INPUT`, not in the oracle.** `MODEL_INPUT` gives
8101 `cycle_component_id = 8101, is_cycle_representative = TRUE`; the oracle excludes self-edges
from `graph_edge` (line 69), so 8101 has no component. The `rotation_anomaly_class` agrees
(`SELF_LOOP`, since self-loop outranks cycle) but the two derived columns disagree, and any consumer
that counts cycle components gets 2 from `MODEL_INPUT` and 1 from the oracle.

**U4 — Q08 `segment_id` is manifest-adopted and unflagged.** Detailed under Axis 3. Fourteen cells,
and it is the primary sort key of the declared `order_by`.

---

## Proposed `Review:` wording for the DECISION_LOG entry

> **Review:** Independent reviewer `REVIEW-D0021`, which did not author the model-input layer, the
> oracle or any specification document, returned **DERIVABLE — no circularity** on the ordering and
> **rejected the justification**. Full report at `build/task_reports/REVIEW-D0021.md`. The reviewer
> established that the premise is false: the anomaly classes are ordered in
> `ATTRIBUTE_AUTHORITY.md` DV-25 ("self/cycle/missing/different/day/time/continuity/
> diversion-conflict/cancel/missing-time") and again in `SOURCE_CONTRACT.md:363-366`, both shipped in
> commit `15d8f35` thirty-four minutes before `EXPECTED_ANSWERS.yaml` existed, so the manifest was
> written from the enumeration rather than the reverse; the frozen `SYN-ANOM-01..11` fixture
> numbering reproduces the DV-25 order exactly across all ten shared classes. The suppression of
> flight 8103 is separately and fully determined by `DEMO_QUESTIONS.md:312`, "retain all member/link
> evidence but emit one `CYCLE` output row per cycle component at its minimum `flight_id`", which
> the model-input layer implements literally by retaining both members with
> `is_cycle_representative` rather than dropping either. Three manifest fixtures independently pin
> three other precedence pairs (`SELF_LOOP` over `CYCLE` at 8101, `DIFFERENT_AIRCRAFT` over
> `BROKEN_CONTINUITY` at 8105, `BACKWARD_TIME` over `BROKEN_CONTINUITY` at 8107), all agreeing with
> DV-25 and none contradicting it, and the DATA-04b oracle — committed thirty-five minutes earlier
> by a different agent reading `SOURCE` only — declares the identical ordering and the identical
> class-gated representative suppression. The reviewer additionally refuted the supporting claim
> that this is "the only ordering under which flight 8103 is suppressed": pairing
> `BACKWARD_TIME` over `CYCLE` with a component-gated rather than class-gated suppression yields
> byte-identical eleven-row output, so the row count discriminates neither degree of freedom and the
> fitting was tested against a check that cannot fail. Cell accounting: of Q08's 224 cells, 196 are
> strictly derived, 14 are supplied `row_id` labels already flagged in `data/run_oracles.py`, and 14
> are manifest-adopted `segment_id` templates that are **not** flagged; **zero** cells have their
> value determined by the cycle precedence, which fixes only whether a twelfth row exists. Four
> corrections were required, all raised as new findings the task did not declare: the justification
> must be replaced by the contract citation; the `DIVERSION_ENDPOINT_CONFLICT` rank is placed three
> different ways across DV-25, the oracle and the model-input layer and must be pinned; cycle
> detection is scoped globally in the model-input layer versus per selected `(aircraft, AF-06)` in
> the oracle, which diverges on any cross-aircraft or cross-day cycle; and the `SYN-ANOM-<NN>` /
> `SYN-ROT-<aircraft>-<YYYYMMDD>-<NN>` templates appear in no specification and must be disclosed
> under the D-0018 template-adopted class, since `segment_id` is Q08's primary sort key.

---

## Required changes

| # | Change | File | Severity |
|---|---|---|---|
| R1 | Replace the "not stated in the contract, so I derived it from the manifest" justification with the contract citation: `ATTRIBUTE_AUTHORITY.md` DV-25, `SOURCE_CONTRACT.md:363-366`, `DEMO_QUESTIONS.md:312`. Delete the "only ordering under which 8103 is suppressed" claim — it is false. | D-0021 entry; `data/model_input/60_actual_flight.sql:87-99` header | **Must fix.** A customer engineer can falsify the "only ordering" claim in two minutes. |
| R2 | Disclose `segment_id` as a manifest-adopted template under the D-0018 class. Add `segment_id` to the Q08 label reporting in `data/run_oracles.py` (report it, keep it under the strict verdict, as Q05 does), and record the 196/14/14 three-way split. | `data/run_oracles.py`, D-0021 entry | **Must fix.** Currently counted as independently derived; it is not, and it is the declared primary sort key. |
| R3 | Pin the `DIVERSION_ENDPOINT_CONFLICT` rank. Three artifacts, three placements, zero coverage. Pick one, state why, make the oracle and the model-input layer agree, and bind QUERY-ROT to it. | D-0021 entry; `60_actual_flight.sql`, `q08_actual_rotation_enriched.sql` | **Must fix before QUERY-ROT** or you ship a fourth placement. |
| R4 | Declare U2 (global vs selected-day cycle scope) and U3 (self-loop as a cycle component) as ambiguities in the D-0020 style, with `visible_as` columns, and mark them implemented-but-unexercised for REDTEAM-01. | D-0021 entry, `build/task_reports/DATA-04a.json` `declared_ambiguities` | Should fix. Latent divergence between the two artifacts the demo claims are independent. |
| R5 | Note `TARGET_NOT_OPERATED` (D-0020 A5) exists in `MODEL_INPUT` but has no oracle branch, so a QUERY-ROT conformance harness will diverge the first time a rotation target is cancelled. | D-0020 A5 cross-reference; QUERY-ROT brief | Should fix. |
| R6 | Bind QUERY-ROT to: inherit the ordering from the contract citation, expose the anomaly set order-free with the precedence collapsed in one readable ordered list, apply the cycle dedup at presentation only, and keep the `segment_id` templates out of the PyRel model per the D-0018 QUERY-UC2 binding. | QUERY-ROT brief | Should fix. |

No change to `EXPECTED_ANSWERS.yaml`. No change to the shipped `MODEL_INPUT` classification logic
for the cycle precedence — it is correct.

## Evidence index

- `EXPECTED_ANSWERS.yaml:5-10` authority block; `:250-256` NF-R01 (8103 present as a source id,
  8999 deliberately absent); `:1496-1511` `Q08-ANOMALIES`.
- `SOURCE_CONTRACT.md:358-372` DV-45 / acceptance conjunction / anomaly enumeration / DV-52-53;
  `:462` `ROTATION_LINK_VALIDATION` contract row.
- `ATTRIBUTE_AUTHORITY.md:337-338` DV-24 / DV-25.
- `DEMO_QUESTIONS.md:312-313` cycle normalization.
- `data/SYNTHETIC_DATA_SPEC.md:519-536` Q08 fixture table and the "Anomaly precedence is exactly the
  frozen manifest order" disclosure; `:622` `Q08-R005 <- [AF-8102, AF-8103]`.
- `data/model_input/60_actual_flight.sql:87-99` documented precedence; `:104-120` cycle CTEs;
  `:146-175` classification; `:196-198` representative flag.
- `data/oracles/q08_actual_rotation_enriched.sql:17-21` declared precedence; `:64-92` cycle CTEs;
  `:97-115` classification; `:146` class-gated suppression; `:159,188` segment templates.
- Live: `SOURCE.AIRCRAFT_FLIGHT` rows 8001-8003, 8101-8112, 8205-8206;
  `MODEL_INPUT.ROTATION_LINK_VALIDATION` for aircraft 1001/1098/1099; global cycle-participating
  row count = 3; `run_oracles.py --question Q08` = 3 PASS.
- `git log` provenance for `15d8f35`, `0d2feb3`, `9eec511`, `e4b7db0`.
