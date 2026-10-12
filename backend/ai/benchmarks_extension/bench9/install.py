"""Install the pinned Stockfish 19 build for Benchmark 9 and check that it plays.

Usage (from the project root, with PYTHONPATH=backend)::

    python -m ai.benchmarks_extension.bench9.install           # install if missing, then check
    python -m ai.benchmarks_extension.bench9.install --check   # only check the installed engine
    python -m ai.benchmarks_extension.bench9.install --force   # download again

Nothing here runs during a game: bots only look for the installed file.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import chess
import chess.engine

from ai.benchmarks_extension.bench9 import provenance
from ai.benchmarks_extension.bench9.engine import EngineError, EngineSettings, UciEngine

LICENSE_FILES = ("Copying.txt", "AUTHORS", "README.md")
DOWNLOAD_TIMEOUT_S = 60.0


def sha256_file(path: Path) -> str:
    """SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, expected_sha256: str) -> bytes:
    """Download ``url`` into memory and verify its SHA-256 (ValueError on mismatch)."""
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_S) as response:  # noqa: S310
        data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"archive checksum mismatch: expected {expected_sha256}, got {actual}")
    print(f"  {len(data) / 1e6:.1f} MB, sha256 OK")
    return data


def read_members(archive: str, data: bytes, names: list[str]) -> dict[str, bytes]:
    """Read the named archive members (by full path or by base name) into memory."""
    found: dict[str, bytes] = {}
    if archive.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zipped:
            for info in zipped.infolist():
                key = _match(info.filename, names)
                if key and not info.is_dir():
                    found[key] = zipped.read(info)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tarred:
            for member in tarred.getmembers():
                key = _match(member.name, names)
                handle = tarred.extractfile(member) if key and member.isfile() else None
                if handle is not None:
                    found[key] = handle.read()
    return found


def _match(name: str, wanted: list[str]) -> str | None:
    for key in wanted:
        if name == key or (name.count("/") == 1 and name.endswith("/" + key)):
            return key
    return None


def install(asset: provenance.ReleaseAsset, dest: Path, force: bool = False) -> Path:
    """Download, verify and unpack the engine binary plus its license files into ``dest``."""
    binary = dest / asset.binary_name
    if binary.is_file() and not force:
        if asset.binary_sha256 is None or sha256_file(binary) == asset.binary_sha256:
            print(f"Already installed: {binary}")
            return binary
        print("Installed binary does not match the pinned checksum; reinstalling")
    data = download(asset.url, asset.archive_sha256)
    members = read_members(asset.archive, data, [asset.member, *LICENSE_FILES])
    if asset.member not in members:
        raise ValueError(f"{asset.member} not found in {asset.archive}")
    executable = members.pop(asset.member)
    actual = hashlib.sha256(executable).hexdigest()
    if asset.binary_sha256 is not None and actual != asset.binary_sha256:
        raise ValueError(f"binary checksum mismatch: expected {asset.binary_sha256}, got {actual}")
    dest.mkdir(parents=True, exist_ok=True)
    partial = binary.with_name(binary.name + ".part")
    partial.write_bytes(executable)
    partial.chmod(partial.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(partial, binary)
    for name, content in members.items():
        (dest / name).write_bytes(content)
    record = {
        "engine": f"{provenance.ENGINE_NAME} {provenance.ENGINE_VERSION}",
        "release_tag": provenance.RELEASE_TAG,
        "source_commit": provenance.SOURCE_COMMIT,
        "source_url": provenance.SOURCE_URL,
        "license": provenance.LICENSE,
        "archive": asset.url,
        "archive_sha256": asset.archive_sha256,
        "binary": binary.name,
        "binary_sha256": actual,
        "nnue": provenance.NNUE_NAME,
    }
    (dest / "INSTALLED.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Installed {binary} (sha256 {actual})")
    return binary


def smoke_test(binary: Path) -> str:
    """Start the engine, check its identity and NNUE, play one legal move; return its name."""
    engine = UciEngine(EngineSettings(path=binary))
    engine.start()
    try:
        result = engine.search(chess.Board(), chess.engine.Limit(time=0.2), object())
        info = result.info
        print(f"  engine: {engine.name}")
        print(f"  NNUE loaded: {engine.network or '?'} (pinned {provenance.NNUE_NAME})")
        print(
            f"  startpos 0.2 s: bestmove {result.move} depth {info.get('depth')} "
            f"nodes {info.get('nodes')} nps {info.get('nps')}"
        )
        if engine.network != provenance.NNUE_NAME:
            raise EngineError(f"engine loaded {engine.network!r}, not {provenance.NNUE_NAME}")
        return engine.name
    finally:
        engine.close()


def main(argv: list[str] | None = None) -> int:
    """Command line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(description="Install Stockfish 19 for Benchmark 9.")
    parser.add_argument("--check", action="store_true", help="only check the installed engine")
    parser.add_argument("--force", action="store_true", help="download even if installed")
    parser.add_argument("--dest", type=Path, default=provenance.ENGINE_DIR)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # project paths may not fit the console code page
    system, machine = provenance.current_platform()
    print(f"Platform: {system}/{machine}")
    try:
        asset = provenance.asset_for(system, machine)
        binary = args.dest / asset.binary_name
        if args.check:
            if not binary.is_file():
                print(f"FAIL: {binary} is missing; run without --check to install")
                return 1
        else:
            binary = install(asset, args.dest, force=args.force)
        print("Smoke test:")
        name = smoke_test(binary)
    except (ValueError, OSError, EngineError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"PASS: {name} ready for Benchmark 9")
    return 0


if __name__ == "__main__":
    sys.exit(main())
