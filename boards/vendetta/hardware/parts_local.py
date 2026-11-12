"""Parts the Vendetta board needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land patterns: KiCad's stock library, copied unchanged into vendetta-local.pretty by make_local_footprints.py.
LCSC numbers the maker's files do not give are left empty for the orchestrator.
"""
LOCAL_SYMBOLS = {
    # the maker's EEPROM: onsemi CAT24C256, 256 kbit (32 KB) I2C EEPROM, 1.8-5.5 V, in the 208 mil (EIAJ) SOIC-8 his
    # board was drawn for ("X" package code). A0-A2 and WP are pulled low inside the chip when left open.
    "EEPROM_CAT24C256_SOIC8_EIAJ": ("U", "CAT24C256", "vendetta-local:SOIC-8_5.3x5.3mm_P1.27mm",
                                    {"SAOPP_ID": "", "MPN": "CAT24C256XI-T2", "LCSC": ""}, 4,
                                    [("8", "VCC", "L", 0), ("1", "A0", "L", 1), ("2", "A1", "L", 2), ("3", "A2", "L", 3),
                                     ("5", "SDA", "R", 0), ("6", "SCL", "R", 1), ("7", "WP", "R", 2), ("4", "GND", "R", 3)]),
    # the series cell diode docs/standard.md section 3 requires (the EEPROM sits on SDA/SCL); as boards/knight-rider
    "D_Schottky_Cell": ("D", "RB751S40", "vendetta-local:D_SOD-523",
                        {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
}
