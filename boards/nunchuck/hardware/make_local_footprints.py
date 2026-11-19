#!/usr/bin/env python3
"""Write nunchuck-local.pretty: the two parts this board needs that the shared SAO++ library does not have.

Run with system Python from the repo root:  python3 boards/nunchuck/hardware/make_local_footprints.py

  Nunchuk-male   the maker's own Wii-plug tongue (edge fingers), cut out of his 2024 KiCad 8 board file
                 (original/Electronic Design/SAO Nunchuck V1 Design Files KiCAD 8/SAO_Nunchuck.kicad_pcb, part X2).
                 Pads are copied unchanged. Its Edge.Cuts lines (the tongue and the two slots beside it) are taken
                 OUT of the footprint: they live in hardware/outline.json as part of the one board outline, which is
                 what tools/panelize.py and the fab expect. The maker's courtyard is kept.
  JST_SH_...     the Qwiic socket, KiCad's stock Connector_JST footprint, unchanged (the maker used the same pattern).

On top of that this script only adds the SAOPP_ID / MPN / LCSC fields and drops 3D-model links.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAKER_PCB = HERE.parent / "original" / "Electronic Design" / "SAO Nunchuck V1 Design Files KiCAD 8" / "SAO_Nunchuck.kicad_pcb"
STOCK = Path("/home/hoid/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints")
OUT = HERE / "nunchuck-local.pretty"
QWIIC = "JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal"


def prop(k, v):
    return (f'\t(property "{k}" "{v}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(hide yes)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.8 0.8)\n\t\t\t\t(thickness 0.12)\n\t\t\t)\n\t\t)\n\t)\n')


def top_blocks(txt, opener):
    """(start, end) of every top-level '(opener ...)' block in a footprint file (one tab of indent)."""
    out = []
    for m in re.finditer(r"\n\t\(" + opener + r"[ \n]", txt):
        i, depth = m.start() + 2, 0
        for j in range(i, len(txt)):
            depth += txt[j] == "("
            depth -= txt[j] == ")"
            if depth == 0:
                out.append((m.start(), j + 1))
                break
    return out


def cut(txt, spans):
    for a, b in sorted(spans, reverse=True):
        txt = txt[:a] + txt[b:]
    return txt


def add_fields(txt, fields):
    for k in fields:
        assert f'(property "{k}"' not in txt, k
    i = txt.index('\n\t(property "Reference"')
    return txt[:i + 1] + "".join(prop(k, v) for k, v in fields.items()) + txt[i + 1:]


OUT.mkdir(exist_ok=True)

# ---- the maker's tongue, out of his board file --------------------------------------------------
pcb = MAKER_PCB.read_text()
m = re.search(r'\n\t\(footprint "Andy_Footprint_Library:Nunchuk-male"\n', pcb)
i, depth = m.start() + 2, 0
for j in range(i, len(pcb)):
    depth += pcb[j] == "("
    depth -= pcb[j] == ")"
    if depth == 0:
        break
block = pcb[i:j + 1]
fp = "\n".join(line[1:] if line.startswith("\t") else line for line in block.split("\n"))   # one tab less indent
fp = fp.replace('(footprint "Andy_Footprint_Library:Nunchuk-male"', '(footprint "Nunchuk-male"\n\t(version 20240108)\n\t(generator "pcbnew")\n\t(generator_version "8.0")', 1)
fp = re.sub(r"\n\t\(at 107\.5182 114\.2251\)", "", fp, count=1)                              # placement belongs to the board
fp = re.sub(r'\n\t\(descr "[^"]*"\)', '\n\t(descr "Wii Nunchuk plug tongue: edge fingers that the Nunchuk cable plug slides onto. Maker: ageppert (Andrew Geppert), SAO Nunchuck V1 2024, MIT. The tongue and slot outline is in the board outline, not here.")', fp)
fp = re.sub(r'\n\t\(tags "[^"]*"\)', '\n\t(tags "Wii Nunchuk edge connector")', fp)
fp = re.sub(r'\n\t\(property ki_fp_filters "[^"]*"\)', "", fp)
fp = fp.replace('(property "Description" "Nunchuck-male"', '(property "Description" ""')                  # the schematic symbol has none
fp = re.sub(r'\n\t\t\(net \d+ "[^"]*"\)', "", fp)                                            # pad nets belong to the board
fp = re.sub(r'(\(property "Footprint" )"[^"]*"', r'\1"nunchuck-local:Nunchuk-male"', fp)
fp = re.sub(r'(\(property "Reference" )"X2"', r'\1"REF**"', fp)
edges = [(a, b) for a, b in top_blocks(fp, "fp_line") + top_blocks(fp, "fp_arc") if '(layer "Edge.Cuts")' in fp[a:b]]
assert len(edges) == 19, len(edges)
fp = cut(fp, edges)
assert "Edge.Cuts" not in fp and fp.count('(layer "F.CrtYd")') == 1          # the maker's own courtyard is kept
pads = re.findall(r'\(pad "(\d+)"', fp)
assert pads == ["1", "2", "3", "4", "6"], pads
assert fp.count("\n\t(attr smd)") == 1
fp = fp.replace("\n\t(attr smd)", "\n\t(attr smd exclude_from_pos_files exclude_from_bom)")   # copper on the board: nothing to buy or place
fp = add_fields(fp, {"SAOPP_ID": "", "MPN": "none: edge fingers on the board itself", "LCSC": ""})
fp += "\n"
(OUT / "Nunchuk-male.kicad_mod").write_text(fp)
print("wrote", OUT.name + "/Nunchuk-male from the maker's board file (", len(edges), "outline lines moved to outline.json )")

# ---- the Qwiic socket: KiCad stock, unchanged --------------------------------------------------
q = (STOCK / "Connector_JST.pretty" / f"{QWIIC}.kicad_mod").read_text()
q = cut(q, top_blocks(q, "model"))
q = add_fields(q, {"SAOPP_ID": "", "MPN": "SM04B-SRSS-TB(LF)(SN)", "LCSC": ""})
(OUT / f"{QWIIC}.kicad_mod").write_text(q)
print("wrote", OUT.name + "/" + QWIIC, "from KiCad's stock Connector_JST library")
