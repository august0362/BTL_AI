"""Chuyển bộ quân SVG sang PNG (dùng pygame-ce, không cần thư viện thêm).

Dùng:
    python another/tools/svg_to_png.py `
        frontend/gui/assets/pieces/rhosgfx/svg `
        frontend/gui/assets/pieces/rhosgfx --size 256
"""

import argparse
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

PIECE_NAMES = [c + p for c in "wb" for p in "KQRBNP"]


def convert(src_dir: Path, dst_dir: Path, size: int) -> list[Path]:
    """Chuyển 12 file <màu><quân>.svg trong src_dir thành PNG size×size trong dst_dir."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in PIECE_NAMES:
        src = src_dir / f"{name}.svg"
        if not src.exists():
            raise FileNotFoundError(src)
        surface = pygame.image.load_sized_svg(str(src), (size, size))
        dst = dst_dir / f"{name}.png"
        pygame.image.save(surface, str(dst))
        written.append(dst)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--size", type=int, default=256)
    args = parser.parse_args()
    for path in convert(args.src, args.dst, args.size):
        print(path)


if __name__ == "__main__":
    main()
