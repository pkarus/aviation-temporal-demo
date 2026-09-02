# Overnight multi-agent task graph

This file is the executable plan for the orchestrator. A task is green only when its success
criteria have been rerun against real artifacts. A task report is written to
`build/task_reports/<TASK_ID>.json` with commands, changed files, test output, timings, and open
issues. Blank skill cells are intentional.

## Execution DAG

```text
ORCH-00 ─┬─ SPEC-01 → SPEC-02 → SPEC-03 → DATA-01 → DATA-02 → DATA-03 → DATA-04
         ├─ ENV-01 ────────────────────────────────────────────────────────┤
         └─ INFRA-01 → INFRA-02 → INFRA-03 ───────────────────────────────┤
                                                                           ↓
                                                                     MODEL-01 → MODEL-02
                                                                           │
                                    ┌──────────────────────────────────────┼─────────────────────────┐
                                    ↓                                      ↓                         ↓
                                QUERY-UC1                              QUERY-UC2                  QUERY-ROT
                                    └──────────────────────────────────────┼─────────────────────────┘
                                                                           ↓
                                                                      QUERY-INT
                                      ┌────────────────────────────────────┼───────────────────────┐
                                      ↓                                    ↓                       ↓
                                 NOTEBOOK-01                           AGENT-01                 LAB-01
                                      ↓                                    ↓
                                 NOTEBOOK-02                           AGENT-02
                                      └───────────────────┬────────────────┘
                                                          ↓
                                                       PERF-01
                                                          ↓
                                                       HTML-01
                                                          ↓
                                                     REDTEAM-01
                                                          ↓
                                                       GATE-01
                                                          ↓
                                                     HANDOFF-01
```

## Task definitions

### ORCH-00 — Establish the orchestrated project

- **Dependencies:** none
- **Instructions:** Create the demo from the canonical template. Add `AGENTS.md`, filled `BRIEF.md`,
  this task graph, `ADVERSARIAL_REVIEW.md`, and `build/task_reports/`. Lock names, file ownership,
  dependency rules, reduced-demo fallback, confidentiality rules, and completion protocol. Do not
  inherit the template's optimization-oriented five-act assumptions.
- **Success criteria:** A fresh agent can identify scope, account, role, artifacts, dependencies,
  commands, skill routing, and release gates from `AGENTS.md` and this file alone.
- **Skills:**
- **Status:** complete when this planning turn closes green.

### INFRA-01 — Verify the target account

- **Dependencies:** none
- **Instructions:** Use only live CLI queries; do not read credential files. Connect with `-c rai`
  and record organization, account name/locator, region, current user, role, and warehouse. The long
  account-named profile currently has an invalid PAT and must not be used.
- **Success criteria:** Live output proves `NDSOEBE / RAI_SALES_ENGINEERING_AWS_US_WEST_2`, locator
  `AJB85638`, user `piotr.kraus@relational.ai`, and warehouse `RAI_XS`.
- **Skills:** `rai:rai-setup`
- **Status:** complete.

### INFRA-02 — Create the scoped role and database

- **Dependencies:** `ORCH-00`, `INFRA-01`
- **Instructions:** Run reviewed `data/00_bootstrap.sql` once as `ACCOUNTADMIN`. Create
  `RAI_DEMO_AVIATION_TEMPORAL` and `PK_AVIATION_TEMPORAL`. Grant the demo role to the current user
  and account roles `RAI_USER`, `RAI_DEVELOPER`, and `ACCOUNTADMIN`. Grant the RAI application role,
  Cortex/PyPI runtime roles, agent creation, observability, task execution, warehouse, and egress
  integration. Never confuse account roles with application roles.
- **Success criteria:** Database ownership is the demo role; requested parents can inherit it; agent
  and RAI prerequisites exist. No non-demo database is changed.
- **Skills:**
- **Status:** complete.

### INFRA-03 — Verify and freeze the security graph

- **Dependencies:** `INFRA-02`
- **Instructions:** Add a read-only `data/bootstrap_verification.sql`. Verify role parents,
  application/database roles, database owner, schemas, warehouse, and Snowflake Intelligence access.
  Test a query with `--role RAI_DEMO_AVIATION_TEMPORAL`. Never repeat ownership transfer if the
  database exists with an unexpected owner; stop and report instead.
- **Success criteria:** Verification output is saved; the demo role can use its database and
  warehouse; `RAI_USER`, `RAI_DEVELOPER`, and `ACCOUNTADMIN` are recorded as parents.
- **Skills:**
- **Status:** complete. The checked-in verification script passes against the live account.

### ENV-01 — Build a reproducible Python/RAI environment

- **Dependencies:** `ORCH-00`, `INFRA-01`
- **Instructions:** Create a fresh `.venv` with `uv`; do not copy sibling virtual environments.
  Pin a RelationalAI version supporting the APIs selected by later tasks, plus notebook/test/chart
  dependencies. Run `.venv/bin/rai connect`. Record Python, SDK, CLI, and Snowflake CLI versions.
  The reference demo's installed SDK is only `1.2.2`; do not assume it satisfies current deployment
  or optional path APIs. Validate every preview dependency before allowing it onto the critical path.
- **Success criteria:** Lockfile exists; clean install succeeds; `rai connect` reaches the verified
  account; a version manifest is saved.
- **Skills:** `rai:rai-setup`

### SPEC-01 — Freeze adversarial semantic decisions

- **Dependencies:** `ORCH-00`
- **Instructions:** Re-read the four external customer documents as source requirements. Turn every
  finding in `ADVERSARIAL_REVIEW.md` into a chosen treatment, explicit limitation, or fixture. In
  particular resolve same-day date semantics, end-of-life behavior, incomplete snapshots, capacity
  carrier dimension, and exact versus candidate matching.
- **Success criteria:** No P0 item lacks a decision or hard test. G1 cannot pass with “TBD” in an
  identity, validity, carrier, amendment, or end-of-life rule.
- **Skills:**

### SPEC-02 — Author source and ontology contracts

- **Dependencies:** `SPEC-01`
- **Instructions:** Create `SOURCE_CONTRACT.md`, `ATTRIBUTE_AUTHORITY.md`, and
  `NEO4J_RAI_MAPPING.md`. Document source grain/key/type/nullability, reduced demo columns,
  authoritative sources, identity/state split, interval convention, provenance, code-resolution
  semantics, route/schedule grain, fulfillment, rotation, and every Neo4j node/edge mapping. Use
  association concepts for multi-attribute temporal links.
- **Success criteria:** Every modeled field traces to a documented source column or declared
  synthetic derivation. Every in-scope attribute has one owner and temporal treatment. G1 passes.
- **Skills:** `rai:rai-ontology`

### SPEC-03 — Define questions, oracles, and scoped parity claims

- **Dependencies:** `SPEC-02`
- **Instructions:** Create `DEMO_QUESTIONS.md`, `EXPECTED_ANSWERS.yaml`, and
  `NEO4J_PARITY_MATRIX.md`. For all eight questions specify parameters, reasoner classification,
  feasibility, named expected rows, SQL oracle shape, RAI shape, parity claim, differentiation, and
  limitation. Classify rotation as ordinary self-reference unless an installed-version path test
  proves a graph reasoner is useful. Do not invent optimization or prediction.
- **Success criteria:** Expected answers exist before generator/query implementation and are frozen.
  Claims are limited to supplied workloads.
- **Skills:** `rai:rai-discovery`

### DATA-01 — Specify deterministic synthetic fixtures

- **Dependencies:** `SPEC-03`
- **Instructions:** Write `data/SYNTHETIC_DATA_SPEC.md`: fixed seed/date, `smoke` and `demo` scales,
  row budget, table distributions, stable keys, named fixture IDs, expected-answer ownership, and all
  negative fixtures from the adversarial review. Target roughly 100k–170k raw demo rows and keep each
  table below 500k. Random filler may not alter anchored results.
- **Success criteria:** Every expected answer and boundary rule maps to explicit input rows; scale is
  sufficient for semantics but is labeled non-production.
- **Skills:**

### DATA-02 — Implement the generator

- **Dependencies:** `DATA-01`
- **Instructions:** Implement a deterministic generator with `--scale smoke|demo`, assertions,
  stable IDs, generated manifests, and realistic but synthetic identifiers. Generate only documented
  or query-relevant columns. Include code-resolution ambiguity, snapshot completeness, same-day
  ordering, independent dimension changes, codeshare, stopover, diversion, and union-precedence cases.
- **Success criteria:** Two clean runs produce identical manifests and anchored rows; generator unit
  tests pass; no customer data appears in output.
- **Skills:**

### DATA-03 — Create and load the Snowflake source layer

- **Dependencies:** `DATA-02`, `INFRA-03`, `ENV-01`
- **Instructions:** Implement idempotent DDL/load scripts in `data/`. Load only with connection `rai`
  and `--role RAI_DEMO_AVIATION_TEMPORAL`. Use `SOURCE`, `MODEL_INPUT`, `VALIDATION`, `NOTEBOOKS`, and
  `RAI_AGENT`. Preserve logical view semantics but materialize a physical schedules table for RAI.
  Add comments, PK/FK metadata, manifest checks, and change tracking on every `model.Table()` source.
  Serialize all Snowflake mutations through this task owner.
- **Success criteria:** Clean load and rerun succeed; row counts match manifests; types match the
  contract; resolution cardinalities and snapshot completeness pass; change tracking is live. G3 passes.
- **Skills:**

### DATA-04 — Build canonical temporal inputs and independent SQL oracles

- **Dependencies:** `DATA-03`
- **Instructions:** Build canonicalization and interval-candidate SQL without pre-answering the RAI
  semantic questions. Implement itinerary de-duplication, typed historical/forward union, aircraft
  assignment candidates, schedule presence/coalescing, exact/candidate schedule changes, resolution
  tables, optional fulfillment, rotation self-reference, and date calendars. Use half-open intervals,
  date+sequence ordering, explicit completeness, and two clocks. Independently implement raw-fixture
  SQL oracles and compare complete result sets to `EXPECTED_ANSWERS.yaml`.
- **Success criteria:** All adversarial temporal tests and eight SQL result sets pass. Concurrent route
  states are preserved; incomplete snapshots do not create removals. G2 and G4 pass.
- **Skills:**

### MODEL-01 — Build the canonical modular ontology

- **Dependencies:** `DATA-04`
- **Instructions:** Implement strict-mode `rai_code/aviation_model/` with core source mappings,
  computed temporal semantics, and no application-specific output formatting. Use `model.Table()`,
  stable identities, functional Properties only after multiplicity proof, labeled same-type roles,
  association concepts for validity/provenance, both schedule clocks, explicit unresolved mappings,
  and lineage. Keep temporal predicates and cross-use-case enrichment visible in RAI.
- **Success criteria:** Model loads live under the demo role; counts and relationships are nonempty;
  type/FD tests pass; `inspect.schema()` inventory is saved; no implicit-property or deprecated-API
  warnings. G5 passes.
- **Skills:** `rai:rai-ontology`, then `rai:rai-pyrel`

### MODEL-02 — Produce the standalone Snowflake upload artifact

- **Dependencies:** `MODEL-01`
- **Instructions:** Generate, rather than independently hand-maintain, `rai_code/manual/aviation_temporal.py`
  from the canonical package where possible. Remove local relative-import assumptions and secrets.
  Test it in a Snowsight/Workspace-like runtime and compare its schema inventory with the package.
- **Success criteria:** Both forms produce identical ontology inventories and smoke-query results in
  the target runtime.
- **Skills:** `rai:rai-pyrel`

### QUERY-UC1 — Implement aircraft-history questions

- **Dependencies:** `MODEL-02`, `DATA-04`
- **Exclusive files:** `rai_code/queries/uc1.py`, `tests/test_uc1.py`
- **Instructions:** Implement aircraft as-of reconstruction, every status-reversion spell, 120
  month-end fleet series, and independent type/engine history. Cover before-first-event, boundary,
  after-EOL, same-day ordering, irrelevant events, missing config, and repeated `A -> B -> A`.
- **Success criteria:** Complete result sets equal the independent manifest and SQL oracle; no pandas
  query logic; all boundary tests pass.
- **Skills:** `rai:rai-pyrel`

### QUERY-UC2 — Implement schedule questions

- **Dependencies:** `MODEL-02`, `DATA-04`
- **Exclusive files:** `rai_code/queries/uc2.py`, `tests/test_uc2.py`
- **Instructions:** Implement exact schedule modifications, additions/removals, candidate amendments,
  market entries/exits, and capacity. Require explicit knowledge/operating dates and carrier dimension.
  Preserve ambiguity, concurrent states, codeshare semantics, cabin reconciliation, disappearance,
  reappearance, and missing/incomplete snapshots.
- **Success criteria:** Complete outputs equal manifest and SQL oracle; heuristic rows expose confidence
  and evidence; physical capacity never double-counts codeshares.
- **Skills:** `rai:rai-pyrel`

### QUERY-ROT — Implement rotation and cross-use-case enrichment

- **Dependencies:** `MODEL-02`, `DATA-04`, `ENV-01`
- **Exclusive files:** `rai_code/queries/rotation.py`, `tests/test_rotation.py`
- **Instructions:** Implement ordered rotation over typed `next_flight`, using actual airports and
  times, then enrich each leg with as-of type/engine. Validate same-aircraft continuity, nondecreasing
  time, no self-loop/cycle, divergence, cancellation, missing time, and broken links. Keep self-reference
  query as the supported baseline. Use path enumeration only if a runtime test passes and it adds value.
- **Success criteria:** Ordered chain and enrichment equal the oracle. No scheduled-arrival shortcut.
  Optional graph path and baseline return identical fixture chains.
- **Skills:** `rai:rai-pyrel`; add `rai:rai-graph-analysis` only for a validated optional graph implementation.

### QUERY-INT — Integrate and benchmark all queries

- **Dependencies:** `QUERY-UC1`, `QUERY-UC2`, `QUERY-ROT`
- **Instructions:** Assemble the three owned modules without rewriting them. Add stable query catalog
  functions, parameter validation, aliases, machine-readable output, exact result comparison, and
  cold/warm timing. Do not update frozen expected answers to make a failing implementation pass.
- **Success criteria:** One command executes all eight live queries, reproduces expected rows, and
  writes results/timings. G6 passes.
- **Skills:** `rai:rai-pyrel`

### NOTEBOOK-01 — Build and execute the local technical notebook

- **Dependencies:** `QUERY-INT`
- **Instructions:** Build a notebook showing the source question, concise PyRel, results, Neo4j-to-RAI
  translation, evidence, and limitations for each act. Include ontology, timeline, two-clock, change,
  and rotation visualizations. Prefer five live acts with three appendix queries.
- **Success criteria:** Headless execution succeeds; all eight questions and figures render; there are
  no placeholders or hidden manual state.
- **Skills:**

### NOTEBOOK-02 — Upload and verify the Snowsight notebook

- **Dependencies:** `NOTEBOOK-01`, `INFRA-03`, `ENV-01`
- **Instructions:** Create stage/notebook artifacts under the demo database with the demo role. Upload
  the standalone model/query files, configure packages, execute, and verify visual rendering. UI
  inspection is required when a signed-in browser is available.
- **Success criteria:** Remote execution is green and visible under intended role contexts.
- **Skills:** `browser:control-in-app-browser` only for UI verification.

### AGENT-01 — Deploy a curated Snowflake Intelligence agent

- **Dependencies:** `QUERY-INT`, `INFRA-03`, `ENV-01`
- **Instructions:** Implement deploy/update/status/chat/debug commands and a curated `QueryCatalog`.
  Put sprocs/stage in `PK_AVIATION_TEMPORAL.RAI_AGENT` and the agent in
  `SNOWFLAKE_INTELLIGENCE.AGENTS`. Every tool documents both clocks, carrier dimension, exact versus
  candidate changes, mixed-engine limitation, and safe empty/unsupported behavior. Prefer deployed
  model materializations for predictable performance.
- **Success criteria:** Direct sproc calls, status, and a canonical chat work live; agent is visible to
  demo, RAI user/developer, and admin contexts.
- **Skills:** `rai:rai-deployment`

### AGENT-02 — Adversarially evaluate the agent

- **Dependencies:** `AGENT-01`
- **Instructions:** Build canonical prompts, paraphrases, ambiguous-clock/carrier prompts, invalid
  dates/IDs, unsupported mixed-engine asks, amendment-confidence asks, and attempts to mix planned
  and actual airports. Trace tool calls and compare to expected catalog IDs/parameters/results.
- **Success criteria:** Supported prompts return anchored answers; ambiguity asks for missing semantics;
  unsupported questions do not hallucinate; every tool error is surfaced. G8 passes.
- **Skills:**

### LAB-01 — Create a skill-assisted ontology editing lab

- **Dependencies:** `QUERY-INT`
- **Instructions:** Create a customer-facing lab that inspects the real schema, adds one reversible
  derived temporal rule, validates it, queries it, and restores baseline. The lab must demonstrate
  how AI agents use RAI skills without modifying frozen golden-answer semantics.
- **Success criteria:** A fresh agent can complete the lab from its instructions and all before/after
  validations pass.
- **Skills:** `rai:rai-ontology`, `rai:rai-pyrel`

### PERF-01 — Measure and diagnose declared-scale performance

- **Dependencies:** `NOTEBOOK-02`, `AGENT-02`, `LAB-01`
- **Instructions:** Record row counts, SDK/engine/config, source sync, compile, each query, notebook,
  and agent latency for smoke/demo scale, cold and warm. Start with one XS logic engine and five-minute
  auto-suspend. Do not use these results as a production sizing benchmark. Diagnose before resizing.
- **Success criteria:** Timing JSON and report are complete; any engine change has metric evidence;
  claims distinguish cold, warm, materialized, and agent latency. G7 passes.
- **Skills:** `rai:rai-health` only if performance, CDC, or transaction thresholds fail.

### HTML-01 — Build the self-contained technical runbook

- **Dependencies:** `PERF-01`
- **Instructions:** Generate `RUNNING.html` with preflight, exact account/role, commands, fallback path,
  five live acts plus appendix, ontology/timeline/two-clock diagrams, code excerpts, parity matrix,
  expected outputs, timings, troubleshooting, and limitations. Position RAI as proven parity for these
  workloads and differentiated by Snowflake-native data/governance/agent access. Never claim universal
  Neo4j replacement or production performance. Keep customer documents out of the HTML.
- **Success criteria:** Opens without network dependencies; all tabs/images/commands work; every claim
  traces to live evidence; UC1-only fallback is truthful and runnable.
- **Skills:** `browser:control-in-app-browser` only for render QA.

### REDTEAM-01 — Independently attack the finished demo

- **Dependencies:** `HTML-01`
- **Instructions:** A reviewer who did not author the implementation reruns grants, fixtures, full
  result comparisons, temporal boundaries, wrong-clock/wrong-grain queries, agent prompts, notebook,
  performance artifacts, HTML claims, and confidentiality checks. Do not accept producer summaries.
- **Success criteria:** `REDTEAM_REPORT.md` has no unresolved severity-1/2 findings. Every parity row
  is evidence-backed and overbroad superiority claims are absent.
- **Skills:**

### GATE-01 — Implement the complete prep gate

- **Dependencies:** `REDTEAM-01`
- **Instructions:** Implement `prep_demo.py` to verify account/role, role graph, schemas/counts,
  metadata/change tracking, expected manifests, temporal integrity, SQL oracles, ontology inventory,
  eight queries, agent/direct sprocs/evals, notebooks, figures, HTML, and artifact freshness. Run once
  cold and once warm. No mocks or silent warnings.
- **Success criteria:** Both runs exit zero and save machine-readable results. Any failure returns
  nonzero and names the responsible upstream task. G9 passes.
- **Skills:**

### HANDOFF-01 — Package the overnight result

- **Dependencies:** `GATE-01`
- **Instructions:** Write `HANDOFF_BRIEFING.md` with technical talk track, fixture catalog, limitations,
  measured timings, troubleshooting, reduced-demo fallback, and manual teardown instructions. Commit
  all intended artifacts, but do not push unless separately requested.
- **Success criteria:** A fresh engineer can run and narrate the demo from `RUNNING.html`; git status
  and artifact provenance are understood; the handoff contains no unverified claims.
- **Skills:**

## Current orchestration state (2026-09-02, orchestrator restart)

The previous autonomous run ended inside DATA-03 with the loader written but unexecuted. D-0017
superseded that publication apparatus. This section is the resume point; it is updated in place,
not appended to, so it always describes now.

### Green and committed

| Task | Evidence |
|---|---|
| ORCH-00, INFRA-01/02/03, ENV-01 | role, database, grants and venv verified live |
| SPEC-01/02/03 | source contract, attribute authority, Neo4j mapping, 8 questions, 24 frozen result sets, parity matrix |
| DATA-01/02 | deterministic generator, manifest 1.1.0, byte-identical across clean and reordered runs |
| DATA-03 | 145,054 rows across ten SOURCE tables, change tracking on, counts equal the manifest |
| PROBE-01 | twelve PyRel uncertainties resolved by live probe, in `build/design/PROBE_RESULTS.md` |
| DATA-04a | MODEL_INPUT canonical temporal layer built |
| DATA-04b | independent SQL oracles reproduce all 24 frozen result sets |
| MODEL-01/02 | 44 concepts, 1292 properties, 170 rules; standalone artifact generated from the package; 93 of 93 gate tests verified green by the orchestrator on its own 21-minute live run |
| FIDELITY-01 | Neo4j structural audit; found one supplied edge missing and three documents falsely claiming it; all repairs landed |

### In flight

QUERY-UC1 (Q01-Q04), QUERY-UC2 (Q05-Q07), QUERY-ROT (Q08), ENRICH-02 (local generator
enrichment), and the reference-pattern extraction feeding the notebook, agent, HTML and gate
phases.

### The open substantive problem

Measured live, the loaded data does not tell the customer's story. `aircraft_state` and
`aircraft_status` average 1.005 and 1.004 versions per aircraft with only 2 of 999 aircraft ever
changing, while `aircraft_type` and `engine_type` average 48.034 versions each. The status
vocabulary across 48,000 events is In Service 47,991, Storage 7, Maintenance 2. Both directions
contradict the customer document: they describe status as changing repeatedly with aircraft coming
out of storage back into service, and type changes as rare conversions. Golden question 2 is
entirely about In Service to Storage to In Service spells and has almost nothing to show; golden
question 3's ten-year month-end series is nearly flat.

D-0023 through D-0026 accept an additive enrichment that raises state to 8.57 versions, status to
2.32 with 467 aircraft changing, 439 storage spells, and reduces type and engine to 1.20 and 1.31
real conversions. No frozen expected value may move; 24 new result sets are added instead.

### Sequencing rule for the enrichment

ENRICH-02 is local only: generator, local tests, loader field count, regenerated CSVs. The
Snowflake reload, the MODEL_INPUT rebuild, the oracle re-verification and the model count
re-verification are orchestrator-owned and must not start until the three query agents have
finished, because they query the live model and a mid-flight reload would make their results
shift under them. Frozen expectations do not move under the enrichment, so queries authored now
stay valid afterwards.

### Pending operational actions

- Engine auto-suspend on `aviation_temporal_logic_s` was raised from 5 to 60 minutes to make an
  iterative build possible against a 631-second cold start. Set it back before handoff:
  `.venv/bin/rai reasoners alter --type Logic --name aviation_temporal_logic_s --auto-suspend-mins 5`
- After the enrichment reload, add the 24 new expected result sets (a separate task, since they
  must be derived from the enriched data).
- `RouteState.schedules` is declared and correct but evaluates to zero rows: the single non-null
  `schedule_key` in the current dataset points at a schedule with no route state. The enrichment
  is the fix.

## Orchestrator contract

- Dispatch a task only after every dependency is green.
- Run only one Snowflake-mutating task at a time. Parallel agents may read Snowflake.
- Parallel code tasks must own disjoint files. Only `QUERY-INT` assembles query modules.
- Before using a listed skill, the assigned agent reads its complete `SKILL.md`. Blank means no skill.
- Expected answers freeze at `SPEC-03`; fix data/code, not expectations.
- After bootstrap, every Snowflake mutation specifies connection `rai` and role
  `RAI_DEMO_AVIATION_TEMPORAL`.
- A failed task stays failed until its own success criteria rerun green. Dispatch a repair task with
  the original transcript; do not mark the downstream task green by workaround.
- No success may rely only on import checks, mocks, CLI deployment existence, or producer assertions
  when live execution is required.
- Keep confidential inputs outside the repo and do not externally host the HTML without authorization.
- If the overnight run cannot pass UC2, preserve the verified UC1 vertical slice and narrow the agent,
  HTML, and claims. Never hide missing functionality.

## Scope reduction, 2026-09-02

The user narrowed the deliverable to the ontology plus the eight RAI queries. `NOTEBOOK-01`,
`NOTEBOOK-02`, `AGENT-01`, `AGENT-02`, `LAB-01`, `PERF-01`, `HTML-01`, `REDTEAM-01`, `GATE-01` and
`HANDOFF-01` are descoped and not attempted. Their definitions above are left intact and unedited,
with dependencies unchanged, so a later session can resume any of them directly.

Retained: `MODEL-01`, `MODEL-02`, `QUERY-UC1`, `QUERY-UC2`, `QUERY-ROT`, `QUERY-INT`, each still bound
by the success criteria written above. `QUERY-INT` remains the terminal gate for this reduced scope
and still records cold and warm timings.

The completion protocol in the "Orchestrator contract" section still applies to every retained task.
In particular, expected answers stay frozen at `SPEC-03`, a failed task stays failed until its own
criteria rerun green, and no success may rest on an import check, a mock, or a producer assertion
where live execution is required. See `BRIEF.md` for what this reduction costs relative to the
original definition of done.
