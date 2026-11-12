#!/usr/bin/env python3
"""Write sao-modem-local.pretty: the land patterns this board needs that the shared SAO++ library does not have.

Run with system Python from the repo root:  python3 boards/sao-modem/hardware/make_local_footprints.py

All four are KiCad 10 stock footprints, copied unchanged (the SOIC-8, the 0603 resistor and the 2 mm test pad are the
ones the maker used). The script only adds the SAOPP_ID / MPN / LCSC fields the SAO++ build expects.
"""
import glob
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_found = glob.glob(os.path.expanduser("~/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/*/stable/active/files/footprints"))
assert _found, "KiCad's stock footprint library (flatpak) was not found"
STOCK = Path(_found[0])
OUT = HERE / "sao-modem-local.pretty"

PARTS = {
    "SOIC-8_3.9x4.9mm_P1.27mm": STOCK / "Package_SO.pretty" / "SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod",
    "R_0603_1608Metric": STOCK / "Resistor_SMD.pretty" / "R_0603_1608Metric.kicad_mod",
    "D_SOD-523": STOCK / "Diode_SMD.pretty" / "D_SOD-523.kicad_mod",
    "TestPoint_Pad_D2.0mm": STOCK / "TestPoint.pretty" / "TestPoint_Pad_D2.0mm.kicad_mod",
}
FIELDS = ("SAOPP_ID", "MPN", "LCSC")          # filled in per part by build_board.py from parts_local.py


def prop(k):
    return (f'\t(property "{k}" ""\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.8 0.8)\n\t\t\t\t(thickness 0.12)\n\t\t\t)\n\t\t)\n\t)\n')


OUT.mkdir(exist_ok=True)
for name, src in PARTS.items():
    txt = src.read_text()
    assert re.match(r'\(footprint "' + re.escape(name) + '"', txt), name
    assert not any(f'(property "{k}"' in txt for k in FIELDS), name
    i = txt.index('\n\t(property "Reference"')
    txt = txt[:i + 1] + "".join(prop(k) for k in FIELDS) + txt[i + 1:]
    (OUT / f"{name}.kicad_mod").write_text(txt)
    print("wrote", OUT.name + "/" + name)
