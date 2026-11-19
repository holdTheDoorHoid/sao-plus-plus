#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py tars`: mark the solder jumper and the six touch-area dots "not in BOM" (pattern from boards/han-saolo).

tools/gen_schematic.py writes every symbol with (in_bom yes). JP1 and TP1-TP6 are bare copper, nothing to buy or place,
and their KiCad stock footprints say so (exclude_from_bom, exclude_from_pos_files). Without this step the schematic BOM
lists parts the placement file does not, and tools/export_fab.py stops (placement count != BOM count).
Run from the repo root:  python3 boards/tars/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "tars.kicad_sch"
NOT_PARTS = ("JP1", "TP1", "TP2", "TP3", "TP4", "TP5", "TP6")

s = SCH.read_text()
n = 0
for ref in NOT_PARTS:
    # each placed symbol is one '(symbol (lib_id ...' block whose Reference property names it
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    block = m.group(0)
    s = s.replace(block, block.replace("(in_bom yes)", "(in_bom no)"), 1)
    n += 1
SCH.write_text(s)
print(f"{SCH.name}: {n} symbols marked not-in-BOM")
