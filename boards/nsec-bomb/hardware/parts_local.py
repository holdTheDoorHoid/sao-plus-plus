# Parts only the NorthSec Bomb uses so far (read by tools/saopp_symbols.load_local and tools/gen_schematic.py).
# There is nothing to buy here: the "part" is a bare copper pad on the front that the builder solders a jumper wire to.
LOCAL_SYMBOLS = {
    # NorthSec's board had eight 0.7 mm plated holes (KiCad's stock single-pin socket footprint, quantity 0 in their
    # parts list: nothing was fitted). Four are on the supply ("3v3"), four each lead to one LED ("Conn1".."Conn4").
    # A wire from a 3v3 point to a Conn point lights that LED. Here each hole is a 1.6 mm square pad with no hole, so
    # nothing pokes through to the back, where the coin cell and the connector now sit.
    "Wire_Pad": ("J", "wire pad", "nsec-bomb-local:WirePad_1.6x1.6mm",
                 {"SAOPP_ID": "", "MPN": "none: bare pad, nothing fitted", "LCSC": ""}, 2, [("1", "~", "L", 0)]),
}
