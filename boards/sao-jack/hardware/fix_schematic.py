#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py sao-jack`: mark the six kit parts "not in BOM".

tools/gen_schematic.py writes every symbol with (in_bom yes). R1, R2 and D1-D4 are the through-hole parts the buyer
solders (that is what hamster's kit is for), so the assembly house must not be asked to fit them: their footprints are
left out of the placement file, and this step leaves them out of the assembly BOM to match. Without it
tools/export_fab.py stops (placement count != BOM count). The kit parts are listed in ../README.md instead.
Run from the repo root:  python3 boards/sao-jack/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "sao-jack.kicad_sch"
KIT_PARTS = ("R1", "R2", "D1", "D2", "D3", "D4")

s = SCH.read_text()
for ref in KIT_PARTS:
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    block = m.group(0)
    s = s.replace(block, block.replace("(in_bom yes)", "(in_bom no)"), 1)
SCH.write_text(s)
print(f"{SCH.name}: {len(KIT_PARTS)} kit parts marked not-in-BOM")
