# Parts only Floppy Disk uses so far (read by tools/saopp_symbols.load_local and tools/gen_schematic.py).
# Footprints live in floppy-disk-local.pretty/, each copied unchanged from KiCad 10's stock library by
# make_local_footprints.py. Format as in tools/saopp_symbols.py:
#   name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
LOCAL_SYMBOLS = {
    # The 256-byte ID EEPROM (maker: M24C02-WMN in SOIC-8, address 0x50). This is the open slot SAOPP-EE-01 in
    # docs/parts.md; the candidate part is NOT yet approved by the owner. Pinout read from the IDCHIP AD24C02 datasheet
    # Ver 1.1 (May 2022), page 2, figure 2, opened from the LCSC page for C5125083: 1 SCL, 2 GND, 3 SDA, 4 VCC, 5 WP.
    # (The same pinout as the widely used AT24C02C-STUM.) The symbol name is shared with the DC619 EEPROM board.
    "EE-01_24C02_SOT-23-5": ("U", "24C02", "floppy-disk-local:SOT-23-5",
                             {"SAOPP_ID": "SAOPP-EE-01", "MPN": "AD24C02", "LCSC": "C5125083"}, 4,
                             [("1", "SCL", "L", 0), ("2", "GND", "L", 1), ("3", "SDA", "L", 2),
                              ("5", "WP", "R", 0), ("4", "VCC", "R", 2)]),
    # The floppy's storage: the maker's 64 KB EEPROM, his part and his footprint (README BOM: M24512-RMN6TP).
    # E0 high, E1 and E2 low: address 0x51, as on the original.
    "EEPROM_24C512_SOIC8": ("U", "M24512", "floppy-disk-local:SOIC-8_3.9x4.9mm_P1.27mm",
                            {"SAOPP_ID": "", "MPN": "M24512-RMN6TP", "LCSC": "C79991"}, 5,
                            [("1", "E0", "L", 0), ("2", "E1", "L", 1), ("3", "E2", "L", 2), ("4", "VSS", "L", 3),
                             ("8", "VCC", "R", 0), ("7", "~{WC}", "R", 1), ("6", "SCL", "R", 2), ("5", "SDA", "R", 3)]),
    # The series cell diode docs/standard.md section 3 requires (both chips sit on SDA and SCL).
    # Same part and footprint as Knight Rider's and Han SAOlo's, so the boards share one reel.
    "D_Schottky_Cell": ("D", "RB751S40", "floppy-disk-local:D_SOD-523",
                        {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    # The maker's write-protect solder bridges (his JP1 / JP2): open as shipped; bridge with solder to write-protect
    # that chip. Bare copper, nothing to buy or place.
    "SolderJumper_2_Open": ("JP", "write protect", "floppy-disk-local:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
                            {"SAOPP_ID": "", "MPN": "none: PCB copper, nothing fitted", "LCSC": ""}, 2,
                            [("1", "A", "L", 0), ("2", "B", "R", 0)]),
}
