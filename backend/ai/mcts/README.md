# MCTS — mốc 1: thi đấu với Random

`MctsBot` hiện là bot thật kế thừa `BaseBot`, giữ ID `mcts` và đường dẫn entry point
`ai.mcts.bot:MctsBot`. Không cần thay registry, GUI hoặc cấu hình chung.

## Hai chế độ và cách gọi tên khi báo cáo

| Cấu hình | Thuật toán | Cách xử lý rollout chưa kết thúc |
|---|---|---|
| `use_heuristics = false` | **Pure MCTS / UCT**: mở rộng ngẫu nhiên, rollout chọn đều nước hợp lệ | Giá trị trung lập 0,5, ghi nhận là cutoff |
| `use_heuristics = true` (mặc định) | **MCTS có hỗ trợ heuristic**: cùng cây UCT và backpropagation, rollout ưu tiên ăn quân/phong cấp/phát triển quân, kiểm tra chiếu hết một nước ở gốc | Ước lượng vật chất và vị trí, ánh xạ vào 0,05–0,95 |

**Không gọi chế độ thứ hai là Pure MCTS hoàn toàn.** Nó vẫn chọn nước bằng thống kê
cây MCTS, nhưng chính sách rollout và giá trị ở điểm cắt đã dùng kiến thức cờ vua.
Đây là phần kết hợp bổ sung được người dùng cho phép. Không dùng Alpha-Beta,
Stockfish, mạng học sâu, trọng số huấn luyện, sách khai cuộc hoặc tablebase.

Giới hạn rollout là giới hạn **mô phỏng**, không làm ván thực tế bị xử hòa. Trong
chế độ Pure, nếu hầu hết rollout đều bị cắt ở 0,5 thì tín hiệu chọn nước sẽ yếu.
`eval` là giá trị tìm kiếm đã đổi về −1..1 theo bên vừa đi, **không phải xác suất
thắng đã hiệu chuẩn**.

## Bốn giai đoạn

1. **Selection**: đi từ gốc xuống các nút đã mở rộng hết, chọn UCT lớn nhất:
   `W/N + c * sqrt(ln(parent_visits)/N)`. Nút chưa thăm có UCT vô hạn.
2. **Expansion**: lấy một nước chưa thử, thực hiện trên bản sao và tạo đúng một nút.
3. **Simulation**: rollout tới kết quả thật, tới giới hạn nửa nước hoặc hết thời gian.
4. **Backpropagation**: mỗi nút nhận điểm theo `player_just_moved`. Trắng thắng:
   nút của trắng nhận 1, nút của đen nhận 0; hòa thật nhận 0,5.

Sau tìm kiếm, chọn **nút con có nhiều lượt thăm nhất** (robust child); nếu bằng
lượt thăm thì chọn giá trị trung bình cao hơn. Ngoại lệ được báo rõ ở `shortcut`:
chỉ có một nước hợp lệ hoặc phát hiện chiếu hết một nước trong chế độ hỗ trợ.
Nếu hết ngân sách trước khi mở nút nào, trả một nước hợp lệ dự phòng.

Mỗi lần chọn nước tạo cây mới. Mỗi mô phỏng dùng `copy(stack=True)` để giữ lịch sử.
Bot không thay bàn cờ của caller, không giữ bàn cờ/cây từ ván trước và dùng
`random.Random(seed)` riêng. `reset()` xóa thống kê, không đặt lại chuỗi RNG.

## Luật kết thúc

Luật cờ dùng `python-chess`. Chiếu hết được xét trước luật hòa. Lặp ba lần chỉ tính
khi **đã thực sự lặp ba lần**; luật 50 nước chỉ tính khi `halfmove_clock >= 100`.
Không dùng `outcome(claim_draw=True)`, vì có thể kết thúc sớm một nửa nước.
Giữ cả các luật hòa tự động của thư viện khi `claim_draw = false`.

`max_plies` của ván thi đấu vẫn do `MatchRunner`/`GameState` quản lý. Bot không được
truyền số nửa nước đã tính riêng trong `GameState`, nên không suy ra giới hạn ván
từ bộ đếm rollout.

## Cấu hình

| Khóa | Mặc định | Ý nghĩa |
|---|---:|---|
| `max_think_time_s` | 1,0 | Trần thời gian hợp tác mỗi nước; 0 = chỉ giới hạn số simulation |
| `simulations` | 100000 | Trần số vòng MCTS, dừng khi gặp giới hạn đầu tiên |
| `exploration_constant` | √2 | Hệ số khám phá UCT, không âm |
| `rollout_max_plies` | 4 / 120 | Mặc định cho bản hỗ trợ / bản Pure; 0 = cắt ngay sau expansion |
| `use_heuristics` | true | Bật/tắt toàn bộ phần heuristic |
| `claim_draw` | true | Áp dụng hòa do lặp ba lần và 50 nước như luật dự án |
| `seed` | không đặt | Seed RNG riêng |
| `fast_mode` | false | Giới hạn tối đa 32 simulation, rollout 4 ply, thời gian 0,05 giây |
| `allow_random_init` | bỏ qua | MCTS không cần trọng số |

Bot dừng tìm kiếm ở khoảng 97% ngân sách để chừa thời gian trả kết quả. Một nước
bắt buộc hoặc chiếu hết có thể trả sớm. Đây **không phải cam kết thời gian cứng**:
hệ điều hành, tải CPU và GC có thể gây vượt nhẹ. Khi dùng thời gian thực, cùng seed
không đảm bảo cùng nước vì số simulation phụ thuộc máy. Muốn tái lập chính xác,
đặt `max_think_time_s = 0` và một số `simulations` cố định.

Các khóa đã nằm trong bot nên `[bots.mcts]` trống hiện tại vẫn chạy được. Muốn chỉnh
riêng trên máy cá nhân, thêm vào `backend/config/local.toml` (không commit):

```toml
[bots.mcts]
max_think_time_s = 1.0
use_heuristics = true
seed = 0
```

Không cần cài thêm thư viện cho MCTS ngoài các phụ thuộc đã có của dự án.

## Chạy thử trên Windows / Python 3.13

Tại thư mục gốc dự án, sau khi đã tạo môi trường theo hướng dẫn nhóm:

```bat
set PYTHONPATH=%CD%\backend;%CD%\frontend;%CD%\another
.venv\Scripts\python -c "import chess; from ai.registry import create_bot; b=create_bot('mcts', {'seed': 0}); print(b.select_move(chess.Board())); print(b.last_search_info)"
.venv\Scripts\python -m pytest another\tests\ai\mcts another\tests\ai\test_bot_contract.py -k mcts --basetemp=.pytest-tmp
```

Chạy `run.bat` và chọn MCTS để chơi thử. Tên lớp/ID không đổi; hậu tố baseline
được hệ thống tự bỏ vì `is_baseline` kế thừa từ `BaseBot` là `False`.

## Đánh giá mục tiêu thắng ít nhất 70%

Mốc này dùng **tỷ lệ thắng**, với hòa không tính là thắng. Đồng thời báo điểm
`(thắng + 0,5 × hòa) / tổng ván` để không nhầm hai chỉ số.

```bat
set PYTHONPATH=%CD%\backend;%CD%\frontend;%CD%\another
.venv\Scripts\python -m tests.ai.mcts.benchmark --games 100 --seconds 1 --workers 1 --seed 20261101 --max-plies 150 --opening-plies 2 --output mcts-results
```

- Dùng đúng `bench_random` từ registry và `MatchRunner` hiện có.
- 50 khai cuộc, mỗi khai cuộc 2 nửa nước; chơi hai ván đổi màu.
- Hai ván trong cặp dùng cùng seed và chuỗi khai cuộc; tổng cộng 50 trắng, 50 đen.
- Không tính ưu thế vật chất là thắng: phải có kết quả thật theo luật dự án.
- Tối đa 150 nửa nước/ván, bằng mặc định giải xếp hạng AI hiện tại.
- Có `games.jsonl`, `games.pgn`, `summary.json`: kết quả từng ván, seed, màu,
  thời gian, lỗi, số simulation, tỷ lệ cutoff và SHA-256 mã bot lúc chạy.
- `workers=1` thích hợp đo trên máy cá nhân. Tăng workers khi có đủ lõi CPU;
  không dùng số workers vượt tài nguyên khi so sức mạnh với ngân sách thời gian.
- Khoảng Wilson 95% chỉ để tham khảo; các ván ghép cặp không hoàn toàn độc lập.
  Kết quả một loạt đấu không phải bảo đảm tỷ lệ thắng trên mọi seed/máy.

Thêm `--pure` để đo bản thuần. `--seconds 0 --simulations 200` cho thí nghiệm với
ngân sách tất định. Runner cũng hỗ trợ `--opponent bench_alphabeta3` cho mốc sau;
khả năng đó không có nghĩa đã vượt Benchmark 2.

## Các file trong phần việc

- `bot.py`: hợp đồng bot, cấu hình, RNG, entry point.
- `node.py`: cấu trúc nút, UCT, backpropagation, robust child.
- `search.py`: vòng tìm kiếm, rollout, luật kết thúc, deadline và thống kê.
- `evaluation.py`: heuristic nội bộ, chỉ chạy khi bật hỗ trợ.
- `another/tests/ai/mcts/test_search.py`: kiểm tra từng giai đoạn và luật hòa.
- `another/tests/ai/mcts/test_mcts_bot.py`: registry, cấu hình, seed, reset, board.
- `another/tests/ai/mcts/benchmark.py`: thí nghiệm qua bộ điều phối chung.

Thay đổi chỉ nằm trong package MCTS và test mới của MCTS. Không sửa test cũ,
backend chung, registry, GUI, cấu hình chung hoặc dependency của dự án.
