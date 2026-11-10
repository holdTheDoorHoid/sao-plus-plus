#!/usr/bin/env python3
"""Generate the SAO++ shared footprints into lib/sao-plus-plus.pretty/.

Dimensions come from the manufacturer drawings linked in each description.
Footprints are drawn for the FRONT side (KiCad convention); boards flip them to the back.
Run:  python3 tools/gen_footprints.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "lib" / "sao-plus-plus.pretty"
FONT = "(effects (font (size 0.8 0.8) (thickness 0.12)))"


def head(name, descr, tags, attr="smd"):
    return (f'(footprint "{name}"\n  (version 20240108)\n  (generator "saopp_gen_footprints")\n  (layer "F.Cu")\n'
            f'  (descr "{descr}")\n  (tags "{tags}")\n  (attr {attr})\n')


def props(ref_at, val_at, name, extra):
    s = (f'  (property "Reference" "REF**" (at {ref_at[0]} {ref_at[1]} 0) (layer "F.SilkS") {FONT})\n'
         f'  (property "Value" "{name}" (at {val_at[0]} {val_at[1]} 0) (layer "F.Fab") {FONT})\n')
    for k, v in extra.items():
        s += f'  (property "{k}" "{v}" (at 0 0 0) (layer "F.Fab") hide {FONT})\n'
    return s


def line(x1, y1, x2, y2, layer, w=0.12):
    return f'  (fp_line (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type solid)) (layer "{layer}"))\n'


def rect(x1, y1, x2, y2, layer, w=0.1):
    return f'  (fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type solid)) (fill none) (layer "{layer}"))\n'


def circle(cx, cy, r, layer, w=0.1):
    return f'  (fp_circle (center {cx} {cy}) (end {cx + r} {cy}) (stroke (width {w}) (type solid)) (fill none) (layer "{layer}"))\n'


def text(txt, x, y, layer, size=1.0, th=0.15):
    return (f'  (fp_text user "{txt}" (at {x} {y} 0) (layer "{layer}") '
            f'(effects (font (size {size} {size}) (thickness {th}))))\n')


def pad(num, shape, x, y, w, h, layers, rr=None, kind="smd", drill=None):
    s = f'  (pad "{num}" {kind} {shape} (at {x} {y}) (size {w} {h})'
    if drill:
        s += f' (drill {drill})'
    s += f' (layers {" ".join(chr(34) + l + chr(34) for l in layers)})'
    if rr is not None:
        s += f' (roundrect_rratio {rr})'
    return s + ')\n'


SMD = ["F.Cu", "F.Paste", "F.Mask"]


def conn():
    name = "SAOPP_CONN-01_BoxHeader_2x03_P2.54mm_SMD_XFCN_BH254VS-6P"
    s = head(name,
             "SAO v1.69bis add-on connector: 2x3 2.54mm shrouded keyed SMD box header, XFCN BH254VS-6P (LCSC C492445). "
             "Drawing: https://www.lcsc.com/datasheet/C492445.pdf (land pattern 1.1 x 4.0 pads, 10.5 outer span; pads here are "
             "1.1 x 4.4 for joint strength). Pin 1 VCC, 2 GND, 3 SDA, 4 SCL, 5 GPIO1, 6 GPIO2. Key slot is on the odd-pin side.",
             "SAO SAO++ box header IDC 2x03 SMD")
    s += props((0, -9), (0, 9), name, {"SAOPP_ID": "SAOPP-CONN-01", "MPN": "BH254VS-6P", "LCSC": "C492445"})
    for i in range(3):
        y = -2.54 + 2.54 * i
        s += pad(2 * i + 1, "roundrect", -3.4, y, 4.4, 1.1, SMD, 0.2)
        s += pad(2 * i + 2, "roundrect", 3.4, y, 4.4, 1.1, SMD, 0.2)
    s += rect(-4.45, -7.635, 4.45, 7.635, "F.Fab")
    s += rect(-3.25, -6.4, 3.25, 6.4, "F.Fab")                    # shroud inner wall
    s += rect(-4.45, -2.25, -3.25, 2.25, "F.Fab")                 # key slot (4.5 wide)
    s += rect(-6.1, -8.15, 6.1, 8.15, "F.CrtYd", 0.05)
    for sx in (-1, 1):
        s += line(-4.56, sx * 7.75, 4.56, sx * 7.75, "F.SilkS")
        s += line(-4.56, sx * 7.75, -4.56, sx * 3.5, "F.SilkS")
        s += line(4.56, sx * 7.75, 4.56, sx * 3.5, "F.SilkS")
    s += line(-6.1, -3.4, -6.1, -1.7, "F.SilkS", 0.3)             # pin-1 bar
    return name, s + ")\n"


def sw():
    name = "SAOPP_SW-01_Slide_SP3T_CK_PCM13SMTR"
    s = head(name,
             "SAO / OFF / BATTERY power switch: C&K PCM13SMTR SP3T right-angle slide. Datasheet https://www.lcsc.com/datasheet/C221842.pdf : "
             "pos1 connects 1-3, pos2 connects 2-3, pos3 connects 3-4, so pin 3 is the common (load), pin 1 = SAO VCC, pin 2 = no connection (OFF), "
             "pin 4 = coin cell +. Land pattern matches KiCad Button_Switch_SMD:SW_SP3T_PCM13. Board edge belongs at y = +2.1 or closer; "
             "the knob reaches y = +3.1. Two 0.9 mm locating-peg holes go through the board.",
             "SAO++ slide switch SP3T PCM13")
    s += props((0, -3.3), (0, 4.4), name, {"SAOPP_ID": "SAOPP-SW-01", "MPN": "PCM13SMTR", "LCSC": "C221842", "Digikey": "401-2017-1-ND"})
    for x, y in ((-5.15, -0.78), (-5.15, 1.43), (5.15, -0.78), (5.15, 1.43)):
        s += pad("", "rect", x, y, 1, 0.8, SMD)
    for x in (-2.5, 2.5):
        s += pad("", "circle", x, 0.33, 0.9, 0.9, ["*.Cu"], kind="np_thru_hole", drill=0.9)   # no mask opening: nothing shiny on the art side
    for n, x in ((1, -3), (2, -1.5), (3, 1.5), (4, 3)):
        s += pad(n, "rect", x, -1.43, 0.7, 1.5, SMD)
    s += rect(-4.85, -0.95, 4.85, 1.6, "F.Fab")
    s += rect(-0.65, 1.6, 0.65, 3.1, "F.Fab")                     # knob, centre position
    s += rect(-2.15, 1.6, 2.15, 3.1, "Dwgs.User", 0.05)           # knob travel
    s += rect(-5.9, -2.45, 5.9, 3.4, "F.CrtYd", 0.05)
    s += line(-4.4, -1.07, -3.6, -1.07, "F.SilkS") + line(3.6, -1.07, 4.4, -1.07, "F.SilkS")
    s += line(-0.9, -1.07, 0.9, -1.07, "F.SilkS")
    return name, s + ")\n"


def bat():
    name = "SAOPP_BAT-01_CR2032_SMD_TE_BAT-HLD-001"
    s = head(name,
             "CR2032 retainer clip, TE/Linx BAT-HLD-001 (LCSC C7501066). Drawing: https://www.lcsc.com/datasheet/C7501066.pdf "
             "(recommended footprint: two 1.8 x 5.2 pads 21.0 apart, 17.0 dia cell pad). Pads 1 = clip = cell PLUS; pad 2 = bare 17 mm "
             "disc under the cell = cell MINUS (no paste; use ENIG). The clip fits the pads either way round: the open side must face +Y "
             "of this footprint (arrow), where the cell slides in. Keep parts and exposed copper out of the 10.5 mm radius circle.",
             "SAO++ CR2032 coin cell holder BAT-HLD-001")
    s += props((0, -12.4), (0, 12), name, {"SAOPP_ID": "SAOPP-BAT-01", "MPN": "BAT-HLD-001", "LCSC": "C7501066"})
    s += pad(1, "rect", -10.5, 0, 1.8, 5.2, SMD)
    s += pad(1, "rect", 10.5, 0, 1.8, 5.2, SMD)
    s += pad(2, "circle", 0, 0, 17, 17, ["F.Cu", "F.Mask"])
    s += rect(-11.45, -11.0, 11.45, 4.3, "F.Fab")                 # clip body: closed end at -Y
    s += circle(0, 0, 10, "F.Fab")                                # cell seated
    s += circle(0, 0, 10.5, "F.CrtYd", 0.05)
    s += rect(-11.9, -11.5, 11.9, 4.8, "F.CrtYd", 0.05)
    s += line(-8.0, -11.15, 8.0, -11.15, "F.SilkS")
    s += line(0, 12.2, 0, 10.2, "F.SilkS", 0.2) + line(0, 10.2, -0.8, 11.0, "F.SilkS", 0.2) + line(0, 10.2, 0.8, 11.0, "F.SilkS", 0.2)
    s += text("+", -10.5, -3.7, "F.SilkS", 1.2, 0.2)
    return name, s + ")\n"


def led():
    name = "SAOPP_LED-10_1206_ReverseMount_ThroughBoard"
    s = head(name,
             "1206 reverse-mount LED that shines THROUGH the board (no hole): the lens faces the PCB and lights bare FR4 from behind. "
             "Keep copper off both sides inside a 1.6 mm radius of the centre. Lite-On LTST-C230KRKT (red, LCSC C125107) and family. "
             "Pads per KiCad LED_SMD:LED_1206_3216Metric_ReverseMount. Pad 1 = cathode, pad 2 = anode.",
             "SAO++ LED reverse mount 1206 through board")
    s += props((0, -2.2), (0, 2.2), name, {"SAOPP_ID": "SAOPP-LED-10", "MPN": "LTST-C230KRKT", "LCSC": "C125107"})
    s += pad(1, "roundrect", -1.55, 0, 0.95, 1.75, SMD, 0.25)
    s += pad(2, "roundrect", 1.55, 0, 0.95, 1.75, SMD, 0.25)
    s += rect(-1.6, -0.8, 1.6, 0.8, "F.Fab")
    s += circle(0, 0, 1.6, "Dwgs.User", 0.05)
    s += ('  (fp_circle (center 0 0) (end 0.95 0) (stroke (width 0) (type solid)) (fill solid) (layer "F.Mask"))\n')  # bare FR4 window under the lens
    s += rect(-2.28, -1.46, 2.28, 1.46, "F.CrtYd", 0.05)
    s += line(-2.4, -1.3, -2.4, 1.3, "F.SilkS", 0.2)              # cathode bar
    return name, s + ")\n"


def res():
    name = "SAOPP_R_0603_1608Metric"
    s = head(name, "0603 chip resistor, IPC-7351 nominal land pattern (same pads as KiCad Resistor_SMD:R_0603_1608Metric). "
                   "Kept in this library so SAO++ projects open with no global libraries configured.", "SAO++ resistor 0603")
    s += props((0, -1.5), (0, 1.5), name, {"SAOPP_ID": "SAOPP-R-01", "MPN": "0603WAF1301T5E", "LCSC": "C22767"})
    s += pad(1, "roundrect", -0.825, 0, 0.8, 0.95, SMD, 0.25)
    s += pad(2, "roundrect", 0.825, 0, 0.8, 0.95, SMD, 0.25)
    s += rect(-0.8, -0.4125, 0.8, 0.4125, "F.Fab")
    s += rect(-1.48, -0.73, 1.48, 0.73, "F.CrtYd", 0.05)
    s += line(-0.16, -0.51, 0.16, -0.51, "F.SilkS") + line(-0.16, 0.51, 0.16, 0.51, "F.SilkS")
    return name, s + ")\n"


def panel_parts():
    out = []
    name = "SAOPP_PANEL_MouseBite_0.5mm"
    s = head(name, "One 0.5 mm unplated mouse-bite hole for break-off tabs. Placed by tools/panelize.py.", "SAO++ panel mouse bite", "board_only exclude_from_pos_files exclude_from_bom")
    s += props((0, -1), (0, 1), name, {}).replace('(layer "F.SilkS")', '(layer "F.Fab") hide')
    s += pad("", "circle", 0, 0, 0.5, 0.5, ["*.Cu"], kind="np_thru_hole", drill=0.5)
    out.append((name, s + ")\n"))
    name = "SAOPP_PANEL_ToolingHole_1.152mm"
    s = head(name, "1.152 mm unplated tooling hole for assembly-line pins (JLCPCB's size), with a mask opening.", "SAO++ panel tooling hole", "board_only exclude_from_pos_files exclude_from_bom")
    s += props((0, -2), (0, 2), name, {}).replace('(layer "F.SilkS")', '(layer "F.Fab") hide')
    s += pad("", "circle", 0, 0, 1.152, 1.152, ["*.Cu", "*.Mask"], kind="np_thru_hole", drill=1.152)
    out.append((name, s + ")\n"))
    name = "SAOPP_PANEL_Fiducial_1mm_BothSides"
    s = head(name, "Assembly fiducial: 1 mm bare copper dot in a 2 mm mask opening, on both sides of the panel rail.", "SAO++ panel fiducial", "board_only exclude_from_pos_files exclude_from_bom")
    s += props((0, -2), (0, 2), name, {}).replace('(layer "F.SilkS")', '(layer "F.Fab") hide')
    for cu, mask in (("F.Cu", "F.Mask"), ("B.Cu", "B.Mask")):
        s += f'  (pad "" smd circle (at 0 0) (size 1 1) (layers "{cu}" "{mask}") (solder_mask_margin 0.5))\n'
    out.append((name, s + ")\n"))
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (conn, sw, bat, led, res):
        name, body = fn()
        (OUT / f"{name}.kicad_mod").write_text(body)
        print("wrote", name)
    for name, body in panel_parts():
        (OUT / f"{name}.kicad_mod").write_text(body)
        print("wrote", name)
