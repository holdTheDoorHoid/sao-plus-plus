"""Parts DC619 EEPROM needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])

EE-01_24C02_SOT-23-5 is the candidate for the open shared slot SAOPP-EE-01 (docs/parts.md). The Floppy Disk board uses the
same symbol name and part, so the two can be promoted to lib/ together. Pinout read from the IDCHIP AD24C02 datasheet
(Ver 1.1, May 2022, page 2, SOT23-5 drawing; LCSC C5125083, read 2026-11-11): 1 SCL, 2 GND, 3 SDA, 4 VCC, 5 WP. That is
the same as the widely published AT24C02C-STUM SOT-23-5 pinout. The SOT-23-5 package has no A0-A2 address pins.
Land pattern: KiCad's stock Package_TO_SOT_SMD:SOT-23-5, copied unchanged by make_local_footprints.py.
"""
LOCAL_SYMBOLS = {
    "EE-01_24C02_SOT-23-5": ("U", "24C02", "dc619-eeprom-local:SOT-23-5",
                             {"SAOPP_ID": "SAOPP-EE-01", "MPN": "AD24C02", "LCSC": "C5125083"}, 4,
                             [("1", "SCL", "L", 0), ("3", "SDA", "L", 1), ("5", "WP", "L", 2),
                              ("4", "VCC", "R", 0), ("2", "GND", "R", 2)]),
}
