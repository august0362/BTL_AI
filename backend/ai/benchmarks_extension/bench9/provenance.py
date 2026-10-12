"""Pinned identity of the upstream engine that Benchmark 9 runs.

Values were read from the official GitHub release ``sf_19`` (2026-09-05) and checked
locally: the archive SHA-256 matches the digest GitHub publishes for each asset, and the
binary SHA-256 is the hash of the executable inside that archive.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from pathlib import Path

ENGINE_NAME = "Stockfish"
ENGINE_VERSION = "19"
RELEASE_TAG = "sf_19"
SOURCE_COMMIT = "edb0d9db6731067ec50ce619ff372b463bc4dd5d"
SOURCE_URL = "https://github.com/official-stockfish/Stockfish"
LICENSE = "GPL-3.0-only"
# The default network is embedded in the binary (src/evaluate.h: EvalFileDefaultName).
NNUE_NAME = "nn-1a298aa575a0.nnue"
RELEASE_URL = f"{SOURCE_URL}/releases/download/{RELEASE_TAG}"

ENGINE_DIR = Path(__file__).resolve().parent / "engine"


@dataclass(frozen=True)
class ReleaseAsset:
    """One official release archive and the executable inside it."""

    archive: str
    archive_sha256: str
    member: str  # path of the executable inside the archive
    binary_sha256: str | None  # None = not recorded yet (checked against the archive only)

    @property
    def url(self) -> str:
        """Download URL of the archive."""
        return f"{RELEASE_URL}/{self.archive}"

    @property
    def binary_name(self) -> str:
        """File name of the installed executable."""
        return Path(self.member).name


ASSETS: dict[tuple[str, str], ReleaseAsset] = {
    ("windows", "x86_64"): ReleaseAsset(
        "stockfish-windows-x86-64-universal.zip",
        "3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7",
        "stockfish/stockfish-windows-x86-64-universal.exe",
        "45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0",
    ),
    ("windows", "arm64"): ReleaseAsset(
        "stockfish-windows-arm64-universal.zip",
        "8372ad3f0d7276deb2c70f801f541ec7db463219fc6d9c7592864e542aa4f401",
        "stockfish/stockfish-windows-arm64-universal.exe",
        None,
    ),
    ("linux", "x86_64"): ReleaseAsset(
        "stockfish-linux-x86-64-universal.tar.gz",
        "9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f",
        "stockfish/stockfish-linux-x86-64-universal",
        "0f83d24cc46d2c66c60f16001af5444873bc112b7d028594513426894c12da19",
    ),
    ("linux", "arm64"): ReleaseAsset(
        "stockfish-linux-arm64-universal.tar.gz",
        "fe26cfd1d9db4c8af3d21e24d9ff34cacb31c1f940085a7583da11796f2bac01",
        "stockfish/stockfish-linux-arm64-universal",
        None,
    ),
}

_MACHINES = {
    "amd64": "x86_64",
    "x86_64": "x86_64",
    "x64": "x86_64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


def current_platform() -> tuple[str, str]:
    """Return (operating system, CPU architecture) of this machine, normalized."""
    system = "windows" if sys.platform == "win32" else sys.platform
    if system.startswith("linux"):
        system = "linux"
    machine = platform.machine().lower()
    return system, _MACHINES.get(machine, machine)


def asset_for(system: str, machine: str) -> ReleaseAsset:
    """Return the pinned release asset for a platform (ValueError when unsupported)."""
    try:
        return ASSETS[(system, machine)]
    except KeyError:
        supported = ", ".join(f"{s}/{m}" for s, m in ASSETS)
        raise ValueError(
            f"Benchmark 9: no pinned Stockfish build for {system}/{machine} "
            f"(supported: {supported}). Build {RELEASE_TAG} from {SOURCE_URL} and set "
            "[bots.bench_super_alphabeta_nnue] engine_path."
        ) from None


def default_engine_path() -> Path | None:
    """Where the installer puts the executable on this machine (None if unsupported)."""
    try:
        asset = asset_for(*current_platform())
    except ValueError:
        return None
    return ENGINE_DIR / asset.binary_name
