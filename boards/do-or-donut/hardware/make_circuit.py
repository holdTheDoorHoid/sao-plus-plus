#!/usr/bin/env python3
"""Write hardware/circuit.json (the circuit as data) for Do Or Donut.

  python3 boards/do-or-donut/hardware/make_circuit.py

The 144 LEDs come from matrix.json (the maker's wiring, extracted and checked by extract_matrix.py); everything else
is listed here. tools/gen_schematic.py and build_board.py both read circuit.json. Schematic positions are on a 2.54 grid.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
M = json.loads((HERE / "matrix.json").read_text())

parts = [
    {"ref": "J1", "symbol": "SAO_Connector_v1.69bis", "at": [33.02, 17.78],
     "nets": {"1": "VSAO", "2": "GND", "3": "SDA", "4": "SCL", "5": "SAO_GPIO1", "6": "SAO_GPIO2"}},
    {"ref": "SW1", "symbol": "Power_Switch_SP3T_PCM13", "at": [33.02, 35.56], "value": "SAO / OFF / USB-BAT",
     "nets": {"3": "V3V3", "1": "VSAO", "2": "OFF_SENSE"}},
    {"ref": "J2", "symbol": "LiPo_Connector_JST_PH", "at": [33.02, 53.34], "nets": {"1": "BAT+", "2": "GND"}},
    {"ref": "R7", "symbol": "R_Series_330", "at": [68.58, 17.78], "nets": {"1": "SAO_GPIO1", "2": "D7_RX"}},
    {"ref": "R8", "symbol": "R_Series_330", "at": [68.58, 30.48], "nets": {"1": "SAO_GPIO2", "2": "D6_TX"}},
    {"ref": "C5", "symbol": "C_100n", "at": [68.58, 43.18], "nets": {"1": "V3V3", "2": "GND"}},
    {"ref": "U2", "symbol": "XIAO_ESP32_Module", "at": [109.22, 17.78],
     "nets": {"2": "OFF_SENSE", "4": "LED_SCL", "5": "SDA", "6": "SCL", "7": "D6_TX", "8": "D7_RX",
              "11": "LED_SDA", "12": "V3V3", "13": "GND", "15": "BAT+", "16": "GND"}},
    {"ref": "R5", "symbol": "R_LED_1k3", "at": [147.32, 17.78], "value": "1.3k", "nets": {"1": "V3V3", "2": "LED_SDA"}},
    {"ref": "R4", "symbol": "R_LED_1k3", "at": [147.32, 30.48], "value": "1.3k", "nets": {"1": "V3V3", "2": "LED_SCL"}},
    {"ref": "R1", "symbol": "R_LED_1k3", "at": [147.32, 43.18], "value": "1.3k", "nets": {"1": "V3V3", "2": "SDB"}},
    {"ref": "R6", "symbol": "R_20k", "at": [271.78, 17.78], "nets": {"1": "R_EXT", "2": "GND"}},
    {"ref": "C1", "symbol": "C_100n", "at": [271.78, 30.48], "nets": {"1": "C_FILT", "2": "GND"}},
    {"ref": "U1", "symbol": "IS31FL3731_SSOP28", "at": [198.12, 17.78],
     "nets": {"2": "V3V3", "5": "GND", "19": "LED_SDA", "20": "LED_SCL", "18": "GND", "3": "SDB", "16": "C_FILT", "6": "R_EXT"}
     | {str(p): n for n, p in M["driver"]["pins"].items()}},
    {"ref": "C3", "symbol": "C_100n", "at": [243.84, 17.78], "nets": {"1": "V3V3", "2": "GND"}},
    {"ref": "C4", "symbol": "C_100n", "at": [243.84, 30.48], "nets": {"1": "V3V3", "2": "GND"}},
]
# LEDs in reference order, 10 columns (shorter ones on the right, clear of the title block)
HEIGHTS = [15, 15, 15, 15, 15, 15, 14, 14, 13, 13]
slots = [(c, r) for c, hgt in enumerate(HEIGHTS) for r in range(hgt)]
for k, d in enumerate(M["leds"]):
    c, r = slots[k]
    parts.append({"ref": d["ref"], "symbol": "LED_0603_Matrix", "at": [20.32 + c * 27.94, round(63.5 + r * 7.62, 2)],
                  "nets": {"2": d["anode"], "1": d["cathode"]}})

notes = [
    ["SAO++ edition of davedarko's Do Or Donut: 144 LEDs\\nand IS31FL3731 are his circuit, unchanged (matrix.json).\\nDriver on a private I2C bus: D10 SDA, D3 SCL, 0x74.", [220.98, 45.72]],
    ["SW1: SAO = badge feeds the 3.3 V rail. OFF = XIAO D1\\nhigh, firmware sleeps. USB-BAT = XIAO feeds the rail.\\nNever USB and SAO at once. To confirm against the\\ndatasheet: R6, C1, C3-C5.", [220.98, 54.61]],
]
c = {"title": "Do Or Donut - SAO++ edition", "rev": "A",
     "credit": "Original design: davedarko (Dave Darko), 2019, github.com/davedarko/Simple-Add-ons-SAO",
     "parts": parts, "notes": notes}
(HERE / "circuit.json").write_text(json.dumps(c, indent=1) + "\n")
print("circuit.json:", len(parts), "parts")
