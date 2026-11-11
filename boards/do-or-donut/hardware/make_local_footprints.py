#!/usr/bin/env python3
"""Write the footprints only Do Or Donut uses into hardware/do-or-donut-local.pretty/.

  python3 boards/do-or-donut/hardware/make_local_footprints.py

- LED_0603_CHIP-LED0603_davedarko: the maker's own 0603 LED land pattern (Eagle library "led", package CHIP-LED0603,
  read from original/donut.brd), converted. The maker's three tiny silkscreen bars between the pads go to F.Fab: they sit
  under the LED body once it is fitted, so they are not part of the visible art, and on the silkscreen they would touch
  the pads' solder-mask openings 144 times.
  Pad 1 = cathode (the maker's pad "C"), pad 2 = anode (the maker's pad "A"), so the KiCad LED convention holds.
- SSOP-28_IS31FL3731_davedarko: the maker's land pattern for the IS31FL3731 (Eagle library "nightcapaudio", package
  SSOP28DB), converted. Pad numbers are the chip's pin numbers.
- R_0603_1608Metric: copied from KiCad's stock library (Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod), pads unchanged,
  with the three SAO++ fields added. Used for the 20 k current-setting resistor, which is not on the shared parts list.
  (The shared 0603 footprint cannot be named by a board-local symbol: tools/saopp_symbols.load_local requires local parts
  to use '<slug>-local:' footprints.)
Eagle is y-up and KiCad is y-down, so every y is negated.
"""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "do-or-donut-local.pretty"
BRD = HERE.parent / "original" / "donut.brd"
STOCK = Path("/home/hoid/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable")


LCSC = {"IS31FL3731-SALS2-TR": "C2940545", "0603WAF2002T5E": "C4184"}     # checked on lcsc.com 2026-11-11


def fields(mpn):
    return "".join(f'  (property "{k}" "{v}" (at 0 0 0) (layer "F.Fab") hide (effects (font (size 0.8 0.8) (thickness 0.12))))\n'
                   for k, v in (("SAOPP_ID", ""), ("MPN", mpn), ("LCSC", LCSC.get(mpn, ""))))


def head(name, descr, mpn, ref_y, val_y):
    return (f'(footprint "{name}"\n  (version 20240108)\n  (generator "do-or-donut_make_local_footprints")\n  (layer "F.Cu")\n'
            f'  (descr "{descr}")\n  (attr smd)\n'
            f'  (property "Reference" "REF**" (at 0 {ref_y} 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))\n'
            f'  (property "Value" "{name}" (at 0 {val_y} 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))\n'
            + fields(mpn))


def f(v):
    return f"{v:.4f}".rstrip("0").rstrip(".") if v else "0"


def rect(x0, y0, x1, y1, layer, w):
    return (f'  (fp_rect (start {f(x0)} {f(y0)}) (end {f(x1)} {f(y1)}) (stroke (width {w}) (type solid)) (fill none) (layer "{layer}"))\n')


def main():
    pk = {}
    root = ET.parse(BRD).getroot()
    for lib in root.find("drawing/board/libraries"):
        for p in lib.find("packages"):
            pk[p.get("name")] = p

    # ---- LED ----
    p = pk["CHIP-LED0603"]
    s = head("LED_0603_CHIP-LED0603_davedarko", "0603 chip LED, the maker's land pattern (Eagle led.lbr CHIP-LED0603 as used in Do Or Donut by davedarko). Pad 1 cathode, pad 2 anode.",
             "0603 LED, colour to be chosen", -1.6, 1.6)
    num = {"C": "1", "A": "2"}
    for e in p:
        if e.tag == "smd":
            s += (f'  (pad "{num[e.get("name")]}" smd rect (at {f(float(e.get("x")))} {f(-float(e.get("y")))}) '
                  f'(size {f(float(e.get("dx")))} {f(float(e.get("dy")))}) (layers "F.Cu" "F.Paste" "F.Mask"))\n')
        elif e.tag == "rectangle":
            x1, y1, x2, y2 = (float(e.get(k)) for k in ("x1", "y1", "x2", "y2"))
            s += rect(x1, -y2, x2, -y1, "F.Fab", 0.05)
        elif e.tag == "wire" and e.get("layer") == "51":
            s += (f'  (fp_line (start {f(float(e.get("x1")))} {f(-float(e.get("y1")))}) (end {f(float(e.get("x2")))} {f(-float(e.get("y2")))}) '
                  f'(stroke (width 0.1) (type solid)) (layer "F.Fab"))\n')
    s += rect(-0.55, -1.25, 0.55, 1.25, "F.CrtYd", 0.05)    # pads + 0.1 mm: the maker set some LEDs 2.54 mm apart end to end
    (OUT / "LED_0603_CHIP-LED0603_davedarko.kicad_mod").write_text(s + ")\n")

    # ---- IS31FL3731, SSOP-28 ----
    p = pk["SSOP28DB"]
    s = head("SSOP-28_IS31FL3731_davedarko", "SSOP-28 0.65 mm pitch, the maker's land pattern for the IS31FL3731 (Eagle nightcapaudio.lbr SSOP28DB as used in Do Or Donut by davedarko).",
             "IS31FL3731-SALS2-TR", -5.2, 5.2)
    for e in p:
        if e.tag == "smd":
            s += (f'  (pad "{e.get("name")}" smd rect (at {f(float(e.get("x")))} {f(-float(e.get("y")))}) '
                  f'(size {f(float(e.get("dx")))} {f(float(e.get("dy")))}) (layers "F.Cu" "F.Paste" "F.Mask"))\n')
        elif e.tag == "wire" and e.get("layer") == "21":
            s += (f'  (fp_line (start {f(float(e.get("x1")))} {f(-float(e.get("y1")))}) (end {f(float(e.get("x2")))} {f(-float(e.get("y2")))}) '
                  f'(stroke (width {f(float(e.get("width")))}) (type solid)) (layer "F.SilkS"))\n')
        elif e.tag == "wire" and e.get("layer") == "27":
            s += (f'  (fp_line (start {f(float(e.get("x1")))} {f(-float(e.get("y1")))}) (end {f(float(e.get("x2")))} {f(-float(e.get("y2")))}) '
                  f'(stroke (width 0.1) (type solid)) (layer "F.Fab"))\n')
        elif e.tag == "circle" and e.get("layer") == "21":
            cx, cy, r = float(e.get("x")), -float(e.get("y")), float(e.get("radius"))
            s += (f'  (fp_circle (center {f(cx)} {f(cy)}) (end {f(cx + r)} {f(cy)}) (stroke (width {f(float(e.get("width")))}) (type solid)) (fill none) (layer "F.SilkS"))\n')
    s += rect(-5.45, -4.6, 5.45, 4.6, "F.CrtYd", 0.05)
    (OUT / "SSOP-28_IS31FL3731_davedarko.kicad_mod").write_text(s + ")\n")

    # ---- 0603 resistor, KiCad stock ----
    src = sorted(STOCK.glob("*/files/footprints/Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod"))[-1]
    txt = src.read_text()
    i = txt.index("\t(attr smd)")
    props = "".join(f'\t(property "{k}" "{v}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n'
                    for k, v in (("SAOPP_ID", ""), ("MPN", "0603WAF2002T5E"), ("LCSC", "C4184")))
    (OUT / "R_0603_1608Metric.kicad_mod").write_text(txt[:i] + props + txt[i:])
    print("wrote", sorted(x.name for x in OUT.iterdir()))


if __name__ == "__main__":
    main()
