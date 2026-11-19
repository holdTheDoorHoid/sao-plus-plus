#!/usr/bin/env python3
"""Copy the two land patterns this board needs that the shared library does not have into duck-bath-local.pretty.

  LED_D5.0mm-4_RGB_single-side   the maker's own footprint (original/duckbath/footprints.pretty/), land pattern
                                 unchanged: four 0.85 mm holes on 1.27 mm pitch, pads on the back only. Edits: the
                                 reference text moved from the front silkscreen to the front fab layer (the front is
                                 art), and the SAOPP_ID / MPN / LCSC fields added.
  R_0603_1608Metric              the shared SAOPP_R_0603_1608Metric land pattern (lib/sao-plus-plus.pretty), copied
                                 unchanged, for the 100 ohm resistors (a different value, so a different local part).
Run: python3 boards/duck-bath/hardware/make_local_footprints.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUT = HERE / "duck-bath-local.pretty"
OUT.mkdir(exist_ok=True)


def with_fields(txt, fields):
    props = "".join(f'\t(property "{k}" "{v}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n'
                    f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n'
                    for k, v in fields.items())
    i = txt.index('\n\t(property "Reference"')
    return txt[:i + 1] + props + txt[i + 1:]


led = (HERE / ".." / "original" / "duckbath" / "footprints.pretty" / "LED_D5.0mm-4_RGB_single-side.kicad_mod").read_text()
led = re.sub(r'\n\t\(property "LCSC" "".*?\n\t\)\n', "\n", led, count=1, flags=re.S)       # replaced by the fields below
i = led.index('(property "Reference"')
j = led.index('(layer "F.SilkS")', i)
led = led[:j] + '(layer "F.Fab")' + led[j + len('(layer "F.SilkS")'):]
assert '"F.SilkS"' not in led, "front silkscreen left in the LED footprint"
led = re.sub(r'\n\t\(property "Description" ".*?\n\t\)\n', "\n", led, count=1, flags=re.S)   # the symbol has none
led = led.replace("(size 0.7 0.7)", "(size 0.8 0.8)")   # the "B G + R" leg labels: up to the house minimum text size
(OUT / "LED_D5.0mm-4_RGB_single-side.kicad_mod").write_text(
    with_fields(led, {"SAOPP_ID": "", "MPN": "5 mm RGB LED, common anode", "LCSC": ""}))

r = (ROOT / "lib" / "sao-plus-plus.pretty" / "SAOPP_R_0603_1608Metric.kicad_mod").read_text()
r = r.replace('(footprint "SAOPP_R_0603_1608Metric"', '(footprint "R_0603_1608Metric"', 1)
(OUT / "R_0603_1608Metric.kicad_mod").write_text(r)
for f in sorted(OUT.iterdir()):
    print(f.name, len(re.findall(r"\(pad ", f.read_text())), "pads")
