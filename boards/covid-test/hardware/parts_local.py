# Parts only the COVID-19 Test board uses so far (read by tools/saopp_symbols.load_local).
# name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row)])
LOCAL_SYMBOLS = {
    # The maker's readme asks for an LMC555 ("3V capable"); his schematic says NE555D, which needs 4.5 V and does not
    # run reliably from 3.3 V or a coin cell. The LMC555 (TI, CMOS) runs from 1.5 V to 15 V, same pinout, same SOIC-8.
    # Footprint: KiCad stock Package_SO:SOIC-8_3.9x4.9mm_P1.27mm (the one the maker used), copied unchanged.
    "Timer_LMC555_SOIC8": ("U", "LMC555", "covid-test-local:SOIC-8_3.9x4.9mm_P1.27mm",
                           {"SAOPP_ID": "", "MPN": "LMC555CMX/NOPB", "LCSC": "C90760"}, 4,
                           [("8", "VCC", "L", 0), ("4", "RESET", "L", 1), ("2", "TRIG", "L", 2), ("6", "THR", "L", 3),
                            ("5", "CV", "L", 4),
                            ("7", "DIS", "R", 0), ("3", "OUT", "R", 1), ("1", "GND", "R", 4)]),
    # The two timing resistors (one value, used twice). Footprint: KiCad stock Resistor_SMD:R_0603_1608Metric, copied
    # unchanged (the same land pattern as the shared SAOPP_R_0603 footprint).
    "R_Timing_3M3": ("R", "3.3M", "covid-test-local:R_0603_1608Metric",
                     {"SAOPP_ID": "", "MPN": "0603WAF3304T5E", "LCSC": "C26096"}, 2,
                     [("1", "~", "L", 0), ("2", "~", "R", 0)]),
}
