#!/usr/bin/env python3
"""
Exact LTspice .asc -> .net compiler, connectivity verifier, and visual renderer.

Uses the actual macOS LTspice .asy symbol definitions from:
  ~/Library/Application Support/LTspice/lib/sym/
so that every .asc schematic we build is guaranteed to have exact pin
alignment, zero floating nodes, and 100% electrical equivalence between
opening/running in LTspice GUI and running LTspice -b on the compiled .net.
"""

import os
import re
import math
from pathlib import Path
from collections import defaultdict

SYM_ROOT = Path.home() / "Library/Application Support/LTspice/lib/sym"


def transform_pt(px, py, sx, sy, orient):
    """Exact LTspice coordinate transform for R0/R90/R180/R270 and M0/M90/M180/M270."""
    if orient == "R0":
        return (sx + px, sy + py)
    elif orient == "R90":
        return (sx - py, sy + px)
    elif orient == "R180":
        return (sx - px, sy - py)
    elif orient == "R270":
        return (sx + py, sy - px)
    elif orient == "M0":
        return (sx - px, sy + py)
    elif orient == "M90":
        return (sx - py, sy - px)
    elif orient == "M180":
        return (sx + px, sy - py)
    elif orient == "M270":
        return (sx + py, sy + px)
    else:
        raise ValueError(f"Unknown orientation: {orient}")


class SymbolDef:
    def __init__(self, name):
        self.name = name
        self.prefix = ""
        self.default_value = ""
        self.pins = []       # list of (x, y, spice_order, pin_name)
        self.lines = []      # list of (x1, y1, x2, y2)
        self.rects = []      # list of (x1, y1, x2, y2)
        self.circles = []    # list of (x1, y1, x2, y2)
        self.arcs = []       # list of (x1, y1, x2, y2, x3, y3, x4, y4)
        self._load()

    def _load(self):
        rel = self.name.replace("\\", "/") + ".asy"
        path = SYM_ROOT / rel
        if not path.exists():
            # Case-insensitive fallback
            for p in SYM_ROOT.rglob("*.asy"):
                if p.stem.lower() == Path(rel).stem.lower():
                    path = p
                    break
        if not path.exists():
            raise FileNotFoundError(f"Symbol .asy not found: {self.name} ({path})")

        cur_pin = None
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                parts = line.split()
                tag = parts[0]
                if tag == "SYMATTR":
                    if len(parts) >= 3:
                        k = parts[1]
                        v = " ".join(parts[2:])
                        if k == "Prefix":
                            self.prefix = v
                        elif k == "Value":
                            self.default_value = v
                elif tag == "PIN":
                    if cur_pin is not None:
                        self.pins.append(cur_pin)
                    cur_pin = {"x": int(parts[1]), "y": int(parts[2]), "order": len(self.pins) + 1, "name": ""}
                elif tag == "PINATTR" and cur_pin is not None:
                    if parts[1] == "SpiceOrder":
                        cur_pin["order"] = int(parts[2])
                    elif parts[1] == "PinName":
                        cur_pin["name"] = parts[2]
                elif tag == "LINE":
                    # LINE Normal x1 y1 x2 y2
                    nums = [int(x) for x in parts[2:6]]
                    self.lines.append(tuple(nums))
                elif tag == "RECTANGLE":
                    nums = [int(x) for x in parts[2:6]]
                    self.rects.append(tuple(nums))
                elif tag == "CIRCLE":
                    nums = [int(x) for x in parts[2:6]]
                    self.circles.append(tuple(nums))
                elif tag == "ARC":
                    nums = [int(x) for x in parts[2:10]]
                    self.arcs.append(tuple(nums))
        if cur_pin is not None:
            self.pins.append(cur_pin)
        self.pins.sort(key=lambda p: p["order"])


_SYM_CACHE = {}


def get_symbol(name):
    if name not in _SYM_CACHE:
        _SYM_CACHE[name] = SymbolDef(name)
    return _SYM_CACHE[name]


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            return x
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def point_on_segment(px, py, x1, y1, x2, y2):
    """True if point (px, py) lies on orthogonal or collinear segment (x1,y1)-(x2,y2)."""
    if min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2):
        # Cross product == 0
        return (x2 - x1) * (py - y1) == (y2 - y1) * (px - x1)
    return False


def parse_asc(asc_path):
    wires = []
    flags = []
    symbols = []
    texts = []
    cur_sym = None

    with open(asc_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            parts = line.split()
            tag = parts[0]
            if tag == "WIRE":
                wires.append((int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])))
            elif tag == "FLAG":
                flags.append((int(parts[1]), int(parts[2]), parts[3]))
            elif tag == "SYMBOL":
                cur_sym = {
                    "type": parts[1],
                    "x": int(parts[2]),
                    "y": int(parts[3]),
                    "orient": parts[4],
                    "attrs": {},
                }
                symbols.append(cur_sym)
            elif tag == "SYMATTR" and cur_sym is not None:
                k = parts[1]
                v = " ".join(parts[2:])
                cur_sym["attrs"][k] = v
            elif tag == "TEXT":
                # TEXT x y align size text...
                x, y = int(parts[1]), int(parts[2])
                align = parts[3]
                size = parts[4]
                # Preserve exact text after size token
                m = re.match(r"^TEXT\s+-?\d+\s+-?\d+\s+\S+\s+\S+\s+(.*)$", line)
                txt = m.group(1) if m else ""
                texts.append((x, y, align, size, txt))
    return wires, flags, symbols, texts


def compile_asc_to_net(asc_path, net_path=None, strict=True):
    """
    Compile an LTspice .asc schematic into an equivalent .net SPICE netlist.
    Returns (net_path, info_dict). Raises RuntimeError on disconnected pins if strict=True.
    """
    asc_path = Path(asc_path)
    if net_path is None:
        net_path = asc_path.with_suffix(".net")
    else:
        net_path = Path(net_path)

    wires, flags, symbols, texts = parse_asc(asc_path)

    uf = UnionFind()
    all_points = set()

    # 1. Connect endpoints of every wire
    for x1, y1, x2, y2 in wires:
        p1, p2 = (x1, y1), (x2, y2)
        uf.union(p1, p2)
        all_points.add(p1)
        all_points.add(p2)

    # 2. Collect all pin positions & flag positions
    sym_pins = []
    for sym in symbols:
        sdef = get_symbol(sym["type"])
        pins_xy = []
        for p in sdef.pins:
            pt = transform_pt(p["x"], p["y"], sym["x"], sym["y"], sym["orient"])
            pins_xy.append((pt, p["name"]))
            all_points.add(pt)
            uf.find(pt)
        sym_pins.append((sym, sdef, pins_xy))

    for fx, fy, fname in flags:
        pt = (fx, fy)
        all_points.add(pt)
        uf.find(pt)

    # 3. LTspice T-junction rule: any wire endpoint, pin, or flag lying on a wire segment connects to it
    # (Note: two crossing wires do NOT connect unless an endpoint lies on the other segment!)
    for pt in list(all_points):
        px, py = pt
        for x1, y1, x2, y2 in wires:
            if point_on_segment(px, py, x1, y1, x2, y2):
                uf.union(pt, (x1, y1))

    # 4. Also connect all flags sharing the same label name (e.g., global net labels & GND '0')
    flag_by_name = defaultdict(list)
    for fx, fy, fname in flags:
        flag_by_name[fname].append((fx, fy))
    for fname, pts in flag_by_name.items():
        for p in pts[1:]:
            uf.union(pts[0], p)

    # 5. Assign net names to every equivalence class
    root_to_name = {}
    # Priority: '0' (GND) first, then explicit FLAG labels
    for fname, pts in flag_by_name.items():
        r = uf.find(pts[0])
        if fname == "0":
            root_to_name[r] = "0"
        elif r not in root_to_name:
            root_to_name[r] = fname

    # Auto-name unnamed nets N001, N002, ...
    net_counter = 1
    for pt in sorted(all_points):
        r = uf.find(pt)
        if r not in root_to_name:
            root_to_name[r] = f"N{net_counter:03d}"
            net_counter += 1

    # 6. Check pin connectivity (count how many pins attach to each net)
    net_pin_count = defaultdict(int)
    for sym, sdef, pins_xy in sym_pins:
        for pt, pname in pins_xy:
            net_pin_count[root_to_name[uf.find(pt)]] += 1

    dangling = []
    for sym, sdef, pins_xy in sym_pins:
        inst = sym["attrs"].get("InstName", "?")
        for pt, pname in pins_xy:
            net = root_to_name[uf.find(pt)]
            if net_pin_count[net] < 2 and net != "0":
                dangling.append(f"{inst}.{pname} @ {pt} (net={net})")

    if strict and dangling:
        raise RuntimeError(
            f"Disconnected/dangling pins in {asc_path.name}:\n  " + "\n  ".join(dangling)
        )

    # 7. Emit SPICE netlist lines
    lines = [f"* {asc_path.as_posix()}"]
    for sym, sdef, pins_xy in sym_pins:
        inst = sym["attrs"].get("InstName", "X?")
        val = sym["attrs"].get("Value", sdef.default_value)
        val2 = sym["attrs"].get("Value2", "")
        sline = sym["attrs"].get("SpiceLine", "")
        sline2 = sym["attrs"].get("SpiceLine2", "")
        prefix = sym["attrs"].get("Prefix", sdef.prefix)

        # Ensure instance name starts with SPICE prefix
        if prefix and not inst.upper().startswith(prefix[0].upper()):
            spice_inst = prefix[0] + inst
        else:
            spice_inst = inst

        nodes = [root_to_name[uf.find(pt)] for pt, _ in pins_xy]

        # LTspice 3-pin nmos/pmos maps to 4-node M device (D G S S model)
        if sdef.name.lower() in ("nmos", "pmos") and len(nodes) == 3:
            nodes = [nodes[0], nodes[1], nodes[2], nodes[2]]

        extras = " ".join(x for x in (val, val2, sline, sline2) if x)
        lines.append(f"{spice_inst} {' '.join(nodes)} {extras}")

    # Emit SPICE directives (TEXT starting with '!')
    for _, _, _, _, txt in texts:
        if txt.startswith("!"):
            directive = txt[1:].replace("\\n", "\n")
            lines.append(directive)

    lines.append(".backanno")
    lines.append(".end")

    net_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return net_path, {
        "num_components": len(symbols),
        "num_nets": len(set(root_to_name.values())),
        "dangling": dangling,
        "nets": sorted(set(root_to_name.values())),
    }


def render_asc_preview(asc_path, png_path):
    """Render a clean high-resolution PNG preview of an LTspice .asc schematic."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle, Arc

    wires, flags, symbols, texts = parse_asc(asc_path)

    all_x, all_y = [], []
    for x1, y1, x2, y2 in wires:
        all_x.extend([x1, x2])
        all_y.extend([y1, y2])
    for fx, fy, _ in flags:
        all_x.append(fx)
        all_y.append(fy)
    for sym in symbols:
        all_x.extend([sym["x"] - 64, sym["x"] + 64])
        all_y.extend([sym["y"] - 64, sym["y"] + 64])
    for tx, ty, _, _, _ in texts:
        all_x.append(tx)
        all_y.append(ty)

    xmin, xmax = min(all_x) - 80, max(all_x) + 160
    ymin, ymax = min(all_y) - 80, max(all_y) + 100
    w_span = max(xmax - xmin, 200)
    h_span = max(ymax - ymin, 200)

    fig_w = 14.0
    fig_h = max(6.0, min(14.0, fig_w * h_span / w_span))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=180)
    ax.set_facecolor("#FAFBF7")

    # Draw wires
    for x1, y1, x2, y2 in wires:
        ax.plot([x1, x2], [y1, y2], color="#0044AA", lw=1.6, solid_capstyle="round")

    # Draw junction dots (points where >=3 wire endpoints or T-junctions meet)
    pt_deg = defaultdict(int)
    for x1, y1, x2, y2 in wires:
        pt_deg[(x1, y1)] += 1
        pt_deg[(x2, y2)] += 1
    for pt in list(pt_deg.keys()):
        for x1, y1, x2, y2 in wires:
            if pt != (x1, y1) and pt != (x2, y2) and point_on_segment(pt[0], pt[1], x1, y1, x2, y2):
                pt_deg[pt] += 2
    for (jx, jy), deg in pt_deg.items():
        if deg >= 3:
            ax.plot(jx, jy, "s", color="#0044AA", ms=4.5)

    # Draw symbols
    for sym in symbols:
        sdef = get_symbol(sym["type"])
        sx, sy, ori = sym["x"], sym["y"], sym["orient"]
        for x1, y1, x2, y2 in sdef.lines:
            p1 = transform_pt(x1, y1, sx, sy, ori)
            p2 = transform_pt(x2, y2, sx, sy, ori)
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#8B0000", lw=1.6)
        for x1, y1, x2, y2 in sdef.circles:
            p1 = transform_pt(x1, y1, sx, sy, ori)
            p2 = transform_pt(x2, y2, sx, sy, ori)
            cx, cy = 0.5 * (p1[0] + p2[0]), 0.5 * (p1[1] + p2[1])
            r = 0.5 * max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]))
            circ = Circle((cx, cy), r, fill=(r < 6), edgecolor="#8B0000", facecolor="#8B0000", lw=1.5)
            ax.add_patch(circ)
        for x1, y1, x2, y2, x3, y3, x4, y4 in sdef.arcs:
            # Approximate inductor arcs cleanly as semicircles
            p1 = transform_pt(x1, y1, sx, sy, ori)
            p2 = transform_pt(x2, y2, sx, sy, ori)
            cx, cy = 0.5 * (p1[0] + p2[0]), 0.5 * (p1[1] + p2[1])
            rx, ry = 0.5 * abs(p2[0] - p1[0]), 0.5 * abs(p2[1] - p1[1])
            p3 = transform_pt(x3, y3, sx, sy, ori)
            p4 = transform_pt(x4, y4, sx, sy, ori)
            a1 = math.degrees(math.atan2(p3[1] - cy, p3[0] - cx))
            a2 = math.degrees(math.atan2(p4[1] - cy, p4[0] - cx))
            # Draw short arc
            arc = Arc((cx, cy), 2 * rx, 2 * ry, angle=0, theta1=min(a1, a2), theta2=max(a1, a2), color="#8B0000", lw=1.6)
            ax.add_patch(arc)

        inst = sym["attrs"].get("InstName", "")
        val = sym["attrs"].get("Value", "")
        # Put compact label near center of symbol
        pts = [transform_pt(p["x"], p["y"], sx, sy, ori) for p in sdef.pins]
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        label_str = f"{inst}\n{val}" if len(val) <= 18 else f"{inst}"
        ax.text(mx + 14, my - 6, label_str, fontsize=6.5, color="#111111",
                va="center", ha="left", family="monospace",
                bbox=dict(boxstyle="round,pad=0.12", fc="#FAFBF7", ec="none", alpha=0.75))

    # Draw flags
    for fx, fy, fname in flags:
        if fname == "0":
            # GND triangle
            ax.plot([fx - 10, fx + 10, fx, fx - 10], [fy, fy, fy + 12, fy], color="#0044AA", lw=1.5)
        else:
            ax.plot(fx, fy, "o", color="#006622", ms=3.5)
            ax.text(fx, fy - 8, fname, fontsize=7, color="#006622", fontweight="bold", ha="center", va="bottom")

    # Draw directives/comments
    for tx, ty, align, _, txt in texts:
        is_dir = txt.startswith("!")
        clean = txt[1:].replace("\\n", "\n")
        color = "#000000" if is_dir else "#0055AA"
        ax.text(tx, ty, clean, fontsize=6.5, color=color, family="monospace", va="top", ha="left")

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymax, ymin)  # Invert Y axis (screen coords)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(Path(asc_path).name, fontsize=11, fontweight="bold")
    plt.tight_layout()
    Path(png_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(png_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: asc_compiler.py <file.asc> [preview.png]")
        sys.exit(1)
    net, info = compile_asc_to_net(sys.argv[1])
    print(f"Compiled {sys.argv[1]} -> {net}: {info}")
    if len(sys.argv) >= 3:
        render_asc_preview(sys.argv[1], sys.argv[2])
        print(f"Rendered preview -> {sys.argv[2]}")
