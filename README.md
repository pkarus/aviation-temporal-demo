# Aviation temporal intelligence demo

This repository implements a Snowflake-native RelationalAI demonstration of temporal aircraft,
schedule, passenger-flight, and rotation analysis. It is designed for customer data engineers and
data scientists evaluating the supplied workloads against their current Neo4j approach.

## Start the autonomous build

Open a Codex session with this repository as its working directory:

```text
/Users/piotrkraus/rai-repos/rai-demos/aviation_temporal_demo
```

Paste the prompt in [`ORCHESTRATOR_PROMPT.md`](ORCHESTRATOR_PROMPT.md). The orchestrator reads
[`AGENTS.md`](AGENTS.md), executes [`TASK_GRAPH.md`](TASK_GRAPH.md), dispatches independent agents,
records reviewed choices in [`DECISION_LOG.md`](DECISION_LOG.md), and continues until the cold and
warm end-to-end gates pass or no authorized work remains.

Do not start from the parent `rai-demos` directory: that adds unrelated demos to the working context
and makes file ownership and Git status ambiguous.

## Live target

- Snowflake connection: `rai`
- Account: `NDSOEBE.RAI_SALES_ENGINEERING_AWS_US_WEST_2`
- Database: `PK_AVIATION_TEMPORAL`
- Role: `RAI_DEMO_AVIATION_TEMPORAL`
- Warehouse: `RAI_XS`

The one-time account bootstrap is complete. All later Snowflake mutations use the demo role.

## Authoritative workflow

`TASK_GRAPH.md` supersedes the generic inherited `PIPELINE.md`. A task is green only after its live
success criteria pass. Task evidence lives in `build/task_reports/`; expected answers freeze before
implementation; Snowflake writes are serialized; and the independently runnable UC1 vertical slice
is the reduced-demo fallback.

The release artifacts are the standalone Python ontology, verified queries, local and Snowsight
notebooks, curated Snowflake Intelligence agent, ontology editing lab, `RUNNING.html`, performance
evidence, and `HANDOFF_BRIEFING.md`.

## Confidentiality and claims

The source customer documents remain outside this repository. The demo can establish parity only
for the supplied, tested workloads. It does not claim universal Neo4j replacement or extrapolate
production performance from synthetic data.
