"""agent/deploy.py - lifecycle CLI for the aviation temporal Snowflake Intelligence agent.

Run every command from the repository root::

    .venv/bin/python -m agent.deploy preflight
    .venv/bin/python -m agent.deploy deploy
    .venv/bin/python -m agent.deploy update
    .venv/bin/python -m agent.deploy status
    .venv/bin/python -m agent.deploy chat "..."
    .venv/bin/python -m agent.deploy debug
    .venv/bin/python -m agent.deploy setup-sql --deployer-role RAI_DEMO_AVIATION_TEMPORAL
    .venv/bin/python -m agent.deploy teardown

Three placement facts, each of which costs a wasted deploy to rediscover.

* **The agent object goes in ``SNOWFLAKE_INTELLIGENCE.AGENTS``.** The Snowflake Intelligence
  picker lists only agents in that schema. The four stored procedures and the stage stay in
  ``PK_AVIATION_TEMPORAL.RAI_AGENT``; ``DeploymentConfig.agent_schema`` is what splits them.
* **Every Snowflake mutation runs as ``RAI_DEMO_AVIATION_TEMPORAL``.** The connection profile's
  default role is broader than this demo needs, so :func:`_build_manager` issues an explicit
  ``USE ROLE`` before anything else rather than relying on the profile default.
* **``init_tools`` runs inside the stored procedure**, in a fresh Python process with no
  repository checkout. It therefore imports the catalog and the ontology from inside its own
  body, and :mod:`agent.queries` does the model import once behind a model-lock retry.

Concurrency. Importing the ontology is a write transaction on the shared named model; a
concurrent reader fails with ``prepareIndex: model is currently locked`` rather than waiting.
A ``deploy``, a ``preflight`` with tools, a ``chat`` round trip, a ``pytest`` gate and a direct
``demo_queries`` run are five separate processes that each do their own model import, so run
them one at a time. :mod:`agent.queries` retries through the lock, but serialising is still the
right habit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# ``queries`` and ``aviation_model`` are top-level packages rooted at ``rai_code``, not at the
# repository root. discover_imports() resolves a module through importlib, so this path has to
# be present in the deploying interpreter for the ontology and the catalog to be found and
# uploaded at all. Inside the sproc the path does not exist and the insert is a harmless no-op;
# Snowpark has already registered both packages by then.
_RAI_CODE = str(REPO_ROOT / "rai_code")
if _RAI_CODE not in sys.path:
    sys.path.insert(0, _RAI_CODE)

from relationalai.agent.cortex import (  # noqa: E402
    CortexAgentManager,
    DeploymentConfig,
    QueryCatalog,
    ToolRegistry,
    discover_imports,
)
from relationalai.config import SnowflakeConnection, create_config  # noqa: E402

# ---------------------------------------------------------------------------------
# Configuration - the locked names from BRIEF.md
# ---------------------------------------------------------------------------------

AGENT_NAME = "AVIATION_TEMPORAL"
MODEL_NAME = "aviation_temporal"
DATABASE = "PK_AVIATION_TEMPORAL"
SCHEMA = "RAI_AGENT"
# The agent must live here to appear in the Snowflake Intelligence picker; the sprocs and the
# stage stay in {DATABASE}.{SCHEMA}.
AGENT_SCHEMA = "SNOWFLAKE_INTELLIGENCE.AGENTS"
WAREHOUSE = "RAI_XS"
ROLE = "RAI_DEMO_AVIATION_TEMPORAL"

# The ontology import inside the sproc costs roughly two minutes on a warm engine, and Q01 is a
# 19-29 second query on top of that, so the 300 second default is too tight for a cold sproc.
QUERY_TIMEOUT_S = 900


def _agent_location() -> str:
    return AGENT_SCHEMA or f"{DATABASE}.{SCHEMA}"


def _build_manager() -> CortexAgentManager:
    session = create_config().get_session(SnowflakeConnection)
    session.sql(f"USE ROLE {ROLE}").collect()
    session.sql(f"USE WAREHOUSE {WAREHOUSE}").collect()
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}").collect()
    return CortexAgentManager(
        session=session,
        config=DeploymentConfig(
            agent_name=AGENT_NAME,
            model_name=MODEL_NAME,
            database=DATABASE,
            schema=SCHEMA,
            agent_schema=AGENT_SCHEMA,
            warehouse=WAREHOUSE,
            query_timeout_s=QUERY_TIMEOUT_S,
            # QueryCatalog is PREVIEW in SDK 1.20.1, so the flag is required even though
            # nothing in this demo is prescriptive or predictive.
            allow_preview=True,
        ),
    )


# ---------------------------------------------------------------------------------
# init_tools - executed inside every sproc invocation
# ---------------------------------------------------------------------------------


def init_tools() -> ToolRegistry:
    """Build the tool registry inside the stored procedure.

    Self-contained by contract: it closes over no session, connection or dataframe, and it
    imports the catalog and the ontology from inside its own body so both resolve from the
    packaged sproc code rather than from the deployer's process.

    The catalog is registered **without** ``model=``, which is deliberate. Passing the model
    would switch ``QueryCatalog`` into catalog-plus-dynamic mode and let the agent author ad-hoc
    query specs against the ontology at runtime. This demo's whole point is a curated surface
    with frozen expected answers, and an ad-hoc path is exactly how an unsupported request such
    as the exact mixed-engine set turns into a plausible fabricated answer. Catalog-only makes
    the SDK tell the agent, in its own orchestration instructions, that it cannot answer
    anything outside these entries.

    The import is absolute rather than relative on purpose. ``python -m agent.deploy`` makes
    this module ``__main__``, so cloudpickle serialises ``init_tools`` by value; a relative
    ``from . import queries`` then depends on ``__package__`` surviving that round trip, while
    ``from agent import queries`` only depends on the ``agent`` package Snowpark has already
    registered as a top-level import.
    """
    from agent import queries as catalog

    return ToolRegistry().add(
        model=catalog.model_package().model,
        description=catalog.MODEL_DESCRIPTION,
        queries=QueryCatalog(*catalog.CATALOG),
    )


# ---------------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------------


def _print_status(manager: CortexAgentManager) -> None:
    status = manager.status()
    print(
        json.dumps(
            {
                "agent": f"{_agent_location()}.{AGENT_NAME}",
                "agent_exists": status.agent_exists,
                "sproc_schema": f"{DATABASE}.{SCHEMA}",
                "stage_exists": status.stage_exists,
                "sprocs": status.sprocs,
                "fully_deployed": status.fully_deployed(),
            },
            indent=2,
        )
    )


def cmd_deploy(manager: CortexAgentManager) -> int:
    print(
        f"Deploying sprocs to {DATABASE}.{SCHEMA} and agent {AGENT_NAME} "
        f"to {_agent_location()} as role {ROLE} ..."
    )
    manager.deploy(init_tools=init_tools, imports=discover_imports())
    _print_status(manager)
    return 0


def cmd_update(manager: CortexAgentManager) -> int:
    print(f"Updating stored procedures for {AGENT_NAME} ...")
    manager.update(init_tools=init_tools, imports=discover_imports())
    _print_status(manager)
    return 0


def cmd_status(manager: CortexAgentManager) -> int:
    _print_status(manager)
    return 0


def cmd_chat(manager: CortexAgentManager, message: str, *, trace: bool) -> int:
    response = manager.chat().send(message)
    if trace:
        print("--- tool calls ---")
        for call in response.tool_calls():
            print(f"{call.name}: {json.dumps(call.arguments, default=str)[:2000]}")
        print("--- tool results ---")
        for result in response.tool_results():
            payload = result.json_result()
            print(f"{result.name}: {json.dumps(payload, default=str)[:6000]}")
        print("--- final text ---")
    print(response.full_text())
    return 0


def cmd_preflight(manager: CortexAgentManager) -> int:
    report = manager.preflight(init_tools=init_tools)
    print(report.format(config=manager.config, role=report.role))
    return 1 if report.has_errors else 0


def cmd_setup_sql(manager: CortexAgentManager, deployer_role: str, si_role: str | None) -> int:
    out = manager.print_setup_sql(deployer_role=deployer_role, si_role=si_role)
    if out:
        print(out)
    return 0


def cmd_teardown(manager: CortexAgentManager) -> int:
    print(
        f"Tearing down agent {AGENT_NAME} from {_agent_location()} and sprocs from "
        f"{DATABASE}.{SCHEMA} ..."
    )
    print("WARNING: this permanently deletes the agent's Snowflake Intelligence history.")
    manager.cleanup()
    _print_status(manager)
    return 0


# ---------------------------------------------------------------------------------
# debug - the three checks the cortex-integration skill prescribes, in order
# ---------------------------------------------------------------------------------


def _call(session: Any, sql: str) -> Any:
    print(f"\nSQL> {sql}")
    rows = session.sql(sql).collect()
    if not rows or rows[0][0] is None:
        return None
    raw = rows[0][0]
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def cmd_debug(
    manager: CortexAgentManager,
    question: str,
    query_id: str,
    query_json: str | None,
) -> int:
    """Describe the agent, invoke each sproc directly, then trace one chat turn.

    A successful ``deploy`` means the objects exist. It does not mean the agent answers. A
    direct ``CALL`` is the fastest way to read the real error, because Snowflake returns the
    import failure, missing grant or model construction failure verbatim instead of the agent
    wrapping it in a generic envelope.
    """
    fq = f"{DATABASE}.{SCHEMA}"
    session = manager._session

    print("=== agent spec ===")
    try:
        described = manager._api.describe(
            manager.config.agent_database,
            manager.config.agent_schema_name,
            manager.config.agent_name,
        )
        spec = described.agent_spec
        print(
            json.dumps(
                {
                    "owner": described.owner,
                    "database": described.database_name,
                    "schema": described.schema_name,
                    "name": described.name,
                    "tools": [
                        (tool.to_dict() if hasattr(tool, "to_dict") else dict(tool))
                        for tool in (spec.tools or [])
                    ]
                    if spec is not None
                    else None,
                },
                indent=2,
                default=str,
            )[:6000]
        )
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        print(f"describe failed: {exc}")

    print("\n=== direct sproc calls ===")
    payload = _call(session, f"CALL {fq}.RAI_DISCOVER_MODELS()")
    print(json.dumps(payload, indent=2, default=str)[:8000])
    if payload is None:
        print("DISCOVER returned nothing; nothing downstream can succeed.")
        return 1
    model_id = 0

    explain = _call(session, f"CALL {fq}.RAI_EXPLAIN_CONCEPT({model_id}, '{query_id}')")
    print(json.dumps(explain, indent=2, default=str)[:4000])

    if query_json:
        escaped = query_json.replace("'", "''")
        result = _call(session, f"CALL {fq}.RAI_QUERY_MODEL({model_id}, '{escaped}')")
        print(json.dumps(result, indent=2, default=str)[:12000])

    if not question:
        return 0
    print("\n=== chat turn ===")
    return cmd_chat(manager, question, trace=True)


# ---------------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage the aviation temporal Cortex agent lifecycle."
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("deploy", help="Preflight, then create stage, sprocs and agent")
    sub.add_parser("update", help="Update sprocs without re-registering the agent")
    sub.add_parser("status", help="Print deployment status")

    chat_p = sub.add_parser("chat", help="Send one message to the deployed agent")
    chat_p.add_argument("message", help="Message to send")
    chat_p.add_argument(
        "--trace",
        action="store_true",
        help="Print the tool calls and raw tool-result envelopes before the answer",
    )

    debug_p = sub.add_parser(
        "debug", help="Describe the agent, call the sprocs directly, trace one chat turn"
    )
    debug_p.add_argument(
        "--question",
        default="What can I ask about?",
        help="Question to trace through one chat turn",
    )
    debug_p.add_argument(
        "--query-id",
        default="demo_scope_and_limits",
        help="Catalog query id to explain via RAI_EXPLAIN_CONCEPT",
    )
    debug_p.add_argument(
        "--query-json",
        default=None,
        help='Optional RAI_QUERY_MODEL payload, e.g. \'{"id":"aircraft_as_of",'
        '"args":{"aircraft_id":1001,"as_of_date":"2026-08-31"}}\'',
    )

    sub.add_parser("preflight", help="Probe grants and payload sizes without deploying")
    sub.add_parser("teardown", help="Remove the agent, sprocs and stage")

    setup_p = sub.add_parser("setup-sql", help="Emit a paste-ready GRANT block")
    setup_p.add_argument("--deployer-role", default=ROLE)
    setup_p.add_argument("--si-role", default=None)

    args = parser.parse_args(argv)
    manager = _build_manager()

    if args.command == "deploy":
        return cmd_deploy(manager)
    if args.command == "update":
        return cmd_update(manager)
    if args.command == "status":
        return cmd_status(manager)
    if args.command == "chat":
        return cmd_chat(manager, args.message, trace=args.trace)
    if args.command == "debug":
        return cmd_debug(manager, args.question, args.query_id, args.query_json)
    if args.command == "preflight":
        return cmd_preflight(manager)
    if args.command == "teardown":
        return cmd_teardown(manager)
    if args.command == "setup-sql":
        return cmd_setup_sql(manager, args.deployer_role, args.si_role)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
