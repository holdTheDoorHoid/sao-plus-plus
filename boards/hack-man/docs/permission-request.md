# Permission request to InstantArcade / Bob (draft — not sent)

Status: **drafted 2026-11-10, not sent.** When there is a reply, save it as `permission.md` in this folder (date,
where it was said, exact words), then set `permission: "written"` and `permission_ref: docs/permission.md` in
`board.yml`.

---

Hi Bob,

I'm working on SAO++ (https://github.com/holdTheDoorHoid/sao-plus-plus), an open project that rebuilds classic
add-ons around the 6-pin SAO v1.69bis header and a shared set of parts, so they can be made again in quantity.

I've made a version of your Hack-Man SAO. You didn't publish design files or code, so this is a redraw from
the pictures and write-up on your hackaday.io page, not a copy of your files: the sprites and lettering are
traced from your "Design in Inkscape" picture, the board is laid out from scratch, and the firmware is new
(it follows the behaviour you describe: attract mode, the three extra modes, and your I2C commands at 0x1A).
The differences: no bump-out (a surface-mount header on the back), a Seeed XIAO ESP32 in place of the PY32,
a badge / off / USB-battery switch and a LiPo connector, and the board is about 9 mm taller to fit the XIAO.
It's in the repo now, marked "permission pending, not open-licensed", credited to you. I should have asked
first; if you want it changed or taken down, say so and it's done.

1. May this version stay published in the SAO++ repo, credited to you, under CERN-OHL-S (hardware) and
   CC-BY-SA (art)? If you'd prefer a different license, tell me which.
2. May boards made from it be sold or given away at cons? (If you'd rather it stay non-commercial, I'll mark
   it that way and keep it out of anything I sell.)
3. Would you be willing to share your original KiCad files or firmware? Your attract-mode timing in
   particular would be better than my reconstruction.
4. Is there anything you'd like changed, credited differently, or left out?

Happy to send renders or finished boards. Thanks for making it, and for the write-up on the PY32.
