"""deploy.py - stage the notebook and its sibling sources, then create the Snowsight notebook.

Idempotent. Re-run it after any edit to ``aviation_viz.py``, ``build_notebook.py`` or the query
modules; it rebuilds the .ipynb, re-PUTs every file with ``OVERWRITE=TRUE``, and re-creates the
notebook object so the next open picks the new files up.

    .venv/bin/python rai_code/notebooks/deploy.py            # stage + create
    .venv/bin/python rai_code/notebooks/deploy.py --execute  # and run it headless
    .venv/bin/python rai_code/notebooks/deploy.py --url      # print the Snowsight URL

Two settings on the ``CREATE NOTEBOOK`` are load-bearing and neither survives being set in the
UI, because ``CREATE OR REPLACE`` does not carry UI state over:

``EXTERNAL_ACCESS_INTEGRATIONS = (PYPI_ACCESS)``
    the first cell pip-installs ``relationalai``, and a fresh container has no PyPI egress
    without it. Note the integration on this account is named ``PYPI_ACCESS``, not the
    ``PYPI_ACCESS_INTEGRATION`` the reference demos use.
``COMPUTE_POOL``
    opening a notebook interactively provisions a pool automatically; ``snow notebook execute``
    does not, and fails with no pool attached.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = ROOT / "rai_code" / "notebooks"

SNOW = "snow"
CONN = "rai"
ROLE = "RAI_DEMO_AVIATION_TEMPORAL"
DB = "PK_AVIATION_TEMPORAL"
WAREHOUSE = "RAI_XS"

NB_SCHEMA = "NOTEBOOKS"
NB_STAGE = "AVIATION_NOTEBOOK_STAGE"
NB_FOLDER = "aviation"
NB_NAME = "AVIATION_TEMPORAL_DEMO"
NB_MAIN = "aviation_temporal_demo.ipynb"
COMPUTE_POOL = "SYSTEM_COMPUTE_POOL_CPU"
PYPI_INTEGRATION = "PYPI_ACCESS"

#: Everything that has to sit beside the notebook on the stage. The ontology artifact is the
#: standalone flat module rather than the aviation_model package, because a package of relative
#: imports does not survive being flattened onto a stage folder.
SOURCES = (
    HERE / NB_MAIN,
    HERE / "aviation_viz.py",
    ROOT / "rai_code" / "manual" / "aviation_temporal.py",
    ROOT / "rai_code" / "queries" / "uc1.py",
    ROOT / "rai_code" / "queries" / "uc2.py",
    ROOT / "rai_code" / "queries" / "rotation.py",
    ROOT / "build" / "design" / "ontology_inventory.json",
)


def run(args: list[str], *, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(args[:4])} ...", flush=True)
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def sql(statement: str, *, timeout: int = 900) -> str:
    out = run(
        [SNOW, "sql", "-c", CONN, "--role", ROLE, "-q", statement, "--format", "json"],
        timeout=timeout,
    )
    if out.returncode != 0:
        raise RuntimeError(f"{statement[:90]}...\n{out.stdout}\n{out.stderr}")
    return out.stdout


def build() -> None:
    import build_notebook  # sibling module on sys.path, only needed here

    build_notebook.main()


def stage() -> None:
    missing = [str(p) for p in SOURCES if not p.is_file()]
    if missing:
        raise SystemExit(f"missing source files: {missing}")

    sql(
        f"CREATE SCHEMA IF NOT EXISTS {DB}.{NB_SCHEMA}; "
        f"CREATE STAGE IF NOT EXISTS {DB}.{NB_SCHEMA}.{NB_STAGE} "
        f"DIRECTORY = (ENABLE = TRUE) ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');"
    )
    # AUTO_COMPRESS=FALSE because Snowsight reads the .ipynb and the .py files directly.
    puts = ";\n".join(
        f"PUT file://{p.absolute()} @{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}/ "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        for p in SOURCES
    )
    sql(puts + ";")
    print(f"  staged {len(SOURCES)} files to @{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}/")


def create() -> None:
    sql(
        f"CREATE OR REPLACE NOTEBOOK {DB}.{NB_SCHEMA}.{NB_NAME} "
        f"FROM '@{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}' "
        f"MAIN_FILE = '{NB_MAIN}' "
        f"QUERY_WAREHOUSE = {WAREHOUSE} "
        f"RUNTIME_NAME = 'SYSTEM$BASIC_RUNTIME' "
        f"COMPUTE_POOL = '{COMPUTE_POOL}' "
        f"IDLE_AUTO_SHUTDOWN_TIME_SECONDS = 3600 "
        f"EXTERNAL_ACCESS_INTEGRATIONS = ({PYPI_INTEGRATION}) "
        f"COMMENT = 'Aviation temporal demo - ontology graph plus all nine questions.';"
    )
    sql(f"ALTER NOTEBOOK {DB}.{NB_SCHEMA}.{NB_NAME} ADD LIVE VERSION FROM LAST;")
    print(f"  notebook {DB}.{NB_SCHEMA}.{NB_NAME} created")


def execute() -> int:
    print(f"  executing {DB}.{NB_SCHEMA}.{NB_NAME} headless (this takes ~10-15 minutes)")
    started = time.time()
    out = run(
        [SNOW, "notebook", "execute", f"{DB}.{NB_SCHEMA}.{NB_NAME}", "-c", CONN, "--role", ROLE],
        timeout=3600,
    )
    elapsed = time.time() - started
    print(out.stdout.strip())
    if out.stderr.strip():
        print(out.stderr.strip(), file=sys.stderr)
    print(f"  exit {out.returncode} after {elapsed / 60:.1f} min")
    return out.returncode


def url() -> None:
    out = run([SNOW, "notebook", "get-url", f"{DB}.{NB_SCHEMA}.{NB_NAME}", "-c", CONN], timeout=60)
    print(out.stdout.strip() or f"snow://notebook/{DB}.{NB_SCHEMA}.{NB_NAME}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--execute", action="store_true", help="run the notebook headless afterwards")
    p.add_argument("--url", action="store_true", help="print the Snowsight URL and exit")
    p.add_argument("--skip-build", action="store_true", help="stage the existing .ipynb as is")
    args = p.parse_args()

    if args.url:
        url()
        return 0

    sys.path.insert(0, str(HERE))
    if not args.skip_build:
        build()
    stage()
    create()
    url()
    return execute() if args.execute else 0


if __name__ == "__main__":
    raise SystemExit(main())
