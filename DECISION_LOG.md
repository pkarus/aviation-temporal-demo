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

## D-0013 — Generated source serialization and fail-closed publication

- **Date:** 2026-09-01
- **Trigger:** DATA-02 reversible implementation-boundary review
- **Question:** What generated-file format, byte contract, publication protocol, and rollback should
  DATA-02 use so DATA-03 can load deterministic fixtures without committing 145,054 generated demo
  rows or permitting two conforming generators to emit different artifacts?
- **Alternatives:** commit generated rows; use an implicit Arrow/Parquet boundary; emit loosely
  specified CSV/JSON directly into the final directory; emit a byte-frozen CSV/JSON package through
  validated atomic publication.
- **Evidence:** `build/*` is already reserved for regenerable artifacts, the environment does not
  declare Arrow/Parquet as an explicit generator contract, Snowflake can load typed CSV with an
  explicit file format, and DATA-01 freezes SOURCE_CONTRACT field order plus exact scalar types.
  The demo scale is small enough to regenerate but large and noisy enough that committing the raw
  output would obscure reviewed source and expected-answer changes. Direct writes can leave a stale
  or partial manifest that appears current after a failure.
- **Review:** Independent reviewer `/root/data01_final_review` rejected the initial proposal with
  three Sev2 findings: empty CSV fields did not distinguish null from a legitimate empty string;
  “canonical JSON” did not freeze serializer bytes or hash domains; and direct publication was not
  fail-closed. The reviewer also corrected the rationale from “no PyArrow dependency” to avoiding an
  explicit Arrow/Parquet boundary and required round-trip, hash, publication-fault, and ignore tests.
- **Decision:** Commit generator code and tests, but publish generated source packages only under
  ignored `build/generated_data/<scale>/`. Emit one CSV per SOURCE object with exactly one header row
  in SOURCE_CONTRACT column order. CSV bytes are UTF-8 with LF endings, comma delimiter, double-quote
  enclosure when required, and doubled embedded quotes. An unquoted empty field encodes null; every
  non-null empty string is rejected before publication. NUMBER, FLOAT, BOOLEAN, DATE, TIME, and
  TIMESTAMP_NTZ use one versioned exact scalar formatter, and DATA-03 must declare matching explicit
  Snowflake file-format options, skip exactly one header row, enforce exact column counts, and fail on
  conversion error. Emit the manifest as canonical JSON using sorted keys, compact separators,
  `ensure_ascii=false`, `allow_nan=false`, UTF-8, and exactly one final LF. CSV file hashes cover exact
  file bytes; ordered-row hashes cover versioned typed canonical rows; the manifest records both and
  never hashes itself. Generate into a scale-specific temporary sibling, validate all counts, rows,
  known answers, hashes, round trips, and expected-result ownership, write the manifest last, then
  replace the target directory only after the package is complete. A failed run leaves no publishable
  target manifest for that attempt.
- **Confidence:** high; the boundary is deterministic, Snowflake-loadable, independently reviewed,
  and does not alter any frozen semantic or expected answer.
- **Affected artifacts/tests:** DATA-02 generator, generated manifests, DATA-03 file format/load
  scripts, and generator unit tests. Tests round-trip null, the text `NULL`, comma, quote, CR/LF,
  Unicode, leading/trailing spaces, and every contracted scalar type; reject non-null empty strings;
  assert exact headers and row widths for all ten objects; independently recompute file and typed-row
  hashes; prove two clean runs byte-identical and reordered input canonically identical; prove the
  manifest has no self-hash cycle; inject a pre-publication failure and prove no partial/current
  manifest appears; and use `git check-ignore` to prove generated packages remain untracked.
- **Rollback:** Delete only `build/generated_data/<validated-scale>/` and regenerate. Reverting the
  serializer requires a versioned manifest/file-format change, independent byte review, and rerunning
  DATA-02 determinism plus DATA-03 clean-load/rerun gates; frozen expected answers remain untouched.
- **Status:** accepted provisionally for DATA-02 and DATA-03.

## D-0014 — Atomic SOURCE publication and recoverable rollback snapshots

- **Date:** 2026-09-01
- **Trigger:** DATA-03 reversible Snowflake load-design review
- **Question:** How should DATA-03 publish ten generated source objects as one governed dataset while
  preserving permanent table identity, grants, comments, constraints, and operational change
  tracking across clean and warm loads?
- **Alternatives:** recreate or truncate permanent tables one at a time; treat a prior manifest or
  retention-dependent Time Travel as the primary rollback; publish all tables with DML in one
  transaction after independent staging validation and retain explicit pre-publication snapshots.
- **Evidence:** Snowflake DDL auto-commits, so it cannot be mixed into an atomic data-publication
  transaction. Snow CLI 3.16.0 documents `--single-transaction` as autocommit-off execution bounded
  by `BEGIN`/`COMMIT`, with rollback on command failure. Snowflake documents `INSERT OVERWRITE` as DML
  processed in the current transaction and recommends it where object identity and change-tracking
  history must be retained. The ten SOURCE tables are one manifest-bound semantic package; exposing
  only a subset, or advancing the manifest separately, would make downstream validation ambiguous.
  A previous manifest does not itself contain restorable rows, and Time Travel depends on retained
  history.
- **Review:** Independent reviewer `/root/data03_design_review` passed the core staging plus atomic
  `INSERT OVERWRITE` design with zero Sev1 findings, but required two Sev2 amendments: bind this
  decision before regenerating both packages and prove that only the decision-log authority hash and
  outer manifest bytes change; and create run-scoped zero-copy rollback clones of all ten current
  SOURCE tables plus a snapshot of the active singleton manifest immediately before publication.
  The review also required fresh run-scoped staging, immutable manifest-hash stage prefixes, exact
  uploaded-byte verification, DML-only publication SQL, explicit columns, `NORELY` metadata,
  mid-transaction failure injection, operational `CHANGES` evidence, and tested clone restoration.
- **Decision:** Create permanent SOURCE tables once, outside the publication transaction, and fail on
  structural drift during warm runs. Declare only data-true PK, UNIQUE, and FK metadata, all `NOT
  ENFORCED NORELY`; never set `RELY`. Load each exact manifest CSV into a fresh run-scoped transient
  VALIDATION staging table through the versioned D-0013 file format. Use an immutable
  manifest-SHA-256 internal-stage prefix, one explicit uncompressed file per `COPY`,
  `ON_ERROR=ABORT_STATEMENT`, `PURGE=FALSE`, and validate uploaded bytes by downloading them to a
  temporary directory and recomputing SHA-256. Validate all counts, types, column order, hashes,
  keys, resolution cardinalities, snapshot completeness, functional dependencies, and named fixture
  controls before publication. Immediately before publication, create uniquely named transient
  zero-copy clones of every current SOURCE table and copy the active manifest row into a run-scoped
  rollback table; validate rollback counts and fingerprints. Publish with one Snow CLI
  `--single-transaction` file containing exactly ten fully qualified `INSERT OVERWRITE` statements
  and one manifest `INSERT OVERWRITE`, each with explicit target and source column lists and no DDL,
  session changes, truncation, or transaction-control statements. The manifest row is the governed
  activation marker; no `PASSED` row may name a partially published package. Retain the exact staged
  prefix and rollback snapshots through G3, then remove only their validated, run-specific names.
- **Confidence:** high; the chosen path follows documented Snowflake transaction boundaries,
  preserves table identity, and adds a data-bearing rollback independent of retention history.
- **Affected artifacts/tests:** DATA-03 DDL/load/validation scripts, both generated package
  manifests, the SOURCE table inventory, `VALIDATION.SOURCE_LOAD_MANIFEST`, and the DATA-03 report.
  Before any Snowflake mutation, regenerate smoke and demo after this decision and prove an
  allowlisted diff: every CSV byte hash, typed-row hash, row count, seed, serializer/file-format
  version, schema contract, and semantic result is unchanged; only
  `authority_sha256.DECISION_LOG.md` and the outer manifest file SHA may change. Verify exact file
  format options, `PUT`/`LIST` membership and sizes, downloaded stage-file SHA-256, zero
  `VALIDATION_MODE=RETURN_ALL_ERRORS` errors, one loaded file per fresh staging table, 195/195 source
  columns, independent key/FK/cardinality/completeness queries, stable table IDs/comments/constraints
  and `CHANGE_TRACKING=ON`, and an operational `CHANGES` query across cold/warm timestamps. Inject a
  failing statement after the fifth overwrite and prove all ten target counts/fingerprints plus the
  manifest remain unchanged. Rerun an identical warm publication, then execute the transactional
  rollback-clone restore path and prove exact restoration of all eleven objects.
- **Rollback:** On a post-publication semantic failure, use one new DML-only
  `--single-transaction` run to `INSERT OVERWRITE` all ten targets and the active manifest from the
  validated pre-publication rollback snapshots. Use Time Travel only as an emergency fallback. A
  cold baseline is represented by validated empty clones and an empty manifest snapshot. Reversing
  this publication protocol requires a superseding reviewed decision, an equivalent atomicity and
  data-bearing rollback proof, and rerunning DATA-02 authority binding plus every DATA-03 clean,
  failure-injection, warm, change-tracking, and restoration gate.
- **Status:** accepted provisionally for DATA-03 after independent design review; final acceptance
  requires the live G3 evidence above.

## D-0015 — Version the generated-source decision authority at the D-0014 boundary

- **Date:** 2026-09-01
- **Trigger:** DATA-03 cold-start compatibility review before the first Snowflake mutation
- **Question:** How can an ignored generated package remain reproducible after later append-only
  orchestration decisions that do not change its source data, without allowing a later
  source-affecting decision to bypass package review?
- **Alternatives:** forbid all later decision entries; hash the entire current log and repin the
  generator and loader after every unrelated decision; introduce a separate immutable source
  authority artifact; treat the exact D-0014 log prefix as the embedded versioned authority baseline
  and record the current full-log hash separately.
- **Evidence:** The D-0014-complete `DECISION_LOG.md` is exactly 35,385 UTF-8 bytes and its SHA-256 is
  `2bcce37e71fb21de30174e1de599c7d0abb3e228359eca4fafd892de38b7f843`. Both D-0014-regenerated
  manifests bind that value; the smoke manifest SHA-256 is
  `8e24fcf1581d89958a8b8bbab0683372817bbe01c42b3c89ac7f2a56d980383e` and demo is
  `c05c732e158298b3c04e432a8e428ebc8e93a60e59fb2b53f4ca45c558dbd119`. Generated packages are
  intentionally ignored, so a clean run must regenerate before loading. Hashing the whole growing
  log would change otherwise identical manifest bytes after every later decision and make the
  hash-pinned DATA-03 loader reject a valid cold regeneration.
- **Review:** The DATA-03 code reviewer found the clean-regeneration incompatibility before mutation.
  Independent reviewer `/root/spec_03` rejected a bare prefix check with two Sev2 findings: the
  legacy manifest key could misleadingly appear to attest the current full file, and an arbitrary
  binary or non-decision suffix would pass. The reviewer required explicit baseline semantics,
  separate full-current audit hashes, mandatory re-versioning for later source-affecting decisions,
  strict UTF-8 append grammar, monotonic unique decision headings, cross-component constants, and
  exact/tampered/truncated/appended tests.
- **Decision:** For generated-source manifest version 1.0, supersede the interpretation of
  `authority_sha256["DECISION_LOG.md"]`: it is the SHA-256 of the decision-log authority baseline
  through D-0014, not the SHA-256 of the current full `DECISION_LOG.md`. The baseline is exactly the
  first 35,385 bytes, ends after the D-0014 status and final LF, and has the SHA-256 above. Generator
  and loader must fail if the current file is shorter, is not strict UTF-8, or changes any baseline
  byte. A nonempty suffix must be append-only Markdown decisions: after the single separating LF it
  begins with `## D-0015 —`, every subsequent top-level decision heading is a unique strictly
  increasing `D-NNNN`, and no other `##` heading form is accepted. Generator and loader constants
  must be cross-asserted. DATA-02 evidence and DATA-03 local/live load evidence separately record the
  SHA-256 of the complete current log; labels must distinguish `decision_log_baseline_sha256` from
  `decision_log_current_sha256`. A decision after D-0014 that changes source schema, rows,
  serialization, typed hashes, frozen expected semantics, or generation authority is not a
  compatible suffix: it must version and repin the generated package through an independent review.
- **Confidence:** high; the frozen prefix detects every rewrite or truncation of all source-package
  decisions through publication design, while the strict suffix grammar and full-current audit hash
  preserve later provenance. SHA-256 provides integrity comparison here, not authorship or a digital
  signature.
- **Affected artifacts/tests:** DATA-02 generator/tests/report compatibility evidence, DATA-03
  loader/tests/report, generated smoke/demo manifests, and cold `prep_demo.py`. Test the exact
  baseline; current D-0015 suffix; valid D-0015 and D-0015-plus-D-0016 synthetic suffixes; first- and
  last-prefix-byte tampering; 35,384-byte truncation and empty input; invalid UTF-8; non-decision,
  duplicate, decreasing, skipped-first, and malformed headings; and proof that the complete-current
  hash changes while the baseline hash stays fixed. Rerun clean and reordered generation for both
  scales and require byte-identical trees, unchanged 20 CSV file hashes and typed-row hashes,
  unchanged semantic validations, exact smoke/demo manifest SHAs above, and DATA-03 preflight
  acceptance.
- **Rollback:** Restore whole-current-file decision hashing, regenerate both scales, repin DATA-03
  manifest/report expectations, and rerun full DATA-02 determinism plus DATA-03 preflight. After live
  publication, use the D-0014 eleven-object transactional rollback if the active package itself must
  be reverted. A future separate immutable source-authority artifact may supersede this embedded
  baseline only through a versioned manifest and loader review.
- **Status:** accepted provisionally after independent review; final acceptance requires the stated
  DATA-02 compatibility rerun and DATA-03 cold preflight.

## D-0016 — Preserve contracted nullable identities in Snowflake key metadata

- **Date:** 2026-09-02
- **Trigger:** DATA-03 cold prepublication structural gate
- **Question:** How should standard-table key metadata represent source identity candidates whose
  frozen source columns are nullable, after Snowflake made `PRIMARY KEY` columns physically `NOT
  NULL` despite `NOT ENFORCED NORELY`?
- **Alternatives:** narrow the frozen source contract to non-null; remove all key metadata; recreate
  the source tables; retain `PRIMARY KEY` only for contract-non-null identity and use nullable
  `UNIQUE` metadata for the remaining proven identity candidates, repairing the empty unpublished
  tables in place.
- **Evidence:** The first cold run executed scoped DDL and then stopped before `PUT`, `COPY`, rollback
  snapshots, or publication because `SOURCE.AIRCRAFT_MASTER.aircraft_id` was `IS_NULLABLE=NO` while
  AM-01 is contract-nullable. Live read-only reconciliation proved all ten permanent SOURCE tables
  and all ten failed-run transient staging tables contain zero rows, the active manifest contains
  zero rows, no rollback clone exists, and no staged package file was uploaded. The same PK-induced
  narrowing affects nullable AH-01, AC-01, AF-01, AP-01/AP-02, and AL-01/AL-02; SC-01 is the only
  declared primary-key column whose contract is non-null. Snowflake's constraint documentation says
  a primary key implies both unique and non-null, while a unique key permits nulls. Standard-table
  UNIQUE, PK, and FK constraints remain informational; NOT NULL remains enforced.
- **Review:** Independent reviewer `/root/data03_code_review` confirmed PK-to-UNIQUE is the narrow
  contract-preserving repair and identified four Sev2 controls. Dropping the AM primary key with the
  default cascade could silently drop the AH foreign key, so the repair must explicitly drop that FK
  first and use `RESTRICT` on all six PK drops. Because DDL auto-commits and constraint drops have no
  constraint-level `IF EXISTS`, reconciliation must recognize exact old, desired, and reviewed
  partial states, execute one statement at a time with a postcheck, no-op at desired state, and
  refuse nonempty or unknown states. The account's supported `SHOW TABLES` output has no object-ID
  field and `ACCOUNT_USAGE.TABLES` is unauthorized, so identity evidence must not depend on either.
  Finally, D-0015 classifies this source-schema metadata correction as package-affecting and requires
  a new manifest version and decision-authority repin before retry.
- **Decision:** Preserve all 195 frozen columns, types, order, nullability, comments, and source rows.
  Keep `PK_SCHEDULE_SNAPSHOT_CALENDAR(expected_publish_date) NOT ENFORCED NORELY`. Replace the six
  primary keys on contract-nullable identities with named `UNIQUE NOT ENFORCED NORELY` constraints:
  AM aircraft ID, AH history ID, AC configuration ID, AF flight ID, AP `(airport_id,
  effective_start_date)`, and AL `(airline_id,effective_start_date)`. Retain the nullable PF/PH
  source-ID UNIQUE constraints and the truthful AH-to-AM and SS-to-SC foreign keys. Independently
  validate non-null key uniqueness and both FKs from data; never set `RELY`. Repair only when all ten
  targets and the active manifest are empty and the observed metadata is an exact recognized state.
  The ordered in-place repair is: drop AH-to-AM FK; for each affected table drop its old PK with
  `RESTRICT`; drop NOT NULL from exactly AM-01, AH-01, AC-01, AF-01, AP-01, AP-02, AL-01, and AL-02;
  add the six named nullable UNIQUE constraints; then re-add AH-to-AM against the AM unique key. Run
  one scoped DDL statement per Snow CLI invocation, verify the expected state after every statement,
  and resume safely from any reviewed partial prefix. Reject unknown, nonempty, or already-published
  states. Drop only the exact ten empty `COLD_20260901_01` staging tables after their inventory is
  validated; do not use cascade or broad cleanup.
- **Identity evidence:** Preserve the permanent SOURCE objects in place. Capture supported
  `SHOW TABLES` `created_on` values before and after publication and require exact equality together
  with unchanged fully qualified names, kind, owner, comments, ownership grants, constraint shapes,
  and `CHANGE_TRACKING=ON`. Do not parse undocumented reference tokens or require an unavailable
  object-ID column.
- **Package version:** Supersede generated manifest v1.0.0 with v1.0.1 and repin its decision-log
  authority baseline through this complete D-0016 entry. After this entry is appended, record the
  exact baseline byte count and SHA-256 in code and task reports. Regenerate both scales and prove
  all twenty CSV bytes, file hashes, typed-row hashes, counts, source semantics, and expected results
  are unchanged; only the manifest version, decision baseline hash, and resulting outer manifest
  bytes may differ. Later compatible decisions begin at D-0017 under D-0015's strict append grammar.
- **Confidence:** high; it follows documented Snowflake constraint semantics, preserves the frozen
  source contract and bounded Neo4j-parity scope, and repairs only empty unpublished metadata without
  inventing a table, column, row, or customer rule.
- **Affected artifacts/tests:** DATA-02 generator/tests/report and both generated manifests; DATA-03
  loader/tests/report; live constraints/nullability; failed-run exact cleanup evidence. Add
  manifest-v1.0.1 clean/reordered determinism tests, generator/loader D-0016 baseline cross-assertion,
  strict D-0017-plus suffix tests, exact six-UNIQUE/one-PK/two-FK shape tests, nullable-key DDL tests,
  old/desired/every-reviewed-prefix reconciliation tests, unknown/nonempty refusal, FK-safe
  `RESTRICT` ordering, no-`CASCADE` scans, exact failed-run cleanup, and supported creation-timestamp
  stability across cold/warm/restore/republish.
- **Rollback:** Before publication, reverse only from a recognized desired state on verified empty
  tables: drop AH-to-AM FK, drop the six UNIQUE constraints with `RESTRICT`, set NOT NULL on the same
  eight columns, recreate the six former PKs, then recreate the FK, checking every step. This inverse
  intentionally restores the observed predecision metadata, not the preferred contract. After a
  package is published, use D-0014's eleven-object data rollback and a separately reviewed metadata
  migration; never recreate populated permanent tables or hide nullable source cases.
- **Status:** accepted provisionally after independent review; final acceptance requires local
  version/repair gates and live cold/warm G3 evidence.

## D-0017 — Supersede the generated-source publication apparatus

- **Date:** 2026-09-02
- **Trigger:** Orchestrator review of the stalled DATA-03 task after the previous agent run ended
- **Question:** Is the D-0014 transactional publication protocol, the D-0015 decision-log authority
  baseline, and the D-0016 in-place constraint reconciliation proportionate to the risk of loading
  ten deterministic synthetic CSV files into an empty, unpublished demo schema?
- **Alternatives:** continue the existing protocol and execute the pending repair plus publication;
  keep the protocol but waive individual gates case by case; supersede the publication apparatus and
  load with ordinary idempotent DDL and COPY under the same scoped role.
- **Evidence:** The previous run spent roughly eleven hours between the DATA-02 commit and its end
  without committing any work or writing a single row to Snowflake. Live read-only inspection
  confirms all ten SOURCE tables exist with zero rows, the active manifest is empty, no rollback
  clone exists, no package file was staged, and the D-0016 repair never executed. The asset the
  protocol protects is a deterministic synthetic package that regenerates byte-identically from a
  fixed seed in about sixteen seconds, so no unrecoverable state exists to roll back to. D-0016 was
  itself triggered by Snowflake making PRIMARY KEY columns physically NOT NULL, a condition that is
  correctable on empty unpublished tables by recreating them. D-0015 exists only to stop later
  governance prose from invalidating an unrelated data package, a coupling that disappears once the
  decision log is not a data-determining input. The demo's remaining and unstarted work is the entire
  RelationalAI surface: ontology, eight queries, notebook, agent, runbook and gate.
- **Review:** Reviewed with the user, who approved superseding the apparatus and directed that the
  demo implement all eight questions with an ontology authored through the RelationalAI ontology
  skills. The scope reduction applies to publication mechanics only.
- **Decision:** Supersede the publication mechanics of D-0014, the decision-log authority baseline of
  D-0015, and the in-place reconciliation procedure of D-0016. Retain in full: the D-0013
  serialization and file-format boundary, the frozen SOURCE contract with its 195 columns, types,
  order and nullability, the frozen EXPECTED_ANSWERS.yaml, every semantic invariant in this log
  through D-0012, and the D-0016 finding itself that contract-nullable identity columns must be
  declared as named UNIQUE NOT ENFORCED NORELY rather than PRIMARY KEY. Replace
  `data/load_snowflake_source.py` with a lean `data/load_source.py` that verifies the package
  locally against its manifest, recreates the ten SOURCE tables with full column comments,
  constraints and CHANGE_TRACKING, stages and copies the exact CSV bytes, and verifies loaded row
  counts and content hashes against the manifest. Remove DECISION_LOG.md from the generated
  manifest's `authority_sha256` set: the decision log is governance prose, not a determinant of the
  generated data, and binding it made unrelated decisions invalidate a valid package. The manifest
  continues to bind SOURCE_CONTRACT.md, ATTRIBUTE_AUTHORITY.md, EXPECTED_ANSWERS.yaml,
  data/SYNTHETIC_DATA_SPEC.md and the DATA-01 report, which do determine the data. Bump the
  generated manifest to version 1.1.0.
- **Confidence:** high for the publication mechanics, which protect a regenerable artifact in a
  scoped demo database that no other workload reads. The retained items are the ones that carry
  customer semantics, and none of them is weakened here.
- **Affected artifacts/tests:** `data/generate_synthetic_data.py` and `tests/test_synthetic_data.py`
  lose the decision-log authority gate; both scales regenerate under manifest 1.1.0 with unchanged
  CSV bytes, file hashes, typed-row hashes, row counts and semantic validations.
  `data/load_snowflake_source.py` and `data/test_load_snowflake_source.py` are removed in favour of
  `data/load_source.py` and `data/test_load_source.py`. Prove that only the manifest version and the
  authority set change: all twenty CSV file hashes and typed-row hashes must be identical before and
  after.
- **Rollback:** The superseded protocol is recoverable from Git history at commit 518e613 plus the
  uncommitted working tree captured in the orchestration branch. Restoring it requires regenerating
  both scales, repinning the loader constants, and rerunning the DATA-02 determinism gate. The
  loaded SOURCE data itself is reproducible at any time by rerunning the generator and the loader.
- **Status:** accepted; final acceptance requires a green live load and the downstream ontology and
  query gates.

---

## D-0018 — Q05 `event_id` is a supplied manifest label, not a derived identity

- **Date:** 2026-09-02
- **Trigger:** DATA-04b reproduced all 24 frozen result sets from independent SQL oracles with zero
  cell diffs, but could not derive the 30 Q05 `event_id` mnemonics from any source fixture.
- **Question:** Q05's frozen `order_by` sorts on `event_id`. The manifest populates that column with
  hand-authored mnemonic strings such as `SYN-CHG-20260831-CAP-700-TERMINAL`, while
  `ATTRIBUTE_AUTHORITY.md` defines the DV-34 through DV-37 identities as SHA-256 digests. No
  implementation can reproduce the declared Q05 row order without being told those 30 strings. Is
  this an oracle fault, a generator fault, or a defect in the frozen expectation, and what is the
  smallest honest treatment?
- **Alternatives:** derive the mnemonics from a generating rule; emit them from the generator into
  `SOURCE` so they become derivable; supersede Q05's `order_by` to a derivable key as D-0010 and
  D-0011 superseded other Q05 content; carry the mnemonics in a declared label table keyed on an
  independently computed semantic identity and disclose the residual circularity.
- **Evidence:** All 30 mnemonics were enumerated and scored against seven candidate generating
  functions; the best fit reproduces 15 of 30. Three irreducible contradictions remain, the sharpest
  being that on 2026-08-31, under one `event_class` and one `field_name`, the manifest maps
  `SYN-SK-BASE_100` to `BASE` but `SYN-SK-PHY_BASE_700` to `CAP-700`, which refutes every
  token-selection rule. The declared row order is separately unrecoverable: on the same date the
  `EXACT_ADDITION` block orders `[MKT_ENTRY_714, UNPAIR_NEW]` while the `UNPAIRED_ADDITION` block
  orders the identical pair inverted, and the declared `member_side` / `member_schedule_key`
  tiebreakers yield the wrong order, so no total order on any per-key attribute reproduces the
  manifest. Generator fault is refuted: `SOURCE` carries no label column, `SCHEDULE_KEY_READABLE` is
  `SYN-READABLE|<key>|<publish_date>`, the four amendment objects are `MODEL_INPUT` contracts keyed
  on DV-34..37 SHA-256, and `data/SYNTHETIC_DATA_SPEC.md` never contracts a mnemonic. Seventeen live
  mutations of the Q05 oracle all failed loudly and no silent pass was constructible.
- **Review:** Independent reviewer `REVIEW-D0018`, which did not author the proposal, returned
  UPHELD WITH CHANGES. Full report at `build/task_reports/REVIEW-D0018.md`. The reviewer supplied the
  inverted-block proof above, refuted the generator-fault branch, verified mutation resistance at
  17 of 17, and proved the semantic key collision-free over the five declared classes with non-null
  `schedule_key`, with `comparison_date` and `schedule_key` load-bearing. It required four
  corrections, all accepted and applied: the diagnosis is a manifest/contract conflict on `event_id`
  rather than a plain non-derivable presentation column, and the D-0010/D-0011 supersession
  precedent must be recorded as considered and rejected; the claim that candidate, group and member
  ids are derived is over-stated, because their string templates, the `NN` ordinal rule and the
  `REMOVED`-before-`ADDED` `-Mk` ordering were all adopted from the manifest; the `semantic_verdict`
  must stop excluding the five derived `event_id` cells, a real defect under which an ordinal-padding
  perturbation gave a strict FAIL but a passing semantic verdict; and the ordering circularity must
  be disclosed in `DEMO_QUESTIONS.md` and the DATA-04b summary.
- **Decision:** Treat the 30 Q05 `event_id` mnemonics as supplied manifest labels. Carry them in
  `data/oracles/q05_event_labels.sql`, keyed on the independently computed semantic identity
  `(comparison_date, event_class, schedule_key, field_name)`, and render any computed event absent
  from that table as a visible `UNLABELLED|...` id so the table cannot mask an extra, missing or
  misclassified event. Do not supersede Q05's `order_by`: supersession would touch 30 values, the
  declared row sequence and the result hash, and replacing the mnemonics with SHA-256 digests would
  make the demo's most visually explanatory output unreadable on stage. Disclose instead. Of
  Q05-CANONICAL's 560 cells, 490 are independently recomputed and 65 are supplied (35 `row_id` plus
  30 `event_id`); the declared row sequence is supplied and, per the evidence above, could never have
  been verified. The event set, per-pair counts, every `event_class`, `exactness`, `confidence`,
  schedule/related/member key, `field_name`, `old_value`, `new_value`, `crosses_snapshot_gap`, the
  candidate/ambiguous/unpaired partition and closure, and the eligibility gate all remain
  independently verified.
- **Confidence:** high on non-derivability, which is proved twice by independent argument. High on
  fail-loud behaviour, which is proved by 17 live mutations. Medium on the disclosure being
  sufficient for a customer audience; REDTEAM-01 must retest this specific claim.
- **Affected artifacts/tests:** `data/oracles/q05_event_labels.sql`, `data/run_oracles.py`
  (`LABEL_COLUMNS["Q05"]` must exclude only the 30 declared-label rows, not the whole column),
  `data/test_oracles.py` (regression test that an ordinal-padding perturbation fails the semantic
  verdict), `build/task_reports/DATA-04b.json` summary, and the `DEMO_QUESTIONS.md` Q05 phrase
  "independently recomputed". `EXPECTED_ANSWERS.yaml` is not edited.
- **QUERY-UC2 binding:** the label map stays in a shared conformance harness outside both the oracle
  and the PyRel model. Putting it in the model would embed the frozen answer inside the very artifact
  whose independence the demo asserts. The RAI query emits the contracted DV-34..37 identity or
  leaves `event_id` unpopulated; Q05 is compared as an order-free join on the semantic identity for
  the semantic verdict, with the declared sequence asserted separately as a labelled presentation
  check; the mnemonics are joined last, in the notebook and agent layer, so the audience still reads
  `SYN-CHG-20260831-CAP-700-TERMINAL`.
- **Rollback:** if the disclosed circularity is later judged unacceptable, supersede Q05's `order_by`
  to a derivable key under a new reviewed decision. That changes the declared sequence and the Q05
  result hash but no row's content, and the semantic verdict is already order-free.
- **Status:** accepted.

### D-0018 arithmetic correction (appended 2026-09-02, entry above left intact)

The `Decision` field above states "490 are independently recomputed and 65 are supplied". Those two
figures do not partition 560; they sum to 555. DATA-04b verified the cells directly and the true
split is three-way, not two-way:

- **490 strictly derived** — the 14 columns that are neither `row_id` nor `event_id`, recomputed from
  raw `SOURCE` with no manifest input.
- **5 template-adopted `event_id`** — the candidate, group and member ids whose *content* is derived
  but whose string templates `SYN-CAND-<YYYYMMDD>-NN`, `SYN-AMB-<YYYYMMDD>-NN` and `<group_id>-M<k>`,
  two-digit padding, unconstrained `NN` ordinal rule and fitted `REMOVED`-before-`ADDED` `-Mk`
  ordering were all adopted from the manifest.
- **65 supplied** — 35 `row_id` plus the 30 declared `event_id` mnemonics.

490 + 5 + 65 = 560. Strictly derived is 87.5 percent; derived-or-computed is 88.4 percent. The
reviewer's report carries both 490 and 88.4 percent (which is 495/560) in different places, which is
the source of the error; quoting the two-way split in customer-facing material would read as a
contradiction. Use the three-way split. Nothing about the decision, the evidence, the rollback or the
QUERY-UC2 binding changes.

Separately, DATA-04b records a point of dissent worth preserving: the review's third required
correction described "unique across all 35 rows" as a claim to be fixed, but that phrasing appears in
no DATA-04b artifact. The precise uniqueness statement was added, not corrected. REDTEAM-01 should not
cite it as a defect that shipped.

---

## D-0019 — `CODE_RESOLUTION` binding strategy for the ontology

- **Date:** 2026-09-02
- **Trigger:** DATA-04a built `MODEL_INPUT.CODE_RESOLUTION` at 546,494 rows, 3.8 times the whole
  SOURCE layer, of which roughly 122,000 are `INVALID_INPUT` for legitimately null raw codes.
- **Question:** Must MODEL-01 bind the row-scoped resolution table, given that its size is the single
  most likely cause of a slow CDC sync and a slow cold start?
- **Evidence:** The size is contract-correct, not a defect: `SOURCE_CONTRACT.md` defines
  `resolution_id` as `SHA-256(domain, source_object, DV-46 source_row_token, field_role, raw_code,
  method)`, which is row-scoped by construction, and the contract explicitly requires the stable
  result to exist even at zero candidates. A distinct-code projection `CODE_RESOLUTION_CODE` exists at
  390 rows. Every other MODEL_INPUT object already carries its own resolved target id and resolution
  status columns, so the ontology's link semantics — a concept link only at `EXACT` cardinality one —
  do not require the row-scoped grain. PROBE-01 measured model indexing as scaling with bound tables
  and rules rather than rows (a 48,000-row model indexed in 34.3s), which weakens but does not settle
  the concern, because CDC sync cost is a different quantity from indexing cost.
- **Decision (provisional, measurement-gated):** MODEL-01 binds `CODE_RESOLUTION_CODE` for link
  semantics and does not bind the row-scoped `CODE_RESOLUTION` by default. Before that exclusion is
  treated as permanent, MODEL-01 must run one timed experiment binding the row-scoped table and record
  the sync and indexing delta in `build/task_reports/MODEL-01.json`. If the measured cost is
  acceptable, bind both and delete this exclusion; if it is not, the exclusion stands with the
  measurement as its evidence. Do not decide this by intuition in either direction.
- **Retained:** the row-scoped table stays materialized and reachable from SQL, so the NF-X01 code
  resolution truth table and any audit of a specific ambiguous code remain answerable.
- **Confidence:** medium. The link semantics argument is solid; the performance premise is unmeasured,
  which is exactly why the decision is gated on a measurement rather than taken now.
- **Rollback:** bind the row-scoped table in `sources.py`; no semantic change, only cost.
- **Status:** accepted provisionally, pending the MODEL-01 measurement.

---

## D-0020 — Seven contract ambiguities resolved in the canonical model-input layer

- **Date:** 2026-09-02
- **Trigger:** DATA-04a reached seven points where `SOURCE_CONTRACT.md` and `ATTRIBUTE_AUTHORITY.md`
  do not determine a single treatment. Per the orchestration protocol these were resolved
  provisionally rather than escalated, with the uncertainty made visible in a status or confidence
  column in every case.
- **Decisions, as implemented and each visible in output:**
  - **A1.** The DV-08 resolution *status token* is a watched value, so
    `UNRESOLVED_NULL_CONFIGURATION -> UNRESOLVED_MISSING_CONFIGURATION` mints a second audit
    assignment. This is the literal reading of "the type-resolution outcome of AH-13". DV-33 remains
    `UNKNOWN_STATE` under either reading, so no as-of answer moves.
  - **A2.** `aircraft_state` is `UNKNOWN_STATE` only when every one of AH-17 through AH-31 is null,
    because DV-33 is defined per dimension, not per attribute.
  - **A3.** Key-shift compatibility components are signature-scoped, matching DV-36's own identity
    definition. The failure mode is bounded in the safe direction: it can only over-merge into a LOW
    confidence ambiguous group, and can never assert a false `CANDIDATE_UNIQUE`.
  - **A4.** A definition functional-dependency violation keeps the subseries row with
    `definition_status='AMBIGUOUS_DEFINITION'` and null definition fields: identity is kept, the
    definition is not invented. Zero rows today.
  - **A5.** New typed rotation anomaly `TARGET_NOT_OPERATED`, ranked below `BROKEN_CONTINUITY`, for a
    rotation target that is itself cancelled or missing a time. Zero rows today.
  - **A6.** Unmatched actual and passenger observations live in `FULFILLMENT_AMBIGUOUS_GROUP` at member
    grain with a null `group_id`, because that contract row is where "unmatched observations retain a
    deterministic identity plus reason" is written.
  - **A7.** AH-32 true or null quarantines the event as `NOT_FOR_USE_EVENT` or
    `UNKNOWN_ELIGIBILITY_FLAG`, mirroring the explicit AM-15 rule. Zero rows today.
- **Confidence:** high for A1, A2, A6 and A7, which follow the literal contract text. Medium for A3,
  A4 and A5, which are unexercised by the shipped fixtures and therefore untested by data.
- **Affected artifacts/tests:** `data/model_input/*.sql`, `data/test_model_input.py`. A4, A5 and A7
  produce zero rows against the current fixture universe; REDTEAM-01 must treat "implemented but
  unexercised" as distinct from "verified" when auditing them.
- **Rollback:** each is a localized SQL branch with its own status token; reverting one does not
  disturb the others.
- **Status:** accepted provisionally.
