import hashlib
from pathlib import Path

import chess
import pytest

from ai.deep_rl.bot import DeepRLBot
from ai.deep_rl.metrics import MetricsLogger, plot
from ai.deep_rl.user import policy
from ai.deep_rl.weights import resolve_weights


def test_metrics_csv_and_optional_plot(tmp_path: Path) -> None:
    csv_path = tmp_path / "nested" / "metrics.csv"
    logger = MetricsLogger(csv_path)
    logger.log(step=1, loss=0.5, win_rate=0.2, epsilon=1.0)
    logger.log(step=2, loss=0.3, win_rate=0.4, epsilon=0.8)
    assert csv_path.read_text(encoding="utf-8").splitlines() == [
        "step,loss,win_rate,epsilon",
        "1,0.5,0.2,1.0",
        "2,0.3,0.4,0.8",
    ]
    pytest.importorskip("matplotlib")
    output = tmp_path / "plot.png"
    plot(csv_path, output)
    assert output.is_file() and output.stat().st_size > 0


def test_weights_file_url_sha256_and_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "checkpoint.bin"
    source.write_bytes(b"weights")
    digest = hashlib.sha256(b"weights").hexdigest()
    cached = resolve_weights(source.as_uri(), digest, tmp_path / "cache")
    assert cached is not None and cached.read_bytes() == b"weights"
    with pytest.raises(ValueError, match="mismatch"):
        resolve_weights(source.as_uri(), "0" * 64, tmp_path / "bad-cache")


def test_bot_unavailable_and_random_stub(monkeypatch) -> None:
    with pytest.raises(NotImplementedError):
        policy.load_policy(None)
    bot = DeepRLBot()
    assert bot.is_baseline is True
    board = chess.Board()
    assert bot.select_move(board) in board.legal_moves

    class StubPolicy:
        def select_move(self, board):
            return next(iter(board.legal_moves))

    monkeypatch.setattr("ai.deep_rl.bot.load_policy", lambda *args, **kwargs: StubPolicy())
    bot = DeepRLBot()
    board = chess.Board()
    assert bot.select_move(board) in board.legal_moves
