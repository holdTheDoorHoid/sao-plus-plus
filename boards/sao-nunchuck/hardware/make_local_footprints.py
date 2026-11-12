#!/usr/bin/env python3
"""One-off helper: lift the two footprints this board keeps from the maker out of his board file into
sao-nunchuck-local.pretty/, so build_board.py can place them like any library part.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-nunchuck/hardware/make_local_footprints.py

  Nunchuck_Plug_EdgeFingers   ageppert's 'Nunchuk-male' (his X2): the five gold fingers a Nunchuck plug grips, three on
                              the back and two on the front. Pads and front silkscreen mark unchanged. His footprint
                              also carried the notch outline as Edge.Cuts lines: those are cut here, because the SAO++
                              outline is one polygon (hardware/outline.json) drawn by build_board.py.
                              Marked exclude-from-BOM / exclude-from-placement: it is board copper, nothing to buy.
  Qwiic_JST_SH_SM04B-SRSS-TB_NotFitted
                              KiCad's stock JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal as ageppert used it (his
                              X3), pads unchanged, but with the solder-paste openings removed and marked
                              exclude-from-BOM / exclude-from-placement / do-not-populate: SAO++ leaves the two Qwiic
                              sockets unfitted (see README).
"""
import os
import re
import sys

import pcbnew
from pcbnew import ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "Electronic Design", "SAO Nunchuck V1 Design Files KiCAD 8", "SAO_Nunchuck.kicad_pcb")
LIB = os.path.join(HERE, "sao-nunchuck-local.pretty")
os.makedirs(LIB, exist_ok=True)

board = pcbnew.LoadBoard(SRC)
fps = {fp.GetReference(): fp for fp in board.GetFootprints()}


def save(ref, name, expect):
    fp = fps[ref]
    if fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(0)             # after the flip: flipping changes the angle
    fp.SetPosition(VECTOR2I(0, 0))
    for pad in fp.Pads():
        pad.SetNetCode(0)
    got = {(p.GetNumber(), round(ToMM(p.GetPosition().x), 3), round(ToMM(p.GetPosition().y), 3)) for p in fp.Pads()}
    assert expect <= got, (ref, sorted(got))
    fp.SetFPID(pcbnew.LIB_ID("sao-nunchuck-local", name))
    fp.SetReference("REF**")
    fp.SetValue(name)
    path = os.path.join(LIB, name + ".kicad_mod")
    if os.path.exists(path):
        os.remove(path)
    pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP).FootprintSave(LIB, fp)
    return path


def cut(txt, keep):
    """Drop every one-tab-indented block for which keep(block) is False."""
    out, i = [], 0
    for m in re.finditer(r"\n\t\((fp_line|fp_arc|fp_rect|fp_poly|fp_circle)[ \n]", txt):
        a = m.start()
        depth = 0
        for j in range(a + 2, len(txt)):
            depth += (txt[j] == "(") - (txt[j] == ")")
            if depth == 0:
                break
        if not keep(txt[a:j + 1]):
            out.append(txt[i:a])
            i = j + 1
    out.append(txt[i:])
    return "".join(out)


def blank_description(txt):
    """The generated schematic symbols have an empty Description; KiCad's parity check wants the footprint's to match."""
    txt, k = re.subn(r'\(property "Description" "[^"]*"', '(property "Description" ""', txt)
    assert k == 1
    return txt


# pad positions as in the maker's file (his footprint coordinates)
p = save("X2", "Nunchuck_Plug_EdgeFingers", {("1", 2.032, 5.08), ("2", 0.0, 5.08), ("3", -2.032, 5.08), ("4", -2.032, 5.08), ("6", 2.032, 5.08)})
t = open(p).read()
n0 = t.count('(layer "Edge.Cuts")')
t = cut(t, lambda b: '(layer "Edge.Cuts")' not in b)
assert n0 == 19 and '"Edge.Cuts"' not in t, n0
t, k = re.subn(r"\n\t\(attr [^)]*\)", "", t)
t = t.replace('\n\t(property "Reference"', '\n\t(attr exclude_from_pos_files exclude_from_bom)\n\t(property "Reference"', 1)
t = blank_description(t)
open(p, "w").write(t)
print("wrote", p, "- cut", n0, "outline lines")

p = save("X3", "Qwiic_JST_SH_SM04B-SRSS-TB_NotFitted", {("1", -1.5, -2.0), ("2", -0.5, -2.0), ("3", 0.5, -2.0), ("4", 1.5, -2.0), ("MP", -2.8, 1.875), ("MP", 2.8, 1.875)})
t = open(p).read()
t, k1 = re.subn(r' "[FB]\.Paste"', "", t)
t, k2 = re.subn(r"\n\t\(attr smd[^)]*\)", "\n\t(attr smd exclude_from_pos_files exclude_from_bom dnp)", t)
assert k1 == 6 and k2 == 1, (k1, k2)
t = blank_description(t)
open(p, "w").write(t)
print("wrote", p, "- paste removed from", k1, "pads")
sys.stdout.flush()
os._exit(0)
