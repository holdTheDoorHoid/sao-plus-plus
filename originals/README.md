# SAO++ Originals

**This folder holds LSOH's own SAO designs.** Everything under `boards/` is a port or recreation of
another maker's SAO; nothing in this folder is. Originals are LSOH's work end to end, so they carry the
SAO++ licences (CERN-OHL-S-2.0 hardware, CC-BY-SA-4.0 art) with no permission question attached.

Each board lives in `originals/<slug>/`, laid out exactly like a port (copy `boards/_template`), with
`original.permission: own` and LSOH as the maker. `tools/check_boards.py` refuses an `own` board in
`boards/` and anything else in `originals/`, so the two never mix. Slugs are unique across both folders.

## First shortlist

Chosen 2026-11-11 from a brainstorm of about 60
cybersecurity-themed ideas. The owner took the suggested top ten as the shortlist.

The goal for these boards: mostly art, plus light. Nothing on them needs a chip. They use only
the shared parts in `docs/parts.md`, except for one possible new part (a self-flashing LED, see the end).

## How each board is lit

- **Back-lit (B):** a reverse-mount LED (SAOPP-LED-10 red, LED-11 white) shines up through a
  window in the board with no copper and no solder mask. The board material itself glows.
  This is how Fat Pika's cheeks work.
- **Side-lit (S):** a side-view LED (the LTST-S270 family: red, yellow or green on the same 1.3 k
  resistor) shines along the board or out through a slot or edge.
- **Front (F):** an LED on the top face, used as an eye, a lamp or a dot.
- **Blink:** a self-flashing LED. This is the only part that is not stocked yet.

## Prior-art check (2026-11-11)

Each idea was checked against the 374 boards in the Badgelife Archive and with a web search on
hackaday.io and Tindie. **No match was found for any of the ten.** The only near miss: MakeItHackin
sells a "Root Access" SAO, but it is a cedar board with NeoPixels, not a terminal prompt. A search
that finds nothing does not prove nothing exists. Do a last check before each board is published.

## The ten

| # | Board | The joke | Art | Light | Notes |
|---|---|---|---|---|---|
| 1 | **Fake Cell Tower** | An IMSI catcher in disguise | A lattice cell tower wearing a groucho nose-and-mustache | Blinking red beacon on top (Blink). Optional back-lit "signal" arcs. | On-brand next to Rayhunter and Open Cell Range. The lattice outline is fine detail; check the minimum slot width. |
| 2 | **Spear Phish** | Phishing | An anglerfish, jaws open, with the lure on a stalk | The lure glows (B, white or yellow-green), maybe the eye too (F) | Strongest silhouette of the ten. The stalk is a thin piece of board: keep it at least 3 mm wide, or it snaps. |
| 3 | **lp0 on fire** | A real Linux kernel error message | A dot-matrix printer with flames and paper feeding out. "lp0 on fire" printed on the paper. | Flames back-lit red and yellow (B) | Deep cut, easy art. |
| 4 | **Hi-Vis Vest + Clipboard** | "Look busy and they'll let you in" | A hi-vis vest with reflective stripes, a clipboard tucked under it | Stripes back-lit white (B) to look reflective | Yellow solder mask makes the vest. Confirm the fab offers yellow. |
| 5 | **Blinking Root Prompt** | The cursor never stops blinking | A tiny terminal window, `root@badge:~#` and a block cursor | Cursor is a blinking LED (Blink) behind a rectangular window | Simplest board here. Black mask with green or white silk. |
| 6 | **Air Gap** | Light leaks across the "air gap" | Two computers facing each other across a real slot cut through the board | Side LED in one computer shines across the slot into the other (S) | The light crossing the slot is the joke. Needs the slot wide enough to read as a gap (about 2-3 mm). |
| 7 | **Side Channel** | A side-channel attack, drawn as a canal | A canal with a little boat, maybe a lock gate | A side LED shines down the length of the canal (S) | Sister board to Air Gap. Same lighting trick. |
| 8 | **Honeypot** | The classic decoy | A honey jar with a dripping lid and bees | Honey back-lit amber (B) | Amber is not a stocked colour: yellow (LTST-S270 family) or white behind yellow mask. |
| 9 | **Badge Reader** | Access control | A wall-mounted card reader with a status lamp | Red lamp lit (F). Optional green lamp driven by the badge's GPIO pin. | On-brand next to Open Door Range and TheTick. Green-on-GPIO needs no chip but only works on badges that drive the pin. |
| 10 | **Get-Out-of-Jail Letter** | The pentester's authorization letter | A letter on letterhead with a wax seal and signature | Wax seal back-lit red (B) | The letter text is the art: keep it short enough to read at silk size. |

## Parts

Every board takes the house set: the SAO connector, the SAO / OFF / BAT switch, the CR2032 clip,
one 1.3 k resistor per LED, and LEDs from the stocked list.

The only possible new part is a **self-flashing LED**, wanted by the Fake Cell Tower and the
Blinking Root Prompt. It is not chosen yet. Options to compare: a self-flashing SMD LED (one part,
no chip), or putting those two boards on the XIAO controller instead (heavier and costlier). The
self-flashing LED must also behave on a 3 V coin cell. Verify that before adopting it.

## Not decided yet


- Board sizes and solder-mask colours for each.
- Who draws the art: the owner, or a draft from Claude for the owner to correct.
- Whether to build all ten at once (one agent per board, as with the port batches) or start with one or two.
