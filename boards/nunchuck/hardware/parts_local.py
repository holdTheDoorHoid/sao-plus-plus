"""Parts SAO Nunchuck needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land patterns: the maker's own Wii-plug tongue (cut from his 2024 KiCad 8 board) and KiCad's stock JST SH socket, written
into nunchuck-local.pretty by make_local_footprints.py. LCSC numbers are left for the orchestrator.
"""
LOCAL_SYMBOLS = {
    # the point of the board: a tongue of board edge with gold fingers that a Wii Nunchuk's cable plug slides onto.
    # Fingers 1-3 on the back, 4 and 6 on the front, numbered as the maker numbered them (there is no finger 5).
    # Not a bought part: it is copper on the board itself.
    "Wii_Nunchuk_Tongue": ("J", "Wii Nunchuk plug", "nunchuck-local:Nunchuk-male",
                           {"SAOPP_ID": "", "MPN": "none: edge fingers on the board itself", "LCSC": ""}, 3,
                           [("3", "3V3", "L", 0), ("1", "SDA", "L", 1), ("2", "NC", "L", 2),
                            ("6", "GND", "R", 0), ("4", "SCL", "R", 1)]),
    # Qwiic / STEMMA QT socket (JST SH 4-pin, 1.0 mm, side entry), SparkFun's pin order GND, 3V3, SDA, SCL.
    # Two of them, as on the maker's board, to chain other I2C boards off the badge's bus.
    "Qwiic_JST_SH_4": ("J", "Qwiic", "nunchuck-local:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal",
                       {"SAOPP_ID": "", "MPN": "SM04B-SRSS-TB(LF)(SN)", "LCSC": "C160404"}, 3,
                       [("1", "GND", "L", 0), ("2", "3V3", "L", 1), ("3", "SDA", "L", 2), ("4", "SCL", "L", 3),
                        ("MP", "SHELL", "R", 0)]),
}
