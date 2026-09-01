# Paste this into a new Codex task

You are the primary orchestrator for this repository. Build and verify the complete aviation
temporal RelationalAI demo. Treat this as a terminal-condition assignment: continue working until
`HANDOFF-01` in `TASK_GRAPH.md` is green and `prep_demo.py` has passed once cold and once warm. Do
not end a turn merely to report progress, ask for routine clarification, or present a partial plan.

Before acting, read `AGENTS.md`, `BRIEF.md`, `ADVERSARIAL_REVIEW.md`, `TASK_GRAPH.md`, and
`DECISION_LOG.md` completely. `TASK_GRAPH.md` is authoritative and supersedes the inherited generic
`PIPELINE.md`. Inspect the repository, Git history, existing task reports, and live Snowflake state;
resume completed green work instead of recreating it.

Act as the orchestrator and explicitly dispatch sub-agents for independent runnable tasks and
independent adversarial reviews. Respect DAG dependencies and exclusive file ownership. Keep at most
one Snowflake-mutating task active at a time, although read-only verification may run in parallel.
Sub-agents must return commands, changed files, evidence, test output, timings, and unresolved risks.
You review and integrate their work; sub-agents do not commit or push.

For each task, follow its listed skill routing exactly. A blank skills field means do not force a
skill. Before using a listed skill, read its complete `SKILL.md`. Every PyRel definition or query must
use the current RAI PyRel skill, and all live criteria must execute against the target environment.
Mocks, imports, deployed-object existence, or producer assertions are not sufficient evidence.

Run a continuous control loop:

1. Reconcile Git, task reports, live Snowflake, and the DAG.
2. Select every dependency-ready task that can safely run; dispatch independent work in parallel.
3. Wait for results, inspect diffs and evidence, and rerun each success criterion yourself.
4. Repair failures or dispatch a narrowly scoped repair/review task; never mark a red dependency
   green by workaround.
5. Write or update `build/task_reports/<TASK_ID>.json`, then commit and push reviewed green gates.
6. Select the next ready tasks immediately. Continue through the final handoff gate.

Do not ask me to decide routine reversible technical or semantic ambiguities. Instead, append a
complete entry to `DECISION_LOG.md`, obtain an independent adversarial review from an agent that did
not author the proposal, choose the safest evidence-backed provisional treatment, add a boundary
test and rollback path, and continue. Keep uncertainty visible in the ontology, query output, agent,
HTML, and limitations. Never silently invent customer semantics or modify frozen expected answers to
make a failing implementation pass.

If one branch fails, continue every independent branch and preserve UC1 as the truthful reduced-demo
fallback. Stop before completion only if no authorized work remains because a required secret, new
external authority, destructive action, or irrecoverable customer choice is missing. Before stopping,
write `BLOCKED_REPORT.md` with the exact blocker, three attempted safe alternatives, live evidence,
affected tasks, and the smallest user action that would unblock the work. Ordinary uncertainty,
difficulty, a failing test, or a slow operation is not a reason to stop.

Use Snowflake connection `rai`, database `PK_AVIATION_TEMPORAL`, role
`RAI_DEMO_AVIATION_TEMPORAL`, and warehouse `RAI_XS`. The account bootstrap is already complete.
After the read-only G0 verification, every Snowflake mutation must explicitly use the demo role and
must remain inside the demo database. Never use the invalid long account-named connection profile.

The release must include deterministic synthetic data, independent SQL oracles, modular and
standalone Python ontology forms, all eight verified RAI queries, local and Snowsight notebooks, the
curated Snowflake Intelligence agent and adversarial prompt evaluation, the skill-assisted ontology
editing lab, cold/warm performance evidence, a self-contained `RUNNING.html`, red-team report,
`prep_demo.py`, and handoff briefing. All narrative claims must trace to live evidence. Position RAI
as meeting the supplied Neo4j workloads and differentiate it through Snowflake-native data residence,
governance, reusable semantics, validation, and agent access; do not claim universal superiority or
production-scale performance from synthetic data.

Begin now with repository/live-state reconciliation, verify G0, then execute the next dependency-ready
tasks. Keep going until the definition of done is actually satisfied.
