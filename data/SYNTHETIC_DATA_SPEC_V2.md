# Deterministic synthetic aviation data specification, version 2

## 1. Authority, status, and what this document is

This is the successor to `data/SYNTHETIC_DATA_SPEC.md` (specification version 1.0.0). It is
**specification version 2.0.0** and it is a **design proposal awaiting review**, not an accepted
input contract. Nothing in it may be generated, loaded, or published until the supersession decisions
in section 3 are accepted and recorded in `DECISION_LOG.md`.

`SEMANTIC_DECISIONS.md`, `SOURCE_CONTRACT.md` (with the section 12 additions specified here),
`ATTRIBUTE_AUTHORITY.md`, `NEO4J_RAI_MAPPING.md`, and decisions D-0003 through D-0022 remain
authoritative. Where this file can be read two ways, those authorities win.

### Why version 2 exists

`NEO4J_FIDELITY_AUDIT.md` deviation A7 measured the problem. Against the live v1 load:

| Measure | v1 live | What that means for the demo |
|---|---:|---|
| `aircraft_state` versions per aircraft | 1.005 (2 of 999 aircraft above one) | Q01 as-of reconstruction has nothing to reconstruct |
| `aircraft_status` versions per aircraft | 1.004 (2 of 999 above one) | Q02 has no spell population outside one fixture |
| Live status vocabulary | `In Service` 1,001 / `Storage` 3 / `Maintenance` 2 | Q02 and Q03 are single-valued |
| `aircraft_type` / `engine_type` versions per aircraft | 48, almost all `SYN-TYPE-FILL-NNN` daily churn | Q04 shows churn, not conversions |
| Q03 month-end series | essentially flat, two aircraft | the ten-year chart has no shape |
| `FULFILLMENT_EXACT` | 4 rows of 3,900 legs | the `FULFILLED` edge exists but is not exercised |
| `PASSENGER_FLIGHT_CANONICAL.schedule_key` non-null | 1 of 19,996 | the `SCHEDULES` edge would be empty once built |

Version 2 does not add volume. It adds **structure**: real aircraft lifecycles over a ten-year
window that is disjoint from every frozen expectation, and a second weekly schedule-knowledge block
in 2027 that is disjoint from the frozen August 2026 block. The predicted post-change measures are
in section 12.

### The one design rule that makes this safe

**Every enrichment lives in a time window and an identifier range that no frozen expected answer can
see, and it is demonstrated through additional result sets rather than by changing an existing one.**

- Aircraft enrichment is confined to `aircraft_start_of_life_date >= 2025-01-01`, so
  `Q03-CANONICAL` (2015-01-31 through 2024-12-31) cannot see it.
- Schedule enrichment is confined to snapshot dates in 2027, so `Q05-CANONICAL` (August 2026),
  `Q06-CANONICAL` (2026-08-24 versus 2026-08-31) and `Q07-MARKETING` / `Q07-OPERATING`
  (knowledge 2026-08-31, operating 2026-09-07) cannot see it.
- Passenger and actual-flight enrichment is confined to 2027 operating dates and to identifier
  blocks disjoint from every anchored identifier.

Consequence, stated up front because it is the reviewable claim: **zero of the 24 frozen result sets
and zero of the 11 frozen contract truth tables change a single expected value.** The supersession
that section 3 asks for is purely **additive**.

## 2. Reproducibility constants

| Constant | Value | Change from v1 |
|---|---|---|
| Specification version | `2.0.0` | was `1.0.0` |
| Expected-manifest version | `1.2.0` | was `1.1.1`; additive only |
| Seed | `20260901` | unchanged |
| Frozen generation date | `2026-09-01` | unchanged |
| Frozen generation timestamp | `2026-09-01T00:00:00Z` | unchanged |
| Source open/unknown-future date | `9999-12-31` | unchanged |
| Model open-interval date | `9999-01-01` | unchanged |
| Text encoding / line ending / hash | UTF-8 no BOM / LF / SHA-256 | unchanged |
| Enriched aircraft window | `2025-01-01` through `2034-12-31` | new |
| Enriched schedule knowledge window | `2027-01-04` through `2027-06-28` | new |
| Data horizon sentinel for open lifecycle | `2035-01-01` (exclusive) | new |

Every v1 determinism rule is retained verbatim: no wall clock, no locale, no hostname, no Python hash
seed, no unordered-set order, no input-file order. The counter PRF is unchanged:

```text
SHA256("20260901" || "|" || source_object || "|" || zero_padded_row_index || "|" || field_id)
```

The DV-43 `dv43-lp-v1` grammar, the physical row-ordering rules, the CSV serializer, and the
typed-row hash are all unchanged. Two clean runs of one scale MUST be byte-identical. A
reordered-input run MUST produce identical canonical rows, identifiers, expected results, and
canonical manifest hashes.

### 2.1 PRF ordinal allocation (extended)

v1 ordinals are retained exactly for every row that v1 emitted and that v2 still emits. v2 allocates
new, disjoint ordinal blocks so that no v1 row's PRF input changes:

| Source object | v1 ordinals (retained) | v2 additions |
|---|---|---|
| `AIRCRAFT_MASTER` | named `000000..000005`; filler `100000+i` | unchanged (same 993 filler aircraft, same order) |
| `AIRCRAFT_HISTORY` | named `000000..000023` | filler is re-derived: `300000 + k`, where `k` is the zero-based traversal position of ascending `(i, event_ordinal)` over the v2 event streams. The v1 `100000+k` block is retired and MUST NOT be emitted. |
| `AIRCRAFT_CONFIGURATION` | named `000000..000003` | fleet definitions `310000+f` for `f=0..12`; remaining filler `100000+i` for `i=13..1995` (ordinal preserved for the definitions v1 also emitted at that index) |
| `SCHEDULE_SNAPSHOT` | canonical `000000..000080`, V02 `000081`, DUP `000082`, diagnostics `000083..000087`, August filler `100000+5i+d`, October diagnostics `200000+i` | 2027 block `400000 + m`, where `m` is the zero-based traversal position of ascending `(cohort_rank, key_index, physical_date_index)`; `cohort_rank` is the section 9.2 table order |
| `SCHEDULE_SNAPSHOT_CALENDAR` | ten dates `000000..000009` | 26 new dates `000010..000035` in ascending date order |
| `PASSENGER_FORWARD` | named `000000..000008` | filler `300000+i` (the v1 `100000+i` block is retired) |
| `PASSENGER_HISTORICAL` | named `000000..000012` | filler `300000+i` (the v1 `100000+i` block is retired) |
| `AIRCRAFT_FLIGHT` | named `000000..000023` | filler `300000+i` (the v1 `100000+i` block is retired) |
| `AIRPORT_REFERENCE` | whitelist `000000..000008`, ambiguity `000009..000010`, filler `100000+i` | unchanged |
| `AIRLINE_REFERENCE` | sorted-union position for exact identities, ambiguity `001000..001001`, padding `100000+i` | the sorted-union position rule is retained and re-evaluated over the larger union; padding stays `100000+i` |

The v1 known-answer vector
(`20260901|SOURCE.SCHEDULE_SNAPSHOT|100000|SS-39` -> digest
`491861981a7e9e11dd9d7f5650a019f5cd99b2eff006d88f74b9b18081ded65d` -> SS-39 `9712`) is retained as a
regression assertion, because the August filler block is unchanged. A second known-answer vector for
the 2027 block MUST be computed once by the implementer and frozen into this table before the first
publishable run.

## 3. Supersession requested, and exactly what it covers

Three decisions are required, following the D-0010 / D-0011 pattern (append-only entry, independent
recomputation, rollback statement, no expected value edited to accommodate an implementation).

### D-0023 (proposed) - fleet lifecycle enrichment and additive result-set supersession

Supersede `data/SYNTHETIC_DATA_SPEC.md` 1.0.0 with this document and `EXPECTED_ANSWERS.yaml` 1.1.1
with 1.2.0. **1.2.0 adds result sets and adds nothing else.** No existing `result_set_id`, row
identifier, expected scalar, cardinality, ordering rule, parameter, closure assertion, or truth-table
row changes. The `authority.supersession` string gains one sentence naming D-0023 and stating that it
is additive.

New result sets (parameters are frozen here; expected rows are produced as described in section 3.4):

| New result set | Parameters | Purpose |
|---|---|---|
| `Q01-ENRICHED-MID-STORAGE` | `aircraft_id=1556`, `as_of_date=2031-06-30` | stored aircraft, base changed two years earlier |
| `Q01-ENRICHED-RETURN-DAY` | `aircraft_id=1860`, `as_of_date=2027-08-03` | first day back in service, half-open boundary |
| `Q01-ENRICHED-CONVERSION-DAY` | `aircraft_id=1107`, `as_of_date=2032-06-01` | type changed that day, engine did not |
| `Q01-ENRICHED-POST-EOL` | `aircraft_id=1000`, `as_of_date=2032-06-30` | existence upper bound on a filler aircraft |
| `Q02-ENRICHED-MULTI-SPELL` | `aircraft_id=1860` | three spells: 365, 3 and 180 days |
| `Q02-ENRICHED-LONG-SPELL` | `aircraft_id=1556` | one 304-day closed spell plus one still-open storage that is correctly not reported |
| `Q02-ENRICHED-SAME-DAY` | `aircraft_id=1859` | zero-day spell on a filler aircraft |
| `Q02-ENRICHED-STATUS-BUT-NO-STORAGE` | `aircraft_id=1307` | maintenance history, zero storage spells, empty result |
| `Q03-ENRICHED` | `start_month_end=2025-01-31`, `end_month_end=2034-12-31`, `status='In Service'` | 985 rows over 120 month ends, ten types, readable shape |
| `Q04-ENRICHED-ENGINE-ONLY` | `aircraft_id=1000` | re-engine with no type change |
| `Q04-ENRICHED-TYPE-ONLY` | `aircraft_id=1207` | type change with no re-engine |
| `Q04-ENRICHED-INDEPENDENT` | `aircraft_id=1107` | both dimensions change, on different dates |
| `Q04-ENRICHED-COUPLED` | `aircraft_id=1307` | both dimensions change on the same date |
| `Q05-ENRICHED` | `start_knowledge_date=2027-01-04`, `end_knowledge_date=2027-06-28`, `cadence_days=7` | 392 rows, 23 adjacent pairs, all eight event classes |
| `Q05-ENRICHED-GAP-PAIRS` | `start_knowledge_date=2027-03-08`, `end_knowledge_date=2027-04-26`, `cadence_days=7` | the two gap-crossing pairs in isolation |
| `Q06-ENRICHED-MARKETING` | `latest=2027-06-28`, `comparison=2027-06-21`, `carrier_role='marketing'` | 4 entries, 3 exits |
| `Q06-ENRICHED-OPERATING` | `latest=2027-06-28`, `comparison=2027-06-21`, `carrier_role='operating'` | 2 entries, 3 exits; roles visibly differ |
| `Q07-ENRICHED-KNOWLEDGE-LATE` | `knowledge=2027-06-28`, `operating=2027-07-05`, `role='marketing'` | baseline |
| `Q07-ENRICHED-KNOWLEDGE-EARLY` | `knowledge=2027-06-21`, `operating=2027-07-05`, `role='marketing'` | same operating date, earlier knowledge, four rows differ |
| `Q07-ENRICHED-OPERATING-SHIFT` | `knowledge=2027-06-28`, `operating=2027-07-03`, `role='marketing'` | same knowledge date, different operating date, four rows differ |
| `Q07-ENRICHED-ROLE` | `knowledge=2027-06-28`, `operating=2027-07-05`, `role='operating'` | operating role plus four `UNRESOLVED_PHYSICAL_SERVICE` rows |
| `Q08-ENRICHED-ROTATION` | `aircraft_id=<section 11.3>`, `flight_departure_date=2027-06-08` | five-leg rotation, one UTC-midnight crossing, one type discrepancy |
| `Q08-ENRICHED-ANOMALIES` | `aircraft_id=<section 11.4>`, `flight_departure_date=2027-07-06` | full anomaly set on a filler aircraft |
| `Q08-ENRICHED-CLEAN` | `aircraft_id=<section 11.3>`, `flight_departure_date=2027-06-09` | four-leg rotation with zero anomalies |

**Rollback:** delete the new result sets, restore specification 1.0.0, regenerate. The frozen 1.1.1
content is unchanged in place, so rollback cannot lose an expectation.

### D-0024 (proposed) - carry nine A4 versioned attributes

Add nine columns to `SOURCE.AIRCRAFT_HISTORY` as AH-34 through AH-42 (section 8). The contracted
column count moves from **195 to 204**. All nine join the `aircraft_state` watched set, which becomes
AH-17 through AH-31 plus AH-34 through AH-42. `SOURCE_CONTRACT.md` section 12 (`Explicit limitations
and omissions`) gains one bullet naming the A4 attributes still not carried and why.

**Hard rule that makes this safe:** for the six anchored aircraft (1001, 1002, 1004, 1005, 1098,
1099) all nine new fields are constant across every one of their 24 events. No anchored aircraft can
therefore gain a state version, and no frozen result set exposes any of the nine columns in its
output schema.

### D-0025 (proposed) - a second knowledge block in 2027

Add 26 rows to `SOURCE.SCHEDULE_SNAPSHOT_CALENDAR` for the weekly Mondays 2027-01-04 through
2027-06-28, of which 2027-03-15 is `PRESENT_INCOMPLETE` and 2027-04-19 is `MISSING_DECLARED`. The ten
v1 calendar rows keep SC-01 through SC-04 and SC-06 byte-identical, and SC-05 keeps its v1 value
because **no row is added at any v1 snapshot date**.

D-0011's assertion is preserved and extended: the only eligible complete dates inside Q05's inclusive
2026-08-03 through 2026-08-31 window remain exactly its five weekly endpoints, and the
`SYN-SK-GAP_CONTROL_001` previous-eligible-complete date remains 2026-10-05 because every new date is
after 2026-10-26.

### 3.4 How the new expected rows acquire independent authority

The frozen 1.1.1 rows were hand-specified before any generator existed. That exact procedure does not
scale to 985 Q03 rows and 392 Q05 rows, and pretending otherwise would be dishonest. The procedure for
1.2.0 additions is:

1. This document declares every cohort, presence map, transition, and date formula. The expected rows
   are a **deterministic function of this document alone**, with no reference to the generator.
2. An independent recomputation script, written against this document and **not** importing
   `data/generate_synthetic_data.py`, produces the candidate rows. The section 12 aggregate
   invariants (cardinality, distinct month ends, per-class histogram, per-pair distribution, spell
   duration buckets) are checked against the values frozen in this document first. A mismatch is a
   specification defect, resolved by fixing the specification and re-deriving, never by accepting the
   script's output.
3. Only after the aggregates match are the rows written into `EXPECTED_ANSWERS.yaml` 1.2.0, each new
   result set carrying a `result_set_sha256` so bulk review is tractable.
4. `data/run_oracles.py` then reproduces every new result set from Snowflake SQL, and the RAI query
   layer reproduces it a third time. Three independent producers, as today.

The aggregate invariants in section 12 are the reviewable core. They are the numbers to argue about.

## 4. Scale budget

| Raw source table | v1 `demo` | v2 `demo` | Delta | Driver |
|---|---:|---:|---:|---|
| `AIRCRAFT_MASTER` | 999 | 999 | 0 | same 6 anchors plus same 993 filler identities |
| `AIRCRAFT_HISTORY` | 48,000 | 30,233 | -17,767 | 48 days of fake churn replaced by 30 years-of-life events per aircraft |
| `AIRCRAFT_CONFIGURATION` | 2,000 | 2,000 | 0 | 4 anchors, 13 fleet definitions, 1,983 unreferenced filler definitions |
| `SCHEDULE_SNAPSHOT` | 70,000 | 124,636 | +54,636 | the 2027 knowledge block |
| `SCHEDULE_SNAPSHOT_CALENDAR` | 10 | 36 | +26 | 2027 weekly calendar |
| `PASSENGER_FORWARD` | 10,000 | 10,000 | 0 | same count, redesigned filler |
| `PASSENGER_HISTORICAL` | 10,000 | 10,000 | 0 | same count, redesigned filler |
| `AIRCRAFT_FLIGHT` | 3,900 | 3,900 | 0 | same count; the AF-01 range 5000..8999 holds at most 3,999 rows and is already near full |
| `AIRPORT_REFERENCE` | 45 | 45 | 0 | unchanged |
| `AIRLINE_REFERENCE` | 100 | 180 | +80 | 2027 carrier pools and market-churn carriers |
| **Total** | **145,054** | **182,029** | **+36,975** | |

Largest table 124,636 rows, well inside the 500,000 ceiling; total inside the 100,000 to 350,000 band.
`SCHEDULE_SNAPSHOT` is the only tuning knob: the 2,000-key stable core in section 9.2 is 50,000 of its
54,636 new rows and can be reduced to 1,200 keys (30,000 rows, total 162,029) with no semantic loss
beyond market-protection coverage, which then needs re-checking.

The `smoke` scale is unchanged at 249 rows and keeps every golden and negative fixture. `smoke` gains
no v2 enrichment: it exists to prove the fixtures, and the enrichment is by construction irrelevant to
them. The `demo` scale remains a strict semantic superset of `smoke`.

## 5. Identifier allocation, disjoint from every anchor

Anchored identifiers, restated so an implementer can assert against them without re-reading
`EXPECTED_ANSWERS.yaml`:

| Kind | Anchored values that must keep their exact current data |
|---|---|
| `aircraft_id` | 1001, 1002, 1004, 1005, 1098, 1099; 1003 reserved and never loaded |
| `aircraft_history_id` | 101001, 101003, 101004, 101005, 101007, 101008, 101009, 101010, 101011, 101020, 101021, 101022, 101023, 101024, 102001, 102002, 102004, 102005, 102006, 102099, 104001, 105001, 109801, 109901 |
| `aircraft_configuration_id` | 2001, 2002, 2003, 2005; 999999 deliberately absent |
| `flight_id` (AF-01) | 5101, 5102, 5103, 7101, 7102, 7199, 7200, 8001, 8002, 8003, 8101 through 8112, 8205, 8206; 8999 deliberately absent |
| `forward_source_row_id` (PF-01) | 6001, 6002, 6101, 6102, 6103, 6199 plus two null-identifier rows |
| `historical_source_row_id` (PH-01) | 5001, 5101, 5102, 5103, 7200, 7301 through 7306, 7309, 7310 |
| `schedule_key` | the 22 `SYN-SK-*` canonical keys, the five `SYN-SK-DIAG-*` / `SYN-SK-UTC-UNRESOLVED` diagnostics, `SYN-SK-HIST_700` |
| snapshot dates | 2026-08-03, 08-10, 08-17, 08-24, 08-31, 09-07, 2026-10-05, 10-12, 10-19, 10-26 |

v2 allocations:

| Range or pattern | Count | Use |
|---|---:|---|
| `aircraft_id` 1000, 1006 through 1097, 1100 through 1997, 1998, 1999 (the sorted set `1000..1999` minus 1003 minus the six anchors) | 993 | the enriched fleet; `a_i` denotes the `i`-th element, `i = 0..992` |
| `aircraft_history_id` 101000..199999 minus the 24 anchors, ascending | 30,209 used | enriched aircraft events |
| `aircraft_configuration_id` 300000..300012 | 13 | fleet type and engine definitions |
| `aircraft_configuration_id` 300013..301995 | 1,983 | unreferenced filler definitions, v1 template |
| `AVAIL` = ascending `5000..8998` minus the 24 AF anchors | 3,975 available | AF filler is `AVAIL[0:3876]`, partitioned by section 11.1 |
| PH-01 pool = ascending `5000..7999` minus the 13 PH anchors minus every AF-01 already used, plus the 700 deliberately shared fulfilment identifiers | see section 10 | passenger historical identifiers |
| PF-01 pool = ascending `5000..7999` minus the 6 non-null PF anchors minus every identifier used by PH or AF | see section 10 | passenger forward identifiers |
| `SYN-SK-W27-*` | 2,527 keys | 2027 schedule cohorts, section 9.2 |
| `SYN-MKT-W27-{00..15}`, `SYN-OP-W27-{00..15}` | 32 | 2027 carrier pools |
| `SYN-MKT-W27-ENT-{00..11}`, `SYN-MKT-W27-EXIT-{00..11}`, `SYN-OP-W27-ENT-{02..11}`, `SYN-OP-W27-EXIT-{00..11}` | 46 | market-churn carriers |
| flight numbers 1900..1999 | 100 | 2027 schedule and actual flight numbers; disjoint from the anchored 700..799 and from the v1 filler ranges 1700..1799 and 1800..1899 |
| `SYN-TYPE-NB1`, `NB2`, `NB3`, `WB1`, `WB2`, `RJ1`, `RJ2`, `FRT1` | 8 | fleet aircraft types; disjoint from `SYN-TYPE-A`, `SYN-TYPE-B`, `SYN-TYPE-MIXED` |
| `SYN-ENGINE-N1A`, `N1B`, `N2A`, `N3A`, `N3B`, `W1A`, `W1B`, `W2A`, `R1A`, `R2A`, `F1A` | 11 | fleet engine types; disjoint from `SYN-ENGINE-A`, `-B`, `-MIXED-REPORTED` |

Every v2 identifier is visibly synthetic and inside a declared range. No v2 row uses an anchored
numeric identifier, an anchored schedule key, an anchored snapshot date, or an anchored flight number.

## 6. Fleet type and engine catalogue

`AIRCRAFT_CONFIGURATION` rows 2001, 2002, 2003 and 2005 are byte-identical to v1. Thirteen new fleet
definitions replace the first thirteen v1 filler definitions:

| AC-01 | AC-05 type | AC-03 type label | AC-07 class | AC-08 engines | AC-14 engine | AC-12 engine label |
|---:|---|---|---|---:|---|---|
| 300000 | `SYN-TYPE-NB1` | `Synthetic narrowbody generation 1` | `SYN-CLASS-NB` | 2 | `SYN-ENGINE-N1A` | `Synthetic turbofan N1A` |
| 300001 | `SYN-TYPE-NB1` | `Synthetic narrowbody generation 1` | `SYN-CLASS-NB` | 2 | `SYN-ENGINE-N1B` | `Synthetic turbofan N1B` |
| 300002 | `SYN-TYPE-NB2` | `Synthetic narrowbody generation 2` | `SYN-CLASS-NB` | 2 | `SYN-ENGINE-N1A` | `Synthetic turbofan N1A` |
| 300003 | `SYN-TYPE-NB2` | `Synthetic narrowbody generation 2` | `SYN-CLASS-NB` | 2 | `SYN-ENGINE-N2A` | `Synthetic turbofan N2A` |
| 300004 | `SYN-TYPE-NB3` | `Synthetic narrowbody generation 3` | `SYN-CLASS-NB` | 2 | `SYN-ENGINE-N3A` | `Synthetic turbofan N3A` |
| 300005 | `SYN-TYPE-NB3` | `Synthetic narrowbody generation 3` | `SYN-CLASS-NB` | 2 | `SYN-ENGINE-N3B` | `Synthetic turbofan N3B` |
| 300006 | `SYN-TYPE-WB1` | `Synthetic widebody generation 1` | `SYN-CLASS-WB` | 2 | `SYN-ENGINE-W1A` | `Synthetic turbofan W1A` |
| 300007 | `SYN-TYPE-WB1` | `Synthetic widebody generation 1` | `SYN-CLASS-WB` | 2 | `SYN-ENGINE-W1B` | `Synthetic turbofan W1B` |
| 300008 | `SYN-TYPE-WB2` | `Synthetic widebody generation 2` | `SYN-CLASS-WB` | 4 | `SYN-ENGINE-W2A` | `Synthetic turbofan W2A` |
| 300009 | `SYN-TYPE-RJ1` | `Synthetic regional jet generation 1` | `SYN-CLASS-RJ` | 2 | `SYN-ENGINE-R1A` | `Synthetic turbofan R1A` |
| 300010 | `SYN-TYPE-RJ2` | `Synthetic regional jet generation 2` | `SYN-CLASS-RJ` | 2 | `SYN-ENGINE-R2A` | `Synthetic turbofan R2A` |
| 300011 | `SYN-TYPE-FRT1` | `Synthetic freighter generation 1` | `SYN-CLASS-FRT` | 2 | `SYN-ENGINE-F1A` | `Synthetic turbofan F1A` |
| 300012 | `SYN-TYPE-NB2` | `Synthetic narrowbody generation 2` | `SYN-CLASS-NB` | 2 | `SYN-ENGINE-N1B` | `Synthetic turbofan N1B` |

For all thirteen: AC-02 is `SYN-FAMILY-` plus the type suffix, AC-04 is `SYN-SERIES-` plus the type
suffix, AC-06 is `SYN-MFR-NB` / `-WB` / `-RJ` / `-FRT` by class, AC-09 is `false`, AC-10 is
`SYN-ENG-MFR-` plus the engine suffix, AC-11 is `SYN-ENG-FAM-` plus the engine suffix, AC-13 is
`SYN-ENG-SER-` plus the engine suffix, AC-15 is `TURBOFAN`, and AC-16 is `2026-08-31`.

Note 300012: `NB2` with engine `N1B`. It exists so that an aircraft that has already re-engined can
later change type **without** changing engine. Without it the "both dimensions, independent dates"
case in section 7.4 is not constructible.

Definitions 300013 through 301995 use the v1 filler template unchanged with index `i = AC-01 -
300000`, and are **not referenced by any event**. That is deliberate: a definition table normally
contains more definitions than a fleet uses. The v1 assertion "every configuration resolves" is
restated in section 12 as "every configuration **referenced by an event** resolves".

## 7. Enriched aircraft population

### 7.1 Master rows

The six anchored `AIRCRAFT_MASTER` rows are byte-identical to v1. The 993 filler rows keep their
identifiers and the v1 full template, with these overrides driven by cohort (section 7.2):

- AM-07 `aircraft_start_of_life_date` = `service_start(i)`, always `>= 2025-01-01`.
- AM-08 `aircraft_end_of_life_date` = `eol(i)` or null.
- AM-04 = `max(2025-01-01, service_start - 540 days)`;
  AM-05 = `max(2025-01-01, service_start - 120 days)`;
  AM-06 = `max(2025-01-01, service_start - 30 days)`;
  AM-16 = `max(2025-01-01, service_start - 100 days)`;
  AM-17 = `max(2025-01-01, service_start - 60 days)`.
  For the cohorts whose `service_start` is 2025-01-01 all five collapse to 2025-01-01. That compresses
  order-to-delivery to a single day for those 700 aircraft. It is a **declared synthetic artifact**,
  accepted because keeping every filler master date at or after 2025-01-01 is what makes
  `Q03-CANONICAL` structurally unreachable rather than merely arithmetically unreached.
- AM-09 = whitelist entry `i mod 9`; AM-18 = `Synthetic build label {AM-09}`.
- AM-10 through AM-15 and AM-19 keep the v1 template. AM-11 through AM-14 remain `CURRENT_ONLY`.

### 7.2 Cohorts

`a_i` is the `i`-th of the 993 sorted filler aircraft identifiers. Eight contiguous cohorts:

| Cohort | `i` range | n | Base config | `service_start(i)` | `eol(i)` |
|---|---|---:|---:|---|---|
| C1 `FOUNDING_NB1` | 0..299 | 300 | 300000 | `2025-01-01` | `2032-01-05 + 7i` days for `i < 100`, else null |
| C2 `LEGACY_RJ1` | 300..449 | 150 | 300009 | `2025-01-01` | `2028-01-03 + 7(i-300)` days |
| C3 `MIDLIFE_WB1` | 450..549 | 100 | 300006 | `2025-01-01` | null |
| C4 `RENEWAL_NB3` | 550..749 | 200 | 300004 | `2028-01-03 + 9(i-550)` days | null |
| C5 `RENEWAL_WB2` | 750..799 | 50 | 300008 | `2030-01-07 + 21(i-750)` days | null |
| C6 `FREIGHT_FRT1` | 800..849 | 50 | 300011 | `2025-01-01` | null |
| C7 `CHURN_NB2` | 850..959 | 110 | 300002 | `2026-01-05 + 7(i-850)` days | null |
| C8 `SHORT_LIFE_RJ2` | 960..992 | 33 | 300010 | `2025-07-01` | `2027-07-05 + 14(i-960)` days |

`service_end(i)` is `eol(i)` if set, otherwise the data horizon `2035-01-01`. No event is emitted at
or after `service_end(i)`.

Each cohort carries a narrative beat:

- **C1** is the incumbent narrowbody fleet. It re-engines, partly converts to NB2, and 100 of its 300
  aircraft retire between 2032-01-05 and 2033-11-29. That is the retirement wave.
- **C2** is a regional-jet type that leaves the fleet entirely: 50 of its 150 aircraft convert to RJ2
  and all 150 originals are retired by 2030-11-12. The RJ1 line in Q03 reaches zero.
- **C3** is the mid-life widebody fleet that goes through a long grounding: two storage spells each,
  the second running 200 to 1,091 days. The WB1 line in Q03 dips from 100 to 34 and recovers.
- **C4** is the renewal type entering service from 2028 and reaching 200 aircraft. Its line crosses
  C2's declining line, which is the visual centrepiece of the ten-year chart.
- **C5** is a small widebody renewal, entering from 2030.
- **C6** is the deliberate flat control. Fifty freighters, no events after entry. If a query shows this
  line moving, the query is wrong.
- **C7** is the operationally noisy cohort: 0 to 3 storage spells each, plus maintenance. It supplies
  most of the Q02 duration spread including the zero-day spells.
- **C8** is a short-lived type that appears in 2025 and is gone by 2028, so Q03 shows a type that both
  enters and leaves inside the window.

### 7.3 Lifecycle events per cohort

All dates are computed with calendar-day arithmetic. `j` is the zero-based index within the cohort.

**C1**, `i = 0..299`:
- `E0` at `2025-01-01`, status `In Service`, config 300000.
- If `i mod 5 == 0` (60 aircraft), with `k = i div 5`: storage at `2026-03-02 + 7k`, duration
  `30 + 17(k mod 11)` days, return to `In Service` at storage start plus duration.
- If `i < 150`: engine change to config 300001 at `2028-03-01 + 5i`.
- If `100 <= i < 150`: type change to config 300012 at `2032-06-01 + 10(i-100)`. Engine stays N1B.
- If `200 <= i < 300`: type change to config 300002 at `2030-06-03 + 15(i-200)`. Engine stays N1A.
- If `i mod 7 == 3`: base airport changes at `2029-05-01` to whitelist entry `(i+4) mod 9`, with AH-24
  and AH-26 updated to match.
- If `i mod 11 == 5`: registration changes at `2031-02-03` from `SYN-REG-{a_i}` to `SYN-REG-{a_i}-R2`.

**C2**, `i = 300..449`, `j = i-300`:
- `E0` at `2025-01-01`, config 300009.
- Maintenance at `2026-02-02 + 5j`, return to `In Service` 21 days later.
- If `j mod 3 == 0` (50 aircraft): type and engine change together to config 300010 at
  `2027-01-04 + 9(j div 3)`. This is the **coupled** change: both dimensions mint a version on the
  same date, which is the contrast case for Q04.

**C3**, `i = 450..549`, `j = i-450`:
- `E0` at `2025-01-01`, config 300006.
- Spell 1: storage at `2025-09-01 + 3j`, duration `7 + 3j` days, return at start plus duration.
- Spell 2: storage at `2028-07-03 + 9j`, duration `200 + 9j` days, return at start plus duration.
- If `j mod 2 == 0`: engine change to config 300007 at `2031-03-03`. For some aircraft this date falls
  inside spell 2, so the engine changes while the aircraft is stored. That is intentional and correct:
  the dimensions are independent.

**C4**, `i = 550..749`, `j = i-550`:
- `E0` at `service_start(i)`, config 300004.
- If `j mod 3 == 0`: engine change to config 300005 at `service_start + 1095` days.
- If `j mod 4 == 1`: maintenance at `service_start + 500` days, return 18 days later.

**C5**, `i = 750..799`: `E0` at `service_start(i)`, config 300008. No further lifecycle events.

**C6**, `i = 800..849`: `E0` at `2025-01-01`, config 300011. No further lifecycle events.

**C7**, `i = 850..959`, `j = i-850`:
- `E0` at `service_start(i)`, config 300002.
- Spell count is `j mod 4`, so 27 aircraft have none, 28 have one, 27 have two and 28 have three.
- Spell `s` (`1`-based): storage at `service_start + 150 + 500(s-1) + 13(j mod 25)` days, duration
  `DUR[(7j + 13s) mod 9]` where `DUR = [0, 1, 3, 14, 45, 90, 180, 365, 450]`, return at start plus
  duration. Spacing 500 exceeds the maximum duration 450, so spells never overlap.
- Duration 0 means the storage and the return share one date. They are then two observations on the
  same day with `row_sequence_number` 20 and 30, exactly mirroring the anchored 101010 / 101011 pair.
- If `j mod 3 == 0`: maintenance at `service_start + 90` days, return 12 days later.

**C8**, `i = 960..992`, `j = i-960`:
- `E0` at `2025-07-01`, config 300010.
- If `j mod 2 == 0`: storage at `2026-03-02 + 30j`, duration 60 days, return at start plus duration.

### 7.4 Periodic state observations

For each filler aircraft, for each date `d` in `{Jan 1, Apr 1, Jul 1, Oct 1}` of the years 2025
through 2034 with `service_start(i) < d < service_end(i)` and `d` not already the date of a lifecycle
event for that aircraft, emit one observation. It carries forward the entire prior state payload,
with AH-08 `start_event` = `SYN-OBSERVATION` and AH-12 `event_source` =
`SYNTHETIC_PERIODIC`. Let `p` be the zero-based index of the observation within that aircraft's
periodic sequence. If `p mod 4 == 3`, revise AH-41 `maximum_landing_weight_lb` by `+250` and AH-42
`operating_empty_weight_lb` by `+150` relative to the carried-forward values; otherwise change
nothing.

This is the deliberate mix the ontology needs: roughly three quarters of periodic observations are
watched-value-identical and must be suppressed by consecutive-equality, and one quarter mints a real
`aircraft_state` version. It exercises the suppression rule at population scale rather than through
five hand-placed fixture rows, and it is why the state dimension reaches 8.57 versions per aircraft.

### 7.5 Event ordering, identifiers, and carry-forward

- Events for one aircraft on one date are ordered `E0` (0), storage or maintenance (1), return (2),
  type or engine change (3), base or registration change (4), periodic (5), and receive
  `row_sequence_number` 10, 20, 30 in that order. AH-04 `event_sequence_number` equals AH-03.
- The `(aircraft_id, start_event_date, row_sequence_number)` tuple is unique for every event.
- AH-01 is drawn from ascending `101000..199999` excluding the 24 anchors, traversing `(i,
  event_ordinal)` in ascending order. 30,209 identifiers are consumed.
- Every event is a **complete source snapshot**. Fields not named by the event carry forward from the
  immediately preceding event for that aircraft, never from the global template. AH-08 and AH-12 are
  row-local and do not carry forward.
- AH-06 `end_event_date` is null for every filler event. Only anchored 102099 carries the
  `9999-12-31` source sentinel, which keeps `TT-SENTINELS` scoped as written.
- AH-07 `is_current` is false for every filler event. AH-32 `not_for_use` is false. AH-33
  `publish_date` is `2026-08-31`.
- Status vocabulary stays exactly `In Service`, `Storage`, `Maintenance`. No fourth value is invented.
  `AircraftStatus` is minted from observed values, and inventing a status the customer's document does
  not evidence would be a fidelity regression dressed up as richness. Retirement is expressed by AM-08,
  which is what D-0003 already decided.

### 7.6 Resulting event count

| Cohort | AH rows |
|---|---:|
| C1 | 11,722 |
| C2 | 3,083 |
| C3 | 4,445 |
| C4 | 3,884 |
| C5 | 739 |
| C6 | 2,000 |
| C7 | 3,943 |
| C8 | 393 |
| filler total | **30,209** |
| anchors | 24 |
| **table total** | **30,233** |

## 8. Deviation A4: the nine versioned attributes to carry

`AIRCRAFT_HISTORY` gains AH-34 through AH-42. Every one is nullable in the contract sense used by the
rest of the table (the column is `NOT NULL` in DDL only where the data is never null; see the
nullability column), every one joins the `aircraft_state` watched set, and every one is populated on
every event as part of the complete-snapshot rule.

| Field | Column | Type | Null | Watched | Populated |
|---|---|---|---|---|---|
| AH-34 | `base_state` | VARCHAR | no | yes | synthetic state token derived from the base airport: SFO and LAX -> `SYN-ST-CA`, LAS -> `SYN-ST-NV`, SEA -> `SYN-ST-WA`, DEN -> `SYN-ST-CO`, ORD -> `SYN-ST-IL`, PHX -> `SYN-ST-AZ`, BOS -> `SYN-ST-MA`, MIA -> `SYN-ST-FL` |
| AH-35 | `base_region` | VARCHAR | no | yes | `SYN-RGN-WEST` (SFO, LAX, LAS, SEA, PHX), `SYN-RGN-MOUNTAIN` (DEN), `SYN-RGN-CENTRAL` (ORD), `SYN-RGN-EAST` (BOS, MIA) |
| AH-36 | `storage_location_type` | VARCHAR | yes | yes | null unless the event's status is `Storage`; then `SYN-STG-LONG-TERM` when the spell duration is at least 180 days, `SYN-STG-SHORT-TERM` when 1 to 179 days, `SYN-STG-SAME-DAY` when 0 days |
| AH-37 | `noise_certification` | VARCHAR | no | yes | derived from the resolved engine: `SYN-NOISE-CH3` for N1A, R1A, W1A, F1A; `SYN-NOISE-CH4` for N1B, N2A, R2A, W1B; `SYN-NOISE-CH14` for N3A, N3B, W2A. So a re-engine changes it, which is the point. |
| AH-38 | `has_winglets` | BOOLEAN | no | yes | false at `E0` for C1, C2, C3, C6, C8; true at `E0` for C4, C5, C7. For C1 aircraft with `i mod 5 == 2` it flips to true on the engine-change date; for C3 aircraft with `j mod 3 == 1` it flips to true at `2030-04-01`. |
| AH-39 | `aircraft_registration_country` | VARCHAR | no | yes | `Synthetic United States` for every row, and it changes to `Synthetic United States (reregistered)` on the registration-change date for the C1 aircraft with `i mod 11 == 5`. Demonstrates that two representations of one fact version together with AH-19. |
| AH-40 | `transponder_miscode` | BOOLEAN | no | yes | false except for the C7 aircraft with `j mod 17 == 4` (6 aircraft), where it is true from `E0` until the first periodic observation on or after `service_start + 400` days, then false. A data-quality flag with a correction event. |
| AH-41 | `maximum_landing_weight_lb` | NUMBER(38,0) | no | yes | `142000` for NB types, `210000` for WB types, `84000` for RJ types, `146000` for FRT, plus the section 7.4 periodic revisions |
| AH-42 | `operating_empty_weight_lb` | NUMBER(38,0) | no | yes | `92000` NB, `138000` WB, `52000` RJ, `88000` FRT, plus the section 7.4 periodic revisions |

For the six anchored aircraft every one of the nine is a constant across all 24 anchored events:
AH-34 = `SYN-ST-CA`, AH-35 = `SYN-RGN-WEST`, AH-36 = null, AH-37 = `SYN-NOISE-CH3`, AH-38 = false,
AH-39 = `Synthetic United States`, AH-40 = false, AH-41 = `142000`, AH-42 = `92000`. Constant payload
cannot mint a version, and none of the nine appears in any frozen output schema, so no anchored result
can move.

### 8.1 What is deliberately not carried, and why

Honest accounting against the A4 list. These are **not** added:

| Attribute | Reason |
|---|---|
| `aircraft_length_m`, `aircraft_height_m` | Physically immutable. They would be constant columns on a versioned stream and no golden question groups, filters or aggregates on them. Adding them would make the payload wider and the demo no more capable. |
| `maximum_zero_fuel_weight_lb`, `maximum_payload_lb` | Two weights already carry the "state row was republished because a weight was revised" story (AH-41, AH-42). Two more are the same story with more columns. |
| `winglet_modifier`, `aircraft_minor_variant`, `aircraft_modifiers` | Free-text modifier strings. No query can do anything with them beyond displaying them, and `has_winglets` already gives the versioned-boolean case. |
| `aircraft_registration_region` name form beyond AH-20 | AH-20 already exists and is watched. |
| Master-side `apu_family`, `apu_type_subseries`, `apu_manufacturer`, `maximum_cargo_volume_cu_ft`, `maximum_fuel_capacity_gal`, `is_accidents_only`, `aircraft_type_id` | All immutable master facts. D-0005 already decided the master/versioned split, and `Aircraft.master_current_only_*` already demonstrates the `CURRENT_ONLY` prohibition. Adding seven more immutable columns does not change what any query can express. |

After D-0024 the count is roughly 29 of the customer's 38 versioned attributes rather than 20. The
remaining nine are named above with a reason, which is a defensible position on stage. Claiming
parity would not be.

`SOURCE_CONTRACT.md` section 12 gains: "Nine of the customer's versioned `AIRCRAFT_STATE` attributes
are still not carried: two physical dimensions, two non-MTOW weights, three free-text modifier
strings, and two master-side descriptors. Each is immutable or non-queryable in the bounded workload;
the omission is scope, not capability."

## 9. Enriched schedule population

### 9.1 The 2027 snapshot calendar

Twenty-six new `SCHEDULE_SNAPSHOT_CALENDAR` rows. `w_k = 2027-01-04 + 7k` for `k = 0..25`.

| SC-01 | SC-02 `is_present` | SC-03 `is_complete` | SC-04 | SC-06 |
|---|---|---|---|---|
| `w_k` for `k` not in {10, 15} (24 rows) | true | true | `SC-{YYYYMMDD}-COMPLETE` | `COMPLETE_VALIDATED` |
| `w_10 = 2027-03-15` | true | false | `SC-20270315-INCOMPLETE` | `INCOMPLETE_RETAINED` |
| `w_15 = 2027-04-19` | false | false | `SC-20270419-MISSING` | `MISSING_DECLARED` |

SC-05 is the exact realized raw row count for that date: 2,301 at `w_10`, 0 at `w_15`, and the
per-date total from section 9.2 elsewhere.

There are therefore **24 eligible complete dates** and **23 adjacent eligible pairs**. Let `E` be the
24 eligible dates in ascending order and let pair `p` (`p = 1..23`) be `(E[p-1], E[p])`. Pair 10 is
`(2027-03-08, 2027-03-22)` and crosses the incomplete date; pair 14 is `(2027-04-12, 2027-04-26)` and
crosses the missing date. Both must report `crosses_snapshot_gap = true`, and neither ineligible date
may derive a single boundary, addition, removal, reappearance or market event.

The ten v1 calendar rows are byte-identical including SC-05, because **no v2 row is emitted at any v1
snapshot date**.

### 9.2 The 2027 schedule cohorts

Common defaults for every 2027 key, before per-cohort overrides: SS-02 =
`SYN-READABLE|{SS-01}|{SS-03}`; SS-07 = `J`; SS-08 = `2027-08-01`; SS-09 = `2027-12-31`; SS-12 =
`SYN-T-W27-A`; SS-13 = `SYN-T-W27-B`; SS-14 through SS-20 all true; SS-21 = `1234567`; SS-22 = 7;
SS-23 = `16:00:00`; SS-24 = `18:00:00`; SS-25 = `09:00:00`; SS-26 = `11:00:00`; SS-27 = 0; SS-28 =
120; SS-29 = `SYN-EQ-NB`; SS-30 = 180.0; SS-31 = 8.0; SS-32 = 20.0; SS-33 = 20.0; SS-34 = 152.0;
SS-35 = false; SS-36 = null; SS-37 = 0; SS-38 = null. SS-39 is the ordinary PRF rule
`9000 + (first two digest bytes as unsigned big-endian modulo 1000)`. SS-40 is DV-43 over the typed
SS-01 through SS-39 serialization, computed after all overrides.

The operating window `2027-08-01` through `2027-12-31` is load-bearing: it makes every cohort except
`CAP` and `CLK` **operating-ineligible** on the Q07 operating dates 2027-07-03 and 2027-07-05, which
is what keeps `Q07-ENRICHED-*` down to about 30 rows instead of thousands.

Route set: the 72 ordered pairs of distinct whitelist airports, `ROUTE[r]` for `r = 0..71` in
ascending `(origin index, destination index)` order. Carrier pools:
`P_MKT[c] = SYN-MKT-W27-{c:02}` and `P_OP[c] = SYN-OP-W27-{c:02}` for `c = 0..15`.
Flight numbers `SS-06 = 1900 + (key_index mod 100)`.

| Rank | Cohort | Keys | Presence | Rows |
|---:|---|---|---|---:|
| 1 | `SYN-SK-W27-CORE-{00000..01999}` | 2,000 | all 25 physical dates (24 eligible plus `w_10`) | 50,000 |
| 2 | `SYN-SK-W27-MOD-{000..068}` | 69 | all 25 physical dates | 1,725 |
| 3 | `SYN-SK-W27-ADD-{000..022}` | 23 | `E[p..23]` where `p = index + 1` | 276 |
| 4 | `SYN-SK-W27-REM-{000..022}` | 23 | `E[0..p-1]` where `p = index + 1` | 276 |
| 5 | `SYN-SK-W27-SHIFTOLD-{000..022}` | 23 | `E[0..p-1]`, `p = index + 1` | 276 |
| 6 | `SYN-SK-W27-SHIFTNEW-{000..022}` | 23 | `E[p..23]`, `p = index + 1` | 276 |
| 7 | `SYN-SK-W27-AMBOLD-{00..05}` | 6 | `E[0..p-1]`, `p = 2g + 1` | 36 |
| 8 | `SYN-SK-W27-AMBNEWA-{00..05}`, `SYN-SK-W27-AMBNEWB-{00..05}` | 12 | `E[p..23]`, `p = 2g + 1` | 216 |
| 9 | `SYN-SK-W27-UNPOLD-{00..05}` | 6 | `E[0..p-1]`, `p = u + 2` | 27 |
| 10 | `SYN-SK-W27-UNPNEW-{00..05}` | 6 | `E[p+8..23]`, `p = u + 2` | 69 |
| 11 | `SYN-SK-W27-REAP-{000..007}` | 8 | `E[0..p-1]` and `E[p+1..23]`, `p = 2r + 2` | 184 |
| 12 | `SYN-SK-W27-MKTENT-{00..11}` | 12 | `E[p..23]`; `p = 23` for `m = 0..3`, `p = 2(m-4) + 3` for `m = 4..11` | 116 |
| 13 | `SYN-SK-W27-MKTEXIT-{00..11}` | 12 | `E[0..p-1]`; `p = 23` for `m = 0..2`, `p = 2(m-3) + 2` for `m = 3..11` | 159 |
| 14 | `SYN-SK-W27-CLK-{00..03}` | 4 | `E[0..22]` plus `w_10` | 96 |
| 15 | `SYN-SK-W27-CLK-{04..07}` | 4 | `E[23]` only | 4 |
| 16 | `SYN-SK-W27-CLK-{08..11}` | 4 | all 25 physical dates | 100 |
| 17 | `SYN-SK-W27-CAP-{000..023}` | 24 | all 25 physical dates | 600 |
| 18 | `SYN-SK-W27-INERT-{000..199}` | 200 | `w_10` only | 200 |
| | **total** | **2,527** | | **54,636** |

Per-cohort overrides:

- **CORE** `j = 0..1999`: SS-04 = `P_MKT[j mod 16]`, SS-05 = `P_OP[j mod 16]`, SS-10 and SS-11 from
  `ROUTE[(j div 16) mod 72]`. The 2,000 keys therefore cover all 1,152 `(pool carrier, route)` markets
  with one or two always-present keys each. Content is byte-identical across all 25 dates, so CORE
  contributes zero Q05 events and provides the **market protection** every other cohort relies on.
- **MOD** `j = 0..68`: same carrier and route assignment rule as CORE, taken from
  `ROUTE[(j div 16) mod 72]`. Change pair `p = (j div 3) + 1`, so each of the 23 pairs receives
  exactly three modifications. Changed field is `F[j mod 10]` where `F` is
  `[SS-30 total_seats, SS-22 weekly_frequency, SS-12 departure_terminal, SS-13 arrival_terminal,
  SS-32 business_class_seats, SS-33 premium_economy_seats, SS-28 scheduled_block_minutes,
  SS-29 equipment_subtype_code_iata, SS-35 is_codeshare, SS-07 service_type_iata]`. New values:
  numeric fields gain `+6` (seats), `+1` (frequency), `+15` (block minutes); terminals move to
  `SYN-T-W27-A2` / `SYN-T-W27-B2`; equipment becomes `SYN-EQ-WB`; `is_codeshare` becomes true with
  SS-36 = `P_MKT[(j+1) mod 16]`; service type becomes `F`. Every key changes at exactly one pair and
  is otherwise stable.
- **ADD / REM**: carriers and routes from the pool as for CORE. Nothing changes content-wise; the
  event is presence alone.
- **SHIFTOLD / SHIFTNEW** index `q = 0..22`: both keys share SS-04 = `P_MKT[q mod 16]`, SS-06 =
  `1900 + q`, SS-10 and SS-11 from `ROUTE[q]`. The old key has SS-08 = `2027-08-01`, SS-09 =
  `2027-10-31`; the new key has SS-08 = `2027-11-01`, SS-09 = `2027-12-31`, so the operating ranges
  are contiguous and non-overlapping. Exactly one added key carries this signature at pair `p`, so the
  classification is `CANDIDATE_UNIQUE` and both presence rows are consumed by it.
- **AMBOLD / AMBNEWA / AMBNEWB** group `g = 0..5`: all three keys share SS-04 =
  `P_MKT[(g + 8) mod 16]`, SS-06 = `1950 + g`, and `ROUTE[60 + g]`. The two added keys have different
  but overlapping operating ranges (`2027-11-01..2027-12-31` and `2027-11-08..2028-01-07`), so two
  candidates exist and the group is `AMBIGUOUS_CANDIDATE_GROUP` with three members.
- **UNPOLD / UNPNEW** index `u = 0..5`: share SS-04 = `P_MKT[(u + 4) mod 16]`, SS-06 = `1980 + u`,
  `ROUTE[40 + u]`. The removal is at pair `u + 2` and the addition at pair `u + 10`, so they are never
  in the same comparison and cannot pair. Both sides are `UNPAIRED`.
- **REAP** index `r = 0..7`: pool carrier and route. Absent at exactly `E[2r + 2]`, present at every
  other eligible date. Produces a removal at pair `2r + 2` and an addition at pair `2r + 3`, each with
  its own unpaired evidence, mirroring the anchored `SYN-SK-REAPPEAR_400` behaviour.
- **MKTENT** `m = 0..11`: SS-04 = `SYN-MKT-W27-ENT-{m:02}`, a carrier used by nothing else, so its
  `(carrier, route)` market has no other key at any date and its appearance is a genuine market entry.
  SS-05 = `P_OP[m mod 16]` for `m = 0..1` (whose operating market is therefore protected by CORE and
  does **not** enter) and `SYN-OP-W27-ENT-{m:02}` for `m = 2..11`. Routes `ROUTE[m]`.
- **MKTEXIT** `m = 0..11`: SS-04 = `SYN-MKT-W27-EXIT-{m:02}`, SS-05 =
  `SYN-OP-W27-EXIT-{m:02}`, routes `ROUTE[20 + m]`. Both roles exit.
- **CLK 00..03**: SS-04 = `P_MKT[c]` and SS-05 = `P_OP[c]` for `c = 0..3`, routes `ROUTE[8 + c]`,
  SS-08 = `2027-07-01`, SS-09 = `2027-07-31`, all weekdays true. Known through 2027-06-21 and absent
  from 2027-06-28. Markets are pool markets, hence CORE-protected, so they produce no Q06 event.
- **CLK 04..07**: same construction with `c = 4..7` and routes `ROUTE[12 + c]`, present only at
  2027-06-28.
- **CLK 08..09**: SS-08 = `2027-06-01`, SS-09 = `2027-07-04`, all weekdays true. Operating on
  2027-07-03 and not on 2027-07-05.
- **CLK 10..11**: SS-08 = `2027-07-01`, SS-09 = `2027-07-31`, SS-14 true and SS-15 through SS-20
  false, SS-21 = `1000000`, SS-22 = 1. 2027-07-05 is a Monday and 2027-07-03 is a Saturday, so these
  operate on 07-05 and not on 07-03.
- **CAP** `n = 0..23`: eight routes `ROUTE[n mod 8]` times three carriers. SS-08 = `2027-07-01`,
  SS-09 = `2027-07-31`, all weekdays true. For `n div 8 == 0` and `== 1`: SS-04 = `P_MKT[n mod 8]`,
  SS-05 = `P_OP[n mod 8]`, SS-35 false, and physical capacity varies by `n` (SS-22 in `{2, 3, 5, 7,
  10, 14}` by `n mod 6`; SS-30 in `{100.0, 180.0, 240.0, 320.0}` by `n mod 4` with SS-31 through SS-34
  reconciling exactly). For `n div 8 == 2`: SS-35 true, SS-36 = `P_MKT[(n + 4) mod 16]`, and the
  operating carrier is a codeshare-only marketing identity with no physical service, which reproduces
  `UNRESOLVED_PHYSICAL_SERVICE` on the operating clock for four of the eight routes.
  Additionally, keys `CAP-020`, `CAP-021`, `CAP-022` carry one cabin-quality defect each
  (total mismatch, null cabin, premium exceeds economy) so `cabin_quality` is not uniformly
  `RECONCILED` in the enriched answer.
- **INERT** `n = 0..199`: pool carriers `P_MKT[n mod 16]` / `P_OP[n mod 16]`, routes
  `ROUTE[n mod 72]`, SS-06 = `1900 + (n mod 100)`. Present only at the incomplete date. They must
  produce zero canonical observations, zero segments, and zero events.

Only CORE, MOD, CLK 00..03, CLK 08..11, CAP and INERT are emitted at the incomplete date `w_10`,
giving SC-05 = `2000 + 69 + 4 + 4 + 24 + 200 = 2301` there. Restricting the churn cohorts to eligible
dates keeps the presence logic single-branch and makes "physically retained, semantically inert"
provable by row count.

### 9.3 Q05-ENRICHED shape

392 rows over 23 adjacent pairs. Class histogram, which is the primary frozen invariant:

| Event class | Rows |
|---|---:|
| `EXACT_KEY_PRESERVING_MODIFICATION` | 69 |
| `EXACT_ADDITION` | 88 |
| `EXACT_REMOVAL` | 82 |
| `CANDIDATE_UNIQUE` | 23 |
| `AMBIGUOUS_CANDIDATE_GROUP` | 6 |
| `AMBIGUOUS_GROUP_MEMBER` | 18 |
| `UNPAIRED_ADDITION` | 53 |
| `UNPAIRED_REMOVAL` | 53 |
| **total** | **392** |

Per-pair row counts, ascending by pair index 1 through 23:
`17, 16, 23, 16, 23, 16, 23, 14, 21, 16, 23, 16, 16, 16, 16, 14, 14, 12, 10, 10, 10, 10, 40`.
Pairs 10 and 14 carry 16 rows each and both have `crosses_snapshot_gap = true`. Pair 23 carries 40
rows because the market-churn and clock cohorts are concentrated at the final comparison, which is
also the pair the Q06 and Q07 enriched invocations use.

The exact-presence partner closure rule from v1.1 is preserved and must hold over all 392 rows: every
`EXACT_ADDITION` or `EXACT_REMOVAL` not consumed by exactly one unique candidate or one ambiguous
group has exactly one unpaired evidence row with matching comparison date, side and schedule key, and
no exact presence row is both partnered and unpaired. Arithmetic check:
`88 + 82 = 170` exact presence rows; `23` unique candidates consume `46`; `6` ambiguous groups consume
`18`; the remaining `106` map one-to-one onto `53 + 53 = 106` unpaired rows.

### 9.4 Q06-ENRICHED shape

At `latest = 2027-06-28`, `comparison = 2027-06-21`:

- marketing: 4 `ENTRY` (`SYN-MKT-W27-ENT-00` through `-03` on `ROUTE[0..3]`) and 3 `EXIT`
  (`SYN-MKT-W27-EXIT-00` through `-02` on `ROUTE[20..22]`), 7 rows.
- operating: 2 `ENTRY` (`SYN-OP-W27-ENT-02`, `-03`) and 3 `EXIT`
  (`SYN-OP-W27-EXIT-00` through `-02`), 5 rows.

The marketing and operating answers differ by exactly two rows, and the reason is a modelled fact
rather than a coincidence: `MKTENT-00` and `MKTENT-01` are marketed by a new carrier but operated by
an incumbent that already serves the route. That is the "marketing and operating are separate roles"
beat with data behind it.

Additional entries and exits are distributed over pairs 2 through 18 so a fleet-wide narration over
all 23 pairs shows churn every week rather than only at the endpoint.

### 9.5 Q07-ENRICHED shape

Four invocations, all on the same underlying keys, differing only in which clock moves:

| Result set | knowledge | operating | role | Contributing keys | Rows |
|---|---|---|---|---|---:|
| `Q07-ENRICHED-KNOWLEDGE-LATE` | 2027-06-28 | 2027-07-05 | marketing | CAP 24, CLK 04..07, CLK 10..11 | 30 |
| `Q07-ENRICHED-KNOWLEDGE-EARLY` | 2027-06-21 | 2027-07-05 | marketing | CAP 24, CLK 00..03, CLK 10..11 | 30 |
| `Q07-ENRICHED-OPERATING-SHIFT` | 2027-06-28 | 2027-07-03 | marketing | CAP 24, CLK 04..07, CLK 08..09 | 30 |
| `Q07-ENRICHED-ROLE` | 2027-06-28 | 2027-07-05 | operating | CAP physical 16 keys grouped to 8 operating markets, CAP codeshare-only 8 keys, CLK 04..07 and 10..11 | 18 |

The demo beat: the first two invocations differ in **four rows** with the same operating date, because
four services were withdrawn from the plan and four were added in the last week of knowledge. The
first and third differ in **four rows** with the same knowledge date, because two services stop
operating on 07-04 and two only operate on Mondays. Same question, same data, two clocks, visibly
different answers. `Q07-ENRICHED-ROLE` additionally returns four `UNRESOLVED_PHYSICAL_SERVICE` rows
and, across all four invocations, `cabin_quality` takes at least three distinct values.

## 10. Enriched passenger population and fulfilment

### 10.1 Historical rows

10,000 rows: 13 anchors byte-identical, 9,987 filler in four blocks.

| Block | Rows | Construction |
|---|---:|---|
| `FUL-PH` | 700 | PH-01 is the `n`-th element of `AVAIL[1989:2689]` (the AF fulfilment block, section 11.1). PH-04 equals the matching leg's AF-06; PH-05 and PH-06 equal its AF-04 and AF-03; PH-07 equals its AF-05 as a number; PH-10 and PH-11 are the leg's endpoints as IATA. PH-02 is the CORE key whose knowledge window contains PH-03. 600 of these are one-leg plans; 50 are two-leg stopover plans where two PH rows share one canonical key and PH-22 = 1 with PH-23 set to the intermediate IATA. |
| `SCHED-PH` | 6,800 | generated from schedules. PH-02 = `SYN-SK-W27-CORE-{k:05}` for `k = index mod 2000`; PH-03 = the eligible snapshot date whose knowledge segment contains it; PH-04 = `2027-08-01 + (index mod 150)` days, always inside the key's operating window; PH-05, PH-06, PH-07, PH-10, PH-11 copied from that key's SS-04, SS-05, SS-06, SS-10, SS-11. |
| `UNION-OVERLAP-PH` | 500 | canonical keys that also appear in `PASSENGER_FORWARD`, so historical precedence is exercised 500 times instead of once. PH-02 set as for `SCHED-PH`. |
| `PLAIN-PH` | 1,987 | PH-02 null. Deliberately schedule-keyless historical rows, because a real feed is not fully populated. |

PH-01 is assigned from the pool in section 5 to the first 2,287 filler rows in block order after the
700 `FUL-PH` identifiers; the remaining rows carry PH-01 null and remain distinguishable because their
full-row DV-43 values differ. PH-08, PH-09, PH-12 through PH-21 keep the v1 template except that
PH-12 / PH-13 are `09:00:00` / `11:00:00`, PH-14 / PH-15 are `16:00:00` / `18:00:00`, PH-16 / PH-17
are `-420.0`, and PH-18 is 0.

### 10.2 Forward rows

10,000 rows: 9 anchors byte-identical, 9,991 filler.

| Block | Rows | Construction |
|---|---:|---|
| `HEUR-PF` | 400 | 340 rows each uniquely compatible with one `HEUR` leg (section 11.1) on carrier, flight number, operating date and endpoints, producing `HEURISTIC_CANDIDATE`; 60 rows forming 30 pairs each compatible with the same leg, producing 30 `AMBIGUOUS_CANDIDATE_GROUP`s with two members. |
| `SCHED-PF` | 8,000 | forward plans generated from CORE keys the same way as `SCHED-PH`, with PF-05 in `2027-08-01 .. 2027-12-31` and PF-10 through PF-13 expanded timestamps on PF-05. |
| `UNION-OVERLAP-PF` | 500 | the forward side of the 500 overlapping canonical keys. Historical wins; forward lineage is retained. |
| `PLAIN-PF` | 1,091 | forward-only plans on 2027 dates with no historical or actual counterpart. |

PF-01 is assigned from the section 5 pool to as many rows as it holds, in block order; the remainder
carry PF-01 null with distinct DV-43 values. No filler PF row may reproduce an anchored canonical key
or an anchored DV-43 digest.

### 10.3 Fulfilment coverage targets

| Measure | v1 live | v2 target |
|---|---:|---:|
| `FULFILLMENT_EXACT` rows | 4 | **700** |
| Actual legs with an exact fulfilment | 4 of 3,900 (0.1%) | 700 of 3,900 (18%) |
| Canonical passenger flights exactly fulfilled | 4 | 650 (600 direct plus 50 stopover plans) |
| Actual legs carrying candidate evidence only | 2 | 400 |
| Actual legs deliberately unmatched | 1 | 647 |
| `PASSENGER_HISTORICAL` rows with non-null `schedule_key` | 1 | **8,000 of 10,000 (80%)** |
| Canonical passenger flights with non-null `schedule_key` | 1 of 19,996 (0.005%) | **8,000 of about 19,499 (41%)** |
| Schedule-keyed flights that pin to exactly one route-state version | 1 | 8,000 (100% by construction) |

The 41% ceiling is structural, not a data gap: `SOURCE_CONTRACT.md` gives
`PASSENGER_FORWARD` no `schedule_key` field, so forward-only canonical flights cannot carry one. That
sentence belongs in the talk track, because it is the honest answer to "why is it not 100%".

With 8,000 schedule-keyed flights whose publish date falls inside exactly one route-state knowledge
segment, the A1 `ROUTE_STATE -> PASSENGER_FLIGHT` relationship becomes worth building: the walk
airport -> route -> route state -> airline -> generated flights returns rows.

## 11. Enriched actual flights and rotations

### 11.1 AF identifier partition

`AVAIL` is ascending `5000..8998` minus the 24 AF anchors, 3,975 identifiers. The 3,876 filler rows
are allocated by contiguous slice, which is deterministic and cannot collide with an anchor:

| Block | Slice | Rows | Use |
|---|---|---:|---|
| `ROT` | `AVAIL[0:1989]` | 1,989 | rotation legs |
| `FUL` | `AVAIL[1989:2689]` | 700 | exact-fulfilment legs, shared with PH-01 |
| `HEUR` | `AVAIL[2689:3089]` | 400 | heuristic and ambiguous candidate legs |
| `ANOM` | `AVAIL[3089:3229]` | 140 | the dedicated anomaly aircraft |
| `UNM` | `AVAIL[3229:3876]` | 647 | unmatched actual legs |
| unused | `AVAIL[3876:3975]` | 99 | reserved, not emitted |

### 11.2 Common construction

AF-02 is a filler aircraft identifier. AF-03 and AF-04 are `P_OP[c]` and `P_MKT[c]`. AF-05 is the
string form of a flight number in 1900..1999. AF-06 is the source-local selected day and AF-07 is the
UTC date, which equals AF-06 except where a leg crosses UTC midnight. AF-08, AF-09 and AF-10 are
`SYN-AP-*` internal identifiers. AF-17, AF-18 and AF-19 are the descriptive labels of the aircraft's
resolved configuration on AF-06, except where a discrepancy is injected. AF-11 and AF-12 are 0 unless
an anomaly requires otherwise.

### 11.3 Rotation cohort

609 rotations over the dates `2027-06-01` through `2027-06-30`: 300 rotations of four legs, 120 of
three, 60 of five, and 129 single-leg rotations, totalling 1,989 legs.

Rotation `r` (`r = 0..608`) has date `2027-06-01 + (r mod 30)` days. Its aircraft is chosen by
starting at index `i = (7r) mod 993` and advancing `i` cyclically until `a_i` (a) exists on that date
under its AM-07 and AM-08 bounds, (b) is date-visible `In Service` on that date under section 7, and
(c) has not already been assigned a rotation on that date. That guarantees every enriched rotation has
a resolvable as-of type and engine, which is the point of Q08's enrichment column.

Legs of one rotation form a connected chain over the whitelist: leg `l` departs the previous leg's
arrival airport, gate departure is the previous arrival plus a turn of `45 + 15(l mod 3)` minutes, and
block time is `90 + 30(l mod 4)` minutes. The first leg departs at `13:00` UTC, except for rotations
with `r mod 5 == 0`, which depart at `21:30` UTC so the final leg lands on the following UTC date and
AF-07 is `AF-06 + 1` while AF-06 still selects the rotation. AF-20 points at the next leg and is null
on the terminal leg.

Type discrepancy: for legs with `(r + l) mod 12 == 5`, AF-17 is set to the label of a **different**
fleet type, so `type_discrepancy` is true on roughly 8% of legs rather than on one hand-placed leg.

Anomalies inside real rotations: for the 30 rotations with `r mod 20 == 13`, exactly one link is
corrupted, cycling through the eleven anomaly codes by `(r div 20) mod 11`. Codes that need no extra
row (`SELF_LOOP`, `CYCLE`, `MISSING_TARGET`, `BACKWARD_TIME`, `BROKEN_CONTINUITY`,
`DIVERSION_ENDPOINT_CONFLICT`, `CANCELLED`, `MISSING_TIME`,
`UNKNOWN_OR_INVALID_CANCELLATION_FLAG`) are constructed in place. `DIFFERENT_AIRCRAFT` points AF-20
at a leg of another rotation on the same date; `OUTSIDE_SELECTED_DAY` points it at a leg on the
following date. So the enriched anomaly rate is 30 of 609 rotations, about 5%, which is what an
operational feed looks like.

`Q08-ENRICHED-ROTATION` names the rotation with `r` such that the date is `2027-06-08` and the leg
count is five; `Q08-ENRICHED-CLEAN` names a four-leg rotation on `2027-06-09` with `r mod 20 != 13`.
The implementer resolves both aircraft identifiers from the deterministic assignment above and freezes
them into the D-0023 table before generation.

### 11.4 Dedicated anomaly aircraft

Ten filler aircraft, `a_i` for `i` in `{30, 90, 150, 210, 270, 330, 390, 450, 510, 570}`, each on one
date `2027-07-06 + 2n` for `n = 0..9`, carry the full eleven-code anomaly set constructed exactly as
the anchored `AF-8101..8112` plus targets `8205` / `8206` pattern, at 12 source legs plus 2 target
legs each, 140 legs total. `Q08-ENRICHED-ANOMALIES` invokes the first of these, giving an eleven-row
anomaly answer on a filler aircraft that mirrors the anchored 1099 answer without touching it.

`a_1999` must receive **no** actual leg with AF-06 = `2026-08-31`, so `Q08-NOT-FOUND` stays empty.
Every v2 AF date is in 2027, which satisfies this by construction, and section 12 asserts it directly.

### 11.5 Airline reference

`AIRLINE_REFERENCE` grows to 180 rows. The exact-required union gains the 32 pool carriers, the 12
`MKTENT` and 12 `MKTEXIT` marketing carriers, the 10 `SYN-OP-W27-ENT-{02..11}` and 12
`SYN-OP-W27-EXIT-*` operating carriers, and any codeshare identity referenced by SS-36. Every one uses
the v1 complete AL-01 through AL-10 constructor with AL-05 = `SYN-ICAO-` plus the first 12 uppercase
hex digits of `SHA256(AL-01)`. The two controlled ambiguity rows and the `SYN-ZZZ` absence are
unchanged. Padding tokens `SYN-MKT-REF-FILL-{NNN}` fill the table to 180. No new alias may equal any
golden raw carrier, `SYN-DUP`, or `SYN-ZZZ`, and every golden raw carrier must still have candidate
count exactly one.

`AIRPORT_REFERENCE` is unchanged at 45 rows, so `TT-CODE-RESOLUTION` cannot move.

## 12. Mandatory assertions

Generation remains fail-closed: any count, key, type, hash, ownership, endpoint, isolation or
expected-result mismatch produces no publishable manifest.

### 12.1 Frozen-expectation preservation (run before anything is written)

1. All 253 v1.1.1 expected rows are reproduced exactly, once each, with the v1 ownership map intact.
2. `Q03-CANONICAL` recomputes exactly 132 rows over exactly 120 month ends with only
   `SYN-TYPE-A` and `SYN-TYPE-B`, and **no filler aircraft appears in it**. Additionally, every filler
   AM-07 is at or after `2025-01-01` and every filler AH-05 is at or after `2025-01-01`.
3. `Q05-CANONICAL` recomputes exactly 35 rows with adjacent counts 7, 5, 9, 14 and the 13/13 presence
   closure; no 2027 key contributes.
4. `Q06-CANONICAL` recomputes exactly its two rows and retains its declared result-set SHA-256
   `8513a82b4b666032fb3c4136830d96cefa924e61aeb6c573b2a8f20f38a8e227`.
5. `Q07` retains its declared v1.0 `result_sets` SHA-256
   `252a18496a59cc871dbe019ad7b2ac79674310b44435602b215d7c46b8091f2f`, and
   `Q07-KNOWLEDGE-END-EMPTY` is still empty, which requires that no 2027 key is present at the
   2026-09-07 snapshot.
6. `Q08-NOT-FOUND` is still empty: no AF row has `AF-02 = a_1999` and `AF-06 = 2026-08-31`, and more
   strongly no AF row has `AF-06` in 2026 other than the 24 anchors.
7. `Q02-CANONICAL` returns exactly two rows for 1001 and `Q02-NO-SPELLS` is empty for 1004.
8. All eleven contract truth tables reproduce their frozen rows. In particular the nine new AH columns
   are constant across all 24 anchored events, only AH row 102099 carries the `9999-12-31` source
   sentinel, `AIRPORT_REFERENCE` is byte-identical, and the four `TT-CODE-RESOLUTION` inputs still
   yield candidate counts 1, 0, 2, 0.
9. Every non-SC golden source row is byte-identical to its v1 form after the nine new AH columns are
   appended with their constant anchor values. The ten v1 SC rows including SC-05 are byte-identical.

### 12.2 Enrichment invariants (the reviewable numbers)

10. `AIRCRAFT_HISTORY` holds exactly 30,233 rows with the section 7.6 per-cohort split.
11. Versions per aircraft over the 993 filler aircraft: `aircraft_state` mean 8.57 with all 993 above
    one and maximum 16; `aircraft_status` mean 2.32 with 465 above one and maximum 9;
    `aircraft_type` mean 1.20 with 200 above one; `engine_type` mean 1.31 with 305 above one.
12. Status observation vocabulary over filler events: `In Service` 28,272, `Storage` 1,654,
    `Maintenance` 283. Exactly three distinct values.
13. Q02 spell population over the 993 filler aircraft: 437 closed spells; 737 aircraft with none, 102
    with one, 127 with two, 27 with three. Duration buckets: 18 at zero days, 38 at 1 to 7, 31 at 8 to
    30, 88 at 31 to 90, 163 at 91 to 365, 58 at 366 to 730, 41 above 730; minimum 0, median 157,
    maximum 1,091.
14. No aircraft has a `Storage` observation nested inside an unclosed storage spell, and the
    consecutive-status-compressed sequence never repeats a status.
15. `Q03-ENRICHED` recomputes exactly **985** rows over exactly **120** month ends with exactly ten
    distinct `aircraft_type_id` values. `SYN-TYPE-RJ1` is 150 at 2025-01-31 and absent from every
    month end after 2030-11-30. `SYN-TYPE-NB3` is absent before 2028-01-31 and 200 at 2034-12-31.
    `SYN-TYPE-FRT1` is exactly 50 at all 120 month ends. `SYN-TYPE-B` is exactly 3 and
    `SYN-TYPE-MIXED` exactly 1 at all 120 month ends, which is how the anchored aircraft visibly
    survive inside the enriched answer.
16. `SCHEDULE_SNAPSHOT` holds exactly 124,636 rows: the 70,000 v1 rows byte-identical plus 54,636 in
    the section 9.2 per-cohort split. `SCHEDULE_SNAPSHOT_CALENDAR` holds exactly 36 rows.
17. The 2027 block has exactly 24 eligible complete dates, 23 adjacent pairs, and exactly two
    gap-crossing pairs at indices 10 and 14. Exactly 2,301 rows sit at the incomplete date
    2027-03-15 and they derive zero canonical observations, zero segment boundaries and zero events.
    Zero rows sit at 2027-04-19.
18. `Q05-ENRICHED` recomputes exactly **392** rows with the section 9.3 class histogram and per-pair
    distribution, and the exact-presence partner closure holds over all 392.
19. `Q06-ENRICHED-MARKETING` recomputes exactly 7 rows (4 entries, 3 exits) and
    `Q06-ENRICHED-OPERATING` exactly 5 (2 entries, 3 exits), and the difference is attributable to
    `MKTENT-00` and `MKTENT-01` alone.
20. The four `Q07-ENRICHED-*` sets recompute exactly 30, 30, 30 and 18 rows; the first two differ in
    exactly 4 rows; the first and third differ in exactly 4 rows; `Q07-ENRICHED-ROLE` contains exactly
    4 `UNRESOLVED_PHYSICAL_SERVICE` rows; and `cabin_quality` takes at least three distinct values
    across the four sets.
21. `AIRCRAFT_FLIGHT` holds exactly 3,900 rows with the section 11.1 partition. Exactly 700 legs carry
    an exact fulfilment, exactly 400 carry candidate evidence only, exactly 647 are unmatched, and no
    identifier outside `5000..8998` is used. 8999 is absent.
22. Rotations: exactly 609 rotations over `2027-06-01..2027-06-30`, every rotation's aircraft
    date-visible `In Service` with a resolvable as-of type and engine, exactly 30 rotations carrying
    exactly one anomaly each with all eleven codes represented, roughly 8% of legs flagged
    `type_discrepancy`, and at least 120 rotations whose final leg has `AF-07 = AF-06 + 1`.
23. The ten dedicated anomaly aircraft each reproduce all eleven anomaly codes on their date under the
    frozen precedence order, with `CYCLE` emitted once per component at its minimum flight identifier.
24. Passenger coverage: exactly 8,000 `PASSENGER_HISTORICAL` rows carry a non-null `schedule_key`;
    100% of them pin to exactly one route-state knowledge segment; exactly 500 canonical keys are
    present on both passenger sides with historical precedence and both lineages retained.
25. Every 2027 route uses two distinct whitelist IATA endpoints; every actual endpoint is a
    `SYN-AP-*` internal identifier; every AM-09, AH-23 and AH-25 code is whitelisted; every non-null
    AH-22 is a matching whitelist `SYN-AP-*`; every non-airport identity is visibly synthetic or
    inside a frozen numeric range.
26. Column count is 204 and every column is commented. Two clean `demo` runs are byte-identical. A
    reordered-input run produces identical canonical rows, identifiers, expected results and manifest
    hashes.

### 12.3 Predicted post-change fidelity measures

The A7 table, restated with the v2 predictions, which is what the audit should be updated to say:

| Measure | v1 live | v2 predicted |
|---|---:|---:|
| `aircraft_state` versions per aircraft | 1.005 | 8.57 |
| aircraft with more than one state version | 2 of 999 | 999 of 999 |
| `aircraft_status` versions per aircraft | 1.004 | 2.32 |
| aircraft with more than one status version | 2 of 999 | 467 of 999 (465 filler plus 1001 and 1002) |
| `aircraft_type` versions per aircraft | 48 (fake churn) | 1.20 (real conversions) |
| `engine_type` versions per aircraft | 48 (fake churn) | 1.31 (real conversions) |
| In Service -> Storage -> In Service spells | 2 | 439 |
| distinct spell-duration buckets populated | 2 | 7 |
| Q03 rows over its ten-year window | 132 over 2 aircraft and 2 types | 985 over 997 aircraft and 10 types |
| Q05 rows and populated event classes | 35 rows, 8 classes but 6 of them at 1 to 3 rows | 392 rows, 8 classes, minimum 6 rows |
| Q06 market zero-crossings | 2 | 24 across the block, 12 at the demo endpoint |
| `FULFILLMENT_EXACT` rows | 4 | 700 |
| canonical flights with a schedule key | 1 of 19,996 | 8,000 of about 19,499 |
| versioned A4 attributes carried | about 20 of 38 | about 29 of 38 |

The type and engine version counts **fall**, and that is the improvement. Forty-eight daily
`SYN-TYPE-FILL-NNN` values per aircraft is not richness; it is noise that makes Q04 unreadable. 1.20
and 1.31 with 200 and 305 aircraft actually converting is what an airline fleet looks like.

## 13. Implementation notes against the current generator

`data/generate_synthetic_data.py` needs these changes and no others in structure:

| Function | Change |
|---|---|
| `EXPECTED_COUNTS['demo']` | new counts from section 4 |
| `parse_contract_fields` | picks up AH-34..AH-42 automatically once `SOURCE_CONTRACT.md` is updated; assert 204 |
| `aircraft_master` | replace the `i mod 365` date rule with the section 7.2 cohort rule |
| `aircraft_configuration` | insert the thirteen fleet definitions at 300000..300012, shift filler to 300013..301995 |
| `history_template` | add the nine new columns with the section 8 defaults |
| `aircraft_history` | replace the `49/48 consecutive days` filler loop with the section 7.3 and 7.4 event builder; keep the anchored inventory and its carry-forward loop untouched, widening the carry-forward range from `AH-17..AH-31` to include `AH-34..AH-42` |
| `schedule_rows` | add the 2027 cohort builder; leave the v1 universe, August filler and October diagnostics untouched |
| `snapshot_calendar` | add the 26 new rows |
| `passenger_forward`, `passenger_historical` | replace the 2035/2036 filler blocks with the section 10 blocks |
| `aircraft_flights` | replace the 2040 filler block with the section 11 blocks |
| `airline_reference` | union grows; the sorted-position ordinal rule is unchanged |
| `compute_q05`, `compute_q06`, `compute_q07` | must now also materialize the enriched sets before publication |
| `validate_q03`, `validate_schedule_results`, `validate_identity_namespaces`, `validate_tables` | extend with the section 12 assertions; the v1 filler-isolation assertion "all filler existence begins after 2024-12-31" is retained, and assertion "every configuration resolves" is restated as "every configuration referenced by an event resolves" |

`data/oracles/` needs one new SQL file per new result set, or a parameterized reuse of the existing
eight, plus one new probe `probe_fleet_lifecycle.sql` asserting section 12.2 items 11 through 14 and
one new probe `probe_schedule_2027.sql` asserting items 17 and 18. `data/run_oracles.py` needs the new
result sets registered and a new `TRUTH_TABLE_NOT_ORACLED` entry only if a new truth table is added,
which this specification does not do.

The v1 `probe_incomplete_snapshots.sql`, `probe_concurrent_route_states.sql`,
`probe_schedule_canonicalisation.sql` and `probe_temporal_integrity.sql` checks were reviewed
individually against this design: every one is scoped to a named key, a named aircraft, a named date
or a threshold that the enrichment can only strengthen. In particular
`GAP_CONTROL_PREVIOUS_ELIGIBLE_IS_20261005` survives because every new snapshot date is after
2026-10-26, and `NO_SEGMENT_BOUNDARY_ON_INELIGIBLE_DATES` survives because the 2027 churn cohorts are
not emitted at the ineligible 2027 dates.

## 14. Risks, ranked

1. **`Q03-CANONICAL` is the single load-bearing preservation claim.** It is the only frozen result set
   whose value depends on the whole aircraft population rather than on named identifiers. The
   protection is structural (every filler date at or after 2025-01-01) and is asserted twice
   (assertion 2 and assertion 9). If an implementer relaxes the date floor for realism, this breaks
   silently and the failure looks like a Q03 count drift.
2. **985 and 392 hand-reviewable rows are a lot of rows.** Section 3.4's aggregate-first review
   procedure is the mitigation, but a reviewer who skips the aggregates and skims the rows will not
   catch a systematic error. The per-class histogram, the per-pair distribution and the spell-duration
   buckets are the checks that actually bind.
3. **The `AVAIL[1989:2689]` fulfilment block deliberately makes PH-01 and AF-01 collide.** That is how
   `EXACT_FULFILLMENT` is defined, so it is correct, but it means the two identifier pools are no
   longer independently allocatable. An implementer who reorders the AF blocks changes which passenger
   rows fulfil, and 700 expected fulfilments move. The slice boundaries are part of the contract.
4. **The nine new AH columns widen the watched set, which is a semantic change to version minting.**
   For filler aircraft that is the intent. For anchored aircraft it is neutralized only by the
   constant-payload rule in section 8. That rule is the difference between an additive supersession
   and a broken manifest.
5. **`SCHEDULE_SNAPSHOT` grows 78%.** 124,636 rows is comfortable on `RAI_XS` for the v1 query shapes,
   but Q05 over 23 adjacent pairs of a 2,527-key universe is roughly five times the v1 comparison
   work. If the enriched Q05 does not return inside the cold budget, the CORE cohort is the knob:
   halve it before touching anything semantic.
6. **Q02 cannot show a fleet-wide distribution through its frozen interface.** Its parameter schema
   takes a non-nullable `aircraft_id`. This specification therefore ships the distribution as a
   validation-layer artifact (`probe_fleet_lifecycle.sql`) and four named per-aircraft result sets. An
   alternative exists (widen `aircraft_id` to nullable with null meaning the whole fleet) but it
   changes a frozen parameter schema, which is a larger ask than the additive supersession, and the
   demo works without it. It is called out here so the reviewer can accept or reject it explicitly
   rather than discovering it on stage.
7. **The order-to-delivery compression for 700 aircraft is visibly synthetic.** All five master
   milestone dates equal 2025-01-01 for the founding cohorts. A data engineer in the audience may
   notice. The alternative is pre-2025 master dates, which weakens risk 1. Compression was chosen
   deliberately; the talk track should say so rather than hope nobody looks.
8. **`AF-01` has no headroom.** The reserved range `5000..8999` holds 3,999 rows and 3,900 are used.
   Any future request for more actual legs requires widening a frozen `numeric_namespace_assertion`,
   which is a scope supersession rather than a data change.
9. **The 1,983 unreferenced filler configurations are now dead weight.** They keep the table at 2,000
   rows and exercise the definition-layer functional dependencies, but nothing references them. That is
   defensible (reference tables are wider than the fleet) and it is stated here so it is not
   discovered as a defect.
10. **This specification has not been executed.** Every number in sections 7.6, 9.2, 9.3, 12.2 and
    12.3 comes from a deterministic model of the rules written here, not from a generator run. They are
    predictions with an arithmetic derivation, and section 3.4 step 2 exists precisely so that a
    mismatch is treated as a specification defect rather than quietly absorbed.

## 15. Failure, rollback, and handoff

Generation is fail-closed and expected answers are never edited to accommodate generator output.
The rollback for any implementation of this specification is deletion of its generated output
directory followed by regeneration from specification 1.0.0; the frozen 1.1.1 expectations are
untouched by construction, so rollback cannot lose an expectation.

Changing D-0008's offset sign, D-0003's end-of-life boundary, D-0010 or D-0011 schedule closure, or
D-0023's additive-only constraint requires a new reviewed decision and a new manifest supersession
before this specification may change.

No Snowflake mutation is part of generation. Only the load task may publish the verified files, using
the scoped demo role and database. `SOURCE` is currently bound live by the ontology layer, so no
reload may begin until that binding is released and the D-0023, D-0024 and D-0025 decisions are
accepted.
