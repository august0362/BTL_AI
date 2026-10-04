"""GUI widgets and screens must use semantic theme colors."""

import re
from pathlib import Path


def test_screens_and_widgets_have_no_literal_colors():
    root = Path(__file__).resolve().parents[3] / "frontend" / "gui"
    pattern = re.compile(r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)|#[0-9a-fA-F]{6}")
    offenders = []
    for folder in (root / "screens", root / "widgets"):
        for path in folder.glob("*.py"):
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(root.parent)))
    assert not offenders, f"literal colors found in: {offenders}"
