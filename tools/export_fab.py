#!/usr/bin/env python3
"""Make the files a board house needs, for the single board and (if present) its panel.

  python3 tools/export_fab.py <slug>

Writes into boards/<slug>/production/:
  single/                         one board
    gerbers/                      Gerber RS-274X + Excellon drill files
    <slug>-gerbers.zip            upload this for bare boards
    <slug>-bom-jlcpcb.csv         JLCPCB assembly: bill of materials
    <slug>-cpl-jlcpcb.csv         JLCPCB assembly: component placement list
    <slug>-bom-pcbway.csv         PCBWay assembly: bill of materials
    <slug>-centroid-pcbway.csv    PCBWay assembly: pick-and-place file
  panel/                          same set for <slug>-panel.kicad_pcb (made by tools/panelize.py)

Uses kicad-cli from PATH, or the KiCad flatpak if that is what is installed.
"""
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"


def kicad(*args):
    base = ["kicad-cli"] if shutil.which("kicad-cli") else ["flatpak", "run", f"--filesystem={ROOT}", "--command=kicad-cli", "org.kicad.KiCad"]
    r = subprocess.run(base + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"kicad-cli {' '.join(map(str, args))}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def fab_set(slug, pcb, out, parts, copies):
    """Gerbers, drills, zip, and assembly files for one .kicad_pcb."""
    name = pcb.stem
    g = out / "gerbers"
    if g.exists():
        shutil.rmtree(g)
    g.mkdir(parents=True)
    kicad("pcb", "export", "gerbers", "--layers", LAYERS, "--no-x2", "--no-netlist", "--subtract-soldermask", "-o", str(g) + "/", pcb)
    kicad("pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
          "--excellon-separate-th", "--drill-origin", "absolute", "-o", str(g) + "/", pcb)
    for junk in g.glob("*.gbrjob"):
        junk.unlink()
    for drl in g.glob("*.drl"):                # a drill file with no holes only confuses the upload checker
        if not re.search(r"^X", drl.read_text(), flags=re.M):
            drl.unlink()
    files = sorted(g.iterdir())
    with zipfile.ZipFile(out / f"{name}-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)

    # placement straight from the board, so it always matches the Gerbers
    pos = out / "_pos.csv"
    kicad("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", pos, pcb)
    placed = list(csv.DictReader(io.StringIO(pos.read_text())))
    pos.unlink()

    def base_ref(ref):                      # panel copies are J101, J201 ...: map back to J1
        m = re.fullmatch(r"([A-Za-z]+)(\d)(\d\d)", ref)
        return f"{m.group(1)}{int(m.group(3))}" if (copies > 1 and m) else ref

    by_part = {}
    for row in placed:
        part = parts.get(base_ref(row["Ref"]))
        assert part, f"{row['Ref']} is on the board but not in the schematic BOM"
        by_part.setdefault(part["key"], (part, []))[1].append(row["Ref"])
    assert sum(len(r) for _, r in by_part.values()) == len(parts) * copies, "placement count does not match BOM x copies"
    allrefs = [r["Ref"] for r in placed]
    assert len(allrefs) == len(set(allrefs)), "duplicate designators in the placement file"

    side = {"top": "Top", "bottom": "Bottom"}
    cpl = [[r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm', side[r["Side"]], f'{float(r["Rot"]):g}'] for r in placed]
    write_csv(out / f"{name}-cpl-jlcpcb.csv", ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"], cpl)
    write_csv(out / f"{name}-centroid-pcbway.csv", ["Designator", "Mid X (mm)", "Mid Y (mm)", "Rotation", "Layer"],
              [[r["Ref"], f'{float(r["PosX"]):.4f}', f'{float(r["PosY"]):.4f}', f'{float(r["Rot"]):g}', side[r["Side"]]] for r in placed])

    jlc, pcbway = [], []
    for i, (part, refs) in enumerate(sorted(by_part.values(), key=lambda v: v[1][0]), 1):
        fp = part["Footprint"].split(":")[-1]
        jlc.append([part["Value"], ",".join(refs), fp, part["LCSC"]])
        pcbway.append([i, ",".join(refs), len(refs), part["Maker"], part["MPN"], part["Value"], fp, "SMD",
                       f'LCSC {part["LCSC"]}' if part["LCSC"] else "", ])
    write_csv(out / f"{name}-bom-jlcpcb.csv", ["Comment", "Designator", "Footprint", "LCSC Part #"], jlc)
    write_csv(out / f"{name}-bom-pcbway.csv",
              ["Item #", "Designator", "Qty", "Manufacturer", "Mfg Part #", "Description / Value", "Package/Footprint", "Type", "Your Instructions / Notes"], pcbway)
    print(f"{out.relative_to(ROOT)}: {len(files)} fab files, {len(placed)} placements, {len(by_part)} BOM lines")
    return [f.name for f in files]


MAKERS = {"BH254VS-6P": "XFCN", "PCM13SMTR": "C&K", "BAT-HLD-001": "TE Connectivity / Linx", "LTST-C230KRKT": "Lite-On", "0603WAF1301T5E": "UNI-ROYAL"}


def main(slug):
    board = ROOT / "boards" / slug
    prod = board / "production"
    sch = board / "hardware" / f"{slug}.kicad_sch"
    tmp = prod / "_bom.csv"
    kicad("sch", "export", "bom", "--fields", "Reference,Value,Footprint,MPN,LCSC", "--labels", "Reference,Value,Footprint,MPN,LCSC",
          "--group-by", "", "-o", tmp, sch)
    parts = {}
    for row in csv.DictReader(io.StringIO(tmp.read_text())):
        row["key"] = (row["Value"], row["Footprint"], row["MPN"])
        row["Maker"] = MAKERS.get(row["MPN"], "")
        parts[row["Reference"]] = row
    tmp.unlink()

    listing = {"single": fab_set(slug, board / "hardware" / f"{slug}.kicad_pcb", prod / "single", parts, 1)}
    panel = prod / "panel" / f"{slug}-panel.kicad_pcb"
    if panel.exists():
        info = json.loads((prod / "panel" / "panel-info.json").read_text())
        listing["panel"] = fab_set(slug, panel, prod / "panel", parts, info["boards"])
    return listing


if __name__ == "__main__":
    main(sys.argv[1])
