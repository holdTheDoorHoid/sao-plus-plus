"""Parts TARS needs that the shared SAO++ library does not have (yet). Read by tools/saopp_symbols.load_local.

Format as in tools/saopp_symbols.py:
  name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
Land patterns: the maker's own display footprint, Knight Rider's red 0603 LED, and KiCad stock footprints, copied into
tars-local.pretty by make_local_footprints.py. LCSC numbers are left for the orchestrator, except the red LED's (already
checked for Knight Rider).
"""
LOCAL_SYMBOLS = {
    # the maker's display: 0.96 in, 80 x 160 IPS, ST7735S controller, 13-pin ribbon soldered to pads under the glass.
    # Pin names are the maker's (his ST7735S_Display symbol); his files give no part number.
    "Display_ST7735S_80x160": ("U", "ST7735S 80x160", "tars-local:ST7735S-160x80-13PIN",
                               {"SAOPP_ID": "", "MPN": "0.96 in 80x160 ST7735S IPS, 13-pin 0.7 mm solder ribbon (maker gives no part number)", "LCSC": ""}, 4,
                               [("1", "TP0", "L", 0), ("2", "TP1", "L", 1), ("3", "SDA", "L", 2), ("4", "SCL", "L", 3),
                                ("5", "DC", "L", 4), ("6", "RST", "L", 5), ("7", "CS", "L", 6),
                                ("10", "VCC", "R", 0), ("12", "LEDA", "R", 1), ("11", "LEDK", "R", 2), ("8", "GND", "R", 3),
                                ("13", "GND", "R", 4), ("9", "NC", "R", 5)]),
    # NEW chip (not in the maker's design): six-channel capacitive touch controller on the XIAO's private I2C bus. It
    # replaces the maker's six 1 M resistors and six microcontroller pins (see README "Why a touch chip"). Pin numbers
    # and land pattern from KiCad's own library symbol Sensor_Touch:CAP1206-x-SL (SOIC-14); pins 1, 6 and 14 are not
    # in that symbol (not connected). "-1" is the version at I2C address 0x28.
    "Touch_CAP1206_SOIC14": ("U", "CAP1206-1", "tars-local:SOIC-14_3.9x8.7mm_P1.27mm",
                             {"SAOPP_ID": "", "MPN": "CAP1206-1-SL-TR", "LCSC": "C2652106"}, 4,
                             [("2", "CS1", "L", 0), ("3", "~{ALERT}", "L", 1), ("4", "SMDATA", "L", 2), ("5", "SMCLK", "L", 3),
                              ("7", "VDD", "L", 4), ("1", "NC", "L", 5), ("6", "NC", "L", 6),
                              ("13", "CS2", "R", 0), ("12", "CS3", "R", 1), ("11", "CS4", "R", 2), ("10", "CS5", "R", 3),
                              ("9", "CS6", "R", 4), ("8", "GND", "R", 5), ("14", "NC", "R", 6)]),
    # the maker's cue light, on the FRONT where he had it; the red LED already checked for Knight Rider
    "LED_0603_Red_Front": ("D", "red", "tars-local:LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder",
                           {"SAOPP_ID": "", "MPN": "LTST-C191KRKT", "LCSC": "C125099"}, 2,
                           [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    # the maker's display backlight resistor (11 ohm from 3.3 V); no shared value is near it
    "R_11R": ("R", "11", "tars-local:R_0603_1608Metric",
              {"SAOPP_ID": "", "MPN": "0603WAF110JT5E", "LCSC": ""}, 2,
              [("1", "~", "L", 0), ("2", "~", "R", 0)]),
    # the maker's two Qwiic / STEMMA QT sockets (JST SH 4-pin, 1.0 mm): GND, VCC, SDA, SCL
    "Conn_Qwiic_JST_SH4": ("J", "Qwiic", "tars-local:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal",
                           {"SAOPP_ID": "", "MPN": "SM04B-SRSS-TB(LF)(SN)", "LCSC": "C160404"}, 3,
                           [("1", "GND", "L", 0), ("2", "VCC", "L", 1), ("3", "SDA", "L", 2), ("4", "SCL", "L", 3)]),
    # the maker's speaker socket (Molex PicoBlade 2-pin, 1.25 mm); the speaker itself hangs on a lead
    "Conn_Speaker_PicoBlade2": ("J", "speaker", "tars-local:Molex_PicoBlade_53261-0271_1x02-1MP_P1.25mm_Horizontal",
                                {"SAOPP_ID": "", "MPN": "53261-0271", "LCSC": "C177225"}, 2,
                                [("1", "1", "L", 0), ("2", "2", "L", 1)]),
    # marks one of the maker's six touch areas (front copper zones): a 1 mm bare-copper dot inside it, nothing fitted
    "TouchPad_Marker": ("TP", "touch area", "tars-local:TestPoint_Pad_D1.0mm",
                        {"SAOPP_ID": "", "MPN": "none: bare copper inside a touch pad", "LCSC": ""}, 2,
                        [("1", "1", "L", 0)]),
    # the maker's speaker mode jumper: 1-2 bridged by copper (push-pull), cut and bridge 2-3 for one-sided drive
    "Jumper3_Bridged12": ("JP", "speaker mode", "tars-local:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm",
                          {"SAOPP_ID": "", "MPN": "none: solder jumper, nothing fitted", "LCSC": ""}, 2,
                          [("1", "A", "L", 0), ("2", "C", "R", 0), ("3", "B", "L", 1)]),
}
