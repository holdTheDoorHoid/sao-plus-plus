"""Parts the Flux Capacitor needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Three are the already-checked Knight Rider local parts, copied entry for entry (chip, ISP pads, cell diode); the
front LED is new. Footprints: see make_local_footprints.py. LCSC numbers only where already verified for Knight Rider
and the cell diode; the new LED's is left for the orchestrator.
"""
LOCAL_SYMBOLS = {
    # the maker's chip (he drew an ATtiny45-20 in the 208 mil EIAJ SOIC-8; ATtiny13/45/85 share pins and package).
    # Knight Rider's ATtiny85V part, so the two boards share one reel; the V grade also runs from the cell after the diode
    "ATtiny85_SOIC8_EIAJ": ("U", "ATtiny85V", "flux-capacitor-local:SO08-EIAJ",
                            {"SAOPP_ID": "", "MPN": "ATTINY85V-10SU", "LCSC": "C152192"}, 5,
                            [("1", "PB5/~{RESET}", "L", 0), ("2", "PB3", "L", 1), ("3", "PB4", "L", 2), ("4", "GND", "L", 3),
                             ("8", "VCC", "R", 0), ("7", "PB2/SCK", "R", 1), ("6", "PB1/MISO", "R", 2), ("5", "PB0/MOSI", "R", 3)]),
    # the maker's nine forward-facing 1206 LEDs, on the FRONT where he put them (they are the art)
    "LED_1206_Red_Front": ("D", "red", "flux-capacitor-local:LED_1206_3216Metric",
                           {"SAOPP_ID": "", "MPN": "LTST-C150KRKT", "LCSC": "C125086"}, 2,
                           [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    # the maker's six AVR ISP programming pads (bare copper, nothing fitted); standard AVR 6-pin ISP order
    "ISP_Pads_AVR_2x3": ("JP", "ISP pads", "flux-capacitor-local:2X3_SMD_PAD",
                         {"SAOPP_ID": "", "MPN": "none: bare pads, nothing fitted", "LCSC": ""}, 3,
                         [("P$1", "MISO", "L", 0), ("P$3", "SCK", "L", 1), ("P$5", "~{RST}", "L", 2),
                          ("P$2", "VCC", "R", 0), ("P$4", "MOSI", "R", 1), ("P$6", "GND", "R", 2)]),
    # the series cell diode docs/standard.md section 3 asks for (a chip on the cell; ISP programmer on the same rail)
    "D_Schottky_Cell": ("D", "RB751S40", "flux-capacitor-local:D_SOD-523",
                        {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
}
