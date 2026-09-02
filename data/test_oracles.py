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
    assert expected_doc["schema_version"] == "1.2.0"
    assert expected_doc["manifest_id"] == "aviation-temporal-spec03-us-synthetic-v1.2.0"
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


# ---------------------------------------------------------------------------
# D-0021 / REVIEW-D0021 repairs
# ---------------------------------------------------------------------------
def test_q08_segment_id_is_disclosed_as_manifest_adopted():
    """R2: segment_id must not be counted as independently derived."""
    assert ro.TEMPLATE_ADOPTED_COLUMNS["Q08"] == ["segment_id"]
    # ... and must NOT be label-excluded from the semantic verdict
    assert "segment_id" not in ro.LABEL_COLUMNS["Q08"]
    assert ro.template_adopted_columns_for_row("Q08", {"segment_id": "SYN-ANOM-01"}) == {"segment_id"}


def test_q08_segment_id_templates_appear_in_no_specification():
    """The premise of the R2 disclosure, re-verified rather than trusted."""
    specs = ["SOURCE_CONTRACT.md", "ATTRIBUTE_AUTHORITY.md", "DEMO_QUESTIONS.md",
             "SEMANTIC_DECISIONS.md", os.path.join("data", "SYNTHETIC_DATA_SPEC.md")]
    for name in specs:
        body = open(os.path.join(REPO_ROOT, name)).read()
        assert "SYN-ANOM-" not in body, f"{name} unexpectedly defines SYN-ANOM-"
        assert "SYN-ROT-" not in body, f"{name} unexpectedly defines SYN-ROT-"
    manifest = open(ro.EXPECTED_PATH).read()
    assert "SYN-ANOM-" in manifest and "SYN-ROT-" in manifest


@pytest.mark.parametrize("qid,rsids,total,supplied,template,derived", [
    ("Q05", ["Q05-CANONICAL"], 560, 65, 5, 490),
    ("Q08", ["Q08-CANONICAL", "Q08-ANOMALIES"], 224, 14, 14, 196),
])
def test_declared_cell_accounting(expected_doc, qid, rsids, total, supplied, template, derived):
    q = next(x for x in expected_doc["questions"] if x["question_id"] == qid)
    schema = q["output_schema"]
    rows = [ro.canonical_row(r, schema)
            for rs in q["result_sets"] if rs["result_set_id"] in rsids for r in rs["rows"]]
    s = sum(len(ro.label_columns_for_row(qid, r)) for r in rows)
    t = sum(len(ro.template_adopted_columns_for_row(qid, r)) for r in rows)
    c = sum(len(r) for r in rows)
    assert (c, s, t, c - s - t) == (total, supplied, template, derived)


def test_template_adopted_columns_stay_under_the_semantic_verdict():
    """Disclosure must not weaken the check: a segment_id regression fails BOTH."""
    schema = [{"name": "row_id", "type": "VARCHAR"},
              {"name": "segment_id", "type": "VARCHAR"},
              {"name": "flight_id", "type": "NUMBER(38,0)"}]
    row = {"row_id": "Q08-R004", "segment_id": "SYN-ANOM-01", "flight_id": 8101}
    bad = dict(row, segment_id="SYN-ANOM-1")
    out = ro.compare([row], [bad], schema, ro.LABEL_COLUMNS["Q08"], "Q08")
    assert out["verdict"] == "FAIL" and out["semantic_verdict"] == "FAIL"


def test_diversion_endpoint_conflict_follows_dv25_rank_eight():
    """R3: DV-25 is the ordering authority; diversion sits after continuity."""
    sql = open(os.path.join(ORACLE_DIR, "q08_actual_rotation_enriched.sql")).read()
    body = sql.split("CASE", 1)[1]
    order = [c for c in [
        "'SELF_LOOP'", "'CYCLE'", "'MISSING_TARGET'", "'DIFFERENT_AIRCRAFT'",
        "'OUTSIDE_SELECTED_DAY'", "'BACKWARD_TIME'", "'BROKEN_CONTINUITY'",
        "'DIVERSION_ENDPOINT_CONFLICT'", "'CANCELLED'", "'MISSING_TIME'",
        "'UNKNOWN_OR_INVALID_CANCELLATION_FLAG'"] if c in body]
    positions = [body.index(c) for c in order]
    assert positions == sorted(positions), f"CASE arms are out of DV-25 order: {order}"
    assert (body.index("'BROKEN_CONTINUITY'")
            < body.index("'DIVERSION_ENDPOINT_CONFLICT'")), "diversion must rank after continuity"


# The DV-25 rotation anomaly order: ATTRIBUTE_AUTHORITY.md:338
# ("self/cycle/missing/different/day/time/continuity/diversion-conflict/cancel/
# missing-time"), repeated in SOURCE_CONTRACT.md:363-366, plus DV-52's eleventh
# class. Both ship in commit 15d8f35, before EXPECTED_ANSWERS.yaml existed.
DV25_ANOMALY_ORDER = [
    "SELF_LOOP", "CYCLE", "MISSING_TARGET", "DIFFERENT_AIRCRAFT",
    "OUTSIDE_SELECTED_DAY", "BACKWARD_TIME", "BROKEN_CONTINUITY",
    "DIVERSION_ENDPOINT_CONFLICT", "CANCELLED", "MISSING_TIME",
    "UNKNOWN_OR_INVALID_CANCELLATION_FLAG",
]


def _q08_anomaly_class_order(expected_doc):
    """Anomaly classes in declared SYN-ANOM-<NN> segment_id order."""
    q8 = next(q for q in expected_doc["questions"] if q["question_id"] == "Q08")
    rows = next(rs for rs in q8["result_sets"]
                if rs["result_set_id"] == "Q08-ANOMALIES")["rows"]
    return [r["anomaly_code"] for r in sorted(rows, key=lambda r: r["segment_id"])]


def _oracle_case_arm_order():
    """Anomaly classes in the order their CASE arms appear in the Q08 oracle."""
    body = open(os.path.join(
        ORACLE_DIR, "q08_actual_rotation_enriched.sql")).read().split("CASE", 1)[1]
    found = [(body.index(f"'{c}'"), c) for c in DV25_ANOMALY_ORDER if f"'{c}'" in body]
    return [c for _, c in sorted(found)]


def test_frozen_manifest_anomaly_precedence_array_is_self_inconsistent(expected_doc):
    """PIN the D-0021 divergence so it cannot silently resolve.

    The frozen manifest disagrees with itself about rotation anomaly precedence:

      * scope.rotation_anomaly_support.anomaly_precedence (EXPECTED_ANSWERS.yaml:199)
        ranks DIVERSION_ENDPOINT_CONFLICT sixth;
      * the Q08-ANOMALIES rows (:1501-1511) assign the classes to the
        SYN-ANOM-01..11 ordinals in DV-25 order, i.e. diversion eighth.

    The array is unexercised metadata -- every anomaly fixture has exactly one
    applicable class -- which is why the inconsistency survived the freeze.
    D-0021 resolves it in favour of the rows and the contract. This oracle
    originally implemented the array verbatim; R3 moved it to DV-25.

    If this test fails, do NOT just update the constants. Work out which of the
    three legs moved and re-open D-0021.
    """
    array = expected_doc["scope"]["rotation_anomaly_support"]["anomaly_precedence"]
    rows = _q08_anomaly_class_order(expected_doc)

    # Leg 1: the frozen ROWS are the authority and they equal DV-25.
    assert rows == DV25_ANOMALY_ORDER, (
        "Q08-ANOMALIES no longer assigns anomaly classes to the SYN-ANOM ordinals in DV-25 "
        f"order. Rows now say {rows}. The frozen expected rows changed; D-0021's resolution "
        "rested on them, so re-open it.")

    # Leg 2: the ARRAY still contradicts the rows, on exactly three classes.
    assert array != rows, (
        "EXPECTED_ANSWERS.yaml scope.rotation_anomaly_support.anomaly_precedence now AGREES "
        "with the Q08-ANOMALIES rows. Someone has 'fixed' the frozen manifest. That is a "
        "semantic change to a frozen contract and requires reviewed supersession, not a silent "
        "edit -- and D-0021's whole rationale (contract and rows outrank one unexercised "
        "metadata field) needs restating. Do not simply delete this assertion.")
    divergent = [(i + 1, rows[i], array[i]) for i in range(len(rows)) if rows[i] != array[i]]
    assert [d[0] for d in divergent] == [6, 7, 8], (
        f"the manifest self-inconsistency moved to different positions: {divergent}")
    assert {d[1] for d in divergent} == {
        "BACKWARD_TIME", "BROKEN_CONTINUITY", "DIVERSION_ENDPOINT_CONFLICT"}, divergent
    assert array.index("DIVERSION_ENDPOINT_CONFLICT") == 5, "array should still rank it 6th"

    # Leg 3: the implementation follows the ROWS (DV-25), not the array.
    assert _oracle_case_arm_order() == rows, (
        "the Q08 oracle no longer classifies in the frozen-row / DV-25 order. R3 requires the "
        f"rows order {rows}, oracle has {_oracle_case_arm_order()}.")
    assert _oracle_case_arm_order() != array

    # And the divergence must stay documented where an implementer will see it.
    sql = open(os.path.join(ORACLE_DIR, "q08_actual_rotation_enriched.sql")).read()
    for token in ("KNOWN CONFLICT", "D-0021", "DV-25", "anomaly_precedence"):
        assert token in sql, f"the Q08 oracle header no longer documents {token}"


def test_fixture_class_to_flight_assignment_corroborates_dv25(expected_doc):
    """The load-bearing corroboration: class-to-flight_id assignment.

    The SYN-ANOM ordinals are assigned by ascending flight_id, so the numbering
    only tracks the fixture author's flight-id choices rather than independently
    establishing the order. What does carry weight is WHICH flight the author
    gave each class: 8107 BACKWARD_TIME, 8108 BROKEN_CONTINUITY, 8109 DIVERSION
    -- DV-25's order, against the anomaly_precedence array.
    """
    q8 = next(q for q in expected_doc["questions"] if q["question_id"] == "Q08")
    rows = next(rs for rs in q8["result_sets"]
                if rs["result_set_id"] == "Q08-ANOMALIES")["rows"]
    by_flight = {r["flight_id"]: r["anomaly_code"] for r in rows}
    assert by_flight[8107] == "BACKWARD_TIME"
    assert by_flight[8108] == "BROKEN_CONTINUITY"
    assert by_flight[8109] == "DIVERSION_ENDPOINT_CONFLICT"
    # ordinals really are flight_id order, which is why they are only corroboration
    ordered = sorted(rows, key=lambda r: r["segment_id"])
    assert [r["flight_id"] for r in ordered] == sorted(r["flight_id"] for r in rows)


@live
def test_q08_result_sets_still_match_after_the_dv25_rank_change(live_run):
    for rsid in ("Q08-CANONICAL", "Q08-ANOMALIES", "Q08-NOT-FOUND"):
        rec = next(r for r in live_run["result_sets"] if r["result_set_id"] == rsid)
        assert rec["verdict"] == "PASS", rec


@live
def test_live_cell_accounting_partitions_every_result_set(live_run):
    for rec in live_run["result_sets"]:
        if not rec.get("total_cells"):
            continue
        assert (rec["supplied_label_cells"] + rec["template_adopted_cells"]
                + rec["strictly_derived_cells"] == rec["total_cells"]), rec


# ---------------------------------------------------------------------------
# Run-verdict semantics: skipped is not passed, and --all is not weakened
# ---------------------------------------------------------------------------
def _group(name, status, mandatory=True):
    return {"name": name, "status": status, "mandatory_on_complete_run": mandatory,
            "skip_reason": None, "detail": None}


def test_partial_run_tolerates_a_skipped_check():
    v = ro.evaluate_run(0, [_group("q05_cross_question_closure", "SKIPPED")], complete_run=False)
    assert v["all_green"] is True
    assert v["checks_skipped"] == ["q05_cross_question_closure"]
    assert v["mandatory_checks_skipped_on_complete_run"] == []


def test_complete_run_refuses_a_skipped_mandatory_check():
    """--all must not be weakened by declining to look."""
    v = ro.evaluate_run(0, [_group("adversarial_probes", "SKIPPED")], complete_run=True)
    assert v["all_green"] is False
    assert v["mandatory_checks_skipped_on_complete_run"] == ["adversarial_probes"]


@pytest.mark.parametrize("complete", [False, True])
def test_a_failed_check_is_always_hard(complete):
    """A genuine FAIL is red on every invocation, partial or complete."""
    v = ro.evaluate_run(0, [_group("q05_cross_question_closure", "FAIL")], complete_run=complete)
    assert v["all_green"] is False
    assert v["checks_failed"] == ["q05_cross_question_closure"]


def test_a_failed_result_set_is_always_hard():
    v = ro.evaluate_run(1, [_group("q05_cross_question_closure", "PASS")], complete_run=False)
    assert v["all_green"] is False


def test_skipped_is_never_silently_passed():
    """A skip must be visible in the summary, not absent from it."""
    v = ro.evaluate_run(0, [_group("adversarial_probes", "SKIPPED"),
                            _group("contract_truth_tables", "SKIPPED")], complete_run=False)
    assert sorted(v["checks_skipped"]) == ["adversarial_probes", "contract_truth_tables"]
    assert "adversarial_probes" not in v["checks_failed"]


def _invoke(*argv, cwd=REPO_ROOT):
    import subprocess
    proc = subprocess.run(
        [os.path.join(REPO_ROOT, ".venv", "bin", "python"),
         os.path.join(REPO_ROOT, "data", "run_oracles.py"), *argv],
        capture_output=True, text=True, cwd=cwd)
    with open(os.path.join(ro.OUTPUT_DIR, "_summary.json")) as fh:
        return proc, json.load(fh)


@live
def test_partial_selection_excluding_q05_exits_zero_with_closure_skipped():
    """The reported defect: --question Q08 must not report a spurious FAIL."""
    proc, summary = _invoke("--result-set", "Q08-CANONICAL", "--skip-probes")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FAIL" not in proc.stdout, proc.stdout
    assert "SKIP  q05 cross-question closure" in proc.stdout
    assert summary["all_green"] is True
    assert summary["invocation"]["complete_run"] is False
    assert "q05_cross_question_closure" in summary["checks_skipped"]
    # and it is reported, not omitted
    names = {g["name"] for g in summary["check_groups"]}
    assert "q05_cross_question_closure" in names
    group = next(g for g in summary["check_groups"]
                 if g["name"] == "q05_cross_question_closure")
    assert group["status"] == "SKIPPED" and group["skip_reason"]


@live
def test_skip_probes_reports_skipped_groups_rather_than_passing_them_silently():
    """The latent second defect: --skip-probes used to pass 0 probes vacuously."""
    proc, summary = _invoke("--result-set", "Q08-CANONICAL", "--skip-probes")
    assert proc.returncode == 0
    assert set(summary["checks_skipped"]) >= {"adversarial_probes", "contract_truth_tables"}
    for name in ("adversarial_probes", "contract_truth_tables"):
        g = next(x for x in summary["check_groups"] if x["name"] == name)
        assert g["status"] == "SKIPPED" and "--skip-probes" in g["skip_reason"]


@live
def test_a_broken_closure_on_a_full_run_still_exits_non_zero(monkeypatch):
    """--all must stay mandatory: break the closure and require a hard failure.

    Runs in-process against a Q05-including selection so the FAIL path is the
    real one, and separately asserts the complete-run rule via evaluate_run.
    """
    import sys
    original = ro.verify_q05_closure

    def broken(doc, rows):
        out = original(doc, rows)
        out["verdict"] = "FAIL"
        out["checks"].append({"name": "injected_defect", "verdict": "FAIL",
                              "detail": "deliberately broken closure"})
        return out

    monkeypatch.setattr(ro, "verify_q05_closure", broken)
    monkeypatch.setattr(sys, "argv",
                        ["run_oracles.py", "--result-set", "Q05-CANONICAL", "--skip-probes"])
    rc = ro.main()
    assert rc != 0, "a broken Q05 closure must exit non-zero"
    with open(os.path.join(ro.OUTPUT_DIR, "_summary.json")) as fh:
        summary = json.load(fh)
    assert summary["all_green"] is False
    assert "q05_cross_question_closure" in summary["checks_failed"]
    # and the complete-run rule independently
    assert ro.evaluate_run(0, [_group("q05_cross_question_closure", "FAIL")],
                           complete_run=True)["all_green"] is False


@live
def test_complete_run_exits_zero_and_skips_nothing():
    proc, summary = _invoke("--all")
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    assert summary["invocation"]["complete_run"] is True
    assert summary["checks_skipped"] == [], summary["checks_skipped"]
    assert summary["all_green"] is True
    assert len(summary["result_sets"]) == 24


@live
def test_run_is_all_green(live_run):
    assert live_run["all_green"], json.dumps(
        {k: v for k, v in live_run.items() if k != "result_sets"}, indent=2)[:4000]
