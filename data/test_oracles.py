"""DATA-04b pytest gate for the independent SQL oracles.

Two tiers:

* Offline tests (no Snowflake): independence, read-only shape, parameter
  validation, frozen-manifest integrity and the declared preservation hashes.
* Live tests (marked ``live``): the complete ``--all`` oracle run against
  ``PK_AVIATION_TEMPORAL.SOURCE``, compared to the frozen manifest.

Run everything::

    .venv/bin/pytest data/test_oracles.py -v

Offline only::

    DATA04B_SKIP_LIVE=1 .venv/bin/pytest data/test_oracles.py -v

Reuse the JSON already written by a previous ``run_oracles.py --all`` instead of
re-executing it::

    DATA04B_REUSE_RESULTS=1 .venv/bin/pytest data/test_oracles.py -v
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re

import pytest
import yaml

from data import run_oracles as ro

live = pytest.mark.skipif(
    os.environ.get("DATA04B_SKIP_LIVE") == "1",
    reason="DATA04B_SKIP_LIVE=1: offline tests only",
)

REPO_ROOT = ro.REPO_ROOT
ORACLE_DIR = ro.ORACLE_DIR


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def expected_doc():
    with open(ro.EXPECTED_PATH) as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="session")
def oracle_sql_files():
    files = sorted(glob.glob(os.path.join(ORACLE_DIR, "*.sql")) +
                   glob.glob(os.path.join(ORACLE_DIR, "*.sql.inc")))
    assert files, "no oracle SQL files found"
    return files


@pytest.fixture(scope="session")
def live_run():
    """One live --all execution shared by every live test."""
    summary_path = os.path.join(ro.OUTPUT_DIR, "_summary.json")
    marker = os.environ.get("DATA04B_REUSE_RESULTS")
    if marker and os.path.exists(summary_path):
        with open(summary_path) as fh:
            return json.load(fh)
    import subprocess
    proc = subprocess.run(
        [os.path.join(REPO_ROOT, ".venv", "bin", "python"),
         os.path.join(REPO_ROOT, "data", "run_oracles.py"), "--all"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert os.path.exists(summary_path), f"no summary written:\n{proc.stdout}\n{proc.stderr}"
    with open(summary_path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# independence and read-only shape
# ---------------------------------------------------------------------------
FORBIDDEN_DEPENDENCIES = ("MODEL_INPUT", "model_input", "build_model_input")


def test_oracles_never_reference_the_model_input_layer(oracle_sql_files):
    """The whole point of DATA-04b: agreement with DATA-04a must be meaningful."""
    offenders = []
    for path in oracle_sql_files:
        # strip comments: the header comments state that the layer is NOT read
        body = re.sub(r"--[^\n]*", "", open(path).read())
        for token in FORBIDDEN_DEPENDENCIES:
            if token in body:
                offenders.append((os.path.basename(path), token))
    assert not offenders, f"oracle SQL depends on the MODEL_INPUT layer: {offenders}"


def test_runner_never_references_the_model_input_layer():
    body = open(os.path.join(REPO_ROOT, "data", "run_oracles.py")).read()
    # The module docstring names the layer only to state that it is not read.
    code = body.split('"""', 2)[2]
    for token in FORBIDDEN_DEPENDENCIES:
        assert token not in code, f"run_oracles.py code references {token}"


def test_every_oracle_reads_only_the_source_schema(oracle_sql_files):
    for path in oracle_sql_files:
        body = open(path).read()
        for ref in re.findall(r"PK_AVIATION_TEMPORAL\.([A-Z_]+)\.", body):
            assert ref == "SOURCE", f"{os.path.basename(path)} reads schema {ref}"


DDL_TOKENS = ("INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP",
              "ALTER", "TRUNCATE", "GRANT", "REVOKE", "COPY", "PUT")


def test_no_oracle_statement_mutates_snowflake(oracle_sql_files):
    for path in oracle_sql_files:
        body = re.sub(r"--[^\n]*", "", open(path).read()).upper()
        for token in DDL_TOKENS:
            assert not re.search(rf"\b{token}\b", body), \
                f"{os.path.basename(path)} contains {token}"


def test_run_sql_refuses_a_mutating_statement():
    with pytest.raises(ro.SnowError):
        ro.run_sql("CREATE TABLE PK_AVIATION_TEMPORAL.SOURCE.X (a INT)", "unit")
    with pytest.raises(ro.SnowError):
        ro.run_sql("SELECT 1; DELETE FROM t", "unit")


def test_render_rejects_an_unsafe_parameter():
    with pytest.raises(ro.SnowError):
        ro.render("q01_aircraft_as_of.sql",
                  {"aircraft_id": 1001, "as_of_date": "2026-08-31'; DROP TABLE t --"})


def test_render_leaves_no_unsubstituted_placeholder():
    for qid, fname in ro.SQL_FILES.items():
        params = {"aircraft_id": 1001, "as_of_date": "2026-08-31",
                  "start_month_end": "2015-01-31", "end_month_end": "2024-12-31",
                  "status": "In Service", "start_knowledge_date": "2026-08-03",
                  "end_knowledge_date": "2026-08-31", "cadence_days": 7,
                  "latest_knowledge_date": "2026-08-31",
                  "comparison_knowledge_date": "2026-08-24", "carrier_role": "marketing",
                  "knowledge_date": "2026-08-31", "operating_date": "2026-09-07",
                  "flight_departure_date": "2026-08-31"}
        sql = ro.render(fname, params)
        assert "{{" not in sql, f"{qid} still has a placeholder"


# ---------------------------------------------------------------------------
# frozen manifest integrity
# ---------------------------------------------------------------------------
def test_expected_answers_is_the_frozen_v111_manifest(expected_doc):
    assert expected_doc["schema_version"] == "1.1.1"
    assert expected_doc["manifest_id"] == "aviation-temporal-spec03-us-synthetic-v1.1.1"
    assert expected_doc["status"] == "FROZEN_BEFORE_DATA_AND_QUERY_IMPLEMENTATION"


def test_manifest_declares_twenty_four_result_sets(expected_doc):
    count = sum(len(q["result_sets"]) for q in expected_doc["questions"])
    assert count == 24


def test_declared_preservation_hashes_verify(expected_doc):
    checks = ro.verify_declared_hashes(expected_doc)
    failed = [c for c in checks if c["verdict"] != "PASS"]
    assert not failed, failed
    assert len(checks) == 3


def test_expected_cardinality_matches_declared_rows(expected_doc):
    for q in expected_doc["questions"]:
        for rs in q["result_sets"]:
            assert len(rs["rows"]) == rs["expected_cardinality"], rs["result_set_id"]


def test_no_duplicate_row_ids_inside_a_result_set(expected_doc):
    for q in expected_doc["questions"]:
        for rs in q["result_sets"]:
            ids = [r["row_id"] for r in rs["rows"]]
            assert len(ids) == len(set(ids)), rs["result_set_id"]


def test_every_expected_row_carries_exactly_the_declared_columns(expected_doc):
    for q in expected_doc["questions"]:
        declared = {c["name"] for c in q["output_schema"]}
        for rs in q["result_sets"]:
            for row in rs["rows"]:
                assert set(row) == declared, (rs["result_set_id"], row.get("row_id"))


def test_q03_has_120_distinct_month_ends(expected_doc):
    q3 = next(q for q in expected_doc["questions"] if q["question_id"] == "Q03")
    rs = q3["result_sets"][0]
    assert len({r["month_end"] for r in rs["rows"]}) == rs["expected_distinct_month_ends"] == 120


def test_dv43_known_answer_digest_is_the_declared_constant(expected_doc):
    ka = expected_doc["scope"]["dv43_known_answer"]
    assert ka["expected_sha256"] == "a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7"
    assert ka["expected_dv46_source_row_token"] == "FORWARD|" + ka["expected_sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", ka["expected_sha256"])


def test_q05_declared_label_table_covers_only_exact_and_unpaired_rows(expected_doc):
    """The declared label table must not silently supply a derivable event id."""
    body = open(os.path.join(ORACLE_DIR, "q05_event_labels.sql")).read()
    labelled = set(re.findall(r"'(SYN-(?:CHG|ADD|REM|UNPAIR)[^']*)'\)", body))
    q5 = next(q for q in expected_doc["questions"] if q["question_id"] == "Q05")
    canonical = next(rs for rs in q5["result_sets"] if rs["result_set_id"] == "Q05-CANONICAL")
    expected_labels = {r["event_id"] for r in canonical["rows"]
                       if r["event_class"].startswith(("EXACT", "UNPAIRED"))}
    derived = {r["event_id"] for r in canonical["rows"]
               if not r["event_class"].startswith(("EXACT", "UNPAIRED"))}
    assert labelled == expected_labels, labelled ^ expected_labels
    assert len(labelled) == 30
    assert not (labelled & derived)


# ---------------------------------------------------------------------------
# typed parameter validation (pre-execution)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("qid,params,expected", [
    ("Q01", {"aircraft_id": 1001, "as_of_date": "2026-08-31"}, None),
    ("Q01", {"aircraft_id": -1, "as_of_date": "2026-08-31"}, "INVALID_AIRCRAFT_ID"),
    ("Q01", {"aircraft_id": None, "as_of_date": "2026-08-31"}, "INVALID_AIRCRAFT_ID"),
    ("Q01", {"aircraft_id": 1001, "as_of_date": "2026-02-30"}, "INVALID_DATE"),
    ("Q06", {"latest_knowledge_date": "2026-08-31", "comparison_knowledge_date": "2026-08-24",
             "carrier_role": "marketing"}, None),
    ("Q06", {"latest_knowledge_date": "2026-08-31", "comparison_knowledge_date": "2026-08-24",
             "carrier_role": None}, "MISSING_CARRIER_ROLE"),
    ("Q06", {"latest_knowledge_date": "2026-02-30", "comparison_knowledge_date": "2026-02-23",
             "carrier_role": "marketing"}, "INVALID_DATE"),
    ("Q06", {"latest_knowledge_date": "2026-08-31", "comparison_knowledge_date": "2026-08-24",
             "carrier_role": "codeshare"}, "INVALID_CARRIER_ROLE"),
    ("Q07", {"knowledge_date": None, "operating_date": "2026-09-07",
             "carrier_role": "operating"}, "MISSING_KNOWLEDGE_DATE"),
    ("Q07", {"knowledge_date": "2026-08-31", "operating_date": None,
             "carrier_role": "operating"}, "MISSING_OPERATING_DATE"),
    ("Q07", {"knowledge_date": "2026-08-31", "operating_date": "2026-09-07",
             "carrier_role": None}, "MISSING_CARRIER_ROLE"),
    ("Q08", {"aircraft_id": 1999, "flight_departure_date": "2026-08-31"}, None),
])
def test_parameter_validation(qid, params, expected):
    assert ro.validate_parameters(qid, params) == expected


def test_every_parameter_error_scenario_is_reproduced_without_touching_snowflake(expected_doc):
    """PARAMETER_ERROR result sets must fail validation before any query runs."""
    for q in expected_doc["questions"]:
        for rs in q["result_sets"]:
            if rs["invocation_status"] != "PARAMETER_ERROR":
                continue
            code = ro.validate_parameters(q["question_id"], dict(rs["parameters"]))
            assert code == rs["error_code"], rs["result_set_id"]
            assert rs["rows"] == []


# ---------------------------------------------------------------------------
# live tests
# ---------------------------------------------------------------------------
@live
def test_all_twenty_four_result_sets_execute_and_match(live_run):
    assert len(live_run["result_sets"]) == 24
    failed = [r for r in live_run["result_sets"] if r["verdict"] != "PASS"]
    assert not failed, json.dumps(failed, indent=2)


@live
def test_semantic_verdicts_are_green_independently_of_declared_labels(live_run):
    failed = [r for r in live_run["result_sets"]
              if r["semantic_verdict"] not in ("PASS", None)]
    assert not failed, json.dumps(failed, indent=2)


@live
def test_q05_cross_question_closure_holds(live_run):
    closure = live_run["q05_cross_question_closure"]
    assert closure["verdict"] == "PASS", json.dumps(closure, indent=2)


@live
def test_declared_q06_and_q07_preservation_hashes_verify_live(live_run):
    failed = [c for c in live_run["declared_hash_checks"] if c["verdict"] != "PASS"]
    assert not failed, failed


@live
def test_concurrent_route_states_are_preserved(live_run):
    probe = next(p for p in live_run["adversarial_probes"]
                 if p["probe"] == "concurrent_route_states_preserved")
    assert probe["verdict"] == "PASS", json.dumps(probe, indent=2)


@live
def test_incomplete_snapshots_create_no_removals(live_run):
    probe = next(p for p in live_run["adversarial_probes"]
                 if p["probe"] == "incomplete_snapshots_create_no_removals")
    assert probe["verdict"] == "PASS", json.dumps(probe, indent=2)


@live
def test_temporal_integrity_probes_pass(live_run):
    for name in ("temporal_integrity_and_sentinels", "schedule_canonicalisation_and_no_change"):
        probe = next(p for p in live_run["adversarial_probes"] if p["probe"] == name)
        assert probe["verdict"] == "PASS", json.dumps(probe, indent=2)


@live
def test_contract_truth_tables_reproduce(live_run):
    failed = [t for t in live_run["contract_truth_tables"] if t["verdict"] != "PASS"]
    assert not failed, json.dumps(failed, indent=2)


@live
def test_hard_test_coverage_is_fully_accounted_for(live_run, expected_doc):
    declared = set(expected_doc["hard_test_coverage"])
    accounted = set(live_run["hard_test_coverage_evidence"])
    assert declared == accounted, declared ^ accounted


def test_label_exclusion_is_scoped_per_row_not_per_column(expected_doc):
    """REVIEW-D0018 P12: the five derived Q05 event ids must NOT be excluded."""
    q5 = next(q for q in expected_doc["questions"] if q["question_id"] == "Q05")
    rows = next(rs for rs in q5["result_sets"]
                if rs["result_set_id"] == "Q05-CANONICAL")["rows"]
    declared = [r for r in rows if "event_id" in ro.label_columns_for_row("Q05", r)]
    derived = [r for r in rows if "event_id" not in ro.label_columns_for_row("Q05", r)]
    assert len(declared) == 30 and len(derived) == 5
    assert {r["event_class"] for r in derived} == {
        "CANDIDATE_UNIQUE", "AMBIGUOUS_CANDIDATE_GROUP", "AMBIGUOUS_GROUP_MEMBER"}
    # row_id stays excluded on every row, derived or not
    assert all("row_id" in ro.label_columns_for_row("Q05", r) for r in rows)


def test_compare_flags_a_derived_event_id_diff_as_semantic():
    """Unit form of the P12 regression: no Snowflake needed."""
    schema = [{"name": "row_id", "type": "VARCHAR"},
              {"name": "event_id", "type": "VARCHAR"},
              {"name": "event_class", "type": "VARCHAR"}]
    labels = ["row_id", "event_id"]
    declared_row = {"row_id": "Q05-R001", "event_id": "SYN-ADD-20260810-300",
                    "event_class": "EXACT_ADDITION"}
    derived_row = {"row_id": "Q05-R006", "event_id": "SYN-CAND-20260817-01",
                   "event_class": "CANDIDATE_UNIQUE"}
    # perturbing a DECLARED mnemonic: strict fail, semantic pass (by design)
    bad_declared = dict(declared_row, event_id="SYN-ADD-20260810-XXX")
    out = ro.compare([declared_row], [bad_declared], schema, labels, "Q05")
    assert out["verdict"] == "FAIL" and out["semantic_verdict"] == "PASS"
    # perturbing a DERIVED id: strict fail AND semantic fail
    bad_derived = dict(derived_row, event_id="SYN-CAND-20260817-1")
    out = ro.compare([derived_row], [bad_derived], schema, labels, "Q05")
    assert out["verdict"] == "FAIL" and out["semantic_verdict"] == "FAIL"


@live
def test_derived_q05_event_ids_are_under_semantic_test(expected_doc):
    """Live P12 regression: drop the SYN-CAND ordinal padding in the rendered
    SQL only (never on disk) and require BOTH verdicts to fail."""
    original_render = ro.render
    padded = ("LPAD(ROW_NUMBER() OVER (PARTITION BY s.comparison_date "
              "ORDER BY s.signature_token)::VARCHAR, 2, '0')")
    unpadded = ("ROW_NUMBER() OVER (PARTITION BY s.comparison_date "
                "ORDER BY s.signature_token)::VARCHAR")

    def perturbed_render(name, params):
        sql = original_render(name, params)
        if name != ro.SQL_FILES["Q05"]:
            return sql
        # scope the perturbation to the SYN-CAND block so group_id (which is not
        # a label column) is untouched and event_id is the ONLY differing cell
        head, sep, tail = sql.partition("'SYN-AMB-'")
        assert sep, "q05 SQL no longer contains the SYN-AMB block"
        assert padded in head, "q05 SYN-CAND padding expression drifted"
        return head.replace(padded, unpadded) + sep + tail

    q5 = next(q for q in expected_doc["questions"] if q["question_id"] == "Q05")
    rs = next(r for r in q5["result_sets"] if r["result_set_id"] == "Q05-CANONICAL")
    ro.render = perturbed_render
    try:
        rec = ro.execute_result_set(q5, rs)
    finally:
        ro.render = original_render

    cmp_ = rec["comparison"]
    changed = {c for d in cmp_["diffs"] if d["kind"] == "CELL_MISMATCH" for c in d["cells"]}
    assert changed == {"event_id"}, f"perturbation was not isolated to event_id: {changed}"
    assert cmp_["verdict"] == "FAIL"
    assert cmp_["semantic_verdict"] == "FAIL", (
        "a format regression in the DERIVED SYN-CAND id must fail the semantic "
        "verdict; the per-column exclusion used to report PASS here (REVIEW-D0018 P12)")


@live
def test_run_is_all_green(live_run):
    assert live_run["all_green"], json.dumps(
        {k: v for k, v in live_run.items() if k != "result_sets"}, indent=2)[:4000]
