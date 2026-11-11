#!/usr/bin/env python3
"""Write knight-rider-local.pretty: the parts this board needs that the shared SAO++ library does not have.

Run with system Python from the repo root:  python3 boards/knight-rider/hardware/make_local_footprints.py

Every land pattern is copied unchanged. Four come from the maker's own 2024 KiCad 8 library
(original/KiCad8/kitt_0805.pretty) and one from KiCad's stock library. This script only adds what the SAO++ build
needs on top: the SAOPP_ID / MPN / LCSC fields, a courtyard where the maker's footprint had none (drawn round the
pads and body, not used for anything but spacing checks), and it drops 3D-model links that point at KiCad 8 paths.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAKER = HERE.parent / "original" / "KiCad8" / "kitt_0805.pretty"
STOCK = Path("/home/hoid/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints")
OUT = HERE / "knight-rider-local.pretty"

# name: (source file, fields, courtyard half-size (x, y) or None if the source already has one)
PARTS = {
    "SO08-EIAJ": (MAKER / "SO08-EIAJ.kicad_mod",
                  {"SAOPP_ID": "", "MPN": "ATTINY85V-10SU", "LCSC": ""}, (2.75, 4.75)),
    "2X3_SMD_PAD": (MAKER / "2X3_SMD_PAD.kicad_mod",
                    {"SAOPP_ID": "", "MPN": "none: bare pads, nothing fitted", "LCSC": ""}, (2.75, 4.0)),
    "TACTILE-SWITCH-1101NE": (MAKER / "TACTILE-SWITCH-1101NE.kicad_mod",
                              {"SAOPP_ID": "", "MPN": "SparkFun COM-08229 class (6 x 3.5 mm, 2 pads at 6.3 mm)", "LCSC": ""}, (4.55, 2.0)),
    "LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder": (MAKER / "LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder.kicad_mod",
                                                      {"SAOPP_ID": "", "MPN": "LTST-C191KRKT", "LCSC": ""}, None),
    "D_SOD-523": (STOCK / "Diode_SMD.pretty" / "D_SOD-523.kicad_mod",
                  {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": ""}, None),
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
for name, (src, fields, cy) in PARTS.items():
    txt = src.read_text()
    txt = re.sub(r'^\(footprint "[^"]*"', f'(footprint "{name}"', txt, count=1)
    txt = drop_block(txt, "model")
    txt = re.sub(r"\(property \"Description\" \"[^\"]*\"", "(property \"Description\" \"\"", txt)
    for k in fields:
        txt = re.sub(r'\n\t\(property "' + k + r'" "[^"]*"', "\n\t(property \"" + k + "\" \"\"", txt)   # (none of the sources has these)
    i = txt.index('\n\t(property "Reference"')
    txt = txt[:i + 1] + "".join(prop(k, v) for k, v in fields.items()) + txt[i + 1:]
    if cy:
        assert "F.CrtYd" not in txt, name
        x, y = cy
        rect = (f'\t(fp_rect\n\t\t(start {-x} {-y})\n\t\t(end {x} {y})\n\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n'
                f'\t\t(fill no)\n\t\t(layer "F.CrtYd")\n\t)\n')
        k = txt.rindex(")")
        txt = txt[:k] + rect + txt[k:]
    if "(attr smd)" not in txt:
        i = txt.index("\n\t(fp_")
        txt = txt[:i + 1] + "\t(attr smd)\n" + txt[i + 1:]
    (OUT / f"{name}.kicad_mod").write_text(txt)
    print("wrote", OUT.name + "/" + name, "from", src.parent.name)
