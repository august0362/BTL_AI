"""Vệ sinh repo — documents/CONTEXT.md §8.1 (7), §9."""

import fnmatch
import shutil
import subprocess

import pytest

from tests._helpers import PROJECT_ROOT

MAX_FILE_BYTES = 5 * 1024 * 1024
FORBIDDEN_PATTERNS = [
    "database/data/*",
    "another/local_tools/*",
    "backend/config/local.toml",
    "backend/ai/*/weights/*",
    "*.pt",
    "*.pth",
    "*.ckpt",
    ".env",
]
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".txt", ".json", ".cfg", ".ini"}
# Ghép chuỗi để chính file này không bị tự phát hiện.
CONFLICT_MARKERS = ("<" * 7 + " ", "<" * 7 + "\n", ">" * 7 + " ", ">" * 7 + "\n")


def tracked_files() -> list[str]:
    if shutil.which("git") is None or not (PROJECT_ROOT / ".git").exists():
        pytest.skip("không phải git repo")
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=PROJECT_ROOT, capture_output=True, check=True
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def test_no_large_files():
    big = [p for p in tracked_files() if (PROJECT_ROOT / p).stat().st_size > MAX_FILE_BYTES]
    assert not big, f"File > 5MB (dùng GitHub Release): {big}"


def test_no_forbidden_paths():
    bad = [p for p in tracked_files() if any(fnmatch.fnmatch(p, pat) for pat in FORBIDDEN_PATTERNS)]
    assert not bad, f"File không được commit: {bad}"


def test_no_conflict_markers():
    bad = []
    for p in tracked_files():
        path = PROJECT_ROOT / p
        if path.suffix not in TEXT_SUFFIXES or not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(True), 1):
            if line.startswith(CONFLICT_MARKERS):
                bad.append(f"{p}:{i}")
    assert not bad, f"Còn marker xung đột merge: {bad}"
