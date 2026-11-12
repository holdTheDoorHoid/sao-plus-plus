#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py nsec-bandaid`: mark the two optional pull-up resistors "not fitted".

R2 and R3 are NorthSec's I2C pull-ups. The SAO++ standard says an add-on carries no pull-ups, so their pads are on the
board but nothing is fitted by default (see the README). tools/gen_schematic.py writes every symbol as a bought,
fitted part; this step marks R2 and R3 "do not populate" and "not in BOM" so that the BOM and placement files leave
them out (hardware/build_board.py sets the same flags on the two footprints).
Same idea as boards/han-saolo/hardware/fix_schematic.py.
Run from the repo root:  python3 boards/nsec-bandaid/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "nsec-bandaid.kicad_sch"
NOT_FITTED = ("R2", "R3")

s = SCH.read_text()
n = 0
for ref in NOT_FITTED:
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\(dnp no\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    block = m.group(0)
    s = s.replace(block, block.replace("(in_bom yes)", "(in_bom no)").replace("(dnp no)", "(dnp yes)"), 1)
    n += 1
SCH.write_text(s)
print(f"{SCH.name}: {n} symbols marked not fitted / not in BOM")
