#!/usr/bin/env python3
"""Write sao-jack-local.pretty: the two through-hole kit footprints, lifted unchanged out of hamster's board file.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-jack/hardware/make_local_footprints.py

The maker used KiCad's stock LED_THT:LED_D3.0mm (with an extra outline on the back silkscreen, so the builder can see
which way round the LED goes from the soldering side) and Resistor_THT:R_Axial_DIN0204_L3.6mm_D1.6mm_P7.62mm_Horizontal.
Both exist only inside his .kicad_pcb, so this script takes D1 and R1 from it, puts each back at the origin, unrotated
and on the front, and saves it as a library footprint with the three SAO++ fields added.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "sao-jack"
load_local(SLUG)
SRC = os.path.join(HERE, "..", "original", "jack", "jack.kicad_pcb")
OUT = os.path.join(HERE, SLUG + "-local.pretty")
os.makedirs(OUT, exist_ok=True)

board = pcbnew.LoadBoard(SRC)
for ref, sym in (("D1", "LED_3mm_THT_Kit"), ("R1", "R_Axial_THT_Kit")):
    _, _, fpid, fields, _, _ = SYMBOLS[sym]
    name = fpid.split(":")[1]
    fp = board.FindFootprintByReference(ref)
    assert fp is not None and str(fp.GetFPID().GetLibItemName()) == name, (ref, fp.GetFPIDAsString())
    if fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(0)
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    fp.SetReference("REF**")
    fp.SetValue(name)
    fp.SetFPID(pcbnew.LIB_ID(SLUG + "-local", name))
    fp.SetPath(pcbnew.KIID_PATH(""))
    for pad in fp.Pads():
        pad.SetNetCode(0)
    for k, v in fields.items():
        f = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, k)
        f.SetText(v)
        f.SetVisible(False)
        f.SetLayer(pcbnew.F_Fab)
        fp.Add(f)
    path = os.path.join(OUT, name + ".kicad_mod")
    if os.path.exists(path):
        os.remove(path)
    pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP).FootprintSave(OUT, fp)   # (pcbnew.FootprintSave cannot guess the type of an empty folder)
    print("wrote", os.path.relpath(path, ROOT), "from the maker's", ref)
