"""Pack three trusted Kaggle checkpoints into a weights-only V20 bot file."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Mapping
from pathlib import Path

import torch

from .model import DEFAULT_CONFIG, PolicyValueNet
from .policy import PHASES, V20_FORMAT


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def extract_state(
    path: str | Path, model_config: Mapping[str, int] = DEFAULT_CONFIG
) -> dict[str, torch.Tensor]:
    """Extract and strictly check the P/V core, discarding training-only data."""
    data = torch.load(path, map_location="cpu", weights_only=False)
    state = data.get("model", data.get("state_dict")) if isinstance(data, dict) else None
    if not isinstance(state, dict):
        raise ValueError(f"checkpoint {Path(path).name} requires model/state_dict")
    if any(key.startswith("core.") for key in state):
        state = {key[5:]: value for key, value in state.items() if key.startswith("core.")}
    try:
        model = PolicyValueNet(**model_config)
        expected = model.state_dict()
        filtered = {key: value for key, value in state.items() if key in expected}
        model.load_state_dict(filtered, strict=True)
    except (TypeError, RuntimeError, ValueError) as exc:
        raise ValueError(f"invalid V20 core in {Path(path).name}: {exc}") from exc
    return {key: value.detach().cpu() for key, value in model.state_dict().items()}


def pack(
    start: str | Path,
    mid: str | Path,
    end: str | Path,
    out: str | Path,
    model_config: Mapping[str, int] = DEFAULT_CONFIG,
) -> str:
    """Write all phase experts and source hashes; return the output SHA-256."""
    paths = dict(zip(PHASES, map(Path, (start, mid, end)), strict=True))
    models = {phase: extract_state(path, model_config) for phase, path in paths.items()}
    sources = {phase: {"file": path.name, "sha256": _sha256(path)} for phase, path in paths.items()}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "format": V20_FORMAT,
            "model_config": dict(model_config),
            "models": models,
            "meta": {"sources": sources},
        },
        out,
    )
    return _sha256(out)


def main() -> None:
    """Pack START, MID, and END checkpoints and print the packed file hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=Path)
    parser.add_argument("--mid", required=True, type=Path)
    parser.add_argument("--end", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(pack(args.start, args.mid, args.end, args.out))


if __name__ == "__main__":
    main()
