"""Parts Mr. Robot needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land patterns: the maker's own speaker footprint, KiCad's stock SOT-23, and the SOD-523 that Knight Rider already uses,
copied into mr-robot-local.pretty by make_local_footprints.py. LCSC numbers are left for the orchestrator, except the
diode's, which docs/parts.md gives.
"""
LOCAL_SYMBOLS = {
    # the maker's sounder, on his own footprint. His BOM calls it "KMTG-1102 ... the speaker"; his readme calls it a piezo.
    # Pin numbers are his pad names: 2 (his P$2) went to the supply, 1 (his P$1) to the transistor.
    "Sounder_KMTG1102": ("LS", "KMTG1102", "mr-robot-local:KMTG-1102",
                         {"SAOPP_ID": "", "MPN": "KMTG1102-A1", "LCSC": ""}, 2,
                         [("2", "+", "L", 0), ("1", "-", "R", 0)]),
    # the low-side switch for the sounder; the maker's transistor type
    "Q_NPN_BC847": ("Q", "BC847B", "mr-robot-local:SOT-23",
                    {"SAOPP_ID": "", "MPN": "BC847B,215", "LCSC": ""}, 2,
                    [("1", "B", "L", 0), ("3", "C", "R", 0), ("2", "E", "R", 1)]),
    # the shared 30 mA Schottky (docs/parts.md SAOPP-D-01), here as the flyback diode across the sounder
    "D_Schottky_RB751": ("D", "RB751S40", "mr-robot-local:D_SOD-523",
                         {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                         [("2", "A", "L", 0), ("1", "K", "R", 0)]),
}
