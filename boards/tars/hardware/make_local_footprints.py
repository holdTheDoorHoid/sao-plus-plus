#!/usr/bin/env python3
"""Copy the land patterns TARS needs that the shared library does not have into tars-local.pretty.

  ST7735S-160x80-13PIN   the maker's own display footprint (original/KiCad/TARS/TARS.pretty). Land pattern unchanged:
                         13 pads 4.0 x 0.4 mm at 0.7 mm pitch, where the display's ribbon is folded under the glass and
                         soldered; the glass outline (28 x 13.3 mm) is on Dwgs.User. Edits: a courtyard round the glass
                         (the maker's had none; DRC needs one) and the SAOPP_ID / MPN / LCSC fields.
  LED_0603_...HandSolder boards/knight-rider/hardware/knight-rider-local.pretty (itself KiCad's stock 0603 LED), the
                         red LTST-C191KRKT already checked for Knight Rider; copied unchanged. The maker's cue light used
                         the same stock land pattern.
  R_0603_1608Metric      KiCad's stock Resistor_SMD:R_0603_1608Metric, for the 11 ohm backlight resistor (no shared value
                         is close to 11 ohm). Land pattern unchanged; fields added.
  SOIC-14_3.9x8.7mm...   KiCad's stock Package_SO:SOIC-14_3.9x8.7mm_P1.27mm, the land pattern KiCad's own CAP1206-x-SL
                         symbol names. Unchanged; fields added.
  JST_SH_SM04B-SRSS-TB   KiCad's stock Connector_JST footprint, the maker's two Qwiic / STEMMA QT sockets.
  Molex_PicoBlade_53261  KiCad's stock Connector_Molex footprint, the maker's 2-pin speaker socket.
  TestPoint_Pad_D1.0mm   KiCad's stock TestPoint footprint: a 1 mm bare-copper dot inside each of the maker's six
                         touch areas (front copper), so the schematic, the router and DRC know where each touch area is. Its silkscreen ring is removed.
                         It sits under the gold of the touch area and changes nothing you can see.
  SolderJumper-3...      KiCad's stock Jumper footprint, the maker's speaker mode jumper (pads 1-2 bridged by copper).
For the connectors the two mounting pads are renamed "MP" -> "" (unnumbered), as on the shared switch and LiPo socket,
so the schematic does not need a pin for them.
Run: python3 boards/tars/hardware/make_local_footprints.py
"""
import glob
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "tars-local.pretty"
OUT.mkdir(exist_ok=True)
STOCK = Path(sorted(glob.glob("/home/hoid/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/*/files/footprints"))[0])


def with_fields(txt, fields):
    """Add the SAOPP_ID / MPN / LCSC fields the build script fills in (metadata only)."""
    props = "".join(f'\t(property "{k}" "{v}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n'
                    f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n'
                    for k, v in fields.items())
    i = txt.index('\n\t(property "Reference"')
    return txt[:i + 1] + props + txt[i + 1:]


def unnumber_mp(txt):
    n = txt.count('(pad "MP"')
    assert n == 2, n
    return txt.replace('(pad "MP"', '(pad ""')


# the maker's display footprint, plus a courtyard 0.2 mm round the glass outline (+-14 x +-6.65 on Dwgs.User)
disp = (HERE / ".." / "original" / "KiCad" / "TARS" / "TARS.pretty" / "ST7735S-160x80-13PIN.kicad_mod").read_text()
assert "(start -14 -6.65)" in disp and "(end 14 6.65)" in disp
assert "CrtYd" not in disp
crt = ('\t(fp_rect\n\t\t(start -14.2 -6.85)\n\t\t(end 14.2 6.85)\n\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n'
       '\t\t(fill no)\n\t\t(layer "F.CrtYd")\n\t)\n')
i = disp.index("\t(pad ")
disp = disp[:i] + crt + disp[i:]
(OUT / "ST7735S-160x80-13PIN.kicad_mod").write_text(
    with_fields(disp, {"SAOPP_ID": "", "MPN": "0.96 in 80x160 ST7735S IPS, 13-pin 0.7 mm solder ribbon (maker gives no part number)", "LCSC": ""}))

kr = HERE / ".." / ".." / "knight-rider" / "hardware" / "knight-rider-local.pretty" / "LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder.kicad_mod"
(OUT / kr.name).write_text(kr.read_text())

COPIES = [
    ("Resistor_SMD.pretty/R_0603_1608Metric", {"SAOPP_ID": "", "MPN": "0603WAF110JT5E", "LCSC": ""}, False),
    ("Package_SO.pretty/SOIC-14_3.9x8.7mm_P1.27mm", {"SAOPP_ID": "", "MPN": "CAP1206-1-SL", "LCSC": ""}, False),
    ("Connector_JST.pretty/JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", {"SAOPP_ID": "", "MPN": "SM04B-SRSS-TB(LF)(SN)", "LCSC": ""}, True),
    ("Connector_Molex.pretty/Molex_PicoBlade_53261-0271_1x02-1MP_P1.25mm_Horizontal", {"SAOPP_ID": "", "MPN": "53261-0271", "LCSC": ""}, True),
    ("TestPoint.pretty/TestPoint_Pad_D1.0mm", {"SAOPP_ID": "", "MPN": "none: bare copper inside a touch pad", "LCSC": ""}, False),
    ("Jumper.pretty/SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm", {"SAOPP_ID": "", "MPN": "none: solder jumper, nothing fitted", "LCSC": ""}, False),
]
for rel, fields, mp in COPIES:
    src = STOCK / (rel + ".kicad_mod")
    txt = src.read_text()
    if mp:
        txt = unnumber_mp(txt)
    if "TestPoint" in rel:
        # no silkscreen ring: these dots sit in the maker's gold on the art side
        import re as _re
        txt, n = _re.subn(r'\n\t\(fp_circle(?:(?!\n\t\(fp_|\n\t\(pad|\n\t\(property).)*?\(layer "F\.SilkS"\)(?:(?!\n\t\().)*?\n\t\)', '', txt, flags=_re.S)
        assert n == 1, n
    (OUT / src.name).write_text(with_fields(txt, fields))

for f in sorted(OUT.iterdir()):
    print(f.name, len(re.findall(r"\(pad ", f.read_text())), "pads")
