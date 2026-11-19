"""Parts Duck Bath needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land patterns are copied into duck-bath-local.pretty by make_local_footprints.py: the maker's own 5 mm RGB LED
footprint, and the shared 0603 resistor land pattern for the 100 ohm resistors. LCSC numbers are the maker's own
(from the LCSC fields in his KiCad files); the orchestrator verifies them.
"""
LOCAL_SYMBOLS = {
    # the point of the board: a 5 mm, 4-leg, common-anode RGB LED standing on the FRONT, inside the bubbles. The rubber
    # duck sits on it. Maker's footprint (legs soldered on the back only). Pin order is his: 1 red, 2 anode, 3 green, 4 blue.
    # His files give no part number for it (LCSC field empty), so the MPN below describes it; the orchestrator picks one.
    "LED_RGB_5mm_CA": ("D", "RGB 5mm CA", "duck-bath-local:LED_D5.0mm-4_RGB_single-side",
                       {"SAOPP_ID": "", "MPN": "5 mm RGB LED, common anode, 4 legs, R-A-G-B order (maker gives no part number)",
                        "LCSC": ""}, 3,
                       [("2", "A", "L", 0), ("1", "R", "R", 0), ("3", "G", "R", 1), ("4", "B", "R", 2)]),
    # the maker's LED resistor: 100 ohm 0603 (his LCSC field: C22775). Kept rather than the shared 330 ohm because green
    # and blue need about 3 V and would barely light through 330 ohm from a 3.3 V rail.
    "R_100": ("R", "100", "duck-bath-local:R_0603_1608Metric",
              {"SAOPP_ID": "", "MPN": "0603WAF1000T5E", "LCSC": "C22775"}, 2,
              [("1", "~", "L", 0), ("2", "~", "R", 0)]),
}
