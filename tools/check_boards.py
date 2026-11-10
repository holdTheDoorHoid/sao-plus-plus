#!/usr/bin/env python3
"""Validate every boards/<slug>/ folder against the SAO++ house rules.

Checks (fail = exit 1):
  - board.yml exists, parses, and slug matches the folder name
  - provenance is filled in: original title/makers/source/license, and a permission basis
  - permission "written" must point at evidence (permission_ref)
  - every shared_parts id exists in docs/parts.md
  - README.md exists

Run from the repo root:  python3 tools/check_boards.py
CI runs the same command.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {"planned", "porting", "prototype", "verified", "released"}
PERMISSIONS = {"license", "written", "own"}


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
    for key in ("title", "makers", "source_url", "license", "permission"):
        if not orig.get(key):
            errs.append(f"{folder.name}: original.{key} is empty")
    perm = orig.get("permission")
    if perm and perm not in PERMISSIONS:
        errs.append(f"{folder.name}: original.permission must be one of {sorted(PERMISSIONS)}")
    if perm == "written" and not orig.get("permission_ref"):
        errs.append(f"{folder.name}: written permission needs original.permission_ref (link or docs/ file)")

    for pid in meta.get("shared_parts") or []:
        if pid not in part_ids:
            errs.append(f"{folder.name}: shared part {pid} is not listed in docs/parts.md")

    if not (folder / "README.md").exists():
        errs.append(f"{folder.name}: missing README.md")
    return errs


def main() -> int:
    part_ids = known_part_ids()
    boards = sorted(p for p in (ROOT / "boards").iterdir() if p.is_dir() and not p.name.startswith("_"))
    errors = []
    for b in boards:
        errors += check_board(b, part_ids)
    for e in errors:
        print("FAIL", e)
    print(f"{len(boards)} board(s) checked, {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
