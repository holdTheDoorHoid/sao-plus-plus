#!/usr/bin/env python3
"""Run after `python3 tools/gen_schematic.py vendetta`: mark the maker's four option resistors "do not populate".

tools/gen_schematic.py writes every symbol with (in_bom yes) (dnp no). R1-R3 (address A0-A2) and R4 (write protect)
are the maker's optional straps; this board leaves them off so the EEPROM answers at 0x50 and can be written.
build_board.py marks the same four footprints DNP / not in BOM / not in the placement file, so the schematic-parity
check and tools/export_fab.py (placement count == BOM count) agree.
Run from the repo root:  python3 boards/vendetta/hardware/fix_schematic.py
"""
import re
from pathlib import Path

SCH = Path(__file__).resolve().parent / "vendetta.kicad_sch"
DNP = ("R1", "R2", "R3", "R4")

s = SCH.read_text()
n = 0
for ref in DNP:
    m = re.search(r'\(symbol \(lib_id "[^"]+"\)[^\n]*\(in_bom yes\)[^\n]*\(dnp no\)[^\n]*\n    \(property "Reference" "' + ref + '"', s)
    assert m, ref
    block = m.group(0)
    s = s.replace(block, block.replace("(in_bom yes)", "(in_bom no)").replace("(dnp no)", "(dnp yes)"), 1)
    n += 1
SCH.write_text(s)
print(f"{SCH.name}: {n} symbols marked DNP / not-in-BOM")
