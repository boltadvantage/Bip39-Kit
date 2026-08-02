#!/usr/bin/env python3
"""
Generate printable numbered tabs (0000-2047) for drawing BIP39 words from a bag.

Each tab is a disc carrying a four-digit number, produced as TWO bodies:

  * base   -- the full disc
  * digits -- rectangular prisms occupying only the top DIGIT_DEPTH mm

Load a plate, assign the second body to your other filament, print at 100%
infill. Because the digit body sits inside the disc rather than proud of it or
cut into it, every tab has identical geometry -- only the pigment differs. That
is what keeps the tabs uniform in mass: embossing makes `1111` and `8888` differ
by a whole glyph volume, whereas a colour swap makes them differ only by the
density delta between two filaments, roughly 2% of a much smaller number.

Digits are drawn as seven-segment shapes, not font glyphs. Every segment is a
plain rectangle, so the enclosed areas in 0/4/6/8/9 are wide rectangular gaps
that cannot bridge over or fail to fill -- the failure mode a real typeface
would give you at this size.

Numbers are assigned to plate positions in a SHUFFLED order, from a fixed seed.
Print quality drifts over a run this long -- spool changes, nozzle wear, plate
position -- so printing 0000-0063 together would make that drift line up with a
contiguous block of the wordlist. Shuffling decorrelates physical variation from
index. The seed is fixed so the whole run is reproducible and auditable.

  ./make-tabs.py            write every plate
  ./make-tabs.py 3          write only plate 3 (for a test print)
"""
import math
import os
import random
import sys
import zipfile

# ---- geometry, millimetres -------------------------------------------------
DIAM        = 16.0     # tab diameter
THICK       = 2.0      # tab thickness: rigid enough not to bend, thin enough to be cheap
DIGIT_DEPTH = 0.6      # top layers that change colour (3 layers at 0.2mm)
SEG_N       = 32       # facets around the disc

# Stroke is 0.8 mm = exactly two 0.4 mm extrusions, so segments print as clean
# double walls on any slicer rather than relying on variable-width extrusion.
# That leaves 1.4 mm counters inside 0/4/6/8/9 -- roughly 3.5 extrusions wide,
# far too big to bridge over.
DW, DH, DS  = 3.0, 5.0, 0.8     # digit width, height, stroke thickness
DGAP        = 0.6               # space between digits

# 12 x 12 at 19 mm pitch is 228 x 228 mm, which sits inside a Bambu P1S/X1
# (256 x 256) with ~14 mm of margin all round. Drop to 8 x 8 for a 220 mm bed
# such as an Ender or Prusa MK-series.
COLS, ROWS  = 12, 12            # tabs per plate
PITCH       = 19.0              # centre-to-centre spacing
SEED        = 20260802

COLOR_BASE   = "#2E4A62FF"
COLOR_DIGITS = "#F2C14EFF"

# Seven-segment map.  a=top  b=upper-right  c=lower-right
#                     d=bottom  e=lower-left  f=upper-left  g=middle
SEGMENTS = {
    "0": "abcdef", "1": "bc",    "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd",  "6": "afgedc", "7": "abc",  "8": "abcdefg", "9": "abcdfg",
}


class Mesh:
    """Triangle soup with consistent outward winding."""

    def __init__(self):
        self.v = []
        self.t = []

    def _add(self, xyz):
        self.v.append(xyz)
        return len(self.v) - 1

    def box(self, x0, y0, z0, x1, y1, z1):
        i = [self._add((x, y, z))
             for x, y, z in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        for a, b, c in ((0, 2, 1), (0, 3, 2),      # bottom, normal -z
                        (4, 5, 6), (4, 6, 7),      # top, normal +z
                        (0, 1, 5), (0, 5, 4),      # -y
                        (1, 2, 6), (1, 6, 5),      # +x
                        (2, 3, 7), (2, 7, 6),      # +y
                        (3, 0, 4), (3, 4, 7)):     # -x
            self.t.append((i[a], i[b], i[c]))

    def cylinder(self, cx, cy, r, z0, z1, n=SEG_N):
        bc = self._add((cx, cy, z0))
        tc = self._add((cx, cy, z1))
        ring_b, ring_t = [], []
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            ring_b.append(self._add((x, y, z0)))
            ring_t.append(self._add((x, y, z1)))
        for k in range(n):
            j = (k + 1) % n
            self.t.append((bc, ring_b[j], ring_b[k]))          # bottom, faces -z
            self.t.append((tc, ring_t[k], ring_t[j]))          # top, faces +z
            self.t.append((ring_b[k], ring_b[j], ring_t[j]))   # wall
            self.t.append((ring_b[k], ring_t[j], ring_t[k]))


def digit(mesh, ch, x, y, z0, z1):
    """One seven-segment digit with its lower-left corner at (x, y)."""
    on = SEGMENTS[ch]
    h2 = DH / 2.0
    bars = {
        "a": (x + DS, y + DH - DS, x + DW - DS, y + DH),
        "g": (x + DS, y + h2 - DS / 2, x + DW - DS, y + h2 + DS / 2),
        "d": (x + DS, y, x + DW - DS, y + DS),
        "f": (x, y + h2 - DS / 2, x + DS, y + DH),
        "b": (x + DW - DS, y + h2 - DS / 2, x + DW, y + DH),
        "e": (x, y, x + DS, y + h2 + DS / 2),
        "c": (x + DW - DS, y, x + DW, y + h2 + DS / 2),
    }
    for s in on:
        x0, y0, x1, y1 = bars[s]
        mesh.box(x0, y0, z0, x1, y1, z1)


def number(mesh, value, cx, cy, z0, z1):
    text = f"{value:04d}"
    total_w = 4 * DW + 3 * DGAP
    x = cx - total_w / 2.0
    y = cy - DH / 2.0
    for ch in text:
        digit(mesh, ch, x, y, z0, z1)
        x += DW + DGAP


def write_3mf(path, bodies):
    """bodies: [(name, colour, Mesh)] -> a 3MF the slicer opens as separate objects."""
    parts = []
    for n, (name, color, m) in enumerate(bodies):
        verts = "".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in m.v)
        tris = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.t)
        parts.append(f'<object id="{n + 2}" type="model" pid="1" pindex="{n}" name="{name}">'
                     f'<mesh><vertices>{verts}</vertices>'
                     f'<triangles>{tris}</triangles></mesh></object>')
    items = "".join(f'<item objectid="{n + 2}"/>' for n in range(len(bodies)))
    mats = "".join(f'<base name="{name}" displaycolor="{color}"/>'
                   for name, color, _ in bodies)

    model = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources><basematerials id="1">{mats}</basematerials>'
             f'{"".join(parts)}</resources>'
             f'<build>{items}</build></model>')

    ctypes = ('<?xml version="1.0" encoding="UTF-8"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
              'relationships+xml"/><Default Extension="model" ContentType="application/'
              'vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.'
            'com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')

    # Fixed timestamps so the output is byte-reproducible: regenerate on any
    # machine and the hashes match, which is the point of the fixed seed.
    stamp = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in (("[Content_Types].xml", ctypes),
                           ("_rels/.rels", rels),
                           ("3D/3dmodel.model", model)):
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    per_plate = COLS * ROWS
    plates = -(-2048 // per_plate)

    order = list(range(2048))
    random.Random(SEED).shuffle(order)

    only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    manifest = []

    for p in range(plates):
        chunk = order[p * per_plate:(p + 1) * per_plate]
        if only is not None and p + 1 != only:
            manifest.extend((p + 1, s, v) for s, v in enumerate(chunk, 1))
            continue

        base, digits = Mesh(), Mesh()
        for slot, value in enumerate(chunk):
            cx = (slot % COLS) * PITCH + PITCH / 2
            cy = (slot // COLS) * PITCH + PITCH / 2
            base.cylinder(cx, cy, DIAM / 2, 0.0, THICK)
            number(digits, value, cx, cy, THICK - DIGIT_DEPTH, THICK)
            manifest.append((p + 1, slot + 1, value))

        path = os.path.join(here, f"tabs-plate-{p + 1:02d}.3mf")
        write_3mf(path, [("base", COLOR_BASE, base), ("digits", COLOR_DIGITS, digits)])
        print(f"  {os.path.basename(path)}  {len(chunk)} tabs  "
              f"{len(base.t) + len(digits.t):,} triangles  "
              f"{os.path.getsize(path) / 1024:.0f} KB")

    manifest.sort(key=lambda r: r[2])
    with open(os.path.join(here, "manifest.csv"), "w") as f:
        f.write("number,plate,slot\n")
        for plate, slot, value in manifest:
            f.write(f"{value:04d},{plate},{slot}\n")
    print(f"\n  manifest.csv  2048 rows (sorted by number, so you can tick them off)")


if __name__ == "__main__":
    main()
