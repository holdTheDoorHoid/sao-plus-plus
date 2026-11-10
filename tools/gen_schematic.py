#!/usr/bin/env python3
"""Generate boards/<slug>/hardware/<slug>.kicad_sch from boards/<slug>/hardware/circuit.json.

SAO++ boards are small, so the circuit is written down once as data (which part, which pin on which net)
and both the schematic and the board script read it. Every pin sits on a named label; unlisted pins get a
no-connect flag.  Run:  python3 tools/gen_schematic.py <slug>
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from saopp_symbols import LIB, SYMBOLS, pin_xy, symbol_sexpr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NS = uuid.UUID("5a0b1b15-0000-4000-8000-00000000a011")
FONT = "(effects (font (size 1.27 1.27)))"


def uid(slug, what):
    return str(uuid.uuid5(NS, f"{slug}:{what}"))


def main(slug):
    hw = ROOT / "boards" / slug / "hardware"
    c = json.loads((hw / "circuit.json").read_text())
    root = uid(slug, "root")
    used = []
    for p in c["parts"]:
        if p["symbol"] not in used:
            used.append(p["symbol"])
    s = f'(kicad_sch (version 20231120) (generator "saopp_gen_schematic") (uuid "{root}") (paper "A4")\n'
    s += f'  (title_block (title "{c["title"]}") (rev "{c["rev"]}") (comment 1 "{c["credit"]}") (comment 2 "Generated from circuit.json - edit that, not this file"))\n'
    s += "  (lib_symbols\n" + "".join(symbol_sexpr(n, LIB + ":").replace("\n", "\n  ") for n in used).rstrip() + "\n  )\n"
    for p in c["parts"]:
        name, ref = p["symbol"], p["ref"]
        prefix, value, fp, fields, _, pins = SYMBOLS[name]
        x, y = p["at"]
        su = uid(slug, ref)
        s += (f'  (symbol (lib_id "{LIB}:{name}") (at {x} {y} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{su}")\n'
              f'    (property "Reference" "{ref}" (at {x} {y - 5.08} 0) {FONT})\n'
              f'    (property "Value" "{p.get("value", value)}" (at {x} {y + (max(r for *_, r in pins) + 2) * 2.54} 0) {FONT})\n'
              f'    (property "Footprint" "{fp}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
              f'    (property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n')
        for k, v in fields.items():
            s += f'    (property "{k}" "{v}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
        for num, *_ in pins:
            s += f'    (pin "{num}" (uuid "{uid(slug, ref + ":" + num)}"))\n'
        s += f'    (instances (project "{slug}" (path "/{root}" (reference "{ref}") (unit 1))))\n  )\n'
        for num, _, side, _ in pins:
            px, py = pin_xy(name, num)
            ax, ay = round(x + px, 2), round(y - py, 2)
            net = p.get("nets", {}).get(num)
            if net:
                ang, just = (180, "right") if side == "L" else (0, "left")
                s += (f'  (global_label "{net}" (shape passive) (at {ax} {ay} {ang}) (effects (font (size 1.27 1.27)) (justify {just})) '
                      f'(uuid "{uid(slug, ref + ":lbl:" + num)}")\n'
                      f'    (property "Intersheetrefs" "" (at {ax} {ay} 0) (effects (font (size 1.27 1.27)) hide)))\n')
            else:
                s += f'  (no_connect (at {ax} {ay}) (uuid "{uid(slug, ref + ":nc:" + num)}"))\n'
    for i, (txt, (x, y)) in enumerate(c.get("notes", [])):
        s += (f'  (text "{txt}" (exclude_from_sim no) (at {x} {y} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) '
              f'(uuid "{uid(slug, "note%d" % i)}"))\n')
    s += '  (sheet_instances (path "/" (page "1")))\n)\n'
    (hw / f"{slug}.kicad_sch").write_text(s)
    # library tables so a fresh clone opens with no setup
    (hw / "sym-lib-table").write_text(f'(sym_lib_table\n  (version 7)\n  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/../../../lib/{LIB}.kicad_sym")(options "")(descr "SAO++ shared symbols"))\n)\n')
    (hw / "fp-lib-table").write_text(f'(fp_lib_table\n  (version 7)\n  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/../../../lib/{LIB}.pretty")(options "")(descr "SAO++ shared footprints"))\n)\n')
    print("wrote", hw / f"{slug}.kicad_sch")


if __name__ == "__main__":
    main(sys.argv[1])
