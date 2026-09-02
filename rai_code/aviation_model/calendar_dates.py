"""calendar_dates.py - the ``MonthEnd`` concept behind Q03.

Named ``calendar_dates`` rather than ``calendar`` so it cannot shadow the Python standard
library module of that name for any consumer of this package.

Why a materialized concept rather than a Python range. Q03's whole point is that the
interval-to-calendar inequality join replaces a 120-iteration parameter sweep, and that the same
query works for an irregular calendar. That only holds if the calendar is a *joined dimension*
inside the model. PROBE U-05 separately confirmed ``std.datetime.date.range(freq="M")`` produces
exactly the right 120 month ends, so the notebook keeps it as an independent cross-check - but
the query joins the table, not the range.
"""

from relationalai.semantics import Date

from ._binding import bind_scalars, scalar_properties
from .model import model
from .sources import MI_MONTH_END_CALENDAR, SCHEMA_MI_MONTH_END_CALENDAR

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
