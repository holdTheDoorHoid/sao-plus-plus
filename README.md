# SAO++

Classic Simple Add-Ons, rebuilt for today's badges and for real production runs.

SAO++ takes older SAOs (the little art boards that plug into conference badges), ports them to the **SAO v1.69bis** 6-pin standard, adds small improvements where they make sense, and publishes them openly. Every board shares the same connector, power switch, battery holder, and LED family, so they can be built side by side on the same reels and the same assembly setup.

## What every SAO++ board has

- **6-pin SAO v1.69bis connector**, surface-mount and shrouded, on the back. Nothing pokes through the art side.
- **SAO / OFF / BATTERY switch**: runs from the badge or from its own CR2032. It is wired so the badge can never charge the coin cell.
- **CR2032 coin cell**: about a week of daytime wear with two LEDs.
- **Side-firing LEDs** on the back that light up the art from the edges.
- **All parts on the back**; the front is pure art.

The full rules are in [docs/standard.md](docs/standard.md), and the shared parts with live prices are in [docs/parts.md](docs/parts.md).

## Layout

```
boards/<slug>/        one folder per board
  board.yml           provenance, license, permission, features, shared parts used
  README.md           credit to the original maker, what changed, build notes
  hardware/           KiCad 10 project
  art/                source artwork
  production/         Gerbers, drill, BOM and placement files for one board and for a panel
  firmware/           only for boards with a microcontroller
boards/_template/     copy this to start a new board
lib/                  shared KiCad symbols, footprints, 3D models, power block, starter project
docs/                 house standard, approved parts, porting and permission guide
tools/                check_boards.py (paperwork check, runs on every push), gen_footprints.py, saopp_symbols.py,
                      gen_schematic.py, panelize.py, export_fab.py
```

## Boards

| Board | Original maker | Status |
|---|---|---|
| [Fat Pika](boards/fat-pika/) | TwinkleTwinkie (DEF CON 26, 2018) | Designed and rule-checked, not yet built. **Permission pending: not open-licensed**, see the board README |

## Adding a board

Read [docs/porting-guide.md](docs/porting-guide.md). In short: confirm the license or get the maker's permission **first**, copy `boards/_template`, start from `lib/template`, and run `python3 tools/check_boards.py`.

## License

- Hardware designs: [CERN-OHL-S-2.0](LICENSE). Anyone can build and sell these; changes you distribute must stay open.
- Artwork: [CC-BY-SA-4.0](LICENSE-ART).
- **These licenses cover SAO++'s own work only.** A board marked "permission pending" in its README is not open-licensed: its original design and art stay with the original maker.
- Boards ported from other makers keep their credit, and their original license terms are recorded in each `board.yml`. Where a board's original license differs, its README says so and it takes precedence for that board.

Original designs remain credited to their makers. If you made one of these boards and want it changed or removed, open an issue.
