"""Parts GPIO-16 needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])

MCP23017, 28-lead SSOP. Pin numbers and names: Microchip "MCP23017/MCP23S17 Data Sheet", DS20001952C (July 2016),
page 1 "Package Types" and Table 2-1 (SOIC/SPDIP/SSOP column); checked against DS20001952D (June 2022), which has the
same pinout and adds that GPA7 and GPB7 are outputs only (this board only ever uses them as outputs).
Land pattern: hardware/make_local_footprints.py.
"""
LOCAL_SYMBOLS = {
    "MCP23017_SSOP28": ("U", "MCP23017", "gpio-16-local:SSOP-28_5.3x10.2mm_P0.65mm_Microchip_C04-2073A",
                        {"SAOPP_ID": "", "MPN": "MCP23017T-E/SS", "LCSC": "C558584"}, 6,
                        [("13", "SDA", "L", 0), ("12", "SCK", "L", 1),
                         ("18", "~{RESET}", "L", 3),
                         ("15", "A0", "L", 5), ("16", "A1", "L", 6), ("17", "A2", "L", 7),
                         ("9", "VDD", "L", 9), ("10", "VSS", "L", 10),
                         ("11", "NC", "L", 12), ("14", "NC", "L", 13), ("20", "INTA", "L", 14), ("19", "INTB", "L", 15),
                         ("21", "GPA0", "R", 0), ("22", "GPA1", "R", 1), ("23", "GPA2", "R", 2), ("24", "GPA3", "R", 3),
                         ("25", "GPA4", "R", 4), ("26", "GPA5", "R", 5), ("27", "GPA6", "R", 6), ("28", "GPA7", "R", 7),
                         ("1", "GPB0", "R", 8), ("2", "GPB1", "R", 9), ("3", "GPB2", "R", 10), ("4", "GPB3", "R", 11),
                         ("5", "GPB4", "R", 12), ("6", "GPB5", "R", 13), ("7", "GPB6", "R", 14), ("8", "GPB7", "R", 15)]),
}
