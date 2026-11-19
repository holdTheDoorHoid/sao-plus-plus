#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py nunchuck`: mark the Wii tongue J2 "not in BOM".

tools/gen_schematic.py writes every symbol with (in_bom yes). J2 is gold fingers on the board edge, nothing to buy or
place, and its footprint says so (exclude_from_bom, exclude_from_pos_files). Without this step the schematic BOM lists a
part the placement file does not. Same fix as boards/han-saolo/hardware/fix_schematic.py.
Run from the repo root:  python3 boards/nunchuck/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "nunchuck.kicad_sch"
NOT_PARTS = ("J2",)

s = SCH.read_text()
n = 0
for ref in NOT_PARTS:
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    block = m.group(0)
    s = s.replace(block, block.replace("(in_bom yes)", "(in_bom no)"), 1)
    n += 1
SCH.write_text(s)
print(f"{SCH.name}: {n} symbol marked not-in-BOM")
