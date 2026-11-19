"""Parts Eggplant needs that the shared SAO++ library does not have. Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land pattern: the maker's own bicolour LED package from his Eagle board, written into eggplant-local.pretty by
make_local_footprints.py. LCSC is left empty for the orchestrator to verify; MPN is exactly what his BOM says.
"""
LOCAL_SYMBOLS = {
    # the maker's bicolour LED (blue + red in one 0805 package, four pads). His BOM: "PHBM2012QBDSURKC".
    "LED_Bicolour_0805": ("D", "blue/red", "eggplant-local:LED_Bicolour_0805",
                          {"SAOPP_ID": "", "MPN": "APHBM2012QBDSURKC", "LCSC": "C5568785"}, 3,
                          [("1", "A_BLUE", "L", 0), ("2", "A_RED", "L", 1),
                           ("3", "K_BLUE", "R", 0), ("4", "K_RED", "R", 1)]),
}
