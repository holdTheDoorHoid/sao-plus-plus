#!/usr/bin/env python3
"""Write the one land pattern this board needs that the shared library does not have into eggplant-local.pretty.

  LED_Bicolour_0805   the maker's own "0805-DUALLED" package from his Eagle board (original/eggplant/eggplant.brd,
                      library darknet_parts_library), for his bicolour blue / red LED "PHBM2012QBDSURKC".
                      Land pattern unchanged: four 1.2 x 0.6 mm pads at x = +-0.9, y = +-0.475. Eagle's y axis
                      points up and KiCad's down, so every y is negated. His pad names become numbers (KiCad
                      symbols need plain pin numbers): AB -> 1 (blue anode), AR -> 2 (red anode), CB -> 3, CR -> 4.
                      Added: his 2.1 x 2.3 mm body outline (his layer 49) on the fab layer, a pin-1 mark, a courtyard
                      0.25 mm round pads and body, and the SAOPP_ID / MPN / LCSC fields.
The pad positions are read from the Eagle file here, not typed in.
Run: python3 boards/eggplant/hardware/make_local_footprints.py
"""
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "eggplant-local.pretty"
OUT.mkdir(exist_ok=True)
root = ET.parse(HERE / ".." / "original" / "eggplant" / "eggplant.brd").getroot()
pkg = [p for p in root.iter("package") if p.get("name") == "0805-DUALLED"][0]
NUM = {"AB": "1", "AR": "2", "CB": "3", "CR": "4"}
pads = []
for s in pkg.findall("smd"):
    x, y, dx, dy = (float(s.get(k)) for k in ("x", "y", "dx", "dy"))
    pads.append((NUM[s.get("name")], x, -y, dx, dy))
assert sorted(p[0] for p in pads) == ["1", "2", "3", "4"]
xmax = max(abs(p[1]) + p[3] / 2 for p in pads)
ymax = max(abs(p[2]) + p[4] / 2 for p in pads)
cx, cy = max(xmax, 1.05) + 0.25, max(ymax, 1.15) + 0.25


def prop(k, v, at="0 0 0", layer="F.Fab", hide=True):
    h = "\t\t(hide yes)\n" if hide else ""
    return (f'\t(property "{k}" "{v}"\n\t\t(at {at})\n\t\t(layer "{layer}")\n{h}'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')


def line(x1, y1, x2, y2, layer, w):
    return (f'\t(fp_line\n\t\t(start {x1} {y1})\n\t\t(end {x2} {y2})\n\t\t(stroke\n\t\t\t(width {w})\n\t\t\t(type solid)\n'
            f'\t\t)\n\t\t(layer "{layer}")\n\t)\n')


s = '(footprint "LED_Bicolour_0805"\n\t(version 20240108)\n\t(generator "saopp_eggplant")\n\t(layer "F.Cu")\n'
s += ('\t(descr "Bicolour blue/red 0805 LED, four pads, the maker\'s own land pattern (darknet_parts_library 0805-DUALLED, '
      'original/eggplant/eggplant.brd). 1 = blue anode (his AB), 2 = red anode (AR), 3 = blue cathode (CB), 4 = red cathode (CR).")\n')
s += prop("SAOPP_ID", "") + prop("MPN", "PHBM2012QBDSURKC") + prop("LCSC", "")
s += prop("Reference", "REF**", "0 -2.2 0", "F.SilkS", False) + prop("Value", "LED_Bicolour_0805", "0 2.2 0")
s += line(-1.05, -1.15, 1.05, -1.15, "F.Fab", 0.1) + line(1.05, -1.15, 1.05, 1.15, "F.Fab", 0.1)
s += line(1.05, 1.15, -1.05, 1.15, "F.Fab", 0.1) + line(-1.05, 1.15, -1.05, -1.15, "F.Fab", 0.1)
s += line(-1.3, -1.0, -1.3, 1.0, "F.Fab", 0.1)                        # anode side mark
for x1, y1, x2, y2 in ((-cx, -cy, cx, -cy), (cx, -cy, cx, cy), (cx, cy, -cx, cy), (-cx, cy, -cx, -cy)):
    s += line(round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3), "F.CrtYd", 0.05)
for num, x, y, dx, dy in sorted(pads):
    s += (f'\t(pad "{num}" smd rect\n\t\t(at {x} {y})\n\t\t(size {dx} {dy})\n'
          f'\t\t(layers "F.Cu" "F.Paste" "F.Mask")\n\t)\n')
s += ")\n"
(OUT / "LED_Bicolour_0805.kicad_mod").write_text(s)
print(sorted(pads), "courtyard", cx, cy)
