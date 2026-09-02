"""config.py - one ``_build_config()`` that works locally and inside Snowflake.

Two runtimes, one function:

* **Local Python.** ``create_config(...)`` merges the programmatic keys over the
  auto-discovered ``~/.snowflake/connections.toml`` profile. PROBE-01 confirmed the merge
  works without passing ``connections`` explicitly, even though the docstring implies it is
  required.
* **Snowsight / Workspace / stored procedure.** There is no discoverable ``raiconfig.yaml``,
  so ``ConfigFromActiveSession`` is used when a Snowpark session exists.

Both branches set the same two things, and both matter:

* ``model.implicit_properties = False`` (strict mode). The field defaults to ``True``, so it
  has to be set explicitly. Strict mode does *not* protect a ``model.Table()`` from a column
  typo (PROBE U-01) - ``sources.py``'s explicit ``schema=`` dicts do that - but it does stop
  an undeclared Concept property from being invented silently.
* ``reasoners.logic.name = "aviation_temporal_logic_s"``. Pinning the named engine is the
  difference between a 2.5-6s warm query and a 631s cold start (PROBE U-12). Note the ``_s``
  suffix: SDK 1.20.1 refuses ``HIGHMEM_X64_XS`` for Logic reasoners, so the locked ``_xs``
  name in BRIEF.md does not exist and must not be used.
"""

from __future__ import annotations

from typing import Any

from .constants import LOGIC_REASONER


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
