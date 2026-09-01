# Decision log

Append-only record for choices made during autonomous development. A decision can be provisional;
uncertainty must never be erased or disguised as customer-confirmed semantics.

Each new entry contains: ID/time, triggering task, question, alternatives, evidence, independent
review, chosen treatment, confidence, affected artifacts/tests, rollback, and status. Supersede an
entry with a new entry rather than editing its historical conclusion.

## D-0001 — Target account interpretation

- **Date:** 2026-09-01
- **Trigger:** infrastructure bootstrap
- **Question:** Does “Shares engineering” refer to the configured Sales Engineering account?
- **Alternatives:** wait for another account name; use the only live verified SE account.
- **Evidence:** Snowflake connection `rai` resolves to organization `NDSOEBE`, account
  `RAI_SALES_ENGINEERING_AWS_US_WEST_2`, locator `AJB85638`; the account contains the RAI Native App,
  `RAI_XS`, and Snowflake Intelligence prerequisites.
- **Review:** independent live-account audit found the long account-named profile invalid and the
  short `rai` profile healthy.
- **Decision:** use the verified Sales Engineering account and record the interpretation explicitly.
- **Confidence:** high
- **Tests:** `data/bootstrap_verification.sql`
- **Rollback:** point the configuration at a user-specified account and rerun G0 before any further
  Snowflake mutation.
- **Status:** accepted provisionally; visible to the user.

## D-0002 — GitHub repository namespace

- **Date:** 2026-09-01
- **Trigger:** repository publication
- **Question:** Which namespace should own the private remote when no organization was specified?
- **Alternatives:** authenticated personal namespace; infer an organization; leave local only.
- **Evidence:** GitHub CLI is authenticated as `pkarus` with private repository scope; no target
  organization was requested.
- **Review:** inferring an organization would expand scope and may require different governance.
- **Decision:** create `pkarus/aviation-temporal-demo` as private. Repository transfer remains
  available if an organization is later selected.
- **Confidence:** high
- **Tests:** `gh repo view` reports `isPrivate: true`; SSH push to `origin/main` succeeded.
- **Rollback:** transfer the repository or replace `origin` after explicit owner selection.
- **Status:** executed; private remote is `git@github.com:pkarus/aviation-temporal-demo.git`.

## D-0003 — Aircraft end-of-life boundary

- **Date:** 2026-09-01
- **Trigger:** SPEC-01
- **Question:** Is `AIRCRAFT_END_OF_LIFE_DATE` inclusive or exclusive for as-of reconstruction?
- **Alternatives:** inclusive terminal day; exclusive half-open boundary; leave unspecified.
- **Evidence:** The source describes an end-of-life date but does not define terminal-day
  inclusivity. All modeled validity uses half-open intervals, and source `9999-12-31` means unknown
  future rather than a finite bound.
- **Review:** Independent SPEC-01 review confirmed that an explicit boundary and rollback test are
  required and found the exclusive treatment coherent and testable.
- **Decision:** Treat a real end-of-life date as exclusive:
  `existence_from <= date < end_of_life_date`. Null or source-sentinel EOL maps to an open model
  interval.
- **Confidence:** medium; binding for this release but not customer-confirmed.
- **Affected artifacts/tests:** `SEMANTIC_DECISIONS.md` P0-03; HT-05 and HT-08 through HT-10; all
  aircraft as-of queries.
- **Rollback:** If authoritative clarification makes the terminal day inclusive, normalize to
  `end_of_life_date + 1 day`, update frozen fixtures, and rerun the named tests and every aircraft
  as-of oracle.
- **Status:** accepted provisionally for the release.

## D-0004 — Same-day audit sequence versus date-visible state

- **Date:** 2026-09-01
- **Trigger:** SPEC-01
- **Question:** Which same-day aircraft observation is visible to a calendar-date as-of query when
  no intraday effective timestamp exists?
- **Alternatives:** first event; last event; zero-width intervals for every event; separate audit and
  daily projections.
- **Evidence:** The source provides event date and deterministic sequence but no intraday effective
  timestamp. Multiple same-day transitions must remain auditable, including `A -> B -> A`, while a
  date-level query requires one unambiguous value.
- **Review:** Independent review required explicit interval ownership and confirmed the final design:
  audit observations have no date interval; the final-per-day projection owns half-open as-of
  intervals.
- **Decision:** Preserve every event-ordered audit observation for sequence/spell analysis. Use the
  final relevant observation per aircraft, dimension, and date for date-visible state. Same-day
  status reversions remain audit spells with zero calendar-day duration.
- **Confidence:** high under the supplied date-grain source.
- **Affected artifacts/tests:** `SEMANTIC_DECISIONS.md` P0-01/P0-02; NF-A01/NF-A02; HT-01 through
  HT-05.
- **Rollback:** If authoritative intraday effective timestamps become available, evaluate visibility
  at timestamp grain while preserving stable audit identities, then rerun HT-01 through HT-05 and
  status/as-of oracles.
- **Status:** accepted provisionally for the release.

## D-0005 — Temporal treatment of APU, dimensions, and weights

- **Date:** 2026-09-01
- **Trigger:** SPEC-01
- **Question:** Should APU, aircraft-level dimensions, and weights be immutable identity attributes
  or temporal state?
- **Alternatives:** always immutable; always temporal; use source-lineage-specific treatment.
- **Evidence:** The requirements contain conflicting prose, while the event-history/change-detection
  description treats these groups as potentially changing. Projecting a current master value
  backward would fabricate history.
- **Review:** Independent review found the lineage-specific treatment complete and testable,
  provided SPEC-02 assigns every reduced column exactly one owner and temporal treatment.
- **Decision:** Version historically observed values in `aircraft_state`. Treat master-only copies as
  `CURRENT_ONLY` and prohibit them from historical as-of reconstruction.
- **Confidence:** medium pending exact field-level source inventory.
- **Affected artifacts/tests:** `SEMANTIC_DECISIONS.md` P0-04; HT-11; aircraft reconstruction and
  attribute-authority contracts.
- **Rollback:** Move a field only when authoritative lineage proves immutability or supplies history;
  update the authority matrix and frozen manifest, then rerun HT-11 and every affected reconstruction
  oracle.
- **Status:** accepted provisionally for the release.

## D-0006 — Schedule-key-changing amendments

- **Date:** 2026-09-01
- **Trigger:** SPEC-01
- **Question:** Can a schedule removal and addition caused by a key-changing date amendment be
  asserted as one exact modification?
- **Alternatives:** force a heuristic pair; treat all as unrelated; preserve exact presence facts
  plus conservative candidate evidence.
- **Evidence:** Schedule identity includes effective/discontinue dates, so changing either changes
  the key. The supplied source has no stable amendment identifier.
- **Review:** Independent review confirmed that categorical candidates, ambiguity groups, and
  unpaired events are coherent and preserve exact source facts.
- **Decision:** Keep key-preserving modifications and key additions/removals exact. Emit key-shift
  links only as medium-confidence unique candidates, low-confidence ambiguous groups, or unpaired
  events. Never replace exact presence facts or promote a candidate without a source-stable amendment
  ID.
- **Confidence:** high.
- **Affected artifacts/tests:** `SEMANTIC_DECISIONS.md` P0-07; NF-S05; HT-19 through HT-22;
  agent/notebook/HTML label tests.
- **Rollback:** Promote key-shift links only after contracting a stable source amendment identifier;
  retain prior candidate evidence and rerun HT-19 through HT-22 and interface-label tests.
- **Status:** accepted provisionally for the release.

## D-0007 — Physical capacity and codeshare de-duplication

- **Date:** 2026-09-01
- **Trigger:** SPEC-01
- **Question:** How should physical operating capacity avoid codeshare double counting when no stable
  physical-service group identifier is supplied?
- **Alternatives:** sum every operating-carrier row; fuzzy-group schedules; count a source-controlled
  base representative and expose unresolved services.
- **Evidence:** Marketing and operating roles differ, and marketing copies can represent the same
  physical service. Fuzzy time/equipment grouping cannot establish exact physical identity.
- **Review:** Independent review accepted the conservative representative rule and required the
  possible undercount to remain visible rather than be silently guessed.
- **Decision:** For operating/physical capacity, count only an unambiguous non-codeshare/base row
  whose marketing carrier equals the operating carrier. Exclude marketing-only copies. Report a
  codeshare-only service without such a row as `UNRESOLVED_PHYSICAL_SERVICE`.
- **Confidence:** medium because the reduced source lacks a stable physical-service group key.
- **Affected artifacts/tests:** `SEMANTIC_DECISIONS.md` P0-09; NF-S07; HT-26 through HT-29.
- **Rollback:** Adopt a stable source physical-service identifier when available, compare old/new
  complete results, and rerun HT-26 through HT-29 before replacing the conservative rule.
- **Status:** accepted provisionally for the release.

## D-0008 — Historical passenger UTC-offset sign convention

- **Date:** 2026-09-01
- **Trigger:** SPEC-02
- **Question:** What sign does the historical passenger source use for
  `departure_utc_offset_minutes` and `arrival_utc_offset_minutes` when deriving dated UTC timestamps
  from local date/time?
- **Alternatives:** offset is local minus UTC; offset is UTC minus local; leave every offset-derived
  UTC timestamp unresolved.
- **Evidence:** The supplied schema names both fields as UTC offset minutes and supplies local time,
  operating date, arrival-day indicator, and UTC time, but does not define the sign. The conventional
  UTC-offset interpretation is `local = UTC + offset`, so `UTC = local - offset`. Forward passenger
  rows already carry expanded UTC timestamps and remain authoritative for themselves. Schedule UTC
  `TIME` without offset/date evidence remains unresolved under P0-08.
- **Review:** Independent reviewer `/root/spec_02/spec_02_redteam` found the unstated sign
  release-blocking for HT-25 and required a source-visible convention, boundary tests, and rollback.
- **Decision:** Provisionally interpret source offset minutes as `local - UTC`. Build departure local
  timestamp from operating date plus local departure time; build arrival local timestamp from
  operating date plus arrival-day indicator plus local arrival time; derive UTC by subtracting the
  respective offset minutes. Null/non-finite offset yields `UNRESOLVED_UTC_DATE`; never infer the sign
  from clock ordering.
- **Confidence:** medium-low; binding for the release but not customer-confirmed.
- **Affected artifacts/tests:** `SOURCE_CONTRACT.md` and `ATTRIBUTE_AUTHORITY.md` UTC derivations;
  NF-S10; HT-25; both-clock schedule/passenger outputs and interface limitation labels.
- **Rollback:** If authoritative lineage defines the opposite sign, change only the offset normalizer
  from subtraction to addition, regenerate the affected fixtures/expected manifest, compare complete
  old/new results, and rerun HT-25 plus every UTC-instance and both-clock query/interface test.
- **Status:** accepted provisionally pending authoritative confirmation.

## D-0009 — U.S.-centered synthetic geography and public-identifier policy

- **Date:** 2026-09-01
- **Trigger:** SPEC-03 user scope update
- **Question:** How should all eight golden questions target U.S. flights when the reduced airport
  contract has no country-classification field?
- **Alternatives:** geography-neutral synthetic codes; explicitly synthetic U.S.-domestic operations
  using public airport geography labels; fixtures or claims tied to real-carrier operations.
- **Evidence:** The user explicitly selected U.S. flights. Public U.S. airport codes, names, and IANA
  time-zone names provide useful geography and clock-boundary labels, while the supplied schema and
  confidential inputs do not authorize fabricated operational facts about real carriers. Because
  `AIRPORT_REFERENCE` has no country field, U.S. scope cannot honestly be presented as an
  ontology-derived domestic/international classification.
- **Review:** Independent reviewer `/root/us_scope_review` found no SPEC-01/SPEC-02 contradiction and
  required an enumerated U.S. airport whitelist, synthetic non-airport identities, closed-map-aware
  planned-versus-actual airport codes, explicit offset/DST evidence, and a claim scan. The reviewer
  also required AP-09 time-zone lineage not to override expanded passenger timestamps, D-0008
  offsets, or unresolved schedule `TIME` values.
- **Decision:** Use an explicitly synthetic U.S.-domestic core for all eight golden questions. Every
  named schedule, passenger, and actual-flight route has both endpoints in an enumerated public U.S.
  airport whitelist. Public IATA/ICAO codes, airport names, and IANA time-zone names are geography
  labels only. Airport internal IDs and every carrier, aircraft, registration, schedule, passenger,
  capacity, time, and actual-flight fact use a visibly synthetic namespace. Planned schedule and
  passenger endpoints use public IATA labels; actual-flight endpoints use the synthetic internal
  airport IDs required by the closed resolution map. The ontology does not claim to derive country
  or domestic status.
- **Confidence:** high; directly user-authorized and independently reviewed.
- **Affected artifacts/tests:** `DEMO_QUESTIONS.md`, `EXPECTED_ANSWERS.yaml`,
  `NEO4J_PARITY_MATRIX.md`, DATA-01/02 fixture geography, all SQL/RAI golden outputs, notebooks,
  agent, HTML, and confidentiality/claim scans. Tests whitelist every golden endpoint; enforce
  synthetic patterns for non-airport identities; distinguish planned IATA from actual internal
  airport resolution; keep ambiguity fixtures synthetic; cover explicit U.S. offsets, DST edges,
  local/UTC date crossings, and AF-06 versus AF-07 day differences; and reject real-operator claims.
- **Rollback:** Replace the airport whitelist/geography labels, regenerate the deterministic fixtures
  and expected artifacts together before implementation, and rerun HT-23, HT-25, HT-29, HT-33
  through HT-38, HT-42, HT-45, HT-49, all eight complete-result gates, and confidentiality/claim
  scans. No SPEC-01/SPEC-02 semantic change is needed unless country classification is added.
- **Status:** accepted for this release.

## D-0010 — Shared schedule universe and Q05 manifest supersession

- **Date:** 2026-09-01
- **Trigger:** DATA-01 constructibility gate
- **Question:** How should the frozen unfiltered Q05 schedule-change answer reconcile with schedule
  facts required by NF-S04, Q06 market entry/exit, Q07 capacity, and the both-clock boundary fixture
  in the same source dataset?
- **Alternatives:** silently split fixtures into separate source universes; add an uncontracted Q05
  cohort filter; preserve one shared source universe and supersede the internally inconsistent
  expected manifest before generator implementation.
- **Evidence:** Q05 compares every schedule key across complete snapshots on 2026-08-03, 08-10,
  08-17, 08-24, and 08-31. NF-S04 requires a key to disappear and reappear on those endpoints. Q06
  requires one marketing market to be absent/present and another present/absent on 08-24 versus
  08-31. Four Q07 schedules must open target knowledge segments on 08-31 without creating Q06 market
  entries, and `TT-BOTH-CLOCKS` requires a target segment `[2026-08-24, 2026-08-31)`. P0-07 also
  requires every exact addition/removal without an eligible partner to retain explicit unpaired
  evidence. The v1.0 Q05 19-row set omitted these forced facts and even omitted unpaired evidence for
  its own ordinary addition/removal.
- **Review:** DATA-01 produced a per-key contradiction witness. Independent reviewer
  `/root/data01_preflight` classified it Sev1 and recomputed the minimal coherent repair: ten forced
  exact events plus six forced unpaired events, taking Q05 from 19 to 35 rows. The reviewer rejected
  a cohort filter because no such source field or typed query parameter exists and it would exclude
  NF-S04 despite Q05 traceability.
- **Decision:** Preserve one shared schedule source universe and the unfiltered Q05 workload.
  Supersede `EXPECTED_ANSWERS.yaml` v1.0.0 with reviewed v1.1.0 before DATA-01 resumes. Add exactly:
  unpaired evidence for the existing ordinary addition/removal; NF-S04 exact disappearance,
  reappearance, and their unpaired evidence; Q06 exact market-entry addition, market-exit removal,
  and their unpaired evidence; four key-preserving 08-31 content changes that open the Q07 target
  capacity states while keeping their market identities present at both Q06 endpoints; and two
  key-preserving changes that open and close the both-clock target segment. Q06 and Q07 complete
  result sets remain unchanged. No result may be hidden through invalid resolution, a private
  fixture universe, or an undeclared filter.
- **Confidence:** high; required by the frozen source grains and P0-05 through P0-08.
- **Affected artifacts/tests:** `DEMO_QUESTIONS.md`, `EXPECTED_ANSWERS.yaml`,
  `NEO4J_PARITY_MATRIX.md`, `build/task_reports/SPEC-03.json`, DATA-01/02 schedule fixtures, Q05/Q06/Q07
  SQL and RAI gates, HT-13/15/17/19 through HT-29/42/49. Add a static cross-question event-closure
  test; assert Q05 exactly 35 rows, Q06 exactly two rows, Q07 marketing/operating sets unchanged,
  and exactly one unpaired row for every exact addition/removal without a unique or ambiguous
  candidate classification.
- **Rollback:** Only a separately reviewed customer requirement may introduce a typed Q05 cohort
  parameter and corresponding parity limitation. That change must supersede the catalog/manifest,
  rerun the same event-closure and complete-result gates, and remain visible in every interface;
  never restore v1.0 by silently filtering or splitting the source data.
- **Status:** accepted pre-implementation correction; v1.0.0 remains in Git history and is
  superseded by v1.1.0 after the renewed SPEC-03 adversarial gate passes.

## D-0011 — Isolate the snapshot-gap fixture from Q05 cadence

- **Date:** 2026-09-01
- **Trigger:** D-0010 independent event-closure review
- **Question:** Can the NF-S03 post-gap complete snapshot remain on 2026-08-27 while Q05 says the
  prior eligible endpoint for its 2026-08-31 comparison is 2026-08-24?
- **Alternatives:** redefine Q05 to ignore intervening eligible snapshots; make the post-gap snapshot
  ineligible and lose HT-13 coverage; move the complete gap fixture outside the canonical Q05 window.
- **Evidence:** P0-05 compares adjacent dates in the eligible complete-snapshot sequence. The v1.0
  manifest declared 2026-08-27 present and complete, between Q05's 2026-08-24 and 2026-08-31
  endpoints. Therefore a complete 08-31 comparison could not truthfully name 08-24 as its previous
  eligible date. The `cadence_days` input does not authorize skipping a complete snapshot under the
  frozen semantics.
- **Review:** Independent reviewer `/root/data01_preflight` found the intervening snapshot while
  recomputing D-0010 event closure and recommended moving the negative fixture rather than adding an
  uncontracted cadence-selection rule.
- **Decision:** Move the complete NF-S03 gap sequence outside the canonical August window. Use an
  isolated weekly sequence with prior complete 2026-10-05, missing 2026-10-12, incomplete
  2026-10-19, and post-gap complete 2026-10-26. Update the Q05 ineligible-endpoint scenario, Q06
  incomplete-endpoint scenario, TT snapshot-completeness rows, source-control IDs, and traceability
  dates consistently. The only eligible complete dates inside Q05's inclusive 2026-08-03 through
  2026-08-31 window are exactly its five weekly endpoints.
- **Confidence:** high; directly required by P0-05 adjacency.
- **Affected artifacts/tests:** `EXPECTED_ANSWERS.yaml`, `DEMO_QUESTIONS.md`, SPEC-03 report,
  DATA-01/02 snapshot calendar rows, Q05/Q06 SQL and RAI gates, NF-S03, HT-12 through HT-15/42.
  Add an assertion enumerating the exact five eligible complete Q05 dates and proving no intervening
  date; independently prove the October gap comparison has `crosses_snapshot_gap = true` and does
  not alter any August result.
- **Rollback:** Only an explicit reviewed change to P0-05 and the typed Q05 contract may introduce a
  cadence-selected subsequence that skips complete snapshots. If adopted, supersede the manifest,
  expose the selection rule in every interface, and rerun adjacency, gap, and complete-result tests.
- **Status:** accepted as part of the pre-implementation v1.1.0 correction.

## D-0012 — Bind DV-43 bytes and replace the null-ID lineage alias

- **Date:** 2026-09-01
- **Trigger:** DATA-01 expected-row constructibility gate
- **Question:** How can the valid `PASSENGER_FORWARD` fixture with null PF-01 produce the frozen
  DV-46 lineage token when the v1.1.0 manifest used the human-readable suffix
  `SYN-DV43-VALID-KEY-NULL-ID-01` instead of a SHA-256 digest and the source contract did not spell
  out the byte framing needed to compute one independent literal?
- **Alternatives:** weaken DV-43/DV-46 to permit aliases; give the fixture a non-null stable source
  ID and lose the required null-ID fallback case; retain the display alias only as presentation,
  bind a versioned length-prefixed byte grammar, and supersede the one impossible lineage scalar
  with its independently computed digest.
- **Evidence:** `SOURCE_CONTRACT.md` requires DV-43 to be SHA-256 over typed normalized fields and
  DV-46 for a retained PF row with null PF-01 to be `FORWARD|<DV-43>`. `ATTRIBUTE_AUTHORITY.md`
  assigns the same semantic ownership. The v1.1.0 TT32-R11/source anchor instead froze
  `FORWARD|SYN-DV43-VALID-KEY-NULL-ID-01`; its suffix is neither hexadecimal nor a SHA-256 output,
  and no alias mechanism exists. DATA-01 therefore proved that no conforming raw row could produce
  the expected scalar.
- **Review:** Independent DATA-01 reviewer `/root/data_01/data01_adversarial` classified the defect
  Sev1 and rejected weakening the hash contract. Independent reviewer `/root/dv43_token_review`
  recomputed the chosen framing in both Python and Ruby, round-tripped the payload exactly, and
  verified sensitivity to null-versus-empty, source token, Field ID, type tag, and value changes.
- **Decision:** Supersede the ambiguous prose-level framing for this release with byte grammar
  `dv43-lp-v1`. `LP(s)` is the ASCII decimal length of the UTF-8 byte string, then ASCII `:`, then
  those bytes. A PF payload begins with `LP(FORWARD)`. Each PF-01-through-PF-19 field in ascending
  Field-ID order appends `LP(Field-ID)`, `LP(the exact SOURCE_CONTRACT Snowflake type tag)`, and
  `LP(N)` for null; a non-null field instead appends `LP(V)` followed by `LP(the canonical scalar)`.
  `N` and `V` are the wire tags and explicitly supersede the earlier informal backticked `NULL`
  wording; canonical scalar rules otherwise remain unchanged. For the named valid-key/null-ID row,
  the complete payload is 610 bytes and SHA-256 is
  `a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7`; DV-46 is therefore
  `FORWARD|a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7`. Keep
  `SYN-PAX-VALID-NULL-ID-01` only as the human-readable passenger presentation token. Supersede the
  expected manifest to v1.1.1; no other expected row or business result changes.
- **Confidence:** high; two independent implementations produced the same known-answer vector and
  the repair restores the already chosen hash semantics rather than changing them.
- **Affected artifacts/tests:** `EXPECTED_ANSWERS.yaml`, `DEMO_QUESTIONS.md`,
  `NEO4J_PARITY_MATRIX.md`, the SPEC-03 report, `data/SYNTHETIC_DATA_SPEC.md`, DATA-02 hash helpers,
  TT32-R11, NF-F02, DV-43/DV-46, HT-32/42/49. Add a 610-byte known-answer test, a decoder
  round-trip test, null/empty/domain/Field-ID/type/value sensitivity tests, a 64-lowercase-hex DV-46
  assertion for every null-ID retained PF/PH row, 253-row ownership reconciliation, and a proof that
  every result except the corrected lineage scalar remains byte-for-byte equal to v1.1.0.
- **Rollback:** If authoritative source-system hashing evidence requires another byte framing,
  append a superseding decision; version the grammar and manifest, recompute the known-answer vector
  independently in two implementations, and rerun every hash/lineage/expected-result gate. Never
  restore a human-readable alias in DV-43 or DV-46.
- **Status:** accepted pre-implementation correction; v1.1.0 remains in Git history and is
  superseded by v1.1.1 after the renewed SPEC-03 adversarial gate passes.
