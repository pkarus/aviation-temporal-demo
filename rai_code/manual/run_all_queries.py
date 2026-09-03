#!/usr/bin/env python3
"""run_all_queries.py - every question in the aviation temporal demo, as text. No charts.

DO NOT EDIT. GENERATED from the ontology package and ``rai_code/queries/`` by
``python rai_code/manual/_gen_run_all_queries.py``. The query logic below is the *same bytes*
as ``rai_code/queries/uc1.py``, ``uc2.py`` and ``rotation.py``; edit those and regenerate.

One self-contained file. Nothing beside it is needed and nothing is imported from beside it -
no ``raiconfig.yaml``, no ``aviation`` package on ``sys.path``, no staged sibling modules, no
``EXPECTED_ANSWERS.yaml``, no credentials. The ontology and all three query modules are embedded
below and exec'd into their own namespaces, so the file does not care what the working directory
is. ``_build_config()`` picks ``ConfigFromActiveSession`` when a Snowpark session exists and
``create_config()`` otherwise, which is why the same bytes run in both places.

    # Snowsight Workspace: open the file, connect a notebook service, press Run.
    # local:
    .venv/bin/python rai_code/manual/run_all_queries.py
    .venv/bin/python rai_code/manual/run_all_queries.py Q03 Q08

Running it in a Snowsight Workspace needs two things from the notebook service, both set once
under **Edit service**, and neither of which this file can do for you:

* an x86 compute pool you have ``USAGE`` on, with ``NOTEBOOK`` in its allowed workload types;
* a package source for ``relationalai``, which is PyPI-only and *not* in Snowflake's Anaconda
  channel: either the managed artifact repository
  ``snowflake.snowpark.pypi_shared_repository`` or an external access integration with PyPI
  egress (this account has one named ``PYPI_ACCESS``). Picking an artifact repository disables
  integration-based installs, so choose one.

:func:`ensure_runtime` then pip-installs whatever is still missing. Workspace package installs
do not survive the weekend maintenance restart, so seeing it install is normal.

Getting this file into a Workspace. There is no ``snow workspace`` command, but a workspace is
addressable as a filesystem over SQL, so a one-line ``PUT`` is the repeatable route - no UI
click-through, and re-runnable after every regenerate::

    snow sql -c rai --role RAI_DEMO_AVIATION_TEMPORAL -q "PUT
      'file://<repo>/rai_code/manual/run_all_queries.py'
      'snow://workspace/\"USER$<you>\".PUBLIC.\"DEFAULT$\"/versions/live/aviation/queires/'
      AUTO_COMPRESS=FALSE OVERWRITE=TRUE;"

``LS 'snow://workspace/..."DEFAULT$"/versions/head/aviation/'`` lists what is there now. The
Snowsight UI route (Projects, Workspaces, the ``+`` beside a folder, Upload Files) does the
same thing by hand.

Nine question groups, 25 enriched parameter sets, all against the live
``PK_AVIATION_TEMPORAL`` database through the ``aviation_temporal_logic_s`` reasoner.

Runtime. **8.7 minutes** for all 25, measured 2026-09-03 against ``aviation_temporal_logic_s``
(HIGHMEM_X64_S) already READY, from a laptop. Budget longer in a Workspace, where the container
also pays a cold start and a pip install.

* Model sync, once, before the first question: 135s of that 8.7 minutes. Nine to eleven minutes
  instead if the engine is SUSPENDED and has to provision first, so resume it beforehand:
  ``rai reasoners resume --type Logic --name aviation_temporal_logic_s --wait``.
* Q03 opens because it is the cheapest thing that looks impressive: 985 rows in 4.3s, 120 month
  ends from one query. Q04, Q02, Q08 and Q06 are all 4 to 12s.
* Q02F closes at 103s because it derives every storage spell in the fleet, and Q01 costs 17-18s
  per parameter set because it resolves four independently clocked dimensions with a separate
  query each. Both are structural, so they run last and the output starts moving immediately.
* One Q07 set took 71s against 9-11s for the other three: first touch on the knowledge-clock
  relations, not a property of that parameter set.

Selecting a subset. Edit :data:`QUESTIONS` below, pass question ids on the command line, or
call :func:`run` directly::

    run(questions=["Q03", "Q08"])          # two groups
    run(questions=UC1)                     # Q01, Q02, Q02F, Q03, Q04
    run(questions=UC2)                     # Q05, Q06, Q07
    run(result_sets=["Q07-ENRICHED-ROLE"]) # one parameter set
    run(include_frozen=True)               # also the v1.1.1 sets, error cases included

A failing question is reported and the run continues; the summary table at the end says which.

Open validity intervals read as the ``9999-01-01`` model sentinel on a laptop and as a bare
``NaT`` in the Snowflake runtime. Both mean "still open"; the printer does not normalise them,
so you will see whichever one your runtime produced.
"""

from __future__ import annotations

import sys
import time
import traceback
import types


# --------------------------------------------------------------------------- what to run

#: Question groups to run. ``None`` runs all nine, in the order below. Overridden by any
#: question ids given on the command line.
QUESTIONS: list[str] | None = None

#: Individual parameter sets to run, by ``result_set_id``. ``None`` runs every set selected by
#: :data:`QUESTIONS` and :data:`INCLUDE_FROZEN`.
RESULT_SETS: list[str] | None = None

#: The v1.1.1 frozen sets are mostly one to three rows and include the deliberate parameter-error
#: cases. Off by default; the v1.2.0 enriched sets are the interesting ones.
INCLUDE_FROZEN: bool = False

#: Rows printed per result set. ``None`` prints every row - Q03 enriched alone is 985 of them.
MAX_DISPLAY_ROWS: int | None = 20

#: Widest column the printer will render before truncating with an ellipsis.
MAX_COLUMN_WIDTH: int = 30

UC1 = ["Q01", "Q02", "Q02F", "Q03", "Q04"]
UC2 = ["Q05", "Q06", "Q07"]
ROTATION = ["Q08"]

#: One entry per question group, slowest last. Generated from ``EXPECTED_ANSWERS.yaml``
#: (parameters, declared parameter order, expected cardinality) and ``DEMO_QUESTIONS.md``
#: (the business question). Regenerate rather than editing.
QUESTION_SPECS = [{'question_id': 'Q03',
  'catalog_id': 'month_end_fleet_composition',
  'module': 'uc1',
  'heading': 'Q03 - Produce 120 month-end fleet-composition points',
  'business_question': 'At each month end for ten calendar years, how many in-service aircraft '
                       'are assigned to each exact aircraft type?',
  'parameter_order': ['start_month_end', 'end_month_end', 'status'],
  'order_by': ['month_end ASC', 'aircraft_type_id ASC'],
  'result_sets': [{'result_set_id': 'Q03-CANONICAL',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'start_month_end': '2015-01-31',
                                  'end_month_end': '2024-12-31',
                                  'status': 'In Service'},
                   'expected_status': 'OK',
                   'expected_rows': 132},
                  {'result_set_id': 'Q03-ENRICHED',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'start_month_end': '2025-01-31',
                                  'end_month_end': '2034-12-31',
                                  'status': 'In Service'},
                   'expected_status': 'OK',
                   'expected_rows': 985}]},
 {'question_id': 'Q04',
  'catalog_id': 'type_engine_histories',
  'module': 'uc1',
  'heading': 'Q04 - Show independent type and engine histories',
  'business_question': 'For one aircraft, list type and engine assignment intervals '
                       'independently and identify the type assignments that change the type '
                       'from the preceding assignment.',
  'parameter_order': ['aircraft_id'],
  'order_by': ['dimension ASC', 'valid_from ASC', 'assignment_id ASC'],
  'result_sets': [{'result_set_id': 'Q04-CANONICAL',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1001},
                   'expected_status': 'OK',
                   'expected_rows': 4},
                  {'result_set_id': 'Q04-ENRICHED-ENGINE-ONLY',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1000},
                   'expected_status': 'OK',
                   'expected_rows': 3},
                  {'result_set_id': 'Q04-ENRICHED-TYPE-ONLY',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1207},
                   'expected_status': 'OK',
                   'expected_rows': 3},
                  {'result_set_id': 'Q04-ENRICHED-INDEPENDENT',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1107},
                   'expected_status': 'OK',
                   'expected_rows': 4},
                  {'result_set_id': 'Q04-ENRICHED-COUPLED',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1307},
                   'expected_status': 'OK',
                   'expected_rows': 4}]},
 {'question_id': 'Q02',
  'catalog_id': 'status_reversion_spells',
  'module': 'uc1',
  'heading': 'Q02 - Find every In Service → Storage → In Service spell',
  'business_question': 'For an aircraft, which ordered audit-status assignments form every '
                       'reversion spell, how many calendar days did Storage last, and was it a '
                       'same-day spell?',
  'parameter_order': ['aircraft_id'],
  'order_by': ['storage_start_date ASC',
               'storage_start_sequence ASC',
               'storage_event_id ASC',
               'return_event_id ASC'],
  'result_sets': [{'result_set_id': 'Q02-CANONICAL',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1001},
                   'expected_status': 'OK',
                   'expected_rows': 2},
                  {'result_set_id': 'Q02-NO-SPELLS',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1004},
                   'expected_status': 'OK',
                   'expected_rows': 0},
                  {'result_set_id': 'Q02-ENRICHED-MULTI-SPELL',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1860},
                   'expected_status': 'OK',
                   'expected_rows': 3},
                  {'result_set_id': 'Q02-ENRICHED-LONG-SPELL',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1556},
                   'expected_status': 'OK',
                   'expected_rows': 2},
                  {'result_set_id': 'Q02-ENRICHED-SAME-DAY',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1859},
                   'expected_status': 'OK',
                   'expected_rows': 2},
                  {'result_set_id': 'Q02-ENRICHED-STATUS-BUT-NO-STORAGE',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1307},
                   'expected_status': 'OK',
                   'expected_rows': 0}]},
 {'question_id': 'Q08',
  'catalog_id': 'actual_rotation_enriched',
  'module': 'rotation',
  'heading': 'Q08 - Reconstruct and enrich an actual aircraft rotation',
  'business_question': 'For one aircraft and source-local departure date, what is the validated '
                       'ordered actual-leg chain, where did each leg actually operate, and what '
                       'aircraft type/engine was independently date-visible for each leg?',
  'parameter_order': ['aircraft_id', 'flight_departure_date'],
  'order_by': ['segment_id ASC',
               'row_kind DESC',
               'leg_order ASC NULLS LAST',
               'flight_id ASC',
               'anomaly_code ASC NULLS LAST'],
  'result_sets': [{'result_set_id': 'Q08-CANONICAL',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1001, 'flight_departure_date': '2026-08-31'},
                   'expected_status': 'OK',
                   'expected_rows': 3},
                  {'result_set_id': 'Q08-ANOMALIES',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1099, 'flight_departure_date': '2026-08-31'},
                   'expected_status': 'OK',
                   'expected_rows': 11},
                  {'result_set_id': 'Q08-NOT-FOUND',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1999, 'flight_departure_date': '2026-08-31'},
                   'expected_status': 'NOT_FOUND',
                   'expected_rows': 0},
                  {'result_set_id': 'Q08-ENRICHED-ROTATION',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1072, 'flight_departure_date': '2027-06-08'},
                   'expected_status': 'OK',
                   'expected_rows': 5},
                  {'result_set_id': 'Q08-ENRICHED-ANOMALIES',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1035, 'flight_departure_date': '2027-07-06'},
                   'expected_status': 'OK',
                   'expected_rows': 11},
                  {'result_set_id': 'Q08-ENRICHED-CLEAN',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1330, 'flight_departure_date': '2027-06-09'},
                   'expected_status': 'OK',
                   'expected_rows': 4}]},
 {'question_id': 'Q06',
  'catalog_id': 'market_latest_vs_seven_days',
  'module': 'uc2',
  'heading': 'Q06 - Compare market entries and exits seven days apart',
  'business_question': 'For one explicit carrier role, which exact resolved airline/route '
                       'markets entered or exited between an exact latest complete snapshot and '
                       'the snapshot seven days earlier?',
  'parameter_order': ['latest_knowledge_date', 'comparison_knowledge_date', 'carrier_role'],
  'order_by': ['change_kind ASC', 'airline_id ASC', 'route_id ASC'],
  'result_sets': [{'result_set_id': 'Q06-CANONICAL',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'latest_knowledge_date': '2026-08-31',
                                  'comparison_knowledge_date': '2026-08-24',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'OK',
                   'expected_rows': 2},
                  {'result_set_id': 'Q06-INCOMPLETE-ENDPOINT',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'latest_knowledge_date': '2026-10-26',
                                  'comparison_knowledge_date': '2026-10-19',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'ENDPOINT_INCOMPLETE',
                   'expected_rows': 0},
                  {'result_set_id': 'Q06-MISSING-CARRIER-ROLE',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'latest_knowledge_date': '2026-08-31',
                                  'comparison_knowledge_date': '2026-08-24',
                                  'carrier_role': None},
                   'expected_status': 'PARAMETER_ERROR',
                   'expected_rows': 0},
                  {'result_set_id': 'Q06-INVALID-DATE',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'latest_knowledge_date': '2026-02-30',
                                  'comparison_knowledge_date': '2026-02-23',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'PARAMETER_ERROR',
                   'expected_rows': 0},
                  {'result_set_id': 'Q06-ENRICHED-MARKETING',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'latest_knowledge_date': '2027-06-28',
                                  'comparison_knowledge_date': '2027-06-21',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'OK',
                   'expected_rows': 7},
                  {'result_set_id': 'Q06-ENRICHED-OPERATING',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'latest_knowledge_date': '2027-06-28',
                                  'comparison_knowledge_date': '2027-06-21',
                                  'carrier_role': 'operating'},
                   'expected_status': 'OK',
                   'expected_rows': 5}]},
 {'question_id': 'Q07',
  'catalog_id': 'route_capacity_two_clocks',
  'module': 'uc2',
  'heading': 'Q07 - Compute route frequency and cabin capacity with both clocks',
  'business_question': 'At an explicit knowledge date and operating date, what weekly route '
                       'frequency and cabin capacity are visible for an explicit marketing or '
                       'operating carrier role?',
  'parameter_order': ['knowledge_date', 'operating_date', 'carrier_role'],
  'order_by': ['result_status ASC', 'airline_id ASC', 'route_id ASC'],
  'result_sets': [{'result_set_id': 'Q07-MARKETING',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'knowledge_date': '2026-08-31',
                                  'operating_date': '2026-09-07',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'OK',
                   'expected_rows': 3},
                  {'result_set_id': 'Q07-OPERATING',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'knowledge_date': '2026-08-31',
                                  'operating_date': '2026-09-07',
                                  'carrier_role': 'operating'},
                   'expected_status': 'OK',
                   'expected_rows': 2},
                  {'result_set_id': 'Q07-KNOWLEDGE-END-EMPTY',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'knowledge_date': '2026-09-07',
                                  'operating_date': '2026-09-07',
                                  'carrier_role': 'operating'},
                   'expected_status': 'OK',
                   'expected_rows': 0},
                  {'result_set_id': 'Q07-MISSING-KNOWLEDGE-DATE',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'knowledge_date': None,
                                  'operating_date': '2026-09-07',
                                  'carrier_role': 'operating'},
                   'expected_status': 'PARAMETER_ERROR',
                   'expected_rows': 0},
                  {'result_set_id': 'Q07-MISSING-OPERATING-DATE',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'knowledge_date': '2026-08-31',
                                  'operating_date': None,
                                  'carrier_role': 'operating'},
                   'expected_status': 'PARAMETER_ERROR',
                   'expected_rows': 0},
                  {'result_set_id': 'Q07-MISSING-CARRIER-ROLE',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'knowledge_date': '2026-08-31',
                                  'operating_date': '2026-09-07',
                                  'carrier_role': None},
                   'expected_status': 'PARAMETER_ERROR',
                   'expected_rows': 0},
                  {'result_set_id': 'Q07-ENRICHED-KNOWLEDGE-LATE',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'knowledge_date': '2027-06-28',
                                  'operating_date': '2027-07-05',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'OK',
                   'expected_rows': 30},
                  {'result_set_id': 'Q07-ENRICHED-KNOWLEDGE-EARLY',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'knowledge_date': '2027-06-21',
                                  'operating_date': '2027-07-05',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'OK',
                   'expected_rows': 30},
                  {'result_set_id': 'Q07-ENRICHED-OPERATING-SHIFT',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'knowledge_date': '2027-06-28',
                                  'operating_date': '2027-07-03',
                                  'carrier_role': 'marketing'},
                   'expected_status': 'OK',
                   'expected_rows': 30},
                  {'result_set_id': 'Q07-ENRICHED-ROLE',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'knowledge_date': '2027-06-28',
                                  'operating_date': '2027-07-05',
                                  'carrier_role': 'operating'},
                   'expected_status': 'OK',
                   'expected_rows': 18}]},
 {'question_id': 'Q05',
  'catalog_id': 'schedule_four_week_changes',
  'module': 'uc2',
  'heading': 'Q05 - Classify four weeks of schedule changes',
  'business_question': 'Across five complete weekly snapshots (four comparisons), which exact '
                       'schedule keys were added, removed, or modified, and which key-shift '
                       'amendment relationships are unique candidates, ambiguous groups, or '
                       'unpaired evidence?',
  'parameter_order': ['start_knowledge_date', 'end_knowledge_date', 'cadence_days'],
  'order_by': ['comparison_date ASC',
               'Q05_event_class rank ASC',
               'event_id ASC',
               'member_side ASC NULLS LAST',
               'member_schedule_key ASC NULLS LAST'],
  'result_sets': [{'result_set_id': 'Q05-CANONICAL',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'start_knowledge_date': '2026-08-03',
                                  'end_knowledge_date': '2026-08-31',
                                  'cadence_days': 7},
                   'expected_status': 'OK',
                   'expected_rows': 35},
                  {'result_set_id': 'Q05-INELIGIBLE-ENDPOINT',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'start_knowledge_date': '2026-10-12',
                                  'end_knowledge_date': '2026-10-19',
                                  'cadence_days': 7},
                   'expected_status': 'ENDPOINT_MISSING',
                   'expected_rows': 0},
                  {'result_set_id': 'Q05-ENRICHED',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'start_knowledge_date': '2027-01-04',
                                  'end_knowledge_date': '2027-06-28',
                                  'cadence_days': 7},
                   'expected_status': 'OK',
                   'expected_rows': 392},
                  {'result_set_id': 'Q05-ENRICHED-GAP-PAIRS',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'start_knowledge_date': '2027-03-08',
                                  'end_knowledge_date': '2027-04-26',
                                  'cadence_days': 7},
                   'expected_status': 'OK',
                   'expected_rows': 87}]},
 {'question_id': 'Q01',
  'catalog_id': 'aircraft_as_of',
  'module': 'uc1',
  'heading': 'Q01 - Reconstruct an aircraft as of a date',
  'business_question': 'For one physical aircraft and calendar date, what type, reported engine, '
                       'lifecycle status, registration, and base were date-visible, and which '
                       'requested dimensions are unresolved?',
  'parameter_order': ['aircraft_id', 'as_of_date'],
  'order_by': ['aircraft_id ASC', 'as_of_date ASC'],
  'result_sets': [{'result_set_id': 'Q01-CANONICAL',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1001, 'as_of_date': '2026-08-31'},
                   'expected_status': 'OK',
                   'expected_rows': 1},
                  {'result_set_id': 'Q01-BEFORE-FIRST',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1004, 'as_of_date': '2019-06-30'},
                   'expected_status': 'OK',
                   'expected_rows': 1},
                  {'result_set_id': 'Q01-UNKNOWN-GAP',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1002, 'as_of_date': '2022-05-15'},
                   'expected_status': 'OK',
                   'expected_rows': 1},
                  {'result_set_id': 'Q01-EOL-BOUNDARY',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': 1002, 'as_of_date': '2024-07-01'},
                   'expected_status': 'OK',
                   'expected_rows': 1},
                  {'result_set_id': 'Q01-INVALID-AIRCRAFT-ID',
                   'manifest_version': '1.1.1',
                   'enriched': False,
                   'parameters': {'aircraft_id': -1, 'as_of_date': '2026-08-31'},
                   'expected_status': 'PARAMETER_ERROR',
                   'expected_rows': 0},
                  {'result_set_id': 'Q01-ENRICHED-MID-STORAGE',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1556, 'as_of_date': '2031-06-30'},
                   'expected_status': 'OK',
                   'expected_rows': 1},
                  {'result_set_id': 'Q01-ENRICHED-RETURN-DAY',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1860, 'as_of_date': '2027-08-03'},
                   'expected_status': 'OK',
                   'expected_rows': 1},
                  {'result_set_id': 'Q01-ENRICHED-CONVERSION-DAY',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1107, 'as_of_date': '2032-06-01'},
                   'expected_status': 'OK',
                   'expected_rows': 1},
                  {'result_set_id': 'Q01-ENRICHED-POST-EOL',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_id': 1000, 'as_of_date': '2032-06-30'},
                   'expected_status': 'OK',
                   'expected_rows': 1}]},
 {'question_id': 'Q02F',
  'catalog_id': 'fleet_storage_spell_distribution',
  'module': 'uc1',
  'heading': 'Q02F - Bucket every storage spell in the fleet by duration',
  'business_question': 'Across the whole fleet rather than one aircraft, how are In Service -> '
                       'Storage -> In Service spells distributed by duration, and how many '
                       'distinct aircraft does each duration bucket involve?',
  'parameter_order': ['aircraft_scope'],
  'order_by': ['bucket_order ASC'],
  'result_sets': [{'result_set_id': 'Q02F-FLEET-DISTRIBUTION',
                   'manifest_version': '1.2.0',
                   'enriched': True,
                   'parameters': {'aircraft_scope': 'FLEET'},
                   'expected_status': 'OK',
                   'expected_rows': 7}]}]

_ORDER_INDEX = {spec["question_id"]: i for i, spec in enumerate(QUESTION_SPECS)}


# --------------------------------------------------------------------- runtime bootstrap

#: The pinned SDK. Matches what the demo was built and measured against; the runner does not
#: upgrade an environment that already has a working ``relationalai``.
RELATIONALAI_REQUIREMENT = "relationalai==1.20.1"

#: Where a narrowly pinned protobuf goes if - and only if - the runtime's own copy turns out to
#: be incompatible. Its own directory, forced to the front of ``sys.path``, so the ~100 other
#: preinstalled packages in a Snowflake container runtime are left alone.
_LIB_DIR = "/tmp/aviation_runner_libs"


def _in_snowflake() -> bool:
    """True when a Snowpark session already exists - Workspace, notebook or stored procedure."""
    try:
        from snowflake.snowpark.context import get_active_session

        get_active_session()
        return True
    except Exception:
        return False


def _pip(*arguments: str) -> bool:
    """``sys.executable -m pip install`` with the given arguments. Never raises.

    A ``.py`` file gets no IPython magics, so the notebook's ``!pip`` line does not exist here
    and there is no dependency scanner reading this file either. ``subprocess`` is the only
    route, and it is the one the Workspace demonstrably supports.
    """
    import subprocess

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", *arguments],
            capture_output=True,
            text=True,
            timeout=900,
        )
    except Exception as exc:  # noqa: BLE001 - reported, never fatal on its own
        print(f"  pip is not usable in this runtime: {type(exc).__name__}: {exc}")
        return False
    if completed.returncode != 0:
        print(f"  pip install {' '.join(arguments)} failed:\n{completed.stderr.strip()[:2000]}")
        return False
    return True


def _forget(*prefixes: str) -> None:
    """Drop already-imported modules so the next import re-resolves against the new path."""
    for name in [
        m for m in list(sys.modules)
        if any(m == p or m.startswith(p + ".") for p in prefixes)
    ]:
        del sys.modules[name]


def _check_protobuf() -> None:
    """Prove protobuf works with RelationalAI's generated code *before* the first query.

    Two opposite failures, and which one you get depends entirely on the runtime:

    * **Too old.** ``google.protobuf.runtime_version`` arrived in protobuf 5.27, and the legacy
      Snowflake notebook container shipped something older. ``pip install relationalai`` does
      not repair it, because pip sees a protobuf on the path and calls the requirement
      satisfied while ``google.protobuf`` keeps resolving out of the *system* interpreter's
      site-packages.
    * **Too new.** The Snowflake Container Runtime that backs Workspaces ships protobuf 6.x,
      while ``lqp`` - RelationalAI's query protocol - carries gencode built against 5.28 and
      pins ``protobuf<6``.

    Either way RelationalAI reaches protobuf *lazily*, inside the query executor, so an
    unrepaired mismatch does not surface when the ontology loads. It surfaces on the first
    query, several minutes in, which is why this probe imports ``lqp``'s generated module here
    rather than waiting to find out. If the runtime is already consistent this function does
    nothing at all.
    """
    def probe() -> str | None:
        try:
            from google.protobuf import runtime_version  # noqa: F401
            import lqp.proto.v1.logic_pb2  # noqa: F401
        except Exception as exc:  # noqa: BLE001 - the message is the diagnosis
            return f"{type(exc).__name__}: {exc}"
        return None

    problem = probe()
    if problem is None:
        return

    import google.protobuf

    print(f"  protobuf {google.protobuf.__version__} is not usable with lqp: {problem}")

    # Cheapest repair first: protobuf's own documented escape hatch for a runtime that is newer
    # than the gencode it is asked to load.
    import os

    os.environ["TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK"] = "true"
    _forget("google", "lqp")
    if probe() is None:
        print("  repaired with TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK")
        return

    print(f"  installing a private protobuf into {_LIB_DIR}")
    if _pip("--upgrade", "--target", _LIB_DIR, "protobuf>=5.29,<6"):
        if _LIB_DIR not in sys.path:
            sys.path.insert(0, _LIB_DIR)
        _forget("google", "lqp")
        if probe() is None:
            print("  repaired with a pinned protobuf on the front of sys.path")
            return

    raise RuntimeError(
        "protobuf in this runtime is not compatible with RelationalAI's lqp gencode and could "
        "not be repaired from inside the process. Install 'protobuf>=5.29,<6' into the "
        "environment that executes this file - in a Snowsight Workspace, from the Workspace "
        "terminal - and run it again.\n"
        f"  last error: {probe()}"
    )


def ensure_runtime() -> None:
    """Make ``relationalai``, ``pandas`` and a working ``protobuf`` importable, or say why not.

    ``relationalai`` is PyPI-only; it is not in Snowflake's Anaconda channel. So in a Snowsight
    Workspace the notebook service that executes this file needs one of two things attached
    under **Edit service**, and there is no third option worth pretending about:

    * the Snowflake-managed PyPI artifact repository
      ``snowflake.snowpark.pypi_shared_repository`` (no egress needed; the ``PUBLIC`` role
      normally has it), or
    * an external access integration with PyPI egress - this account has one named
      ``PYPI_ACCESS``.

    Note the two are mutually exclusive: selecting an artifact repository disables installs
    through external access integrations. Note also that a Workspace's installed packages do
    not survive the weekend maintenance restart, so this function installing something is
    normal, not a symptom.
    """
    missing = []
    for module, requirement in (("pandas", "pandas"), ("relationalai", RELATIONALAI_REQUIREMENT)):
        try:
            __import__(module)
        except ImportError:
            missing.append(requirement)

    if missing:
        print(f"  not importable: {', '.join(missing)} - installing")
        if not _pip(*missing) or not _pip("protobuf>=5.29,<6"):
            raise RuntimeError(
                "This file needs " + ", ".join(missing) + ", and pip could not supply them.\n"
                "  * Snowsight Workspace: attach snowflake.snowpark.pypi_shared_repository (or "
                "the PYPI_ACCESS external access integration) to the notebook service under "
                "Edit service, then re-run. You can also install it once from the Workspace "
                "terminal: pip install " + RELATIONALAI_REQUIREMENT + "\n"
                "  * locally: .venv/bin/python -m pip install " + RELATIONALAI_REQUIREMENT
            )
        _forget("relationalai", "pandas", "lqp", "google")

    _check_protobuf()

    import google.protobuf
    import pandas
    import relationalai

    print(f"  relationalai {getattr(relationalai, '__version__', '?')}"
          f"   pandas {pandas.__version__}   protobuf {google.protobuf.__version__}")
    print(f"  python {sys.version.split()[0]}"
          f"   runtime: {'Snowflake, active Snowpark session' if _in_snowflake() else 'local'}")


# --------------------------------------------------------------------- embedded modules

#: A directory that does not have to exist. ``uc1`` and ``uc2`` compute a ``REPO_ROOT`` from
#: ``__file__`` at import time to locate ``EXPECTED_ANSWERS.yaml``; the manifest is never read
#: by any code path this runner takes, but the attribute has to be there for the import to
#: succeed. Three path components so ``Path(__file__).resolve().parents[2]`` resolves.
_FAKE_ROOT = "/tmp/aviation_runner_src/rai_code/queries"

_MODULES: dict[str, types.ModuleType] = {}


def _exec_module(name: str, source: str, filename: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = filename
    module.__package__ = ""
    sys.modules[name] = module
    exec(compile(source, filename, "exec"), module.__dict__)
    return module


def load_modules() -> dict[str, types.ModuleType]:
    """Materialise the ontology and the three query modules from the embedded sources.

    Four separate module namespaces rather than one flat concatenation, because ``uc1``, ``uc2``
    and ``rotation`` each define ``warm_model``, ``main``, ``REPO_ROOT`` and ``_records``, and
    ``uc1._records(df, columns)`` and ``uc2._records(df)`` do not take the same arguments.
    Flattening them would silently keep whichever came last.

    The ontology is registered under ``aviation_model`` *and*
    ``aviation_model.computed_schedule`` because the query modules were written against the
    package and ``uc2`` reaches for that one submodule. Both names are aliases of the same
    module object, not copies: there is exactly one ``Model`` in the interpreter, which matters
    because a second one makes the free ``distinct(...)`` raise ``[Ambiguous model]``.
    """
    if _MODULES:
        return _MODULES

    started = time.time()
    ontology = _exec_module("aviation_temporal", _SRC_AVIATION_MODEL, "aviation_temporal.py")
    sys.modules["aviation_model"] = ontology
    sys.modules["aviation_model.computed_schedule"] = ontology
    ontology.computed_schedule = ontology

    _MODULES["am"] = ontology
    for name, source in (
        ("uc1", _SRC_UC1),
        ("uc2", _SRC_UC2),
        ("rotation", _SRC_ROTATION),
    ):
        _MODULES[name] = _exec_module(name, source, f"{_FAKE_ROOT}/{name}.py")

    print(f"  ontology and query modules loaded in {time.time() - started:.1f}s")
    print(f"  reasoner: {ontology.LOGIC_REASONER}   database: {ontology.DB}")
    return _MODULES


# ------------------------------------------------------------------------- invocation

def _invoke(spec: dict, parameters: dict) -> tuple[str, str | None, "object"]:
    """Run one parameter set. Returns ``(invocation_status, error_code, DataFrame)``.

    No query function is named here. Each module already publishes the mapping from a question
    id to its callable and its declared parameter order, and this dispatches through those, so
    a renamed function or a changed signature is a regenerate rather than an edit.
    """
    mods = load_modules()
    question_id = spec["question_id"]
    module = _MODULES[spec["module"]]

    if spec["module"] == "uc1":
        entry = module.CATALOG[question_id]
        kwargs = {name: parameters[name] for name in entry["parameters"] if name in parameters}
        try:
            return "OK", None, entry["callable"](**kwargs)
        except module.QueryParameterError as exc:
            import pandas as pd

            return "PARAMETER_ERROR", exc.error_code, pd.DataFrame(columns=list(entry["columns"]))

    if spec["module"] == "uc2":
        return module.invoke_result_set(question_id, {"parameters": parameters})

    args = [parameters.get(name) for name in spec["parameter_order"]]
    outcome = module.invoke(*args, am=mods["am"])
    return outcome.invocation_status, outcome.error_code, outcome.rows


# ---------------------------------------------------------------------------- printing

_RULE = "=" * 100


def _wrap(text: str, width: int = 96, indent: str = "  ") -> str:
    import textwrap

    return "\n".join(textwrap.wrap(text, width=width, initial_indent=indent,
                                   subsequent_indent=indent)) if text else ""


def _format_frame(frame) -> str:
    """The result rows as a plain fixed-width table, with an honest truncation note."""
    import pandas as pd

    if frame is None or len(frame) == 0:
        return "  (no rows)"
    shown = frame if MAX_DISPLAY_ROWS is None else frame.head(MAX_DISPLAY_ROWS)
    with pd.option_context(
        "display.max_columns", None,
        "display.width", 10_000,
        "display.max_colwidth", MAX_COLUMN_WIDTH,
        "display.show_dimensions", False,
    ):
        body = shown.to_string(index=False)
    text = "\n".join("  " + line for line in body.splitlines())
    hidden = len(frame) - len(shown)
    if hidden:
        text += f"\n  ... {hidden} more rows (set MAX_DISPLAY_ROWS = None to print them all)"
    return text


def _print_header(spec: dict) -> None:
    print()
    print(_RULE)
    print(spec["heading"])
    print(_RULE)
    if spec["business_question"]:
        print(_wrap(spec["business_question"]))
    print(f"  catalog id: {spec['catalog_id']}   order by: {', '.join(spec['order_by']) or '-'}")


# ------------------------------------------------------------------------------- run

def _selected(questions, result_sets, include_frozen) -> list[tuple[dict, dict]]:
    questions = questions if questions is not None else QUESTIONS
    result_sets = result_sets if result_sets is not None else RESULT_SETS
    include_frozen = INCLUDE_FROZEN if include_frozen is None else include_frozen

    if questions is not None:
        wanted = {q.upper() for q in questions}
        unknown = wanted - {spec["question_id"] for spec in QUESTION_SPECS}
        if unknown:
            raise SystemExit(
                f"unknown question id(s) {sorted(unknown)}; "
                f"known: {[spec['question_id'] for spec in QUESTION_SPECS]}"
            )
    else:
        wanted = None

    out: list[tuple[dict, dict]] = []
    for spec in QUESTION_SPECS:
        if wanted is not None and spec["question_id"] not in wanted:
            continue
        for result_set in spec["result_sets"]:
            if result_sets is not None:
                if result_set["result_set_id"] not in result_sets:
                    continue
            elif not include_frozen and not result_set["enriched"]:
                continue
            out.append((spec, result_set))
    return out


def run(questions=None, result_sets=None, include_frozen=None) -> int:
    """Run the selected questions against the live model and print every answer.

    Returns the number of parameter sets that failed, so a caller can branch on it. A failure
    is caught, recorded and printed in the summary; it never stops the run, because a script
    that dies on question three is no use in front of an audience.
    """
    selection = _selected(questions, result_sets, include_frozen)
    if not selection:
        print("nothing selected")
        return 0

    groups = sorted({spec["question_id"] for spec, _ in selection}, key=_ORDER_INDEX.get)
    print(_RULE)
    print("Aviation temporal demo - all questions, no charts")
    print(_RULE)
    print(f"  {len(groups)} question group(s), {len(selection)} parameter set(s): "
          f"{', '.join(groups)}")

    total_started = time.time()
    print("\n[1/3] runtime")
    ensure_runtime()

    print("\n[2/3] ontology")
    mods = load_modules()

    print("\n[3/3] model sync (roughly 150s on a READY engine, once for the whole run)")
    sync_started = time.time()
    mods["uc1"].warm_model()
    print(f"  warm in {time.time() - sync_started:.1f}s")

    results: list[dict] = []
    for spec, result_set in selection:
        _print_header(spec)
        parameters = result_set["parameters"]
        rendered = ", ".join(f"{k}={v!r}" for k, v in parameters.items()) or "(none)"
        print(f"  parameter set: {result_set['result_set_id']} "
              f"(manifest v{result_set['manifest_version']})")
        print(f"  parameters: {rendered}")

        started = time.time()
        try:
            status, error_code, frame = _invoke(spec, parameters)
            elapsed = time.time() - started
            rows = 0 if frame is None else len(frame)
            expected = result_set["expected_rows"]
            # The frozen cardinality is printed alongside the live one because it costs nothing
            # and it is the difference between "the query ran" and "the query is right". It is
            # a sanity light, not a verdict: tests/ owns the row-by-row comparison.
            agrees = "" if expected is None else (
                "   (manifest expects the same)" if rows == expected
                else f"   *** manifest expects {expected} ***"
            )
            print(f"  status: {status}{'' if error_code is None else ' / ' + str(error_code)}"
                  f"   rows: {rows}   {elapsed:.1f}s{agrees}")
            print(_format_frame(frame))
            results.append({
                "question_id": spec["question_id"],
                "result_set_id": result_set["result_set_id"],
                "rows": rows,
                "expected": expected,
                "seconds": elapsed,
                "outcome": "OK",
                "detail": status if status != "OK" else "",
            })
        except Exception as exc:  # noqa: BLE001 - reported in the summary, never fatal
            elapsed = time.time() - started
            print(f"  FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=6, file=sys.stdout)
            results.append({
                "question_id": spec["question_id"],
                "result_set_id": result_set["result_set_id"],
                "rows": 0,
                "expected": result_set["expected_rows"],
                "seconds": elapsed,
                "outcome": "FAILED",
                "detail": f"{type(exc).__name__}: {exc}"[:160],
            })

    _print_summary(results, time.time() - total_started)
    return sum(1 for r in results if r["outcome"] == "FAILED")


def _print_summary(results: list[dict], total: float) -> None:
    width = max([len(r["result_set_id"]) for r in results] + [len("parameter set")])
    rule = "  " + "-" * (8 + 1 + width + 1 + 7 + 1 + 8 + 1 + 9 + 2 + 8)
    print()
    print(_RULE)
    print("SUMMARY")
    print(_RULE)
    print(f"  {'question':<8} {'parameter set':<{width}} {'rows':>7} {'frozen':>8} "
          f"{'seconds':>9}  status")
    print(rule)
    for r in results:
        expected = "-" if r["expected"] is None else str(r["expected"])
        flag = "" if r["expected"] in (None, r["rows"]) or r["outcome"] != "OK" else "  (differs)"
        print(f"  {r['question_id']:<8} {r['result_set_id']:<{width}} {r['rows']:>7} "
              f"{expected:>8} {r['seconds']:>9.1f}  {r['outcome']}{flag}"
              f"{'' if not r['detail'] else '  ' + r['detail']}")
    failed = [r for r in results if r["outcome"] == "FAILED"]
    differs = [r for r in results
               if r["outcome"] == "OK" and r["expected"] not in (None, r["rows"])]
    print(rule)
    print(f"  {len(results) - len(failed)}/{len(results)} parameter sets returned, "
          f"{sum(r['rows'] for r in results)} rows total, {total / 60:.1f} min wall clock")
    if failed:
        print(f"  {len(failed)} FAILED: {', '.join(r['result_set_id'] for r in failed)}")
    if differs:
        print(f"  {len(differs)} returned a different row count from the frozen manifest: "
              f"{', '.join(r['result_set_id'] for r in differs)}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    include_frozen = None
    if "--all-parameter-sets" in argv:
        argv.remove("--all-parameter-sets")
        include_frozen = True
    return run(questions=argv or None, include_frozen=include_frozen)


# ============================================================================
# Embedded sources. Byte-for-byte copies, exec'd into their own module namespaces
# by load_modules() above. Everything below this line is generated; nothing below
# this line should ever be edited in place.
# ============================================================================

_SRC_AVIATION_MODEL = r'''"""aviation_temporal.py - the standalone RelationalAI ontology for the aviation temporal demo.

DO NOT EDIT. GENERATED from ``rai_code/aviation_model/`` by
``python -m aviation_model._gen_standalone``. Edit the package and regenerate; a hand edit here
silently forks the ontology, and ``tests/test_model.py::test_standalone_file_matches_the_package``
will fail on the next run.

This is the artifact you upload to a Snowflake stage and import from a Snowsight notebook or a
Workspace. It is self-contained: no relative imports, no ``raiconfig.yaml``, and no credentials.
``_build_config()`` detects the runtime - ``ConfigFromActiveSession`` when a Snowpark session
exists (Snowsight notebook, Workspace, stored procedure), ``create_config()`` otherwise (local
Python, auto-discovering ``~/.snowflake``). Both branches set strict mode
(``implicit_properties: False``) and pin the warm ``aviation_temporal_logic_s`` reasoner, which
is the difference between a 2.5-6s warm query and a 631s cold start.

Reading order, and it is also the load order: sentinels and tokens; the runtime config; the one
``Model``; the ``model.Table()`` bindings with their explicit ``schema=`` dicts; the reference,
aircraft, schedule and flight concepts; the shared temporal predicates; and finally the derived
rule layer, which is where the demo's actual content lives.
"""

from __future__ import annotations

import json
import datetime as dt

from pathlib import Path
from typing import Any, Iterable, Mapping

from relationalai.semantics import Bool, Date, DateTime, Float, Integer, Model, Number, String, inspect
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.constraints import unique
from relationalai.semantics.std.datetime import date as std_date


# ================================================================================================
# constants.py
# ================================================================================================
# constants.py - sentinels, tokens and the one database path string.
#
# Nothing here touches the network. ``DB`` is the single string MODEL-02's standalone
# generation has to rewrite, which is why every ``model.Table()`` path in ``sources.py``
# interpolates it rather than spelling the database out.



# --- Snowflake location -----------------------------------------------------------

DB = "PK_AVIATION_TEMPORAL"
SOURCE_SCHEMA = "SOURCE"
MODEL_INPUT_SCHEMA = "MODEL_INPUT"

MODEL_NAME = "aviation_temporal"
LOGIC_REASONER = "aviation_temporal_logic_s"

# --- Interval sentinels -----------------------------------------------------------
#
# BRIEF.md non-negotiable: source ``9999-12-31`` (unknown future) and model ``9999-01-01``
# (open interval) are different facts and never collapse. DATA-04 normalises the source
# sentinel away before RAI sees it, replacing it with NULL plus a companion
# ``*_IS_UNKNOWN_FUTURE`` boolean, so ``SOURCE_UNKNOWN_FUTURE`` must never appear in any
# bound date column. ``computed_aircraft.SentinelLeak`` is the zero-count guard that proves it.

MODEL_OPEN_INTERVAL = dt.date(9999, 1, 1)
SOURCE_UNKNOWN_FUTURE = dt.date(9999, 12, 31)

# --- Dimension discriminators (DV-04 / DV-05 ``dimension`` column) -----------------

DIM_AIRCRAFT_STATE = "aircraft_state"
DIM_AIRCRAFT_TYPE = "aircraft_type"
DIM_ENGINE_TYPE = "engine_type"
DIM_AIRCRAFT_STATUS = "aircraft_status"

DIMENSIONS = (
    DIM_AIRCRAFT_STATE,
    DIM_AIRCRAFT_TYPE,
    DIM_ENGINE_TYPE,
    DIM_AIRCRAFT_STATUS,
)

# --- DV-33 dimension query status -------------------------------------------------
#
# Four mutually exclusive outcomes, in the strict order SOURCE_CONTRACT.md fixes. Two are
# the presence of a covering daily assignment (``OK``, ``UNKNOWN_STATE``) and are carried on
# the row by DATA-04; two are the absence of one (``NO_RECORDED_STATE``, ``OUTSIDE_EXISTENCE``)
# and can only be decided against a date, so they are produced by ``temporal.dv33_branches``.

DV33_OK = "OK"
DV33_UNKNOWN_STATE = "UNKNOWN_STATE"
DV33_NO_RECORDED_STATE = "NO_RECORDED_STATE"
DV33_OUTSIDE_EXISTENCE = "OUTSIDE_EXISTENCE"

# --- Carrier roles (DV-29) --------------------------------------------------------

CARRIER_ROLE_MARKETING = "marketing"
CARRIER_ROLE_OPERATING = "operating"
CARRIER_ROLES = (CARRIER_ROLE_MARKETING, CARRIER_ROLE_OPERATING)

# --- Status tokens used by model rules --------------------------------------------
#
# Exact raw AH-09 values. NEO4J_RAI_MAPPING.md forbids trimming or case folding, so these
# are the literal strings and not a normalised form.

STATUS_IN_SERVICE = "In Service"
STATUS_STORAGE = "Storage"

# --- Resolution / physical-service tokens -----------------------------------------

RESOLUTION_EXACT = "EXACT"
PHYSICAL_SERVICE_COUNTED = "COUNTED"
PHYSICAL_SERVICE_UNRESOLVED = "UNRESOLVED_PHYSICAL_SERVICE"

# --- Rotation ---------------------------------------------------------------------

ROTATION_NO_TARGET_TOKEN = "NO_TARGET"

# --- ISO weekday numbering (1 = Monday), paired with the seven SS-14..SS-20 flags ---

WEEKDAY_FLAG_COLUMNS = (
    (1, "is_operating_monday"),
    (2, "is_operating_tuesday"),
    (3, "is_operating_wednesday"),
    (4, "is_operating_thursday"),
    (5, "is_operating_friday"),
    (6, "is_operating_saturday"),
    (7, "is_operating_sunday"),
)


# ================================================================================================
# config.py
# ================================================================================================
# config.py - one ``_build_config()`` that works locally and inside Snowflake.
#
# Two runtimes, one function:
#
# * **Local Python.** ``create_config(...)`` merges the programmatic keys over the
#   auto-discovered ``~/.snowflake/connections.toml`` profile. PROBE-01 confirmed the merge
#   works without passing ``connections`` explicitly, even though the docstring implies it is
#   required.
# * **Snowsight / Workspace / stored procedure.** There is no discoverable ``raiconfig.yaml``,
#   so ``ConfigFromActiveSession`` is used when a Snowpark session exists.
#
# Both branches set the same two things, and both matter:
#
# * ``model.implicit_properties = False`` (strict mode). The field defaults to ``True``, so it
#   has to be set explicitly. Strict mode does *not* protect a ``model.Table()`` from a column
#   typo (PROBE U-01) - ``sources.py``'s explicit ``schema=`` dicts do that - but it does stop
#   an undeclared Concept property from being invented silently.
# * ``reasoners.logic.name = "aviation_temporal_logic_s"``. Pinning the named engine is the
#   difference between a 2.5-6s warm query and a 631s cold start (PROBE U-12). Note the ``_s``
#   suffix: SDK 1.20.1 refuses ``HIGHMEM_X64_XS`` for Logic reasoners, so the locked ``_xs``
#   name in BRIEF.md does not exist and must not be used.






def _active_snowpark_session() -> Any | None:
    """Return the ambient Snowpark session, or ``None`` when running locally."""
    try:
        from snowflake.snowpark.context import get_active_session
    except Exception:
        return None
    try:
        return get_active_session()
    except Exception:
        return None


def in_snowflake_runtime() -> bool:
    """True when an ambient Snowpark session exists (Snowsight, Workspace, sproc)."""
    return _active_snowpark_session() is not None


def _build_config(**overrides: Any):
    """Strict-mode config pinned to the warm logic reasoner, for either runtime."""
    from relationalai.config.config import ConfigFromActiveSession, create_config

    settings: dict[str, Any] = {
        "model": {"implicit_properties": False},
        "reasoners": {"logic": {"name": LOGIC_REASONER}},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key] = {**settings[key], **value}
        else:
            settings[key] = value

    session = _active_snowpark_session()
    if session is not None:
        return ConfigFromActiveSession(**settings)
    return create_config(**settings)


# ================================================================================================
# model.py
# ================================================================================================
# model.py - the single ``Model`` instance.
#
# Kept in its own module so that ``sources.py`` and every ``core_*`` / ``computed_*`` module can
# import it without a circular import, and so there is exactly one ``Model`` per process. The
# free ``distinct(...)`` raises ``[Ambiguous model]`` the moment a second ``Model`` exists in the
# same interpreter (PROBE N-02), so a second instance is never created here.




model = Model(MODEL_NAME, config=_build_config())


# ================================================================================================
# _binding.py
# ================================================================================================
# _binding.py - the two helpers every ``core_*`` module uses to lift a table onto a Concept.
#
# Why helpers rather than 700 hand-written lines. The bound tables carry 748 contracted columns
# and ``SOURCE_CONTRACT.md`` requires every modelled field to trace to a documented source
# column. Writing each ``Property`` by hand would be 700 chances to mistype a column name, and
# PROBE U-01 proved a mistyped column binds *silently* as an ``Any``-typed relation. Driving the
# declarations off ``sources.py``'s explicit ``schema=`` dict makes the typo structurally
# impossible: the only column names in the system come from ``INFORMATION_SCHEMA``.
#
# Two live findings shape the implementation.
#
# * **Batched ``define()`` preserves sparse facts.** ``ONTOLOGY_DESIGN.md`` R2 warns that all
#   columns passed to ``.new()`` in one call are required, so a null drops the row. That is true
#   of ``.new()`` and is why identity is minted separately. It is *not* true of several
#   ``entity.prop(column)`` statements batched into one ``define()``: measured live against
#   ``MODEL_INPUT.AIRCRAFT_ELIGIBLE`` (999 rows, ``AIRCRAFT_END_OF_LIFE_DATE`` non-null on
#   exactly one), the batched and the one-define-per-column forms both returned
#   ``rows=999 eol_nn=1``. Absence of a value stays absence of a fact, which is P0-02.8.
# * **One ``define()`` call site per concept.** PyRel warns after 50 ``define()`` calls from the
#   same bytecode offset. Batching keeps every concept to a single call from
#   ``bind_scalars``, so the whole model makes roughly forty rule-emitting calls in total.
#
# Identity properties are never re-declared here: ``identify_by`` creates them, and declaring a
# second ``Property`` for the same name is a duplicate. Every caller passes those column names in
# ``exclude``.






def scalar_properties(
    concept,
    schema: Mapping[str, Any],
    *,
    exclude: Iterable[str] = (),
    rename: Mapping[str, str] | None = None,
    reading: str = "has",
) -> dict[str, str]:
    """Declare one ``Property`` per source column and attach it to ``concept``.

    ``schema`` is the ``SCHEMA_*`` dict from ``sources.py``, so the column names and RAI types
    are the ones ``INFORMATION_SCHEMA`` reported. Returns the ``{attribute: column}`` map that
    :func:`bind_scalars` consumes.

    The anti-bundle rule holds: every scalar becomes its own ``Property``, never a multi-field
    ``Relationship``, so each one is independently filterable and aggregatable.
    """
    rename = dict(rename or {})
    skip = set(exclude)
    mapping: dict[str, str] = {}
    for column, rai_type in schema.items():
        if column in skip:
            continue
        attr = rename.get(column, column)
        prop = model.Property(f"{concept} {reading} {rai_type:{attr}}")
        setattr(concept, attr, prop)
        mapping[attr] = column
    return mapping


def bind_scalars(concept, table, key: Mapping[str, Any], mapping: Mapping[str, str]) -> None:
    """Bind every scalar in ``mapping`` from ``table`` in a single ``define()``.

    ``key`` is the ``Concept.lookup(...)`` keyword mapping that re-finds the entity minted by
    the caller's ``.new()``. ``lookup`` supersedes the deprecated ``filter_by`` used throughout
    ``ONTOLOGY_DESIGN.md``; a key that resolves to no entity yields no fact and no error, which
    is the quarantine semantics section 1.3 depends on and the reason ``inventory.py`` asserts
    a per-concept count against SQL.
    """
    entity = concept.lookup(**key)
    statements = [getattr(entity, attr)(getattr(table, column)) for attr, column in mapping.items()]
    model.define(entity, *statements)


# ================================================================================================
# sources.py
# ================================================================================================
# sources.py - every ``model.Table()`` binding, with an explicit ``schema=`` dict.
#
# GENERATED from ``PK_AVIATION_TEMPORAL.INFORMATION_SCHEMA.COLUMNS``, then checked in.
# Regenerate with ``python -m aviation_model._regen_sources``;
# ``tests/test_model.py::test_declared_types_match_information_schema`` re-derives the mapping
# live and fails on any drift.
#
# Three rules this file exists to enforce, all from ``build/design/PROBE_RESULTS.md``:
#
# * **R1 - an explicit ``schema=`` dict everywhere.** Strict mode gives *zero* typo protection
#   on a ``model.Table()`` (PROBE U-01): a misspelled column binds silently as an ``Any``-typed
#   relation and produces an empty or NaN result later. The dict is the only defence, and
#   ``inventory.py`` asserts that no discovered column is ``Any``.
# * **U-03 - the 26 Snowflake ``TIME`` columns are declared ``String``.** Discovered *or*
#   explicitly declared as ``DateTime`` they come back 100% NULL with no error. Declared
#   ``String`` the value is byte-identical to ``TO_VARCHAR(t, 'HH24:MI:SS.FF3')``, so every
#   time-of-day literal must be written ``'HH:MM:SS.mmm'``; ``'16:00:00'`` matches zero rows.
# * **U-02 - a wrong declared type is a silent all-NaN column, not a ``TyperError``.** Types are
#   therefore derived from ``INFORMATION_SCHEMA`` rather than eyeballed, and the integer mapping
#   mirrors the SDK's own CDC bucketing rather than the column's declared precision:
#   ``NUMBER(p,0)`` with ``p <= 18`` is ``Number.size(18, 0)`` and with ``19 <= p <= 38`` is
#   ``Integer``. Declaring the faithful ``Number.size(19, 0)`` for a ``NUMBER(19,0)`` column
#   returned 600 rows and 0 non-null values, silently - see :func:`derive_type`. The MODEL-01
#   gate asserts per-column non-null counts against SQL, not just row counts, which is the only
#   check that catches it.
#
# D-0027 SUPERSEDES D-0019 here: the row-scoped ``CODE_RESOLUTION`` (784,140 rows),
# ``CODE_RESOLUTION_CANDIDATE`` (627,424) and ``CODE_RESOLUTION_INPUT`` (784,140) ARE now bound.
# D-0019 excluded them on a performance premise that measurement refuted: binding all three cost
# 0.18s on first query and no measurable warm delta. The distinct-code projection
# ``CODE_RESOLUTION_CODE`` (660 rows) is retained for link semantics, and every other
# MODEL_INPUT object already carries its own resolved target id plus resolution status. The
# timed experiment that settled it is recorded in ``build/task_reports/MODEL-01.json``; the
# tables stay materialized and reachable from SQL.




SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR = {
    "expected_publish_date": Date,
    "is_present": Bool,
    "is_complete": Bool,
    "source_lineage_id": String,
    "observed_row_count": Integer,
    "validation_status": String,
}

SRC_SCHEDULE_SNAPSHOT_CALENDAR = model.Table(f"{DB}.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR", schema=SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR)

SCHEMA_SRC_AIRCRAFT_CONFIGURATION = {
    "aircraft_configuration_id": Integer,
    "aircraft_family": String,
    "aircraft_type": String,
    "aircraft_series": String,
    "aircraft_subseries": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type": String,
    "engine_series": String,
    "engine_subseries": String,
    "engine_propulsion_type": String,
    "publish_date": Date,
}

SRC_AIRCRAFT_CONFIGURATION = model.Table(f"{DB}.SOURCE.AIRCRAFT_CONFIGURATION", schema=SCHEMA_SRC_AIRCRAFT_CONFIGURATION)

SCHEMA_MI_AIRCRAFT_ELIGIBLE = {
    "aircraft_id": Integer,
    "aircraft_serial_number": String,
    "aircraft_line_number": String,
    "aircraft_order_date": Date,
    "aircraft_order_date_is_unknown_future": Bool,
    "aircraft_build_date": Date,
    "aircraft_build_date_is_unknown_future": Bool,
    "aircraft_delivery_date": Date,
    "aircraft_delivery_date_is_unknown_future": Bool,
    "aircraft_roll_out_date": Date,
    "aircraft_roll_out_date_is_unknown_future": Bool,
    "aircraft_first_flight_date": Date,
    "aircraft_first_flight_date_is_unknown_future": Bool,
    "aircraft_start_of_life_date": Date,
    "aircraft_start_of_life_date_is_unknown_future": Bool,
    "aircraft_end_of_life_date": Date,
    "aircraft_end_of_life_date_is_unknown_future": Bool,
    "existence_from": Date,
    "existence_to": Date,
    "has_finite_end_of_life": Bool,
    "existence_from_basis": String,
    "aircraft_build_airport_code_iata": String,
    "aircraft_build_airport": String,
    "original_delivery_operator": String,
    "original_delivery_operator_category": String,
    "master_current_only_apu_type": String,
    "master_current_only_aircraft_width_m": Float,
    "master_current_only_operating_maximum_takeoff_weight_lb": Integer,
    "master_current_only_certified_maximum_takeoff_weight_lb": Integer,
    "not_for_use": Bool,
    "first_eligible_event_date": Date,
}

MI_AIRCRAFT_ELIGIBLE = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_ELIGIBLE", schema=SCHEMA_MI_AIRCRAFT_ELIGIBLE)

SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE = {
    "aircraft_history_id": Integer,
    "aircraft_id": Integer,
    "row_sequence_number": Integer,
    "event_sequence_number": Integer,
    "start_event_date": Date,
    "end_event_date": Date,
    "end_event_date_is_unknown_future": Bool,
    "is_current": Bool,
    "start_event": String,
    "start_aircraft_status": String,
    "end_event": String,
    "end_aircraft_status": String,
    "event_source": String,
    "aircraft_configuration_id": Integer,
    "aircraft_code_iata": String,
    "aircraft_code_icao": String,
    "aircraft_value_sub_series": String,
    "aircraft_registration_number": String,
    "aircraft_transponder_code": String,
    "aircraft_registration_country_code_iso": String,
    "aircraft_registration_region": String,
    "aircraft_cargo": String,
    "storage_location": String,
    "storage_airport_code_iata": String,
    "base_airport": String,
    "base_airport_code_iata": String,
    "base_city": String,
    "base_country": String,
    "apu_type": String,
    "aircraft_width_m": Float,
    "operating_maximum_takeoff_weight_lb": Integer,
    "certified_maximum_takeoff_weight_lb": Integer,
    "base_state": String,
    "base_region": String,
    "storage_location_type": String,
    "noise_certification": String,
    "has_winglets": Bool,
    "aircraft_registration_country": String,
    "transponder_miscode": Bool,
    "maximum_landing_weight_lb": Integer,
    "operating_empty_weight_lb": Integer,
    "not_for_use": Bool,
    "publish_date": Date,
    "publish_date_is_unknown_future": Bool,
    "existence_from": Date,
    "existence_to": Date,
    "event_order_rank": Number.size(18, 0),
    "configuration_resolved": Bool,
    "aircraft_family": String,
    "aircraft_type": String,
    "aircraft_series": String,
    "aircraft_subseries": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type": String,
    "engine_series": String,
    "engine_subseries": String,
    "engine_propulsion_type": String,
    "configuration_publish_date": Date,
    "type_resolution_status": String,
    "engine_resolution_status": String,
    "mixed_engine_set_complete": Bool,
    "would_be_lost_by_inner_join": Bool,
}

MI_AIRCRAFT_EVENT_ELIGIBLE = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE", schema=SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE)

SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE = {
    "quarantine_id": String,
    "source_object": String,
    "quarantine_reason": String,
    "raw_aircraft_history_id": Integer,
    "raw_aircraft_id": Integer,
    "raw_row_sequence_number": Integer,
    "raw_event_sequence_number": Integer,
    "raw_start_event_date": Date,
    "typed_normalized_row_hash": String,
    "quarantine_key_basis": String,
    "missing_required_fields": String,
    "occurrence_count": Number.size(18, 0),
}

MI_AIRCRAFT_EVENT_QUARANTINE = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_EVENT_QUARANTINE", schema=SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE)

SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT = {
    "audit_assignment_id": String,
    "dimension": String,
    "aircraft_id": Integer,
    "event_date": Date,
    "row_sequence_number": Integer,
    "event_sequence_number": Integer,
    "aircraft_history_id": Integer,
    "event_order_rank": Number.size(18, 0),
    "dimension_sequence": Number.size(18, 0),
    "is_final_relevant_observation_of_day": Bool,
    "watched_signature": String,
    "previous_watched_signature": String,
    "dimension_resolution_status": String,
    "end_event_date": Date,
    "end_event_date_is_unknown_future": Bool,
    "start_event": String,
    "event_source": String,
    "aircraft_configuration_id": Integer,
    "aircraft_registration_number": String,
    "aircraft_transponder_code": String,
    "aircraft_registration_country_code_iso": String,
    "aircraft_registration_region": String,
    "aircraft_cargo": String,
    "storage_location": String,
    "storage_airport_code_iata": String,
    "base_airport": String,
    "base_airport_code_iata": String,
    "base_city": String,
    "base_country": String,
    "apu_type": String,
    "aircraft_width_m": Float,
    "operating_maximum_takeoff_weight_lb": Integer,
    "certified_maximum_takeoff_weight_lb": Integer,
    "base_state": String,
    "base_region": String,
    "storage_location_type": String,
    "noise_certification": String,
    "has_winglets": Bool,
    "aircraft_registration_country": String,
    "transponder_miscode": Bool,
    "maximum_landing_weight_lb": Integer,
    "operating_empty_weight_lb": Integer,
    "aircraft_status_code": String,
    "aircraft_code_iata": String,
    "aircraft_code_icao": String,
    "aircraft_value_sub_series": String,
    "aircraft_type_subseries": String,
    "exact_aircraft_type_subseries": String,
    "aircraft_family": String,
    "aircraft_type_label": String,
    "aircraft_series": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_type_subseries": String,
    "exact_engine_type_subseries": String,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type_label": String,
    "engine_series": String,
    "engine_propulsion_type": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "mixed_engine_set_complete": Bool,
}

MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT", schema=SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT)

SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT = {
    "daily_assignment_id": String,
    "audit_assignment_id": String,
    "dimension": String,
    "aircraft_id": Integer,
    "valid_from": Date,
    "valid_to": Date,
    "next_assignment_date": Date,
    "existence_from": Date,
    "existence_to": Date,
    "valid_to_clipped_to_existence": Bool,
    "aircraft_history_id": Integer,
    "row_sequence_number": Integer,
    "event_sequence_number": Integer,
    "event_order_rank": Number.size(18, 0),
    "dimension_resolution_status": String,
    "dimension_query_status": String,
    "end_event_date": Date,
    "end_event_date_is_unknown_future": Bool,
    "end_event_date_disagrees_with_valid_to": Bool,
    "start_event": String,
    "event_source": String,
    "aircraft_configuration_id": Integer,
    "aircraft_registration_number": String,
    "aircraft_transponder_code": String,
    "aircraft_registration_country_code_iso": String,
    "aircraft_registration_region": String,
    "aircraft_cargo": String,
    "storage_location": String,
    "storage_airport_code_iata": String,
    "base_airport": String,
    "base_airport_code_iata": String,
    "base_city": String,
    "base_country": String,
    "apu_type": String,
    "aircraft_width_m": Float,
    "operating_maximum_takeoff_weight_lb": Integer,
    "certified_maximum_takeoff_weight_lb": Integer,
    "base_state": String,
    "base_region": String,
    "storage_location_type": String,
    "noise_certification": String,
    "has_winglets": Bool,
    "aircraft_registration_country": String,
    "transponder_miscode": Bool,
    "maximum_landing_weight_lb": Integer,
    "operating_empty_weight_lb": Integer,
    "aircraft_status_code": String,
    "aircraft_code_iata": String,
    "aircraft_code_icao": String,
    "aircraft_value_sub_series": String,
    "aircraft_type_subseries": String,
    "exact_aircraft_type_subseries": String,
    "aircraft_family": String,
    "aircraft_type_label": String,
    "aircraft_series": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_type_subseries": String,
    "exact_engine_type_subseries": String,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type_label": String,
    "engine_series": String,
    "engine_propulsion_type": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "mixed_engine_set_complete": Bool,
}

MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT", schema=SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT)

SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION = {
    "aircraft_subseries": String,
    "aircraft_family": String,
    "aircraft_type": String,
    "aircraft_series": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "definition_variant_count": Number.size(18, 0),
    "source_configuration_count": Number.size(18, 0),
    "definition_status": String,
}

MI_AIRCRAFT_TYPE_DEFINITION = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION", schema=SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION)

SCHEMA_MI_ENGINE_TYPE_DEFINITION = {
    "engine_subseries": String,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type": String,
    "engine_series": String,
    "engine_propulsion_type": String,
    "definition_variant_count": Number.size(18, 0),
    "source_configuration_count": Number.size(18, 0),
    "definition_status": String,
}

MI_ENGINE_TYPE_DEFINITION = model.Table(f"{DB}.MODEL_INPUT.ENGINE_TYPE_DEFINITION", schema=SCHEMA_MI_ENGINE_TYPE_DEFINITION)

SCHEMA_MI_AIRPORT_CURRENT = {
    "airport_id": String,
    "selected_effective_start_date": Date,
    "selected_effective_end_date": Date,
    "airport_code_iata": String,
    "airport_code_icao": String,
    "airport_name": String,
    "is_active": Bool,
    "is_current": Bool,
    "time_zone_name": String,
    "reference_period_count": Number.size(18, 0),
    "projection_rule": String,
}

MI_AIRPORT_CURRENT = model.Table(f"{DB}.MODEL_INPUT.AIRPORT_CURRENT", schema=SCHEMA_MI_AIRPORT_CURRENT)

SCHEMA_MI_AIRLINE_CURRENT = {
    "airline_id": String,
    "selected_effective_start_date": Date,
    "selected_effective_end_date": Date,
    "carrier_code_iata": String,
    "carrier_code_icao": String,
    "carrier_short_name": String,
    "carrier_full_name": String,
    "is_iata_controlled_duplicate": Bool,
    "is_active": Bool,
    "is_current": Bool,
    "reference_period_count": Number.size(18, 0),
    "projection_rule": String,
}

MI_AIRLINE_CURRENT = model.Table(f"{DB}.MODEL_INPUT.AIRLINE_CURRENT", schema=SCHEMA_MI_AIRLINE_CURRENT)

SCHEMA_MI_CODE_RESOLUTION_CODE = {
    "domain": String,
    "method": String,
    "raw_code": String,
    "candidate_count": Number.size(18, 0),
    "single_candidate_id": String,
    "resolution_status": String,
    "matched_code_systems": String,
}

MI_CODE_RESOLUTION_CODE = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_CODE", schema=SCHEMA_MI_CODE_RESOLUTION_CODE)

SCHEMA_MI_CODE_RESOLUTION_CODE_CANDIDATE = {
    "domain": String,
    "method": String,
    "raw_code": String,
    "candidate_id": String,
    "matched_code_systems": String,
}

MI_CODE_RESOLUTION_CODE_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE", schema=SCHEMA_MI_CODE_RESOLUTION_CODE_CANDIDATE)

SCHEMA_MI_CODE_RESOLUTION_INPUT = {
    "domain": String,
    "source_object": String,
    "source_row_token": String,
    "field_role": String,
    "raw_field_id": String,
    "raw_code": String,
    "method": String,
    "source_occurrence_count": Number.size(18, 0),
}

MI_CODE_RESOLUTION_INPUT = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_INPUT", schema=SCHEMA_MI_CODE_RESOLUTION_INPUT)

SCHEMA_MI_CODE_RESOLUTION = {
    "resolution_id": String,
    "domain": String,
    "source_object": String,
    "source_row_token": String,
    "field_role": String,
    "raw_field_id": String,
    "raw_code": String,
    "method": String,
    "source_occurrence_count": Number.size(18, 0),
    "candidate_count": Number.size(18, 0),
    "resolution_status": String,
    "resolved_identity_id": String,
    "matched_code_systems": String,
}

MI_CODE_RESOLUTION = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION", schema=SCHEMA_MI_CODE_RESOLUTION)

SCHEMA_MI_CODE_RESOLUTION_CANDIDATE = {
    "resolution_id": String,
    "candidate_id": String,
    "domain": String,
    "method": String,
    "raw_code": String,
    "matched_code_systems": String,
    "candidate_count": Number.size(18, 0),
    "resolution_status": String,
}

MI_CODE_RESOLUTION_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_CANDIDATE", schema=SCHEMA_MI_CODE_RESOLUTION_CANDIDATE)

SCHEMA_MI_MONTH_END_CALENDAR = {
    "month_end": Date,
    "month_start": Date,
    "calendar_year": Number.size(18, 0),
    "calendar_month": Number.size(18, 0),
    "month_index": Integer,
}

MI_MONTH_END_CALENDAR = model.Table(f"{DB}.MODEL_INPUT.MONTH_END_CALENDAR", schema=SCHEMA_MI_MONTH_END_CALENDAR)

SCHEMA_MI_ROUTE = {
    "route_id": String,
    "origin_station_code_iata": String,
    "destination_station_code_iata": String,
    "origin_airport_id": String,
    "origin_airport_resolution_status": String,
    "destination_airport_id": String,
    "destination_airport_resolution_status": String,
    "canonical_observation_count": Number.size(18, 0),
    "distinct_schedule_key_count": Number.size(18, 0),
}

MI_ROUTE = model.Table(f"{DB}.MODEL_INPUT.ROUTE", schema=SCHEMA_MI_ROUTE)

SCHEMA_MI_ROUTE_STATE = {
    "route_state_key": String,
    "schedule_key": String,
    "route_id": String,
    "knowledge_valid_from": Date,
    "knowledge_valid_to": Date,
    "is_open_state": Bool,
    "segment_open_kind": String,
    "is_reappearance": Bool,
    "closing_reason": String,
    "previous_eligible_publish_date_at_open": Date,
    "open_crosses_snapshot_gap": Bool,
    "open_skipped_calendar_dates": String,
    "close_crosses_snapshot_gap": Bool,
    "close_skipped_calendar_dates": String,
    "contributing_snapshot_count": Number.size(18, 0),
    "normalized_row_hash": String,
    "schedule_key_readable": String,
    "itinerary_variation_identifier": Integer,
    "marketing_carrier_internal": String,
    "operating_carrier_internal": String,
    "flight_number": Integer,
    "service_type_iata": String,
    "operating_effective_date": Date,
    "operating_discontinue_date": Date,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "departure_terminal": String,
    "arrival_terminal": String,
    "is_operating_monday": Bool,
    "is_operating_tuesday": Bool,
    "is_operating_wednesday": Bool,
    "is_operating_thursday": Bool,
    "is_operating_friday": Bool,
    "is_operating_saturday": Bool,
    "is_operating_sunday": Bool,
    "days_pattern": String,
    "weekly_frequency": Integer,
    "passenger_departure_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "arrival_day_indicator": Integer,
    "scheduled_block_minutes": Integer,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "first_class_seats": Float,
    "business_class_seats": Float,
    "premium_economy_seats": Float,
    "economy_class_seats": Float,
    "is_codeshare": Bool,
    "codeshare_carrier_internal": String,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "watched_content_signature": String,
    "economy_excluding_premium": Float,
    "exclusive_cabin_sum": Float,
    "cabin_quality_status": String,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "codeshare_airline_id": String,
    "codeshare_airline_resolution_status": String,
    "origin_airport_id": String,
    "origin_airport_resolution_status": String,
    "destination_airport_id": String,
    "destination_airport_resolution_status": String,
    "physical_service_status": String,
    "utc_date_status": String,
}

MI_ROUTE_STATE = model.Table(f"{DB}.MODEL_INPUT.ROUTE_STATE", schema=SCHEMA_MI_ROUTE_STATE)

SCHEMA_MI_ROUTE_STATE_LINEAGE = {
    "route_state_key": String,
    "schedule_key": String,
    "publish_date": Date,
    "normalized_row_hash": String,
    "itinerary_variation_identifier": Integer,
    "raw_observation_count": Number.size(18, 0),
    "semantic_duplicate_count": Number.size(18, 0),
    "watched_content_signature": String,
    "is_segment_opening_observation": Bool,
    "snapshot_source_lineage_id": String,
    "snapshot_validation_status": String,
}

MI_ROUTE_STATE_LINEAGE = model.Table(f"{DB}.MODEL_INPUT.ROUTE_STATE_LINEAGE", schema=SCHEMA_MI_ROUTE_STATE_LINEAGE)

SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION = {
    "schedule_key": String,
    "publish_date": Date,
    "schedule_key_readable": String,
    "normalized_row_hash": String,
    "itinerary_variation_identifier": Integer,
    "raw_observation_count": Number.size(18, 0),
    "semantic_duplicate_count": Number.size(18, 0),
    "selection_rule": String,
    "snapshot_is_present": Bool,
    "snapshot_is_complete": Bool,
    "is_eligible_snapshot": Bool,
    "snapshot_validation_status": String,
    "snapshot_source_lineage_id": String,
    "marketing_carrier_internal": String,
    "operating_carrier_internal": String,
    "flight_number": Integer,
    "service_type_iata": String,
    "effective_date": Date,
    "discontinue_date": Date,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "departure_terminal": String,
    "arrival_terminal": String,
    "is_operating_monday": Bool,
    "is_operating_tuesday": Bool,
    "is_operating_wednesday": Bool,
    "is_operating_thursday": Bool,
    "is_operating_friday": Bool,
    "is_operating_saturday": Bool,
    "is_operating_sunday": Bool,
    "days_pattern": String,
    "weekly_frequency": Integer,
    "passenger_departure_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "arrival_day_indicator": Integer,
    "scheduled_block_minutes": Integer,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "first_class_seats": Float,
    "business_class_seats": Float,
    "premium_economy_seats": Float,
    "economy_class_seats": Float,
    "is_codeshare": Bool,
    "codeshare_carrier_internal": String,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "route_id": String,
    "route_key_status": String,
    "watched_content_signature": String,
    "economy_excluding_premium": Float,
    "exclusive_cabin_sum": Float,
    "cabin_quality_status": String,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "codeshare_airline_id": String,
    "codeshare_airline_resolution_status": String,
    "origin_airport_id": String,
    "origin_airport_resolution_status": String,
    "destination_airport_id": String,
    "destination_airport_resolution_status": String,
    "physical_service_status": String,
    "utc_date_status": String,
}

MI_SCHEDULE_CANONICAL_OBSERVATION = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION", schema=SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION)

SCHEMA_MI_SCHEDULE_COMPARISON = {
    "comparison_id": String,
    "previous_knowledge_date": Date,
    "comparison_date": Date,
    "previous_eligible_rank": Number.size(18, 0),
    "comparison_eligible_rank": Number.size(18, 0),
    "calendar_day_span": Number.size(18, 0),
    "skipped_calendar_date_count": Number.size(18, 0),
    "crosses_snapshot_gap": Bool,
    "skipped_calendar_dates": String,
    "comparison_kind": String,
}

MI_SCHEDULE_COMPARISON = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_COMPARISON", schema=SCHEMA_MI_SCHEDULE_COMPARISON)

SCHEMA_MI_SCHEDULE_EXACT_CHANGE = {
    "comparison_id": String,
    "previous_knowledge_date": Date,
    "comparison_date": Date,
    "crosses_snapshot_gap": Bool,
    "skipped_calendar_dates": String,
    "schedule_key": String,
    "change_kind": String,
    "field_name": String,
    "old_value": String,
    "new_value": String,
    "is_reappearance": Bool,
}

MI_SCHEDULE_EXACT_CHANGE = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_EXACT_CHANGE", schema=SCHEMA_MI_SCHEDULE_EXACT_CHANGE)

SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE = {
    "comparison_id": String,
    "previous_knowledge_date": Date,
    "comparison_date": Date,
    "schedule_key": String,
    "side": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "effective_date": Date,
    "discontinue_date": Date,
    "operating_carrier_internal": String,
    "days_pattern": String,
    "weekly_frequency": Integer,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "candidate_eligible": Bool,
    "ineligibility_reason": String,
    "candidate_signature": String,
}

MI_SCHEDULE_AMENDMENT_SIDE = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE)

SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE = {
    "amendment_candidate_id": String,
    "comparison_id": String,
    "removed_schedule_key": String,
    "added_schedule_key": String,
    "amendment_candidate_class": String,
    "amendment_confidence": String,
    "exactness": String,
    "candidate_signature": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "removed_effective_date": Date,
    "removed_discontinue_date": Date,
    "added_effective_date": Date,
    "added_discontinue_date": Date,
    "removed_operating_carrier_internal": String,
    "added_operating_carrier_internal": String,
    "removed_days_pattern": String,
    "added_days_pattern": String,
    "removed_weekly_frequency": Integer,
    "added_weekly_frequency": Integer,
    "removed_equipment_subtype_code_iata": String,
    "added_equipment_subtype_code_iata": String,
    "removed_total_seats": Float,
    "added_total_seats": Float,
}

MI_SCHEDULE_AMENDMENT_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_CANDIDATE", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE)

SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP = {
    "amendment_group_id": String,
    "comparison_id": String,
    "candidate_signature": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "removed_member_count": Number.size(18, 0),
    "added_member_count": Number.size(18, 0),
    "removed_schedule_keys": String,
    "added_schedule_keys": String,
    "amendment_candidate_class": String,
    "amendment_confidence": String,
    "exactness": String,
}

MI_SCHEDULE_AMENDMENT_GROUP = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP)

SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER = {
    "amendment_group_member_id": String,
    "amendment_group_id": String,
    "comparison_id": String,
    "side": String,
    "member_schedule_key": String,
    "member_class": String,
    "amendment_confidence": String,
    "exactness": String,
    "candidate_signature": String,
    "unpaired_reason": String,
}

MI_SCHEDULE_AMENDMENT_GROUP_MEMBER = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP_MEMBER", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER)

SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL = {
    "passenger_flight_key": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "planned_origin_station_code_iata": String,
    "planned_destination_station_code_iata": String,
    "operating_date": Date,
    "selected_source_system": String,
    "selected_source_row_token": String,
    "selected_source_row_token_basis": String,
    "selected_stable_source_row_id": Integer,
    "selected_typed_normalized_row_hash": String,
    "source_precedence_rule": String,
    "lineage_observation_count": Number.size(18, 0),
    "historical_lineage_retained": Bool,
    "forward_lineage_retained": Bool,
    "operating_carrier_internal": String,
    "publish_date": Date,
    "service_type_iata": String,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "is_codeshare": Bool,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "arrival_day_indicator": Integer,
    "plan_departure_local_timestamp": DateTime,
    "plan_arrival_local_timestamp": DateTime,
    "plan_departure_utc_timestamp": DateTime,
    "plan_arrival_utc_timestamp": DateTime,
    "utc_date_status": String,
    "schedule_key": String,
    "historical_effective_date": Date,
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_departure_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_utc_time": String,  # TIME -> String (PROBE U-03)
    "departure_utc_offset_minutes": Float,
    "arrival_utc_offset_minutes": Float,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "planned_origin_airport_id": String,
    "planned_origin_airport_resolution_status": String,
    "planned_destination_airport_id": String,
    "planned_destination_airport_resolution_status": String,
}

MI_PASSENGER_FLIGHT_CANONICAL = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL", schema=SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL)

SCHEMA_MI_PASSENGER_FLIGHT_INVALID = {
    "source_system": String,
    "stable_source_row_id": Integer,
    "source_row_token": String,
    "typed_normalized_row_hash": String,
    "passenger_key_status": String,
    "invalid_reason": String,
    "missing_key_components": String,
    "raw_marketing_carrier_internal": String,
    "raw_flight_number": Integer,
    "raw_departure_station_code_iata": String,
    "raw_arrival_station_code_iata": String,
    "raw_operating_date": Date,
    "publish_date": Date,
}

MI_PASSENGER_FLIGHT_INVALID = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_FLIGHT_INVALID", schema=SCHEMA_MI_PASSENGER_FLIGHT_INVALID)

SCHEMA_MI_PASSENGER_SOURCE_LINEAGE = {
    "passenger_flight_key": String,
    "source_system": String,
    "source_row_token": String,
    "source_row_token_basis": String,
    "stable_source_row_id": Integer,
    "typed_normalized_row_hash": String,
    "publish_date": Date,
    "source_precedence_rank": Number.size(18, 0),
    "selection_rank": Number.size(18, 0),
    "is_selected_observation": Bool,
    "schedule_key": String,
    "operating_carrier_internal": String,
    "total_seats": Float,
    "is_codeshare": Bool,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "utc_date_status": String,
}

MI_PASSENGER_SOURCE_LINEAGE = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_SOURCE_LINEAGE", schema=SCHEMA_MI_PASSENGER_SOURCE_LINEAGE)

SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE = {
    "quarantine_id": String,
    "source_object": String,
    "quarantine_reason": String,
    "typed_normalized_row_hash": String,
    "quarantine_key_basis": String,
    "missing_key_components": String,
    "raw_flight_number": Integer,
    "raw_departure_station_code_iata": String,
    "raw_arrival_station_code_iata": String,
    "raw_operating_date": Date,
    "occurrence_count": Number.size(18, 0),
}

MI_PASSENGER_SOURCE_QUARANTINE = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_SOURCE_QUARANTINE", schema=SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE)

SCHEMA_MI_PASSENGER_PLANNED_LEG = {
    "passenger_flight_key": String,
    "leg_index": Integer,
    "from_station_code_iata": String,
    "to_station_code_iata": String,
    "station_count": Number.size(18, 0),
    "from_airport_id": String,
    "from_airport_resolution_status": String,
    "to_airport_id": String,
    "to_airport_resolution_status": String,
}

MI_PASSENGER_PLANNED_LEG = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_PLANNED_LEG", schema=SCHEMA_MI_PASSENGER_PLANNED_LEG)

SCHEMA_MI_AIRCRAFT_FLIGHT = {
    "flight_id": Integer,
    "aircraft_id": Integer,
    "aircraft_link_exists": Bool,
    "operating_carrier_code": String,
    "marketing_carrier_code": String,
    "raw_flight_number": String,
    "normalized_flight_number": Integer,
    "flight_number_status": String,
    "flight_departure_date": Date,
    "flight_departure_date_utc": Date,
    "departure_airport_code": String,
    "arrival_airport_code": String,
    "actual_continuity_arrival_code": String,
    "diverted_airport_code": String,
    "raw_is_cancelled": Integer,
    "is_cancelled_boolean": Bool,
    "cancellation_flag_status": String,
    "raw_is_diverted": Integer,
    "is_diverted_boolean": Bool,
    "diversion_flag_status": String,
    "diversion_endpoint_conflict": Bool,
    "actual_gate_departure_time_utc": DateTime,
    "actual_gate_arrival_time_utc": DateTime,
    "actual_gate_departure_time_local": DateTime,
    "actual_gate_arrival_time_local": DateTime,
    "actual_source_aircraft_type": String,
    "actual_source_aircraft_code_iata": String,
    "actual_source_aircraft_family": String,
    "next_flight_id": Integer,
    "actual_origin_airport_id": String,
    "actual_origin_airport_resolution_status": String,
    "actual_destination_airport_id": String,
    "actual_destination_airport_resolution_status": String,
    "diverted_airport_id": String,
    "diverted_airport_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
}

MI_AIRCRAFT_FLIGHT = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_FLIGHT", schema=SCHEMA_MI_AIRCRAFT_FLIGHT)

SCHEMA_MI_ROTATION_LINK_VALIDATION = {
    "flight_id": Integer,
    "target_token": String,
    "next_flight_id": Integer,
    "aircraft_id": Integer,
    "selected_local_date": Date,
    "selected_date_basis": String,
    "rotation_link_status": String,
    "rotation_anomaly_class": String,
    "is_accepted_link": Bool,
    "cycle_component_id": Integer,
    "is_cycle_representative": Bool,
    "is_self_loop_link": Bool,
    "actual_origin_code": String,
    "actual_continuity_arrival_code": String,
    "diverted_airport_code": String,
    "diversion_endpoint_conflict": Bool,
    "actual_gate_departure_time_utc": DateTime,
    "actual_gate_arrival_time_utc": DateTime,
    "is_cancelled_boolean": Bool,
    "cancellation_flag_status": String,
    "is_diverted_boolean": Bool,
    "diversion_flag_status": String,
    "target_flight_id": Integer,
    "target_aircraft_id": Integer,
    "target_selected_local_date": Date,
    "target_departure_time_utc": DateTime,
    "target_origin_code": String,
    "target_is_cancelled_boolean": Bool,
}

MI_ROTATION_LINK_VALIDATION = model.Table(f"{DB}.MODEL_INPUT.ROTATION_LINK_VALIDATION", schema=SCHEMA_MI_ROTATION_LINK_VALIDATION)

SCHEMA_MI_FULFILLMENT_EXACT = {
    "exact_fulfillment_id": String,
    "actual_flight_id": Integer,
    "passenger_flight_key": String,
    "passenger_source_system": String,
    "passenger_source_row_token": String,
    "passenger_stable_source_row_id": Integer,
    "fulfillment_class": String,
    "exactness": String,
    "exact_link_basis": String,
    "confirmed_link": Bool,
    "actual_operating_date": Date,
    "planned_operating_date": Date,
    "actual_marketing_airline_id": String,
    "planned_marketing_airline_id": String,
    "actual_operating_airline_id": String,
    "planned_operating_airline_id": String,
    "normalized_flight_number": Integer,
    "planned_flight_number": Integer,
    "actual_origin_airport_id": String,
    "actual_destination_airport_id": String,
}

MI_FULFILLMENT_EXACT = model.Table(f"{DB}.MODEL_INPUT.FULFILLMENT_EXACT", schema=SCHEMA_MI_FULFILLMENT_EXACT)

SCHEMA_MI_FULFILLMENT_CANDIDATE = {
    "fulfillment_candidate_id": String,
    "actual_flight_id": Integer,
    "passenger_flight_key": String,
    "fulfillment_class": String,
    "exactness": String,
    "confidence": String,
    "confirmed_link": Bool,
    "marketing_role_agrees": Bool,
    "operating_role_agrees": Bool,
    "normalized_flight_number": Integer,
    "actual_operating_date": Date,
    "leg_index": Integer,
    "station_count": Number.size(18, 0),
    "planned_service_has_stopovers": Bool,
    "actual_origin_airport_id": String,
    "actual_destination_airport_id": String,
}

MI_FULFILLMENT_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.FULFILLMENT_CANDIDATE", schema=SCHEMA_MI_FULFILLMENT_CANDIDATE)

SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP = {
    "fulfillment_group_member_id": String,
    "fulfillment_group_id": String,
    "side": String,
    "member_identity": String,
    "member_class": String,
    "exactness": String,
    "confidence": String,
    "confirmed_link": Bool,
    "actual_member_count": Integer,
    "passenger_member_count": Integer,
    "unmatched_reason": String,
}

MI_FULFILLMENT_AMBIGUOUS_GROUP = model.Table(f"{DB}.MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP", schema=SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP)


# alias -> (Table, "SCHEMA.TABLE", declared column -> RAI type)
TABLE_INVENTORY = {
    "SRC_SCHEDULE_SNAPSHOT_CALENDAR": (SRC_SCHEDULE_SNAPSHOT_CALENDAR, "SOURCE.SCHEDULE_SNAPSHOT_CALENDAR", SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR),
    "SRC_AIRCRAFT_CONFIGURATION": (SRC_AIRCRAFT_CONFIGURATION, "SOURCE.AIRCRAFT_CONFIGURATION", SCHEMA_SRC_AIRCRAFT_CONFIGURATION),
    "MI_AIRCRAFT_ELIGIBLE": (MI_AIRCRAFT_ELIGIBLE, "MODEL_INPUT.AIRCRAFT_ELIGIBLE", SCHEMA_MI_AIRCRAFT_ELIGIBLE),
    "MI_AIRCRAFT_EVENT_ELIGIBLE": (MI_AIRCRAFT_EVENT_ELIGIBLE, "MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE", SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE),
    "MI_AIRCRAFT_EVENT_QUARANTINE": (MI_AIRCRAFT_EVENT_QUARANTINE, "MODEL_INPUT.AIRCRAFT_EVENT_QUARANTINE", SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE),
    "MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT": (MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT, "MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT", SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT),
    "MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT": (MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT, "MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT", SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT),
    "MI_AIRCRAFT_TYPE_DEFINITION": (MI_AIRCRAFT_TYPE_DEFINITION, "MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION", SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION),
    "MI_ENGINE_TYPE_DEFINITION": (MI_ENGINE_TYPE_DEFINITION, "MODEL_INPUT.ENGINE_TYPE_DEFINITION", SCHEMA_MI_ENGINE_TYPE_DEFINITION),
    "MI_AIRPORT_CURRENT": (MI_AIRPORT_CURRENT, "MODEL_INPUT.AIRPORT_CURRENT", SCHEMA_MI_AIRPORT_CURRENT),
    "MI_AIRLINE_CURRENT": (MI_AIRLINE_CURRENT, "MODEL_INPUT.AIRLINE_CURRENT", SCHEMA_MI_AIRLINE_CURRENT),
    "MI_CODE_RESOLUTION_CODE": (MI_CODE_RESOLUTION_CODE, "MODEL_INPUT.CODE_RESOLUTION_CODE", SCHEMA_MI_CODE_RESOLUTION_CODE),
    "MI_CODE_RESOLUTION_CODE_CANDIDATE": (MI_CODE_RESOLUTION_CODE_CANDIDATE, "MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE", SCHEMA_MI_CODE_RESOLUTION_CODE_CANDIDATE),
    "MI_CODE_RESOLUTION_INPUT": (MI_CODE_RESOLUTION_INPUT, "MODEL_INPUT.CODE_RESOLUTION_INPUT", SCHEMA_MI_CODE_RESOLUTION_INPUT),
    "MI_CODE_RESOLUTION": (MI_CODE_RESOLUTION, "MODEL_INPUT.CODE_RESOLUTION", SCHEMA_MI_CODE_RESOLUTION),
    "MI_CODE_RESOLUTION_CANDIDATE": (MI_CODE_RESOLUTION_CANDIDATE, "MODEL_INPUT.CODE_RESOLUTION_CANDIDATE", SCHEMA_MI_CODE_RESOLUTION_CANDIDATE),
    "MI_MONTH_END_CALENDAR": (MI_MONTH_END_CALENDAR, "MODEL_INPUT.MONTH_END_CALENDAR", SCHEMA_MI_MONTH_END_CALENDAR),
    "MI_ROUTE": (MI_ROUTE, "MODEL_INPUT.ROUTE", SCHEMA_MI_ROUTE),
    "MI_ROUTE_STATE": (MI_ROUTE_STATE, "MODEL_INPUT.ROUTE_STATE", SCHEMA_MI_ROUTE_STATE),
    "MI_ROUTE_STATE_LINEAGE": (MI_ROUTE_STATE_LINEAGE, "MODEL_INPUT.ROUTE_STATE_LINEAGE", SCHEMA_MI_ROUTE_STATE_LINEAGE),
    "MI_SCHEDULE_CANONICAL_OBSERVATION": (MI_SCHEDULE_CANONICAL_OBSERVATION, "MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION", SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION),
    "MI_SCHEDULE_COMPARISON": (MI_SCHEDULE_COMPARISON, "MODEL_INPUT.SCHEDULE_COMPARISON", SCHEMA_MI_SCHEDULE_COMPARISON),
    "MI_SCHEDULE_EXACT_CHANGE": (MI_SCHEDULE_EXACT_CHANGE, "MODEL_INPUT.SCHEDULE_EXACT_CHANGE", SCHEMA_MI_SCHEDULE_EXACT_CHANGE),
    "MI_SCHEDULE_AMENDMENT_SIDE": (MI_SCHEDULE_AMENDMENT_SIDE, "MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE", SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE),
    "MI_SCHEDULE_AMENDMENT_CANDIDATE": (MI_SCHEDULE_AMENDMENT_CANDIDATE, "MODEL_INPUT.SCHEDULE_AMENDMENT_CANDIDATE", SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE),
    "MI_SCHEDULE_AMENDMENT_GROUP": (MI_SCHEDULE_AMENDMENT_GROUP, "MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP", SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP),
    "MI_SCHEDULE_AMENDMENT_GROUP_MEMBER": (MI_SCHEDULE_AMENDMENT_GROUP_MEMBER, "MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP_MEMBER", SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER),
    "MI_PASSENGER_FLIGHT_CANONICAL": (MI_PASSENGER_FLIGHT_CANONICAL, "MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL", SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL),
    "MI_PASSENGER_FLIGHT_INVALID": (MI_PASSENGER_FLIGHT_INVALID, "MODEL_INPUT.PASSENGER_FLIGHT_INVALID", SCHEMA_MI_PASSENGER_FLIGHT_INVALID),
    "MI_PASSENGER_SOURCE_LINEAGE": (MI_PASSENGER_SOURCE_LINEAGE, "MODEL_INPUT.PASSENGER_SOURCE_LINEAGE", SCHEMA_MI_PASSENGER_SOURCE_LINEAGE),
    "MI_PASSENGER_SOURCE_QUARANTINE": (MI_PASSENGER_SOURCE_QUARANTINE, "MODEL_INPUT.PASSENGER_SOURCE_QUARANTINE", SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE),
    "MI_PASSENGER_PLANNED_LEG": (MI_PASSENGER_PLANNED_LEG, "MODEL_INPUT.PASSENGER_PLANNED_LEG", SCHEMA_MI_PASSENGER_PLANNED_LEG),
    "MI_AIRCRAFT_FLIGHT": (MI_AIRCRAFT_FLIGHT, "MODEL_INPUT.AIRCRAFT_FLIGHT", SCHEMA_MI_AIRCRAFT_FLIGHT),
    "MI_ROTATION_LINK_VALIDATION": (MI_ROTATION_LINK_VALIDATION, "MODEL_INPUT.ROTATION_LINK_VALIDATION", SCHEMA_MI_ROTATION_LINK_VALIDATION),
    "MI_FULFILLMENT_EXACT": (MI_FULFILLMENT_EXACT, "MODEL_INPUT.FULFILLMENT_EXACT", SCHEMA_MI_FULFILLMENT_EXACT),
    "MI_FULFILLMENT_CANDIDATE": (MI_FULFILLMENT_CANDIDATE, "MODEL_INPUT.FULFILLMENT_CANDIDATE", SCHEMA_MI_FULFILLMENT_CANDIDATE),
    "MI_FULFILLMENT_AMBIGUOUS_GROUP": (MI_FULFILLMENT_AMBIGUOUS_GROUP, "MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP", SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP),
}


# ================================================================================================
# core_reference.py
# ================================================================================================
# core_reference.py - reference entities every other module links to.
#
# Loaded before ``core_aircraft`` / ``core_schedule`` / ``core_flight`` because Python needs the
# Concept objects to exist before their reading f-strings interpolate them.
#
# ``Airport`` and ``Airline`` bind from the ``MODEL_INPUT.*_CURRENT`` projections rather than from
# ``SOURCE.*_REFERENCE``. PROBE G-03 / G-04 showed the raw source is *already* one effective
# period per entity, so binding ``SOURCE`` directly would not have raised - but the projections
# carry a ``PROJECTION_RULE`` column recording the declared deterministic order, which is exactly
# what ``ATTRIBUTE_AUTHORITY.md`` demands instead of relying on ``WHERE is_current``. Using them
# puts the choice of winner in the data instead of in a query. ``REFERENCE_PERIOD_COUNT`` is
# carried so a future multi-period fixture is visible rather than silent.
#
# ``CodeResolutionCode`` is the D-0019 substitution for the row-scoped ``CODE_RESOLUTION``: link
# semantics only ever need "does this raw code resolve to exactly one identity", which is a
# property of the code, not of the row that mentioned it.




# --- Airport (AP-01) --------------------------------------------------------------

Airport = model.Concept("Airport", identify_by={"airport_id": String})

_airport_scalars = scalar_properties(
    Airport, SCHEMA_MI_AIRPORT_CURRENT, exclude=("airport_id",)
)
model.define(Airport.new(airport_id=MI_AIRPORT_CURRENT.airport_id))
bind_scalars(
    Airport,
    MI_AIRPORT_CURRENT,
    {"airport_id": MI_AIRPORT_CURRENT.airport_id},
    _airport_scalars,
)

# --- Airline (AL-01) --------------------------------------------------------------

Airline = model.Concept("Airline", identify_by={"airline_id": String})

_airline_scalars = scalar_properties(
    Airline, SCHEMA_MI_AIRLINE_CURRENT, exclude=("airline_id",)
)
model.define(Airline.new(airline_id=MI_AIRLINE_CURRENT.airline_id))
bind_scalars(
    Airline,
    MI_AIRLINE_CURRENT,
    {"airline_id": MI_AIRLINE_CURRENT.airline_id},
    _airline_scalars,
)

# --- Code resolution, at code grain (D-0019) --------------------------------------

CodeResolutionCode = model.Concept(
    "CodeResolutionCode",
    identify_by={"domain": String, "method": String, "raw_code": String},
)

_code_resolution_scalars = scalar_properties(
    CodeResolutionCode,
    SCHEMA_MI_CODE_RESOLUTION_CODE,
    exclude=("domain", "method", "raw_code"),
)
model.define(
    CodeResolutionCode.new(
        domain=MI_CODE_RESOLUTION_CODE.domain,
        method=MI_CODE_RESOLUTION_CODE.method,
        raw_code=MI_CODE_RESOLUTION_CODE.raw_code,
    )
)
bind_scalars(
    CodeResolutionCode,
    MI_CODE_RESOLUTION_CODE,
    {
        "domain": MI_CODE_RESOLUTION_CODE.domain,
        "method": MI_CODE_RESOLUTION_CODE.method,
        "raw_code": MI_CODE_RESOLUTION_CODE.raw_code,
    },
    _code_resolution_scalars,
)

CodeResolutionCodeCandidate = model.Concept(
    "CodeResolutionCodeCandidate",
    identify_by={"resolution": CodeResolutionCode, "candidate_id": String},
)

CodeResolutionCodeCandidate.matched_code_systems = model.Property(
    f"{CodeResolutionCodeCandidate} matched {String:matched_code_systems}"
)

_candidate_resolution_key = {
    "domain": MI_CODE_RESOLUTION_CODE_CANDIDATE.domain,
    "method": MI_CODE_RESOLUTION_CODE_CANDIDATE.method,
    "raw_code": MI_CODE_RESOLUTION_CODE_CANDIDATE.raw_code,
}
model.define(
    CodeResolutionCodeCandidate.new(
        resolution=CodeResolutionCode.lookup(**_candidate_resolution_key),
        candidate_id=MI_CODE_RESOLUTION_CODE_CANDIDATE.candidate_id,
    )
)
model.define(
    CodeResolutionCodeCandidate.lookup(
        resolution=CodeResolutionCode.lookup(**_candidate_resolution_key),
        candidate_id=MI_CODE_RESOLUTION_CODE_CANDIDATE.candidate_id,
    ).matched_code_systems(MI_CODE_RESOLUTION_CODE_CANDIDATE.matched_code_systems)
)

# ``candidates`` carries no cardinality claim: a raw code may resolve to zero, one or many
# candidates (SOURCE_CONTRACT.md multiplicity gate), and only a cardinality-one EXACT
# resolution is ever allowed to create a concept link elsewhere in the model. It is declared as
# a ``Relationship`` rather than as an ``.alt()`` reading over ``candidate.resolution`` because
# ``resolution`` is an *identity* component, and ``identify_by`` names an entity component's
# owner slot after the lowercased concept - an inverse reading would have to spell
# ``coderesolutioncodecandidate``. A ``Relationship`` adds no functional dependency either.
CodeResolutionCode.candidates = model.Relationship(
    f"{CodeResolutionCode:resolution} has candidate {CodeResolutionCodeCandidate:candidate}"
)
model.define(CodeResolutionCode.candidates(CodeResolutionCodeCandidate)).where(
    CodeResolutionCodeCandidate.resolution == CodeResolutionCode
)

# --- Code resolution, at row grain (D-0027) ---------------------------------------
#
# D-0019 excluded the row-scoped resolution on a suspicion about sync and cold-start cost and
# gated the exclusion on one measurement. The measurement came back at 0.18 seconds against an
# 18-second first query, inside the warm-query noise band, so the premise is refuted and the
# exclusion does not stand. ``CodeResolutionCode`` above remains the grain link semantics read;
# ``CodeResolution`` adds the provenance grain, which is the one question the code grain cannot
# answer: which source object, row and field role mentioned a given raw code.

CodeResolution = model.Concept("CodeResolution", identify_by={"resolution_id": String})

_row_resolution_scalars = scalar_properties(
    CodeResolution, SCHEMA_MI_CODE_RESOLUTION, exclude=("resolution_id",)
)
model.define(CodeResolution.new(resolution_id=MI_CODE_RESOLUTION.resolution_id))
bind_scalars(
    CodeResolution,
    MI_CODE_RESOLUTION,
    {"resolution_id": MI_CODE_RESOLUTION.resolution_id},
    _row_resolution_scalars,
)

CodeResolutionCandidate = model.Concept(
    "CodeResolutionCandidate",
    identify_by={"resolution": CodeResolution, "candidate_id": String},
)

_row_candidate_scalars = scalar_properties(
    CodeResolutionCandidate,
    SCHEMA_MI_CODE_RESOLUTION_CANDIDATE,
    exclude=("resolution_id", "candidate_id"),
)
_row_candidate_key = {
    "resolution": CodeResolution.lookup(
        resolution_id=MI_CODE_RESOLUTION_CANDIDATE.resolution_id
    ),
    "candidate_id": MI_CODE_RESOLUTION_CANDIDATE.candidate_id,
}
model.define(CodeResolutionCandidate.new(**_row_candidate_key))
bind_scalars(
    CodeResolutionCandidate,
    MI_CODE_RESOLUTION_CANDIDATE,
    _row_candidate_key,
    _row_candidate_scalars,
)

# Same reasoning as the code-grain relationship: zero, one or many candidates are all legal and
# only a cardinality-one EXACT resolution ever creates a link, so this carries no functional
# dependency.
CodeResolution.candidates = model.Relationship(
    f"{CodeResolution:resolution} has row candidate {CodeResolutionCandidate:candidate}"
)
model.define(CodeResolution.candidates(CodeResolutionCandidate)).where(
    CodeResolutionCandidate.resolution == CodeResolution
)

# --- SnapshotDate (SC-01) ---------------------------------------------------------
#
# The eligibility control for Q05 and Q06. P0-05.1: a snapshot is usable only when it is both
# present and complete; SC-05 observed row counts are validation evidence and never a
# completeness test on their own.

SnapshotDate = model.Concept("SnapshotDate", identify_by={"expected_publish_date": Date})

_snapshot_scalars = scalar_properties(
    SnapshotDate,
    SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR,
    exclude=("expected_publish_date",),
)
model.define(
    SnapshotDate.new(
        expected_publish_date=SRC_SCHEDULE_SNAPSHOT_CALENDAR.expected_publish_date
    )
)
bind_scalars(
    SnapshotDate,
    SRC_SCHEDULE_SNAPSHOT_CALENDAR,
    {"expected_publish_date": SRC_SCHEDULE_SNAPSHOT_CALENDAR.expected_publish_date},
    _snapshot_scalars,
)

# Shared derived property #3 in QUERY_ROUTING.md: one definition, two consumers with different
# refusal behaviour. Q05 walks adjacent eligible dates; Q06 requires both exact endpoints to be
# eligible and refuses rather than falling back. The definition is shared; the refusal is not.
SnapshotDate.is_eligible = model.Relationship(f"{SnapshotDate} is an eligible snapshot")
model.define(SnapshotDate.is_eligible()).where(
    SnapshotDate.is_present == True,  # noqa: E712 - RAI equality, not Python truthiness
    SnapshotDate.is_complete == True,  # noqa: E712
)


# ================================================================================================
# core_aircraft.py
# ================================================================================================
# core_aircraft.py - UC1: aircraft identity, events, definitions and both assignment layers.
#
# This module is the reduced-demo fallback (AGENTS.md: "UC1 is the independently runnable
# fallback"). It plus ``temporal.py``, ``calendar.py`` and ``computed_aircraft.py`` answers Q01
# through Q04 on its own, with no schedule or flight surface at all.
#
# The shape that matters, and the reason it is not obvious:
#
# * **Identity never carries state.** ``Aircraft`` is ``AM-01`` alone. Registration, type, engine
#   and status are all versioned assignments hanging off it, never properties of it (P0-01.1).
# * **Two assignment layers, not one.** The *audit* stream is the ordered same-day truth and
#   carries **no** date interval, ever. The *daily* projection carries the half-open interval and
#   keeps only the final relevant observation per aircraft/dimension/date. Q02's same-day
#   ``Storage -> In Service`` spell exists only on the audit stream; reading the daily stream
#   loses it silently. Keeping them as two concepts makes that impossible to conflate by accident.
# * **Compound identity makes the same-day rule structural.** BRIEF.md: "Order aircraft events by
#   date and sequence; do not identify a version by date alone." Putting ``event_date``,
#   ``row_sequence`` and ``event`` into ``identify_by`` means two same-day observations are two
#   entities permanently, and no downstream rule can collapse them. PROBE U-08 confirmed
#   Concept-valued identity components load from a Snowflake table, that an identical re-define
#   mints zero new entities, and that a row whose parent does not resolve produces no assignment
#   *and no error* - which is why ``inventory.py`` asserts a count per association.
# * **The DV-05 string key is carried as a non-identity property.** ``EXPECTED_ANSWERS.yaml``
#   freezes the literal ``assignment_id`` spelling, so RAI reads it rather than re-deriving it.
#
# Multiplicity: every ``assignment -> parent`` link is a functional ``Property``, and every
# ``parent -> assignments`` link is unconstrained. Where the forward link is a Property this
# module declares, the inverse is an ``.alt()`` *reading* over the same fields, which adds a name
# and no FD. Where the forward link is an *identity component* (``assignment.aircraft``,
# ``assignment.event``) the inverse is an explicit multi-valued ``Relationship`` instead, because
# ``identify_by`` names the owner slot after the lowercased concept and an ``.alt()`` reading
# would have to spell ``aircraftdimensionauditassignment`` to match. Both forms leave the
# one-to-many direction unconstrained, which is what SOURCE_CONTRACT.md requires: "Aircraft to
# audit assignments, one-to-many, association concept; never a functional property".




# --- Aircraft (AM-01) -------------------------------------------------------------

Aircraft = model.Concept("Aircraft", identify_by={"id": Integer})

_aircraft_scalars = scalar_properties(
    Aircraft, SCHEMA_MI_AIRCRAFT_ELIGIBLE, exclude=("aircraft_id",)
)
model.define(Aircraft.new(id=MI_AIRCRAFT_ELIGIBLE.aircraft_id))
bind_scalars(
    Aircraft,
    MI_AIRCRAFT_ELIGIBLE,
    {"id": MI_AIRCRAFT_ELIGIBLE.aircraft_id},
    _aircraft_scalars,
)

# --- AircraftConfiguration (AC-01) ------------------------------------------------
#
# A join target only. It left-preserves every event: an assignment whose configuration does not
# resolve keeps its identity and simply has no configuration fact (P0-12.3).

AircraftConfiguration = model.Concept("AircraftConfiguration", identify_by={"id": Integer})

_configuration_scalars = scalar_properties(
    AircraftConfiguration,
    SCHEMA_SRC_AIRCRAFT_CONFIGURATION,
    exclude=("aircraft_configuration_id",),
)
model.define(
    AircraftConfiguration.new(id=SRC_AIRCRAFT_CONFIGURATION.aircraft_configuration_id)
)
bind_scalars(
    AircraftConfiguration,
    SRC_AIRCRAFT_CONFIGURATION,
    {"id": SRC_AIRCRAFT_CONFIGURATION.aircraft_configuration_id},
    _configuration_scalars,
)

# --- AircraftType (AC-05) and EngineType (AC-14) ----------------------------------
#
# Definition attributes only, and only because PROBE G-01 / G-02 measured zero violating keys.
# AC-08 ``engine_count`` and AC-09 ``has_multiple_engine_types`` deliberately do NOT live on
# ``EngineType``: they are ENGINE_ASSIGNMENT_ATTRIBUTEs per ATTRIBUTE_AUTHORITY.md, they are
# functional on the subseries in this fixture only by accident of a near-bijective generator,
# and asserting one engine count per engine-subseries identity would be wrong in the domain.
# They are bound on the assignment instead, below.

AircraftType = model.Concept("AircraftType", identify_by={"subseries": String})

_aircraft_type_scalars = scalar_properties(
    AircraftType, SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION, exclude=("aircraft_subseries",)
)
model.define(AircraftType.new(subseries=MI_AIRCRAFT_TYPE_DEFINITION.aircraft_subseries))
bind_scalars(
    AircraftType,
    MI_AIRCRAFT_TYPE_DEFINITION,
    {"subseries": MI_AIRCRAFT_TYPE_DEFINITION.aircraft_subseries},
    _aircraft_type_scalars,
)

EngineType = model.Concept("EngineType", identify_by={"subseries": String})

_engine_type_scalars = scalar_properties(
    EngineType, SCHEMA_MI_ENGINE_TYPE_DEFINITION, exclude=("engine_subseries",)
)
model.define(EngineType.new(subseries=MI_ENGINE_TYPE_DEFINITION.engine_subseries))
bind_scalars(
    EngineType,
    MI_ENGINE_TYPE_DEFINITION,
    {"subseries": MI_ENGINE_TYPE_DEFINITION.engine_subseries},
    _engine_type_scalars,
)

# --- AircraftStatus (AH-09) -------------------------------------------------------
#
# G-07: no attributes at all, ever. The identity is the raw AH-09 string with no trim and no
# case fold (NEO4J_RAI_MAPPING.md), and adding a "display label" would be the first step toward
# the normalisation the contract forbids. Minted from the observed audit values, so the
# vocabulary is whatever the source actually contains rather than a hard-coded enum.

AircraftStatus = model.Concept("AircraftStatus", identify_by={"code": String})

model.define(
    AircraftStatus.new(code=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_status_code)
)

# --- AircraftEvent (AH-01) --------------------------------------------------------
#
# An ordered fact. It never carries a date interval (P0-01.4); ``END_EVENT_DATE`` is retained
# as provenance and takes part in no validity predicate.

AircraftEvent = model.Concept("AircraftEvent", identify_by={"id": Integer})

_event_scalars = scalar_properties(
    AircraftEvent,
    SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE,
    exclude=("aircraft_history_id", "aircraft_id"),
)
model.define(AircraftEvent.new(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id))
bind_scalars(
    AircraftEvent,
    MI_AIRCRAFT_EVENT_ELIGIBLE,
    {"id": MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id},
    _event_scalars,
)

AircraftEvent.aircraft = model.Property(
    f"{AircraftEvent:event} observed on {Aircraft:aircraft}"
)
model.define(
    AircraftEvent.lookup(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id).aircraft(
        Aircraft.lookup(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_id)
    )
)
Aircraft.events = AircraftEvent.aircraft.alt(
    f"{Aircraft:aircraft} has event {AircraftEvent:event}"
)

# --- AircraftEventQuarantine (DV-44) ----------------------------------------------

AircraftEventQuarantine = model.Concept(
    "AircraftEventQuarantine", identify_by={"quarantine_id": String}
)
_event_quarantine_scalars = scalar_properties(
    AircraftEventQuarantine,
    SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE,
    exclude=("quarantine_id",),
)
model.define(
    AircraftEventQuarantine.new(quarantine_id=MI_AIRCRAFT_EVENT_QUARANTINE.quarantine_id)
)
bind_scalars(
    AircraftEventQuarantine,
    MI_AIRCRAFT_EVENT_QUARANTINE,
    {"quarantine_id": MI_AIRCRAFT_EVENT_QUARANTINE.quarantine_id},
    _event_quarantine_scalars,
)

# --- AircraftDimensionAuditAssignment (DV-04) -------------------------------------
#
# Identity = (dimension, aircraft, event_date, row_sequence, event). Verified live: 97,983 rows,
# 97,983 distinct tuples. No interval here by construction - the audit stream is order, not
# duration.

_AUDIT_IDENTITY_COLUMNS = (
    "dimension",
    "aircraft_id",
    "event_date",
    "row_sequence_number",
    "aircraft_history_id",
)

AircraftDimensionAuditAssignment = model.Concept(
    "AircraftDimensionAuditAssignment",
    identify_by={
        "dimension": String,
        "aircraft": Aircraft,
        "event_date": Date,
        "row_sequence": Integer,
        "event": AircraftEvent,
    },
)
AuditAssignment = AircraftDimensionAuditAssignment  # readable alias for rule modules

_audit_scalars = scalar_properties(
    AuditAssignment,
    SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    exclude=_AUDIT_IDENTITY_COLUMNS,
)

def _audit_key() -> dict:
    """A *fresh* identity-key mapping for each rule.

    ``lookup()`` returns a new reference every call and two references are never unified
    implicitly, so a single shared key object reused across several ``define()`` calls would
    risk one rule's binding leaking into another. Building it per rule costs nothing and
    removes the question.
    """
    return {
        "dimension": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.dimension,
        "aircraft": Aircraft.lookup(id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_id),
        "event_date": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.event_date,
        "row_sequence": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.row_sequence_number,
        "event": AircraftEvent.lookup(
            id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_history_id
        ),
    }


model.define(AuditAssignment.new(**_audit_key()))
bind_scalars(
    AuditAssignment,
    MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    _audit_key(),
    _audit_scalars,
)

# The inverses of the two *identity* components are declared as explicit multi-valued
# ``Relationship``s rather than as ``.alt()`` readings. ``.alt()`` is the cheaper construct and
# is used everywhere else in this file, but it requires the new reading to reuse the underlying
# relationship's field names, and ``identify_by`` names an entity component's owner slot after
# the lowercased concept - here ``aircraftdimensionauditassignment``. An inverse reading forced
# to spell that would be unreadable in the ontology inventory a customer sees. A
# ``Relationship`` adds no functional dependency either, so the "one aircraft, many
# assignments" direction stays unconstrained exactly as SOURCE_CONTRACT.md requires.
Aircraft.audit_assignments = model.Relationship(
    f"{Aircraft:aircraft} has audit assignment {AuditAssignment:assignment}"
)
model.define(Aircraft.audit_assignments(AuditAssignment)).where(
    AuditAssignment.aircraft == Aircraft
)
AircraftEvent.audit_assignments = model.Relationship(
    f"{AircraftEvent:event} minted audit assignment {AuditAssignment:assignment}"
)
model.define(AircraftEvent.audit_assignments(AuditAssignment)).where(
    AuditAssignment.event == AircraftEvent
)

# --- AircraftDimensionDailyAssignment (DV-05) -------------------------------------
#
# Identity = (dimension, aircraft, valid_from, event). Verified live: 97,979 rows, 97,979
# distinct tuples, and the same count for the DV-05 string key. The half-open interval
# DV-06/DV-07 lives here as two functional ``Date`` properties, because 1.20.1 has no interval
# type at all - which is honest parity with Neo4j, and is also why nothing in the API holds a
# one-open-version-per-parent assumption on our behalf.

_DAILY_IDENTITY_COLUMNS = (
    "dimension",
    "aircraft_id",
    "valid_from",
    "aircraft_history_id",
)

AircraftDimensionDailyAssignment = model.Concept(
    "AircraftDimensionDailyAssignment",
    identify_by={
        "dimension": String,
        "aircraft": Aircraft,
        "valid_from": Date,
        "event": AircraftEvent,
    },
)
DailyAssignment = AircraftDimensionDailyAssignment  # readable alias for rule modules

_daily_scalars = scalar_properties(
    DailyAssignment,
    SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    exclude=_DAILY_IDENTITY_COLUMNS,
)

def _daily_key() -> dict:
    """A fresh identity-key mapping for each rule; see :func:`_audit_key`."""
    return {
        "dimension": MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.dimension,
        "aircraft": Aircraft.lookup(id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_id),
        "valid_from": MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.valid_from,
        "event": AircraftEvent.lookup(
            id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_history_id
        ),
    }


model.define(DailyAssignment.new(**_daily_key()))
bind_scalars(
    DailyAssignment,
    MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    _daily_key(),
    _daily_scalars,
)

Aircraft.daily_assignments = model.Relationship(
    f"{Aircraft:aircraft} has daily assignment {DailyAssignment:assignment}"
)
model.define(Aircraft.daily_assignments(DailyAssignment)).where(
    DailyAssignment.aircraft == Aircraft
)

# --- Exact links out of the assignments -------------------------------------------
#
# All four are ``Property``: at most one exact target per assignment, never exactly one
# (SOURCE_CONTRACT.md "zero-or-one exact target per dimension"). An unresolved reference is
# therefore the absence of a fact rather than a fabricated node, which is precisely the
# ``UNKNOWN_STATE`` gap P0-02.8 wants and what makes the DV-33 classification expressible.
# Verified live: zero orphan ``EXACT_AIRCRAFT_TYPE_SUBSERIES`` and zero orphan
# ``EXACT_ENGINE_TYPE_SUBSERIES`` over 47,984 non-null values each.

DailyAssignment.aircraft_type = model.Property(
    f"{DailyAssignment:assignment} conformed to {AircraftType:aircraft_type}"
)
DailyAssignment.engine_type = model.Property(
    f"{DailyAssignment:assignment} equipped with {EngineType:engine_type}"
)
DailyAssignment.status = model.Property(
    f"{DailyAssignment:assignment} assigned status {AircraftStatus:status}"
)
DailyAssignment.configuration = model.Property(
    f"{DailyAssignment:assignment} read configuration {AircraftConfiguration:configuration}"
)

model.define(
    DailyAssignment.lookup(**_daily_key()).aircraft_type(
        AircraftType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.exact_aircraft_type_subseries
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).engine_type(
        EngineType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.exact_engine_type_subseries
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).status(
        AircraftStatus.lookup(
            code=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_status_code
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).configuration(
        AircraftConfiguration.lookup(
            id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_configuration_id
        )
    )
)

AuditAssignment.aircraft_type = model.Property(
    f"{AuditAssignment:assignment} observed type {AircraftType:aircraft_type}"
)
AuditAssignment.engine_type = model.Property(
    f"{AuditAssignment:assignment} observed engine {EngineType:engine_type}"
)
AuditAssignment.status = model.Property(
    f"{AuditAssignment:assignment} observed status {AircraftStatus:status}"
)
AuditAssignment.configuration = model.Property(
    f"{AuditAssignment:assignment} observed configuration {AircraftConfiguration:configuration}"
)

model.define(
    AuditAssignment.lookup(**_audit_key()).aircraft_type(
        AircraftType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.exact_aircraft_type_subseries
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).engine_type(
        EngineType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.exact_engine_type_subseries
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).status(
        AircraftStatus.lookup(
            code=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_status_code
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).configuration(
        AircraftConfiguration.lookup(
            id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_configuration_id
        )
    )
)

AircraftType.daily_assignments = DailyAssignment.aircraft_type.alt(
    f"{AircraftType:aircraft_type} assigned by {DailyAssignment:assignment}"
)
EngineType.daily_assignments = DailyAssignment.engine_type.alt(
    f"{EngineType:engine_type} fitted by {DailyAssignment:assignment}"
)

# --- No resolved base-airport link, deliberately ----------------------------------
#
# Tempting, and wrong. AH-24 ``BASE_AIRPORT`` is a descriptive label ("Synthetic base"), not an
# internal airport id, and AH-25 ``BASE_AIRPORT_CODE_IATA`` is a public IATA code that
# ``AIRPORT_CURRENT`` does not key on. DATA-04 emits no resolved ``BASE_AIRPORT_ID`` column for
# the aircraft dimension, so there is no exact resolution to bind and inventing one by joining
# on the IATA code would assert a link the contract never resolved. Both raw values stay bound
# as plain strings (SOURCE_CONTRACT.md: a failed resolution must still show the code), and Q01
# emits ``base_airport_code_iata`` from the string, not from an ``Airport`` entity.


# ================================================================================================
# calendar_dates.py
# ================================================================================================
# calendar_dates.py - the ``MonthEnd`` concept behind Q03.
#
# Named ``calendar_dates`` rather than ``calendar`` so it cannot shadow the Python standard
# library module of that name for any consumer of this package.
#
# Why a materialized concept rather than a Python range. Q03's whole point is that the
# interval-to-calendar inequality join replaces a 120-iteration parameter sweep, and that the same
# query works for an irregular calendar. That only holds if the calendar is a *joined dimension*
# inside the model. PROBE U-05 separately confirmed ``std.datetime.date.range(freq="M")`` produces
# exactly the right 120 month ends, so the notebook keeps it as an independent cross-check - but
# the query joins the table, not the range.




MonthEnd = model.Concept("MonthEnd", identify_by={"month_end": Date})

_month_end_scalars = scalar_properties(
    MonthEnd, SCHEMA_MI_MONTH_END_CALENDAR, exclude=("month_end",)
)
model.define(MonthEnd.new(month_end=MI_MONTH_END_CALENDAR.month_end))
bind_scalars(
    MonthEnd,
    MI_MONTH_END_CALENDAR,
    {"month_end": MI_MONTH_END_CALENDAR.month_end},
    _month_end_scalars,
)


# ================================================================================================
# core_schedule.py
# ================================================================================================
# core_schedule.py - UC2: schedules, routes, route states and the change/amendment evidence.
#
# **This module contains the demo's central semantic beat, and it is one line long.**
#
# The customer's Neo4j model versions state by ``(schedule_key, valid_from)`` but hangs it off
# ``ROUTE`` via ``(ROUTE)-[:HAS]->(ROUTE_STATE)``. A generic SCD Type 2 builder has exactly one
# structural assumption - at most one open ``valid_to`` per parent key - so their builder has to be
# told, per relationship, that the partition is ``schedule_key`` and not the parent ``route``.
# Nothing in the graph schema records that. Get it wrong and you either close states that should
# stay open or you raise an integrity error on a route that legitimately has hundreds of
# concurrent open schedules.
#
# In RAI there is nothing to relax, because there was never a constraint to relax:
#
# .. code-block:: python
#
#     RouteState = model.Concept("RouteState", identify_by={"route_state_key": String})
#
# ``Route`` does not appear in that identity. The versioning partition is therefore a structural,
# readable property of the ontology sitting in one line a reviewer can check, rather than a
# parameter passed to a builder. And because cardinality in RAI is declared per relationship and
# points one way, ``Route.states`` - an ``.alt()`` reading over the same fields as
# ``RouteState.route`` - carries no cardinality claim at all. Multi-open is the default; single-open
# is what you would have to opt into.
#
# Measured, live: at knowledge date 2026-08-31 the route ``SFO->LAX`` has **1,339 concurrent open
# route states**, and one query returns them without error. The mirror-image mistake is one
# reversed arrow away and fails loudly - ``Route.current_state = model.Property(...)`` raises
# ``FDError: Found non-unique values`` naming the offending relation and printing the two
# conflicting hashes. Note for the talk track: it fails at the **first evaluation** of the
# relation, after 13-19 seconds of engine work, not at define time. Saying "define time" on stage
# would be a factual error the audience can check on screen.
#
# One honest limitation, stated because the credibility of the limitations list matters: RAI
# cannot *express* "this route may have many concurrent open states" as a positive assertion.
# ``SD/std/constraints.py`` offers ``unique``, ``exclusive``, ``anyof`` and ``oneof`` and nothing
# else - there is no minimum-cardinality or negative-constraint vocabulary. The property is proved
# by a query returning ``open_states > 1``, which is what HT-18 asks for, not by a declaration.
#
# ``Schedule`` is identity-only, deliberately. SS-02 ``schedule_key_readable`` is tempting to hang
# on it and is per-*observation* lineage that can legitimately differ across snapshots for the
# same key, so a ``Property`` on ``Schedule`` would ``FDError``. It lives on ``RouteState`` and on
# ``ScheduleObservation`` instead.




# --- Schedule (SS-01) - identity only ---------------------------------------------

Schedule = model.Concept("Schedule", identify_by={"schedule_key": String})

model.define(Schedule.new(schedule_key=MI_SCHEDULE_CANONICAL_OBSERVATION.schedule_key))
model.define(Schedule.new(schedule_key=MI_ROUTE_STATE.schedule_key))

# --- Route (DV-12) - carrier-agnostic and directional ------------------------------

Route = model.Concept("Route", identify_by={"route_id": String})

_route_scalars = scalar_properties(Route, SCHEMA_MI_ROUTE, exclude=("route_id",))
model.define(Route.new(route_id=MI_ROUTE.route_id))
bind_scalars(Route, MI_ROUTE, {"route_id": MI_ROUTE.route_id}, _route_scalars)

# Two same-type slots, so two separately role-labelled Properties rather than one two-slot
# Relationship. With a single Relationship, ``define(...)`` silently binds both slots to
# whichever column is listed first, collapsing origin and destination into the same entity.
Route.origin_airport = model.Property(f"{Route:route} starts at {Airport:origin_airport}")
Route.destination_airport = model.Property(
    f"{Route:route} ends at {Airport:destination_airport}"
)
model.define(
    Route.lookup(route_id=MI_ROUTE.route_id).origin_airport(
        Airport.lookup(airport_id=MI_ROUTE.origin_airport_id)
    )
).where(MI_ROUTE.origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    Route.lookup(route_id=MI_ROUTE.route_id).destination_airport(
        Airport.lookup(airport_id=MI_ROUTE.destination_airport_id)
    )
).where(MI_ROUTE.destination_airport_resolution_status == RESOLUTION_EXACT)

# --- RouteState (DV-13) - the multi-open case -------------------------------------

RouteState = model.Concept("RouteState", identify_by={"route_state_key": String})

_route_state_scalars = scalar_properties(
    RouteState, SCHEMA_MI_ROUTE_STATE, exclude=("route_state_key",)
)
model.define(RouteState.new(route_state_key=MI_ROUTE_STATE.route_state_key))
bind_scalars(
    RouteState,
    MI_ROUTE_STATE,
    {"route_state_key": MI_ROUTE_STATE.route_state_key},
    _route_state_scalars,
)

# The FD points from the state to its parents, which is the functional direction. Each state has
# exactly one route and one schedule; a route has as many concurrent states as the source says.
RouteState.route = model.Property(f"{RouteState:state} covers {Route:route}")
RouteState.schedule = model.Property(f"{RouteState:state} versions {Schedule:schedule}")

model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).route(
        Route.lookup(route_id=MI_ROUTE_STATE.route_id)
    )
)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).schedule(
        Schedule.lookup(schedule_key=MI_ROUTE_STATE.schedule_key)
    )
)

# The Neo4j ``HAS`` edge, recovered exactly. An ``.alt()`` reading refers to the *same*
# underlying relationship fields under a different name, so it adds a name and never an inverse
# FD. This is the line that makes multi-open free.
Route.states = RouteState.route.alt(f"{Route:route} has state {RouteState:state}")
Schedule.states = RouteState.schedule.alt(
    f"{Schedule:schedule} has version {RouteState:state}"
)

# DELIBERATELY ABSENT, and this comment must survive every refactor:
#   there is no ``unique(...)`` over the Route slot of ``Route.states``, and no
#   ``Route.current_state`` Property. SOURCE_CONTRACT.md: the one-open-per-route constraint is
#   *prohibited*. See constraints.py, where the absence is recorded next to the assertions that
#   are present.

# --- Carrier roles: two Properties, never one generic ``airline`` -----------------
#
# ATTRIBUTE_AUTHORITY.md: "SS-04 and SS-05 are separate carrier roles. No generic airline owner
# exists." The ``carrier_role`` query parameter selects which Property a query traverses, and a
# missing role is a clarification state at the API boundary (P0-09.1), never a default.
#
# Only an EXACT cardinality-one resolution creates the link. An ambiguous or unresolved carrier
# code cannot produce an airline-level market at all, and the raw code stays bound as a string so
# a failed resolution still shows the code rather than vanishing.

RouteState.marketing_airline = model.Property(
    f"{RouteState:state} marketed by {Airline:marketing_airline}"
)
RouteState.operating_airline = model.Property(
    f"{RouteState:state} operated by {Airline:operating_airline}"
)
RouteState.codeshare_airline = model.Property(
    f"{RouteState:state} codeshared with {Airline:codeshare_airline}"
)

model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).marketing_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.marketing_airline_id)
    )
).where(MI_ROUTE_STATE.marketing_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).operating_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.operating_airline_id)
    )
).where(MI_ROUTE_STATE.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).codeshare_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.codeshare_airline_id)
    )
).where(MI_ROUTE_STATE.codeshare_airline_resolution_status == RESOLUTION_EXACT)

Airline.commercializes = RouteState.marketing_airline.alt(
    f"{Airline:marketing_airline} commercializes {RouteState:state}"
)
Airline.operates = RouteState.operating_airline.alt(
    f"{Airline:operating_airline} operates {RouteState:state}"
)

RouteState.origin_airport = model.Property(
    f"{RouteState:state} departs {Airport:origin_airport}"
)
RouteState.destination_airport = model.Property(
    f"{RouteState:state} arrives {Airport:destination_airport}"
)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).origin_airport(
        Airport.lookup(airport_id=MI_ROUTE_STATE.origin_airport_id)
    )
).where(MI_ROUTE_STATE.origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).destination_airport(
        Airport.lookup(airport_id=MI_ROUTE_STATE.destination_airport_id)
    )
).where(MI_ROUTE_STATE.destination_airport_resolution_status == RESOLUTION_EXACT)

# --- RouteStateSnapshotLineage ----------------------------------------------------
#
# Many contributing snapshots coalesce into one route state, so this is an association concept
# with its own identity rather than a property. Grain verified live: 60,076 rows, 60,076 distinct
# (route_state_key, publish_date, normalized_row_hash) tuples.

RouteStateSnapshotLineage = model.Concept(
    "RouteStateSnapshotLineage",
    identify_by={"route_state": RouteState, "publish_date": Date, "row_hash": String},
)

_rs_lineage_scalars = scalar_properties(
    RouteStateSnapshotLineage,
    SCHEMA_MI_ROUTE_STATE_LINEAGE,
    exclude=("route_state_key", "publish_date", "normalized_row_hash"),
)


def _rs_lineage_key() -> dict:
    return {
        "route_state": RouteState.lookup(
            route_state_key=MI_ROUTE_STATE_LINEAGE.route_state_key
        ),
        "publish_date": MI_ROUTE_STATE_LINEAGE.publish_date,
        "row_hash": MI_ROUTE_STATE_LINEAGE.normalized_row_hash,
    }


model.define(RouteStateSnapshotLineage.new(**_rs_lineage_key()))
bind_scalars(
    RouteStateSnapshotLineage,
    MI_ROUTE_STATE_LINEAGE,
    _rs_lineage_key(),
    _rs_lineage_scalars,
)

RouteState.lineage = model.Relationship(
    f"{RouteState:state} was contributed by {RouteStateSnapshotLineage:lineage}"
)
model.define(RouteState.lineage(RouteStateSnapshotLineage)).where(
    RouteStateSnapshotLineage.route_state == RouteState
)

# --- ScheduleObservation (SS-01, SS-03) -------------------------------------------
#
# The canonical per-snapshot observation with the watched SS-04..SS-38 payload. Grain verified
# live: 69,998 rows, 69,998 distinct (schedule_key, publish_date). This is the concept Q05
# compares across adjacent eligible snapshot dates.

ScheduleObservation = model.Concept(
    "ScheduleObservation", identify_by={"schedule": Schedule, "publish_date": Date}
)

_observation_scalars = scalar_properties(
    ScheduleObservation,
    SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION,
    exclude=("schedule_key", "publish_date"),
)


def _observation_key() -> dict:
    return {
        "schedule": Schedule.lookup(
            schedule_key=MI_SCHEDULE_CANONICAL_OBSERVATION.schedule_key
        ),
        "publish_date": MI_SCHEDULE_CANONICAL_OBSERVATION.publish_date,
    }


model.define(ScheduleObservation.new(**_observation_key()))
bind_scalars(
    ScheduleObservation,
    MI_SCHEDULE_CANONICAL_OBSERVATION,
    _observation_key(),
    _observation_scalars,
)

Schedule.observations = model.Relationship(
    f"{Schedule:schedule} was observed as {ScheduleObservation:observation}"
)
model.define(Schedule.observations(ScheduleObservation)).where(
    ScheduleObservation.schedule == Schedule
)

# ROUTE_ID is non-null on 69,993 of 69,998 observations; the five without one keep their identity
# and simply carry no route fact, which is the left-preserving behaviour P0-12.3 requires.
ScheduleObservation.route = model.Property(
    f"{ScheduleObservation:observation} covers {Route:route}"
)
model.define(
    ScheduleObservation.lookup(**_observation_key()).route(
        Route.lookup(route_id=MI_SCHEDULE_CANONICAL_OBSERVATION.route_id)
    )
)

ScheduleObservation.snapshot = model.Property(
    f"{ScheduleObservation:observation} was published on {SnapshotDate:snapshot}"
)
model.define(
    ScheduleObservation.lookup(**_observation_key()).snapshot(
        SnapshotDate.lookup(
            expected_publish_date=MI_SCHEDULE_CANONICAL_OBSERVATION.publish_date
        )
    )
)

# --- ScheduleComparison (DV-34) ---------------------------------------------------
#
# A Concept and not a per-invocation parameter, because Q05 must emit ``comparison_date``,
# ``previous_knowledge_date`` and ``crosses_snapshot_gap`` per comparison, and those are facts
# derived from the eligible ``SnapshotDate`` sequence rather than inputs supplied by the caller.
# Seven comparisons exist in the fixture.

ScheduleComparison = model.Concept("ScheduleComparison", identify_by={"comparison_id": String})

_comparison_scalars = scalar_properties(
    ScheduleComparison, SCHEMA_MI_SCHEDULE_COMPARISON, exclude=("comparison_id",)
)
model.define(ScheduleComparison.new(comparison_id=MI_SCHEDULE_COMPARISON.comparison_id))
bind_scalars(
    ScheduleComparison,
    MI_SCHEDULE_COMPARISON,
    {"comparison_id": MI_SCHEDULE_COMPARISON.comparison_id},
    _comparison_scalars,
)

ScheduleComparison.comparison_snapshot = model.Property(
    f"{ScheduleComparison:comparison} compares {SnapshotDate:comparison_snapshot}"
)
ScheduleComparison.previous_snapshot = model.Property(
    f"{ScheduleComparison:comparison} against {SnapshotDate:previous_snapshot}"
)
model.define(
    ScheduleComparison.lookup(
        comparison_id=MI_SCHEDULE_COMPARISON.comparison_id
    ).comparison_snapshot(
        SnapshotDate.lookup(expected_publish_date=MI_SCHEDULE_COMPARISON.comparison_date)
    )
)
model.define(
    ScheduleComparison.lookup(
        comparison_id=MI_SCHEDULE_COMPARISON.comparison_id
    ).previous_snapshot(
        SnapshotDate.lookup(
            expected_publish_date=MI_SCHEDULE_COMPARISON.previous_knowledge_date
        )
    )
)

# --- ScheduleExactChange ----------------------------------------------------------
#
# Exact presence-and-content facts. They stand on their own and are never consumed or replaced
# by the conservative amendment evidence below - NEO4J_PARITY_MATRIX.md lists "a candidate key
# shift is an exact schedule amendment" as a prohibited statement.
#
# Identity is the full four-tuple. FIELD_NAME is 100% non-null across all 12,040 rows (measured;
# a nullable identity component would silently drop the row - PROBE E3f took 48,000 rows down to
# 1 that way), and the tuple is unique.

ScheduleExactChange = model.Concept(
    "ScheduleExactChange",
    identify_by={
        "comparison": ScheduleComparison,
        "schedule_key": String,
        "change_kind": String,
        "field_name": String,
    },
)

_exact_change_scalars = scalar_properties(
    ScheduleExactChange,
    SCHEMA_MI_SCHEDULE_EXACT_CHANGE,
    exclude=("comparison_id", "schedule_key", "change_kind", "field_name"),
)


def _exact_change_key() -> dict:
    return {
        "comparison": ScheduleComparison.lookup(
            comparison_id=MI_SCHEDULE_EXACT_CHANGE.comparison_id
        ),
        "schedule_key": MI_SCHEDULE_EXACT_CHANGE.schedule_key,
        "change_kind": MI_SCHEDULE_EXACT_CHANGE.change_kind,
        "field_name": MI_SCHEDULE_EXACT_CHANGE.field_name,
    }


model.define(ScheduleExactChange.new(**_exact_change_key()))
bind_scalars(
    ScheduleExactChange,
    MI_SCHEDULE_EXACT_CHANGE,
    _exact_change_key(),
    _exact_change_scalars,
)

ScheduleExactChange.schedule = model.Property(
    f"{ScheduleExactChange:change} changed {Schedule:schedule}"
)
model.define(
    ScheduleExactChange.lookup(**_exact_change_key()).schedule(
        Schedule.lookup(schedule_key=MI_SCHEDULE_EXACT_CHANGE.schedule_key)
    )
)

# --- Amendment evidence (DV-35, DV-36, DV-37) -------------------------------------
#
# Kept structurally separate from the exact changes. A key-shift pair is reported as
# ``CANDIDATE_UNIQUE`` with ``exactness = CANDIDATE``, never promoted to a modification; where
# one removal is compatible with two additions the answer is an ambiguous group plus its members
# at LOW confidence with no pair chosen. Picking a winner by any tie-break is wrong.
#
# ``AMENDMENT_GROUP_ID`` is non-null on only 3 of 12,029 member rows (unpaired evidence carries
# none, per D-0020 A6), so the member identity is its own id column and the group link is an
# optional Property.

ScheduleAmendmentSide = model.Concept(
    "ScheduleAmendmentSide",
    identify_by={"comparison": ScheduleComparison, "schedule_key": String, "side": String},
)

_amendment_side_scalars = scalar_properties(
    ScheduleAmendmentSide,
    SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE,
    exclude=("comparison_id", "schedule_key", "side"),
)


def _amendment_side_key() -> dict:
    return {
        "comparison": ScheduleComparison.lookup(
            comparison_id=MI_SCHEDULE_AMENDMENT_SIDE.comparison_id
        ),
        "schedule_key": MI_SCHEDULE_AMENDMENT_SIDE.schedule_key,
        "side": MI_SCHEDULE_AMENDMENT_SIDE.side,
    }


model.define(ScheduleAmendmentSide.new(**_amendment_side_key()))
bind_scalars(
    ScheduleAmendmentSide,
    MI_SCHEDULE_AMENDMENT_SIDE,
    _amendment_side_key(),
    _amendment_side_scalars,
)

ScheduleAmendmentCandidate = model.Concept(
    "ScheduleAmendmentCandidate", identify_by={"candidate_id": String}
)
_amendment_candidate_scalars = scalar_properties(
    ScheduleAmendmentCandidate,
    SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE,
    exclude=("amendment_candidate_id",),
)
model.define(
    ScheduleAmendmentCandidate.new(
        candidate_id=MI_SCHEDULE_AMENDMENT_CANDIDATE.amendment_candidate_id
    )
)
bind_scalars(
    ScheduleAmendmentCandidate,
    MI_SCHEDULE_AMENDMENT_CANDIDATE,
    {"candidate_id": MI_SCHEDULE_AMENDMENT_CANDIDATE.amendment_candidate_id},
    _amendment_candidate_scalars,
)

ScheduleAmendmentGroup = model.Concept(
    "ScheduleAmendmentGroup", identify_by={"group_id": String}
)
_amendment_group_scalars = scalar_properties(
    ScheduleAmendmentGroup,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP,
    exclude=("amendment_group_id",),
)
model.define(
    ScheduleAmendmentGroup.new(group_id=MI_SCHEDULE_AMENDMENT_GROUP.amendment_group_id)
)
bind_scalars(
    ScheduleAmendmentGroup,
    MI_SCHEDULE_AMENDMENT_GROUP,
    {"group_id": MI_SCHEDULE_AMENDMENT_GROUP.amendment_group_id},
    _amendment_group_scalars,
)

ScheduleAmendmentGroupMember = model.Concept(
    "ScheduleAmendmentGroupMember", identify_by={"member_id": String}
)
_amendment_member_scalars = scalar_properties(
    ScheduleAmendmentGroupMember,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    exclude=("amendment_group_member_id",),
)
model.define(
    ScheduleAmendmentGroupMember.new(
        member_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id
    )
)
bind_scalars(
    ScheduleAmendmentGroupMember,
    MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    {"member_id": MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id},
    _amendment_member_scalars,
)

ScheduleAmendmentGroupMember.group = model.Property(
    f"{ScheduleAmendmentGroupMember:member} belongs to {ScheduleAmendmentGroup:group}"
)
model.define(
    ScheduleAmendmentGroupMember.lookup(
        member_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id
    ).group(
        ScheduleAmendmentGroup.lookup(
            group_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_id
        )
    )
)
ScheduleAmendmentGroup.members = model.Relationship(
    f"{ScheduleAmendmentGroup:group} has member {ScheduleAmendmentGroupMember:member}"
)
model.define(ScheduleAmendmentGroup.members(ScheduleAmendmentGroupMember)).where(
    ScheduleAmendmentGroupMember.group == ScheduleAmendmentGroup
)


# ================================================================================================
# core_flight.py
# ================================================================================================
# core_flight.py - the plan side, the actual side, and the optional bridge between them.
#
# Passenger flights and aircraft flights are **separate** and stay separate (BRIEF.md
# non-negotiable). Fulfillment is optional and asymmetric, and that asymmetry is the single
# cleanest demonstration in the whole model of what a directed ``Property`` plus an ``.alt()``
# inverse buys you:
#
# * ``AircraftFlight.fulfils`` is a ``Property``. The FD ``leg -> plan`` is enforced: one actual
#   leg fulfils at most one planned service.
# * ``PassengerFlight.fulfilled_by`` is the ``.alt()`` inverse over the *same* fields, so it
#   carries no FD. The stopover case - one planned passenger service fulfilled by several actual
#   legs - loads without error.
#
# A property-graph edge cannot express that pair without an out-of-band constraint.
#
# ``ExactFulfillment`` stays a separate association concept even though ``fulfils`` exists,
# because P0-10.6 requires candidates to be stored separately from confirmed fulfillment and the
# association carries DV-39, the evidence and the sanity-check outcome. ``fulfils`` is derived
# from ``ExactFulfillment`` **only**; ``FulfillmentCandidate`` never feeds it. That makes the
# exact/heuristic separation structural rather than a convention.
#
# Two code systems that must not be joined to each other: actual endpoints are ``SYN-AP-*``
# internal ids resolved against AP-01, planned endpoints are public IATA labels resolved against
# AP-04. Joining actual legs on IATA silently returns nothing.




# --- PassengerFlight (DV-20) - the plan side --------------------------------------

PassengerFlight = model.Concept(
    "PassengerFlight", identify_by={"passenger_flight_key": String}
)

_passenger_scalars = scalar_properties(
    PassengerFlight,
    SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL,
    exclude=("passenger_flight_key",),
)
model.define(
    PassengerFlight.new(
        passenger_flight_key=MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key
    )
)
bind_scalars(
    PassengerFlight,
    MI_PASSENGER_FLIGHT_CANONICAL,
    {"passenger_flight_key": MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key},
    _passenger_scalars,
)

# PH-02 ``schedule_key`` is bound as a ``Property`` from the canonical row, which by
# construction carries the DV-21 precedence-winning lineage observation's value. PROBE G-05
# passed only *vacuously* against the raw lineage - the one coalescing DV-20 key that absorbs
# two lineage rows has NULL PH-02 on both - so relying on that pass would have been relying on a
# fixture accident. Binding from the winner makes the functional dependency true by
# construction, which is what P0-10.3 requires anyway. Non-null on 7,951 of 19,446 canonical
# rows after the D-0023 enrichment; it was 1 of 19,996 before, which is why the binding had to
# be true by construction rather than by fixture accident.
PassengerFlight.schedule = model.Property(
    f"{PassengerFlight:plan} realises {Schedule:schedule}"
)
model.define(
    PassengerFlight.lookup(
        passenger_flight_key=MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key
    ).schedule(Schedule.lookup(schedule_key=MI_PASSENGER_FLIGHT_CANONICAL.schedule_key))
)

PassengerFlight.marketing_airline = model.Property(
    f"{PassengerFlight:plan} marketed by {Airline:marketing_airline}"
)
PassengerFlight.operating_airline = model.Property(
    f"{PassengerFlight:plan} operated by {Airline:operating_airline}"
)
PassengerFlight.planned_origin_airport = model.Property(
    f"{PassengerFlight:plan} planned from {Airport:planned_origin_airport}"
)
PassengerFlight.planned_destination_airport = model.Property(
    f"{PassengerFlight:plan} planned to {Airport:planned_destination_airport}"
)


def _plan_key() -> dict:
    return {"passenger_flight_key": MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key}


model.define(
    PassengerFlight.lookup(**_plan_key()).marketing_airline(
        Airline.lookup(airline_id=MI_PASSENGER_FLIGHT_CANONICAL.marketing_airline_id)
    )
).where(MI_PASSENGER_FLIGHT_CANONICAL.marketing_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    PassengerFlight.lookup(**_plan_key()).operating_airline(
        Airline.lookup(airline_id=MI_PASSENGER_FLIGHT_CANONICAL.operating_airline_id)
    )
).where(MI_PASSENGER_FLIGHT_CANONICAL.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    PassengerFlight.lookup(**_plan_key()).planned_origin_airport(
        Airport.lookup(airport_id=MI_PASSENGER_FLIGHT_CANONICAL.planned_origin_airport_id)
    )
).where(
    MI_PASSENGER_FLIGHT_CANONICAL.planned_origin_airport_resolution_status
    == RESOLUTION_EXACT
)
model.define(
    PassengerFlight.lookup(**_plan_key()).planned_destination_airport(
        Airport.lookup(
            airport_id=MI_PASSENGER_FLIGHT_CANONICAL.planned_destination_airport_id
        )
    )
).where(
    MI_PASSENGER_FLIGHT_CANONICAL.planned_destination_airport_resolution_status
    == RESOLUTION_EXACT
)

# --- PassengerSourceLineage -------------------------------------------------------
#
# Historical and forward lineage are BOTH retained (SOURCE_CONTRACT.md), which is why this is an
# association concept rather than a set of columns on the flight. ``IS_SELECTED_OBSERVATION``,
# ``SOURCE_PRECEDENCE_RANK`` and ``SELECTION_RANK`` are carried so the union precedence is
# auditable rather than implicit. Grain verified live: 19,998 rows, 19,998 distinct tuples.

PassengerSourceLineage = model.Concept(
    "PassengerSourceLineage",
    identify_by={
        "passenger_flight": PassengerFlight,
        "source_system": String,
        "source_row_token": String,
    },
)

_lineage_scalars = scalar_properties(
    PassengerSourceLineage,
    SCHEMA_MI_PASSENGER_SOURCE_LINEAGE,
    exclude=("passenger_flight_key", "source_system", "source_row_token"),
)


def _lineage_key() -> dict:
    return {
        "passenger_flight": PassengerFlight.lookup(
            passenger_flight_key=MI_PASSENGER_SOURCE_LINEAGE.passenger_flight_key
        ),
        "source_system": MI_PASSENGER_SOURCE_LINEAGE.source_system,
        "source_row_token": MI_PASSENGER_SOURCE_LINEAGE.source_row_token,
    }


model.define(PassengerSourceLineage.new(**_lineage_key()))
bind_scalars(
    PassengerSourceLineage,
    MI_PASSENGER_SOURCE_LINEAGE,
    _lineage_key(),
    _lineage_scalars,
)

PassengerFlight.lineage = model.Relationship(
    f"{PassengerFlight:plan} was observed as {PassengerSourceLineage:lineage}"
)
model.define(PassengerFlight.lineage(PassengerSourceLineage)).where(
    PassengerSourceLineage.passenger_flight == PassengerFlight
)

# --- PassengerPlannedLeg ----------------------------------------------------------
#
# The ordered planned station sequence. A single planned service with intermediate stops has
# several legs, which is what makes the stopover fulfillment case real.
#
# ``LEG_INDEX`` is ``NUMBER(9,0)`` and is declared ``Number.size(18, 0)``, not ``Integer`` and
# not ``Number.size(9, 0)``. The SDK buckets integer precision by bit width, so every
# ``NUMBER(p,0)`` with ``p <= 18`` discovers as ``Decimal(18,0)``; declaring the column's own
# precision instead relies on an undocumented leniency, and declaring ``Integer``
# (``Number.size(38, 0)``) would be a silent all-NaN column. See ``_regen_sources.derive_type``
# for the ``NUMBER(19,0)`` case where getting this wrong cost 600 values.

PassengerPlannedLeg = model.Concept(
    "PassengerPlannedLeg",
    identify_by={"passenger_flight": PassengerFlight, "leg_index": Number.size(18, 0)},
)

_planned_leg_scalars = scalar_properties(
    PassengerPlannedLeg,
    SCHEMA_MI_PASSENGER_PLANNED_LEG,
    exclude=("passenger_flight_key", "leg_index"),
)


def _planned_leg_key() -> dict:
    return {
        "passenger_flight": PassengerFlight.lookup(
            passenger_flight_key=MI_PASSENGER_PLANNED_LEG.passenger_flight_key
        ),
        "leg_index": MI_PASSENGER_PLANNED_LEG.leg_index,
    }


model.define(PassengerPlannedLeg.new(**_planned_leg_key()))
bind_scalars(
    PassengerPlannedLeg,
    MI_PASSENGER_PLANNED_LEG,
    _planned_leg_key(),
    _planned_leg_scalars,
)

PassengerFlight.planned_legs = model.Relationship(
    f"{PassengerFlight:plan} has planned leg {PassengerPlannedLeg:leg}"
)
model.define(PassengerFlight.planned_legs(PassengerPlannedLeg)).where(
    PassengerPlannedLeg.passenger_flight == PassengerFlight
)

# --- Invalid and quarantined passenger observations -------------------------------
#
# Retained with a deterministic identity plus a reason, never dropped. An observation that
# cannot form a DV-20 key is a fact about the source, not an absence.

InvalidPassengerObservation = model.Concept(
    "InvalidPassengerObservation",
    identify_by={"source_system": String, "stable_source_row_id": Integer},
)
_invalid_scalars = scalar_properties(
    InvalidPassengerObservation,
    SCHEMA_MI_PASSENGER_FLIGHT_INVALID,
    exclude=("source_system", "stable_source_row_id"),
)
model.define(
    InvalidPassengerObservation.new(
        source_system=MI_PASSENGER_FLIGHT_INVALID.source_system,
        stable_source_row_id=MI_PASSENGER_FLIGHT_INVALID.stable_source_row_id,
    )
)
bind_scalars(
    InvalidPassengerObservation,
    MI_PASSENGER_FLIGHT_INVALID,
    {
        "source_system": MI_PASSENGER_FLIGHT_INVALID.source_system,
        "stable_source_row_id": MI_PASSENGER_FLIGHT_INVALID.stable_source_row_id,
    },
    _invalid_scalars,
)

PassengerSourceQuarantine = model.Concept(
    "PassengerSourceQuarantine", identify_by={"quarantine_id": String}
)
_passenger_quarantine_scalars = scalar_properties(
    PassengerSourceQuarantine,
    SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE,
    exclude=("quarantine_id",),
)
model.define(
    PassengerSourceQuarantine.new(
        quarantine_id=MI_PASSENGER_SOURCE_QUARANTINE.quarantine_id
    )
)
bind_scalars(
    PassengerSourceQuarantine,
    MI_PASSENGER_SOURCE_QUARANTINE,
    {"quarantine_id": MI_PASSENGER_SOURCE_QUARANTINE.quarantine_id},
    _passenger_quarantine_scalars,
)

# --- AircraftFlight (AF-01) - the actual side -------------------------------------

AircraftFlight = model.Concept("AircraftFlight", identify_by={"flight_id": Integer})

_flight_scalars = scalar_properties(
    AircraftFlight, SCHEMA_MI_AIRCRAFT_FLIGHT, exclude=("flight_id",)
)
model.define(AircraftFlight.new(flight_id=MI_AIRCRAFT_FLIGHT.flight_id))
bind_scalars(
    AircraftFlight,
    MI_AIRCRAFT_FLIGHT,
    {"flight_id": MI_AIRCRAFT_FLIGHT.flight_id},
    _flight_scalars,
)


def _leg_key() -> dict:
    return {"flight_id": MI_AIRCRAFT_FLIGHT.flight_id}


# PROBE G-06: ``AircraftFlight.aircraft`` is functional (zero violating flight ids) but the
# inverse is 1..13 flights per aircraft, so the inverse must be multi-valued. Easy to get
# backwards, and a ``Property`` on the inverse would FDError on the first aircraft with two legs.
AircraftFlight.aircraft = model.Property(f"{AircraftFlight:leg} was flown by {Aircraft:aircraft}")
model.define(
    AircraftFlight.lookup(**_leg_key()).aircraft(
        Aircraft.lookup(id=MI_AIRCRAFT_FLIGHT.aircraft_id)
    )
)
Aircraft.actual_flights = AircraftFlight.aircraft.alt(
    f"{Aircraft:aircraft} flew {AircraftFlight:leg}"
)

# Two same-type slots again, so two role-labelled Properties. AF-09 ``actual`` arrival is
# DV-45 and is the continuity endpoint; AF-10 ``diverted`` never repairs it.
AircraftFlight.actual_origin = model.Property(
    f"{AircraftFlight:leg} started at {Airport:actual_origin}"
)
AircraftFlight.actual_destination = model.Property(
    f"{AircraftFlight:leg} ended at {Airport:actual_destination}"
)
AircraftFlight.diverted_airport = model.Property(
    f"{AircraftFlight:leg} diverted to {Airport:diverted_airport}"
)
model.define(
    AircraftFlight.lookup(**_leg_key()).actual_origin(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.actual_origin_airport_id)
    )
).where(MI_AIRCRAFT_FLIGHT.actual_origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    AircraftFlight.lookup(**_leg_key()).actual_destination(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.actual_destination_airport_id)
    )
).where(
    MI_AIRCRAFT_FLIGHT.actual_destination_airport_resolution_status == RESOLUTION_EXACT
)
model.define(
    AircraftFlight.lookup(**_leg_key()).diverted_airport(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.diverted_airport_id)
    )
).where(MI_AIRCRAFT_FLIGHT.diverted_airport_resolution_status == RESOLUTION_EXACT)

AircraftFlight.operating_airline = model.Property(
    f"{AircraftFlight:leg} was operated by {Airline:operating_airline}"
)
AircraftFlight.marketing_airline = model.Property(
    f"{AircraftFlight:leg} was marketed by {Airline:marketing_airline}"
)
model.define(
    AircraftFlight.lookup(**_leg_key()).operating_airline(
        Airline.lookup(airline_id=MI_AIRCRAFT_FLIGHT.operating_airline_id)
    )
).where(MI_AIRCRAFT_FLIGHT.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    AircraftFlight.lookup(**_leg_key()).marketing_airline(
        Airline.lookup(airline_id=MI_AIRCRAFT_FLIGHT.marketing_airline_id)
    )
).where(MI_AIRCRAFT_FLIGHT.marketing_airline_resolution_status == RESOLUTION_EXACT)

# The raw AF-20 self-reference, chained through a lookup on both ends so the target must already
# exist. PROBE G-06 found exactly one dangling ``NEXT_FLIGHT_ID`` in the fixture - the
# ``MISSING_TARGET`` anomaly - and this binding silently produces no fact for it, which is the
# intended behaviour. ``RotationLinkValidation`` is the thing that surfaces it.
AircraftFlight.next_flight_raw = model.Property(
    f"{AircraftFlight:leg} points to next {AircraftFlight:next_leg_raw}"
)
model.define(
    AircraftFlight.lookup(flight_id=MI_AIRCRAFT_FLIGHT.flight_id).next_flight_raw(
        AircraftFlight.lookup(flight_id=MI_AIRCRAFT_FLIGHT.next_flight_id)
    )
)

# --- RotationLinkValidation (DV-24, DV-25) ----------------------------------------
#
# One row per candidate edge, plus a terminal row per leg whose target token is the literal
# ``NO_TARGET``. Grain verified live: 3,900 rows, 3,900 distinct (flight_id, target_token), of
# which 2 are ``ACCEPTED``, 3 ``EXCLUDED``, 9 ``REJECTED`` and 3,886 ``TERMINAL_NO_TARGET``.

RotationLinkValidation = model.Concept(
    "RotationLinkValidation",
    identify_by={"flight": AircraftFlight, "target_token": String},
)

_rotation_scalars = scalar_properties(
    RotationLinkValidation,
    SCHEMA_MI_ROTATION_LINK_VALIDATION,
    exclude=("flight_id", "target_token"),
)


def _rotation_key() -> dict:
    return {
        "flight": AircraftFlight.lookup(flight_id=MI_ROTATION_LINK_VALIDATION.flight_id),
        "target_token": MI_ROTATION_LINK_VALIDATION.target_token,
    }


model.define(RotationLinkValidation.new(**_rotation_key()))
bind_scalars(
    RotationLinkValidation,
    MI_ROTATION_LINK_VALIDATION,
    _rotation_key(),
    _rotation_scalars,
)

RotationLinkValidation.target_flight = model.Property(
    f"{RotationLinkValidation:validation} validates target {AircraftFlight:target_flight}"
)
model.define(
    RotationLinkValidation.lookup(**_rotation_key()).target_flight(
        AircraftFlight.lookup(flight_id=MI_ROTATION_LINK_VALIDATION.target_flight_id)
    )
)

AircraftFlight.rotation_validations = model.Relationship(
    f"{AircraftFlight:leg} was validated by {RotationLinkValidation:validation}"
)
model.define(AircraftFlight.rotation_validations(RotationLinkValidation)).where(
    RotationLinkValidation.flight == AircraftFlight
)

# --- Fulfillment: exact, candidate, and ambiguous ---------------------------------

ExactFulfillment = model.Concept(
    "ExactFulfillment", identify_by={"exact_fulfillment_id": String}
)
_exact_fulfillment_scalars = scalar_properties(
    ExactFulfillment, SCHEMA_MI_FULFILLMENT_EXACT, exclude=("exact_fulfillment_id",)
)
model.define(
    ExactFulfillment.new(exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id)
)
bind_scalars(
    ExactFulfillment,
    MI_FULFILLMENT_EXACT,
    {"exact_fulfillment_id": MI_FULFILLMENT_EXACT.exact_fulfillment_id},
    _exact_fulfillment_scalars,
)

ExactFulfillment.actual_flight = model.Property(
    f"{ExactFulfillment:fulfillment} confirms leg {AircraftFlight:actual_flight}"
)
ExactFulfillment.passenger_flight = model.Property(
    f"{ExactFulfillment:fulfillment} confirms plan {PassengerFlight:passenger_flight}"
)
model.define(
    ExactFulfillment.lookup(
        exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id
    ).actual_flight(AircraftFlight.lookup(flight_id=MI_FULFILLMENT_EXACT.actual_flight_id))
)
model.define(
    ExactFulfillment.lookup(
        exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id
    ).passenger_flight(
        PassengerFlight.lookup(
            passenger_flight_key=MI_FULFILLMENT_EXACT.passenger_flight_key
        )
    )
)

FulfillmentCandidate = model.Concept(
    "FulfillmentCandidate", identify_by={"candidate_id": String}
)
_fulfillment_candidate_scalars = scalar_properties(
    FulfillmentCandidate,
    SCHEMA_MI_FULFILLMENT_CANDIDATE,
    exclude=("fulfillment_candidate_id",),
)
model.define(
    FulfillmentCandidate.new(
        candidate_id=MI_FULFILLMENT_CANDIDATE.fulfillment_candidate_id
    )
)
bind_scalars(
    FulfillmentCandidate,
    MI_FULFILLMENT_CANDIDATE,
    {"candidate_id": MI_FULFILLMENT_CANDIDATE.fulfillment_candidate_id},
    _fulfillment_candidate_scalars,
)

# D-0020 A6: unmatched actual and passenger observations live here at member grain with a NULL
# group id, because that contract row is where "unmatched observations retain a deterministic
# identity plus reason" is written. ``FULFILLMENT_GROUP_ID`` is non-null on only 3 of 23,887
# rows, so the identity is the member id and the group link is an optional Property.
FulfillmentGroupMember = model.Concept(
    "FulfillmentGroupMember", identify_by={"member_id": String}
)
_fulfillment_member_scalars = scalar_properties(
    FulfillmentGroupMember,
    SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP,
    exclude=("fulfillment_group_member_id",),
)
model.define(
    FulfillmentGroupMember.new(
        member_id=MI_FULFILLMENT_AMBIGUOUS_GROUP.fulfillment_group_member_id
    )
)
bind_scalars(
    FulfillmentGroupMember,
    MI_FULFILLMENT_AMBIGUOUS_GROUP,
    {"member_id": MI_FULFILLMENT_AMBIGUOUS_GROUP.fulfillment_group_member_id},
    _fulfillment_member_scalars,
)

# --- The asymmetric fulfillment link ----------------------------------------------
#
# Derived from ``ExactFulfillment`` only. ``FulfillmentCandidate`` never feeds it: that is the
# exact/heuristic separation, made structural rather than documented.

AircraftFlight.fulfils = model.Property(
    f"{AircraftFlight:leg} fulfilled {PassengerFlight:plan}"
)
model.define(AircraftFlight.fulfils(PassengerFlight)).where(
    ExactFulfillment.actual_flight == AircraftFlight,
    ExactFulfillment.passenger_flight == PassengerFlight,
)
PassengerFlight.fulfilled_by = AircraftFlight.fulfils.alt(
    f"{PassengerFlight:plan} was fulfilled by {AircraftFlight:leg}"
)


# ================================================================================================
# temporal.py
# ================================================================================================
# temporal.py - the shared temporal predicate layer. Pure; no model rules of its own.
#
# **This module is the demo's central differentiation claim.** ``NEO4J_PARITY_MATRIX.md`` sells
# "one reusable semantic model for the eight bounded workloads instead of query-local temporal
# rules". If any of the predicates below get retyped inside ``uc1.py``, ``uc2.py`` or
# ``rotation.py``, that claim stops being true, and the four questions that resolve the same
# as-of instant (Q01 at a parameter date, Q03 at 120 month ends, Q04 across the whole stream, Q08
# at each leg's AF-06) get four independent chances to put the exclusive bound on the wrong side.
#
# RAI 1.20.1 has **no temporal support at all**. A search of the whole ``semantics`` tree for
# ``valid_from``, ``bitemporal``, ``as_of``, ``effective_from`` and ``interval`` returns nothing:
# no interval type, no validity-annotated relationship, no as-of operator. Every predicate here is
# therefore a hand-written conjunction over two ``Date`` properties. That is honest parity with a
# property graph, which has none either - and it is the reason nothing in the API holds a
# "one open version per parent" assumption that would have to be relaxed for the multi-open route
# case (see ``core_schedule.py``).
#
# The functions return **tuples of conditions**, spread into ``model.where(*...)``. They are
# deliberately Python helpers and not model relationships: a materialized
# ``visible_on(assignment, Date)`` rule would range over the unbounded extension of the ``Date``
# core concept and either fail to ground or explode. The two places where the date set *is*
# bounded by an entity - Q03's ``MonthEnd`` and Q08's ``AircraftFlight`` - do get real
# materialized model rules, in ``computed_aircraft.py`` and ``computed_rotation.py``.
#
# The two interval conventions are NOT interchangeable and must never share one helper:
#
# * **knowledge / validity is half-open**: ``valid_from <= d < valid_to``.
# * **operating is inclusive at both ends**: ``effective_date <= d <= discontinue_date``.
#
# ``SEMANTIC_DECISIONS.md``: "Knowledge ``valid_to`` is excluded; source operating
# ``discontinue_date`` is included." A single generic helper applied to both would silently make
# the operating upper bound exclusive, lose the last operating day, and break nine rows of the
# frozen ``TT-BOTH-CLOCKS`` truth table while still returning a plausible answer. Hence
# :func:`visible_on` / :func:`known_on` (half-open) and :func:`operates_on` (inclusive) are
# separate functions with deliberately different names.





# --- Half-open predicates ---------------------------------------------------------


def visible_on(assignment, d):
    """``valid_from <= d < valid_to`` on a daily assignment. P0-02.1 / BRIEF.md.

    Safe without a null guard on the upper bound because DATA-04 guarantees ``VALID_TO`` is
    never NULL: the open case is written as the model sentinel ``9999-01-01``, never as NULL.
    Verified live - zero rows in ``AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT`` carry the *source*
    sentinel ``9999-12-31``, and ``computed_aircraft.SentinelLeak`` keeps proving it.
    """
    return (assignment.valid_from <= d, d < assignment.valid_to)


def within_existence(aircraft, d):
    """``existence_from <= d < existence_to``. D-0003 makes the finite EOL bound exclusive.

    ``Q01-EOL-BOUNDARY`` (aircraft 1002 at 2024-07-01) is the frozen test: all four dimensions
    must come back ``OUTSIDE_EXISTENCE``, which only happens with ``<`` and not ``<=``.
    """
    return (aircraft.existence_from <= d, d < aircraft.existence_to)


def known_on(state, knowledge_date):
    """``knowledge_valid_from <= k < knowledge_valid_to`` on a route state. DV-14 / DV-15.

    Shared derived predicate #4 in ``QUERY_ROUTING.md``: Q05 compares presence across adjacent
    eligible dates, Q06 compares counts seven days apart, Q07 uses it as one half of the
    two-clock filter. The half-open convention has to be byte-identical in all three or Q06's
    zero-crossings and Q07's ``active_schedule_count`` disagree about the same schedule.

    Note ``AT_END`` is ineligible: the knowledge bound is exclusive at the top, which is why
    three of the nine ``TT-BOTH-CLOCKS`` rows fail on this clause alone.
    """
    return (
        state.knowledge_valid_from <= knowledge_date,
        knowledge_date < state.knowledge_valid_to,
    )


# --- Inclusive predicate, plus the weekday join -----------------------------------


def operates_on(state, operating_date: dt.date, weekday_relationship=None):
    """``effective_date <= o <= discontinue_date`` **and** the weekday flag for ``o``.

    Inclusive on BOTH ends, deliberately - SS-09 ``discontinue_date`` is the last operating
    day, not the first excluded one. The ``<=`` on the second clause is the single most
    load-bearing character in this file.

    The weekday integer is computed in Python from the query parameter
    (``operating_date.isoweekday()``, ISO numbering, 1 = Monday) rather than from a RAI date
    part function. That removes any doubt about the day-numbering convention, and
    ``operating_date`` is a required typed parameter anyway (P0-08.3).
    """
    conditions = [
        state.operating_effective_date <= operating_date,
        operating_date <= state.operating_discontinue_date,
    ]
    if weekday_relationship is not None:
        conditions.append(weekday_relationship(state, operating_date.isoweekday()))
    return tuple(conditions)


def iso_weekday(operating_date: dt.date) -> int:
    """ISO weekday of a query parameter, 1 = Monday. Paired with SS-14..SS-20."""
    return operating_date.isoweekday()


# --- DV-33, the four-value as-of dimension status ---------------------------------


def dv33_branches(model, aircraft, assignment, d, *, scope=(), exact_target=None):
    """The four mutually exclusive DV-33 branch condition sets, for one dimension at one date.

    ``scope`` is **required in practice** and is the clauses that restrict ``assignment`` to a
    single dimension - either ``(assignment.dimension == DIM_AIRCRAFT_TYPE,)`` or the subtype
    membership ``(AircraftTypeDaily(assignment),)``. Omitting it is a silent wrong answer, not
    an error, and it cost a live test failure to find: ``AircraftDimensionDailyAssignment`` is
    one physical concept with a ``dimension`` discriminator, so an unscoped ``assignment`` ranges
    over all four dimensions. Aircraft 1001 at 2022-05-15 then reported both ``OK`` (its
    ``aircraft_type`` assignment resolves to ``SYN-TYPE-B``) *and* ``UNKNOWN_STATE`` (its
    ``aircraft_state`` assignment covers the same date and has no ``aircraft_type`` value).
    P0-01.5 makes change detection per dimension; this parameter is where that becomes real.

    The scope is folded into the covering clauses, so it applies inside the negations too - a
    ``NO_RECORDED_STATE`` that ignored the dimension would be answering a different question.

    ``exact_target`` is the optional-target **property chain itself** - for example
    ``typ.aircraft_type`` - and not a comparison. That distinction is the difference between a
    correct classification and a silently overlapping one, and it cost a live test failure to
    find:

    ``model.not_(typ.aircraft_type == AircraftType)`` reads as "there exists some ``AircraftType``
    that this assignment's type is not equal to", which is true for **every** assignment as soon
    as the model holds two aircraft types. Measured: aircraft 1001 at 2022-05-15 fired both
    ``OK`` and ``UNKNOWN_STATE``. The correct negation is over the property's *existence* -
    ``model.not_(typ.aircraft_type)`` - which is the documented shape for "entities without this
    relationship". Binding the bare chain in ``where()`` conversely requires a value to exist,
    so the positive branch is just the chain.

    Returns ``[(status_token, (conditions...)), ...]`` in the contract's strict order. The
    caller spreads each condition tuple into its own ``model.where(...)`` and tags the result
    with the token, which keeps the classification defined exactly once for Q01, Q03, Q04 and
    Q08. A caller that also needs the resolved target in its projection adds its own
    ``assignment.aircraft_type == AircraftType`` clause to the ``OK`` branch.

    Why this is a builder and not an ordered ``|`` fallback, which is what
    ``ONTOLOGY_DESIGN.md`` section 5.3 specified: **the written form does not compile.** PROBE
    D7 ran section 5.3's exact shape and it raised ``[Unground Variable] Variable 'ty' is
    unground`` - ``|`` requires every branch to ground the same variables, and these four
    branches deliberately do not. PROBE D10 then confirmed the same four outcomes are correct
    and stable when authored as mutually exclusive conditions. Separately, ``| None`` raises
    outright (``AttributeError`` inside ``front_compiler``), so the frozen ``null`` cells in
    ``EXPECTED_ANSWERS.yaml`` come from a plain dot-chain rendering absence as ``NaN``, never
    from a ``None`` fallback.

    Mutual exclusivity is structural, not incidental - ``<`` on one boundary and ``>=`` on the
    other - because overlapping conditions on a single derived ``Property`` are an ``FDError``.

    Two of the four values are the presence of a covering assignment and DATA-04 already
    decides between them on the row (``DIMENSION_QUERY_STATUS``, measured live: exactly two
    distinct values, ``OK`` and ``UNKNOWN_STATE``). The other two are the *absence* of a
    covering assignment and can only be decided against a date, which is why they cannot be
    materialized on any row and why this function exists.
    """
    inside = within_existence(aircraft, d)
    covers = (*scope, assignment.aircraft == aircraft, *visible_on(assignment, d))
    covered = (*inside, *covers)

    branches = [(DV33_OUTSIDE_EXISTENCE, (model.not_(*inside),))]
    if exact_target is not None:
        branches.append((DV33_OK, (*covered, exact_target)))
        branches.append((DV33_UNKNOWN_STATE, (*covered, model.not_(exact_target))))
    else:
        branches.append((DV33_OK, covered))
    # ``not_(A, B, C)`` is NOT(A AND B AND C), and ``assignment`` appears nowhere else in this
    # branch, so this reads as "no assignment covers the date" - which is exactly
    # NO_RECORDED_STATE: inside existence, before the first assignment or in a real gap.
    branches.append((DV33_NO_RECORDED_STATE, (*inside, model.not_(*covers))))
    return branches


# ================================================================================================
# computed_aircraft.py
# ================================================================================================
# computed_aircraft.py - the reusable derived layer over UC1. This is where the RAI content is.
#
# Everything above this file is plumbing: identity, source binding, and two half-open ``Date``
# columns. Everything the demo actually argues about lives here.
#
# Six groups of rules:
#
# 1. **Dimension subtypes.** One physical assignment table with a ``dimension`` discriminator
#    becomes four named streams. ``identity_includes_type`` stays ``False``, so the subtype
#    instance *is* its parent entity - one assignment, viewed through its dimension. This buys two
#    things. The four independent clocks in Q01 become four visibly independent joins in the query
#    code, which is the point of the demo. And Q02 can rank status observations ``.per(Aircraft)``
#    instead of ``.per(Aircraft, dimension)``.
# 1b. **Four dimension-scoped edges off ``Aircraft`` plus three direct one-hop readings**, so the
#    supplied Neo4j edge structure is visible on the concept rather than recoverable only through a
#    subtype predicate (FIDELITY-01 A2 / A3).
# 2. **The dense ordinals** that turn "the previous assignment" and "the next qualifying
#    assignment" from a four-column lexicographic comparison into one integer comparison.
# 3. **Q04's reconciliation properties**, ``previous_definition_id`` and the three-valued
#    ``is_type_change``.
# 4. **Q03's month-end rule** - the demo's headline reusable temporal rule, where the type clock
#    and the status clock are two independent half-open joins in one rule, visibly not aligned.
# 5. **Two integrity guards** that RAI cannot declare, so it derives them and the gate asserts
#    they are empty.
#
# One thing that is deliberately *not* here: the four-value DV-33 as-of status is not a
# materialized property, because it is a function of a date and ``Date`` has an unbounded
# extension. ``DIMENSION_QUERY_STATUS`` on the row already decides the two present-row values
# (measured live: exactly ``OK`` 97,975 and ``UNKNOWN_STATE`` 4), and ``temporal.dv33_branches``
# owns the two absence values. See that function's docstring for why section 5.3's ``|`` chain
# could not be used.




# --- 1. Dimension subtypes --------------------------------------------------------

AircraftStateDaily = model.Concept("AircraftStateDailyAssignment", extends=[DailyAssignment])
AircraftTypeDaily = model.Concept("AircraftTypeDailyAssignment", extends=[DailyAssignment])
EngineTypeDaily = model.Concept("EngineTypeDailyAssignment", extends=[DailyAssignment])
AircraftStatusDaily = model.Concept("AircraftStatusDailyAssignment", extends=[DailyAssignment])

model.define(AircraftStateDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_AIRCRAFT_STATE
)
model.define(AircraftTypeDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_AIRCRAFT_TYPE
)
model.define(EngineTypeDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_ENGINE_TYPE
)
model.define(AircraftStatusDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_AIRCRAFT_STATUS
)

AircraftStateAudit = model.Concept("AircraftStateAuditAssignment", extends=[AuditAssignment])
AircraftTypeAudit = model.Concept("AircraftTypeAuditAssignment", extends=[AuditAssignment])
EngineTypeAudit = model.Concept("EngineTypeAuditAssignment", extends=[AuditAssignment])
AircraftStatusAudit = model.Concept("AircraftStatusAuditAssignment", extends=[AuditAssignment])

model.define(AircraftStateAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_AIRCRAFT_STATE
)
model.define(AircraftTypeAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_AIRCRAFT_TYPE
)
model.define(EngineTypeAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_ENGINE_TYPE
)
model.define(AircraftStatusAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_AIRCRAFT_STATUS
)

# --- 1b. Neo4j edge fidelity: four scoped edges and three direct one-hop readings --
#
# FIDELITY-01 findings A2 and A3. The supplied Neo4j model has **four independently clocked
# edges** off ``AIRCRAFT`` - ``HAS``, ``CONFORMED``, ``EQUIPPED``, ``ASSIGNED`` - and in Cypher
# the edge *type* is the dimension scope, so their query cannot make the mistake ours can. Ours
# already did: aircraft 1001 at 2022-05-15 reported both ``OK`` and ``UNKNOWN_STATE`` because an
# unscoped assignment ref ranged over all four dimensions. The ``scope`` parameter on
# ``temporal.dv33_branches`` is a guard rail; these four relationships are the modelling answer,
# so ``Aircraft`` has four visibly distinct outbound edges rather than one plus a predicate.
#
# Additive on purpose. ``Aircraft.daily_assignments`` and ``Aircraft.audit_assignments`` stay for
# the general case, the underlying assignment concept is untouched, and every existing query
# keeps working.

Aircraft.state_assignments = model.Relationship(
    f"{Aircraft:aircraft} has state {DailyAssignment:assignment}"
)
Aircraft.type_assignments = model.Relationship(
    f"{Aircraft:aircraft} has type assignment {DailyAssignment:assignment}"
)
Aircraft.engine_assignments = model.Relationship(
    f"{Aircraft:aircraft} has engine assignment {DailyAssignment:assignment}"
)
Aircraft.status_assignments = model.Relationship(
    f"{Aircraft:aircraft} has status assignment {DailyAssignment:assignment}"
)

model.define(Aircraft.state_assignments(DailyAssignment)).where(
    AircraftStateDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)
model.define(Aircraft.type_assignments(DailyAssignment)).where(
    AircraftTypeDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)
model.define(Aircraft.engine_assignments(DailyAssignment)).where(
    EngineTypeDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)
model.define(Aircraft.status_assignments(DailyAssignment)).where(
    AircraftStatusDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)

# The direct one-hop edges, carrying the two Neo4j edge properties. This is the closest possible
# match to ``(AIRCRAFT)-[:CONFORMED]->(AIRCRAFT_TYPE) {valid_from, valid_to}``: one hop from
# ``Aircraft`` to the definition node with the validity interval on the edge itself, exactly
# where a Cypher-literate reviewer looks for it. Without these, every one-hop pattern on
# ``CONFORMED`` / ``EQUIPPED`` / ``ASSIGNED`` costs two hops plus a dimension predicate.
#
# ``Relationship`` and not ``Property``: an aircraft conforms to many types over time, so no
# direction is functional. Four fields is one more than the reading-quality guidance likes, and
# that is the deliberate trade - the fields are the supplied edge's own payload, and the
# two-hop path through the assignment remains available for everything else the assignment
# carries. Consumers should run ``inspect.fields()`` before binding, as for any multi-field
# relationship.

Aircraft.conformed_to = model.Relationship(
    f"{Aircraft:aircraft} conformed to {AircraftType:aircraft_type} "
    f"from {Date:valid_from} until {Date:valid_to}"
)
Aircraft.equipped_with = model.Relationship(
    f"{Aircraft:aircraft} equipped with {EngineType:engine_type} "
    f"from {Date:valid_from} until {Date:valid_to}"
)
Aircraft.assigned_status = model.Relationship(
    f"{Aircraft:aircraft} assigned status {AircraftStatus:status} "
    f"from {Date:valid_from} until {Date:valid_to}"
)

model.define(
    Aircraft.conformed_to(
        Aircraft, AircraftType, DailyAssignment.valid_from, DailyAssignment.valid_to
    )
).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.aircraft == Aircraft,
    DailyAssignment.aircraft_type == AircraftType,
)
model.define(
    Aircraft.equipped_with(
        Aircraft, EngineType, DailyAssignment.valid_from, DailyAssignment.valid_to
    )
).where(
    EngineTypeDaily(DailyAssignment),
    DailyAssignment.aircraft == Aircraft,
    DailyAssignment.engine_type == EngineType,
)
model.define(
    Aircraft.assigned_status(
        Aircraft, AircraftStatus, DailyAssignment.valid_from, DailyAssignment.valid_to
    )
).where(
    AircraftStatusDaily(DailyAssignment),
    DailyAssignment.aircraft == Aircraft,
    DailyAssignment.status == AircraftStatus,
)

# The two missing inverses (A3). Without these, "which aircraft were ever in Storage" cannot be
# entered from the status node the way it can in Cypher - ``AircraftStatus`` had zero
# relationships in the inventory. ``AircraftConfiguration`` had none either.
AircraftStatus.daily_assignments = model.Relationship(
    f"{AircraftStatus:status} was assigned by {DailyAssignment:assignment}"
)
model.define(AircraftStatus.daily_assignments(DailyAssignment)).where(
    DailyAssignment.status == AircraftStatus
)

AircraftConfiguration.daily_assignments = model.Relationship(
    f"{AircraftConfiguration:configuration} was read by {DailyAssignment:assignment}"
)
model.define(AircraftConfiguration.daily_assignments(DailyAssignment)).where(
    DailyAssignment.configuration == AircraftConfiguration
)

# --- 2. The dense ordinals (shared derivation #2 in QUERY_ROUTING.md) -------------
#
# Audit stream: DATA-04 already materializes the DV-03 dense ordinal over the canonical order
# tuple (AH-05 event_date, AH-03 row_sequence, AH-04 event_sequence, AH-01 event id) as
# ``DIMENSION_SEQUENCE``. Verified live: 3,996 (aircraft, dimension) groups, every one dense
# 1..n, zero violations. The MODEL_INPUT boundary says do not recompute a heavy derivation that
# Snowflake already owns, so ``event_ordinal`` is an alias that gives the ontology the
# vocabulary QUERY_ROUTING.md uses rather than a second window function.
#
# Do NOT substitute ``EVENT_ORDER_RANK``: it is dense per aircraft across all four dimensions
# on the audit stream (999 groups, 1 violation) and is *not* dense per (aircraft, dimension) on
# the daily stream (6 of 3,996 groups violate). Measured, not assumed.

AuditAssignment.event_ordinal = model.Property(
    f"{AuditAssignment:assignment} is at ordinal {Integer:event_ordinal}"
)
model.define(AuditAssignment.event_ordinal(AuditAssignment.dimension_sequence))

# Daily stream: there is no dense ordinal in MODEL_INPUT, so this one is a real PyRel rule.
# ``VALID_FROM`` is unique per (aircraft, dimension) - verified live, zero violations over all
# 3,996 groups - so ranking on it alone is total and deterministic. PROBE U-10 proved
# ``aggs.rank`` with ordering keys plus ``.per()`` materializes correctly as a ``Property``.
DailyAssignment.daily_ordinal = model.Property(
    f"{DailyAssignment:assignment} is at daily ordinal {Integer:daily_ordinal}"
)
model.define(
    DailyAssignment.daily_ordinal(
        aggs.rank(aggs.asc(DailyAssignment.valid_from)).per(
            DailyAssignment.aircraft, DailyAssignment.dimension
        )
    )
)

# --- 3. Q04 reconciliation: previous definition and the three-valued type change ---
#
# Two independently clocked streams placed side by side and never aligned to each other. The
# derivation is strictly *within* one stream: the previous assignment is the one at
# ``daily_ordinal - 1`` for the same aircraft *and the same dimension*, which is why the
# ordinal is partitioned by both.

DailyAssignment.previous_definition_id = model.Property(
    f"{DailyAssignment:assignment} follows definition {String:previous_definition_id}"
)

_prev_type = DailyAssignment.ref("prev_type")
model.define(
    DailyAssignment.previous_definition_id(_prev_type.exact_aircraft_type_subseries)
).where(
    AircraftTypeDaily(DailyAssignment),
    AircraftTypeDaily(_prev_type),
    _prev_type.aircraft == DailyAssignment.aircraft,
    _prev_type.daily_ordinal == DailyAssignment.daily_ordinal - 1,
)

_prev_engine = DailyAssignment.ref("prev_engine")
model.define(
    DailyAssignment.previous_definition_id(_prev_engine.exact_engine_type_subseries)
).where(
    EngineTypeDaily(DailyAssignment),
    EngineTypeDaily(_prev_engine),
    _prev_engine.aircraft == DailyAssignment.aircraft,
    _prev_engine.daily_ordinal == DailyAssignment.daily_ordinal - 1,
)

# ``is_type_change`` is three-valued, which is exactly why it is a rule and not a ``select``
# expression: ``false`` on the first assignment of the type stream, ``true`` on a real change,
# and *absent* (rendering as null) on every engine row. The three conditions are mutually
# exclusive by construction - first-of-stream has no previous value to compare, so the two
# comparison rules cannot reach it - and overlapping conditions on one derived ``Property``
# would be an ``FDError``.
DailyAssignment.is_type_change = model.Property(
    f"{DailyAssignment:assignment} changed type {Bool:is_type_change}"
)
model.define(DailyAssignment.is_type_change(False)).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.daily_ordinal == 1,
)
model.define(DailyAssignment.is_type_change(True)).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.previous_definition_id
    != DailyAssignment.exact_aircraft_type_subseries,
)
model.define(DailyAssignment.is_type_change(False)).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.previous_definition_id
    == DailyAssignment.exact_aircraft_type_subseries,
)

# --- 4. Q03: the bounded as-of rule that SHOULD be a model rule -------------------
#
# The demo's headline reusable temporal rule. The type clock and the status clock are two
# independent half-open joins in one rule, visibly not aligned to each other, and the calendar
# is a joined dimension rather than a parameter sweep - so the identical rule works for an
# irregular set of dates. Q03 is then a single ``count(Aircraft).per(MonthEnd, AircraftType)``
# over this relationship, not 120 queries.
#
# A ``Relationship``, not a ``Property``: the triple (aircraft, month end, type) is the fact,
# and one aircraft is in service on many month ends.

InServiceOnMonthEnd = model.Relationship(
    f"{Aircraft:aircraft} is in service on {MonthEnd:month_end} as {AircraftType:aircraft_type}"
)

_status_at_month_end = DailyAssignment.ref("status_at_month_end")
_type_at_month_end = DailyAssignment.ref("type_at_month_end")

model.define(InServiceOnMonthEnd(Aircraft, MonthEnd, AircraftType)).where(
    # existence, half-open, EOL exclusive (D-0003)
    Aircraft.existence_from <= MonthEnd.month_end,
    MonthEnd.month_end < Aircraft.existence_to,
    # the status clock
    AircraftStatusDaily(_status_at_month_end),
    _status_at_month_end.aircraft == Aircraft,
    _status_at_month_end.valid_from <= MonthEnd.month_end,
    MonthEnd.month_end < _status_at_month_end.valid_to,
    _status_at_month_end.aircraft_status_code == STATUS_IN_SERVICE,
    # the type clock, independently
    AircraftTypeDaily(_type_at_month_end),
    _type_at_month_end.aircraft == Aircraft,
    _type_at_month_end.valid_from <= MonthEnd.month_end,
    MonthEnd.month_end < _type_at_month_end.valid_to,
    _type_at_month_end.aircraft_type == AircraftType,
)

# --- 5. Integrity guards RAI cannot declare ---------------------------------------
#
# ``SD/std/constraints.py`` offers ``unique``, ``exclusive``, ``anyof`` and ``oneof`` and
# nothing else: there is no negative-constraint or minimum-cardinality vocabulary. And PROBE
# U-04 showed ``require(unique(...))`` is a silent no-op in 1.20.1 with *and* without
# ``emit_constraints: True``. So a real guard is a derived flag plus a zero-count assertion in
# the gate, which is what these two are.

# HT-06: the source "unknown future" sentinel must never reach the model. DATA-04 normalises
# 9999-12-31 to NULL plus a companion ``*_IS_UNKNOWN_FUTURE`` boolean, so "unknown future" in
# RAI is the absence of a value plus a flag, never a magic date. Measured live: zero rows.
SentinelLeak = model.Relationship(
    f"{DailyAssignment:assignment} leaked the source unknown-future sentinel"
)
model.define(SentinelLeak(DailyAssignment)).where(
    DailyAssignment.valid_to == SOURCE_UNKNOWN_FUTURE
)

# HT-07: AH-06 ``END_EVENT_DATE`` is provenance only and takes part in no interval predicate.
# Where it disagrees with the derived ``VALID_TO`` the disagreement is surfaced, never
# reconciled. DATA-04 already computes the comparison; this lifts it into a queryable flag so
# the notebook can show the count without re-deriving the rule.
EndEventDisagreement = model.Relationship(
    f"{DailyAssignment:assignment} disagrees with its source end date"
)
model.define(EndEventDisagreement(DailyAssignment)).where(
    DailyAssignment.end_event_date_disagrees_with_valid_to == True  # noqa: E712
)


# ================================================================================================
# computed_schedule.py
# ================================================================================================
# computed_schedule.py - the reusable derived layer over UC2.
#
# Five things, each of which would otherwise get retyped in a query module:
#
# 1. **The weekday predicate**, as a multi-valued relationship rather than a seven-branch match.
# 2. **The physical-service representative flag** (D-0007), so the codeshare de-duplication rule
#    lives in the ontology instead of in eight query functions.
# 3. **The cabin-derivation cross-check**, which proves DV-26 in RAI without moving authority for
#    it out of Snowflake.
# 4. **A route-state snapshot-gap flag**, lifted so Q05's ``crosses_snapshot_gap`` is queryable.
# 5. **The Neo4j ``SCHEDULES`` edge**, the only supplied edge that has to be derived rather than
#    loaded, from the P0-08 two-clock conjunction.
#
# Both schedule clocks stay separately queryable and their two interval conventions never merge:
# knowledge is half-open (DV-14 inclusive, DV-15 **exclusive**), operating is inclusive on both
# ends (SS-08 and SS-09 both included). The helpers that apply them are
# ``temporal.known_on`` and ``temporal.operates_on`` and they are deliberately two functions.




# --- 1. The weekday predicate -----------------------------------------------------
#
# Up to seven values per state, so a real multi-valued ``Relationship``. Deriving it from the
# seven SS-14..SS-20 booleans turns ``operates_on`` into one join instead of a seven-branch
# match, while the raw booleans stay bound and untouched - Q05 must emit each of them field by
# field with old and new values, so both forms are needed and neither is redundant.
#
# ISO numbering, 1 = Monday. The query side computes the integer in Python from
# ``operating_date.isoweekday()`` rather than from a RAI date-part function, which removes any
# doubt about the day-numbering convention.
#
# The loop is over seven items, not rows. PyRel warns past fifty ``define()`` calls from one
# call site; seven is fine, and the alternative - seven hand-copied blocks - would be the same
# rules with more chances to transpose a day.

RouteStateOperatesOnWeekday = model.Relationship(
    f"{RouteState:state} operates on weekday {Integer:weekday}"
)

for _weekday, _flag_column in WEEKDAY_FLAG_COLUMNS:
    model.define(RouteStateOperatesOnWeekday(RouteState, _weekday)).where(
        getattr(RouteState, _flag_column) == True  # noqa: E712
    )

# --- 2. The D-0007 physical-service representative --------------------------------
#
# For the operating carrier role, only a base-representative state may be counted: not a
# codeshare, and marketing and operating carriers resolving to the same airline. Everything else
# is ``UNRESOLVED_PHYSICAL_SERVICE`` and must be *emitted as visibly unresolved*, never excluded
# and never guessed into a number - ``Q07-R004`` freezes exactly that row.
#
# DATA-04 already classifies this as ``PHYSICAL_SERVICE_STATUS`` (measured live: 4 rows
# ``PHYSICAL_SERVICE_REPRESENTATIVE``, 12,026 ``UNRESOLVED_PHYSICAL_SERVICE``). The flag is
# derived from that column rather than recomputed, keeping one authority - and
# ``PhysicalServiceDisagreement`` below re-derives the rule independently in RAI and asserts the
# two agree, which is the honest way to have both.

RouteStateIsPhysicalRepresentative = model.Relationship(
    f"{RouteState:state} is the physical service representative"
)
model.define(RouteStateIsPhysicalRepresentative(RouteState)).where(
    RouteState.physical_service_status != PHYSICAL_SERVICE_UNRESOLVED
)

# The independent RAI re-derivation of D-0007, used only as a guard. A state qualifies when it
# is not a codeshare and its two carrier roles resolve to the same airline. Any row where the
# Snowflake classification and this rule disagree is surfaced; the gate asserts the flag is
# empty.
PhysicalServiceDisagreement = model.Relationship(
    f"{RouteState:state} disagrees with the derived physical-service rule"
)
model.define(PhysicalServiceDisagreement(RouteState)).where(
    RouteState.physical_service_status != PHYSICAL_SERVICE_UNRESOLVED,
    RouteState.is_codeshare == True,  # noqa: E712
)
model.define(PhysicalServiceDisagreement(RouteState)).where(
    RouteState.physical_service_status != PHYSICAL_SERVICE_UNRESOLVED,
    RouteState.marketing_airline != RouteState.operating_airline,
)

# --- 3. The DV-26 cabin-derivation cross-check ------------------------------------
#
# ``ECONOMY_EXCLUDING_PREMIUM`` is DV-26: premium economy is a subset of economy, so the
# exclusive bucket is SS-34 minus SS-33 and the four cabin buckets must sum to the per-flight
# total. Q07 double-counts economy the moment someone forgets that.
#
# Authority stays with the MODEL_INPUT column - two competing definitions of one number is worse
# than one - but the arithmetic is asserted *in RAI* so the semantic is visible in the ontology
# and a Snowflake regression cannot pass silently. Measured live: zero disagreements over 12,030
# route states. Raw SS-30..SS-34 stay bound and are never overwritten (P0-09.6).

CabinDerivationDisagreement = model.Relationship(
    f"{RouteState:state} disagrees with the DV-26 economy-excluding-premium derivation"
)
model.define(CabinDerivationDisagreement(RouteState)).where(
    RouteState.economy_excluding_premium
    != RouteState.economy_class_seats - RouteState.premium_economy_seats
)

# --- 4. Snapshot-gap visibility ---------------------------------------------------
#
# A route-state segment that opened or closed across a missing or incomplete snapshot is
# evidence Q05 must carry, and an incomplete snapshot must never be read as a removal. The two
# flags are lifted from the DV-16 columns so the query layer joins a named flag rather than
# re-deriving the gap arithmetic.

RouteStateOpenCrossesGap = model.Relationship(
    f"{RouteState:state} opened across a snapshot gap"
)
model.define(RouteStateOpenCrossesGap(RouteState)).where(
    RouteState.open_crosses_snapshot_gap == True  # noqa: E712
)

RouteStateCloseCrossesGap = model.Relationship(
    f"{RouteState:state} closed across a snapshot gap"
)
model.define(RouteStateCloseCrossesGap(RouteState)).where(
    RouteState.close_crosses_snapshot_gap == True  # noqa: E712
)

# --- 5. The Neo4j SCHEDULES edge --------------------------------------------------
#
# ``(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)`` is the one supplied edge that is derived
# rather than loaded, and it is a real ``Relationship`` and not a ``Property``:
# NEO4J_RAI_MAPPING.md calls it "potential one-to-many; no functional claim". One route state
# schedules many operating dates, and one passenger flight is reachable from more than one
# knowledge version of the same schedule key, so neither direction is functional and a
# ``Property`` here would ``FDError``.
#
# It is *derived*, not imported, from the P0-08 conjunction, one clause per line:
#
#   1. exact schedule identity - PH-02 equals SS-01, expressed as both sides resolving to the
#      same ``Schedule`` entity. Only the DV-21 precedence-winning lineage row supplies PH-02,
#      so this is exact by construction rather than by a fixture accident;
#   2. the passenger publish date lies inside the state's half-open knowledge interval;
#   3. the passenger operating date lies inside the state's **inclusive** SS-08/SS-09 operating
#      interval - inclusive on both ends, unlike the knowledge clock; and
#   4. the operating date's ISO weekday is one the state actually operates.
#
# Anything failing the conjunction stays unlinked and visible, which is the point: a missing
# schedule identity or a failed clock applicability is a fact about the source, not a gap to be
# bridged. Both clocks appear in the same rule with their two different conventions, which is
# the same asymmetry Q07 turns on.

RouteStateSchedules = model.Relationship(
    f"{RouteState:state} schedules {PassengerFlight:flight}"
)
RouteState.schedules = RouteStateSchedules

model.define(RouteStateSchedules(RouteState, PassengerFlight)).where(
    RouteState.schedule == PassengerFlight.schedule,
    RouteState.knowledge_valid_from <= PassengerFlight.publish_date,
    PassengerFlight.publish_date < RouteState.knowledge_valid_to,
    RouteState.operating_effective_date <= PassengerFlight.operating_date,
    PassengerFlight.operating_date <= RouteState.operating_discontinue_date,
    RouteStateOperatesOnWeekday(
        RouteState, std_date.isoweekday(PassengerFlight.operating_date)
    ),
)

PassengerFlight.scheduled_by = RouteStateSchedules.alt(
    f"{PassengerFlight:flight} is scheduled by {RouteState:state}"
)


# ================================================================================================
# computed_rotation.py
# ================================================================================================
# computed_rotation.py - the accepted rotation edge, its transitive closure, and Q08 enrichment.
#
# The accepted-rotation-link relationship is one of the five things MODEL-01 owes the ontology,
# and it is the one where authoring it once matters most: the ordered traversal, the anomaly
# query, and any future path experiment must all walk an **identical** edge set, or the demo can
# be shown two different rotations for the same aircraft.
#
# Q08 is an ordinary typed self-reference, not a graph-reasoner question, and that verdict is
# evidence-based rather than a preference. Every algorithm in the graph-analysis catalogue returns
# an unordered or scalar result - reachability gives ``(source, target)``, distance gives
# ``(start, end, length)``, WCC gives ``(node, component)``, centrality gives ``(node, score)`` -
# while Q08's output is sixteen columns of which twelve are per-leg payload and one is a position
# within a path. None of those algorithms produces a position or carries edge payload, so each
# would have to be joined back to ``AircraftFlight`` anyway, which is the self-join the baseline
# already does.
#
# ``leg_order`` therefore comes from the link structure: ``1 + the number of accepted-chain
# predecessors``. Sorting the day's legs by departure time and numbering them reproduces the
# canonical answer on this fixture and is an explicit fail.
#
# PROBE U-07 settled the termination question. The 1.2.2 ``union`` + ``per(u, v).min(...)``
# recursion idiom compiles unchanged on 1.20.1 and produces a complete, correct, finite closure on
# a deliberately cyclic edge set in 3.6 seconds, with no visited set and no step bound - because
# ``min`` over the ``u == v`` base case caps every self-distance at 0 and the lattice is finite.
# There is no step-bound parameter in the 1.20.1 API and none is needed. P0-11.5 asks for a
# visited set and a finite step bound; the guard here is a different and stronger mechanism -
# cycles are excluded at the acceptance rule itself - and that difference is a note, not a risk.




# --- The accepted rotation edge ---------------------------------------------------
#
# ``Property``, because SOURCE_CONTRACT.md gives "actual flight to next actual flight:
# zero-or-one raw reference" and the accepted link is a subset of the raw one. In a
# ``Property`` all fields except the last are keys, so the FD is ``leg -> next_leg``, which is
# exactly what is wanted. Both same-type slots are role-labelled; without labels ``define()``
# would silently bind both to whichever column is listed first.
#
# The full P0-11.4 acceptance conjunction - target exists, is a different flight, shares the
# aircraft and the AF-06 local date, departs no earlier than the current actual arrival, departs
# *from* the current actual arrival airport (DV-45 = AF-09), and neither leg cancelled - is
# evaluated by DATA-04 and lands as ``IS_ACCEPTED_LINK`` / ``ROTATION_LINK_STATUS`` on
# ``ROTATION_LINK_VALIDATION``. Recomputing it here would put two competing definitions of the
# rotation in the system, which is the failure this module exists to prevent. What RAI owns is
# the *relationship*: one named edge set that every consumer traverses.

AircraftFlight.accepted_next_flight = model.Property(
    f"{AircraftFlight:leg} continues to {AircraftFlight:accepted_next_leg}"
)

_accepted_target = AircraftFlight.ref("accepted_target")
model.define(AircraftFlight.accepted_next_flight(_accepted_target)).where(
    RotationLinkValidation.flight == AircraftFlight,
    RotationLinkValidation.is_accepted_link == True,  # noqa: E712
    RotationLinkValidation.target_flight == _accepted_target,
)

# --- Segment heads ----------------------------------------------------------------
#
# A segment head is a leg with no accepted *inbound* edge. ``model.not_()`` over a ref is the
# documented way to ask for entities without a relationship; a bare ``not_`` on the property
# would not bind the variable.

RotationSegmentHead = model.Relationship(
    f"{AircraftFlight:leg} starts a rotation segment"
)
_inbound = AircraftFlight.ref("inbound")
model.define(RotationSegmentHead(AircraftFlight)).where(
    model.not_(_inbound.accepted_next_flight == AircraftFlight)
)

# --- Transitive position over the accepted edge -----------------------------------
#
# ``rotation_leg_distance(u, v)`` is the minimum number of accepted hops from ``u`` to ``v``,
# with ``0`` for ``u == v``. ``leg_order`` is then ``1 + distance(head, leg)`` and
# ``segment_id`` anchors on the head's ``flight_id``. A cycle is exactly "a node that reaches
# itself at a non-zero distance" in this same closure, so no separate cycle algorithm is needed
# - and the accepted-edge rule already excludes cycles, so the fixture's 8102/8103 pair surfaces
# through ``RotationLinkValidation`` evidence rather than through the chain.

# A ``Property`` and not a ``Relationship``: the *minimum* number of hops is functional per
# (from_leg, to_leg), so the FD is correct and the two-argument call form
# ``rotation_leg_distance(u, n)`` reads the value back inside the recursive step.
rotation_leg_distance = model.Property(
    f"{AircraftFlight:from_leg} reaches {AircraftFlight:to_leg} in {Integer:hops}"
)

_u = AircraftFlight.ref("dist_u")
_v = AircraftFlight.ref("dist_v")
_n = AircraftFlight.ref("dist_n")

model.define(
    rotation_leg_distance(
        _u,
        _v,
        aggs.per(_u, _v).min(
            model.union(
                model.select(0).where(_u == _v),
                model.select(rotation_leg_distance(_u, _n) + 1).where(
                    _n.accepted_next_flight == _v
                ),
            )
        ),
    )
)

# --- Q08 enrichment: the as-of type and engine on the LOCAL date ------------------
#
# The single sharpest trap in Q08. All three canonical legs have AF-06 = 2026-08-31 while
# AF-07 = 2026-09-01 and their UTC departure timestamps fall on 2026-09-01. Enrichment and day
# selection use **AF-06**, the local selected-day basis. Using AF-07, or deriving the date from
# AF-13, shifts the as-of instant by a day and can silently pick the wrong type or engine
# interval. ``TT-US-CLOCK-AUTHORITY`` freezes that assertion.
#
# This is the second of the two places where a materialized as-of rule is correct rather than a
# query-time predicate: the date set is bounded by the ``AircraftFlight`` rows themselves, so no
# calendar is needed and no cross product is possible.
#
# Declared ``Property`` because the value is functional per leg - one leg, one local date, one
# aircraft, one type. If it ever FDErrors, the daily assignments overlap and the model has just
# found a DATA-04 bug for us, which is a feature.

AircraftFlight.as_of_aircraft_type = model.Property(
    f"{AircraftFlight:leg} was of type {AircraftType:as_of_aircraft_type}"
)
AircraftFlight.as_of_engine_type = model.Property(
    f"{AircraftFlight:leg} was fitted with {EngineType:as_of_engine_type}"
)

_type_at_leg = DailyAssignment.ref("type_at_leg")
model.define(AircraftFlight.as_of_aircraft_type(AircraftType)).where(
    AircraftFlight.aircraft == Aircraft,
    _type_at_leg.aircraft == Aircraft,
    _type_at_leg.dimension == DIM_AIRCRAFT_TYPE,
    _type_at_leg.valid_from <= AircraftFlight.flight_departure_date,
    AircraftFlight.flight_departure_date < _type_at_leg.valid_to,
    _type_at_leg.aircraft_type == AircraftType,
)

_engine_at_leg = DailyAssignment.ref("engine_at_leg")
model.define(AircraftFlight.as_of_engine_type(EngineType)).where(
    AircraftFlight.aircraft == Aircraft,
    _engine_at_leg.aircraft == Aircraft,
    _engine_at_leg.dimension == DIM_ENGINE_TYPE,
    _engine_at_leg.valid_from <= AircraftFlight.flight_departure_date,
    AircraftFlight.flight_departure_date < _engine_at_leg.valid_to,
    _engine_at_leg.engine_type == EngineType,
)

# --- DV-32 type discrepancy -------------------------------------------------------
#
# AF-17 ``ACTUAL_SOURCE_AIRCRAFT_TYPE`` is discrepancy *evidence* and is never aircraft-history
# authority (ATTRIBUTE_AUTHORITY.md). The disagreement is reported, never reconciled, and the
# source value is never overwritten. ``Q08-R002`` freezes a ``true`` here: the as-of type is
# ``SYN-TYPE-B`` from history while the actual source reads "Synthetic narrowbody A".
#
# Three-valued in the output - absent where there is no as-of type to compare - so it is a rule
# and not a ``select`` expression, and the two conditions are mutually exclusive.

AircraftFlight.type_discrepancy = model.Property(
    f"{AircraftFlight:leg} disagrees on type {Bool:type_discrepancy}"
)
model.define(AircraftFlight.type_discrepancy(True)).where(
    AircraftFlight.as_of_aircraft_type == AircraftType,
    AircraftType.aircraft_type != AircraftFlight.actual_source_aircraft_type,
)
model.define(AircraftFlight.type_discrepancy(False)).where(
    AircraftFlight.as_of_aircraft_type == AircraftType,
    AircraftType.aircraft_type == AircraftFlight.actual_source_aircraft_type,
)


# ================================================================================================
# constraints.py
# ================================================================================================
# constraints.py - the multiplicity gates, and one deliberate absence.
#
# **Read this before believing anything in this file is enforced.**
#
# PROBE U-04 ran a deliberately violated ``require(unique(...))`` against the live engine, with
# and without ``reasoners.logic.emit_constraints: True``. In both configurations the require
# returned normally, the following query returned normally, and the violating data was still
# there. **``require(unique(...))`` is a silent no-op in SDK 1.20.1.** The corroborating source is
# ``backends/legacy_lqp/rewrite/annotate_constraints.py``: by default all constraints are
# discharged and removed from the IR in a later pass, and even with the flag on
# ``_should_declare_constraint`` additionally requires a non-structural functional dependency, so
# a structural FD is never declared as a runtime constraint.
#
# The calls below are therefore kept as **documentation only**. They put the multiplicity gate
# from ``SOURCE_CONTRACT.md`` into the model where a reviewer sees it, next to the one that is
# deliberately absent. They must not be presented to anyone as live checks.
#
# The real enforcement is two mechanisms, both of which do work:
#
# 1. **``Property`` itself.** The compiler-enforced functional dependency on every ``Property``
#    raises ``FDError: Found non-unique values`` naming the offending relation and printing the
#    two conflicting hashes. It fires at the **first evaluation** of the relation - measured at
#    13-19 seconds of engine work - not at define time. The design brief said "define time"; that
#    is wrong and saying it on stage would be a factual error the audience can check on screen.
# 2. **Zero-count assertion queries** in ``tests/test_model.py`` and in the Phase 8 gate, for
#    every claim a ``Property`` cannot express: the sentinel-leak guard, the end-event
#    disagreement, the cabin derivation, the physical-service re-derivation, and the G-01..G-06
#    functional-dependency probes.




# --- Present, and true ------------------------------------------------------------
#
# A route state has exactly one route and one schedule; its two carrier roles are zero-or-one
# EXACT resolutions. All four are already enforced by the ``Property`` declarations in
# ``core_schedule.py``; these restate them where the contract's reader looks for them.

model.require(unique(RouteState.route[RouteState]))
model.require(unique(RouteState.schedule[RouteState]))
model.require(unique(RouteState.marketing_airline[RouteState]))
model.require(unique(RouteState.operating_airline[RouteState]))

# One actual leg fulfils at most one planned service. The *inverse* is deliberately
# unconstrained, which is what makes the stopover case load: one planned passenger service may
# be fulfilled by several actual legs.
model.require(unique(AircraftFlight.fulfils[AircraftFlight]))

# --- Deliberately absent, and this comment is the point ---------------------------
#
#   There is NO unique(...) over the Route slot of ``Route.states``.
#   There is NO ``Route.current_state`` Property.
#
# SOURCE_CONTRACT.md: the one-open-per-route constraint is *prohibited*. Route-state versioning
# partitions by schedule identity, never by route, and a route legitimately has many concurrent
# open states - 1,339 of them on ``SFO->LAX`` at knowledge date 2026-08-31, measured live.
#
# The absent constraint is as informative as the present ones, and RAI cannot state the positive
# form: ``SD/std/constraints.py`` offers ``unique``, ``exclusive``, ``anyof`` and ``oneof`` and
# has no minimum-cardinality or negative-constraint vocabulary. "This route may have many
# concurrent open states" is provable by query and not declarable. Say that plainly rather than
# implying RAI declares something a property graph cannot.


# ================================================================================================
# inventory.py
# ================================================================================================
# inventory.py - ``inspect.schema(model)`` dumped to JSON, plus the two assertions that matter.
#
# Two jobs:
#
# * **MODEL-01's exit artifact.** ``build/design/ontology_inventory.json`` is what the gate, the
#   runbook and the notebook read to describe the ontology, and it is what MODEL-02's parity test
#   diffs the standalone file against.
# * **The only defence against two silent failure modes**, both measured live by PROBE-01 and
#   neither of which raises anything:
#
#   1. ``no_any_columns`` - a mistyped column in a ``model.Table()`` ``schema=`` dict binds
#      *silently* as an ``Any``-typed relation (U-01). Strict mode does not stop it. It then
#      produces an empty or NaN result in a query three phases later. One assertion over
#      ``inspect.schema(model).tables`` catches every column typo in ``sources.py`` and costs
#      nothing.
#   2. ``per_column_non_null`` - a *wrongly declared type* yields an all-NaN column rather than a
#      ``TyperError`` (U-02). A row-count check passes happily. So the gate compares the non-null
#      count of every bound column against ``COUNT(<col>)`` in SQL.
#
# ``inspect.schema`` is also the "here is what actually registered" artifact, which is a different
# thing from "here is what I intended to build" - the second assertion exists because the two
# diverged silently in the probe run.






def default_inventory_path() -> Path:
    """Repo-relative artifact path, resolved lazily.

    Lazily because MODEL-02's standalone file has to import cleanly inside a Snowsight or
    Workspace runtime where ``__file__`` may not point anywhere useful and where there is no
    repo to write into. Nothing here touches the filesystem at import time.
    """
    return Path(__file__).resolve().parents[2] / "build" / "design" / "ontology_inventory.json"


INVENTORY_PATH = default_inventory_path()


def _rel(info: Any) -> dict[str, Any]:
    return {
        "name": info.name,
        "type_name": info.type_name,
        "reading": info.reading,
        "is_property": info.is_property,
        "is_identity": info.is_identity,
        "fields": [{"name": f.name, "type_name": f.type_name} for f in info.fields],
        "alt_readings": sorted(info.alt_readings),
    }


def build_inventory() -> dict[str, Any]:
    """Serialise ``inspect.schema(model)`` into a stable, diffable JSON structure.

    Sorted everywhere. ``inspect.schema`` guarantees deterministic *declaration* order, which
    is not the same as being stable across two differently-organised programs - the MODEL-02
    standalone file concatenates the package's modules and so declares in a different order.
    Sorting makes the parity diff compare content rather than sequence.

    Rule texts are excluded on purpose: they embed frontend object ids that differ between
    processes, so including them would make an identical model look different.
    """
    schema = inspect.schema(model)

    concepts = {
        c.name: {
            "extends": sorted(c.extends),
            "identify_by": [_rel(p) for p in c.identify_by],
            "properties": sorted((_rel(p) for p in c.properties), key=lambda d: d["name"]),
            "relationships": sorted(
                (_rel(r) for r in c.relationships), key=lambda d: (d["name"], d["reading"])
            ),
            "data_sources": sorted(c.data_sources),
        }
        for c in schema.concepts
    }

    tables = {
        t.name: {
            "columns": sorted(
                ({"name": col.name, "type_name": col.type_name} for col in t.columns),
                key=lambda d: d["name"],
            ),
            "loads": sorted(t.loads),
        }
        for t in schema.tables
    }

    bare = sorted(
        (_rel(r) for r in schema.bare_relationships), key=lambda d: (d["name"], d["reading"])
    )

    declared = {
        alias: {"object": qualified, "columns": {c: str(t) for c, t in cols.items()}}
        for alias, (_tbl, qualified, cols) in TABLE_INVENTORY.items()
    }

    return {
        "model": schema.name,
        "sdk_version": _sdk_version(),
        "concept_count": len(concepts),
        "table_count": len(tables),
        "property_count": sum(len(v["properties"]) + len(v["identify_by"]) for v in concepts.values()),
        "relationship_count": sum(len(v["relationships"]) for v in concepts.values()),
        "bare_relationship_count": len(bare),
        "define_rule_count": len(schema.defines),
        "require_rule_count": len(schema.requires),
        "declared_source_count": len(declared),
        "declared_column_count": sum(len(v["columns"]) for v in declared.values()),
        "concepts": dict(sorted(concepts.items())),
        "tables": dict(sorted(tables.items())),
        "bare_relationships": bare,
        "declared_sources": dict(sorted(declared.items())),
    }


def _sdk_version() -> str:
    try:
        import relationalai

        return getattr(relationalai, "__version__", "unknown")
    except Exception:  # pragma: no cover - version reporting must never break the dump
        return "unknown"


def assert_no_any_columns(inventory: dict[str, Any]) -> list[str]:
    """Every discovered table column must have a concrete type. Returns the offenders.

    An ``Any`` here means a column name in a ``sources.py`` ``schema=`` dict does not exist in
    Snowflake. PROBE U-01: ``t.no_such_column`` binds without error and shows up as
    ``FieldInfo(name='no_such_column', type_name='Any')``.
    """
    offenders = []
    for table_name, table in inventory["tables"].items():
        for column in table["columns"]:
            if column["type_name"] == "Any":
                offenders.append(f"{table_name}.{column['name']}")
    return sorted(offenders)


def write_inventory(path: Path | None = None) -> dict[str, Any]:
    """Build the inventory, assert no ``Any`` column, and write the JSON artifact."""
    inventory = build_inventory()
    offenders = assert_no_any_columns(inventory)
    if offenders:
        raise AssertionError(
            "Any-typed table columns found, which means a column name in sources.py does not "
            f"exist in Snowflake: {offenders}"
        )
    target = path or INVENTORY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(inventory, indent=1, sort_keys=True, default=str) + "\n")
    return inventory


if __name__ == "__main__":  # pragma: no cover - operational entry point
    inv = write_inventory()
    print(
        f"wrote {INVENTORY_PATH} - {inv['concept_count']} concepts, "
        f"{inv['table_count']} tables, {inv['declared_column_count']} declared columns"
    )
'''

_SRC_UC1 = r'''"""uc1.py - Q01 to Q04 of the aviation temporal demo, as live PyRel queries.

Five questions over the aircraft surface, all of them answered by the *same* shared temporal
predicate layer in ``aviation_model.temporal``:

* **Q01** ``aircraft_as_of`` - reconstruct one aircraft at one instant across four
  independently clocked dimensions, each carrying its own DV-33 status.
* **Q02** ``status_reversion_spells`` - every ``In Service -> Storage -> In Service`` spell on
  the *audit* stream, including the same-day zero-day spell the daily projection loses.
* **Q02F** ``fleet_storage_spell_distribution`` - the same spell derivation with the
  per-aircraft filter removed, bucketed by duration against a joined bucket dimension (D-0026,
  manifest v1.2.0).
* **Q03** ``month_end_fleet_composition`` - in-service count per exact aircraft type at every
  month end over ten years, from **one** query joined against a materialized calendar.
* **Q04** ``type_engine_histories`` - the type stream and the engine stream side by side,
  never boundary-aligned, plus the three-valued ``is_type_change``.

Three rules this module holds to, each of which cost somebody a live failure to learn.

1. **Nothing temporal is retyped here.** Every interval conjunction comes from
   ``aviation_model.temporal`` - :func:`~aviation_model.temporal.within_existence`,
   :func:`~aviation_model.temporal.visible_on` and
   :func:`~aviation_model.temporal.dv33_branches` - and Q03's calendar join comes from the
   ``InServiceOnMonthEnd`` model rule. ``NEO4J_PARITY_MATRIX.md`` sells "one reusable semantic
   model for the eight bounded workloads instead of query-local temporal rules"; a copy of
   ``valid_from <= d < valid_to`` in this file would make that claim false and would give each
   question its own chance to put the exclusive bound on the wrong side.
2. **The filtering, joining and aggregation happen in PyRel.** pandas is used for exactly three
   things: naming and ordering the frozen output columns, normalising RAI's pandas dtypes back
   to Python scalars (RAI ``Date`` arrives as ``Timestamp``, integer aggregates as
   ``Int128Array``), and stamping the manifest ``row_id`` label. No filter, no join, no group-by
   is performed on a DataFrame.
3. **Parameters are validated before any query is sent.** ``EXPECTED_ANSWERS.yaml``'s
   ``canonicalization`` section is explicit: "validation returns error_code before query
   execution and rows remain empty". :class:`QueryParameterError` carries the frozen
   ``error_code``.

``row_id`` is in every frozen ``output_schema`` but is a *supplied manifest label*, not a
derived value - ``DEMO_QUESTIONS.md`` says so under D-0018, and the independent SQL oracles do
not emit it either. Each function therefore takes ``row_id_start`` and stamps
``<QID>-R<n:03d>`` in the frozen ``order_by`` order. ``main()`` and ``tests/test_uc1.py`` pass
the base declared by the manifest and separately assert the frozen labels are exactly that
contiguous run, so the numbering is checked rather than assumed.

Run it::

    PYTHONPATH=rai_code .venv/bin/python rai_code/queries/uc1.py

The first query in a fresh interpreter pays a roughly 130 second full-model sync; warm queries
are 3 to 9 seconds. Only ever build one ``Model`` per process - a second one makes the free
``distinct(...)`` raise ``[Ambiguous model]`` (PROBE N-02) - which is why this module imports
the package's single ``aviation_model.model`` and never constructs its own.

Do not run two query modules against this model concurrently. Building the model is a write
transaction and a concurrent reader **errors** rather than waiting, with
``prepareIndex: model is currently locked``. :func:`warm_model` retries through it; ``main()``
calls it first.
"""

from __future__ import annotations

import datetime as dt
import itertools
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

if __name__ == "__main__" and __package__ in (None, ""):  # pragma: no cover - script entry
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aviation_model as am
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import datetime as rdt

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "EXPECTED_ANSWERS.yaml"


# ---------------------------------------------------------------------------------
# Model warm-up, and the concurrency hazard it exists for
# ---------------------------------------------------------------------------------

_LOCK_MARKERS = ("model is currently locked", "prepareindex")


def warm_model(*, attempts: int = 8, delay: float = 30.0) -> float:
    """Pay the one-off model sync up front, retrying while another process holds the lock.

    Two facts, both measured rather than assumed, and both of which look like the other one if
    you only see a stalled terminal:

    * **The sync is about 130 seconds, not ten minutes.** Measured here at 122.8s on an already
      ``READY`` engine and independently at 133.5s by the UC2 agent. PROBE U-12's 631s figure
      includes nine minutes of engine *provisioning* from ``SUSPENDED``; once the engine is up,
      the model sync alone is roughly two minutes. Warm queries are 3 to 9 seconds.
    * **Building the model is a write transaction, and a concurrent reader errors rather than
      waiting.** Importing ``aviation_model`` in a second process while a first is still
      indexing fails with ``prepareIndex: model is currently locked``. UC2 lost two runs to this
      and spent the time debugging a query that was fine. If you see that message it is another
      process, not your query.

    Returns the elapsed seconds so a caller can report cold versus warm honestly.
    """
    import time

    started = time.time()
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            am.model.select(aggs.count(am.Aircraft).alias("n")).to_df()
            return time.time() - started
        except Exception as exc:  # noqa: BLE001 - re-raised below unless it is the lock
            message = str(exc).lower()
            if not any(marker in message for marker in _LOCK_MARKERS):
                raise
            last = exc
            print(
                f"model locked by another process, retry {attempt + 1}/{attempts} "
                f"in {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(
        f"model still locked after {attempts} attempts over "
        f"{time.time() - started:.0f}s"
    ) from last


# ---------------------------------------------------------------------------------
# Typed parameter validation
# ---------------------------------------------------------------------------------


class QueryParameterError(ValueError):
    """A typed parameter violation, raised *before* any query reaches the engine.

    ``invocation_status`` is always ``PARAMETER_ERROR`` and ``error_code`` is the frozen token.
    ``Q01-INVALID-AIRCRAFT-ID`` is the only parameter-error result set among Q01 to Q04, and it
    freezes ``INVALID_AIRCRAFT_ID`` for ``aircraft_id = -1``: an out-of-domain identifier, so
    the check is on the domain and not on whether the row happens to exist.
    """

    invocation_status = "PARAMETER_ERROR"

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code


def _require_aircraft_id(value: Any) -> int:
    """``NUMBER(38,0)``, not null, in domain. Aircraft identifiers are positive integers."""
    if value is None or isinstance(value, bool):
        raise QueryParameterError("INVALID_AIRCRAFT_ID", f"aircraft_id must not be {value!r}")
    try:
        aircraft_id = int(value)
    except (TypeError, ValueError):
        raise QueryParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id {value!r} is not an integer"
        ) from None
    if isinstance(value, float) and aircraft_id != value:
        raise QueryParameterError("INVALID_AIRCRAFT_ID", f"aircraft_id {value!r} is not integral")
    if aircraft_id <= 0:
        raise QueryParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id {aircraft_id} is out of domain"
        )
    return aircraft_id


def _require_date(value: Any, name: str, error_code: str) -> dt.date:
    """``DATE``, not null, castable. A ``datetime`` is narrowed; a string must be ISO."""
    if value is None:
        raise QueryParameterError(error_code, f"{name} must not be null")
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            raise QueryParameterError(
                error_code, f"{name} {value!r} is not an ISO date"
            ) from None
    raise QueryParameterError(error_code, f"{name} {value!r} is not castable to DATE")


def _require_enum(value: Any, name: str, allowed: Sequence[str], error_code: str) -> str:
    if value is None:
        raise QueryParameterError(error_code, f"{name} must not be null")
    if value not in allowed:
        raise QueryParameterError(
            error_code, f"{name} {value!r} is not one of {list(allowed)}"
        )
    return str(value)


# ---------------------------------------------------------------------------------
# pandas-side normalisation (dtype only - never filtering, joining or aggregation)
# ---------------------------------------------------------------------------------


def _is_missing(value: Any) -> bool:
    """True for ``None`` / ``NaN`` / ``NaT`` / ``pd.NA``.

    Checked before any ``isinstance`` test because ``pd.NaT`` *is* a ``datetime`` instance, so
    an ``isinstance(value, dt.date)`` branch would happily return it.
    """
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _to_date(value: Any) -> dt.date | None:
    """RAI ``Date`` to ``datetime.date``.

    MODEL-01 finding M-02: RAI ``Date`` properties arrive as pandas ``Timestamp``, so a naive
    ``df["d"] == dt.date(...)`` matches nothing and passes vacuously. Normalising element-wise
    rather than through ``pd.to_datetime`` also survives the ``9999-01-01`` open-interval
    sentinel, which is past ``Timestamp.max`` (2262-04-11) and would overflow a vectorised cast.
    """
    if _is_missing(value):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _to_int(value: Any) -> int | None:
    """RAI ``Integer`` / ``Int128Array`` cell to ``int``. Pandas reductions on Int128 raise."""
    return None if _is_missing(value) else int(value)


def _to_bool(value: Any) -> bool | None:
    """RAI ``Bool`` to ``bool``. Absence stays ``None``; Q04's flag is three-valued."""
    return None if _is_missing(value) else bool(value)


def _to_str(value: Any) -> str | None:
    return None if _is_missing(value) else str(value)


_NORMALISERS: Mapping[str, Callable[[Any], Any]] = {
    # Q01
    "aircraft_id": _to_int,
    "as_of_date": _to_date,
    "is_complete": _to_bool,
    "aircraft_state_status": _to_str,
    "aircraft_type_status": _to_str,
    "engine_type_status": _to_str,
    "aircraft_status_status": _to_str,
    "aircraft_type_id": _to_str,
    "aircraft_type": _to_str,
    "engine_type_id": _to_str,
    "engine_type": _to_str,
    "engine_count": _to_int,
    "mixed_engine_set_complete": _to_bool,
    "lifecycle_status": _to_str,
    "registration_number": _to_str,
    "base_airport_code_iata": _to_str,
    # Q02
    "storage_event_id": _to_int,
    "storage_start_date": _to_date,
    "storage_start_sequence": _to_int,
    "return_event_id": _to_int,
    "return_date": _to_date,
    "return_sequence": _to_int,
    "storage_days": _to_int,
    "same_day": _to_bool,
    # Q02F
    "bucket_order": _to_int,
    "duration_bucket": _to_str,
    "spell_count": _to_int,
    "aircraft_count": _to_int,
    "minimum_storage_days": _to_int,
    "maximum_storage_days": _to_int,
    # Q03
    "month_end": _to_date,
    "in_service_aircraft_count": _to_int,
    # Q04
    "dimension": _to_str,
    "assignment_id": _to_str,
    "valid_from": _to_date,
    "valid_to": _to_date,
    "definition_id": _to_str,
    "definition_label": _to_str,
    "previous_definition_id": _to_str,
    "is_type_change": _to_bool,
}


def _records(df: pd.DataFrame, columns: Sequence[str]) -> list[dict[str, Any]]:
    """One normalised dict per RAI row, restricted to ``columns``.

    An empty RAI result is a **zero-column** DataFrame (PROBE D11), not a zero-row frame with
    the expected columns, so the column list is supplied by the caller and never read off the
    returned frame.
    """
    if df.shape[1] == 0 or df.shape[0] == 0:
        return []
    return [
        {name: _NORMALISERS[name](row.get(name)) for name in columns}
        for row in df.to_dict("records")
    ]


def _finalise(
    rows: Iterable[Mapping[str, Any]],
    *,
    columns: Sequence[str],
    order_by: Sequence[str],
    question_id: str,
    row_id_start: int,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """The frozen columns, in the frozen order, with the manifest ``row_id`` stamped last.

    ``na_position="last"`` implements the canonicalization rule "Nulls sort last in every
    nullable order key"; ``kind="stable"`` keeps the sort deterministic when the declared keys
    do not fully order the rows. Row order out of ``to_df()`` is explicitly not guaranteed, so
    ordering here is mandatory rather than cosmetic.

    ``dtype=object`` is load-bearing, not defensive. Left to infer, pandas turns a nullable
    integer column such as Q04's ``engine_count`` (``[None, None, 2, 2]``) into ``float64`` and
    the frozen ``null`` cells silently become ``NaN`` floats, so a null and a zero-ish float
    stop being distinguishable and ``2`` is reported as ``2.0``. Keeping Python scalars means
    the frame compares against the YAML exactly as parsed.

    ``row_id_prefix`` and ``row_id_width`` exist because the manifest labels two generations of
    result set differently: the v1.1.1 sets are ``<QID>-R<nnn>`` (``Q01-R001``) while every
    v1.2.0 set is ``<RESULT_SET_ID>-R<nnnn>`` (``Q01-ENRICHED-MID-STORAGE-R0001``). ``row_id`` is
    a supplied manifest label rather than a derived value, so the caller states the convention
    and the comparison then checks it rather than assuming it.
    """
    payload_columns = [name for name in columns if name != "row_id"]
    frame = pd.DataFrame(list(rows), columns=payload_columns, dtype=object)
    if len(frame):
        frame = frame.sort_values(
            list(order_by), kind="stable", na_position="last"
        ).reset_index(drop=True)
    prefix = row_id_prefix or question_id
    frame.insert(
        0,
        "row_id",
        [f"{prefix}-R{row_id_start + i:0{row_id_width}d}" for i in range(len(frame))],
    )
    return frame[list(columns)]


# ---------------------------------------------------------------------------------
# Frozen output schemas (asserted against EXPECTED_ANSWERS.yaml in tests/test_uc1.py)
# ---------------------------------------------------------------------------------

Q01_COLUMNS = (
    "row_id",
    "aircraft_id",
    "as_of_date",
    "is_complete",
    "aircraft_state_status",
    "aircraft_type_status",
    "engine_type_status",
    "aircraft_status_status",
    "aircraft_type_id",
    "aircraft_type",
    "engine_type_id",
    "engine_type",
    "engine_count",
    "mixed_engine_set_complete",
    "lifecycle_status",
    "registration_number",
    "base_airport_code_iata",
)
Q01_ORDER_BY = ("aircraft_id", "as_of_date")

Q02_COLUMNS = (
    "row_id",
    "aircraft_id",
    "storage_event_id",
    "storage_start_date",
    "storage_start_sequence",
    "return_event_id",
    "return_date",
    "return_sequence",
    "storage_days",
    "same_day",
)
Q02_ORDER_BY = (
    "storage_start_date",
    "storage_start_sequence",
    "storage_event_id",
    "return_event_id",
)

Q02F_COLUMNS = (
    "row_id",
    "bucket_order",
    "duration_bucket",
    "spell_count",
    "aircraft_count",
    "minimum_storage_days",
    "maximum_storage_days",
)
Q02F_ORDER_BY = ("bucket_order",)
Q02F_SCOPE_ENUM = ("FLEET",)

Q03_COLUMNS = (
    "row_id",
    "month_end",
    "aircraft_type_id",
    "aircraft_type",
    "in_service_aircraft_count",
)
Q03_ORDER_BY = ("month_end", "aircraft_type_id")

Q04_COLUMNS = (
    "row_id",
    "aircraft_id",
    "dimension",
    "assignment_id",
    "valid_from",
    "valid_to",
    "definition_id",
    "definition_label",
    "engine_count",
    "mixed_engine_set_complete",
    "previous_definition_id",
    "is_type_change",
)
Q04_ORDER_BY = ("dimension", "valid_from", "assignment_id")

Q03_STATUS_ENUM = (am.STATUS_IN_SERVICE,)


# ---------------------------------------------------------------------------------
# Q01 - aircraft_as_of
# ---------------------------------------------------------------------------------

_ref_counter = itertools.count(1)


@dataclass(frozen=True, eq=False)
class _Dimension:
    """One of Q01's four independently clocked dimension streams.

    ``scope`` is what restricts the shared ``AircraftDimensionDailyAssignment`` ref to a single
    dimension and is **not optional**: the concept is one physical table with a ``dimension``
    discriminator, so an unscoped ref ranges over all four and returns a silently wrong answer
    rather than an error. Aircraft 1001 at 2022-05-15 reported both ``OK`` and
    ``UNKNOWN_STATE`` before the scope existed.

    ``exact_target`` is the optional-target property *chain itself*, never a comparison:
    ``model.not_(ref.aircraft_type == AircraftType)`` reads as "there exists some type this is
    not equal to", true for nearly everything once two types exist. ``dv33_branches`` negates
    the chain's existence instead.

    ``ok_bindings`` are the extra clauses that bind the resolved definition entity so the
    projection can read its identity and label off the definition concept rather than off the
    assignment payload. They are added to the ``OK`` branch only.
    """

    name: str
    ref: Any
    scope: tuple
    exact_target: Any
    ok_bindings: tuple
    payload: Mapping[str, Any] = field(default_factory=dict)


def _q01_dimensions(tag: str) -> tuple[_Dimension, ...]:
    """Four separately named refs. One shared ref would unify the four dimensions into one.

    ``aircraft_state`` gets no ``exact_target``: its payload is plain strings (AH-17 / AH-25)
    with no exact resolution to a definition entity, and ``MODEL_INPUT`` confirms it live -
    ``DIMENSION_QUERY_STATUS`` is ``OK`` on all 1,004 state rows and all 1,003 status rows,
    with ``UNKNOWN_STATE`` occurring only on ``aircraft_type`` and ``engine_type``. Note there
    is deliberately no resolved ``Airport`` link for AH-25: the contract never resolved one, so
    the raw IATA code is emitted as a string.
    """
    state = am.DailyAssignment.ref(f"q01_state_{tag}")
    typ = am.DailyAssignment.ref(f"q01_type_{tag}")
    eng = am.DailyAssignment.ref(f"q01_engine_{tag}")
    sta = am.DailyAssignment.ref(f"q01_status_{tag}")
    return (
        _Dimension(
            name=am.DIM_AIRCRAFT_STATE,
            ref=state,
            scope=(state.dimension == am.DIM_AIRCRAFT_STATE,),
            exact_target=None,
            ok_bindings=(),
            payload={
                "registration_number": state.aircraft_registration_number,
                "base_airport_code_iata": state.base_airport_code_iata,
            },
        ),
        _Dimension(
            name=am.DIM_AIRCRAFT_TYPE,
            ref=typ,
            scope=(typ.dimension == am.DIM_AIRCRAFT_TYPE,),
            exact_target=typ.aircraft_type,
            ok_bindings=(typ.aircraft_type == am.AircraftType,),
            payload={
                "aircraft_type_id": am.AircraftType.subseries,
                "aircraft_type": am.AircraftType.aircraft_type,
            },
        ),
        _Dimension(
            name=am.DIM_ENGINE_TYPE,
            ref=eng,
            scope=(eng.dimension == am.DIM_ENGINE_TYPE,),
            exact_target=eng.engine_type,
            ok_bindings=(eng.engine_type == am.EngineType,),
            payload={
                "engine_type_id": am.EngineType.subseries,
                "engine_type": am.EngineType.engine_type,
                # AC-08 and DV-09 belong to the assignment, not to the EngineType identity:
                # asserting one engine count per engine subseries would be wrong in the domain.
                "engine_count": eng.engine_count,
                "mixed_engine_set_complete": eng.mixed_engine_set_complete,
            },
        ),
        _Dimension(
            name=am.DIM_AIRCRAFT_STATUS,
            ref=sta,
            scope=(sta.dimension == am.DIM_AIRCRAFT_STATUS,),
            exact_target=sta.status,
            ok_bindings=(sta.status == am.AircraftStatus,),
            payload={"lifecycle_status": am.AircraftStatus.code},
        ),
    )


_Q01_STATUS_COLUMN = {
    am.DIM_AIRCRAFT_STATE: "aircraft_state_status",
    am.DIM_AIRCRAFT_TYPE: "aircraft_type_status",
    am.DIM_ENGINE_TYPE: "engine_type_status",
    am.DIM_AIRCRAFT_STATUS: "aircraft_status_status",
}

_Q01_PAYLOAD_COLUMNS = (
    "aircraft_type_id",
    "aircraft_type",
    "engine_type_id",
    "engine_type",
    "engine_count",
    "mixed_engine_set_complete",
    "lifecycle_status",
    "registration_number",
    "base_airport_code_iata",
)


def _dv33_branches(dimension: _Dimension, as_of: dt.date) -> list[tuple[str, tuple]]:
    """The four DV-33 branches for one dimension at one date, from the shared builder."""
    return am.dv33_branches(
        am.model,
        am.Aircraft,
        dimension.ref,
        as_of,
        scope=dimension.scope,
        exact_target=dimension.exact_target,
    )


def _run_branch(
    aircraft_id: int, dimension: _Dimension, token: str, conditions: tuple
) -> pd.DataFrame:
    """Evaluate one DV-33 branch. Non-empty means the branch fired.

    The ``OK`` branch also projects the payload; every other branch projects the identity only,
    because the frozen answer's payload cells are null wherever the dimension is not ``OK``.
    The nulls come from that structural absence, never from a ``| None`` fallback - ``| None``
    raises inside ``front_compiler`` before a query is even sent (PROBE U-09).
    """
    projection = [am.Aircraft.id.alias("aircraft_id")]
    extra: tuple = ()
    if token == am.DV33_OK:
        extra = dimension.ok_bindings
        projection += [expr.alias(name) for name, expr in dimension.payload.items()]
    return (
        am.model.where(am.Aircraft.id == aircraft_id, *conditions, *extra)
        .select(*projection)
        .to_df()
    )


def _fired(df: pd.DataFrame) -> bool:
    """PROBE D11: an empty RAI result has no columns at all, so check both dimensions."""
    return bool(df.shape[1]) and bool(len(df))


def _resolve_dimension(
    aircraft_id: int, dimension: _Dimension, as_of: dt.date, *, strict: bool = False
) -> tuple[str | None, dict[str, Any]]:
    """The DV-33 status and payload for one dimension.

    ``OUTSIDE_EXISTENCE`` is skipped here and evaluated once for the whole row: its condition
    set is ``not_(existence_from <= d, d < existence_to)`` and mentions no assignment at all,
    so it is dimension-independent by construction and running it four times would be four
    identical queries.

    ``strict=True`` evaluates every remaining branch and raises if more than one fires. The
    branches are mutually exclusive structurally (``<`` on one boundary, ``>=`` on the other),
    so the default short-circuits at the first hit and saves up to two queries per dimension;
    ``tests/test_uc1.py`` runs the strict form over the frozen cases to keep that honest.
    """
    fired: list[tuple[str, pd.DataFrame]] = []
    for token, conditions in _dv33_branches(dimension, as_of):
        if token == am.DV33_OUTSIDE_EXISTENCE:
            continue
        frame = _run_branch(aircraft_id, dimension, token, conditions)
        if _fired(frame):
            fired.append((token, frame))
            if not strict:
                break
    if not fired:
        return None, {}
    if len(fired) > 1:
        raise AssertionError(
            f"DV-33 branches overlapped for aircraft {aircraft_id} "
            f"dimension {dimension.name} at {as_of}: {[token for token, _ in fired]}"
        )
    token, frame = fired[0]
    if len(frame) != 1:
        raise AssertionError(
            f"dimension {dimension.name} resolved to {len(frame)} rows for aircraft "
            f"{aircraft_id} at {as_of}; the multiplicity gate guarantees zero or one"
        )
    payload = {
        name: _NORMALISERS[name](frame.iloc[0][name])
        for name in dimension.payload
        if name in frame.columns
    }
    return token, payload


def aircraft_as_of(
    aircraft_id: int,
    as_of_date: dt.date | str,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
    strict: bool = False,
) -> pd.DataFrame:
    """Q01 - reconstruct one aircraft at one instant. Exactly one row, always.

    Four dimension streams are resolved independently against the same scalar date; no interval
    is ever intersected with another interval, which is why the misaligned type and engine
    boundaries are irrelevant here. Each dimension carries its own DV-33 status and
    ``is_complete`` is the validation overlay: true only when all four are ``OK``.

    The four absence cases are genuinely different facts and collapsing any two of them fails a
    frozen result set:

    * ``OUTSIDE_EXISTENCE`` - ``Q01-EOL-BOUNDARY``, aircraft 1002 at 2024-07-01. Its
      ``existence_to`` *is* 2024-07-01 and D-0003 makes the finite end-of-life bound exclusive,
      so all four dimensions are outside. ``<=`` instead of ``<`` returns ``OK`` here.
    * ``NO_RECORDED_STATE`` - ``Q01-BEFORE-FIRST``, aircraft 1004 at 2019-06-30. Inside
      existence (from 2019-01-01) but before its first assignment (2020-01-01).
    * ``UNKNOWN_STATE`` - ``Q01-UNKNOWN-GAP``, aircraft 1002 at 2022-05-15. A covering
      assignment exists but resolves to no definition, so type and engine are ``UNKNOWN_STATE``
      while state and status are ``OK``. This is an explicit recorded gap, never backfilled:
      AM-11 through AM-14 are ``CURRENT_ONLY`` under D-0005 and a query that coalesced the
      historical null to the master value would look more complete and be wrong.
    * an aircraft the model does not hold at all - not a frozen case. Reported as four
      ``OUTSIDE_EXISTENCE`` statuses, matching ``q01_aircraft_as_of.sql``'s
      ``existence_from IS NULL`` branch, so the RAI answer and the SQL oracle stay aligned.
    """
    aircraft_id = _require_aircraft_id(aircraft_id)
    as_of = _require_date(as_of_date, "as_of_date", "INVALID_AS_OF_DATE")

    dimensions = _q01_dimensions(f"{next(_ref_counter)}")

    # OUTSIDE_EXISTENCE once, from the shared builder, for the whole row.
    outside_conditions = next(
        conditions
        for token, conditions in _dv33_branches(dimensions[0], as_of)
        if token == am.DV33_OUTSIDE_EXISTENCE
    )
    outside = _fired(
        am.model.where(am.Aircraft.id == aircraft_id, *outside_conditions)
        .select(am.Aircraft.id.alias("aircraft_id"))
        .to_df()
    )

    statuses: dict[str, str] = {}
    payload: dict[str, Any] = {name: None for name in _Q01_PAYLOAD_COLUMNS}
    if outside:
        statuses = {dim.name: am.DV33_OUTSIDE_EXISTENCE for dim in dimensions}
    else:
        for dimension in dimensions:
            token, values = _resolve_dimension(
                aircraft_id, dimension, as_of, strict=strict
            )
            statuses[dimension.name] = token or am.DV33_OUTSIDE_EXISTENCE
            payload.update(values)

    row: dict[str, Any] = {"aircraft_id": aircraft_id, "as_of_date": as_of}
    row.update(
        {
            _Q01_STATUS_COLUMN[name]: status
            for name, status in statuses.items()
        }
    )
    row["is_complete"] = all(status == am.DV33_OK for status in statuses.values())
    row.update(payload)
    return _finalise(
        [row],
        columns=Q01_COLUMNS,
        order_by=Q01_ORDER_BY,
        question_id="Q01",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q02 / Q02F - the shared storage-spell derivation
# ---------------------------------------------------------------------------------


def _spell_bindings(tag_prefix: str) -> tuple[Any, Any, tuple]:
    """The ``In Service -> Storage -> In Service`` spell, bound once for Q02 and Q02F.

    Returns ``(storage_ref, return_ref, conditions)``. The caller adds its own scope - Q02 a
    single ``Aircraft.id`` equality, Q02F nothing at all - and its own projection. Factoring it
    here is not tidiness: ``data/oracles/q02f_fleet_spell_distribution.sql`` states that the
    fleet derivation is "byte-for-byte the Q02 derivation with the per-aircraft filter removed,
    so the two answers cannot disagree about what a spell is", and two copies of these clauses
    would put that guarantee at the mercy of a future edit to one of them.

    Three separately named refs over ``AircraftStatusAudit``, the **audit** stream and never the
    daily projection. The daily stream keeps only the final relevant observation per aircraft,
    dimension and date, so aircraft 1001's four same-day observations on 2020-06-01 (row
    sequences 5, 10, 20, 30 -> Maintenance, In Service, Storage, In Service) collapse to one and
    the zero-day spell at sequences 20 and 30 disappears with no error at all.

    ``event_ordinal`` is the shared dense DV-03 ordinal per (aircraft, dimension) over
    ``(AH-05, AH-03, AH-04, AH-01)``, which reduces "the previous assignment" and "the next
    qualifying assignment" from a four-column lexicographic comparison to one integer
    comparison.

    The return leg is the **minimal** later In Service, bound with the HAVING-style ``:=``
    pattern. The SQL oracle instead takes the immediate successor and requires it to be In
    Service; the two definitions differ only when a Storage is followed by some third status
    before service resumes. Measured live over the whole fleet they agree exactly - 439 spells
    either way, out of 442 Storage observations that follow an In Service - so the frozen
    answers do not discriminate between them. The minimal-successor form is kept because it is
    the one that cannot pair a Storage with a later spell's return, which is what holds Q02
    down to two rows for aircraft 1001.
    """
    tag = f"{tag_prefix}_{next(_ref_counter)}"
    storage = am.AuditAssignment.ref(f"{tag}_storage")
    prior = am.AuditAssignment.ref(f"{tag}_prior")
    ret = am.AuditAssignment.ref(f"{tag}_return")

    first_return = aggs.min(ret.event_ordinal).per(storage)

    conditions = (
        # the Storage observation
        am.AircraftStatusAudit(storage),
        storage.aircraft == am.Aircraft,
        storage.aircraft_status_code == am.STATUS_STORAGE,
        # its immediate predecessor must be In Service
        am.AircraftStatusAudit(prior),
        prior.aircraft == am.Aircraft,
        prior.aircraft_status_code == am.STATUS_IN_SERVICE,
        prior.event_ordinal == storage.event_ordinal - 1,
        # the minimal later In Service observation
        am.AircraftStatusAudit(ret),
        ret.aircraft == am.Aircraft,
        ret.aircraft_status_code == am.STATUS_IN_SERVICE,
        ret.event_ordinal > storage.event_ordinal,
        return_ordinal := first_return,
        ret.event_ordinal == return_ordinal,
    )
    return storage, ret, conditions


# ---------------------------------------------------------------------------------
# Q02 - status_reversion_spells
# ---------------------------------------------------------------------------------


def status_reversion_spells(
    aircraft_id: int,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """Q02 - every ``In Service -> Storage -> In Service`` spell, on the **audit** stream.

    Reading the daily projection here is the fatal mistake. The daily stream keeps only the
    final relevant observation per aircraft, dimension and date, so aircraft 1001's four
    same-day observations on 2020-06-01 (row sequences 5, 10, 20, 30 -> Maintenance,
    In Service, Storage, In Service) collapse to one and the zero-day spell at sequences 20 and
    30 disappears without any error. ``NEO4J_PARITY_MATRIX.md`` sells exactly that row as the
    differentiator over a coarse aircraft-plus-date state key.

    Three separately named refs over ``AircraftStatusAuditAssignment``:

    * ``storage`` - the Storage observation,
    * ``prior`` - its immediate predecessor, which must be In Service, at
      ``event_ordinal - 1``,
    * ``ret`` - the *minimal* later In Service observation, bound with the HAVING-style
      ``:=`` pattern so the aggregate can be compared inside ``where()``.

    ``event_ordinal`` is the shared dense DV-03 ordinal per (aircraft, dimension) over
    ``(AH-05, AH-03, AH-04, AH-01)``, which is what reduces "the next qualifying assignment"
    from a four-column lexicographic comparison to one integer comparison. Pairing with the
    *minimal* later In Service rather than any later one is what stops the first Storage from
    also pairing with the second spell's return.

    Nothing here de-duplicates on the watched status value. Consecutive equality is suppressed
    upstream but global equality is not, so ``In Service -> Storage -> In Service`` stays three
    assignments; a ``distinct()`` over the status would delete the second In Service and with it
    the spell. ``distinct()`` appears nowhere in this query.

    ``storage_days`` is a calendar-day difference and is 0 for the same-day spell. The audit
    stream carries no timestamps, so intraday elapsed time does not exist to be derived.
    """
    aircraft_id = _require_aircraft_id(aircraft_id)
    storage, ret, spell = _spell_bindings("q02")

    frame = (
        am.model.select(
            am.Aircraft.id.alias("aircraft_id"),
            storage.event.id.alias("storage_event_id"),
            storage.event_date.alias("storage_start_date"),
            storage.row_sequence.alias("storage_start_sequence"),
            ret.event.id.alias("return_event_id"),
            ret.event_date.alias("return_date"),
            ret.row_sequence.alias("return_sequence"),
            rdt.date.diff("day", storage.event_date, ret.event_date).alias("storage_days"),
            (storage.event_date == ret.event_date).alias("same_day"),
        )
        .where(am.Aircraft.id == aircraft_id, *spell)
        .to_df()
    )

    payload_columns = [name for name in Q02_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q02_COLUMNS,
        order_by=Q02_ORDER_BY,
        question_id="Q02",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q02F - fleet_storage_spell_distribution
# ---------------------------------------------------------------------------------

# (bucket_order, duration_bucket, minimum_days, maximum_days). The bounds are the
# specification 12.2 item 13 duration buckets, inclusive at both ends, and they tile the
# non-negative integers with no gap and no overlap. The open top bucket is closed at ten
# thousand years of storage rather than left unbounded, because a bucket dimension has to be a
# finite set of rows to be joinable and because the maximum spell in the fixture is 1,091 days.
_Q02F_BUCKETS: tuple[tuple[int, str, int, int], ...] = (
    (1, "ZERO_DAYS", 0, 0),
    (2, "DAYS_1_TO_7", 1, 7),
    (3, "DAYS_8_TO_30", 8, 30),
    (4, "DAYS_31_TO_90", 31, 90),
    (5, "DAYS_91_TO_365", 91, 365),
    (6, "DAYS_366_TO_730", 366, 730),
    (7, "DAYS_OVER_730", 731, 3_652_500),
)

_bucket_concept: Any = None


def storage_spell_bucket() -> Any:
    """The Q02F duration bucket, as a materialized joinable dimension. Built once per process.

    This deliberately mirrors Q03's ``MonthEnd``. Q03's frozen trap is "an approach that only
    works because the interval is regular"; the bucket bounds here are *deliberately* irregular
    (0, 1-7, 8-30, 31-90, 91-365, 366-730, 731+), which is precisely why they cannot be a
    computed step function and have to be data. Making them a concept turns the classification
    into a single inequality join - ``minimum_days <= storage_days <= maximum_days`` - so the
    whole distribution is one query rather than seven bucket-shaped queries, and the same query
    would answer a completely different set of buckets.

    It lives in this module rather than in ``aviation_model`` because it is question-private
    presentation: ``QUERY_ROUTING.md`` puts "the per-question output column names" and the
    result-set ordering on the catalog side of the boundary, and a storage-duration bucket
    label is the same kind of thing. Nothing temporal is defined here - the spell itself comes
    from :func:`_spell_bindings`, which is shared with Q02.

    Construction is lazy so that importing this module for Q01, Q03 or Q04 does not pay the
    re-index cost of a concept those questions never read. ``model.data`` drops any row with a
    null or an empty string anywhere in the frame (PROBE N-01), so the frame is built from the
    literal tuple above and is null-free by construction; the row count is asserted after the
    define for exactly that reason.
    """
    global _bucket_concept
    if _bucket_concept is not None:
        return _bucket_concept

    from relationalai.semantics import Integer, String

    bucket = am.model.Concept(
        "Q02FStorageSpellBucket", identify_by={"bucket_order": Integer}
    )
    bucket.duration_bucket = am.model.Property(
        f"{bucket} is labelled {String:duration_bucket}"
    )
    bucket.minimum_days = am.model.Property(f"{bucket} starts at {Integer:minimum_days}")
    bucket.maximum_days = am.model.Property(f"{bucket} ends at {Integer:maximum_days}")

    rows = am.model.data(
        pd.DataFrame(
            list(_Q02F_BUCKETS),
            columns=["bucket_order", "duration_bucket", "minimum_days", "maximum_days"],
        )
    )
    am.model.define(
        entry := bucket.new(bucket_order=rows.bucket_order),
        entry.duration_bucket(rows.duration_bucket),
        entry.minimum_days(rows.minimum_days),
        entry.maximum_days(rows.maximum_days),
    )

    _bucket_concept = bucket
    _assert_buckets_present(bucket)
    return bucket


def _assert_buckets_present(bucket: Any) -> None:
    """Fail loudly if the bucket dimension is not there, because the failure mode is silence.

    Two separate ways it can be missing, and both give an empty Q02F rather than an error:

    * ``model.data`` drops every row with a null or an empty string anywhere in the frame
      (PROBE N-01). The frame here is null-free by construction, so this is the cheap regression
      guard on that.
    * **A sibling process rebuilt the model.** This concept is added to the shared named model
      by a query module rather than by ``aviation_model``, so a concurrent process that imports
      ``aviation_model`` alone rewrites the model definition without it. Observed live: Q02F
      returned seven correct rows and then, later in the same pytest session, an empty frame,
      while a sibling query agent was running. The proper fix is for the bucket dimension to
      live in ``aviation_model``; until it does, this check turns a silently empty answer into a
      named one.
    """
    loaded = am.model.select(aggs.count(bucket).alias("n")).to_df()
    found = int(loaded.iloc[0]["n"]) if len(loaded) and loaded.shape[1] else 0
    if found != len(_Q02F_BUCKETS):
        raise AssertionError(
            f"Q02F bucket dimension holds {found} rows, expected {len(_Q02F_BUCKETS)}. "
            "Either model.data() dropped rows, or another process rebuilt the shared model "
            "without this query-module-local concept. Re-run this module alone."
        )


def fleet_storage_spell_distribution(
    aircraft_scope: str = "FLEET",
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 4,
) -> pd.DataFrame:
    """Q02F - the storage-spell duration distribution over the whole fleet. One query.

    D-0026: Q02's frozen parameter schema takes a non-nullable ``aircraft_id`` and may not be
    widened, so the fleet-wide view ships as its own question with its own parameter shape. The
    spell derivation is the identical :func:`_spell_bindings` with the per-aircraft filter
    simply not applied, so Q02 and Q02F cannot disagree about what a spell is.

    ``spell_count`` counts spells and ``aircraft_count`` counts *distinct aircraft*, and they
    differ in three of the seven buckets (38 vs 35, 89 vs 86, 163 vs 160) because one aircraft
    can contribute several spells to one bucket. That difference is the built-in check on
    Silent Corruption #4: an ``aircraft_count`` equal to ``spell_count`` in every bucket means
    the distinct wrapper was lost and the aggregate is counting spell tuples, not aircraft.

    Every bucket in the frozen answer is non-empty, so the inner join is not hiding an empty
    one. Were a bucket ever to go empty it would drop out rather than report zero, which is the
    right behaviour here for the same reason it is in Q03: the manifest freezes observed
    buckets, not a completed grid.
    """
    _require_enum(aircraft_scope, "aircraft_scope", Q02F_SCOPE_ENUM, "INVALID_AIRCRAFT_SCOPE")

    from relationalai.semantics.std import numbers

    bucket = storage_spell_bucket()
    _assert_buckets_present(bucket)
    storage, ret, spell = _spell_bindings("q02f")
    # ``date.diff`` yields the runtime's narrow INT while ``min``/``max`` declare their output
    # as the core ``Integer`` (INT128), and ``model2lqp._translate_aggregate`` asserts the two
    # are the same type. Measured live: ``min(TypeName.INT) had output type of
    # TypeName.INT128``, raised at compile time and not silently. ``numbers.integer`` widens the
    # input to match. ``count`` is exempt from that assertion, which is why ``spell_count``
    # never hit it.
    storage_days = numbers.integer(
        rdt.date.diff("day", storage.event_date, ret.event_date)
    )

    frame = (
        am.model.select(
            bucket.bucket_order.alias("bucket_order"),
            bucket.duration_bucket.alias("duration_bucket"),
            aggs.count(storage).per(bucket).alias("spell_count"),
            aggs.count(am.model.distinct(am.Aircraft)).per(bucket).alias("aircraft_count"),
            aggs.min(storage_days).per(bucket).alias("minimum_storage_days"),
            aggs.max(storage_days).per(bucket).alias("maximum_storage_days"),
        )
        .where(
            *spell,
            bucket.minimum_days <= storage_days,
            storage_days <= bucket.maximum_days,
        )
        .to_df()
    )

    payload_columns = [name for name in Q02F_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q02F_COLUMNS,
        order_by=Q02F_ORDER_BY,
        question_id="Q02F",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q03 - month_end_fleet_composition
# ---------------------------------------------------------------------------------


def month_end_fleet_composition(
    start_month_end: dt.date | str,
    end_month_end: dt.date | str,
    status: str = am.STATUS_IN_SERVICE,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """Q03 - in-service count per exact type at every month end. **One** query, not 120.

    The calendar is a joined dimension, not a parameter sweep. ``MonthEnd`` is a materialized
    concept over ``MODEL_INPUT.MONTH_END_CALENDAR``, and the join predicate is a pure
    inequality, so the identical query answers an irregular set of dates. Nothing here adds 30
    or 31 days, steps a month, or generates a series: writing the query 120 times and writing
    one that only works because the interval is regular are both explicit customer fails, and
    the second is the subtler of the two.

    The aggregation reads ``InServiceOnMonthEnd``, the shared model rule in
    ``computed_aircraft.py`` where the status clock and the type clock are two *independent*
    half-open joins against the same month end - visibly not aligned to each other - plus the
    half-open existence bound. Q01 and Q03 therefore cannot drift on the boundary semantics,
    which they would if this file restated the predicate.

    ``.per(MonthEnd, AircraftType)`` groups on the bare concepts. ``.per(...aircraft_type)``
    on the property instead would introduce a second anonymous iterator and cartesian-multiply
    the rows, and ``distinct()`` does not repair that one.

    The 120 month ends and two types give 240 possible cells but only 132 are nonzero, and the
    inner-join semantics already omit the rest. No ``| 0``, no completed grid, no filler rows.

    ``status`` is a validated single-value enum. The In Service predicate lives in the model
    rule, where it is shared, rather than being re-spelled per query; the frozen
    ``parameter_schema`` admits exactly one value, so validation is the whole of the parameter's
    job.
    """
    start = _require_date(start_month_end, "start_month_end", "INVALID_MONTH_END")
    end = _require_date(end_month_end, "end_month_end", "INVALID_MONTH_END")
    _require_enum(status, "status", Q03_STATUS_ENUM, "INVALID_STATUS")
    if start > end:
        raise QueryParameterError(
            "INVALID_MONTH_END_RANGE",
            f"start_month_end {start} is after end_month_end {end}",
        )

    frame = (
        am.model.select(
            am.MonthEnd.month_end.alias("month_end"),
            am.AircraftType.subseries.alias("aircraft_type_id"),
            am.AircraftType.aircraft_type.alias("aircraft_type"),
            aggs.count(am.Aircraft)
            .per(am.MonthEnd, am.AircraftType)
            .alias("in_service_aircraft_count"),
        )
        .where(
            am.InServiceOnMonthEnd(am.Aircraft, am.MonthEnd, am.AircraftType),
            am.MonthEnd.month_end >= start,
            am.MonthEnd.month_end <= end,
        )
        .to_df()
    )

    payload_columns = [name for name in Q03_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q03_COLUMNS,
        order_by=Q03_ORDER_BY,
        question_id="Q03",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q04 - type_engine_histories
# ---------------------------------------------------------------------------------


def type_engine_histories(
    aircraft_id: int,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """Q04 - the type stream and the engine stream side by side, never aligned.

    One concept plus a ``dimension`` discriminator, filtered - not two concepts unioned. The
    contract keys the daily assignment by ``(dimension, AH-02, AH-05, AH-01)``, so type and
    engine are two slices of one relation and ``model.union()`` would only invite divergent
    payload handling between the branches.

    The independence is the answer, and it is visible in the frozen rows: aircraft 1001's type
    stream breaks at 2019-01-01 and its engine stream at 2021-07-01, and neither boundary
    appears in the other. Any join of the two streams on overlapping validity, any merged
    timeline, any "as-of both" reconstruction returns more or fewer than four rows.

    ``definition_id`` and ``definition_label`` are one column each across both dimensions, so
    the two dimension-scoped payload columns are coalesced with the ``|`` fallback operator
    *inside* the query. The payload is already dimension-scoped in ``MODEL_INPUT`` - a type row
    carries no engine columns and vice versa - so the fallback is unambiguous.

    ``engine_count`` (AC-08) and ``mixed_engine_set_complete`` (DV-09) sit on the assignment,
    not on the ``EngineType`` identity, and type rows carry null in both. ``is_type_change`` is
    three-valued and comes from the shared derived property: ``false`` on the first type
    assignment, ``true`` on a real change, and *absent* on every engine row. Absence renders as
    null through the plain dot-chain; ``| None`` raises and ``| False`` would turn Q04's four
    frozen nulls into four wrong ``false`` cells.
    """
    aircraft_id = _require_aircraft_id(aircraft_id)
    tag = f"{next(_ref_counter)}"
    asgn = am.DailyAssignment.ref(f"q04_asgn_{tag}")

    frame = (
        am.model.select(
            am.Aircraft.id.alias("aircraft_id"),
            asgn.dimension.alias("dimension"),
            asgn.daily_assignment_id.alias("assignment_id"),
            asgn.valid_from.alias("valid_from"),
            asgn.valid_to.alias("valid_to"),
            (
                asgn.exact_aircraft_type_subseries | asgn.exact_engine_type_subseries
            ).alias("definition_id"),
            (asgn.aircraft_type_label | asgn.engine_type_label).alias("definition_label"),
            asgn.engine_count.alias("engine_count"),
            asgn.mixed_engine_set_complete.alias("mixed_engine_set_complete"),
            asgn.previous_definition_id.alias("previous_definition_id"),
            asgn.is_type_change.alias("is_type_change"),
        )
        .where(
            am.Aircraft.id == aircraft_id,
            asgn.aircraft == am.Aircraft,
            asgn.dimension.in_([am.DIM_AIRCRAFT_TYPE, am.DIM_ENGINE_TYPE]),
        )
        .to_df()
    )

    payload_columns = [name for name in Q04_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q04_COLUMNS,
        order_by=Q04_ORDER_BY,
        question_id="Q04",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# The frozen manifest, the nine invocations, and the comparison
# ---------------------------------------------------------------------------------

CATALOG: Mapping[str, dict[str, Any]] = {
    "Q01": {
        "callable": aircraft_as_of,
        "columns": Q01_COLUMNS,
        "order_by": Q01_ORDER_BY,
        "parameters": ("aircraft_id", "as_of_date"),
    },
    "Q02": {
        "callable": status_reversion_spells,
        "columns": Q02_COLUMNS,
        "order_by": Q02_ORDER_BY,
        "parameters": ("aircraft_id",),
    },
    "Q02F": {
        "callable": fleet_storage_spell_distribution,
        "columns": Q02F_COLUMNS,
        "order_by": Q02F_ORDER_BY,
        "parameters": ("aircraft_scope",),
    },
    "Q03": {
        "callable": month_end_fleet_composition,
        "columns": Q03_COLUMNS,
        "order_by": Q03_ORDER_BY,
        "parameters": ("start_month_end", "end_month_end", "status"),
    },
    "Q04": {
        "callable": type_engine_histories,
        "columns": Q04_COLUMNS,
        "order_by": Q04_ORDER_BY,
        "parameters": ("aircraft_id",),
    },
}

# Q02F is the v1.2.0 fleet-wide sibling of Q02 (D-0026). It is an aircraft-history question
# with no owner in QUERY_ROUTING.md, which was written against manifest v1.1.1 and predates it;
# UC2 owns Q05 to Q07 and ROT owns Q08, so it belongs here.
UC1_QUESTION_IDS = ("Q01", "Q02", "Q02F", "Q03", "Q04")


def load_manifest() -> dict[str, Any]:
    """``EXPECTED_ANSWERS.yaml``, parsed. FROZEN - read only, never written."""
    import yaml

    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def frozen_questions(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or load_manifest()
    return {
        question["question_id"]: question
        for question in manifest["questions"]
        if question["question_id"] in UC1_QUESTION_IDS
    }


def expected_frame(question_id: str, result_set: Mapping[str, Any]) -> pd.DataFrame:
    """The frozen rows as a DataFrame with the frozen columns and the frozen dtypes.

    Built from the manifest's own column list rather than from whatever the query returned, so
    a zero-row result still compares against the full declared schema.
    """
    columns = CATALOG[question_id]["columns"]
    rows = [
        {name: _NORMALISERS[name](row.get(name)) for name in columns if name != "row_id"}
        | {"row_id": row["row_id"]}
        for row in (result_set.get("rows") or [])
    ]
    frame = pd.DataFrame(rows, columns=list(columns), dtype=object)
    return frame[list(columns)]


def row_id_base(result_set: Mapping[str, Any], question_id: str) -> int:
    """The manifest's own ``row_id`` base for a result set, defaulting to 1 when empty."""
    return row_id_convention(result_set, question_id)[0]


def row_id_convention(
    result_set: Mapping[str, Any], question_id: str
) -> tuple[int, str, int]:
    """``(start, prefix, width)`` read off the manifest's own first ``row_id``.

    Two conventions are live at once. The v1.1.1 result sets label rows ``<QID>-R<nnn>``
    (``Q01-R001``, ``Q03-R132``) and every v1.2.0 result set labels them
    ``<RESULT_SET_ID>-R<nnnn>`` (``Q01-ENRICHED-MID-STORAGE-R0001``). ``row_id`` is a supplied
    manifest label, not a derived value - ``DEMO_QUESTIONS.md`` says so under D-0018 and the
    independent SQL oracles do not emit it either - so the convention is read from the frozen
    answer and then reproduced, and the cell-by-cell comparison is what checks it. A zero-row
    result set has no label to read and no rows to stamp.
    """
    rows = result_set.get("rows") or []
    if not rows:
        return 1, question_id, 3
    label, digits = str(rows[0]["row_id"]).rsplit("-R", 1)
    return int(digits), label, len(digits)


def compare(actual: pd.DataFrame, expected: pd.DataFrame) -> list[str]:
    """Complete cell-by-cell comparison after the declared order. Returns the diffs."""
    problems: list[str] = []
    if list(actual.columns) != list(expected.columns):
        problems.append(
            f"columns differ: got {list(actual.columns)} want {list(expected.columns)}"
        )
        return problems
    if len(actual) != len(expected):
        problems.append(f"row count differs: got {len(actual)} want {len(expected)}")
    for index in range(min(len(actual), len(expected))):
        for column in expected.columns:
            got, want = actual.iloc[index][column], expected.iloc[index][column]
            got = None if _is_missing(got) else got
            want = None if _is_missing(want) else want
            if got != want:
                problems.append(
                    f"row {index} column {column}: got {got!r} ({type(got).__name__}) "
                    f"want {want!r} ({type(want).__name__})"
                )
    return problems


def run_result_set(question_id: str, result_set: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Invoke one frozen result set and compare. Returns ``(verdict, problems)``."""
    entry = CATALOG[question_id]
    parameters = dict(result_set.get("parameters") or {})
    kwargs = {name: parameters[name] for name in entry["parameters"] if name in parameters}
    start, prefix, width = row_id_convention(result_set, question_id)
    kwargs["row_id_start"] = start
    kwargs["row_id_prefix"] = prefix
    kwargs["row_id_width"] = width
    expected_status = result_set.get("invocation_status")
    expected_code = result_set.get("error_code")

    try:
        actual = entry["callable"](**kwargs)
    except QueryParameterError as exc:
        if expected_status != "PARAMETER_ERROR":
            return "FAIL", [f"unexpected {exc.error_code} for an {expected_status} result set"]
        if exc.error_code != expected_code:
            return "FAIL", [f"error_code {exc.error_code} != frozen {expected_code}"]
        if result_set.get("rows"):
            return "FAIL", ["a PARAMETER_ERROR result set must freeze zero rows"]
        return "PASS", []

    if expected_status != "OK":
        return "FAIL", [
            f"expected {expected_status} / {expected_code} but the query returned "
            f"{len(actual)} rows"
        ]
    problems = compare(actual, expected_frame(question_id, result_set))
    cardinality = result_set.get("expected_cardinality")
    if cardinality is not None and len(actual) != cardinality:
        problems.append(f"cardinality {len(actual)} != frozen {cardinality}")
    distinct_month_ends = result_set.get("expected_distinct_month_ends")
    if distinct_month_ends is not None:
        observed = actual["month_end"].nunique()
        if observed != distinct_month_ends:
            problems.append(
                f"distinct month ends {observed} != frozen {distinct_month_ends}"
            )
    return ("PASS" if not problems else "FAIL"), problems


def main() -> int:
    """Run every frozen UC1 result set against the live engine and print a summary."""
    import time

    cold = warm_model()
    print(f"model sync {cold:.1f}s", flush=True)

    questions = frozen_questions()
    verdicts: list[tuple[str, str, int, float, list[str]]] = []
    for question_id in UC1_QUESTION_IDS:
        question = questions[question_id]
        for result_set in question["result_sets"]:
            started = time.time()
            try:
                verdict, problems = run_result_set(question_id, result_set)
            except Exception as exc:  # pragma: no cover - surfaced, never swallowed
                verdict, problems = "ERROR", [f"{type(exc).__name__}: {exc}"]
            verdicts.append(
                (
                    result_set["result_set_id"],
                    verdict,
                    int(result_set.get("expected_cardinality") or 0),
                    time.time() - started,
                    problems,
                )
            )

    width = max(len(name) for name, *_ in verdicts)
    print()
    print("QUERY-UC1 against the live aviation_temporal model")
    print("-" * (width + 34))
    for name, verdict, cardinality, elapsed, problems in verdicts:
        print(f"{name:<{width}}  {verdict:<5}  rows={cardinality:<4} {elapsed:6.1f}s")
        for problem in problems[:8]:
            print(f"{'':<{width}}         {problem}")
        if len(problems) > 8:
            print(f"{'':<{width}}         ... {len(problems) - 8} more")
    passed = sum(1 for _, verdict, *_ in verdicts if verdict == "PASS")
    print("-" * (width + 34))
    print(f"{passed}/{len(verdicts)} frozen result sets reproduced exactly")
    return 0 if passed == len(verdicts) else 1


if __name__ == "__main__":  # pragma: no cover - script entry
    raise SystemExit(main())
'''

_SRC_UC2 = r'''"""uc2.py - QUERY-UC2. Q05, Q06 and Q07 as live PyRel queries over ``aviation_temporal``.

Three schedule questions, one shared temporal predicate layer:

* **Q06** ``market_latest_vs_seven_days`` - market entries and exits between two exact
  knowledge endpoints. Knowledge clock **only**; there is no operating date and no weekday
  predicate anywhere in this question.
* **Q07** ``route_capacity_two_clocks`` - weekly frequency and cabin capacity as understood on
  a past knowledge date for one operating date. **Both** clocks, with their two different
  interval conventions.
* **Q05** ``schedule_four_week_changes`` - additions, removals, key-preserving modifications
  and conservative amendment evidence across consecutive eligible publish snapshots.

Build order was Q06, then Q07, then Q05, per ``build/design/QUERY_ROUTING.md``. That inverts
the numeric order deliberately: Q06 is the cheapest possible proof that snapshot eligibility,
route-state knowledge validity and exact carrier resolution all work, Q07 adds the second clock
and the capacity derivations to a surface Q06 has already proven, and Q05's amendment
classifier is the last thing to debug rather than the first.

Non-negotiables encoded here, each of which cost a real failure somewhere in this project:

1. **Two interval conventions, never one helper.** Knowledge validity is half-open
   (``valid_from <= d < valid_to``, ``aviation_model.known_on``); the operating window is
   inclusive at both ends (``effective_date <= d <= discontinue_date``,
   ``aviation_model.operates_on``). Both appear in the same ``where()`` in Q07. A single
   generic helper would silently make the operating upper bound exclusive, lose the last
   operating day, and break nine rows of ``TT-BOTH-CLOCKS`` while still looking plausible.
   Nothing in this module retypes either conjunction: they come from ``temporal.py``.
2. **Boolean properties are always compared.** ``where(RouteState.is_codeshare)`` matches all
   12,030 route states because a bare property reference *binds* the value instead of testing
   it (MODEL-01 finding M-01). Every boolean filter reached from here goes through a named
   model relationship (``RouteStateIsPhysicalRepresentative``,
   ``RouteStateOperatesOnWeekday``) or is written ``== True``.
3. **RAI ``Date`` values arrive as pandas ``Timestamp``.** Comparing one to
   ``datetime.date(...)`` matches nothing and passes vacuously (MODEL-01 finding M-02). Every
   cell leaving this module is normalised to a Python native by :func:`_cell`, so the frames
   compare against ``EXPECTED_ANSWERS.yaml`` by value.
4. **An empty RAI result is a zero-*column* DataFrame**, not a zero-row frame with the
   expected columns (PROBE D11). Every function assembles its own column list, so
   ``Q07-KNOWLEDGE-END-EMPTY`` returns a correctly shaped empty frame with
   ``invocation_status = OK``.
5. **Marketing and operating are separate carrier dimensions.** ``carrier_role`` is required
   with no default in both Q06 and Q07. For the operating role, Q07 counts only a D-0007
   physical base representative, so a codeshare-only service is emitted as visibly
   ``UNRESOLVED_PHYSICAL_SERVICE`` with every measure null rather than double counted or
   silently dropped. Physical capacity may therefore visibly *undercount* codeshare-only
   service; that is the contracted behaviour, not a defect.
6. **An incomplete or missing snapshot never manufactures a removal.** Eligibility is
   ``is_present AND is_complete`` and nothing else. Q05 and Q06 share the definition and
   differ only in their refusal policy: Q06 requires both *exact* endpoints to be eligible and
   refuses rather than falling back to the previous eligible date.
7. **A key-shifting amendment is never asserted as an exact modification.** ``schedule_key``
   hashes the effective and discontinue dates, so shifting either date mints a new key and
   presence comparison sees one removal plus one unrelated addition. Those two exact rows
   survive, and the relationship between them is reported separately as ``CANDIDATE_UNIQUE``
   at ``CANDIDATE`` exactness and ``MEDIUM`` confidence. Where one removal is compatible with
   two additions the answer is an ``AMBIGUOUS_CANDIDATE_GROUP`` plus its members at ``LOW``
   confidence with no pair chosen.

Where the query logic lives
---------------------------

Filtering, joining and aggregation happen in PyRel. What this module does in Python is
parameter validation, the typed error codes, the normalised union of the Q05 branches, the
frozen row ordering, and the supplied-label layer below. ``QUERY_ROUTING.md`` assigns exactly
those to the catalog layer.

Two acknowledged gaps against ``QUERY_ROUTING.md``, both consequences of file ownership rather
than of taste:

* Q05's normalised ``ScheduleChangeEvent`` view is *preferred* in the ontology. This module may
  not write the ontology package, so the five branches are unioned here, each branch emitting
  the full 16-column schema with explicit nulls. RAI 1.20.1 has no fragment union either
  (``model.union(a, b).to_df()`` raises ``[Missing arg]``, PROBE D5/D6), so even inside the
  ontology this would be a set of ``define`` rules rather than one query.
* ``event_class_rank`` is likewise preferred on the concept. It is a module constant here,
  taken from the manifest's ``enum_sort_ranks.Q05_event_class``.

Supplied manifest labels (D-0018)
---------------------------------

``row_id`` in all three questions, and ``Q05-CANONICAL``'s ``event_id`` for its five declared
classes, are **not derivable**. D-0018 proved this twice: the Q05 mnemonics follow no
generative rule (``SYN-SK-BASE_100`` maps to ``BASE`` while ``SYN-SK-PHY_BASE_700`` maps to
``CAP-700`` under one event class and one field name), and the declared row sequence is
separately unrecoverable because on 2026-08-31 the ``EXACT_ADDITION`` block orders
``[MKT_ENTRY_714, UNPAIR_NEW]`` while the ``UNPAIRED_ADDITION`` block orders the identical pair
inverted. The contracted identities are SHA-256 digests (measured: ``728f067e...`` for the one
amendment candidate), not mnemonics.

D-0018's QUERY-UC2 binding is therefore honoured literally: the label map is **not** in the
ontology and **not** hard-coded here. Every query function takes an optional
:class:`LabelSource`; without one, ``row_id`` and the declared ``event_id`` values render as
visible ``UNLABELLED|...`` tokens so a missing, extra or misclassified event cannot be masked.
:func:`manifest_label_source` builds a :class:`LabelSource` from ``EXPECTED_ANSWERS.yaml`` and
joins it on the *independently computed* semantic identity, which is what the conformance
harness in :func:`main` and ``tests/test_uc2.py`` uses. The three candidate/group/member
``event_id`` values are computed here from the manifest-adopted string templates
``SYN-CAND-<YYYYMMDD>-NN``, ``SYN-AMB-<YYYYMMDD>-NN`` and ``<group_id>-M<k>``, with their
ordinals ranked **in PyRel**.

The verdict is reported as two, apart and labelled, exactly as D-0018 requires: an order-free
**semantic** verdict over the columns the query derives (:func:`compare_semantic`), and a
**presentation** verdict over the declared sequence and the supplied identifier columns
(:func:`compare_rows`). Passing the second is evidence the module applies the labels, not that
it recovered them.

At manifest 1.2.0 the supplied surface **shrank on its own**. D-0023's enriched Q05 result sets
freeze the fail-loud token itself as their ``event_id``, and that token is a pure function of
the semantic identity, so :func:`unlabelled_event_id` reproduces every enriched declared-class
``event_id`` cell with no manifest input - 345 in ``Q05-ENRICHED`` and 78 in
``Q05-ENRICHED-GAP-PAIRS``. Of the 20 UC2 result sets, only ``Q05-CANONICAL``'s 30 mnemonics
are a genuinely supplied ``event_id``.

Running
-------

    .venv/bin/rai reasoners resume --type Logic --name aviation_temporal_logic_s --wait
    PYTHONPATH=rai_code .venv/bin/python rai_code/queries/uc2.py

Measured 2026-09-02 on ``aviation_temporal_logic_s`` (HIGHMEM_X64_S) against the post-D-0023
reload: 133.5s model install, index and CDC re-sync; all 20 result sets in 217.0s with a 7.98s
median and a 69.15s worst case (``Q05-CANONICAL``, which pays first touch on the four amendment
relations - the 392-row ``Q05-ENRICHED`` behind it costs 23.28s).

The three query modules share one model on one engine, and importing any of them is a **write**
transaction. A read issued while a sibling holds that lock fails with ``prepareIndex: The model
is currently locked by active write transaction(s)`` rather than waiting, so :func:`warm_model`
retries. Blocking on a sibling's install was measured at roughly 13 minutes; that is contention,
not a hang.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ANSWERS = REPO_ROOT / "EXPECTED_ANSWERS.yaml"

CARRIER_ROLE_MARKETING = "marketing"
CARRIER_ROLE_OPERATING = "operating"
CARRIER_ROLES = (CARRIER_ROLE_MARKETING, CARRIER_ROLE_OPERATING)

# --- frozen output schemas ---------------------------------------------------------
#
# Column lists are spelled out rather than read from EXPECTED_ANSWERS.yaml so that a
# manifest edit cannot silently reshape a query result, and so an empty result still has
# the right columns (PROBE D11: an empty RAI frame has none at all).

Q05_COLUMNS: tuple[str, ...] = (
    "row_id",
    "comparison_date",
    "previous_knowledge_date",
    "event_id",
    "event_class",
    "exactness",
    "confidence",
    "schedule_key",
    "related_schedule_key",
    "field_name",
    "old_value",
    "new_value",
    "group_id",
    "member_side",
    "member_schedule_key",
    "crosses_snapshot_gap",
)

Q06_COLUMNS: tuple[str, ...] = (
    "row_id",
    "carrier_role",
    "airline_id",
    "route_id",
    "change_kind",
    "before_schedule_count",
    "after_schedule_count",
    "comparison_knowledge_date",
    "latest_knowledge_date",
)

Q07_COLUMNS: tuple[str, ...] = (
    "row_id",
    "result_status",
    "carrier_role",
    "airline_id",
    "route_id",
    "knowledge_date",
    "operating_date",
    "active_schedule_count",
    "weekly_frequency",
    "weekly_total_seats",
    "weekly_first_seats",
    "weekly_business_seats",
    "weekly_premium_economy_seats",
    "weekly_economy_excluding_premium_seats",
    "cabin_quality",
    "unresolved_service_key",
)

# --- Q05 semantic enums -----------------------------------------------------------
#
# The frozen order is by this rank, not alphabetical: sorting on the class name would put
# AMBIGUOUS_* first and fail the declared sequence. Taken verbatim from
# EXPECTED_ANSWERS.yaml canonicalization.enum_sort_ranks.Q05_event_class.

EVENT_CLASS_RANK: Mapping[str, int] = {
    "EXACT_KEY_PRESERVING_MODIFICATION": 10,
    "EXACT_ADDITION": 20,
    "EXACT_REMOVAL": 30,
    "CANDIDATE_UNIQUE": 40,
    "AMBIGUOUS_CANDIDATE_GROUP": 50,
    "AMBIGUOUS_GROUP_MEMBER": 60,
    "UNPAIRED_ADDITION": 70,
    "UNPAIRED_REMOVAL": 80,
}

# Exactness and confidence for the three exact classes. The other five classes carry these
# as bound MODEL_INPUT columns and are read from the model, never mapped here.
EXACT_EXACTNESS = "EXACT"
EXACT_CONFIDENCE = "EXACT"
EXACT_CLASSES = (
    "EXACT_KEY_PRESERVING_MODIFICATION",
    "EXACT_ADDITION",
    "EXACT_REMOVAL",
)
DECLARED_LABEL_CLASSES = EXACT_CLASSES + ("UNPAIRED_ADDITION", "UNPAIRED_REMOVAL")
AMBIGUOUS_MEMBER_CLASS = "AMBIGUOUS_GROUP_MEMBER"
AMBIGUOUS_GROUP_CLASS = "AMBIGUOUS_CANDIDATE_GROUP"
CANDIDATE_UNIQUE_CLASS = "CANDIDATE_UNIQUE"

# DV-37 side enumeration. REMOVED sorts before ADDED in the ``-Mk`` member ordinal, which is
# the manifest-adopted rule and not alphabetical.
SIDE_REMOVED = "REMOVED"
SIDE_ADDED = "ADDED"

PRESENCE_FIELD = "__presence__"
RESULT_COUNTED = "COUNTED"
RESULT_UNRESOLVED = "UNRESOLVED_PHYSICAL_SERVICE"
CABIN_RECONCILED = "RECONCILED"
CABIN_UNRECONCILED = "UNRECONCILED"
CABIN_NOT_COUNTED = "NOT_COUNTED"

_UNLABELLED = "UNLABELLED"


# --------------------------------------------------------------------------- errors


class Uc2InvocationError(RuntimeError):
    """A refusal that carries the frozen ``invocation_status`` and ``error_code``.

    ``EXPECTED_ANSWERS.yaml`` distinguishes three kinds of zero-row answer and the catalog
    layer must be able to tell them apart: a ``PARAMETER_ERROR`` raised before any query runs,
    an endpoint refusal (``ENDPOINT_MISSING`` / ``ENDPOINT_INCOMPLETE``) where the query is
    deliberately not run, and a legitimately empty ``OK`` result. The third is a DataFrame,
    not an exception - ``Q07-KNOWLEDGE-END-EMPTY`` is zero rows with status ``OK``.
    """

    def __init__(self, invocation_status: str, error_code: str, message: str) -> None:
        super().__init__(f"{error_code}: {message}")
        self.invocation_status = invocation_status
        self.error_code = error_code


class ParameterError(Uc2InvocationError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__("PARAMETER_ERROR", error_code, message)


class EndpointError(Uc2InvocationError):
    """``invocation_status`` equals the ``error_code`` for the two endpoint refusals."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(error_code, error_code, message)


# --------------------------------------------------------------- parameter validation


def _coerce_date(value: Any, missing_code: str, name: str) -> dt.date:
    """A required ``DATE`` parameter, with the two frozen failure modes kept apart.

    ``Q06-INVALID-DATE`` passes the string ``2026-02-30``, which is uncastable rather than
    absent, and freezes ``INVALID_DATE``. A null parameter is a different fault and gets its
    own code. Both are raised before any query is sent.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParameterError(missing_code, f"{name} is required and has no default")
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ParameterError(
                "INVALID_DATE", f"{name}={value!r} is not a valid calendar date ({exc})"
            ) from exc
    raise ParameterError("INVALID_DATE", f"{name}={value!r} is not a date")


def _coerce_carrier_role(value: Any) -> str:
    """``carrier_role`` is required with no default in both Q06 and Q07.

    Marketing and operating are separate carrier dimensions and never collapse, so a null is
    a clarification state at the API boundary rather than an opportunity to pick one.
    ``Q06-MISSING-CARRIER-ROLE`` and ``Q07-MISSING-CARRIER-ROLE`` both freeze
    ``MISSING_CARRIER_ROLE``.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParameterError(
            "MISSING_CARRIER_ROLE",
            "carrier_role is required and has no default; marketing and operating are "
            "separate carrier dimensions",
        )
    role = str(value).strip()
    if role not in CARRIER_ROLES:
        raise ParameterError(
            "INVALID_CARRIER_ROLE",
            f"carrier_role={value!r} is not one of {CARRIER_ROLES}",
        )
    return role


def _coerce_cadence_days(value: Any) -> int:
    """``cadence_days`` is validated and then does not filter, exactly as the SQL oracle does.

    ``parameter_schema`` declares it non-nullable with ``minimum: 1``, and the independent
    oracle binds it in its ``params`` CTE and never references it again: the Q05 window is
    ``eligible_dates BETWEEN start AND end`` plus adjacency, which is already the cadence the
    snapshot calendar publishes. Filtering on it would silently drop the 21- and 28-day
    October comparisons from any wider window, so it stays a declared, validated,
    non-filtering parameter and this docstring is the disclosure.
    """
    if value is None:
        raise ParameterError("MISSING_CADENCE_DAYS", "cadence_days is required")
    try:
        cadence = int(value)
    except (TypeError, ValueError) as exc:
        raise ParameterError(
            "INVALID_CADENCE_DAYS", f"cadence_days={value!r} is not an integer"
        ) from exc
    if cadence < 1:
        raise ParameterError(
            "INVALID_CADENCE_DAYS", f"cadence_days={cadence} violates minimum 1"
        )
    return cadence


# ------------------------------------------------------------------- the loaded model


_MODEL_PACKAGE: Any = None


def model_package() -> Any:
    """The loaded ``aviation_model`` package, imported once per interpreter.

    ``aviation_model.model`` is a module-level singleton on purpose: the free
    ``distinct(...)`` raises ``[Ambiguous model]`` the moment a second ``Model`` exists in the
    same process (PROBE N-02), and every fresh ``Model`` pays 25-100s of indexing before its
    first query.
    """
    global _MODEL_PACKAGE
    if _MODEL_PACKAGE is None:
        rai_code = str(REPO_ROOT / "rai_code")
        if rai_code not in sys.path:
            sys.path.insert(0, rai_code)
        import aviation_model  # noqa: PLC0415 - deliberately lazy; the import loads the model

        _MODEL_PACKAGE = aviation_model
    return _MODEL_PACKAGE


def _weekday_relationship() -> Any:
    from aviation_model.computed_schedule import (  # noqa: PLC0415
        RouteStateOperatesOnWeekday,
    )

    return RouteStateOperatesOnWeekday


def _physical_representative() -> Any:
    from aviation_model.computed_schedule import (  # noqa: PLC0415
        RouteStateIsPhysicalRepresentative,
    )

    return RouteStateIsPhysicalRepresentative


# ------------------------------------------------------------------ cell normalisation


def _cell(value: Any) -> Any:
    """One RAI cell as a Python native, or ``None``.

    RAI ``Date`` properties arrive as pandas ``Timestamp`` and integer aggregates as
    ``Int128``; comparing either to a frozen ``datetime.date`` or ``int`` fails or, worse,
    passes vacuously (MODEL-01 finding M-02). Absence arrives as ``NaN`` in a ``StringDtype``
    column (PROBE D1), which is the frozen ``null``.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, dt.datetime):
        return value.date()
    return value


def _as_date(value: Any) -> dt.date | None:
    cell = _cell(value)
    if cell is None:
        return None
    if isinstance(cell, dt.date):
        return cell
    return dt.date.fromisoformat(str(cell))


def _as_int(value: Any) -> int | None:
    cell = _cell(value)
    return None if cell is None else int(cell)


def _as_float(value: Any) -> float | None:
    cell = _cell(value)
    return None if cell is None else float(cell)


def _as_bool(value: Any) -> bool | None:
    cell = _cell(value)
    return None if cell is None else bool(cell)


def _as_str(value: Any) -> str | None:
    cell = _cell(value)
    return None if cell is None else str(cell)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows of a RAI frame as dicts, tolerating the zero-column empty frame (PROBE D11)."""
    if df.shape[1] == 0 or df.shape[0] == 0:
        return []
    return df.to_dict("records")


# ------------------------------------------------------------------- supplied labels


@dataclass(frozen=True)
class LabelSource:
    """The supplied manifest labels, joined on an independently computed semantic identity.

    ``row_ids`` is keyed on the question's derived identity tuple; ``event_ids`` is Q05 only
    and is keyed on ``(comparison_date, event_class, schedule_key, field_name)`` exactly as
    ``data/oracles/q05_event_labels.sql`` is, which D-0018's reviewer proved collision-free
    over the five declared classes. Every value in both maps is *supplied*, not derived; the
    fourteen other Q05 columns and every Q06/Q07 measure are computed from the model.
    """

    row_ids: Mapping[tuple, str] = field(default_factory=dict)
    event_ids: Mapping[tuple, str] = field(default_factory=dict)

    def row_id(self, identity: tuple, fallback_kind: str) -> str:
        supplied = self.row_ids.get(identity)
        if supplied is not None:
            return supplied
        return _unlabelled(fallback_kind, identity)

    def event_id(self, identity: tuple) -> str:
        supplied = self.event_ids.get(identity)
        if supplied is not None:
            return supplied
        return unlabelled_event_id(identity)


EMPTY_LABELS = LabelSource()


def _unlabelled_token(identity: Sequence[Any]) -> str:
    """``UNLABELLED|<part>|<part>...``, with ``None`` rendered as an empty part."""
    parts = "|".join("" if p is None else str(p) for p in identity)
    return f"{_UNLABELLED}|{parts}"


def _unlabelled(kind: str, identity: Sequence[Any]) -> str:
    """A visible fail-loud token.

    D-0018: an event the query computes that the label table does not carry must render as a
    diagnostic string, never as a plausible-looking valid label, so the label join cannot mask
    an extra, missing or misclassified event.
    """
    return _unlabelled_token((kind, *identity))


def unlabelled_event_id(identity: Sequence[Any]) -> str:
    """The Q05 fail-loud ``event_id``, ``UNLABELLED|`` plus the semantic identity itself.

    Deliberately *derivable*: it is a pure function of the four semantic-identity columns
    ``(comparison_date, event_class, schedule_key, field_name)`` that the query already
    computes, with no manifest input. The 1.2.0 enriched Q05 result sets freeze exactly this
    string for their declared-class events - 345 in ``Q05-ENRICHED`` and 78 in
    ``Q05-ENRICHED-GAP-PAIRS`` - so those ``event_id`` cells are recomputed rather than
    supplied, and the supplied-label problem D-0018 documents is confined to
    ``Q05-CANONICAL``'s 30 hand-authored mnemonics.

    Fail-loud survives the change: an extra, missing or misclassified event produces a token
    that differs from the frozen one in exactly the field that was got wrong, so the label
    join still cannot mask it.
    """
    return _unlabelled_token(identity)


def _q05_row_identity(row: Mapping[str, Any]) -> tuple:
    return (
        row["comparison_date"],
        row["event_class"],
        row["schedule_key"],
        row["related_schedule_key"],
        row["field_name"],
        row["group_id"],
        row["member_side"],
        row["member_schedule_key"],
    )


def _q05_label_identity(row: Mapping[str, Any]) -> tuple:
    """The ``q05_event_labels`` key: field_name is '' for the two unpaired classes."""
    return (
        row["comparison_date"],
        row["event_class"],
        row["schedule_key"],
        row["field_name"] or "",
    )


def _q06_row_identity(row: Mapping[str, Any]) -> tuple:
    return (row["carrier_role"], row["change_kind"], row["airline_id"], row["route_id"])


def _q07_row_identity(row: Mapping[str, Any]) -> tuple:
    return (row["result_status"], row["carrier_role"], row["airline_id"], row["route_id"])


_ROW_IDENTITY: Mapping[str, Callable[[Mapping[str, Any]], tuple]] = {
    "Q05": _q05_row_identity,
    "Q06": _q06_row_identity,
    "Q07": _q07_row_identity,
}


def _load_manifest() -> Mapping[str, Any]:
    import yaml  # noqa: PLC0415

    with EXPECTED_ANSWERS.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def manifest_label_source(
    question_id: str,
    manifest: Mapping[str, Any] | None = None,
    result_set_id: str | None = None,
) -> LabelSource:
    """Build a :class:`LabelSource` from the frozen manifest. Conformance harness only.

    This is the D-0018 "shared conformance harness" seam. The label *values* live in
    ``EXPECTED_ANSWERS.yaml`` and are read at comparison time; they are not embedded in the
    ontology (which would put the frozen answer inside the artifact whose independence the
    demo asserts) and they are not literals in this file. The join key is computed from the
    query's own output columns, so supplying labels cannot change any derived cell.

    **``result_set_id`` scoping is required at manifest 1.2.0, not optional.** The semantic
    identity is unique *within* a result set but not across them, because D-0023's additive
    enrichment added result sets that re-ask the same question at different parameters. Q07's
    three enriched marketing sets share all 30 ``(result_status, carrier_role, airline_id,
    route_id)`` identities while declaring different ``row_id`` prefixes, and 87 of Q05's
    ``Q05-ENRICHED-GAP-PAIRS`` identities recur inside ``Q05-ENRICHED``. A question-wide map
    would silently resolve those 117 collisions last-write-wins and label one result set with
    another's identifiers - the precise class of masking D-0018 exists to prevent. Building
    the map question-wide is therefore still allowed but raises on a conflicting collision
    rather than picking a winner.
    """
    manifest = manifest or _load_manifest()
    identity = _ROW_IDENTITY[question_id]
    row_ids: dict[tuple, str] = {}
    event_ids: dict[tuple, str] = {}
    for question in manifest["questions"]:
        if question["question_id"] != question_id:
            continue
        for result_set in question["result_sets"]:
            if result_set_id is not None and result_set["result_set_id"] != result_set_id:
                continue
            for raw in result_set.get("rows") or ():
                row = _manifest_row(raw)
                key = identity(row)
                previous = row_ids.get(key)
                if previous is not None and previous != row["row_id"]:
                    raise ValueError(
                        f"{question_id}: identity {key!r} carries both {previous!r} and "
                        f"{row['row_id']!r} across result sets; pass result_set_id"
                    )
                row_ids[key] = row["row_id"]
                if question_id == "Q05" and row["event_class"] in DECLARED_LABEL_CLASSES:
                    event_ids[_q05_label_identity(row)] = row["event_id"]
    return LabelSource(row_ids=row_ids, event_ids=event_ids)


_DATE_COLUMNS = frozenset(
    {
        "comparison_date",
        "previous_knowledge_date",
        "comparison_knowledge_date",
        "latest_knowledge_date",
        "knowledge_date",
        "operating_date",
    }
)


def _manifest_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """One frozen row with its declared representations applied.

    ``canonicalization.date_representation`` is "quoted ISO YYYY-MM-DD, cast to DATE before
    comparison", so the quoted scalars become ``datetime.date`` here rather than being
    string-compared against a normalised query cell.
    """
    row = dict(raw)
    for column in _DATE_COLUMNS & set(row):
        if row[column] is not None:
            row[column] = dt.date.fromisoformat(str(row[column]))
    return row


# ------------------------------------------------------------- snapshot eligibility


_SNAPSHOT_CALENDAR: dict[dt.date, tuple[bool, bool]] | None = None


def snapshot_calendar(refresh: bool = False) -> Mapping[dt.date, tuple[bool, bool]]:
    """``{expected_publish_date: (is_present, is_complete)}`` from the live model.

    The eligibility control is a separate small query that runs *before* the change or market
    query, which is what makes an endpoint refusal distinguishable from a natural empty
    result. Eligibility is ``is_present AND is_complete`` and nothing else: SC-05 observed row
    counts are validation evidence, never a completeness test - note 2026-10-26 is complete
    with an observed row count of zero, and 2026-10-19 is present with 9,917 rows and
    incomplete.
    """
    global _SNAPSHOT_CALENDAR
    if _SNAPSHOT_CALENDAR is not None and not refresh:
        return _SNAPSHOT_CALENDAR
    am = model_package()
    df = am.model.select(
        am.SnapshotDate.expected_publish_date.alias("expected_publish_date"),
        am.SnapshotDate.is_present.alias("is_present"),
        am.SnapshotDate.is_complete.alias("is_complete"),
    ).to_df()
    calendar: dict[dt.date, tuple[bool, bool]] = {}
    for row in _records(df):
        day = _as_date(row["expected_publish_date"])
        if day is None:
            continue
        calendar[day] = (bool(_as_bool(row["is_present"])), bool(_as_bool(row["is_complete"])))
    _SNAPSHOT_CALENDAR = calendar
    return calendar


def _require_eligible_endpoints(endpoints: Sequence[tuple[str, dt.date]]) -> None:
    """Refuse an ineligible endpoint. Missing takes precedence over incomplete.

    Both Q05 and Q06 require *exact* endpoints. Falling back to the previous eligible date
    would answer a different question: ``Q06-INCOMPLETE-ENDPOINT`` compares 2026-10-26 with
    2026-10-19, and the previous eligible complete snapshot before 2026-10-19 is 2026-10-05.
    Returning that comparison's rows is wrong, not lenient.
    """
    calendar = snapshot_calendar()
    absent = [
        (name, day)
        for name, day in endpoints
        if day not in calendar or not calendar[day][0]
    ]
    if absent:
        detail = ", ".join(f"{name}={day.isoformat()}" for name, day in absent)
        raise EndpointError(
            "ENDPOINT_MISSING",
            f"snapshot not present for {detail}; an absent snapshot cannot be substituted "
            "and never manufactures a change",
        )
    incomplete = [(name, day) for name, day in endpoints if not calendar[day][1]]
    if incomplete:
        detail = ", ".join(f"{name}={day.isoformat()}" for name, day in incomplete)
        raise EndpointError(
            "ENDPOINT_INCOMPLETE",
            f"snapshot present but incomplete for {detail}; an incomplete snapshot is not "
            "an eligible endpoint and is never silently replaced by an earlier one",
        )


# ------------------------------------------------------------------------- ordering


def _sort_key(row: Mapping[str, Any], keys: Sequence[str]) -> tuple:
    """Frozen ``order_by`` with nulls last in every nullable key.

    ``canonicalization.object_rules``: "Nulls sort last in every nullable order key". A plain
    tuple sort would raise on ``None`` against ``str``, so each key becomes
    ``(is_null, value)``.
    """
    out: list[tuple[int, Any]] = []
    for key in keys:
        value = row[key]
        out.append((1, "") if value is None else (0, value))
    return tuple(out)


def _frame(rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> pd.DataFrame:
    """An ``object``-dtype frame with exactly the frozen columns.

    ``object`` dtype is deliberate: it keeps ``None`` as ``None`` rather than promoting an
    integer column with a null into ``float`` and turning the frozen ``null`` into ``NaN``,
    which is what ``Q07-R004``'s seven null measures need.
    """
    materialised = [dict(row) for row in rows]
    frame = pd.DataFrame(materialised, columns=list(columns), dtype=object)
    return frame.reset_index(drop=True)


# ============================================================================== Q06


def _q06_carrier_link(state: Any, airline: Any, role: str) -> Any:
    """The role-specific exact carrier link.

    Only an ``EXACT`` cardinality-one resolution creates the link in the ontology, so an
    ambiguous or unresolved carrier code cannot produce an airline-level market at all. The
    raw code stays bound as a string on the state; it is never substituted for an identity.
    """
    am = model_package()
    if role == CARRIER_ROLE_MARKETING:
        return state.marketing_airline == airline
    return state.operating_airline == airline


def _q06_side(
    role: str,
    live_on: dt.date,
    absent_on: dt.date,
) -> list[tuple[str, str, int]]:
    """Markets live at ``live_on`` with no state at ``absent_on``, and their key counts.

    A correlated NOT EXISTS: the inner ``where`` is a subquery with its own fresh
    ``RouteState`` ref, correlated to the outer query through the shared ``Airline`` and
    ``Route`` entities. ``model.not_(A, B)`` is ``NOT (A AND B)``, so both clock clauses and
    both link clauses belong inside **one** ``not_(where(...))`` - "there is no state that is
    both this market and live at the other endpoint", not "no state for this market" AND "no
    state live at the other endpoint".

    Knowledge clock only. There is no operating date and no weekday predicate in Q06: the
    question is when knowledge changed, not which service operates on some other date, and
    adding an operating filter is a category error rather than a refinement.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    live = am.RouteState.ref("live")
    other = am.RouteState.ref("other")
    df = am.model.select(
        distinct(
            am.Airline.airline_id.alias("airline_id"),
            am.Route.route_id.alias("route_id"),
            aggs.count(am.Schedule).per(am.Airline, am.Route).alias("schedule_count"),
        )
    ).where(
        *am.known_on(live, live_on),
        _q06_carrier_link(live, am.Airline, role),
        live.route == am.Route,
        live.schedule == am.Schedule,
        am.model.not_(
            am.model.where(
                *am.known_on(other, absent_on),
                _q06_carrier_link(other, am.Airline, role),
                other.route == am.Route,
            )
        ),
    ).to_df()
    return [
        (str(row["airline_id"]), str(row["route_id"]), int(_as_int(row["schedule_count"]) or 0))
        for row in _records(df)
    ]


def market_latest_vs_seven_days(
    latest_knowledge_date: dt.date | str | None,
    comparison_knowledge_date: dt.date | str | None,
    carrier_role: str | None,
    *,
    labels: LabelSource | None = None,
) -> pd.DataFrame:
    """Q06 - market entries and exits between two exact knowledge endpoints.

    Grain is ``(carrier_role, exact resolved airline, directional route)`` and the measure is
    the count of distinct eligible schedule keys. ``ENTRY`` is zero to positive, ``EXIT`` is
    positive to zero; every other transition (1 to 2, 2 to 1) is deliberately not an event,
    which is what the stable positive market shadows in the universe exercise. If more than
    two rows come back on the canonical parameters the cause is almost certainly a clock
    predicate that is too narrow, not a missing filter.

    Both endpoints must be eligible complete snapshots and neither is ever substituted.
    """
    latest = _coerce_date(
        latest_knowledge_date, "MISSING_LATEST_KNOWLEDGE_DATE", "latest_knowledge_date"
    )
    comparison = _coerce_date(
        comparison_knowledge_date,
        "MISSING_COMPARISON_KNOWLEDGE_DATE",
        "comparison_knowledge_date",
    )
    role = _coerce_carrier_role(carrier_role)
    label_source = labels or EMPTY_LABELS

    _require_eligible_endpoints(
        (("comparison_knowledge_date", comparison), ("latest_knowledge_date", latest))
    )

    rows: list[dict[str, Any]] = []
    for airline_id, route_id, after_count in _q06_side(role, latest, comparison):
        rows.append(
            {
                "carrier_role": role,
                "airline_id": airline_id,
                "route_id": route_id,
                "change_kind": "ENTRY",
                "before_schedule_count": 0,
                "after_schedule_count": after_count,
                "comparison_knowledge_date": comparison,
                "latest_knowledge_date": latest,
            }
        )
    for airline_id, route_id, before_count in _q06_side(role, comparison, latest):
        rows.append(
            {
                "carrier_role": role,
                "airline_id": airline_id,
                "route_id": route_id,
                "change_kind": "EXIT",
                "before_schedule_count": before_count,
                "after_schedule_count": 0,
                "comparison_knowledge_date": comparison,
                "latest_knowledge_date": latest,
            }
        )

    rows.sort(key=lambda row: _sort_key(row, ("change_kind", "airline_id", "route_id")))
    for row in rows:
        row["row_id"] = label_source.row_id(_q06_row_identity(row), "Q06")
    return _frame(rows, Q06_COLUMNS)


def market_count_at(knowledge_date: dt.date, carrier_role: str) -> int:
    """Distinct ``(airline, route)`` markets live at one knowledge date.

    Exists for the entries/exits partition check: ``n_latest - entries`` and
    ``n_comparison - exits`` must both equal the intersection. If they disagree the
    correlation in :func:`_q06_side` is not binding and the ``not_()`` is testing "no such
    state anywhere" rather than "no such state for this market", which is the classic failure
    of the correlated anti-join.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    role = _coerce_carrier_role(carrier_role)
    df = am.model.select(
        aggs.count(distinct(am.Airline.airline_id, am.Route.route_id)).alias("n")
    ).where(
        *am.known_on(am.RouteState, knowledge_date),
        _q06_carrier_link(am.RouteState, am.Airline, role),
        am.RouteState.route == am.Route,
    ).to_df()
    records = _records(df)
    return 0 if not records else int(_as_int(records[0]["n"]) or 0)


# ============================================================================== Q07


def _q07_counted(role: str, knowledge_date: dt.date, operating_date: dt.date) -> list[dict[str, Any]]:
    """Weekly measures over the states that count towards capacity for this role.

    Both clocks are in the same ``where()`` with their two different conventions, and the
    weekday flag for the operating date joins as a named relationship rather than a
    seven-branch match. For the operating role the D-0007 physical base representative gate is
    added: only a state that is not a codeshare and whose marketing and operating carriers
    resolve to the same airline may contribute physical capacity. For the marketing role every
    eligible state with a resolved marketing airline counts.

    Weekly measures are per-flight seats multiplied by ``weekly_frequency``, summed over the
    active states in the group - so a route with two concurrently open states sums both.
    ``active_schedule_count`` counts distinct schedules, not lineage contributions.
    Premium economy is a subset of economy, so the exclusive bucket is the bound DV-26
    ``economy_excluding_premium`` and the four cabin buckets sum to the per-flight total.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    state = am.RouteState
    gate: tuple[Any, ...] = ()
    if role == CARRIER_ROLE_OPERATING:
        gate = (_physical_representative()(state),)

    df = am.model.select(
        distinct(
            am.Airline.airline_id.alias("airline_id"),
            am.Route.route_id.alias("route_id"),
            aggs.count(am.Schedule).per(am.Airline, am.Route).alias("active_schedule_count"),
            aggs.sum(state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_frequency"),
            aggs.sum(state.total_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_total_seats"),
            aggs.sum(state.first_class_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_first_seats"),
            aggs.sum(state.business_class_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_business_seats"),
            aggs.sum(state.premium_economy_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_premium_economy_seats"),
            aggs.sum(state.economy_excluding_premium * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_economy_excluding_premium_seats"),
            (
                aggs.count(state)
                .per(am.Airline, am.Route)
                .where(state.cabin_quality_status != CABIN_RECONCILED)
                | 0
            ).alias("unreconciled_states"),
        )
    ).where(
        *am.known_on(state, knowledge_date),
        *am.operates_on(state, operating_date, _weekday_relationship()),
        *gate,
        _q06_carrier_link(state, am.Airline, role),
        state.route == am.Route,
        state.schedule == am.Schedule,
    ).to_df()

    rows: list[dict[str, Any]] = []
    for row in _records(df):
        unreconciled = _as_int(row["unreconciled_states"]) or 0
        rows.append(
            {
                "result_status": RESULT_COUNTED,
                "carrier_role": role,
                "airline_id": _as_str(row["airline_id"]),
                "route_id": _as_str(row["route_id"]),
                "knowledge_date": knowledge_date,
                "operating_date": operating_date,
                "active_schedule_count": _as_int(row["active_schedule_count"]),
                "weekly_frequency": _as_int(row["weekly_frequency"]),
                "weekly_total_seats": _as_float(row["weekly_total_seats"]),
                "weekly_first_seats": _as_float(row["weekly_first_seats"]),
                "weekly_business_seats": _as_float(row["weekly_business_seats"]),
                "weekly_premium_economy_seats": _as_float(row["weekly_premium_economy_seats"]),
                "weekly_economy_excluding_premium_seats": _as_float(
                    row["weekly_economy_excluding_premium_seats"]
                ),
                "cabin_quality": CABIN_RECONCILED if unreconciled == 0 else CABIN_UNRECONCILED,
                "unresolved_service_key": None,
            }
        )
    return rows


def _q07_unresolved(
    role: str, knowledge_date: dt.date, operating_date: dt.date
) -> list[dict[str, Any]]:
    """Markets that are eligible on both clocks but have no state that counts for this role.

    ``Q07-R004`` freezes exactly this row: ``SYN-OP-X`` on ``SFO->SEA`` at
    ``UNRESOLVED_PHYSICAL_SERVICE`` with every measure null, ``cabin_quality = NOT_COUNTED``
    and ``unresolved_service_key = SYN-SK-CSH_ONLY_900``. Codeshare-only service must be
    emitted as visibly unresolved, never excluded and never guessed into a number: its absence
    would be a two-row answer where three rows are expected, and its inclusion as a number
    would double count somebody else's metal.

    For the marketing role the counting gate is vacuously true, so this branch is
    structurally empty rather than special-cased away. It still runs, because "the marketing
    role can never be unresolved" is a claim worth having a query behind.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    any_state = am.RouteState.ref("any_state")
    counting = am.RouteState.ref("counting")
    inner: list[Any] = [
        *am.known_on(counting, knowledge_date),
        *am.operates_on(counting, operating_date, _weekday_relationship()),
        _q06_carrier_link(counting, am.Airline, role),
        counting.route == am.Route,
    ]
    if role == CARRIER_ROLE_OPERATING:
        inner.append(_physical_representative()(counting))

    df = am.model.select(
        distinct(
            am.Airline.airline_id.alias("airline_id"),
            am.Route.route_id.alias("route_id"),
            aggs.min(any_state.schedule_key)
            .per(am.Airline, am.Route)
            .alias("unresolved_service_key"),
        )
    ).where(
        *am.known_on(any_state, knowledge_date),
        *am.operates_on(any_state, operating_date, _weekday_relationship()),
        _q06_carrier_link(any_state, am.Airline, role),
        any_state.route == am.Route,
        am.model.not_(am.model.where(*inner)),
    ).to_df()

    return [
        {
            "result_status": RESULT_UNRESOLVED,
            "carrier_role": role,
            "airline_id": _as_str(row["airline_id"]),
            "route_id": _as_str(row["route_id"]),
            "knowledge_date": knowledge_date,
            "operating_date": operating_date,
            "active_schedule_count": None,
            "weekly_frequency": None,
            "weekly_total_seats": None,
            "weekly_first_seats": None,
            "weekly_business_seats": None,
            "weekly_premium_economy_seats": None,
            "weekly_economy_excluding_premium_seats": None,
            "cabin_quality": CABIN_NOT_COUNTED,
            "unresolved_service_key": _as_str(row["unresolved_service_key"]),
        }
        for row in _records(df)
    ]


def route_capacity_two_clocks(
    knowledge_date: dt.date | str | None,
    operating_date: dt.date | str | None,
    carrier_role: str | None,
    *,
    labels: LabelSource | None = None,
) -> pd.DataFrame:
    """Q07 - weekly route frequency and cabin capacity under both clocks.

    Knowledge validity is half-open and the operating window is inclusive at both ends. Both
    matter and dropping either fails quietly: filtering on knowledge alone returns states that
    are known but not operating on the operating date, and filtering on operating alone
    returns states as understood today rather than as understood on the knowledge date. Both
    give a plausible, well-formed, wrong answer, which is what the nine-row ``TT-BOTH-CLOCKS``
    truth table exists to catch - and note that ``knowledge_position = AT_END`` is ineligible
    in all three of its rows because the knowledge bound is exclusive at the top.

    One route may carry many concurrently open states, because schedule versioning partitions
    by schedule identity and never by route. ``SYN-OP-A`` on ``SFO->LAX`` has
    ``active_schedule_count = 2``; any "latest state per route" or unique-state assumption
    collapses that row, and the parity matrix prohibits a one-open-per-route constraint.

    An empty answer is an answer: ``Q07-KNOWLEDGE-END-EMPTY`` is zero rows with
    ``invocation_status = OK``, which is a different outcome from the three parameter errors.
    """
    knowledge = _coerce_date(knowledge_date, "MISSING_KNOWLEDGE_DATE", "knowledge_date")
    operating = _coerce_date(operating_date, "MISSING_OPERATING_DATE", "operating_date")
    role = _coerce_carrier_role(carrier_role)
    label_source = labels or EMPTY_LABELS

    rows = _q07_counted(role, knowledge, operating) + _q07_unresolved(role, knowledge, operating)
    rows.sort(key=lambda row: _sort_key(row, ("result_status", "airline_id", "route_id")))
    for row in rows:
        row["row_id"] = label_source.row_id(_q07_row_identity(row), "Q07")
    return _frame(rows, Q07_COLUMNS)


def both_clocks_truth_table(
    schedule_key: str = "SYN-SK-CLOCK_BOUNDARY_001",
) -> pd.DataFrame:
    """``TT-BOTH-CLOCKS`` evaluated by the same two predicates Q07 uses.

    Nine ``(knowledge_date, operating_date)`` combinations against one fixture state whose
    knowledge interval is ``[2026-08-24, 2026-08-31)`` and whose operating window is
    ``[2026-09-01, 2026-09-07]`` with all seven weekday flags true. Exactly two combinations
    are eligible. This is the test that catches the two errors the frozen table was written
    for: dropping a clock, and mixing the two interval conventions. Applying half-open
    semantics to the operating upper bound would make ``TT23-R06`` ineligible; applying
    inclusive semantics to the knowledge upper bound would make ``TT23-R07`` through
    ``TT23-R09`` eligible.
    """
    am = model_package()
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    positions = [
        ("TT23-R01", "BEFORE", dt.date(2026, 8, 23), "BEFORE", dt.date(2026, 8, 31)),
        ("TT23-R02", "BEFORE", dt.date(2026, 8, 23), "INSIDE", dt.date(2026, 9, 1)),
        ("TT23-R03", "BEFORE", dt.date(2026, 8, 23), "AT_END", dt.date(2026, 9, 7)),
        ("TT23-R04", "INSIDE", dt.date(2026, 8, 24), "BEFORE", dt.date(2026, 8, 31)),
        ("TT23-R05", "INSIDE", dt.date(2026, 8, 24), "INSIDE", dt.date(2026, 9, 1)),
        ("TT23-R06", "INSIDE", dt.date(2026, 8, 24), "AT_END", dt.date(2026, 9, 7)),
        ("TT23-R07", "AT_END", dt.date(2026, 8, 31), "BEFORE", dt.date(2026, 8, 31)),
        ("TT23-R08", "AT_END", dt.date(2026, 8, 31), "INSIDE", dt.date(2026, 9, 1)),
        ("TT23-R09", "AT_END", dt.date(2026, 8, 31), "AT_END", dt.date(2026, 9, 7)),
    ]
    rows: list[dict[str, Any]] = []
    for row_id, k_pos, k_date, o_pos, o_date in positions:
        df = am.model.select(aggs.count(am.RouteState).alias("n")).where(
            am.RouteState.schedule_key == schedule_key,
            *am.known_on(am.RouteState, k_date),
            *am.operates_on(am.RouteState, o_date, _weekday_relationship()),
        ).to_df()
        records = _records(df)
        matched = 0 if not records else (_as_int(records[0]["n"]) or 0)
        rows.append(
            {
                "row_id": row_id,
                "knowledge_position": k_pos,
                "knowledge_date": k_date,
                "operating_position": o_pos,
                "operating_date": o_date,
                "eligible": matched > 0,
            }
        )
    return _frame(
        rows,
        (
            "row_id",
            "knowledge_position",
            "knowledge_date",
            "operating_position",
            "operating_date",
            "eligible",
        ),
    )


# ============================================================================== Q05


def _q05_window(start: dt.date, end: dt.date) -> tuple[Any, ...]:
    """The adjacent-eligible comparisons that lie inside ``[start, end]``.

    ``ScheduleComparison`` is the contracted DV-34 adjacency over the whole eligible snapshot
    sequence, so each comparison already pairs a date with the *previous eligible* date rather
    than the previous calendar date. Restricting a contiguous window to
    ``previous >= start AND comparison <= end`` therefore yields exactly the window-local
    adjacent pairs - for the canonical window, the four pairs
    ``q05_window_assertions.adjacent_pairs`` names and no others.
    """
    am = model_package()
    return (
        am.ScheduleComparison.previous_knowledge_date >= start,
        am.ScheduleComparison.comparison_date <= end,
    )


def _q05_exact(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """The exact layer: key-preserving modifications and presence additions/removals.

    These stand on their own and are never consumed, replaced or suppressed by the
    conservative amendment evidence below. ``SYN-SK-SHIFT_OLD`` and ``SYN-SK-SHIFT_NEW``
    appear here as an exact removal and an exact addition *and* separately as a candidate
    pair; ``SYN-SK-MKT_ENTRY_714`` and ``SYN-SK-MKT_EXIT_715`` exist for Q06 and still appear
    here, four rows in total, because D-0010/D-0011 forbid a question-private fixture filter.
    ``SYN-SK-REAPPEAR_400`` is an exact removal on 2026-08-10 followed by an exact addition on
    2026-08-17, not a no-op and not a modification.

    ``old_value`` and ``new_value`` are legitimately null on the two ``arrival_station_code_iata``
    transitions (null to ``PHX`` and back), and a repeated unchanged eligible observation
    contributes lineage without minting a change event.
    """
    am = model_package()
    change = am.ScheduleExactChange
    comparison = am.ScheduleComparison
    df = am.model.select(
        comparison.comparison_date.alias("comparison_date"),
        comparison.previous_knowledge_date.alias("previous_knowledge_date"),
        comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
        change.change_kind.alias("event_class"),
        change.schedule_key.alias("schedule_key"),
        change.field_name.alias("field_name"),
        change.old_value.alias("old_value"),
        change.new_value.alias("new_value"),
    ).where(change.comparison == comparison, *_q05_window(start, end)).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": EXACT_EXACTNESS,
            "confidence": EXACT_CONFIDENCE,
            "schedule_key": _as_str(row["schedule_key"]),
            "related_schedule_key": None,
            "field_name": _as_str(row["field_name"]),
            "old_value": _as_str(row["old_value"]),
            "new_value": _as_str(row["new_value"]),
            "group_id": None,
            "member_side": None,
            "member_schedule_key": None,
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_ordinal": None,
        }
        for row in _records(df)
    ]


def _q05_candidates(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``CANDIDATE_UNIQUE``: one removal and one addition compatible on the typed signature.

    The signature is ``(marketing carrier, flight number, origin, destination)`` with
    **overlapping** inclusive operating ranges and every component plus both bounds non-null.
    The pair is reported at ``CANDIDATE`` exactness and ``MEDIUM`` confidence and is never
    promoted to a modification: ``NEO4J_PARITY_MATRIX.md`` lists "a candidate key shift is an
    exact schedule amendment" as a prohibited statement. Both ``schedule_key`` (the removed
    side) and ``related_schedule_key`` (the added side) are populated so the evidence is
    legible, and both exact presence rows survive alongside it.

    The ``NN`` ordinal is ranked in PyRel over ``candidate_signature`` within the comparison,
    per the manifest-adopted ``SYN-CAND-<YYYYMMDD>-NN`` template.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415
    from relationalai.semantics.std.aggregates import asc  # noqa: PLC0415

    candidate = am.ScheduleAmendmentCandidate
    comparison = am.ScheduleComparison
    df = am.model.select(
        distinct(
            comparison.comparison_date.alias("comparison_date"),
            comparison.previous_knowledge_date.alias("previous_knowledge_date"),
            comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
            candidate.amendment_candidate_class.alias("event_class"),
            candidate.exactness.alias("exactness"),
            candidate.amendment_confidence.alias("confidence"),
            candidate.removed_schedule_key.alias("schedule_key"),
            candidate.added_schedule_key.alias("related_schedule_key"),
            aggs.rank(asc(candidate.candidate_signature)).per(comparison).alias("ordinal"),
        )
    ).where(
        comparison.comparison_id == candidate.comparison_id, *_q05_window(start, end)
    ).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": _as_str(row["exactness"]),
            "confidence": _as_str(row["confidence"]),
            "schedule_key": _as_str(row["schedule_key"]),
            "related_schedule_key": _as_str(row["related_schedule_key"]),
            "field_name": None,
            "old_value": None,
            "new_value": None,
            "group_id": None,
            "member_side": None,
            "member_schedule_key": None,
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_ordinal": _as_int(row["ordinal"]),
        }
        for row in _records(df)
    ]


def _q05_groups(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``AMBIGUOUS_CANDIDATE_GROUP``: one removal compatible with more than one addition.

    ``schedule_key`` and ``related_schedule_key`` are both null and no pair is chosen. Picking
    a winner by any tie-break is wrong, which is the whole point of the class existing.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415
    from relationalai.semantics.std.aggregates import asc  # noqa: PLC0415

    group = am.ScheduleAmendmentGroup
    comparison = am.ScheduleComparison
    df = am.model.select(
        distinct(
            comparison.comparison_date.alias("comparison_date"),
            comparison.previous_knowledge_date.alias("previous_knowledge_date"),
            comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
            group.amendment_candidate_class.alias("event_class"),
            group.exactness.alias("exactness"),
            group.amendment_confidence.alias("confidence"),
            group.group_id.alias("group_hash"),
            aggs.rank(asc(group.candidate_signature)).per(comparison).alias("ordinal"),
        )
    ).where(comparison.comparison_id == group.comparison_id, *_q05_window(start, end)).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": _as_str(row["exactness"]),
            "confidence": _as_str(row["confidence"]),
            "schedule_key": None,
            "related_schedule_key": None,
            "field_name": None,
            "old_value": None,
            "new_value": None,
            "group_id": None,
            "member_side": None,
            "member_schedule_key": None,
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_group_hash": _as_str(row["group_hash"]),
            "_ordinal": _as_int(row["ordinal"]),
        }
        for row in _records(df)
    ]


def _q05_ambiguous_members(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``AMBIGUOUS_GROUP_MEMBER``: every schedule key the ambiguous group touches.

    ``schedule_key`` and ``related_schedule_key`` stay null; the key is carried in
    ``member_schedule_key`` with its ``member_side``, so a reader can see the whole
    compatibility component without any pair being asserted.

    The ``-Mk`` ordinal is the manifest-adopted rule ``REMOVED`` before ``ADDED``, then
    schedule key ascending (the natural alternative, ``(schedule_key, side)``, produces a
    different and failing answer). It is composed from two single-ordering aggregates rather
    than one two-key rank, because ``rank(desc(side), asc(key))`` raises
    ``Mixed orderings in rank/cumsum are not supported yet`` in 1.20.1 - measured, not
    guessed. So the rank runs *within* a side, the removed side's cardinality is counted per
    group, and the added side is offset by it. Both halves are computed in PyRel; only the
    integer addition and the string template are Python, which is where the D-0018
    presentation layer belongs.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415
    from relationalai.semantics.std.aggregates import asc  # noqa: PLC0415

    member = am.ScheduleAmendmentGroupMember
    group = am.ScheduleAmendmentGroup
    comparison = am.ScheduleComparison
    df = am.model.select(
        distinct(
            comparison.comparison_date.alias("comparison_date"),
            comparison.previous_knowledge_date.alias("previous_knowledge_date"),
            comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
            member.member_class.alias("event_class"),
            member.exactness.alias("exactness"),
            member.amendment_confidence.alias("confidence"),
            group.group_id.alias("group_hash"),
            member.side.alias("member_side"),
            member.member_schedule_key.alias("member_schedule_key"),
            aggs.rank(asc(member.member_schedule_key))
            .per(group, member.side)
            .alias("rank_within_side"),
            (
                aggs.count(member).per(group).where(member.side == SIDE_REMOVED) | 0
            ).alias("removed_count"),
        )
    ).where(
        member.member_class == AMBIGUOUS_MEMBER_CLASS,
        member.group == group,
        comparison.comparison_id == member.comparison_id,
        *_q05_window(start, end),
    ).to_df()

    rows: list[dict[str, Any]] = []
    for row in _records(df):
        side = _as_str(row["member_side"])
        within = _as_int(row["rank_within_side"]) or 0
        removed = _as_int(row["removed_count"]) or 0
        ordinal = within if side == SIDE_REMOVED else removed + within
        rows.append(
            {
                "comparison_date": _as_date(row["comparison_date"]),
                "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
                "event_class": _as_str(row["event_class"]),
                "exactness": _as_str(row["exactness"]),
                "confidence": _as_str(row["confidence"]),
                "schedule_key": None,
                "related_schedule_key": None,
                "field_name": None,
                "old_value": None,
                "new_value": None,
                "group_id": None,
                "member_side": side,
                "member_schedule_key": _as_str(row["member_schedule_key"]),
                "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
                "_group_hash": _as_str(row["group_hash"]),
                "_ordinal": ordinal,
            }
        )
    return rows


def _q05_unpaired(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``UNPAIRED_ADDITION`` / ``UNPAIRED_REMOVAL``: exact presence with no eligible partner.

    Every exact addition or removal that no candidate and no ambiguous group consumes gets
    exactly one unpaired evidence row with matching comparison date, side and schedule key,
    and no exact presence row is ever both partnered and unpaired. Confidence is ``NONE`` and
    exactness is ``UNPAIRED``: this is the honest answer when the key hash has destroyed the
    link and nothing in the data restores it.
    """
    am = model_package()
    member = am.ScheduleAmendmentGroupMember
    comparison = am.ScheduleComparison
    df = am.model.select(
        comparison.comparison_date.alias("comparison_date"),
        comparison.previous_knowledge_date.alias("previous_knowledge_date"),
        comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
        member.member_class.alias("event_class"),
        member.exactness.alias("exactness"),
        member.amendment_confidence.alias("confidence"),
        member.side.alias("member_side"),
        member.member_schedule_key.alias("member_schedule_key"),
    ).where(
        member.member_class != AMBIGUOUS_MEMBER_CLASS,
        comparison.comparison_id == member.comparison_id,
        *_q05_window(start, end),
    ).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": _as_str(row["exactness"]),
            "confidence": _as_str(row["confidence"]),
            "schedule_key": _as_str(row["member_schedule_key"]),
            "related_schedule_key": None,
            "field_name": None,
            "old_value": None,
            "new_value": None,
            "group_id": None,
            "member_side": _as_str(row["member_side"]),
            "member_schedule_key": _as_str(row["member_schedule_key"]),
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_ordinal": None,
        }
        for row in _records(df)
    ]


def _q05_apply_labels(
    rows: list[dict[str, Any]], label_source: LabelSource
) -> list[dict[str, Any]]:
    """Attach ``event_id`` and ``group_id``, then ``row_id``. Presentation layer only.

    Three of the eight classes get a computed id from a manifest-adopted string template; the
    other five get a supplied mnemonic or a fail-loud ``UNLABELLED|...`` token. Nothing here
    touches a derived cell.
    """
    group_label_by_hash: dict[str, str] = {}
    for row in rows:
        if row["event_class"] == AMBIGUOUS_GROUP_CLASS:
            label = f"SYN-AMB-{row['comparison_date']:%Y%m%d}-{row['_ordinal']:02d}"
            row["group_id"] = label
            row["event_id"] = label
            group_hash = row.get("_group_hash")
            if group_hash:
                group_label_by_hash[group_hash] = label

    for row in rows:
        event_class = row["event_class"]
        if event_class == AMBIGUOUS_GROUP_CLASS:
            continue
        if event_class == CANDIDATE_UNIQUE_CLASS:
            row["event_id"] = f"SYN-CAND-{row['comparison_date']:%Y%m%d}-{row['_ordinal']:02d}"
        elif event_class == AMBIGUOUS_MEMBER_CLASS:
            group_hash = row.get("_group_hash")
            group_label = group_label_by_hash.get(
                group_hash or "", _unlabelled("GROUP", (group_hash,))
            )
            row["group_id"] = group_label
            row["event_id"] = f"{group_label}-M{row['_ordinal']}"
        else:
            row["event_id"] = label_source.event_id(_q05_label_identity(row))

    for row in rows:
        row.pop("_ordinal", None)
        row.pop("_group_hash", None)
        row["row_id"] = label_source.row_id(_q05_row_identity(row), "Q05")
    return rows


def schedule_four_week_changes(
    start_knowledge_date: dt.date | str | None,
    end_knowledge_date: dt.date | str | None,
    cadence_days: int | None,
    *,
    labels: LabelSource | None = None,
) -> pd.DataFrame:
    """Q05 - classify schedule changes across consecutive eligible publish snapshots.

    Eight visibly separate event classes, in two strictly separated layers. The exact layer
    (``EXACT_KEY_PRESERVING_MODIFICATION``, ``EXACT_ADDITION``, ``EXACT_REMOVAL``) is a
    presence-and-content fact set that stands on its own. The evidence layer
    (``CANDIDATE_UNIQUE``, ``AMBIGUOUS_CANDIDATE_GROUP``, ``AMBIGUOUS_GROUP_MEMBER``,
    ``UNPAIRED_ADDITION``, ``UNPAIRED_REMOVAL``) says what the exact layer cannot: which
    removal/addition pairs *might* be one carrier amending one service.

    **The trap this question exists for.** ``schedule_key`` hashes the effective and
    discontinue dates, so a carrier shifting either date mints a new key and one amendment
    looks like a removal plus an unrelated addition. That is not a bug to be fixed by
    rewriting the key: it is what the source does. Recognising the pair needs a match on
    ``(carrier, flight_number, origin, destination)`` with overlapping date ranges, and such a
    pair is reported as a **candidate** carrying confidence and evidence - never silently
    asserted as an exact modification, and never allowed to consume the two exact rows.

    An incomplete or missing snapshot never manufactures a removal. Both endpoints must be
    eligible; ``Q05-INELIGIBLE-ENDPOINT`` (2026-10-12 to 2026-10-19) is zero rows with
    ``ENDPOINT_MISSING`` because 2026-10-12 is absent and 2026-10-19 is present but
    incomplete, and the previous eligible complete snapshot, 2026-10-05, is not substituted
    for either.
    """
    start = _coerce_date(
        start_knowledge_date, "MISSING_START_KNOWLEDGE_DATE", "start_knowledge_date"
    )
    end = _coerce_date(end_knowledge_date, "MISSING_END_KNOWLEDGE_DATE", "end_knowledge_date")
    _coerce_cadence_days(cadence_days)
    label_source = labels or EMPTY_LABELS

    _require_eligible_endpoints(
        (("start_knowledge_date", start), ("end_knowledge_date", end))
    )

    rows = (
        _q05_exact(start, end)
        + _q05_candidates(start, end)
        + _q05_groups(start, end)
        + _q05_ambiguous_members(start, end)
        + _q05_unpaired(start, end)
    )
    rows = _q05_apply_labels(rows, label_source)
    rows.sort(
        key=lambda row: (
            (0, row["comparison_date"]),
            (0, EVENT_CLASS_RANK.get(row["event_class"], 999)),
            *_sort_key(row, ("event_id", "member_side", "member_schedule_key")),
        )
    )
    return _frame(rows, Q05_COLUMNS)


# =============================================================== conformance harness


QUESTION_FUNCTIONS: Mapping[str, Callable[..., pd.DataFrame]] = {
    "Q05": schedule_four_week_changes,
    "Q06": market_latest_vs_seven_days,
    "Q07": route_capacity_two_clocks,
}

_PARAMETER_ORDER: Mapping[str, tuple[str, ...]] = {
    "Q05": ("start_knowledge_date", "end_knowledge_date", "cadence_days"),
    "Q06": ("latest_knowledge_date", "comparison_knowledge_date", "carrier_role"),
    "Q07": ("knowledge_date", "operating_date", "carrier_role"),
}

_QUESTION_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "Q05": Q05_COLUMNS,
    "Q06": Q06_COLUMNS,
    "Q07": Q07_COLUMNS,
}


def invoke_result_set(
    question_id: str,
    result_set: Mapping[str, Any],
    labels: LabelSource | None = None,
) -> tuple[str, str | None, pd.DataFrame]:
    """Run one frozen result set. Returns ``(invocation_status, error_code, frame)``.

    A refusal yields a correctly shaped **empty** frame plus its status, so the three kinds of
    zero-row answer stay distinguishable: ``PARAMETER_ERROR`` before execution, an endpoint
    refusal, and a legitimately empty ``OK`` result.
    """
    function = QUESTION_FUNCTIONS[question_id]
    parameters = result_set["parameters"]
    args = [parameters.get(name) for name in _PARAMETER_ORDER[question_id]]
    try:
        return "OK", None, function(*args, labels=labels)
    except Uc2InvocationError as exc:
        return (
            exc.invocation_status,
            exc.error_code,
            _frame((), _QUESTION_COLUMNS[question_id]),
        )


def compare_rows(
    got: pd.DataFrame, expected: Sequence[Mapping[str, Any]], columns: Sequence[str]
) -> list[str]:
    """Complete ordered-sequence comparison. Missing and extra columns fail."""
    diffs: list[str] = []
    if list(got.columns) != list(columns):
        diffs.append(f"columns {list(got.columns)} != {list(columns)}")
        return diffs
    if len(got) != len(expected):
        diffs.append(f"cardinality {len(got)} != {len(expected)}")
    for index in range(max(len(got), len(expected))):
        if index >= len(got):
            diffs.append(f"row {index}: missing {expected[index].get('row_id')}")
            continue
        if index >= len(expected):
            diffs.append(f"row {index}: unexpected {got.iloc[index].get('row_id')}")
            continue
        actual = got.iloc[index]
        wanted = expected[index]
        for column in columns:
            left = actual[column]
            right = wanted.get(column)
            if not _cells_equal(left, right):
                diffs.append(
                    f"row {index} ({wanted.get('row_id')}) {column}: {left!r} != {right!r}"
                )
    return diffs


def _cells_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) is bool(right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
    return left == right


# --- the D-0018 verdict split ------------------------------------------------------
#
# Q05's declared order_by sorts on event_id, and Q05-CANONICAL's 30 declared-class event_ids
# are hand-authored mnemonics that no implementation can derive; the declared sequence is
# separately unrecoverable (on 2026-08-31 the EXACT_ADDITION block orders
# [MKT_ENTRY_714, UNPAIR_NEW] while the UNPAIRED_ADDITION block orders the identical pair
# inverted). D-0018 therefore requires two verdicts, reported apart and labelled:
#
#   SEMANTIC     - order-free, over the columns the query computes with no manifest input.
#                  This is the verdict that is genuinely earned.
#   PRESENTATION - the declared sequence and the supplied identifier columns, asserted only
#                  after the label join. Passing it is evidence the module *applies* the
#                  supplied labels, not that it recovered them.
#
# Q06 and Q07 have derivable order keys, so their semantic verdict is over every column
# except row_id and their presentation verdict is the full ordered comparison.

_SUPPLIED_COLUMNS: Mapping[str, frozenset[str]] = {
    "Q05": frozenset({"row_id", "event_id"}),
    "Q06": frozenset({"row_id"}),
    "Q07": frozenset({"row_id"}),
}


def semantic_columns(question_id: str) -> tuple[str, ...]:
    """The output columns the query derives with no manifest input."""
    supplied = _SUPPLIED_COLUMNS[question_id]
    return tuple(c for c in _QUESTION_COLUMNS[question_id] if c not in supplied)


def compare_semantic(
    got: pd.DataFrame, expected: Sequence[Mapping[str, Any]], question_id: str
) -> list[str]:
    """Order-free multiset comparison over the derived columns only (D-0018).

    A multiset and not a set: two rows that agree on every derived column are two events, and
    collapsing them would hide a duplicate. Q05's semantic identity is unique within a result
    set, so in practice the multiplicities are all one, and asserting them keeps it that way.
    """
    columns = semantic_columns(question_id)
    missing = [c for c in columns if c not in got.columns]
    if missing:
        return [f"missing columns {missing}"]

    def norm(value: Any) -> Any:
        """One cell as a hashable canonical form, matching :func:`_cells_equal`.

        Numerics collapse to ``float`` so a frozen ``200`` and a computed ``200.0`` are the
        same event rather than two; ``bool`` is checked before ``int`` because it is a
        subclass of it and ``True`` must not become ``1.0``.
        """
        value = _cell(value)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return round(float(value), 9)
        return str(value)

    def key(row: Mapping[str, Any]) -> tuple:
        return tuple(norm(row.get(c)) for c in columns)

    got_counts: dict[tuple, int] = {}
    for row in _records(got):
        got_counts[key(row)] = got_counts.get(key(row), 0) + 1
    want_counts: dict[tuple, int] = {}
    for row in expected:
        want_counts[key(row)] = want_counts.get(key(row), 0) + 1

    def render(k: tuple) -> str:
        return "|".join("" if part is None else str(part) for part in k)

    diffs: list[str] = []
    for k in sorted(set(want_counts) - set(got_counts), key=render):
        diffs.append(f"missing event {render(k)}")
    for k in sorted(set(got_counts) - set(want_counts), key=render):
        diffs.append(f"unexpected event {render(k)}")
    for k in sorted(set(got_counts) & set(want_counts), key=render):
        if got_counts[k] != want_counts[k]:
            diffs.append(
                f"multiplicity {got_counts[k]} != {want_counts[k]} for {render(k)}"
            )
    return diffs


@dataclass
class Verdict:
    result_set_id: str
    question_id: str
    rows: int
    seconds: float
    semantic: list[str] = field(default_factory=list)
    presentation: list[str] = field(default_factory=list)

    @property
    def semantic_ok(self) -> bool:
        return not self.semantic

    @property
    def presentation_ok(self) -> bool:
        return not self.presentation


def run_result_set(
    question_id: str, result_set: Mapping[str, Any], manifest: Mapping[str, Any]
) -> Verdict:
    """Invoke one frozen result set and return both verdicts plus its wall time.

    Labels are scoped to **this** result set. At manifest 1.2.0 that is a correctness
    requirement rather than tidiness - see :func:`manifest_label_source`.
    """
    import time  # noqa: PLC0415

    labels = manifest_label_source(question_id, manifest, result_set["result_set_id"])
    started = time.monotonic()
    status, error_code, frame = invoke_result_set(question_id, result_set, labels)
    elapsed = time.monotonic() - started

    expected_rows = [_manifest_row(row) for row in (result_set.get("rows") or ())]
    verdict = Verdict(
        result_set_id=result_set["result_set_id"],
        question_id=question_id,
        rows=len(frame),
        seconds=elapsed,
    )

    invocation: list[str] = []
    if status != result_set["invocation_status"]:
        invocation.append(
            f"invocation_status {status!r} != {result_set['invocation_status']!r}"
        )
    expected_code = result_set.get("error_code")
    if expected_code is not None and error_code != expected_code:
        invocation.append(f"error_code {error_code!r} != {expected_code!r}")
    if len(frame) != result_set["expected_cardinality"]:
        invocation.append(
            f"cardinality {len(frame)} != {result_set['expected_cardinality']}"
        )

    # The invocation status gates both verdicts: a refusal that should have been an answer is
    # a semantic failure, not a presentation one.
    verdict.semantic = invocation + compare_semantic(frame, expected_rows, question_id)
    verdict.presentation = compare_rows(
        frame, expected_rows, _QUESTION_COLUMNS[question_id]
    )
    return verdict


_MODEL_LOCKED = "locked by active write transaction"


def warm_model(attempts: int = 20, delay: float = 45.0) -> float:
    """Force the one-off model install and index, retrying while it is write-locked.

    The three query modules (``uc1``, ``uc2``, ``rotation``) share one ``aviation_temporal``
    model on one engine. Importing any of them installs the model's rules, which is a **write**
    transaction, and RAI 1.20.1 refuses to prepare the index for a read while another
    transaction holds that write lock:

        prepareIndex: The model is currently locked by active write transaction(s)

    That is contention, not a defect, and it is the expected state whenever two of the three
    modules start within a few minutes of each other. Retrying is the correct response; failing
    the whole conformance run because a sibling module happened to be installing is not.

    Returns the wall time spent, which is the honest cold-start number: on a freshly reloaded
    ``SOURCE`` and ``MODEL_INPUT`` it is dominated by the CDC re-sync and is measured in
    minutes, not seconds.
    """
    import time  # noqa: PLC0415

    started = time.monotonic()
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            snapshot_calendar(refresh=True)
            return time.monotonic() - started
        except Exception as exc:  # noqa: BLE001 - re-raised below if it is not the lock
            if _MODEL_LOCKED not in str(exc):
                raise
            last = exc
            print(
                f"  model write-locked by a sibling module; retry "
                f"{attempt + 1}/{attempts} in {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(
        f"model still write-locked after {attempts} attempts over "
        f"{attempts * delay / 60:.0f} minutes"
    ) from last


def main(argv: Sequence[str] | None = None) -> int:
    """Run every frozen UC2 result set plus ``TT-BOTH-CLOCKS`` and print both verdicts.

    Covers manifest 1.1.1 and the 1.2.0 result sets D-0023 added, in the QUERY_ROUTING build
    order Q06, Q07, Q05. Timings are wall clock per result set; the first is the cold one and
    carries the CDC re-sync and model indexing for the whole run.
    """
    manifest = _load_manifest()
    questions = {q["question_id"]: q for q in manifest["questions"]}
    truth_tables = {t["truth_table_id"]: t for t in manifest["contract_truth_tables"]}

    cold = warm_model()
    print(f"  model ready after {cold:.1f}s (install, index and CDC re-sync)", flush=True)

    verdicts: list[Verdict] = []
    for question_id in ("Q06", "Q07", "Q05"):
        for result_set in questions[question_id]["result_sets"]:
            verdict = run_result_set(question_id, result_set, manifest)
            verdicts.append(verdict)
            print(
                f"  ran {verdict.result_set_id:<34} {verdict.rows:>4} rows "
                f"{verdict.seconds:7.2f}s "
                f"sem={'PASS' if verdict.semantic_ok else 'FAIL'} "
                f"pres={'PASS' if verdict.presentation_ok else 'FAIL'}",
                flush=True,
            )

    import time  # noqa: PLC0415

    started = time.monotonic()
    got = both_clocks_truth_table()
    tt_seconds = time.monotonic() - started
    table = truth_tables["TT-BOTH-CLOCKS"]
    expected_tt = [_manifest_row(row) for row in table["rows"]]
    tt_diffs = compare_rows(got, expected_tt, tuple(got.columns))

    width = max([len(v.result_set_id) for v in verdicts] + [len("TT-BOTH-CLOCKS")])
    print()
    print("QUERY-UC2 conformance against EXPECTED_ANSWERS.yaml (1.1.1 + 1.2.0)")
    print(f"{'result set'.ljust(width)}  rows  seconds  semantic  presentation  detail")
    print("-" * (width + 46))
    failures = 0
    for verdict in verdicts:
        if not (verdict.semantic_ok and verdict.presentation_ok):
            failures += 1
        detail = "; ".join((verdict.semantic + verdict.presentation)[:3])
        print(
            f"{verdict.result_set_id.ljust(width)}  {verdict.rows:>4}  "
            f"{verdict.seconds:7.2f}  "
            f"{'PASS' if verdict.semantic_ok else 'FAIL':<8}  "
            f"{'PASS' if verdict.presentation_ok else 'FAIL':<12}  {detail}"
        )
    print(
        f"{'TT-BOTH-CLOCKS'.ljust(width)}  {len(got):>4}  {tt_seconds:7.2f}  "
        f"{'PASS' if not tt_diffs else 'FAIL':<8}  {'-':<12}  "
        + "; ".join(tt_diffs[:3])
    )
    print("-" * (width + 46))
    total = len(verdicts) + 1
    failures += 1 if tt_diffs else 0
    warm = sorted(v.seconds for v in verdicts)
    print(f"{total - failures}/{total} checks pass")
    print(
        f"cold model install / index / CDC re-sync: {cold:.1f}s; "
        f"warm per result set median {warm[len(warm) // 2]:.2f}s, "
        f"min {warm[0]:.2f}s, max {warm[-1]:.2f}s; "
        f"all {len(verdicts)} result sets {sum(v.seconds for v in verdicts):.1f}s"
    )
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

_SRC_ROTATION = r'''"""rotation.py - Q08 ``actual_rotation_enriched``, the demo's closing beat.

One aircraft, one **source-local** departure date (AF-06), and the answer is the ordered chain of
legs the aircraft actually operated that day: where each leg started and ended, when it actually
left and arrived, whether the link to the next leg was accepted or refused and why, and what
aircraft type and engine the *independent* aircraft-history streams say the airframe carried on
that date. It is the only question that crosses both use cases: ``AIRCRAFT_FLIGHT.aircraft_id`` is
the same identity as UC1's ``Aircraft``, so "what type was that aircraft on that date, and what
engines was it fitted with" is one query here rather than a join across two graphs.

**Why this is a traversal and not a filter plus a sort.** Each leg ends where the next begins, so
``leg_order`` is a property of the link structure, not of the clock. This module derives it as
``1 + the number of accepted-chain predecessors``, read out of ``rotation_leg_distance``, the
transitive closure over ``AircraftFlight.accepted_next_flight`` authored in
``aviation_model.computed_rotation``. Sorting the day's legs by
``actual_gate_departure_time_utc`` and numbering them reproduces the canonical answer on this
fixture and is an explicit fail: it would also silently "repair" the diversion case below.

**The traps this module is written against**, each one a real row in the shipped fixtures:

* *A stopover is one passenger flight but two aircraft flights.* Legs are never de-duplicated
  against the plan, so a rotation legitimately holds more legs than the published schedule
  suggests. Nothing here reads the plan side at all.
* *A DIVERTED flight ends somewhere other than its planned destination.* Continuity is on the
  **actual** arrival airport (AF-09 = DV-45) and the **actual** gate times (AF-13 / AF-14), never
  on a scheduled arrival and never on AF-10. There is no scheduled-arrival column anywhere in
  this file. Flight 7200 is the live proof: it planned SFO to LAX, actually landed at LAS, and
  aircraft 1100's leg 5103 departs from LAX at exactly 7200's arrival minute. A chain built on the
  planned endpoint would link them; the actual chain leaves both as singleton segments.
* *Enriching on the UTC date.* All three canonical legs carry AF-06 2026-08-31 while AF-07 is
  2026-09-01 and the UTC gate departures fall on 2026-09-01. Day selection and enrichment both use
  AF-06. ``TT-US-CLOCK-AUTHORITY`` row ``TTUS-R05`` freezes that assertion, and
  ``flight_departure_date_utc`` is never read by this module.
* *Suppressing the type discrepancy.* AF-17 is discrepancy evidence and never aircraft-history
  authority. ``Q08-R002`` reports ``as_of_aircraft_type_id = SYN-TYPE-B`` from history next to
  ``actual_source_aircraft_type = "Synthetic narrowbody A"`` with ``type_discrepancy = true``. The
  disagreement is reported, never reconciled.
* *Cycle duplication.* Flights 8102 and 8103 form a cycle. Exactly one ``CYCLE`` row is emitted
  per component, anchored at its minimum ``flight_id``, while every member stays queryable as
  evidence (see :func:`rotation_anomaly_evidence`). Emitting one row per member would give 12
  anomaly rows instead of 11.
* *Losing excluded legs.* ``CANCELLED``, ``MISSING_TIME`` and
  ``UNKNOWN_OR_INVALID_CANCELLATION_FLAG`` are ``EXCLUDED`` from the operated chain and still
  visible as anomaly rows.
* *A twelfth anomaly class arriving unannounced.* ``MODEL_INPUT`` also emits
  ``TARGET_NOT_OPERATED`` (D-0020 A5) - a link whose target is itself cancelled, invalid-flagged
  or missing an arrival time. It is outside the eleven-class DV-25 vocabulary the manifest
  declares and the independent SQL oracle has no branch for it, so a conformance harness would
  diverge the first time a selected rotation hit one. It is emitted, because ``is_accepted_link``
  is false and suppressing the row would delete a leg from the chain with no stated reason - and
  every invocation reports it separately through
  :attr:`RotationResult.beyond_manifest_anomaly_classes`. Four legs in the enriched universe carry
  it (5310, 5470, 6190, 6345); none is in a frozen Q08 result set.

**Nothing semantic is recomputed here.** The per-edge acceptance conjunction, the DV-25 anomaly
classification and its precedence, the cycle component and its representative, the transitive
closure, and the as-of type and engine resolution on AF-06 all live in the ontology
(``aviation_model.computed_rotation``, which resolves the same daily-assignment intervals Q01
resolves, scoped per dimension). This module contributes the three things
``QUERY_ROUTING.md`` marks as catalog-layer rather than semantic: parameter validation and typed
error codes, the manifest's ``SYN-ROT`` / ``SYN-ANOM`` presentation labels (kept out of the PyRel
model per the D-0018 / D-0021 bindings), and the frozen output ordering.

**Path reasoner.** Not used, and the verdict is now *measured against the live engine* rather than
cited. ``build/design/QUERY_ROUTING.md`` sets five pass conditions plus a value bar for the
optional ``relationalai.semantics.std.path`` implementation. It was built and run::

    p = path(AircraftFlight.accepted_next_flight).repeat(min=1, max=32).all_paths()
    model.select((idx + 1).alias("leg_order"), node.flight_id, src.flight_id).where(
        p.nodes(0, src), p.nodes(p.length, dst), p.nodes(idx, node),
        src.aircraft == Aircraft, Aircraft.id == aircraft_id,
        src.flight_departure_date == day, RotationSegmentHead(src),
        hval.flight == src, model.not_(hval.rotation_anomaly_class),
        model.not_(dst.accepted_next_flight(out)),
    )

Conditions 1 to 4 pass: it executes on 1.20.1, returns exactly ``[8001, 8002, 8003]`` for
``Q08-CANONICAL`` (and the 5-leg and 4-leg enriched chains), returns nothing for the anomaly-only
aircraft, terminates under the ``repeat`` bound, and the per-leg enrichment joins on without
tripping the interior-binder hook. Condition 5 passes too: 3.4 to 3.6s warm against the baseline's
4.4 to 4.6s.

It still does not ship, on the value bar and on one correctness finding:

* ``repeat(min=1, ...)`` requires at least one edge, so a **single-leg rotation segment is not a
  path**. Aircraft 1225 on 2027-06-24 has two segments - ``5309 -> 5310`` and the singleton
  ``5312`` - and the path implementation returns two rows where the closure baseline returns
  three. ``repeat(min=0, ...)`` is the obvious repair and it raises
  ``[PathUngroundedPatternError] Pattern potentially admits an infinite number of single-node
  paths``. Recovering the singleton therefore needs a union with a separate no-edge branch, which
  is more code and a second correctness surface, not less.
* The maximal-chain filter (``not_`` inbound, ``not_`` outbound) is still needed, so the path adds
  a ``repeat`` bound constant without removing the head and terminal predicates.
* It is a query-level construct and cannot be materialised as an ontology property, so every
  consumer would restate the pattern - the opposite of the one-reusable-semantic-model claim.
* ``shortest_paths()``, ``undirected()`` and ``reverse()`` all raise ``NotImplementedError`` at
  1.20.1, and every ``path()`` call emits a spurious ``RuleLoopWarning``. (Three transient
  ``SnowflakeTableObjectsException``\\ s during the experiment turned out **not** to be the path
  library: they were the shared-model write lock a sibling agent was holding. See
  :func:`retry_on_model_lock`.)

Ordinary typed self-reference is the supported baseline and is what ships.

Run the frozen result sets::

    PYTHONPATH=rai_code .venv/bin/python rai_code/queries/rotation.py
"""

from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from relationalai.semantics.std import aggregates as aggs

QUESTION_ID = "Q08"
CATALOG_ID = "actual_rotation_enriched"

#: The frozen ``output_schema`` column order. ``to_df()`` follows ``select()`` argument order and
#: silently appends ``_2`` on a name collision, so every column is aliased at every call site and
#: the assembled frame is reindexed onto this tuple before it is returned.
OUTPUT_COLUMNS: tuple[str, ...] = (
    "row_id",
    "row_kind",
    "segment_id",
    "leg_order",
    "flight_id",
    "actual_origin",
    "actual_destination",
    "actual_departure_utc",
    "actual_arrival_utc",
    "next_flight_id",
    "link_outcome",
    "anomaly_code",
    "as_of_aircraft_type_id",
    "as_of_engine_type_id",
    "actual_source_aircraft_type",
    "type_discrepancy",
)

#: ``row_kind DESC`` in the frozen ``order_by`` puts ``LEG`` before ``ANOMALY``. Ascending would
#: invert it. Within one result set the two kinds never share a ``segment_id`` because their
#: templates differ, so the leading ``segment_id ASC`` key settles the block order on its own:
#: ``SYN-ANOM-*`` sorts before ``SYN-ROT-*``.
ROW_KIND_LEG = "LEG"
ROW_KIND_ANOMALY = "ANOMALY"

#: DV-25 class whose output rows are collapsed to one per component. The precedence itself, and
#: which member is the representative, are the ontology's answer and are not re-derived here.
CYCLE_ANOMALY_CLASS = "CYCLE"

#: The eleven classes the frozen manifest declares at
#: ``scope.rotation_anomaly_support.anomaly_precedence``. Listed here as a *vocabulary* only - the
#: order in that array is the one D-0021 rejects (it puts ``DIVERSION_ENDPOINT_CONFLICT`` sixth,
#: while ``ATTRIBUTE_AUTHORITY.md:338`` DV-25 puts it eighth and the manifest's own rows follow
#: DV-25). Nothing in this module orders anomalies by class, so the contradiction is inert here;
#: the classification and its precedence are ``MODEL_INPUT``'s answer, read through
#: ``RotationLinkValidation``.
MANIFEST_ANOMALY_CLASSES: frozenset[str] = frozenset(
    {
        "SELF_LOOP",
        CYCLE_ANOMALY_CLASS,
        "MISSING_TARGET",
        "DIFFERENT_AIRCRAFT",
        "OUTSIDE_SELECTED_DAY",
        "BACKWARD_TIME",
        "BROKEN_CONTINUITY",
        "DIVERSION_ENDPOINT_CONFLICT",
        "CANCELLED",
        "MISSING_TIME",
        "UNKNOWN_OR_INVALID_CANCELLATION_FLAG",
    }
)

#: ``TARGET_NOT_OPERATED`` (D-0020 A5) is a twelfth class that ``MODEL_INPUT`` emits for a link
#: whose *target* is cancelled, carries an invalid cancellation flag, or has no actual arrival
#: time. It is outside the DV-25 vocabulary, it is absent from
#: :data:`MANIFEST_ANOMALY_CLASSES`, and - the part that matters - the independent SQL oracle in
#: ``data/oracles/q08_actual_rotation_enriched.sql`` has no branch for it, so a conformance
#: harness diverges the first time a selected rotation hits one. D-0021 records this against A5,
#: which was written when the class had zero rows; the enriched universe has four (flights 5310,
#: 5470, 6190, 6345, none of them in a frozen Q08 result set).
#:
#: The row is **emitted**, not suppressed. ``is_accepted_link`` is false for it, so the chain
#: genuinely stops there; hiding the anomaly would delete a leg from the answer with no stated
#: reason, which is the exact failure mode "losing excluded legs" warns about. Instead every
#: invocation reports which beyond-vocabulary classes it emitted
#: (:attr:`RotationResult.beyond_manifest_anomaly_classes`) so the divergence is loud.
BEYOND_MANIFEST_ANOMALY_CLASS = "TARGET_NOT_OPERATED"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _REPO_ROOT / "EXPECTED_ANSWERS.yaml"


# --------------------------------------------------------------------------- errors


class RotationQueryError(Exception):
    """Base for every non-``OK`` invocation of Q08.

    Carries the manifest's two-level outcome: an ``invocation_status`` and an ``error_code``.
    ``EXPECTED_ANSWERS.yaml`` freezes zero rows for these, and the manifest's own object rules
    require a caller to be able to tell a refusal apart from a legitimately empty answer, so the
    refusal is raised rather than returned as an empty frame.
    """

    invocation_status = "ERROR"
    error_code = "ERROR"

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class RotationParameterError(RotationQueryError):
    """A typed parameter violates ``parameter_schema``. No query is executed."""

    invocation_status = "PARAMETER_ERROR"


class RotationNotFound(RotationQueryError):
    """The parameters are well formed and the selection is empty.

    ``Q08-NOT-FOUND`` freezes this for aircraft 1999 on 2026-08-31: the aircraft exists and has
    three actual flights, all in 2040, so the selected day holds none. "Empty is an answer" does
    not apply here - the manifest gives this scenario ``NOT_FOUND`` / ``NO_ACTUAL_FLIGHTS`` rather
    than ``OK`` with zero rows.
    """

    invocation_status = "NOT_FOUND"


class RotationInvariantError(RuntimeError):
    """A structural impossibility in the reconstructed chain.

    Raised rather than returned, because every one of these means the emitted ``leg_order`` would
    be a plausible but wrong sequence. ``accepted_next_flight`` is a ``Property`` so out-degree is
    at most one; a leg reachable from two segment heads (in-degree above one) would double-count,
    and a gap in ``leg_order`` would mean the closure and the head set disagree.
    """


@dataclass(frozen=True)
class RotationResult:
    """A catalog-shaped invocation outcome: status, error code, rows.

    ``QUERY-INT`` owns the catalog layer, so :func:`invoke` exists to hand it the frozen triple
    without making it catch exceptions. The raising form (:func:`actual_rotation_enriched`) stays
    the primary entry point.

    ``beyond_manifest_anomaly_classes`` is the fence around
    :data:`BEYOND_MANIFEST_ANOMALY_CLASS`: any emitted anomaly class outside the manifest's
    eleven-class vocabulary, sorted. Empty for all six frozen Q08 result sets. Non-empty means the
    answer is still the model's truth but the independent SQL oracle will disagree, so a
    conformance harness must report the divergence rather than absorb it.
    """

    invocation_status: str
    error_code: str | None
    rows: pd.DataFrame
    beyond_manifest_anomaly_classes: tuple[str, ...] = ()


# ----------------------------------------------------------------- parameter validation


def _coerce_aircraft_id(value: Any) -> int:
    """AM-01 identity, ``NUMBER(38,0)``, not nullable.

    ``bool`` is rejected explicitly: it is an ``int`` subclass in Python, and ``True`` would
    silently select aircraft 1.
    """
    if value is None:
        raise RotationParameterError(
            "MISSING_AIRCRAFT_ID", "aircraft_id is required and must not be null"
        )
    if isinstance(value, bool):
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id must be an integer, got {value!r}"
        )
    try:
        aircraft_id = int(value)
    except (TypeError, ValueError):
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id must be an integer, got {value!r}"
        ) from None
    if aircraft_id != value and not isinstance(value, str):
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id must be integral, got {value!r}"
        )
    if aircraft_id <= 0:
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id is out of domain: {value!r}"
        )
    return aircraft_id


def _coerce_departure_date(value: Any) -> dt.date:
    """AF-06, the **source-local** departure date. Never AF-07 and never derived from AF-13.

    A ``datetime`` is narrowed to its date part; an ISO string is parsed. An uncastable string
    such as ``2026-02-30`` is ``INVALID_DATE``, matching the manifest's naming for Q06.
    """
    if value is None:
        raise RotationParameterError(
            "MISSING_FLIGHT_DEPARTURE_DATE",
            "flight_departure_date is required and must not be null",
        )
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            raise RotationParameterError(
                "INVALID_DATE", f"flight_departure_date is not a valid date: {value!r}"
            ) from None
    raise RotationParameterError(
        "INVALID_DATE", f"flight_departure_date must be a DATE, got {value!r}"
    )


# ------------------------------------------------------------------------- pandas helpers
#
# Every cell that leaves RAI goes through one of these. Integer aggregates come back as an
# ``Int128Array`` whose missing element is ``pd.NA``, a sparse property renders as ``NaN`` in an
# object or ``StringDtype`` column, and a missing ``DateTime`` renders as ``NaT``. All three mean
# "no fact" and all three must become ``None`` before they are compared against the manifest's
# YAML nulls.


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _int_or_none(value: Any) -> int | None:
    return None if _is_missing(value) else int(value)


def _str_or_none(value: Any) -> str | None:
    return None if _is_missing(value) else str(value)


def _bool_or_none(value: Any) -> bool | None:
    return None if _is_missing(value) else bool(value)


def _datetime_or_none(value: Any) -> dt.datetime | None:
    if _is_missing(value):
        return None
    stamp = pd.Timestamp(value)
    return stamp.to_pydatetime()


# ------------------------------------------------------------------------------ queries


def _default_package():
    """Import the ontology package lazily.

    ``aviation_model`` constructs the single ``Model`` at import time and a second ``Model`` in
    one interpreter makes the free ``distinct(...)`` raise ``[Ambiguous model]`` (PROBE N-02), so
    importing this module must not build one. Callers that already hold the package pass it in.
    """
    import aviation_model

    return aviation_model


# ------------------------------------------------------------------ concurrency: the model lock
#
# Importing any query module installs the ontology, which is a **write transaction** on the shared
# `aviation_temporal` model. While it is open, another process's read does not queue - it fails,
# and the failure surfaces two levels away from its cause: the SDK reports
# ``SnowflakeTableObjectsException: Getting the following table failed with the error in
# Snowflake``, and only the debug span carries the real text, ``model is currently locked by
# active write transaction(s)``. Measured here: three of four path-experiment invocations in one
# process, and one of forty-one test cases, all while a sibling query agent was installing its own
# module. Retrying is correct; debugging the query is not.

#: Substrings that identify a lock collision rather than a defect. Matched against the whole
#: exception chain because the informative text is nested inside the SDK's wrapper.
_MODEL_LOCK_MARKERS = (
    "model is currently locked",
    "Getting the following table failed with the error in Snowflake",
)

MODEL_LOCK_ATTEMPTS = 6
MODEL_LOCK_BACKOFF_SECONDS = 20.0


def is_model_lock_error(error: BaseException) -> bool:
    """True when an exception (or anything it wraps) is the shared-model write lock."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = f"{type(current).__name__}: {current}"
        if any(marker in text for marker in _MODEL_LOCK_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


def retry_on_model_lock(
    call,
    *,
    attempts: int = MODEL_LOCK_ATTEMPTS,
    backoff_seconds: float = MODEL_LOCK_BACKOFF_SECONDS,
    on_retry=None,
):
    """Run ``call()``, retrying only while a sibling holds the model's write lock.

    Deliberately narrow. Any exception that is not :func:`is_model_lock_error` propagates on the
    first attempt, because a retry loop that swallows a real ``TyperError`` or an empty-frame
    ``KeyError`` would turn a query bug into a slow query bug.
    """
    import time

    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - re-raised unless it is the lock
            if attempt == attempts or not is_model_lock_error(error):
                raise
            if on_retry is not None:
                on_retry(attempt, error)
            time.sleep(backoff_seconds)
    raise AssertionError("unreachable")


def warm_model(am=None, **retry_kwargs):
    """Take the model lock hit once, up front, on a query too small to be anything else.

    Call this before a timed run or a test session so a sibling's install shows up here rather
    than as a failure attributed to whichever result set happened to be first.
    """
    package = am if am is not None else _default_package()
    retry_on_model_lock(
        lambda: package.model.select(aggs.count(package.AircraftFlight).alias("n")).to_df(),
        **retry_kwargs,
    )
    return package


def selected_leg_count(am, aircraft_id: int, day: dt.date) -> int:
    """How many actual legs the aircraft flew on the selected AF-06 date.

    This is the ``NOT_FOUND`` gate and it is deliberately its own query: it separates "this
    aircraft did not fly that day" from "it flew and every link was refused", which are different
    answers with the same row count in the anomaly-only case.

    An empty RAI result is a **zero-column** DataFrame rather than a zero-row frame with the
    expected columns (PROBE D11), so the shape is checked before any cell is read.
    """
    df = (
        am.model.select(aggs.count(am.AircraftFlight).alias("n"))
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == aircraft_id,
            am.AircraftFlight.flight_departure_date == day,
        )
        .to_df()
    )
    if df.shape[0] == 0 or df.shape[1] == 0:
        return 0
    return _int_or_none(df.iloc[0, 0]) or 0


def chain_legs(am, aircraft_id: int, day: dt.date) -> pd.DataFrame:
    """The operated chain: one row per leg, with its segment head and its traversal position.

    The whole question is in the ``where`` clause, so it is worth reading slowly.

    * ``RotationSegmentHead(head)`` is a leg with no accepted **inbound** edge, authored in the
      ontology as ``not_(inbound.accepted_next_flight == leg)``.
    * ``model.not_(head_val.rotation_anomaly_class)`` requires the head's own validated link to
      carry no DV-25 anomaly class. It is a negation over the property's *existence*: writing
      ``not_(head_val.rotation_anomaly_class == "CYCLE")`` would ask "is there some class this is
      not equal to", which is true for nearly every row. Filtering the **head** alone is
      sufficient and is exactly the independent oracle's ``chain_start`` predicate, because an
      accepted edge can only leave an anomaly-free leg; a leg whose own outgoing link is
      anomalous can therefore still be a chain member (reached by an accepted edge) while also
      appearing as an anomaly row. No shipped fixture exercises that overlap, and it is the
      oracle's behaviour too.
    * ``rotation_leg_distance(head, leg)`` is the transitive closure over the accepted edge,
      appearing twice on purpose: once in ``where`` so a pair with no path is excluded rather than
      rendered as ``NaN``, and once in ``select`` where ``+ 1`` turns "hops from the head" into
      ``leg_order``. That is the *only* source of ordering in this module.
    * ``leg_val.flight == leg`` reads DV-24 for the leg's own link, which is the ``link_outcome``.
      Exactly one ``RotationLinkValidation`` row exists per flight (3,900 of 3,900), the terminal
      one carrying the literal ``NO_TARGET`` token, so this cannot inflate.

    Endpoints are read through the resolved ``Airport`` entity, so the ``SYN-AP-*`` internal-ID
    code system is honoured structurally. Planned endpoints are public IATA labels resolved
    against a different field and are never joined here.
    """
    head = am.AircraftFlight.ref("rotation_head")
    head_val = am.RotationLinkValidation.ref("rotation_head_validation")
    leg_val = am.RotationLinkValidation.ref("rotation_leg_validation")
    leg = am.AircraftFlight
    return (
        am.model.select(
            head.flight_id.alias("segment_head_flight_id"),
            (am.rotation_leg_distance(head, leg) + 1).alias("leg_order"),
            leg.flight_id.alias("flight_id"),
            leg.actual_origin.airport_id.alias("actual_origin"),
            leg.actual_destination.airport_id.alias("actual_destination"),
            leg.actual_gate_departure_time_utc.alias("actual_departure_utc"),
            leg.actual_gate_arrival_time_utc.alias("actual_arrival_utc"),
            leg.next_flight_id.alias("next_flight_id"),
            leg_val.rotation_link_status.alias("link_outcome"),
            leg.as_of_aircraft_type.subseries.alias("as_of_aircraft_type_id"),
            leg.as_of_engine_type.subseries.alias("as_of_engine_type_id"),
            leg.actual_source_aircraft_type.alias("actual_source_aircraft_type"),
            leg.type_discrepancy.alias("type_discrepancy"),
        )
        .where(
            leg.aircraft == am.Aircraft,
            am.Aircraft.id == aircraft_id,
            leg.flight_departure_date == day,
            am.RotationSegmentHead(head),
            head_val.flight == head,
            am.model.not_(head_val.rotation_anomaly_class),
            am.rotation_leg_distance(head, leg),
            leg_val.flight == leg,
        )
        .to_df()
    )


def rotation_anomalies(am, aircraft_id: int, day: dt.date, *, deduplicate_cycles: bool = True) -> pd.DataFrame:
    """The typed anomaly companion set: one row per refused or excluded leg.

    ``where(val.rotation_anomaly_class)`` binds the bare property, which requires a value to
    exist, so an anomaly-free leg does not appear. The DV-25 class and its precedence are the
    ontology's answer; nothing is reclassified here.

    ``deduplicate_cycles`` applies the presentation rule from ``DEMO_QUESTIONS.md``: one ``CYCLE``
    row per component, anchored at its minimum ``flight_id``. It is expressed as
    ``not_(class == CYCLE, is_cycle_representative == False)``, which is ``NOT(A AND B)`` over two
    literal comparisons on an already-bound reference. Note ``== False`` rather than a bare
    property reference: ``where(Concept.bool_property)`` matches every entity that *has* the
    property regardless of value. Pass ``False`` to see the retained evidence, which is what
    :func:`rotation_anomaly_evidence` does.
    """
    val = am.RotationLinkValidation.ref("rotation_anomaly_validation")
    leg = am.AircraftFlight
    conditions = [
        leg.aircraft == am.Aircraft,
        am.Aircraft.id == aircraft_id,
        leg.flight_departure_date == day,
        val.flight == leg,
        val.rotation_anomaly_class,
    ]
    if deduplicate_cycles:
        conditions.append(
            am.model.not_(
                val.rotation_anomaly_class == CYCLE_ANOMALY_CLASS,
                val.is_cycle_representative == False,  # noqa: E712
            )
        )
    return (
        am.model.select(
            leg.flight_id.alias("flight_id"),
            leg.actual_origin.airport_id.alias("actual_origin"),
            leg.actual_destination.airport_id.alias("actual_destination"),
            leg.actual_gate_departure_time_utc.alias("actual_departure_utc"),
            leg.actual_gate_arrival_time_utc.alias("actual_arrival_utc"),
            leg.next_flight_id.alias("next_flight_id"),
            val.rotation_link_status.alias("link_outcome"),
            val.rotation_anomaly_class.alias("anomaly_code"),
            val.cycle_component_id.alias("cycle_component_id"),
            val.is_cycle_representative.alias("is_cycle_representative"),
        )
        .where(*conditions)
        .to_df()
    )


def rotation_anomaly_evidence(am, aircraft_id: int, day: dt.date) -> pd.DataFrame:
    """Every anomaly row including the cycle members the output collapses.

    The contract is "retain all member and link evidence, emit one row per component". This is the
    retained half, and it is what makes the collapse auditable rather than a silent drop: flight
    8103 is here and is not in the answer.
    """
    return rotation_anomalies(am, aircraft_id, day, deduplicate_cycles=False)


# ---------------------------------------------------------------------------- assembly


def _segment_id(aircraft_id: int, day: dt.date, ordinal: int) -> str:
    """``SYN-ROT-<aircraft>-<YYYYMMDD>-<NN>``.

    A manifest-adopted presentation label (D-0021 reclassified Q08's 14 ``segment_id`` cells as
    exactly that), deliberately assembled here and not in the PyRel model, per the D-0018
    binding that keeps output templates out of the ontology.
    """
    return f"SYN-ROT-{aircraft_id}-{day.strftime('%Y%m%d')}-{ordinal:02d}"


def _anomaly_segment_id(ordinal: int) -> str:
    """``SYN-ANOM-<NN>``, ordinal by ``flight_id`` ascending. Also manifest-adopted."""
    return f"SYN-ANOM-{ordinal:02d}"


def _leg_record(row: pd.Series, segment_id: str) -> dict[str, Any]:
    return {
        "row_kind": ROW_KIND_LEG,
        "segment_id": segment_id,
        "leg_order": _int_or_none(row["leg_order"]),
        "flight_id": _int_or_none(row["flight_id"]),
        "actual_origin": _str_or_none(row["actual_origin"]),
        "actual_destination": _str_or_none(row["actual_destination"]),
        "actual_departure_utc": _datetime_or_none(row["actual_departure_utc"]),
        "actual_arrival_utc": _datetime_or_none(row["actual_arrival_utc"]),
        "next_flight_id": _int_or_none(row["next_flight_id"]),
        "link_outcome": _str_or_none(row["link_outcome"]),
        # A LEG row never carries an anomaly code. The refusal that ended the chain, if there was
        # one, is reported on its own ANOMALY row.
        "anomaly_code": None,
        "as_of_aircraft_type_id": _str_or_none(row["as_of_aircraft_type_id"]),
        "as_of_engine_type_id": _str_or_none(row["as_of_engine_type_id"]),
        "actual_source_aircraft_type": _str_or_none(row["actual_source_aircraft_type"]),
        "type_discrepancy": _bool_or_none(row["type_discrepancy"]),
    }


def _anomaly_record(row: pd.Series, segment_id: str) -> dict[str, Any]:
    return {
        "row_kind": ROW_KIND_ANOMALY,
        "segment_id": segment_id,
        # An anomaly has no position in the operated chain, so leg_order and all four enrichment
        # columns are null. Filling them in would imply the leg was operated in sequence.
        "leg_order": None,
        "flight_id": _int_or_none(row["flight_id"]),
        "actual_origin": _str_or_none(row["actual_origin"]),
        "actual_destination": _str_or_none(row["actual_destination"]),
        "actual_departure_utc": _datetime_or_none(row["actual_departure_utc"]),
        "actual_arrival_utc": _datetime_or_none(row["actual_arrival_utc"]),
        "next_flight_id": _int_or_none(row["next_flight_id"]),
        "link_outcome": _str_or_none(row["link_outcome"]),
        "anomaly_code": _str_or_none(row["anomaly_code"]),
        "as_of_aircraft_type_id": None,
        "as_of_engine_type_id": None,
        "actual_source_aircraft_type": None,
        "type_discrepancy": None,
    }


#: Default ``row_id`` label shape, the one the v1.1.1 result sets use (``Q08-R001``). The v1.2.0
#: result sets label their rows ``Q08-ENRICHED-ROTATION-R0001`` instead - a different prefix and a
#: different zero-pad width. ``row_id`` is a *supplied* manifest label (D-0021 counts Q08's 14
#: ``row_id`` cells as supplied, not derived), so reproducing either shape is a caller's choice and
#: not a semantic claim; :func:`row_id_label_format` recovers it from the manifest.
DEFAULT_ROW_ID_PREFIX = f"{QUESTION_ID}-R"
DEFAULT_ROW_ID_WIDTH = 3


def _assemble(
    leg_rows: pd.DataFrame,
    anomaly_rows: pd.DataFrame,
    aircraft_id: int,
    day: dt.date,
    row_id_start: int,
    row_id_prefix: str,
    row_id_width: int,
) -> pd.DataFrame:
    """Build the frozen frame in the frozen order, without re-deriving any order.

    The sequence is constructed rather than sorted into place:

    * ``SYN-ANOM-*`` blocks come first because ``segment_id ASC`` is the leading order key and
      ``A`` precedes ``R``. Within them the ordinal, and therefore the order, is ``flight_id``
      ascending, which is the manifest's presentation rule for the anomaly companion set.
    * ``SYN-ROT-*`` segments follow, numbered by their head's ``flight_id`` ascending, and inside
      each segment the rows are placed by ``leg_order`` - the value the traversal produced. No
      time column is ever an ordering key.
    """
    records: list[dict[str, Any]] = []

    if anomaly_rows.shape[1] > 0 and not anomaly_rows.empty:
        ordered_anomalies = anomaly_rows.sort_values("flight_id", kind="stable")
        for ordinal, (_, row) in enumerate(ordered_anomalies.iterrows(), start=1):
            records.append(_anomaly_record(row, _anomaly_segment_id(ordinal)))

    if leg_rows.shape[1] > 0 and not leg_rows.empty:
        heads = sorted({_int_or_none(v) for v in leg_rows["segment_head_flight_id"]})
        seen: set[int] = set()
        for ordinal, head_flight_id in enumerate(heads, start=1):
            segment = leg_rows[
                leg_rows["segment_head_flight_id"].map(_int_or_none) == head_flight_id
            ]
            positions = [_int_or_none(v) for v in segment["leg_order"]]
            if sorted(positions) != list(range(1, len(positions) + 1)):
                raise RotationInvariantError(
                    f"segment anchored at flight {head_flight_id} has leg_order {sorted(positions)}, "
                    f"expected 1..{len(positions)}"
                )
            segment_id = _segment_id(aircraft_id, day, ordinal)
            for _, row in segment.sort_values("leg_order", kind="stable").iterrows():
                flight_id = _int_or_none(row["flight_id"])
                if flight_id in seen:
                    raise RotationInvariantError(
                        f"flight {flight_id} is reachable from more than one segment head; "
                        "the accepted edge set is not a set of disjoint chains"
                    )
                seen.add(flight_id)
                records.append(_leg_record(row, segment_id))

    row_ids = itertools.count(row_id_start)
    for record in records:
        record["row_id"] = f"{row_id_prefix}{next(row_ids):0{row_id_width}d}"

    frame = pd.DataFrame.from_records(records, columns=list(OUTPUT_COLUMNS))
    return _typed(frame)


def _typed(frame: pd.DataFrame) -> pd.DataFrame:
    """Give the frame the frozen ``output_schema`` types.

    ``NUMBER(38,0)`` nullable columns become pandas nullable ``Int64`` rather than ``float64``, so
    a flight id never comes back as ``8002.0``; ``BOOLEAN`` nullable becomes ``boolean`` so the
    third state stays ``NA`` instead of collapsing to ``False``; and the two ``TIMESTAMP_NTZ``
    columns become ``datetime64[ns]`` so a missing gate time is ``NaT``.
    """
    frame = frame.copy()
    for column in ("leg_order", "flight_id", "next_flight_id"):
        frame[column] = pd.array(
            [_int_or_none(v) for v in frame[column]], dtype="Int64"
        )
    for column in ("actual_departure_utc", "actual_arrival_utc"):
        frame[column] = pd.to_datetime(
            pd.Series([_datetime_or_none(v) for v in frame[column]], dtype="object"),
            errors="raise",
        )
    frame["type_discrepancy"] = pd.array(
        [_bool_or_none(v) for v in frame["type_discrepancy"]], dtype="boolean"
    )
    for column in (
        "row_id",
        "row_kind",
        "segment_id",
        "actual_origin",
        "actual_destination",
        "link_outcome",
        "anomaly_code",
        "as_of_aircraft_type_id",
        "as_of_engine_type_id",
        "actual_source_aircraft_type",
    ):
        frame[column] = pd.Series(
            [_str_or_none(v) for v in frame[column]], dtype="object"
        )
    return frame.reset_index(drop=True)


# ------------------------------------------------------------------------- entry points


def actual_rotation_enriched(
    aircraft_id: Any,
    flight_departure_date: Any,
    *,
    am=None,
    row_id_start: int = 1,
    row_id_prefix: str = DEFAULT_ROW_ID_PREFIX,
    row_id_width: int = DEFAULT_ROW_ID_WIDTH,
) -> pd.DataFrame:
    """Q08. The validated, ordered, enriched actual rotation of one aircraft on one local day.

    Parameters
    ----------
    aircraft_id:
        AM-01 identity, ``NUMBER(38,0)``, required.
    flight_departure_date:
        AF-06, the source-local departure date, ``DATE``, required. A ``date``, a ``datetime`` or
        an ISO string.
    am:
        The loaded ``aviation_model`` package. Imported on demand when omitted; pass it in to
        keep one ``Model`` per process.
    row_id_start:
        First ``row_id`` ordinal. ``row_id`` is a *supplied* manifest label rather than a derived
        value (D-0021 counts Q08's 14 ``row_id`` cells as supplied), and the manifest numbers it
        continuously across result sets, so the offset is a caller's choice:
        ``Q08-CANONICAL`` starts at 1 and ``Q08-ANOMALIES`` at 4.
    row_id_prefix, row_id_width:
        The rest of the label shape, for the same reason. v1.1.1 uses ``Q08-R`` and 3 digits;
        the v1.2.0 result sets use their own ``Q08-<SET>-R`` prefix and 4 digits.
        :func:`row_id_label_format` reads both off the manifest.

    Returns
    -------
    A DataFrame with exactly :data:`OUTPUT_COLUMNS`, in the frozen ``order_by`` sequence.

    Raises
    ------
    RotationParameterError
        A typed parameter is null or out of domain. No query runs.
    RotationNotFound
        ``NO_ACTUAL_FLIGHTS``: the aircraft flew no leg on that AF-06 date.
    """
    aircraft = _coerce_aircraft_id(aircraft_id)
    day = _coerce_departure_date(flight_departure_date)
    package = am if am is not None else _default_package()

    if selected_leg_count(package, aircraft, day) == 0:
        raise RotationNotFound(
            "NO_ACTUAL_FLIGHTS",
            f"aircraft {aircraft} operated no actual flight on {day.isoformat()}",
        )

    legs = chain_legs(package, aircraft, day)
    anomalies = rotation_anomalies(package, aircraft, day)
    return _assemble(
        legs, anomalies, aircraft, day, row_id_start, row_id_prefix, row_id_width
    )


def beyond_manifest_anomaly_classes(frame: pd.DataFrame) -> tuple[str, ...]:
    """Emitted anomaly classes outside the manifest's eleven-class DV-25 vocabulary.

    Today that is only :data:`BEYOND_MANIFEST_ANOMALY_CLASS`, but the check is written against
    the vocabulary rather than against that one literal, so a future ``MODEL_INPUT`` class is
    caught the same way instead of arriving unannounced.
    """
    if frame.shape[1] == 0 or frame.empty:
        return ()
    emitted = {
        _str_or_none(value)
        for value in frame["anomaly_code"]
        if _str_or_none(value) is not None
    }
    return tuple(sorted(emitted - MANIFEST_ANOMALY_CLASSES))


def invoke(
    aircraft_id: Any,
    flight_departure_date: Any,
    *,
    am=None,
    row_id_start: int = 1,
    row_id_prefix: str = DEFAULT_ROW_ID_PREFIX,
    row_id_width: int = DEFAULT_ROW_ID_WIDTH,
) -> RotationResult:
    """:func:`actual_rotation_enriched` as a catalog triple instead of an exception."""
    try:
        rows = actual_rotation_enriched(
            aircraft_id,
            flight_departure_date,
            am=am,
            row_id_start=row_id_start,
            row_id_prefix=row_id_prefix,
            row_id_width=row_id_width,
        )
    except RotationQueryError as error:
        empty = _typed(pd.DataFrame(columns=list(OUTPUT_COLUMNS)))
        return RotationResult(type(error).invocation_status, error.error_code, empty)
    return RotationResult("OK", None, rows, beyond_manifest_anomaly_classes(rows))


# --------------------------------------------------------------- frozen-answer comparison


def canonical_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """One canonical dict per row, in row order, for comparison against the manifest.

    Absence is ``None`` whichever way pandas rendered it (``NA``, ``NaN``, ``NaT``), integers are
    ``int`` rather than ``Int64`` scalars, and timestamps are naive ``datetime`` objects, which is
    what the manifest's ``timestamp_representation`` ("cast to TIMESTAMP_NTZ before comparison")
    asks for.
    """
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "row_id": _str_or_none(row["row_id"]),
                "row_kind": _str_or_none(row["row_kind"]),
                "segment_id": _str_or_none(row["segment_id"]),
                "leg_order": _int_or_none(row["leg_order"]),
                "flight_id": _int_or_none(row["flight_id"]),
                "actual_origin": _str_or_none(row["actual_origin"]),
                "actual_destination": _str_or_none(row["actual_destination"]),
                "actual_departure_utc": _datetime_or_none(row["actual_departure_utc"]),
                "actual_arrival_utc": _datetime_or_none(row["actual_arrival_utc"]),
                "next_flight_id": _int_or_none(row["next_flight_id"]),
                "link_outcome": _str_or_none(row["link_outcome"]),
                "anomaly_code": _str_or_none(row["anomaly_code"]),
                "as_of_aircraft_type_id": _str_or_none(row["as_of_aircraft_type_id"]),
                "as_of_engine_type_id": _str_or_none(row["as_of_engine_type_id"]),
                "actual_source_aircraft_type": _str_or_none(
                    row["actual_source_aircraft_type"]
                ),
                "type_discrepancy": _bool_or_none(row["type_discrepancy"]),
            }
        )
    return rows


def _canonical_frozen_cell(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in ("actual_departure_utc", "actual_arrival_utc"):
        return dt.datetime.fromisoformat(str(value))
    if column in ("leg_order", "flight_id", "next_flight_id"):
        return int(value)
    if column == "type_discrepancy":
        return bool(value)
    return str(value)


def frozen_result_sets() -> list[dict[str, Any]]:
    """Parse Q08 out of ``EXPECTED_ANSWERS.yaml``. The manifest is FROZEN and read-only here."""
    import yaml

    with _MANIFEST_PATH.open() as handle:
        manifest = yaml.safe_load(handle)
    question = next(q for q in manifest["questions"] if q["question_id"] == QUESTION_ID)
    result_sets: list[dict[str, Any]] = []
    for raw in question["result_sets"]:
        rows = [
            {
                column: _canonical_frozen_cell(column, row.get(column))
                for column in OUTPUT_COLUMNS
            }
            for row in raw.get("rows") or []
        ]
        result_sets.append(
            {
                "result_set_id": raw["result_set_id"],
                "manifest_version": raw.get("manifest_version"),
                "parameters": raw["parameters"],
                "invocation_status": raw["invocation_status"],
                "error_code": raw.get("error_code"),
                "expected_cardinality": raw["expected_cardinality"],
                "rows": rows,
            }
        )
    return result_sets


def diff_rows(
    actual: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]
) -> list[str]:
    """Human-readable differences between two canonical row sequences, or an empty list."""
    problems: list[str] = []
    if len(actual) != len(expected):
        problems.append(f"cardinality: got {len(actual)}, expected {len(expected)}")
    for index, (got, want) in enumerate(zip(actual, expected)):
        for column in OUTPUT_COLUMNS:
            if got[column] != want[column]:
                problems.append(
                    f"row {index} ({want.get('row_id')}) {column}: "
                    f"got {got[column]!r}, expected {want[column]!r}"
                )
    return problems


# ------------------------------------------------------------------------------- main


def row_id_label_format(result_set: dict[str, Any]) -> tuple[str, int, int]:
    """Recover ``(prefix, width, start)`` for one result set's ``row_id`` labels.

    The manifest uses two shapes and neither is derivable from the data:

    * v1.1.1 numbers continuously across result sets in one ``Q08-R<3 digits>`` series -
      ``Q08-CANONICAL`` starts at ``Q08-R001`` and ``Q08-ANOMALIES`` resumes at ``Q08-R004``.
    * v1.2.0 restarts at 1 inside a per-result-set prefix with four digits, for example
      ``Q08-ENRICHED-ANOMALIES-R0001``.

    Reading the shape off the expected rows is honest precisely because ``row_id`` is a supplied
    label: D-0021 counts Q08's 14 ``row_id`` cells as supplied rather than derived, so this
    reproduces a presentation convention and asserts nothing about the answer. Every other column
    is compared against the manifest without being told anything.
    """
    rows = result_set["rows"]
    if not rows:
        return DEFAULT_ROW_ID_PREFIX, DEFAULT_ROW_ID_WIDTH, 1
    label = str(rows[0]["row_id"])
    head, _, digits = label.rpartition("R")
    if not digits.isdigit():
        return DEFAULT_ROW_ID_PREFIX, DEFAULT_ROW_ID_WIDTH, 1
    return f"{head}R", len(digits), int(digits)


def main() -> int:
    """Run every frozen Q08 result set against the live model and report pass or fail."""
    import time

    def note_retry(attempt: int, _error: BaseException) -> None:
        print(f"           (model locked by a sibling write; retry {attempt})")

    warm_started = time.time()
    am = warm_model(on_retry=note_retry)
    warm_elapsed = time.time() - warm_started

    result_sets = frozen_result_sets()
    failures = 0

    print(
        f"{QUESTION_ID} {CATALOG_ID}: {len(result_sets)} frozen result sets "
        f"(model install + warm {warm_elapsed:.1f}s)"
    )
    for result_set in result_sets:
        name = result_set["result_set_id"]
        parameters = result_set["parameters"]
        prefix, width, start = row_id_label_format(result_set)
        started = time.time()
        outcome = retry_on_model_lock(
            lambda: invoke(
                parameters["aircraft_id"],
                parameters["flight_departure_date"],
                am=am,
                row_id_start=start,
                row_id_prefix=prefix,
                row_id_width=width,
            ),
            on_retry=note_retry,
        )
        elapsed = time.time() - started

        problems: list[str] = []
        if outcome.invocation_status != result_set["invocation_status"]:
            problems.append(
                f"invocation_status: got {outcome.invocation_status}, "
                f"expected {result_set['invocation_status']}"
            )
        if outcome.error_code != result_set["error_code"]:
            problems.append(
                f"error_code: got {outcome.error_code}, expected {result_set['error_code']}"
            )
        if list(outcome.rows.columns) != list(OUTPUT_COLUMNS):
            problems.append(f"columns: got {list(outcome.rows.columns)}")
        problems.extend(diff_rows(canonical_rows(outcome.rows), result_set["rows"]))

        status = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        version = result_set.get("manifest_version") or "1.1.1"
        print(
            f"  [{status}] {name:<28} v{version}  {len(outcome.rows):>3} rows "
            f"({result_set['expected_cardinality']} expected)  "
            f"{outcome.invocation_status}/{outcome.error_code}  {elapsed:5.1f}s"
        )
        # Never silent: an anomaly class outside the manifest vocabulary is stated even when the
        # result set still matches, because the SQL oracle has no branch for it (D-0020 A5).
        if outcome.beyond_manifest_anomaly_classes:
            print(
                "           NOTE beyond-manifest anomaly class(es) emitted: "
                + ", ".join(outcome.beyond_manifest_anomaly_classes)
            )
        for problem in problems:
            print(f"           {problem}")

    print("ALL FROZEN Q08 RESULT SETS PASS" if not failures else f"{failures} RESULT SET(S) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


# ------------------------------------------------------------------------- entry point
#
# Last in the file on purpose: the embedded sources above are ordinary module globals, and
# calling main() before the interpreter has read them raises NameError.
#
# The condition is deliberately wider than the usual __main__ guard. A local `python
# run_all_queries.py` sets __name__ to "__main__"; a Snowsight Workspace Run, and a notebook
# cell that exec()s the file, execute it under a namespace that has no import machinery behind
# it, so __spec__ is absent. A genuine `import run_all_queries` always has a __spec__, and that
# is the one case where nothing should fire by itself - call run() when you are ready.

if __name__ == "__main__" or globals().get("__spec__") is None:
    raise SystemExit(1 if main() else 0)
else:
    # Never silent. If some runtime imports this file rather than running it, say so, so the
    # symptom is a printed hint and not an empty output pane.
    print(f"{__name__} imported, nothing run. Call run() - for example run(questions=['Q03']).")
