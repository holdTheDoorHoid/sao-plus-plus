# Parts only the Gold Star board uses so far (read by tools/saopp_symbols.load_local).
# name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row)])
LOCAL_SYMBOLS = {
    # The maker's schematic says NE555, which needs 4.5 V and does not run from 3.3 V or a coin cell. Same choice as the
    # COVID-19 Test board: TI LMC555 (CMOS, 1.5 V to 15 V, same pinout, same SOIC-8). Footprint: KiCad stock
    # Package_SO:SOIC-8_3.9x4.9mm_P1.27mm, copied unchanged. Two boards now use this part: it should move to lib/.
    "Timer_LMC555_SOIC8": ("U", "LMC555", "gold-star-local:SOIC-8_3.9x4.9mm_P1.27mm",
                           {"SAOPP_ID": "", "MPN": "LMC555CMX/NOPB", "LCSC": "C90760"}, 4,
                           [("8", "VCC", "L", 0), ("4", "RESET", "L", 1), ("2", "TRIG", "L", 2), ("6", "THR", "L", 3),
                            ("5", "CV", "L", 4),
                            ("7", "DIS", "R", 0), ("3", "OUT", "R", 1), ("1", "GND", "R", 4)]),
    # The maker's schematic says 4017 (CD4017B: 3 V minimum, and only a fraction of a milliamp of output drive at 3 V).
    # The 74HC4017 is the same counter with the same pinout in high-speed CMOS: 2.0 V to 6.0 V, several milliamps of
    # drive at 3 V. NOT YET CHECKED AT A DISTRIBUTOR: no maker's part number, stock or price has been looked up, so the
    # MPN field only names the type and package. Footprint: KiCad stock Package_SO:SOIC-16_3.9x9.9mm_P1.27mm, unchanged.
    "Counter_74HC4017_SOIC16": ("U", "74HC4017", "gold-star-local:SOIC-16_3.9x9.9mm_P1.27mm",
                                {"SAOPP_ID": "", "MPN": "74HC4017 (SOIC-16)", "LCSC": ""}, 5,
                                [("16", "VCC", "L", 0), ("14", "CP0", "L", 2), ("13", "/CP1", "L", 3), ("15", "MR", "L", 4),
                                 ("8", "GND", "L", 10),
                                 ("3", "Q0", "R", 0), ("2", "Q1", "R", 1), ("4", "Q2", "R", 2), ("7", "Q3", "R", 3),
                                 ("10", "Q4", "R", 4), ("1", "Q5", "R", 5), ("5", "Q6", "R", 6), ("6", "Q7", "R", 7),
                                 ("9", "Q8", "R", 8), ("11", "Q9", "R", 9), ("12", "Q5-9", "R", 10)]),
    # Timing resistor: the same 3.3 M part the COVID-19 Test board uses (no new reel). Footprint: KiCad stock
    # Resistor_SMD:R_0603_1608Metric, copied unchanged (same land pattern as the shared SAOPP_R_0603 footprint).
    "R_Timing_3M3": ("R", "3.3M", "gold-star-local:R_0603_1608Metric",
                     {"SAOPP_ID": "", "MPN": "0603WAF3304T5E", "LCSC": "C26096"}, 2,
                     [("1", "~", "L", 0), ("2", "~", "R", 0)]),
}
