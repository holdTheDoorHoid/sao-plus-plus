#!/usr/bin/env python3
"""Validate every boards/<slug>/ (ports) and originals/<slug>/ (LSOH's own designs) folder against the SAO++ house rules.

Checks (fail = exit 1):
  - board.yml exists, parses, and slug matches the folder name
  - provenance is filled in: original title/makers/source/license, and a permission basis
  - permission "written" must point at evidence (permission_ref)
  - permission "pending" (published before the maker answered) must record the owner's decision, and warns every run
  - every shared_parts id exists in docs/parts.md
  - README.md exists
  - originals/ holds only permission "own" boards, and boards/ holds none; slugs are unique across both

Run from the repo root:  python3 tools/check_boards.py
CI runs the same command.
"""
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from saopp_paths import all_board_dirs, kind_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {"planned", "porting", "prototype", "verified", "released"}
PERMISSIONS = {"license", "written", "own", "pending"}


def known_part_ids():
    text = (ROOT / "docs" / "parts.md").read_text(encoding="utf-8")
    return set(re.findall(r"\bSAOPP-[A-Z]+-\d+\b", text))


def check_board(folder: Path, part_ids: set) -> list:
    errs = []
    meta_path = folder / "board.yml"
    if not meta_path.exists():
        return [f"{folder.name}: missing board.yml"]
    try:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return [f"{folder.name}: board.yml does not parse: {e}"]

    if meta.get("slug") != folder.name:
        errs.append(f"{folder.name}: slug '{meta.get('slug')}' does not match folder name")
    if meta.get("status") not in STATUSES:
        errs.append(f"{folder.name}: status must be one of {sorted(STATUSES)}")

    orig = meta.get("original") or {}
    kind = kind_of(folder)
    # An original has no outside source to link to; a port must say where it came from.
    required = ("title", "makers", "license", "permission") if kind == "original" else ("title", "makers", "source_url", "license", "permission")
    for key in required:
        if not orig.get(key):
            errs.append(f"{folder.name}: original.{key} is empty")
    perm = orig.get("permission")
    if perm and perm not in PERMISSIONS:
        errs.append(f"{folder.name}: original.permission must be one of {sorted(PERMISSIONS)}")
    if kind == "original" and perm != "own":
        errs.append(f"{folder.name}: boards in originals/ are LSOH's own designs; original.permission must be 'own'")
    if kind == "port" and perm == "own":
        errs.append(f"{folder.name}: an 'own' design belongs in originals/, not boards/ (boards/ is for ports of other makers' SAOs)")
    if perm == "written" and not orig.get("permission_ref"):
        errs.append(f"{folder.name}: written permission needs original.permission_ref (link or docs/ file)")
    if perm == "pending":
        # Published before the maker answered, by the repo owner's explicit decision. Allowed, but never silently:
        # the decision must be written down, and the board cannot be called verified or released.
        if not orig.get("pending_decision"):
            errs.append(f"{folder.name}: permission 'pending' needs original.pending_decision (who decided to publish, and when)")
        if meta.get("status") in ("verified", "released"):
            errs.append(f"{folder.name}: a board with pending permission cannot be '{meta.get('status')}'")
        print(f"WARN {folder.name}: published with the original maker's permission still pending")

    for pid in meta.get("shared_parts") or []:
        if pid not in part_ids:
            errs.append(f"{folder.name}: shared part {pid} is not listed in docs/parts.md")

    if not (folder / "README.md").exists():
        errs.append(f"{folder.name}: missing README.md")
    return errs


def main() -> int:
    part_ids = known_part_ids()
    boards = all_board_dirs()
    errors = []
    seen = {}
    for b in boards:
        if b.name in seen:
            errors.append(f"{b.name}: slug used in both {seen[b.name]}/ and {b.parent.name}/; slugs must be unique")
        seen[b.name] = b.parent.name
    for b in boards:
        errors += check_board(b, part_ids)
    for e in errors:
        print("FAIL", e)
    n_orig = sum(1 for b in boards if kind_of(b) == "original")
    print(f"{len(boards)} board(s) checked ({len(boards) - n_orig} ports, {n_orig} originals), {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
