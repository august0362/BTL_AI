# CONTEXT — Chess AI Tournament

> Tài liệu kiến trúc gốc của dự án. Mọi thành viên đọc file này trước khi code.
> Thay đổi hợp đồng giao diện (mục 4) phải qua PR có approve của `@august0362` và ghi vào `CHANGELOG.md`.
>
> Phiên bản tài liệu: **0.3.0** — cập nhật 2026-10-03

---

## 1. Mục tiêu

Hệ thống thi đấu cờ vua giữa 4 AI độc lập và người chơi:

| Option | Thuật toán | Package |
|---|---|---|
| 1 | Alpha-Beta + Linear Regression | `backend/ai/alphabeta_regression/` |
| 2 | Alpha-Beta + Genetic Algorithm | `backend/ai/genetic_alphabeta/` |
| 3 | Pure MCTS | `backend/ai/mcts/` |
| 4 | Deep Reinforcement Learning (DQN, PyTorch) | `backend/ai/deep_rl/` |

Luật cờ (nước hợp lệ, chiếu, hòa…) do thư viện `python-chess` đảm nhiệm. Không ai tự viết luật cờ.

## 2. Thành viên & vai trò

| GitHub | Vai trò |
|---|---|
| `@august0362` | Product Owner, admin repo, Lead Integrator, GUI/UX, **Option 4** |
| `@cieldontcry` | Option 1 |
| `@khanhtaduy2k5` | Option 2 |
| `@quanganh167` | Option 3 |
| Claude | Kiến trúc, đặc tả, test case, tài liệu, prompt cho Codex |
| Codex | Sinh code theo prompt của Claude |

Thành viên tự quyết thuật toán **bên trong** package của mình. Họ chỉ bắt buộc tuân thủ hợp đồng ở mục 4 và quy tắc ở mục 8.

## 3. Kiến trúc

### 3.1 Quy tắc phụ thuộc

```
                 ┌────────────┐
                 │   backend/core/    │  chỉ phụ thuộc python-chess
                 └─────▲──────┘
        ┌──────────────┼───────────────┐
   ┌────┴────┐   ┌─────┴──────┐   ┌────┴────┐
   │   backend/ai/   │◄──│ backend/tournament/│◄──│  frontend/gui/   │
   └─────────┘   └────────────┘   └─────────┘
```

| Module | Được import | CẤM import |
|---|---|---|
| `backend/core/` | `chess`, thư viện chuẩn | `ai`, `tournament`, `gui` |
| `backend/ai/base_bot.py`, `backend/ai/registry.py` | `core`, `chess` | các package bot cụ thể (chỉ nạp động qua chuỗi) |
| `backend/ai/<bot>/` | `ai.base_bot`, `core`, `chess`, thư viện ngoài | **bot khác**, `tournament`, `gui` |
| `backend/tournament/` | `core`, `ai.base_bot`, `ai.registry` | `gui`, import trực tiếp package bot |
| `frontend/gui/` | `core`, `tournament`, `ai.registry` | import trực tiếp package bot |

CI kiểm tra tự động các quy tắc trên (mục 9). Vi phạm thì CI đỏ và không merge được.

### 3.2 Cây thư mục

```text
BTL_AI/
├── backend/
│   ├── ai/                 # bot, lớp nền và registry
│   ├── config/             # cấu hình mặc định và cấu hình máy cá nhân
│   ├── core/               # trạng thái ván và kiểu dữ liệu
│   └── tournament/         # trận đấu, lịch sử và xếp hạng
├── frontend/
│   ├── gui/                # ứng dụng Pygame, màn hình và widget
│   └── resource/           # bảng màu và tài nguyên giao diện
├── database/
│   └── data/               # lịch sử và xếp hạng tạo khi chơi (.gitignore)
├── documents/              # CONTEXT, hướng dẫn, kế hoạch và prompt
├── environments/
│   ├── .python-version
│   ├── requirements.txt
│   └── requirements-dev.txt
├── another/
│   ├── local_tools/        # công cụ cá nhân (.gitignore)
│   ├── scripts/            # script Windows cho Git và kiểm thử
│   ├── tests/              # test đơn vị, hợp đồng và kiến trúc
│   └── tools/              # công cụ phát triển và tạo tài nguyên
├── .github/                # workflow, CODEOWNERS và mẫu Pull Request
├── .venv/                  # môi trường Python cục bộ
├── main.py                 # điểm khởi chạy
├── run.bat
├── pyproject.toml
└── README.md
```

Các tên package Python vẫn là `ai`, `core`, `tournament` và `gui`. `run.bat`, pytest và CI thêm `backend/`, `frontend/` và `another/` vào đường dẫn import.

## 4. Hợp đồng giao diện

### 4.1 `backend/ai/base_bot.py` — BaseBot

```python
from abc import ABC, abstractmethod
import chess

class BaseBot(ABC):
    bot_id: str = ""          # khớp khóa trong registry, vd "mcts"
    display_name: str = ""    # tên hiện trên GUI

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.last_search_info: dict = {}

    @abstractmethod
    def select_move(self, board: chess.Board) -> chess.Move:
        """Trả về một nước HỢP LỆ cho board.turn. Board là bản sao."""

    def reset(self) -> None:
        """Gọi trước mỗi ván mới. Mặc định: xóa last_search_info."""
        self.last_search_info = {}
```

**Quy tắc bắt buộc cho mọi bot:**
1. `select_move` nhận **bản sao** bàn cờ. Bot được phép push/pop trên bản sao, nhưng không giữ tham chiếu sang ván sau.
2. Luôn trả về một nước nằm trong `board.legal_moves`. Harness chỉ gọi khi ván chưa kết thúc.
3. Không có biến toàn cục dùng chung giữa các instance. Hai instance cùng loại phải chạy độc lập, vì cần cho trận bot tự đấu với chính nó.
4. Import package bot **không được** tốn nhiều thời gian hay tải mô hình nặng. Việc tải trọng số làm trong `__init__` hoặc lười ở nước đi đầu tiên.
5. Nếu bot không thể khởi tạo (vd thiếu trọng số, không có mạng), `__init__` raise `BotUnavailableError(message)` (định nghĩa trong `backend/ai/base_bot.py`). GUI sẽ khóa bot đó kèm thông báo, không crash.
6. `last_search_info` là dict tùy chọn, cập nhật sau mỗi lần `select_move`. Các khóa chuẩn (đều tùy chọn): `depth: int`, `nodes: int`, `eval: float` (−1..1, góc nhìn bên vừa đi). Thời gian suy nghĩ do harness tự đo, bot không cần báo.
7. **Không giới hạn thời gian** (xem Open Issue OI-1). Tham số thời gian sau này sẽ truyền qua `config` nên chữ ký hàm không đổi.
8. Test hợp đồng (`another/tests/ai/test_bot_contract.py`) khởi tạo bot với `config = {"fast_mode": True, "allow_random_init": True, "seed": 0}`:
   - `fast_mode`: bot nên dùng tìm kiếm nhỏ (vd depth 1–2, vài trăm simulation) để CI chạy nhanh.
   - `allow_random_init`: bot cần trọng số được phép khởi tạo ngẫu nhiên khi thiếu file.
   - `seed`: bot có yếu tố ngẫu nhiên nên dùng `random.Random(seed)` riêng, **không** dùng `random` toàn cục.
   - Bot bỏ qua những khóa mình không dùng.

### 4.2 `backend/ai/registry.py`

```python
BOT_REGISTRY: dict[str, str] = {
    "alphabeta_regression": "ai.alphabeta_regression.bot:AlphaBetaRegressionBot",
    "genetic_alphabeta":    "ai.genetic_alphabeta.bot:GeneticAlphaBetaBot",
    "mcts":                 "ai.mcts.bot:MctsBot",
    "deep_rl":              "ai.deep_rl.bot:DeepRLBot",
}
DEBUG_BOTS: dict[str, str] = {"random": "ai.random_bot.bot:RandomBot"}
BENCHMARK_BOTS: dict[str, str] = {
    "bench_random":           "ai.benchmarks.bot:BenchmarkRandomBot",
    "bench_alphabeta_material": "ai.benchmarks.bot:BenchmarkMaterialBot",
    "bench_alphabeta3":       "ai.benchmarks.bot:BenchmarkAlphaBetaBot",
    "bench_alphabeta_tt":     "ai.benchmarks.bot:BenchmarkAlphaBetaTTBot",
    "bench_alphabeta_custom": "ai.benchmarks.bot:BenchmarkAlphaBetaCustomBot",
}

def list_bots(include_debug: bool = False, include_baseline: bool = False,
              include_benchmarks: bool = False) -> list[str]: ...
def create_bot(bot_id: str, config: dict | None = None) -> BaseBot: ...  # importlib, raise BotUnavailableError
```

Mỗi bot đặt lớp chính ở `backend/ai/<bot>/bot.py`.

**Bot benchmark (quyết định 2026-10-07, cập nhật cùng ngày):** `BENCHMARK_BOTS` là danh sách **opt-in**, chỉ trả về khi gọi `list_bots(include_benchmarks=True)`; mặc định của `list_bots()` không đổi. GUI gọi `list_bots(include_debug=show_debug_bots, include_benchmarks=True)` nên màn **Người vs Bot**, **Bot vs Bot** và **Xếp hạng Elo** đều có đủ **8 bot** (4 thành viên + 4 benchmark); giải **Xếp hạng AI** (§4.9) cũng nạp đủ 8 bot. Bot `baseline` (`BASELINE_BOTS`) **không** hiện trên GUI (không ở màn chọn, không ở bảng Elo). `create_bot` nhận cả 4 khóa benchmark.

**Baseline ngẫu nhiên (quyết định 2026-10-04):** bot nào chưa có code thật thì tạm **đi nước hợp lệ ngẫu nhiên**, để GUI và giải đấu luôn chơi được đủ 4 bot.
- Lớp dùng chung `backend/ai/baseline.py::RandomBaselineBot(BaseBot)`. Thuộc tính `is_baseline = True`, có `random.Random(config.get("seed"))` riêng. Đặt ở `backend/ai/` (không phải package bot), nên các bot được phép import.
- Khung `backend/ai/<bot>/bot.py` của 3 bot thành viên kế thừa `RandomBaselineBot`. Thành viên viết bot thật thì thay toàn bộ lớp và bỏ kế thừa đó, `is_baseline` trở về `False`.
- `DeepRLBot`: nếu `user.policy.load_policy` còn raise `NotImplementedError` thì chạy chế độ baseline (`is_baseline = True`), không raise `BotUnavailableError` nữa. Lỗi thật khác (thiếu trọng số, sai sha256…) vẫn raise `BotUnavailableError`.
- GUI ghi thêm hậu tố `t("players.baseline_suffix")` ("(baseline)") sau tên bot đang ở chế độ baseline: màn chuẩn bị, panel, lịch sử, xếp hạng.
- Khi bot thật thay baseline, nhóm nên bấm **Đặt lại** bảng xếp hạng (Elo cũ là của bản ngẫu nhiên).

### 4.3 `backend/core/` — GameState & kiểu dữ liệu

```python
# backend/core/types.py
class Termination(StrEnum):          # giá trị ghi vào JSON — KHÔNG đổi
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"
    FIFTY_MOVES = "fifty_moves"
    MAX_PLIES = "max_plies"
    ABORTED = "aborted"

class IllegalMoveError(ValueError): ...
class GameOverError(RuntimeError): ...

@dataclass(frozen=True)
class GameResult:
    winner: chess.Color | None     # None = hòa (hoặc ABORTED)
    termination: Termination
    def score_for(self, color: chess.Color) -> float: ...  # 1 / 0.5 / 0; ABORTED -> ValueError

@dataclass(frozen=True)
class MoveRecord:
    ply: int; uci: str; san: str
    think_time_s: float
    search_info: dict              # bản sao last_search_info
    material_eval: float           # giá trị thanh đánh giá sau nước đi
    is_random_opening: bool

# backend/core/game_state.py
class GameState:
    def __init__(self, fen: str | None = None, max_plies: int = 300,
                 claim_draw: bool = True): ...     # max_plies <= 0 -> ValueError
    board: chess.Board          # property, luôn trả BẢN SAO (giữ move_stack)
    turn: chess.Color           # property
    fen: str                    # property, FEN hiện tại
    starting_fen: str           # property, FEN lúc tạo
    ply_count: int              # property, số nửa nước đã push QUA GameState này
    def legal_moves(self) -> list[chess.Move]: ...
    def push(self, move: chess.Move) -> str: ...   # trả SAN; IllegalMoveError / GameOverError
    def is_over(self) -> bool: ...
    def result(self) -> GameResult | None: ...     # None nếu chưa xong
    def to_pgn(self, headers: dict[str, str]) -> str: ...  # Result: 1-0 / 0-1 / 1/2-1/2 / *
```

`GameState` **không có undo** vì đây là yêu cầu sản phẩm.

### 4.4 Luật kết thúc ván

Phần này viết cho người chưa chơi cờ vua. Ván kết thúc khi:

| Tình huống | Kết quả | Giải thích |
|---|---|---|
| **Chiếu hết** (checkmate) | Bên chiếu thắng | Vua bị tấn công và không còn cách thoát |
| **Hết nước** (stalemate) | Hòa | Đến lượt nhưng không có nước hợp lệ, và vua không bị chiếu |
| **Không đủ quân** | Hòa | Không bên nào còn đủ quân để chiếu hết (vd chỉ còn Vua với Vua) |
| **Lặp 3 lần** | Hòa | Cùng một thế cờ xuất hiện lần thứ 3 |
| **Luật 50 nước** | Hòa | 50 nước liên tiếp (100 nửa nước) không ai ăn quân, không ai đi Tốt |
| **Giới hạn an toàn** | Hòa | Ván dài quá `max_plies` = **300 nửa nước** (mặc định), để tránh 2 bot đi mãi |
| **Dừng ván** | Không tính | Người dùng bấm "Dừng ván", ván không ghi vào xếp hạng |

Thuật ngữ:
- **Nửa nước (ply):** một lần đi của một bên. "1 nước" trong cờ vua = trắng đi + đen đi = 2 nửa nước.
- Lặp 3 lần và luật 50 nước được **tự áp dụng** (khi `claim_draw = true`), không cần ai "xin hòa".
- Mọi giới hạn đều chỉnh được trong `backend/config/default.toml`.

Quy tắc cài đặt (cho Codex/dev) — kiểm tra theo **đúng thứ tự** sau, dừng ở điều kiện đầu tiên đúng:
1. Chiếu hết / hết nước (`board.outcome(claim_draw=False)`). Chiếu hết thắng mọi luật hòa.
2. Không đủ quân (`board.is_insufficient_material()`).
3. Nếu `claim_draw`: `board.is_repetition(3)` → THREEFOLD_REPETITION.
4. Nếu `claim_draw`: `board.halfmove_clock >= 100` → FIFTY_MOVES.
5. Luật tự động của python-chess (lặp 5 lần → THREEFOLD_REPETITION, 75 nước → FIFTY_MOVES).
6. `ply_count >= max_plies` → MAX_PLIES.

⚠️ **Không** dùng `board.outcome(claim_draw=True)`: hàm này coi là hòa cả khi "nước tiếp theo **có thể** tạo lặp 3 lần", nên kết thúc ván sớm 1 nửa nước.

### 4.5 `backend/core/material.py` — Thanh đánh giá

Thanh đánh giá dùng **chênh lệch quân** (phương án B), trung lập và không phụ thuộc bot nào:
- Giá trị: Tốt 1, Mã 3, Tượng 3, Xe 5, Hậu 9, Vua 0.
- `material_diff(board) -> int` = tổng quân trắng − tổng quân đen.
- `eval_bar_value(board, scale) -> float` = `tanh(material_diff / scale)`, nằm trong khoảng −1 (đen ưu thế tuyệt đối) đến +1 (trắng ưu thế tuyệt đối). `scale` mặc định 8.

### 4.6 `backend/tournament/` — Điều phối ván đấu

`backend/tournament/` **không** biết gì về GUI, file xếp hạng hay lịch sử khi đang chơi. GUI (controller) nhận `GameRecord` qua callback rồi tự gọi `Ranking`/`History`.

```python
# backend/tournament/players.py
HUMAN_ID = "human"

class MatchAborted(Exception): ...          # HumanPlayer bị hủy khi đang chờ

class Player(Protocol):                     # BaseBot và HumanPlayer đều thỏa mãn
    bot_id: str
    display_name: str
    def select_move(self, board: chess.Board) -> chess.Move: ...
    def reset(self) -> None: ...

class HumanPlayer:
    bot_id = HUMAN_ID
    def __init__(self, display_name: str = "Human"): ...
    def submit_move(self, move: chess.Move) -> None: ...  # GUI gọi (luồng GUI)
    def select_move(self, board) -> chess.Move: ...       # chặn chờ; BỎ QUA nước không hợp lệ
    def cancel(self) -> None: ...                         # select_move đang chờ -> raise MatchAborted
    def reset(self) -> None: ...                          # xóa hàng đợi + trạng thái hủy
```

```python
# backend/tournament/records.py
@dataclass
class GameRecord:
    game_id: str                 # uuid4().hex
    started_at: str              # ISO-8601 UTC, độ chính xác micro giây
    mode: str                    # "human_vs_bot" | "bot_vs_bot"
    white_id: str                # bot_id hoặc "human"
    black_id: str
    white_name: str
    black_name: str
    opening_moves: list[str]     # UCI, khai cuộc ngẫu nhiên
    moves: list[MoveRecord]      # MỌI nước, kể cả khai cuộc (is_random_opening=True)
    result: GameResult
    pgn: str = ""
    series_id: str | None = None
    series_game_index: int | None = None   # 1-based
    error: str | None = None     # lý do nếu ván bị hủy do bot lỗi
    def to_json(self) -> dict: ...          # json.dumps được; winner: "white"/"black"/null
    @classmethod
    def from_json(cls, d: dict) -> "GameRecord": ...   # from_json(r.to_json()) == r
```

```python
# backend/tournament/match_runner.py
def generate_random_opening(plies: int, rng: random.Random) -> list[str]: ...
    # từ thế cờ chuẩn; kết quả KHÔNG được là ván đã kết thúc (chọn lại, tối đa 100 lần)

class MatchRunner:
    def __init__(self, white: Player, black: Player, *, mode: str = "bot_vs_bot",
                 random_opening_plies: int = 0, opening_moves: list[str] | None = None,
                 max_plies: int = 300, claim_draw: bool = True, eval_scale: float = 8.0,
                 rng: random.Random | None = None,
                 on_move: Callable[[MoveRecord, GameState], None] | None = None,
                 series_id: str | None = None, series_game_index: int | None = None,
                 clock: Callable[[], float] = time.perf_counter): ...
    def play(self) -> GameRecord: ...       # đồng bộ; GUI gọi trong luồng nền
    def request_stop(self) -> None: ...     # an toàn từ luồng khác
    def pause(self) -> None: ...            # chặn TRƯỚC nước kế tiếp
    def resume(self) -> None: ...
```

Hành vi `play()`:
1. Gọi `reset()` của cả hai người chơi.
2. Khai cuộc: nếu có `opening_moves` thì dùng đúng danh sách đó; ngược lại nếu `random_opening_plies > 0` thì `generate_random_opening`. Các nước khai cuộc: `think_time_s = 0`, `search_info = {}`, `is_random_opening = True`, vẫn gọi `on_move`. Người chơi **không** được hỏi trong lúc khai cuộc.
3. Vòng lặp tới khi `GameState.is_over()`. Mỗi lượt, trước khi hỏi người chơi: chờ nếu đang pause; nếu đã `request_stop` thì hủy.
4. Hỏi `select_move(state.board)` (bản sao), đo thời gian bằng `clock`. Nếu sau khi nhận nước mà đã `request_stop` thì hủy, **không** push nước đó.
5. Ghi `MoveRecord`: `ply = state.ply_count` sau khi push, `search_info` = **bản sao** `last_search_info` (nếu có), `material_eval = eval_bar_value(board, eval_scale)`. Rồi gọi `on_move(record, state)`.
6. **Ván bị hủy** (`Termination.ABORTED`, `winner=None`) khi: `request_stop`, `HumanPlayer` raise `MatchAborted`, bot raise exception bất kỳ, hoặc bot trả nước không hợp lệ. Hai trường hợp cuối điền `error` (có `bot_id` + mô tả). **Không bao giờ để exception của bot lan ra ngoài** (GUI không được crash).
7. `request_stop()` cũng gọi `cancel()` của người chơi nào có hàm đó (để giải phóng `HumanPlayer` đang chờ).
8. `pgn` được điền khi ván kết thúc, headers gồm `White`, `Black` (display name) và `Date`.

```python
# backend/tournament/series.py
def series_colors(n_games: int, rng: random.Random) -> list[bool]: ...
    # True = A cầm trắng. 1 ván: [True]. 3 ván: [True, False, rng.choice([True, False])]

@dataclass
class SeriesResult:
    series_id: str
    a_id: str
    b_id: str
    games: list[GameRecord]
    score_a: float
    score_b: float
    winner: str | None           # "a" | "b" | None (hòa trận hoặc bị hủy)
    aborted: bool

class SeriesRunner:
    def __init__(self, player_a: Player, player_b: Player, n_games: int, *,  # n_games ∈ {1, 3}
                 random_opening_plies: int = 0, max_plies: int = 300, claim_draw: bool = True,
                 eval_scale: float = 8.0, rng: random.Random | None = None,
                 on_move=None, on_game_end: Callable[[GameRecord], None] | None = None): ...
    def play(self) -> SeriesResult: ...
    def request_stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
```

- Series luôn là `mode="bot_vs_bot"`. Người vs Bot dùng thẳng `MatchRunner` (1 ván).
- Khai cuộc ngẫu nhiên sinh **một lần** cho cả loạt, rồi truyền qua `opening_moves` cho từng ván.
- Best of 3 **đấu đủ 3 ván**. Ván bị hủy thì loạt dừng ngay: `aborted=True`, `winner=None`.
- Điểm: thắng 1, hòa 0,5, thua 0. Bằng điểm thì `winner=None`.

### 4.7 Xếp hạng (`backend/tournament/ranking.py`)

```python
@dataclass
class PlayerStats:
    wins: int = 0
    draws: int = 0
    losses: int = 0
    elo: float = 1200.0
    games: int       # property
    points: float    # property = wins + 0.5 * draws

def expected_score(r_a: float, r_b: float) -> float: ...   # 1 / (1 + 10 ** ((r_b - r_a) / 400))

class Ranking:
    def __init__(self, path: Path | None, *, elo_initial: float = 1200, elo_k: float = 32,
                 known_ids: Iterable[str] = (), debug_ids: Iterable[str] = ("random",)): ...
        # path=None: chỉ trong bộ nhớ. File hỏng -> đổi tên thành <tên>.corrupt, bắt đầu mới
    def stats(self, player_id: str) -> PlayerStats: ...     # id lạ -> PlayerStats mặc định
    def table(self) -> list[tuple[str, PlayerStats]]: ...   # gồm mọi known_ids; sắp Elo giảm dần, rồi points, rồi id
    def record_game(self, record: GameRecord) -> bool: ...  # True nếu được tính; tự lưu file
    def reset(self) -> None: ...                            # tự lưu file
```

- Hồ sơ gồm **8 bot** (4 thành viên + 4 benchmark) và **một hồ sơ chung `human`**. Elo mọi hồ sơ bắt đầu từ `ranking.elo_initial` (1200) và chỉ thay đổi qua ván Người vs Bot / Bot vs Bot; giải Xếp hạng AI (§4.9) **không** ghi vào Elo.
- Mỗi **ván** cập nhật W/D/L và Elo cho cả hai bên, dùng rating **trước** ván: `R_mới = R + K·(S − E)`.
- `record_game` trả `False` và **không** thay đổi gì khi: ván ABORTED, `white_id == black_id`, hoặc một bên thuộc `debug_ids`.
- File JSON: `{"version": 1, "players": {id: {wins, draws, losses, elo}}}`. Ghi an toàn: ghi file tạm cùng thư mục rồi `os.replace`.
- Giải round-robin cá nhân (`another/local_tools/`) dùng file riêng `database/data/local_arena/`, không đụng `database/data/ranking.json`.

### 4.8 Lịch sử ván (`backend/tournament/history.py`)

```python
class History:
    def __init__(self, directory: Path, max_games: int = 20): ...   # tự tạo thư mục
    def save(self, record: GameRecord) -> Path: ...    # <dir>/<game_id>.json, rồi xóa ván cũ vượt max
    def list(self) -> list[GameRecord]: ...            # mới nhất trước (started_at, rồi game_id); bỏ qua file hỏng
    def load(self, game_id: str) -> GameRecord: ...
    def export_pgn(self, game_id: str, dest: Path) -> Path: ...     # ghi record.pgn ra file
```

- Mỗi **ván đơn lẻ** là một mục. Ván trong Best of 3 có `series_id` và `series_game_index` để GUI ghi chú "Ván 2/3".
- Ván bị hủy **vẫn lưu** (để xem lại) nhưng không tính xếp hạng.

### 4.9 Bảng xếp hạng AI — giải vòng tròn (`backend/ai/benchmarks/`, `backend/tournament/`)

Thang **bot benchmark** cho việc phân loại sức mạnh, tách khỏi xếp hạng Elo (§4.7). Bốn bot nằm trong package `backend/ai/benchmarks/` (đăng ký opt-in ở §4.2):

| id | Tên | Cách chơi |
|---|---|---|
| `bench_random` | Benchmark 1 · Random | Chọn đều ngẫu nhiên trong các nước hợp lệ (có `seed`) |
| `bench_alphabeta_material` | Benchmark 1.5 · Alpha-Beta thuần | Negamax alpha-beta độ sâu 3, eval `material` (tổng quân mình − tổng quân địch), tất định — mốc "Alpha-Beta thuần" |
| `bench_alphabeta3` | Benchmark 2 · Alpha-Beta 3 | Negamax alpha-beta, độ sâu cố định (mặc định 3), eval `pst` (vật chất + bảng ô quân), hòa ngẫu nhiên có `seed` giữa các nước tốt nhất |
| `bench_alphabeta_tt` | Benchmark 3 · Alpha-Beta TT | Eval `pst` như Benchmark 2 + bảng chuyển vị (Zobrist), sắp xếp nước đi (MVV-LVA, phong cấp, killer) và **quiescence search** (chỉ xét nước ăn quân ở lá, tối đa 8 nửa nước) |
| `bench_alphabeta_custom` | Benchmark 4 · Alpha-Beta Custom | Như Benchmark 3 + check extension (tối đa 2 lần) + mobility (mã/tượng 4, xe 2, hậu 1 điểm mỗi ô kiểm soát), độ sâu mặc định 3; khi `depth >= 4` bật thêm null-move pruning (R=2) + late move reductions; eval mặc định `advanced` = `pst` + cấu trúc tốt (chồng −15, cô lập −15, thông +5..+100 theo hàng) + an toàn vua trước tàn cuộc (thiếu tốt che −15/cột, cột mở quanh vua −20) + cặp tượng +30 + xe cột mở +20 / nửa mở +10; tính bằng bitboard, cache theo vị trí tốt và vua; đổi được qua `evaluator` |

```python
# backend/ai/benchmarks/evaluation.py   (eval trả điểm theo bên đang đi, dùng cho negamax)
def material_evaluator(board) -> float: ...     # bọc ai.baseline.evaluate
def positional_evaluator(board) -> float: ...   # thêm kiểm soát trung tâm + phát triển quân
def pst_evaluator(board) -> float: ...          # Benchmark 2: vật chất + bảng ô quân, chiếu hết theo ply
def register_evaluator(name: str, evaluator) -> None: ...   # mở rộng cho Benchmark 4
def build_evaluator(name: str = "positional") -> Callable: ...   # tên lạ -> ValueError

# backend/ai/benchmarks/search.py
class SearchResult(NamedTuple):
    move: chess.Move | None; score: float; nodes: int; depth: int = 0
class SearchTimeout(Exception): ...            # nội bộ: hết ngân sách thời gian giữa chừng
class TranspositionTable:                       # khóa Zobrist, cờ EXACT/LOWERBOUND/UPPERBOUND
    def clear(self) -> None: ...
    def get(self, key: int) -> tuple[int, float, int, chess.Move | None] | None: ...
    def store(self, key, depth, score, flag, move) -> None: ...
def order_moves(board, *, tt_move=None, killer=None) -> list[chess.Move]: ...
def alpha_beta(board, depth, evaluator) -> SearchResult: ...
def alpha_beta_tt(board, depth, evaluator, *, tt=None, killers=None) -> SearchResult: ...
    # alpha_beta_tt phải cho CÙNG điểm với alpha_beta trên mọi thế cờ
def alpha_beta_iterative(board, max_depth, evaluator, *, tt=None, killers=None,
                         time_limit_s=None) -> SearchResult: ...
    # sâu dần 1..max_depth; hết `time_limit_s` (giây) thì bỏ kết quả dở và trả nước
    # của tầng sâu nhất đã tính xong. time_limit_s=None/<=0 -> tính đủ max_depth.
```

**Benchmark 2 — mục tiêu độ khó (quyết định 2026-10-07):** người chơi bình thường **thắng được nếu chơi cẩn thận**, nhưng **không thắng nhanh** bằng mẹo đơn giản. Vì vậy:
- Eval `pst` (`evaluation.pst_evaluator`, đăng ký tên `"pst"`): `PIECE_VALUES` + bảng ô quân "Simplified Evaluation Function" (Tomasz Michniewski) cho tốt, mã, tượng, xe, hậu; vua dùng bảng trung cuộc, chuyển sang bảng tàn cuộc khi **cả hai bên không còn hậu** hoặc mỗi bên có ≤ 1 quân nhẹ ngoài tốt. Bảng viết theo góc nhìn Trắng (a8 ở đầu mảng), Đen lật hàng (`chess.square_mirror`).
- Chiếu hết: `-(MATE_SCORE - board.ply())` theo bên đang đi → bot ưu tiên chiếu hết **nhanh** và chống đỡ **lâu**. Hòa (`is_stalemate`, `is_insufficient_material`, `is_repetition(3)`, `can_claim_fifty_moves`) = 0 → khi đang hơn quân bot tránh lặp nước.
- **Không** có quiescence search (cố ý: bot còn lỗi "đường chân trời" — người chơi có thể khai thác bằng chiến thuật đổi quân/đòn phối hợp).
- Ở gốc, các nước có điểm bằng nhau (chênh ≤ 1e-9) được chọn ngẫu nhiên bằng `random.Random(config.get("seed"))` → không học thuộc được một đường thắng duy nhất; cùng `seed` thì vẫn tất định. `alpha_beta_iterative(..., rng=None)` nhận thêm `rng` (mặc định `None` = hành vi cũ, nước đầu tiên); chỉ Benchmark 2 truyền `rng`.
- `[bots.bench_alphabeta3] evaluator` (mặc định `"pst"`) cho phép đổi eval; `material_evaluator` giữ nguyên cho test và các bot khác.

`bench_alphabeta_tt` / `bench_alphabeta_custom` giữ bảng chuyển vị và killer **trong một ván**; `reset()` (gọi đầu mỗi ván) xóa cả hai.
Ba bot tìm kiếm dùng `alpha_beta_iterative` với `config["max_think_time_s"]` (không có/<=0 = không giới hạn) nên **không bao giờ vượt trần thời gian mỗi nước**.

```python
# backend/tournament/tournament_config.py
@dataclass(frozen=True)
class TournamentConfig:
    bots: tuple[str, ...]
    matches_per_pair: int = 20     # mỗi cặp đấu bấy nhiêu ván, chia đều Trắng/Đen
    max_history: int = 10          # số "Trận Chiến Lần n" giữ lại (FIFO)
    max_plies: int = 150           # quá số nửa nước -> hòa (không vờn nhau vô tận)
    depth: int = 0                 # > 0: ép độ sâu mọi bot; 0: giữ cấu hình riêng của bot
    max_think_time_s: float = 1.0  # trần thời gian suy nghĩ mỗi nước (giây); 0 = không giới hạn
    random_opening_plies: int = 2
    claim_draw: bool = True
    seed: int = -1                 # -1 = ngẫu nhiên; >= 0 để tái lập
    @classmethod
    def from_config(cls, config: dict) -> "TournamentConfig": ...   # đọc bảng [tournament], kẹp giá trị hợp lệ
    def validate(self) -> None: ...                                  # raise ValueError nếu không hợp lệ

# backend/tournament/round_robin.py
@dataclass
class Matchup:                    # tổng đối đầu một cặp: games, wins_a/b, draws, score_a/b
    def add(self, winner: chess.Color | None, a_is_white: bool) -> None: ...
@dataclass(frozen=True)
class StandingRow:                # bot_id, rank, points, games, wins, draws, losses, think_time_s, score_pct
@dataclass
class TournamentResult:           # participants, matches_per_pair, completed, standings, matchups, battle, errors
    def to_json(self) -> dict: ...        # version 1
    @classmethod
    def from_json(cls, data: dict) -> "TournamentResult": ...
def compute_standings(participants, matchups, think_times=None) -> tuple[StandingRow, ...]: ...

class RoundRobinRunner:
    def __init__(self, participant_ids, *, matches_per_pair=20, max_plies=150, claim_draw=True,
                 random_opening_plies=2, depth=None, max_think_time_s=None, eval_scale=8.0,
                 bot_configs=None, seed=None, on_progress=None, on_ply=None, on_game_end=None,
                 clock=time.perf_counter, create_bot=None): ...
    pairs: tuple[tuple[str, str], ...]     # mọi cặp KHÔNG thứ tự
    games_total: int                        # len(pairs) * matches_per_pair
    def play(self) -> TournamentResult: ...  # đồng bộ; GUI chạy trong luồng nền
    def request_stop(self) -> None: ...      # dừng sau ván hiện tại, ván dở bị hủy và không tính điểm
    def standings(self) -> tuple[StandingRow, ...]: ...   # bảng sống trong lúc đấu
    # on_ply(ply) được gọi sau mỗi nửa nước -> GUI hiển thị tiến trình ngay trong ván

# backend/tournament/tournament_history.py
class TournamentHistory:
    def __init__(self, directory: Path, max_runs: int = 10): ...   # tự tạo thư mục
    def next_index(self) -> int: ...          # tiếp tục sau khi đã cắt bớt
    def save(self, result: TournamentResult) -> TournamentResult: ...   # đóng dấu battle, ghi <dir>/battle_NNNN.json, cắt FIFO
    def list(self) -> list[TournamentResult]: ...   # mới nhất trước, bỏ qua file hỏng
    def load(self, battle: int) -> TournamentResult: ...
    def clear(self) -> None: ...
```

- **Thể thức:** vòng tròn một lượt mọi cặp (`itertools.combinations`). Mỗi cặp đấu `matches_per_pair` ván, màu chia đều: nửa số ván bot A cầm Trắng, nửa cầm Đen (lẻ thì lệch tối đa 1 ván).
- **Bot mới mỗi ván:** `RoundRobinRunner` gọi `create_bot(bot_id, config)` cho **từng ván** (không tái dùng instance). Mặc định `create_bot` là `ai.registry.create_bot` (nạp lười, đúng ranh giới §3.1).
- **Giới hạn:** mỗi bot giữ độ sâu riêng (`[bots.<id>]` hoặc mặc định của bot); `tournament.depth > 0` mới **ép** mọi bot cùng độ sâu. Ván dừng khi hết `max_plies` hoặc theo luật hòa (`claim_draw`) và xử hòa.
- **Trần thời gian:** `tournament.max_think_time_s` được truyền cho mọi bot. Bot benchmark tự dừng đúng hạn (iterative deepening); bot của thành viên chỉ bị giới hạn nếu code của họ đọc khóa này — hệ thống **không** ngắt ngang tiến trình đang tính (OI-1, OI-2).
- **Điểm:** thắng 1, hòa 0,5, thua 0.
- **Xếp hạng:** điểm giảm dần; **bằng điểm thì tổng thời gian suy nghĩ ít hơn xếp trên**. Hạng theo kiểu thi đấu tiêu chuẩn "1224": bằng cả điểm lẫn thời gian thì **chia sẻ hạng** (1, 2, 3, 4, 5, 5, 7).
- **Lịch sử:** mỗi lần chạy xong lưu thành `battle_NNNN.json` (tiêu đề "Trận Chiến Lần n"), giữ tối đa `max_history` bản gần nhất. Kết quả giải **tách riêng** ở `database/data/tournaments/`, không ghi vào `history/` hay `ranking.json`.
- **Lỗi bot:** một bot hỏng chỉ bị ghi vào `TournamentResult.errors` và bỏ ván đó, không làm sập giải.

## 5. Đặc tả GUI (Pygame)

### 5.1 Cửa sổ
- Canvas logic **960×640**: bàn cờ chiếm 640×640 bên trái, panel 320×640 bên phải.
- Cửa sổ resize được. Canvas được scale **giữ đúng tỷ lệ 3:2**, phần thừa tô viền đen (letterbox). Tọa độ chuột được quy đổi ngược về canvas logic.
- Bot chạy trong **luồng nền** để cửa sổ luôn phản hồi trong lúc bot suy nghĩ.

### 5.2 Màn hình

| Màn hình | Nội dung |
|---|---|
| Menu chính | Người vs Bot · Bot vs Bot · **Xếp hạng AI** · Lịch sử · Xếp hạng · Cài đặt · Thoát |
| Chuẩn bị (Người vs Bot) | Chọn 1 trong 8 bot (4 thành viên + 4 benchmark), chọn màu Trắng/Đen/**Ngẫu nhiên**, đổi phe tự do. Bấm Bắt đầu |
| Chuẩn bị (Bot vs Bot) | Chọn bot Trắng và bot Đen độc lập trong 8 bot (được trùng nhau), nút hoán đổi, chọn 1 ván / Best of 3 |
| Ván đấu | Bàn cờ + panel. **Không Undo, không đổi phe.** Có nút Dừng ván và icon loa |
| Bot vs Bot đang chạy | Như trên, thêm Tạm dừng / Tiếp tục / Tốc độ (độ trễ giữa các nước) |
| Lịch sử | Danh sách 20 ván. Mở ra là màn Xem lại |
| Xem lại | Play/Pause, tốc độ, ◀ ▶ từng nước, về đầu/cuối, xuất PGN |
| Xếp hạng | Bảng W/D/L, điểm, Elo. Nút Reset |
| Xếp hạng AI | Bảng xếp hạng 8 bot benchmark + thành viên; nút **Bắt đầu đấu** (đổi thành **Dừng đấu** khi chạy), **Lịch sử**, **Quay lại** nằm **dưới bảng** |
| Lịch sử giải đấu | Danh sách 10 "Trận Chiến Lần n" + bảng xếp hạng và tỉ số đối đầu từng cặp. Màn riêng |
| Cài đặt | Ngôn ngữ (vi/en), âm thanh bật/tắt, độ trễ xem lại mặc định |

Bot nào raise `BotUnavailableError` thì hiện mờ trong danh sách chọn, kèm lý do.

### 5.3 Bàn cờ
- Đi quân bằng **click chọn quân → click ô đích** (kéo thả là tùy chọn, có thì tốt).
- Highlight ô đang chọn, các nước hợp lệ, nước vừa đi, vua đang bị chiếu.
- **Phong cấp:** hộp chọn Hậu / Xe / Tượng / Mã.
- Lật bàn cờ khi người chơi cầm đen.

### 5.4 Panel bên phải (mỗi mục **thu gọn/mở rộng** bằng nút mũi tên)
1. Tỷ số loạt (Best of 3) và tên hai bên
2. Thanh đánh giá (chênh lệch quân, mục 4.5)
3. Lịch sử nước đi (ký hiệu SAN, cuộn được)
4. Thời gian suy nghĩ: nước vừa rồi và trung bình của mỗi bên
5. Thông tin tìm kiếm của bot (depth/nodes nếu bot có báo)
6. Quân đã bị ăn

### 5.5 Âm thanh
- Có tiếng khi đi quân, ăn quân, chiếu tướng và kết thúc ván.
- **Mặc định TẮT.** Bật/tắt trong Cài đặt **và** bằng icon loa ngay trong ván. Hai chỗ đồng bộ với nhau.
- Chỉ dùng âm thanh có giấy phép CC0 (gợi ý: kenney.nl), ghi nguồn vào `frontend/gui/assets/CREDITS.md`.

### 5.6 Đa ngôn ngữ
- Mọi chuỗi hiển thị lấy qua `t("key")`. File `frontend/gui/locales/vi.toml` và `en.toml` phải **có cùng tập khóa** (CI kiểm tra).
- Mặc định `vi`. Đổi ngôn ngữ trong Cài đặt, có hiệu lực ngay.

### 5.7 Tài nguyên đồ họa
- Bộ quân **rhosgfx** (tác giả RhosGFX, giấy phép **CC0 1.0**), nguồn: `lichess-org/lila/public/piece/rhosgfx`. **Đã có sẵn** trong repo (SVG gốc + PNG), nguồn ghi tại `frontend/gui/assets/CREDITS.md`.
- Chuyển SVG sang **PNG 256×256** một lần, commit PNG vào `frontend/gui/assets/pieces/rhosgfx/`, tên file theo mẫu `wK.png, wQ.png, …, bP.png`. Pygame scale xuống kích thước ô lúc chạy.
- Ô bàn cờ tự vẽ bằng code, màu lấy theo theme (§5.12).

### 5.8 Module GUI thuần logic (test được, KHÔNG import pygame)

Logic tách khỏi phần vẽ để test trên CI không cần màn hình. 4 module dưới đây **cấm import `pygame`**.

```python
# frontend/gui/scaling.py
LOGICAL_SIZE = (960, 640)
@dataclass(frozen=True)
class Viewport:                       # vùng canvas sau khi scale, nằm giữa cửa sổ
    scale: float; offset_x: int; offset_y: int; width: int; height: int
    @classmethod
    def fit(cls, window_w, window_h, logical=LOGICAL_SIZE) -> "Viewport": ...
        # scale = min(ww/lw, wh/lh); width/height = round(l*scale); offset = (w - width)//2
        # kích thước <= 0 -> ValueError
    def to_logical(self, x, y) -> tuple[float, float] | None: ...  # None nếu click vào viền đen
    def to_window(self, x, y) -> tuple[float, float]: ...

# frontend/gui/board_geometry.py      (bàn cờ ở góc trên-trái canvas logic)
BOARD_SIZE = 640; SQUARE_SIZE = 80
def square_at(x, y, flipped=False) -> chess.Square | None: ...   # ngoài bàn -> None
def square_origin(square, flipped=False) -> tuple[int, int]: ...  # góc trên-trái ô
    # flipped=False: a8 ở (0,0), h1 ở (560,560). flipped=True: ngược lại.

# frontend/gui/move_input.py          (click chọn quân -> click ô đích)
@dataclass(frozen=True)
class InputResult:
    kind: str                 # "none" | "select" | "deselect" | "move" | "promotion"
    square: int | None = None
    move: chess.Move | None = None
    promotion_moves: tuple[chess.Move, ...] = ()
class MoveInput:
    selected: int | None
    def click(self, board, square: int | None, player_color) -> InputResult: ...
    def choose_promotion(self, piece_type) -> chess.Move: ...   # không có phong cấp chờ -> ValueError
    def legal_targets(self, board) -> set[int]: ...
    def clear(self) -> None: ...

# frontend/gui/game_info.py           (số liệu cho panel)
def captured_pieces(board) -> dict[chess.Color, list[chess.PieceType]]: ...
    # quân CỦA màu đó đã mất = max(0, số ban đầu - hiện tại); thứ tự Q, R, B, N, P
def think_time_summary(moves) -> dict[chess.Color, tuple[float | None, float | None]]: ...
    # (nước gần nhất, trung bình), bỏ qua nước khai cuộc ngẫu nhiên; ply lẻ = trắng

# frontend/gui/i18n.py
SUPPORTED_LANGUAGES = ("vi", "en")
LOCALES_DIR = Path(__file__).parent / "locales"
class Translator:
    def __init__(self, language="vi", directory=LOCALES_DIR): ...   # ngôn ngữ lạ -> ValueError
    language: str                                                    # property
    def set_language(self, language) -> None: ...                    # ngôn ngữ lạ -> ValueError, giữ nguyên
    def t(self, key: str, **params) -> str: ...
        # khóa dạng "menu.quit"; thiếu khóa -> trả chính key; thiếu tham số -> giữ nguyên "{name}"
```

Quy tắc click (`MoveInput.click`):
- Không phải lượt của `player_color` thì trả `none`.
- Click ngoài bàn (`square=None`): đang chọn thì `deselect`, không thì `none`.
- Chưa chọn quân: click quân mình **có nước đi hợp lệ** thì `select`; click chỗ khác thì `none`.
- Đang chọn: click lại đúng ô đó thì `deselect`. Click quân mình khác có nước đi thì `select` (đổi quân). Click ô đích hợp lệ thì `move`, hoặc `promotion` nếu là nước phong cấp (giữ trạng thái chờ đến khi gọi `choose_promotion`). Click ô không hợp lệ thì `deselect`.

### 5.9 Bộ điều khiển ván (`frontend/gui/controller.py`) — KHÔNG import pygame

Cầu nối giữa màn hình và `backend/tournament/`. Chạy ván trong **luồng nền**; màn hình chỉ đọc **ảnh chụp** (snapshot) mỗi frame.

```python
@dataclass(frozen=True)
class ControllerSnapshot:
    board: chess.Board                 # bản sao thế cờ hiện tại
    moves: tuple[MoveRecord, ...]      # các nước của ván hiện tại
    game_index: int                    # 1-based, ván đang chơi trong loạt
    n_games: int                       # 1 hoặc 3
    finished_games: tuple[GameRecord, ...]
    series_result: SeriesResult | None # có khi cả loạt xong (bot vs bot)
    thinking: bool                     # True khi đang chờ BOT (không phải người) đi
    waiting_for_human: bool            # True khi HumanPlayer.select_move đang chờ nước của người
    finished: bool                     # luồng nền đã kết thúc
    paused: bool

class GameController:
    def __init__(self, white: Player, black: Player, *, mode: str, config: dict,
                 n_games: int = 1, ranking: Ranking | None = None,
                 history: History | None = None, rng: random.Random | None = None): ...
        # mode "human_vs_bot": bắt buộc n_games == 1, KHÔNG khai cuộc ngẫu nhiên
        # mode "bot_vs_bot": dùng SeriesRunner, random_opening_plies từ config["game"]
        # max_plies, claim_draw từ config["game"]; eval_scale từ config["eval_bar"]["scale"]
    def start(self) -> None: ...            # gọi đúng 1 lần; lần 2 -> RuntimeError
    def snapshot(self) -> ControllerSnapshot: ...   # an toàn từ luồng GUI
    def submit_human_move(self, move: chess.Move) -> None: ...  # chuyển cho HumanPlayer
    def human_color(self) -> chess.Color | None: ...           # None nếu bot vs bot
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def join(self, timeout: float | None = None) -> bool: ...  # True nếu luồng đã xong
```

- `HumanPlayer` được bọc bởi một proxy (giữ `bot_id`, `display_name`, `cancel`, `reset`) để biết khi nào nó đang chờ → `waiting_for_human`. GUI chỉ nhận click khi `waiting_for_human` là True (`MatchRunner.play()` xóa hàng đợi lúc bắt đầu ván, nước gửi sớm hơn sẽ mất).
- `pause()` gọi trước `start()` vẫn có hiệu lực (ván bắt đầu ở trạng thái tạm dừng).
- Mỗi ván kết thúc (kể cả bị hủy): `history.save(record)` và `ranking.record_game(record)` (nếu được truyền vào). Gọi trong luồng nền.
- Bot vs Bot: sau mỗi nước (không phải nước khai cuộc) ngủ `config["ui"]["bot_move_delay_ms"]` ms để người xem kịp theo dõi. Đang ngủ mà `stop()` thì thoát ngay.
- Exception bất kỳ trong luồng nền không được làm chết GUI: ván kết thúc dạng ABORTED, `finished=True`.

### 5.10 Ứng dụng Pygame (`frontend/gui/app.py`, `frontend/gui/screens/`, `frontend/gui/widgets/`)

Phạm vi **M3 (MVP)**: Menu → Chuẩn bị Người vs Bot → Ván đấu → Kết quả. Các màn khác (Bot vs Bot, Lịch sử, Xem lại, Xếp hạng, Cài đặt) là M4.

```python
class App:
    def __init__(self, config: dict | None = None, data_dir: Path | None = None): ...
        # config None -> core.config.load_config(); data_dir None -> <repo>/data
        # tạo cửa sổ RESIZABLE kích thước config["window"], canvas logic 960×640
        # Ranking(data_dir/"ranking.json"), History(data_dir/"history", max_games)
    def run(self) -> None: ...                      # vòng lặp chính tới khi đóng cửa sổ
    def render_frame(self) -> None: ...             # xử lý sự kiện đang chờ + vẽ 1 frame
    def goto(self, name: str) -> None: ...          # "menu" | "setup_human" | "game"
    current_screen_name: str                        # property
    def start_human_game(self, bot_id: str, human_color: chess.Color) -> None: ...
        # tạo GameController (HumanPlayer vs registry.create_bot(bot_id, bot_config)), chuyển sang "game"
    controller: GameController | None               # property
    def click_logical(self, x: float, y: float) -> None: ...   # giả lập click chuột trái (tọa độ canvas)
    def click_window(self, x: float, y: float) -> None: ...    # giả lập click (tọa độ cửa sổ, qua Viewport)
    def resize(self, width: int, height: int) -> None: ...
    translator: Translator                          # property
    def quit(self) -> None: ...                     # dừng controller, pygame.quit()
```

- Bố cục: bàn cờ vẽ tại (0,0)–(640,640) của canvas; panel 320 px bên phải.
- Canvas logic vẽ xong được scale (smoothscale) theo `Viewport` lên cửa sổ, viền đen.
- Bàn cờ: ô sáng/tối theo `config["board"]`, quân từ `frontend/gui/assets/pieces/<piece_set>/<wK..bP>.png` scale về 80 px (cache). Highlight: ô đang chọn, ô đích hợp lệ (chấm tròn), nước vừa đi, vua bị chiếu (đỏ). Lật bàn khi người cầm đen.
- Click bàn cờ → `board_geometry.square_at` → `MoveInput.click(snapshot.board, square, human_color)` → `move` thì `controller.submit_human_move`; `promotion` thì mở hộp chọn 4 quân (có nút hủy → `MoveInput.clear()`).
- Panel MVP: tên 2 bên + "đang suy nghĩ…", thanh đánh giá (`MoveRecord.material_eval` của nước cuối), danh sách nước đi SAN (cuộn, nước mới nhất luôn thấy), thời gian suy nghĩ (`game_info.think_time_summary`), quân bị ăn (`game_info.captured_pieces`), nút "Dừng ván" / "Về menu". Mỗi mục có mũi tên thu gọn/mở rộng.
- Ván xong: hiện kết quả (`t("game.result.*")` + `t("termination.*")`) đè lên bàn cờ, nút "Chơi lại" và "Về menu".
- Màn Chuẩn bị Người vs Bot: chọn bot trong `registry.list_bots(include_debug=config["ui"]["show_debug_bots"], include_benchmarks=True)`; bot nào `create_bot` raise `BotUnavailableError` thì hiện mờ kèm lý do (thử tạo một lần khi mở màn). Chọn màu Trắng / Đen / Ngẫu nhiên. Nút Bắt đầu, Quay lại.
- Mọi chuỗi qua `translator.t(...)`. Font: `pygame.font.SysFont` có hỗ trợ tiếng Việt (thử "segoeui", "arial", mặc định).

### 5.11 M4 — các màn còn lại

**Module logic mới (test được):**

```python
# frontend/gui/replay_model.py   — KHÔNG import pygame
class ReplayModel:
    def __init__(self, record: GameRecord): ...      # bắt đầu ở index 0 (thế cờ ban đầu)
    index: int; length: int                           # property; length = len(record.moves)
    board: chess.Board                                # property: bản sao thế cờ sau `index` nửa nước (giữ move_stack)
    last_move: chess.Move | None                      # nước dẫn tới thế cờ hiện tại
    current_move: MoveRecord | None                   # record.moves[index-1] hoặc None
    def first(self) -> None: ...
    def last(self) -> None: ...
    def next(self) -> bool: ...                       # False nếu đã ở cuối
    def prev(self) -> bool: ...                       # False nếu đã ở đầu
    def seek(self, index: int) -> None: ...           # kẹp vào [0, length]
    playing: bool                                     # property
    def play(self, now_ms: float) -> None: ...        # đang ở cuối thì quay về đầu rồi phát
    def pause(self) -> None: ...
    delay_ms: int                                     # property + setter, kẹp [100, 5000]
    def tick(self, now_ms: float) -> bool: ...        # đang phát và đã qua delay_ms từ bước trước -> next(); tới cuối thì tự pause; True nếu vừa tiến

# frontend/gui/sound.py
SOUND_EVENTS = ("move", "capture", "check", "game_end")
def sound_for_move(board_before: chess.Board, move: chess.Move) -> str: ...
    # "check" nếu nước đó chiếu; ngược lại "capture" nếu ăn quân (kể cả bắt tốt qua đường); ngược lại "move"
class SoundManager:
    def __init__(self, sounds_dir: Path, enabled: bool = False): ...
    enabled: bool                                     # property + setter
    def play(self, event: str) -> None: ...           # tắt -> không làm gì; KHÔNG BAO GIỜ raise (mixer lỗi, thiếu file...)
        # khởi tạo pygame.mixer lười ở lần phát đầu tiên; file: <sounds_dir>/<event>.wav

# frontend/gui/leaderboard_view.py — KHÔNG import pygame
@dataclass(frozen=True)
class LeaderboardRow:
    rank: int; player_id: str; name: str; games: int; wins: int; draws: int; losses: int
    points: float; elo: int                           # elo làm tròn
def leaderboard_rows(ranking: Ranking, translator: Translator) -> list[LeaderboardRow]: ...
    # theo thứ tự ranking.table(); rank 1..n; name = translator.t(f"players.{id}")
```

`GameController` thêm `set_bot_move_delay(ms: int) -> None`: đổi độ trễ Bot vs Bot ngay lập tức, kể cả khi đang chờ (đặt 0 thì đi tiếp ngay).

Âm thanh: 4 file `frontend/gui/assets/sounds/{move,capture,check,game_end}.wav` **tự sinh** bằng `another/tools/make_sounds.py` (sóng sin ngắn, thư viện chuẩn `wave` + `math`). Đây là tài nguyên do dự án tự tạo nên không vướng giấy phép.

**App mở rộng (bổ sung §5.10):**

```python
App(config=None, data_dir=None, local_config_path=None)   # local_config_path None -> core.config.LOCAL_CONFIG_PATH
goto(name)            # thêm "setup_bots", "history", "leaderboard", "settings"
def start_bot_game(self, white_id: str, black_id: str, n_games: int) -> None: ...  # -> "game"
def open_replay(self, game_id: str) -> None: ...         # -> "replay"
replay_model: ReplayModel | None                          # property
ranking: Ranking; history: History                        # property; Ranking(known_ids=list_bots(include_benchmarks=True)+["human"])
sound_enabled: bool                                       # property
def set_sound_enabled(self, enabled: bool) -> None: ...   # lưu ui.sound_enabled vào local config
def set_language(self, language: str) -> None: ...        # đổi ngay + lưu ui.language
def set_replay_delay(self, ms: int) -> None: ...          # lưu ui.replay_delay_ms
def reset_ranking(self) -> None: ...                      # nút Reset (sau hộp xác nhận) gọi hàm này
```

**Màn hình:**
- **Chuẩn bị Bot vs Bot:** chọn bot Trắng và bot Đen trong `list_bots(include_debug=show_debug_bots, include_benchmarks=True)` (cho phép trùng nhau; bot không khả dụng thì hiện mờ kèm lý do), nút Đổi bên, chọn 1 ván / Best of 3, Bắt đầu, Quay lại.
- **Ván đấu (Bot vs Bot):** như Người vs Bot, cộng thêm: tỷ số loạt + "Ván i/n", nút Tạm dừng/Tiếp tục, nút Tốc độ (xoay vòng 0 / 150 / 300 / 800 ms qua `set_bot_move_delay`). Loạt xong thì hiện kết quả loạt (`game.result.series_win` / `series_draw`).
- **Lịch sử:** danh sách `history.list()`: "Trắng vs Đen — kết quả — lý do — ngày", có ghi chú loạt (`history.series_note`). Click một dòng → `open_replay`. Nút Xuất PGN ghi `data_dir/exports/<game_id>.pgn` và hiện `history.exported`.
- **Xem lại:** bàn cờ (lật nếu người chơi cầm đen) + nút Về đầu / Lùi / Phát-Dừng / Tiến / Về cuối, tốc độ, nút Xuất PGN, panel nước đi (tô nước hiện tại), thanh đánh giá theo `current_move`. Mỗi frame gọi `tick`.
- **Xếp hạng:** bảng `leaderboard_rows` (Hạng, Người chơi, Số ván, Thắng, Hòa, Thua, Điểm, Elo). Nút Đặt lại → hộp xác nhận → `reset_ranking()`.
- **Cài đặt:** ngôn ngữ (vi/en, đổi ngay), âm thanh bật/tắt, tốc độ xem lại mặc định.
- **Âm thanh:** khi snapshot có nước mới thì phát `sound_for_move`; ván kết thúc thì phát `game_end`. Icon loa trong màn Ván đấu bật/tắt `set_sound_enabled`, đồng bộ với Cài đặt. Mặc định tắt.

### 5.12 Giao diện v2 — nét, theme, chuẩn thiết kế

**Tên ứng dụng:** "Chess" (tiêu đề cửa sổ, `app.title` ở cả vi và en). Bỏ cụm "Giải đấu Cờ vua AI".

**Độ nét (bắt buộc):**
- Windows: gọi `ctypes.windll.shcore.SetProcessDpiAwareness(2)` (dự phòng `user32.SetProcessDPIAware()`) **trước** `pygame.init()`, để Windows không tự kéo giãn cửa sổ.
- Kích thước cửa sổ mặc định = 960×640 × `ui_scale`. `ui_scale` = DPI màn hình / 96, giới hạn sao cho cửa sổ không vượt quá 90% màn hình.
- **Vẽ ở độ phân giải thật:** bỏ cách "vẽ canvas 960×640 rồi smoothscale phóng to".
  - Màn hình và widget vẫn dùng **tọa độ logic 960×640** (cho click và bố cục).
  - Một lớp vẽ chung (`frontend/gui/render.py`) nhân mọi tọa độ, kích thước, độ dày nét và cỡ font với `scale = viewport.scale`. Font được tạo theo cỡ thật (cache theo cỡ). Ảnh quân được scale từ PNG 256 px xuống đúng kích thước ô thật.
  - Surface vẽ có kích thước đúng bằng `(viewport.width, viewport.height)`; blit thẳng, không scale lần hai.
- API cho test: `app.render_scale` (float) và `app.canvas_size` (tuple) bằng `Viewport` hiện tại.

**Theme (`frontend/gui/theme.py`):** 6 theme lấy từ `frontend/resource/theme/*.png`, chọn trong Cài đặt (lưu `ui.theme`, mặc định `dark_winter`). Mỗi theme cung cấp các **vai trò màu**, widget chỉ dùng vai trò, **không bao giờ** dùng mã màu cứng:

| Vai trò | Ý nghĩa |
|---|---|
| `bg` | nền màn hình |
| `surface`, `surface_alt` | nền panel / thẻ, nền xen kẽ (hàng bảng, mục chọn) |
| `border` | viền, đường kẻ |
| `text`, `text_muted`, `text_disabled` | chữ chính / phụ / bị khóa |
| `primary`, `primary_hover`, `on_primary` | nút hành động chính + chữ trên nút |
| `secondary`, `secondary_hover`, `on_secondary` | nút phụ |
| `accent` | lựa chọn đang bật, tab, tiêu điểm |
| `attention` | nước vừa đi, gợi ý: **dùng tiết chế** |
| `danger` | vua bị chiếu, nút Đặt lại / Dừng ván |
| `board_light`, `board_dark`, `board_select`, `board_last`, `board_hint` | bàn cờ |

Bảng màu nguồn (đã đo từ PNG):

| id | Tên hiển thị (vi / en) | Màu gốc |
|---|---|---|
| `dark_winter` **(mặc định)** | Rừng đêm / Night Forest | `#092328 #12544F #2A835F #8BBB92` |
| `dark_cold` | Biển đêm / Deep Sea | `#091540 #1B2CC1 #7692FF #ABD2FA` |
| `cold` | Bầu trời / Sky | `#E3F2FD #90CAF9 #2196F3 #0D47A1` |
| `fall` | Mùa thu / Autumn | `#E2A16F #FFF0DD #D1D3D4 #86B0BD` |
| `summer` | Mùa hè / Summer | `#FFEED6 #A5AF79 #827148 #E8A07C` |
| `winter` | Mùa đông / Winter | `#777C6D #B7B89F #CBCBCB #EEEEEE` |

`dark_winter` (gợi ý, được tinh chỉnh nếu cần để đạt độ tương phản):
- Giao diện: `bg #092328`, `surface #0E3236`, `surface_alt #12423F`, `border #1E5F57`, `text #EAF4EC`, `text_muted #8BBB92`, `primary #2A835F`, `on_primary #FFFFFF`, `secondary #12544F`, `accent #8BBB92`, `attention #E9B949` (ấm, tương phản với xanh), `danger #D9534F`.
- Bàn cờ: `board_light #DDEBDD`, `board_dark #5F9C7C`.

Quy tắc tạo theme:
- Màu vai trò lấy từ 4 màu gốc, hoặc **đậm/nhạt hơn** chúng (pha với đen/trắng).
- Riêng `attention` và `danger` được chọn màu bổ trợ ngoài bảng gốc, để luôn nhận ra được.

**Tâm lý màu & chuẩn thiết kế:**
- **Theme mặc định tối, tông xanh lục/xanh ngọc:**
  - Xanh lục gợi cảm giác bình tĩnh, cân bằng, giúp tập trung khi suy nghĩ chiến thuật.
  - Nền tối giảm chói khi chơi lâu.
- **Màu ấm `attention` chỉ dùng cho thứ cần chú ý:** nước vừa đi, lượt của bạn.
- **Màu đỏ `danger` chỉ dùng cho nguy hiểm hoặc thao tác phá hủy:** chiếu tướng, Đặt lại, Dừng ván.
- **Độ tương phản (WCAG 2.1 AA):**
  - `text` trên `bg`/`surface`, và `on_primary` trên `primary`: ≥ **4.5:1**.
  - `text_muted` trên `bg`: ≥ 3:1.
  - `board_light` với `board_dark`: ≥ 1.6:1, để ô sáng và ô tối phân biệt được.
- **Lưới 8 px** cho khoảng cách.
- **Thang chữ:** 13 / 15 / 18 / 24 / 36 px (ở scale 1). Font hỗ trợ tiếng Việt.
- **Bo góc:** 10 px cho nút và thẻ.
- **Mỗi màn chỉ một nút chính** (`primary`), các nút khác là `secondary`.
- **Trạng thái nút:**
  - thường / hover (sáng hơn, con trỏ hình bàn tay) / nhấn / bị khóa (`text_disabled`, không hover);
  - nút đang được chọn trong nhóm (màu quân, bot, ngôn ngữ, theme) dùng `accent`.
  - App chuyển `MOUSEMOTION` cho màn hình qua `handle_hover(x, y)` (mặc định không làm gì).
- **Menu:**
  - Bỏ hình tròn trang trí.
  - Tiêu đề "Chess" kèm một quân Vua (ảnh rhosgfx) làm logo.
  - Nút xếp theo cột, căn giữa.
- **Cài đặt:** chọn theme bằng các ô mẫu màu (4 màu gốc) kèm tên; đổi là áp dụng ngay.

### 5.13 Theme từ bảng màu Color Hunt (18 theme bổ sung)

Ngoài 6 theme ở §5.12, thêm **18 theme** tạo **tự động** từ file `frontend/resource/theme/Color Hunt Palette <24 hex>.png`. Mã màu đọc từ **tên file**: 4 màu, mỗi màu 6 ký tự hex, không cần mở ảnh.
- id: `ch_<6 hex đầu>` (vd `ch_3368a0`).
- Bỏ qua bảng trùng với theme đã có (`e3f2fd…` trùng `cold`).
- File mới thêm vào thư mục được nhận tự động. Tên hiển thị lấy theo bảng dưới; bảng chưa có tên thì hiển thị "Color Hunt #<hex>".

| id | vi / en | Màu |
|---|---|---|
| `ch_3368a0` | Biển sương / Coastal Mist | `#3368A0 #66A3BF #C8DFDB #F2EFE7` |
| `ch_3e0f8d` | Hoàng hôn tím / Violet Dusk | `#3E0F8D #9564DD #E4DA72 #EEEEEE` |
| `ch_499a13` | Lá xuân / Spring Leaf | `#499A13 #BBDC12 #8ECA3C #276F27` |
| `ch_601d49` | Mận chín / Plum | `#601D49 #BD5579 #EA9D9D #FFEBB8` |
| `ch_a5b68d` | Đồng cỏ / Meadow | `#A5B68D #ECDFCC #FCFAEE #DA8359` |
| `ch_bf9264` | Vườn ô liu / Olive Grove | `#BF9264 #6F826A #BBD8A3 #F0F1C5` |
| `ch_e4e0e1` | Cà phê / Coffee | `#E4E0E1 #D6C0B3 #AB886D #493628` |
| `ch_fbdb93` | Rượu vang / Wine | `#FBDB93 #BE5B50 #8A2D3B #641B2E` |
| `ch_fbefef` | Anh đào / Sakura | `#FBEFEF #FFE2E2 #F5CBCB #C5B3D3` |
| `ch_fdf4d2` | Oải hương / Lavender | `#FDF4D2 #B0CDE6 #A290B7 #946D6D` |
| `ch_ff9d9d` | Kem trái cây / Sorbet | `#FF9D9D #FFC5AA #EEF8CD #BBF1D2` |
| `ch_ffcdb2` | Đào / Peach | `#FFCDB2 #FFB4A2 #E5989B #B5828C` |
| `ch_ffdab3` | Chiều tà / Dusk | `#FFDAB3 #C8AAAA #9F8383 #574964` |
| `ch_ffdcdc` | Sữa dâu / Strawberry Milk | `#FFDCDC #FFF2EB #FFE8CD #FFD6BA` |
| `ch_ffeecc` | Kẹo bông / Cotton Candy | `#FFEECC #FFDDCC #FFCCCC #FEBBCC` |
| `ch_fff2c6` | Mây trời / Daydream | `#FFF2C6 #FFF8DE #AAC4F5 #8CA9FF` |
| `ch_fff2d7` | Cát vàng / Sand | `#FFF2D7 #FFE0B5 #F8C794 #D8AE7E` |
| `ch_fff8e8` | Giấy cổ / Parchment | `#FFF8E8 #F7EED3 #AAB396 #674636` |

**Thuật toán tạo vai trò màu** (`derive_theme(palette) -> Theme`, dùng chung, test được):
1. Sắp 4 màu theo độ sáng tương đối (relative luminance, WCAG).
2. **Theme tối** nếu màu tối nhất có L < 0,08 **và** đủ tương phản 4,5:1 với màu sáng nhất. Ngược lại là **theme sáng**.
   - Tối: `bg` = màu tối nhất (đậm thêm nếu cần), `surface` = `bg` pha sáng 6–10%.
   - Sáng: `bg` = màu sáng nhất, `surface` = `bg` pha trắng/đậm nhẹ.
3. `primary` = màu có **độ bão hòa cao nhất** trong 2 màu giữa. **Chỉnh độ sáng** (giữ sắc độ hue) cho đến khi `on_primary` (trắng hoặc gần đen) đạt ≥ 4,5:1.
   - `secondary` = màu giữa còn lại, chỉnh tương tự.
   - `accent` = màu còn lại hoặc `primary` đậm hơn, sao cho khác rõ `secondary` (≥ 1,5:1).
4. `text` = gần đen hoặc gần trắng, **nhuốm sắc độ của bảng** (ví dụ `#2B2230` thay vì `#000000`). Đạt ≥ 4,5:1 trên cả `bg` và `surface`.
   - `text_muted` ≥ 3:1 trên `bg`.
5. Bàn cờ: `board_light` / `board_dark` lấy từ 2 màu của bảng (pha nhạt/đậm nếu cần), tương phản giữa hai màu ≥ 1,6:1.
   - Quân rhosgfx (kem và nâu cam, viền đen) phải nhìn rõ trên cả hai màu ô: tương phản viền đen với mỗi ô ≥ 3:1.
6. `attention` (ấm) và `danger` (đỏ) chọn trong bộ màu bổ trợ cố định, lấy biến thể đạt ≥ 3:1 trên `bg`.

6 theme ở §5.12 cũng phải qua đúng các ngưỡng tương phản này. Có thể giữ giá trị chọn tay, miễn đạt chuẩn.

**Màn Cài đặt — chọn theme (24 theme):**
- Lưới ô mẫu màu chia 2 nhóm: **Tối** và **Sáng**.
- Cuộn được (con lăn + nút ▲/▼ vẽ bằng hình).
- Ô đang dùng có viền `accent`. Rê chuột lên một ô thì **xem trước** màu ngay trên màn Cài đặt; bấm mới lưu.

### 5.14 Xếp hạng AI — màn + bộ điều khiển (`frontend/gui/tournament_view.py`, `tournament_controller.py`, `screens/tournament.py`, `screens/tournament_history.py`, `widgets/progress_bar.py`)

`tournament_view.py` **không import pygame** (test được trên CI):

```python
def tournament_rows(standings, translator) -> list[TournamentRow]: ...   # dịch tên bot, giữ hạng
def provisional_standings(bot_ids) -> tuple[StandingRow, ...]: ...
    # bảng 0 điểm, hạng 1..n theo thứ tự config — hiện sẵn khi chưa đấu ván nào
def format_points(points) -> str: ...            # "g" — bỏ ".0"
def format_seconds(seconds) -> str: ...          # "<s:.1f>s"
def format_head_to_head(matchup) -> str: ...     # "15 - 5"
def format_matchup(matchup, translator) -> str: ...   # "MCTS  15 - 5  Deep RL"
def progress_fraction(done, total) -> float: ...      # kẹp 0..1
```

```python
# frontend/gui/tournament_controller.py   — chạy nền, KHÔNG import pygame
@dataclass(frozen=True)
class TournamentSnapshot:
    running: bool; finished: bool; stopped: bool
    games_done: int; games_total: int
    current_pair: tuple[str, str] | None
    standings: tuple[StandingRow, ...]
    result: TournamentResult | None
    error: str | None
    progress: float                          # property, games_done / games_total

class TournamentController:
    def __init__(self, config: dict, *, settings: TournamentConfig | None = None,
                 history: TournamentHistory | None = None, create_bot=None): ...
    def start(self) -> None: ...       # chạy RoundRobinRunner trong threading.Thread; gọi 2 lần -> RuntimeError
    def stop(self) -> None: ...        # cờ dừng + runner.request_stop()
    def join(self, timeout=None) -> bool: ...
    def snapshot(self) -> TournamentSnapshot: ...   # an toàn luồng; bảng sống lấy từ runner
```

- **Màn "Xếp hạng AI":** vẽ sẵn bảng điểm (khi chưa có dữ liệu thì dùng `provisional_standings`; nếu đã có trận gần nhất thì dùng bảng đó). Trong lúc chạy hiện dòng trạng thái (`tournament.running`), **thanh tiến trình tổng** (`snapshot.progress`) và cặp đang đấu. **Hai nút nằm dưới bảng**: `tournament.start` (đổi nhãn/th style sang `tournament.stop` + `danger` khi đang chạy) và `tournament.history`.
- **Màn "Lịch sử giải đấu":** danh sách tối đa 10 "Trận Chiến Lần n" (nút chọn), bảng xếp hạng của trận đang xem và danh sách tỉ số đối đầu (`format_matchup`), cuộn bằng ▲/▼.
- **Không chặn UI:** mọi tính toán trong luồng nền; màn hình chỉ đọc `snapshot()` mỗi frame. `App.quit()` và nút **Dừng đấu** đều gọi `TournamentController.stop()`.
- Bảng 8 dòng (đủ 8 bot mặc định); motif mới chỉ dùng vai trò màu của theme (§5.12).

## 6. Cấu hình

- `backend/config/default.toml` được commit. `backend/config/local.toml` nằm trong .gitignore và ghi đè từng khóa (deep merge).
- Màn Cài đặt chỉ ghi vào `local.toml`.
- Code đọc cấu hình qua `backend/core/config.py`. Không module nào tự mở file TOML.
- Đọc dùng `tomllib` (có sẵn); ghi `local.toml` dùng thư viện `tomli-w`.

```python
# backend/core/config.py
DEFAULT_CONFIG_PATH: Path   # <repo>/backend/config/default.toml
LOCAL_CONFIG_PATH: Path     # <repo>/backend/config/local.toml
def load_config(default_path=DEFAULT_CONFIG_PATH, local_path=LOCAL_CONFIG_PATH) -> dict: ...
    # local_path=None hoặc file không tồn tại -> chỉ dùng default
def deep_merge(base: dict, override: dict) -> dict: ...         # trả dict MỚI, không sửa input
def save_local_config(updates: dict, local_path=LOCAL_CONFIG_PATH) -> None: ...  # merge vào local hiện có
def get_bot_config(config: dict, bot_id: str) -> dict: ...       # config["bots"][bot_id] hoặc {}
```

```toml
[window]
width = 960
height = 640
fps = 60

[game]
random_opening_plies = 2   # chỉ Bot vs Bot. Đơn vị: nửa nước (2 = mỗi bên 1 nước)
max_plies = 300            # quá số này thì xử hòa
claim_draw = true          # tự hòa khi lặp 3 lần / luật 50 nước

[ranking]
elo_initial = 1200
elo_k = 32

[history]
max_games = 20

[ui]
language = "vi"            # "vi" | "en"
sound_enabled = false
piece_set = "rhosgfx"
bot_move_delay_ms = 300    # độ trễ tối thiểu giữa các nước Bot vs Bot
replay_delay_ms = 800
show_debug_bots = false

[eval_bar]
scale = 8.0

[bots.deep_rl]
weights_url = ""           # link asset trên GitHub Release
weights_sha256 = ""
device = "cpu"

[tournament]               # bảng xếp hạng AI (§4.9)
bots = [                   # bot tham gia; mặc định 4 thành viên + 4 benchmark
    "alphabeta_regression", "genetic_alphabeta", "mcts", "deep_rl",
    "bench_random", "bench_alphabeta3", "bench_alphabeta_tt", "bench_alphabeta_custom",
]
matches_per_pair = 20      # số ván mỗi cặp; chia đều Trắng/Đen
max_history = 10           # số "Trận Chiến Lần n" giữ lại gần nhất
max_plies = 150            # quá số nửa nước -> hòa
max_think_time_s = 1.0     # trần thời gian suy nghĩ mỗi nước (giây); 0 = không giới hạn
depth = 0                  # > 0: ép mọi bot cùng độ sâu; 0: giữ độ sâu riêng của từng bot
random_opening_plies = 2
claim_draw = true
seed = -1                  # -1 = ngẫu nhiên mỗi lần chạy; >= 0 để tái lập

[bots.bench_random]
seed = -1

[bots.bench_alphabeta3]
depth = 3

[bots.bench_alphabeta_tt]
depth = 3

[bots.bench_alphabeta_custom]
depth = 3
evaluator = "positional"   # tên trong ai.benchmarks.evaluation

# Các bot khác tự thêm [bots.<bot_id>]. Nội dung bảng này được truyền vào BaseBot(config=...)
```

## 7. Option 4 — Deep RL (`backend/ai/deep_rl/`)

- Dùng **PyTorch**. Huấn luyện trên **Kaggle** (CPU/GPU). Khi chạy trong game, suy luận trên **CPU**.
- Board encoding (bàn cờ → tensor) nằm **bên trong** `backend/ai/deep_rl/`, không dùng chung với bot khác.
- `import torch` đặt **lười** bên trong bot để việc import package không làm chậm GUI.
- Trọng số:
  - Checkpoint trong lúc train ở lại Kaggle (output / Kaggle Dataset).
  - Bản tốt nhất được upload lên **GitHub Release**, tag dạng `deeprl-vX.Y`.
  - Lần đầu khởi tạo, bot tự tải file về `backend/ai/deep_rl/weights/` (gitignored) và kiểm tra `sha256`. Nếu không có mạng hoặc sai checksum thì raise `BotUnavailableError`.
- Elo **không phải** reward. Reward huấn luyện do Option 4 tự thiết kế; Elo chỉ dùng để đánh giá.
- Trên CI: nếu thiếu trọng số, test hợp đồng dùng mô hình khởi tạo ngẫu nhiên (`config = {"allow_random_init": True}`) để vẫn kiểm tra được bot đi nước hợp lệ.

## 8. Quy trình Git & quản trị repo

### 8.1 Quy tắc
1. **Không ai push thẳng vào `main`**, kể cả admin.
2. Mỗi việc làm trên một branch riêng: `feat/<module>-<mô-tả>`, `fix/<module>-<mô-tả>`, `documents/<mô-tả>`. Ví dụ: `feat/mcts-uct-selection`.
3. Mở Pull Request vào `main` theo template. CI phải **xanh** và branch phải **cập nhật với `main`** trước khi merge.
4. Duyệt PR:
   - PR của thành viên khác: cần **1 approve của `@august0362`**.
   - PR của `@august0362`: tự merge được khi CI xanh, không cần approve (GitHub không cho tự approve).
5. Chỉ sửa trong thư mục của mình. Muốn sửa `backend/core/`, `backend/ai/base_bot.py`, `backend/ai/registry.py` hoặc `backend/tournament/` thì phải nêu lý do trong PR.
6. Thêm thư viện vào `environments/requirements.txt` thì ghi rõ trong mô tả PR (tên, phiên bản, lý do).
7. Không commit: `database/data/`, `another/local_tools/`, `backend/config/local.toml`, `backend/ai/*/weights/`, file > 5MB (CI chặn).

### 8.2 Cấu hình GitHub (admin `@august0362` làm một lần)

**Ruleset 1 — `main-protect`** (target: `main`, **không ai được bypass**):
- Restrict deletions; Block force pushes
- Require status checks to pass: `ci` · bật *Require branches to be up to date before merging*

**Ruleset 2 — `main-review`** (target: `main`, bypass: **Repository admin**):
- Require a pull request before merging
  - Required approvals: 1
  - Require review from Code Owners
  - Dismiss stale approvals when new commits are pushed

Admin bypass Ruleset 2 nhưng vẫn bị Ruleset 1 chặn: push thẳng một commit chưa chạy CI sẽ bị từ chối. Vì vậy admin vẫn phải đi qua PR, chỉ là không cần người khác approve.

### 8.3 `.github/CODEOWNERS`

```
# Dán username GitHub vào đây. Mỗi dòng: <đường dẫn>  <người được duyệt>
*                          @august0362
/backend/ai/alphabeta_regression/  @cieldontcry    @august0362
/backend/ai/genetic_alphabeta/     @khanhtaduy2k5  @august0362
/backend/ai/mcts/                  @TBD_member3    @august0362
/backend/ai/deep_rl/               @august0362
/.github/                  @august0362
```

## 9. Kiểm thử & CI

- Python: **3.13** (quyết định 2026-10-03, thay cho 3.14: máy nhóm đã có sẵn, mọi thư viện `pygame-ce`, `torch`, `numpy`, `chess` có wheel chính thức; tránh lệch hành vi annotation giữa 3.13 và 3.14). Ghim trong `environments/.python-version`; CI đọc từ file này.
- GUI dùng **`pygame-ce`** (bản cộng đồng của Pygame, vẫn `import pygame`, hỗ trợ Python mới nhanh hơn).
- Công cụ: `pytest`, `pytest-cov`, `ruff` (lint/format), `import-linter` (ranh giới module).

**Các check trong job `ci`** (chạy mỗi lần push branch và mỗi PR):

| Check | Nội dung |
|---|---|
| Lint | `ruff check` + `ruff format --check` (file `.md` không bị format) |
| Ranh giới module | `lint-imports` theo bảng mục 3.1 |
| Unit test | `pytest` |
| Coverage | ≥ **80%** cho `backend/core/` và `backend/tournament/` |
| Hợp đồng bot | Mọi bot trong registry có code: trả nước hợp lệ trên bộ thế cờ chuẩn, không sửa board gốc, 2 instance độc lập |
| i18n | `vi.toml` và `en.toml` cùng tập khóa |
| Config | `default.toml` đọc được và đủ các khóa bắt buộc |
| Repo hygiene | Không có file > 5MB, không có thư mục cấm, không có marker xung đột `<<<<<<<` |
| Cài đặt sạch | `pip install -r environments/requirements.txt` trên môi trường trống |
| GUI smoke | Khởi tạo app ở chế độ headless (`SDL_VIDEODRIVER=dummy`), render 1 frame mỗi màn hình |

Code bên trong từng bot không bị bắt buộc coverage, chỉ bắt buộc qua test hợp đồng.

**Test viết trước, code viết sau (TDD):** Claude viết test đặc tả trước. File test của module chưa tồn tại sẽ tự **skip** (helper `another/tests/_helpers.py::require_module`), nên CI vẫn xanh. Khi module được tạo, test tự kích hoạt và phải xanh mới merge được.

## 10. Open Issues & Deferred

| ID | Vấn đề | Trạng thái |
|---|---|---|
| OI-1 | Giới hạn thời gian / độ sâu mỗi nước | Hoãn với ván thường. Giải xếp hạng AI đã có `tournament.max_think_time_s` (bot benchmark tự dừng đúng hạn) + `max_plies`; bot thành viên không đọc khóa này thì vẫn chỉ đo, không ngắt |
| OI-2 | Dừng cứng bot đang suy nghĩ (chạy bot trong tiến trình riêng) | Hoãn. Hiện "Dừng ván" có hiệu lực sau nước hiện tại |
| OI-3 | Chi tiết giải round-robin cá nhân (`another/local_tools/`) | Đã có bản cơ bản `another/local_tools/arena.py` (2026-10-04). Chỉ trên máy `@august0362`, không push |
| OI-4 | Username GitHub thành viên Option 3 | Chờ. Cập nhật mục 2 và CODEOWNERS |
| OI-5 | Giá trị `max_plies`, số nước khai cuộc ngẫu nhiên tối ưu | Tạm dùng 300 và 2. Chỉnh trong config khi có số liệu |
| OI-6 | Thanh đánh giá dùng đánh giá riêng của bot | Hoãn. Hiện dùng chênh lệch quân |
| OI-7 | Bảng Xếp hạng AI hiển thị tối đa 8 dòng (đủ 8 bot mặc định) | Chấp nhận. Thêm bot thì cần cuộn bảng; `tournament.bots` vẫn là nguồn dữ liệu |
