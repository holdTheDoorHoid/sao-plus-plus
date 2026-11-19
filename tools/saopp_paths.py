"""Where SAO++ board folders live.

Two kinds of board, kept in separate top-level folders:
  boards/<slug>/     ports and recreations of other makers' SAOs
  originals/<slug>/  LSOH's own designs (SAO++ Originals)

Every tool finds a board by slug through board_dir(), so a slug must be unique across both folders
(tools/check_boards.py enforces this).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"boards": "port", "originals": "original"}


def all_board_dirs():
    """Every board folder in both trees, skipping _template and other _-prefixed folders."""
    out = []
    for top in KINDS:
        base = ROOT / top
        if base.is_dir():
            out += sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_"))
    return out


def board_dir(slug: str) -> Path:
    """The folder for one board, from either tree."""
    hits = [ROOT / top / slug for top in KINDS if (ROOT / top / slug).is_dir()]
    if len(hits) > 1:
        raise SystemExit(f"slug '{slug}' exists in both boards/ and originals/; slugs must be unique")
    if not hits:
        raise SystemExit(f"no board '{slug}' in boards/ or originals/")
    return hits[0]


def kind_of(folder: Path) -> str:
    """'port' for boards/<slug>, 'original' for originals/<slug>."""
    return KINDS[folder.parent.name]
