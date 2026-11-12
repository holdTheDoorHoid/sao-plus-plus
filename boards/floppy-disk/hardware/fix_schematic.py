#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py floppy-disk`: mark the two solder bridges "not in BOM".

tools/gen_schematic.py writes every symbol with (in_bom yes). JP1 and JP2 are bare copper, nothing to buy or place,
and their KiCad stock footprint says so (exclude_from_bom, exclude_from_pos_files). Without this step the schematic
BOM lists two parts the placement file does not, and tools/export_fab.py stops (placement count != BOM count).
Same step as boards/han-saolo/hardware/fix_schematic.py.
Run from the repo root:  python3 boards/floppy-disk/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "floppy-disk.kicad_sch"
NOT_PARTS = ("JP1", "JP2")

s = SCH.read_text()
n = 0
for ref in NOT_PARTS:
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    block = m.group(0)
    s = s.replace(block, block.replace("(in_bom yes)", "(in_bom no)"), 1)
    n += 1
SCH.write_text(s)
print(f"{SCH.name}: {n} symbols marked not-in-BOM")
