# Parts only Han SAOlo uses so far (read by tools/saopp_symbols.load_local and tools/gen_schematic.py).
# Footprints live in han-saolo-local.pretty/, each copied unchanged from KiCad 10's stock library (the same stock
# footprints davedarko used in his 2024 KiCad 8 files): Package_SO, Diode_SMD, Jumper and TestPoint.
# LCSC numbers are left empty for the orchestrator to verify and fill in.
LOCAL_SYMBOLS = {
    # The maker's chip: Microchip ATtiny412, 8-pin SOIC (150 mil). The firmware (megaTinyCore, tinyNeoPixel) targets it.
    "ATtiny412_SOIC8": ("U", "ATtiny412", "han-saolo-local:SOIC-8_3.9x4.9mm_P1.27mm",
                        {"SAOPP_ID": "", "MPN": "ATTINY412-SSNR", "LCSC": "C1337190"}, 5,
                        [("1", "VCC", "L", 0), ("2", "PA6", "L", 1), ("3", "PA7", "L", 2), ("4", "PA1/SDA", "L", 3),
                         ("8", "GND", "R", 0), ("7", "PA3", "R", 1), ("6", "PA0/UPDI", "R", 2), ("5", "PA2/SCL", "R", 3)]),
    # The series cell diode docs/standard.md section 3 requires (the ATtiny is wired to SAO SDA and SCL).
    # Same part and footprint as Knight Rider's, so the two boards share one reel.
    "D_Schottky_Cell": ("D", "RB751S40", "han-saolo-local:D_SOD-523",
                        {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
    # The maker's 3-pad solder jumper (his JP2): LED data from the ATtiny (pads 1-2 bridged by copper, as shipped)
    # or, after cutting that bridge and bridging 2-3 with solder, from the badge on SAO GPIO1. Bare copper, nothing to buy.
    "SolderJumper_3_Bridged12": ("JP", "LED data: ATtiny / GPIO1", "han-saolo-local:SolderJumper-3_P1.3mm_Bridged2Bar12_RoundedPad1.0x1.5mm",
                                 {"SAOPP_ID": "", "MPN": "none: PCB copper, nothing fitted", "LCSC": ""}, 3,
                                 [("1", "A", "L", 0), ("3", "B", "L", 1), ("2", "C", "R", 0)]),
    # Bare round copper pads, nothing fitted: the maker's chain-out pad for more LEDs (2 mm), the maker's ground pad
    # (3 mm), and a new UPDI programming pad (1.5 mm).
    "TestPad_2mm": ("TP", "pad", "han-saolo-local:TestPoint_Pad_D2.0mm",
                    {"SAOPP_ID": "", "MPN": "none: bare pad, nothing fitted", "LCSC": ""}, 2, [("1", "~", "L", 0)]),
    "TestPad_3mm": ("TP", "pad", "han-saolo-local:TestPoint_Pad_D3.0mm",
                    {"SAOPP_ID": "", "MPN": "none: bare pad, nothing fitted", "LCSC": ""}, 2, [("1", "~", "L", 0)]),
    "TestPad_1.5mm": ("TP", "pad", "han-saolo-local:TestPoint_Pad_D1.5mm",
                      {"SAOPP_ID": "", "MPN": "none: bare pad, nothing fitted", "LCSC": ""}, 2, [("1", "~", "L", 0)]),
}
