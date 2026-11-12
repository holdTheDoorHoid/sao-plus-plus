# SAO++ import survey — 2026-11-11

The owner sent about 200 links. Seven research agents went through all of them, reading only (GitHub API and web pages), and I spot-checked the licences of the top picks. **None of the circuits were opened.** "LED-only" and "has a chip" are mostly guessed from the names and READMEs, so whoever ports a board checks the schematic first.

Licence key, against our CERN-OHL-S-2.0 repo:
- **OPEN**: MIT, Apache-2.0 or Unlicense. We can port it and credit the maker. No ask needed.
- **COPYLEFT**: GPL, AGPL or CC-BY-SA. These are a different share-alike licence. We can't relicense under CERN-OHL-S without the maker's OK, or a decision to keep that one board under its original licence.
- **NONE**: no licence. Ask the maker, then publish with the "permission pending" banner if the owner says so, as we did for earlier boards.
- **NC**: "don't sell", which is excluded.

House-standard reminder: any board with a chip gets rebuilt around the XIAO ESP32 plus new Rust firmware (standard 3a). That makes every MCU board below a much bigger job than its original.

---

## 1. SAOs — ranked by how easy they are to import

### Tier A — open licence, editable source, simple (can start now)

| SAO | Maker | Source | Files | Licence | What it is | Notes |
|---|---|---|---|---|---|---|
| SAO Jack | hamster (DC30) | github.com/hamster/defcon30/tree/main/jack | KiCad 8 | MIT ✔ | learn-to-solder blinky, already v1.69bis | Easiest on the list |
| SAO Modem | hamster (DC30) | github.com/hamster/defcon30/tree/main/modem | KiCad 8 + panel | MIT ✔ | blinky LEDs, already v1.69bis | |
| Gold Star | greymanhw (2019) | github.com/greymanhw/gold-star | KiCad 5 | MIT ✔ | star art board | Check the header type |
| Open Sauce Cowboy | calebmarting (OS 2026) | github.com/calebmarting/os2026-badge `Board Files/` | KiCad | MIT ✔ | LED, 1k, switch | |
| Open Sauce Logo SAO | calebmarting | same | KiCad | MIT ✔ | LED | Open Sauce logo is their trademark |
| Sauce Arm, T Piece | calebmarting | same | KiCad | MIT ✔ | unknown | check the circuits |
| NorthSec 2025: Bandaid, Bomb, CashBag, Diamond, SlotMachine, SlotMachine v2 | NorthSec | github.com/nsec/nsec-badge/tree/nsec25/hw/2025/sao | KiCad | MIT ✔ (LICENSE: "except where stated in files") | unknown, probably LED art | Check each file's header for an exception |
| Floppy disk (SMD variant) | Uri Shaked (~2020) | github.com/urish/floppy-disk-sao | KiCad 5 | MIT (README only, no LICENSE file) | I2C EEPROM + LED | New part (24-series EEPROM), and needs the cell diode |
| GPIO-16 (MCP23017) | AND!XOR (DC27) | github.com/ANDnXOR/sao-reference-designs/tree/master/DC27 | schematic PNG + BOM | Apache-2.0 ✔ | I2C expander, 16 LEDs | Redraw from the schematic. New part |
| DC619 EEPROM | AND!XOR (DC27) | same | schematic PNG | Apache-2.0 ✔ | I2C EEPROM at 0x50 | Trivial. Pairs with Floppy (same part) |
| Mad Cat Backpack | Wireb (2018) | github.com/Wireb/Mad_Cat_Backpack | KiCad legacy + hex | MIT ✔ | PIC animation board for Mad Cat | Companion to our Mad Cat. The PIC becomes XIAO, so medium effort |

### Tier B — open licence, but needs a chip rewrite or is hard

| SAO | Maker | Files | Licence | Why it's harder |
|---|---|---|---|---|
| Duck Bath, Duck Jaws | astuder | KiCad 8 | MIT (LICENSE text) | CH32V003 + RGB, so XIAO + firmware. Check the "Jaws" art |
| SAO CORE4 | ageppert | KiCad 8 + BOM | MIT | Hand-wound magnetic cores + MCP23017. Lovely, but hard to build |
| SAO Nunchuck | ageppert | KiCad 8 | MIT | Wii connector pass-through. Hardly any art |
| TARS | davedarko | KiCad + iBOM | MIT ✔ | RP2040 + display. Interstellar IP |
| fpa-sao (DC27) | thedarknet | Eagle | MIT ✔ | Eagle import, unknown circuit |
| Eggplant (DC26) | thedarknet | Eagle + BOM | MIT ✔ | MCU + I2C firmware |
| Metamer v2.1 | eosti | KiCad (Altium originals) | MIT | 16 exotic spectral LEDs + driver. The spectra are the point |
| Spy vs Spy Blackhat/Whitehat | SPIvSPI (DC27) | KiCad 5 | MIT | MAD Magazine characters + firmware |
| Trevor 2018/2019 | AND!XOR | Gerbers only | Apache-2.0 | Must redraw. ATtiny817 |
| Open Sauce Bop It | calebmarting | KiCad | MIT | mic + slider. "Bop It" is Hasbro's |
| Scouter SAO | HTHackers | Gerbers only | GPL-3.0 | redraw + copyleft |

### Tier C — editable source, NO licence (one permission ask per maker unlocks a batch)

| Maker | Boards | Files | Notes |
|---|---|---|---|
| **davedarko** (rest of Simple-Add-ons-SAO) | CongregationRaidTeam2024, Knowledge, MrAnderson, SAO library stick, …stick short, SAO_stick_sideways, DS3231 module connector, SAO_explained | KiCad / Eagle | Same maker as the current batch. The owner's earlier yes covered only those seven, so this needs a fresh yes. Some of these are tools or explainers, not art boards |
| **wrickert** (Untitled Electronics) | RMABadge/SAO: NotCamera, 18650Battery, BatteryTotem, BernieMittens, DesktopHolder, DumpsterFire, InfinityMirrorSquare, Tux, WrenchTotem, ZeldaStones, Python. UntitledElectronics/SAO: Budda, DumpsterFire V1/V2, Korok, LLTB, Rick, ToasterBath (= LLTB copy), ZeldaStones ×4. Plus DC33 satelliteSAO and Defcon31-Tooth | KiCad (legacy and modern) | **Biggest single unlock: about 20 boards, one maker.** Some boards appear in both repos (dedupe). Zelda/Korok are Nintendo's, Bernie is a real person, Tux is free to use |
| **Aerospace Village** | 2022: Caution, Master Warning, Remove Before Flight, gold_star, gold_star v2, JWST, Space Shuttle, SR-71, Village, Crew, Speaker, VORTAC, B-2, An-225, 787 multiplier, 787 Boeing extender. 2023: HAS4, SAO_pin, Crew, Space Shuttle, Speaker | KiCad 6+ + gerbers | About 20 boards, one ask. Mostly LED art. Speaker and VORTAC are probably active. Boeing logo is a trademark |
| **TwinkleTwinkie** | Krusty the It (KiCad zip, LED-only), SAO Hat (KiCad zip, LED-only), Peanut Butter SAO (hackaday 174028, unchecked), Prince OSHCat (OSHPark gerbers), Wireshark 0x4e00 (gerbers, maybe not an SAO), Iron Gauntlet (gerbers, Marvel) | mixed | The permission request we've already drafted for him could add these. Krusty = Simpsons. SAO Hat is a "MAGA"-style political hat, so that's the owner's call. Prince = real-person likeness |
| ec0 / digitalrane | OzSecCon 2019: ecig, keyboard, mult | KiCad 5 | Built for the "LSAO" header variant, so the header has to be redone. mult is probably a splitter |
| badgelife (DC32 crest) | link_sao, triforce_sao | KiCad 8 | Prototypes. Zelda (Nintendo) art |
| ageppert | Etch sAo Sketch v1.0–1.2 | KiCad 8 | His other repos are MIT, so a quick ask. OLED + bridge + pots, so hard |
| Scorch Works | SAO Infinity Mirror | KiCad zip + STL/DXF | LED-only, but it needs laser-cut acrylic mirrors and a bezel |
| tilde.industries | MCH2022 Butterfly | KiCad | |
| Aaron Eiche | Mac SAO | KiCad 9 | README says "open to use", so a quick ask. CH32V003 + OLED. Apple trade dress |
| lle | DC31 Blinky add-on, DC32 SAO | Eagle | STM32, so XIAO rewrite |
| NorthSec 2023 | level1–6 (mycellium, diamond, morel, tripleTH, tripleSMD, 1up) | zips (format unchecked) + BOM | 1up/mushrooms look like Mario |
| deshipu | Duplicant SAO v1/v2 | EasyEDA | Round LCD. Klei (Oxygen Not Included) art |
| NerdFlare | Solder Challenge 26 | KiCad | Solder-practice board, barely an SAO |

### Tier D — copyleft-licence mismatch (owner decision first)

| SAO | Licence | Files | Notes |
|---|---|---|---|
| Vectrex SAO + controller | CC-BY-SA-4.0 | KiCad + BOM | PIC + IS31FL3731. Vectrex trade dress. Best of this group |
| Llama SAO, Trevor Totem | GPL-3.0 (compukidmike/DC26) | KiCad 4/5 + BOM | 4-pin v1. Art-heavy |
| 2022 MiniMage | AGPL-3.0 (DC801/BM-Badge) | KiCad 6+ | |
| Mr Robot badge add-ons (DealWithIt, DickbuttDeauth, HiHowAreYou, Memes, Pogs, Supreme, ThoughtsAndPrayers, TidePod, TrollFace) | GPL-3.0 | Eagle (some boards only half there) | Nearly all third-party trademarks or memes. **Recommend skipping** |
| Furbymin | CC-BY-SA-3.0 | Gerbers only | analog theremin, 65 mm. Hard |
| MalO SAO | CC-BY-SA-3.0 | EasyEDA + KiCad bits | RP2350B and everything else. He sells it right now ($50). **Skip** |

### Tier E — no source at all (redraw from photos or gerbers, like Hack-Man), and needs permission

SAO LoRa Walkie Talkie (gerbers + PDF, ~$15 Reyax module), SAOut Of This World (gerbers + BOM, "Happy Bunny" modified-MIT), Avocato / Mooncake / Lord Commander (gerbers + .sch, no BOM, Final Space IP), Harbinger set (Nick Cage, Bob Ross, Pickle Rick — zips not opened), Bob Ross Happy Trees frame (AND!XOR, Apache, gerbers, passive), lucky OSHCat (fustini, OSHPark gerbers).

**Commercial, no files (uberflux) — recommend leaving alone unless a maker invites it:** He-Meme Man (GZL-2), Badge Crown (000000widow), Not Just a Crosswalk (caelyb), HackThePlanet 555 SAO (HogFillet), Social Battery (znjp). The Agency Wand (000000widow + TrueControl) has a repo at git.trueserve.org that nobody opened yet. It's a wand, not an SAO.

### Already in SAO++ (skip)
Fat Pika, Mad Cat, La Bomba, Big Green, Nibbler, Hack-Man, Mysterio, Soot Sprite, plus the davedarko boards (done or in progress). These links were in the list too.

### Not SAOs — nothing to import
- **Fixtures and tools:** ShittyWall, Shitty Add-On Panel. These two are worth borrowing as an SAO++ **test/display fixture**, not as boards. Also SAO Demo Controller (RP2040 tester: the same idea, could be our bench tester), DMM SAO, Sparky SAO Display stand.
- **Projects:** Core64/Core64c (badge kits), Brushless Motor Biz Card, Small Word Clock, Light Rail, Sympetrum v2, Beep Badge, Mr Stash, Psychoholics pin, Switch Ornament, Stemmett Nixie, Plasma Toroid, Diptyx, CubeRaman, RCKid, Meshtastic Weather Station, Smallest Ultimate Security Board, Skull of Fate (no files were ever posted), Chestoro (firmware only), Skeletor pin, LAVA badge, NYC badge.
- **Excluded:** hamster/trevorforget ("don't sell for profit").
- **Unreachable:** the 3 Reddit threads (Reddit blocks automated fetches), gothconbadge.myshopify.com, the YouTube video ("Space Drop – Solder Project", nothing else readable). These need a look by hand.

---

## 2. Full badges (separated out)

**Badges that contain SAO designs** (the SAOs are already counted above):
DC801/BM-Badge (MiniMage) · compukidmike/DC26 GoonBox (Llama, Trevor Totem) · compukidmike/dc27 Fifth Element (≈10 sub-boards, but structural parts of one assembly, not standalone SAOs, so skip) · Hack-a-Day 2024 Supercon 8 Add-On Badge (i2c_proto_petal KiCad + own LICENSE; petal_matrix and pure_proto_petal Altium-only; Touchwheel lives at todbot/TouchwheelSAO) · AerospaceVillage avBadge_2022 and _2023 · nsec-badge nsec25 (+ a CTF add-on) · nsec badge-conf-2023 · thedarknet darknet8 (fpa-sao) and dc26 (eggplant) · HTHackers ScryptKeeper (Scouter) · wrickert/UntitledElectronics (+ RMABadge) · badgelife/dc32-crest-badge · hamster/defcon30 (not a badge, just the two SAOs) · digitalrane/badgelife · bbenchoff/MrRobotBadge · b1uN7 Flying Skull (Addon_board: a custom 1x6 + 2x3 header, not an SAO).

**Badges with v1.69bis SAO headers** (useful as a known-good host for the "pin-1 check on a real badge" we still owe): Hack-a-Day 2025 Communicator (SAOv2), BTV DC32, DCZia DC27 Laser Theremin (2), DC31 (1), DC32 (2), yolobadge (1), zippy, DC208 Geiger (1), DC27 Enterprise (1), DC801 DC27 party (2 + minibadge), NerdFlare 25, Supercon 2019. If the owner has any of these physically, that's the test rig.

**Minibadge (Saintcon standard, not SAO):** compukidmike/minibadge (spec), minibadge10x10, Saintcon2018–2025 (holders, a 10×10 display, the Klip-on example). These are a different connector and form factor; they could become a separate "minibadge" line later.

**Badges with nothing to extract:** DC801 DC24/25/26/27 Party · AND!XOR DC24, DC28 · eosti + Hack-a-Day 2025 Communicator · Vectorscope · HaDge · compukidmike Bowtie/Screwdriver, dc28, Defcon29 · AerospaceVillage 2020, 2021, 2024 · Dumb-Badge · HTH Elite 2019 · cryptovillage 2015–2018 · BTV DC32 · Cyphercon 5.3 · wrickert/badge, RickRio · UncutGem (a magnetometer, not a badge) · hadbadge2019 · thedarknet DC24, DC25, hhvkit · BCoin2024 · qc16 · dc_sdr · bornhack 2016, 2019–2025 · BHV 2024 · Ben's hivolt · seeess Shoot 31/32/33 (STL only) · hamster SAINTCON, zippy, DC32, DC23/DC26/DC24/DC25/DC22/DC26-party (the DC26 party one is a fork of DC801/DCZia, a duplicate) · seeigecannon ×3 · AustinHackers AHA (RFM69 radio daughterboard, not an SAO) · securelyfitz ×6 · Kermie · DC208 Geiger · dczia DC25–DC32, zippy, yolobadge · waifu-badge.

---

## 3. Recommended order and parallelism

**What actually limits parallelism here** (from batch 2 and the davedarko batch):
1. **Owner decisions, not agents.** Every NONE/COPYLEFT board needs a per-maker yes. Grouping by maker turns ~60 asks into about 8.
2. **Shared files.** `docs/parts.md`, `tools/saopp_board.py`, the README index and the repo CLAUDE.md. Board agents should write only inside `boards/<slug>/`; the orchestrator merges the shared files.
3. **The checkout.** The current agent works directly in `~/Desktop/sao-plus-plus` on `boards/davedarko-2`, with seven boards uncommitted. New agents need their own worktrees, and nobody should start until that batch lands.
4. **CPU for the autorouter.** The router time caps in the repo CLAUDE.md matter. About **6 board agents at once** worked in batch 2. Hold to that.
5. **New parts.** Anything that adds a part (EEPROM, MCP23017) should get the part chosen once, before the boards that use it start.
6. **Chip boards** need XIAO + Rust firmware: Opus, and at most ~3 at once so the firmware can actually be reviewed.

**Waves:**

| Wave | Boards | Needs from owner | Parallel |
|---|---|---|---|
| **0 — now** | Jack, Modem, Gold Star, OS Cowboy, OS Logo, nsec Diamond / CashBag / Bomb / Bandaid / SlotMachine v2 (skip v1) | Nothing (all open) except an OK on the Open Sauce logo | 6 at once, in 2 rounds (≈11 boards) |
| **0b — parts first** | Pick a 24-series EEPROM and an MCP23017 part → then Floppy, DC619 EEPROM, GPIO-16 | Approve the 2 new parts (breaks "fewest parts") | 3 at once |
| **1 — one ask each** | wrickert (~20), Aerospace Village (~20), davedarko remainder (8), TwinkleTwinkie extras (Krusty, Hat, Peanut Butter) | One yes per maker + IP calls (Zelda, Bernie, Simpsons, political hat) | 6 at once; each maker's batch shares one brief |
| **2 — copyleft call** | Vectrex, Llama, Trevor Totem, MiniMage | Decide: ask the maker, or keep these boards under their original licence | 3 |
| **3 — chip boards** | Duck Bath/Jaws, Mad Cat Backpack, CORE4, Nunchuck, TARS, eggplant, fpa-sao, Mac SAO, lle ×2, Metamer, SPIvSPI | Licence asks where marked; firmware licence (still open from Hack-Man) | 3 (Opus) |
| **4 — redraw from photos/gerbers** | LoRa Walkie, SAOut, Infinity Mirror, Iron Gauntlet, Prince OSHCat, Harbinger trio, cybr1d trio, Trevor, Scouter | Permission + IP | 2–3, low priority |

Throughput guess: at six-wide and roughly batch-2 speed, Wave 0 (11 boards) is about a day's work. Wave 1 (~50 boards) takes several days and is gated on the owner's answers, not agent time.
