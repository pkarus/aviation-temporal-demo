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
- **Tests:** verify remote visibility is private and fetch/push succeed.
- **Rollback:** transfer the repository or replace `origin` after explicit owner selection.
- **Status:** approved by the user's request to create and push a private remote.
