# Deterministic synthetic aviation data specification

## Authority, scope, and release status

This is the normative DATA-01 input contract for DATA-02. It instantiates the frozen v1.1.1
manifest in `EXPECTED_ANSWERS.yaml`; it does not change any expected answer. `SEMANTIC_DECISIONS.md`,
`SOURCE_CONTRACT.md`, `ATTRIBUTE_AUTHORITY.md`, `NEO4J_RAI_MAPPING.md`, and decisions D-0003 through
D-0012 remain authoritative. If this file can be read two ways, those frozen authorities win.

Every flight scenario is explicitly synthetic and U.S.-domestic. Public airport labels are limited
to `SFO`, `LAX`, `LAS`, `SEA`, `DEN`, `ORD`, `PHX`, `BOS`, and `MIA`; they provide geography labels,
not observed operational facts. All carriers, aircraft facts, schedules, passenger services,
capacities, times, and actual legs are fictional. Planned endpoints use whitelisted IATA labels.
Actual endpoints use the corresponding `SYN-AP-*` internal IDs. No source row or modeled rule
derives country or domestic status.

The data demonstrates functional behavior at representative shape only. Neither scale is a
production benchmark, and neither supports a performance, cost, security, or universal-comparison
claim.

## Reproducibility constants

| Constant | Frozen value |
|---|---|
| Specification version | `1.0.0` |
| Expected-manifest version | `1.1.1` |
| Seed | `20260901` |
| Frozen generation date | `2026-09-01` |
| Frozen generation timestamp | `2026-09-01T00:00:00Z` |
| Source open/unknown-future date | `9999-12-31` |
| Model open-interval date | `9999-01-01` |
| Text encoding | UTF-8, no BOM |
| Line ending | LF |
| Hash | SHA-256 |

Generation MUST NOT read the wall clock, locale, machine hostname, Python hash seed, unordered set
order, or input file order. Pseudorandom filler uses a counter PRF:

```text
SHA256("20260901" || "|" || source_object || "|" || zero_padded_row_index || "|" || field_id)
```

`source_object` is one of these exact ASCII tokens; aliases and case changes are invalid. The
counter is a scale-stable constructor ordinal, not a physical file position. It is rendered as
exactly six ASCII digits with leading zeroes; an ordinal outside `0..999999` is an error. Named rows
retain the same ordinal in smoke and demo, and later physical sorting never changes it.

| Source object | Exact PRF token | Constructor ordinal assignment |
|---|---|---|
| `AIRCRAFT_MASTER` | `SOURCE.AIRCRAFT_MASTER` | six named rows `000000..000005` in inventory order; demo filler `100000+i` in sorted `a_i` order |
| `AIRCRAFT_HISTORY` | `SOURCE.AIRCRAFT_HISTORY` | 24 named rows `000000..000023` in inventory order; demo filler `100000+k`, where `k` is zero-based traversal position of ascending `(i,j)` |
| `AIRCRAFT_CONFIGURATION` | `SOURCE.AIRCRAFT_CONFIGURATION` | four named rows `000000..000003`; demo filler `100000+i` |
| `SCHEDULE_SNAPSHOT` | `SOURCE.SCHEDULE_SNAPSHOT` | 81 canonical rows `000000..000080` in displayed key/date order; V02=`000081`; DUP=`000082`; five named diagnostics `000083..000087`; August filler `100000+5*i+d` for ordered date index `d=0..4`; 9,912 extra diagnostics `200000+i` |
| `SCHEDULE_SNAPSHOT_CALENDAR` | `SOURCE.SCHEDULE_SNAPSHOT_CALENDAR` | ten displayed dates `000000..000009` |
| `PASSENGER_FORWARD` | `SOURCE.PASSENGER_FORWARD` | nine named rows `000000..000008`; demo filler `100000+i` |
| `PASSENGER_HISTORICAL` | `SOURCE.PASSENGER_HISTORICAL` | thirteen named rows `000000..000012`; demo filler `100000+i` |
| `AIRCRAFT_FLIGHT` | `SOURCE.AIRCRAFT_FLIGHT` | 24 named rows `000000..000023`; demo filler `100000+i` |
| `AIRPORT_REFERENCE` | `SOURCE.AIRPORT_REFERENCE` | whitelist rows `000000..000008` in frozen manifest order; ambiguity rows `000009..000010`; demo filler `100000+i` |
| `AIRLINE_REFERENCE` | `SOURCE.AIRLINE_REFERENCE` | exact-required identities use their position in the sorted 65-identity demo union, preserving the same ordinal in smoke; ambiguity A/B are `001000..001001`; padding is `100000+i` |

For example, the first August filler row (`i=0`, `d=0`, 2026-08-03) and field SS-39 use the exact
ASCII PRF input
`20260901|SOURCE.SCHEDULE_SNAPSHOT|100000|SS-39`. Its SHA-256 is
`491861981a7e9e11dd9d7f5650a019f5cd99b2eff006d88f74b9b18081ded65d`; the first two bytes are
big-endian 18712, so the ordinary SS-39 rule yields `9000 + (18712 mod 1000) = 9712`. DATA-02 must
include this known-answer vector and fail on any different digest or SS-39.

Integers, selections, and Boolean values are derived from the digest bytes in big-endian order.
No runtime RNG implementation is on the reproducibility boundary. Any shuffle test shuffles a copy
using a second domain token and MUST reproduce the same canonical output after sorting.

DV-43, DV-44, and DV-46 use D-0012 grammar `dv43-lp-v1`, the concrete form of the typed,
length-prefixed serialization required
by `SOURCE_CONTRACT.md`. For any UTF-8 byte string `b`, `frame(b)` is the ASCII base-10 byte length,
one colon byte, then `b`, with no whitespace or terminator. Each field in ascending Field-ID order
is encoded as `frame(Field-ID) || frame(exact Snowflake type tag) || frame("N")` for null, or
`frame(Field-ID) || frame(exact Snowflake type tag) || frame("V") || frame(canonical value)` for a
value. This separate N/V frame makes null distinct from the VARCHAR text `NULL`. PF prepends
`frame("FORWARD")`; PH prepends `frame("HISTORICAL")`; these are the source-system prefixes required
by the contract. SHA-256 is computed over the resulting bytes and rendered as 64 lowercase hex
characters. No separator other than frame colons participates. Files are emitted in source-contract
Field-ID order. Rows are emitted in the following physical order before file hashing:

- scalar source keys ascending, null last;
- composite keys lexicographically by typed component;
- `AIRCRAFT_HISTORY` by `(aircraft_id, start_event_date, row_sequence_number,
  event_sequence_number, aircraft_history_id)`;
- `SCHEDULE_SNAPSHOT` by `(publish_date, schedule_key, itinerary_variation_identifier,
  normalized_row_hash)`; and
- null source IDs by DV-46 source row token.

The generated manifest records specification/expected-manifest hashes, scale, constants, exact row
counts, per-table ordered-row hash, output-file hash, and the 253-row ownership hash. Two clean runs
of one scale MUST be byte-identical. A reordered-input run MUST have different raw input order but
identical canonical rows, IDs, expected results, and canonical manifest hashes.

## Exact scale budgets

| Raw source table | `smoke` rows | `demo` rows | Filler rule |
|---|---:|---:|---|
| `AIRCRAFT_MASTER` | 6 | 999 | Every allowed numeric aircraft ID `1000..1999` except reserved-not-loaded `1003`; anchor rows replace filler rows. |
| `AIRCRAFT_HISTORY` | 24 | 48,000 | Unique IDs in `101000..199999`; no filler event belongs to a golden aircraft. |
| `AIRCRAFT_CONFIGURATION` | 4 | 2,000 | Four named definitions plus deterministic unique filler definitions. |
| `SCHEDULE_SNAPSHOT` | 88 | 70,000 | 81 golden constructed observations, two NF-S01 raw variant/duplicate occurrences, and five named incomplete-snapshot diagnostics; demo additionally has 60,000 stable August filler rows and 9,912 further incomplete-snapshot diagnostic rows. |
| `SCHEDULE_SNAPSHOT_CALENDAR` | 10 | 10 | Identical dates/statuses; scale-specific observed counts. |
| `PASSENGER_FORWARD` | 9 | 10,000 | Anchors plus valid, disjoint 2035 filler; null stable IDs use DV-43 fallback. |
| `PASSENGER_HISTORICAL` | 13 | 10,000 | Anchors plus valid, disjoint 2036 filler; exact-link sanity cannot match actual filler. |
| `AIRCRAFT_FLIGHT` | 24 | 3,900 | Anchors plus valid 2040 actual filler, disjoint from golden aircraft/dates/keys. |
| `AIRPORT_REFERENCE` | 11 | 45 | Nine whitelist identities, two controlled ambiguous-code identities, then disjoint reference-only filler. |
| `AIRLINE_REFERENCE` | 60 | 100 | Exact identities for every exact-required anchor/filler carrier, controlled non-exact diagnostics, and disjoint reference-only padding. |
| **Total** | **249** | **145,054** | Representative functional shape; every table is below 500,000 rows. |

`smoke` contains every golden and negative fixture. `demo` is a strict semantic superset: it keeps
every non-SC golden source row byte-identical and adds only filler proven not to affect the 253
expected rows. Calendar anchors keep SC-01..SC-04 and SC-06 byte-identical; SC-05 intentionally
changes to the scale's exact raw-row count. The scale name and exact counts must appear in timing
and result artifacts.

## Row-template convention

The tables below are complete constructors, not partial examples. Each object first receives every
field from its named full-row template. A named row then applies its listed overrides. An explicit
`null` is a value. There is no third “unspecified” state. DATA-02 must fail if any contracted Field ID
is absent after expansion or if an override names a non-contracted field.

## U.S. geography and code-resolution rows

### Airport reference

For the nine whitelist rows, AP-01 is `SYN-AP-{IATA}`, AP-02 is `2000-01-01`, AP-03 is null,
AP-04/AP-05/AP-06/AP-09 are the exact IATA, ICAO, public-name, and IANA-zone values frozen under
`scope.airport_whitelist` in `EXPECTED_ANSWERS.yaml`, and AP-07/AP-08 are true.

Two additional smoke rows are:

| AP-01 | AP-02 | AP-03 | AP-04 | AP-05 | AP-06 | AP-07 | AP-08 | AP-09 |
|---|---|---|---|---|---|---|---|---|
| `SYN-AP-DUP-A` | `2000-01-01` | null | `SYN-DUP` | `SYN-ICAO-DUP-A` | `Synthetic ambiguity A` | true | true | null |
| `SYN-AP-DUP-B` | `2000-01-01` | null | `SYN-DUP` | `SYN-ICAO-DUP-B` | `Synthetic ambiguity B` | true | true | null |

There is no AP row whose IATA code equals `SYN-ZZZ`. Null raw input is not converted. Thus `SFO`,
`SYN-ZZZ`, `SYN-DUP`, and null produce the frozen exact/unresolved/ambiguous/invalid truth rows.
The 34 demo-only AP rows use this complete filler template for index `i=000..033`: AP-01=
`SYN-AP-REF-FILL-{i}`, AP-02=`2000-01-01`, AP-03=null, AP-04=`SYN-IATA-FILL-{i}`,
AP-05=`SYN-ICAO-REF-FILL-{i}`, AP-06=`Synthetic non-operational airport reference filler {i}`,
AP-07=true, AP-08=true, and AP-09=null. These reference-only tokens are disjoint from all
operational raw codes and never appear in AM/AH/SS/PF/PH/AF.

AP-09 is lineage-only. It never overrides PF expanded timestamps, D-0008 PH offsets, SS UTC `TIME`,
or the AF-06 selected local date.

### Airline reference

Let `required_anchor_carriers` be the sorted distinct non-null raw values from SS-04/SS-05/SS-36 of
the 81 golden schedule observations and five named diagnostics, PF-02/PF-03, PH-05/PH-06, and
AF-03/AF-04, except the controlled non-exact raw values `SYN-DUP`, `SYN-ZZZ`, and null. Only for
`demo`, add `SYN-MKT-FILL-{00..15}` and `SYN-OP-FILL-{00..15}` for schedule filler; these 32
identities are not required in `smoke`. For each scale-required token `c`, emit one
row with AL-01=`c`, AL-02=`2000-01-01`, AL-03=null, AL-04=`c`,
AL-05=`SYN-ICAO-` plus the first 12 uppercase hex digits of `SHA256(c)`, AL-06=`c`,
AL-07=`Synthetic airline ` plus `c`, AL-08=false, AL-09=true, and AL-10=true. The union resolver
therefore sees one distinct AL-01 even when the raw token matches two columns of that row.

Add two controlled ambiguous identities. They use the same full constructor except AL-01 is
`SYN-MKT-DUP-A`/`SYN-MKT-DUP-B`, AL-04 is `SYN-DUP` for both, and AL-05 is
`SYN-ICAO-DUP-A`/`SYN-ICAO-DUP-B`. The union resolver therefore returns two distinct AL-01
candidates for raw `SYN-DUP`. No AL column equals `SYN-ZZZ`, and null is never converted.

The deduplicated exact-required set has exactly 33 identities in smoke and 65 in demo; including the
two ambiguity rows gives 35/67. Pad with 25 smoke tokens `c=SYN-MKT-REF-FILL-{000..024}` or 33 demo
tokens `{000..032}`. Every padding row uses
the same complete AL-01..AL-10 constructor in the preceding paragraph, including deterministic
AL-05, and its AL-04/AL-05 values are disjoint from every raw source carrier. A pre-generation
assertion proves that each golden raw carrier has candidate count one and no filler alias equals a
golden raw carrier.

NF-X01 runs the four TT-CODE-RESOLUTION statuses independently in each domain. Airport inputs are
the frozen `SFO`/`SYN-ZZZ`/`SYN-DUP`/null vector. Airline inputs are
`SYN-MKT-DIAG`/`SYN-ZZZ`/`SYN-DUP`/null and must produce the same
`EXACT`/`UNRESOLVED`/`AMBIGUOUS`/`INVALID_INPUT` cardinality-and-link vector. The TT38 literal
`raw_code` rows remain the frozen airport-domain representation; the separate airline-domain
assertion is HT/NF evidence and does not add a 254th expected row.

## Aircraft constructors

### `AIRCRAFT_MASTER` full template

AM-01 is supplied by the row inventory. AM-02=`SYN-SERIAL-{AM-01}`, AM-03=`SYN-LINE-{AM-01}`,
AM-04=`2014-01-01`, AM-05=`2014-06-01`, AM-06=`2014-12-01`, AM-07=`2025-01-01`, AM-08=null,
AM-09=`SEA`, AM-10=`SYN-OP-ORIGINAL`, AM-11=`SYN-APU-CURRENT`, AM-12=35.8,
AM-13=170000, AM-14=175000, AM-15=false, AM-16=`2014-06-15`, AM-17=`2014-07-01`,
AM-18=`Seattle synthetic build label`, and AM-19=`SYNTHETIC_DELIVERY`.

Anchor overrides are complete after template expansion:

| AM-01 | AM-04/05/06 | AM-07 | AM-08 | AM-09 | AM-18 | Purpose |
|---:|---|---|---|---|---|---|
| 1001 | `2014-01-01` / `2014-06-01` / `2014-12-01` | `2015-01-01` | null | `SEA` | `Seattle synthetic build label` | Q01/Q02/Q03/Q04/Q08 |
| 1002 | `2015-01-01` / `2015-06-01` / `2015-12-01` | `2016-01-01` | `2024-07-01` | `ORD` | `Chicago synthetic build label` | Q01/Q03/EOL |
| 1004 | `2018-01-01` / `2018-06-01` / `2018-12-01` | `2019-01-01` | null | `DEN` | `Denver synthetic build label` | before-first state |
| 1005 | `2024-01-01` / `2024-06-01` / `2024-12-01` | `2025-01-01` | null | `SEA` | `Seattle synthetic build label` | mixed-engine limit |
| 1098 | `2024-01-01` / `2024-06-01` / `2024-12-01` | `2025-01-01` | null | `SEA` | `Seattle synthetic build label` | different-aircraft target |
| 1099 | `2024-01-01` / `2024-06-01` / `2024-12-01` | `2025-01-01` | null | `LAX` | `Los Angeles synthetic build label` | rotation anomalies |

AM-11 through AM-14 deliberately differ from historically observed values and remain
`CURRENT_ONLY`. No AM row for reserved ID 1003 is emitted. Demo filler is the sorted 993 remaining
allowed IDs `a_i`. Let `d=i mod 365` and `p=2025-01-01+d calendar days`; after the full template,
set AM-04=`p`, AM-05=`p+30 days`, AM-06=`p+60 days`, AM-16=`p+75 days`, AM-17=`p+90 days`, and
AM-07=`p+120 days`. Set AM-09 to whitelist entry `i mod 9` and AM-18 to
`Synthetic build label {AM-09}`. Consequently no filler aircraft exists at a Q03 month end.

### `AIRCRAFT_CONFIGURATION` rows

| AC-01 | AC-02 | AC-03 | AC-04 | AC-05 | AC-06 | AC-07 | AC-08 | AC-09 | AC-10 | AC-11 | AC-12 | AC-13 | AC-14 | AC-15 | AC-16 |
|---:|---|---|---|---|---|---|---:|---|---|---|---|---|---|---|---|
| 2001 | `SYN-FAMILY-A` | `Synthetic narrowbody A` | `SYN-SERIES-A` | `SYN-TYPE-A` | `SYN-MFR-A` | `SYN-CLASS-NB` | 2 | false | `SYN-ENG-MFR-A` | `SYN-ENG-FAM-A` | `Synthetic turbofan A` | `SYN-ENG-SER-A` | `SYN-ENGINE-A` | `TURBOFAN` | `2026-08-31` |
| 2002 | `SYN-FAMILY-B` | `Synthetic narrowbody B` | `SYN-SERIES-B` | `SYN-TYPE-B` | `SYN-MFR-B` | `SYN-CLASS-NB` | 2 | false | `SYN-ENG-MFR-A` | `SYN-ENG-FAM-A` | `Synthetic turbofan A` | `SYN-ENG-SER-A` | `SYN-ENGINE-A` | `TURBOFAN` | `2026-08-31` |
| 2003 | `SYN-FAMILY-B` | `Synthetic narrowbody B` | `SYN-SERIES-B` | `SYN-TYPE-B` | `SYN-MFR-B` | `SYN-CLASS-NB` | 2 | false | `SYN-ENG-MFR-B` | `SYN-ENG-FAM-B` | `Synthetic turbofan B` | `SYN-ENG-SER-B` | `SYN-ENGINE-B` | `TURBOFAN` | `2026-08-31` |
| 2005 | `SYN-FAMILY-M` | `Synthetic mixed-engine test aircraft` | `SYN-SERIES-M` | `SYN-TYPE-MIXED` | `SYN-MFR-M` | `SYN-CLASS-WB` | 4 | true | `SYN-ENG-MFR-M` | `SYN-ENG-FAM-M` | `Synthetic reported mixed engine` | `SYN-ENG-SER-M` | `SYN-ENGINE-MIXED-REPORTED` | `TURBOFAN` | `2026-08-31` |

Configuration ID 999999 is deliberately absent. Each of 1,996 demo filler definitions at zero-based
index `i=0..1995`
uses this complete AC-01..AC-16 template: AC-01=`300000+i`, AC-02=`SYN-FAMILY-FILL-{i}`,
AC-03=`Synthetic filler aircraft type {i}`, AC-04=`SYN-SERIES-FILL-{i}`,
AC-05=`SYN-TYPE-FILL-{i}`, AC-06=`SYN-MFR-FILL-{i}`, AC-07=`SYN-CLASS-FILL`, AC-08=2,
AC-09=false, AC-10=`SYN-ENG-MFR-FILL-{i}`, AC-11=`SYN-ENG-FAM-FILL-{i}`,
AC-12=`Synthetic filler engine type {i}`, AC-13=`SYN-ENG-SER-FILL-{i}`,
AC-14=`SYN-ENGINE-FILL-{i}`, AC-15=`TURBOFAN`, and AC-16=`2026-08-31`. Thus all fields are
deterministic and both definition FDs hold.

### `AIRCRAFT_HISTORY` full template and variants

The full template sets AH-01/AH-02/AH-03/AH-05 from the inventory, AH-04=AH-03, AH-06=null,
AH-07=false, AH-08=`SYN-OBSERVATION`, AH-09=`In Service`, AH-10=null, AH-11=null,
AH-12=`SYNTHETIC_FIXTURE`, AH-13=2001, AH-14=`SA1`, AH-15=`SYN1`, AH-16=`SYN-TYPE-A`,
AH-17=`SYN-REG-{aircraft_id}`, AH-18=`SYN-XPDR-{aircraft_id}`, AH-19=`US`,
AH-20=`SYN-US`, AH-21=`PASSENGER`, AH-22=null, AH-23=null,
AH-24=`Synthetic base`, AH-25=`SFO`, AH-26=`Synthetic city`, AH-27=`United States`,
AH-28=null, AH-29=35.0, AH-30=165000, AH-31=170000, AH-32=false, and
AH-33=`2026-08-31`.

Configuration variants replace AH-13 through AH-16 as follows: `A/A` uses 2001 and
`SA1/SYN1/SYN-TYPE-A`; `B/A` uses 2002 and `SB1/SYN2/SYN-TYPE-B`; `B/B` uses 2003 and
`SB1/SYN2/SYN-TYPE-B`; `MIXED` uses 2005 and `SM1/SYN5/SYN-TYPE-MIXED`; `GAP_NULL` uses null and
null codes; `GAP_MISSING` uses 999999 and null codes.

The 24 smoke rows are exactly:

| AH-01 | AH-02 | AH-05 | AH-03 | Variant | AH-09 | State/provenance override |
|---:|---:|---|---:|---|---|---|
| 101001 | 1001 | `2015-01-01` | 10 | A/A | `In Service` | base `SFO`, registration `SYN-REG-1001` |
| 101003 | 1001 | `2018-03-01` | 10 | A/A | `Storage` | AH-22=`SYN-AP-LAX`, AH-23=`LAX` |
| 101004 | 1001 | `2018-04-15` | 10 | A/A | `In Service` | AH-22/AH-23=null |
| 101005 | 1001 | `2019-01-01` | 10 | B/A | `In Service` | no state change |
| 101008 | 1001 | `2020-06-01` | 5 | B/A | `Maintenance` | no state change |
| 101009 | 1001 | `2020-06-01` | 10 | B/A | `In Service` | no state change |
| 101010 | 1001 | `2020-06-01` | 20 | B/A | `Storage` | no state change |
| 101011 | 1001 | `2020-06-01` | 30 | B/A | `In Service` | no state change |
| 101020 | 1001 | `2020-06-01` | 40 | B/A | `In Service` | only AH-12=`SYNTHETIC_IRRELEVANT`; no watched delta |
| 101021 | 1001 | `2021-02-01` | 10 | B/A | `In Service` | AH-28=`SYN-APU-B` (null-to-value) |
| 101022 | 1001 | `2021-03-01` | 10 | B/A | `In Service` | AH-28=`SYN-APU-B` (same-day duplicate/irrelevant) |
| 101023 | 1001 | `2021-03-01` | 20 | B/A | `In Service` | AH-28=null (value-to-null) |
| 101024 | 1001 | `2021-03-01` | 30 | B/A | `In Service` | AH-28=`SYN-APU-B` (null-to-value; final-per-day) |
| 101007 | 1001 | `2021-07-01` | 10 | B/B | `In Service` | AH-28=`SYN-APU-B` |
| 102001 | 1002 | `2016-01-01` | 10 | A/A | `In Service` | base `SEA`, registration `SYN-REG-1002` |
| 102002 | 1002 | `2020-01-01` | 10 | A/A | `Storage` | AH-22=`SYN-AP-DEN`, AH-23=`DEN` |
| 102004 | 1002 | `2022-05-01` | 10 | GAP_NULL | `Storage` | state remains resolved |
| 102005 | 1002 | `2022-06-01` | 10 | GAP_MISSING | `Storage` | state remains resolved |
| 102006 | 1002 | `2022-07-01` | 10 | A/A | `Storage` | type/engine resolution restored |
| 102099 | 1002 | `2023-01-01` | 10 | A/A | `Storage` | AH-06=`9999-12-31`; business fields unchanged |
| 104001 | 1004 | `2020-01-01` | 10 | A/A | `Maintenance` | base `PHX`, registration `SYN-REG-1004` |
| 105001 | 1005 | `2025-01-01` | 10 | MIXED | `In Service` | base `ORD`, registration `SYN-REG-1005` |
| 109801 | 1098 | `2025-01-01` | 10 | B/B | `In Service` | base `LAX`, registration `SYN-REG-1098` |
| 109901 | 1099 | `2025-01-01` | 10 | B/B | `In Service` | base `SFO`, registration `SYN-REG-1099` |

For every row, state values not named in the override carry forward the immediately preceding full
observation for that aircraft, not the global template. This makes each event a complete source
snapshot. AH-06 is never used to close a derived interval. The inner-join-loss fixture consists
exactly of 102004 and 102005.

Demo filler excludes aircraft IDs `{1001,1002,1004,1005,1098,1099}`. For sorted filler aircraft
`a_i`, emit 49 history rows when `i<312`, otherwise 48; this is exactly 47,976 filler plus 24 anchor
rows = 48,000. Traverse `(i,j)` in ascending order and assign the next available AH-01 in
`101000..199999` excluding anchors. Set AH-02=`a_i`, AH-03=AH-04=`j+1`, AH-05=`AM-07(a_i)+j days`,
and AH-13=`300000+((i+j) mod 1996)`. The three descriptive codes are
AH-14=`SYN-SERIES-FILL-{configuration_index}`, AH-15=`SYN-SUBTYPE-FILL-{configuration_index}`,
and AH-16=`SYN-TYPE-FILL-{configuration_index}`; every other AH field comes from the full template.
Each aircraft's order tuple is therefore strictly unique and every configuration resolves. Filler
cannot change Q01/Q02/Q04/Q08 because IDs differ and cannot change Q03 because its existence and
assignments begin after `2024-12-31`.

## Unified schedule constructors

The mapping under `scope.schedule_source_universe` in `EXPECTED_ANSWERS.yaml` is directly
executable source input. DATA-02 MUST construct all 35 watched SS-04-through-SS-38 fields from its
32 common defaults plus the three route mappings SS-06/SS-10/SS-11, apply fixed overrides, apply
dated transitions, and emit rows only on true presence dates. No question-private field, cohort,
source table, or filter is permitted.

Every schedule row, including golden anchors, August filler, and incomplete diagnostics, receives
all lineage fields. SS-02=`SYN-READABLE|{SS-01}|{SS-03}`. Ordinary non-golden SS-39 is
`9000 + (the first two PRF digest bytes as an unsigned big-endian integer modulo 1000)`; golden
anchor rows use their explicit inventory index below. After every field override, SS-40 is DV-43
over the typed SS-01..SS-39 serialization. The BASE_100 V01/V02/DUP exception below then applies:
V01 uses its golden anchor index, V02 uses 9998, and DUP copies V01 byte-for-byte through SS-39.
Thus filler and diagnostic constructors are full SS-01..SS-40 rows, while the special ranking and
semantic-duplicate fixture remains unchanged.

### All 81 canonical golden observations

The following compact inventory lists every canonical `(SS-01,SS-03)` row; expanding every date
produces exactly 81 distinct observations:

| SS-01 | Exact SS-03 values |
|---|---|
| `SYN-SK-BASE_100` | 2026-08-03, 08-10, 08-17, 08-24, 08-31, 09-07 |
| `SYN-SK-REMOVE_200` | 2026-08-03 |
| `SYN-SK-ADD_300` | 2026-08-10, 08-17, 08-24, 08-31, 09-07 |
| `SYN-SK-SHIFT_OLD` | 2026-08-03, 08-10 |
| `SYN-SK-SHIFT_NEW` | 2026-08-17, 08-24, 08-31 |
| `SYN-SK-AMB_OLD` | 2026-08-03, 08-10, 08-17 |
| `SYN-SK-AMB_NEW_A` | 2026-08-24, 08-31 |
| `SYN-SK-AMB_NEW_B` | 2026-08-24, 08-31 |
| `SYN-SK-UNPAIR_OLD` | 2026-08-03, 08-10, 08-17, 08-24 |
| `SYN-SK-UNPAIR_NEW` | 2026-08-31 |
| `SYN-SK-STABLE_010` | 2026-08-03, 08-10, 08-17, 08-24, 08-31 |
| `SYN-SK-REAPPEAR_400` | 2026-08-03, 08-17, 08-24, 08-31 |
| `SYN-SK-PHY_BASE_700` | 2026-08-03, 08-10, 08-17, 08-24, 08-31 |
| `SYN-SK-PHY_BASE_701` | 2026-08-03, 08-10, 08-17, 08-24, 08-31 |
| `SYN-SK-MKT_COPY_702` | 2026-08-03, 08-10, 08-17, 08-24, 08-31 |
| `SYN-SK-CSH_ONLY_900` | 2026-08-03, 08-10, 08-17, 08-24, 08-31 |
| `SYN-SK-CLOCK_BOUNDARY_001` | 2026-08-03, 08-10, 08-17, 08-24, 08-31, 09-07 |
| `SYN-SK-MKT_ENTRY_714` | 2026-08-31 |
| `SYN-SK-MKT_EXIT_715` | 2026-08-03, 08-10, 08-17, 08-24 |
| `SYN-SK-CLOCK_SHADOW_001` | 2026-08-03, 08-10, 08-17, 08-24, 08-31, 09-07 |
| `SYN-SK-UNPAIR_MARKET_SHADOW` | 2026-08-03, 08-10, 08-17, 08-24, 08-31 |
| `SYN-SK-GAP_CONTROL_001` | 2026-10-05 |

Years omitted in the table are 2026. Golden SS-39 is 9000 plus the zero-based anchor-observation
index, and the universal lineage rule supplies SS-02/SS-40.

For `SYN-SK-BASE_100|2026-08-03`, emit two additional raw occurrences:

- V02 has SS-22=0 and SS-39=9998, so it ranks below the golden V01 row;
- DUP is byte-identical through SS-39 to V01 and therefore has the same SS-40 and increments the
  semantic duplicate occurrence count.

Raw input reorder must not change V01 selection or its hash.

### Snapshot calendar

| SC-01 | SC-02 | SC-03 | SC-04 | SC-05 smoke/demo | SC-06 |
|---|---|---|---|---|---|
| 2026-08-03 | true | true | `SC-20260803-COMPLETE` | 17 / 12017 | `COMPLETE_VALIDATED` |
| 2026-08-10 | true | true | `SC-20260810-COMPLETE` | 14 / 12014 | `COMPLETE_VALIDATED` |
| 2026-08-17 | true | true | `SC-20260817-COMPLETE` | 15 / 12015 | `COMPLETE_VALIDATED` |
| 2026-08-24 | true | true | `SC-20260824-COMPLETE` | 16 / 12016 | `COMPLETE_VALIDATED` |
| 2026-08-31 | true | true | `SC-20260831-COMPLETE` | 16 / 12016 | `COMPLETE_VALIDATED` |
| 2026-09-07 | true | true | `SC-20260907-COMPLETE` | 4 / 4 | `COMPLETE_VALIDATED` |
| 2026-10-05 | true | true | `SC-20261005-COMPLETE` | 1 / 1 | `COMPLETE_VALIDATED` |
| 2026-10-12 | false | false | `SC-20261012-MISSING` | 0 / 0 | `MISSING_DECLARED` |
| 2026-10-19 | true | false | `SC-20261019-INCOMPLETE` | 5 / 9917 | `INCOMPLETE_RETAINED` |
| 2026-10-26 | true | true | `SC-20261026-COMPLETE` | 0 / 0 | `COMPLETE_VALIDATED` |

Exactly the five August dates are Q05-eligible. October 5 is the immediate prior eligible complete
date for October 26. The missing and incomplete dates generate no absence event.

### Schedule filler isolation

Demo emits exactly 12,000 filler schedule keys `SYN-SK-FILL-{00000..11999}` at all five August
complete dates, for 60,000 rows. Each key's SS-04..SS-38 bytes are identical across the five dates.
Routes cycle through the nine whitelist without equal endpoints. Marketing and operating carriers
cycle through the disjoint exact-resolved pools `SYN-MKT-FILL-{00..15}` and
`SYN-OP-FILL-{00..15}`. For zero-based key index `i`, SS-06=`1700 + (i mod 100)`; `1700..1799` is
the declared non-golden schedule-filler number range and is disjoint from every anchored `700..799`
flight number. SS-10 is whitelist entry `i mod 9`; SS-11 is entry `(i+1) mod 9`, so endpoints are
always distinct. SS-08=`2035-01-01`, SS-09=`2035-12-31`; therefore every filler state is
operating-ineligible on `2026-09-07`. Stable presence at both Q06 endpoints prevents a market
zero-crossing, and stable content prevents a Q05 change.

Both scales include these five exact rows at the present-but-incomplete `2026-10-19` snapshot. They
start from the frozen common SS-04..SS-38 mapping, use SS-05=`SYN-OP-DIAG`, unique keys, and
SS-08=`2026-09-01`, SS-09=`2026-09-06`:

| SS-01 | SS-04 | SS-06 | SS-10 -> SS-11 | Exact SS-30..SS-34 or clock override | Owned truth row |
|---|---|---:|---|---|---|
| `SYN-SK-DIAG-TOTAL-MISMATCH` | `SYN-MKT-DIAG` (exact) | 790 | SFO -> LAX | 181 / 8 / 20 / 20 / 152 | TT28-R02 |
| `SYN-SK-DIAG-NULL-CABIN` | `SYN-ZZZ` (unresolved) | 791 | LAX -> LAS | 180 / null / 20 / 20 / 152 | TT28-R03 |
| `SYN-SK-DIAG-NEGATIVE-CABIN` | `SYN-DUP` (ambiguous) | 792 | SEA -> DEN | 180 / -1 / 20 / 20 / 152 | TT28-R04 |
| `SYN-SK-DIAG-PREMIUM-EXCEEDS` | null (invalid) | 793 | BOS -> MIA | 180 / 8 / 20 / 40 / 30 | TT28-R05 |
| `SYN-SK-UTC-UNRESOLVED` | `SYN-MKT-DIAG` (exact) | 794 | ORD -> MIA | SS-23=`23:00:00`, SS-24=`01:00:00`, SS-25=`23:00:00`, SS-26=`01:00:00`, SS-27=1 | TT25-R08 |

For the UTC diagnostic, `2026-09-07` is the fixture's separately supplied operating date used to
combine SS-25/SS-26 into local timestamps; the source still supplies no UTC date, expanded UTC
timestamp, or offset. SS-23/SS-24 remain lineage-only TIME values, so DV-51 is
`UNRESOLVED_UTC_DATE`. AP-09 must not repair it.

Demo adds exactly 9,912 more rows, for 9,917 total rows at `2026-10-19`, using unique
`SYN-SK-INCOMPLETE-{0000..9911}` keys. For index `i`, SS-06=`1800+(i mod 100)` in a second
declared non-golden range, SS-10 is whitelist entry `i mod 9`, SS-11 is the next entry, and SS-04/05
are `SYN-MKT-FILL-{i mod 16:02}`/`SYN-OP-FILL-{i mod 16:02}`; all other watched fields retain the
common defaults. All 9,917 are retained diagnostics but cannot open, close, add, remove, reappear,
or create a market event because SC-03 is false. The additional diagnostics have valid cabin
payloads, whitelisted routes, and disjoint synthetic carriers.

DATA-02 must independently materialize the 22 exact plus 13 evidence Q05 rows, the exact two Q06
zero-crossings, and the five Q07 rows from these source rows before it may write output files.

## Passenger source constructors

### Forward full template and nine smoke rows

The PF template sets PF-01 from the inventory; PF-02=`SYN-MKT-FUL`, PF-03=`SYN-OP-FUL`,
PF-04=700, PF-05=`2026-08-31`, PF-06=`2026-08-01`, PF-07=`J`, PF-08=`SFO`, PF-09=`LAX`,
PF-10=`2026-08-31T09:00:00`, PF-11=`2026-08-31T11:00:00`,
PF-12=`2026-08-31T16:00:00`, PF-13=`2026-08-31T18:00:00`, PF-14=0,
PF-15=`SYN-EQ-NB`, PF-16=180, PF-17=false, PF-18=0, and PF-19=null.

| PF-01 / token | PF-02 | PF-03 | PF-04 | PF-05 | PF-08 -> PF-09 | Special override |
|---|---|---|---:|---|---|---|
| 6001 | `SYN-MKT-A` | `SYN-OP-A` | 700 | 2026-08-31 | SFO -> LAX | union overlap with PH-5001 |
| 6002 | `SYN-MKT-A` | `SYN-OP-A` | 701 | 2026-08-31 | LAX -> LAS | forward-only; historical fields remain null |
| 6101 | `SYN-MKT-FUL` | `SYN-OP-FUL` | 722 | 2026-08-31 | SEA -> DEN | unique heuristic candidate |
| 6102 | `SYN-MKT-FUL` | `SYN-OP-FUL` | 723 | 2026-08-31 | BOS -> MIA | ambiguous candidate A |
| 6103 | `SYN-MKT-FUL` | `SYN-OP-FUL` | 723 | 2026-08-31 | ORD -> MIA | PF-18=1, PF-19=`BOS`; ambiguous B |
| 6199 | `SYN-MKT-FUL` | `SYN-OP-FUL` | 727 | 2026-08-31 | SFO -> null | stable invalid-key audit row |
| null / DV-43 `a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7` | `SYN-MKT-FUL` | `SYN-OP-FUL` | 726 | 2026-08-31 | MIA -> BOS | valid key; DV-46 hash fallback; not quarantined |
| null / `SYN-QUARANTINE-PF-HASH-01` | `SYN-MKT-FUL` | `SYN-OP-FUL` | 728 | 2026-08-31 | MIA -> null | invalid key and null ID; quarantined |
| 6201 | `SYN-MKT-CLOCK` | `SYN-OP-CLOCK` | 730 | 2026-09-07 | SFO -> LAX | PF-10/11=`2026-09-07T08:00:00`/`2026-09-07T10:00:00`; PF-12/13=`2026-09-07T15:00:00`/`2026-09-07T17:00:00`; expanded timestamps win |

The display token for the quarantined null-ID row is a fixture label only and is not a new source
column. Applying the normative frame above to the complete valid null-ID row yields the displayed
DV-43 and DV-46=
`FORWARD|a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7`.
`SYN-PAX-VALID-NULL-ID-01` is only that canonical passenger's presentation token; it is not a raw PF
field, DV-43 input, or DV-46 suffix.

### Historical full template and thirteen smoke rows

The PH template sets PH-01 from inventory; PH-02=null, PH-03=`2026-08-01`,
PH-04=`2026-08-31`, PH-05=`SYN-MKT-FUL`, PH-06=`SYN-OP-FUL`, PH-07=700,
PH-08=`J`, PH-09=`2026-08-01`, PH-10=`SFO`, PH-11=`LAX`, PH-12=`09:00:00`,
PH-13=`11:00:00`, PH-14=`16:00:00`, PH-15=`18:00:00`, PH-16=-420.0,
PH-17=-420.0, PH-18=0, PH-19=`SYN-EQ-NB`, PH-20=180.0, PH-21=false, PH-22=0,
and PH-23=null.

| PH-01 | PH-02 | PH-04 | PH-05/06 | PH-07 | PH-10 -> PH-11 | Special override |
|---:|---|---|---|---:|---|---|
| 5001 | `SYN-SK-HIST_700` | 2026-08-31 | `SYN-MKT-A` / `SYN-OP-A` | 700 | SFO -> LAX | wins PF-6001 overlap |
| 5101 | null | 2026-08-31 | `SYN-MKT-FUL` / `SYN-OP-FUL` | 720 | SFO -> LAX | exact AF-5101 |
| 5102 | null | 2026-08-31 | `SYN-MKT-FUL` / `SYN-OP-FUL` | 721 | SFO -> LAS | PH-22=1, PH-23=`LAX`; exact first leg |
| 5103 | null | 2026-08-31 | `SYN-MKT-FUL` / `SYN-OP-FUL` | 721 | SFO -> LAS | PH-22=1, PH-23=`LAX`; exact second leg; same canonical plan |
| 7200 | null | 2026-08-31 | `SYN-MKT-FUL` / `SYN-OP-FUL` | 725 | SFO -> LAX | exact diverted AF-7200 |
| 7301 | null | 2026-03-08 | `SYN-MKT-CLOCK` / `SYN-OP-CLOCK` | 731 | SFO -> LAX | local 01:30/01:55, offsets -480/-480 |
| 7302 | null | 2026-03-08 | `SYN-MKT-CLOCK` / `SYN-OP-CLOCK` | 732 | SFO -> LAX | local 03:30/03:55, offsets -420/-420 |
| 7303 | null | 2026-11-01 | `SYN-MKT-CLOCK` / `SYN-OP-CLOCK` | 733 | BOS -> MIA | local 01:30/01:50, offsets -240/-240 |
| 7304 | null | 2026-11-01 | `SYN-MKT-CLOCK` / `SYN-OP-CLOCK` | 734 | BOS -> MIA | local 01:30/01:50, offsets -300/-300 |
| 7305 | null | 2026-07-15 | `SYN-MKT-CLOCK` / `SYN-OP-CLOCK` | 735 | PHX -> DEN | local 12:00/13:00, offsets -420/-420 |
| 7306 | null | 2026-09-07 | `SYN-MKT-CLOCK` / `SYN-OP-CLOCK` | 736 | SFO -> LAX | local 23:30/01:15, PH-18=1, offsets -420/-420 |
| 7309 | null | 2026-09-07 | `SYN-MKT-UNIT` / `SYN-OP-UNIT` | 739 | ORD -> DEN | local 12:00/14:00, offsets 0/0; non-operational unit case |
| 7310 | null | 2026-09-07 | `SYN-MKT-UNIT` / `SYN-OP-UNIT` | 740 | SFO -> LAX | local 23:30/01:15, PH-18=1, offsets +120/+120; non-operational unit case |

PH-14/15 equal the time components of the frozen TT-UTC-OFFSETS UTC values: 7301=`09:30/09:55`,
7302=`10:30/10:55`, 7303=`05:30/05:50`, 7304=`06:30/06:50`, 7305=`19:00/20:00`,
7306=`06:30/08:15`, 7309=`12:00/14:00`, and 7310=`21:30/23:15`. These TIME values are retained
for lineage, but dated timestamps are derived only from PH-16/17 under D-0008. Null or non-finite
offsets yield unresolved status; no AP-09 repair is allowed.

Clock construction is explicit: DV-47 is `PH-04 + PH-12`; DV-48 is
`PH-04 + PH-18 calendar days + PH-13`; D-0008 defines
`offset_minutes = local - UTC`, so DV-49/DV-50 subtract PH-16/PH-17 minutes from DV-47/DV-48.
The two March SFO rows and two November BOS rows supply the distinct pre/post DST offsets directly;
the PHX row supplies -420 explicitly and does not infer a no-DST rule from AP-09. PF-12/PF-13 are
already expanded timestamps and win without recomputation. SS-23/SS-24 remain UTC TIME lineage only
and never gain a date from clock ordering or AP-09.

Demo PF filler has zero-based indices `i=0..9990` (9 anchors + 9,991 filler = 10,000). Let
`c=i mod 16`, `f=floor(i/16) mod 100`, and `d=floor(i/1600)`. Override the full template with
PF-02=`SYN-MKT-FILL-{c:02}`, PF-03=`SYN-OP-FILL-{c:02}`, PF-04=`2700+f`,
PF-05=`2035-01-01+d days`, PF-06=`2034-12-01`, PF-08=whitelist entry `d mod 9`, and PF-09=the next
whitelist entry. PF-10/11 are 09:00/11:00 on PF-05; PF-12/13 are 16:00/18:00 on PF-05. This
mixed-radix mapping makes every canonical key unique. Assign the first 2,993 rows the ascending
available PF-01 values in `5000..7999` excluding the seven non-null anchors; the remaining 6,998
have PF-01=null and remain stable because their full-row DV-43 values differ.

Demo PH filler similarly has `i=0..9986` (13 anchors + 9,987 filler = 10,000), with the same `c/f/d`
decomposition and PH-05/06=`SYN-MKT-FILL-{c:02}`/`SYN-OP-FILL-{c:02}`, PH-07=`2800+f`,
PH-04=`2036-01-01+d days`, PH-03=`2035-12-01`, PH-09=`2036-01-01`, and adjacent whitelisted
PH-10/11. PH-12/13=`09:00/11:00`, PH-14/15=`09:00/11:00`, PH-16/17=0, and PH-18=0. Assign the
first 2,987 rows ascending available PH-01 values in `5000..7999` excluding the thirteen anchors and set the
remaining 7,000 IDs null. PF/PH filler carrier/date/flight domains are disjoint from every golden
combination and from one another. No filler actual leg has a compatible date, so no exact or
heuristic fulfillment evidence can be added.

## Actual-flight constructors

The AF template sets AF-01 from inventory, AF-02=1100, AF-03=`SYN-OP-FUL`,
AF-04=`SYN-MKT-FUL`, AF-05=`700`, AF-06=`2026-08-31`, AF-07=`2026-08-31`,
AF-08=`SYN-AP-SFO`, AF-09=`SYN-AP-LAX`, AF-10=null, AF-11=0, AF-12=0,
AF-13=`2026-08-31T14:00:00`, AF-14=`2026-08-31T15:00:00`, AF-15=null,
AF-16=null, AF-17=`Synthetic narrowbody B`, AF-18=`SB1`, AF-19=`SYN-FAMILY-B`, and
AF-20=null.

The 24 smoke rows are the seven fulfillment rows, three clean-rotation rows, and fourteen anomaly
source/target rows below.

| AF-01 | AF-02 | AF-05 | AF-06 / AF-07 | AF-08 -> AF-09 | AF-13 -> AF-14 | AF-20 | Override/purpose |
|---:|---:|---|---|---|---|---:|---|
| 5101 | 1100 | `720` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 14:00 -> 15:30 | null | exact direct fulfillment |
| 5102 | 1100 | `721` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 14:00 -> 15:30 | null | exact stopover leg 1 |
| 5103 | 1100 | `721` | 2026-08-31 / 2026-08-31 | LAX -> LAS | 16:00 -> 17:00 | null | exact stopover leg 2 |
| 7101 | 1100 | `722` | 2026-08-31 / 2026-08-31 | SEA -> DEN | 14:00 -> 17:00 | null | unique heuristic candidate |
| 7102 | 1100 | `723` | 2026-08-31 / 2026-08-31 | BOS -> MIA | 14:00 -> 17:00 | null | ambiguous candidate |
| 7199 | 1100 | `724` | 2026-08-31 / 2026-08-31 | ORD -> PHX | 14:00 -> 17:00 | null | unmatched actual |
| 7200 | 1100 | `725` | 2026-08-31 / 2026-08-31 | SFO -> LAS | 14:00 -> 16:00 | null | AF-10=LAS, AF-12=1; valid diversion |
| 8001 | 1001 | `741` | 2026-08-31 / 2026-09-01 | SFO -> LAX | 2026-09-01 00:30 -> 02:00 | 8002 | clean rotation; source type B |
| 8002 | 1001 | `742` | 2026-08-31 / 2026-09-01 | LAX -> LAS | 2026-09-01 02:45 -> 04:00 | 8003 | AF-17=`Synthetic narrowbody A`; source discrepancy |
| 8003 | 1001 | `743` | 2026-08-31 / 2026-09-01 | LAS -> SFO | 2026-09-01 04:45 -> 06:15 | null | clean terminal; source type B |
| 8101 | 1099 | `751` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 14:00 -> 15:00 | 8101 | SELF_LOOP |
| 8102 | 1099 | `752` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 14:00 -> 15:00 | 8103 | CYCLE with 8103 |
| 8103 | 1099 | `753` | 2026-08-31 / 2026-08-31 | LAX -> SFO | 16:00 -> 17:30 | 8102 | cycle target |
| 8104 | 1099 | `754` | 2026-08-31 / 2026-08-31 | SEA -> DEN | 15:00 -> 18:00 | 8999 | MISSING_TARGET; 8999 absent |
| 8105 | 1099 | `755` | 2026-08-31 / 2026-08-31 | LAX -> LAS | 16:00 -> 17:00 | 8205 | DIFFERENT_AIRCRAFT |
| 8106 | 1099 | `756` | 2026-08-31 / 2026-08-31 | LAS -> SFO | 18:00 -> 19:30 | 8206 | OUTSIDE_SELECTED_DAY |
| 8107 | 1099 | `757` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 20:00 -> 21:30 | 8101 | BACKWARD_TIME |
| 8108 | 1099 | `758` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 14:00 -> 15:30 | 8107 | BROKEN_CONTINUITY |
| 8109 | 1099 | `759` | 2026-08-31 / 2026-08-31 | SFO -> LAS | 14:00 -> 16:00 | 8106 | AF-10=LAX, AF-12=1; DIVERSION_ENDPOINT_CONFLICT |
| 8110 | 1099 | `760` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 14:00 -> 15:30 | null | AF-11=1; CANCELLED |
| 8111 | 1099 | `761` | 2026-08-31 / 2026-08-31 | SFO -> LAX | null -> null | null | MISSING_TIME |
| 8112 | 1099 | `762` | 2026-08-31 / 2026-08-31 | SFO -> LAX | 22:00 -> 23:30 | null | AF-11=2; invalid cancellation flag |
| 8205 | 1098 | `765` | 2026-08-31 / 2026-08-31 | LAX -> LAS | 18:00 -> 19:00 | null | different-aircraft target |
| 8206 | 1099 | `766` | 2026-09-01 / 2026-09-01 | SFO -> LAX | 15:00 -> 16:30 | null | outside-day target |

Endpoint abbreviations in this table expand to `SYN-AP-*`. Timestamp-only times inherit the row's
date. All fulfillment rows use exact-resolved `SYN-OP-FUL`/`SYN-MKT-FUL`. Rotation rows use
`SYN-OP-ROT`/`SYN-MKT-ROT`. Anomaly precedence is exactly the frozen manifest order; one CYCLE row
is emitted at minimum member 8102.

AF-06 is always the source-local selected-day basis; AF-07 is UTC-date lineage and never substitutes
for AF-06. Thus AF-8001..8003 are selected by AF-06=`2026-08-31` even though each has
AF-07=`2026-09-01` and UTC timestamps on September 1. A target with a different AF-06 terminates the
selected-day link as `OUTSIDE_SELECTED_DAY`.

Demo has 3,876 AF filler rows after the 24 anchors. Assign the first 3,876 ascending available AF-01
values in `5000..8998` excluding anchors; AF-8999 is explicitly reserved and absent. For filler
index `i`, AF-02 is sorted filler aircraft `a_(i mod 993)`, AF-03/04 are
`SYN-OP-FILL-{i mod 16:02}`/`SYN-MKT-FILL-{i mod 16:02}`, AF-05 is the string form of
`3700+(i mod 100)`, AF-06=AF-07=`2040-01-01+floor(i/100) days`, AF-08 is whitelist internal ID
`i mod 9`, AF-09 is the next whitelist internal ID, AF-13/14 are 09:00/11:00 on AF-06, and AF-20 is
null. Every other field comes from the full template. These aircraft/date/flight combinations are
disjoint from golden Q08 and every passenger key, so filler creates no fulfillment evidence.

## Complete result-set ownership

All 24 result sets are owned below. A row range names only manifest rows; the detailed input-row
owner for every nonempty row is in the following 253-row map. Empty sets are expected typed API
outcomes, not missing fixtures.

| Result-set ID | Expected rows | Constructor or boundary owner |
|---|---|---|
| `Q01-CANONICAL` | Q01-R001 | AM/AH/AC 1001 |
| `Q01-BEFORE-FIRST` | Q01-R002 | AM-1004 and first AH-104001 after requested date |
| `Q01-UNKNOWN-GAP` | Q01-R003 | AH-102004 plus absent configuration definition |
| `Q01-EOL-BOUNDARY` | Q01-R004 | AM-1002 exclusive AM-08 boundary |
| `Q01-INVALID-AIRCRAFT-ID` | empty | negative typed parameter; no numeric-namespace match |
| `Q02-CANONICAL` | Q02-R001..002 | AH-1001 status events |
| `Q02-NO-SPELLS` | empty | AM-1004/AH-104001 never enters `Storage` |
| `Q03-CANONICAL` | Q03-R001..132 | AM/AH/AC 1001/1002; no pre-2025 filler |
| `Q04-CANONICAL` | Q04-R001..004 | AH/AC 1001 configuration history |
| `Q05-CANONICAL` | Q05-R001..035 | 81 canonical SS rows plus five eligible August SC rows |
| `Q05-INELIGIBLE-ENDPOINT` | empty | SC 2026-10-12 missing and 2026-10-19 incomplete |
| `Q06-CANONICAL` | Q06-R001..002 | MKT_ENTRY/MKT_EXIT plus market-protection shadows |
| `Q06-INCOMPLETE-ENDPOINT` | empty | SC 2026-10-19 incomplete gate |
| `Q06-MISSING-CARRIER-ROLE` | empty | null typed role parameter gate |
| `Q06-INVALID-DATE` | empty | invalid 2026-02-30 parameter gate |
| `Q07-MARKETING` | Q07-R001,R002,R005 | four capacity keys at knowledge/operating clocks |
| `Q07-OPERATING` | Q07-R003..004 | four capacity keys at knowledge/operating clocks |
| `Q07-KNOWLEDGE-END-EMPTY` | empty | capacity keys absent at complete 2026-09-07 snapshot |
| `Q07-MISSING-KNOWLEDGE-DATE` | empty | null typed knowledge-date gate |
| `Q07-MISSING-OPERATING-DATE` | empty | null typed operating-date gate |
| `Q07-MISSING-CARRIER-ROLE` | empty | null typed role gate |
| `Q08-CANONICAL` | Q08-R001..003 | AF-8001..8003 plus date-visible AH/AC-1001 |
| `Q08-ANOMALIES` | Q08-R004..014 | AF anomaly rows, targets, and absent AF-8999 |
| `Q08-NOT-FOUND` | empty | AM-1999 exists in demo, but no AF-1999/selected-day leg; smoke has no matching aircraft or AF row |

## Expected-row ownership

The following YAML-like ownership map is normative. DATA-02 expands `start..end` inclusive with the
declared width and MUST prove that the expansion owns exactly the 253 unique row IDs in
`EXPECTED_ANSWERS.yaml`, once each and no more. Empty/error result sets own no row and are validated
by their typed invocation outcome.

```yaml
expected_row_ownership:
  - {ids: [Q01-R001], source: [AM-1001, AH-101001, AH-101005, AH-101007, AH-101011, AH-101024, AC-2003]}
  - {ids: [Q01-R002], source: [AM-1004, AH-104001]}
  - {ids: [Q01-R003], source: [AM-1002, AH-102002, AH-102004, AH-102005]}
  - {ids: [Q01-R004], source: [AM-1002]}
  - {range: {prefix: Q02-R, start: 1, end: 2, width: 3}, source: [AH-101003, AH-101004, AH-101008, AH-101009, AH-101010, AH-101011]}
  - {range: {prefix: Q03-R, start: 1, end: 12, width: 3}, source: [AM-1001, AH-101001, AC-2001], rule: one_Type_A}
  - {range: {prefix: Q03-R, start: 13, end: 38, width: 3}, source: [AM-1001, AM-1002, AH-101001, AH-102001, AC-2001], rule: two_Type_A}
  - {ids: [Q03-R039], source: [AH-101003, AH-102001, AC-2001], rule: aircraft_1001_in_storage}
  - {range: {prefix: Q03-R, start: 40, end: 48, width: 3}, source: [AH-101004, AH-102001, AC-2001], rule: two_Type_A}
  - {range: {prefix: Q03-R, start: 49, end: 72, width: 3}, source: [AH-101005, AH-102001, AC-2001, AC-2002], rule: alternating_A_1002_then_B_1001_each_month}
  - {range: {prefix: Q03-R, start: 73, end: 132, width: 3}, source: [AH-101005, AH-102002, AC-2002], rule: one_Type_B_1001}
  - {ids: [Q04-R001], source: [AH-101001, AH-101005, AC-2001]}
  - {ids: [Q04-R002], source: [AH-101005, AC-2002]}
  - {ids: [Q04-R003], source: [AH-101001, AH-101005, AH-101007, AC-2001, AC-2002]}
  - {ids: [Q04-R004], source: [AH-101007, AC-2003]}
  - {range: {prefix: Q05-R, start: 1, end: 35, width: 3}, source: [SS-81-golden-observations, SC-five-August-complete-dates, CROSS-QUESTION-EVENT-CLOSURE-V1.1], rule: row_id_to_schedule_key_and_transition_in_EXPECTED_ANSWERS}
  - {ids: [Q06-R001], source: [SS-SYN-SK-MKT_ENTRY_714, SC-20260824, SC-20260831]}
  - {ids: [Q06-R002], source: [SS-SYN-SK-MKT_EXIT_715, SC-20260824, SC-20260831]}
  - {ids: [Q07-R001], source: [SS-SYN-SK-PHY_BASE_700, SS-SYN-SK-PHY_BASE_701, SC-20260831, SC-20260907]}
  - {ids: [Q07-R002], source: [SS-SYN-SK-MKT_COPY_702, SC-20260831, SC-20260907]}
  - {ids: [Q07-R003], source: [SS-SYN-SK-PHY_BASE_700, SS-SYN-SK-PHY_BASE_701, SC-20260831, SC-20260907]}
  - {ids: [Q07-R004], source: [SS-SYN-SK-CSH_ONLY_900, SC-20260831, SC-20260907]}
  - {ids: [Q07-R005], source: [SS-SYN-SK-CSH_ONLY_900, SC-20260831, SC-20260907]}
  - {ids: [Q08-R001], source: [AF-8001, AH-101007, AC-2003]}
  - {ids: [Q08-R002], source: [AF-8002, AH-101007, AC-2003]}
  - {ids: [Q08-R003], source: [AF-8003, AH-101007, AC-2003]}
  - {ids: [Q08-R004], source: [AF-8101]}
  - {ids: [Q08-R005], source: [AF-8102, AF-8103]}
  - {ids: [Q08-R006], source: [AF-8104, absent-AF-8999]}
  - {ids: [Q08-R007], source: [AF-8105, AF-8205]}
  - {ids: [Q08-R008], source: [AF-8106, AF-8206]}
  - {ids: [Q08-R009], source: [AF-8107, AF-8101]}
  - {ids: [Q08-R010], source: [AF-8108, AF-8107]}
  - {ids: [Q08-R011], source: [AF-8109, AF-8106]}
  - {ids: [Q08-R012], source: [AF-8110]}
  - {ids: [Q08-R013], source: [AF-8111]}
  - {ids: [Q08-R014], source: [AF-8112]}
  - {range: {prefix: TT23-R, start: 1, end: 9, width: 2}, source: [SS-SYN-SK-CLOCK_BOUNDARY_001, SC-20260824, SC-20260831]}
  - {range: {prefix: TT25-R, start: 1, end: 6, width: 2}, source: [PH-7301..PH-7306], rule: TT25-Rnn_maps_to_PH-(7300+nn)}
  - {ids: [TT25-R07], source: [PF-6201]}
  - {ids: [TT25-R08], source: [SS-SYN-SK-UTC-UNRESOLVED-at-incomplete-20261019]}
  - {ids: [TT25-R09], source: [PH-7309]}
  - {ids: [TT25-R10], source: [PH-7310]}
  - {ids: [TTUS-R01], source: [PF-6201, AP-SYN-AP-SFO]}
  - {ids: [TTUS-R02], source: [PH-7303, AP-SYN-AP-BOS]}
  - {ids: [TTUS-R03], source: [SS-SYN-SK-UTC-UNRESOLVED, AP-SYN-AP-ORD]}
  - {ids: [TTUS-R04], source: [PH-7305, AP-SYN-AP-PHX]}
  - {ids: [TTUS-R05], source: [AF-8001, AP-SYN-AP-SFO]}
  - {ids: [TT28-R01], source: [SS-SYN-SK-PHY_BASE_700-at-20260831]}
  - {ids: [TT28-R02], source: [SS-SYN-SK-DIAG-TOTAL-MISMATCH-at-20261019]}
  - {ids: [TT28-R03], source: [SS-SYN-SK-DIAG-NULL-CABIN-at-20261019]}
  - {ids: [TT28-R04], source: [SS-SYN-SK-DIAG-NEGATIVE-CABIN-at-20261019]}
  - {ids: [TT28-R05], source: [SS-SYN-SK-DIAG-PREMIUM-EXCEEDS-at-20261019]}
  - {ids: [TT38-R01], source: [AP-SYN-AP-SFO, AL-SYN-MKT-DIAG], rule: exact_in_each_domain}
  - {ids: [TT38-R02], source: [raw-SYN-ZZZ, absent-AP-SYN-ZZZ, absent-AL-SYN-ZZZ], rule: unresolved_in_each_domain}
  - {ids: [TT38-R03], source: [AP-SYN-AP-DUP-A, AP-SYN-AP-DUP-B, AL-SYN-MKT-DUP-A, AL-SYN-MKT-DUP-B], rule: ambiguous_in_each_domain}
  - {ids: [TT38-R04], source: [null-airport-raw-code, null-airline-raw-code], rule: invalid_in_each_domain}
  - {ids: [TT12-R01], source: [SC-20261005, SC-20261012, SS-SYN-SK-GAP_CONTROL_001]}
  - {ids: [TT12-R02], source: [SC-20261005, SC-20261019, SS-SYN-SK-GAP_CONTROL_001]}
  - {ids: [TT13-R01], source: [SC-20261005, SC-20261012, SC-20261019, SC-20261026, SS-SYN-SK-GAP_CONTROL_001]}
  - {ids: [TT15-R01], source: [SC-20260810, SC-20260817, SS-SYN-SK-REAPPEAR_400]}
  - {ids: [TT30-R01], source: [PH-5001, PF-6001]}
  - {ids: [TT30-R02], source: [PF-6002]}
  - {ids: [TT32-R01], source: [PH-5101, AF-5101]}
  - {ids: [TT32-R02], source: [PF-6101, AF-7101]}
  - {ids: [TT32-R03], source: [PH-5102, AF-5102]}
  - {ids: [TT32-R04], source: [PH-5103, AF-5103]}
  - {ids: [TT32-R05], source: [PF-6102, PF-6103, AF-7102]}
  - {ids: [TT32-R06], source: [AF-7199]}
  - {ids: [TT32-R07], source: [PF-6199]}
  - {ids: [TT32-R08], source: [PF-null-quarantine]}
  - {ids: [TT32-R09], source: [PF-6102, AF-7102]}
  - {ids: [TT32-R10], source: [PF-6103, AF-7102]}
  - {ids: [TT32-R11], source: [PF-null-valid-DV43-a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7]}
  - {ids: [TT33-R01], source: [PH-7200, AF-7200]}
  - {ids: [TT06-R01], source: [AH-102099]}
  - {ids: [TT06-R02], source: [AM-1004, AH-104001]}
  - {ids: [TT09-R01], source: [AM-1002]}
  - {ids: [TT40-R01], source: [AM-1005, AH-105001, AC-2005]}
```

For Q05, the expanded IDs are additionally checked individually against
`cross_question_event_closure.q05_rows_by_adjacent_pair` and
`exact_presence_partner_closure`; a single range does not permit an unvalidated generic owner.

## Negative-fixture, P0, hard-test, and derived-field ownership

| Frozen owner | Concrete source ownership |
|---|---|
| NF-A01 | AH 101020..101024; irrelevant event, null/value transitions, final-per-day control. |
| NF-A02 | AH 101003/101004/101008..101011. |
| NF-A03 | AH 101001/101005/101007 plus AC 2001..2003. |
| NF-A04 | AH 102004/102005 and deliberately absent AC null/999999; left preservation and loss count. |
| NF-A05 | AM 1002/1004 and AH 102099/104001; existence, finite/open EOL, source sentinel/provenance. |
| NF-S01 | three raw BASE_100/2026-08-03 occurrences, V01/V02/DUP. |
| NF-S02 | all five unchanged STABLE_010 August observations. |
| NF-S03 | SC October 5/12/19/26 and GAP_CONTROL_001. |
| NF-S04 | REAPPEAR_400 August presence map. |
| NF-S05 | BASE/REMOVE/ADD/SHIFT/AMB/UNPAIR keys and market shadow. |
| NF-S06 | PHY_BASE_700/701 and MKT_COPY_702 concurrent states. |
| NF-S07 | four capacity keys and exact carrier references. |
| NF-S08 | PHY_BASE_700 plus four incomplete-snapshot cabin diagnostics. |
| NF-S09 | CLOCK_BOUNDARY_001 plus CLOCK_SHADOW_001. |
| NF-S10 | PH 7301..7306/7309/7310, PF 6201, and UTC-unresolved SS diagnostic. |
| NF-F01 | PH 5001 and PF 6001/6002. |
| NF-F02 | PH 5101..5103/7200, PF 6101..6103/6199/two null-ID cases, and AF fulfillment rows. |
| NF-R01 | AF 8001..8003/8101..8112/8205/8206 and deliberate absence 8999. |
| NF-R02 | AF 8002 versus AH/AC date-visible B/B. |
| NF-X01 | AP exact/two SYN-DUP/missing SYN-ZZZ/null controls plus AL exact/two SYN-DUP/missing SYN-ZZZ/null controls; domains resolve independently. |
| NF-X02 | AM 1005, AH 105001, AC 2005. |
| NF-E01 | clean smoke/demo generation, reordered input, identical rerun, and later cold/warm/CDC labels. |

P0 and HT ownership is exhaustive:

| Rules/tests | Input constructors |
|---|---|
| P0-01 / HT-01..04 | AM/AH anchors 1001 and NF-A01/A02. |
| P0-02 / HT-05..07 | AH daily/audit rows, AM finite/open bounds, SS knowledge transitions, AH-06 102099. |
| P0-03 / HT-08..10 | AM 1002/1004 plus their histories. |
| P0-04 / HT-11 | Complete AM/AH/AC/SS/SC/PF/PH/AF/AP/AL templates; 195/195 fields. |
| P0-05 / HT-12..15 | SC ten-date calendar, GAP_CONTROL_001, REAPPEAR_400. |
| P0-06 / HT-16..18 | NF-S01/S02 and concurrent capacity keys. |
| P0-07 / HT-19..22 | 81 SS anchor rows and v1.1 exact/evidence closure. |
| P0-08 / HT-23..25 | CLOCK_BOUNDARY/SHADOW, PH/PF clock rows, UTC-unresolved SS row. |
| P0-09 / HT-26..29 | Four capacity keys, carrier refs, cabin diagnostic rows, two market keys/shadows. |
| P0-10 / HT-30..33 | PF/PH union and fulfillment anchors plus AF 7200 diversion. |
| P0-11 / HT-34..37 | AF clean/anomaly rows and AH/AC 1001 enrichment. |
| P0-12 / HT-38..40 | AP/AL resolution controls, AH missing config, AC mixed definition. |
| P0-13 / HT-41..43 | Physical source rows and deterministic hashes; live/model gates remain downstream. |
| P0-14 / HT-44..46 | Exact scale/count/version metadata and self-contained aircraft anchor subset. |
| P0-15 / HT-47..49 | Typed empty/error invocations plus exact/candidate/ambiguous/unpaired and plan/actual fixtures. |

Derived-field ownership is also closed:

- DV-01..09 and DV-33: AM/AH/AC aircraft constructors;
- DV-10..11: AP/AL rows and every raw code context;
- DV-12..19, DV-26..31, DV-34..37, and schedule DV-43/DV-46: SS/SC constructors;
- DV-20..23, DV-38..44, passenger DV-43/DV-46, and DV-47..51: PF/PH plus fulfillment AF rows;
- DV-24..25, DV-32, DV-45, and DV-52..53: AF constructors; and
- DV-44 quarantine cases: PF invalid/null-ID and any downstream non-golden quality filler explicitly
  labeled by closed reason code.

No DATA-02 field outside SOURCE_CONTRACT or DV-01..53 may become a modeled semantic field.

## Mandatory filler-isolation assertions

Before writing either scale, DATA-02 must prove:

1. all filler aircraft existence/status/type begins after `2024-12-31`;
2. no filler row uses aircraft IDs 1001/1002/1004/1005/1098/1099;
3. all 12,000 August schedule filler keys are present at all five endpoints with byte-identical
   SS-04..SS-38, exact-resolved disjoint carriers, and whitelisted unequal endpoints;
4. no schedule filler operates on `2026-09-07`;
5. every 10/19 diagnostic is ineligible because SC-03=false and creates zero absence-derived facts;
6. filler AP/AL aliases have empty intersection with every golden raw code;
7. PF/PH/AF filler key/date/carrier sets have empty compatibility intersections and do not use
   golden aircraft/date selections;
8. AF-8999 is absent in both scales and no filler key or reference materializes it;
9. every non-SC golden source row is byte-identical between scales; SC-01..04/06 are identical while
   SC-05 equals the scale-specific raw count; all 253 expected-row ownership hashes are identical;
10. Q03 recomputes exactly 132 rows over exactly 120 month ends;
11. Q05 recomputes exactly 35 rows with adjacent counts 7/5/9/14 and 13/13 presence closure;
12. Q06 has exactly two zero-crossings and Q07 has exactly five canonical rows; and
13. every named route has two whitelist endpoints, every named actual endpoint is `SYN-AP-*`, every
    AM-09/AH-23/AH-25 aircraft airport code is whitelisted, every non-null AH-22 aircraft location is
    a matching whitelist `SYN-AP-*` identity, and every non-airport identity is visibly synthetic or
    inside the frozen numeric range.

## Failure, rollback, and handoff

Generation is fail-closed. A count, key, type, hash, ownership, endpoint, filler-isolation, or
expected-result mismatch produces no publishable manifest and leaves the task red. Expected answers
must not be edited to accommodate generator output.

The rollback for any DATA-02 implementation is deletion of its generated output directory followed
by regeneration from this specification; source contracts and frozen expectations are untouched.
`smoke` is the safe reduced input and contains the complete UC1 fallback plus every semantic fixture.
Changing D-0008's offset sign, D-0003's EOL boundary, or D-0010/D-0011 schedule closure requires a
new reviewed decision and expected-manifest supersession before this specification can change.

No Snowflake mutation is part of DATA-01 or DATA-02 generation. DATA-03 alone may load the verified
files, using the scoped demo role and database.
