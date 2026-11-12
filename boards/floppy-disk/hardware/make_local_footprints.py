#!/usr/bin/env python3
"""Write floppy-disk-local.pretty: the parts this board needs that the shared SAO++ library does not have (yet).

Run with system Python from the repo root:  python3 boards/floppy-disk/hardware/make_local_footprints.py

Every land pattern is KiCad 10's stock footprint, copied unchanged (Uri Shaked's 2020 board used the same stock
SOIC-8 and solder-jumper footprints). This script only adds the SAOPP_ID / MPN / LCSC fields the SAO++ build needs
and drops the 3D-model links.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STOCK = Path.home() / ".local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints"
OUT = HERE / "floppy-disk-local.pretty"

# name: (stock library, fields)
PARTS = {
    "SOT-23-5": ("Package_TO_SOT_SMD", {"SAOPP_ID": "SAOPP-EE-01", "MPN": "AD24C02", "LCSC": "C5125083"}),
    "SOIC-8_3.9x4.9mm_P1.27mm": ("Package_SO", {"SAOPP_ID": "", "MPN": "M24512-RMN6TP", "LCSC": "C79991"}),
    "D_SOD-523": ("Diode_SMD", {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}),
    "SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm": ("Jumper", {"SAOPP_ID": "", "MPN": "none: PCB copper, nothing fitted", "LCSC": ""}),
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
for name, (lib, fields) in PARTS.items():
    src = STOCK / f"{lib}.pretty" / f"{name}.kicad_mod"
    txt = drop_block(src.read_text(), "model")
    for k in fields:
        assert f'(property "{k}"' not in txt, (name, k)
    i = txt.index('\n\t(property "Reference"')
    txt = txt[:i + 1] + "".join(prop(k, v) for k, v in fields.items()) + txt[i + 1:]
    (OUT / f"{name}.kicad_mod").write_text(txt)
    print("wrote", OUT.name + "/" + name, "from KiCad stock", lib)
