"""Resolve and verify model weights downloaded from a release URL."""

from __future__ import annotations

import hashlib
import os
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_WEIGHTS_DIR = Path(__file__).with_name("weights")


def sha256_file(path: str | Path) -> str:
    """Return the lowercase SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_weights(
    url: str,
    sha256: str,
    cache_dir: str | Path | None = None,
) -> Path | None:
    """Download a release asset once, verify it, and return its cached path."""
    if not url:
        return None
    if not sha256 or len(sha256) != 64:
        raise ValueError("a 64-character sha256 is required when weights_url is set")
    parsed = urllib.parse.urlparse(url)
    name = Path(urllib.parse.unquote(parsed.path)).name or "weights.pt"
    directory = Path(cache_dir) if cache_dir is not None else DEFAULT_WEIGHTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / name
    if destination.is_file() and sha256_file(destination) == sha256.lower():
        return destination
    temporary = destination.with_name(f"{destination.name}.download")
    try:
        urllib.request.urlretrieve(url, temporary)
        actual = sha256_file(temporary)
        if actual != sha256.lower():
            raise ValueError(f"weights sha256 mismatch: expected {sha256}, got {actual}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
