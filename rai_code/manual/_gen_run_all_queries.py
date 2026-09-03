"""_gen_run_all_queries.py - generate ``rai_code/manual/run_all_queries.py``.

The Snowsight-Workspace query runner is **generated**, never hand-maintained, for the same
reason ``rai_code/manual/aviation_temporal.py`` is: a second hand-written copy of a query
diverges from the first, and the divergence surfaces as a Workspace that answers differently
from the local test suite. This generator copies **no query logic at all**. It embeds the three
query modules verbatim and dispatches through the tables they already publish -
``uc1.CATALOG``, ``uc2.QUESTION_FUNCTIONS`` / ``uc2._PARAMETER_ORDER`` and ``rotation.invoke`` -
so a change to a query, its parameters or its columns is picked up by a regenerate and by
nothing else.

What the generator emits:

* the standalone ontology, taken live from :func:`aviation_model._gen_standalone.render` rather
  than from the checked-in artifact, so the runner can never embed a stale ontology;
* the three query modules verbatim, byte for byte from ``rai_code/queries/``;
* the enriched (manifest v1.2.0) parameter sets read out of ``EXPECTED_ANSWERS.yaml``, plus the
  frozen v1.1.1 sets as a selectable extra, with each question's declared parameter order taken
  from the manifest's own ``parameter_schema``;
* the business question text scraped from ``DEMO_QUESTIONS.md``.

The four sources are embedded as raw triple-single-quoted string literals and exec'd into
separate ``types.ModuleType`` objects at run time. Concatenating them the way
``_gen_standalone`` concatenates the ontology package is not an option here: ``uc1``, ``uc2``
and ``rotation`` each define ``warm_model``, ``main``, ``_records``, ``_is_missing`` and
``REPO_ROOT``, and ``uc1._records(df, columns)`` and ``uc2._records(df)`` do not even take the
same arguments. Separate module namespaces keep the three modules exactly as tested.

No secrets: credentials come from ``ConfigFromActiveSession`` inside Snowflake and from the
auto-discovered ``~/.snowflake`` profile locally. The generator re-uses ``_gen_standalone``'s
secret patterns and asserts the whole emitted file against them.

Regenerate with::

    .venv/bin/python rai_code/manual/_gen_run_all_queries.py
"""

from __future__ import annotations

import importlib.util
import pprint
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PACKAGE_DIR = REPO_ROOT / "rai_code" / "aviation_model"
QUERIES_DIR = REPO_ROOT / "rai_code" / "queries"
MANIFEST_PATH = REPO_ROOT / "EXPECTED_ANSWERS.yaml"
QUESTIONS_DOC = REPO_ROOT / "DEMO_QUESTIONS.md"
TARGET = HERE / "run_all_queries.py"

#: Slowest last. Q03 returns 985 rows in under four seconds and is the one that makes the
#: point fastest, so it opens; Q01 re-resolves four dimension streams per call and Q02F derives
#: every storage spell in the fleet, so those close. Measured warm on
#: ``aviation_temporal_logic_s`` (HIGHMEM_X64_S).
DISPLAY_ORDER = ("Q03", "Q04", "Q02", "Q08", "Q06", "Q07", "Q05", "Q01", "Q02F")

#: Which embedded module owns each question, and how the runner reaches it. The runner never
#: names a query function: ``uc1`` questions go through ``uc1.CATALOG``, ``uc2`` questions
#: through ``uc2.invoke_result_set``, and Q08 through ``rotation.invoke``.
QUESTION_MODULE = {
    "Q01": "uc1",
    "Q02": "uc1",
    "Q02F": "uc1",
    "Q03": "uc1",
    "Q04": "uc1",
    "Q05": "uc2",
    "Q06": "uc2",
    "Q07": "uc2",
    "Q08": "rotation",
}

#: Q02F post-dates ``DEMO_QUESTIONS.md`` (D-0026, manifest v1.2.0), so its heading and business
#: question have no source to scrape. Everything else is read out of the document.
EXTRA_TITLES = {
    "Q02F": (
        "Q02F - Bucket every storage spell in the fleet by duration",
        "Across the whole fleet rather than one aircraft, how are In Service -> Storage -> "
        "In Service spells distributed by duration, and how many distinct aircraft does each "
        "duration bucket involve?",
    ),
}


# ------------------------------------------------------------------ sources to embed


def _load_gen_standalone() -> Any:
    """Import ``_gen_standalone`` by path, without importing the ``aviation_model`` package.

    ``import aviation_model._gen_standalone`` would execute ``aviation_model/__init__.py``,
    which builds the ``Model`` and talks to Snowflake. The generator must run offline, so the
    module is loaded directly from its file; it imports only ``ast``, ``re`` and ``pathlib``.
    """
    spec = importlib.util.spec_from_file_location(
        "_gen_standalone_for_runner", PACKAGE_DIR / "_gen_standalone.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _embed(name: str, source: str) -> str:
    """One source file as a raw triple-single-quoted literal.

    Raw so that the backslashes in the sources' own escape sequences survive the round trip
    unchanged; triple-*single* because every docstring in all four files is delimited with
    ``\"\"\"``. The generator asserts the delimiter does not occur in the payload, and the
    payload always ends in a newline so no backslash can ever abut the closing quote.
    """
    if "'''" in source:
        raise AssertionError(f"{name} contains ''' and cannot be embedded as a raw literal")
    if not source.endswith("\n"):
        source += "\n"
    # The payload starts immediately after the opening delimiter so line numbers in a traceback
    # match the file it was copied from.
    return f"_SRC_{name.upper()} = r'''{source}'''\n"


# ------------------------------------------------------------------ manifest + doc scraping


def _manifest() -> dict[str, Any]:
    import yaml

    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _titles() -> dict[str, tuple[str, str]]:
    """``{question_id: (heading, business question)}`` scraped from ``DEMO_QUESTIONS.md``."""
    lines = QUESTIONS_DOC.read_text(encoding="utf-8").splitlines()
    heading = re.compile(r"^## (Q\d+[A-Z]?)\s+[\u2014-]\s+(.+)$")
    marker = "- **Business question:**"
    out: dict[str, tuple[str, str]] = {}

    for index, line in enumerate(lines):
        match = heading.match(line)
        if not match:
            continue
        qid, title = match.group(1), match.group(2).strip()
        business = ""
        for cursor in range(index + 1, len(lines)):
            if lines[cursor].startswith("## "):
                break
            if not lines[cursor].startswith(marker):
                continue
            business = lines[cursor].split(marker, 1)[1]
            for cont in lines[cursor + 1 :]:
                if not cont.startswith("  ") or cont.lstrip().startswith("- **"):
                    break
                business += " " + cont.strip()
            break
        out[qid] = (f"{qid} - {title}", " ".join(business.split()))

    out.update(EXTRA_TITLES)
    return out


def _question_specs() -> list[dict[str, Any]]:
    """One spec per question group, in :data:`DISPLAY_ORDER`, with both parameter tiers."""
    manifest = _manifest()
    titles = _titles()
    by_id = {q["question_id"]: q for q in manifest["questions"]}

    missing = [qid for qid in DISPLAY_ORDER if qid not in by_id]
    if missing:
        raise AssertionError(f"DISPLAY_ORDER names questions the manifest does not hold: {missing}")
    extra = [qid for qid in by_id if qid not in DISPLAY_ORDER]
    if extra:
        raise AssertionError(f"the manifest holds questions DISPLAY_ORDER does not run: {extra}")

    specs: list[dict[str, Any]] = []
    for qid in DISPLAY_ORDER:
        question = by_id[qid]
        heading, business = titles.get(qid, (qid, ""))
        sets = []
        for result_set in question["result_sets"]:
            version = result_set.get("manifest_version") or "1.1.1"
            sets.append(
                {
                    "result_set_id": result_set["result_set_id"],
                    "manifest_version": version,
                    "enriched": version == "1.2.0",
                    "parameters": dict(result_set["parameters"]),
                    "expected_status": result_set.get("invocation_status"),
                    "expected_rows": result_set.get("expected_cardinality"),
                }
            )
        if not any(s["enriched"] for s in sets):
            raise AssertionError(f"{qid} has no v1.2.0 enriched result set to default to")
        specs.append(
            {
                "question_id": qid,
                "catalog_id": question["catalog_id"],
                "module": QUESTION_MODULE[qid],
                "heading": heading,
                "business_question": business,
                "parameter_order": [p["name"] for p in question["parameter_schema"]],
                "order_by": list(question.get("order_by") or ()),
                "result_sets": sets,
            }
        )
    return specs


# ------------------------------------------------------------------ the emitted runner


_HEADER = '''#!/usr/bin/env python3
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
      'snow://workspace/\\"USER$<you>\\".PUBLIC.\\"DEFAULT$\\"/versions/live/aviation/queires/'
      AUTO_COMPRESS=FALSE OVERWRITE=TRUE;"

``LS 'snow://workspace/..."DEFAULT$"/versions/head/aviation/'`` lists what is there now. The
Snowsight UI route (Projects, Workspaces, the ``+`` beside a folder, Upload Files) does the
same thing by hand.

Nine question groups, {n_sets} enriched parameter sets, all against the live
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
'''


_BOOTSTRAP = '''

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
        print(f"  pip install {' '.join(arguments)} failed:\\n{completed.stderr.strip()[:2000]}")
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
        "terminal - and run it again.\\n"
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
                "This file needs " + ", ".join(missing) + ", and pip could not supply them.\\n"
                "  * Snowsight Workspace: attach snowflake.snowpark.pypi_shared_repository (or "
                "the PYPI_ACCESS external access integration) to the notebook service under "
                "Edit service, then re-run. You can also install it once from the Workspace "
                "terminal: pip install " + RELATIONALAI_REQUIREMENT + "\\n"
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
'''


_LOADER = '''

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
'''


_PRINTER = '''

# ---------------------------------------------------------------------------- printing

_RULE = "=" * 100


def _wrap(text: str, width: int = 96, indent: str = "  ") -> str:
    import textwrap

    return "\\n".join(textwrap.wrap(text, width=width, initial_indent=indent,
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
    text = "\\n".join("  " + line for line in body.splitlines())
    hidden = len(frame) - len(shown)
    if hidden:
        text += f"\\n  ... {hidden} more rows (set MAX_DISPLAY_ROWS = None to print them all)"
    return text


def _print_header(spec: dict) -> None:
    print()
    print(_RULE)
    print(spec["heading"])
    print(_RULE)
    if spec["business_question"]:
        print(_wrap(spec["business_question"]))
    print(f"  catalog id: {spec['catalog_id']}   order by: {', '.join(spec['order_by']) or '-'}")
'''


_RUNNER = '''

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
    print("\\n[1/3] runtime")
    ensure_runtime()

    print("\\n[2/3] ontology")
    mods = load_modules()

    print("\\n[3/3] model sync (roughly 150s on a READY engine, once for the whole run)")
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
'''


#: The entry point is emitted *after* the embedded sources, not with the rest of the runner.
#: ``_SRC_AVIATION_MODEL`` and friends are module globals, so they only exist once the
#: interpreter has read past them; a ``main()`` call placed above them raises ``NameError``
#: before a single query runs.
_ENTRYPOINT = '''

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
'''


def render() -> str:
    gen = _load_gen_standalone()
    specs = _question_specs()
    n_sets = sum(1 for spec in specs for rs in spec["result_sets"] if rs["enriched"])

    parts = [
        _HEADER.replace("{n_sets}", str(n_sets)),
        "\n#: One entry per question group, slowest last. Generated from ``EXPECTED_ANSWERS.yaml``\n"
        "#: (parameters, declared parameter order, expected cardinality) and ``DEMO_QUESTIONS.md``\n"
        "#: (the business question). Regenerate rather than editing.\n"
        "QUESTION_SPECS = " + pprint.pformat(specs, width=98, sort_dicts=False) + "\n\n"
        '_ORDER_INDEX = {spec["question_id"]: i for i, spec in enumerate(QUESTION_SPECS)}\n',
        _BOOTSTRAP,
        _LOADER,
        _PRINTER,
        _RUNNER,
        "\n\n# ============================================================================\n"
        "# Embedded sources. Byte-for-byte copies, exec'd into their own module namespaces\n"
        "# by load_modules() above. Everything below this line is generated; nothing below\n"
        "# this line should ever be edited in place.\n"
        "# ============================================================================\n\n",
        _embed("aviation_model", gen.render()),
        "\n",
        _embed("uc1", (QUERIES_DIR / "uc1.py").read_text(encoding="utf-8")),
        "\n",
        _embed("uc2", (QUERIES_DIR / "uc2.py").read_text(encoding="utf-8")),
        "\n",
        _embed("rotation", (QUERIES_DIR / "rotation.py").read_text(encoding="utf-8")),
        _ENTRYPOINT,
    ]
    text = "".join(parts)

    offenders = [p.pattern for p in gen._SECRET_PATTERNS if p.search(text)]
    if offenders:
        raise AssertionError(f"generated runner matches secret patterns: {offenders}")
    compile(text, str(TARGET), "exec")
    return text


def main() -> None:
    text = render()
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET} - {len(text.splitlines())} lines")


if __name__ == "__main__":  # pragma: no cover - operational entry point
    main()
