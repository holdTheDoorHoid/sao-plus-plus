#!/usr/bin/env python3
"""Add the two inner copper layers to Do Or Donut's Gerber sets. Run AFTER `python3 tools/export_fab.py do-or-donut`.

  python3 boards/do-or-donut/production/add_inner_layers.py

tools/export_fab.py exports a fixed two-layer list (F.Cu, B.Cu ...). This board is four-layer, so its In1.Cu and In2.Cu
Gerbers are made here, with the same options, and added to each folder and zip. (Reported to the orchestrator; the
shared tool is not edited from a board folder.)
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROD = Path(__file__).resolve().parent
base = ["kicad-cli"] if shutil.which("kicad-cli") else ["flatpak", "run", f"--filesystem={ROOT}", "--command=kicad-cli", "org.kicad.KiCad"]
for sub, pcb in (("single", ROOT / "boards/do-or-donut/hardware/do-or-donut.kicad_pcb"),
                 ("panel", PROD / "panel/do-or-donut-panel.kicad_pcb")):
    if not pcb.exists():
        continue
    g = PROD / sub / "gerbers"
    r = subprocess.run(base + ["pcb", "export", "gerbers", "--layers", "In1.Cu,In2.Cu", "--no-x2", "--no-netlist",
                               "-o", str(g) + "/", str(pcb)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    for junk in g.glob("*.gbrjob"):
        junk.unlink()
    files = sorted(g.iterdir())
    assert any("In1_Cu" in f.name for f in files) and any("In2_Cu" in f.name for f in files), files
    with zipfile.ZipFile(PROD / sub / f"{pcb.stem}-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)
    print(f"{sub}: {len(files)} Gerber/drill files zipped, inner layers included")
