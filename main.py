"""Điểm khởi chạy game: python main.py"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(_ROOT / "backend"), str(_ROOT / "frontend")]


def main() -> None:
    from gui.app import main as run_gui

    run_gui()


if __name__ == "__main__":
    main()
