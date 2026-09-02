"""test_uc2.py - QUERY-UC2 live gate for Q05, Q06 and Q07.

Every test here hits the live ``PK_AVIATION_TEMPORAL`` under ``RAI_DEMO_AVIATION_TEMPORAL`` via
the ``aviation_temporal_logic_s`` reasoner. Nothing is mocked, nothing is asserted from a
producer's claim, and an import that succeeds is not a query that runs.

Run with a warm engine::

    .venv/bin/rai reasoners resume --type Logic --name aviation_temporal_logic_s --wait
    PYTHONPATH=rai_code TERM=dumb .venv/bin/python -m pytest tests/test_uc2.py -q

Cold start from SUSPENDED was measured at 631s. The engine is shared with other tasks, so a
slow first query is queueing rather than failure.

The suite asserts **complete result sets** against ``EXPECTED_ANSWERS.yaml`` - every cell of
every row, in the declared order - not cardinalities. Cardinality checks are kept only as
extra early-diagnostic assertions where the manifest names a per-pair count.

Groups, and what each one is defending against:

1. **Complete frozen conformance.** All twelve UC2 result sets plus ``TT-BOTH-CLOCKS``.
2. **The eight Q05 event classes**, each asserted by class rather than only in aggregate, so a
   collapsed or missing class cannot hide inside a correct total.
3. **The key-shift trap.** A date shift mints a new ``schedule_key``; the pair must surface as
   a labelled ``CANDIDATE_UNIQUE`` and never as an exact modification, with both exact
   presence rows surviving alongside it.
4. **Snapshot completeness.** A missing or incomplete snapshot must never manufacture a
   removal, and an ineligible endpoint must be refused rather than substituted.
5. **Multi-open route states.** One route legitimately carries several concurrently valid
   states; any unique-state assumption collapses ``Q07-R001``.
6. **Both clocks.** Half-open knowledge and inclusive operating, including the operating upper
   bound, which is the single most load-bearing comparison operator in the demo.
7. **Codeshare de-duplication.** Physical capacity never double counts, and the codeshare-only
   service is emitted as visibly unresolved rather than dropped or guessed.
8. **Typed refusals.** The three kinds of zero-row answer stay distinguishable.

Session-scoped fixtures run each live invocation exactly once; the individual tests are
assertions over cached frames.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rai_code"))

pytestmark = pytest.mark.live

KNOWLEDGE_DATE = dt.date(2026, 8, 31)
OPERATING_DATE = dt.date(2026, 9, 7)
COMPARISON_DATE = dt.date(2026, 8, 24)

Q05_START = dt.date(2026, 8, 3)
Q05_END = dt.date(2026, 8, 31)

# The October gap-control sequence, deliberately outside the Q05 canonical window.
GAP_PREVIOUS = dt.date(2026, 10, 5)
GAP_MISSING = dt.date(2026, 10, 12)
GAP_INCOMPLETE = dt.date(2026, 10, 19)
GAP_AFTER = dt.date(2026, 10, 26)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="session")
def uc2():
    """The query module. Importing it loads the one ``Model`` for this interpreter."""
    from queries import uc2 as module

    module.model_package()
    return module


@pytest.fixture(scope="session")
def manifest(uc2):
    return uc2._load_manifest()


@pytest.fixture(scope="session")
def frozen(manifest):
    """``{result_set_id: result_set}`` for the three UC2 questions."""
    out: dict[str, Mapping[str, Any]] = {}
    for question in manifest["questions"]:
        if question["question_id"] not in {"Q05", "Q06", "Q07"}:
            continue
        for result_set in question["result_sets"]:
            out[result_set["result_set_id"]] = {
                **result_set,
                "question_id": question["question_id"],
            }
    return out


# Every UC2 result set in the manifest: the twelve frozen at 1.1.1, then the eight D-0023 added
# at 1.2.0. The enriched ones re-ask the same three questions at 2027 parameters over the
# enriched population, so they exercise the same code path at roughly ten times the cardinality
# (Q07 3 rows to 30, Q05 35 to 392).
RESULT_SET_IDS = (
    "Q06-CANONICAL",
    "Q06-INCOMPLETE-ENDPOINT",
    "Q06-MISSING-CARRIER-ROLE",
    "Q06-INVALID-DATE",
    "Q06-ENRICHED-MARKETING",
    "Q06-ENRICHED-OPERATING",
    "Q07-MARKETING",
    "Q07-OPERATING",
    "Q07-KNOWLEDGE-END-EMPTY",
    "Q07-MISSING-KNOWLEDGE-DATE",
    "Q07-MISSING-OPERATING-DATE",
    "Q07-MISSING-CARRIER-ROLE",
    "Q07-ENRICHED-KNOWLEDGE-LATE",
    "Q07-ENRICHED-KNOWLEDGE-EARLY",
    "Q07-ENRICHED-OPERATING-SHIFT",
    "Q07-ENRICHED-ROLE",
    "Q05-CANONICAL",
    "Q05-INELIGIBLE-ENDPOINT",
    "Q05-ENRICHED",
    "Q05-ENRICHED-GAP-PAIRS",
)


@pytest.fixture(scope="session")
def invocations(uc2, frozen, manifest):
    """Every frozen UC2 result set, invoked once. ``{id: (status, error_code, frame)}``.

    Labels are scoped **per result set**, not per question. At 1.2.0 the semantic identity is
    no longer unique across a question's result sets: Q07's three enriched marketing sets
    share all 30 identities and 87 of ``Q05-ENRICHED-GAP-PAIRS``'s recur inside
    ``Q05-ENRICHED``. A question-wide map would label one set with another's identifiers.
    """
    out: dict[str, tuple[str, str | None, Any]] = {}
    for result_set_id in RESULT_SET_IDS:
        result_set = frozen[result_set_id]
        question_id = result_set["question_id"]
        labels = uc2.manifest_label_source(question_id, manifest, result_set_id)
        out[result_set_id] = uc2.invoke_result_set(question_id, result_set, labels)
    return out


@pytest.fixture(scope="session")
def q05(invocations):
    """The 35-row canonical Q05 frame as a list of dicts."""
    _, _, frame = invocations["Q05-CANONICAL"]
    return frame.to_dict("records")


@pytest.fixture(scope="session")
def q05_gap(uc2, manifest):
    """Q05 across the October gap: 2026-10-05 to 2026-10-26, both endpoints eligible.

    This window brackets a missing snapshot (2026-10-12) and an incomplete one
    (2026-10-19), so it is the live test that neither manufactures an event.
    """
    labels = uc2.manifest_label_source("Q05", manifest, "Q05-CANONICAL")
    frame = uc2.schedule_four_week_changes(GAP_PREVIOUS, GAP_AFTER, 7, labels=labels)
    return frame.to_dict("records")


@pytest.fixture(scope="session")
def truth_table(uc2):
    return uc2.both_clocks_truth_table()


@pytest.fixture(scope="session")
def frozen_truth_table(manifest):
    for table in manifest["contract_truth_tables"]:
        if table["truth_table_id"] == "TT-BOTH-CLOCKS":
            return table
    raise AssertionError("TT-BOTH-CLOCKS missing from the manifest")


@pytest.fixture(scope="session")
def market_totals(uc2):
    """Distinct marketing markets live at each Q06 endpoint, for the partition check."""
    return {
        "latest": uc2.market_count_at(KNOWLEDGE_DATE, "marketing"),
        "comparison": uc2.market_count_at(COMPARISON_DATE, "marketing"),
    }


# ---------------------------------------------------------------------------- helpers


def _rows(records, **match):
    return [r for r in records if all(r[k] == v for k, v in match.items())]


def _one(records, **match):
    found = _rows(records, **match)
    assert len(found) == 1, (match, found)
    return found[0]


# ========================================================== 1. complete conformance


@pytest.mark.parametrize("result_set_id", RESULT_SET_IDS)
def test_frozen_result_set_semantic_verdict(uc2, frozen, invocations, result_set_id):
    """The order-free verdict over the derived columns (D-0018).

    Every column the query computes from the model with no manifest input, compared as a
    multiset so a duplicated or dropped event cannot hide behind a correct total. This is the
    verdict that is genuinely earned; the ordered one below is separately labelled because
    Q05's declared sequence sorts on a supplied column.
    """
    result_set = frozen[result_set_id]
    status, error_code, frame = invocations[result_set_id]
    expected_rows = [uc2._manifest_row(r) for r in (result_set.get("rows") or ())]

    assert status == result_set["invocation_status"], (result_set_id, status)
    if result_set.get("error_code") is not None:
        assert error_code == result_set["error_code"], (result_set_id, error_code)
    assert len(frame) == result_set["expected_cardinality"], result_set_id

    diffs = uc2.compare_semantic(frame, expected_rows, result_set["question_id"])
    assert not diffs, f"{result_set_id}: " + "; ".join(diffs[:10])


@pytest.mark.parametrize("result_set_id", RESULT_SET_IDS)
def test_frozen_result_set_reproduced_completely(
    uc2, frozen, invocations, result_set_id
):
    """Every cell of every row, in the declared order, plus the invocation status.

    ``canonicalization.object_rules``: rows compare as a complete ordered sequence after the
    declared ``order_by``, and missing or extra columns fail. A cardinality-only check would
    pass on a frame of thirty-five wrong rows.

    For Q05 this is the **presentation** half of the D-0018 split: it asserts that the module
    applies the supplied labels and the declared sequence, not that it recovered them.
    """
    result_set = frozen[result_set_id]
    question_id = result_set["question_id"]
    status, error_code, frame = invocations[result_set_id]
    expected_rows = [uc2._manifest_row(r) for r in (result_set.get("rows") or ())]

    assert status == result_set["invocation_status"], (result_set_id, status)
    if result_set.get("error_code") is not None:
        assert error_code == result_set["error_code"], (result_set_id, error_code)
    assert len(frame) == result_set["expected_cardinality"], result_set_id

    columns = uc2._QUESTION_COLUMNS[question_id]
    diffs = uc2.compare_rows(frame, expected_rows, columns)
    assert not diffs, f"{result_set_id}: " + "; ".join(diffs[:10])


def test_empty_ok_result_still_carries_the_frozen_columns(uc2, invocations):
    """``Q07-KNOWLEDGE-END-EMPTY`` is zero rows with status ``OK``, not an error.

    An empty RAI result is a zero-*column* DataFrame (PROBE D11), so a query module that
    returned the engine's frame directly would hand the catalog a frame with no columns at all
    and ``df["airline_id"]`` would raise ``KeyError``. The module assembles its own column
    list, and the distinction between this and the three parameter errors is the point.
    """
    status, error_code, frame = invocations["Q07-KNOWLEDGE-END-EMPTY"]
    assert (status, error_code) == ("OK", None)
    assert len(frame) == 0
    assert list(frame.columns) == list(uc2.Q07_COLUMNS)


def test_q05_declared_sequence_is_a_presentation_check(uc2, frozen, q05):
    """The declared row order, asserted separately and labelled as supplied (D-0018).

    The frozen ``order_by`` sorts on ``event_id``, and 30 of the 35 ``event_id`` values are
    hand-authored mnemonics that no implementation can derive: on 2026-08-31 the
    ``EXACT_ADDITION`` block orders ``[MKT_ENTRY_714, UNPAIR_NEW]`` while the
    ``UNPAIRED_ADDITION`` block orders the identical pair inverted, so no total order on any
    per-key attribute reproduces the manifest. This test therefore checks that the module
    *applies* the declared sequence once the supplied labels are joined; it is not evidence
    that the sequence was independently recovered, and the semantic verdict below is
    order-free on purpose.
    """
    expected = [uc2._manifest_row(r) for r in frozen["Q05-CANONICAL"]["rows"]]
    assert [r["row_id"] for r in q05] == [r["row_id"] for r in expected]
    assert [r["event_id"] for r in q05] == [r["event_id"] for r in expected]


def test_q05_semantic_verdict_is_order_free(uc2, frozen, q05):
    """The fourteen derived columns compared as a set, independent of the declared sequence.

    This is the verdict D-0018 says is genuinely earned: the event set, every
    ``event_class``, ``exactness``, ``confidence``, schedule/related/member key,
    ``field_name``, ``old_value``, ``new_value`` and ``crosses_snapshot_gap`` recomputed from
    the model with no manifest input. ``row_id`` and ``event_id`` are excluded because they
    are supplied.
    """
    derived = tuple(c for c in uc2.Q05_COLUMNS if c not in {"row_id", "event_id"})
    got = {tuple(row[c] for c in derived) for row in q05}
    want = {
        tuple(uc2._manifest_row(r)[c] for c in derived)
        for r in frozen["Q05-CANONICAL"]["rows"]
    }
    assert got == want, {
        "only_in_query": sorted(map(str, got - want)),
        "only_in_manifest": sorted(map(str, want - got)),
    }


def test_q05_enriched_event_ids_are_derived_not_supplied(uc2, frozen):
    """The 1.2.0 enriched Q05 ``event_id`` values need no label source at all.

    D-0018's supplied-label problem is confined to ``Q05-CANONICAL``'s 30 hand-authored
    mnemonics. ``Q05-ENRICHED`` freezes the fail-loud token instead, which is a pure function
    of the four semantic-identity columns the query already computes. Running with **no**
    ``LabelSource`` and still reproducing all 392 ``event_id`` cells is the proof: 380
    declared-class events by the derivable token and 12 candidate/group/member events by the
    manifest-adopted string templates. Only ``row_id`` stays supplied.
    """
    frame = uc2.schedule_four_week_changes("2027-01-04", "2027-06-28", 7)
    got = frame.to_dict("records")
    expected = [uc2._manifest_row(r) for r in frozen["Q05-ENRICHED"]["rows"]]

    by_identity = {uc2._q05_row_identity(r): r["event_id"] for r in expected}
    assert len(by_identity) == len(expected)
    for row in got:
        identity = uc2._q05_row_identity(row)
        assert identity in by_identity, row
        assert row["event_id"] == by_identity[identity], row
    assert len(got) == len(expected)
    # row_id remains supplied, and says so.
    assert all(r["row_id"].startswith(uc2._UNLABELLED) for r in got)


def test_q05_rows_by_adjacent_pair(manifest, q05):
    """The per-pair counts 7 / 5 / 9 / 14, the manifest's cheapest early diagnostic.

    ``cross_question_event_closure.q05_rows_by_adjacent_pair`` also names the row ids in each
    bucket, so both the count and the membership are asserted. A window that silently used
    three pairs or five would still total 35 under some misclassifications.
    """
    closure = manifest["cross_question_event_closure"]
    by_pair = {}
    for row in q05:
        by_pair.setdefault(
            (row["previous_knowledge_date"], row["comparison_date"]), []
        ).append(row["row_id"])

    assert len(q05) == closure["q05_expected_cardinality"] == 35
    assert len(by_pair) == 4
    for bucket in closure["q05_rows_by_adjacent_pair"]:
        key = (
            dt.date.fromisoformat(bucket["previous_knowledge_date"]),
            dt.date.fromisoformat(bucket["comparison_date"]),
        )
        assert key in by_pair, key
        assert len(by_pair[key]) == bucket["expected_count"], key
        assert sorted(by_pair[key]) == sorted(bucket["row_ids"]), key


def test_q05_window_uses_only_the_declared_adjacent_pairs(manifest, q05):
    """All and only the four adjacent eligible complete pairs, per ``q05_window_assertions``.

    Comparisons are pairs of *previous eligible* dates, not previous calendar dates. The
    canonical window's five eligible dates give exactly four pairs; a window filter that
    leaked the 2026-09-07 comparison in would add 12,012 exact removals.
    """
    assertions = manifest["scope"]["schedule_source_universe"]["q05_window_assertions"]
    declared = {
        (dt.date.fromisoformat(a), dt.date.fromisoformat(b))
        for a, b in assertions["adjacent_pairs"]
    }
    seen = {(row["previous_knowledge_date"], row["comparison_date"]) for row in q05}
    assert seen == declared


# ==================================================== 2. the eight Q05 event classes


def test_q05_all_eight_event_classes_present_with_frozen_counts(uc2, q05):
    """Each class asserted on its own, so a collapsed class cannot hide in a correct total.

    22 exact rows (9 modifications, 7 additions, 6 removals) plus 13 evidence rows
    (1 candidate, 1 ambiguous group, 3 ambiguous members, 4 unpaired additions, 4 unpaired
    removals). Every one of the eight ranks in ``enum_sort_ranks.Q05_event_class`` is
    populated: an implementation that never emits, say, ``AMBIGUOUS_CANDIDATE_GROUP`` would
    otherwise only be caught by the total.
    """
    counts: dict[str, int] = {}
    for row in q05:
        counts[row["event_class"]] = counts.get(row["event_class"], 0) + 1

    assert counts == {
        "EXACT_KEY_PRESERVING_MODIFICATION": 9,
        "EXACT_ADDITION": 7,
        "EXACT_REMOVAL": 6,
        "CANDIDATE_UNIQUE": 1,
        "AMBIGUOUS_CANDIDATE_GROUP": 1,
        "AMBIGUOUS_GROUP_MEMBER": 3,
        "UNPAIRED_ADDITION": 4,
        "UNPAIRED_REMOVAL": 4,
    }
    assert set(counts) == set(uc2.EVENT_CLASS_RANK)


def test_q05_exactness_and_confidence_per_class(q05):
    """The five exactness tiers and their confidences never blur.

    ``NEO4J_PARITY_MATRIX.md`` requires exact, candidate, ambiguous and unpaired to remain
    separate and visibly labelled. An implementation that reported everything as ``EXACT``
    would reproduce every other column in this question.
    """
    expected = {
        "EXACT_KEY_PRESERVING_MODIFICATION": ("EXACT", "EXACT"),
        "EXACT_ADDITION": ("EXACT", "EXACT"),
        "EXACT_REMOVAL": ("EXACT", "EXACT"),
        "CANDIDATE_UNIQUE": ("CANDIDATE", "MEDIUM"),
        "AMBIGUOUS_CANDIDATE_GROUP": ("AMBIGUOUS", "LOW"),
        "AMBIGUOUS_GROUP_MEMBER": ("AMBIGUOUS", "LOW"),
        "UNPAIRED_ADDITION": ("UNPAIRED", "NONE"),
        "UNPAIRED_REMOVAL": ("UNPAIRED", "NONE"),
    }
    for row in q05:
        assert (row["exactness"], row["confidence"]) == expected[row["event_class"]], row


def test_q05_ordering_uses_the_class_rank_not_the_class_name(uc2, q05):
    """Alphabetical ``event_class`` ordering would put ``AMBIGUOUS_*`` first and fail.

    Within each comparison date the class ranks must be non-decreasing in the returned order.
    """
    by_date: dict[dt.date, list[int]] = {}
    for row in q05:
        by_date.setdefault(row["comparison_date"], []).append(
            uc2.EVENT_CLASS_RANK[row["event_class"]]
        )
    for day, ranks in by_date.items():
        assert ranks == sorted(ranks), (day, ranks)
    dates = [row["comparison_date"] for row in q05]
    assert dates == sorted(dates)


def test_q05_modification_field_deltas_including_null_transitions(q05):
    """Key-preserving modifications carry the changed field with its old and new values.

    ``SYN-SK-CLOCK_BOUNDARY_001`` transitions ``arrival_station_code_iata`` from null to
    ``PHX`` and back, so both a null ``old_value`` and a null ``new_value`` must survive as
    the frozen ``null``. Absence arrives as ``NaN`` in a ``StringDtype`` column and ``| None``
    raises outright in 1.20.1, so this is where a careless fallback would show up as the
    string ``"None"`` or as a dropped row.
    """
    opened = _one(
        q05,
        event_class="EXACT_KEY_PRESERVING_MODIFICATION",
        schedule_key="SYN-SK-CLOCK_BOUNDARY_001",
        comparison_date=dt.date(2026, 8, 24),
    )
    assert (opened["field_name"], opened["old_value"], opened["new_value"]) == (
        "arrival_station_code_iata",
        None,
        "PHX",
    )
    closed = _one(
        q05,
        event_class="EXACT_KEY_PRESERVING_MODIFICATION",
        schedule_key="SYN-SK-CLOCK_BOUNDARY_001",
        comparison_date=dt.date(2026, 8, 31),
    )
    assert (closed["field_name"], closed["old_value"], closed["new_value"]) == (
        "arrival_station_code_iata",
        "PHX",
        None,
    )
    seats = _one(
        q05,
        event_class="EXACT_KEY_PRESERVING_MODIFICATION",
        schedule_key="SYN-SK-BASE_100",
        comparison_date=dt.date(2026, 8, 10),
    )
    assert (seats["field_name"], seats["old_value"], seats["new_value"]) == (
        "total_seats",
        "180",
        "186",
    )


def test_q05_presence_rows_use_the_presence_pseudo_field(uc2, q05):
    """Additions and removals are presence facts, not content facts."""
    for row in q05:
        if row["event_class"] in {"EXACT_ADDITION", "EXACT_REMOVAL"}:
            assert row["field_name"] == uc2.PRESENCE_FIELD, row
            wanted = ("ABSENT", "PRESENT") if row["event_class"] == "EXACT_ADDITION" else (
                "PRESENT",
                "ABSENT",
            )
            assert (row["old_value"], row["new_value"]) == wanted, row


def test_q05_reappearance_is_a_removal_then_an_addition(q05):
    """``SYN-SK-REAPPEAR_400`` is removed on 2026-08-10 and added back on 2026-08-17.

    That is two exact presence events, not a no-op and not a modification. A change detector
    that diffed only the endpoints of the window would see nothing at all; one that paired the
    removal with the addition would report a modification that never happened.
    """
    removal = _one(
        q05, event_class="EXACT_REMOVAL", schedule_key="SYN-SK-REAPPEAR_400"
    )
    addition = _one(
        q05, event_class="EXACT_ADDITION", schedule_key="SYN-SK-REAPPEAR_400"
    )
    assert removal["comparison_date"] == dt.date(2026, 8, 10)
    assert addition["comparison_date"] == dt.date(2026, 8, 17)
    assert not _rows(
        q05,
        event_class="EXACT_KEY_PRESERVING_MODIFICATION",
        schedule_key="SYN-SK-REAPPEAR_400",
    )
    # It is unpaired on both sides: no candidate ever links the two segments.
    assert _one(
        q05, event_class="UNPAIRED_REMOVAL", member_schedule_key="SYN-SK-REAPPEAR_400"
    )["comparison_date"] == dt.date(2026, 8, 10)
    assert _one(
        q05, event_class="UNPAIRED_ADDITION", member_schedule_key="SYN-SK-REAPPEAR_400"
    )["comparison_date"] == dt.date(2026, 8, 17)


def test_q05_ambiguous_group_and_members_choose_no_winner(q05):
    """One removal compatible with two additions: a group plus three members, no pair.

    ``schedule_key`` and ``related_schedule_key`` are null on all four rows. Picking a winner
    by any tie-break is wrong, and reporting the group without its members would hide which
    keys are in the compatibility component. The ``-Mk`` ordinals follow the manifest-adopted
    ``REMOVED`` before ``ADDED`` then key-ascending rule.
    """
    group = _one(q05, event_class="AMBIGUOUS_CANDIDATE_GROUP")
    assert group["group_id"] == "SYN-AMB-20260824-01"
    assert group["event_id"] == group["group_id"]
    assert group["schedule_key"] is None and group["related_schedule_key"] is None
    assert group["member_side"] is None and group["member_schedule_key"] is None

    members = _rows(q05, event_class="AMBIGUOUS_GROUP_MEMBER")
    assert len(members) == 3
    assert [(m["event_id"], m["member_side"], m["member_schedule_key"]) for m in members] == [
        ("SYN-AMB-20260824-01-M1", "REMOVED", "SYN-SK-AMB_OLD"),
        ("SYN-AMB-20260824-01-M2", "ADDED", "SYN-SK-AMB_NEW_A"),
        ("SYN-AMB-20260824-01-M3", "ADDED", "SYN-SK-AMB_NEW_B"),
    ]
    for member in members:
        assert member["group_id"] == "SYN-AMB-20260824-01"
        assert member["schedule_key"] is None
        assert member["related_schedule_key"] is None
    # The three exact presence rows survive the ambiguity untouched.
    assert _one(q05, event_class="EXACT_REMOVAL", schedule_key="SYN-SK-AMB_OLD")
    assert _one(q05, event_class="EXACT_ADDITION", schedule_key="SYN-SK-AMB_NEW_A")
    assert _one(q05, event_class="EXACT_ADDITION", schedule_key="SYN-SK-AMB_NEW_B")


def test_q05_unpaired_closure_over_every_exact_presence_row(manifest, q05):
    """Every exact presence row is either partnered exactly once or unpaired exactly once.

    ``exact_presence_partner_closure.rule``: no exact presence row may be both partnered and
    unpaired. The candidate consumes one removal and one addition; the ambiguous group
    consumes three; the remaining eight get one unpaired evidence row each with a matching
    comparison date, side and schedule key.
    """
    closure = manifest["cross_question_event_closure"]["exact_presence_partner_closure"]
    consumed: set[tuple[dt.date, str, str]] = set()
    candidate = _one(q05, event_class="CANDIDATE_UNIQUE")
    consumed.add((candidate["comparison_date"], "REMOVED", candidate["schedule_key"]))
    consumed.add(
        (candidate["comparison_date"], "ADDED", candidate["related_schedule_key"])
    )
    for member in _rows(q05, event_class="AMBIGUOUS_GROUP_MEMBER"):
        consumed.add(
            (
                member["comparison_date"],
                member["member_side"],
                member["member_schedule_key"],
            )
        )

    presence = {
        (
            row["comparison_date"],
            "ADDED" if row["event_class"] == "EXACT_ADDITION" else "REMOVED",
            row["schedule_key"],
        )
        for row in q05
        if row["event_class"] in {"EXACT_ADDITION", "EXACT_REMOVAL"}
    }
    unpaired = {
        (row["comparison_date"], row["member_side"], row["member_schedule_key"])
        for row in q05
        if row["event_class"] in {"UNPAIRED_ADDITION", "UNPAIRED_REMOVAL"}
    }

    assert consumed <= presence
    assert unpaired <= presence
    assert not (consumed & unpaired), "a presence row is both partnered and unpaired"
    assert consumed | unpaired == presence, "a presence row is neither partnered nor unpaired"
    assert len(unpaired) == len(closure["unpaired_exact_to_evidence"]) == 8


def test_q05_unpaired_rows_mirror_their_exact_partner(manifest, q05):
    """The eight declared exact-to-unpaired correspondences, row by row."""
    closure = manifest["cross_question_event_closure"]["exact_presence_partner_closure"]
    by_row_id = {row["row_id"]: row for row in q05}
    for pair in closure["unpaired_exact_to_evidence"]:
        exact = by_row_id[pair["exact_row_id"]]
        evidence = by_row_id[pair["unpaired_row_id"]]
        assert exact["schedule_key"] == pair["schedule_key"]
        assert evidence["member_schedule_key"] == pair["schedule_key"]
        assert evidence["member_side"] == pair["side"]
        assert evidence["comparison_date"] == exact["comparison_date"]
        assert evidence["field_name"] is None
        assert evidence["old_value"] is None and evidence["new_value"] is None


def test_q05_cross_question_fixtures_are_not_filtered_out(q05):
    """D-0010/D-0011: no question-private fixture filter is permitted.

    ``SYN-SK-MKT_ENTRY_714`` and ``SYN-SK-MKT_EXIT_715`` exist for Q06 and must still appear
    in Q05 as an exact addition and an exact removal *and* as unpaired evidence - four rows in
    total. The capacity fixtures ``SYN-SK-PHY_BASE_700/701``, ``SYN-SK-MKT_COPY_702`` and
    ``SYN-SK-CSH_ONLY_900`` exist for Q07 and must appear here as terminal modifications.
    """
    assert _one(q05, event_class="EXACT_ADDITION", schedule_key="SYN-SK-MKT_ENTRY_714")
    assert _one(q05, event_class="UNPAIRED_ADDITION", schedule_key="SYN-SK-MKT_ENTRY_714")
    assert _one(q05, event_class="EXACT_REMOVAL", schedule_key="SYN-SK-MKT_EXIT_715")
    assert _one(q05, event_class="UNPAIRED_REMOVAL", schedule_key="SYN-SK-MKT_EXIT_715")
    for capacity_key in (
        "SYN-SK-PHY_BASE_700",
        "SYN-SK-PHY_BASE_701",
        "SYN-SK-MKT_COPY_702",
        "SYN-SK-CSH_ONLY_900",
    ):
        row = _one(
            q05,
            event_class="EXACT_KEY_PRESERVING_MODIFICATION",
            schedule_key=capacity_key,
        )
        assert row["field_name"] == "departure_terminal"


# ======================================================== 3. the key-shift trap (Q05)


def test_key_shift_pair_is_a_labelled_candidate_never_an_exact_change(q05):
    """THE trap the customer says they have not solved.

    ``schedule_key`` hashes the effective and discontinue dates, so a carrier shifting either
    date mints a new key: presence comparison sees one removal of ``SYN-SK-SHIFT_OLD`` and one
    unrelated addition of ``SYN-SK-SHIFT_NEW``. Recognising the pair requires matching on
    ``(carrier, flight_number, origin, destination)`` with overlapping operating ranges, and
    the answer must be reported as a **candidate** carrying confidence and evidence.

    Four things are asserted, and each of them is a separate way to get this wrong:

    1. the two exact presence rows exist and survive - they are not consumed by the candidate;
    2. neither key carries an ``EXACT_KEY_PRESERVING_MODIFICATION`` - the amendment is never
       asserted as an exact modification (a prohibited statement in
       ``NEO4J_PARITY_MATRIX.md``);
    3. the relationship is one ``CANDIDATE_UNIQUE`` row at ``CANDIDATE`` exactness and
       ``MEDIUM`` confidence, naming both keys, on the same comparison date;
    4. neither key appears as unpaired, because the candidate consumed both sides.
    """
    removal = _one(q05, event_class="EXACT_REMOVAL", schedule_key="SYN-SK-SHIFT_OLD")
    addition = _one(q05, event_class="EXACT_ADDITION", schedule_key="SYN-SK-SHIFT_NEW")
    assert removal["comparison_date"] == addition["comparison_date"] == dt.date(2026, 8, 17)
    assert removal["exactness"] == addition["exactness"] == "EXACT"

    for key in ("SYN-SK-SHIFT_OLD", "SYN-SK-SHIFT_NEW"):
        assert not _rows(
            q05, event_class="EXACT_KEY_PRESERVING_MODIFICATION", schedule_key=key
        ), f"{key} must never be reported as an exact modification"

    candidate = _one(q05, event_class="CANDIDATE_UNIQUE")
    assert candidate["schedule_key"] == "SYN-SK-SHIFT_OLD"
    assert candidate["related_schedule_key"] == "SYN-SK-SHIFT_NEW"
    assert candidate["exactness"] == "CANDIDATE"
    assert candidate["confidence"] == "MEDIUM"
    assert candidate["comparison_date"] == dt.date(2026, 8, 17)
    assert candidate["event_id"] == "SYN-CAND-20260817-01"
    assert candidate["field_name"] is None
    assert candidate["group_id"] is None

    for key in ("SYN-SK-SHIFT_OLD", "SYN-SK-SHIFT_NEW"):
        assert not _rows(q05, member_schedule_key=key), f"{key} was consumed, not unpaired"


def test_no_row_claims_exact_confidence_for_a_key_changing_amendment(q05):
    """No evidence row may borrow the exact layer's labels.

    Every ``CANDIDATE``, ``AMBIGUOUS`` or ``UNPAIRED`` row must carry a non-``EXACT``
    confidence, and every ``EXACT`` row must carry a null ``related_schedule_key`` - an exact
    fact never names a partner.
    """
    for row in q05:
        if row["exactness"] == "EXACT":
            assert row["confidence"] == "EXACT", row
            assert row["related_schedule_key"] is None, row
        else:
            assert row["confidence"] != "EXACT", row


# ================================================== 4. snapshot completeness (Q05/Q06)


def test_incomplete_snapshot_does_not_manufacture_a_removal(q05_gap):
    """``TT12-R01`` / ``TT12-R02`` / ``TT13-R01``, live.

    The window 2026-10-05 to 2026-10-26 brackets a missing snapshot (2026-10-12,
    ``MISSING_DECLARED``) and an incomplete one (2026-10-19, present with 9,917 rows and
    ``INCOMPLETE_RETAINED``). Both endpoints are eligible, so the query runs - and it must
    produce exactly one absence-derived event, observed at 2026-10-26 against 2026-10-05,
    with ``crosses_snapshot_gap`` true. Neither ineligible date may appear as a comparison
    endpoint, and neither may contribute a removal of its own: 9,917 rows out of ~12,000 would
    otherwise look like about 2,100 removals on 2026-10-19 and the same number of additions on
    2026-10-26.
    """
    assert len(q05_gap) == 2
    for row in q05_gap:
        assert row["comparison_date"] == GAP_AFTER, row
        assert row["previous_knowledge_date"] == GAP_PREVIOUS, row
        assert row["crosses_snapshot_gap"] is True, row
        assert GAP_MISSING not in (row["comparison_date"], row["previous_knowledge_date"])
        assert GAP_INCOMPLETE not in (
            row["comparison_date"],
            row["previous_knowledge_date"],
        )

    classes = sorted(row["event_class"] for row in q05_gap)
    assert classes == ["EXACT_REMOVAL", "UNPAIRED_REMOVAL"]
    keys = {row["schedule_key"] for row in q05_gap}
    assert keys == {"SYN-SK-GAP_CONTROL_001"}


def test_events_outside_the_canonical_window_are_visibly_unlabelled(uc2, q05_gap):
    """The supplied label table cannot mask an extra or misclassified event (D-0018).

    ``q05_event_labels`` is keyed on ``comparison_date``, so it labels ``Q05-CANONICAL`` only.
    Any other parameterisation must render a visible ``UNLABELLED|...`` id rather than
    silently re-attaching a valid-looking mnemonic. That fail-loud behaviour is what makes the
    label join safe.
    """
    for row in q05_gap:
        assert row["event_id"].startswith(uc2._UNLABELLED), row
        assert row["row_id"].startswith(uc2._UNLABELLED), row


def test_q05_refuses_an_ineligible_endpoint_rather_than_falling_back(uc2):
    """2026-10-12 is absent, so the comparison is refused with ``ENDPOINT_MISSING``.

    The previous eligible complete snapshot for that region is 2026-10-05. Substituting it
    would answer a different question and return rows where the manifest freezes none.
    """
    with pytest.raises(uc2.EndpointError) as excinfo:
        uc2.schedule_four_week_changes(GAP_MISSING, GAP_INCOMPLETE, 7)
    assert excinfo.value.error_code == "ENDPOINT_MISSING"
    assert excinfo.value.invocation_status == "ENDPOINT_MISSING"


def test_q06_refuses_an_incomplete_endpoint_and_names_it_incomplete(uc2):
    """Present but incomplete is a distinct refusal from absent.

    ``Q06-INCOMPLETE-ENDPOINT`` compares 2026-10-26 with 2026-10-19: the latter is present, so
    ``ENDPOINT_MISSING`` would be the wrong code, and falling back to 2026-10-05 would return
    rows. Latest-versus-seven-days requires both *exact* calendar endpoints to be eligible.
    """
    with pytest.raises(uc2.EndpointError) as excinfo:
        uc2.market_latest_vs_seven_days(GAP_AFTER, GAP_INCOMPLETE, "marketing")
    assert excinfo.value.error_code == "ENDPOINT_INCOMPLETE"
    assert excinfo.value.invocation_status == "ENDPOINT_INCOMPLETE"


def test_snapshot_eligibility_is_presence_and_completeness_only(uc2):
    """Row counts are validation evidence, never a completeness test.

    2026-10-26 is complete with an observed row count of **zero** and must be eligible;
    2026-10-19 is present with 9,917 rows and must not be. Any implementation that inferred
    completeness from a row count gets both of these backwards.

    Scoped by year. D-0025 added 26 snapshot dates in 2027 - 24 eligible, one present but
    incomplete, one missing - so that the enriched schedule block exercises presence,
    completeness and gap semantics on its own dates without touching the 2026 calendar any
    frozen expectation reads. Asserting one flat set would couple the 2026 contract to the
    2027 enrichment, which is exactly the coupling D-0023's additivity argument avoids.
    """
    calendar = uc2.snapshot_calendar()
    assert calendar[GAP_AFTER] == (True, True)
    assert calendar[GAP_INCOMPLETE] == (True, False)
    assert calendar[GAP_MISSING] == (False, False)
    eligible = {day for day, (present, complete) in calendar.items() if present and complete}

    assert {day for day in eligible if day.year == 2026} == {
        dt.date(2026, 8, 3),
        dt.date(2026, 8, 10),
        dt.date(2026, 8, 17),
        dt.date(2026, 8, 24),
        dt.date(2026, 8, 31),
        dt.date(2026, 9, 7),
        dt.date(2026, 10, 5),
        dt.date(2026, 10, 26),
    }

    block_2027 = {day: flags for day, flags in calendar.items() if day.year == 2027}
    assert len(block_2027) == 26
    assert sum(1 for present, complete in block_2027.values() if present and complete) == 24
    assert sum(1 for present, complete in block_2027.values() if present and not complete) == 1
    assert sum(1 for present, _ in block_2027.values() if not present) == 1
    assert set(calendar) == set(block_2027) | {
        day for day in calendar if day.year == 2026
    }


# ==================================================== 5. multi-open route states (Q07)


def test_concurrent_open_route_states_on_one_route(uc2, invocations):
    """One route, several concurrently valid states. ``Q07-R001`` depends on it.

    Schedule versioning partitions by schedule identity and never by route, so ``SFO->LAX``
    carries many states that are concurrently valid at 2026-08-31. Two of them are eligible on
    both clocks for ``SYN-OP-A``, and its answer is the **sum** over both: frequency 10 from
    7 + 3, and 1560 seats from 7 x 180 plus 3 x 100. Any ``argmax``, "latest state per route"
    or unique-state assumption silently returns one of them and a plausible wrong number.
    """
    am = uc2.model_package()
    from relationalai.semantics.std import aggregates as aggs

    per_route = am.model.select(
        am.Route.route_id.alias("route_id"),
        aggs.count(am.RouteState).per(am.Route).alias("open_states"),
    ).where(
        am.RouteState.route == am.Route,
        *am.known_on(am.RouteState, KNOWLEDGE_DATE),
    ).to_df()
    counts = {str(r["route_id"]): int(r["open_states"]) for r in per_route.to_dict("records")}
    assert counts["SFO->LAX"] > 1
    assert sum(1 for v in counts.values() if v > 1) > 1
    # Measured 2026-09-02 after the D-0023 reload: every one of the ten routes carries over a
    # thousand concurrently open states at this knowledge date, SFO->LAX 1,339 of them. The
    # three-digit gap between that and Q07-MARKETING's active_schedule_count of 2 is the whole
    # point: the partition is by schedule identity and carrier, never by route.
    assert counts["SFO->LAX"] > 1000
    assert all(v > 1 for v in counts.values())

    _, _, marketing = invocations["Q07-MARKETING"]
    rows = marketing.to_dict("records")
    multi = [r for r in rows if r["airline_id"] == "SYN-OP-A"][0]
    assert multi["route_id"] == "SFO->LAX"
    assert multi["active_schedule_count"] == 2
    assert multi["weekly_frequency"] == 10
    assert multi["weekly_total_seats"] == 1560.0
    single = [r for r in rows if r["airline_id"] == "SYN-MKT-B"][0]
    assert single["active_schedule_count"] == 1
    assert single["weekly_frequency"] == 7
    assert single["weekly_total_seats"] == 1260.0


def test_q07_cabin_buckets_sum_to_the_weekly_total(invocations):
    """The four exclusive cabin buckets must sum to the weekly total on every counted row.

    Premium economy is a subset of economy (DV-26), so the exclusive economy bucket is
    economy minus premium. Forgetting that double counts premium economy: for ``Q07-R002`` the
    per-flight buckets are 8 + 20 + 20 + 132 = 180, and 7 x 180 = 1260.
    """
    for result_set_id in ("Q07-MARKETING", "Q07-OPERATING"):
        _, _, frame = invocations[result_set_id]
        for row in frame.to_dict("records"):
            if row["result_status"] != "COUNTED":
                continue
            total = (
                row["weekly_first_seats"]
                + row["weekly_business_seats"]
                + row["weekly_premium_economy_seats"]
                + row["weekly_economy_excluding_premium_seats"]
            )
            assert total == pytest.approx(row["weekly_total_seats"]), (result_set_id, row)
            assert row["cabin_quality"] == "RECONCILED", row


# =========================================================== 6. both clocks (TT-23)


def test_both_clocks_truth_table_complete(uc2, truth_table, frozen_truth_table):
    """All nine ``TT-BOTH-CLOCKS`` rows, cell by cell.

    Exactly two of nine combinations are eligible. This is the table that catches dropping a
    clock: filtering on knowledge alone would make ``TT23-R04`` eligible, and filtering on
    operating alone would make ``TT23-R02``, ``R03``, ``R08`` and ``R09`` eligible.
    """
    expected = [uc2._manifest_row(r) for r in frozen_truth_table["rows"]]
    diffs = uc2.compare_rows(truth_table, expected, tuple(truth_table.columns))
    assert not diffs, "; ".join(diffs[:10])
    assert len(truth_table) == frozen_truth_table["expected_cardinality"] == 9


def test_operating_upper_bound_is_inclusive(truth_table):
    """``TT23-R06``: the last operating day is an operating day.

    ``discontinue_date`` is the last operating day, not the first excluded one. Applying
    half-open semantics to it - the single most tempting refactor in ``temporal.py`` - makes
    this row ineligible and loses the last day of every schedule in the demo.
    """
    rows = {r["row_id"]: r for r in truth_table.to_dict("records")}
    at_end = rows["TT23-R06"]
    assert at_end["operating_position"] == "AT_END"
    assert at_end["operating_date"] == dt.date(2026, 9, 7)
    assert at_end["eligible"] is True
    inside = rows["TT23-R05"]
    assert inside["eligible"] is True


def test_knowledge_upper_bound_is_exclusive(truth_table, invocations):
    """``TT23-R07`` to ``TT23-R09``: ``knowledge_position = AT_END`` is never eligible.

    Knowledge validity is half-open, so a state whose ``knowledge_valid_to`` equals the
    knowledge date has been superseded. Making that bound inclusive would admit the superseded
    state in all three rows, and would also turn ``Q07-KNOWLEDGE-END-EMPTY`` from a correct
    empty answer into a populated wrong one.
    """
    rows = {r["row_id"]: r for r in truth_table.to_dict("records")}
    for row_id in ("TT23-R07", "TT23-R08", "TT23-R09"):
        assert rows[row_id]["knowledge_position"] == "AT_END"
        assert rows[row_id]["eligible"] is False, row_id
    _, _, empty = invocations["Q07-KNOWLEDGE-END-EMPTY"]
    assert len(empty) == 0


def test_dropping_a_clock_changes_the_answer(uc2):
    """Both clocks are load-bearing, proved by removing each one in turn.

    Neither single-clock variant errors and both return well-formed frames, which is exactly
    why this failure is silent in production. Knowledge-only admits states that are known but
    not operating on 2026-09-07; operating-only admits states as understood at every knowledge
    date rather than at 2026-08-31.
    """
    am = uc2.model_package()
    from relationalai.semantics import distinct
    from relationalai.semantics.std import aggregates as aggs

    from aviation_model.computed_schedule import RouteStateOperatesOnWeekday

    def markets(*clauses):
        df = am.model.select(
            distinct(
                am.Airline.airline_id.alias("airline_id"),
                am.Route.route_id.alias("route_id"),
                aggs.sum(am.RouteState.weekly_frequency)
                .per(am.Airline, am.Route)
                .alias("weekly_frequency"),
            )
        ).where(
            *clauses,
            am.RouteState.marketing_airline == am.Airline,
            am.RouteState.route == am.Route,
            am.RouteState.schedule == am.Schedule,
        ).to_df()
        return {
            (str(r["airline_id"]), str(r["route_id"])): int(r["weekly_frequency"])
            for r in df.to_dict("records")
        }

    both = markets(
        *am.known_on(am.RouteState, KNOWLEDGE_DATE),
        *am.operates_on(am.RouteState, OPERATING_DATE, RouteStateOperatesOnWeekday),
    )
    knowledge_only = markets(*am.known_on(am.RouteState, KNOWLEDGE_DATE))
    operating_only = markets(
        *am.operates_on(am.RouteState, OPERATING_DATE, RouteStateOperatesOnWeekday)
    )

    assert len(both) == 3
    assert both != knowledge_only
    assert both != operating_only
    assert len(knowledge_only) > len(both)
    assert len(operating_only) > len(both)


def test_moving_either_clock_moves_the_enriched_answer(invocations):
    """The 1.2.0 two-clock beat: each clock changes the answer on its own, by a known amount.

    Three enriched result sets share two of their three parameters. Moving the knowledge date
    back one week changes 8 of the 30 markets; moving the operating date from Monday to the
    preceding Saturday changes 4. Measured against the manifest rather than predicted: D-0023
    forecast "exactly 4 rows when either clock moves", and the knowledge side actually moves
    8. Both are non-zero, which is the property the demo beat needs - a single-clock
    implementation would return the same frame for at least one of these pairs.
    """

    def measures(result_set_id):
        _, _, frame = invocations[result_set_id]
        return {
            (row["airline_id"], row["route_id"]): (
                row["result_status"],
                row["active_schedule_count"],
                row["weekly_frequency"],
                row["weekly_total_seats"],
            )
            for row in frame.to_dict("records")
        }

    late = measures("Q07-ENRICHED-KNOWLEDGE-LATE")
    early = measures("Q07-ENRICHED-KNOWLEDGE-EARLY")
    shifted = measures("Q07-ENRICHED-OPERATING-SHIFT")

    def moved(a, b):
        return {k for k in set(a) | set(b) if a.get(k) != b.get(k)}

    assert len(late) == len(early) == len(shifted) == 30
    assert len(moved(late, early)) == 8, sorted(moved(late, early))
    assert len(moved(late, shifted)) == 4, sorted(moved(late, shifted))


# ============================================== 7. codeshare and carrier-role separation


def test_codeshare_only_service_is_visibly_unresolved_not_dropped(invocations):
    """``Q07-R004``: emitted as unresolved, with every measure null and the key named.

    ``SYN-SK-CSH_ONLY_900`` is a codeshare-only service on ``SFO->SEA``. Under the operating
    role it has no physical base representative, so it cannot be counted - but excluding it
    would make the operating answer a one-row result where two are expected, and guessing a
    number would attribute somebody else's metal to ``SYN-OP-X``. The honest answer is a
    visible ``UNRESOLVED_PHYSICAL_SERVICE`` row.
    """
    _, _, frame = invocations["Q07-OPERATING"]
    rows = frame.to_dict("records")
    assert len(rows) == 2
    unresolved = [r for r in rows if r["result_status"] == "UNRESOLVED_PHYSICAL_SERVICE"]
    assert len(unresolved) == 1
    row = unresolved[0]
    assert row["airline_id"] == "SYN-OP-X"
    assert row["route_id"] == "SFO->SEA"
    assert row["unresolved_service_key"] == "SYN-SK-CSH_ONLY_900"
    assert row["cabin_quality"] == "NOT_COUNTED"
    for measure in (
        "active_schedule_count",
        "weekly_frequency",
        "weekly_total_seats",
        "weekly_first_seats",
        "weekly_business_seats",
        "weekly_premium_economy_seats",
        "weekly_economy_excluding_premium_seats",
    ):
        assert row[measure] is None, measure
    # COUNTED sorts before the unresolved status.
    assert rows[0]["result_status"] == "COUNTED"


def test_physical_capacity_is_not_double_counted(invocations):
    """The operating role counts metal once, and may visibly undercount rather than inflate.

    ``SYN-OP-A`` on ``SFO->LAX`` reports identical numbers under both roles because it is the
    marketing carrier of its own schedules: two correct rows in two different result sets, not
    double counting. Meanwhile ``SFO->SEA`` carries 200 marketing seats for ``SYN-MKT-X`` and
    **no** counted operating capacity at all, because the only operating-side service there is
    a codeshare. That undercount is the contracted behaviour: the alternative would be to
    count the same aircraft twice.
    """
    _, _, marketing = invocations["Q07-MARKETING"]
    _, _, operating = invocations["Q07-OPERATING"]
    m_rows = {(r["airline_id"], r["route_id"]): r for r in marketing.to_dict("records")}
    o_rows = {(r["airline_id"], r["route_id"]): r for r in operating.to_dict("records")}

    for measure in (
        "active_schedule_count",
        "weekly_frequency",
        "weekly_total_seats",
        "weekly_first_seats",
        "weekly_business_seats",
        "weekly_premium_economy_seats",
        "weekly_economy_excluding_premium_seats",
    ):
        assert (
            m_rows[("SYN-OP-A", "SFO->LAX")][measure]
            == o_rows[("SYN-OP-A", "SFO->LAX")][measure]
        ), measure

    marketing_sfo_sea = m_rows[("SYN-MKT-X", "SFO->SEA")]
    assert marketing_sfo_sea["weekly_total_seats"] == 200.0
    counted_operating = [
        r
        for r in operating.to_dict("records")
        if r["route_id"] == "SFO->SEA" and r["result_status"] == "COUNTED"
    ]
    assert counted_operating == []

    marketing_total = sum(
        r["weekly_total_seats"]
        for r in marketing.to_dict("records")
        if r["result_status"] == "COUNTED"
    )
    operating_total = sum(
        r["weekly_total_seats"]
        for r in operating.to_dict("records")
        if r["result_status"] == "COUNTED"
    )
    assert operating_total <= marketing_total


def test_carrier_roles_never_merge(uc2, invocations):
    """Marketing and operating are separate dimensions, and every row says which it is."""
    _, _, marketing = invocations["Q07-MARKETING"]
    _, _, operating = invocations["Q07-OPERATING"]
    assert set(marketing["carrier_role"]) == {"marketing"}
    assert set(operating["carrier_role"]) == {"operating"}
    _, _, q06 = invocations["Q06-CANONICAL"]
    assert set(q06["carrier_role"]) == {"marketing"}


# ============================================================= 8. Q06 specifics


def test_q06_entries_and_exits_partition_the_two_endpoints(market_totals, invocations):
    """The anti-join correlation is binding, proved arithmetically.

    ``n_latest - entries`` and ``n_comparison - exits`` must both equal the intersection. If
    they disagree, the ``not_()`` is testing "no such state anywhere" rather than "no such
    state for this market", which is the classic failure of the correlated anti-join and would
    return either every market or none.
    """
    _, _, frame = invocations["Q06-CANONICAL"]
    rows = frame.to_dict("records")
    entries = [r for r in rows if r["change_kind"] == "ENTRY"]
    exits = [r for r in rows if r["change_kind"] == "EXIT"]
    assert len(entries) == 1 and len(exits) == 1
    assert market_totals["latest"] - len(entries) == market_totals["comparison"] - len(exits)
    assert market_totals["latest"] > 100, "the stable market shadows must be present"


def test_q06_counts_are_zero_crossings_at_schedule_key_grain(invocations):
    """Before/after counts are distinct eligible schedule keys, not lineage contributions.

    Both are 0 or 1 in the canonical answer, so an inflation bug shows up immediately. A
    transition of 1 to 2 or 2 to 1 is deliberately not an event, which is what the stable
    positive market shadows exercise: 156 markets are live at each endpoint and only two of
    them cross zero.
    """
    _, _, frame = invocations["Q06-CANONICAL"]
    rows = frame.to_dict("records")
    entry = [r for r in rows if r["change_kind"] == "ENTRY"][0]
    exit_row = [r for r in rows if r["change_kind"] == "EXIT"][0]
    assert (entry["before_schedule_count"], entry["after_schedule_count"]) == (0, 1)
    assert (exit_row["before_schedule_count"], exit_row["after_schedule_count"]) == (1, 0)
    assert entry["airline_id"] == "SYN-MKT-ENTRY" and entry["route_id"] == "SEA->DEN"
    assert exit_row["airline_id"] == "SYN-MKT-EXIT" and exit_row["route_id"] == "BOS->MIA"
    for row in rows:
        assert row["comparison_knowledge_date"] == COMPARISON_DATE
        assert row["latest_knowledge_date"] == KNOWLEDGE_DATE


def test_q06_operating_role_runs_and_stays_separate(uc2):
    """The operating role is a real, separately answerable question, not an untested branch."""
    frame = uc2.market_latest_vs_seven_days(KNOWLEDGE_DATE, COMPARISON_DATE, "operating")
    assert list(frame.columns) == list(uc2.Q06_COLUMNS)
    assert set(frame["carrier_role"]) <= {"operating"}
    for row in frame.to_dict("records"):
        assert row["change_kind"] in {"ENTRY", "EXIT"}
        counts = (row["before_schedule_count"], row["after_schedule_count"])
        assert 0 in counts and max(counts) > 0, row


# ========================================================== 9. typed parameter refusals


@pytest.mark.parametrize(
    "call, error_code",
    [
        (("Q07", (None, "2026-09-07", "operating")), "MISSING_KNOWLEDGE_DATE"),
        (("Q07", ("2026-08-31", None, "operating")), "MISSING_OPERATING_DATE"),
        (("Q07", ("2026-08-31", "2026-09-07", None)), "MISSING_CARRIER_ROLE"),
        (("Q07", ("2026-02-30", "2026-09-07", "operating")), "INVALID_DATE"),
        (("Q07", ("2026-08-31", "2026-09-07", "codeshare")), "INVALID_CARRIER_ROLE"),
        (("Q06", ("2026-08-31", "2026-08-24", None)), "MISSING_CARRIER_ROLE"),
        (("Q06", ("2026-02-30", "2026-02-23", "marketing")), "INVALID_DATE"),
        (("Q06", (None, "2026-08-24", "marketing")), "MISSING_LATEST_KNOWLEDGE_DATE"),
        (("Q05", (None, "2026-08-31", 7)), "MISSING_START_KNOWLEDGE_DATE"),
        (("Q05", ("2026-08-03", "2026-13-01", 7)), "INVALID_DATE"),
        (("Q05", ("2026-08-03", "2026-08-31", 0)), "INVALID_CADENCE_DAYS"),
        (("Q05", ("2026-08-03", "2026-08-31", None)), "MISSING_CADENCE_DAYS"),
    ],
)
def test_parameter_errors_are_typed_and_raised_before_execution(uc2, call, error_code):
    """Validation returns an error code before any query runs, and never a default.

    ``canonicalization.object_rules``: a ``PARAMETER_ERROR`` scenario intentionally contains a
    null or an uncastable raw date input, validation returns the error code before query
    execution, and rows remain empty. A ``carrier_role`` default would silently answer the
    marketing question when the operating one was asked.
    """
    question_id, args = call
    with pytest.raises(uc2.ParameterError) as excinfo:
        uc2.QUESTION_FUNCTIONS[question_id](*args)
    assert excinfo.value.error_code == error_code
    assert excinfo.value.invocation_status == "PARAMETER_ERROR"


def test_invalid_date_is_distinguishable_from_a_missing_date(uc2):
    """2026-02-30 is uncastable, not absent, and the two are different faults."""
    with pytest.raises(uc2.ParameterError) as invalid:
        uc2.market_latest_vs_seven_days("2026-02-30", "2026-02-23", "marketing")
    with pytest.raises(uc2.ParameterError) as missing:
        uc2.market_latest_vs_seven_days("2026-08-31", None, "marketing")
    assert invalid.value.error_code == "INVALID_DATE"
    assert missing.value.error_code == "MISSING_COMPARISON_KNOWLEDGE_DATE"


def test_dates_accept_both_iso_strings_and_date_objects(uc2, invocations):
    """The catalog layer passes strings; a notebook passes ``datetime.date``. Both must work.

    ``canonicalization.date_representation`` is a quoted ISO scalar cast to DATE before
    comparison, so accepting the string form is part of reproducing the frozen parameters.
    """
    from_strings = uc2.route_capacity_two_clocks("2026-08-31", "2026-09-07", "marketing")
    _, _, from_manifest = invocations["Q07-MARKETING"]
    assert list(from_strings["airline_id"]) == list(from_manifest["airline_id"])
    assert list(from_strings["knowledge_date"]) == [KNOWLEDGE_DATE] * 3


def test_unlabelled_rows_when_no_label_source_is_supplied(uc2):
    """Without the conformance harness, ``row_id`` is a visible fail-loud token.

    D-0018: the supplied labels live in the manifest, not in the model and not in the query
    module. A query run with no label source still returns every derived cell, and says
    plainly that its identity column is not derived.
    """
    frame = uc2.route_capacity_two_clocks(KNOWLEDGE_DATE, OPERATING_DATE, "marketing")
    assert len(frame) == 3
    for row in frame.to_dict("records"):
        assert row["row_id"].startswith(uc2._UNLABELLED), row
        assert row["airline_id"] in {"SYN-MKT-B", "SYN-MKT-X", "SYN-OP-A"}
