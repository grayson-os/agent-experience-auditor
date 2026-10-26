#!/usr/bin/env python3
"""Render an OutSystems 11 Architecture Canvas diagram as SVG.

Usage:
    python3 render_canvas.py <canvas.json> <canvas.svg> [--html <canvas.html>]

The input JSON lists modules (with layer and sub-layer) and module-to-module
references (consumer -> producer). The script validates the model, detects
upward, side, and cycle violations, writes the SVG, and prints a plain-text
summary of the canvas, its violations, its cycles, and any gaps in the model.

When the model has more than FOCUS_THRESHOLD modules, the script also writes a
focused diagram next to the SVG (<name>-focus.svg) that keeps the audited
module, its direct references, and every module involved in a violation.

With --html, the script also fills the interactive Artifact template
(assets/canvas-artifact.html) with the model and writes it to the given path.

Requires Python 3.8+ and the standard library only.
"""

import json
import math
import os
import sys
from collections import deque
from xml.sax.saxutils import escape

# Layers and sub-layers, top to bottom. There is no Orchestration layer.
LAYERS = [
    {
        "id": "end-user",
        "title": "END USER",
        "fill": "#dbe7fb",
        "stroke": "#5b7fbf",
        "sublayers": ["End User"],
    },
    {
        "id": "core",
        "title": "CORE",
        "fill": "#fdf1cf",
        "stroke": "#c9a227",
        "sublayers": ["API", "Core Widgets", "Composite Logic", "Core Service"],
    },
    {
        "id": "foundation",
        "title": "FOUNDATION",
        "fill": "#dcefd9",
        "stroke": "#5a9a52",
        "sublayers": ["Style Guide", "Foundation Service", "Library", "Plugin"],
    },
]
LAYER_RANK = {layer["id"]: rank for rank, layer in enumerate(LAYERS)}
SUBLAYER_RANK = {
    (layer["id"], sublayer): rank
    for layer in LAYERS
    for rank, sublayer in enumerate(layer["sublayers"])
}
OWNERS = ("team", "platform")
KIND_ORDER = {"upward": 0, "side": 1, "cycle": 2}

# Layout, in pixels.
MIN_WIDTH = 960
MARGIN = 20
LAYER_COL = 110
SUBLAYER_COL = 140
ROW_PAD = 26
BOX_H = 38
CHANNEL_W = 48
BOX_GAP_Y = 48
LANE_STEP = 5
LAYER_GAP = 14
TITLE_H = 44
MIN_COLS = 4
MAX_COLS = 8
CHAR_W = 7.4
FONT = "Segoe UI, Helvetica, Arial, sans-serif"

# Models with more modules than this also get a focused diagram.
FOCUS_THRESHOLD = 15

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "canvas-artifact.html")
PLACEHOLDER = "__CANVAS_MODEL__"

INK = "#1a1a1a"
MUTED = "#555555"
EDGE = "#a8a8a8"
RED = "#d32f2f"
RED_FILL = "#fdecea"
PURPLE = "#7b1fa2"
PURPLE_FILL = "#f3e5f5"
AMBER = "#b26a00"


def fail(message):
    print("error: " + message, file=sys.stderr)
    sys.exit(1)


def load_model(path):
    try:
        with open(path, encoding="utf-8") as handle:
            model = json.load(handle)
    except (OSError, ValueError) as exc:
        fail("cannot read {}: {}".format(path, exc))
    validate(model)
    return model


def validate(model):
    if not isinstance(model, dict):
        fail("the model must be a JSON object")
    modules = model.get("modules")
    references = model.get("references", [])
    if not isinstance(modules, list) or not modules:
        fail('"modules" must be a non-empty list')
    if not isinstance(references, list):
        fail('"references" must be a list')

    valid = {layer["id"]: layer["sublayers"] for layer in LAYERS}
    names = set()
    for module in modules:
        if not isinstance(module, dict):
            fail("every module must be an object")
        name = module.get("name")
        layer = module.get("layer")
        sublayer = module.get("sublayer")
        if not name:
            fail("every module needs a name")
        if name in names:
            fail("duplicate module " + name)
        names.add(name)
        if layer not in valid:
            fail("{}: layer must be one of {}".format(name, ", ".join(valid)))
        if sublayer not in valid[layer]:
            fail("{}: sublayer for {} must be one of {}".format(name, layer, ", ".join(valid[layer])))
        if module.get("owner", "team") not in OWNERS:
            fail("{}: owner must be one of {}".format(name, ", ".join(OWNERS)))
        if not isinstance(module.get("references_checked", False), bool):
            fail("{}: references_checked must be true or false".format(name))

    seen = set()
    for ref in references:
        if not isinstance(ref, dict):
            fail("every reference must be an object")
        source, target = ref.get("from"), ref.get("to")
        for end in (source, target):
            if end not in names:
                fail("reference {} -> {} uses undeclared module {}".format(source, target, end))
        if source == target:
            fail("reference {} -> {} points at itself".format(source, target))
        if (source, target) in seen:
            fail("duplicate reference {} -> {}".format(source, target))
        seen.add((source, target))

    audited = model.get("audited")
    if audited is not None and audited not in names:
        fail("audited module {} is not in modules".format(audited))
    omitted = model.get("omitted", [])
    if not isinstance(omitted, list):
        fail('"omitted" must be a list of module names')


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def strongly_connected(graph):
    """Tarjan's algorithm, iterative. Returns the components, in discovery order."""
    index, low, on_stack, stack, components = {}, {}, set(), [], []
    counter = 0
    for root in graph:
        if root in index:
            continue
        work = [(root, iter(graph[root]))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for nxt in children:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(graph[nxt])))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                members = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    members.append(member)
                    if member == node:
                        break
                components.append(members)
    return components


def shortest_path(graph, start, goal, allowed):
    """Shortest path from start to goal that stays inside `allowed`."""
    previous = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = previous[node]
            return path[::-1]
        for nxt in sorted(graph[node]):
            if nxt in allowed and nxt not in previous:
                previous[nxt] = node
                queue.append(nxt)
    return None


def canonical_cycle(nodes):
    """Rotate a cycle (without its repeated end) to start at its smallest name."""
    start = min(range(len(nodes)), key=lambda i: nodes[i].lower())
    return tuple(nodes[start:] + nodes[:start])


def against_order(info, source, target):
    """True when a reference points up the canvas, by layer or by sub-layer."""
    a, b = info[source], info[target]
    if LAYER_RANK[b["layer"]] != LAYER_RANK[a["layer"]]:
        return LAYER_RANK[b["layer"]] < LAYER_RANK[a["layer"]]
    return SUBLAYER_RANK[(b["layer"], b["sublayer"])] < SUBLAYER_RANK[(a["layer"], a["sublayer"])]


def analyze(model):
    """Find violations, cycles, and gaps in the model.

    Returns a dict with:
      violations: numbered list of {number, from, to, kinds, cycle}
      cycles: list of {id, members, paths, break_candidates}
      unchecked: team modules whose own references were not inspected
    """
    modules, references = model["modules"], model.get("references", [])
    info = {m["name"]: m for m in modules}
    audited = model.get("audited")

    graph = {name: [] for name in info}
    for ref in references:
        graph[ref["from"]].append(ref["to"])

    kinds = {}

    def add(edge, kind):
        kinds.setdefault(edge, [])
        if kind not in kinds[edge]:
            kinds[edge].append(kind)

    # Upward and side references. Modules the team doesn't own are not judged.
    for ref in references:
        edge = (ref["from"], ref["to"])
        consumer, producer = info[edge[0]], info[edge[1]]
        if consumer.get("owner", "team") != "team":
            continue
        if LAYER_RANK[producer["layer"]] < LAYER_RANK[consumer["layer"]]:
            add(edge, "upward")
        elif consumer["layer"] == "end-user" and producer["layer"] == "end-user":
            add(edge, "side")

    # Cycles: every reference inside a strongly connected component with more
    # than one module lies on at least one cycle, direct or indirect.
    components = [sorted(c, key=str.lower) for c in strongly_connected(graph) if len(c) > 1]
    components.sort(key=lambda c: c[0].lower())
    cycles, cycle_of = [], {}
    for number, members in enumerate(components, 1):
        cycle_id = "C{}".format(number)
        allowed = set(members)
        edges = sorted(
            ((a, b) for a in members for b in graph[a] if b in allowed),
            key=lambda e: (e[0].lower(), e[1].lower()),
        )
        paths = set()
        for a, b in edges:
            add((a, b), "cycle")
            cycle_of[(a, b)] = cycle_id
            back = shortest_path(graph, b, a, allowed)
            paths.add(canonical_cycle([a] + back[:-1]))
        cycles.append({
            "id": cycle_id,
            "members": members,
            "paths": sorted(paths, key=lambda p: (len(p), [n.lower() for n in p])),
            "break_candidates": [e for e in edges if against_order(info, *e)],
        })

    ordered = sorted(
        kinds.items(),
        key=lambda item: (
            min(KIND_ORDER[k] for k in item[1]),
            cycle_of.get(item[0], ""),
            item[0][0].lower(),
            item[0][1].lower(),
        ),
    )
    violations = []
    for number, (edge, edge_kinds) in enumerate(ordered, 1):
        violations.append({
            "number": number,
            "from": edge[0],
            "to": edge[1],
            "kinds": sorted(edge_kinds, key=KIND_ORDER.get),
            "cycle": cycle_of.get(edge),
        })

    unchecked = sorted(
        (
            m["name"] for m in modules
            if m.get("owner", "team") == "team"
            and not m.get("references_checked", m["name"] == audited)
        ),
        key=str.lower,
    )
    return {"violations": violations, "cycles": cycles, "unchecked": unchecked}


def cycle_kind(cycle):
    """A direct cycle is two modules referencing each other; an indirect one runs through others."""
    direct = {len(path) == 2 for path in cycle["paths"]}
    if direct == {True}:
        return "direct"
    return "indirect" if direct == {False} else "direct and indirect"


def violation_label(violation):
    parts = []
    for kind in violation["kinds"]:
        parts.append("cycle " + violation["cycle"] if kind == "cycle" else kind)
    return ", ".join(parts)


def focus_modules(model, analysis):
    """Modules for the focused diagram, or None when it would not help."""
    modules = model["modules"]
    if len(modules) <= FOCUS_THRESHOLD:
        return None
    audited = model.get("audited")
    keep = set()
    if audited:
        keep.add(audited)
        for ref in model.get("references", []):
            if audited in (ref["from"], ref["to"]):
                keep.update((ref["from"], ref["to"]))
    for violation in analysis["violations"]:
        keep.update((violation["from"], violation["to"]))
    for cycle in analysis["cycles"]:
        keep.update(cycle["members"])
    if not keep or len(keep) >= len(modules):
        return None
    return keep


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def best_slots(desired, cols):
    """Assign increasing column slots to members sorted by desired position,
    minimizing the total distance from each member's desired column."""
    k = len(desired)
    inf = float("inf")
    cost = [[inf] * cols for _ in range(k)]
    back = [[0] * cols for _ in range(k)]
    for s in range(cols):
        cost[0][s] = abs(s - desired[0])
    for i in range(1, k):
        best, best_s = inf, 0
        for s in range(cols):
            if s - 1 >= 0 and cost[i - 1][s - 1] < best:
                best, best_s = cost[i - 1][s - 1], s - 1
            if best < inf:
                cost[i][s] = best + abs(s - desired[i])
                back[i][s] = best_s
    s = min(range(cols), key=lambda c: (cost[k - 1][c], c))
    slots = [0] * k
    for i in range(k - 1, -1, -1):
        slots[i] = s
        s = back[i][s]
    return slots


def order_columns(lines, cols, references):
    """Place the modules of each box line in columns so that references run
    as straight as possible (barycenter heuristic, a few sweeps)."""
    neighbours = {name: [] for line in lines for name in line}
    for ref in references:
        if ref["from"] in neighbours and ref["to"] in neighbours:
            neighbours[ref["from"]].append(ref["to"])
            neighbours[ref["to"]].append(ref["from"])

    column = {}
    for line in lines:
        k = len(line)
        for j, name in enumerate(line):
            column[name] = int(round((j + 0.5) * cols / k - 0.5))

    for sweep in range(8):
        sequence = lines if sweep % 2 == 0 else lines[::-1]
        for line in sequence:
            desired = {}
            for name in line:
                linked = neighbours[name]
                if linked:
                    desired[name] = sum(column[n] for n in linked) / len(linked)
                else:
                    desired[name] = column[name]
            members = sorted(line, key=lambda n: (desired[n], n.lower()))
            for name, slot in zip(members, best_slots([desired[n] for n in members], cols)):
                column[name] = slot
    return column


def layout(modules, references):
    """Place every module box on a shared column grid.

    Returns (boxes, bands, grid, width, bottom). Columns line up across every
    row so the gaps between them form vertical channels for routing edges.
    """
    longest = max(len(m["name"]) for m in modules)
    box_w = int(min(max(120, longest * CHAR_W + 24), 220))

    groups = {}
    for m in modules:
        groups.setdefault((m["layer"], m["sublayer"]), []).append(m["name"])
    widest = max(len(names) for names in groups.values())
    cols = max(MIN_COLS, min(MAX_COLS, widest))

    # Split each sub-layer into box lines of at most `cols` modules.
    rows_by_layer, lines = {}, []
    for layer in LAYERS:
        rows = []
        for sublayer in layer["sublayers"]:
            members = sorted(groups.get((layer["id"], sublayer), []), key=str.lower)
            if members:
                chunks = [members[i:i + cols] for i in range(0, len(members), cols)]
                rows.append((sublayer, chunks))
                lines.extend(chunks)
        rows_by_layer[layer["id"]] = rows
    column = order_columns(lines, cols, references)

    area_x = MARGIN + LAYER_COL + SUBLAYER_COL
    grid_w = cols * box_w + (cols + 1) * CHANNEL_W
    width = max(MIN_WIDTH, int(area_x + grid_w + MARGIN))
    grid_left = area_x + (width - MARGIN - area_x - grid_w) / 2
    grid = {
        "cols": cols,
        "box_w": box_w,
        "col_x": [grid_left + CHANNEL_W + k * (box_w + CHANNEL_W) for k in range(cols)],
        "channel_x": [grid_left + CHANNEL_W / 2 + k * (box_w + CHANNEL_W) for k in range(cols + 1)],
        "lines": [],
    }

    boxes, bands = {}, []
    y = MARGIN + TITLE_H
    for layer in LAYERS:
        band_top = y
        row_specs = []
        rows = rows_by_layer[layer["id"]]
        if not rows:
            height = BOX_H + 2 * ROW_PAD
            row_specs.append(("", y, height))
            y += height
        for sublayer, chunks in rows:
            count = len(chunks)
            height = count * BOX_H + (count - 1) * BOX_GAP_Y + 2 * ROW_PAD
            for line, chunk in enumerate(chunks):
                top = y + ROW_PAD + line * (BOX_H + BOX_GAP_Y)
                grid["lines"].append((top, top + BOX_H))
                for name in chunk:
                    col = column[name]
                    boxes[name] = {
                        "x": grid["col_x"][col], "y": top, "w": box_w, "h": BOX_H,
                        "col": col, "line": len(grid["lines"]) - 1,
                    }
            row_specs.append((sublayer, y, height))
            y += height
        bands.append({"layer": layer, "top": band_top, "bottom": y, "rows": row_specs})
        y += LAYER_GAP
    return boxes, bands, grid, width, y - LAYER_GAP


# ---------------------------------------------------------------------------
# Edge routing
# ---------------------------------------------------------------------------


class Lanes:
    """Hands out distinct offsets inside a corridor or channel."""

    def __init__(self):
        self.used = {}

    def load(self, key):
        return self.used.get(key, 0)

    def take(self, key, low, high):
        k = self.used.get(key, 0)
        self.used[key] = k + 1
        center = (low + high) / 2
        room = max(0, int((high - low) / 2 - LANE_STEP) // LANE_STEP)
        step = (k + 1) // 2 if room == 0 else ((k + 1) // 2) % (room + 1)
        sign = 1 if k % 2 else -1
        return center + sign * step * LANE_STEP


def corridor(grid, upper, lower):
    """Y range of the horizontal gap between box line `upper` and `lower`."""
    lines = grid["lines"]
    top = lines[upper][1] if upper >= 0 else lines[lower][0] - ROW_PAD
    bottom = lines[lower][0] if lower < len(lines) else lines[upper][1] + ROW_PAD
    return top, bottom


def assign_ports(boxes, references):
    """Spread edge endpoints along each box side so arrows don't stack."""
    sides = {}
    for ref in references:
        a, b = boxes[ref["from"]], boxes[ref["to"]]
        if a["line"] == b["line"]:
            out_side, in_side = "top", "top"
        elif b["line"] > a["line"]:
            out_side, in_side = "bottom", "top"
        else:
            out_side, in_side = "top", "bottom"
        sides.setdefault((ref["from"], out_side), []).append((b["x"], ref["to"], ref, "out"))
        sides.setdefault((ref["to"], in_side), []).append((a["x"], ref["from"], ref, "in"))

    ports = {}
    for (name, side), entries in sides.items():
        box = boxes[name]
        entries.sort(key=lambda entry: (entry[0], entry[1].lower()))
        usable = box["w"] * 0.7
        start = box["x"] + (box["w"] - usable) / 2
        for i, (_, _, ref, direction) in enumerate(entries):
            px = start + usable * (i + 1) / (len(entries) + 1)
            py = box["y"] if side == "top" else box["y"] + box["h"]
            ports[(ref["from"], ref["to"], direction)] = (px, py)
    return ports


def route(grid, lanes, a, b, start, end):
    """Orthogonal route from port `start` on box a to port `end` on box b.

    Edges only travel through corridors (between box lines) and channels
    (between box columns), so they never pass behind a module box.
    """
    (sx, sy), (ex, ey) = start, end
    la, lb = a["line"], b["line"]
    if la == lb:
        low, high = corridor(grid, la - 1, la)
        y = lanes.take(("h", la - 1, la), low, high)
        return [(sx, sy), (sx, y), (ex, y), (ex, ey)]
    down = lb > la
    first = (la, la + 1) if down else (la - 1, la)
    last = (lb - 1, lb) if down else (lb, lb + 1)
    y1 = lanes.take(("h",) + first, *corridor(grid, *first))
    if first == last:
        return [(sx, sy), (sx, y1), (ex, y1), (ex, ey)]
    y2 = lanes.take(("h",) + last, *corridor(grid, *last))
    left, right = min(a["col"], b["col"]), max(a["col"], b["col"]) + 1
    channel = min(
        range(left, right + 1),
        key=lambda c: (
            abs(grid["channel_x"][c] - sx) + abs(grid["channel_x"][c] - ex) + 24 * lanes.load(("v", c)),
            c,
        ),
    )
    cx = grid["channel_x"][channel]
    x = lanes.take(("v", channel), cx - CHANNEL_W / 2 + 4, cx + CHANNEL_W / 2 - 4)
    return [(sx, sy), (sx, y1), (x, y1), (x, y2), (ex, y2), (ex, ey)]


def path_data(points, radius=6):
    """SVG path through `points` with rounded corners."""
    pts = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
    d = ["M{:.1f},{:.1f}".format(*pts[0])]
    for i in range(1, len(pts) - 1):
        (px, py), (cx, cy), (nx, ny) = pts[i - 1], pts[i], pts[i + 1]
        r1 = min(radius, abs(cx - px) / 2 + abs(cy - py) / 2)
        r2 = min(radius, abs(nx - cx) / 2 + abs(ny - cy) / 2)
        r = min(r1, r2)

        def toward(fx, fy, tx, ty, dist):
            length = max(abs(tx - fx) + abs(ty - fy), 1e-9)
            return fx + (tx - fx) / length * dist, fy + (ty - fy) / length * dist

        b1 = toward(cx, cy, px, py, r)
        b2 = toward(cx, cy, nx, ny, r)
        d.append("L{:.1f},{:.1f} Q{:.1f},{:.1f} {:.1f},{:.1f}".format(b1[0], b1[1], cx, cy, b2[0], b2[1]))
    d.append("L{:.1f},{:.1f}".format(*pts[-1]))
    return " ".join(d)


def marker_point(points, taken, boxes, radius=11):
    """A point on the route for a numbered marker, clear of other markers and boxes."""
    segments = sorted(
        range(len(points) - 1),
        key=lambda i: -(abs(points[i + 1][0] - points[i][0]) + abs(points[i + 1][1] - points[i][1])),
    )

    def clear(x, y):
        for tx, ty in taken:
            if math.hypot(tx - x, ty - y) < 2 * radius + 4:
                return False
        for box in boxes.values():
            if box["x"] - radius < x < box["x"] + box["w"] + radius and box["y"] - radius < y < box["y"] + box["h"] + radius:
                return False
        return True

    for i in segments:
        (x1, y1), (x2, y2) = points[i], points[i + 1]
        for t in (0.5, 0.35, 0.65, 0.2, 0.8):
            x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            if clear(x, y):
                return x, y
    (x1, y1), (x2, y2) = points[segments[0]], points[segments[0] + 1]
    return (x1 + x2) / 2, (y1 + y2) / 2


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------


def text(x, y, value, size=13, weight="normal", anchor="middle", fill=INK):
    return '<text x="{:.1f}" y="{:.1f}" font-family="{}" font-size="{}" font-weight="{}" text-anchor="{}" dominant-baseline="central" fill="{}">{}</text>'.format(
        x, y, FONT, size, weight, anchor, fill, escape(value)
    )


def wrap(value, size, width):
    words, lines, line = value.split(), [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if line and len(candidate) * size * 0.56 > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    return lines


def wrapped(x, y, value, size, weight, width):
    lines = wrap(value, size, width)
    top = y - (len(lines) - 1) * size * 0.65
    return [text(x, top + i * size * 1.3, l, size, weight) for i, l in enumerate(lines)]


def fit(name, width, size=13):
    """Shorten a module name with an ellipsis if it doesn't fit its box."""
    room = int((width - 16) / (size * 0.56))
    return name if len(name) <= room else name[:max(1, room - 1)] + "…"


def badge(x, y, number, color):
    return [
        '<circle cx="{:.1f}" cy="{:.1f}" r="10" fill="{}" stroke="#ffffff" stroke-width="1.5"/>'.format(x, y, color),
        text(x, y, str(number), 11, "bold", "middle", "#ffffff"),
    ]


def edge_color(violation):
    return PURPLE if "cycle" in violation["kinds"] else RED


def legend(width, top):
    """Legend items flowed left to right, wrapping to new lines as needed."""
    items = [
        ("line", EDGE, 1.2, "Reference (consumer to producer)"),
        ("line", RED, 2.4, "Upward or side reference"),
        ("line", PURPLE, 2.4, "Reference in a cycle"),
        ("badge", RED, None, "Violation number, listed below"),
        ("box", (RED_FILL, RED, 2, None), None, "Owns an upward or side reference"),
        ("box", (PURPLE_FILL, PURPLE, 2, None), None, "In a cycle"),
        ("box", ("#ffffff", INK, 4, None), None, "Audited module"),
        ("box", ("#ffffff", MUTED, 1.2, "5,3"), None, "OutSystems or Forge module"),
        ("unchecked", AMBER, None, "References not checked"),
    ]
    out, x, y = [], MARGIN, top + 12
    for kind, color, stroke, label in items:
        item_w = 60 + len(label) * 6.6
        if x + item_w > width - MARGIN:
            x, y = MARGIN, y + 26
        if kind == "line":
            out.append('<path d="M{0:.1f},{1:.1f} L{2:.1f},{1:.1f}" stroke="{3}" stroke-width="{4}" marker-end="url(#arrow-{5})"/>'.format(
                x, y, x + 36, color, stroke, {EDGE: "grey", RED: "red", PURPLE: "purple"}[color]))
        elif kind == "badge":
            out.extend(badge(x + 18, y, 1, color))
        elif kind == "box":
            fill, line, line_w, dash = color
            out.append('<rect x="{:.1f}" y="{:.1f}" width="36" height="18" rx="4" fill="{}" stroke="{}" stroke-width="{}"{}/>'.format(
                x, y - 9, fill, line, line_w, ' stroke-dasharray="{}"'.format(dash) if dash else ""))
        else:
            out.extend(unchecked_mark(x + 18, y))
        out.append(text(x + 46, y, label, 12, "normal", "start"))
        x += item_w
    return out, y + 18


def unchecked_mark(x, y):
    return [
        '<circle cx="{:.1f}" cy="{:.1f}" r="8" fill="#fff4e0" stroke="{}" stroke-width="1.5"/>'.format(x, y, AMBER),
        text(x, y + 0.5, "?", 11, "bold", "middle", AMBER),
    ]


def notes(model, analysis, width, top, focus_note):
    """Violation table, cycle paths, and gaps, written below the canvas."""
    out, y = [], top
    usable = width - 2 * MARGIN

    def heading(value):
        nonlocal y
        y += 26
        out.append(text(MARGIN, y, value, 14, "bold", "start"))
        y += 6

    def paragraph(value, indent=0, color=INK, size=12):
        nonlocal y
        for line in wrap(value, size, usable - indent):
            y += 18
            out.append(text(MARGIN + indent, y, line, size, "normal", "start", color))

    if focus_note:
        y += 8
        paragraph(focus_note, color=MUTED)

    heading("Violations" if analysis["violations"] else "Violations: none")
    for violation in analysis["violations"]:
        y += 24
        out.extend(badge(MARGIN + 10, y, violation["number"], edge_color(violation)))
        out.append(text(MARGIN + 28, y, violation_label(violation), 12, "bold", "start", edge_color(violation)))
        out.append(text(MARGIN + 150, y, "{} → {}".format(violation["from"], violation["to"]), 12, "normal", "start"))

    if analysis["cycles"]:
        heading("Cycles")
        for cycle in analysis["cycles"]:
            kind = cycle_kind(cycle)
            paragraph("{} ({}, {} modules): {}".format(cycle["id"], kind, len(cycle["members"]), ", ".join(cycle["members"])), color=PURPLE)
            for path in cycle["paths"]:
                paragraph(" → ".join(list(path) + [path[0]]), indent=16)
            if cycle["break_candidates"]:
                paragraph("Points against the canvas order: " + ", ".join(
                    "{} → {}".format(a, b) for a, b in cycle["break_candidates"]), indent=16, color=MUTED)

    gaps = []
    if analysis["unchecked"]:
        gaps.append("References not checked for {}. Cycles through these modules can't be ruled out.".format(
            ", ".join(analysis["unchecked"])))
    omitted = model.get("omitted") or []
    if omitted:
        gaps.append("Not shown: " + ", ".join(omitted))
    if gaps:
        heading("Gaps")
        for gap in gaps:
            paragraph(gap, color=AMBER if gap.startswith("References") else MUTED)
    return out, y + MARGIN


def render(model, analysis, keep=None, focus_note=None):
    """Return the SVG for the whole model, or for the modules in `keep`."""
    modules = [m for m in model["modules"] if keep is None or m["name"] in keep]
    names = {m["name"] for m in modules}
    references = [r for r in model.get("references", []) if r["from"] in names and r["to"] in names]
    info = {m["name"]: m for m in modules}
    audited = model.get("audited")
    violations = {(v["from"], v["to"]): v for v in analysis["violations"]}
    in_cycle = {name for cycle in analysis["cycles"] for name in cycle["members"]}
    owns = {v["from"] for v in analysis["violations"] if set(v["kinds"]) - {"cycle"}}
    unchecked = set(analysis["unchecked"])

    boxes, bands, grid, width, canvas_bottom = layout(modules, references)
    ports = assign_ports(boxes, references)
    lanes = Lanes()

    title = model.get("title") or "Architecture Canvas"
    if keep is not None:
        title += " (focused)"
    body = [
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        text(MARGIN, MARGIN + TITLE_H / 2 - 6, title, 18, "bold", "start"),
    ]

    # Layer bands: identical width, stacked in one column.
    for band in bands:
        layer, top, bottom = band["layer"], band["top"], band["bottom"]
        body.append('<rect x="{}" y="{}" width="{}" height="{}" fill="{}" stroke="{}" stroke-width="1.5" rx="4"/>'.format(
            MARGIN, top, width - 2 * MARGIN, bottom - top, layer["fill"], layer["stroke"]))
        body.append('<line x1="{0}" y1="{1}" x2="{0}" y2="{2}" stroke="{3}" stroke-width="1"/>'.format(
            MARGIN + LAYER_COL, top, bottom, layer["stroke"]))
        body.extend(wrapped(MARGIN + LAYER_COL / 2, (top + bottom) / 2, layer["title"], 14, "bold", LAYER_COL - 16))
        for i, (sublayer, row_top, row_h) in enumerate(band["rows"]):
            if i:
                body.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{}" stroke-width="1"/>'.format(
                    MARGIN + LAYER_COL, row_top, width - MARGIN, row_top, layer["stroke"]))
            body.append('<line x1="{0}" y1="{1}" x2="{0}" y2="{2}" stroke="{3}" stroke-width="1" stroke-dasharray="3,3"/>'.format(
                MARGIN + LAYER_COL + SUBLAYER_COL, row_top, row_top + row_h, layer["stroke"]))
            if sublayer:
                body.extend(wrapped(MARGIN + LAYER_COL + SUBLAYER_COL / 2, row_top + row_h / 2, sublayer, 13, "normal", SUBLAYER_COL - 16))
            else:
                body.append(text(MARGIN + LAYER_COL + SUBLAYER_COL + 24, row_top + row_h / 2, "No modules in this layer", 13, "normal", "start", MUTED))

    # Edges: compliant references first and faint, violations on top.
    ordered = sorted(references, key=lambda r: ((r["from"], r["to"]) in violations, r["from"].lower(), r["to"].lower()))
    routes = {}
    for ref in ordered:
        edge = (ref["from"], ref["to"])
        points = route(grid, lanes, boxes[edge[0]], boxes[edge[1]],
                       ports[(edge[0], edge[1], "out")], ports[(edge[0], edge[1], "in")])
        routes[edge] = points
        violation = violations.get(edge)
        if violation:
            color = edge_color(violation)
            body.append('<path d="{}" fill="none" stroke="{}" stroke-width="2.4" marker-end="url(#arrow-{})"><title>{}</title></path>'.format(
                path_data(points), color, "purple" if color == PURPLE else "red",
                escape("{}. {} -> {} ({})".format(violation["number"], edge[0], edge[1], violation_label(violation)))))
        else:
            body.append('<path d="{}" fill="none" stroke="{}" stroke-width="1.2" marker-end="url(#arrow-grey)"><title>{}</title></path>'.format(
                path_data(points), EDGE, escape("{} -> {}".format(*edge))))

    # Module boxes, drawn over the edges.
    for name, box in boxes.items():
        module = info[name]
        fill, stroke, stroke_w = "#ffffff", INK, 1.2
        if name in in_cycle:
            fill, stroke, stroke_w = PURPLE_FILL, PURPLE, 2.2
        if name in owns:
            fill, stroke, stroke_w = RED_FILL, RED, 2.2
        if name == audited:
            stroke_w = 4
        platform = module.get("owner", "team") == "platform"
        dash = ' stroke-dasharray="5,3"' if platform else ""
        if platform and name not in in_cycle:
            stroke = MUTED
        body.append('<g><title>{}</title>'.format(escape("{} ({} / {}{})".format(
            name, module["layer"], module["sublayer"], ", OutSystems or Forge" if platform else ""))))
        body.append('<rect x="{}" y="{}" width="{}" height="{}" rx="5" fill="{}" stroke="{}" stroke-width="{}"{}/>'.format(
            box["x"], box["y"], box["w"], box["h"], fill, stroke, stroke_w, dash))
        weight = "bold" if name == audited else "normal"
        body.append(text(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2, fit(name, box["w"]), 13, weight, "middle", MUTED if platform else INK))
        if name in unchecked:
            body.extend(unchecked_mark(box["x"] + box["w"] - 2, box["y"] + 2))
        body.append("</g>")

    # Numbered markers on violating references, drawn last so they stay readable.
    taken = []
    for edge, points in routes.items():
        violation = violations.get(edge)
        if violation:
            x, y = marker_point(points, taken, boxes)
            taken.append((x, y))
            body.extend(badge(x, y, violation["number"], edge_color(violation)))

    legend_out, legend_bottom = legend(width, canvas_bottom + 14)
    body.extend(legend_out)
    notes_out, height = notes(model, analysis, width, legend_bottom, focus_note)
    body.extend(notes_out)

    head = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" viewBox="0 0 {0} {1}">'.format(width, int(height)),
        "<defs>",
    ]
    for key, color, size in (("grey", EDGE, 7), ("red", RED, 6), ("purple", PURPLE, 6)):
        head.append('<marker id="arrow-{0}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="{2}" markerHeight="{2}" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{1}"/></marker>'.format(key, color, size))
    head.append("</defs>")
    return "\n".join(head + body + ["</svg>"])


# ---------------------------------------------------------------------------
# Text summary
# ---------------------------------------------------------------------------


def summary(model, analysis):
    modules = model["modules"]
    refs = model.get("references", [])
    audited = model.get("audited")
    lines = ["Architecture Canvas: {} modules, {} references, {} violations, {} cycles".format(
        len(modules), len(refs), len(analysis["violations"]), len(analysis["cycles"]))]
    for layer in LAYERS:
        lines.append(layer["title"])
        any_rows = False
        for sublayer in layer["sublayers"]:
            members = sorted((m for m in modules if m["layer"] == layer["id"] and m["sublayer"] == sublayer),
                             key=lambda m: m["name"].lower())
            if members:
                any_rows = True
                marked = []
                for m in members:
                    tags = []
                    if m["name"] == audited:
                        tags.append("audited")
                    if m.get("owner", "team") == "platform":
                        tags.append("platform")
                    marked.append(m["name"] + (" ({})".format(", ".join(tags)) if tags else ""))
                lines.append("  {}: {}".format(sublayer, ", ".join(marked)))
        if not any_rows:
            lines.append("  (no modules)")

    lines.append("Violations:" if analysis["violations"] else "Violations: none")
    for v in analysis["violations"]:
        lines.append("  {}. [{}] {} -> {}".format(v["number"], violation_label(v), v["from"], v["to"]))

    lines.append("Cycles:" if analysis["cycles"] else "Cycles: none")
    for cycle in analysis["cycles"]:
        kind = cycle_kind(cycle)
        lines.append("  {} ({}, {} modules): {}".format(cycle["id"], kind, len(cycle["members"]), ", ".join(cycle["members"])))
        for path in cycle["paths"]:
            lines.append("    " + " -> ".join(list(path) + [path[0]]))
        if cycle["break_candidates"]:
            lines.append("    Against the canvas order: " + ", ".join(
                "{} -> {}".format(a, b) for a, b in cycle["break_candidates"]))

    if analysis["unchecked"]:
        lines.append("Gaps:")
        lines.append("  References not checked for: " + ", ".join(analysis["unchecked"]))
        lines.append("  Cycles through these modules can't be ruled out.")
    if model.get("omitted"):
        lines.append("Not shown: " + ", ".join(model["omitted"]))
    return "\n".join(lines)


def artifact_html(model):
    """The interactive Artifact template with the model embedded in it."""
    try:
        with open(TEMPLATE, encoding="utf-8") as handle:
            template = handle.read()
    except OSError as exc:
        fail("cannot read the Artifact template {}: {}".format(TEMPLATE, exc))
    if template.count(PLACEHOLDER) != 1:
        fail("the Artifact template must contain {} exactly once".format(PLACEHOLDER))
    # Escape <, > and & so the JSON can't close its <script> element.
    data = json.dumps(model, indent=2, ensure_ascii=False)
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    title = escape(model.get("title") or "Architecture Canvas")
    template = template.replace("<title>Architecture Canvas</title>", "<title>{}</title>".format(title), 1)
    return template.replace(PLACEHOLDER, data)


def focus_path(path):
    root, ext = os.path.splitext(path)
    return root + "-focus" + (ext or ".svg")


def write(path, content):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    except OSError as exc:
        fail("cannot write {}: {}".format(path, exc))


def main(argv):
    html_path = None
    if len(argv) == 5 and argv[3] == "--html":
        html_path = argv[4]
    elif len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    model = load_model(argv[1])
    analysis = analyze(model)
    write(argv[2], render(model, analysis))
    written = [argv[2]]

    keep = focus_modules(model, analysis)
    if keep:
        note = ("Focused view: {} of {} modules. It keeps the audited module, the modules it references or is "
                "referenced by, and every module in a violation or cycle. The full canvas is in {}.").format(
                    len(keep), len(model["modules"]), os.path.basename(argv[2]))
        target = focus_path(argv[2])
        write(target, render(model, analysis, keep, note))
        written.append(target)

    if html_path:
        write(html_path, artifact_html(model))
        written.append(html_path)

    print(summary(model, analysis))
    for path in written:
        print("Wrote " + path)


if __name__ == "__main__":
    main(sys.argv)
