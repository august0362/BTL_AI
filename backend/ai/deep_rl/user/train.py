"""Huấn luyện DQN bằng self-play: một mạng chơi cả hai bên (bàn cờ luôn lật về bên sắp đi).

Chạy: ``python -m ai.deep_rl.user.train --out <thư_mục>`` (xem ``--help`` cho mọi siêu tham số).

- ``--warmup-games`` ván đầu đi ngẫu nhiên hoàn toàn (ε = 1) chỉ để đổ dữ liệu vào replay
  buffer; mạng chưa học. Sau đó chọn nước bằng softmax(Q/τ), τ giảm tuyến tính từ
  ``--temp-start`` về ``--temp-end`` ở ván cuối.
- Mỗi ``--train-every`` nửa nước mới thì làm 1 bước gradient (batch ``--batch-size``).
- Phần thưởng của nước vừa đi: +1 nếu chiếu hết, 0 nếu hòa, 0 trong ván. Ván chạm
  ``--max-plies`` bị cắt nhưng không coi là kết thúc (vẫn bootstrap từ s').
- Mỗi ``--eval-every`` ván: đấu thử (argmax) với đối thủ ngẫu nhiên và đối thủ tham ăn, ghi
  ``metrics.csv``, lưu ``checkpoint.pt`` (để chạy tiếp) và ``best.pt`` (trọng số cho bot).
- Thời gian còn lại: số giây mỗi ván được làm mượt ``E = a·x + (1 − a)·E`` (a =
  ``--eta-smoothing``, chỉ tính các đoạn sau khởi động), ``eta = E × số ván còn lại``.
"""

from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass, fields
from pathlib import Path

import chess
import numpy as np
import torch

from ai.deep_rl.evaluate import evaluate
from ai.deep_rl.metrics import MetricsLogger
from ai.deep_rl.opponents import GreedyCaptureOpponent, RandomOpponent
from ai.deep_rl.user.agent import Agent
from ai.deep_rl.user.features import ACTIONS, PLANES, action_mask, encode, legal_actions
from ai.deep_rl.user.model import Model
from ai.deep_rl.user.policy import DQNPolicy, save_weights
from ai.deep_rl.user.replay import ReplayBuffer

_EMPTY_STATE = np.zeros((PLANES, 8, 8), dtype=np.uint8)
_EMPTY_MASK = np.zeros(ACTIONS, dtype=np.bool_)


@dataclass
class TrainConfig:
    """Siêu tham số huấn luyện (mỗi trường là một tham số dòng lệnh cùng tên)."""

    out: str = "runs/deep_rl"
    games: int = 15_000
    warmup_games: int = 1_000
    max_plies: int = 150
    gamma: float = 0.99
    lr: float = 1e-4
    batch_size: int = 256
    buffer_size: int = 500_000
    learning_starts: int = 10_000
    train_every: int = 4
    tau: float = 0.005
    huber_delta: float = 1.0
    temp_start: float = 1.0
    temp_end: float = 0.1
    channels: int = 64
    blocks: int = 6
    parallel: int = 64
    eval_every: int = 500
    eval_games: int = 20
    seed: int = 0
    device: str = "auto"
    eta_smoothing: float = 0.3
    resume: str = ""


@dataclass
class _Game:
    """Một ván self-play đang chạy, kèm thế cờ đã mã hóa và nước hợp lệ hiện tại."""

    board: chess.Board
    random_moves: bool
    state: np.ndarray
    moves: list[chess.Move]
    actions: np.ndarray


def _new_game(random_moves: bool) -> _Game:
    board = chess.Board()
    moves, actions = legal_actions(board)
    return _Game(board, random_moves, encode(board), moves, actions)


def temperature(games_done: int, config: TrainConfig) -> float:
    """τ giảm tuyến tính từ ``temp_start`` (hết khởi động) về ``temp_end`` (ván cuối)."""
    span = config.games - config.warmup_games
    if span <= 0:
        return config.temp_end
    fraction = min(1.0, max(0.0, (games_done - config.warmup_games) / span))
    return config.temp_start + (config.temp_end - config.temp_start) * fraction


def play_move(game: _Game, index: int, max_plies: int) -> tuple[tuple, bool, str]:
    """Đi nước ``game.moves[index]``; trả về (chuyển tiếp, ván đã dừng chưa, kết quả)."""
    board = game.board
    state, action = game.state, int(game.actions[index])
    board.push(game.moves[index])
    outcome = board.outcome()
    if outcome is not None:
        done, reward, result = True, (1.0 if outcome.winner is not None else 0.0), outcome.result()
    elif board.is_repetition(3) or board.halfmove_clock >= 100:
        done, reward, result = True, 0.0, "1/2-1/2"
    else:
        done, reward, result = False, 0.0, "*"
    if done:
        next_state, next_mask = _EMPTY_STATE, _EMPTY_MASK
    else:
        game.state = encode(board)
        game.moves, game.actions = legal_actions(board)
        next_state, next_mask = game.state, action_mask(game.actions)
    finished = done or board.ply() >= max_plies
    return (state, action, reward, next_state, done, next_mask), finished, result


def smooth(old: float | None, value: float, alpha: float) -> float:
    """Làm mượt mũ ``E = α·x + (1 − α)·E``; chưa có ``E`` thì lấy luôn ``x``."""
    return value if old is None else alpha * value + (1.0 - alpha) * old


def format_duration(seconds: float) -> str:
    """``h:mm:ss``; ``?`` khi chưa ước tính được."""
    if not math.isfinite(seconds):
        return "?"
    total = round(seconds)
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(name)


def _save_checkpoint(agent: Agent, games_done: int, path: Path) -> None:
    torch.save(
        {
            "config": agent.online.config(),
            "online": agent.online.state_dict(),
            "target": agent.target.state_dict(),
            "optimizer": agent.optimizer.state_dict(),
            "games_done": games_done,
        },
        path,
    )


def _load_checkpoint(agent: Agent, path: str) -> int:
    data = torch.load(path, map_location=agent.device, weights_only=True)
    agent.online.load_state_dict(data["online"])
    agent.target.load_state_dict(data["target"])
    agent.optimizer.load_state_dict(data["optimizer"])
    return int(data["games_done"])


def _score(result: object) -> float:
    return (result.wins + 0.5 * result.draws) / (result.wins + result.draws + result.losses)


def train(config: TrainConfig) -> Path:
    """Chạy self-play + học; trả về thư mục kết quả."""
    out = Path(config.out)
    out.mkdir(parents=True, exist_ok=True)
    device = _device(config.device)
    rng = np.random.default_rng(config.seed)
    torch.manual_seed(config.seed)
    agent = Agent(
        Model(config.channels, config.blocks),
        gamma=config.gamma,
        lr=config.lr,
        tau=config.tau,
        huber_delta=config.huber_delta,
        device=device,
    )
    games_done = _load_checkpoint(agent, config.resume) if config.resume else 0
    buffer = ReplayBuffer(config.buffer_size)
    logger = MetricsLogger(out / "metrics.csv")
    print(f"device={device} games={config.games} start_at={games_done}", flush=True)

    slots: list[_Game | None] = [None] * config.parallel
    games_started = games_done
    pending = 0
    losses: list[float] = []
    q_means: list[float] = []
    results = {"1-0": 0, "0-1": 0, "1/2-1/2": 0, "*": 0}
    plies_total = 0
    best_score = -math.inf
    next_eval = (games_done // config.eval_every + 1) * config.eval_every
    started_at = time.time()
    seconds_per_game: float | None = None
    mark_time, mark_games = started_at, games_done

    while games_done < config.games:
        for slot, game in enumerate(slots):
            if game is None and games_started < config.games:
                slots[slot] = _new_game(games_started < config.warmup_games)
                games_started += 1
        active = [slot for slot, game in enumerate(slots) if game is not None]
        chosen = {
            slot: int(rng.integers(len(slots[slot].moves)))
            for slot in active
            if slots[slot].random_moves
        }
        learned = [slot for slot in active if slot not in chosen]
        if learned:
            states = np.stack([slots[slot].state for slot in learned])
            masks = np.stack([action_mask(slots[slot].actions) for slot in learned])
            picked = agent.act(states, masks, temperature(games_done, config))
            for slot, action in zip(learned, picked, strict=True):
                chosen[slot] = int(np.flatnonzero(slots[slot].actions == action)[0])

        for slot in active:
            game = slots[slot]
            transition, finished, result = play_move(game, chosen[slot], config.max_plies)
            buffer.add(*transition)
            if finished:
                games_done += 1
                results[result] += 1
                plies_total += game.board.ply()
                slots[slot] = None

        ready = games_done >= config.warmup_games and len(buffer) >= config.learning_starts
        pending = pending + len(active) if ready else 0
        while pending >= config.train_every:
            pending -= config.train_every
            stats = agent.update(buffer.sample(config.batch_size, rng))
            losses.append(stats["loss"])
            q_means.append(stats["q_mean"])

        if games_done >= next_eval or games_done >= config.games:
            while next_eval <= games_done:
                next_eval += config.eval_every
            now = time.time()
            if mark_games >= config.warmup_games and games_done > mark_games:
                interval = (now - mark_time) / (games_done - mark_games)
                seconds_per_game = smooth(seconds_per_game, interval, config.eta_smoothing)
            mark_time, mark_games = now, games_done
            remaining = config.games - games_done
            eta = math.nan if seconds_per_game is None else seconds_per_game * remaining
            policy = DQNPolicy(agent.online, device)
            games, plies = config.eval_games, config.max_plies
            vs_random = evaluate(policy, RandomOpponent(), games, games_done, plies)
            vs_greedy = evaluate(policy, GreedyCaptureOpponent(), games, 1, plies)
            score = (_score(vs_random) + _score(vs_greedy)) / 2
            finished_games = sum(results.values())
            row = {
                "loss": float(np.mean(losses)) if losses else math.nan,
                "q_mean": float(np.mean(q_means)) if q_means else math.nan,
                "win_rate": vs_random.wins / config.eval_games,
                "win_rate_greedy": vs_greedy.wins / config.eval_games,
                "score": score,
                "epsilon": 1.0 if games_done <= config.warmup_games else 0.0,
                "temperature": temperature(games_done, config),
                "buffer": len(buffer),
                "avg_plies": plies_total / max(1, finished_games),
                "white_wins": results["1-0"],
                "black_wins": results["0-1"],
                "draws": results["1/2-1/2"],
                "truncated": results["*"],
                "minutes": (now - started_at) / 60,
                "eta_minutes": eta / 60,
            }
            logger.log(step=games_done, **row)
            print(
                f"[{games_done}/{config.games}] {row['minutes']:.1f} min"
                f" eta={format_duration(eta)} loss={row['loss']:.4f} q={row['q_mean']:.3f}"
                f" tau={row['temperature']:.2f} buffer={len(buffer)}"
                f" | vs random {vs_random.wins}/{vs_random.draws}/{vs_random.losses}"
                f" vs greedy {vs_greedy.wins}/{vs_greedy.draws}/{vs_greedy.losses}"
                f" (W/D/L) score={score:.3f}",
                flush=True,
            )
            losses.clear()
            q_means.clear()
            results = dict.fromkeys(results, 0)
            plies_total = 0
            _save_checkpoint(agent, games_done, out / "checkpoint.pt")
            if games_done > config.warmup_games and score > best_score:
                best_score = score
                save_weights(agent.online, out / "best.pt")

    save_weights(agent.online, out / "final.pt")
    if not (out / "best.pt").exists():
        save_weights(agent.online, out / "best.pt")
    return out


def parse_args(argv: list[str] | None = None) -> TrainConfig:
    """Đọc tham số dòng lệnh thành ``TrainConfig``."""
    parser = argparse.ArgumentParser(description="DQN self-play cho bot deep_rl")
    for item in fields(TrainConfig):
        flag = "--" + item.name.replace("_", "-")
        parser.add_argument(flag, type=type(item.default), default=item.default)
    return TrainConfig(**vars(parser.parse_args(argv)))


def main(argv: list[str] | None = None) -> int:
    """Điểm vào dòng lệnh."""
    train(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
