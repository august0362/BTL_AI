"""Huấn luyện DQN bằng self-play: một mạng chơi cả hai bên (bàn cờ luôn lật về bên sắp đi).

Chạy: ``python -m ai.deep_rl.user.train --out <thư_mục>`` (xem ``--help`` cho mọi siêu tham số).

- ``--warmup-games`` ván đầu đi ngẫu nhiên hoàn toàn (ε = 1) chỉ để đổ dữ liệu vào replay
  buffer; mạng chưa học. Sau đó chọn nước bằng softmax(Q/τ) với nhiệt độ τ cố định
  ``--temperature`` (mặc định 0.3): ``π(a|s) = e^{Q(s,a)/τ} / Σ_b e^{Q(s,b)/τ}``.
- Mỗi ``--train-every`` nửa nước mới thì làm 1 bước gradient (batch ``--batch-size``).
- Phần thưởng của nước vừa đi: +1 nếu chiếu hết, 0 nếu hòa, 0 trong ván. Ván chạm
  ``--max-plies`` bị cắt nhưng không coi là kết thúc (vẫn bootstrap từ s').
- Mỗi ``--eval-every`` ván: đấu thử (argmax) với đối thủ ngẫu nhiên và đối thủ tham ăn, ghi
  ``metrics.csv``, lưu ``checkpoint.pt`` (để chạy tiếp) và ``best.pt`` (trọng số cho bot).
- ``--init-weights <file .pt>`` (vd ``sl_pretrained.pt`` từ ``pretrain``) nạp trọng số vào cả
  mạng chính lẫn mạng đóng băng; kích thước mạng lấy theo file. Khi đó thường đặt
  ``--warmup-games 0`` và lr nhỏ để chỉ tinh chỉnh.
- Thời gian còn lại: số giây mỗi ván được làm mượt ``E = a·x + (1 − a)·E`` (a =
  ``--eta-smoothing``, chỉ tính các đoạn sau khởi động), ``eta = E × số ván còn lại``.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections import deque
from dataclasses import dataclass, fields
from pathlib import Path

import chess
import numpy as np
import torch

from ai.deep_rl.evaluate import evaluate
from ai.deep_rl.metrics import MetricsLogger
from ai.deep_rl.opponents import (
    GreedyCaptureOpponent,
    MaterialAlphaBetaOpponent,
    RandomOpponent,
)
from ai.deep_rl.user.agent import Agent, masked_q
from ai.deep_rl.user.curriculum import (
    draw_start_kind,
    load_decisive_games,
    load_mate_puzzles,
    load_tactic_puzzles,
    parse_phase_mix,
    phase_by_name,
    phase_for,
    start_board,
)
from ai.deep_rl.user.features import ACTIONS, PLANES, action_mask, encode, legal_actions
from ai.deep_rl.user.model import Model
from ai.deep_rl.user.policy import DQNPolicy, load_file, save_weights
from ai.deep_rl.user.potential import potential
from ai.deep_rl.user.pretrain import build_dataset, validation_games
from ai.deep_rl.user.replay import ReplayBuffer
from ai.deep_rl.user.schedule import (
    BATCH_KINDS,
    GAME_KINDS,
    LEVEL_KINDS,
    draw_kind,
    mate_level_cap,
    parse_schedule,
    schedule_at,
)
from ai.deep_rl.user.tactics import tactic_positions, tactics_rate

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
    temperature: float = 0.3
    temp_start: float = 0.3
    temp_ramp_fraction: float = 0.3
    channels: int = 64
    blocks: int = 6
    parallel: int = 64
    eval_every: int = 500
    eval_games: int = 20
    seed: int = 0
    device: str = "auto"
    eta_smoothing: float = 0.3
    resume: str = ""
    init_weights: str = ""
    expert_pgn: str = ""
    expert_fraction: float = 0.25
    margin: float = 0.05
    margin_weight: float = 1.0
    curriculum_pgn: str = ""
    endgame_fraction: float = 0.3
    endgame_back_min: int = 2
    endgame_back_max: int = 20
    middlegame_fraction: float = 0.3
    middlegame_back_min: int = 20
    middlegame_back_max: int = 80
    free_fraction: float = 0.1
    long_max_plies: int = 400
    endgame_max_plies: int = 60
    middlegame_max_plies: int = 120
    decisive_buffer_size: int = 100_000
    decisive_fraction: float = 0.0
    n_step: int = 1
    max_hours: float = 0.0
    draw_penalty: float = 0.0
    potential_scale: float = 0.0
    double_dqn: int = 0
    lr_warmup_games: int = 0
    lr_warmup_factor: float = 0.1
    mate_puzzles: str = ""
    mate_max_level: int = 4
    mate_pass_rate: float = 0.8
    mate_window: int = 500
    mate_min_games: int = 500
    mate_max_games: int = 4000
    mate_temperature: float = 0.3
    mate_expert: int = 0
    mate_review: str = ""
    mate_level_max_games: str = ""
    phase_mix: str = ""
    puzzle_review: float = 0.0
    snapshot_every: int = 0
    bench_eval_games: int = 0
    bench_depth: int = 3
    puzzle_expert_fraction: float = 0.0
    regular_puzzle_expert_fraction: float = 0.0
    tactics_positions: int = 300
    expert_fraction_end: float = -1.0
    gm_positions: int = 500
    game_schedule: str = ""
    batch_schedule: str = ""
    tactic_puzzles: str = ""
    mate_level_schedule: str = ""


@dataclass
class _Game:
    """Một ván self-play đang chạy, kèm thế cờ đã mã hóa và nước hợp lệ hiện tại."""

    board: chess.Board
    random_moves: bool
    state: np.ndarray
    moves: list[chess.Move]
    actions: np.ndarray
    starting_ply: int
    max_plies: int
    game_index: int = 0
    drill_level: int = 0
    attacker: chess.Color = chess.WHITE
    pending: list[tuple] | None = None
    transitions: list[tuple] | None = None
    regular: bool = False  # puzzle ôn trong phần ván thường: tính là ván thường


def _new_game(
    random_moves: bool,
    board: chess.Board | None = None,
    max_plies: int = 150,
    game_index: int = 0,
    drill_level: int = 0,
) -> _Game:
    board = chess.Board() if board is None else board
    moves, actions = legal_actions(board)
    return _Game(
        board,
        random_moves,
        encode(board),
        moves,
        actions,
        board.ply(),
        max_plies,
        game_index,
        drill_level,
        board.turn,
        [],
        [],
    )


def _new_mate_game(
    puzzles: list[tuple[str, list[chess.Move]]],
    level: int,
    rng: np.random.Generator,
    game_index: int = 0,
) -> _Game:
    """Bắt đầu ván luyện từ một puzzle ngẫu nhiên."""
    fen, _ = puzzles[int(rng.integers(len(puzzles)))]
    return _new_game(
        False,
        chess.Board(fen),
        2 * level - 1,
        game_index=game_index,
        drill_level=level,
    )


def _mate_success(game: _Game) -> bool:
    """Kiểm tra bên tấn công có chiếu hết trong ván luyện không."""
    return game.drill_level > 0 and game.board.is_checkmate() and game.board.turn != game.attacker


def _parse_mate_review(value: str) -> dict[int, dict[int, float]]:
    """Parse per-level review probabilities from the command-line format."""
    reviews: dict[int, dict[int, float]] = {}
    if not value:
        return reviews
    try:
        for entry in value.split(";"):
            level_text, probabilities_text = entry.split(":", maxsplit=1)
            level = int(level_text)
            if not 1 <= level <= 4:
                raise ValueError("levels must be between 1 and 4")
            if level in reviews:
                raise ValueError(f"duplicate current level {level}")
            probabilities: dict[int, float] = {}
            for item in probabilities_text.split(","):
                earlier_text, probability_text = item.split("=", maxsplit=1)
                earlier = int(earlier_text)
                probability = float(probability_text)
                if not 1 <= earlier <= 4 or earlier >= level:
                    raise ValueError(
                        f"review level {earlier} must be in 1..4 and less than {level}"
                    )
                if not math.isfinite(probability) or probability < 0:
                    raise ValueError("review probabilities must be finite and nonnegative")
                probabilities[earlier] = probability
            if sum(probabilities.values()) > 1:
                raise ValueError(f"review probabilities for level {level} sum to more than 1")
            reviews[level] = probabilities
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid mate_review {value!r}: {exc}") from exc
    return reviews


def _parse_level_max_games(value: str) -> dict[int, int]:
    """Đọc số ván tối đa riêng cho từng cấp, vd ``"3=10000,4=10000"``."""
    limits: dict[int, int] = {}
    if not value:
        return limits
    try:
        for item in value.split(","):
            level_text, games_text = item.split("=", maxsplit=1)
            level, games = int(level_text), int(games_text)
            if not 1 <= level <= 4 or games <= 0:
                raise ValueError("levels must be in 1..4 and limits positive")
            limits[level] = games
    except ValueError as exc:
        raise ValueError(f"invalid mate_level_max_games {value!r}: {exc}") from exc
    return limits


def _snapshot_name(regular_games: int) -> str:
    """Tên file ảnh chụp: ``snap_5k.pt`` hoặc ``snap_2500.pt``."""
    if regular_games % 1000 == 0:
        return f"snap_{regular_games // 1000}k.pt"
    return f"snap_{regular_games}.pt"


def _draw_mate_level(
    current_level: int, reviews: dict[int, dict[int, float]], rng: np.random.Generator
) -> int:
    """Draw a review level or the current level using the training RNG."""
    draw = float(rng.random())
    cumulative = 0.0
    for level, probability in reviews.get(current_level, {}).items():
        cumulative += probability
        if draw < cumulative:
            return level
    return current_level


def temperature_for(game_index: int, config: TrainConfig) -> float:
    """Tính nhiệt độ theo chỉ số ván trong đoạn tăng tuyến tính."""
    ramp_games = config.games * config.temp_ramp_fraction
    progress = 1.0 if ramp_games <= 0 else min(max(game_index / ramp_games, 0.0), 1.0)
    return config.temp_start + progress * (config.temperature - config.temp_start)


def _append_training_sample(
    game: _Game, raw: list[tuple], buffer: ReplayBuffer, gamma: float, done: bool
) -> None:
    """Lưu mẫu n bước từ đầu hàng đợi."""
    reward = sum(((-gamma) ** index) * item[2] for index, item in enumerate(raw))
    last = raw[-1]
    transition = (raw[0][0], raw[0][1], reward, last[3], done, last[5], len(raw))
    buffer.add(*transition)
    if game.transitions is not None:
        game.transitions.append(transition)


def _store_ready(
    game: _Game, buffer: ReplayBuffer, n_step: int, gamma: float, finished: bool, terminal: bool
) -> None:
    """Lưu cửa sổ đủ n bước hoặc xả hàng đợi ở cuối ván."""
    pending = game.pending
    if pending is None:
        return
    while pending and (len(pending) >= n_step or finished):
        count = min(n_step, len(pending))
        _append_training_sample(game, pending[:count], buffer, gamma, terminal)
        pending.pop(0)


def _copy_decisive(game: _Game, buffer: ReplayBuffer) -> None:
    """Chép toàn bộ mẫu của ván chiếu hết sang replay quyết định."""
    if game.board.is_checkmate():
        for transition in game.transitions or []:
            buffer.add(*transition)


def _sample_batches(
    buffer: ReplayBuffer,
    decisive_buffer: ReplayBuffer,
    expert_buffer: ReplayBuffer | None,
    batch_size: int,
    expert_fraction: float,
    decisive_fraction: float,
    rng: np.random.Generator,
    puzzle_buffer: ReplayBuffer | None = None,
    puzzle_fraction: float = 0.0,
    tactic_buffer: ReplayBuffer | None = None,
    tactic_fraction: float = 0.0,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray] | None]:
    """Lấy batch theo tỉ lệ chuyên gia (PGN), lời giải puzzle, chiếu hết và replay chính.

    Mẫu lời giải puzzle được ghép vào phần chuyên gia (cùng học bằng TD)."""
    expert_count = round(batch_size * expert_fraction) if expert_buffer is not None else 0
    puzzle_count = round(batch_size * puzzle_fraction) if puzzle_buffer is not None else 0
    tactic_count = round(batch_size * tactic_fraction) if tactic_buffer is not None else 0
    decisive_count = min(round(batch_size * decisive_fraction), len(decisive_buffer))
    main_count = batch_size - expert_count - puzzle_count - tactic_count - decisive_count
    batch = buffer.sample(main_count, rng)
    if decisive_count:
        batch = _concat_batches(batch, decisive_buffer.sample(decisive_count, rng))
    expert_batch = (
        expert_buffer.sample(expert_count, rng) if expert_count and expert_buffer else None
    )
    for extra_buffer, extra_count in ((puzzle_buffer, puzzle_count), (tactic_buffer, tactic_count)):
        if extra_count:
            extra = extra_buffer.sample(extra_count, rng)
            expert_batch = extra if expert_batch is None else _concat_batches(expert_batch, extra)
    return batch, expert_batch


def play_move(
    game: _Game,
    index: int,
    max_plies: int | None = None,
    *,
    draw_penalty: float = 0.0,
    potential_scale: float = 0.0,
    gamma: float = 0.99,
) -> tuple[tuple, bool, str]:
    """Đi nước ``game.moves[index]``; trả về (chuyển tiếp, ván đã dừng chưa, kết quả)."""
    board = game.board
    state, action = game.state, int(game.actions[index])
    old_potential = potential(board, potential_scale)
    board.push(game.moves[index])
    outcome = board.outcome()
    if outcome is not None:
        done, reward, result = True, (1.0 if outcome.winner is not None else 0.0), outcome.result()
    elif board.is_repetition(3) or board.halfmove_clock >= 100:
        done, reward, result = True, 0.0, "1/2-1/2"
    else:
        done, reward, result = False, 0.0, "*"
    if done and reward == 0.0:
        reward = -draw_penalty
    next_potential = 0.0 if done else potential(board, potential_scale)
    reward = reward - gamma * next_potential - old_potential
    if done:
        next_state, next_mask = _EMPTY_STATE, _EMPTY_MASK
    else:
        game.state = encode(board)
        game.moves, game.actions = legal_actions(board)
        next_state, next_mask = game.state, action_mask(game.actions)
    finished = done or board.ply() - game.starting_ply >= game.max_plies
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


def _short(count: int) -> str:
    """Số gọn cho log: ``950``, ``8.5k``, ``1.2M``."""
    if count < 1000:
        return str(count)
    if count < 1_000_000:
        return f"{count / 1000:.1f}k"
    return f"{count / 1_000_000:.1f}M"


def _num(value: float, spec: str) -> str:
    """Định dạng số cho log; ``-`` khi chưa có (nan)."""
    return format(value, spec) if math.isfinite(value) else "-"


def _initial_model(config: TrainConfig) -> Model:
    """Mạng mới, hoặc nạp từ ``--init-weights`` (file ``save_weights``)."""
    if not config.init_weights:
        return Model(config.channels, config.blocks)
    data = load_file(config.init_weights)
    saved_scale = float(data.get("meta", {}).get("potential_scale", 0.0))
    if saved_scale != config.potential_scale:
        raise ValueError(
            f"init weights potential_scale={saved_scale} differs from "
            f"--potential-scale={config.potential_scale}"
        )
    model = Model(**data["config"])
    model.load_state_dict(data["model"])
    print(f"init weights: {config.init_weights} {data['config']}", flush=True)
    return model


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
    data = load_file(path, agent.device)
    agent.online.load_state_dict(data["online"])
    agent.target.load_state_dict(data["target"])
    agent.optimizer.load_state_dict(data["optimizer"])
    return int(data["games_done"])


def _score(result: object) -> float:
    return (result.wins + 0.5 * result.draws) / (result.wins + result.draws + result.losses)


def train(config: TrainConfig) -> Path:
    """Chạy self-play + học; trả về thư mục kết quả."""
    if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    out = Path(config.out)
    out.mkdir(parents=True, exist_ok=True)
    device = _device(config.device)
    rng = np.random.default_rng(config.seed)
    torch.manual_seed(config.seed)
    agent = Agent(
        _initial_model(config),
        gamma=config.gamma,
        lr=config.lr,
        tau=config.tau,
        huber_delta=config.huber_delta,
        device=device,
        margin=config.margin,
        margin_weight=config.margin_weight,
        double_dqn=config.double_dqn,
    )
    games_done = _load_checkpoint(agent, config.resume) if config.resume else 0
    regular_games_done = games_done
    buffer = ReplayBuffer(config.buffer_size)
    decisive_buffer = ReplayBuffer(config.decisive_buffer_size)
    mate_puzzles = load_mate_puzzles(config.mate_puzzles) if config.mate_puzzles else None
    mate_reviews = _parse_mate_review(config.mate_review)
    mate_progress = (
        _MateProgress(
            config.mate_max_level,
            config.mate_window,
            config.mate_pass_rate,
            config.mate_min_games,
            config.mate_max_games,
            _parse_level_max_games(config.mate_level_max_games),
        )
        if mate_puzzles is not None and not config.game_schedule
        else None
    )
    if mate_progress is not None:
        if not 1 <= config.mate_max_level <= 4:
            raise ValueError("mate_max_level must be between 1 and 4")
        if config.mate_window <= 0 or config.mate_min_games <= 0 or config.mate_max_games <= 0:
            raise ValueError("mate window and game limits must be positive")
        if not 0.0 <= config.mate_pass_rate <= 1.0 or config.mate_min_games > config.mate_max_games:
            raise ValueError("invalid mate pass rate or game limits")
        for level in range(1, config.mate_max_level + 1):
            if not mate_puzzles[level]:
                raise ValueError(f"mate puzzle CSV has no puzzles for level {level}")
    puzzle_share = max(config.puzzle_expert_fraction, config.regular_puzzle_expert_fraction)
    if config.expert_fraction + config.decisive_fraction + puzzle_share >= 1:
        raise ValueError("expert, decisive and puzzle fractions must leave room for self-play")
    phase_mix = parse_phase_mix(config.phase_mix)
    game_anchors = (
        parse_schedule(config.game_schedule, GAME_KINDS) if config.game_schedule else None
    )
    batch_anchors = (
        parse_schedule(config.batch_schedule, BATCH_KINDS) if config.batch_schedule else None
    )
    tactic_puzzles = load_tactic_puzzles(config.tactic_puzzles) if config.tactic_puzzles else None
    level_anchors = (
        parse_schedule(config.mate_level_schedule, LEVEL_KINDS)
        if config.mate_level_schedule
        else None
    )
    used_game_kinds = {kind for _, shares in game_anchors or [] for kind, v in shares.items() if v}
    used_batch_kinds = {
        kind for _, shares in batch_anchors or [] for kind, v in shares.items() if v
    }
    if "mate" in used_game_kinds | used_batch_kinds and mate_puzzles is None:
        raise ValueError("schedules use mate puzzles: pass --mate-puzzles")
    if "tactic" in used_game_kinds | used_batch_kinds and not tactic_puzzles:
        raise ValueError("schedules use tactic puzzles: pass --tactic-puzzles")
    if "pgn" in used_batch_kinds and not config.expert_pgn:
        raise ValueError("batch schedule uses pgn: pass --expert-pgn")
    for _, shares in batch_anchors or []:
        if sum(shares.values()) >= 1:
            raise ValueError("every batch schedule point must leave room for self-play samples")
    if not 0.0 <= config.puzzle_review <= 1.0:
        raise ValueError("puzzle_review must be in [0, 1]")
    if config.puzzle_review > 0 and mate_puzzles is None:
        raise ValueError("puzzle_review needs --mate-puzzles")
    for phase_name, shares in phase_mix.items():
        if config.puzzle_review + sum(shares.values()) > 1:
            raise ValueError(f"phase_mix for {phase_name} plus puzzle_review is more than 1")

    expert_parts = []
    gm_eval: dict[str, np.ndarray] | None = None
    if config.expert_pgn:
        expert_data = build_dataset(
            [config.expert_pgn], out / "expert.npz", config.potential_scale, config.gamma
        )
        # Cần đủ ván để tách 10 % làm bộ đo mà vẫn còn dữ liệu chuyên gia (PGN nhỏ thì bỏ qua gm%)
        if config.gm_positions > 0 and int(expert_data["game_ids"].max()) + 1 >= 20:
            gm_eval, expert_data = _split_gm_eval(expert_data, config.gm_positions)
            print(
                f"gm%: {len(gm_eval['actions'])} held-out grandmaster positions"
                f" (pretrain validation games, removed from the expert buffer)",
                flush=True,
            )
        expert_parts.append(expert_data)
    # Lời giải puzzle: kho riêng khi có tỉ lệ riêng, không thì gộp vào kho chuyên gia như cũ
    separate_puzzles = (
        config.puzzle_expert_fraction > 0
        or config.regular_puzzle_expert_fraction > 0
        or batch_anchors is not None
    )
    puzzle_buffer = None
    if config.mate_expert and mate_puzzles is not None:
        puzzle_data = mate_expert_data(mate_puzzles, config.potential_scale, config.gamma)
        if separate_puzzles:
            puzzle_buffer = ReplayBuffer.from_arrays(puzzle_data)
            print(f"loaded {len(puzzle_buffer)} puzzle solution transitions", flush=True)
        else:
            expert_parts.append(puzzle_data)
    tactic_buffer = None
    if tactic_puzzles and "tactic" in used_batch_kinds:
        tactic_buffer = ReplayBuffer.from_arrays(
            solution_data(tactic_puzzles, config.potential_scale, config.gamma)
        )
        print(f"loaded {len(tactic_buffer)} tactic solution transitions", flush=True)
    expert_buffer = None
    if expert_parts:
        keys = ("states", "actions", "masks", "next_states", "next_masks", "rewards", "dones")
        combined = {key: np.concatenate([part[key] for part in expert_parts]) for key in keys}
        expert_buffer = ReplayBuffer.from_arrays(combined)
        print(f"loaded {len(expert_buffer)} expert transitions", flush=True)
    curriculum_games = load_decisive_games([config.curriculum_pgn]) if config.curriculum_pgn else []
    if config.curriculum_pgn and not curriculum_games:
        raise ValueError("không tìm thấy ván quyết định hợp lệ trong curriculum PGN")
    logger = MetricsLogger(out / "metrics.csv")
    tactics = tactic_positions(config.tactics_positions) if config.tactics_positions > 0 else []
    print(
        f"device={device} games={config.games} start_at={regular_games_done} lr={config.lr:.6g}",
        flush=True,
    )

    slots: list[_Game | None] = [None] * config.parallel
    review_slots: set[int] = set()
    regular_games_started = games_done
    pending = 0
    losses: list[float] = []
    q_means: list[float] = []
    td_losses: list[float] = []
    margin_losses: list[float] = []
    results = {"1-0": 0, "0-1": 0, "1/2-1/2": 0, "*": 0}
    plies_total = 0
    decisive_mates = 0
    updates = 0
    samples_self = 0
    samples_decisive = 0
    samples_expert = 0
    drill_games_since_log = 0
    review_games_since_log = 0
    mate_summary_printed = False
    last_regular_phase: str | None = None
    mixed_mate_results: deque[bool] = deque(maxlen=config.mate_window)
    next_bench_progress = 0.2
    final_bench_done = False
    next_snapshot = (
        (regular_games_done // config.snapshot_every + 1) * config.snapshot_every
        if config.snapshot_every > 0
        else 0
    )
    best_score = -math.inf
    next_eval = (games_done // config.eval_every + 1) * config.eval_every
    started_at = time.time()
    deadline = started_at + config.max_hours * 3600 if config.max_hours > 0 else math.inf
    seconds_per_game: float | None = None
    mark_time, mark_games = started_at, games_done

    timed_out = False
    while (
        regular_games_done < config.games
        or any(game is not None for game in slots)
        or (mate_progress is not None and mate_progress.level <= config.mate_max_level)
    ):
        for slot, game in enumerate(slots):
            if game is None:
                if mate_progress is not None and mate_progress.level <= config.mate_max_level:
                    current_level = mate_progress.level
                    level = _draw_mate_level(current_level, mate_reviews, rng)
                    slots[slot] = _new_mate_game(
                        mate_puzzles[level],
                        level,
                        rng,
                        game_index=regular_games_started,
                    )
                    if level != current_level:
                        review_slots.add(slot)
                elif regular_games_started < config.games:
                    random_moves = regular_games_started < config.warmup_games
                    phase = phase_for(regular_games_started, config)
                    kind = phase.name
                    progress = regular_games_started / max(1, config.games)
                    if game_anchors is not None and not random_moves:
                        kind = draw_kind(schedule_at(game_anchors, progress), rng)
                    elif not random_moves:
                        kind = draw_start_kind(phase.name, phase_mix, config.puzzle_review, rng)
                    if kind == "mate":
                        if level_anchors is not None:
                            level = int(draw_kind(schedule_at(level_anchors, progress), rng)[1:])
                        else:
                            cap = mate_level_cap(progress, config.mate_max_level)
                            level = int(rng.integers(1, cap + 1))
                        slots[slot] = _new_mate_game(
                            mate_puzzles[level], level, rng, game_index=regular_games_started
                        )
                        slots[slot].regular = True
                    elif kind == "tactic":
                        fen, solution = tactic_puzzles[int(rng.integers(len(tactic_puzzles)))]
                        slots[slot] = _new_game(
                            False,
                            chess.Board(fen),
                            len(solution),
                            game_index=regular_games_started,
                        )
                    elif kind == "puzzle":
                        level = int(rng.integers(1, config.mate_max_level + 1))
                        slots[slot] = _new_mate_game(
                            mate_puzzles[level], level, rng, game_index=regular_games_started
                        )
                        slots[slot].regular = True
                    else:
                        if kind != phase.name:
                            phase = phase_by_name(kind, config)
                        initial_board = None
                        game_plies = config.max_plies
                        if not random_moves and curriculum_games:
                            game_plies = phase.max_plies
                            if phase.back_range is not None:
                                source = curriculum_games[int(rng.integers(len(curriculum_games)))]
                                initial_board = start_board(source, *phase.back_range, rng)
                        slots[slot] = _new_game(
                            random_moves,
                            initial_board,
                            game_plies,
                            game_index=regular_games_started,
                        )
                    regular_games_started += 1
        active = [slot for slot, game in enumerate(slots) if game is not None]
        lr = learning_rate_for(regular_games_done, config)
        for group in agent.optimizer.param_groups:
            group["lr"] = lr
        chosen = {
            slot: int(rng.integers(len(slots[slot].moves)))
            for slot in active
            if slots[slot].random_moves
        }
        learned = [slot for slot in active if slot not in chosen]
        if learned:
            by_temperature: dict[float, list[int]] = {}
            for slot in learned:
                game = slots[slot]
                temp = (
                    config.mate_temperature
                    if game.drill_level
                    else temperature_for(game.game_index, config)
                )
                by_temperature.setdefault(temp, []).append(slot)
            for temp, temperature_slots in by_temperature.items():
                states = np.stack([slots[slot].state for slot in temperature_slots])
                masks = np.stack([action_mask(slots[slot].actions) for slot in temperature_slots])
                picked = agent.act(states, masks, temp)
                for slot, action in zip(temperature_slots, picked, strict=True):
                    chosen[slot] = int(np.flatnonzero(slots[slot].actions == action)[0])

        level_change: tuple[int, int, float] | None = None
        for slot in active:
            game = slots[slot]
            transition, finished, result = play_move(
                game,
                chosen[slot],
                draw_penalty=config.draw_penalty,
                potential_scale=config.potential_scale,
                gamma=config.gamma,
            )
            game.pending.append(transition)
            terminal = bool(transition[4])
            _store_ready(game, buffer, config.n_step, config.gamma, finished, terminal)
            if finished:
                games_done += 1
                if game.drill_level and not game.regular:
                    success = _mate_success(game)
                    drill_games_since_log += 1
                    if slot in review_slots:
                        review_games_since_log += 1
                        review_slots.remove(slot)
                    changed = mate_progress.record(success, game.drill_level)
                    if changed is not None:
                        old_level, level_games, rate = changed
                        level_change = (old_level, level_games, rate)
                        print(
                            f"== mate L{old_level} done: {rate:.1%} over the last window,"
                            f" {level_games:,} games",
                            flush=True,
                        )
                        if mate_progress.level > config.mate_max_level:
                            print("== mate drills complete; starting regular games", flush=True)
                else:
                    if game.regular and mate_progress is not None:
                        mate_progress.record(_mate_success(game), game.drill_level)
                    elif game.regular and game.drill_level:
                        mixed_mate_results.append(_mate_success(game))
                    regular_games_done += 1
                results[result] += 1
                plies_total += game.board.ply() - game.starting_ply
                if game.board.is_checkmate():
                    decisive_mates += 1
                _copy_decisive(game, decisive_buffer)
                slots[slot] = None

        ready = regular_games_done >= config.warmup_games and len(buffer) >= config.learning_starts
        pending = pending + len(active) if ready else 0
        while pending >= config.train_every:
            pending -= config.train_every
            fractions = _batch_fractions(
                regular_games_done,
                mate_progress is not None and mate_progress.level <= config.mate_max_level,
                batch_anchors,
                config,
            )
            batch, expert_batch = _sample_batches(
                buffer,
                decisive_buffer,
                expert_buffer,
                config.batch_size,
                fractions["pgn"],
                fractions["decisive"],
                rng,
                puzzle_buffer,
                fractions["mate"],
                tactic_buffer,
                fractions["tactic"],
            )
            stats = agent.update(batch, expert_batch)
            updates += 1
            decisive_count = min(
                round(config.batch_size * fractions["decisive"]), len(decisive_buffer)
            )
            samples_decisive += decisive_count
            samples_self += len(batch["actions"]) - decisive_count
            samples_expert += len(expert_batch["actions"]) if expert_batch is not None else 0
            losses.append(stats["loss"])
            q_means.append(stats["q_mean"])
            td_losses.append(stats["td_loss"])
            margin_losses.append(stats["margin_loss"])

        timed_out = time.time() >= deadline
        if (
            games_done >= next_eval
            or regular_games_done >= config.games
            or timed_out
            or level_change is not None
        ):
            while next_eval <= games_done:
                next_eval += config.eval_every
            now = time.time()
            if mark_games >= config.warmup_games and games_done > mark_games:
                interval = (now - mark_time) / (games_done - mark_games)
                seconds_per_game = smooth(seconds_per_game, interval, config.eta_smoothing)
            mark_time, mark_games = now, games_done
            remaining = config.games - regular_games_done
            in_drills = mate_progress is not None and mate_progress.level <= config.mate_max_level
            eta = (
                math.nan if in_drills or seconds_per_game is None else seconds_per_game * remaining
            )
            policy = DQNPolicy(agent.online, device)
            games, plies = config.eval_games, config.max_plies
            vs_random = evaluate(policy, RandomOpponent(), games, games_done, plies)
            vs_greedy = evaluate(policy, GreedyCaptureOpponent(), games, 1, plies)
            score = (_score(vs_random) + _score(vs_greedy)) / 2
            tactics_hit = tactics_rate(agent.online, tactics, device)
            gm_hit = _gm_rate(agent.online, gm_eval, device)
            finished_games = sum(results.values())
            final_row = regular_games_done >= config.games or timed_out
            progress_done = regular_games_done / max(1, config.games)
            phase_name = (
                f"mate{level_change[0]}"
                if level_change is not None
                else f"mate{mate_progress.level}"
                if in_drills
                else f"mix {progress_done:.0%}"
                if game_anchors is not None
                else phase_for(max(0, regular_games_done - 1), config).name
            )
            bench_label: str | None = None
            if config.bench_eval_games > 0 and game_anchors is not None:
                # Đo B1.5 mỗi 20 % tiến độ (và ở dòng cuối nếu dừng sớm vì hết giờ)
                if progress_done >= next_bench_progress - 1e-9:
                    bench_label = f"{progress_done:.0%}"
                    while next_bench_progress <= progress_done + 1e-9:
                        next_bench_progress += 0.2
                    final_bench_done = progress_done >= 1.0
                elif final_row and not final_bench_done:
                    bench_label = f"{progress_done:.0%}"
                    final_bench_done = True
            elif config.bench_eval_games > 0:
                if level_change is not None:
                    bench_label = phase_name
                elif not in_drills:
                    if last_regular_phase is not None and phase_name != last_regular_phase:
                        bench_label = last_regular_phase
                    elif final_row and not final_bench_done:
                        bench_label = phase_name
                        final_bench_done = True
            if not in_drills and level_change is None:
                last_regular_phase = phase_name
            vs_bench = (
                evaluate(
                    policy,
                    MaterialAlphaBetaOpponent(config.bench_depth),
                    config.bench_eval_games,
                    games_done,
                    plies,
                    opening_plies=2,
                )
                if bench_label is not None
                else None
            )
            row = {
                "loss": float(np.mean(losses)) if losses else math.nan,
                "td_loss": float(np.mean(td_losses)) if td_losses else math.nan,
                "margin_loss": float(np.mean(margin_losses)) if margin_losses else math.nan,
                "q_mean": float(np.mean(q_means)) if q_means else math.nan,
                "win_rate": vs_random.wins / config.eval_games,
                "win_rate_greedy": vs_greedy.wins / config.eval_games,
                "score": score,
                "bench_score": _score(vs_bench) if vs_bench is not None else math.nan,
                "tactics": tactics_hit,
                "gm_match": gm_hit,
                "expert_fraction": _batch_fractions(
                    regular_games_done, in_drills, batch_anchors, config
                )["pgn"],
                "epsilon": 1.0 if regular_games_done <= config.warmup_games else 0.0,
                "temperature": (
                    config.mate_temperature
                    if in_drills or level_change is not None
                    else temperature_for(max(0, regular_games_done - 1), config)
                ),
                "buffer": len(buffer),
                "decisive_buffer": len(decisive_buffer),
                "updates": updates,
                "samples": samples_self + samples_decisive + samples_expert,
                **{
                    f"mate_rate_{level}": (
                        mate_progress.level_rate(level) if mate_progress is not None else math.nan
                    )
                    for level in range(1, 5)
                },
                "avg_plies": plies_total / max(1, finished_games),
                "white_wins": results["1-0"],
                "black_wins": results["0-1"],
                "draws": results["1/2-1/2"],
                "truncated": results["*"],
                "phase": phase_name,
                "mate_rate": (
                    level_change[2]
                    if level_change is not None
                    else mate_progress.rate
                    if in_drills
                    else sum(mixed_mate_results) / len(mixed_mate_results)
                    if mixed_mate_results
                    else math.nan
                ),
                "decisive_share": decisive_mates / max(1, finished_games),
                "minutes": (now - started_at) / 60,
                "eta_minutes": eta / 60,
                "lr": lr,
            }
            logger.log(step=games_done, **row)
            review_share = (
                review_games_since_log / drill_games_since_log if drill_games_since_log else 0.0
            )
            if in_drills or level_change is not None:
                shown_level = level_change[0] if level_change is not None else mate_progress.level
                level_text = (
                    f"L{shown_level} {_short(mate_progress.games_by_level[shown_level])}"
                    f"/{_short(mate_progress.max_games_for(shown_level))}"
                )
            elif game_anchors is not None:
                level_text = (
                    _level_mix_text(schedule_at(level_anchors, progress_done))
                    if level_anchors is not None
                    else f"L1-{mate_level_cap(progress_done, config.mate_max_level)}"
                )
            else:
                level_text = "-"

            # Hai dòng có nhãn rồi một dòng trống (dễ đọc, không tràn trên Kaggle). ``games`` =
            # số ván bài tập khi ở mate1–4, số ván thường sau đó. Còn lại xem metrics.csv.
            shown_games = (
                games_done if in_drills or level_change is not None else regular_games_done
            )
            eta_text = format_duration(eta) if math.isfinite(eta) else "-"
            print(
                f"games: {_short(shown_games):<6} phase: {row['phase']:<10}"
                f" level: {level_text:<13} eta: {eta_text:<8} min: {row['minutes']:.0f}\n"
                f"  q: {_num(row['q_mean'], '.3f'):<6}  td: {_num(row['td_loss'], '.3f'):<5}"
                f"  dec: {row['decisive_share']:.0%}  mate: {_num(row['mate_rate'], '.0%')}"
                f"  | random: {vs_random.wins}/{vs_random.draws}/{vs_random.losses}"
                f"  greedy: {vs_greedy.wins}/{vs_greedy.draws}/{vs_greedy.losses}"
                f"  score: {score:.3f}  tac: {_num(tactics_hit, '.0%')}"
                f"  gm: {_num(gm_hit, '.0%')}\n",
                flush=True,
            )
            if vs_bench is not None:
                print(
                    f"  B1.5 after {bench_label}:"
                    f" {vs_bench.wins}/{vs_bench.draws}/{vs_bench.losses}"
                    f" (W/D/L, {config.bench_eval_games} games) score={_score(vs_bench):.3f}",
                    flush=True,
                )
            if mate_progress is not None and level_change is not None:
                print(
                    f"  mate: {mate_progress.summary(review_share if mate_reviews else None)}",
                    flush=True,
                )
            if level_change is not None or final_row:
                print(
                    f"  samples: updates={updates:,} trained={row['samples']:,}"
                    f" (self {samples_self:,} / mate {samples_decisive:,}"
                    f" / expert {samples_expert:,})"
                    f" | buffer={len(buffer):,} mate_buffer={len(decisive_buffer):,}"
                    f" expert_buffer={len(expert_buffer) if expert_buffer is not None else 0:,}",
                    flush=True,
                )
            drill_games_since_log = 0
            review_games_since_log = 0
            if (
                mate_progress is not None
                and mate_progress.level > config.mate_max_level
                and not mate_summary_printed
                and not any(
                    game is not None and game.drill_level and not game.regular for game in slots
                )
            ):
                print(f"  mate summary: {mate_progress.final_summary()}", flush=True)
                mate_summary_printed = True
            losses.clear()
            q_means.clear()
            td_losses.clear()
            margin_losses.clear()
            results = dict.fromkeys(results, 0)
            plies_total = 0
            decisive_mates = 0
            _save_checkpoint(agent, regular_games_done, out / "checkpoint.pt")
            while config.snapshot_every > 0 and regular_games_done >= next_snapshot:
                save_weights(
                    agent.online,
                    out / _snapshot_name(next_snapshot),
                    {"potential_scale": config.potential_scale, "regular_games": next_snapshot},
                )
                print(f"  snapshot: {_snapshot_name(next_snapshot)}", flush=True)
                next_snapshot += config.snapshot_every
            if regular_games_done > config.warmup_games and score > best_score:
                best_score = score
                save_weights(
                    agent.online, out / "best.pt", {"potential_scale": config.potential_scale}
                )
        if timed_out:
            break

    save_weights(agent.online, out / "final.pt", {"potential_scale": config.potential_scale})
    if not (out / "best.pt").exists():
        save_weights(agent.online, out / "best.pt", {"potential_scale": config.potential_scale})
    return out


def _concat_batches(
    first: dict[str, np.ndarray], second: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """Ghép hai batch replay cùng cấu trúc."""
    return {key: np.concatenate((first[key], second[key])) for key in first}


def _level_mix_text(shares: dict[str, float]) -> str:
    """Tỉ lệ cấp chiếu hết dạng gọn cho log, vd ``1:15 2:25 3:35 4:25``."""
    total = sum(shares.values()) or 1.0
    return " ".join(
        f"{kind[1:]}:{shares[kind] / total:.0%}".replace("%", "")
        for kind in sorted(shares)
        if shares[kind] > 0
    )


def _batch_fractions(
    regular_games_done: int,
    in_drills: bool,
    batch_anchors: list | None,
    config: TrainConfig,
) -> dict[str, float]:
    """Tỉ lệ batch từ mỗi kho: theo ``--batch-schedule`` nếu có, không thì theo các cờ cũ."""
    if batch_anchors is not None:
        shares = schedule_at(batch_anchors, regular_games_done / max(1, config.games))
        return {kind: shares.get(kind, 0.0) for kind in BATCH_KINDS}
    return {
        "pgn": expert_fraction_for(regular_games_done, in_drills, config),
        "decisive": config.decisive_fraction,
        "mate": config.puzzle_expert_fraction
        if in_drills
        else config.regular_puzzle_expert_fraction,
        "tactic": 0.0,
    }


def expert_fraction_for(regular_games_done: int, in_drills: bool, config: TrainConfig) -> float:
    """Tỉ lệ mẫu kỳ thủ: ``expert_fraction`` khi làm bài tập và ở ván thường đầu tiên, giảm
    tuyến tính tới ``expert_fraction_end`` ở ván thường cuối (âm = giữ nguyên)."""
    if config.expert_fraction_end < 0 or in_drills or config.games <= 0:
        return config.expert_fraction
    progress = min(max(regular_games_done / config.games, 0.0), 1.0)
    return config.expert_fraction + progress * (config.expert_fraction_end - config.expert_fraction)


_EXPERT_KEYS = ("states", "actions", "masks", "next_states", "next_masks", "rewards", "dones")


def _split_gm_eval(
    data: dict[str, np.ndarray], count: int
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Tách ``count`` thế cờ của các ván kiểm tra pretrain làm bộ đo ``gm%``; bỏ mọi thế của các
    ván đó khỏi dữ liệu chuyên gia để mạng không học lại chúng."""
    game_ids = data["game_ids"]
    is_val = np.isin(game_ids, validation_games(int(game_ids.max()) + 1))
    val_index = np.flatnonzero(is_val)
    pick = np.random.default_rng(1).choice(
        val_index, size=min(count, len(val_index)), replace=False
    )
    states = np.unpackbits(data["states"][pick], axis=1).reshape(len(pick), PLANES, 8, 8)
    masks = np.unpackbits(data["masks"][pick], axis=1)[:, :ACTIONS].astype(np.bool_)
    gm_eval = {"states": states, "masks": masks, "actions": data["actions"][pick]}
    kept = {key: data[key][~is_val] for key in _EXPERT_KEYS}
    return gm_eval, kept


@torch.no_grad()
def _gm_rate(
    model: torch.nn.Module, gm_eval: dict[str, np.ndarray] | None, device: torch.device
) -> float:
    """Tỉ lệ thế mà nước Q cao nhất trùng nước kỳ thủ (thế của các ván chưa từng học)."""
    if gm_eval is None:
        return math.nan
    states = torch.as_tensor(gm_eval["states"], device=device)
    masks = torch.as_tensor(gm_eval["masks"], device=device)
    best = masked_q(model(states), masks).argmax(dim=1).cpu().numpy()
    return float(np.mean(best == gm_eval["actions"]))


def learning_rate_for(games_done: int, config: TrainConfig) -> float:
    """Tính lr tăng tuyến tính từ hệ số khởi động đến mức đầy đủ."""
    if config.lr_warmup_games <= 0:
        return config.lr
    progress = min(max(games_done / config.lr_warmup_games, 0.0), 1.0)
    return config.lr * (config.lr_warmup_factor + (1.0 - config.lr_warmup_factor) * progress)


class _MateProgress:
    """Theo dõi tỷ lệ chiếu hết và điều kiện lên cấp."""

    def __init__(
        self,
        max_level: int,
        window: int,
        pass_rate: float,
        min_games: int,
        max_games: int,
        level_max_games: dict[int, int] | None = None,
    ):
        self.level = 1
        self.max_level = max_level
        self.window = window
        self.pass_rate = pass_rate
        self.min_games = min_games
        self.max_games = max_games
        self.level_max_games = level_max_games or {}
        self.games = 0
        self.games_by_level = {level: 0 for level in range(1, 5)}
        self.successes_by_level = {level: 0 for level in range(1, 5)}
        self.completion_rates: dict[int, float] = {}
        self.results_by_level = {level: deque(maxlen=window) for level in range(1, 5)}
        self.results: deque[bool] = deque(maxlen=window)

    @property
    def rate(self) -> float:
        return sum(self.results) / len(self.results) if self.results else math.nan

    def max_games_for(self, level: int) -> int:
        """Số ván tối đa của một cấp (riêng cấp đó nếu có, không thì mặc định)."""
        return self.level_max_games.get(level, self.max_games)

    def level_rate(self, level: int) -> float:
        """Return the rolling success rate for a level, including review games."""
        results = self.results_by_level[level]
        return sum(results) / len(results) if results else math.nan

    def summary(self, review_share: float | None = None) -> str:
        """Describe finished, current, and future drill levels."""
        parts = []
        for level in range(1, self.max_level + 1):
            games = self.games_by_level[level]
            if level in self.completion_rates:
                detail = f"done {self.completion_rates[level]:.1%} ({games:,} games)"
            elif level == self.level:
                rate = self.level_rate(level)
                rate_text = f"{rate:.1%}" if math.isfinite(rate) else "n/a"
                detail = (
                    f"{rate_text} ({games:,}/{self.max_games_for(level):,},"
                    f" need ≥{self.pass_rate:.0%} after ≥{self.min_games:,})"
                )
                parts.append(f">L{level} {detail}")
                continue
            else:
                detail = "not started"
            parts.append(f"L{level} {detail}")
        if review_share is not None:
            parts.append(f"review {review_share:.0%}")
        return " | ".join(parts)

    def final_summary(self) -> str:
        """Describe total games, successes, and final rolling rate per level."""
        return " | ".join(
            f"L{level} {self.games_by_level[level]:,} games,"
            f" {self.successes_by_level[level]:,} mates,"
            f" final {self.level_rate(level):.1%}"
            for level in range(1, self.max_level + 1)
        )

    def record(self, success: bool, level: int | None = None) -> tuple[int, int, float] | None:
        recorded_level = self.level if level is None else level
        if recorded_level not in self.results_by_level:
            return None
        self.games_by_level[recorded_level] += 1
        self.successes_by_level[recorded_level] += int(success)
        self.results_by_level[recorded_level].append(success)
        if recorded_level != self.level:
            return None
        self.games = self.games_by_level[recorded_level]
        self.results = self.results_by_level[recorded_level]
        if self.games < self.max_games_for(self.level) and not (
            self.games >= self.min_games and self.rate >= self.pass_rate
        ):
            return None
        old_level, games, rate = self.level, self.games, self.rate
        self.completion_rates[old_level] = rate
        self.level += 1
        self.games = 0
        self.results = self.results_by_level.get(self.level, deque(maxlen=self.window))
        return old_level, games, rate


def mate_expert_data(
    puzzles: dict[int, list[tuple[str, list[chess.Move]]]],
    potential_scale: float = 0.0,
    gamma: float = 0.99,
) -> dict[str, np.ndarray]:
    """Mã hóa các nước của bên tấn công thành mẫu DQfD."""
    entries = [entry for level_entries in puzzles.values() for entry in level_entries]
    return solution_data(entries, potential_scale, gamma)


def solution_data(
    entries: list[tuple[str, list[chess.Move]]],
    potential_scale: float = 0.0,
    gamma: float = 0.99,
) -> dict[str, np.ndarray]:
    """Mẫu (s, a, r, s') cho các nước của bên giải puzzle. Nước chiếu hết: r = +1, kết thúc;
    nước cuối không chiếu hết (puzzle chiến thuật): chưa kết thúc, học tiếp bằng bootstrap."""
    samples: dict[str, list] = {
        key: []
        for key in ("states", "actions", "masks", "next_states", "next_masks", "rewards", "dones")
    }
    for fen, solution in entries:
        board = chess.Board(fen)
        attacker_moves = [solution[index] for index in range(0, len(solution), 2)]
        for index, move in enumerate(attacker_moves):
            state = encode(board)
            legal_moves, actions = legal_actions(board)
            mask = action_mask(actions)
            old_potential = potential(board, potential_scale)
            board.push(move)
            done = board.is_checkmate()
            if done:
                next_state, next_mask = _EMPTY_STATE, _EMPTY_MASK
                base_reward = 1.0
            else:
                next_state = encode(board)
                _, next_actions = legal_actions(board)
                next_mask = action_mask(next_actions)
                base_reward = 0.0
            next_potential = 0.0 if done else potential(board, potential_scale)
            reward = base_reward - gamma * next_potential - old_potential
            samples["states"].append(np.packbits(state.reshape(-1)))
            samples["actions"].append(int(actions[legal_moves.index(move)]))
            samples["masks"].append(np.packbits(mask))
            samples["next_states"].append(np.packbits(next_state.reshape(-1)))
            samples["next_masks"].append(np.packbits(next_mask))
            samples["rewards"].append(reward)
            samples["dones"].append(float(done))
            if done:
                break
            if index * 2 + 1 < len(solution):
                board.push(solution[index * 2 + 1])
    return {
        "states": np.stack(samples["states"]),
        "actions": np.asarray(samples["actions"], dtype=np.int64),
        "masks": np.stack(samples["masks"]),
        "next_states": np.stack(samples["next_states"]),
        "next_masks": np.stack(samples["next_masks"]),
        "rewards": np.asarray(samples["rewards"], dtype=np.float32),
        "dones": np.asarray(samples["dones"], dtype=np.float32),
    }


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
