#!/usr/bin/env python
"""DATA-04b -- independent SQL oracles for the eight golden questions.

This runner executes hand-written SQL oracles directly against
``PK_AVIATION_TEMPORAL.SOURCE`` and compares every declared result set in
``EXPECTED_ANSWERS.yaml`` as a complete, ordered, typed sequence.

Independence contract
---------------------
The oracles read raw ``SOURCE`` fixtures only. They never read
``PK_AVIATION_TEMPORAL.MODEL_INPUT``, ``data/model_input/`` or
``data/build_model_input.py``. Agreement between this oracle and the DATA-04a
canonicalisation layer is therefore evidence, not tautology.

Snowflake access is read-only: every statement is a ``SELECT`` issued through
``snow sql -f`` with ``-c rai --role RAI_DEMO_AVIATION_TEMPORAL``. No table,
view, stage or temporary object is created.

Usage
-----
    .venv/bin/python data/run_oracles.py --all
    .venv/bin/python data/run_oracles.py --question Q05
    .venv/bin/python data/run_oracles.py --result-set Q07-MARKETING
    .venv/bin/python data/run_oracles.py --all --report build/task_reports/DATA-04b.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORACLE_DIR = os.path.join(REPO_ROOT, "data", "oracles")
EXPECTED_PATH = os.path.join(REPO_ROOT, "EXPECTED_ANSWERS.yaml")
OUTPUT_DIR = os.path.join(REPO_ROOT, "build", "oracle_results")

CONNECTION = "rai"
ROLE = "RAI_DEMO_AVIATION_TEMPORAL"

# ---------------------------------------------------------------------------
# Non-derivable presentation labels
# ---------------------------------------------------------------------------
# ``row_id`` is a frozen manifest label, not a value any query can compute from
# the source fixtures: it is neither positional (Q05 and Q07 interleave the
# v1.0 and D-0010 repair ranges) nor derivable from any documented rule.
#
# Q05 ``event_id`` for exact and unpaired rows is likewise a hand-authored
# mnemonic (``SYN-CHG-20260810-BASE-SEATS``, ``SYN-UNPAIR-ADD-20260831``);
# ATTRIBUTE_AUTHORITY.md DV-34/DV-35/DV-36 define SHA-256 identities, not these
# strings, and the mnemonics follow no consistent generative rule. Because the
# frozen ``order_by`` sorts on ``event_id``, the oracle has to be told them in
# order to reproduce the declared row order at all; ``data/oracles/
# q05_event_labels.sql`` therefore carries them as a declared label table keyed
# on the *independently computed* semantic identity of each event. Candidate,
# ambiguous-group and member event ids, and every ``group_id``, ARE derived.
#
# These columns are compared too, but they are additionally reported as
# ``label_columns`` so a reader can see exactly which part of the verdict is
# independent and which part is a declared label.
LABEL_COLUMNS = {
    "Q01": ["row_id"],
    "Q02": ["row_id"],
    "Q03": ["row_id"],
    "Q04": ["row_id"],
    "Q05": ["row_id", "event_id"],
    "Q06": ["row_id"],
    "Q07": ["row_id"],
    "Q08": ["row_id"],
}

# Result sets whose row_id sequence is exactly positional under the declared
# order_by. For these the oracle assigns row_id itself; for the rest the label
# is taken positionally from the frozen manifest and flagged.
POSITIONAL_ROW_IDS = {
    "Q02-CANONICAL": ("Q02-R", 1, 3),
    "Q03-CANONICAL": ("Q03-R", 1, 3),
    "Q04-CANONICAL": ("Q04-R", 1, 3),
    "Q06-CANONICAL": ("Q06-R", 1, 3),
    "Q08-CANONICAL": ("Q08-R", 1, 3),
    "Q08-ANOMALIES": ("Q08-R", 4, 3),
}

SQL_FILES = {
    "Q01": "q01_aircraft_as_of.sql",
    "Q02": "q02_status_reversion_spells.sql",
    "Q03": "q03_month_end_fleet_composition.sql",
    "Q04": "q04_type_engine_histories.sql",
    "Q05": "q05_schedule_four_week_changes.sql",
    "Q06": "q06_market_latest_vs_seven_days.sql",
    "Q07": "q07_route_capacity_two_clocks.sql",
    "Q08": "q08_actual_rotation_enriched.sql",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Snowflake execution (read-only, via snow sql -f)
# ---------------------------------------------------------------------------
class SnowError(RuntimeError):
    pass


def run_sql(sql: str, label: str) -> list[dict[str, Any]]:
    """Execute one read-only SELECT and return JSON rows."""
    stripped = re.sub(r"--[^\n]*", "", sql)
    first = stripped.strip().lstrip("(").strip().upper()
    if not first.startswith(("WITH", "SELECT")):
        raise SnowError(f"{label}: refusing to run a non-SELECT statement")
    for banned in ("INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP",
                   "ALTER", "TRUNCATE", "GRANT", "REVOKE", "COPY"):
        if re.search(rf"\b{banned}\b", stripped.upper()):
            raise SnowError(f"{label}: refusing to run a statement containing {banned}")

    fd, path = tempfile.mkstemp(suffix=".sql", prefix=f"oracle_{label}_")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(sql.rstrip().rstrip(";") + ";\n")
        proc = subprocess.run(
            ["snow", "sql", "-c", CONNECTION, "--role", ROLE, "-f", path, "--format", "JSON"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise SnowError(f"{label}: snow sql failed rc={proc.returncode}\n"
                            f"{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}")
        out = proc.stdout.strip()
        start = out.find("[")
        if start < 0:
            raise SnowError(f"{label}: no JSON payload in snow sql output:\n{out[-2000:]}")
        payload = json.loads(out[start:])
        if payload and isinstance(payload[0], list):  # multi-statement
            payload = payload[-1]
        return payload
    finally:
        os.unlink(path)


def render(sql_name: str, params: dict[str, Any]) -> str:
    with open(os.path.join(ORACLE_DIR, sql_name)) as fh:
        sql = fh.read()
    for include in ("AIRCRAFT_TEMPORAL", "SCHEDULE_TEMPORAL", "Q05_EVENT_LABELS"):
        token = "{{%s}}" % include
        if token in sql:
            fname = {
                "AIRCRAFT_TEMPORAL": "_aircraft_temporal.sql.inc",
                "SCHEDULE_TEMPORAL": "_schedule_temporal.sql.inc",
                "Q05_EVENT_LABELS": "q05_event_labels.sql",
            }[include]
            with open(os.path.join(ORACLE_DIR, fname)) as fh:
                sql = sql.replace(token, fh.read())
    for key, value in params.items():
        token = "{{%s}}" % key
        if token not in sql:
            continue
        if isinstance(value, bool):
            raise SnowError(f"unexpected boolean parameter {key}")
        if isinstance(value, int):
            literal = str(value)
        elif isinstance(value, str):
            if not re.fullmatch(r"[A-Za-z0-9 _:\-]+", value):
                raise SnowError(f"unsafe parameter value for {key}: {value!r}")
            literal = value
        else:
            raise SnowError(f"unsupported parameter type for {key}: {type(value)}")
        sql = sql.replace(token, literal)
    leftovers = re.findall(r"\{\{[A-Za-z0-9_]+\}\}", sql)
    if leftovers:
        raise SnowError(f"{sql_name}: unsubstituted placeholders {sorted(set(leftovers))}")
    return sql


# ---------------------------------------------------------------------------
# Typed parameter validation (runs BEFORE any query is executed)
# ---------------------------------------------------------------------------
def parse_date(raw: Any) -> _dt.date | None:
    if raw is None or not isinstance(raw, str) or not DATE_RE.match(raw):
        return None
    try:
        return _dt.date.fromisoformat(raw)
    except ValueError:
        return None


def validate_parameters(question_id: str, params: dict[str, Any]) -> str | None:
    """Return an error_code, or None when the parameters are valid."""
    if question_id in ("Q01", "Q02", "Q04", "Q08"):
        aid = params.get("aircraft_id")
        if aid is None or not isinstance(aid, int) or isinstance(aid, bool) or aid <= 0:
            return "INVALID_AIRCRAFT_ID"
    if question_id == "Q01":
        if parse_date(params.get("as_of_date")) is None:
            return "INVALID_DATE"
    if question_id == "Q03":
        for name in ("start_month_end", "end_month_end"):
            if parse_date(params.get(name)) is None:
                return "INVALID_DATE"
        if params.get("status") is None:
            return "MISSING_STATUS"
    if question_id == "Q05":
        for name in ("start_knowledge_date", "end_knowledge_date"):
            if params.get(name) is None:
                return "MISSING_KNOWLEDGE_DATE"
            if parse_date(params.get(name)) is None:
                return "INVALID_DATE"
        cadence = params.get("cadence_days")
        if cadence is None or not isinstance(cadence, int) or cadence < 1:
            return "INVALID_CADENCE_DAYS"
    if question_id == "Q06":
        for name in ("latest_knowledge_date", "comparison_knowledge_date"):
            if params.get(name) is None:
                return "MISSING_KNOWLEDGE_DATE"
        if params.get("carrier_role") is None:
            return "MISSING_CARRIER_ROLE"
        for name in ("latest_knowledge_date", "comparison_knowledge_date"):
            if parse_date(params.get(name)) is None:
                return "INVALID_DATE"
        if params["carrier_role"] not in ("marketing", "operating"):
            return "INVALID_CARRIER_ROLE"
    if question_id == "Q07":
        if params.get("knowledge_date") is None:
            return "MISSING_KNOWLEDGE_DATE"
        if params.get("operating_date") is None:
            return "MISSING_OPERATING_DATE"
        if params.get("carrier_role") is None:
            return "MISSING_CARRIER_ROLE"
        for name in ("knowledge_date", "operating_date"):
            if parse_date(params.get(name)) is None:
                return "INVALID_DATE"
        if params["carrier_role"] not in ("marketing", "operating"):
            return "INVALID_CARRIER_ROLE"
    if question_id == "Q08":
        if parse_date(params.get("flight_departure_date")) is None:
            return "INVALID_DATE"
    return None


# ---------------------------------------------------------------------------
# Snapshot-endpoint eligibility (Q05 / Q06 pre-gate)
# ---------------------------------------------------------------------------
_ELIGIBILITY_CACHE: dict[str, dict[str, Any]] | None = None


def snapshot_calendar() -> dict[str, dict[str, Any]]:
    global _ELIGIBILITY_CACHE
    if _ELIGIBILITY_CACHE is None:
        rows = run_sql(open(os.path.join(ORACLE_DIR, "snapshot_calendar.sql")).read(),
                       "snapshot_calendar")
        _ELIGIBILITY_CACHE = {r["EXPECTED_PUBLISH_DATE"]: r for r in rows}
    return _ELIGIBILITY_CACHE


def endpoint_status(dates: list[str]) -> str | None:
    """ENDPOINT_MISSING wins over ENDPOINT_INCOMPLETE; None means both eligible."""
    cal = snapshot_calendar()
    missing, incomplete = [], []
    for d in dates:
        row = cal.get(d)
        if row is None or not row["IS_PRESENT"]:
            missing.append(d)
        elif not row["IS_COMPLETE"]:
            incomplete.append(d)
    if missing:
        return "ENDPOINT_MISSING"
    if incomplete:
        return "ENDPOINT_INCOMPLETE"
    return None


# ---------------------------------------------------------------------------
# Canonicalisation and comparison
# ---------------------------------------------------------------------------
def canon(value: Any, declared_type: str) -> Any:
    if value is None:
        return None
    t = declared_type.upper()
    if t.startswith("NUMBER"):
        return int(value)
    if t == "FLOAT":
        return float(value)
    if t == "BOOLEAN":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)
    if t in ("DATE", "TIME", "TIMESTAMP_NTZ", "VARCHAR"):
        return str(value)
    raise SnowError(f"unknown declared type {declared_type}")


def canonical_row(raw: dict[str, Any], schema: list[dict[str, Any]]) -> dict[str, Any]:
    upper = {k.upper(): v for k, v in raw.items()}
    row = {}
    for col in schema:
        name = col["name"]
        if name.upper() not in upper:
            row[name] = "<<MISSING COLUMN>>"
        else:
            row[name] = canon(upper[name.upper()], col["type"])
    extras = sorted(set(upper) - {c["name"].upper() for c in schema})
    if extras:
        row["<<EXTRA COLUMNS>>"] = extras
    return row


def compare(expected: list[dict], actual: list[dict], schema, label_cols) -> dict[str, Any]:
    diffs = []
    for idx in range(max(len(expected), len(actual))):
        e = expected[idx] if idx < len(expected) else None
        a = actual[idx] if idx < len(actual) else None
        if e is None:
            diffs.append({"position": idx, "kind": "EXTRA_ACTUAL_ROW", "actual": a})
            continue
        if a is None:
            diffs.append({"position": idx, "kind": "MISSING_ACTUAL_ROW", "expected": e})
            continue
        cell = {k: {"expected": e.get(k), "actual": a.get(k)}
                for k in list(e) + [x for x in a if x not in e]
                if e.get(k) != a.get(k)}
        if cell:
            diffs.append({"position": idx, "kind": "CELL_MISMATCH",
                          "row_id_expected": e.get("row_id"), "row_id_actual": a.get("row_id"),
                          "cells": cell, "expected": e, "actual": a})
    semantic_diffs = [d for d in diffs
                      if d["kind"] != "CELL_MISMATCH"
                      or any(c not in label_cols for c in d["cells"])]
    dup_expected = len({r.get("row_id") for r in expected}) != len(expected)
    dup_actual = len({r.get("row_id") for r in actual}) != len(actual)
    return {
        "expected_rows": len(expected),
        "actual_rows": len(actual),
        "duplicate_row_id_expected": dup_expected,
        "duplicate_row_id_actual": dup_actual,
        "diff_count": len(diffs),
        "semantic_diff_count": len(semantic_diffs),
        "diffs": diffs[:40],
        "verdict": "PASS" if (not diffs and not dup_expected and not dup_actual) else "FAIL",
        "semantic_verdict": "PASS" if (not semantic_diffs and not dup_actual) else "FAIL",
    }


def result_hash(rows: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# Execution of one result set
# ---------------------------------------------------------------------------
def execute_result_set(question: dict, rs: dict) -> dict[str, Any]:
    qid = question["question_id"]
    rsid = rs["result_set_id"]
    schema = question["output_schema"]
    label_cols = LABEL_COLUMNS[qid]
    params = dict(rs["parameters"])
    expected_rows = [canonical_row(r, schema) for r in rs["rows"]]
    started = time.time()

    record: dict[str, Any] = {
        "result_set_id": rsid,
        "question_id": qid,
        "catalog_id": question["catalog_id"],
        "parameters": params,
        "expected_invocation_status": rs["invocation_status"],
        "expected_error_code": rs.get("error_code"),
        "expected_cardinality": rs["expected_cardinality"],
        "order_by": question["order_by"],
        "label_columns": label_cols,
    }

    # 1. typed parameter validation, before any query executes
    error_code = validate_parameters(qid, params)
    if error_code is not None:
        record.update({
            "actual_invocation_status": "PARAMETER_ERROR",
            "actual_error_code": error_code,
            "query_executed": False,
            "actual_rows": [],
        })
        record["comparison"] = compare(expected_rows, [], schema, label_cols)
        record["status_match"] = (rs["invocation_status"] == "PARAMETER_ERROR"
                                  and rs.get("error_code") == error_code)
        record["elapsed_seconds"] = round(time.time() - started, 3)
        record["verdict"] = ("PASS" if record["status_match"]
                             and record["comparison"]["verdict"] == "PASS" else "FAIL")
        return record

    # 2. snapshot-endpoint eligibility gate for the two snapshot questions
    if qid == "Q05":
        gate = endpoint_status([params["start_knowledge_date"], params["end_knowledge_date"]])
    elif qid == "Q06":
        gate = endpoint_status([params["comparison_knowledge_date"], params["latest_knowledge_date"]])
    else:
        gate = None
    if gate is not None:
        record.update({
            "actual_invocation_status": gate,
            "actual_error_code": gate,
            "query_executed": False,
            "actual_rows": [],
        })
        record["comparison"] = compare(expected_rows, [], schema, label_cols)
        record["status_match"] = (rs["invocation_status"] == gate and rs.get("error_code") == gate)
        record["elapsed_seconds"] = round(time.time() - started, 3)
        record["verdict"] = ("PASS" if record["status_match"]
                             and record["comparison"]["verdict"] == "PASS" else "FAIL")
        return record

    # 3. run the oracle
    sql = render(SQL_FILES[qid], params)
    raw_rows = run_sql(sql, rsid)
    actual_rows = [canonical_row(r, schema) for r in raw_rows]

    # 4. attach the row_id label
    if rsid in POSITIONAL_ROW_IDS:
        prefix, start, width = POSITIONAL_ROW_IDS[rsid]
        for i, row in enumerate(actual_rows):
            row["row_id"] = f"{prefix}{start + i:0{width}d}"
        record["row_id_source"] = "DERIVED_POSITIONAL"
    elif rsid == "Q01-CANONICAL":
        for row in actual_rows:
            row["row_id"] = "Q01-R001"
        record["row_id_source"] = "DERIVED_POSITIONAL"
    elif len(actual_rows) == len(expected_rows):
        for row, exp in zip(actual_rows, expected_rows):
            row["row_id"] = exp["row_id"]
        record["row_id_source"] = "DECLARED_MANIFEST_LABEL_POSITIONAL"
    else:
        for i, row in enumerate(actual_rows):
            row["row_id"] = f"<<UNLABELLED-{i:03d}>>"
        record["row_id_source"] = "UNAVAILABLE_CARDINALITY_MISMATCH"

    actual_status = "OK"
    actual_error = None
    if qid == "Q08" and not actual_rows:
        actual_status, actual_error = "NOT_FOUND", "NO_ACTUAL_FLIGHTS"

    record.update({
        "actual_invocation_status": actual_status,
        "actual_error_code": actual_error,
        "query_executed": True,
        "actual_rows": actual_rows,
        "actual_result_hash": result_hash(actual_rows),
        "expected_result_hash": result_hash(expected_rows),
    })
    record["comparison"] = compare(expected_rows, actual_rows, schema, label_cols)
    record["status_match"] = (rs["invocation_status"] == actual_status
                              and rs.get("error_code") == actual_error)
    record["elapsed_seconds"] = round(time.time() - started, 3)
    record["verdict"] = ("PASS" if record["status_match"]
                         and record["comparison"]["verdict"] == "PASS" else "FAIL")
    return record


# ---------------------------------------------------------------------------
# Cross-question closure and adversarial probes
# ---------------------------------------------------------------------------
def verify_declared_hashes(doc: dict) -> list[dict[str, Any]]:
    qs = {q["question_id"]: q for q in doc["questions"]}
    closure = doc["cross_question_event_closure"]

    def h(obj):
        return hashlib.sha256(
            json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()

    q6 = qs["Q06"]
    q6_canon = next(r for r in q6["result_sets"] if r["result_set_id"] == "Q06-CANONICAL")
    checks = [
        {"name": "q06_preservation.prior_v1_0_and_current_canonical_result_set_sha256",
         "scope": "Q06-CANONICAL parsed result-set object",
         "expected": closure["q06_preservation"]["prior_v1_0_and_current_canonical_result_set_sha256"],
         "actual": h(q6_canon)},
        {"name": "q06_preservation.current_v1_1_result_sets_sha256",
         "scope": "Q06 parsed result_sets list",
         "expected": closure["q06_preservation"]["current_v1_1_result_sets_sha256"],
         "actual": h(q6["result_sets"])},
        {"name": "q07_preservation.prior_v1_0_result_sets_sha256",
         "scope": "Q07 parsed result_sets list",
         "expected": closure["q07_preservation"]["prior_v1_0_result_sets_sha256"],
         "actual": h(qs["Q07"]["result_sets"])},
    ]
    for c in checks:
        c["verdict"] = "PASS" if c["expected"] == c["actual"] else "FAIL"
    return checks


def verify_q05_closure(doc: dict, q05_rows: list[dict] | None) -> dict[str, Any]:
    closure = doc["cross_question_event_closure"]
    out: dict[str, Any] = {"checks": []}

    def add(name, ok, detail=""):
        out["checks"].append({"name": name, "verdict": "PASS" if ok else "FAIL", "detail": detail})

    if q05_rows is None:
        add("q05_closure", False, "Q05-CANONICAL did not execute")
        out["verdict"] = "FAIL"
        return out

    add("q05_expected_cardinality",
        len(q05_rows) == closure["q05_expected_cardinality"],
        f"{len(q05_rows)} rows vs declared {closure['q05_expected_cardinality']}")

    by_pair: dict[tuple[str, str], int] = {}
    for r in q05_rows:
        by_pair[(r["previous_knowledge_date"], r["comparison_date"])] = \
            by_pair.get((r["previous_knowledge_date"], r["comparison_date"]), 0) + 1
    for decl in closure["q05_rows_by_adjacent_pair"]:
        key = (decl["previous_knowledge_date"], decl["comparison_date"])
        add(f"q05_pair_{key[0]}_to_{key[1]}",
            by_pair.get(key, 0) == decl["expected_count"],
            f"{by_pair.get(key, 0)} vs {decl['expected_count']}")

    exact_presence = [r for r in q05_rows if r["event_class"] in ("EXACT_ADDITION", "EXACT_REMOVAL")]
    partnered: set[tuple[str, str, str]] = set()
    for r in q05_rows:
        if r["event_class"] == "CANDIDATE_UNIQUE":
            partnered.add((r["comparison_date"], "REMOVED", r["schedule_key"]))
            partnered.add((r["comparison_date"], "ADDED", r["related_schedule_key"]))
        if r["event_class"] == "AMBIGUOUS_GROUP_MEMBER":
            partnered.add((r["comparison_date"], r["member_side"], r["member_schedule_key"]))
    unpaired = {(r["comparison_date"], r["member_side"], r["member_schedule_key"])
                for r in q05_rows if r["event_class"] in ("UNPAIRED_ADDITION", "UNPAIRED_REMOVAL")}
    ok, detail = True, []
    for r in exact_presence:
        side = "ADDED" if r["event_class"] == "EXACT_ADDITION" else "REMOVED"
        key = (r["comparison_date"], side, r["schedule_key"])
        in_p, in_u = key in partnered, key in unpaired
        if in_p == in_u:
            ok = False
            detail.append(f"{key} partnered={in_p} unpaired={in_u}")
    add("exact_presence_partner_closure", ok, "; ".join(detail))

    declared_unpaired = {(d["side"], d["schedule_key"])
                         for d in closure["exact_presence_partner_closure"]["unpaired_exact_to_evidence"]}
    computed_unpaired = {(s, k) for (_, s, k) in unpaired}
    add("declared_unpaired_set_matches",
        declared_unpaired == computed_unpaired,
        f"declared-only={sorted(declared_unpaired - computed_unpaired)} "
        f"computed-only={sorted(computed_unpaired - declared_unpaired)}")

    out["verdict"] = "PASS" if all(c["verdict"] == "PASS" for c in out["checks"]) else "FAIL"
    return out


# Contract truth tables that this oracle recomputes from raw SOURCE. The value
# is the SQL file plus the columns that are declared manifest labels rather
# than computed values (case names and assertion prose have no source column).
TRUTH_TABLE_ORACLES = {
    "TT-BOTH-CLOCKS":           ("tt_both_clocks.sql", ["row_id"]),
    "TT-UTC-OFFSETS":           ("tt_utc_offsets.sql", ["row_id", "source_case"]),
    "TT-CABIN-QUALITY":         ("tt_cabin_quality.sql", ["row_id"]),
    "TT-CODE-RESOLUTION":       ("tt_code_resolution.sql", ["row_id"]),
    "TT-SENTINELS":             ("tt_sentinels.sql", ["row_id", "case_id", "assertion"]),
    "TT-MIXED-ENGINE-LIMIT":    ("tt_mixed_engine_limit.sql", ["row_id"]),
    "TT-PLAN-ACTUAL-DIVERSION": ("tt_plan_actual_diversion.sql", ["row_id", "passenger_token"]),
}
# Truth tables deliberately NOT recomputed here, with the reason.
TRUTH_TABLE_NOT_ORACLED = {
    "TT-SNAPSHOT-COMPLETENESS":
        "Every substantive assertion (no inference at the missing 2026-10-12 or incomplete "
        "2026-10-19 snapshot, previous eligible complete date 2026-10-05, the single post-gap "
        "closure at 2026-10-26, reappearance opening a new segment) is proved live by the "
        "incomplete_snapshots_create_no_removals probe. The four manifest rows are a curated "
        "case selection whose case_id/presence_outcome strings are labels, not a query result.",
    "TT-US-CLOCK-AUTHORITY":
        "Its expected_outcome column is assertion prose (KEEP_EXPANDED_TIMESTAMP_AP09_NOT_OVERRIDE "
        "and similar), not a computable value. The underlying behaviour is exercised by "
        "TT-UTC-OFFSETS (AP-09 never repairs) and by Q08-CANONICAL (AF-06 local day selected even "
        "though AF-07 is the next UTC date).",
    "TT-PASSENGER-UNION":
        "Passenger PF/PH canonical-union precedence is the fulfillment layer; no Q01-Q08 result "
        "set depends on it, so DATA-04b does not own an independent oracle for it.",
    "TT-FULFILLMENT":
        "Fulfillment matching and the DV-43 null-ID lineage fallback are the fulfillment layer; "
        "no Q01-Q08 result set depends on them. The declared DV-43 digest is verified as a "
        "manifest constant only.",
}


# Which DATA-04b artifact exercises each hard test. "not owned" entries name
# the layer that owns them; DATA-04b does not silently claim them.
HARD_TEST_EVIDENCE = {
    "HT-01": "Q02-CANONICAL; probe A_TO_B_TO_A_PRESERVED_AS_THREE_ASSIGNMENTS",
    "HT-02": "Q01-CANONICAL",
    "HT-03": "Q02-CANONICAL; probe SAME_DAY_AUDIT_SEQUENCE_PRESERVED",
    "HT-04": "Q01-UNKNOWN-GAP; probe UNRESOLVED_CONFIGURATION_OPENS_ONE_GAP_NOT_TWO",
    "HT-05": "Q01-CANONICAL, Q04-CANONICAL, TT-BOTH-CLOCKS; probe HALF_OPEN_NO_OVERLAPPING_DAILY_ASSIGNMENTS",
    "HT-06": "TT-SENTINELS; probe SOURCE_UNKNOWN_FUTURE_SENTINEL_PRESENT_IN_SOURCE",
    "HT-07": "TT-SENTINELS; probes DERIVED_BOUNDS_NEVER_USE_SOURCE_SENTINEL_99991231, AH06_SENTINEL_EVENT_MINTS_NO_ASSIGNMENT",
    "HT-08": "Q01-BEFORE-FIRST, Q01-UNKNOWN-GAP, Q01-EOL-BOUNDARY, Q01-CANONICAL",
    "HT-09": "Q01-EOL-BOUNDARY, TT-SENTINELS; probes EOL_EXCLUSIVE_PREVIOUS_DAY_ELIGIBLE / BOUNDARY_DAY_EXCLUDED",
    "HT-10": "Q01-EOL-BOUNDARY",
    "HT-11": "not owned by DATA-04b (SOURCE_CONTRACT.md / ATTRIBUTE_AUTHORITY.md field census, DATA-03 gate)",
    "HT-12": "Q05-INELIGIBLE-ENDPOINT; probe MISSING_SNAPSHOT_20261012_NOT_ELIGIBLE + NO_SEGMENT_BOUNDARY_ON_INELIGIBLE_DATES",
    "HT-13": "probes INCOMPLETE_20261019_ROWS_RETAINED_BUT_INERT, GAP_CONTROL_CLOSES_ONLY_AT_20261026, GAP_CONTROL_PREVIOUS_ELIGIBLE_IS_20261005",
    "HT-14": "Q06-INCOMPLETE-ENDPOINT",
    "HT-15": "Q05-R020 / Q05-R024 inside Q05-CANONICAL; probe REAPPEARANCE_OPENS_A_NEW_SEGMENT",
    "HT-16": "Q05-CANONICAL (BASE_100 V01/V02/DUP canonical selection); probe NF_S01_SEMANTIC_DUPLICATE_COLLAPSES_TO_ONE",
    "HT-17": "probe NF_S02_UNCHANGED_OBSERVATION_MINTS_NO_STATE",
    "HT-18": "Q07-MARKETING, Q07-OPERATING",
    "HT-19": "Q05-CANONICAL exact key-preserving modification rows",
    "HT-20": "Q05-CANONICAL rows R004/R005/R006 (unique candidate)",
    "HT-21": "Q05-CANONICAL rows R008..R014 (ambiguous group)",
    "HT-22": "Q05-CANONICAL unpaired evidence + q05 cross-question closure check",
    "HT-23": "TT-BOTH-CLOCKS",
    "HT-24": "Q07-MISSING-KNOWLEDGE-DATE, Q07-MISSING-OPERATING-DATE",
    "HT-25": "TT-UTC-OFFSETS",
    "HT-26": "Q06-MISSING-CARRIER-ROLE, Q07-MISSING-CARRIER-ROLE, Q07-MARKETING, Q07-OPERATING",
    "HT-27": "Q07-OPERATING (UNRESOLVED_PHYSICAL_SERVICE, codeshare never double counted)",
    "HT-28": "TT-CABIN-QUALITY",
    "HT-29": "Q06-CANONICAL + q05 cross-question closure",
    "HT-30": "not owned by DATA-04b (passenger canonical-union layer)",
    "HT-31": "not owned by DATA-04b (fulfillment layer)",
    "HT-32": "not owned by DATA-04b (fulfillment layer; DV-43 digest verified as a manifest constant only)",
    "HT-33": "TT-PLAN-ACTUAL-DIVERSION, Q08-ANOMALIES (DIVERSION_ENDPOINT_CONFLICT)",
    "HT-34": "Q08-CANONICAL (AF-06 local day selected although AF-07 is 2026-09-01)",
    "HT-35": "Q08-ANOMALIES",
    "HT-36": "Q08-ANOMALIES rows R012/R013/R014",
    "HT-37": "Q08-CANONICAL",
    "HT-38": "TT-CODE-RESOLUTION",
    "HT-39": "Q01-UNKNOWN-GAP",
    "HT-40": "TT-MIXED-ENGINE-LIMIT; probe MIXED_ENGINE_SET_INCOMPLETE_NOT_FABRICATED",
    "HT-41": "not owned by DATA-04b (MODEL-01 live gate)",
    "HT-42": "all 24 result sets compared as complete ordered typed sequences",
    "HT-43": "not owned by DATA-04b (MODEL-02 inventory gate)",
    "HT-44": "timings recorded per result set in build/oracle_results/",
    "HT-45": "not owned by DATA-04b (release claim scan)",
    "HT-46": "Q01, Q02, Q03, Q04",
    "HT-47": "every catalog_id and typed parameter set is invoked by --all",
    "HT-48": "Q01-INVALID-AIRCRAFT-ID, Q06-INVALID-DATE, Q06-MISSING-CARRIER-ROLE, Q07-MISSING-* , TT-MIXED-ENGINE-LIMIT",
    "HT-49": "Q05 exact/candidate/ambiguous/unpaired labels, q05 closure, Q08 plan vs actual fields",
}


def run_truth_tables(doc: dict) -> list[dict[str, Any]]:
    out = []
    by_id = {t["truth_table_id"]: t for t in doc["contract_truth_tables"]}
    for tt_id, (fname, label_cols) in TRUTH_TABLE_ORACLES.items():
        tt = by_id[tt_id]
        schema = tt["output_schema"]
        expected = [canonical_row(r, schema) for r in tt["rows"]]
        started = time.time()
        rec: dict[str, Any] = {"truth_table_id": tt_id, "sql_file": f"data/oracles/{fname}",
                               "label_columns": label_cols,
                               "expected_cardinality": tt["expected_cardinality"]}
        try:
            raw = run_sql(render(fname, {}), tt_id)
            actual = [canonical_row(r, schema) for r in raw]
            for i, row in enumerate(actual):
                for col in label_cols:
                    row[col] = expected[i][col] if i < len(expected) else f"<<UNLABELLED-{i}>>"
            rec["actual_rows"] = actual
            rec["comparison"] = compare(expected, actual, schema, label_cols)
            rec["verdict"] = rec["comparison"]["verdict"]
        except Exception as exc:  # noqa: BLE001
            rec["verdict"] = "ERROR"
            rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["elapsed_seconds"] = round(time.time() - started, 3)
        out.append(rec)
    return out


def run_probes() -> list[dict[str, Any]]:
    """Adversarial temporal probes required by the DATA-04 success criteria."""
    probes = []
    for fname, name in (("probe_concurrent_route_states.sql", "concurrent_route_states_preserved"),
                        ("probe_incomplete_snapshots.sql", "incomplete_snapshots_create_no_removals"),
                        ("probe_temporal_integrity.sql", "temporal_integrity_and_sentinels"),
                        ("probe_schedule_canonicalisation.sql", "schedule_canonicalisation_and_no_change")):
        rows = run_sql(render(fname, {}), name)
        failing = [r for r in rows if str(r.get("VERDICT", "")).upper() != "PASS"]
        probes.append({
            "probe": name,
            "sql_file": f"data/oracles/{fname}",
            "rows": rows,
            "verdict": "PASS" if not failing and rows else "FAIL",
            "failing": failing,
        })
    return probes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    import yaml

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--question", action="append", default=[])
    ap.add_argument("--result-set", action="append", default=[])
    ap.add_argument("--report", default=None)
    ap.add_argument("--skip-probes", action="store_true")
    args = ap.parse_args()

    if not (args.all or args.question or args.result_set):
        ap.error("pass --all, --question Qnn or --result-set ID")

    with open(EXPECTED_PATH) as fh:
        doc = yaml.safe_load(fh)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    wanted_q = {q.upper() for q in args.question}
    wanted_rs = {r.upper() for r in args.result_set}

    started = time.time()
    records: list[dict[str, Any]] = []
    for question in doc["questions"]:
        qid = question["question_id"]
        for rs in question["result_sets"]:
            rsid = rs["result_set_id"]
            if not args.all and qid not in wanted_q and rsid.upper() not in wanted_rs:
                continue
            try:
                rec = execute_result_set(question, rs)
            except Exception as exc:  # noqa: BLE001 - report, never hide
                rec = {"result_set_id": rsid, "question_id": qid, "verdict": "ERROR",
                       "error": f"{type(exc).__name__}: {exc}"}
            records.append(rec)
            print(f"{rec['verdict']:<5} {rsid:<28} "
                  f"expected={rec.get('comparison', {}).get('expected_rows', '-')} "
                  f"actual={rec.get('comparison', {}).get('actual_rows', '-')} "
                  f"{rec.get('elapsed_seconds', '-')}s", flush=True)
            with open(os.path.join(OUTPUT_DIR, f"{rsid}.json"), "w") as fh:
                json.dump(rec, fh, indent=2, sort_keys=False)

    hashes = verify_declared_hashes(doc)
    for c in hashes:
        print(f"{c['verdict']:<5} hash {c['name']}")

    q05 = next((r for r in records if r["result_set_id"] == "Q05-CANONICAL"), None)
    closure = verify_q05_closure(doc, q05.get("actual_rows") if q05 and q05.get("query_executed") else None)
    print(f"{closure['verdict']:<5} q05 cross-question closure")

    probes = [] if args.skip_probes else run_probes()
    for p in probes:
        print(f"{p['verdict']:<5} probe {p['probe']}")

    truth_tables = [] if args.skip_probes else run_truth_tables(doc)
    for t in truth_tables:
        print(f"{t['verdict']:<5} truth-table {t['truth_table_id']}")

    summary = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "total_seconds": round(time.time() - started, 3),
        "result_sets": [{"result_set_id": r["result_set_id"], "verdict": r["verdict"],
                         "semantic_verdict": r.get("comparison", {}).get("semantic_verdict"),
                         "expected_rows": r.get("comparison", {}).get("expected_rows"),
                         "actual_rows": r.get("comparison", {}).get("actual_rows"),
                         "actual_result_hash": r.get("actual_result_hash"),
                         "elapsed_seconds": r.get("elapsed_seconds")} for r in records],
        "declared_hash_checks": hashes,
        "q05_cross_question_closure": closure,
        "adversarial_probes": [{k: v for k, v in p.items() if k != "rows"} | {"row_count": len(p["rows"])}
                               for p in probes],
        "contract_truth_tables": [{k: v for k, v in t.items() if k != "actual_rows"}
                                  for t in truth_tables],
        "contract_truth_tables_not_oracled": TRUTH_TABLE_NOT_ORACLED,
        "hard_test_coverage_evidence": HARD_TEST_EVIDENCE,
    }
    failures = [r for r in records if r["verdict"] != "PASS"]
    summary["passed"] = len(records) - len(failures)
    summary["failed"] = len(failures)
    summary["all_green"] = (not failures
                            and all(c["verdict"] == "PASS" for c in hashes)
                            and closure["verdict"] == "PASS"
                            and all(p["verdict"] == "PASS" for p in probes)
                            and all(t["verdict"] == "PASS" for t in truth_tables))
    with open(os.path.join(OUTPUT_DIR, "_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    with open(os.path.join(OUTPUT_DIR, "_probes.json"), "w") as fh:
        json.dump(probes, fh, indent=2)
    with open(os.path.join(OUTPUT_DIR, "_truth_tables.json"), "w") as fh:
        json.dump(truth_tables, fh, indent=2)

    print(f"\n{summary['passed']} passed, {summary['failed']} failed, "
          f"all_green={summary['all_green']}, {summary['total_seconds']}s")
    if args.report:
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, "w") as fh:
            json.dump({"summary": summary, "records": records}, fh, indent=2)
    return 0 if summary["all_green"] else 1


if __name__ == "__main__":
    sys.exit(main())
