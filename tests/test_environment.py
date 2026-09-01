from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_VERSIONS = {
    "ipykernel": "7.3.0",
    "jupyterlab": "4.6.3",
    "matplotlib": "3.11.1",
    "nbclient": "0.11.0",
    "nbformat": "5.11.1",
    "pandas": "3.0.5",
    "plotly": "7.0.0",
    "pyyaml": "6.0.3",
    "relationalai": "1.20.1",
    "pytest": "9.1.1",
}


def test_runtime_and_direct_dependencies_are_pinned() -> None:
    assert sys.version_info[:2] == (3, 13)
    assert (ROOT / "uv.lock").is_file()

    installed = {
        package: importlib.metadata.version(package) for package in EXPECTED_VERSIONS
    }
    assert installed == EXPECTED_VERSIONS


def test_version_manifest_matches_the_verified_environment() -> None:
    manifest = json.loads((ROOT / "environment" / "version_manifest.json").read_text())

    assert manifest["runtime"]["python"] == "3.13.13"
    assert manifest["relationalai"]["sdk"] == EXPECTED_VERSIONS["relationalai"]
    assert manifest["relationalai"]["optional_graph_on_critical_path"] is False
    assert manifest["snowflake"]["connection"] == "rai"
    assert manifest["snowflake"]["account_locator"] == "AJB85638"
    assert manifest["direct_dependencies"] == EXPECTED_VERSIONS


def test_relationalai_public_runtime_surface_is_available() -> None:
    from relationalai.semantics import Model  # noqa: PLC0415

    assert Model.__name__ == "Model"
    assert hasattr(Model, "Table")


def test_rai_cli_comes_from_the_project_virtual_environment() -> None:
    completed = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "rai"), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "rai 1.20.1"


def test_rai_cli_has_model_deployment_commands() -> None:
    completed = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "rai"), "models", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "deploy" in completed.stdout


@pytest.mark.parametrize(
    "module_name",
    ["IPython", "jupyterlab", "matplotlib", "nbclient", "nbformat", "pandas", "plotly", "yaml"],
)
def test_notebook_test_and_chart_modules_import(module_name: str) -> None:
    __import__(module_name)
