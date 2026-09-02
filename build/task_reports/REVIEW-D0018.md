# REVIEW-D0018 — adversarial review of the Q05 `event_id` non-derivability claim

- **Reviewer:** REVIEW-D0018 (independent; did not author DATA-04b, the oracles, or the manifest)
- **Subject:** DATA-04b open issue `DATA-04b-OI-1` and the treatment implemented in
  `data/oracles/q05_event_labels.sql`
- **Date:** 2026-09-02
- **Method:** static enumeration of all 30 mnemonics plus a live in-memory mutation harness that
  monkeypatches `run_oracles.render` and re-runs `Q05-CANONICAL` against
  `PK_AVIATION_TEMPORAL.SOURCE` under 17 injected defects. No repo file was modified, no Snowflake
  object was created, `EXPECTED_ANSWERS.yaml` was not touched.

## Verdict

**UPHELD WITH CHANGES.**

The core claim is correct and I could not break it. The mnemonics are not derivable, the diagnosis is
substantially right, and I found no perturbation in which the label table lets a wrong Q05 result
pass. Three things must change before QUERY-UC2 inherits this: the "candidate/ambiguous/member ids
ARE derived" claim is over-stated, the diagnosis under-states the defect class, and the ordering
circularity must be disclosed in the customer-facing parity wording rather than only in an open
issue.

---

## Axis 1 — Is the non-derivability claim true?

**Yes. Proven twice, once on the strings and once on the declared row order.**

### 1a. The 30 mnemonics

Full enumeration (prefix `SYN-<CHG|ADD|REM|UNPAIR-ADD|UNPAIR-REM>-<YYYYMMDD>`, tail shown):

| date | class | schedule key stem | field | tail |
|---|---|---|---|---|
| 08-10 | ADDITION | `ADD_300` | `__presence__` | `300` |
| 08-10 | MODIFICATION | `BASE_100` | `total_seats` | `BASE-SEATS` |
| 08-10 | REMOVAL | `REAPPEAR_400` | `__presence__` | `REAPPEAR` |
| 08-10 | REMOVAL | `REMOVE_200` | `__presence__` | `200` |
| 08-10 | UNPAIRED_ADDITION | `ADD_300` | – | `300` |
| 08-10 | UNPAIRED_REMOVAL | `REAPPEAR_400` | – | `REAPPEAR` |
| 08-10 | UNPAIRED_REMOVAL | `REMOVE_200` | – | `200` |
| 08-17 | ADDITION | `REAPPEAR_400` | `__presence__` | `REAPPEAR` |
| 08-17 | ADDITION | `SHIFT_NEW` | `__presence__` | `SHIFT-NEW` |
| 08-17 | REMOVAL | `SHIFT_OLD` | `__presence__` | `SHIFT-OLD` |
| 08-17 | UNPAIRED_ADDITION | `REAPPEAR_400` | – | `REAPPEAR` |
| 08-24 | ADDITION | `AMB_NEW_A` | `__presence__` | `AMB-A` |
| 08-24 | ADDITION | `AMB_NEW_B` | `__presence__` | `AMB-B` |
| 08-24 | MODIFICATION | `ADD_300` | `weekly_frequency` | `ADD300-FREQ` |
| 08-24 | MODIFICATION | `CLOCK_BOUNDARY_001` | `arrival_station_code_iata` | `CLOCK-ROUTE-OPEN` |
| 08-24 | REMOVAL | `AMB_OLD` | `__presence__` | `AMB-OLD` |
| 08-31 | ADDITION | `MKT_ENTRY_714` | `__presence__` | `MKT-ENTRY` |
| 08-31 | ADDITION | `UNPAIR_NEW` | `__presence__` | `UNPAIR-NEW` |
| 08-31 | MODIFICATION | `BASE_100` | `departure_terminal` | `BASE-TERMINAL` |
| 08-31 | MODIFICATION | `CLOCK_BOUNDARY_001` | `arrival_station_code_iata` | `CLOCK-ROUTE-CLOSE` |
| 08-31 | MODIFICATION | `CSH_ONLY_900` | `departure_terminal` | `CAP-900-TERMINAL` |
| 08-31 | MODIFICATION | `MKT_COPY_702` | `departure_terminal` | `CAP-702-TERMINAL` |
| 08-31 | MODIFICATION | `PHY_BASE_700` | `departure_terminal` | `CAP-700-TERMINAL` |
| 08-31 | MODIFICATION | `PHY_BASE_701` | `departure_terminal` | `CAP-701-TERMINAL` |
| 08-31 | REMOVAL | `MKT_EXIT_715` | `__presence__` | `MKT-EXIT` |
| 08-31 | REMOVAL | `UNPAIR_OLD` | `__presence__` | `UNPAIR-OLD` |
| 08-31 | UNPAIRED_ADDITION | `MKT_ENTRY_714` | – | `MKT-ENTRY` |
| 08-31 | UNPAIRED_ADDITION | `UNPAIR_NEW` | – | *(empty)* |
| 08-31 | UNPAIRED_REMOVAL | `MKT_EXIT_715` | – | `MKT-EXIT` |
| 08-31 | UNPAIRED_REMOVAL | `UNPAIR_OLD` | – | *(empty)* |

Rule-fit scores over the schedule-key token sequence (best of seven candidate generators, field token
stripped first for modifications):

```
all tokens, _->-            5/30      drop numeric tokens        15/30
numeric token only          6/30      first token                 6/30
last token                  4/30      drop middle token           7/30
drop first token            4/30
```

Nothing is close. Three irreducible contradictions, each between rows that share the discriminating
context, so no per-class, per-field or positional refinement can rescue a rule:

1. **Same date, same class, same field.** `2026-08-31`, `EXACT_KEY_PRESERVING_MODIFICATION`,
   `departure_terminal`: `BASE_100` → `BASE` (numeric dropped, stem kept) while `PHY_BASE_700` →
   `CAP-700` (stem dropped, numeric kept, prefixed with a token `CAP` that appears nowhere in the
   key). This alone kills every token-selection rule.
2. **Same class, same key shape.** `EXACT_ADDITION` maps `MKT_ENTRY_714` → `MKT-ENTRY` (drop the last
   token) and `AMB_NEW_A` → `AMB-A` (drop the *middle* token). Same class, same 3-token shape,
   opposite treatment. And `SHIFT_NEW` → `SHIFT-NEW` keeps `NEW` while `AMB_NEW_A` drops it.
3. **Same key, different class, inconsistent carry-over.** `ADD_300` yields tail `300` in both
   `EXACT_ADDITION` and `UNPAIRED_ADDITION`, but `UNPAIR_NEW` yields `UNPAIR-NEW` in `EXACT_ADDITION`
   and an *empty* tail in `UNPAIRED_ADDITION`.

Field tokens are equally ad hoc: `total_seats` → `SEATS` (last word), `departure_terminal` →
`TERMINAL` (last word), `weekly_frequency` → `FREQ` (abbreviation, not the last word),
`arrival_station_code_iata` → `ROUTE-OPEN` / `ROUTE-CLOSE` (not a word of the field at all, plus a
direction suffix that depends on `new_value` nullity).

I also checked the alternative sources the author did not name: `SCHEDULE_KEY_READABLE` in
`SOURCE.SCHEDULE_SNAPSHOT` is `SYN-READABLE|<schedule_key>|<publish_date>` and carries no mnemonic;
`data/SYNTHETIC_DATA_SPEC.md` contains no `SYN-CHG-`/`SYN-ADD-`/`SYN-REM-`/`SYN-UNPAIR-` string at
all; no `SOURCE` table has a row-id sequence that orders these events; and DV-34/35/36/37 are
SHA-256, which cannot produce them.

### 1b. The declared row order (the stronger proof)

`order_by` is `comparison_date, Q05_event_class rank, event_id, member_side NULLS LAST,
member_schedule_key NULLS LAST`. Within one `(comparison_date, event_class)` block the only
discriminator before the member tiebreakers is `event_id`. Enumerating the declared per-block key
sequences:

```
2026-08-31 EXACT_ADDITION      [MKT_ENTRY_714, UNPAIR_NEW]
2026-08-31 UNPAIRED_ADDITION   [UNPAIR_NEW, MKT_ENTRY_714]      <- inverted
2026-08-31 EXACT_REMOVAL       [MKT_EXIT_715, UNPAIR_OLD]
2026-08-31 UNPAIRED_REMOVAL    [UNPAIR_OLD, MKT_EXIT_715]       <- inverted
```

Two blocks on the same `comparison_date` containing exactly the same two schedule keys order them
**oppositely**. Therefore *no* total order on `schedule_key`, on any per-key attribute
(`flight_number`, `old_value`, route-declaration index in `scope.anchored_schedule_routes`), or on
any function of the pair is capable of reproducing both. The declared fallback tiebreakers do not
rescue it either: in `UNPAIRED_ADDITION` both rows carry `member_side = ADDED`, so
`member_schedule_key` decides and yields `MKT_ENTRY_714` first, which is the opposite of the
manifest. Four further blocks (`2026-08-10 EXACT_REMOVAL`, `2026-08-10 UNPAIRED_REMOVAL`,
`2026-08-31 EXACT_KEY_PRESERVING_MODIFICATION`, `2026-08-24 AMBIGUOUS_GROUP_MEMBER`) also depart from
schedule-key order.

**Conclusion for axis 1: the claim is correct. The mnemonics are not derivable, and the frozen row
order genuinely cannot be produced without them.**

---

## Axis 2 — Is the diagnosis right?

**(a) oracle defect: refuted.** Everything except `event_id` is computed from raw `SOURCE` and every
injected defect is caught (axis 3).

**(b) generator defect: refuted.** `SOURCE` has ten tables and none of them carries an event label.
`SCHEDULE_EXACT_CHANGE`, `SCHEDULE_AMENDMENT_CANDIDATE`, `SCHEDULE_AMENDMENT_GROUP` and
`SCHEDULE_AMENDMENT_GROUP_MEMBER` live in `SOURCE_CONTRACT.md` under **"Canonical physical
model-input contracts"** — they are `MODEL_INPUT` derivations, not source tables, and their contracted
identities are DV-34/35/36/37 SHA-256. `data/SYNTHETIC_DATA_SPEC.md` never asks the generator to emit
a label. The generator did what it was told; the spec never contemplated these strings.

**(c) accepted, but under-stated.** The issue is not merely "the frozen expectation contains a
non-derivable presentation column". It is a **manifest/contract conflict**: `EXPECTED_ANSWERS.yaml`
populates `event_id` with values that contradict the contract's own definition of that identity
(ATTRIBUTE_AUTHORITY DV-34..37), *and* then makes that column load-bearing as a sort key. That is the
same species of internal inconsistency as D-0010 and D-0011, both of which were resolved by
**reviewed supersession of the manifest**, not by a workaround. A stricter reading of the D-0010
precedent would demand supersession here too.

I nevertheless agree with the interim treatment, on two grounds that must be recorded rather than
left implicit: superseding would change 30 `event_id` values, the declared row sequence and the Q05
result hash (blast radius far larger than D-0010/D-0011), and replacing the mnemonics with SHA-256
digests would make the customer-facing Q05 output unreadable, which is a real cost for a demo whose
whole point is legible temporal reconciliation. The decision must say that the conflict was
identified, that supersession was considered, and that the manifest's presentation values win over
DV-34..37 for Q05 `event_id` specifically.

---

## Axis 3 — Does the label table fail loud?

**Yes. Seventeen injected defects, seventeen loud failures. I could not construct a silent pass.**

Harness: `run_oracles.render` monkeypatched in memory, `Q05-CANONICAL` re-executed live per case.

| # | Injected defect | strict verdict | semantic verdict | how it surfaced |
|---|---|---|---|---|
| 00 | none (baseline) | PASS | PASS | 35/35, 0 diffs |
| P1 | drop one EXACT modification | FAIL | FAIL | 34 rows, `MISSING_ACTUAL_ROW` + 12 semantic diffs |
| P2 | inject one spurious EKPM event | FAIL | FAIL | 36 rows, spurious row rendered `UNLABELLED|...` |
| P3 | misclassify a REMOVAL as an ADDITION | FAIL | FAIL | `event_class` + `event_id` (label miss) |
| P4 | swap two label-table rows | FAIL | FAIL | `schedule_key`, `old_value`, `new_value` |
| P5 | drop `field_name` from the label key | PASS | PASS | key is non-minimal (see axis 4) |
| P6 | drop `event_class` from the label key | PASS | PASS | key is non-minimal (see axis 4) |
| P7 | drop `comparison_date` from the label key | FAIL | FAIL | 37 rows via join fan-out |
| P8 | replace the `UNLABELLED` fallback with a plausible string | PASS | PASS | fallback is never hit on the happy path |
| P9 | corrupt one `old_value` | FAIL | FAIL | `old_value` |
| P10 | drop one UNPAIRED evidence row | FAIL | FAIL | 34 rows |
| P11 | change the `-Mk` member ordering rule | FAIL | FAIL | `member_side`, `member_schedule_key` |
| P12 | change the `SYN-CAND` ordinal padding | FAIL | **PASS** | `event_id` only — see the caveat below |
| P13 | flip one UNPAIRED side | FAIL | FAIL | `event_class`, `schedule_key`, member fields |
| P14 | attribute an event to the wrong `schedule_key` | FAIL | FAIL | `schedule_key` + `event_id` (label miss) |
| P15 | P8 + P2 | FAIL | FAIL | cardinality still catches it |
| P16 | P8 + P3 | FAIL | FAIL | `event_class` still catches it |
| P17 | P8 + P14 | FAIL | FAIL | `schedule_key` still catches it |

Findings:

- **The mitigation is adequate.** Extra, missing, misclassified and misattributed events are all
  caught, and P15/P16/P17 show the detection does not depend on the `UNLABELLED` string being
  well-formed: cardinality and the 14 derived columns carry the load. The `UNLABELLED` fallback is a
  *diagnostic aid*, not the detector. That is worth saying accurately, because P8 shows the fallback
  can be silently degraded with no test noticing.
- **All 30 labels are consumed exactly once** (30 label rows, 30 declared-label result rows, baseline
  produces no `UNLABELLED`), so the table contains no spare entry that a spurious event could land
  on. `data/test_oracles.py::test_q05_declared_label_table_covers_only_exact_and_unpaired_rows`
  additionally pins the table to exactly the 30 manifest strings and forbids it from carrying a
  derived id. Good containment.
- **P12 is a real reporting defect.** `LABEL_COLUMNS["Q05"] = ["row_id", "event_id"]` excludes the
  *whole* `event_id` column from `semantic_verdict`, including the five ids the author claims are
  derived. A format regression in the derived `SYN-CAND` / `SYN-AMB` ids therefore reports
  `semantic_verdict = PASS`, and
  `test_semantic_verdicts_are_green_independently_of_declared_labels` would not fail. The strict
  `verdict` still fails, so the gate holds, but the reporting over-claims. Fix or annotate.

---

## Axis 4 — Is `(comparison_date, event_class, schedule_key, field_name)` unique?

**Unique over the domain it is applied to; not unique over all 35 rows.** State it precisely.

- Over the 30 declared-label rows: **zero collisions** (verified by enumeration).
- Over all 35 rows: one 3-way collision,
  `('2026-08-24', 'AMBIGUOUS_GROUP_MEMBER', NULL, '')`. This is harmless because those rows carry
  `schedule_key = NULL`, SQL equality never matches NULL, and their ids come from the derived
  `ambiguous_member` join instead. But the proposal's wording should say "unique across the five
  declared classes with non-null `schedule_key`", not "unique across the 35 rows".
- **Minimality:** dropping `comparison_date` collides (`CLOCK_BOUNDARY_001` /
  `arrival_station_code_iata` recurs on 08-24 and 08-31 — this is what makes P7 fan out to 37 rows).
  Dropping `schedule_key` collides 9 ways. Dropping `event_class` or `field_name` *individually*
  collides zero times today (P5/P6 pass), because `EXACT_ADDITION` carries `__presence__` where
  `UNPAIRED_ADDITION` carries `''`, so each covers for the other. Keep both: the redundancy is what
  makes a misclassification produce an `UNLABELLED` id (P3) instead of silently re-attaching.
- **Durability under the fixture universe:** a schedule key cannot be both added and removed on one
  comparison date (presence flips one way), two modifications on one key/date differ by
  `field_name`, and a key that is simultaneously an exact presence row and an ambiguous group member
  is disambiguated because the member row's `schedule_key` is NULL. I found no construction inside
  `SYN-SCHEDULE-UNIVERSE-01`, or admissible under
  `scope.schedule_source_universe.materialization_rules`, that collides. **No collision exists.**
- One genuine scope limit: the key includes `comparison_date`, so the label table only labels
  `Q05-CANONICAL`. Any other parameterisation would render every event `UNLABELLED`. That is
  fail-loud and correct, but it should be stated so nobody assumes the oracle generalises.

---

## Axis 5 — How much of Q05's PASS is circular?

This is the axis that matters in front of a customer, so here is the exact accounting.

`Q05-CANONICAL` is 35 rows x 16 columns = **560 cells**.

| Cells | Status |
|---|---|
| 35 `row_id` | **declared** — taken positionally from the manifest (`row_id_source = DECLARED_MANIFEST_LABEL_POSITIONAL`); pre-existing issue `DATA-04b-OI-2`, applies to 43 of the 198 golden rows overall |
| 30 `event_id` (exact + unpaired) | **declared** — supplied by `q05_event_labels.sql` |
| 5 `event_id` (candidate / group / member) | **content derived, template adopted** — see the correction below |
| 490 remaining cells | **independently derived from raw `SOURCE`** |

So **88.4 percent of the Q05 cells are independently recomputed and 11.6 percent are supplied**, and
of the supplied ones, 35 are the manifest-wide `row_id` condition that also affects Q01 and Q07.

**Independently verified for Q05, with no manifest input:**

- which 35 events exist, per adjacent pair (7 / 5 / 9 / 14) — enforced by
  `cross_question_event_closure` and reproduced from `SOURCE`
- every event's `event_class`, `exactness`, `confidence`
- every `schedule_key`, `related_schedule_key`, `member_side`, `member_schedule_key`
- every `field_name`, `old_value`, `new_value`
- `crosses_snapshot_gap`
- the candidate / ambiguous / unpaired partition, group membership, and the
  `exact_presence_partner_closure` rule
- the eligibility gate and the `Q05-INELIGIBLE-ENDPOINT` `ENDPOINT_MISSING` result

**Not independently verified:**

- the `event_id` string for the 30 exact and unpaired rows
- the `row_id` string for all 35 rows
- **the declared row sequence.** This is the one that is genuinely circular rather than merely
  cosmetic. The order key is `event_id`; the `event_id` values are supplied; therefore the ordered
  sequence part of the Q05 PASS is *supplied, not verified*. Axis 1b proves it could not have been
  verified: the manifest order is not a function of any derived column.

**Honest framing.** The order is not free-floating — once each derived semantic identity is computed,
the lookup is deterministic and total, and the row-to-content pairing is fully checked. What the
harness cannot claim is "the implementation independently arrived at the manifest's row order for
Q05". Two artifacts currently over-claim and must be softened:

- `DEMO_QUESTIONS.md` Q05, "the bounded claim covers exactly the 35 **independently recomputed** v1.1
  rows"
- `build/task_reports/DATA-04b.json` summary, "reproduce all 24 frozen result sets ... as complete,
  **ordered**, typed sequences"

Both are true of content and false of `event_id` / `row_id` / row order. The per-result-set
`label_columns` and `row_id_source` fields already disclose it correctly; the headline sentences do
not. Fix the headlines. A customer who reads the open issue after hearing "zero cell diffs, fully
independent" will conclude the demo oversold itself; a customer who is told up front "the facts are
recomputed, the display labels are declared and cross-checked for exhaustiveness" will find that
entirely normal.

### Correction to the "candidate/ambiguous/member ids ARE derived" claim

This is over-stated and must be amended. What is derived is the **ordinal content, the grouping and
the membership**. What was **adopted from the frozen manifest** is:

- the string templates `SYN-CAND-<YYYYMMDD>-NN`, `SYN-AMB-<YYYYMMDD>-NN`, `<group_id>-M<k>`, including
  the two-digit zero padding. Neither `SYN-CAND` nor `SYN-AMB` appears anywhere in `SOURCE_CONTRACT.md`,
  `ATTRIBUTE_AUTHORITY.md`, `DEMO_QUESTIONS.md` or `data/SYNTHETIC_DATA_SPEC.md` — only in
  `EXPECTED_ANSWERS.yaml`.
- the `NN` ordinal rule `ROW_NUMBER() OVER (PARTITION BY comparison_date ORDER BY signature_token)`.
  The universe contains exactly one candidate and one group, so `NN` is always `01` and this rule is
  **entirely unconstrained by evidence**.
- the `-Mk` member ordering `REMOVED` before `ADDED`, then `schedule_key` ascending. This is weakly
  grounded in the DV-37 / `SCHEDULE_AMENDMENT_GROUP_MEMBER` side enumeration `REMOVED|ADDED`, but is
  nowhere stated as a sort rule. P11 shows the natural alternative `(schedule_key, side)` produces a
  different and failing answer, so the rule was fitted to the manifest, not read off the contract.

None of this is serious — the information content is a handful of bits versus the 30 mnemonics' full
event identity — but the claim as written says "ARE derived" without qualification and a reviewer
reading only the open issue would be misled.

---

## Axis 6 — What should QUERY-UC2 do?

**Do not put the label table inside the PyRel model.** Sharing `q05_event_labels.sql` verbatim into
the RAI layer would embed 30 lines of the frozen answer inside the artifact whose independence the
demo is trying to demonstrate, and it would do so twice, which converts a disclosed one-off into a
structural property of the deliverable.

Recommended shape:

1. The RAI query computes the same 14 derived columns plus the semantic identity tuple
   `(comparison_date, event_class, schedule_key, field_name)`, and emits its own event identity from
   ATTRIBUTE_AUTHORITY DV-34..37 (which is what the contract actually mandates) or leaves `event_id`
   unpopulated.
2. The **conformance harness** — one shared component outside both the oracle and the model — applies
   the single declared label map to both sides and performs the comparison. That way there is exactly
   one copy of the manifest strings in the repo, in a file whose name says what it is, and neither
   the SQL oracle nor the PyRel model is "told the answer" in its own body.
3. Compare Q05 as an **order-free join on the semantic identity** for the semantic verdict, and check
   the declared sequence separately as an explicitly-labelled presentation assertion. This makes the
   circularity structural and visible instead of hidden inside a passing ordered diff.
4. The notebook / Cortex-agent presentation layer joins the label map last, so the demo still shows
   `SYN-CHG-20260831-CAP-700-TERMINAL` to the audience while the business answer stays fully derived.

If a later decision wants to remove the circularity entirely rather than disclose it, the only clean
route is a reviewed manifest supersession that replaces Q05's `order_by` with a derivable key (for
example `comparison_date, event_class rank, schedule_key, field_name, member_side,
member_schedule_key`) and demotes `event_id` to a non-ordering presentation column. That changes the
declared row sequence but no row's content. I do not recommend doing it now — the disclosure is
cheaper and the demo reads better with mnemonics — but the option should be recorded as the rollback.

---

## Required changes

1. **Amend the derived-id claim** in the DECISION_LOG entry and in
   `data/oracles/q05_event_labels.sql`'s header comment: candidate / group / member ids are derived in
   *content*, but their string templates, the `NN` ordinal rule and the `-Mk` member ordering were
   adopted from the frozen manifest. Note that `NN` is unconstrained (always `01` in this universe).
2. **Restate the diagnosis** as a manifest/contract conflict on `event_id` (manifest values contradict
   ATTRIBUTE_AUTHORITY DV-34..37 and the column is load-bearing as a sort key), record that the
   D-0010/D-0011 supersession precedent was considered and rejected on blast-radius and
   demo-legibility grounds, and name manifest supersession of `order_by` as the rollback.
3. **Fix the semantic-verdict reporting** so the five derived `event_id` cells are enforced — either
   scope `LABEL_COLUMNS` per row rather than per column, or rename
   `test_semantic_verdicts_are_green_independently_of_declared_labels` and record in `run_oracles.py`
   that Q05's `event_id` exclusion also suppresses the derived ids (evidence: P12, strict FAIL /
   semantic PASS).
4. **Correct the uniqueness wording**: the semantic key is unique over the five declared classes with
   non-null `schedule_key`, not over all 35 rows; `comparison_date` and `schedule_key` are
   load-bearing, `event_class` and `field_name` are mutually redundant today and must both be kept
   anyway because that redundancy is what turns a misclassification into an `UNLABELLED` id.
5. **Disclose the ordering circularity** in `DEMO_QUESTIONS.md` Q05 ("independently recomputed") and in
   the `DATA-04b.json` summary ("complete, ordered, typed sequences"), using the 490-of-560 cell
   accounting above. Also state that the `UNLABELLED` fallback is a diagnostic aid and that detection
   actually rests on cardinality plus the 14 derived columns (evidence: P15/P16/P17 still fail with
   the fallback degraded).
6. **Bind QUERY-UC2** to the axis-6 shape: one copy of the label map, in the harness, never in the
   PyRel model.

Nothing here blocks DATA-04b from staying GREEN. No derivation rule exists, no silent-failure path
exists, and the numbers are right.

---

## Proposed `Review:` field for the DECISION_LOG entry

> **Review:** Independent reviewer `REVIEW-D0018` upheld the non-derivability finding with changes.
> Enumerating all 30 mnemonics refuted every candidate generating function (best fit 15 of 30) and
> produced three irreducible contradictions, the sharpest being that on 2026-08-31 under one
> `event_class` and one `field_name` the manifest maps `SYN-SK-BASE_100` to `BASE` but
> `SYN-SK-PHY_BASE_700` to `CAP-700`. The reviewer additionally proved the declared row order is not
> recoverable from any derived column: on 2026-08-31 the `EXACT_ADDITION` block orders
> `[MKT_ENTRY_714, UNPAIR_NEW]` while the `UNPAIRED_ADDITION` block orders the same two keys
> `[UNPAIR_NEW, MKT_ENTRY_714]`, and the declared `member_side` / `member_schedule_key` tiebreakers
> yield the wrong order, so no total order on any per-key attribute reproduces the manifest.
> Generator fault was refuted: `SOURCE` has no label column, `SCHEDULE_KEY_READABLE` is
> `SYN-READABLE|<key>|<publish_date>`, the four amendment objects are `MODEL_INPUT` contracts keyed on
> DV-34..37 SHA-256, and `data/SYNTHETIC_DATA_SPEC.md` never contracts a mnemonic. Seventeen live
> mutations of the Q05 oracle (missing, extra, misclassified, misattributed and mis-valued events,
> loosened label keys, and a degraded `UNLABELLED` fallback) all failed loudly; no silent pass was
> constructible, and detection was shown to rest on cardinality plus the fourteen derived columns
> rather than on the fallback string. The semantic key was proved collision-free over the five
> declared classes with non-null `schedule_key`, with `comparison_date` and `schedule_key`
> load-bearing. The reviewer required four corrections: the diagnosis is a manifest/contract conflict
> on `event_id` rather than a plain presentation column, and the D-0010/D-0011 supersession precedent
> must be recorded as considered and rejected on blast-radius and demo-legibility grounds; the claim
> that candidate/group/member ids are derived is over-stated, since their string templates, the `NN`
> ordinal rule and the `REMOVED`-before-`ADDED` `-Mk` ordering were adopted from the manifest; the
> `semantic_verdict` must stop excluding the five derived `event_id` cells; and the ordering
> circularity must be disclosed in `DEMO_QUESTIONS.md` and the DATA-04b summary, since 490 of Q05's
> 560 cells are independently recomputed but the declared row sequence is supplied, not verified.
> QUERY-UC2 must keep the label map in the shared conformance harness and out of the PyRel model.

---

## Reproduction

```
# axis 1 + axis 4 enumeration and ordering proof
.venv/bin/python /tmp/rev_d0018_derive.py

# axis 3 live mutation harness (17 cases, in-memory only, no file or object mutated)
.venv/bin/python /tmp/rev_d0018_perturb.py

# baseline
.venv/bin/python data/run_oracles.py --question Q05
```
