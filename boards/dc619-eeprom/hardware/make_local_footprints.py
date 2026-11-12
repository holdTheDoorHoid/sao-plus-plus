#!/usr/bin/env python3
"""Write dc619-eeprom-local.pretty: the one part this board needs that the shared SAO++ library does not have yet.

Run with system Python from the repo root:  python3 boards/dc619-eeprom/hardware/make_local_footprints.py

The land pattern is KiCad's stock Package_TO_SOT_SMD:SOT-23-5, copied unchanged. This script only adds the SAOPP_ID /
MPN / LCSC fields the SAO++ build expects and drops the 3D-model link (it points into KiCad's own install).
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STOCK = Path.home() / ".local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints"
OUT = HERE / "dc619-eeprom-local.pretty"

PARTS = {
    "SOT-23-5": (STOCK / "Package_TO_SOT_SMD.pretty" / "SOT-23-5.kicad_mod",
                 {"SAOPP_ID": "SAOPP-EE-01", "MPN": "AD24C02", "LCSC": "C5125083"}),
}


def prop(k, v):
    return (f'\t(property "{k}" "{v}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.8 0.8)\n\t\t\t\t(thickness 0.12)\n\t\t\t)\n\t\t)\n\t)\n')


def drop_block(txt, opener):
    """Remove every top-level '(opener ...)' block."""
    while True:
        m = re.search(r"\n\t\(" + opener + r"[ \n]", txt)
        if not m:
            return txt
        i, depth = m.start() + 2, 0
        for j in range(i, len(txt)):
            depth += txt[j] == "("
            depth -= txt[j] == ")"
            if depth == 0:
                txt = txt[:m.start()] + txt[j + 1:]
                break


OUT.mkdir(exist_ok=True)
for name, (src, fields) in PARTS.items():
    txt = src.read_text()
    txt = drop_block(txt, "model")
    i = txt.index('\n\t(property "Reference"')
    txt = txt[:i + 1] + "".join(prop(k, v) for k, v in fields.items()) + txt[i + 1:]
    assert "(attr smd)" in txt, name
    (OUT / f"{name}.kicad_mod").write_text(txt)
    print("wrote", OUT.name + "/" + name)
