# Permission request to davedarko / Dave Darko (draft — not sent)

Status: **drafted 2026-11-11, extended 2026-11-12, not sent.** Covers the fourteen boards built from
https://github.com/davedarko/Simple-Add-ons-SAO (commit 1a08593): Han SAOlo, Knight Rider, Soot Sprite,
COVID-19 Test, Penghito Poco, Mysterio, Do Or Donut, and (second batch, not yet published when this was written) Vendetta, Hello My Name Is, the LECCO postcard, Sloth, Flux Capacitor, the retro Spacehuhn badge and Mr. Robot. That repository states no license. The Spacehuhn chicken logo is Spacehuhn's (Stefan Kremser), so that board needs his word as well.
When there is a reply, save it as `permission.md` in each board's `docs/` folder (date, where it was said, exact
words), then set `permission: "written"` and `permission_ref: docs/permission.md` in each `board.yml`.

---

Hi Dave,

I'm working on SAO++ (https://github.com/holdTheDoorHoid/sao-plus-plus), an open project that rebuilds
add-ons around the 6-pin SAO v1.69bis header and one shared set of parts, so they can be made again in quantity.
Your "SAO explained" material is a large part of why the project exists.

I've made SAO++ versions of fourteen designs from your Simple-Add-ons-SAO repository: Han SAOlo, Knight Rider,
the Soot Sprite, the COVID-19 Test, Penghito Poco, Mysterio, Do Or Donut, Vendetta, Hello My Name Is, the LECCO
postcard, Mr. Robot, and your three pins (Sloth, Flux Capacitor, retro Spacehuhn) turned into add-ons. Some are
scaled up a little so the header and coin cell fit without covering your lettering; each README gives the factor. Your art and outlines are kept.
The changes are on the back: a surface-mount shrouded header, a badge / off / battery switch, a common coin-cell
clip, and common LEDs where the design allows. Mysterio, Do Or Donut and Mr. Robot get a Seeed XIAO ESP32 in place of, or
alongside, the original controller. Each board's README lists exactly what changed, and where I found something
in the files that looked like a slip (part values that disagree between a readme and a schematic, for instance)
it says so.

Your repository doesn't state a license, so I wanted to ask you directly:

1. May these versions be published in the SAO++ repo, credited to you, under CERN-OHL-S (hardware) and
   CC-BY-SA (art)? If you'd prefer a different license, tell me which.
2. May boards made from them be sold or given away at cons? (If you'd rather they stay non-commercial, I'll
   mark them that way and keep them out of anything I sell.)
3. Penghito Poco is described as a small version of the Penghicorn badge: is that character yours, or should
   someone else be asked as well? The same question for Mysterio, which your write-up says was inspired by
   Simen's Marvel add-ons.
4. Is there anything you'd like changed, credited differently, or left out?

Happy to send renders, the files, or finished boards. And if a clear license in your repo would be easier than
answering this, that works too.
