# Benchmark 9 — Nhật ký triển khai (2026-10-11)

## Phase 0 — Khảo sát repo

- Baseline trước khi sửa: `pytest` 653 passed, 2 skipped.
- Điểm tích hợp: `ai.registry` (`BENCHMARK_BOTS`, `BENCHMARK_LEVELS`), import-linter (`pyproject.toml`), `default.toml`, locale `players.<id>`, `tournament.process_player` (đo RAM theo tiến trình), GUI đọc `list_bots(max_benchmark_level=…)`.
- Ràng buộc phát hiện:
  - `another/tests/ai/test_benchmarks.py` và `test_bot_contract.py` (có sẵn) tạo **mọi** benchmark; `test_benchmarks.py` không bỏ qua `BotUnavailableError` → CI **bắt buộc** có binary engine → thêm bước cài engine vào CI.
  - `another/tests/ai/test_registry.py` so khớp chính xác danh sách benchmark → đăng ký B9 buộc phải sửa test này (thêm id vào danh sách và vào bộ lọc thế hệ ≤ 5). Đây là sửa test có sẵn duy nhất cho B9; được nêu rõ trong báo cáo.
  - Worker đo RAM không thấy tiến trình con → cần hook nhỏ trong `process_player.py`.
- Tài liệu lệch so với code: `CONTEXT.md` ghi "mặc định 7 → 19 bot" trong khi `default.toml` đặt `max_level = 4`; đã sửa câu đó.

## Phase 1 — Engine nền

- Upstream: `sf_19` là bản stable mới nhất (2026-09-05); có bản dev 2026-10-10 nhưng không dùng (không có số đo).
- Stockfish 19 phát hành **binary universal** (tự chọn SIMD) → không cần build theo CPU; `make`/toolchain không cần.
- Tải bản Windows, SHA-256 archive khớp digest GitHub; chạy thử: `go movetime 1000` → độ sâu 23, ~640 knps (1 luồng, i5-12500H). NNUE nhúng: `nn-1a298aa575a0.nnue` (109 MiB).

## Phase 2–3 — Package B9 và tích hợp

- `bench9/` (provenance, engine, bot, install), registry thế hệ 9, import-linter, `default.toml`, locale, CI, `.gitignore`.
- Lỗi tìm ra và đã sửa trong lúc làm:
  1. **App treo khi thoát** nếu còn bot B9 sống: luồng nền python-chess không phải daemon, finalizer `atexit` chạy *sau* khi Python chờ luồng. Sửa: `threading._register_atexit(close_all)`.
  2. **NNUE hỏng vẫn tạo được bot**: Stockfish chỉ nạp mạng ở `go` đầu. Sửa: `go depth 1` lúc khởi động, đọc `info string NNUE evaluation using …`/`ERROR`.
  3. In đường dẫn có tiếng Việt ra console cp1252 làm trình cài đặt lỗi → `stdout.reconfigure(errors="replace")`.
- GUI: kiểm headless với `max_level = 9` — B9 có ở Người vs Bot, Bot vs Bot; bấm chọn B9 và Bắt đầu mở được ván.

## Phase 4 — Thời gian và tài nguyên

- Qua `ProcessPlayer` (như giải), 60 nước, 1 s: trung bình 0,958 s, tối đa 0,981 s, 0 nước vượt trần, độ sâu TB 23,8.
- Trong trận 400 ván (8 ván song song): nửa với B8 — tối đa 0,994 s, 0 vượt; nửa với B7 — 23/≈6 300 nước vượt trần (tối đa 1,134 s), **trùng đúng lúc chạy pytest + render GUI song song** (nps tụt từ ~650k xuống 73k). → Tăng `time_safety_s` mặc định 0,02 → 0,03 s. Trong giải thật các ván chạy tuần tự nên không có mức tải đó.
- RAM: tiến trình Stockfish 210–330 MB (mạng + binary + hash 16 MB), phần Python ~12 MB. Hash 1 MB không giảm đáng kể → giữ 16 MB.
- Threads: giữ 1 (công bằng với bot Python một luồng, tất định). Không đo 2+ luồng vì sẽ vi phạm "cùng chính sách cấp luồng" của giải; với các đối thủ hiện có cũng không thể đo được khác biệt (B9 đã thắng 100 %).
- Sách khai cuộc / Syzygy: không bật mặc định — không có lợi ích đo được (B9 đã thắng mọi ván bằng chiếu hết trước nửa nước 150); `syzygy_path` có sẵn và tự tắt khi thiếu thư mục.

## Phase 5 — Kaggle

Đánh giá: không có đường cải thiện đáng tin → không tạo notebook, giữ mạng chính thức (`KAGGLE_NNUE.md`).

## Phase 6 — Đo sức mạnh

`another/tools/bench9_strength.py`; kết quả ở `BENCHMARK_RESULTS.md`.

## Thay đổi ngoài phạm vi B9 (theo yêu cầu trong lúc làm)

- Bố cục chứa tối đa 25 bot: `setup_human.py` (3 cột khi > 20 bot), `leaderboard.py`, `tournament.py`, `tournament_history.py`. Ảnh xem trước: `.preview/bots25/`.
- Bỏ hẳn `bench5_grok`, `bench6_grok`, `bench5_gemini` (code, registry, config — cả danh sách `tournament.bots` trong `local.toml` —, locale, các danh sách id trong test có sẵn).
