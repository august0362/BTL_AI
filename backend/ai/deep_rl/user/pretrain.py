"""Pretrain có giám sát từ ván của kỳ thủ: học thứ tự nước đi và giá trị.

Chạy: ``python -m ai.deep_rl.user.pretrain --pgn <file/thư_mục> ... --out <thư_mục>``.

1. Đọc mọi ván trong các file ``.pgn`` (hoặc ``.zip`` chứa ``.pgn``); bỏ ván hòa / chưa có
   kết quả. Với mỗi nước của **bên thắng** (Trắng hoặc Đen): ``X = encode(board)``
   (18 × 8 × 8, lật về phía bên đi), ``y = move_to_action(nước)`` trong ``[0, 4672)``, cùng
   mặt nạ nước hợp lệ. Lưu tất cả vào ``positions.npz`` (nén bit) để không phải đọc PGN lại.
2. Tách ``--val-fraction`` số **ván** làm tập kiểm tra (thế cờ cùng ván không lọt sang
   tập học), xáo trộn toàn bộ thế cờ, chia batch.
3. Tối ưu Cross-Entropy và/hoặc large-margin loss trên nước của bên thắng, cùng Huber loss
   trên giá trị Q của mọi nước. Mỗi epoch đo loss có trọng số và Top-1 accuracy; lưu
   ``sl_pretrained.pt`` (cùng định dạng ``best.pt``).
"""

from __future__ import annotations

import argparse
import io
import math
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, fields
from pathlib import Path

import chess
import chess.pgn
import numpy as np
import torch
from torch.nn import functional
from torch.utils.data import DataLoader, TensorDataset

from ai.deep_rl.metrics import MetricsLogger
from ai.deep_rl.user.agent import margin_loss, masked_q
from ai.deep_rl.user.features import ACTIONS, PLANES, action_mask, encode, legal_actions
from ai.deep_rl.user.model import Model
from ai.deep_rl.user.policy import save_weights
from ai.deep_rl.user.potential import potential

_RESULT_WINNER = {"1-0": chess.WHITE, "0-1": chess.BLACK}
_BIT_SHIFTS = torch.arange(7, -1, -1, dtype=torch.uint8)  # thứ tự bit của np.packbits


@dataclass
class PretrainConfig:
    """Siêu tham số pretrain (mỗi trường là một tham số dòng lệnh cùng tên)."""

    out: str = "runs/pretrain"
    epochs: int = 15
    lr: float = 1e-3
    batch_size: int = 256
    val_fraction: float = 0.1
    channels: int = 64
    blocks: int = 6
    seed: int = 0
    device: str = "auto"
    rebuild: bool = False
    ce_weight: float = 1.0
    margin_weight: float = 0.0
    margin: float = 0.05
    value_weight: float = 0.0
    potential_scale: float = 0.0
    gamma: float = 0.99


def _pgn_texts(path: Path) -> Iterator[tuple[str, str]]:
    """Trả về (tên, nội dung) của mọi PGN trong ``path`` (file .pgn, .zip hoặc thư mục)."""
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.suffix.lower() in (".pgn", ".zip"):
                yield from _pgn_texts(child)
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if name.lower().endswith(".pgn"):
                    yield name, archive.read(name).decode("utf-8", errors="replace")
    elif path.suffix.lower() == ".pgn":
        yield path.name, path.read_text(encoding="utf-8", errors="replace")


def winner_transitions(
    game: chess.pgn.Game,
    potential_scale: float = 0.0,
    gamma: float = 0.99,
) -> list[tuple[np.ndarray, int, np.ndarray, float, bool, np.ndarray, np.ndarray]]:
    """Trả về chuyển tiếp của bên thắng; ván hòa hoặc lỗi trả về danh sách rỗng."""
    winner = _RESULT_WINNER.get(game.headers.get("Result", "*"))
    if winner is None or game.errors:
        return []
    board = game.board()
    all_moves = list(game.mainline_moves())
    # Xác định lượt thắng bằng cách phát lại cờ vì màu đi thay đổi sau mỗi nước.
    board = game.board()
    winning_plies = []
    for index, move in enumerate(all_moves):
        if board.turn == winner:
            winning_plies.append(index)
        board.push(move)
    if not winning_plies:
        return []

    board = game.board()
    samples = []
    last_winning_ply = winning_plies[-1]
    for index, move in enumerate(all_moves):
        if board.turn == winner:
            legal_moves, actions = legal_actions(board)
            action = int(actions[legal_moves.index(move)])
            mask = action_mask(actions)
            old_potential = potential(board, potential_scale)
            if index == last_winning_ply:
                next_state = np.zeros((PLANES, 8, 8), dtype=np.uint8)
                next_mask = np.zeros(ACTIONS, dtype=np.bool_)
                reward, done = 1.0, True
            else:
                next_board = board.copy()
                next_board.push(move)
                next_state = encode(next_board)
                _, next_actions = legal_actions(next_board)
                next_mask = action_mask(next_actions)
                reward, done = 0.0, False
            next_potential = 0.0 if done else potential(next_board, potential_scale)
            reward = reward - gamma * next_potential - old_potential
            samples.append((encode(board), action, mask, reward, next_state, done, next_mask))
        board.push(move)
    return samples


def winner_positions(game: chess.pgn.Game) -> list[tuple[np.ndarray, int, np.ndarray]]:
    """Các thế cờ, nước và mặt nạ hợp lệ mà bên thắng đã đi."""
    return [(state, action, mask) for state, action, mask, *_ in winner_transitions(game)]


def build_dataset(
    pgn_paths: list[str | Path],
    out_file: str | Path,
    potential_scale: float = 0.0,
    gamma: float = 0.99,
) -> dict[str, np.ndarray]:
    """Đọc PGN, trích thế cờ của bên thắng và lưu ``out_file`` (.npz)."""
    states, actions, masks, next_states, next_masks, rewards, dones, game_ids = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    games = decisive = 0
    value_states, value_actions, value_targets, value_game_ids = [], [], [], []
    for path in pgn_paths:
        for name, text in _pgn_texts(Path(path)):
            handle = io.StringIO(text)
            file_games = 0
            while (game := chess.pgn.read_game(handle)) is not None:
                games += 1
                file_games += 1
                samples = winner_transitions(game, potential_scale, gamma)
                if not samples:
                    continue
                for state, action, mask, reward, next_state, done, next_mask in samples:
                    states.append(np.packbits(state.reshape(-1)))
                    actions.append(action)
                    masks.append(np.packbits(mask))
                    next_states.append(np.packbits(next_state.reshape(-1)))
                    next_masks.append(np.packbits(next_mask))
                    rewards.append(reward)
                    dones.append(float(done))
                    game_ids.append(decisive)
                board = game.board()
                moves = list(game.mainline_moves())
                winner = _RESULT_WINNER[game.headers["Result"]]
                for index, move in enumerate(moves):
                    legal_moves, legal_indices = legal_actions(board)
                    value_states.append(np.packbits(encode(board).reshape(-1)))
                    value_actions.append(int(legal_indices[legal_moves.index(move)]))
                    plies_left = len(moves) - index - 1
                    sign = 1.0 if board.turn == winner else -1.0
                    value_targets.append(
                        sign * gamma**plies_left - potential(board, potential_scale)
                    )
                    value_game_ids.append(decisive)
                    board.push(move)
                decisive += 1
            print(f"{name}: {file_games} games", flush=True)
    if not states:
        raise ValueError("không tìm thấy ván có người thắng trong các file PGN")
    data = {
        "states": np.stack(states),
        "actions": np.asarray(actions, dtype=np.int64),
        "masks": np.stack(masks),
        "next_states": np.stack(next_states),
        "next_masks": np.stack(next_masks),
        "rewards": np.asarray(rewards, dtype=np.float32),
        "dones": np.asarray(dones, dtype=np.float32),
        "game_ids": np.asarray(game_ids, dtype=np.int32),
        "value_states": np.stack(value_states),
        "value_actions": np.asarray(value_actions, dtype=np.int64),
        "value_targets": np.asarray(value_targets, dtype=np.float32),
        "value_game_ids": np.asarray(value_game_ids, dtype=np.int32),
        "potential_scale": np.asarray(potential_scale, dtype=np.float64),
        "gamma": np.asarray(gamma, dtype=np.float64),
    }
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_file, **data)
    print(f"{games} games, {decisive} decisive, {len(actions)} positions -> {out_file}")
    return data


def validation_games(game_count: int, seed: int = 0, val_fraction: float = 0.1) -> np.ndarray:
    """Chỉ số các ván làm tập kiểm tra (dùng chung cho pretrain và cột ``gm%`` khi tự chơi)."""
    rng = np.random.default_rng(seed)
    return rng.permutation(game_count)[: max(1, round(game_count * val_fraction))]


def _tensors(data: dict[str, np.ndarray], index: np.ndarray) -> TensorDataset:
    count = len(index)
    states = np.unpackbits(data["states"][index], axis=1).reshape(count, PLANES, 8, 8)
    return TensorDataset(
        torch.from_numpy(states),
        torch.from_numpy(data["masks"][index]),
        torch.from_numpy(data["actions"][index]),
    )


def _value_tensors(data: dict[str, np.ndarray], index: np.ndarray) -> TensorDataset:
    """Giải nén mẫu giá trị (thế cờ, nước đi, mục tiêu)."""
    count = len(index)
    states = np.unpackbits(data["value_states"][index], axis=1).reshape(count, PLANES, 8, 8)
    return TensorDataset(
        torch.from_numpy(states),
        torch.from_numpy(data["value_actions"][index]),
        torch.from_numpy(data["value_targets"][index]),
    )


def unpack_masks(packed: torch.Tensor) -> torch.Tensor:
    """Giải nén mặt nạ ``uint8 (B, 584)`` (theo ``np.packbits``) thành ``bool (B, 4672)``."""
    shifts = _BIT_SHIFTS.to(packed.device)
    return ((packed[..., None] >> shifts) & 1).bool().reshape(packed.shape[0], -1)


def masked_cross_entropy(
    model: Model, states: torch.Tensor, packed_masks: torch.Tensor, actions: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Trả về (loss Cross-Entropy, số dự đoán Top-1 đúng) trên logit đã mask."""
    logits = masked_q(model.logits(states), unpack_masks(packed_masks))
    loss = functional.cross_entropy(logits, actions)
    correct = (logits.argmax(dim=1) == actions).sum()
    return loss, correct


def _run_epoch(
    model: Model,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
    value_loader: DataLoader | None = None,
    ce_weight: float = 1.0,
    margin_weight: float = 0.0,
    margin: float = 0.05,
    value_weight: float = 0.0,
) -> dict[str, float]:
    model.train(optimizer is not None)
    policy_count = value_count = total_correct = 0
    ce_total = margin_total = value_total = 0.0
    value_batches = len(value_loader) if value_loader is not None else 0
    policy_batches = len(loader)
    value_iterator = iter(value_loader) if value_loader is not None else None
    with torch.set_grad_enabled(optimizer is not None):
        for batch_index, (states, masks, actions) in enumerate(loader):
            states, masks, actions = states.to(device), masks.to(device), actions.to(device)
            legal_masks = unpack_masks(masks)
            logits = model.logits(states)
            masked_logits = masked_q(logits, legal_masks)
            ce_loss = functional.cross_entropy(masked_logits, actions)
            margin_batch_loss = margin_loss(torch.tanh(logits), legal_masks, actions, margin)
            correct = (masked_logits.argmax(dim=1) == actions).sum()
            batch_value_loss = torch.zeros((), device=device)
            batch_value_count = 0

            # Split the value loader evenly across policy steps; every value batch is used once.
            first_value_batch = math.ceil(batch_index * value_batches / policy_batches)
            last_value_batch = math.ceil((batch_index + 1) * value_batches / policy_batches)
            for _ in range(last_value_batch - first_value_batch):
                if value_iterator is None:
                    break
                value_states, value_actions, targets = next(value_iterator)
                value_states = value_states.to(device)
                value_actions, targets = value_actions.to(device), targets.to(device)
                prediction = model(value_states).gather(1, value_actions[:, None]).squeeze(1)
                value_loss = functional.huber_loss(prediction, targets, reduction="sum")
                batch_value_loss = batch_value_loss + value_loss
                batch_value_count += len(value_actions)
                value_total += float(value_loss.detach().item())
                value_count += len(value_actions)
            batch_value_loss = batch_value_loss / max(1, batch_value_count)
            loss = ce_weight * ce_loss + margin_weight * margin_batch_loss
            loss = loss + value_weight * batch_value_loss
            if optimizer is not None:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
            ce_total += float(ce_loss.detach().item()) * len(actions)
            margin_total += float(margin_batch_loss.detach().item()) * len(actions)
            total_correct += float(correct.item())
            policy_count += len(actions)
    ce_mean = ce_total / max(1, policy_count)
    margin_mean = margin_total / max(1, policy_count)
    value_mean = value_total / max(1, value_count)
    return {
        "loss": ce_weight * ce_mean + margin_weight * margin_mean + value_weight * value_mean,
        "accuracy": total_correct / max(1, policy_count),
        "ce_loss": ce_mean,
        "margin_loss": margin_mean,
        "value_loss": value_mean,
    }


def pretrain(config: PretrainConfig, pgn_paths: list[str | Path]) -> Path:
    """Tạo/nạp ``positions.npz``, huấn luyện và lưu ``sl_pretrained.pt``; trả về đường dẫn đó."""
    out = Path(config.out)
    data_file = out / "positions.npz"
    if data_file.exists() and not config.rebuild:
        data = dict(np.load(data_file))
        if (
            "value_targets" not in data
            or float(data["potential_scale"]) != config.potential_scale
            or float(data["gamma"]) != config.gamma
        ):
            data = build_dataset(pgn_paths, data_file, config.potential_scale, config.gamma)
        print(f"loaded {data_file}: {len(data['actions'])} positions", flush=True)
    else:
        data = build_dataset(pgn_paths, data_file, config.potential_scale, config.gamma)

    torch.manual_seed(config.seed)
    game_count = int(data["game_ids"].max()) + 1
    val_games = validation_games(game_count, config.seed, config.val_fraction)
    is_val = np.isin(data["game_ids"], val_games)
    value_is_val = np.isin(data["value_game_ids"], val_games)
    train_index, val_index = np.flatnonzero(~is_val), np.flatnonzero(is_val)
    generator = torch.Generator().manual_seed(config.seed)
    train_loader = DataLoader(
        _tensors(data, train_index), config.batch_size, shuffle=True, generator=generator
    )
    val_loader = DataLoader(_tensors(data, val_index), config.batch_size)
    value_train_index = np.flatnonzero(~value_is_val)
    value_val_index = np.flatnonzero(value_is_val)
    value_train_loader = DataLoader(
        _value_tensors(data, value_train_index),
        config.batch_size,
        shuffle=True,
        generator=generator,
    )
    value_val_loader = DataLoader(_value_tensors(data, value_val_index), config.batch_size)
    print(f"train {len(train_index)} positions, validation {len(val_index)}", flush=True)

    device = torch.device(
        ("cuda" if torch.cuda.is_available() else "cpu")
        if config.device == "auto"
        else config.device
    )
    model = Model(config.channels, config.blocks).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)
    logger = MetricsLogger(out / "pretrain_metrics.csv")
    best_file = out / "sl_pretrained.pt"
    use_validation_loss = config.value_weight > 0 or config.ce_weight == 0
    best_accuracy = math.inf if use_validation_loss else -1.0
    for epoch in range(1, config.epochs + 1):
        metrics = _run_epoch(
            model,
            train_loader,
            device,
            optimizer,
            value_train_loader,
            config.ce_weight,
            config.margin_weight,
            config.margin,
            config.value_weight,
        )
        val_metrics = _run_epoch(
            model,
            val_loader,
            device,
            None,
            value_val_loader,
            config.ce_weight,
            config.margin_weight,
            config.margin,
            config.value_weight,
        )
        logger.log(
            step=epoch,
            **metrics,
            val_loss=val_metrics["loss"],
            val_accuracy=val_metrics["accuracy"],
            val_margin_loss=val_metrics["margin_loss"],
            val_value_loss=val_metrics["value_loss"],
        )
        marker = ""
        checkpoint_score = val_metrics["loss"] if use_validation_loss else val_metrics["accuracy"]
        improved = (
            checkpoint_score < best_accuracy
            if use_validation_loss
            else checkpoint_score > best_accuracy
        )
        if improved:
            best_accuracy = checkpoint_score
            save_weights(model, best_file, {"potential_scale": config.potential_scale})
            marker = "  -> saved sl_pretrained.pt"
        print(
            f"epoch {epoch}/{config.epochs} loss={metrics['loss']:.4f}"
            f" acc={metrics['accuracy']:.3f} margin_loss={metrics['margin_loss']:.4f}"
            f" value_loss={metrics['value_loss']:.4f} | val_loss={val_metrics['loss']:.4f}"
            f" val_acc={val_metrics['accuracy']:.3f}"
            f" val_margin_loss={val_metrics['margin_loss']:.4f}"
            f" val_value_loss={val_metrics['value_loss']:.4f}{marker}",
            flush=True,
        )
    return best_file


def main(argv: list[str] | None = None) -> int:
    """Điểm vào dòng lệnh."""
    parser = argparse.ArgumentParser(description="Pretrain deep_rl từ PGN (Cross-Entropy)")
    parser.add_argument("--pgn", nargs="+", required=True, help="file .pgn/.zip hoặc thư mục")
    for item in fields(PretrainConfig):
        flag = "--" + item.name.replace("_", "-")
        if isinstance(item.default, bool):
            parser.add_argument(flag, action="store_true")
        else:
            parser.add_argument(flag, type=type(item.default), default=item.default)
    args = vars(parser.parse_args(argv))
    pgn_paths = args.pop("pgn")
    pretrain(PretrainConfig(**args), pgn_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
