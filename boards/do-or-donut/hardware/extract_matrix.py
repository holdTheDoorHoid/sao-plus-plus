#!/usr/bin/env python3
"""Extract the maker's LED matrix wiring from original/donut.brd into hardware/matrix.json, and check it.

  python3 boards/do-or-donut/hardware/extract_matrix.py

The IS31FL3731 drives 144 LEDs as two charlieplexed matrices: matrix A on pins CA1..CA9 and matrix B on CB1..CB9.
Each LED sits between two pins of the same matrix, and for each ordered pair of different pins there is exactly
one LED (9 x 8 = 72 per matrix). The checks below prove the maker's board follows that scheme exactly.

Frame position. The chip lights its matrix one "row" pin at a time; register row x of matrix A holds the 8 LEDs
that share pin CAx, and the LED's column y (1..8) is the other pin, counted upward and skipping CAx itself.
The maker's schematic groups the 8 LEDs of each row by their CATHODE (LED1..LED8 all have their cathode on CA1,
LED9..LED16 on CA2, ...), so `frame` assumes "row pin = cathode". If the datasheet's figure turns out to put
the row on the anode, use `frame_if_row_is_anode` instead: both are written for every LED, so firmware only flips
one switch. This is flagged in the README as to be confirmed against the datasheet.
"""
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRD = HERE.parent / "original" / "donut.brd"
OX, OY = 100.0, 150.8              # KiCad X = OX + eagle x, KiCad Y = OY - eagle y (same transform as build_board.py)
CX, CY = 25.4, 25.4                # board centre, eagle coordinates


def frame(row_pin, other_pin):
    m = row_pin[1]                                 # "A" or "B"
    x, o = int(row_pin[2]), int(other_pin[2])
    col = o if o < x else o - 1                    # 1..8, skipping the row pin
    index = 16 * (x - 1) + (8 if m == "B" else 0) + (col - 1)   # 0..143, the order of the PWM registers
    return {"row_pin": row_pin, "col": col, "index": index,
            "ctrl_reg": f"0x{2 * (x - 1) + (1 if m == 'B' else 0):02X}", "ctrl_bit": col - 1,
            "pwm_reg": f"0x{0x24 + index:02X}"}


def main():
    root = ET.parse(BRD).getroot()
    b = root.find("drawing/board")
    pads = {}
    for s in b.find("signals"):
        for c in s.findall("contactref"):
            pads.setdefault(c.get("element"), {})[c.get("pad")] = s.get("name")
    leds = []
    for e in b.find("elements"):
        n = e.get("name")
        if not n.startswith("LED"):
            continue
        k = int(n[3:])
        x, y = float(e.get("x")), float(e.get("y"))
        rot = float(re.sub(r"[^0-9.]", "", e.get("rot") or "R0") or 0)
        a, c = pads[n]["A"], pads[n]["C"]
        dx, dy = x - CX, y - CY
        leds.append({
            "ref": ("DA" if k <= 72 else "DB") + str(k if k <= 72 else k - 72),
            "maker_ref": n,
            "x_mm": round(dx, 3), "y_mm": round(dy, 3),
            "r_mm": round(math.hypot(dx, dy), 3), "angle_deg": round(math.degrees(math.atan2(dy, dx)) % 360, 2),
            "kicad_xy": [round(OX + x, 4), round(OY - y, 4)], "rotation_deg": rot,
            "anode": a, "cathode": c, "matrix": a[1],
            "frame": frame(c, a), "frame_if_row_is_anode": frame(a, c)})
    leds.sort(key=lambda d: (d["matrix"], int(d["ref"][2:])))

    # ---- checks against the IS31FL3731 scheme ----
    assert len(leds) == 144
    for d in leds:
        assert re.fullmatch(r"C[AB][1-9]", d["anode"]) and re.fullmatch(r"C[AB][1-9]", d["cathode"]), d
        assert d["anode"][1] == d["cathode"][1], f"{d['maker_ref']} spans both matrices"
        assert d["anode"] != d["cathode"], f"{d['maker_ref']} has both ends on one pin"
    pairs = Counter((d["anode"], d["cathode"]) for d in leds)
    assert max(pairs.values()) == 1 and len(pairs) == 144, "an ordered pin pair is used twice"
    for m in "AB":
        assert sum(d["matrix"] == m for d in leds) == 72
        for i in range(1, 10):
            p = f"C{m}{i}"
            assert sum(d["anode"] == p for d in leds) == 8 and sum(d["cathode"] == p for d in leds) == 8, p
    for key in ("frame", "frame_if_row_is_anode"):
        assert sorted(d[key]["index"] for d in leds) == list(range(144)), key
    # the maker's numbering is exactly the cathode-row order: LED(8(x-1)+j) has its cathode on CAx (B: LED 72+...)
    for d in leds:
        k = int(d["maker_ref"][3:]) - (72 if d["matrix"] == "B" else 0)
        assert int(d["cathode"][2]) == (k - 1) // 8 + 1, d["maker_ref"]

    out = {
        "about": "Do Or Donut LED matrix, extracted from the maker's Eagle board (original/donut.brd) by hardware/extract_matrix.py. "
                 "One entry per LED. Positions are the LED centre seen from the FRONT, in mm from the board centre, x to the right, "
                 "y UP; angle_deg is counter-clockwise from 3 o'clock. kicad_xy is the same point in the KiCad board file (y down).",
        "driver": {"chip": "IS31FL3731", "ref": "U1", "i2c_address": "0x74 (AD pin tied to GND)",
                   "bus": "private bus: SDA on XIAO D10, SCL on XIAO D3 (see README)",
                   "pins": {f"CA{i}": p for i, p in zip(range(1, 10), (21, 22, 23, 24, 25, 26, 27, 28, 1))}
                   | {f"CB{i}": p for i, p in zip(range(1, 10), range(7, 16))}},
        "frame_note": "frame = position in the chip's frame registers assuming the register row is the LED's CATHODE pin (the maker's "
                      "schematic grouping). ctrl_reg/ctrl_bit = LED on/off register and bit (page 0..7), pwm_reg = PWM register "
                      "(0x24 + index). If the datasheet puts the row on the anode, use frame_if_row_is_anode. TO BE CONFIRMED.",
        "checks_passed": ["every LED is between two different pins of the same matrix",
                          "all 144 ordered pin pairs are different: 72 in matrix A, 72 in matrix B",
                          "every pin is the anode of 8 LEDs and the cathode of 8 LEDs",
                          "both frame mappings use each of the 144 positions exactly once",
                          "the maker's numbering LED1..LED144 follows the cathode-row order"],
        "leds": leds}
    (HERE / "matrix.json").write_text(json.dumps(out, indent=1) + "\n")
    print("matrix.json: 144 LEDs, all checks passed")


if __name__ == "__main__":
    main()
