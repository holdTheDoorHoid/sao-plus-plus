#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py han-saolo`: mark the bare copper pads and the solder jumper "not in BOM".

tools/gen_schematic.py writes every symbol with (in_bom yes). TP1-TP3 and JP1 are bare copper, nothing to buy or place,
and their KiCad stock footprints say so (exclude_from_bom, exclude_from_pos_files). Without this step the schematic BOM
lists four parts the placement file does not, and tools/export_fab.py stops (placement count != BOM count).
Run from the repo root:  python3 boards/han-saolo/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "han-saolo.kicad_sch"
NOT_PARTS = ("TP1", "TP2", "TP3", "JP1")

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
