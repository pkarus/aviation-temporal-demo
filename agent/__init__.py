"""agent - the Snowflake Intelligence (Cortex) access path for the aviation temporal demo.

Two modules:

* :mod:`agent.queries` - the curated ``QueryCatalog``. One catalog entry per golden question
  plus two compact summary entries and one scope statement. Nothing here computes an answer;
  every entry delegates to the already-verified query modules under ``rai_code/queries``.
* :mod:`agent.deploy` - the ``deploy`` / ``update`` / ``status`` / ``chat`` / ``debug`` CLI.

Run every command from the repository root so ``discover_imports()`` resolves the model and
query packages relative to it::

    .venv/bin/python -m agent.deploy status
"""
