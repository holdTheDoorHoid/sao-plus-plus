#!/usr/bin/env python3
"""Write sloth-local.pretty: the parts this board needs that the shared SAO++ library does not have.

Run with system Python from the repo root:  python3 boards/sloth/hardware/make_local_footprints.py

All five are copied unchanged from boards/knight-rider/hardware/knight-rider-local.pretty (the brief's already-verified
local parts), where they came from:
  SO08-EIAJ, 2X3_SMD_PAD, TACTILE-SWITCH-1101NE  davedarko's own footprints (SparkFun library). The sloth's Eagle file
                                                 uses the same three SparkFun packages; pad sizes and spacings were
                                                 compared with original/REV1/sloth_final.brd and match.
  LED_0603_..._HandSolder                        davedarko's 0603 LED pattern from the 2024 Knight Rider. The sloth's
                                                 Eagle file has 0805 LEDs; the board uses the red 0603 already chosen
                                                 for Knight Rider so no new LED part is added.
  D_SOD-523                                      KiCad stock Diode_SMD:D_SOD-523 (the cell diode).
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "knight-rider" / "hardware" / "knight-rider-local.pretty"
OUT = HERE / "sloth-local.pretty"
NAMES = ["SO08-EIAJ", "2X3_SMD_PAD", "TACTILE-SWITCH-1101NE", "LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder", "D_SOD-523"]
OUT.mkdir(exist_ok=True)
for n in NAMES:
    (OUT / f"{n}.kicad_mod").write_text((SRC / f"{n}.kicad_mod").read_text())
    print("copied", n)
