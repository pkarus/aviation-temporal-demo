"""model.py - the single ``Model`` instance.

Kept in its own module so that ``sources.py`` and every ``core_*`` / ``computed_*`` module can
import it without a circular import, and so there is exactly one ``Model`` per process. The
free ``distinct(...)`` raises ``[Ambiguous model]`` the moment a second ``Model`` exists in the
same interpreter (PROBE N-02), so a second instance is never created here.
"""

from relationalai.semantics import Model

from .config import _build_config
from .constants import MODEL_NAME

model = Model(MODEL_NAME, config=_build_config())
