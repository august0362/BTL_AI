# Benchmark 9 · Super Alpha-Beta NNUE — Kiến trúc

**B9 là benchmark kế thừa engine, không phải engine tự viết.** Toàn bộ tìm kiếm (alpha-beta/PVS, LMR, null-move, singular extension, quản lý TT…) và đánh giá NNUE là của **Stockfish 19** chính thức (GPLv3). Phần của dự án chỉ là adapter UCI, trình cài đặt, cấu hình, test và công cụ đo sức mạnh.

| Thuộc tính | Giá trị |
|---|---|
| `bot_id` | `bench_super_alphabeta_nnue` |
| Tên | `B9 · Super Alpha-Beta NNUE` |
| Lớp | `ai.benchmarks_extension.bench9.bot:SuperAlphaBetaNNUEBot` |
| Thế hệ (`BENCHMARK_LEVELS`) | `9` — hiện khi `[benchmarks] max_level >= 9` (hoặc khi xóa khóa) |
| Engine | Stockfish 19 (`sf_19`, commit `edb0d9d`), NNUE nhúng `nn-1a298aa575a0.nnue` |

## Package `backend/ai/benchmarks_extension/bench9/`

```
bench9/
├── __init__.py      # ghi rõ: engine-derived, GPLv3
├── provenance.py    # bản phát hành đã ghim: tag, commit, URL, SHA-256 archive + binary, tên NNUE
├── engine.py        # UciEngine: chạy/đóng tiến trình, tìm kiếm có hạn chót cứng, đo RAM tiến trình con
├── bot.py           # SuperAlphaBetaNNUEBot (BaseBot): cấu hình, chính sách thời gian, phục hồi lỗi
├── install.py       # python -m ai.benchmarks_extension.bench9.install
└── engine/          # (gitignore) binary + Copying.txt/AUTHORS/README + INSTALLED.json
```

Ranh giới module giữ nguyên (`documents/CONTEXT.md` §3.1): bench9 không import package benchmark nào khác (đã thêm vào hợp đồng *independence* và *forbidden* của import-linter); tournament/GUI chỉ nạp qua `ai.registry`. Import module **không** chạy tiến trình hay tải mạng.

## Luồng một nước đi

1. `select_move(board)` kiểm tra bot chưa bị đóng; 0 nước → `ValueError`; 1 nước → trả ngay.
2. `movetime = max_think_time_s − time_safety_s − overhead`, với `overhead` = độ trễ lớn nhất đo được ở 12 nước gần nhất (khởi đầu 30 ms). Độ trễ đo thật mỗi nước = thời gian `select_move` − `movetime` (gồm IPC python-chess, xử lý lệnh, lập lịch hệ điều hành) — không giả định hằng số.
3. python-chess gửi `position fen <gốc> moves <toàn bộ lịch sử>` (giữ lặp nước, luật 50 nước) rồi `go movetime … [depth …]`. `ucinewgame` được gửi khi `reset()` đổi khóa ván.
4. **Hạn chót cứng:** không có `bestmove` sau `movetime + hard_margin_s` (1 s) → coi là treo: giết tiến trình.
5. Kết quả được kiểm lại là nước hợp lệ trên bàn cờ đầu vào; bàn cờ đầu vào không bị sửa.
6. `last_search_info = {depth, seldepth, nodes, nps, eval (cp theo bên đi), mate?}`.

### Lỗi khởi tạo và lỗi tìm kiếm là hai loại khác nhau

| Tình huống | Xử lý |
|---|---|
| Không có binary / binary sai kiến trúc / file không chạy được / NNUE hỏng / engine thoát ở lần `go` đầu | `BotUnavailableError` khi tạo bot (màn chọn bot hiện lý do; giải đấu ghi lỗi) |
| Engine crash, treo hoặc trả nước vô lý giữa ván | Ghi log, khởi động lại engine **một lần**, tìm lại với thời gian còn lại; nước đó mang `fallback: True` và `engine_error`, `bot.failures += 1` |
| Khởi động lại cũng hỏng | `RuntimeError` → ván bị hủy và ghi lỗi như mọi bot khác. **Không bao giờ** đi nước ngẫu nhiên |

NNUE được kiểm ngay khi khởi động: Stockfish chỉ nạp mạng ở lệnh `go` đầu tiên, nên adapter chạy `go depth 1` và đọc dòng `info string NNUE evaluation using nn-….nnue` (mạng hỏng → Stockfish in `ERROR` rồi thoát → `BotUnavailableError`). Tên mạng thật được lưu ở `bot.network`.

### Vòng đời tiến trình

- Một tiến trình Stockfish cho mỗi instance bot, dùng lại suốt các ván (`reset()` chỉ đổi ván).
- Đóng: `bot.close()`, hoặc tự động khi bot bị thu gom (`weakref.finalize`), hoặc lúc thoát Python. Luồng nền của python-chess **không phải daemon**, nên `engine.close_all()` được đăng ký bằng `threading._register_atexit` (chạy *trước* khi Python chờ các luồng) — không có hook này app treo lúc thoát nếu còn bot sống.
- Trên Windows tiến trình chạy với `CREATE_NO_WINDOW` (không nháy cửa sổ console trong GUI).
- Nếu tiến trình cha bị giết, Stockfish nhận EOF trên stdin và tự thoát.

## Thay đổi hạ tầng chung (nhỏ, có test)

`tournament/process_player.py`: worker đo RAM bằng bộ đếm của chính nó, không thấy tiến trình con. Lúc `stop`, worker cộng thêm `bot.external_memory_bytes()` (nếu bot có) rồi gọi `bot.close()`. B9 trả **đỉnh working set (Windows) / VmHWM (Linux) của tiến trình Stockfish**. Nhờ đó cột *Bộ nhớ* của Xếp hạng AI tính đúng (≈ 230–330 MB, chủ yếu là mạng NNUE ~109 MiB và binary) thay vì chỉ ~12 MB của phần Python. Bot khác không bị ảnh hưởng.

## Luật giải và mốc 150 nửa nước

- Luật cờ (chiếu hết, hòa pat, thiếu quân, lặp 3 lần, 50 nước, nhập thành, bắt tốt qua đường, phong cấp dưới) do Stockfish xử lý trên **toàn bộ lịch sử ván**; adapter kiểm lại tính hợp lệ.
- Stockfish **không biết** mốc `max_plies = 150` của giải. Phân tích: đối thủ trong giải yếu hơn rất nhiều, B9 chiếu hết trung bình sau ~60–65 nửa nước (xem `BENCHMARK_RESULTS.md`); trong mọi ván đo không có ván nào bị xử hòa vì mốc nửa nước. Vì vậy **không thêm** heuristic theo mốc (không có lợi đo được, lại có rủi ro làm yếu cờ thường). Stockfish vốn đã ưu tiên chiếu hết nhanh nhất, tránh hòa pat khi thắng và tìm hòa (lặp/chiếu vĩnh viễn) khi thua — có test cho từng trường hợp.

## Cấu hình (`[bots.bench_super_alphabeta_nnue]`)

| Khóa | Mặc định | Ý nghĩa |
|---|---|---|
| `max_think_time_s` | 1.0 | Trần thời gian mỗi nước; `<= 0` = không giới hạn (khi đó dừng ở độ sâu 20). Giải đấu ghi đè bằng `tournament.max_think_time_s` |
| `depth` | — | Trần độ sâu (giải đấu ép khi `tournament.depth > 0`) |
| `fast_mode` | false | Test: 50 ms mỗi nước |
| `threads` | 1 | Số luồng Stockfish. 1 = công bằng với các bot Python một luồng, và tất định |
| `hash_mb` | 16 | Bảng băm Stockfish (MB) |
| `time_safety_s` | 0.03 | Khoảng an toàn cố định trước trần |
| `engine_path` | — | Engine khác (tương đối = theo gốc repo); hoặc biến môi trường `BENCH9_ENGINE_PATH`. Đường dẫn riêng từng máy ghi trong `local.toml` |
| `nnue_path` | — | Mạng `.nnue` khác (mặc định: mạng chính thức nhúng sẵn) |
| `syzygy_path` | — | Thư mục tablebase Syzygy; không tồn tại thì tắt (ghi log) |
| `seed` | — | Nhận nhưng không dùng: Stockfish 1 luồng không có ngẫu nhiên, không dùng sách khai cuộc |

Một instance luôn tất định khi đặt `depth` (1 luồng); khi tìm theo thời gian, nước có thể khác nhau theo tải CPU.
