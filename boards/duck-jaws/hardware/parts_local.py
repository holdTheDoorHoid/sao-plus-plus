# Parts only Duck Jaws uses so far (read by tools/saopp_symbols.load_local and tools/gen_schematic.py).
# The part itself is on the shared list (SAOPP-LED-01, status "chosen" in docs/parts.md), but the shared library has no
# footprint or symbol for the side-firing family yet. Until it does, both live here; the footprint in
# duck-jaws-local.pretty/ was drawn from the Lite-On datasheet (see its description). Promote to lib/ when the
# orchestrator adds LED-01..04 there, and delete this file.
LOCAL_SYMBOLS = {
    "LED_Side_Red": ("D", "red side-firing", "duck-jaws-local:LED_LiteOn_LTST-S270_SideView",
                     {"SAOPP_ID": "SAOPP-LED-01", "MPN": "LTST-S270KRKT", "LCSC": "C125114"}, 2,
                     [("2", "A", "L", 0), ("1", "K", "R", 0)]),
}
