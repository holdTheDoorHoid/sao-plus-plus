# Wave 1 permission requests (drafts — not sent)

Status: **drafted 2026-11-12, nothing sent, nobody contacted.** These are for the owner to send himself.
Wave 1 is the group in `docs/import-survey-2026-11-11.md` where one yes from one maker unlocks a whole batch.
Everything below was checked read-only on 2026-11-12 (GitHub listings and public web pages). No design file
was opened and no picture was looked at, so what each board shows and whether it has a chip is still taken
from folder names and the makers' own descriptions. Anything marked **not verified** is exactly that.

| Maker | Boards a yes would unlock | Where to send | Status |
|---|---|---|---|
| wrickert / Untitled Electronics | 19 boards with design files (the survey said "about 20") | X/Twitter @wrickert7 (the only handle on his GitHub profile); fallback: open a GitHub issue on `wrickert/UntitledElectronics` | not sent |
| Aerospace Village | 18 designs (16 from 2022, 2 new in 2023; three exist in a 2022 and a 2023 version) | village@aerospacevillage.org (printed on their GitHub profile and their website) | not sent |
| davedarko (the remaining boards) | 6 boards with design files, plus one art-only folder (the survey said 8) | Same conversation as the earlier fourteen: his hackaday.io profile (hackaday.io/davedarko) or Mastodon @davedarko@chaos.social; fallback: GitHub issue on `davedarko/Simple-Add-ons-SAO` | not sent |
| TwinkleTwinkie (the extra boards) | 3 with editable files (Krusty The It, SAO Hat, Peanut Butter), 2 with production files only, 1 with no files | Same conversation as the earlier five: X/Twitter @mrtwinkletwink or a hackaday.io private message | not sent |

**No repo turned out to be openly licensed.** All four makers' Wave 1 sources state no licence, so all four
asks are needed. One side finding: davedarko's separate `YoDawgSAO` repo **is** MIT-licensed and is not in the
survey's open-licence list; it needs no ask (see his section).

When a reply comes in, do what the earlier requests say: save it as `permission.md` in each board's `docs/`
folder (date, where it was said, exact words), then set `permission: "written"` and
`permission_ref: docs/permission.md` in each `board.yml`. A "no", or a "yes except X", is recorded the same way.

Things the survey got wrong or left out are collected at the end.

---

## 1. wrickert / Untitled Electronics

### What was checked

- Two repositories hold the add-ons, both under the personal account `wrickert` (Iowa, US). "Untitled
  Electronics" is his brand name, not a separate GitHub organisation.
  - https://github.com/wrickert/RMABadge, commit `e248fe7` (2026-04-29), folder `SAO/`
  - https://github.com/wrickert/UntitledElectronics, commit `616d06b` (2026-06-02), folder `SAO/`, and
    `Badges/Defcon33/Schematics/satelliteSAO`
- **Licence: none.** GitHub reports no licence for either repo and there is no LICENSE file for his own work.
  The two READMEs contain only their titles: "# RMABadge" and "# UntitledElectronics". The licence-like files
  that do exist belong to other people's material bundled in the repos (CircuitPython, chip-maker code, a
  parts-library notice from SamacSys) and say nothing about his boards.
- **He sells some of these.** A web search shows an Untitled Electronics shop on Tindie
  (tindie.com/stores/untitledelec) with listings for the Dumpster Fire, "This is Not a Camera" and
  BernieMittens add-ons. The shop page itself refused an automated read, so stock and his contact button are
  **not verified**. The request below says plainly that we know he sells them.
- All design files are KiCad. Older boards are in the old KiCad format, newer ones in the current format;
  most folders also carry production (gerber) files.

Boards, with duplicates between the two repos merged:

| Board | Where | Notes |
|---|---|---|
| This is Not a Camera (`NotCamera`) | RMABadge | |
| Dumpster Fire, version 1 | both repos, identical files | |
| Dumpster Fire, version 2 (`DumpsterElectroFire`) | UntitledElectronics | |
| BernieMittens | RMABadge | three variants: with chair, no chair, "Metal" |
| Tux | RMABadge | |
| Python | RMABadge | |
| Infinity Mirror Square | RMABadge | has a firmware folder, so it has a chip; also has laser-cut parts |
| Zelda stones: Goron's Ruby, Kokiri Emerald, Zora's Sapphire, Master Sword (4 boards) | both repos | Master Sword identical in both; the three stones differ, UntitledElectronics also has panels. Which copy is newer: not verified |
| Korok | UntitledElectronics | |
| LLTB / Toaster Bath | UntitledElectronics, two folders | both hold a board named LLTB; the files differ. Treated as one design; which is current: not verified |
| Rick | UntitledElectronics | has picture frames and code alongside, so probably a small screen and a chip: not verified |
| Satellite SAO (DEF CON 33) | UntitledElectronics, inside the Defcon33 badge folder | |
| 18650 Battery, Battery Totem, Wrench Totem, Desktop Holder (4 boards) | RMABadge | by their names these look like stands or power holders for add-ons, not add-ons themselves: not verified. The SAO++ changes may not apply to them |

That is 19 boards with design files. Not counted: `Budda` (one drawing, no board) and the separate
`wrickert/Defcon31-Tooth` repo (commit `6023fa0`), which is a blank KiCad starter template in the DEF CON 31
add-on outline, not a design of his. Its README invites people to "modify and adapt" it but states no licence.
It is left out of the request.

### Where to send

1. X/Twitter **@wrickert7**: the only contact on his GitHub profile (no e-mail, no website listed).
2. The Tindie shop's "contact seller" button, if the owner can see one when he opens the page (not verified).
3. Fallback: open a GitHub issue on `wrickert/UntitledElectronics` (issues are switched on, none open). An
   issue is public, which is fine for this request. His real name is not shown anywhere checked, so the
   request does not use one.

### Request text

Hi,

I'm working on SAO++ (https://github.com/holdTheDoorHoid/sao-plus-plus), an open project that takes classic
add-ons and updates them to the 6-pin SAO v1.69bis header with a shared set of parts, so they can be built
again in quantity.

I'd like to make SAO++ versions of the add-ons in your RMABadge and UntitledElectronics repositories. Nothing
of yours is in the project yet; I'm asking before starting. The boards are:

- This is Not a Camera
- Dumpster Fire (versions 1 and 2)
- BernieMittens
- Tux
- Python
- Infinity Mirror Square
- the four Zelda boards (Goron's Ruby, Kokiri Emerald, Zora's Sapphire, Master Sword)
- Korok
- LLTB / Toaster Bath
- Rick
- the DEF CON 33 Satellite SAO
- and, if you count them as add-ons, the 18650 Battery, Battery Totem, Wrench Totem and Desktop Holder

What would change: your art and outlines are kept, and your credit stays on the board. On the back, each board
gets a surface-mount shrouded 6-pin header, a badge / off / battery switch and a CR2032 clip, and the parts
move to the back so the front is art only. Any board with a controller chip gets a Seeed XIAO ESP32 module and
new firmware in its place. Each board's README would list exactly what changed.

Your repositories don't state a license, so I wanted to ask you directly:

1. May these versions be published in the SAO++ repo, credited to you, under CERN-OHL-S-2.0 (hardware) and
   CC-BY-SA-4.0 (art)? If you'd prefer a different license, tell me which.
2. May boards made from them be sold or given away at cons? I know you sell some of these yourself on Tindie.
   If you'd rather they stay non-commercial, or you'd rather I leave out the ones you still sell, say so and
   I'll mark them that way and keep them out of anything I sell.
3. How would you like to be credited: wrickert, Untitled Electronics, or something else?
4. Is there anything you'd like changed or left out?

A short answer is plenty: "yes to all", "yes except …", or "no". If anything is published and you later want
it changed or taken down, say so and it's done. Happy to send renders or finished boards.

### Third-party art in this batch (the maker cannot grant these; owner's separate decision)

- **Zelda stones ×4 and Korok:** Nintendo (The Legend of Zelda).
- **BernieMittens:** the likeness of a real person (Bernie Sanders, from the 2021 inauguration photograph,
  which has its own photographer).
- **Python:** the folder holds the Python logo; that logo is a trademark of the Python Software Foundation.
- **Tux:** the Linux penguin. The survey calls it free to use; its terms ask for credit to its artist (Larry
  Ewing). Wording of those terms: not verified here.
- **This is Not a Camera:** the art folder holds a camera picture from a clip-art site (kisspng). Who owns
  that picture: not verified.
- **Desktop Holder:** the art folder holds a pattern downloaded from patternhead.com, with a note that reads
  "You're free to use the contents of the download within the terms of use." Those terms: not verified.
- **Rick:** what or whom this shows was not checked (pictures were not opened). If it is a TV character or a
  real person, it belongs on this list.
- **Satellite SAO:** made for a DEF CON 33 badge. Whether it carries a village's or DEF CON's logo: not verified.

---

## 2. Aerospace Village

### What was checked

- https://github.com/AerospaceVillage/avBadge_2022, commit `ea3bf75` (2022-08-02)
- https://github.com/AerospaceVillage/avBadge_2023, commit `6da17b7` (2024-07-06)
- **Licence: none.** GitHub reports no licence for either repo and neither has a LICENSE file. The 2022 README
  says only: "A collection of v1.69 SAO badges to be presented at DefCon 2022" plus two diary lines. The 2023
  README lists the two badges and "A number of SAOs the Village is making." The one licence file in the 2023
  repo is SnapEDA's, for a bought-in connector footprint, not for the village's designs. The village website
  says nothing about a licence for its badges.
- All boards are KiCad, each with production (gerber) files. A few 2022 folders also carry old-format leftovers.
- Most of the design work was committed by the GitHub users `daneallen` and `mmayes`. The village may pass
  the question to them.

| Year | Boards |
|---|---|
| 2022 (16) | Caution; Master Warning; Remove Before Flight; Gold Star; Gold Star v2; James Webb telescope; Space Shuttle; SR-71; Village (the Aerospace Village logo); Crew; Speaker; VORTAC; B-2; An-225; 787 SAO multiplier; 787 with Boeing logo SAO extender |
| 2023 (5) | HAS4; SAO pin; and Crew, Space Shuttle, Speaker again |

The three boards that appear in both years have the same names but different files, so the 2023 ones are
later versions, not copies. Counting each design once gives **18** (17 if Gold Star and Gold Star v2 are one).
The two 787 boards are, by their names, a splitter and an extension for other add-ons rather than art boards;
Speaker and VORTAC probably have active circuits. None of that is verified.

### Where to send

**village@aerospacevillage.org**: shown on their GitHub organisation profile and under "Contact" on
https://www.aerospacevillage.org/. The site also lists a Discord, X (@SecureAerospace) and Bluesky
(aerospacevillage.bsky.social). Fallback: a GitHub issue on `AerospaceVillage/avBadge_2022` (issues are
switched on, none open).

### Request text

Hello Aerospace Village,

I'm working on SAO++ (https://github.com/holdTheDoorHoid/sao-plus-plus), an open project that takes classic
add-ons and updates them to the 6-pin SAO v1.69bis header with a shared set of parts, so they can be built
again in quantity.

I'd like to make SAO++ versions of the add-ons the village published with its DEF CON 2022 and 2023 badges.
Nothing of yours is in the project yet; I'm asking before starting. The boards are:

- from avBadge_2022: Caution, Master Warning, Remove Before Flight, Gold Star (both versions), James Webb
  telescope, Space Shuttle, SR-71, the Village logo, Crew, Speaker, VORTAC, B-2, An-225, and the two 787 boards
- from avBadge_2023: HAS4, SAO pin, and the 2023 versions of Crew, Space Shuttle and Speaker

What would change: the art and outlines are kept, and the village's credit stays on each board. On the back,
each board gets a surface-mount shrouded 6-pin header, a badge / off / battery switch and a CR2032 clip, and
the parts move to the back so the front is art only. Any board with a controller chip gets a Seeed XIAO ESP32
module and new firmware in its place. Each board's README would list exactly what changed.

Neither repository states a license, so I wanted to ask directly:

1. May these versions be published in the SAO++ repo, credited to the Aerospace Village, under CERN-OHL-S-2.0
   (hardware) and CC-BY-SA-4.0 (art)? If you'd prefer a different license, tell me which.
2. May boards made from them be sold or given away at cons? (If you'd rather they stay non-commercial, I'll
   mark them that way and keep them out of anything I sell.)
3. How should the credit read, and should the people who drew the boards be named?
4. Is the village's own logo board (the "Village" SAO) one you would rather keep to yourselves?
5. Is there anything else you'd like changed or left out?

A short answer is plenty: "yes to all", "yes except …", or "no". If this needs to go to whoever designed the
boards, please pass it on. If anything is published and you later want it changed or taken down, say so and
it's done. Happy to send renders or finished boards.

### Third-party art in this batch (the village cannot grant these; owner's separate decision)

- **787 with Boeing logo SAO extender:** the Boeing logo is Boeing's trademark. The plain "787 SAO multiplier"
  still uses a Boeing aircraft name and shape.
- **B-2, SR-71, An-225:** real aircraft by Northrop Grumman, Lockheed and Antonov. A plain silhouette is a
  lower risk than a logo; whether any of these boards carries a maker's logo or lettering: not verified.
- **Space Shuttle, James Webb telescope:** NASA subjects. Whether the NASA logo appears on them (its use is
  restricted): not verified.
- **HAS4:** probably the Hack-A-Sat 4 competition, which has its own organisers and logo: not verified.
- **Gold Star:** another maker (greymanhw) has an MIT-licensed "Gold Star" add-on, listed in the survey's
  open group. Whether the village's Gold Star is related to it: not verified.
- The Aerospace Village's own logo is theirs to grant; it is asked about in the request (question 4).

---

## 3. davedarko (the remaining boards)

### What was checked

- https://github.com/davedarko/Simple-Add-ons-SAO, commit `1a08593` (2026-05-21): the same commit the
  fourteen earlier boards were built from.
- **Licence: none.** GitHub reports no licence, there is no LICENSE file, and the README (a description and a
  table of designs) has no licence statement.
- The earlier request (`boards/han-saolo/docs/permission-request.md`) covers fourteen boards and is marked
  "not sent". All fourteen are already public in SAO++ with the "permission pending" banner, by the owner's
  decisions of 2026-11-11 and 2026-11-12 recorded in each `board.yml`. **If the earlier request has still not
  gone out, send the two together**; the text below reads correctly either way.

What is actually left in the repository:

| Folder | Files | What it is |
|---|---|---|
| `MrAnderson` | KiCad | "Skate SAO": a board that takes fingerboard (toy skateboard) trucks, with a quote by the skateboarder Andy Anderson. His README calls it work in progress |
| `DS3231_Module_Connector` | KiCad | "The Schedule SAO": an adapter that plugs a bought clock module into a badge; the print looks like a November 2024 calendar |
| `SAO library stick` | KiCad | a stick that holds and shows off a row of add-ons; not an add-on itself |
| `SAO library stick short` | KiCad | shorter version of the same |
| `SAO_stick_sideways` | KiCad | sideways version of the same |
| `SAO_explained` | KiCad | his teaching board for the SAO header |
| `CongregationRaidTeam2024` | two drawings (SVG) only | art with no board files; could only be a redraw |
| `Knowledge`, `Add-Ons`, `Slides` | text and one PDF | write-ups and a talk, not boards. Nothing to port |

So a yes unlocks **6 boards with design files and one art-only folder**, not 8. Three of the six are display
sticks and one is a teaching board: for those the owner should decide first whether an SAO++ version makes
sense at all (a stick that holds add-ons has no use for a coin cell).

**Openly licensed, no ask needed:** his separate repository https://github.com/davedarko/YoDawgSAO (commit
`4dd3db0`) carries an **MIT** licence, like his TARS repository that the survey already lists as open. It is
not part of this request. Its art has its own third-party questions (see below).

### Where to send

The same route as the earlier request. Visible routes: his hackaday.io profile (hackaday.io/davedarko, the
site listed on his GitHub profile) and the Mastodon handle he prints on his own boards,
**@davedarko@chaos.social**. Fallback: open a GitHub issue on `davedarko/Simple-Add-ons-SAO` (issues are
switched on, none open).

### Request text

Hi Dave,

This follows on from my note about the fourteen SAO++ versions of your add-ons
(https://github.com/holdTheDoorHoid/sao-plus-plus). To be straight about where that stands: all fourteen are
public in the repo now, each marked "permission pending, not open-licensed" and credited to you. I should have
asked first, and the offer in that note holds: if you want any of them changed or taken down, say so and it's
done.

There are a few more things in your Simple-Add-ons-SAO repository I'd like to ask about before touching them.
None of these is in SAO++ yet:

- the Skate SAO (MrAnderson)
- the Schedule SAO (the DS3231 module connector)
- the three library sticks (long, short and sideways)
- SAO explained
- the Congregation Raid Team 2024 art (there are drawings but no board files, so this would be a redraw)

For the add-ons the treatment would be the same as before: your art, outlines and credits kept; on the back a
surface-mount shrouded 6-pin header, a badge / off / battery switch and a CR2032 clip, with the parts moved to
the back. The sticks and SAO explained are tools more than add-ons, so there I'd mostly be swapping to the
shared header and keeping everything else as you drew it.

The questions are the same as last time:

1. May SAO++ versions of these be published in the repo, credited to you, under CERN-OHL-S-2.0 (hardware) and
   CC-BY-SA-4.0 (art)? If you'd prefer a different license, tell me which.
2. May boards made from them be sold or given away at cons? (If you'd rather they stay non-commercial, I'll
   mark them that way and keep them out of anything I sell.)
3. The Congregation Raid Team art: is that yours to share, or should someone else be asked as well?
4. Is there anything you'd like changed, credited differently, or left out?

A short answer is plenty: "yes to all", "yes except …", or "no", and one answer can cover both notes. As
before, if a clear license in your repo would be easier than answering this, that works too.

### Third-party art in this batch (the maker cannot grant these; owner's separate decision)

- **Skate SAO (MrAnderson):** carries the name of, and a quote by, a real person (the skateboarder Andy
  Anderson); the folder also holds a photo named after his board. Dave's README calls it a homage.
- **Congregation Raid Team 2024:** whose emblem this is was not established: not verified. Question 3 asks
  Dave whose it is; it does not ask him to grant it.
- **Schedule SAO:** the print refers to the Hackaday Supercon 2024 weekend (dates only, as far as his README
  says). Whether a Hackaday logo is on it: not verified.
- Not in this request, but for the record on the MIT-licensed **YoDawgSAO**: its README describes a picture of
  the rapper Xzibit (a real person), an Iron Man face plate (Marvel), the Hackaday logo and the xHain
  hackspace logo. The MIT licence covers Dave's design, not those.

---

## 4. TwinkleTwinkie (the extra boards)

### What was checked

TwinkleTwinkie publishes on hackaday.io, not GitHub (his only GitHub repository is a fork of a drawing tool).
His hackaday.io profile lists 34 projects. The six the survey names:

| Board | Page | What is published | Licence |
|---|---|---|---|
| Krusty The It ("A Terrifying Clown", his DC26 add-on #1) | hackaday.io/project/158664-krusty-the-it | `Krusty_the_It_hackaday.zip`, described as "Completely raw KiCad Project & Gerbers". Two shine-through LEDs, one resistor, 4-pin header, no chip | none stated |
| SAO Hat (his DC26 add-on #5; his own subtitle calls it a "MAGA" style hat; "The words light up white.") | hackaday.io/project/159524-sao-hat | `SAO_Hat_hackaday.zip`, "KiCad Project & Gerbers" | none stated |
| Peanut Butter SAO (about how to pronounce "GIF") | hackaday.io/project/174028-peanut-butter-sao | `GIF_4L_2019-07-23-0017.zip`, "Final 4 Layer version of GIF". What is inside the zip (KiCad or production files only): not verified. **It is a 4-layer board**; SAO++ boards so far are 2-layer | none stated |
| Prince OSHCat DEF CON 27 SAO | oshpark.com/shared_projects/xlZW21Nt | a production-file zip on OSH Park and a parts-list link; no editable source seen | none stated |
| Wireshark 0x4e00 (with Nick Pisarro) | hackaday.io/project/168570-wireshark-0x4e00 | production files, a schematic PDF and ready-built firmware. His page calls it a "Pin/Mini Badge", not an add-on: it has its own coin cell, a small chip and a buzzer that plays a tune. 4-layer | none stated |
| Iron Gauntlet (DC27) | hackaday.io/project/165322-iron-gauntlet-dc27-sao | **no board files.** Only an LED footprint zip; the page speaks of an "eventual" release of the production files | none stated |

- **Licence: none on any of the six pages**, the same as for the five boards already in SAO++.
- The earlier request (`boards/fat-pika/docs/permission-request.md`) covers Fat Pika, Mad Cat, Big Green,
  La Bomba and Nibbler and is marked "not sent". Those five are already public with the "permission pending"
  banner (owner's decision 2026-11-10). **If the earlier request has still not gone out, send the two
  together**; the text below reads correctly either way.
- He sells add-ons on Tindie (the Krusty and SAO Hat pages both link to his listings). Whether those two are
  still on sale: not verified.
- Wave 1 in the survey is the first three boards. The other three are in the request as a lighter, optional
  question, because two need a redraw from production files and one has no files at all.

### Where to send

The same route as the earlier request. Visible routes: X/Twitter **@mrtwinkletwink** (on both his GitHub and
hackaday.io profiles) and a private message on hackaday.io (hackaday.io/TwinkleTwinkie; his listed website
twinkletwinkie.com simply forwards there). There is no repository of his own to open an issue on.

### Request text

Hi TwinkleTwinkie,

This follows on from my note about the SAO++ versions of your DC26 add-ons
(https://github.com/holdTheDoorHoid/sao-plus-plus). To be straight about where that stands: Fat Pika, Mad Cat,
Big Green, La Bomba and Nibbler are public in the repo now, each marked "permission pending, not
open-licensed" and credited to you. I should have asked first, and the offer in that note holds: if you want
any of them changed or taken down, say so and it's done.

There are three more of yours I'd like to do, and this time I'm asking before starting. None of these is in
SAO++ yet:

- Krusty The It
- SAO Hat
- Peanut Butter SAO

They would get the same treatment as the first five: your art and outlines unchanged on the front and your
credit kept on the board; on the back a surface-mount shrouded 6-pin header, a SAO / OFF / battery switch and
a CR2032 clip, with the LEDs swapped for current reverse-mount parts at a low current so a coin cell lasts.
Each board's README would list exactly what changed.

The questions are the same as last time:

1. May SAO++ versions of these three be published in the repo, credited to you, under CERN-OHL-S-2.0
   (hardware) and CC-BY-SA-4.0 (art)? If you'd prefer a different license, tell me which.
2. May boards made from them be sold or given away at cons? (If you'd rather they stay non-commercial, or
   you still sell any of them yourself, I'll mark them that way and keep them out of anything I sell.)
3. Is there anything you'd like changed, credited differently, or left out?

And one optional extra: I'd also like to do Prince OSHCat, Wireshark 0x4e00 and Iron Gauntlet, but I can only
find production files for the first two and none for the gauntlet. If you're happy for those to be included
and would be willing to share the KiCad files, that would be much better than a redraw. If not, no problem,
and I'll leave them alone.

A short answer is plenty: "yes to all", "yes except …", or "no", and one answer can cover both notes. Happy
to send renders or finished boards.

### Third-party art in this batch (the maker cannot grant these; owner's separate decision)

- **Krusty The It:** the name points at Krusty the Clown (The Simpsons, owned by Disney / 20th Television) and
  at "It" (Pennywise: Stephen King's character, Warner Bros. films). A visitor on his page says the teeth and
  eyes look like Pennywise. The picture itself was not looked at.
- **SAO Hat:** a political campaign hat in the "MAGA" style, in his own words. The exact wording on the hat
  was not checked. Whether SAO++ should carry a political item at all is the owner's call, apart from any
  trademark question about the slogan.
- **Peanut Butter SAO:** a joke on "GIF" against the Jif peanut butter brand (J.M. Smucker). Whether the
  board imitates the Jif label: not verified, but likely from the name.
- **Prince OSHCat:** OSHCat is OSH Park's mascot, so OSH Park would need to be asked as well as the maker.
  The survey says the art is also a likeness of the musician Prince (a real person, with an estate); the
  OSH Park page does not describe the picture, so that is not verified.
- **Wireshark 0x4e00:** "Wireshark" is the name of a well-known network tool with its own trademark and shark
  logo; the board plays what OSH Park's page calls a children's song, and tunes have their own owners. Which
  song: not verified. A second person, Nick Pisarro, is credited and would need to agree too.
- **Iron Gauntlet:** the Infinity Gauntlet and its six stones are Marvel's (Disney).

---

## What the survey had wrong or left out

- **wrickert:** "Budda" is a single drawing with no board. "ToasterBath (= LLTB copy)" is not an exact copy:
  both folders hold a board called LLTB, but the files differ. "ZeldaStones ×4" is three stones plus the
  Master Sword. Dumpster Fire version 1 is the same files in both repos. `Defcon31-Tooth` is a blank template
  in DEF CON's outline, not one of his designs. Four of the RMABadge "SAOs" look like stands or holders. The
  survey did not notice that he sells several of these on Tindie, or the Python logo, the clip-art camera and
  the patternhead pattern.
- **Aerospace Village:** the repo names were right. The three boards repeated in 2023 are revised versions,
  not duplicates. There is a public contact e-mail.
- **davedarko:** 6 boards with files, not 8. "Knowledge" is two text files; "CongregationRaidTeam2024" is two
  drawings. `YoDawgSAO` (MIT) is missing from the survey's open-licence tables.
- **TwinkleTwinkie:** Iron Gauntlet is listed as "gerbers", but no board files are published. Peanut Butter
  is a 4-layer board. Wireshark has a co-author and is a pin badge by his own description. His hackaday.io
  profile also lists other add-ons the survey does not mention (Unicorn, Chestoro, I'm 40% UFO!, Kupo!, Iron
  Man SAO, Laughing Skull, Big Deal With It Foot, No Step On Snek, Lucky OSHCat, That's A Big Twinkie, The
  Child, Clack Clack); none of those pages was checked, and they are not in the request.

## Not verified (in one place)

- No circuit, drawing or picture was opened. What each board shows, and which boards have a chip, comes from
  names and the makers' own text.
- The Untitled Electronics Tindie shop page (it refused an automated read): what is on sale, and whether it
  offers a way to message him.
- wrickert's real name; whether "Rick" shows a third party; which copy of the duplicated boards is current.
- Whether the Aerospace Village boards carry NASA, aircraft-maker or Hack-A-Sat logos; who at the village
  answers licence questions.
- What is inside the Peanut Butter zip and the Prince OSHCat zip; the wording on the SAO Hat; the Prince
  likeness; which tune Wireshark plays.
- Whether either of the two earlier requests (davedarko, TwinkleTwinkie) has been sent since their files were
  last updated. Both files still say "not sent".
