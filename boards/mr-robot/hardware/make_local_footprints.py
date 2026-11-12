#!/usr/bin/env python3
"""Copy the three land patterns this board needs that the shared library does not have into mr-robot-local.pretty.

  KMTG-1102   the maker's own speaker footprint (original/KiCad8/saomr.pretty/KMTG-1102.kicad_mod). Land pattern
              unchanged: two 3 x 3 mm pads 14 mm apart, body 11 x 9 mm on the fab layer. Edits: the pads are
              renamed "P$1" -> "1" and "P$2" -> "2" (KiCad symbols need plain pin numbers), and a courtyard rectangle
              round pads and body is added (the maker's had none;
              DRC needs one), and the SAOPP_ID / MPN / LCSC fields.
  SOT-23      KiCad's stock Package_TO_SOT_SMD:SOT-23 (the NPN transistor), land pattern unchanged; fields added.
  D_SOD-523   boards/knight-rider/hardware/knight-rider-local.pretty/D_SOD-523 (itself KiCad's stock
              Diode_SMD:D_SOD-523), the shared RB751S40T1G diode, copied unchanged.
Run: python3 boards/mr-robot/hardware/make_local_footprints.py
"""
import glob
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "mr-robot-local.pretty"
OUT.mkdir(exist_ok=True)
STOCK = Path(sorted(glob.glob("/home/hoid/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/*/files/footprints"))[0])

spk = (HERE / ".." / "original" / "KiCad8" / "saomr.pretty" / "KMTG-1102.kicad_mod").read_text()
assert spk.count('(pad "P$1"') == 1 and spk.count('(pad "P$2"') == 1
spk = spk.replace('(pad "P$1"', '(pad "1"').replace('(pad "P$2"', '(pad "2"')
crt = ('\t(fp_rect\n\t\t(start -8.75 -4.75)\n\t\t(end 8.75 4.75)\n\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n'
       '\t\t(fill no)\n\t\t(layer "F.CrtYd")\n\t)\n')
i = spk.index("\t(pad ")
spk = spk[:i] + crt + spk[i:]


def with_fields(txt, fields):
    """Add the SAOPP_ID / MPN / LCSC fields the build script fills in (metadata only)."""
    props = "".join(f'\t(property "{k}" "{v}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n'
                    f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n'
                    for k, v in fields.items())
    i = txt.index('\n\t(property "Reference"')
    return txt[:i + 1] + props + txt[i + 1:]


(OUT / "KMTG-1102.kicad_mod").write_text(with_fields(spk, {"SAOPP_ID": "", "MPN": "KMTG1102-A1", "LCSC": ""}))
sot = (STOCK / "Package_TO_SOT_SMD.pretty" / "SOT-23.kicad_mod").read_text()
(OUT / "SOT-23.kicad_mod").write_text(with_fields(sot, {"SAOPP_ID": "", "MPN": "BC847B,215", "LCSC": ""}))
kr = HERE / ".." / ".." / "knight-rider" / "hardware" / "knight-rider-local.pretty" / "D_SOD-523.kicad_mod"
(OUT / "D_SOD-523.kicad_mod").write_text(kr.read_text())
for f in sorted(OUT.iterdir()):
    print(f.name, len(re.findall(r"\(pad ", f.read_text())), "pads")
