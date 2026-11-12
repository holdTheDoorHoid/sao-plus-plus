#!/usr/bin/env python3
"""Write the one land pattern this board needs that the shared library does not have into gpio-16-local.pretty.

  SSOP-28_5.3x10.2mm_P0.65mm_Microchip_C04-2073A
      Microchip 28-lead SSOP (SS), 5.30 mm body, for the MCP23017. Every number is from Microchip's
      "MCP23017/MCP23S17 Data Sheet", DS20001952C (July 2016):
        page 35, "Recommended Land Pattern", drawing C04-2073A:
            contact pitch E 0.65 mm, contact pad spacing C 7.20 mm, pad width X1 0.45 mm (max),
            pad length Y1 1.75 mm (max), distance between pads G 0.20 mm (min)
        page 34, package drawing C04-073B: body 5.30 x 10.20 mm nominal (5.60 x 10.50 max), 7.80 mm over the leads
        page 1, "Package Types": pin 1 at the marked corner, pins counted anticlockwise seen from above
      Drawn for the front side like the shared footprints (KiCad convention): pin 1 top left, pins 1-14 down the
      left, 15-28 up the right. The build script flips it to the back.
Run: python3 boards/gpio-16/hardware/make_local_footprints.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "gpio-16-local.pretty"
OUT.mkdir(exist_ok=True)
FONT = "(effects (font (size 0.8 0.8) (thickness 0.12)))"

PITCH, C, X1, Y1 = 0.65, 7.20, 0.45, 1.75          # DS20001952C page 35
BODY_W, BODY_L, BODY_L_MAX = 5.30, 10.20, 10.50     # DS20001952C page 34 (E1, D nominal; D max)
N = 28

name = "SSOP-28_5.3x10.2mm_P0.65mm_Microchip_C04-2073A"
s = (f'(footprint "{name}"\n  (version 20240108)\n  (generator "gpio16_make_local_footprints")\n  (layer "F.Cu")\n'
     '  (descr "Microchip 28-lead SSOP (SS), 5.30 mm body, 0.65 mm pitch. Land pattern from the MCP23017/MCP23S17 data sheet '
     'DS20001952C page 35, drawing C04-2073A: pad spacing 7.20, pads 0.45 x 1.75.")\n'
     '  (tags "SSOP 28 0.65 MCP23017")\n  (attr smd)\n')
s += f'  (property "Reference" "REF**" (at 0 -6.4 0) (layer "F.SilkS") {FONT})\n'
s += f'  (property "Value" "{name}" (at 0 6.4 0) (layer "F.Fab") {FONT})\n'
for k, v in {"SAOPP_ID": "", "MPN": "MCP23017T-E/SS", "LCSC": "C558584"}.items():
    s += f'  (property "{k}" "{v}" (at 0 0 0) (layer "F.Fab") hide {FONT})\n'
half = N // 2
for i in range(half):
    y = round((i - (half - 1) / 2) * PITCH, 4)
    s += f'  (pad "{i + 1}" smd roundrect (at {-C / 2} {y}) (size {Y1} {X1}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))\n'
    s += f'  (pad "{N - i}" smd roundrect (at {C / 2} {y}) (size {Y1} {X1}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))\n'
bw, bl = BODY_W / 2, BODY_L / 2
s += f'  (fp_rect (start {-bw} {-bl}) (end {bw} {bl}) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))\n'
s += f'  (fp_circle (center {-bw + 0.8} {-bl + 0.8}) (end {-bw + 1.1} {-bl + 0.8}) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))\n'
cx, cy = round(C / 2 + Y1 / 2 + 0.25, 3), round(BODY_L_MAX / 2 + 0.25, 3)
s += f'  (fp_rect (start {-cx} {-cy}) (end {cx} {cy}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))\n'
# silkscreen: the two body ends (clear of the pads) and a pin-1 dot outside the first pad
for sy in (-1, 1):
    s += f'  (fp_line (start {-bw} {sy * (bl + 0.11)}) (end {bw} {sy * (bl + 0.11)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
s += (f'  (fp_circle (center {-C / 2 - Y1 / 2 - 0.45} {-(half - 1) / 2 * PITCH}) (end {-C / 2 - Y1 / 2 - 0.3} {-(half - 1) / 2 * PITCH}) '
      '(stroke (width 0.15) (type solid)) (fill solid) (layer "F.SilkS"))\n')
s += ")\n"
(OUT / f"{name}.kicad_mod").write_text(s)
print("wrote", name, s.count("(pad "), "pads")
