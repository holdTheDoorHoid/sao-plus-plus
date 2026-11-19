#!/usr/bin/env python3
"""Write hardware/circuit.json: the TARS circuit as data (which part, which pin on which net).

tools/gen_schematic.py tars draws the schematic from it and hardware/build_board.py places and routes from it.
Run: python3 boards/tars/hardware/make_circuit.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
G = 2.54


def at(col, row):
    return [round(50.8 + col * 25 * G, 2), round(40.64 + row * 10 * G, 2)]


PARTS = [
    # --- the XIAO and its power ---
    ("U2", "XIAO_ESP32_Module", at(3, 0), {
        "1": "PRIV_SDA", "2": "OFF_SENSE", "3": "SPK_B", "4": "TFT_MOSI", "5": "SDA", "6": "SCL", "7": "TFT_DC",
        "8": "TFT_SCLK", "9": "PRIV_SCL", "10": "LED_K", "11": "SPK_A", "12": "V3V3", "13": "GND", "15": "BAT+", "16": "GND"}, None),
    ("J1", "SAO_Connector_v1.69bis", at(0, 0), {"1": "VSAO", "2": "GND", "3": "SDA", "4": "SCL"}, None),
    ("SW1", "Power_Switch_SP3T_PCM13", at(0, 1), {"1": "VSAO", "2": "OFF_SW", "3": "V3V3"}, "SAO / OFF / USB-BAT"),
    ("R13", "R_Series_330", at(1, 1), {"1": "OFF_SW", "2": "OFF_SENSE"}, None),
    ("J5", "LiPo_Connector_JST_PH", at(1, 0), {"1": "BAT+", "2": "GND"}, None),
    ("J3", "Conn_Qwiic_JST_SH4", at(0, 2), {"1": "GND", "2": "V3V3", "3": "SDA", "4": "SCL"}, "Qwiic: badge I2C"),
    # --- the display ---
    ("U1", "Display_ST7735S_80x160", at(5, 0), {
        "3": "TFT_MOSI", "4": "TFT_SCLK", "5": "TFT_DC", "6": "TFT_RST", "7": "GND", "8": "GND", "10": "V3V3",
        "11": "GND", "12": "LEDA", "13": "GND"}, None),
    ("R9", "R_11R", at(6, 1), {"1": "V3V3", "2": "LEDA"}, None),
    ("R16", "R_LED_1k3", at(6, 2), {"1": "V3V3", "2": "TFT_RST"}, None),
    ("C1", "C_100n", at(6, 3), {"1": "TFT_RST", "2": "GND"}, None),
    # --- touch: the new touch chip on the private bus, shared with the maker's second Qwiic socket ---
    ("U3", "Touch_CAP1206_SOIC14", at(3, 2), {
        "2": "TOUCH_A", "13": "TOUCH_UP", "12": "TOUCH_B", "11": "TOUCH_LEFT", "10": "TOUCH_DOWN", "9": "TOUCH_RIGHT",
        "4": "PRIV_SDA", "5": "PRIV_SCL", "7": "V3V3", "8": "GND"}, None),
    ("C2", "C_100n", at(4, 3), {"1": "V3V3", "2": "GND"}, None),
    ("R11", "R_LED_1k3", at(2, 2), {"1": "V3V3", "2": "PRIV_SDA"}, None),
    ("R12", "R_LED_1k3", at(2, 3), {"1": "V3V3", "2": "PRIV_SCL"}, None),
    ("J4", "Conn_Qwiic_JST_SH4", at(1, 2), {"1": "GND", "2": "V3V3", "3": "PRIV_SDA", "4": "PRIV_SCL"}, "Qwiic: XIAO's own I2C"),
    ("TP1", "TouchPad_Marker", at(4, 4), {"1": "TOUCH_A"}, "touch A"),
    ("TP2", "TouchPad_Marker", at(4, 5), {"1": "TOUCH_UP"}, "touch up"),
    ("TP3", "TouchPad_Marker", at(4, 6), {"1": "TOUCH_B"}, "touch B"),
    ("TP4", "TouchPad_Marker", at(3, 4), {"1": "TOUCH_LEFT"}, "touch left"),
    ("TP5", "TouchPad_Marker", at(3, 5), {"1": "TOUCH_DOWN"}, "touch down"),
    ("TP6", "TouchPad_Marker", at(3, 6), {"1": "TOUCH_RIGHT"}, "touch right"),
    # --- cue light (front) ---
    ("D1", "LED_0603_Red_Front", at(5, 3), {"2": "LED_A", "1": "LED_K"}, None),
    ("R10", "R_LED_1k3", at(5, 4), {"1": "V3V3", "2": "LED_A"}, None),
    # --- speaker ---
    ("R14", "R_Series_330", at(0, 3), {"1": "SPK_A", "2": "SPK_AR"}, None),
    ("R15", "R_Series_330", at(0, 4), {"1": "SPK_A", "2": "SPK_AR"}, None),
    ("J2", "Conn_Speaker_PicoBlade2", at(1, 3), {"2": "SPK_AR", "1": "SPK_1"}, None),
    ("JP1", "Jumper3_Bridged12", at(1, 4), {"1": "SPK_B", "2": "SPK_1", "3": "GND"}, None),
]

NOTES = [
    "Power: SW1 common = the 3.3 V rail. SAO = badge 3.3 V feeds the rail (and the XIAO through its 3V3 pin). OFF ties D1 to the rail through R13. USB-BAT leaves the badge disconnected; the XIAO runs from USB-C or the LiPo on J5.",
    "Do not plug in USB with the switch on SAO while on a badge: two 3.3 V regulators would share one rail.",
    "Badge I2C (SDA/SCL, J1 and Qwiic J3): XIAO D4/D5 as an I2C target. No pull-ups on this board (the badge has them); the maker's R7/R8 4k7 are gone.",
    "Private I2C (PRIV_SDA/PRIV_SCL, Qwiic J4): XIAO D0/D8 as controller (bit-banged), touch chip U3 at 0x28, pull-ups R11/R12 1.3k. They also hold the C3's start-up pins GPIO2/GPIO8 high.",
    "Display: CS tied to ground (only device on its wires); RST from R16/C1 at power-up (no pin left); backlight always on through R9 11 ohm as the maker had it.",
    "Speaker on J2: D10 -> R14||R15 (165 ohm, limits current to about 19 mA) -> J2 pin 2; D2 -> JP1 -> J2 pin 1. JP1 1-2 bridged = push-pull (maker's default). Cut 1-2 and bridge 2-3 for one-sided drive.",
    "Cue light D1 (front): 3.3 V -> R10 1.3k -> D1 -> D9 (pulled low to light). D9 is the C3's BOOT pin; pressing BOOT also lights it.",
]


def main():
    parts = []
    for ref, sym, xy, nets, value in PARTS:
        p = {"ref": ref, "symbol": sym, "at": xy, "nets": nets}
        if value:
            p["value"] = value
        parts.append(p)
    c = {"title": "TARS - SAO++ edition", "rev": "A",
         "credit": "Original design: davedarko (Dave Darko), 2024, github.com/davedarko/TARS-SAO (MIT)",
         "parts": parts,
         "notes": [[t, [25.4, 215.9 + 3.81 * i]] for i, t in enumerate(NOTES)]}
    (HERE / "circuit.json").write_text(json.dumps(c, indent=1) + "\n")
    print("wrote circuit.json,", len(parts), "parts")


if __name__ == "__main__":
    main()
