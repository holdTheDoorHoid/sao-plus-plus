"""Parts Knight Rider needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land patterns: the maker's own 2024 KiCad 8 footprints (ATtiny, ISP pads, button, front LED) and KiCad's stock SOD-523
(diode), copied into knight-rider-local.pretty by make_local_footprints.py. LCSC numbers are left for the orchestrator.
"""
LOCAL_SYMBOLS = {
    # the maker's chip: ATtiny85 in the 208 mil (EIAJ) SOIC-8. The low-voltage "V" grade (1.8-5.5 V) because on the coin
    # cell the chip sees about 2.7 V after the cell diode, which is the bottom of the standard -20 grade's range
    "ATtiny85_SOIC8_EIAJ": ("U", "ATtiny85V", "knight-rider-local:SO08-EIAJ",
                            {"SAOPP_ID": "", "MPN": "ATTINY85V-10SU", "LCSC": "C152192"}, 5,
                            [("1", "PB5/~{RESET}", "L", 0), ("2", "PB3", "L", 1), ("3", "PB4", "L", 2), ("4", "GND", "L", 3),
                             ("8", "VCC", "R", 0), ("7", "PB2/SCK", "R", 1), ("6", "PB1/MISO", "R", 2), ("5", "PB0/MOSI", "R", 3)]),
    # forward-facing red LED for the scanner, on the FRONT (art side) where the maker had it
    "LED_0603_Red_Front": ("D", "red", "knight-rider-local:LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder",
                           {"SAOPP_ID": "", "MPN": "LTST-C191KRKT", "LCSC": "C125099"}, 2,
                           [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    # the maker's push button (pattern mode); 6 x 3.5 mm two-pad SMD tactile switch
    "Button_SMD_6x3.5": ("SW", "button", "knight-rider-local:TACTILE-SWITCH-1101NE",
                         {"SAOPP_ID": "", "MPN": "SparkFun COM-08229 class (6 x 3.5 mm, 2 pads at 6.3 mm)", "LCSC": ""}, 2,
                         [("P$1", "~", "L", 0), ("P$2", "~", "R", 0)]),
    # the maker's six AVR ISP programming pads (bare copper, nothing fitted); standard AVR 6-pin ISP order
    "ISP_Pads_AVR_2x3": ("JP", "ISP pads", "knight-rider-local:2X3_SMD_PAD",
                         {"SAOPP_ID": "", "MPN": "none: bare pads, nothing fitted", "LCSC": ""}, 3,
                         [("P$1", "MISO", "L", 0), ("P$3", "SCK", "L", 1), ("P$5", "~{RST}", "L", 2),
                          ("P$2", "VCC", "R", 0), ("P$4", "MOSI", "R", 1), ("P$6", "GND", "R", 2)]),
    # the series cell diode docs/standard.md section 3 requires (this board wires the ATtiny to SAO GPIO2)
    "D_Schottky_Cell": ("D", "RB751S40", "knight-rider-local:D_SOD-523",
                        {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
}
