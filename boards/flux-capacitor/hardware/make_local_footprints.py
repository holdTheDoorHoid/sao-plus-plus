#!/usr/bin/env python3
"""Write flux-capacitor-local.pretty: the parts this board needs that the shared SAO++ library does not have.

Run with system Python from the repo root:  python3 boards/flux-capacitor/hardware/make_local_footprints.py

Every land pattern is copied unchanged:
  SO08-EIAJ, 2X3_SMD_PAD  from boards/knight-rider/hardware/knight-rider-local.pretty. They are SparkFun's Eagle
                          packages of the same names, and this maker's own Eagle file (original/attiny45.brd) uses those
                          same SparkFun packages: pad for pad identical (checked: 0.61 x 2.21 mm pads at 1.27 mm pitch,
                          rows 6.73 mm apart; six 1.778 mm square pads on a 2.54 mm grid).
  D_SOD-523               from knight-rider-local.pretty (itself KiCad's stock Diode_SMD:D_SOD-523), the SAOPP-D-01 diode.
  LED_1206_3216Metric     KiCad's stock LED_SMD:LED_1206_3216Metric (pad 1 = cathode). The maker's Eagle "SML1206"
                          pads (1.5 x 1.5 mm, 3.5 mm apart) are a generic hand-solder pattern; the stock IPC pattern is
                          used for the front LEDs, centred where the maker had each LED.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
KR = HERE.parent.parent / "knight-rider" / "hardware" / "knight-rider-local.pretty"
STOCK = Path("/home/hoid/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints")
OUT = HERE / "flux-capacitor-local.pretty"

PARTS = {
    "SO08-EIAJ": KR / "SO08-EIAJ.kicad_mod",
    "2X3_SMD_PAD": KR / "2X3_SMD_PAD.kicad_mod",
    "D_SOD-523": KR / "D_SOD-523.kicad_mod",
    "LED_1206_3216Metric": STOCK / "LED_SMD.pretty" / "LED_1206_3216Metric.kicad_mod",
}
FIELDS = ("SAOPP_ID", "MPN", "LCSC")


def prop(k):
    return (f'\t(property "{k}" ""\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.8 0.8)\n\t\t\t\t(thickness 0.12)\n\t\t\t)\n\t\t)\n\t)\n')


def drop_block(txt, opener):
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
for name, src in PARTS.items():
    txt = src.read_text()
    txt = re.sub(r'^\(footprint "[^"]*"', f'(footprint "{name}"', txt, count=1)
    txt = drop_block(txt, "model")
    i = txt.index('\n\t(property "Reference"')
    txt = txt[:i + 1] + "".join(prop(k) for k in FIELDS if f'(property "{k}"' not in txt) + txt[i + 1:]
    if name == "2X3_SMD_PAD":       # Knight Rider drew a 5.5 x 8 mm keep-clear box; this board draws it 0.24 mm round the pads
        txt = txt.replace("\t\t(start -2.75 -4.0)\n\t\t(end 2.75 4.0)", "\t\t(start -2.4 -3.7)\n\t\t(end 2.4 3.7)")
        assert "(start -2.4 -3.7)" in txt and "(end 2.4 3.7)" in txt
    (OUT / f"{name}.kicad_mod").write_text(txt)
    print("wrote", OUT.name + "/" + name, "from", src.parent.name)
