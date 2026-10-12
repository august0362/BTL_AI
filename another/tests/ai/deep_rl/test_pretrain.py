import io
import zipfile

import chess
import chess.pgn
import numpy as np
import pytest

from ai.deep_rl.user.features import encode, move_to_action

torch = pytest.importorskip("torch")

from ai.deep_rl.user.model import Model  # noqa: E402
from ai.deep_rl.user.policy import load_policy  # noqa: E402
from ai.deep_rl.user.pretrain import (  # noqa: E402
    build_dataset,
    main,
    unpack_masks,
    winner_positions,
)
from ai.deep_rl.user.train import TrainConfig, _initial_model  # noqa: E402

BLACK_WINS = '[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n\n'
WHITE_WINS = '[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0\n\n'
DRAW = '[Result "1/2-1/2"]\n\n1. e4 e5 1/2-1/2\n\n'


def _game(text: str) -> chess.pgn.Game:
    return chess.pgn.read_game(io.StringIO(text))


def test_winner_positions_use_only_the_winning_side() -> None:
    samples = winner_positions(_game(BLACK_WINS))
    assert len(samples) == 2  # ...e5 and ...Qh4#
    board = chess.Board()
    board.push_uci("f2f3")
    state, action, mask = samples[0]
    assert np.array_equal(state, encode(board))
    assert action == move_to_action(chess.Move.from_uci("e7e5"), chess.BLACK)
    assert mask[action] and mask.sum() == board.legal_moves.count()
    assert len(winner_positions(_game(WHITE_WINS))) == 4
    assert winner_positions(_game(DRAW)) == []


def test_build_dataset_reads_pgn_and_zip(tmp_path) -> None:
    (tmp_path / "a.pgn").write_text(BLACK_WINS + DRAW, encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "b.zip", "w") as archive:
        archive.writestr("b.pgn", WHITE_WINS)
    data = build_dataset([tmp_path], tmp_path / "out" / "positions.npz")
    assert len(data["actions"]) == 6
    assert sorted(set(data["game_ids"].tolist())) == [0, 1]
    assert (tmp_path / "out" / "positions.npz").is_file()


def test_unpack_masks_matches_numpy() -> None:
    mask = np.zeros(4672, dtype=np.bool_)
    mask[[0, 7, 8, 4671]] = True
    packed = torch.from_numpy(np.packbits(mask)[None])
    assert np.array_equal(unpack_masks(packed)[0].numpy(), mask)


def test_forward_is_tanh_of_logits() -> None:
    model = Model(channels=8, blocks=1)
    states = torch.as_tensor(np.stack([encode(chess.Board())]))
    with torch.no_grad():
        assert torch.allclose(model(states), torch.tanh(model.logits(states)))


def test_pretrain_smoke_and_rl_init(tmp_path) -> None:
    (tmp_path / "games.pgn").write_text(BLACK_WINS + WHITE_WINS * 3, encoding="utf-8")
    out = tmp_path / "run"
    args = ["--pgn", str(tmp_path / "games.pgn"), "--out", str(out), "--epochs", "2"]
    args += ["--channels", "8", "--blocks", "1", "--batch-size", "4", "--device", "cpu"]
    assert main(args) == 0
    weights = out / "sl_pretrained.pt"
    assert (out / "pretrain_metrics.csv").is_file()
    board = chess.Board()
    assert load_policy(weights).select_move(board) in board.legal_moves

    model = _initial_model(TrainConfig(init_weights=str(weights)))
    saved = torch.load(weights, weights_only=True)
    assert model.config() == {"channels": 8, "blocks": 1}
    for key, value in model.state_dict().items():
        assert torch.equal(value, saved["model"][key])


def test_load_works_when_torch_utils_is_not_bound(tmp_path, monkeypatch) -> None:
    from ai.deep_rl.user.policy import save_weights

    save_weights(Model(channels=8, blocks=1), tmp_path / "w.pt")
    monkeypatch.delattr(torch, "_utils")  # as on Kaggle: module loaded, attribute missing
    assert load_policy(tmp_path / "w.pt").select_move(chess.Board()) in chess.Board().legal_moves
