# Parts only Do Or Donut uses so far (read by tools/saopp_symbols.load_local and tools/gen_schematic.py).
# Footprints live in do-or-donut-local.pretty/ (written by make_local_footprints.py, which says where each came from).
LOCAL_SYMBOLS = {
    # The 144 "sprinkles". The maker's files do not record a colour; one part number for all 144 once the owner picks one.
    "LED_0603_Matrix": ("D", "LED 0603", "do-or-donut-local:LED_0603_CHIP-LED0603_davedarko",
                        {"SAOPP_ID": "", "MPN": "0603 LED, colour to be chosen", "LCSC": ""}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    # The maker's LED matrix driver, ISSI IS31FL3731 in SSOP-28 (LCSC C2940545, checked by the orchestrator on lcsc.com 2026-11-11).
    "IS31FL3731_SSOP28": ("U", "IS31FL3731", "do-or-donut-local:SSOP-28_IS31FL3731_davedarko",
                          {"SAOPP_ID": "", "MPN": "IS31FL3731-SALS2-TR", "LCSC": "C2940545"}, 6,
                          [("2", "VCC", "L", 0), ("5", "GND", "L", 1), ("19", "SDA", "L", 2), ("20", "SCL", "L", 3),
                           ("18", "AD", "L", 4), ("3", "SDB", "L", 5), ("4", "INTB", "L", 6), ("17", "AUDIO_IN", "L", 7),
                           ("16", "C_FILT", "L", 8), ("6", "R_EXT", "L", 9),
                           ("12", "CB6", "L", 10), ("13", "CB7", "L", 11), ("14", "CB8", "L", 12), ("15", "CB9", "L", 13),
                           ("21", "CA1", "R", 0), ("22", "CA2", "R", 1), ("23", "CA3", "R", 2), ("24", "CA4", "R", 3),
                           ("25", "CA5", "R", 4), ("26", "CA6", "R", 5), ("27", "CA7", "R", 6), ("28", "CA8", "R", 7),
                           ("1", "CA9", "R", 8), ("7", "CB1", "R", 9), ("8", "CB2", "R", 10), ("9", "CB3", "R", 11),
                           ("10", "CB4", "R", 12), ("11", "CB5", "R", 13)]),
    # R_EXT: sets the driver's LED current (datasheet typical application value; to be confirmed).
    "R_20k": ("R", "20k", "do-or-donut-local:R_0603_1608Metric",
              {"SAOPP_ID": "", "MPN": "0603WAF2002T5E", "LCSC": "C4184"}, 2,
              [("1", "~", "L", 0), ("2", "~", "R", 0)]),
}
