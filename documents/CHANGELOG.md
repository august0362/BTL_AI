# CHANGELOG — Chess AI Tournament

> Mới nhất ở trên. Mỗi mục: ngày, phiên bản, loại (Added / Changed / Decided / Deferred / Fixed). Theo [Keep a Changelog](https://keepachangelog.com/), số phiên bản SemVer.

## [Unreleased]

### Added — Bot benchmark (CONTEXT §4.9)
- **B1–B4** (`backend/ai/benchmarks/`), thang phân loại sức mạnh: `bench_random` (ngẫu nhiên đều), `bench_alphabeta3` (alpha-beta sâu 3, eval `ai.baseline`), `bench_alphabeta_tt` (+ TT Zobrist, sắp nước MVV-LVA/killer), `bench_alphabeta_custom` (eval chọn qua `evaluator`). B4: null-move + LMR từ độ sâu còn lại ≥ 2 (trước chỉ khi `depth >= 4`).
- **B5** (5 bot: GPT, Gemini, DeepSeek, Grok — mỗi bản theo một đề xuất — và Tổng hợp): engine PVS dùng hết thời gian; kiểm tra đồng hồ mỗi 256 node (trước 1024), sau đó 128. Test: `another/tests/ai/test_benchmark5.py`.
- **B6** (4 bot) và **B7 "Dragon"**: engine PVS chọn lọc (PST cộng dồn, sinh nước theo giai đoạn, history nhiều tầng, singular/ProbCut/IID, correction history, lazy eval, sách khai cuộc viết tay). Test: `another/tests/ai/test_benchmark6.py`.
- **B8 "Luna"** (`bench8_luna`, thế hệ 8): lõi Dragon + SEE theo ngưỡng; xác minh LMR, cổng an toàn tốt tiến xa, mốc 150 nửa nước + KPK có công tắc nhưng mặc định tắt vì không vượt B7 (100 và 400 ván, CONTEXT §4.9.3). Test: `another/tests/ai/test_benchmark8.py`.
- **Tách module:** B5–B8 mỗi thế hệ một package (`backend/ai/bench5/` … `bench8/`), chỉ nối qua `ai.registry`; `[benchmarks] max_level` bật/tắt theo thế hệ (`registry.BENCHMARK_LEVELS`, `list_bots(max_benchmark_level=...)`) cho màn chọn bot, Elo và Xếp hạng AI. Bố cục các màn đó co lại cho 14–20 bot.
- Tên hiển thị bot đặt trong config: `[bots.<id>] display_name`.

### Added — Giải Xếp hạng AI (CONTEXT §4.9.4, §5.9)
- `backend/tournament/round_robin.py`, `tournament_config.py` (bảng `[tournament]`), `tournament_history.py` ("Trận Chiến Lần n", tách khỏi Elo/ván thường); GUI: mục **Xếp hạng AI** trong menu (`screens/tournament.py`, `screens/tournament_history.py`, `tournament_controller.py`, `tournament_view.py`, `widgets/progress_bar.py`) — bảng hiện sẵn, 2 nút dưới bảng, thanh tiến trình tổng (cả nửa nước đang đi qua `on_ply`), lịch sử kèm tỉ số đối đầu. Bot mới mỗi ván, dừng giữa chừng an toàn, hạng "1224".
- Trần thời gian mỗi nước `[tournament] max_think_time_s` (1,0 s; 0 = không giới hạn), benchmark sâu dần và tự dừng đúng hạn; `depth = 0` mặc định không ép độ sâu.
- **Lượt thách đấu:** lần lượt từng bot thách đấu mọi bot khác và cầm Trắng; `matches_per_pair` = số ván mỗi lượt, mỗi cặp `2 × matches_per_pair` ván (thay cho chia xen kẽ Trắng/Đen, rồi "nửa đầu Trắng").
- **Cột Bộ nhớ:** mỗi bot chạy trong tiến trình riêng mỗi ván (`process_player.py`), hệ điều hành đo đỉnh RAM gồm bộ nhớ tạm lúc nghĩ; trung bình MB/ván; `[tournament] measure_memory`. Test: `another/tests/tournament/test_process_player.py`.
- **Tổng** = điểm ván + (thời gian TB − của bot)/100 + (bộ nhớ TB − của bot)/100 + thưởng thắng ngược; tạm tính khi chạy, tính lại một lần khi kết thúc.
- **Thưởng thắng ngược** chốt theo cặp: bot `sum_e` thấp hơn được `(12 % + 0,5 %·n) × khoảng cách` khi bot cao hơn thua nó n ván, `(6 % + 0,05 %·d) × khoảng cách` cho d ván hòa (thay bản đầu: 12 %/8 % Tổng đối thủ lúc bắt đầu ván, phụ thuộc thứ tự).
- Bấm tiêu đề cột để sắp xếp, sau 5 s tự về theo Tổng.
- Ước tính thời gian còn lại ở góc phải trên (làm mượt hàm mũ theo từng bot, `[tournament] eta_smoothing`). Test: `another/tests/tournament/test_eta.py`.
- Test: `another/tests/ai/test_benchmarks.py`, `another/tests/tournament/test_round_robin.py`, `test_tournament_history.py`, `another/tests/gui/test_tournament_view.py`, `test_tournament_smoke.py`.

### Changed
- **ELO-1:** bảng Elo và màn Người vs Bot / Bot vs Bot gồm cả benchmark (`list_bots(include_benchmarks=True)`) và `human`, bỏ `baseline`; giải Xếp hạng AI không ghi Elo.
- `registry.py`: `BENCHMARK_BOTS` (opt-in), `list_bots(include_benchmarks=...)`; mặc định không đổi. `baseline.py`: tách `evaluate(board)` dùng chung (hành vi không đổi). `pyproject.toml`: các package benchmark vào contract "bot độc lập".

### Fixed
- Nhãn "Đang chạy" của Xếp hạng AI hiện ván đang đấu (trước là ván vừa xong), bot thách đấu đứng trước.
- GUI không còn luôn hiện bot Trắng đang nghĩ (snapshot có `thinking_color`, `first_is_white`).

### Decided
- Bot chưa có code thật chạy **baseline ngẫu nhiên** (`backend/ai/baseline.py`), hậu tố "(baseline)", thay cho `BotUnavailableError("not implemented")`.

## [0.6.0] — 2026-10-04 · Giao diện v2, 24 theme, tài liệu, arena cục bộ — 280 test xanh

### Added
- Giao diện v2 (Codex): tên "Chess"; DPI awareness + vẽ ở độ phân giải thật (hết mờ); `render.py`, `theme.py`; chuẩn thiết kế (lưới 8 px, thang chữ, trạng thái nút, một nút chính mỗi màn).
- 24 theme: 6 có tên + 18 Color Hunt tự sinh từ tên file trong `frontend/resource/theme`; đạt WCAG AA; ô cờ dịu hơn; chọn trong Cài đặt (xem trước khi rê chuột).
- Tài liệu: README đầy đủ, `documents/USER_GUIDE.md` (ảnh `documents/images/`), `documents/CONTRIBUTING.md`.
- `another/local_tools/arena.py` (chỉ trên máy): vòng tròn, xuất CSV/PGN, Elo riêng. `run.bat`, `another/scripts/test.bat`.

### Changed
- Màu bàn cờ theo theme; bỏ `[board]`, thêm `ui.theme`.
- Python **3.14 → 3.13** (`.python-version`, `pyproject.toml`, CI, `run.bat`, README, AGENTS.md, CONTEXT §9): máy nhóm có sẵn 3.13, đủ wheel, tránh lệch hành vi.
- QA ở mức đơn giản (một lần chạy bộ kiểm tra mỗi lần gộp).

## [0.5.0] — 2026-10-03 · GUI đầy đủ (M4), script Git, hạ tầng Deep RL — 264 test xanh

### Added
- M4 (Codex): Bot vs Bot (1 ván / Bo3, tạm dừng, tốc độ), Lịch sử (cuộn, xuất PGN), Xem lại, Xếp hạng (reset), Cài đặt (ngôn ngữ, âm thanh, tốc độ xem lại; lưu `local.toml`), âm thanh tự sinh.
- `another/scripts/push.bat`, `pull.bat` (Codex viết; Claude test với remote cục bộ).
- Hạ tầng Option 4 (Codex): `backend/ai/deep_rl/` encoding, env, opponents, evaluate, metrics, weights, bot adapter, khung `user/` + notebook Kaggle; `documents/RL_LEARNING_GUIDE.md`.

### Changed
- Codex viết cả code lẫn test; Claude đặc tả, prompt, review, gộp. `AGENTS.md`: không sửa/xóa test cũ, được thêm test mới.
- Option 4: lõi RL (`deep_rl/user/`) do @august0362 tự viết.

### Fixed (QA qua ảnh chụp không màn hình)
- Lịch sử chỉ hiện 7/20 ván; icon loa hiện ô vuông; nút Tạm dừng bị nút Tốc độ đè.

## [0.4.0] — 2026-10-03 · GUI MVP (M3) — 238 test xanh

### Added
- `controller.py` (luồng nền, snapshot, `waiting_for_human`), `app.py`, `screens/` (menu, setup_human, game), `widgets/`, `assets_loader.py`; `python main.py` chạy được Người vs Bot (bot ngẫu nhiên). Code do Codex viết.
- `another/tools/render_previews.py`: xuất ảnh các màn (vi/en) vào `.preview/` không cần màn hình.
- `documents/DEEP_RL_DESIGN.md` (nháp thiết kế Option 4). Test: `test_controller.py`, `test_app_smoke.py`, test i18n chống lỗi mã hóa.

### Fixed
- Chuỗi `menu.coming_soon` hỏng mã hóa (PowerShell ghi sai), chữ tràn nút bot, cột thông tin trùng ở màn Chuẩn bị, mũi tên panel hiện ô vuông, nhãn White/Black chưa dịch, dòng trạng thái bị đè.

## [0.3.0] — 2026-10-03 · Code M1, M2, logic M3 (Codex) — 219 test xanh

### Added
- `backend/core/` (types, game_state, material, config), `backend/ai/` (base_bot, registry, random_bot, khung 4 bot), `backend/tournament/` (players, records, match_runner, series, ranking, history), `frontend/gui/` logic (scaling, board_geometry, move_input, game_info, i18n). Codex viết; Claude review, gộp.
- `AGENTS.md` (không sửa test, chỉ sửa file được giao, venv, `--basetemp`, `from __future__ import annotations`). `test_records.py` bắt lỗi `records.py` không import được trên 3.13.

### Fixed
- `records.py`: thêm `from __future__ import annotations` (NameError trên 3.13).

### Decided
- Codex chạy được từ Claude nhưng sandbox không ghi được dưới Desktop → mỗi task chạy trong bản sao `C:/Users/admin/btlai-wt/<ID>`, review rồi chỉ chép về file của task.
- Coverage `core` + `tournament` 92 %; import-linter 3/3; 47 skip còn lại là 4 bot thành viên + hygiene (cần git).

## [0.0.3] — 2026-10-03 · Đặc tả M2, tài nguyên + logic GUI, prompt nhiều agent

### Added
- Test đặc tả M2 `another/tests/tournament/` (players, match_runner, series, ranking, history) + `fakes.py` (kiểm bằng bản tham chiếu không commit: 151 test xanh, 3 contract) và logic GUI `another/tests/gui/` (scaling, board_geometry, move_input, game_info, i18n).
- Bộ quân rhosgfx (SVG + PNG 256 px), `another/tools/svg_to_png.py`, `CREDITS.md`; `locales/vi.toml`, `en.toml` (test: tham số `{}` khớp, đủ kiểu kết thúc ván và tên bot).
- Prompt Codex M2-1, M2-2, M2-3, M3-A + `documents/codex/README.md` (chia đợt cho nhiều agent song song).

### Changed
- CONTEXT 0.3.0: API chi tiết §4.6–4.8 (`records.py` tách riêng; MatchRunner có pause/resume, bắt mọi lỗi bot thành ABORTED kèm `error`); thêm mục module GUI thuần logic.
- Đổi `frontend/gui/i18n/` thành `locales/` (trùng tên module `i18n.py`).

### Decided
- Bot lỗi hoặc trả nước không hợp lệ → ván ABORTED (không tính xếp hạng), GUI không crash; không thêm Termination mới.
- Claude chỉ viết đặc tả/test/prompt; code giao Codex (yêu cầu của Product Owner).

## [0.0.2] — 2026-10-03 · Scaffold, CI, test đặc tả M1

### Added
- Khung thư mục, package bot rỗng; `.gitignore`, `.gitattributes` (LF), `.python-version` (3.14), `pyproject.toml` (ruff, pytest, coverage, import-linter), requirements, `default.toml`, `README.md`, `main.py`; `.github/CODEOWNERS`, PR template, `workflows/ci.yml` (job `ci`).
- Test đặc tả M1 (`core`, `ai`, `architecture`) + `require_module` (module chưa có thì skip); prompt Codex M1-A, M1-B.

### Changed
- Gom tài liệu vào `documents/` (README ở gốc). CONTEXT 0.2.0: API `GameState` (`push` trả SAN, `fen`, `starting_fen`, `ply_count`, `claim_draw`), `IllegalMoveError`/`GameOverError`, `core/config.py`, config test hợp đồng (`fast_mode`, `allow_random_init`, `seed`).

### Decided
- Python 3.14 (bản mới nhất có wheel `pygame-ce 2.5.8`, `torch 2.14.1`) — sau đổi sang 3.13 (0.6.0). `tomli-w` để ghi `local.toml`. Lặp 3 lần / 50 nước bằng `is_repetition(3)` / `halfmove_clock >= 100`, **không** `outcome(claim_draw=True)` (kết thúc sớm 1 nửa nước). CI dùng `torch` CPU. Tên contract import-linter ASCII (console Windows lỗi tiếng Việt). CODEOWNERS dòng `mcts` tạm để `@august0362` (username sai làm GitHub báo lỗi).

## [0.0.1] — 2026-10-03 · Chốt yêu cầu

### Added
- `CONTEXT.md`, `MILESTONES.md`, `TASKS.md`, `CHANGELOG.md`.

### Decided
- **Kiến trúc:** 4 module `core` ← `ai` ← `tournament` ← `gui`; bot cấm import lẫn nhau (import-linter). Hợp đồng `BaseBot.select_move(board) -> Move` trên bản sao, `last_search_info` tùy chọn, `BotUnavailableError`. Bot nạp động qua `registry.py` (`"module:Class"`). `random_bot` cho test/debug (ẩn trên GUI). `HumanPlayer` (hàng đợi) để một `MatchRunner` dùng cho cả hai chế độ. Tên package thường + gạch dưới (tránh lỗi hoa/thường Windows–Linux).
- **Sản phẩm:** Pygame (`pygame-ce`), canvas 960×640 (bàn 640 + panel 320), resize giữ tỷ lệ. Người vs Bot (chọn bot, màu Trắng/Đen/Ngẫu nhiên, 1 ván) và Bot vs Bot (2 bot độc lập, được trùng, 1 ván / Best of 3 đấu đủ 3 ván, đổi màu luân phiên, ván 3 bốc thăm, chung khai cuộc; 1/0,5/0, bằng điểm thì hòa trận). Không Undo, không đổi phe trong ván. Khai cuộc ngẫu nhiên chỉ Bot vs Bot (2 nửa nước). Luật hòa chuẩn tự áp dụng + giới hạn 300 nửa nước. W/D/L + **Elo** (1200, K=32) cho bot và hồ sơ chung "Người chơi", có reset; không tính ván dừng, ván bot tự đấu, ván có bot debug. Lịch sử 20 ván, xem lại, xuất PGN. Panel 6 mục thu gọn được; thanh đánh giá theo chênh lệch quân. Âm thanh mặc định tắt. Song ngữ vi/en. Bộ quân rhosgfx (CC0). Cấu hình TOML `default.toml` + `local.toml` (gitignored).
- **Option 4:** PyTorch, huấn luyện Kaggle; trọng số qua GitHub Release, tự tải + kiểm sha256; checkpoint trung gian ở Kaggle; Elo chỉ để đánh giá, không phải reward.
- **Quy trình:** repo public `august0362/BTL_AI`, admin `@august0362`; cấm push thẳng `main`, merge qua PR khi CI xanh và branch cập nhật; PR thành viên cần 1 approve của `@august0362`, PR admin tự merge khi CI xanh; `CODEOWNERS` là nơi duy nhất ghi username duyệt; CI: ruff, import-linter, pytest, coverage ≥ 80 % cho core/tournament, hợp đồng bot, i18n, config, hygiene, cài đặt sạch, GUI smoke; thành viên Option 1–3 tự quản thuật toán, chỉ bắt buộc qua test hợp đồng.

### Deferred
- OI-1 giới hạn thời gian · OI-2 dừng cứng bot · OI-3 giải round-robin cá nhân · OI-4 username Option 3 · OI-5 tinh chỉnh `max_plies`/khai cuộc · OI-6 thanh đánh giá theo bot.
