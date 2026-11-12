"""Parts only Yo Dawg uses so far (read by tools/saopp_symbols.load_local and tools/gen_schematic.py).

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])

The maker's socket for the 19 x 19 mm mini boards: a 3-way, 1.27 mm pitch, single-row, through-hole female strip, wired
GND - VCC - GND so a mini board works either way round. The footprint in yo-dawg-local.pretty/ is KiCad 10's stock
Connector_PinSocket_1.27mm:PinSocket_1x03_P1.27mm_Vertical, unchanged: the same stock footprint the maker used.
The maker names no manufacturer or part number anywhere in his repository, so none is given here. Do not order from
this file until a real part has been picked and checked against the footprint (0.7 mm holes, 1.27 mm apart).
"""
LOCAL_SYMBOLS = {
    "MiniBoard_Socket_1x03_P1.27": ("J", "mini board socket", "yo-dawg-local:PinSocket_1x03_P1.27mm_Vertical",
                                    {"SAOPP_ID": "", "MPN": "not chosen: 1x3 female socket strip, 1.27 mm pitch, through-hole",
                                     "LCSC": ""}, 3,
                                    [("1", "GND", "L", 0), ("2", "VCC", "L", 1), ("3", "GND", "L", 2)]),
}
