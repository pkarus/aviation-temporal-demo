"""_gen_standalone.py - MODEL-02: generate ``rai_code/manual/aviation_temporal.py``.

The standalone Snowsight/Workspace artifact is **generated** from this package, never
hand-maintained in parallel. Two hand-written copies of a 44-concept ontology diverge, and the
divergence shows up as a notebook that answers differently from the local queries - which is
precisely the failure the "one reusable semantic model" claim cannot survive.

What the generator does:

* concatenates the package modules in dependency order (Python module-level names become plain
  globals, so concatenation preserves semantics exactly);
* drops every relative import - the whole point of the artifact is that there is no package to
  import from;
* hoists and de-duplicates the absolute ``relationalai`` / stdlib imports to the top;
* asserts that no two modules define the same top-level name, so nothing is silently shadowed;
* contains no secrets: credentials come from ``ConfigFromActiveSession`` inside Snowflake and
  from the auto-discovered ``~/.snowflake`` profile locally. No account, user, password, token
  or PAT appears anywhere in the output, and the generator asserts that too.

``tests/test_model.py::test_standalone_file_matches_the_package`` proves the two forms produce
identical ``inspect.schema`` inventories and identical smoke-query results, in separate
processes because two ``Model`` objects in one interpreter break the free ``distinct(...)``.

Regenerate with::

    .venv/bin/python -m aviation_model._gen_standalone      # with rai_code on sys.path
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TARGET = PACKAGE_DIR.parent / "manual" / "aviation_temporal.py"

# Dependency order. ``constants`` -> ``config`` -> ``model`` first because every later module
# needs the single ``Model`` instance; ``core_reference`` before the modules whose reading
# f-strings interpolate ``Airport`` and ``Airline``; ``core_schedule`` before ``core_flight``
# because ``PassengerFlight`` links to ``Schedule``.
MODULE_ORDER = [
    "constants",
    "config",
    "model",
    "_binding",
    "sources",
    "core_reference",
    "core_aircraft",
    "calendar_dates",
    "core_schedule",
    "core_flight",
    "temporal",
    "computed_aircraft",
    "computed_schedule",
    "computed_rotation",
    "constraints",
    "inventory",
]

_SECRET_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bpassword\b",
        r"\bprivate_key\b",
        r"\bprogrammatic[_ ]access[_ ]token\b",
        r"\bpat\s*=",
        r"\bsecret\b",
        r"\baccount\s*=\s*['\"]",
        r"\buser\s*=\s*['\"]",
        r"AJB85638",
        r"NDSOEBE",
    )
]

_HEADER = '''"""aviation_temporal.py - the standalone RelationalAI ontology for the aviation temporal demo.

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

'''


def _module_source(name: str) -> tuple[list[str], list[str], set[str]]:
    """Return (import lines, body lines, top-level names) for one package module."""
    path = PACKAGE_DIR / f"{name}.py"
    text = path.read_text()
    tree = ast.parse(text)
    lines = text.splitlines()

    drop_ranges: list[tuple[int, int]] = []
    imports: list[str] = []
    names: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
            drop_ranges.append((node.lineno, node.end_lineno or node.lineno))
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            drop_ranges.append((node.lineno, node.end_lineno or node.lineno))
            imports.append("\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)]))
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and node is tree.body[0]:
            # the module docstring: keep it, demoted to a comment block
            drop_ranges.append((node.lineno, node.end_lineno or node.lineno))
            continue
        for target in _assigned_names(node):
            names.add(target)

    dropped = set()
    for start, end in drop_ranges:
        dropped.update(range(start, end + 1))

    body = [line for i, line in enumerate(lines, start=1) if i not in dropped]
    return imports, body, names


def _assigned_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        out = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                out.append(target.id)
        return out
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _module_banner(name: str) -> list[str]:
    path = PACKAGE_DIR / f"{name}.py"
    tree = ast.parse(path.read_text())
    doc = ast.get_docstring(tree) or ""
    rule = "# " + "=" * 96
    out = [rule, f"# {name}.py", rule]
    for line in doc.splitlines():
        out.append(("# " + line).rstrip())
    out.append("")
    return out


def _merge_imports(statements: list[str]) -> str:
    """Collapse the modules' import lines into one readable, de-duplicated block.

    Sixteen modules each importing three or four names from ``relationalai.semantics`` produces
    sixteen near-identical lines. Merging them per source module keeps the head of the generated
    file legible, which matters because this file is the artifact a customer opens in Snowsight.
    """
    future: list[str] = []
    plain: set[str] = set()
    aliased: set[tuple[str, str]] = set()
    from_names: dict[str, set[str]] = {}

    for statement in statements:
        node = ast.parse(statement).body[0]
        if isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                future.extend(alias.name for alias in node.names)
                continue
            bucket = from_names.setdefault(node.module or "", set())
            for alias in node.names:
                bucket.add(alias.name if alias.asname is None else f"{alias.name} as {alias.asname}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliased.add((alias.name, alias.asname))
                else:
                    plain.add(alias.name)

    lines: list[str] = []
    if future:
        lines.append("from __future__ import " + ", ".join(sorted(set(future))))
        lines.append("")
    for name in sorted(plain):
        lines.append(f"import {name}")
    for name, asname in sorted(aliased):
        lines.append(f"import {name} as {asname}")
    stdlib = sorted(m for m in from_names if "relationalai" not in m)
    rai = sorted(m for m in from_names if "relationalai" in m)
    if stdlib:
        lines.append("")
    for module in stdlib:
        lines.append(f"from {module} import " + ", ".join(sorted(from_names[module])))
    if rai:
        lines.append("")
    for module in rai:
        lines.append(f"from {module} import " + ", ".join(sorted(from_names[module])))
    return "\n".join(lines).strip() + "\n"


def render() -> str:
    all_imports: list[str] = []
    chunks: list[str] = []
    seen_names: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []

    for name in MODULE_ORDER:
        imports, body, names = _module_source(name)
        for statement in imports:
            if statement not in all_imports:
                all_imports.append(statement)
        for declared in sorted(names):
            if declared in seen_names and seen_names[declared] != name:
                collisions.append((declared, seen_names[declared], name))
            seen_names[declared] = name
        chunks.append("\n".join(_module_banner(name) + body).rstrip() + "\n")

    if collisions:
        raise AssertionError(
            "top-level name collisions between modules would silently shadow a definition: "
            f"{collisions}"
        )

    import_block = _merge_imports(all_imports)

    text = _HEADER + import_block + "\n\n" + "\n\n".join(chunks)

    offenders = [p.pattern for p in _SECRET_PATTERNS if p.search(text)]
    if offenders:
        raise AssertionError(f"generated standalone file matches secret patterns: {offenders}")
    return text


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    text = render()
    TARGET.write_text(text)
    print(f"wrote {TARGET} - {len(text.splitlines())} lines from {len(MODULE_ORDER)} modules")


if __name__ == "__main__":  # pragma: no cover - operational entry point
    main()
