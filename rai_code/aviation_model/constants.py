"""constants.py - sentinels, tokens and the one database path string.

Nothing here touches the network. ``DB`` is the single string MODEL-02's standalone
generation has to rewrite, which is why every ``model.Table()`` path in ``sources.py``
interpolates it rather than spelling the database out.
"""

import datetime as dt

# --- Snowflake location -----------------------------------------------------------

DB = "PK_AVIATION_TEMPORAL"
SOURCE_SCHEMA = "SOURCE"
MODEL_INPUT_SCHEMA = "MODEL_INPUT"

MODEL_NAME = "aviation_temporal"
LOGIC_REASONER = "aviation_temporal_logic_s"

# --- Interval sentinels -----------------------------------------------------------
#
# BRIEF.md non-negotiable: source ``9999-12-31`` (unknown future) and model ``9999-01-01``
# (open interval) are different facts and never collapse. DATA-04 normalises the source
# sentinel away before RAI sees it, replacing it with NULL plus a companion
# ``*_IS_UNKNOWN_FUTURE`` boolean, so ``SOURCE_UNKNOWN_FUTURE`` must never appear in any
# bound date column. ``computed_aircraft.SentinelLeak`` is the zero-count guard that proves it.

MODEL_OPEN_INTERVAL = dt.date(9999, 1, 1)
SOURCE_UNKNOWN_FUTURE = dt.date(9999, 12, 31)

# --- Dimension discriminators (DV-04 / DV-05 ``dimension`` column) -----------------

DIM_AIRCRAFT_STATE = "aircraft_state"
DIM_AIRCRAFT_TYPE = "aircraft_type"
DIM_ENGINE_TYPE = "engine_type"
DIM_AIRCRAFT_STATUS = "aircraft_status"

DIMENSIONS = (
    DIM_AIRCRAFT_STATE,
    DIM_AIRCRAFT_TYPE,
    DIM_ENGINE_TYPE,
    DIM_AIRCRAFT_STATUS,
)

# --- DV-33 dimension query status -------------------------------------------------
#
# Four mutually exclusive outcomes, in the strict order SOURCE_CONTRACT.md fixes. Two are
# the presence of a covering daily assignment (``OK``, ``UNKNOWN_STATE``) and are carried on
# the row by DATA-04; two are the absence of one (``NO_RECORDED_STATE``, ``OUTSIDE_EXISTENCE``)
# and can only be decided against a date, so they are produced by ``temporal.dv33_branches``.

DV33_OK = "OK"
DV33_UNKNOWN_STATE = "UNKNOWN_STATE"
DV33_NO_RECORDED_STATE = "NO_RECORDED_STATE"
DV33_OUTSIDE_EXISTENCE = "OUTSIDE_EXISTENCE"

# --- Carrier roles (DV-29) --------------------------------------------------------

CARRIER_ROLE_MARKETING = "marketing"
CARRIER_ROLE_OPERATING = "operating"
CARRIER_ROLES = (CARRIER_ROLE_MARKETING, CARRIER_ROLE_OPERATING)

# --- Status tokens used by model rules --------------------------------------------
#
# Exact raw AH-09 values. NEO4J_RAI_MAPPING.md forbids trimming or case folding, so these
# are the literal strings and not a normalised form.

STATUS_IN_SERVICE = "In Service"
STATUS_STORAGE = "Storage"

# --- Resolution / physical-service tokens -----------------------------------------

RESOLUTION_EXACT = "EXACT"
PHYSICAL_SERVICE_COUNTED = "COUNTED"
PHYSICAL_SERVICE_UNRESOLVED = "UNRESOLVED_PHYSICAL_SERVICE"

# --- Rotation ---------------------------------------------------------------------

ROTATION_NO_TARGET_TOKEN = "NO_TARGET"

# --- ISO weekday numbering (1 = Monday), paired with the seven SS-14..SS-20 flags ---

WEEKDAY_FLAG_COLUMNS = (
    (1, "is_operating_monday"),
    (2, "is_operating_tuesday"),
    (3, "is_operating_wednesday"),
    (4, "is_operating_thursday"),
    (5, "is_operating_friday"),
    (6, "is_operating_saturday"),
    (7, "is_operating_sunday"),
)
