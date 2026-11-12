"""Parts the SAO Modem needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land patterns are KiCad's stock footprints, the ones the maker used, copied into sao-modem-local.pretty by
make_local_footprints.py. Part numbers are the maker's own (modem-BOM.xlsx in the maker's repo) and have NOT been
checked at a distributor for this project: LCSC is left empty on purpose (see README, "Decisions for the owner").
"""
LOCAL_SYMBOLS = {
    # The maker's transistor: two P-channel MOSFETs in one SOIC-8. Pin-out read from the Diodes Inc. datasheet
    # DS36194 rev 3-2 (July 2019): 1 S1, 2 G1, 3 S2, 4 G2, 5+6 D2, 7+8 D1. Same pins the maker's schematic uses.
    "Q_Dual_PMOS_DMP3085LSD": ("Q", "DMP3085LSD", "sao-modem-local:SOIC-8_3.9x4.9mm_P1.27mm",
                               {"SAOPP_ID": "", "MPN": "DMP3085LSD-13", "LCSC": ""}, 4,
                               [("1", "S1", "L", 0), ("2", "G1", "L", 1), ("3", "S2", "L", 2), ("4", "G2", "L", 3),
                                ("8", "D1", "R", 0), ("7", "D1", "R", 1), ("6", "D2", "R", 2), ("5", "D2", "R", 3)]),
    # The maker's two gate resistors. Their values set how much the board loads the badge's I2C lines, so they are kept.
    "R_Gate_4k7": ("R", "4.7k", "sao-modem-local:R_0603_1608Metric",
                   {"SAOPP_ID": "", "MPN": "RMCF0603JT4K70", "LCSC": ""}, 2,
                   [("1", "~", "L", 0), ("2", "~", "R", 0)]),
    "R_Gate_10k": ("R", "10k", "sao-modem-local:R_0603_1608Metric",
                   {"SAOPP_ID": "", "MPN": "RMCF0603JT10K0", "LCSC": ""}, 2,
                   [("1", "~", "L", 0), ("2", "~", "R", 0)]),
    # The series cell diode docs/standard.md section 3 requires (this board is wired to SDA, SCL, GPIO1 and GPIO2).
    # Same part and footprint as Knight Rider and Han SAOlo; local until the shared library gets a symbol for it.
    "D_Schottky_Cell": ("D", "RB751S40", "sao-modem-local:D_SOD-523",
                        {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
}
