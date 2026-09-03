"""aviation_viz.py - the figure layer for the aviation temporal Snowsight notebook.

Staged next to ``aviation_temporal.py`` and the three query modules, so the notebook cells
stay short enough to read from the back of a room. Nothing here talks to Snowflake; every
function takes a DataFrame that a query module already returned and gives back a
``plotly.graph_objects.Figure``.

Colour is not decoration here, it is an encoding, and every palette below is the validated
default from the data-viz method rather than a hand-picked hex:

* Four **categorical** slots carry the ontology's four domains. Four is not an arbitrary cut.
  A node-link diagram puts every pair of colours on screen at once, and under the all-pairs
  test only a four-slot subset of the eight-slot default palette clears the colour-vision-
  deficiency and normal-vision separation floors in both light and dark mode. The passing
  subset is yellow / magenta / green / violet, which is what ``DOMAIN_COLORS`` uses.
* One **sequential** blue ramp carries edge weight. Blue is deliberately absent from the node
  palette so a heavy edge can never be mistaken for a domain.
* The reserved **status** palette carries the DV-33 dimension states in Q01 and the rotation
  link outcomes in Q08, because those are states rather than series. Status colour never
  travels alone: every status mark in this file also carries its own text label.
* A **diverging** blue/red pair with a neutral gray midpoint carries Q06's market entries and
  exits, which are the one genuinely signed measure in the demo.

Two slots (yellow at 2.11:1 and magenta at 2.62:1) sit below 3:1 against the light chart
surface. The method's relief rule applies and is discharged the same way twice over: every
node is directly labelled, and :func:`ontology_table` gives the same information as a table.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ------------------------------------------------------------------------------- palette

SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# The eight-slot categorical default, in its validated order.
CAT = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

# Sequential blue, 100 -> 700.
SEQ_BLUE = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
    "#184f95", "#104281", "#0d366b",
]

# Reserved status palette. Never reused as a series colour.
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

# Diverging pair with a neutral midpoint.
DIV_POS = "#2a78d6"
DIV_NEG = "#d03b3b"
DIV_MID = "#f0efec"


def _px(colors: Sequence[str], t: float) -> str:
    """Sample a discrete ramp at ``t`` in [0, 1]."""
    if not colors:
        return MUTED
    t = 0.0 if not math.isfinite(t) else min(max(t, 0.0), 1.0)
    return colors[round(t * (len(colors) - 1))]


def _ms(delta: pd.Series) -> np.ndarray:
    """A duration as milliseconds on a date axis.

    A bar whose base is a timestamp needs its length in the axis's own units, and plotly's
    date axis counts milliseconds. Handing it a raw ``timedelta64`` works in some renderers
    and fails to serialise in others, Snowsight's included, so the conversion is explicit.
    """
    return delta.dt.total_seconds().to_numpy(dtype=float) * 1000.0


def _n(value: Any, fmt: str = ",.0f", missing: str = "-") -> str:
    """A scalar number as text, with a null rendered rather than raised.

    Snowsight's pandas and a local pandas do not agree about how a SQL NULL arrives in a
    numeric column - one gives ``None``, the other ``NaN`` - and ``int(NaN)`` raises. Every
    label in this file that prints a single number goes through here, so a missing measure
    shows as a dash in the chart instead of taking the whole notebook down.
    """
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return missing
    try:
        return format(float(value), fmt)
    except (TypeError, ValueError):
        return missing


def _d(value: Any, fmt: str = "%Y-%m-%d", missing: str = "open") -> str:
    """A scalar timestamp as text. ``NaT`` renders rather than raising.

    The Q04 case that found this: an open validity interval comes back as the ``9999-01-01``
    sentinel locally and as ``NaT`` from the Snowsight runtime, and ``NaT.strftime`` raises
    ``ValueError: NaTType does not support strftime``.
    """
    if value is None or value is pd.NaT or (isinstance(value, float) and not math.isfinite(value)):
        return missing
    try:
        return value.strftime(fmt)
    except (AttributeError, ValueError):
        return missing


def _hours(delta: Any, missing: str = "") -> str:
    """A duration as hours, with ``NaT`` rendering blank rather than raising."""
    if pd.isna(delta):
        return missing
    return f"{delta.total_seconds() / 3600:.1f} h"


def _layout(fig: go.Figure, title: str, subtitle: str = "", height: int = 460) -> go.Figure:
    """The shared chrome. Sizing stays simple because Snowsight rejects some explicit widths."""
    head = f"<b>{title}</b>"
    if subtitle:
        head += f'<br><span style="font-size:12px;color:{INK_2}">{subtitle}</span>'
    fig.update_layout(
        title={"text": head, "x": 0, "xanchor": "left", "font": {"size": 17, "color": INK}},
        height=height,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT, "size": 12, "color": INK_2},
        margin={"l": 70, "r": 30, "t": 80, "b": 55},
        legend={
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "font": {"size": 11, "color": INK_2},
        },
        hoverlabel={"bgcolor": SURFACE, "bordercolor": AXIS, "font": {"family": FONT, "size": 12}},
    )
    fig.update_xaxes(
        showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False,
        linecolor=AXIS, tickfont={"size": 11, "color": MUTED},
        title_font={"size": 12, "color": INK_2},
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False,
        linecolor=AXIS, tickfont={"size": 11, "color": MUTED},
        title_font={"size": 12, "color": INK_2},
    )
    return fig


# ============================================================================== ontology

#: The four domains, in the order the demo tells them, mapped onto the validated
#: all-pairs-passing categorical subset (slots 4, 5, 6, 7 of the default palette).
DOMAIN_COLORS = {
    "Aircraft and its history": CAT[3],
    "Schedule and market": CAT[4],
    "Flights, rotation and passengers": CAT[5],
    "Reference and code resolution": CAT[6],
}

_DOMAIN_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Reference and code resolution",
        ("Airline", "Airport", "MonthEnd", "CodeResolution", "CodeResolutionCandidate",
         "CodeResolutionCode", "CodeResolutionCodeCandidate"),
    ),
    (
        "Flights, rotation and passengers",
        ("AircraftFlight", "RotationLinkValidation", "PassengerFlight", "PassengerPlannedLeg",
         "PassengerSourceLineage", "PassengerSourceQuarantine", "InvalidPassengerObservation",
         "ExactFulfillment", "FulfillmentCandidate", "FulfillmentGroupMember"),
    ),
    (
        "Schedule and market",
        ("Schedule", "ScheduleObservation", "ScheduleComparison", "ScheduleExactChange",
         "ScheduleAmendmentCandidate", "ScheduleAmendmentGroup", "ScheduleAmendmentGroupMember",
         "ScheduleAmendmentSide", "SnapshotDate", "Route", "RouteState",
         "RouteStateSnapshotLineage"),
    ),
]


def concept_domain(name: str) -> str:
    """Which of the four demo domains a concept belongs to. Aircraft is the default."""
    for domain, members in _DOMAIN_RULES:
        if name in members:
            return domain
    return "Aircraft and its history"


def ontology_graph(inventory: Mapping[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Nodes and weighted edges from ``build/design/ontology_inventory.json``.

    A node is a concept; its weight is how many properties it carries. An edge joins two
    concepts that the ontology actually relates, and its weight is the number of distinct
    declarations that relate them, so the aircraft-to-daily-assignment spine comes out five
    times heavier than a single foreign-key-shaped property.

    Four kinds of declaration contribute an edge, and they are kept apart in ``kind`` so the
    hover can say which:

    ``extends``
        a subtype edge, ``AircraftStatusDailyAssignment extends AircraftDimensionDailyAssignment``.
    ``relationship``
        a named multi-field relationship such as ``Aircraft assigned status ... from ... until ...``.
    ``identity``
        an identifying field typed by another concept, which is what makes a junction concept
        a junction.
    ``property``
        a plain property typed by another concept.
    ``rule``
        a bare relationship - a derived rule with no owning concept, such as
        ``Aircraft is in service on MonthEnd as AircraftType``, which is the rule Q03 reads.
    """
    concepts: Mapping[str, Any] = inventory["concepts"]
    names = set(concepts)

    weights: dict[tuple[str, str], int] = {}
    kinds: dict[tuple[str, str], set[str]] = {}
    readings: dict[tuple[str, str], list[str]] = {}

    def add(a: str, b: str, kind: str, reading: str) -> None:
        if a == b or a not in names or b not in names:
            return
        key = (a, b) if a < b else (b, a)
        weights[key] = weights.get(key, 0) + 1
        kinds.setdefault(key, set()).add(kind)
        if reading and len(readings.setdefault(key, [])) < 4:
            readings[key].append(reading)

    for name, body in concepts.items():
        for parent in body.get("extends", []):
            add(name, parent, "extends", f"{name} extends {parent}")
        for bucket, kind in (
            ("identify_by", "identity"),
            ("properties", "property"),
            ("relationships", "relationship"),
        ):
            for decl in body.get(bucket, []):
                for fld in decl.get("fields", []):
                    add(name, fld["type_name"], kind, decl.get("reading", ""))

    for bare in inventory.get("bare_relationships", []):
        touched = [f["type_name"] for f in bare.get("fields", []) if f["type_name"] in names]
        for i in range(len(touched)):
            for j in range(i + 1, len(touched)):
                add(touched[i], touched[j], "rule", bare.get("reading", ""))

    degree: dict[str, int] = {n: 0 for n in names}
    strength: dict[str, int] = {n: 0 for n in names}
    for (a, b), w in weights.items():
        degree[a] += 1
        degree[b] += 1
        strength[a] += w
        strength[b] += w

    nodes = pd.DataFrame(
        [
            {
                "concept": n,
                "domain": concept_domain(n),
                "properties": len(concepts[n].get("properties", [])),
                "degree": degree[n],
                "strength": strength[n],
            }
            for n in sorted(names)
        ]
    )
    edges = pd.DataFrame(
        [
            {
                "source": a,
                "target": b,
                "weight": w,
                "kind": "+".join(sorted(kinds[(a, b)])),
                "readings": readings.get((a, b), []),
            }
            for (a, b), w in sorted(weights.items())
        ]
    )
    return nodes, edges


def _spring_layout(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    *,
    iterations: int = 600,
    seed: int = 20260903,
    aspect: float = 1.7,
) -> np.ndarray:
    """A small deterministic force-directed layout. No networkx, no scipy, no surprises.

    Two phases, both seeded, so the picture the audience sees is the picture that was
    rehearsed. Phase one is Fruchterman-Reingold: inverse-square repulsion between every pair
    of the 46 concepts, ``d^2/k`` attraction along each edge scaled by the square root of that
    edge's weight so the aircraft spine pulls tighter than a lone property, and a weak spring
    toward the domain anchor so the four demo domains land in four legible regions instead of
    interleaving. Phase two is pure collision relaxation against each node's drawn radius plus
    the width of its label, which is what stops 46 captions from piling into an unreadable
    smear the way a bare force layout does.
    """
    names = list(nodes["concept"])
    index = {n: i for i, n in enumerate(names)}
    n = len(names)
    rng = np.random.default_rng(seed)

    domains = list(DOMAIN_COLORS)
    present = [d for d in domains if d in set(nodes["domain"])]
    anchors = {
        d: np.array(
            [
                0.62 * aspect * math.cos(2 * math.pi * i / len(present) + math.pi / 4),
                0.62 * math.sin(2 * math.pi * i / len(present) + math.pi / 4),
            ]
        )
        for i, d in enumerate(present)
    }
    home = np.array([anchors[d] for d in nodes["domain"]])
    pos = home + rng.normal(0.0, 0.22, size=(n, 2))

    src = np.array([index[s] for s in edges["source"]], dtype=int)
    dst = np.array([index[t] for t in edges["target"]], dtype=int)
    ew = np.sqrt(edges["weight"].to_numpy(dtype=float))

    k = 1.05 * math.sqrt(4.0 / n)
    t0, t1 = 0.14, 0.002
    for step in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]
        dist2 = np.maximum((delta**2).sum(axis=-1), 1e-6)
        rep = (k * k / dist2)[:, :, None] * delta
        np.einsum("iij->ij", rep)[...] = 0.0
        force = rep.sum(axis=1)

        d_edge = pos[src] - pos[dst]
        n_edge = np.maximum(np.linalg.norm(d_edge, axis=-1), 1e-4)
        pull = ((n_edge / k) * ew)[:, None] * d_edge
        np.add.at(force, src, -pull)
        np.add.at(force, dst, pull)

        force += 0.02 * (home - pos)

        mag = np.maximum(np.linalg.norm(force, axis=-1), 1e-9)
        temperature = t0 + (t1 - t0) * (step / max(iterations - 1, 1))
        pos = pos + (force / mag[:, None]) * np.minimum(mag, temperature)[:, None]

    pos = pos - pos.mean(axis=0)
    pos[:, 0] /= max(np.abs(pos[:, 0]).max(), 1e-6) / aspect
    pos[:, 1] /= max(np.abs(pos[:, 1]).max(), 1e-6)

    # Phase two: separate the drawn boxes, not the idealised points. Each node occupies a
    # rectangle as wide as the wider of its marker and its caption and as tall as the marker
    # plus the caption sitting under it; overlapping pairs are pushed apart along whichever
    # axis they overlap least, which is what keeps 46 captions legible.
    props = nodes["properties"].to_numpy(dtype=float)
    radius = 0.026 + 0.036 * np.sqrt(props / max(props.max(), 1.0))
    half_label = np.array([0.0092 * len(c) for c in names])
    rx = np.maximum(radius * aspect, half_label)
    ry = radius + 0.040
    need_x = rx[:, None] + rx[None, :]
    need_y = ry[:, None] + ry[None, :]
    for _ in range(400):
        dx = pos[:, 0][:, None] - pos[:, 0][None, :]
        dy = pos[:, 1][:, None] - pos[:, 1][None, :]
        pen_x = need_x - np.abs(dx)
        pen_y = need_y - np.abs(dy)
        hit = (pen_x > 0) & (pen_y > 0)
        np.fill_diagonal(hit, False)
        if not hit.any():
            break
        # Overlapping in y by less than in x means the cheaper escape is vertical.
        split_y = (pen_y / need_y) < (pen_x / need_x)
        sx = np.where(dx >= 0, 1.0, -1.0)
        sy = np.where(dy >= 0, 1.0, -1.0)
        push_x = np.where(hit & ~split_y, sx * pen_x * 0.5, 0.0).sum(axis=1)
        push_y = np.where(hit & split_y, sy * pen_y * 0.5, 0.0).sum(axis=1)
        pos = pos + np.stack([push_x, push_y], axis=-1) * 0.35

    pos = pos - (pos.max(axis=0) + pos.min(axis=0)) / 2
    pos[:, 0] /= max(np.abs(pos[:, 0]).max(), 1e-6) / aspect
    pos[:, 1] /= max(np.abs(pos[:, 1]).max(), 1e-6)
    return pos


_EDGE_BANDS = [(1, 1), (2, 2), (3, 3), (4, 5), (6, 99)]


def fig_ontology(
    inventory: Mapping[str, Any],
    *,
    height: int = 760,
    label_all: bool = True,
) -> go.Figure:
    """The opening beat: the ontology drawn as the graph it is.

    Node area grows with the number of properties a concept carries, from the two bare
    marker concepts (``Schedule``, ``AircraftStatus``, which exist to be pointed at) up to
    ``RouteState`` at 75. Node colour is the demo domain. Edge width and edge colour both
    grow with edge weight along one sequential blue ramp, drawn back to front so the heavy
    structural spine sits on top of the thin property web instead of under it.
    """
    nodes, edges = ontology_graph(inventory)
    pos = _spring_layout(nodes, edges)
    nodes = nodes.assign(x=pos[:, 0], y=pos[:, 1])
    xy = {c: (x, y) for c, x, y in zip(nodes["concept"], nodes["x"], nodes["y"])}

    fig = go.Figure()
    wmax = float(edges["weight"].max())

    for lo, hi in _EDGE_BANDS:
        band = edges[(edges["weight"] >= lo) & (edges["weight"] <= hi)]
        if band.empty:
            continue
        ex: list[float | None] = []
        ey: list[float | None] = []
        hx: list[float] = []
        hy: list[float] = []
        htext: list[str] = []
        for row in band.itertuples():
            (x0, y0), (x1, y1) = xy[row.source], xy[row.target]
            ex += [x0, x1, None]
            ey += [y0, y1, None]
            hx.append((x0 + x1) / 2)
            hy.append((y0 + y1) / 2)
            detail = "<br>".join(f"&nbsp;&nbsp;{r}" for r in row.readings)
            htext.append(
                f"<b>{row.source} - {row.target}</b><br>weight {row.weight}"
                f" · {row.kind}<br>{detail}"
            )
        mid = (lo + min(hi, wmax)) / 2
        # The ramp starts at step 350 rather than 100: a weight-1 edge is still a real
        # relationship and has to be visible, it just must not out-shout the spine.
        t = 0.30 + 0.70 * (mid - 1) / max(wmax - 1, 1)
        fig.add_trace(
            go.Scatter(
                x=ex, y=ey, mode="lines", hoverinfo="skip", showlegend=False,
                line={"width": 0.9 + 1.35 * mid, "color": _px(SEQ_BLUE, t)},
                opacity=0.9,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=hx, y=hy, mode="markers", hoverinfo="text", hovertext=htext,
                showlegend=False, marker={"size": 9, "color": "rgba(0,0,0,0)"},
            )
        )

    pmax = float(max(nodes["properties"].max(), 1))
    for domain, color in DOMAIN_COLORS.items():
        grp = nodes[nodes["domain"] == domain]
        if grp.empty:
            continue
        size = 13 + 32 * np.sqrt(grp["properties"].to_numpy(dtype=float) / pmax)
        fig.add_trace(
            go.Scatter(
                x=grp["x"], y=grp["y"],
                mode="markers+text" if label_all else "markers",
                name=f"{domain} ({len(grp)})",
                text=grp["concept"],
                textposition="bottom center",
                textfont={"size": 9, "color": INK_2, "family": FONT},
                cliponaxis=False,
                marker={
                    "size": size,
                    "color": color,
                    "line": {"width": 2, "color": SURFACE},
                    "opacity": 0.95,
                },
                customdata=np.stack(
                    [grp["properties"], grp["degree"], grp["strength"]], axis=-1
                ),
                hovertemplate=(
                    "<b>%{text}</b><br>" + domain
                    + "<br>%{customdata[0]} properties"
                    + "<br>%{customdata[1]} neighbours · edge weight %{customdata[2]}"
                    + "<extra></extra>"
                ),
            )
        )

    subtitle = (
        f"{len(nodes)} concepts · {len(edges)} weighted relationships · "
        f"{int(inventory.get('property_count', nodes['properties'].sum()))} properties. "
        "Node area is property count, node colour is demo domain, "
        "edge width and colour are relationship weight."
    )
    _layout(fig, "The aviation temporal ontology", subtitle, height=height)
    fig.update_layout(
        legend={"orientation": "h", "y": -0.04, "x": 0, "font": {"size": 11, "color": INK_2}},
        margin={"l": 20, "r": 20, "t": 84, "b": 60},
    )
    fig.update_xaxes(visible=False, showgrid=False, range=[-2.0, 2.0])
    fig.update_yaxes(visible=False, showgrid=False, range=[-1.16, 1.10])
    return fig


def ontology_table(inventory: Mapping[str, Any], top: int = 15) -> pd.DataFrame:
    """The table view that discharges the relief rule for the two low-contrast node slots."""
    nodes, _ = ontology_graph(inventory)
    return (
        nodes.sort_values(["strength", "properties"], ascending=False)
        .head(top)
        .reset_index(drop=True)
    )


# ==================================================================================== Q01

#: DV-33 dimension states are states, not series, so they wear the reserved status palette.
#: Every cell also carries its state as text, so colour never has to carry it alone.
DV33_COLORS = {
    "OK": STATUS["good"],
    "UNKNOWN_STATE": STATUS["warning"],
    "NO_RECORDED_STATE": STATUS["serious"],
    "OUTSIDE_EXISTENCE": STATUS["critical"],
}
DV33_ORDER = ["OK", "UNKNOWN_STATE", "NO_RECORDED_STATE", "OUTSIDE_EXISTENCE"]

_Q01_DIMS = [
    ("aircraft_state_status", "aircraft state"),
    ("aircraft_type_status", "aircraft type"),
    ("engine_type_status", "engine type"),
    ("aircraft_status_status", "lifecycle status"),
]


def fig_q01(cases: Sequence[tuple[str, pd.DataFrame]]) -> go.Figure:
    """Q01 as a state matrix: one row per as-of question, one column per dimension stream.

    The chart exists to make the four absence cases visibly different from each other and
    from a hit. A single aircraft-at-an-instant row that collapsed them would be one green
    strip; here ``NO_RECORDED_STATE`` (asked before the aircraft existed),
    ``UNKNOWN_STATE`` (a genuine hole inside the recorded history), ``OUTSIDE_EXISTENCE``
    (asked after end of life) and ``OK`` are four distinct marks, and the mixed row is the
    one that proves the four streams are resolved independently.
    """
    labels: list[str] = []
    grid: list[list[str]] = []
    for label, df in cases:
        row = df.iloc[0] if len(df) else None
        labels.append(label)
        grid.append(
            [str(row[c]) if row is not None and pd.notna(row[c]) else "-" for c, _ in _Q01_DIMS]
        )

    order = {s: i for i, s in enumerate(DV33_ORDER)}
    z = [[order.get(v, len(DV33_ORDER)) for v in r] for r in grid]
    n = len(DV33_ORDER)
    scale: list[list[Any]] = []
    for i, state in enumerate(DV33_ORDER):
        scale.append([i / n, DV33_COLORS[state]])
        scale.append([(i + 1) / n, DV33_COLORS[state]])

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[d for _, d in _Q01_DIMS],
            y=labels,
            colorscale=scale,
            zmin=0,
            zmax=n,
            showscale=False,
            xgap=3,
            ygap=3,
            text=[[v.replace("_", " ").lower() for v in r] for r in grid],
            texttemplate="%{text}",
            textfont={"size": 10, "color": "#ffffff", "family": FONT},
            hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
        )
    )
    _layout(
        fig,
        "Q01 - one aircraft, one instant, four independent clocks",
        "Each cell is one dimension stream resolved on its own against the same as-of date. "
        "is_complete is true only when all four say OK.",
        height=90 + 52 * len(labels),
    )
    fig.update_xaxes(showgrid=False, side="top")
    fig.update_yaxes(showgrid=False, autorange="reversed")
    fig.update_layout(margin={"l": 210, "r": 30, "t": 110, "b": 30})
    return fig


# ==================================================================================== Q02


def fig_q02(df: pd.DataFrame, aircraft_id: int) -> go.Figure:
    """Q02 as a spell timeline: every ``In Service -> Storage -> In Service`` round trip.

    Bars run from the storage observation to the return observation. A same-day reversion has
    zero width and would vanish as a bar, so it is drawn as a diamond instead - which is the
    whole point of reading the audit stream rather than the daily projection, where those
    same-day spells are collapsed away without an error.
    """
    if df.empty:
        return _empty(f"Q02 - aircraft {aircraft_id} has no storage spells",
                      "No In Service -> Storage -> In Service round trip on the audit stream.")

    d = df.copy()
    d["storage_start_date"] = pd.to_datetime(d["storage_start_date"])
    d["return_date"] = pd.to_datetime(d["return_date"])
    d = d.sort_values("storage_start_date").reset_index(drop=True)
    d["lane"] = [f"spell {i + 1}" for i in range(len(d))]

    fig = go.Figure()
    spans = d[~d["same_day"].astype(bool)]
    if not spans.empty:
        fig.add_trace(
            go.Bar(
                x=_ms(spans["return_date"] - spans["storage_start_date"]),
                base=spans["storage_start_date"],
                y=spans["lane"],
                orientation="h",
                marker={"color": CAT[0], "line": {"width": 2, "color": SURFACE}},
                width=0.5,
                name="storage spell",
                text=[f"{_n(v)} d" for v in spans["storage_days"]],
                textposition="outside",
                textfont={"size": 11, "color": INK_2},
                customdata=np.stack(
                    [
                        spans["storage_start_date"].dt.strftime("%Y-%m-%d"),
                        spans["return_date"].dt.strftime("%Y-%m-%d"),
                        spans["storage_days"],
                        spans["storage_start_sequence"],
                        spans["return_sequence"],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{y}</b><br>stored %{customdata[0]} (seq %{customdata[3]})"
                    "<br>returned %{customdata[1]} (seq %{customdata[4]})"
                    "<br>%{customdata[2]} days<extra></extra>"
                ),
            )
        )
    same = d[d["same_day"].astype(bool)]
    if not same.empty:
        fig.add_trace(
            go.Scatter(
                x=same["storage_start_date"],
                y=same["lane"],
                mode="markers+text",
                marker={
                    "symbol": "diamond", "size": 15, "color": STATUS["warning"],
                    "line": {"width": 2, "color": SURFACE},
                },
                name="same-day reversion (zero days)",
                text=["0 d"] * len(same),
                textposition="middle right",
                textfont={"size": 11, "color": INK_2},
                customdata=np.stack(
                    [same["storage_start_sequence"], same["return_sequence"]], axis=-1
                ),
                hovertemplate=(
                    "<b>%{y}</b><br>%{x|%Y-%m-%d}<br>stored at seq %{customdata[0]}, "
                    "returned at seq %{customdata[1]}, same day<extra></extra>"
                ),
            )
        )

    _layout(
        fig,
        f"Q02 - storage spells for aircraft {aircraft_id}",
        "Derived from the audit stream. The daily projection keeps one observation per "
        "aircraft, dimension and date, so a same-day reversion disappears there silently.",
        height=180 + 52 * len(d),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, title="")
    # Bar lengths are milliseconds against a timestamp base, so the axis type is pinned
    # rather than inferred - plotly reads the numeric lengths first and would guess linear.
    fig.update_xaxes(title="", type="date")
    fig.update_layout(
        bargap=0.45, legend={"orientation": "h", "y": -0.22, "x": 0},
        margin={"l": 90, "r": 70, "t": 90, "b": 70},
    )
    return fig


def fig_q02f(df: pd.DataFrame) -> go.Figure:
    """Q02F as a paired bar: spells per bucket against distinct aircraft per bucket.

    Two series and not one, because they are the built-in check on the aggregate. They differ
    in exactly the buckets where a single aircraft contributed more than one spell; if the
    two bars were equal everywhere the distinct wrapper would have been lost and the query
    would be counting spell tuples while claiming to count aircraft.
    """
    d = df.sort_values("bucket_order")
    label = [b.replace("_", " ").lower() for b in d["duration_bucket"]]
    fig = go.Figure()
    for i, (col, name) in enumerate([("spell_count", "spells"), ("aircraft_count", "distinct aircraft")]):
        fig.add_trace(
            go.Bar(
                y=label, x=d[col], orientation="h", name=name,
                marker={"color": CAT[i], "line": {"width": 2, "color": SURFACE}},
                text=d[col], textposition="outside",
                textfont={"size": 11, "color": INK_2},
                customdata=np.stack([d["minimum_storage_days"], d["maximum_storage_days"]], axis=-1),
                hovertemplate=(
                    "<b>%{y}</b><br>" + name + ": %{x}"
                    "<br>observed range %{customdata[0]}-%{customdata[1]} days<extra></extra>"
                ),
            )
        )
    _layout(
        fig,
        "Q02F - fleet storage-spell duration distribution",
        "One query over the whole fleet, same spell definition as Q02. Where the two bars "
        "differ, one aircraft contributed several spells to that bucket.",
        height=110 + 58 * len(d),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, title="")
    fig.update_xaxes(title="count")
    fig.update_layout(
        barmode="group", bargap=0.3, bargroupgap=0.12,
        legend={"orientation": "h", "y": -0.14, "x": 0},
        margin={"l": 160, "r": 60, "t": 90, "b": 60},
    )
    return fig


# ==================================================================================== Q03


def fig_q03_total(df: pd.DataFrame) -> go.Figure:
    """Q03 rolled up: total in-service aircraft at every month end. One series, so no legend."""
    total = (
        df.assign(month_end=pd.to_datetime(df["month_end"]))
        .groupby("month_end", as_index=False)["in_service_aircraft_count"].sum()
        .sort_values("month_end")
    )
    peak = total.loc[total["in_service_aircraft_count"].idxmax()]
    last = total.iloc[-1]

    fig = go.Figure(
        go.Scatter(
            x=total["month_end"], y=total["in_service_aircraft_count"],
            mode="lines", line={"width": 2, "color": CAT[0], "shape": "spline", "smoothing": 0.4},
            fill="tozeroy", fillcolor="rgba(42,120,214,0.10)",
            hovertemplate="<b>%{x|%b %Y}</b><br>%{y} aircraft in service<extra></extra>",
            name="in service", showlegend=False,
        )
    )
    # One series needs no legend box - the title names it - so both marks are direct-labelled.
    for point, text, pos in ((peak, "peak", "top center"), (last, "end of window", "top left")):
        fig.add_trace(
            go.Scatter(
                x=[point["month_end"]], y=[point["in_service_aircraft_count"]],
                mode="markers+text", showlegend=False, hoverinfo="skip",
                marker={"size": 9, "color": CAT[0], "line": {"width": 2, "color": SURFACE}},
                text=[f"{text} {_n(point['in_service_aircraft_count'])}"],
                textposition=pos, textfont={"size": 11, "color": INK_2},
            )
        )
    _layout(
        fig,
        "Q03 - fleet in service at every month end",
        f"{len(total)} month ends answered by one query. MonthEnd is a joined calendar "
        "dimension and the predicate is a pure inequality, not a parameter sweep.",
        height=380,
    )
    fig.update_yaxes(title="aircraft in service", rangemode="tozero")
    fig.update_xaxes(title="")
    return fig


def fig_q03_heat(df: pd.DataFrame) -> go.Figure:
    """Q03 by exact type: a month-end by type heatmap on one sequential ramp.

    Ten aircraft types is past the eight-slot categorical cap, and stacking ten bands would
    be unreadable anyway. Magnitude on one hue is the honest form, and the retirement wave
    reads straight off it: the older generations fade out along the top while the newer ones
    darken.
    """
    d = df.assign(month_end=pd.to_datetime(df["month_end"]))
    pivot = d.pivot_table(
        index="aircraft_type", columns="month_end",
        values="in_service_aircraft_count", aggfunc="sum",
    )
    first_seen = d.groupby("aircraft_type")["month_end"].min().sort_values()
    pivot = pivot.reindex(first_seen.index)

    fig = go.Figure(
        go.Heatmap(
            z=pivot.to_numpy(),
            x=pivot.columns,
            y=pivot.index,
            colorscale=[[i / (len(SEQ_BLUE) - 1), c] for i, c in enumerate(SEQ_BLUE)],
            hoverongaps=False,
            colorbar={
                "title": {"text": "in service", "font": {"size": 11, "color": INK_2}},
                "thickness": 12, "outlinewidth": 0, "tickfont": {"size": 10, "color": MUTED},
            },
            hovertemplate="<b>%{y}</b><br>%{x|%b %Y}: %{z} in service<extra></extra>",
        )
    )
    _layout(
        fig,
        "Q03 - in-service composition by exact aircraft type",
        f"{len(df)} rows, {pivot.shape[0]} types across {pivot.shape[1]} month ends. "
        "Rows are ordered by first appearance, newest generation at the top.",
        height=120 + 34 * pivot.shape[0],
    )
    fig.update_xaxes(showgrid=False, title="")
    fig.update_yaxes(showgrid=False, title="")
    fig.update_layout(margin={"l": 250, "r": 40, "t": 90, "b": 50})
    return fig


# ==================================================================================== Q04

def fig_q04(cases: Sequence[tuple[str, pd.DataFrame]]) -> go.Figure:
    """Q04 as two lanes per aircraft: the type clock above the engine clock, never aligned.

    The independence is the answer, so the two streams get two lanes and no shared boundary
    is implied. Dotted droplines mark every interval boundary; where a type boundary has no
    engine boundary beneath it, that gap is the fact the question exists to show. Any join of
    the two streams on overlapping validity would return a different number of rows.
    """
    lanes: list[str] = []
    fig = go.Figure()
    dim_color = {"aircraft_type": CAT[0], "engine_type": CAT[1]}
    seen: set[str] = set()
    horizon: list[pd.Timestamp] = []

    for label, df in cases:
        d = df.copy()
        d["valid_from"] = pd.to_datetime(d["valid_from"])
        d["valid_to_raw"] = d["valid_to"]
        d["valid_to"] = pd.to_datetime(d["valid_to"])
        horizon += [t for t in d["valid_from"] if pd.notna(t)]
        horizon += [t for t in d["valid_to"] if pd.notna(t) and t.year < 9000]

    cap = (max(horizon) + pd.Timedelta(days=400)) if horizon else pd.Timestamp("2035-01-01")
    floor = (min(horizon) - pd.Timedelta(days=200)) if horizon else pd.Timestamp("2015-01-01")

    for label, df in cases:
        d = df.copy()
        d["valid_from"] = pd.to_datetime(d["valid_from"])
        d["valid_to"] = pd.to_datetime(d["valid_to"])
        for dim in ("aircraft_type", "engine_type"):
            lane = f"{label}<br>{dim.replace('_', ' ')}"
            lanes.append(lane)
            part = d[d["dimension"] == dim].sort_values("valid_from")
            if part.empty:
                continue
            # Open intervals arrive two ways: the 9999-01-01 model sentinel locally, and a
            # bare NaT from the Snowsight runtime. Both mean the same thing.
            open_ended = part["valid_to"].isna() | (part["valid_to"].dt.year >= 9000)
            end = part["valid_to"].where(~open_ended, cap)
            fig.add_trace(
                go.Bar(
                    x=_ms(end - part["valid_from"]),
                    base=part["valid_from"],
                    y=[lane] * len(part),
                    orientation="h",
                    width=0.52,
                    marker={
                        "color": dim_color[dim],
                        "line": {"width": 2, "color": SURFACE},
                        "pattern": {"shape": ["/" if o else "" for o in open_ended],
                                    "fgcolor": SURFACE, "size": 5, "solidity": 0.22},
                    },
                    name=dim.replace("_", " "),
                    legendgroup=dim,
                    showlegend=dim not in seen,
                    text=part["definition_label"],
                    textposition="inside",
                    insidetextanchor="start",
                    textfont={"size": 10, "color": "#ffffff"},
                    customdata=np.stack(
                        [
                            part["valid_from"].dt.strftime("%Y-%m-%d"),
                            [("open" if o else _d(t))
                             for o, t in zip(open_ended, part["valid_to"])],
                            part["definition_id"],
                            part["definition_label"],
                        ],
                        axis=-1,
                    ),
                    hovertemplate=(
                        "<b>%{customdata[3]}</b> (%{customdata[2]})"
                        "<br>valid %{customdata[0]} until %{customdata[1]}<extra></extra>"
                    ),
                )
            )
            seen.add(dim)
            for boundary in part["valid_from"]:
                fig.add_vline(
                    x=boundary, line={"width": 1, "color": AXIS, "dash": "dot"}, opacity=0.7
                )

    _layout(
        fig,
        "Q04 - the type clock and the engine clock, side by side",
        "One relation with a dimension discriminator, not two relations unioned. The dotted "
        "boundaries do not line up, and hatching marks an interval that is still open.",
        height=140 + 62 * len(lanes),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, title="",
                     categoryorder="array", categoryarray=lanes)
    fig.update_xaxes(title="", range=[floor, cap], type="date")
    fig.update_layout(
        bargap=0.4, legend={"orientation": "h", "y": -0.18, "x": 0},
        margin={"l": 200, "r": 50, "t": 90, "b": 70},
    )
    return fig


# ==================================================================================== Q05

#: Q05's eight event classes, ordered exact layer first then evidence layer, onto the eight
#: validated categorical slots in their validated adjacency order.
Q05_ORDER = [
    "EXACT_KEY_PRESERVING_MODIFICATION",
    "EXACT_ADDITION",
    "EXACT_REMOVAL",
    "CANDIDATE_UNIQUE",
    "AMBIGUOUS_CANDIDATE_GROUP",
    "AMBIGUOUS_GROUP_MEMBER",
    "UNPAIRED_ADDITION",
    "UNPAIRED_REMOVAL",
]
Q05_COLORS = dict(zip(Q05_ORDER, CAT))


def fig_q05(df: pd.DataFrame) -> go.Figure:
    """Q05 stacked by snapshot comparison: eight visibly separate event classes over time.

    The stack order is the layer order. The three ``EXACT_*`` classes at the base are a
    presence-and-content fact set that stands on its own; everything above them is the
    evidence layer, which says which removal-and-addition pairs might be one carrier amending
    one service. A schedule key hashes its effective and discontinue dates, so a carrier
    shifting either date mints a new key and one amendment arrives looking like an unrelated
    removal plus an unrelated addition. The evidence layer is what recovers the pair, and the
    ambiguous classes are where it declines to guess.
    """
    d = df.assign(comparison_date=pd.to_datetime(df["comparison_date"]))
    counts = (
        d.groupby(["comparison_date", "event_class"], as_index=False)
        .size().rename(columns={"size": "events"})
    )
    fig = go.Figure()
    for cls in Q05_ORDER:
        part = counts[counts["event_class"] == cls]
        if part.empty:
            continue
        fig.add_trace(
            go.Bar(
                x=part["comparison_date"], y=part["events"],
                name=cls.replace("_", " ").lower(),
                marker={"color": Q05_COLORS[cls], "line": {"width": 2, "color": SURFACE}},
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>" + cls.lower().replace("_", " ")
                + ": %{y}<extra></extra>",
            )
        )
    total = len(d)
    _layout(
        fig,
        "Q05 - schedule change events by class, snapshot to snapshot",
        f"{total} events across {counts['comparison_date'].nunique()} weekly comparisons. "
        "Exact layer at the base, evidence layer above it.",
        height=520,
    )
    fig.update_yaxes(title="events")
    fig.update_xaxes(title="")
    fig.update_layout(
        barmode="stack", bargap=0.25,
        legend={"orientation": "h", "y": -0.16, "x": 0, "font": {"size": 10},
                "traceorder": "normal"},
        margin={"l": 70, "r": 30, "t": 90, "b": 110},
    )
    return fig


def fig_q05_mix(df: pd.DataFrame) -> go.Figure:
    """Q05 rolled up by class, split by whether the pair had to cross a missing snapshot.

    A gap-crossing pair is the harder case: the two snapshots either side of an ineligible
    one are further apart, so more candidate pairings survive and more of them stay ambiguous.
    """
    d = df.copy()
    d["crosses_snapshot_gap"] = d["crosses_snapshot_gap"].fillna(False).astype(bool)
    counts = (
        d.groupby(["event_class", "crosses_snapshot_gap"], as_index=False)
        .size().rename(columns={"size": "events"})
    )
    present = [c for c in Q05_ORDER if c in set(counts["event_class"])]
    fig = go.Figure()
    for crosses, name, color in (
        (False, "within a contiguous pair of snapshots", CAT[0]),
        (True, "crosses a missing snapshot", CAT[1]),
    ):
        part = counts[counts["crosses_snapshot_gap"] == crosses].set_index("event_class")
        vals = [int(part["events"].get(c, 0)) for c in present]
        fig.add_trace(
            go.Bar(
                y=[c.replace("_", " ").lower() for c in present], x=vals, orientation="h",
                name=name, marker={"color": color, "line": {"width": 2, "color": SURFACE}},
                text=[v or "" for v in vals], textposition="outside",
                textfont={"size": 10, "color": INK_2},
                hovertemplate="<b>%{y}</b><br>" + name + ": %{x}<extra></extra>",
            )
        )
    _layout(
        fig,
        "Q05 - event classes, and which ones had to reach across a missing snapshot",
        "An ineligible snapshot is never substituted, so the comparison simply spans further "
        "and the evidence layer has more candidates to weigh.",
        height=120 + 44 * len(present),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, title="")
    fig.update_xaxes(title="events")
    fig.update_layout(
        barmode="stack", bargap=0.32,
        legend={"orientation": "h", "y": -0.16, "x": 0, "traceorder": "normal"},
        margin={"l": 280, "r": 60, "t": 90, "b": 70},
    )
    return fig


# ==================================================================================== Q06


def fig_q06(cases: Sequence[tuple[str, pd.DataFrame]]) -> go.Figure:
    """Q06 as a signed bar: market entries to the right, exits to the left.

    Entry and exit are opposite polarity on one measure, which is the one place in this demo
    a diverging pair is the right encoding. Only zero-to-positive and positive-to-zero are
    events; a carrier going from one schedule to two is a change but not an entry, and the
    stable positive shadows in the data exist to catch a predicate that says otherwise.
    """
    rows: list[dict[str, Any]] = []
    for label, df in cases:
        for r in df.to_dict("records"):
            rows.append({**r, "case": label})
    if not rows:
        return _empty("Q06 - no market entries or exits",
                      "Both endpoints were eligible and nothing crossed zero.")

    d = pd.DataFrame(rows)
    d["signed"] = np.where(d["change_kind"] == "ENTRY", 1, -1) * (
        d["after_schedule_count"] - d["before_schedule_count"]
    ).abs()
    d["label"] = d["route_id"] + "  " + d["airline_id"]
    d = d.sort_values(["case", "change_kind", "route_id"], ascending=[True, True, True])

    fig = go.Figure()
    for kind, color, name in (("ENTRY", DIV_POS, "entry (0 -> positive)"),
                              ("EXIT", DIV_NEG, "exit (positive -> 0)")):
        part = d[d["change_kind"] == kind]
        if part.empty:
            continue
        fig.add_trace(
            go.Bar(
                y=[f"{c}<br>{l}" for c, l in zip(part["case"], part["label"])],
                x=part["signed"], orientation="h", name=name,
                marker={"color": color, "line": {"width": 2, "color": SURFACE}},
                text=[f"{b} -> {a}" for b, a in
                      zip(part["before_schedule_count"], part["after_schedule_count"])],
                textposition="outside", textfont={"size": 10, "color": INK_2},
                customdata=np.stack([part["airline_id"], part["route_id"], part["carrier_role"]],
                                    axis=-1),
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>%{customdata[0]} (%{customdata[2]})"
                    "<br>" + kind.lower() + ", schedules %{text}<extra></extra>"
                ),
            )
        )
    fig.add_vline(x=0, line={"width": 2, "color": AXIS})
    _layout(
        fig,
        "Q06 - who entered and who left the market in one week",
        "Two exact knowledge endpoints, neither substituted. Marketing and operating are "
        "asked separately because the same flight has two carriers.",
        height=130 + 42 * len(d),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, title="")
    fig.update_xaxes(title="schedules gained (right) or lost (left)", zeroline=False, dtick=1)
    fig.update_layout(
        bargap=0.32, legend={"orientation": "h", "y": -0.13, "x": 0},
        margin={"l": 250, "r": 90, "t": 90, "b": 70},
    )
    return fig


# ==================================================================================== Q07

_CABINS = [
    ("weekly_first_seats", "first"),
    ("weekly_business_seats", "business"),
    ("weekly_premium_economy_seats", "premium economy"),
    ("weekly_economy_excluding_premium_seats", "economy"),
]


def fig_q07_cabin(df: pd.DataFrame, top: int = 14) -> go.Figure:
    """Q07 as a cabin-mix stack: weekly seats per carrier and route, split by cabin.

    Four cabins in the validated adjacency order, stacked densest cabin outward, so the
    adjacent pairs on screen are exactly the pairs the palette order was chosen to separate.

    **Only the rows whose cabin split reconciles are stacked.** ``cabin_quality`` is
    ``UNRECONCILED`` when the four cabin measures do not add up to ``weekly_total_seats`` -
    ``SFO->BOS`` on the enriched parameters comes back with a *negative* economy residual,
    because the source's premium-economy figure exceeds what the total leaves room for. That
    is a real fact about the source, not a defect in the query, and stacking a negative
    segment would draw a bar that lies about it. Those rows get their total in the reserved
    warning colour with the reason spelled out beside them instead.
    """
    d = df[df["result_status"] == "COUNTED"].copy()
    if d.empty:
        return _empty("Q07 - nothing counted under both clocks",
                      "Every row came back unresolved or the window was empty.")
    d["label"] = d["route_id"] + "  " + d["airline_id"]
    d = d.sort_values("weekly_total_seats", ascending=False).head(top)
    d = d.sort_values("weekly_total_seats")
    order = list(d["label"])
    ok = d[d["cabin_quality"] == "RECONCILED"]
    bad = d[d["cabin_quality"] != "RECONCILED"]

    fig = go.Figure()
    for i, (col, name) in enumerate(reversed(_CABINS)):
        vals = ok[col].fillna(0)
        if vals.sum() == 0:
            continue
        fig.add_trace(
            go.Bar(
                y=ok["label"], x=vals, orientation="h", name=name,
                marker={"color": CAT[3 - i], "line": {"width": 2, "color": SURFACE}},
                hovertemplate="<b>%{y}</b><br>" + name + ": %{x:,.0f} weekly seats<extra></extra>",
            )
        )
    if not bad.empty:
        fig.add_trace(
            go.Bar(
                y=bad["label"], x=bad["weekly_total_seats"], orientation="h",
                name=f"cabin split does not reconcile ({len(bad)})",
                marker={
                    "color": STATUS["warning"], "line": {"width": 2, "color": SURFACE},
                    "pattern": {"shape": "/", "fgcolor": SURFACE, "size": 6, "solidity": 0.25},
                },
                hovertemplate=(
                    "<b>%{y}</b><br>%{x:,.0f} weekly seats in total"
                    "<br>the four cabin measures do not sum to it<extra></extra>"
                ),
            )
        )
    fig.add_trace(
        go.Scatter(
            x=d["weekly_total_seats"], y=d["label"], mode="text",
            text=[
                f"  {_n(v)} seats / {_n(f)} flights"
                + ("" if q == "RECONCILED" else "  (unreconciled)")
                for v, f, q in zip(d["weekly_total_seats"], d["weekly_frequency"], d["cabin_quality"])
            ],
            textposition="middle right", textfont={"size": 10, "color": INK_2},
            showlegend=False, hoverinfo="skip",
        )
    )
    _layout(
        fig,
        "Q07 - weekly capacity by cabin, under both clocks at once",
        "Knowledge validity is half-open, the operating window is inclusive at both ends. "
        "Filter on one clock only and the answer is still plausible, well formed and wrong.",
        height=140 + 34 * len(d),
    )
    fig.update_yaxes(showgrid=False, title="", categoryorder="array", categoryarray=order)
    fig.update_xaxes(title="weekly seats", range=[0, float(d["weekly_total_seats"].max()) * 1.5])
    fig.update_layout(
        barmode="stack", bargap=0.3,
        legend={"orientation": "h", "y": -0.12, "x": 0, "traceorder": "normal"},
        margin={"l": 260, "r": 40, "t": 90, "b": 70},
    )
    return fig


def fig_q07_clocks(cases: Sequence[tuple[str, pd.DataFrame]], top: int = 12) -> go.Figure:
    """Q07 asked twice: the same operating date, seen from two different knowledge dates.

    This is the two-clock claim made visible. Nothing about the world changed between the two
    bars for a given route; only what was known about it had. Where the bars differ - and
    especially where one bar is missing entirely - a schedule was published, amended or
    withdrawn in the intervening week, and the routes where that happened are pulled to the
    top so the difference is the first thing read rather than the last thing found.
    """
    frames = []
    for label, df in cases:
        part = df[df["result_status"] == "COUNTED"].copy()
        part["label"] = part["route_id"] + "  " + part["airline_id"]
        part["case"] = label
        frames.append(part[["label", "case", "weekly_total_seats", "weekly_frequency"]])
    if not frames:
        return _empty("Q07 - two clocks", "No counted rows on either knowledge date.")

    d = pd.concat(frames, ignore_index=True)
    wide = d.pivot_table(index="label", columns="case", values="weekly_total_seats", aggfunc="sum")
    names = [label for label, _ in cases]
    for name in names:
        if name not in wide:
            wide[name] = np.nan
    disagrees = wide[names].isna().any(axis=1) | (wide[names].nunique(axis=1, dropna=False) > 1)
    wide = wide.assign(_differs=disagrees, _size=wide[names].max(axis=1))
    order = list(
        wide.sort_values(["_differs", "_size"], ascending=[True, True]).tail(top).index
    )

    fig = go.Figure()
    for i, name in enumerate(names):
        part = wide.reindex(order)
        fig.add_trace(
            go.Bar(
                y=order, x=part[name].fillna(0), orientation="h", name=name,
                marker={"color": CAT[i], "line": {"width": 2, "color": SURFACE}},
                text=["not known yet" if pd.isna(v) else "" for v in part[name]],
                textposition="outside", textfont={"size": 10, "color": INK_2},
                hovertemplate="<b>%{y}</b><br>" + name + ": %{x:,.0f} weekly seats<extra></extra>",
            )
        )
    _layout(
        fig,
        "Q07 - one operating date, two knowledge dates",
        "Same routes, same week of operation. Routes whose answer changed between the two "
        "knowledge dates are at the top; everything below was already fully published.",
        height=150 + 40 * len(order),
    )
    fig.update_xaxes(title="weekly seats", rangemode="tozero")
    fig.update_yaxes(title="", showgrid=False, categoryorder="array", categoryarray=order)
    fig.update_layout(
        barmode="group", bargap=0.3, bargroupgap=0.08,
        legend={"orientation": "h", "y": -0.1, "x": 0},
        margin={"l": 270, "r": 130, "t": 96, "b": 70},
    )
    return fig


# ==================================================================================== Q08

LINK_COLORS = {
    "ACCEPTED": STATUS["good"],
    "EXCLUDED": STATUS["warning"],
    "REJECTED": STATUS["critical"],
}


def fig_q08_rotation(df: pd.DataFrame, aircraft_id: int, day: Any) -> go.Figure:
    """Q08 as the day itself: each accepted leg in the air, with the ground time between.

    The legs are ordered by the validated rotation chain rather than by clock time, and the
    gaps between the bars are real turnaround. A leg only appears here once the link into it
    survived validation, which is why the anomaly chart is a separate picture rather than a
    footnote on this one.
    """
    legs = df[df["row_kind"] == "LEG"].copy()
    if legs.empty:
        return _empty(f"Q08 - no rotation for aircraft {aircraft_id} on {day}",
                      "No accepted legs. The anomaly view below says why.")
    legs["dep"] = pd.to_datetime(legs["actual_departure_utc"])
    legs["arr"] = pd.to_datetime(legs["actual_arrival_utc"])
    legs = legs.sort_values("leg_order")
    legs["lane"] = [
        f"{_n(o)}. {s} - {t}" for o, s, t in
        zip(legs["leg_order"], legs["actual_origin"], legs["actual_destination"])
    ]

    fig = go.Figure(
        go.Bar(
            x=_ms(legs["arr"] - legs["dep"]), base=legs["dep"], y=legs["lane"],
            orientation="h", width=0.55, name="airborne",
            marker={"color": CAT[0], "line": {"width": 2, "color": SURFACE}},
            text=[_hours(a - d) for d, a in zip(legs["dep"], legs["arr"])],
            textposition="inside", insidetextanchor="middle",
            textfont={"size": 10, "color": "#ffffff"},
            customdata=np.stack(
                [
                    legs["flight_id"],
                    legs["dep"].dt.strftime("%H:%M"),
                    legs["arr"].dt.strftime("%H:%M"),
                    legs["as_of_aircraft_type_id"].fillna("-"),
                    legs["as_of_engine_type_id"].fillna("-"),
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{y}</b><br>flight %{customdata[0]}"
                "<br>%{customdata[1]} - %{customdata[2]} UTC"
                "<br>type as of the day: %{customdata[3]} / %{customdata[4]}<extra></extra>"
            ),
        )
    )
    prev = legs.iloc[:-1]
    nxt = legs.iloc[1:]
    for (_, a), (_, b) in zip(prev.iterrows(), nxt.iterrows()):
        gap = b["dep"] - a["arr"]
        if pd.isna(gap):
            continue
        fig.add_annotation(
            x=a["arr"] + gap / 2, y=b["lane"],
            text=f"{gap.total_seconds() / 60:.0f} min on the ground",
            showarrow=False, yshift=20, font={"size": 10, "color": MUTED},
        )
    _layout(
        fig,
        f"Q08 - the actual rotation of aircraft {aircraft_id} on {day}",
        "Every leg here survived link validation. Ground time is what falls out between "
        "an arrival and the next departure.",
        height=170 + 62 * len(legs),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, title="")
    fig.update_xaxes(title="UTC", type="date")
    fig.update_layout(bargap=0.4, showlegend=False,
                      margin={"l": 230, "r": 50, "t": 90, "b": 60})
    return fig


def _arc(x0: float, x1: float, height: float, points: int = 40) -> tuple[list[float], list[float]]:
    """A half-ellipse from ``x0`` to ``x1``, peaking at ``height``. Sign of height picks a side."""
    mid = (x0 + x1) / 2
    span = abs(x1 - x0) / 2 or 0.34
    theta = np.linspace(math.pi, 0.0, points) if x1 >= x0 else np.linspace(0.0, math.pi, points)
    return list(mid + span * np.cos(theta)), list(height * np.sin(np.abs(theta)))


def fig_q08_anomaly_graph(df: pd.DataFrame, aircraft_id: int, day: Any) -> go.Figure:
    """Q08's rejected links drawn as the arcs they are, over the flights of one day.

    Flights sit on the axis in flight-number order. Every attempted link is an arc from the
    flight to its declared successor: **above** the line when the successor comes later,
    **below** when it comes earlier or is the flight itself. That single geometric choice is
    what makes ``SELF_LOOP`` and ``BACKWARD_TIME`` unmistakable rather than two more strings
    in a list - a self loop is a small circle over one flight, and a backward link hangs
    beneath the axis.

    A flight whose link failed with no successor at all - a diversion, a cancellation, a
    missing time - has no arc to draw, so the failure is marked on the flight itself with a
    ring in the reserved status colour and its code written underneath. Colour is doubled by
    the code label everywhere, so nothing depends on hue alone.
    """
    an = df[df["row_kind"] == "ANOMALY"].copy()
    if an.empty:
        return _empty(f"Q08 - no anomalies for aircraft {aircraft_id} on {day}",
                      "Every link in the chain validated cleanly.")

    ids = sorted({int(f) for f in an["flight_id"] if pd.notna(f)}
                 | {int(n) for n in an["next_flight_id"] if pd.notna(n)})
    slot = {f: i for i, f in enumerate(ids)}

    fig = go.Figure()
    linked = an[an["next_flight_id"].notna()]
    seen: set[str] = set()
    spans = [abs(slot[int(r.next_flight_id)] - slot[int(r.flight_id)]) for r in linked.itertuples()]
    widest = max(spans + [1])
    nudge: dict[int, int] = {sp: 0 for sp in spans}
    for row in linked.itertuples():
        src, dst = slot[int(row.flight_id)], slot[int(row.next_flight_id)]
        forward = dst > src
        # Arc height tracks how far the link reaches, which separates the apex labels of
        # arcs that would otherwise all peak at the same place.
        peak = (1.0 if forward else -1.0) * (0.30 + 0.70 * abs(dst - src) / widest)
        ax, ay = _arc(src, dst, peak)
        color = LINK_COLORS.get(row.link_outcome, MUTED)
        fig.add_trace(
            go.Scatter(
                x=ax, y=ay, mode="lines", line={"width": 2.5, "color": color},
                name=f"{row.link_outcome.lower()}",
                legendgroup=row.link_outcome,
                showlegend=row.link_outcome not in seen,
                hoverinfo="text",
                hovertext=(
                    f"<b>{row.anomaly_code}</b><br>{row.link_outcome.lower()}"
                    f"<br>flight {int(row.flight_id)} -> {int(row.next_flight_id)}"
                    f"<br>segment {row.segment_id}"
                ),
            )
        )
        seen.add(row.link_outcome)
        # Equal-span arcs peak at the same height, so their captions are staggered by one
        # line to keep two long codes from printing over each other.
        lift = 13 + 17 * (nudge[abs(dst - src)] % 2)
        nudge[abs(dst - src)] += 1
        fig.add_annotation(
            x=(src + dst) / 2, y=peak,
            text=row.anomaly_code.replace("_", " ").lower(),
            showarrow=False, yshift=lift if forward else -lift,
            font={"size": 10, "color": INK_2},
        )

    stranded = an[an["next_flight_id"].isna()]
    for outcome in ("REJECTED", "EXCLUDED"):
        part = stranded[stranded["link_outcome"] == outcome]
        if part.empty:
            continue
        xs = [slot[int(f)] for f in part["flight_id"]]
        fig.add_trace(
            go.Scatter(
                x=xs, y=[0] * len(xs), mode="markers",
                marker={"size": 22, "color": "rgba(0,0,0,0)",
                        "line": {"width": 3, "color": LINK_COLORS[outcome]}},
                name=f"{outcome.lower()}, no successor",
                hoverinfo="text",
                hovertext=[
                    f"<b>{c}</b><br>{outcome.lower()}<br>flight {int(f)}, no successor link"
                    for c, f in zip(part["anomaly_code"], part["flight_id"])
                ],
            )
        )
        for x, code in zip(xs, part["anomaly_code"]):
            # Two staggered rows, because these captions are long and their flights adjacent.
            fig.add_annotation(
                x=x, y=0, text=code.replace("_", " ").lower(), showarrow=False,
                yshift=-38 if x % 2 == 0 else -60, font={"size": 10, "color": INK_2},
            )

    fig.add_shape(
        type="line", x0=-0.5, x1=len(ids) - 0.5, y0=0, y1=0,
        line={"width": 1, "color": AXIS},
    )
    fig.add_trace(
        go.Scatter(
            x=list(range(len(ids))), y=[0] * len(ids), mode="markers+text",
            marker={"size": 11, "color": INK_2, "line": {"width": 2, "color": SURFACE}},
            text=[str(f) for f in ids], textposition="top center",
            textfont={"size": 10, "color": MUTED},
            showlegend=False, hoverinfo="text",
            hovertext=[f"flight {f}" for f in ids],
        )
    )

    _layout(
        fig,
        f"Q08 - why the chain broke for aircraft {aircraft_id} on {day}",
        f"{len(an)} named failure modes on one aircraft on one day. Arcs above the line point "
        "forward in the sequence, arcs below point backward, and a ring is a failure with no "
        "successor to point at.",
        height=480,
    )
    fig.update_xaxes(visible=False, showgrid=False, range=[-0.7, len(ids) - 0.3])
    fig.update_yaxes(visible=False, showgrid=False, range=[-1.05, 1.30])
    fig.update_layout(
        legend={"orientation": "h", "y": -0.06, "x": 0},
        margin={"l": 30, "r": 30, "t": 96, "b": 50},
    )
    return fig


# =================================================================================== misc


def _empty(title: str, subtitle: str) -> go.Figure:
    """A zero-row answer still gets a figure. An empty answer is a fact, not a failure."""
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
        text="zero rows", font={"size": 26, "color": MUTED, "family": FONT},
    )
    _layout(fig, title, subtitle, height=240)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def show(fig: go.Figure) -> None:
    """Render a figure. Snowsight is happier with an explicit ``show`` than with a repr."""
    fig.show()
