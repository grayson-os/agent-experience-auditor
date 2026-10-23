#!/usr/bin/env python3
"""Render an OutSystems 11 Architecture Canvas diagram as SVG.

Usage:
    python3 render_canvas.py <canvas.json> <canvas.svg>

The input JSON lists modules (with layer and sub-layer) and module-to-module
references (consumer -> producer). The script validates the model, detects
upward, side, and cycle violations, writes the SVG, and prints a plain-text
summary of the canvas and its violations to stdout.

Requires Python 3.8+ and the standard library only.
"""

import json
import sys
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

# Layout, in pixels.
WIDTH = 1200
MARGIN = 20
LAYER_COL = 130
SUBLAYER_COL = 160
ROW_PAD = 26
BOX_H = 40
CHANNEL_W = 56
BOX_GAP_Y = 52
LANE_STEP = 6
LAYER_GAP = 14
TITLE_H = 44
LEGEND_H = 64
CHAR_W = 7.4
FONT = "Segoe UI, Helvetica, Arial, sans-serif"

INK = "#1a1a1a"
EDGE = "#6b6b6b"
RED = "#d32f2f"


def fail(message):
    print("error: " + message, file=sys.stderr)
    sys.exit(1)


def load_model(path):
    try:
        with open(path, encoding="utf-8") as handle:
            model = json.load(handle)
    except (OSError, ValueError) as exc:
        fail("cannot read {}: {}".format(path, exc))

    modules = model.get("modules")
    references = model.get("references", [])
    if not isinstance(modules, list) or not modules:
        fail('"modules" must be a non-empty list')
    if not isinstance(references, list):
        fail('"references" must be a list')

    valid = {layer["id"]: layer["sublayers"] for layer in LAYERS}
    names = set()
    for module in modules:
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

    seen = set()
    for ref in references:
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
    return model


def find_violations(modules, references):
    """Return {(from, to): [kinds]} for every reference that breaks a Canvas rule."""
    layer_of = {m["name"]: m["layer"] for m in modules}
    violations = {}

    def add(edge, kind):
        violations.setdefault(edge, [])
        if kind not in violations[edge]:
            violations[edge].append(kind)

    for ref in references:
        edge = (ref["from"], ref["to"])
        consumer, producer = layer_of[edge[0]], layer_of[edge[1]]
        if LAYER_RANK[producer] < LAYER_RANK[consumer]:
            add(edge, "upward")
        elif consumer == "end-user" and producer == "end-user":
            add(edge, "side")

    # Tarjan's strongly connected components; any edge inside a component
    # with more than one module is part of a cycle.
    graph = {m["name"]: [] for m in modules}
    for ref in references:
        graph[ref["from"]].append(ref["to"])
    index, low, on_stack, stack, component = {}, {}, set(), [], {}
    counter = [0]

    def connect(node):
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in graph[node]:
            if nxt not in index:
                connect(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            members = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                members.append(member)
                if member == node:
                    break
            for member in members:
                component[member] = (node, len(members))

    sys.setrecursionlimit(max(1000, len(graph) * 4))
    for node in graph:
        if node not in index:
            connect(node)
    for ref in references:
        a, b = ref["from"], ref["to"]
        if component[a][0] == component[b][0] and component[a][1] > 1:
            add((a, b), "cycle")
    return violations


def layout(modules):
    """Place every module box on a shared column grid.

    Returns (boxes, bands, grid, height). Columns line up across every row so
    the gaps between them form vertical channels for routing edges.
    """
    longest = max(len(m["name"]) for m in modules)
    box_w = int(min(max(140, longest * CHAR_W + 28), 300))
    area_x = MARGIN + LAYER_COL + SUBLAYER_COL
    area_w = WIDTH - MARGIN - area_x
    per_row = max(1, int((area_w - CHANNEL_W) // (box_w + CHANNEL_W)))

    groups = {}
    for m in modules:
        groups.setdefault((m["layer"], m["sublayer"]), []).append(m["name"])
    widest = max(len(names) for names in groups.values())
    cols = min(per_row, widest)
    grid_w = cols * box_w + (cols + 1) * CHANNEL_W
    grid_left = area_x + (area_w - grid_w) / 2
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
        rows = []
        for sublayer in layer["sublayers"]:
            members = sorted(groups.get((layer["id"], sublayer), []), key=str.lower)
            if members:
                rows.append((sublayer, members))
        band_top = y
        row_specs = []
        if not rows:
            height = BOX_H + 2 * ROW_PAD
            row_specs.append(("", [], y, height))
            y += height
        for sublayer, members in rows:
            count = (len(members) + cols - 1) // cols
            height = count * BOX_H + (count - 1) * BOX_GAP_Y + 2 * ROW_PAD
            for line in range(count):
                top = y + ROW_PAD + line * (BOX_H + BOX_GAP_Y)
                grid["lines"].append((top, top + BOX_H))
                for col, name in enumerate(members[line * cols:(line + 1) * cols]):
                    boxes[name] = {
                        "x": grid["col_x"][col], "y": top, "w": box_w, "h": BOX_H,
                        "col": col, "line": len(grid["lines"]) - 1,
                    }
            row_specs.append((sublayer, members, y, height))
            y += height
        bands.append({"layer": layer, "top": band_top, "bottom": y, "rows": row_specs})
        y += LAYER_GAP
    height = y - LAYER_GAP + LEGEND_H + MARGIN
    return boxes, bands, grid, height


class Lanes:
    """Hands out distinct offsets inside a corridor or channel."""

    def __init__(self):
        self.used = {}

    def take(self, key, low, high):
        k = self.used.get(key, 0)
        self.used[key] = k + 1
        center = (low + high) / 2 + LANE_STEP / 2
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
    plan = []
    for ref in references:
        a, b = boxes[ref["from"]], boxes[ref["to"]]
        if a["line"] == b["line"]:
            out_side, in_side = "top", "top"
        elif b["line"] > a["line"]:
            out_side, in_side = "bottom", "top"
        else:
            out_side, in_side = "top", "bottom"
        plan.append((ref, out_side, in_side))
        sides.setdefault((ref["from"], out_side), []).append((b["x"], ref, "out"))
        sides.setdefault((ref["to"], in_side), []).append((a["x"], ref, "in"))

    ports = {}
    for (name, side), entries in sides.items():
        box = boxes[name]
        entries.sort(key=lambda entry: entry[0])
        usable = box["w"] * 0.7
        start = box["x"] + (box["w"] - usable) / 2
        for i, (_, ref, direction) in enumerate(entries):
            px = start + usable * (i + 1) / (len(entries) + 1)
            py = box["y"] if side == "top" else box["y"] + box["h"]
            ports[(ref["from"], ref["to"], direction)] = (px, py)
    return plan, ports


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
    candidates = {a["col"], a["col"] + 1, b["col"], b["col"] + 1}
    channel = min(candidates, key=lambda c: (abs(grid["channel_x"][c] - sx) + abs(grid["channel_x"][c] - ex), c))
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


def label_point(points):
    """Midpoint of the longest segment, where a label is least crowded."""
    best = max(range(len(points) - 1), key=lambda i: abs(points[i + 1][0] - points[i][0]) + abs(points[i + 1][1] - points[i][1]))
    (x1, y1), (x2, y2) = points[best], points[best + 1]
    return (x1 + x2) / 2, (y1 + y2) / 2


def text(x, y, value, size=13, weight="normal", anchor="middle", fill=INK):
    return '<text x="{:.1f}" y="{:.1f}" font-family="{}" font-size="{}" font-weight="{}" text-anchor="{}" dominant-baseline="central" fill="{}">{}</text>'.format(
        x, y, FONT, size, weight, anchor, fill, escape(value)
    )


def wrapped(x, y, value, size, weight, width):
    words, lines, line = value.split(), [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if line and len(candidate) * size * 0.6 > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    top = y - (len(lines) - 1) * size * 0.65
    return [text(x, top + i * size * 1.3, l, size, weight) for i, l in enumerate(lines)]


def render(model):
    modules, references = model["modules"], model.get("references", [])
    audited = model.get("audited")
    violations = find_violations(modules, references)
    owners = {edge[0] for edge in violations}
    boxes, bands, grid, height = layout(modules)
    plan, ports = assign_ports(boxes, references)
    lanes = Lanes()

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" viewBox="0 0 {0} {1}">'.format(WIDTH, int(height)),
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{}"/></marker>'.format(EDGE),
        '<marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{}"/></marker>'.format(RED),
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        text(MARGIN, MARGIN + TITLE_H / 2 - 6, model.get("title") or "Architecture Canvas", 18, "bold", "start"),
    ]

    # Layer bands: identical width, stacked in one column.
    for band in bands:
        layer, top, bottom = band["layer"], band["top"], band["bottom"]
        out.append('<rect x="{}" y="{}" width="{}" height="{}" fill="{}" stroke="{}" stroke-width="1.5" rx="4"/>'.format(
            MARGIN, top, WIDTH - 2 * MARGIN, bottom - top, layer["fill"], layer["stroke"]))
        out.append('<line x1="{0}" y1="{1}" x2="{0}" y2="{2}" stroke="{3}" stroke-width="1"/>'.format(
            MARGIN + LAYER_COL, top, bottom, layer["stroke"]))
        out.extend(wrapped(MARGIN + LAYER_COL / 2, (top + bottom) / 2, layer["title"], 14, "bold", LAYER_COL - 16))
        for i, (sublayer, members, row_top, row_h) in enumerate(band["rows"]):
            if i:
                out.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{}" stroke-width="1"/>'.format(
                    MARGIN + LAYER_COL, row_top, WIDTH - MARGIN, row_top, layer["stroke"]))
            out.append('<line x1="{0}" y1="{1}" x2="{0}" y2="{2}" stroke="{3}" stroke-width="1" stroke-dasharray="3,3"/>'.format(
                MARGIN + LAYER_COL + SUBLAYER_COL, row_top, row_top + row_h, layer["stroke"]))
            if sublayer:
                out.extend(wrapped(MARGIN + LAYER_COL + SUBLAYER_COL / 2, row_top + row_h / 2, sublayer, 13, "normal", SUBLAYER_COL - 16))
            else:
                out.append(text(MARGIN + LAYER_COL + SUBLAYER_COL + 24, row_top + row_h / 2, "No modules in this layer", 13, "normal", "start", "#555555"))

    # Edges: normal references first, violations on top.
    labels = []
    ordered = sorted(plan, key=lambda item: (item[0]["from"], item[0]["to"]) in violations)
    for ref, out_side, in_side in ordered:
        edge = (ref["from"], ref["to"])
        start = ports[(edge[0], edge[1], "out")]
        end = ports[(edge[0], edge[1], "in")]
        points = route(grid, lanes, boxes[edge[0]], boxes[edge[1]], start, end)
        d, mid = path_data(points), label_point(points)
        if edge in violations:
            out.append('<path d="{}" fill="none" stroke="{}" stroke-width="3" marker-end="url(#arrow-red)"/>'.format(d, RED))
            labels.append((mid, ", ".join(violations[edge])))
        else:
            out.append('<path d="{}" fill="none" stroke="{}" stroke-width="1.4" marker-end="url(#arrow)"/>'.format(d, EDGE))

    # Module boxes, drawn over the edges.
    for name, box in boxes.items():
        stroke, width = INK, 1.2
        fill = "#ffffff"
        if name in owners:
            stroke, width, fill = RED, 2.5, "#fdecea"
        if name == audited:
            width = 4
        out.append('<rect x="{}" y="{}" width="{}" height="{}" rx="5" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
            box["x"], box["y"], box["w"], box["h"], fill, stroke, width))
        weight = "bold" if name == audited else "normal"
        out.append(text(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2, name, 13, weight))

    # Violation labels, drawn last so they stay readable.
    for (mx, my), label in labels:
        w = len(label) * 7 + 12
        out.append('<rect x="{:.1f}" y="{:.1f}" width="{}" height="18" rx="3" fill="#ffffff" stroke="{}" stroke-width="1"/>'.format(mx - w / 2, my - 9, w, RED))
        out.append(text(mx, my, label, 11, "bold", "middle", RED))

    # Legend.
    ly = height - MARGIN - LEGEND_H / 2
    x = MARGIN
    out.append('<path d="M{0},{1} L{2},{1}" stroke="{3}" stroke-width="1.4" marker-end="url(#arrow)"/>'.format(x, ly, x + 40, EDGE))
    out.append(text(x + 50, ly, "Reference (consumer to producer)", 12, "normal", "start"))
    x += 290
    out.append('<path d="M{0},{1} L{2},{1}" stroke="{3}" stroke-width="3" marker-end="url(#arrow-red)"/>'.format(x, ly, x + 40, RED))
    out.append(text(x + 50, ly, "Violation (upward, side, cycle)", 12, "normal", "start"))
    x += 280
    out.append('<rect x="{}" y="{}" width="34" height="20" rx="4" fill="#fdecea" stroke="{}" stroke-width="2.5"/>'.format(x, ly - 10, RED))
    out.append(text(x + 44, ly, "Owns a violation", 12, "normal", "start"))
    x += 190
    out.append('<rect x="{}" y="{}" width="34" height="20" rx="4" fill="#ffffff" stroke="{}" stroke-width="4"/>'.format(x, ly - 10, INK))
    out.append(text(x + 44, ly, "Audited module", 12, "normal", "start"))
    omitted = model.get("omitted") or []
    if omitted:
        out.append(text(MARGIN, ly + 24, "Not shown: " + ", ".join(omitted), 11, "normal", "start", "#555555"))
    out.append("</svg>")
    return "\n".join(out), violations


def summary(model, violations):
    lines = []
    modules = model["modules"]
    refs = model.get("references", [])
    lines.append("Architecture Canvas: {} modules, {} references, {} violations".format(len(modules), len(refs), len(violations)))
    for layer in LAYERS:
        lines.append(layer["title"])
        any_rows = False
        for sublayer in layer["sublayers"]:
            members = sorted((m["name"] for m in modules if m["layer"] == layer["id"] and m["sublayer"] == sublayer), key=str.lower)
            if members:
                any_rows = True
                marked = [n + (" (audited)" if n == model.get("audited") else "") for n in members]
                lines.append("  {}: {}".format(sublayer, ", ".join(marked)))
        if not any_rows:
            lines.append("  (no modules)")
    lines.append("Violations:" if violations else "Violations: none")
    for (a, b), kinds in sorted(violations.items()):
        lines.append("  [{}] {} -> {}".format(", ".join(kinds), a, b))
    return "\n".join(lines)


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    model = load_model(argv[1])
    svg, violations = render(model)
    try:
        with open(argv[2], "w", encoding="utf-8") as handle:
            handle.write(svg)
    except OSError as exc:
        fail("cannot write {}: {}".format(argv[2], exc))
    print(summary(model, violations))
    print("Wrote " + argv[2])


if __name__ == "__main__":
    main(sys.argv)
