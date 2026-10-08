# CONTEXT — Chess AI Tournament

> Tài liệu kiến trúc gốc. Mọi thành viên đọc trước khi code. Đổi hợp đồng giao diện (§4) phải qua PR có approve của `@august0362` và ghi `CHANGELOG.md`.
> Phiên bản tài liệu: **0.3.0** — cập nhật 2026-10-03 (nội dung bổ sung đến 2026-10-08).

---

## 1. Mục tiêu

Hệ thống thi đấu cờ vua giữa 4 AI độc lập và người chơi. Luật cờ (nước hợp lệ, chiếu, hòa…) do `python-chess` đảm nhiệm, không ai tự viết luật cờ.

| Option | Thuật toán | Package |
|---|---|---|
| 1 | Alpha-Beta + Linear Regression | `backend/ai/alphabeta_regression/` |
| 2 | Alpha-Beta + Genetic Algorithm | `backend/ai/genetic_alphabeta/` |
| 3 | Pure MCTS | `backend/ai/mcts/` |
| 4 | Deep Reinforcement Learning (DQN, PyTorch) | `backend/ai/deep_rl/` |

## 2. Thành viên & vai trò

| GitHub | Vai trò |
|---|---|
| `@august0362` | Product Owner, admin repo, Lead Integrator, GUI/UX, **Option 4** |
| `@cieldontcry` | Option 1 |
| `@khanhtaduy2k5` | Option 2 |
| `@quanganh167` | Option 3 |
| Claude | Kiến trúc, đặc tả, test case, tài liệu, prompt cho Codex |
| Codex | Sinh code theo prompt của Claude |

Thành viên tự quyết thuật toán **bên trong** package của mình, chỉ bắt buộc theo hợp đồng §4 và quy tắc §8.

## 3. Kiến trúc

### 3.1 Quy tắc phụ thuộc

```
                 ┌──────────────┐
                 │ backend/core/ │  chỉ phụ thuộc python-chess
                 └──────▲───────┘
        ┌───────────────┼────────────────────┐
   ┌────┴──────┐   ┌────┴───────────────┐   ┌┴──────────────┐
   │ backend/ai/│◄──│ backend/tournament/ │◄──│ frontend/gui/ │
   └───────────┘   └────────────────────┘   └───────────────┘
```

| Module | Được import | CẤM import |
|---|---|---|
| `backend/core/` | `chess`, thư viện chuẩn | `ai`, `tournament`, `gui` |
| `backend/ai/base_bot.py`, `registry.py` | `core`, `chess` | package bot cụ thể (chỉ nạp động qua chuỗi) |
| `backend/ai/<bot>/` | `ai.base_bot`, `core`, `chess`, thư viện ngoài | **bot khác**, `tournament`, `gui` |
| `backend/tournament/` | `core`, `ai.base_bot`, `ai.registry` | `gui`, import trực tiếp package bot |
| `frontend/gui/` | `core`, `tournament`, `ai.registry` | import trực tiếp package bot |

CI kiểm tra tự động (§9); vi phạm thì CI đỏ, không merge được.

### 3.2 Cây thư mục

```text
BTL_AI/
├── backend/
│   ├── ai/            # bot, lớp nền, registry; benchmarks/ (B1–B4), bench5/ … bench8/ (mỗi thế hệ một package)
│   ├── config/        # default.toml (commit) + local.toml (máy cá nhân)
│   ├── core/          # trạng thái ván, kiểu dữ liệu
│   └── tournament/    # trận đấu, lịch sử, xếp hạng
├── frontend/gui/      # ứng dụng Pygame: màn hình, widget, locales, assets
├── frontend/resource/ # bảng màu, tài nguyên giao diện
├── database/data/     # lịch sử, xếp hạng tạo khi chơi (.gitignore)
├── documents/         # CONTEXT, hướng dẫn, kế hoạch, prompt
├── environments/      # .python-version, requirements.txt, requirements-dev.txt
├── another/           # local_tools/ (.gitignore), scripts/ (Windows), tests/, tools/
├── .github/           # workflow, CODEOWNERS, mẫu PR
├── main.py  run.bat  pyproject.toml  README.md
```

Package Python vẫn tên `ai`, `core`, `tournament`, `gui`; `run.bat`, pytest và CI thêm `backend/`, `frontend/`, `another/` vào đường dẫn import.

## 4. Hợp đồng giao diện

### 4.1 `backend/ai/base_bot.py` — BaseBot

```python
class BaseBot(ABC):
    bot_id: str = ""          # khớp khóa registry, vd "mcts"
    display_name: str = ""    # tên trên GUI; [bots.<id>] display_name trong config ghi đè
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.last_search_info: dict = {}
    @abstractmethod
    def select_move(self, board: chess.Board) -> chess.Move: ...   # nước HỢP LỆ cho board.turn; board là bản sao
    def reset(self) -> None: ...                                   # trước mỗi ván; mặc định xóa last_search_info
```

**Quy tắc bắt buộc:**
1. `select_move` nhận **bản sao** bàn cờ; được push/pop nhưng không giữ tham chiếu sang ván sau.
2. Luôn trả nước trong `board.legal_moves` (harness chỉ gọi khi ván chưa kết thúc).
3. Không biến toàn cục dùng chung: hai instance cùng loại chạy độc lập (bot tự đấu chính nó).
4. Import package bot phải nhẹ; tải trọng số trong `__init__` hoặc lười ở nước đầu.
5. Không khởi tạo được (thiếu trọng số, không mạng…) → `__init__` raise `BotUnavailableError(message)`; GUI khóa bot kèm thông báo, không crash.
6. `last_search_info` (tùy chọn, cập nhật sau mỗi `select_move`): `depth: int`, `nodes: int`, `eval: float` (−1..1, góc nhìn bên vừa đi). Thời gian do harness đo.
7. Ván thường không giới hạn thời gian (OI-1); tham số thời gian truyền qua `config` (`max_think_time_s`) nên chữ ký không đổi.
8. Test hợp đồng (`another/tests/ai/test_bot_contract.py`) dùng `config = {"fast_mode": True, "allow_random_init": True, "seed": 0}`: `fast_mode` = tìm kiếm nhỏ cho CI; `allow_random_init` = được khởi tạo trọng số ngẫu nhiên khi thiếu file; `seed` = dùng `random.Random(seed)` riêng, không dùng `random` toàn cục. Bot bỏ qua khóa không dùng.

### 4.2 `backend/ai/registry.py`

```python
BOT_REGISTRY = {"alphabeta_regression": "ai.alphabeta_regression.bot:AlphaBetaRegressionBot",
                "genetic_alphabeta": "ai.genetic_alphabeta.bot:GeneticAlphaBetaBot",
                "mcts": "ai.mcts.bot:MctsBot", "deep_rl": "ai.deep_rl.bot:DeepRLBot"}
DEBUG_BOTS = {"random": "ai.random_bot.bot:RandomBot"}
BENCHMARK_BOTS = {   # opt-in, xem §4.9
    "bench_random", "bench_alphabeta_material", "bench_alphabeta3", "bench_alphabeta_tt",
    "bench_alphabeta_custom",                       # ai.benchmarks.bot
    "bench5_gpt|gemini|deepseek|grok|hybrid",       # ai.bench5.bot
    "bench6_gpt|gemini|grok|deepseek",              # ai.bench6.bot
    "bench7",                                       # ai.bench7.bot (Dragon)
    "bench8_luna",                                  # ai.bench8.bot (Luna)
}
BENCHMARK_LEVELS: dict[str, float]   # thế hệ: 1, 1.5, 2, 3, 4, 5, 6, 7, 8
def benchmark_level(config) -> float | None: ...          # đọc [benchmarks] max_level
def benchmark_allowed(bot_id, max_level) -> bool: ...
def list_bots(include_debug=False, include_baseline=False, include_benchmarks=False,
              max_benchmark_level=None) -> list[str]: ...   # benchmark chỉ trả khi thế hệ <= max_level
def create_bot(bot_id: str, config: dict | None = None) -> BaseBot: ...   # importlib; lỗi import -> BotUnavailableError
```

Lớp chính mỗi bot ở `backend/ai/<bot>/bot.py`.

**Bot benchmark (2026-10-07, cập nhật 2026-10-08):** `BENCHMARK_BOTS` chỉ trả khi `list_bots(include_benchmarks=True)`; mặc định `list_bots()` không đổi. GUI gọi `list_bots(include_debug=show_debug_bots, include_benchmarks=True, max_benchmark_level=...)` nên Người vs Bot, Bot vs Bot, Xếp hạng Elo và Xếp hạng AI có 4 bot thành viên + mọi benchmark có thế hệ ≤ `max_level` (mặc định 7 → 19 bot; 8 → 20 bot). `baseline` (`BASELINE_BOTS`) **không** hiện trên GUI. `create_bot` nhận mọi khóa benchmark.

**Baseline ngẫu nhiên (2026-10-04):** bot chưa có code thật thì đi nước hợp lệ ngẫu nhiên, để GUI và giải luôn đủ 4 bot.
- Lớp chung `backend/ai/baseline.py::RandomBaselineBot(BaseBot)`, `is_baseline = True`, `random.Random(config.get("seed"))` riêng. Đặt ở `backend/ai/` nên các bot được import.
- Khung `bot.py` của 3 bot thành viên kế thừa nó; viết bot thật thì thay toàn bộ lớp, `is_baseline` về `False`.
- `DeepRLBot`: nếu `user.policy.load_policy` còn raise `NotImplementedError` thì chạy baseline (không raise `BotUnavailableError`); lỗi thật (thiếu trọng số, sai sha256…) vẫn raise.
- GUI thêm hậu tố `t("players.baseline_suffix")` ("(baseline)") ở màn chuẩn bị, panel, lịch sử, xếp hạng.
- Khi bot thật thay baseline, nên **Đặt lại** bảng xếp hạng (Elo cũ là của bản ngẫu nhiên).

### 4.3 `backend/core/` — GameState & kiểu dữ liệu

```python
# backend/core/types.py
class Termination(StrEnum):   # giá trị ghi JSON — KHÔNG đổi
    CHECKMATE = "checkmate"; STALEMATE = "stalemate"; INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"; FIFTY_MOVES = "fifty_moves"
    MAX_PLIES = "max_plies"; ABORTED = "aborted"
class IllegalMoveError(ValueError): ...
class GameOverError(RuntimeError): ...
@dataclass(frozen=True)
class GameResult:
    winner: chess.Color | None   # None = hòa (hoặc ABORTED)
    termination: Termination
    def score_for(self, color) -> float: ...   # 1 / 0.5 / 0; ABORTED -> ValueError
@dataclass(frozen=True)
class MoveRecord:
    ply: int; uci: str; san: str; think_time_s: float
    search_info: dict          # bản sao last_search_info
    material_eval: float       # giá trị thanh đánh giá sau nước đi
    is_random_opening: bool

# backend/core/game_state.py
class GameState:
    def __init__(self, fen=None, max_plies=300, claim_draw=True): ...   # max_plies <= 0 -> ValueError
    board: chess.Board     # property, luôn BẢN SAO (giữ move_stack)
    turn; fen; starting_fen
    ply_count: int         # số nửa nước đã push QUA GameState này
    def legal_moves(self) -> list[chess.Move]: ...
    def push(self, move) -> str: ...        # trả SAN; IllegalMoveError / GameOverError
    def is_over(self) -> bool: ...
    def result(self) -> GameResult | None: ...
    def to_pgn(self, headers: dict[str, str]) -> str: ...   # Result: 1-0 / 0-1 / 1/2-1/2 / *
```

`GameState` **không có undo** (yêu cầu sản phẩm).

### 4.4 Luật kết thúc ván

| Tình huống | Kết quả | Giải thích |
|---|---|---|
| **Chiếu hết** | Bên chiếu thắng | Vua bị tấn công, không còn cách thoát |
| **Hết nước** (stalemate) | Hòa | Đến lượt, không có nước hợp lệ, vua không bị chiếu |
| **Không đủ quân** | Hòa | Không bên nào đủ quân chiếu hết (vd Vua với Vua) |
| **Lặp 3 lần** | Hòa | Cùng thế cờ xuất hiện lần thứ 3 |
| **Luật 50 nước** | Hòa | 100 nửa nước liên tiếp không ăn quân, không đi Tốt |
| **Giới hạn an toàn** | Hòa | Quá `max_plies` (ván thường 300, giải Xếp hạng AI 150) |
| **Dừng ván** | Không tính | Người dùng bấm "Dừng ván", không ghi xếp hạng |

**Nửa nước (ply)** = một lần đi của một bên (1 nước = 2 nửa nước). Lặp 3 lần và luật 50 nước **tự áp dụng** khi `claim_draw = true`. Mọi giới hạn chỉnh trong `backend/config/default.toml`.

Cài đặt — kiểm tra **đúng thứ tự**, dừng ở điều kiện đầu tiên đúng:
1. Chiếu hết / hết nước (`board.outcome(claim_draw=False)`) — chiếu hết thắng mọi luật hòa.
2. `board.is_insufficient_material()`.
3. Nếu `claim_draw`: `board.is_repetition(3)` → THREEFOLD_REPETITION.
4. Nếu `claim_draw`: `board.halfmove_clock >= 100` → FIFTY_MOVES.
5. Luật tự động của python-chess (lặp 5 lần → THREEFOLD_REPETITION, 75 nước → FIFTY_MOVES).
6. `ply_count >= max_plies` → MAX_PLIES.

⚠️ **Không** dùng `board.outcome(claim_draw=True)`: nó coi là hòa cả khi nước tiếp theo **có thể** lặp 3 lần → kết thúc sớm 1 nửa nước.

### 4.5 `backend/core/material.py` — Thanh đánh giá

Chênh lệch quân, trung lập với mọi bot: Tốt 1, Mã 3, Tượng 3, Xe 5, Hậu 9, Vua 0. `material_diff(board) -> int` = trắng − đen; `eval_bar_value(board, scale=8) -> float` = `tanh(material_diff / scale)` ∈ [−1, +1].

### 4.6 `backend/tournament/` — Điều phối ván đấu

`backend/tournament/` không biết GUI, file xếp hạng hay lịch sử khi đang chơi; GUI (controller) nhận `GameRecord` qua callback rồi tự gọi `Ranking`/`History`.

```python
# players.py
HUMAN_ID = "human"
class MatchAborted(Exception): ...        # HumanPlayer bị hủy khi đang chờ
class Player(Protocol):                   # BaseBot, HumanPlayer, ProcessPlayer
    bot_id: str; display_name: str
    def select_move(self, board) -> chess.Move: ...
    def reset(self) -> None: ...
class HumanPlayer:
    def __init__(self, display_name="Human"): ...
    def submit_move(self, move) -> None: ...   # luồng GUI
    def select_move(self, board) -> chess.Move: ...   # chặn chờ; BỎ QUA nước không hợp lệ
    def cancel(self) -> None: ...               # select_move đang chờ -> MatchAborted
    def reset(self) -> None: ...                # xóa hàng đợi + trạng thái hủy

# records.py
@dataclass
class GameRecord:
    game_id: str            # uuid4().hex
    started_at: str         # ISO-8601 UTC, micro giây
    mode: str               # "human_vs_bot" | "bot_vs_bot"
    white_id: str; black_id: str; white_name: str; black_name: str
    opening_moves: list[str]          # UCI, khai cuộc ngẫu nhiên
    moves: list[MoveRecord]           # MỌI nước, kể cả khai cuộc (is_random_opening=True)
    result: GameResult
    pgn: str = ""
    series_id: str | None = None; series_game_index: int | None = None   # 1-based
    error: str | None = None          # lý do nếu bị hủy do bot lỗi
    def to_json(self) -> dict: ...    # winner: "white"/"black"/null
    @classmethod
    def from_json(cls, d) -> "GameRecord": ...   # from_json(r.to_json()) == r

# match_runner.py
def generate_random_opening(plies, rng) -> list[str]: ...   # từ thế chuẩn; không được là ván đã xong (thử lại ≤ 100 lần)
class MatchRunner:
    def __init__(self, white, black, *, mode="bot_vs_bot", random_opening_plies=0, opening_moves=None,
                 max_plies=300, claim_draw=True, eval_scale=8.0, rng=None, on_move=None,
                 series_id=None, series_game_index=None, clock=time.perf_counter): ...
    def play(self) -> GameRecord: ...    # đồng bộ; GUI gọi trong luồng nền
    def request_stop(self) -> None: ...  # an toàn từ luồng khác
    def pause(self) -> None: ...         # chặn TRƯỚC nước kế tiếp
    def resume(self) -> None: ...
```

`play()`:
1. Gọi `reset()` cả hai người chơi.
2. Khai cuộc: `opening_moves` nếu có, không thì `generate_random_opening` khi `random_opening_plies > 0`. Nước khai cuộc: `think_time_s = 0`, `search_info = {}`, `is_random_opening = True`, vẫn gọi `on_move`; không hỏi người chơi.
3. Lặp tới `GameState.is_over()`. Trước mỗi lượt: chờ nếu đang pause; hủy nếu đã `request_stop`.
4. `select_move(state.board)` (bản sao), đo bằng `clock` — người chơi có `measured_think_time_s` (bot chạy tiến trình riêng, §4.9) thì lấy số đó. Đã `request_stop` sau khi nhận nước thì hủy, **không** push.
5. `MoveRecord`: `ply = state.ply_count` sau push, `search_info` = bản sao `last_search_info`, `material_eval = eval_bar_value(board, eval_scale)`; rồi `on_move(record, state)`.
6. **ABORTED** (`winner=None`) khi: `request_stop`, `HumanPlayer` raise `MatchAborted`, bot raise exception bất kỳ, hoặc trả nước không hợp lệ (hai trường hợp cuối điền `error` có `bot_id`). **Exception của bot không bao giờ lan ra ngoài.**
7. `request_stop()` gọi cả `cancel()` của người chơi có hàm đó.
8. `pgn` điền khi kết thúc, headers `White`, `Black` (display name), `Date`.

```python
# series.py
def series_colors(n_games, rng) -> list[bool]: ...   # True = A Trắng. 1 ván: [True]; 3 ván: [True, False, rng.choice]
@dataclass
class SeriesResult:
    series_id: str; a_id: str; b_id: str; games: list[GameRecord]
    score_a: float; score_b: float
    winner: str | None   # "a" | "b" | None (hòa trận hoặc hủy)
    aborted: bool
class SeriesRunner:
    def __init__(self, player_a, player_b, n_games, *, random_opening_plies=0, max_plies=300,   # n_games ∈ {1, 3}
                 claim_draw=True, eval_scale=8.0, rng=None, on_move=None, on_game_end=None): ...
    def play(self) -> SeriesResult: ...
    def request_stop(self) -> None: ...; def pause(self) -> None: ...; def resume(self) -> None: ...
```

Series luôn `mode="bot_vs_bot"` (Người vs Bot dùng thẳng `MatchRunner`, 1 ván). Khai cuộc sinh **một lần** cho cả loạt. Best of 3 **đấu đủ 3 ván**; ván bị hủy thì loạt dừng (`aborted=True`, `winner=None`). Thắng 1, hòa 0,5, thua 0; bằng điểm → `winner=None`.

### 4.7 Xếp hạng Elo (`backend/tournament/ranking.py`)

```python
@dataclass
class PlayerStats:
    wins: int = 0; draws: int = 0; losses: int = 0; elo: float = 1200.0
    games: int        # property
    points: float     # property = wins + 0.5 * draws
def expected_score(r_a, r_b) -> float: ...   # 1 / (1 + 10 ** ((r_b - r_a) / 400))
class Ranking:
    def __init__(self, path, *, elo_initial=1200, elo_k=32, known_ids=(), debug_ids=("random",)): ...
        # path=None: chỉ trong bộ nhớ. File hỏng -> đổi tên <tên>.corrupt, bắt đầu mới
    def stats(self, player_id) -> PlayerStats: ...      # id lạ -> mặc định
    def table(self) -> list[tuple[str, PlayerStats]]: ...   # mọi known_ids; Elo giảm dần, rồi points, rồi id
    def record_game(self, record) -> bool: ...          # True nếu được tính; tự lưu file
    def reset(self) -> None: ...                         # tự lưu file
```

- Hồ sơ: mọi bot hiện trên GUI (§4.2) + một hồ sơ chung `human`, Elo bắt đầu từ `ranking.elo_initial` (1200), chỉ đổi qua ván Người vs Bot / Bot vs Bot. Giải Xếp hạng AI **không** ghi Elo.
- Mỗi ván cập nhật W/D/L và Elo hai bên, dùng rating **trước** ván: `R_mới = R + K·(S − E)`.
- `record_game` trả `False`, không đổi gì khi: ABORTED, `white_id == black_id`, hoặc một bên thuộc `debug_ids`.
- JSON `{"version": 1, "players": {id: {wins, draws, losses, elo}}}`; ghi file tạm cùng thư mục rồi `os.replace`.
- Giải round-robin cá nhân (`another/local_tools/`) dùng `database/data/local_arena/`, không đụng `ranking.json`.

### 4.8 Lịch sử ván (`backend/tournament/history.py`)

```python
class History:
    def __init__(self, directory, max_games=20): ...   # tự tạo thư mục
    def save(self, record) -> Path: ...    # <dir>/<game_id>.json, rồi xóa ván cũ vượt max
    def list(self) -> list[GameRecord]: ...   # mới nhất trước (started_at, rồi game_id); bỏ file hỏng
    def load(self, game_id) -> GameRecord: ...
    def export_pgn(self, game_id, dest) -> Path: ...
```

Mỗi ván đơn lẻ là một mục; ván trong Best of 3 có `series_id`/`series_game_index` ("Ván 2/3"). Ván bị hủy **vẫn lưu** nhưng không tính xếp hạng.

### 4.9 Xếp hạng AI — bot benchmark & giải vòng tròn

**Bot benchmark** là thang phân loại sức mạnh, tách khỏi Elo (§4.7). B1–B4 ở `backend/ai/benchmarks/`; **mỗi thế hệ sau là một package riêng** (`bench5/` … `bench8/`), tự chứa engine, eval, bảng số, profile, lớp bot, không import package benchmark khác (import-linter kiểm), chỉ nối qua `ai.registry`. **Bật/tắt theo thế hệ:** `[benchmarks] max_level` (4 = B1–B4, 5 = +B5, 6 = +B6, 7 = +B7, 8 = +B8; xóa khóa = hiện tất cả; bot vượt mức bị loại cả khi có trong `tournament.bots`).

| id | Tên | Cách chơi |
|---|---|---|
| `bench_random` | B1 · Random | Chọn đều ngẫu nhiên nước hợp lệ (`seed`) |
| `bench_alphabeta_material` | B1.5 · Alpha-Beta thuần | Negamax alpha-beta độ sâu 3, eval `material`, tất định |
| `bench_alphabeta3` | B2 · Alpha-Beta 3 | Negamax alpha-beta độ sâu cố định (3), eval `pst`, hòa điểm thì chọn ngẫu nhiên theo `seed` |
| `bench_alphabeta_tt` | B3 · Alpha-Beta TT | B2 + bảng chuyển vị Zobrist, sắp nước (MVV-LVA, phong cấp, killer), quiescence (chỉ ăn quân, ≤ 8 nửa nước) |
| `bench_alphabeta_custom` | B4 · Alpha-Beta Custom | B3 + check extension (≤ 2), mobility (mã/tượng 4, xe 2, hậu 1 mỗi ô), null-move (R=2) + LMR (nước yên tĩnh thứ 4 trở đi −1 ply) khi độ sâu còn ≥ 2; eval `advanced` = `pst` + tốt (chồng −15, cô lập −15, thông +5..+100) + an toàn vua trước tàn cuộc (thiếu tốt che −15/cột, cột mở quanh vua −20) + cặp tượng +30 + xe cột mở +20 / nửa mở +10 (bitboard, cache theo tốt và vua; đổi qua `evaluator`) |
| `bench5_gpt` / `_gemini` / `_deepseek` / `_grok` | B5 · … | Engine PVS dùng hết thời gian (§4.9.1), profile chỉ lấy từ `chatgpt.txt` / `gemini.txt` / `deepseek.txt` / `grok.txt` |
| `bench5_hybrid` | B5 · Tổng hợp | Profile tổng hợp 4 nguồn, chỉnh bằng trận |
| `bench6_gpt` / `_gemini` / `_grok` / `_deepseek` | B6 · … | Engine PVS chọn lọc (§4.9.2), mỗi bản chỉ theo một file (bản B6) |
| `bench7` | B7 · Dragon | Tổng hợp 4 thiết kế B6, chọn bằng ablation |
| `bench8_luna` | B8 · Luna | Lõi Dragon + SEE theo ngưỡng; các phương án khác có công tắc, mặc định tắt (§4.9.3) |

**B1–B4** (`backend/ai/benchmarks/`):

```python
# evaluation.py  (điểm theo bên đang đi, cho negamax)
def material_evaluator(board) -> float: ...     # bọc ai.baseline.evaluate
def positional_evaluator(board) -> float: ...   # + kiểm soát trung tâm, phát triển quân
def pst_evaluator(board) -> float: ...          # vật chất + bảng ô quân, chiếu hết theo ply
def register_evaluator(name, evaluator) -> None: ...
def build_evaluator(name="positional") -> Callable: ...   # tên lạ -> ValueError
# search.py
class SearchResult(NamedTuple): move; score: float; nodes: int; depth: int = 0
class SearchTimeout(Exception): ...             # nội bộ: hết thời gian giữa chừng
class TranspositionTable:                       # khóa Zobrist, EXACT/LOWERBOUND/UPPERBOUND
    def clear(self); def get(self, key); def store(self, key, depth, score, flag, move)
def order_moves(board, *, tt_move=None, killer=None) -> list[chess.Move]: ...
def alpha_beta(board, depth, evaluator) -> SearchResult: ...
def alpha_beta_tt(board, depth, evaluator, *, tt=None, killers=None) -> SearchResult: ...   # CÙNG điểm với alpha_beta
def alpha_beta_iterative(board, max_depth, evaluator, *, tt=None, killers=None, time_limit_s=None, rng=None): ...
    # sâu dần; hết time_limit_s thì trả nước của tầng sâu nhất đã xong (None/<=0 = đủ max_depth)
```

- **B2 — độ khó (2026-10-07):** người chơi cẩn thận thắng được nhưng không thắng nhanh bằng mẹo. Eval `pst`: `PIECE_VALUES` + bảng Michniewski cho tốt, mã, tượng, xe, hậu; vua bảng trung cuộc, đổi bảng tàn cuộc khi cả hai hết hậu hoặc mỗi bên ≤ 1 quân nhẹ ngoài tốt (bảng theo góc Trắng, a8 đầu mảng; Đen lật bằng `chess.square_mirror`). Chiếu hết `-(MATE_SCORE - board.ply())` → chiếu nhanh, chống lâu; hòa (`is_stalemate`, `is_insufficient_material`, `is_repetition(3)`, `can_claim_fifty_moves`) = 0. **Không** quiescence (cố ý, còn lỗi đường chân trời). Nước bằng điểm (≤ 1e-9) chọn ngẫu nhiên bằng `random.Random(config.get("seed"))` (chỉ B2 truyền `rng`). `[bots.bench_alphabeta3] evaluator` đổi được eval.
- B3/B4 giữ TT và killer **trong một ván**; `reset()` xóa cả hai. Ba bot tìm kiếm dùng `alpha_beta_iterative` với `max_think_time_s` nên không vượt trần thời gian.

#### 4.9.1 Benchmark 5 (2026-10-08)

Mục tiêu: thắng rõ B4 cùng trần thời gian, chỉ bằng thuật toán (không train, không engine/tablebase/sách ngoài). 4 bản theo 4 đề xuất LLM (`chatgpt.txt`, `gemini.txt`, `deepseek.txt`, `grok.txt` ở gốc repo), bản thứ 5 tổng hợp.

- **Một engine, năm profile** (`ai.bench5`): `search.py` (`Engine5`, `SearchConfig`) — iterative deepening theo thời gian (`soft_fraction`/`hard_fraction` của `max_think_time_s`), PVS fail-soft, aspiration, TT khóa `board._transposition_key()` (thay theo độ sâu, đầy thì bỏ 1/4 cũ nhất), TT move → ăn quân MVV-LVA → phong cấp → 2 killer → countermove → history; null-move, LMR, RFP, futility, LMP, SEE pruning, check extension; quiescence **luôn xét mọi nước thoát chiếu** (không stand-pat), delta pruning; hòa do lặp 2 (hoặc 3) lần trong cây, contempt.
- **Eval** `evaluation.py` (`Evaluator5`, `EvalConfig`): PST Michniewski nội suy MG/EG theo phase (N/B 1, R 2, Q 4, tối đa 24) + thành phần bật theo profile (tốt chồng/cô lập/thông/đảo tốt, cặp tượng, xe cột mở/hàng 7, mã tiền đồn, an toàn vua, mobility B4, tempo, mop-up). Cache theo instance, đối xứng màu.
- **Profile** `profiles.py`: mỗi tham số ghi nguồn; nguồn không nêu số thì ghi giá trị đã chọn.
- **Cấu hình:** `max_think_time_s` mặc định 1,0 s (kể cả GUI); `<= 0` = không giới hạn, dừng ở độ sâu 5; `depth` là trần độ sâu; `fast_mode` = trần 2.

#### 4.9.2 Benchmark 6 và Benchmark 7 "Dragon" (2026-10-08)

Mục tiêu: mỗi B6 mạnh hơn B5 cùng nguồn; B7 mạnh hơn mọi B6. B6 theo bản cập nhật của 4 file; B7 tổng hợp cả bốn.

- **Engine** `ai.bench6.search` (`Engine6`, `SearchConfig6`; B7 có bản sao riêng `ai.bench7.search`): PST + vật chất **cộng dồn theo nước** (MG/EG gói một số nguyên); **sinh nước theo giai đoạn** (TT → ăn quân tốt/phong hậu → killer/countermove → yên tĩnh theo history → ăn quân lỗ); TT list có bucket 1/2/4 ngăn + generation; cache eval; capture history, continuation history 1–3 ply, history gravity; tín hiệu *improving*; LMR log có điều chỉnh (PV, killer, history, improving, cut node); RFP, razoring, futility, LMP, history pruning, SEE pruning, ProbCut, multi-cut; singular extension, IID/IIR, check/recapture/pawn-7th extension; correction history theo cấu trúc tốt; quiescence xét mọi nước thoát chiếu, có thể thêm nước chiếu yên tĩnh; sách khai cuộc viết tay (`BOOK_LINES`, chọn bằng `seed`); 5 chính sách thời gian (`fixed`, `stability`, `panic_easy`, `complexity`, `factors`).
- **Eval** `ai.bench6.evaluation` / `ai.bench7.evaluation` (`Evaluator6`, `EvalConfig6`): Michniewski hoặc **PeSTO**; tốt mở rộng (backward, candidate, phalanx, supported, islands); tốt thông động (bảo vệ, liên kết, bị chặn, khoảng cách vua, xe sau tốt, luật hình vuông); outpost, xe nối; mobility, **king danger** (N/B 2, R 3, Q 5, phi tuyến), đe dọa (tốt đuổi quân, quân nhẹ đuổi quân nặng, quân treo) bằng bảng tấn công bitboard; phát triển quân; mop-up có góc KBNK; hệ số hòa (tượng khác màu, ưu thế nhỏ không tốt, KNN–K, tốt cột biên); co điểm theo luật 50 nước; **lazy eval**. Đối xứng màu.
- Profile: `ai.bench6.profiles` (4 bản) và `ai.bench7.profile` ghi nguồn từng tham số; file không nói thì dùng thiết lập mạnh nhất của lõi B6 (đã kiểm bằng trận). GPT/Grok/DeepSeek đòi "PST tapered" nên dùng PeSTO (hơn Michniewski ~+180 Elo).
- **B7** chọn bằng ablation (200 ván/biến thể ở 0,4 s): PeSTO + HCE (bỏ đi kém ~−60 Elo), singular, ProbCut, correction history, LMP; thời gian cố định 0,65·T (dừng sớm theo độ ổn định và 0,8·T đều yếu hơn).
- **Hạ tầng thời gian (B5–B8):** chừa 100 ms (hoặc 15 %) trước trần, kiểm tra đồng hồ mỗi 128 node, tạm tắt GC chu kỳ của Python khi tìm (một lần quét GC qua TT có thể dừng ~100 ms); không bao giờ vượt `max_think_time_s` (đề xuất "panic 1,5–2 s" bị chặn ở mức hard).
- **Kết quả** (1 s/nước, khai cuộc ngẫu nhiên 4 nửa nước, mỗi khai cuộc 2 ván đổi màu, tối đa 150 nửa nước):
  - B5 vs B4 depth 3 (80 ván/bản): Tổng hợp +382, GPT +228, Grok +163, Gemini +147, DeepSeek +147 Elo; Tổng hợp vs B4 depth 6 + 1 s: +255 [+186, +347].
  - B6 vs B5 cùng nguồn (40 ván): GPT +137, Gemini +241, Grok +191, DeepSeek +241; so với B5 Tổng hợp: GPT/DeepSeek ≈ +50..+100, Gemini/Grok ngang.
  - B7 vs B6 (50 ván): GPT +28, Gemini +147, Grok +182, DeepSeek +21; đo dài hơn: DeepSeek +61 (160 ván), Grok +137, Gemini +127 (80 ván), GPT −53..+60.

#### 4.9.3 Benchmark 8 "Luna" (2026-10-08)

Mục tiêu: vượt B7 theo bản nghiên cứu "Luna B8 — Efficient & Verified Selective Search". `ai.bench8` là bản sao lõi Dragon (`Engine8`, `SearchConfig8`, `Evaluator8`), mỗi phương án là một công tắc:
- `fast_see` (**bật**): SEE theo ngưỡng `see_ge` (vòng swap kiểu Stockfish, dừng sớm); khớp SEE đầy đủ trên 88.676 trường hợp, cùng nước và số node với B7 ở độ sâu cố định; kèm cache phần đánh giá quân.
- `verify` (`Verify8`, tắt): nước bị LMR giảm ≥ 2 ply mà hụt alpha < 60 cp được tìm lại ở độ sâu trung gian, ≤ 5 % số node (`tactical_only`: chỉ nước gần vua địch hoặc đẩy tốt xa).
- `push_guard` (tắt): tốt tiến lên hàng 6/7 không bị LMP, futility, SEE pruning, LMR.
- `ply_limit` + eval `kpk` (tắt): vượt mốc nửa nước của giải là hòa (chiếu hết vẫn tính); luật ô chốt KPK; bot đọc `[bots.bench8_luna] max_plies`.

Kết quả (1 s/nước, khai cuộc 2 nửa nước, đổi màu theo cặp):
- 50 ván/phương án vs B7: FastCore −49 [−137, +33] (đi giống hệt B7 → chính là mức nhiễu), xác minh có lọc −21, xác minh mọi nước +21, cổng an toàn +14, mốc 150 + KPK +21.
- Ghép 3 phương án dương, 100 ván: **−10 [−62, +41]**. Lần thử trước (cắt tỉa theo độ tin cậy, contempt động, nghĩ lâu hơn, bỏ ProbCut) cũng thua (−45 / 100 ván).
- 400 ván/phương án: xác minh LMR −7 [−33, +19], cổng an toàn +14 [−12, +40], mốc 150 + KPK +21 [−5, +47] — không phương án nào có cận dưới > 0.
- **Kết luận:** B8 = Dragon + FastCore (chơi như B7, nhanh hơn chút), **chưa mạnh hơn B7**; mặc định ẩn (`max_level = 7`).

#### 4.9.4 Giải vòng tròn (`backend/tournament/`)

```python
# tournament_config.py
@dataclass(frozen=True)
class TournamentConfig:
    bots: tuple[str, ...]            # lọc theo [benchmarks] max_level
    matches_per_pair: int = 20       # số ván mỗi LƯỢT THÁCH ĐẤU (mỗi cặp 2 × số này)
    max_history: int = 10            # số "Trận Chiến Lần n" giữ lại (FIFO)
    max_plies: int = 150
    depth: int = 0                   # > 0: ép mọi bot cùng độ sâu; 0: giữ cấu hình riêng
    random_opening_plies: int = 2
    claim_draw: bool = True
    seed: int = -1                   # -1 = ngẫu nhiên; >= 0 để tái lập
    max_think_time_s: float = 1.0    # trần mỗi nước; 0 = không giới hạn
    measure_memory: bool = True      # mỗi bot một tiến trình; hệ điều hành đo RAM
    eta_smoothing: float = 0.3       # a của ước tính thời gian còn lại
    @classmethod
    def from_config(cls, config) -> "TournamentConfig": ...   # đọc [tournament], kẹp giá trị hợp lệ
    def validate(self) -> None: ...

# round_robin.py
@dataclass
class Matchup:            # tổng đối đầu một cặp: games, wins_a/b, draws, score_a/b
    def add(self, winner, a_is_white) -> None: ...
@dataclass(frozen=True)
class StandingRow:        # bot_id, rank, points, games, wins, draws, losses, think_time_s, score_pct,
                          # total, bonus (thưởng thắng ngược, nằm trong total), memory_mb
@dataclass
class TournamentResult:   # participants, matches_per_pair, completed, games_played/total, standings, matchups, battle, errors
    def to_json(self) -> dict: ...   # version 1
    @classmethod
    def from_json(cls, data) -> "TournamentResult": ...
def upset_bonuses(expected, matchups) -> dict[str, float]: ...
def compute_standings(participants, matchups, think_times=None, memories_mb=None) -> tuple[StandingRow, ...]: ...
class RoundRobinRunner:
    def __init__(self, participant_ids, *, matches_per_pair=20, max_plies=150, claim_draw=True,
                 random_opening_plies=2, depth=None, max_think_time_s=None, eval_scale=8.0,
                 bot_configs=None, seed=None, on_progress=None, on_ply=None, on_game_end=None,
                 clock=time.perf_counter, create_bot=None, measure_memory=False): ...
    pairs: tuple[tuple[str, str], ...]          # mọi cặp không thứ tự
    schedule: tuple[((str, str), bool), ...]    # (cặp, bot đầu cặp cầm Trắng) theo lượt thách đấu
    games_total: int                             # n·(n−1)·matches_per_pair
    current_game: tuple[str, str] | None         # ván đang đấu: (thách đấu/Trắng, bị thách đấu/Đen)
    def play(self) -> TournamentResult: ...      # đồng bộ; GUI chạy luồng nền
    def request_stop(self) -> None: ...          # ván dở bị hủy, không tính
    def standings(self) -> tuple[StandingRow, ...]: ...   # bảng sống (tạm tính)
    # on_ply(ply) sau mỗi nửa nước -> GUI hiện tiến trình trong ván

# process_player.py
def memory_usage() -> tuple[int, int]: ...      # (RAM hiện tại, đỉnh) của tiến trình, byte
class ProcessPlayer:                              # bot chạy trong tiến trình riêng (spawn), một ván
    def __init__(self, bot_id, config=None): ...  # lỗi tạo bot -> RuntimeError
    measured_think_time_s: float | None; last_search_info: dict
    def select_move(self, board) -> chess.Move: ...
    def reset(self) -> None: ...
    def close(self) -> int | None: ...            # dừng tiến trình, trả bộ nhớ đỉnh − nền (byte)

# tournament_history.py
class TournamentHistory:
    def __init__(self, directory, max_runs=10): ...
    def next_index(self) -> int: ...   # tiếp tục sau khi cắt bớt
    def save(self, result) -> TournamentResult: ...   # đóng dấu battle, ghi battle_NNNN.json, cắt FIFO
    def list(self) -> list[TournamentResult]: ...    # mới nhất trước, bỏ file hỏng
    def load(self, battle) -> TournamentResult: ...
    def clear(self) -> None: ...
```

- **Thể thức — lượt thách đấu:** lần lượt từng bot (theo thứ tự danh sách) thách đấu mọi bot còn lại và **cầm Trắng**. Ví dụ A, B, C, D, E: A thách B, C, D, E (A Trắng); rồi B thách A, C, D, E (B Trắng, A Đen); … đến E. Mỗi cặp có `2 × matches_per_pair` ván, Trắng/Đen chia đều; tổng `n·(n−1)·matches_per_pair` (20 bot, 1 ván/lượt = 380 ván). Khai cuộc ngẫu nhiên từng ván (có yếu tố may mắn, cố ý).
- **Bot mới mỗi ván:** `create_bot(bot_id, config)` cho **từng ván** (mặc định `ai.registry.create_bot`, nạp lười). Mỗi bot giữ độ sâu riêng (`[bots.<id>]`); `tournament.depth > 0` mới ép cùng độ sâu. `max_think_time_s` truyền cho mọi bot: benchmark tự dừng đúng hạn; bot thành viên chỉ bị giới hạn nếu code đọc khóa này (OI-1).
- **Bộ nhớ** (`measure_memory = true`): mỗi ván, mỗi bot chạy trong **một tiến trình riêng** (`ProcessPlayer`). Hệ điều hành tự ghi **đỉnh RAM** (Windows `PeakWorkingSetSize`, Linux `ru_maxrss`) nên đo không làm bot chậm. Nền đo **trước khi tạo bot** (Python, python-chess, registry); bộ nhớ bot = đỉnh − nền, gồm module/trọng số/bảng của bot **và mọi bộ nhớ tạm lúc nghĩ** (TT, cache, cây tìm kiếm) kể cả khi đã giải phóng. Hết ván đóng tiến trình, ghi kết quả ván; cột Bộ nhớ = **trung bình MB mỗi ván**. Thời gian nghĩ đo trong tiến trình con (không tính gửi/nhận). Mở/đóng tiến trình ~0,5–1 s mỗi ván, ngoài thời gian nghĩ. Bot do test tự tạo (`create_bot`) không dùng tiến trình.
- **Điểm:** thắng 1, hòa 0,5, thua 0.
- **Tổng (xếp hạng):** `sum_e` = Điểm ván + (thời gian TB − thời gian của bot) / 100 + (bộ nhớ TB − bộ nhớ của bot) / 100 (giây; MB/ván; TB trên các bot đã đấu; ví dụ TB 50 MB, bot 28 MB → +0,22). **Tổng = `sum_e` + thưởng thắng ngược.** Tổng giảm dần; bằng Tổng thì tổng thời gian ít hơn xếp trên; bằng cả hai thì **chia sẻ hạng** kiểu "1224" (1, 2, 3, 4, 5, 5, 7).
- **Thưởng thắng ngược** (`upset_bonuses`, chốt theo từng cặp): khoảng cách = `sum_e` cao − `sum_e` thấp; chỉ bot có `sum_e` **thấp hơn** được thưởng: `(12 % + 0,5 % · n) × khoảng cách` nếu bot cao hơn thua nó n ván, cộng `(6 % + 0,05 % · d) × khoảng cách` cho d ván hòa. `sum_e` bằng nhau: không thưởng. Cột Điểm chỉ là điểm ván (1 / 0,5 / 0); thưởng (`bonus`) chỉ cộng vào Tổng.
- **Tạm tính:** trong lúc giải chạy, phần thời gian, bộ nhớ và thưởng là **tạm tính** (màn hình ghi "Tổng đang tạm tính"); khi kết thúc, toàn bộ được tính lại một lần trên dữ liệu cả giải — đó là điểm chính thức, không phụ thuộc thứ tự đấu.
- **Ước tính thời gian** (`tournament/eta.py`, `RoundRobinRunner.time_status() -> (đã chạy, còn lại | None)`): mỗi bot giữ thời gian nghĩ mỗi ván làm mượt hàm mũ `E = a·x + (1 − a)·E` (`[tournament] eta_smoothing`, mặc định 0,3), thêm một giá trị làm mượt cho chi phí chung mỗi ván; còn lại = tổng ước tính các ván chưa đấu theo lịch (bot chưa đấu dùng trung bình, ván đang đấu trừ phần đã chạy). Hiện ở **góc phải trên** màn Xếp hạng AI khi giải chạy.
- **Lịch sử giải:** mỗi lần chạy xong lưu `battle_NNNN.json` ("Trận Chiến Lần n"), giữ `max_history` bản gần nhất, ở `database/data/tournaments/` — tách khỏi `history/` và `ranking.json`.
- **Lỗi bot:** chỉ ghi vào `TournamentResult.errors` và bỏ ván đó, không làm sập giải.

## 5. Đặc tả GUI (Pygame)

### 5.1 Cửa sổ & độ nét

- Tọa độ **logic 960×640**: bàn cờ 640×640 bên trái (ô 80 px), panel 320×640 bên phải. Cửa sổ resize được, giữ tỷ lệ 3:2, viền đen (letterbox); chuột quy đổi ngược về tọa độ logic.
- **Vẽ ở độ phân giải thật:** lớp vẽ chung `frontend/gui/render.py` nhân mọi tọa độ, kích thước, nét, cỡ font với `scale = viewport.scale` (font tạo theo cỡ thật, cache theo cỡ; ảnh quân scale từ PNG 256 px). Surface vẽ đúng `(viewport.width, viewport.height)`, blit thẳng, không scale lần hai. API test: `app.render_scale`, `app.canvas_size`.
- Windows: `ctypes.windll.shcore.SetProcessDpiAwareness(2)` (dự phòng `user32.SetProcessDPIAware()`) **trước** `pygame.init()`. Cửa sổ mặc định = 960×640 × `ui_scale` (DPI / 96), không vượt 90 % màn hình.
- Bot chạy **luồng nền**; cửa sổ luôn phản hồi.

### 5.2 Màn hình

| Màn hình | Nội dung |
|---|---|
| Menu chính | Tiêu đề "Chess" + logo quân Vua (rhosgfx), nút theo cột căn giữa: Người vs Bot · Bot vs Bot · **Xếp hạng AI** · Lịch sử · Xếp hạng · Cài đặt · Thoát |
| Chuẩn bị Người vs Bot | Chọn bot trong `list_bots(include_debug=show_debug_bots, include_benchmarks=True, max_benchmark_level=...)` (lưới 2 cột, thu gọn khi > 10 bot, dày khi > 14 bot); bot `BotUnavailableError` hiện mờ kèm lý do (thử tạo một lần khi mở màn). Màu Trắng / Đen / **Ngẫu nhiên**. Bắt đầu, Quay lại |
| Chuẩn bị Bot vs Bot | Bot Trắng và bot Đen độc lập (được trùng; > 9 bot: hàng 30 px, nút hoán đổi cạnh nút thể thức; > 15 bot: mỗi bên 2 cột con 10 hàng), nút Đổi bên, 1 ván / Best of 3, Bắt đầu, Quay lại |
| Ván đấu | Bàn cờ + panel. **Không Undo, không đổi phe.** Dừng ván, icon loa. Ván xong: kết quả (`game.result.*` + `termination.*`) đè lên bàn, nút Chơi lại / Về menu |
| Bot vs Bot đang chạy | Như trên + tỷ số loạt, "Ván i/n", Tạm dừng/Tiếp tục, Tốc độ (0 / 150 / 300 / 800 ms qua `set_bot_move_delay`); loạt xong hiện `game.result.series_win` / `series_draw` |
| Lịch sử | 20 ván: "Trắng vs Đen — kết quả — lý do — ngày" + ghi chú loạt (`history.series_note`); click → Xem lại; Xuất PGN → `data_dir/exports/<game_id>.pgn` (`history.exported`) |
| Xem lại | Bàn cờ (lật nếu người cầm đen), Về đầu / Lùi / Phát-Dừng / Tiến / Về cuối, tốc độ, Xuất PGN, panel nước đi (tô nước hiện tại), thanh đánh giá theo `current_move`; mỗi frame gọi `tick` |
| Xếp hạng (Elo) | `leaderboard_rows`: Hạng, Người chơi, Số ván, Thắng, Hòa, Thua, Điểm, Elo; Đặt lại → hộp xác nhận → `reset_ranking()` |
| Xếp hạng AI | §5.11 |
| Lịch sử giải đấu | 10 "Trận Chiến Lần n" + bảng xếp hạng và tỉ số đối đầu từng cặp (`format_matchup`), cuộn ▲/▼ |
| Cài đặt | Ngôn ngữ (vi/en, đổi ngay), âm thanh, tốc độ xem lại mặc định, theme (§5.10) |

### 5.3 Bàn cờ & panel

- Đi quân: **click chọn quân → click ô đích** (kéo thả tùy chọn). Highlight ô chọn, nước hợp lệ (chấm tròn), nước vừa đi, vua bị chiếu (đỏ). **Phong cấp:** hộp Hậu / Xe / Tượng / Mã (có nút hủy → `MoveInput.clear()`). Lật bàn khi người cầm đen.
- Click bàn → `board_geometry.square_at` → `MoveInput.click(snapshot.board, square, human_color)` → `move` thì `controller.submit_human_move`; `promotion` thì mở hộp chọn.
- **Panel** (mỗi mục thu gọn/mở rộng): tên 2 bên + "đang suy nghĩ…", tỷ số loạt (Best of 3), thanh đánh giá (`material_eval` nước cuối), lịch sử nước SAN (cuộn, nước mới luôn thấy), thời gian suy nghĩ (nước vừa rồi + trung bình mỗi bên), thông tin tìm kiếm (depth/nodes nếu có), quân bị ăn.

### 5.4 Âm thanh, đa ngôn ngữ, đồ họa

- **Âm thanh:** đi quân, ăn quân, chiếu, kết thúc ván; **mặc định TẮT**; bật/tắt trong Cài đặt và icon loa trong ván (đồng bộ). 4 file `frontend/gui/assets/sounds/{move,capture,check,game_end}.wav` **tự sinh** bằng `another/tools/make_sounds.py` (sóng sin, `wave` + `math`) nên không vướng giấy phép; âm thanh ngoài chỉ dùng CC0 (vd kenney.nl), ghi nguồn ở `frontend/gui/assets/CREDITS.md`.
- **Đa ngôn ngữ:** mọi chuỗi qua `t("key")`; `frontend/gui/locales/vi.toml` và `en.toml` **cùng tập khóa** (CI kiểm). Mặc định `vi`, đổi có hiệu lực ngay. Font hỗ trợ tiếng Việt (thử "segoeui", "arial", "dejavusans", rồi mặc định).
- **Quân:** bộ **rhosgfx** (RhosGFX, **CC0 1.0**, nguồn `lichess-org/lila/public/piece/rhosgfx`), đã có trong repo (SVG gốc + PNG 256×256 tại `frontend/gui/assets/pieces/rhosgfx/`, tên `wK.png … bP.png`). Ô bàn cờ vẽ bằng code, màu theo theme.

### 5.5 Module GUI thuần logic (test được, **cấm import pygame**)

```python
# scaling.py
LOGICAL_SIZE = (960, 640)
@dataclass(frozen=True)
class Viewport:                  # vùng canvas sau scale, giữa cửa sổ
    scale: float; offset_x: int; offset_y: int; width: int; height: int
    @classmethod
    def fit(cls, window_w, window_h, logical=LOGICAL_SIZE): ...   # scale = min(ww/lw, wh/lh); kích thước <= 0 -> ValueError
    def to_logical(self, x, y): ...   # None nếu click vào viền
    def to_window(self, x, y): ...
# board_geometry.py              (bàn cờ góc trên-trái)
BOARD_SIZE = 640; SQUARE_SIZE = 80
def square_at(x, y, flipped=False): ...      # ngoài bàn -> None
def square_origin(square, flipped=False): ...   # flipped=False: a8 ở (0,0), h1 ở (560,560)
# move_input.py
@dataclass(frozen=True)
class InputResult:
    kind: str    # "none" | "select" | "deselect" | "move" | "promotion"
    square: int | None = None; move: chess.Move | None = None; promotion_moves: tuple = ()
class MoveInput:
    selected: int | None
    def click(self, board, square, player_color) -> InputResult: ...
    def choose_promotion(self, piece_type) -> chess.Move: ...   # không có phong cấp chờ -> ValueError
    def legal_targets(self, board) -> set[int]: ...
    def clear(self) -> None: ...
# game_info.py
def captured_pieces(board): ...       # quân CỦA màu đó đã mất = max(0, ban đầu − hiện tại); thứ tự Q, R, B, N, P
def think_time_summary(moves): ...    # (nước gần nhất, trung bình) mỗi màu, bỏ khai cuộc; ply lẻ = trắng
# i18n.py
SUPPORTED_LANGUAGES = ("vi", "en")
class Translator:
    def __init__(self, language="vi", directory=LOCALES_DIR, overrides=None): ...   # ngôn ngữ lạ -> ValueError
    language: str
    def set_language(self, language) -> None: ...   # lạ -> ValueError, giữ nguyên
    def t(self, key, **params) -> str: ...          # thiếu khóa -> trả key; thiếu tham số -> giữ "{name}"; overrides (tên bot từ config) thắng mọi ngôn ngữ
# replay_model.py
class ReplayModel:
    def __init__(self, record): ...    # index 0 = thế ban đầu
    index; length                       # length = len(record.moves)
    board                               # bản sao thế cờ sau `index` nửa nước (giữ move_stack)
    last_move; current_move             # current_move = record.moves[index-1] hoặc None
    def first(self); def last(self); def next(self) -> bool; def prev(self) -> bool; def seek(self, index)   # kẹp [0, length]
    playing: bool; delay_ms: int        # delay kẹp [100, 5000]
    def play(self, now_ms); def pause(self)   # play ở cuối thì quay về đầu
    def tick(self, now_ms) -> bool: ...  # qua delay_ms thì next(); tới cuối tự pause
# leaderboard_view.py
@dataclass(frozen=True)
class LeaderboardRow: rank; player_id; name; games; wins; draws; losses; points: float; elo: int
def leaderboard_rows(ranking, translator) -> list[LeaderboardRow]: ...   # theo ranking.table(); name = t(f"players.{id}")
# tournament_view.py
def tournament_rows(standings, translator) -> list[TournamentRow]: ...   # dịch tên, giữ hạng
def sort_rows(rows, field) -> list[TournamentRow]: ...   # giảm dần theo cột; "total" = thứ tự xếp hạng
def provisional_standings(bot_ids): ...   # bảng 0 điểm theo thứ tự config, hiện sẵn khi chưa đấu
def format_points(p); format_total(t); format_seconds(s) -> "<s:.1f>s"; format_memory(mb) -> "<mb:.1f> MB" | "-"
def format_head_to_head(matchup) -> "15 - 5"; format_matchup(matchup, translator) -> "MCTS  15 - 5  Deep RL"
def progress_fraction(done, total) -> float: ...   # kẹp 0..1
# sound.py (dùng pygame.mixer lười)
SOUND_EVENTS = ("move", "capture", "check", "game_end")
def sound_for_move(board_before, move) -> str: ...   # "check" > "capture" (kể cả bắt tốt qua đường) > "move"
class SoundManager:
    def __init__(self, sounds_dir, enabled=False): ...
    enabled: bool
    def play(self, event) -> None: ...   # tắt -> không làm gì; KHÔNG BAO GIỜ raise; file <sounds_dir>/<event>.wav
```

`MoveInput.click`: không phải lượt `player_color` → `none`. Click ngoài bàn: đang chọn → `deselect`, không → `none`. Chưa chọn: click quân mình **có nước hợp lệ** → `select`, chỗ khác → `none`. Đang chọn: click lại ô đó → `deselect`; quân mình khác có nước → `select`; ô đích hợp lệ → `move` (hoặc `promotion`, giữ trạng thái chờ đến `choose_promotion`); ô khác → `deselect`.

### 5.6 Bộ điều khiển ván (`frontend/gui/controller.py`, không import pygame)

Chạy ván trong **luồng nền**; màn hình đọc **snapshot** mỗi frame.

```python
@dataclass(frozen=True)
class ControllerSnapshot:
    board; moves: tuple[MoveRecord, ...]; game_index: int; n_games: int   # game_index 1-based; n_games 1 | 3
    finished_games: tuple[GameRecord, ...]; series_result: SeriesResult | None
    thinking: bool              # đang chờ BOT đi
    thinking_color             # màu của bot đang nghĩ; first_is_white: bên A cầm Trắng ở ván này
    waiting_for_human: bool; finished: bool; paused: bool
class GameController:
    def __init__(self, white, black, *, mode, config, n_games=1, ranking=None, history=None, rng=None): ...
        # human_vs_bot: n_games == 1, không khai cuộc ngẫu nhiên; bot_vs_bot: SeriesRunner, random_opening_plies từ [game]
        # max_plies, claim_draw từ [game]; eval_scale từ [eval_bar] scale
    def start(self) -> None: ...       # đúng 1 lần; lần 2 -> RuntimeError
    def snapshot(self) -> ControllerSnapshot: ...
    def submit_human_move(self, move) -> None: ...
    def human_color(self): ...          # None nếu bot vs bot
    def stop(self); def pause(self); def resume(self)
    def join(self, timeout=None) -> bool: ...
    def set_bot_move_delay(self, ms) -> None: ...   # đổi ngay, kể cả khi đang chờ (0 = đi tiếp ngay)
```

- `HumanPlayer` bọc trong proxy (giữ `bot_id`, `display_name`, `cancel`, `reset`) để biết khi nào đang chờ → `waiting_for_human`; GUI chỉ nhận click khi True (nước gửi sớm hơn bị xóa khi ván bắt đầu).
- `pause()` trước `start()` vẫn có hiệu lực.
- Mỗi ván xong (kể cả hủy): `history.save(record)` và `ranking.record_game(record)` trong luồng nền.
- Bot vs Bot: sau mỗi nước (trừ khai cuộc) ngủ `[ui] bot_move_delay_ms`; `stop()` thoát ngay.
- Exception trong luồng nền → ván ABORTED, `finished=True`, GUI không chết.

### 5.7 Ứng dụng (`frontend/gui/app.py`, `screens/`, `widgets/`)

```python
class App:
    def __init__(self, config=None, data_dir=None, local_config_path=None): ...
        # config None -> load_config(); data_dir None -> <repo>/database/data; local_config_path None -> LOCAL_CONFIG_PATH
        # Ranking(data_dir/"ranking.json", known_ids=list_bots(include_benchmarks=True, max_benchmark_level)+["human"])
        # History(data_dir/"history", max_games); Translator(..., overrides=tên bot từ [bots.<id>] display_name)
    def run(self); def render_frame(self)                 # vòng lặp chính / xử lý sự kiện + vẽ 1 frame
    def goto(self, name): ...   # "menu" | "setup_human" | "setup_bots" | "game" | "history" | "replay"
                                # | "leaderboard" | "settings" | "tournament" | "tournament_history"
    current_screen_name: str
    def start_human_game(self, bot_id, human_color): ...  # HumanPlayer vs registry.create_bot(bot_id, bot_config) -> "game"
    def start_bot_game(self, white_id, black_id, n_games): ...
    def open_replay(self, game_id): ...
    controller; replay_model; ranking; history; translator; sound_enabled
    def click_logical(self, x, y); def click_window(self, x, y); def resize(self, w, h)
    def set_sound_enabled(self, enabled); def set_language(self, language); def set_replay_delay(self, ms)   # lưu local.toml
    def reset_ranking(self); def start_tournament(self); def stop_tournament(self)
    def quit(self) -> None: ...   # dừng controller và giải, pygame.quit()
```

App chuyển `MOUSEMOTION` cho màn hình qua `handle_hover(x, y)`. Âm thanh: snapshot có nước mới thì phát `sound_for_move`, ván xong phát `game_end`.

### 5.8 Theme & chuẩn thiết kế

**Tên ứng dụng:** "Chess" (`app.title` vi và en). **Theme** (`frontend/gui/theme.py`, lưu `ui.theme`, mặc định `dark_winter`): widget chỉ dùng **vai trò màu**, không bao giờ mã màu cứng.

| Vai trò | Ý nghĩa |
|---|---|
| `bg` | nền màn hình |
| `surface`, `surface_alt` | nền panel/thẻ, nền xen kẽ (hàng bảng, mục chọn) |
| `border` | viền, đường kẻ |
| `text`, `text_muted`, `text_disabled` | chữ chính / phụ / bị khóa |
| `primary`, `primary_hover`, `on_primary` | nút chính + chữ trên nút |
| `secondary`, `secondary_hover`, `on_secondary` | nút phụ |
| `accent` | lựa chọn đang bật, tab, tiêu điểm |
| `attention` | nước vừa đi, gợi ý — **tiết chế** |
| `danger` | vua bị chiếu, Đặt lại / Dừng ván |
| `board_light`, `board_dark`, `board_select`, `board_last`, `board_hint` | bàn cờ |

**6 theme gốc** (`frontend/resource/theme/*.png`):

| id | vi / en | Màu gốc |
|---|---|---|
| `dark_winter` **(mặc định)** | Rừng đêm / Night Forest | `#092328 #12544F #2A835F #8BBB92` |
| `dark_cold` | Biển đêm / Deep Sea | `#091540 #1B2CC1 #7692FF #ABD2FA` |
| `cold` | Bầu trời / Sky | `#E3F2FD #90CAF9 #2196F3 #0D47A1` |
| `fall` | Mùa thu / Autumn | `#E2A16F #FFF0DD #D1D3D4 #86B0BD` |
| `summer` | Mùa hè / Summer | `#FFEED6 #A5AF79 #827148 #E8A07C` |
| `winter` | Mùa đông / Winter | `#777C6D #B7B89F #CBCBCB #EEEEEE` |

`dark_winter` gợi ý (tinh chỉnh nếu cần để đạt tương phản): `bg #092328`, `surface #0E3236`, `surface_alt #12423F`, `border #1E5F57`, `text #EAF4EC`, `text_muted #8BBB92`, `primary #2A835F`, `on_primary #FFFFFF`, `secondary #12544F`, `accent #8BBB92`, `attention #E9B949`, `danger #D9534F`; `board_light #DDEBDD`, `board_dark #5F9C7C`. Màu vai trò lấy từ 4 màu gốc hoặc đậm/nhạt hơn; riêng `attention`, `danger` chọn màu bổ trợ ngoài bảng để luôn nhận ra.

**18 theme Color Hunt** tạo **tự động** từ `frontend/resource/theme/Color Hunt Palette <24 hex>.png` (màu đọc từ **tên file**): id `ch_<6 hex đầu>`; bỏ bảng trùng theme đã có (`e3f2fd…` = `cold`); file mới tự nhận, chưa có tên thì hiện "Color Hunt #<hex>".

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

**`derive_theme(palette) -> Theme`** (dùng chung, test được):
1. Sắp 4 màu theo relative luminance (WCAG).
2. **Tối** nếu màu tối nhất L < 0,08 **và** tương phản ≥ 4,5:1 với màu sáng nhất (`bg` = tối nhất, đậm thêm nếu cần; `surface` = `bg` pha sáng 6–10 %); ngược lại **sáng** (`bg` = sáng nhất, `surface` = pha trắng/đậm nhẹ).
3. `primary` = màu bão hòa nhất trong 2 màu giữa, chỉnh độ sáng (giữ hue) đến khi `on_primary` (trắng/gần đen) ≥ 4,5:1; `secondary` = màu giữa còn lại, chỉnh tương tự; `accent` = màu còn lại hoặc `primary` đậm hơn, khác rõ `secondary` (≥ 1,5:1).
4. `text` gần đen/trắng **nhuốm hue của bảng** (vd `#2B2230`), ≥ 4,5:1 trên `bg` và `surface`; `text_muted` ≥ 3:1 trên `bg`.
5. `board_light`/`board_dark` từ 2 màu bảng (pha nếu cần), tương phản nhau ≥ 1,6:1; viền đen của quân rhosgfx ≥ 3:1 trên mỗi ô.
6. `attention` (ấm), `danger` (đỏ) chọn trong bộ màu bổ trợ cố định, biến thể ≥ 3:1 trên `bg`.

6 theme gốc cũng phải qua đúng các ngưỡng này (giữ giá trị chọn tay nếu đạt).

**Chuẩn thiết kế:** theme mặc định tối, tông xanh lục/ngọc (bình tĩnh, tập trung; nền tối giảm chói). `attention` chỉ cho thứ cần chú ý (nước vừa đi, lượt của bạn); `danger` chỉ cho nguy hiểm/phá hủy (chiếu, Đặt lại, Dừng ván). Tương phản WCAG 2.1 AA: `text` trên `bg`/`surface` và `on_primary` trên `primary` ≥ 4,5:1, `text_muted` ≥ 3:1, ô sáng/tối ≥ 1,6:1. Lưới 8 px; thang chữ 13/15/18/24/36 px (scale 1); bo góc 10 px; **mỗi màn một nút `primary`**, còn lại `secondary`. Trạng thái nút: thường / hover (sáng hơn, con trỏ bàn tay) / nhấn / khóa (`text_disabled`); nút đang chọn trong nhóm (màu quân, bot, ngôn ngữ, theme) dùng `accent`.

**Cài đặt — chọn theme (24):** ô mẫu màu (4 màu gốc + tên), chia nhóm **Tối**/**Sáng**, cuộn (con lăn + ▲/▼ vẽ bằng hình), ô đang dùng viền `accent`; rê chuột = **xem trước** ngay, bấm mới lưu.

### 5.9 Xếp hạng AI (`tournament_controller.py`, `screens/tournament.py`, `screens/tournament_history.py`, `widgets/progress_bar.py`)

```python
@dataclass(frozen=True)
class TournamentSnapshot:          # tournament_controller.py — không import pygame
    running: bool; finished: bool; stopped: bool
    games_done: int; games_total: int
    current_pair: tuple[str, str] | None    # ván đang đấu: (thách đấu/Trắng, bị thách đấu/Đen)
    standings: tuple[StandingRow, ...]; result: TournamentResult | None; error: str | None
    plies_current: int; plies_limit: int
    progress: float                          # property: (games_done + phần ván đang đấu) / games_total
class TournamentController:
    def __init__(self, config, *, settings=None, history=None, create_bot=None): ...
    def start(self) -> None: ...     # RoundRobinRunner trong threading.Thread; lần 2 -> RuntimeError
    def stop(self) -> None: ...      # cờ dừng + runner.request_stop()
    def join(self, timeout=None) -> bool: ...
    def snapshot(self) -> TournamentSnapshot: ...   # bảng sống lấy từ runner
```

- Bảng vẽ sẵn: chưa có dữ liệu thì `provisional_standings`; có trận gần nhất cùng đội hình thì dùng bảng đó. Cột: Hạng, Bot, Số ván, Thắng, Hòa, Thua, Điểm, Thời gian, **Bộ nhớ**, Tổng (tối đa 20 dòng; hàng 18 px khi > 9 bot, 16 px khi > 14 bot và các nút dời xuống).
- Đang chạy: dòng trạng thái (`tournament.running` + "Tổng đang tạm tính"), **thanh tiến trình tổng**, nhãn "Đang chạy: A vs B" = ván **đang đấu** (A thách đấu/Trắng, B bị thách đấu/Đen), tô hai dòng của cặp đó.
- **Sắp xếp:** bấm tiêu đề Số ván / Thắng / Hòa / Thua / Điểm / Thời gian / Bộ nhớ / Tổng → giảm dần (dấu ▼); sau **5 s** tự về thứ tự xếp hạng theo Tổng (mặc định); cột Hạng giữ hạng thật.
- Hai nút dưới bảng: `tournament.start` (thành `tournament.stop` + `danger` khi chạy), `tournament.history`; Quay lại.
- **Không chặn UI:** mọi tính toán trong luồng nền; `App.quit()` và Dừng đấu đều gọi `TournamentController.stop()`.

## 6. Cấu hình

- `backend/config/default.toml` (commit) là nguồn mặc định; `backend/config/local.toml` (.gitignore) ghi đè từng khóa (deep merge). Màn Cài đặt chỉ ghi `local.toml`.
- Chỉ đọc qua `backend/core/config.py` (`tomllib`); ghi `local.toml` bằng `tomli-w`.

```python
DEFAULT_CONFIG_PATH: Path; LOCAL_CONFIG_PATH: Path
def load_config(default_path=DEFAULT_CONFIG_PATH, local_path=LOCAL_CONFIG_PATH) -> dict: ...   # local None/không có -> chỉ default
def deep_merge(base, override) -> dict: ...          # dict MỚI, không sửa input
def save_local_config(updates, local_path=LOCAL_CONFIG_PATH) -> None: ...   # merge vào local hiện có
def get_bot_config(config, bot_id) -> dict: ...      # config["bots"][bot_id] hoặc {}
```

| Bảng | Khóa (mặc định) |
|---|---|
| `[window]` | `width = 960`, `height = 640`, `fps = 120` |
| `[game]` | `random_opening_plies = 2` (chỉ Bot vs Bot, nửa nước), `max_plies = 300`, `claim_draw = true` |
| `[ranking]` | `elo_initial = 1200`, `elo_k = 32` |
| `[history]` | `max_games = 20` |
| `[ui]` | `language = "vi"`, `sound_enabled = false`, `piece_set = "rhosgfx"`, `theme = "dark_winter"`, `bot_move_delay_ms = 300`, `replay_delay_ms = 800`, `show_debug_bots = false` |
| `[eval_bar]` | `scale = 8.0` |
| `[benchmarks]` | `max_level` (§4.9; hiện đặt 4 = chỉ B1–B4, 7 = đến B7, 8 = có B8) |
| `[tournament]` | `bots` (4 thành viên + B1 … B8, lọc theo `max_level`), `matches_per_pair = 1`, `max_history = 15`, `max_plies = 150`, `max_think_time_s = 1.0`, `measure_memory = true`, `eta_smoothing = 0.3`, `depth = 0`, `random_opening_plies = 2`, `claim_draw = true`, `seed = -1` |
| `[bots.<id>]` | truyền vào `BaseBot(config=...)`; `display_name` ghi đè tên ở mọi màn/ngôn ngữ (thay `players.<id>` và `BaseBot.display_name`). Ví dụ: `deep_rl` (`weights_url`, `weights_sha256`, `device = "cpu"`), `bench_random` (`seed = -1`), `bench_alphabeta*` (`depth = 3`, `evaluator` = `pst`/`advanced`), benchmark B5+ (`max_think_time_s = 1.0`), `bench8_luna` (`max_plies = 150`) |

## 7. Option 4 — Deep RL (`backend/ai/deep_rl/`)

- **PyTorch**, huấn luyện trên **Kaggle** (CPU/GPU), suy luận trên **CPU** trong game. Board encoding nằm **bên trong** package. `import torch` **lười** trong bot.
- Trọng số: checkpoint train ở Kaggle; bản tốt nhất lên **GitHub Release** (tag `deeprl-vX.Y`); lần đầu bot tự tải về `backend/ai/deep_rl/weights/` (gitignored) và kiểm `sha256` — không mạng/sai checksum → `BotUnavailableError`.
- Elo **không phải** reward (reward do Option 4 tự thiết kế; Elo chỉ để đánh giá).
- CI thiếu trọng số: test hợp đồng dùng mô hình khởi tạo ngẫu nhiên (`allow_random_init`). Không có torch (vd Android) → registry báo bot không khả dụng.

## 8. Quy trình Git & quản trị repo

1. **Không ai push thẳng `main`**, kể cả admin.
2. Branch riêng: `feat/<module>-<mô-tả>`, `fix/<module>-<mô-tả>`, `documents/<mô-tả>` (vd `feat/mcts-uct-selection`).
3. PR vào `main` theo template; CI **xanh** và branch **cập nhật với `main`** trước khi merge.
4. Duyệt: PR thành viên cần **1 approve của `@august0362`**; PR của `@august0362` tự merge khi CI xanh (GitHub không cho tự approve).
5. Chỉ sửa thư mục của mình; sửa `backend/core/`, `ai/base_bot.py`, `ai/registry.py`, `backend/tournament/` phải nêu lý do trong PR.
6. Thêm thư viện vào `environments/requirements.txt` thì ghi tên, phiên bản, lý do trong PR.
7. Không commit: `database/data/`, `another/local_tools/`, `backend/config/local.toml`, `backend/ai/*/weights/`, `android/`, file > 5 MB (CI chặn).

**GitHub (admin làm một lần):** Ruleset `main-protect` (target `main`, **không ai bypass**): restrict deletions, block force pushes, require status check `ci` + *branches up to date*. Ruleset `main-review` (target `main`, bypass: Repository admin): require PR, 1 approval, review from Code Owners, dismiss stale approvals. Admin bypass ruleset 2 nhưng vẫn bị ruleset 1 chặn, nên vẫn phải đi qua PR (chỉ không cần người khác approve).

```
# .github/CODEOWNERS — mỗi dòng: <đường dẫn>  <người duyệt>
*                                  @august0362
/backend/ai/alphabeta_regression/  @cieldontcry    @august0362
/backend/ai/genetic_alphabeta/     @khanhtaduy2k5  @august0362
/backend/ai/mcts/                  @TBD_member3    @august0362
/backend/ai/deep_rl/               @august0362
/.github/                          @august0362
```

## 9. Kiểm thử & CI

- Python **3.13** (2026-10-03, thay 3.14: máy nhóm có sẵn, `pygame-ce`, `torch`, `numpy`, `chess` có wheel chính thức; tránh lệch annotation 3.13/3.14), ghim trong `environments/.python-version`. GUI dùng **`pygame-ce`** (vẫn `import pygame`). Công cụ: `pytest`, `pytest-cov`, `ruff`, `import-linter`.
- **TDD:** Claude viết test đặc tả trước; test của module chưa có tự **skip** (`another/tests/_helpers.py::require_module`), có module thì phải xanh mới merge. Code bên trong bot chỉ bắt buộc qua test hợp đồng.

| Check (job `ci`, mỗi push và PR) | Nội dung |
|---|---|
| Lint | `ruff check` + `ruff format --check` (không format `.md`) |
| Ranh giới module | `lint-imports` theo §3.1 |
| Unit test / Coverage | `pytest`; ≥ **80 %** cho `backend/core/`, `backend/tournament/` |
| Hợp đồng bot | Mọi bot có code: nước hợp lệ trên bộ thế chuẩn, không sửa board gốc, 2 instance độc lập |
| i18n / Config | `vi.toml` và `en.toml` cùng khóa; `default.toml` đọc được, đủ khóa bắt buộc |
| Repo hygiene | Không file > 5 MB, không thư mục cấm, không marker xung đột `<<<<<<<` |
| Cài đặt sạch | `pip install -r environments/requirements.txt` trên môi trường trống |
| GUI smoke | App headless (`SDL_VIDEODRIVER=dummy`), render 1 frame mỗi màn |

## 10. Open Issues & Deferred

| ID | Vấn đề | Trạng thái |
|---|---|---|
| OI-1 | Giới hạn thời gian / độ sâu mỗi nước | Hoãn với ván thường. Giải Xếp hạng AI có `max_think_time_s` (benchmark tự dừng) + `max_plies`; bot thành viên không đọc khóa thì chỉ đo, không ngắt |
| OI-2 | Dừng cứng bot đang nghĩ | Hoãn. "Dừng ván" có hiệu lực sau nước hiện tại (giải Xếp hạng AI đã chạy bot trong tiến trình riêng để đo bộ nhớ) |
| OI-3 | Giải round-robin cá nhân (`another/local_tools/`) | Có bản cơ bản `arena.py` (2026-10-04), chỉ trên máy `@august0362`, không push |
| OI-4 | Username GitHub thành viên Option 3 | Chờ; cập nhật §2 và CODEOWNERS |
| OI-5 | `max_plies`, số nước khai cuộc ngẫu nhiên tối ưu | Tạm 300 (ván thường) / 150 (giải) và 2 |
| OI-6 | Thanh đánh giá dùng đánh giá riêng của bot | Hoãn; hiện dùng chênh lệch quân |
| OI-7 | Bảng Xếp hạng AI tối đa 20 dòng | Chấp nhận (đủ 20 bot khi `max_level = 8`); thêm bot thì cần cuộn bảng |
