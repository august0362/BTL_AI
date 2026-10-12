import csv

import chess
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from ai.deep_rl.user.policy import load_policy
from ai.deep_rl.user.pretrain import (
    PretrainConfig,
    _run_epoch,
    masked_cross_entropy,
    pretrain,
    unpack_masks,
)


class _TinyModel(torch.nn.Module):
    """A trainable action-value vector for fast objective tests."""

    def __init__(self) -> None:
        super().__init__()
        self.values = torch.nn.Parameter(torch.zeros(4672))

    def logits(self, states: torch.Tensor) -> torch.Tensor:
        return self.values.expand(len(states), -1)

    def forward(self, states: torch.Tensor) -> torch.Tensor:
        return torch.tanh(self.logits(states))

    def config(self) -> dict[str, int]:
        return {"channels": 8, "blocks": 1}


def _batch_loaders() -> tuple[DataLoader, DataLoader]:
    legal = np.zeros((2, 4672), dtype=np.bool_)
    legal[:, :2] = True
    policy = TensorDataset(
        torch.zeros((2, 1)),
        torch.from_numpy(np.packbits(legal, axis=1)),
        torch.zeros(2, dtype=torch.long),
    )
    value = TensorDataset(
        torch.zeros((2, 1)),
        torch.zeros(2, dtype=torch.long),
        torch.full((2,), 0.8),
    )
    return DataLoader(policy, batch_size=2), DataLoader(value, batch_size=2)


def test_margin_pretrain_smoke_logs_and_loads_weights(tmp_path) -> None:
    pgn = tmp_path / "games.pgn"
    pgn.write_text(
        '[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n\n'
        '[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0\n\n',
        encoding="utf-8",
    )
    out = tmp_path / "run"
    weights = pretrain(
        PretrainConfig(
            out=str(out),
            epochs=1,
            batch_size=4,
            channels=8,
            blocks=1,
            device="cpu",
            ce_weight=0,
            margin_weight=1,
            value_weight=1,
        ),
        [pgn],
    )
    with (out / "pretrain_metrics.csv").open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert "margin_loss" in row and "val_margin_loss" in row
    assert load_policy(weights).select_move(chess.Board()) in chess.Board().legal_moves


def test_margin_and_value_losses_decrease_without_cross_entropy() -> None:
    policy_loader, value_loader = _batch_loaders()
    model = _TinyModel()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.2)
    args = (policy_loader, torch.device("cpu"), optimizer, value_loader)
    before = _run_epoch(model, *args, ce_weight=0, margin_weight=1, value_weight=1)
    for _ in range(5):
        after = _run_epoch(model, *args, ce_weight=0, margin_weight=1, value_weight=1)
    assert after["margin_loss"] < before["margin_loss"]
    assert after["value_loss"] < before["value_loss"]


def test_default_objective_matches_cross_entropy() -> None:
    policy_loader, _ = _batch_loaders()
    model = _TinyModel()
    states, masks, actions = next(iter(policy_loader))
    expected, _ = masked_cross_entropy(model, states, masks, actions)
    metrics = _run_epoch(model, policy_loader, torch.device("cpu"), None)
    assert PretrainConfig().ce_weight == 1
    assert PretrainConfig().margin_weight == 0
    assert metrics["loss"] == metrics["ce_loss"]
    assert metrics["loss"] == expected.item()
    assert torch.equal(unpack_masks(masks)[:, :2], torch.ones((2, 2), dtype=torch.bool))
