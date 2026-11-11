# Benchmark 9 · Super Alpha-Beta NNUE

**B9 là benchmark kế thừa engine, không tự viết.** Mọi thứ về tìm kiếm và đánh giá NNUE là của
**Stockfish 19** chính thức (GPLv3). Dự án chỉ viết adapter UCI, trình cài đặt, cấu hình, test và công cụ
đo sức mạnh.

| Thuộc tính | Giá trị |
|---|---|
| `bot_id` / lớp | `bench_super_alphabeta_nnue` / `ai.benchmarks_extension.bench9.bot:SuperAlphaBetaNNUEBot` |
| Thế hệ | 9: hiện khi `[benchmarks] max_level >= 9` |
| Engine | Stockfish `sf_19` (commit `edb0d9d`, 2026-09-05), NNUE nhúng `nn-1a298aa575a0.nnue` (109 MiB) |
| Ghim bản phát hành | `bench9/provenance.py`: URL, SHA-256 archive và binary |

## Cài đặt

Binary (~100 MB) không được commit. Mỗi máy cài một lần:

```bat
set PYTHONPATH=backend
.venv\Scripts\python -m ai.benchmarks_extension.bench9.install
```

Trình cài đặt làm các bước sau:
1. Chọn bản **universal** cho Windows/Linux × x86-64/arm64. Binary tự chọn tập lệnh SIMD lúc chạy.
2. Kiểm SHA-256.
3. Giải nén binary, `Copying.txt`, `AUTHORS`, `README.md` vào `bench9/engine/`.
4. Smoke test UCI, kiểm tên mạng NNUE.

Tùy chọn: `--check`, `--force`, `--dest <thư mục>`.

- Nền tảng khác: tự build `sf_19`, rồi đặt `engine_path` trong `local.toml` hoặc biến môi trường
  `BENCH9_ENGINE_PATH`.
- Khi chơi không tải gì. Thiếu engine thì báo `BotUnavailableError` kèm lệnh cài.
- CI cache `bench9/engine` (khóa = hash `provenance.py`) và cài trước pytest, vì `test_benchmarks.py` và
  `test_bot_contract.py` tạo mọi benchmark. Các test cần engine mang dấu `needs_engine`.

## Hoạt động

**Thời gian mỗi nước.** `movetime = max_think_time_s − time_safety_s − overhead`, trong đó `overhead`
là độ trễ lớn nhất đo được ở 12 nước gần nhất. Gửi `position fen … moves <toàn bộ lịch sử>`.
Hạn chót cứng: sau `movetime + 1 s` mà chưa có `bestmove` thì giết tiến trình.

**Lỗi:**
- Thiếu hoặc hỏng binary, hoặc NNUE hỏng: `BotUnavailableError` ngay khi tạo bot (adapter chạy
  `go depth 1` để ép nạp mạng).
- Engine crash giữa ván: khởi động lại **một lần** rồi tìm lại. Hỏng tiếp thì `RuntimeError`.
- **Không bao giờ** đi nước ngẫu nhiên.

**Tiến trình:** mỗi instance bot có một tiến trình Stockfish. Tiến trình được đóng qua `close()`,
`weakref.finalize` hoặc `threading._register_atexit` (luồng của python-chess không phải daemon). Trên
Windows dùng `CREATE_NO_WINDOW`.

**RAM:** `process_player.py` cộng `bot.external_memory_bytes()`, tức đỉnh RAM của tiến trình Stockfish
(≈ 330 MB khi chạy một mình).

**Mốc 150 nửa nước:** Stockfish không biết mốc này. Trong mọi ván đo không ván nào chạm mốc, nên không
thêm heuristic nào.

## Cấu hình `[bots.bench_super_alphabeta_nnue]`

| Khóa | Mặc định | Ý nghĩa |
|---|---|---|
| `max_think_time_s` | 1.0 | Trần thời gian mỗi nước; `<= 0` = dừng ở độ sâu 20 |
| `depth` | — | Trần độ sâu |
| `fast_mode` | false | Test: 50 ms mỗi nước |
| `threads` / `hash_mb` | 1 / 16 | 1 luồng để công bằng với bot Python và tất định |
| `time_safety_s` | 0.03 | Biên an toàn trước trần |
| `engine_path`, `nnue_path`, `syzygy_path` | — | Engine, mạng, tablebase khác. Đường dẫn riêng của máy ghi trong `local.toml` |

## Kết quả (2026-10-11, i5-12500H, 1 s/nước, khai cuộc 2 nửa nước ghép cặp đổi màu)

Công cụ đo: `another/tools/bench9_strength.py`; dữ liệu thô ở `database/data/bench9_strength/`.

| Đối thủ | Ván | Thắng/Hòa/Thua | Elo (cận dưới 95 %) |
|---|---|---|---|
| B7 Dragon, B8 Luna | 200 + 200 | 400/0/0 | > +729 |
| B6 (3 bản), B5 (3 bản), B4, B2, Deep RL (2 bản) | 50 mỗi đối thủ | 500/0/0 | > +484 |

- Cả 900 ván kết thúc bằng chiếu hết, trung bình 32–68 nửa nước.
- Thời gian nghĩ trung bình 0,85–0,96 s.
- 30/≈27.000 nước vượt trần; tất cả rơi vào lúc máy quá tải vì chạy pytest/GUI song song. Trên máy rảnh,
  không nước nào vượt trần.

## Giấy phép và mạng NNUE

- **Giấy phép:** không phân phối binary trong repo; trình cài đặt tải bản chính thức kèm `Copying.txt`
  (GPLv3). Không sửa mã Stockfish; mã nguồn tương ứng là tag `sf_19` ở upstream.
- **Không train NNUE riêng trên Kaggle**, vì ngân sách và dữ liệu nhỏ hơn bản chính thức hàng nghìn lần,
  và không đối thủ nào trong dự án đo được khác biệt.
- **Muốn thử mạng khác:** khai báo một bot riêng trong `local.toml` với `nnue_path`, rồi so trực tiếp với
  B9 gốc bằng `bench9_strength.py`. Chỉ đổi mạng mặc định khi cận dưới 95 % > 0 Elo.
