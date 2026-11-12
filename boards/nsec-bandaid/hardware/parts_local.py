# Parts only NorthSec Bandaid uses that the shared SAO++ library does not hold yet (read by
# tools/saopp_symbols.load_local and tools/gen_schematic.py). The footprint lives in nsec-bandaid-local.pretty/,
# copied unchanged from KiCad 10's stock library by make_local_footprints.py. Format as in tools/saopp_symbols.py:
#   name: (ref prefix, value, footprint, fields, half-width, [(pin number, pin name, side, row), ...])
LOCAL_SYMBOLS = {
    # The series cell diode of docs/standard.md section 3 (approved part SAOPP-D-01). Same part, symbol name and
    # footprint as Knight Rider, Han SAOlo and Floppy Disk, so the boards share one reel. It is "local" only because
    # the shared library has no SOD-523 footprint yet.
    "D_Schottky_Cell": ("D", "RB751S40", "nsec-bandaid-local:D_SOD-523",
                        {"SAOPP_ID": "SAOPP-D-01", "MPN": "RB751S40T1G", "LCSC": "C232576"}, 2,
                        [("2", "A", "L", 0), ("1", "K", "R", 0)]),
}
