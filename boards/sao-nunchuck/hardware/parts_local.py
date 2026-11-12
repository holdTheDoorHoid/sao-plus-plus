# Parts only SAO Nunchuck uses so far (read by tools/saopp_symbols.load_local and tools/gen_schematic.py).
# Footprints live in sao-nunchuck-local.pretty/, lifted from ageppert's board file by make_local_footprints.py.
# Neither is bought or placed by the assembler: fix_schematic.py marks both "not in BOM".
LOCAL_SYMBOLS = {
    # The maker's five gold fingers (his X2, 'Nunchuk-male'): the board edge itself is the socket a Nunchuck plug
    # slides onto. Pin numbers are the maker's (there is no pin 5). Pin 2 is the plug's 'device detect' contact,
    # which the maker left unconnected.
    "Nunchuck_Plug_EdgeFingers": ("X", "Nunchuck plug (board edge fingers)", "sao-nunchuck-local:Nunchuck_Plug_EdgeFingers",
                                  {"SAOPP_ID": "", "MPN": "none: PCB copper, nothing fitted", "LCSC": ""}, 4,
                                  [("3", "3V3", "L", 0), ("1", "SDA", "L", 1), ("4", "SCL", "L", 2),
                                   ("6", "GND", "R", 0), ("2", "DETECT", "R", 1)]),
    # The maker's two Qwiic / STEMMA QT sockets (his X3, X4): JST SH 4-pin, side entry. SAO++ keeps the pads and does
    # not fit the part (it is not on docs/parts.md). MPN and LCSC number are the maker's own fields, not re-checked.
    "Qwiic_JST_SH_NotFitted": ("X", "Qwiic (pads only, not fitted)", "sao-nunchuck-local:Qwiic_JST_SH_SM04B-SRSS-TB_NotFitted",
                               {"SAOPP_ID": "", "MPN": "SM04B-SRSS-TB", "LCSC": "C160404"}, 3,
                               [("2", "3V3", "L", 0), ("3", "SDA", "L", 1), ("4", "SCL", "L", 2), ("1", "GND", "R", 0)]),
}
