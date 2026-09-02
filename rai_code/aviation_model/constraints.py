"""constraints.py - the multiplicity gates, and one deliberate absence.

**Read this before believing anything in this file is enforced.**

PROBE U-04 ran a deliberately violated ``require(unique(...))`` against the live engine, with
and without ``reasoners.logic.emit_constraints: True``. In both configurations the require
returned normally, the following query returned normally, and the violating data was still
there. **``require(unique(...))`` is a silent no-op in SDK 1.20.1.** The corroborating source is
``backends/legacy_lqp/rewrite/annotate_constraints.py``: by default all constraints are
discharged and removed from the IR in a later pass, and even with the flag on
``_should_declare_constraint`` additionally requires a non-structural functional dependency, so
a structural FD is never declared as a runtime constraint.

The calls below are therefore kept as **documentation only**. They put the multiplicity gate
from ``SOURCE_CONTRACT.md`` into the model where a reviewer sees it, next to the one that is
deliberately absent. They must not be presented to anyone as live checks.

The real enforcement is two mechanisms, both of which do work:

1. **``Property`` itself.** The compiler-enforced functional dependency on every ``Property``
   raises ``FDError: Found non-unique values`` naming the offending relation and printing the
   two conflicting hashes. It fires at the **first evaluation** of the relation - measured at
   13-19 seconds of engine work - not at define time. The design brief said "define time"; that
   is wrong and saying it on stage would be a factual error the audience can check on screen.
2. **Zero-count assertion queries** in ``tests/test_model.py`` and in the Phase 8 gate, for
   every claim a ``Property`` cannot express: the sentinel-leak guard, the end-event
   disagreement, the cabin derivation, the physical-service re-derivation, and the G-01..G-06
   functional-dependency probes.
"""

from relationalai.semantics.std.constraints import unique

from .core_flight import AircraftFlight, ExactFulfillment, PassengerFlight  # noqa: F401
from .core_schedule import Route, RouteState  # noqa: F401
from .model import model

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
