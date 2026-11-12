#!/usr/bin/env python3
"""SAO++ schematic symbols: one definition, used for lib/sao-plus-plus.kicad_sym and for generated schematics.

Run:  python3 tools/saopp_symbols.py      (rewrites lib/sao-plus-plus.kicad_sym)
"""
from pathlib import Path

LIB = "sao-plus-plus"
FP = LIB + ":"
G = 2.54

# name: (ref prefix, value, footprint, fields, half-width, [(number, name, side, row)])  row 0 = top
SYMBOLS = {
    "SAO_Connector_v1.69bis": ("J", "SAO v1.69bis", FP + "SAOPP_CONN-01_BoxHeader_2x03_P2.54mm_SMD_XFCN_BH254VS-6P",
                               {"SAOPP_ID": "SAOPP-CONN-01", "MPN": "BH254VS-6P", "LCSC": "C492445"}, 3,
                               [("1", "VCC", "L", 0), ("3", "SDA", "L", 1), ("5", "GPIO1", "L", 2),
                                ("2", "GND", "R", 0), ("4", "SCL", "R", 1), ("6", "GPIO2", "R", 2)]),
    "Power_Switch_SP3T_PCM13": ("SW", "SAO / OFF / BAT", FP + "SAOPP_SW-01_Slide_SP3T_CK_PCM13SMTR",
                                {"SAOPP_ID": "SAOPP-SW-01", "MPN": "PCM13SMTR", "LCSC": "C221842", "Digikey": "401-2017-1-ND"}, 4,
                                [("3", "COMMON", "L", 1), ("1", "POS1", "R", 0), ("2", "POS2", "R", 1), ("4", "POS3", "R", 2)]),
    "CR2032_Clip": ("BT", "CR2032", FP + "SAOPP_BAT-01_CR2032_SMD_TE_BAT-HLD-001",
                    {"SAOPP_ID": "SAOPP-BAT-01", "MPN": "BAT-HLD-001", "LCSC": "C7501066"}, 2,
                    [("1", "+", "L", 0), ("2", "-", "R", 0)]),
    "LED_ThroughBoard_Red": ("D", "red", FP + "SAOPP_LED-10_1206_ReverseMount_ThroughBoard",
                             {"SAOPP_ID": "SAOPP-LED-10", "MPN": "LTST-C230KRKT", "LCSC": "C125107"}, 2,
                             [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    "LED_ThroughBoard_White": ("D", "white", FP + "SAOPP_LED-10_1206_ReverseMount_ThroughBoard",
                               {"SAOPP_ID": "SAOPP-LED-11", "MPN": "LTW-C230DS", "LCSC": "C575513"}, 2,
                               [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    "R_LED_1k3": ("R", "1.3k", FP + "SAOPP_R_0603_1608Metric",
                  {"SAOPP_ID": "SAOPP-R-01", "MPN": "0603WAF1301T5E", "LCSC": "C22767"}, 2,
                  [("1", "~", "L", 0), ("2", "~", "R", 0)]),
    "R_Series_330": ("R", "330", FP + "SAOPP_R_0603_1608Metric",
                     {"SAOPP_ID": "SAOPP-R-02", "MPN": "0603WAF3300T5E", "LCSC": "C23138"}, 2,
                     [("1", "~", "L", 0), ("2", "~", "R", 0)]),
    "C_100n": ("C", "100n", FP + "SAOPP_C_0603_1608Metric",
               {"SAOPP_ID": "SAOPP-C-01", "MPN": "CC0603KRX7R9BB104", "LCSC": "C14663"}, 2,
               [("1", "~", "L", 0), ("2", "~", "R", 0)]),
    "LED_RGB_Side_SK6805": ("D", "SK6805-EC3210R", FP + "SAOPP_LED-20_SK6805-EC3210R_SideView_RGB",
                            {"SAOPP_ID": "SAOPP-LED-20", "MPN": "SK6805-EC3210R", "LCSC": "C5378735"}, 3,
                            [("4", "VDD", "L", 0), ("3", "DIN", "L", 1), ("1", "GND", "R", 0), ("2", "DOUT", "R", 1)]),
    "LiPo_Connector_JST_PH": ("J", "LiPo 3.7 V", FP + "SAOPP_CONN-10_JST_PH_S2B-PH-SM4-TB_1x02_Horizontal",
                              {"SAOPP_ID": "SAOPP-CONN-10", "MPN": "S2B-PH-SM4-TB(LF)(SN)", "LCSC": "C295747"}, 3,
                              [("1", "PIN1", "L", 0), ("2", "PIN2", "L", 1)]),
    "XIAO_ESP32_Module": ("U", "XIAO ESP32-C3 / S3 / C6", FP + "SAOPP_MCU-01_Seeed_XIAO_SMD_C3_S3_C6",
                          {"SAOPP_ID": "SAOPP-MCU-01", "MPN": "XIAO ESP32-C3 / S3 / C6", "LCSC": ""}, 5,
                          [("1", "D0", "L", 0), ("2", "D1", "L", 1), ("3", "D2", "L", 2), ("4", "D3", "L", 3), ("5", "D4/SDA", "L", 4),
                           ("6", "D5/SCL", "L", 5), ("7", "D6/TX", "L", 6), ("16", "BAT-", "L", 7),
                           ("14", "5V", "R", 0), ("13", "GND", "R", 1), ("12", "3V3", "R", 2), ("11", "D10", "R", 3), ("10", "D9", "R", 4),
                           ("9", "D8", "R", 5), ("8", "D7/RX", "R", 6), ("15", "BAT+", "R", 7)]),
}
FONT = "(effects (font (size 1.27 1.27)))"


def pin_xy(name, number):
    """Connection point of a pin in symbol coordinates (y up)."""
    _, _, _, _, hw, pins = SYMBOLS[name]
    for num, _, side, row in pins:
        if num == number:
            x = (-hw - 1) * G if side == "L" else (hw + 1) * G
            return x, -row * G
    raise KeyError((name, number))


def symbol_sexpr(name, lib_prefix=""):
    ref, value, fp, fields, hw, pins = SYMBOLS[name]
    rows = max(r for *_, r in pins)
    top, bot = G, -(rows + 1) * G
    s = f'  (symbol "{lib_prefix}{name}" (pin_names (offset 0.5)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
    s += f'    (property "Reference" "{ref}" (at 0 {top + 1.27} 0) {FONT})\n'
    s += f'    (property "Value" "{value}" (at 0 {bot - 1.27} 0) {FONT})\n'
    s += f'    (property "Footprint" "{fp}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
    s += '    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
    for k, v in fields.items():
        s += f'    (property "{k}" "{v}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
    s += f'    (symbol "{name}_0_1"\n      (rectangle (start {-hw * G} {top}) (end {hw * G} {bot}) (stroke (width 0.254) (type default)) (fill (type background))))\n'
    s += f'    (symbol "{name}_1_1"\n'
    for num, pname, side, row in pins:
        x, y = pin_xy(name, num)
        ang = 0 if side == "L" else 180
        s += (f'      (pin passive line (at {x} {y} {ang}) (length {G}) (name "{pname}" {FONT}) (number "{num}" {FONT}))\n')
    s += '    )\n  )\n'
    return s


def load_local(slug):
    """Merge a board's own extra parts into SYMBOLS and return their names.

    A board that needs a part the shared library does not have yet keeps it in its own folder until it is proven:
      boards/<slug>/ (or originals/<slug>/) hardware/parts_local.py      LOCAL_SYMBOLS = {name: (ref prefix, value, "<slug>-local:<Footprint>", fields, half-width, pins)}
      boards/<slug>/hardware/<slug>-local.pretty  the footprints those symbols name
    tools/gen_schematic.py writes boards/<slug>/hardware/<slug>-local.kicad_sym and both library tables from this."""
    from saopp_paths import board_dir
    path = board_dir(slug) / "hardware" / "parts_local.py"
    if not path.exists():
        return []
    scope = {}
    exec(compile(path.read_text(), str(path), "exec"), scope)
    local = scope["LOCAL_SYMBOLS"]
    for name, spec in local.items():
        assert name not in SYMBOLS or SYMBOLS[name] == spec, f"{name} already exists in the shared library"
        assert spec[2].startswith(f"{slug}-local:"), f"{name}: local footprints must be named '{slug}-local:<Footprint>'"
        SYMBOLS[name] = spec
    return list(local)


def write_lib():
    out = Path(__file__).resolve().parent.parent / "lib" / f"{LIB}.kicad_sym"
    body = "(kicad_symbol_lib (version 20231120) (generator \"saopp_symbols\")\n"
    for name in SYMBOLS:
        body += symbol_sexpr(name)
    out.write_text(body + ")\n")
    print("wrote", out)


if __name__ == "__main__":
    write_lib()
