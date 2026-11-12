#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py sao-nunchuck`: mark the board-copper fingers and the unfitted Qwiic pads.

tools/gen_schematic.py writes every symbol with (in_bom yes) (dnp no). X2 is board copper and X3 / X4 are left unfitted,
and their footprints say so (exclude_from_bom, exclude_from_pos_files; X3 / X4 also do-not-populate). Without this step
the schematic BOM lists three parts the placement file does not, and tools/export_fab.py stops.
Run from the repo root:  python3 boards/sao-nunchuck/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "sao-nunchuck.kicad_sch"
NOT_PARTS = {"X2": False, "X3": True, "X4": True}        # ref: also do-not-populate?

s = SCH.read_text()
for ref, dnp in NOT_PARTS.items():
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    block = m.group(0)
    new = block.replace("(in_bom yes)", "(in_bom no)")
    if dnp:
        assert "(dnp no)" in new
        new = new.replace("(dnp no)", "(dnp yes)")
    s = s.replace(block, new, 1)
SCH.write_text(s)
print(f"{SCH.name}: {len(NOT_PARTS)} symbols marked not-in-BOM")
