#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py nsec-bomb`: mark the eight bare wire pads "not in BOM".

tools/gen_schematic.py writes every symbol with (in_bom yes). J2-J9 are bare copper pads, nothing to buy or place, and
their footprint says so (exclude_from_bom, exclude_from_pos_files). Without this step the schematic BOM lists eight
parts the placement file does not, and tools/export_fab.py stops (placement count != BOM count).
Run from the repo root:  python3 boards/nsec-bomb/hardware/fix_schematic.py     (same idea as Han SAOlo's)
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "nsec-bomb.kicad_sch"
NOT_PARTS = ["J%d" % i for i in range(2, 10)]

s = SCH.read_text()
for ref in NOT_PARTS:
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    s = s.replace(m.group(0), m.group(0).replace("(in_bom yes)", "(in_bom no)"), 1)
SCH.write_text(s)
print(f"{SCH.name}: {len(NOT_PARTS)} symbols marked not-in-BOM")
