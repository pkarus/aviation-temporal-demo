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
