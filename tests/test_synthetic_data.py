from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data import generate_synthetic_data as gen


def tree_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def decode_lp(payload: bytes) -> list[bytes]:
    values = []
    cursor = 0
    while cursor < len(payload):
        colon = payload.index(b":", cursor)
        length = int(payload[cursor:colon])
        start = colon + 1
        values.append(payload[start : start + length])
        cursor = start + length
    assert cursor == len(payload)
    return values


def independent_lp(value: str | bytes) -> bytes:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return str(len(raw)).encode("ascii") + b":" + raw


def independent_ordered_row_hash(table: str, metadata: dict[str, object], csv_content: bytes) -> str:
    rows = list(csv.reader(io.StringIO(csv_content.decode("utf-8"), newline="")))[1:]
    payload = bytearray(independent_lp("typed-row-lp-v1"))
    payload.extend(independent_lp(f"SOURCE.{table}"))
    for values in rows:
        row_payload = bytearray()
        for field_id, type_tag, scalar in zip(metadata["field_ids"], metadata["snowflake_types"], values, strict=True):
            row_payload.extend(independent_lp(field_id))
            row_payload.extend(independent_lp(type_tag))
            if scalar == "":
                row_payload.extend(independent_lp("N"))
            else:
                row_payload.extend(independent_lp("V"))
                row_payload.extend(independent_lp(scalar))
        payload.extend(independent_lp(bytes(row_payload)))
    return hashlib.sha256(payload).hexdigest()


def test_import_contract_and_cli_help() -> None:
    assert sum(len(fields) for fields in gen.FIELDS.values()) == 195
    assert tuple(gen.FIELDS) == gen.TABLE_ORDER
    completed = subprocess.run(
        [str(gen.ROOT / ".venv" / "bin" / "python"), str(gen.ROOT / "data" / "generate_synthetic_data.py"), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--scale {smoke,demo}" in completed.stdout


@pytest.mark.parametrize(
    ("value", "type_tag", "rendered"),
    [
        (17, "NUMBER(38,0)", "17"),
        (-3, "NUMBER(38,0)", "-3"),
        (180.0, "FLOAT", "180.0"),
        (35.8, "FLOAT", "35.8"),
        (True, "BOOLEAN", "true"),
        (False, "BOOLEAN", "false"),
        ("2026-09-01", "DATE", "2026-09-01"),
        ("01:02:03", "TIME", "01:02:03"),
        ("2026-09-01 01:02:03", "TIMESTAMP_NTZ", "2026-09-01T01:02:03"),
        (" NULL ", "VARCHAR", " NULL "),
        ("Zażółć", "VARCHAR", "Zażółć"),
    ],
)
def test_sf_csv_v1_scalar_format(value: object, type_tag: str, rendered: str) -> None:
    assert gen.canonical_scalar(value, type_tag) == rendered


def test_sf_csv_v1_rejects_ambiguous_or_unloadable_scalars() -> None:
    with pytest.raises(ValueError, match="empty VARCHAR"):
        gen.canonical_scalar("", "VARCHAR")
    with pytest.raises(ValueError, match="non-finite"):
        gen.canonical_scalar(float("nan"), "FLOAT")
    with pytest.raises(TypeError, match="NUMBER"):
        gen.canonical_scalar(True, "NUMBER(38,0)")


def test_csv_round_trip_edge_strings_and_null() -> None:
    row = gen.row_for("AIRLINE_REFERENCE", {
        "airline_id": "SYN-MKT-EDGE",
        "effective_start_date": "2000-01-01",
        "effective_end_date": None,
        "carrier_code_iata": "NULL",
        "carrier_code_icao": "comma,value",
        "carrier_short_name": 'quote"value',
        "carrier_full_name": "line1\r\nline2 Zażółć",
        "is_iata_controlled_duplicate": False,
        "is_active": True,
        "is_current": True,
    })
    content = gen.csv_bytes("AIRLINE_REFERENCE", [row])
    assert content.endswith(b"\n")
    gen.validate_lf_record_separators(content)
    gen.validate_csv_roundtrip("AIRLINE_REFERENCE", [row], content)
    parsed = list(csv.reader(io.StringIO(content.decode("utf-8"), newline="")))
    assert parsed[1][2] == ""  # the sole null
    assert parsed[1][3] == "NULL"  # distinct non-null text
    assert parsed[1][4] == "comma,value"
    assert parsed[1][5] == 'quote"value'
    assert parsed[1][6] == "line1\r\nline2 Zażółć"


def test_d0012_payload_decoder_and_sensitivity() -> None:
    rows = gen.passenger_forward("smoke")
    row = next(row for row in rows if row["forward_source_row_id"] is None and row["flight_number"] == 726)
    payload = gen.typed_payload(gen.FIELDS["PASSENGER_FORWARD"], row, "FORWARD")
    assert len(payload) == 610
    assert hashlib.sha256(payload).hexdigest() == "a16873ded9c8aac21b72bd99247cb6301784c3fe6001e378aa6872fa5c8c7ad7"
    frames = decode_lp(payload)
    assert b"".join(independent_lp(frame) for frame in frames) == payload
    assert frames[0] == b"FORWARD"
    assert frames[1:4] == [b"PF-01", b"NUMBER(38,0)", b"N"]
    changed = dict(row)
    changed["arrival_station_code_iata"] = "MIA"
    assert gen.typed_hash(gen.FIELDS["PASSENGER_FORWARD"], changed, "FORWARD") != hashlib.sha256(payload).hexdigest()
    null_text = dict(row)
    null_text["intermediate_stop_station_codes_iata"] = "NULL"
    assert gen.typed_payload(gen.FIELDS["PASSENGER_FORWARD"], null_text, "FORWARD") != payload
    assert gen.typed_hash(gen.FIELDS["PASSENGER_FORWARD"], row, "HISTORICAL") != hashlib.sha256(payload).hexdigest()
    wrong_field_id = (gen.Field("PF-99", gen.FIELDS["PASSENGER_FORWARD"][0].column, gen.FIELDS["PASSENGER_FORWARD"][0].type_tag),) + gen.FIELDS["PASSENGER_FORWARD"][1:]
    wrong_type = (gen.Field(gen.FIELDS["PASSENGER_FORWARD"][0].field_id, gen.FIELDS["PASSENGER_FORWARD"][0].column, "VARCHAR"),) + gen.FIELDS["PASSENGER_FORWARD"][1:]
    assert gen.typed_payload(wrong_field_id, row, "FORWARD") != payload
    assert gen.typed_payload(wrong_type, row, "FORWARD") != payload


def test_prf_known_answer() -> None:
    raw = b"20260901|SOURCE.SCHEDULE_SNAPSHOT|100000|SS-39"
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == "491861981a7e9e11dd9d7f5650a019f5cd99b2eff006d88f74b9b18081ded65d"
    assert 9000 + int.from_bytes(bytes.fromhex(digest)[:2], "big") % 1000 == 9712


def test_smoke_package_semantics_and_headers(tmp_path: Path) -> None:
    manifest = gen.generate("smoke", tmp_path)
    target = tmp_path / "smoke"
    assert manifest["validation"]["total_rows"] == 249
    assert manifest["validation"]["expected_rows_owned"] == 253
    assert manifest["validation"]["q03_rows"] == 132
    schedule = manifest["validation"]["schedule_result_validation"]
    assert {key: schedule[key] for key in ("q05_rows", "q05_adjacent_counts", "q06_rows", "q07_rows")} == {
        "q05_rows": 35, "q05_adjacent_counts": [7, 5, 9, 14], "q06_rows": 2, "q07_rows": 5,
    }
    assert all(schedule[key] for key in ("q05_source_materialization_sha256", "q06_source_materialization_sha256", "q07_source_materialization_sha256"))
    assert manifest["validation"]["q03_source_materialization_sha256"]
    assert manifest["validation"]["frozen_expected_rows_sha256"]
    namespace = manifest["validation"]["identity_namespace_validation"]
    assert namespace["status"] == "passed"
    assert namespace["negative_fixture_class_count"] == 22
    expected_nf_classes = [
        "NF-A01", "NF-A02", "NF-A03", "NF-A04", "NF-A05",
        "NF-S01", "NF-S02", "NF-S03", "NF-S04", "NF-S05", "NF-S06", "NF-S07", "NF-S08", "NF-S09", "NF-S10",
        "NF-F01", "NF-F02", "NF-R01", "NF-R02", "NF-X01", "NF-X02", "NF-E01",
    ]
    assert namespace["negative_fixture_classes"] == expected_nf_classes
    assert list(gen.NEGATIVE_FIXTURE_CLASSES) == expected_nf_classes
    assert "manifest_sha256" not in (target / "manifest.json").read_text()
    for table, metadata in manifest["tables"].items():
        content = (target / metadata["file"]).read_bytes()
        parsed = list(csv.reader(io.StringIO(content.decode("utf-8"), newline="")))
        assert parsed[0] == metadata["columns"]
        assert len(parsed) == metadata["rows"] + 1
        assert all(len(row) == len(metadata["columns"]) for row in parsed)
        assert hashlib.sha256(content).hexdigest() == metadata["file_sha256"]
        assert independent_ordered_row_hash(table, metadata, content) == metadata["ordered_typed_rows_sha256"]
        assert metadata["file_sha256"] != metadata["ordered_typed_rows_sha256"]
    assert manifest["snowflake_file_format"] == {
        "type": "CSV", "compression": "NONE", "record_delimiter": "\n", "field_delimiter": ",", "skip_header": 1,
        "parse_header": False, "field_optionally_enclosed_by": '"', "escape": "NONE", "escape_unenclosed_field": "NONE",
        "multi_line": True, "empty_field_as_null": True, "null_if": [""], "trim_space": False, "skip_blank_lines": False,
        "replace_invalid_characters": False, "error_on_column_count_mismatch": True, "encoding": "UTF8",
    }


def test_demo_exact_budgets_and_isolation(tmp_path: Path) -> None:
    manifest = gen.generate("demo", tmp_path)
    assert manifest["validation"]["total_rows"] == 145_054
    assert {table: value["rows"] for table, value in manifest["tables"].items()} == gen.EXPECTED_COUNTS["demo"]
    assert manifest["validation"]["schedule_result_validation"]["q05_adjacent_counts"] == [7, 5, 9, 14]
    assert manifest["validation"]["ownership_sha256"]
    smoke = gen.generate("smoke", tmp_path)
    for table in gen.TABLE_ORDER:
        demo_rows = list(csv.reader((tmp_path / "demo" / manifest["tables"][table]["file"]).open(newline="")))[1:]
        smoke_rows = list(csv.reader((tmp_path / "smoke" / smoke["tables"][table]["file"]).open(newline="")))[1:]
        if table == "SCHEDULE_SNAPSHOT_CALENDAR":
            index = manifest["tables"][table]["columns"].index("observed_row_count")
            demo_rows = [row[:index] + row[index + 1 :] for row in demo_rows]
            smoke_rows = [row[:index] + row[index + 1 :] for row in smoke_rows]
        demo_counter, smoke_counter = Counter(map(tuple, demo_rows)), Counter(map(tuple, smoke_rows))
        assert all(demo_counter[row] >= count for row, count in smoke_counter.items())


def test_two_clean_runs_and_reordered_input_are_byte_identical(tmp_path: Path) -> None:
    ordinary_raw, _ = gen.construct_tables("smoke")
    reordered_raw, _ = gen.construct_tables("smoke", reordered_input=True)
    ordinary_raw_hashes = gen.raw_order_hashes(ordinary_raw)
    reordered_raw_hashes = gen.raw_order_hashes(reordered_raw)
    assert all(ordinary_raw_hashes[table] != reordered_raw_hashes[table] for table in gen.TABLE_ORDER if len(ordinary_raw[table]) > 1)
    gen.generate("smoke", tmp_path)
    first = tree_hashes(tmp_path / "smoke")
    gen.generate("smoke", tmp_path)
    second = tree_hashes(tmp_path / "smoke")
    gen.generate("smoke", tmp_path, reordered_input=True)
    reordered = tree_hashes(tmp_path / "smoke")
    assert first == second == reordered
    gen.generate("demo", tmp_path)
    demo_first = tree_hashes(tmp_path / "demo")
    gen.generate("demo", tmp_path, reordered_input=True)
    demo_reordered = tree_hashes(tmp_path / "demo")
    assert demo_first == demo_reordered


def test_fault_before_publish_never_exposes_partial_manifest(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="injected"):
        gen.generate("smoke", tmp_path, fail_before_publish=True)
    assert not (tmp_path / "smoke").exists()
    gen.generate("smoke", tmp_path)
    original = tree_hashes(tmp_path / "smoke")
    with pytest.raises(RuntimeError, match="injected"):
        gen.generate("smoke", tmp_path, reordered_input=True, fail_before_publish=True)
    assert tree_hashes(tmp_path / "smoke") == original
    assert not list(tmp_path.glob(".smoke.tmp-*"))


def test_named_negative_fixtures_and_provenance_are_exact() -> None:
    expected = gen.load_expected()
    masters = gen.aircraft_master("smoke")
    history = gen.aircraft_history("smoke", masters)
    assert [row["aircraft_history_id"] for row in history if row["event_source"] == "SYNTHETIC_IRRELEVANT"] == [101020]
    schedules = gen.schedule_rows("smoke", expected)
    null_endpoints = [
        (row["schedule_key"], row["publish_date"])
        for row in schedules
        if row["departure_station_code_iata"] is None or row["arrival_station_code_iata"] is None
    ]
    assert null_endpoints == [
        ("SYN-SK-CLOCK_BOUNDARY_001", value)
        for value in ("2026-08-03", "2026-08-10", "2026-08-17", "2026-08-31", "2026-09-07")
    ]
    flights = gen.aircraft_flights("smoke", masters)
    assert 8999 not in {row["flight_id"] for row in flights}
    assert next(row for row in flights if row["flight_id"] == 7200)["diverted_airport_code"] == "SYN-AP-LAS"
    assert next(row for row in flights if row["flight_id"] == 8109)["diverted_airport_code"] == "SYN-AP-LAX"


def test_generated_data_directory_is_git_ignored() -> None:
    completed = subprocess.run(
        ["git", "check-ignore", "build/generated_data/smoke/manifest.json", "build/generated_data/demo/aircraft_master.csv"],
        cwd=gen.ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.splitlines() == [
        "build/generated_data/smoke/manifest.json",
        "build/generated_data/demo/aircraft_master.csv",
    ]


def test_manifest_json_is_canonical_and_has_no_self_hash(tmp_path: Path) -> None:
    gen.generate("smoke", tmp_path)
    payload = (tmp_path / "smoke" / "manifest.json").read_bytes()
    value = json.loads(payload)
    assert payload == gen.canonical_json_bytes(value)
    assert not any("self_hash" in key.casefold() or "manifest_sha" in key.casefold() for key in value)
