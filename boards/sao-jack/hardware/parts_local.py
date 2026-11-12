"""Parts SAO Jack needs that the shared SAO++ library does not have. Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])

These are the KIT parts: the buyer solders them by hand, which is the whole point of hamster's board. They are NOT fitted
by the assembly house (hardware/fix_schematic.py marks them "not in BOM", and the footprints are left out of the placement
file). Land patterns: KiCad's stock LED_THT:LED_D3.0mm and Resistor_THT:R_Axial_DIN0204_L3.6mm_D1.6mm_P7.62mm_Horizontal
exactly as they sit in the maker's 2022 board file (the LED one carries his extra back-silkscreen outline), copied to
sao-jack-local.pretty by hardware/make_local_footprints.py.

No part numbers are chosen here. The MPN text records what the maker's own 2022 parts list (jack-BOM.xlsx, upstream) named;
none of it has been re-checked for stock or price.
"""
LOCAL_SYMBOLS = {
    # 3 mm (T-1) through-hole LED, lens on the FRONT, legs soldered on the back. Pad 1 (square) = cathode = short leg.
    "LED_3mm_THT_Kit": ("D", "LED 3 mm", "sao-jack-local:LED_D3.0mm",
                        {"SAOPP_ID": "", "MPN": "kit part, not chosen: any 3 mm (T-1) LED. Maker's 2022 list: HLMP1540 green, LTL-4211N red", "LCSC": ""}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    # small axial resistor, body on the BACK, legs soldered on the front. 7.62 mm between holes.
    "R_Axial_THT_Kit": ("R", "680", "sao-jack-local:R_Axial_DIN0204_L3.6mm_D1.6mm_P7.62mm_Horizontal",
                        {"SAOPP_ID": "", "MPN": "kit part, not chosen: any 680 ohm 1/8 W axial resistor with a 3.6 mm body. Maker's 2022 list: CF18JT100R (100 ohm)", "LCSC": ""}, 2,
                        [("1", "~", "L", 0), ("2", "~", "R", 0)]),
}
