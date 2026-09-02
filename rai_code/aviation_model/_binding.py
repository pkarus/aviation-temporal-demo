"""_binding.py - the two helpers every ``core_*`` module uses to lift a table onto a Concept.

Why helpers rather than 700 hand-written lines. The bound tables carry 748 contracted columns
and ``SOURCE_CONTRACT.md`` requires every modelled field to trace to a documented source
column. Writing each ``Property`` by hand would be 700 chances to mistype a column name, and
PROBE U-01 proved a mistyped column binds *silently* as an ``Any``-typed relation. Driving the
declarations off ``sources.py``'s explicit ``schema=`` dict makes the typo structurally
impossible: the only column names in the system come from ``INFORMATION_SCHEMA``.

Two live findings shape the implementation.

* **Batched ``define()`` preserves sparse facts.** ``ONTOLOGY_DESIGN.md`` R2 warns that all
  columns passed to ``.new()`` in one call are required, so a null drops the row. That is true
  of ``.new()`` and is why identity is minted separately. It is *not* true of several
  ``entity.prop(column)`` statements batched into one ``define()``: measured live against
  ``MODEL_INPUT.AIRCRAFT_ELIGIBLE`` (999 rows, ``AIRCRAFT_END_OF_LIFE_DATE`` non-null on
  exactly one), the batched and the one-define-per-column forms both returned
  ``rows=999 eol_nn=1``. Absence of a value stays absence of a fact, which is P0-02.8.
* **One ``define()`` call site per concept.** PyRel warns after 50 ``define()`` calls from the
  same bytecode offset. Batching keeps every concept to a single call from
  ``bind_scalars``, so the whole model makes roughly forty rule-emitting calls in total.

Identity properties are never re-declared here: ``identify_by`` creates them, and declaring a
second ``Property`` for the same name is a duplicate. Every caller passes those column names in
``exclude``.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .model import model


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
