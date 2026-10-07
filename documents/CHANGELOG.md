# CHANGELOG — Chess AI Tournament

> Ghi theo thứ tự mới nhất ở trên. Mỗi mục có: ngày, phiên bản, loại (Added / Changed / Decided / Deferred / Fixed).
> Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/), đánh số theo SemVer.

## [Unreleased]

### Added
- **Bot benchmark** (`backend/ai/benchmarks/`) làm thang phân loại sức mạnh: `bench_random` (ngẫu nhiên đều), `bench_alphabeta3` (alpha-beta sâu 3, eval `ai.baseline`), `bench_alphabeta_tt` (thêm bảng chuyển vị Zobrist + sắp nước MVV-LVA/killer), `bench_alphabeta_custom` (eval mô-đun chọn được qua `evaluator`).
- **Giải vòng tròn xếp hạng AI**: `backend/tournament/round_robin.py` (mọi cặp, chia đều Trắng/Đen, 20 ván mỗi cặp, điểm 1/0.5/0, hạng "1224", phá hòa bằng tổng thời gian suy nghĩ, dừng giữa chừng an toàn, bot mới mỗi ván), `tournament_config.py` (đọc bảng `[tournament]`), `tournament_history.py` (lưu "Trận Chiến Lần n", giữ 10 bản gần nhất — tách khỏi Elo/ván thường).
- **GUI**: mục **Xếp hạng AI** trong Board Menu (dưới "Bot vs Bot", trên "Lịch sử") với `frontend/gui/screens/tournament.py`, `screens/tournament_history.py`, `tournament_controller.py` (luồng nền + nút Dừng đấu), `tournament_view.py`, `widgets/progress_bar.py`; bảng xếp hạng hiện sẵn khi chưa đấu, 2 nút nằm dưới bảng, thanh tiến trình tổng, màn lịch sử riêng kèm tỉ số đối đầu.
- Config: bảng `[tournament]` và `[bots.bench_*]` trong `backend/config/default.toml`.
- Giới hạn thời gian suy nghĩ mỗi nước: `[tournament] max_think_time_s` (mặc định 1.0s, 0 = không giới hạn); bot benchmark sâu dần (`alpha_beta_iterative`) và tự dừng đúng hạn, trả nước của tầng sâu nhất đã tính xong. `[tournament] depth = 0` mặc định **không ép** độ sâu để bot thành viên giữ cấu hình riêng (nhanh hơn nhiều).
- Thanh tiến trình hiển thị cả nửa nước đang đi (`ván x/y · nước a/b`) qua callback `on_ply`.
- Test: `another/tests/ai/test_benchmarks.py`, `another/tests/tournament/test_round_robin.py`, `test_tournament_history.py`, `another/tests/gui/test_tournament_view.py`, `test_tournament_smoke.py`.

### Changed
- **Elo + chọn bot cho đủ 8 bot** (ELO-1): bảng Xếp hạng Elo gồm 8 bot (4 thành viên + 4 benchmark) và `human`, bỏ `baseline`; màn Người vs Bot và Bot vs Bot chọn được cả 8 bot (`list_bots(include_benchmarks=True)`), bố cục xếp lại cho vừa. Giải Xếp hạng AI vẫn không ghi vào Elo.
- `backend/ai/registry.py`: thêm `BENCHMARK_BOTS` (opt-in) và tham số `list_bots(include_benchmarks=...)`; mặc định không đổi.
- `backend/ai/baseline.py`: tách hàm dùng chung `evaluate(board)`; `RandomBaselineBot` gọi lại hàm này (hành vi không đổi).
- `pyproject.toml`: thêm `ai.benchmarks` vào contract "bot độc lập".

### Decided
- Bot chưa có code thật chạy **baseline ngẫu nhiên** (`backend/ai/baseline.py`), hiển thị hậu tố "(baseline)"; thay cho `BotUnavailableError("not implemented")`.

## [0.6.0] — 2026-10-04 · Giao diện v2, 24 theme, tài liệu, arena cục bộ — 280 test xanh

### Added
- Giao diện v2 (Codex): tên "Chess"; DPI awareness + vẽ ở độ phân giải thật (hết mờ); `frontend/gui/render.py`, `frontend/gui/theme.py`; chuẩn thiết kế (lưới 8 px, thang chữ, trạng thái nút, một nút chính mỗi màn).
- 24 theme: 6 theme có tên + 18 theme Color Hunt tự sinh từ tên file trong `frontend/resource/theme`; mọi theme đạt tương phản WCAG AA; ô cờ được làm dịu; chọn trong Cài đặt (xem trước khi rê chuột).
- Tài liệu: README đầy đủ, `documents/USER_GUIDE.md` (có ảnh `documents/images/`), `documents/CONTRIBUTING.md`.
- `another/local_tools/arena.py` (chỉ trên máy, không push): bot đấu vòng tròn, xuất CSV/PGN, Elo riêng.
- `run.bat`, `another/scripts/test.bat`; Python mục tiêu 3.13.

### Changed
- Màu bàn cờ lấy theo theme; bỏ mục `[board]` trong config, thêm `ui.theme`.
- QA ở mức đơn giản theo yêu cầu (một lần chạy bộ kiểm tra / lần gộp).

### Changed
- Python mục tiêu **3.14 → 3.13** (`environments/.python-version`, `pyproject.toml`, CI, `run.bat` ưu tiên 3.13, README, AGENTS.md, CONTEXT §9). Lý do: máy nhóm có sẵn 3.13, đủ wheel, tránh lệch hành vi giữa hai phiên bản.

## [0.5.0] — 2026-10-03 · GUI đầy đủ (M4), script Git, hạ tầng Deep RL — 264 test xanh

### Added
- M4 (Codex): Bot vs Bot (1 ván / Bo3, tạm dừng, tốc độ), Lịch sử (cuộn, xuất PGN), Xem lại, Xếp hạng (reset), Cài đặt (ngôn ngữ, âm thanh, tốc độ xem lại; lưu `backend/config/local.toml`), âm thanh tự sinh.
- `another/scripts/push.bat`, `another/scripts/pull.bat` (Codex viết; Claude test với remote cục bộ).
- Hạ tầng Option 4 (Codex): `backend/ai/deep_rl/` encoding, env, opponents, evaluate, metrics, weights, bot adapter, khung `user/` + notebook Kaggle. `documents/RL_LEARNING_GUIDE.md`.

### Changed
- Phân công: Codex viết cả code lẫn test; Claude chỉ đặc tả, prompt, review, gộp. `AGENTS.md`: không sửa/xoá test cũ, được thêm test mới.
- Option 4: lõi RL (`backend/ai/deep_rl/user/`) do @august0362 tự viết.

### Fixed (QA qua ảnh chụp không màn hình)
- Lịch sử chỉ hiện 7/20 ván; icon loa hiện ô vuông; nút Tạm dừng bị nút Tốc độ đè.

## [0.4.0] — 2026-10-03 · GUI MVP (M3) — 238 test xanh

### Added
- `frontend/gui/controller.py` (GameController: luồng nền, snapshot, `waiting_for_human`), app Pygame `frontend/gui/app.py`, `frontend/gui/screens/` (menu, setup_human, game), `frontend/gui/widgets/`, `frontend/gui/assets_loader.py`; `python main.py` chạy được Người vs Bot (bot ngẫu nhiên). Code do Codex viết.
- `another/tools/render_previews.py`: xuất ảnh các màn hình (vi/en) vào `.preview/` ở chế độ không màn hình để QA.
- `documents/DEEP_RL_DESIGN.md`: bản nháp thiết kế Option 4.
- Test: `another/tests/gui/test_controller.py`, `test_app_smoke.py`; test i18n chống lỗi mã hóa.

### Fixed
- QA phát hiện và sửa: chuỗi `menu.coming_soon` hỏng mã hóa (PowerShell ghi sai), chữ tràn nút bot, cột thông tin trùng lặp ở màn Chuẩn bị, mũi tên panel hiện ô vuông, nhãn White/Black chưa dịch, dòng trạng thái bị đè.

## [0.3.0] — 2026-10-03 · Code M1, M2, logic M3 (Codex) — 219 test xanh

### Added
- `backend/core/` (types, game_state, material, config), `backend/ai/` (base_bot, registry, random_bot, khung 4 bot), `backend/tournament/` (players, records, match_runner, series, ranking, history), `frontend/gui/` logic (scaling, board_geometry, move_input, game_info, i18n). Code do Codex viết; Claude review và gộp.
- `AGENTS.md`: quy tắc chung cho Codex (không sửa test, chỉ sửa file được giao, venv, `--basetemp`, `from __future__ import annotations`).
- `another/tests/tournament/test_records.py`: bắt lỗi `records.py` không import được trên Python 3.13.

### Fixed
- `backend/tournament/records.py`: thêm `from __future__ import annotations` (lúc review phát hiện NameError trên 3.13).

### Decided
- Codex CLI chạy được từ Claude nhưng sandbox không ghi được dưới Desktop → mỗi task chạy trong bản sao `C:/Users/admin/btlai-wt/<ID>`, review rồi chỉ chép về các file của task (cách của dự án IT Studio / BTL kì 2 năm 2).
- Kết quả: coverage `backend/core/` + `backend/tournament/` 92%; import-linter 3/3 contract; 47 skip còn lại là 4 bot của thành viên + hygiene (cần git).

## [0.0.3] — 2026-10-03 · Đặc tả M2, tài nguyên + logic GUI, prompt nhiều agent

### Added
- Test đặc tả M2 `another/tests/tournament/` (players, match_runner, series, ranking, history) + `fakes.py`. Đã kiểm chứng bằng bản tham chiếu (không commit): 151 test xanh, lint-imports giữ đủ 3 contract.
- Test đặc tả logic GUI `another/tests/gui/` (scaling, board_geometry, move_input, game_info, i18n).
- Bộ quân rhosgfx (SVG gốc + PNG 256px), `another/tools/svg_to_png.py`, `frontend/gui/assets/CREDITS.md`.
- Chuỗi giao diện `frontend/gui/locales/vi.toml`, `en.toml`; test i18n kiểm tra thêm tham số `{}` khớp nhau, đủ bản dịch kiểu kết thúc ván và tên bot.
- Prompt Codex: M2-1, M2-2, M2-3, M3-A + `documents/codex/README.md` (chia đợt cho nhiều agent chạy song song).

### Changed
- CONTEXT 0.3.0: API chi tiết §4.6–4.8 (`backend/tournament/records.py` tách riêng; MatchRunner có pause/resume, bắt mọi lỗi bot thành ván ABORTED kèm `error`); thêm §5.8 module GUI thuần logic (cấm import pygame).
- Đổi `frontend/gui/i18n/` thành `frontend/gui/locales/`: thư mục trùng tên module `frontend/gui/i18n.py` làm Python nạp nhầm.

### Decided
- Bot lỗi hoặc trả nước không hợp lệ → ván ABORTED (không tính xếp hạng), GUI không crash. Không thêm giá trị Termination mới.
- Từ đợt này, Claude chỉ viết đặc tả/test/prompt; code giao Codex (theo yêu cầu của Product Owner).

## [0.0.2] — 2026-10-03 · Scaffold, CI, test đặc tả M1

### Added
- Khung thư mục `backend/core/ backend/ai/ backend/tournament/ frontend/gui/ another/tests/ another/tools/ backend/config/`, các package bot rỗng.
- `.gitignore`, `.gitattributes` (LF), `environments/.python-version` (3.14), `pyproject.toml` (ruff, pytest, coverage, import-linter), `environments/requirements.txt`, `environments/requirements-dev.txt`, `backend/config/default.toml`, `README.md`, `main.py`.
- `.github/CODEOWNERS`, `.github/pull_request_template.md`, `.github/workflows/ci.yml` (job `ci`).
- Test đặc tả M1 (`another/tests/core`, `another/tests/ai`, `another/tests/architecture`) + helper `require_module` (module chưa có thì skip).
- Prompt Codex `documents/codex/M1-A_core.md`, `documents/codex/M1-B_ai_base.md`.

### Changed
- Gom 4 file tài liệu vào `documents/`. `README.md` vẫn ở thư mục gốc.
- CONTEXT 0.2.0: chi tiết API `GameState` (`push` trả SAN, `fen`, `starting_fen`, `ply_count`, `claim_draw`), `IllegalMoveError`/`GameOverError`, API `backend/core/config.py`, config cho test hợp đồng (`fast_mode`, `allow_random_init`, `seed`).

### Decided
- Python **3.14**: bản mới nhất có wheel Windows + Linux cho `pygame-ce 2.5.8` và `torch 2.14.1`.
- Thêm `tomli-w` để ghi `backend/config/local.toml` (`tomllib` chỉ đọc được).
- Luật lặp 3 lần / 50 nước cài bằng `is_repetition(3)` / `halfmove_clock >= 100`, **không** dùng `outcome(claim_draw=True)` vì hàm đó kết thúc ván sớm 1 nửa nước.
- CI cài `torch` bản CPU để nhẹ.
- Tên contract import-linter để ASCII vì console Windows lỗi khi in tiếng Việt.
- `CODEOWNERS`: dòng `/backend/ai/mcts/` tạm để `@august0362`; username không tồn tại sẽ làm GitHub báo lỗi file.

## [0.0.1] — 2026-10-03 · Chốt yêu cầu

### Added
- `CONTEXT.md`, `MILESTONES.md`, `TASKS.md`, `CHANGELOG.md`.

### Decided — Kiến trúc
- 4 module tách biệt: `backend/core/` ← `backend/ai/` ← `backend/tournament/` ← `frontend/gui/`. Các package bot **cấm import lẫn nhau**, CI kiểm tra bằng import-linter.
- Hợp đồng bot: `BaseBot.select_move(board: chess.Board) -> chess.Move`, nhận bản sao bàn cờ. Thông tin tìm kiếm báo qua `last_search_info` (tùy chọn). Bot không khởi tạo được thì raise `BotUnavailableError`.
- Bot được nạp động qua `backend/ai/registry.py` (chuỗi `"module:Class"`), nên GUI/tournament không import trực tiếp bot.
- Thêm `random_bot` để test/debug (ẩn trên GUI theo mặc định).
- Người chơi được mô hình hóa bằng `HumanPlayer` (hàng đợi), nên một `MatchRunner` dùng chung cho cả hai chế độ.
- Tên package viết thường có gạch dưới (`backend/ai/deep_rl/`…) để tránh lỗi phân biệt hoa/thường giữa Windows và CI Linux.

### Decided — Sản phẩm
- GUI dùng Pygame (`pygame-ce`). Canvas 960×640 (bàn 640×640 + panel 320), resize giữ tỷ lệ.
- Chế độ Người vs Bot (chọn 1/4 bot, chọn màu Trắng/Đen/Ngẫu nhiên, chỉ 1 ván) và Bot vs Bot (2 bot độc lập, được trùng nhau, 1 ván hoặc Best of 3).
- Không Undo. Không đổi phe trong ván (chỉ đổi ở màn chuẩn bị).
- Best of 3: đấu đủ 3 ván, đổi màu luân phiên (ván 3 bốc thăm), dùng chung khai cuộc. Thắng 1 / hòa 0,5 / thua 0; bằng điểm thì hòa trận.
- Khai cuộc ngẫu nhiên chỉ áp dụng cho Bot vs Bot, mặc định 2 nửa nước.
- Luật hòa chuẩn tự áp dụng (lặp 3 lần, 50 nước, không đủ quân) + giới hạn an toàn 300 nửa nước. Giải thích cho người mới nằm ở CONTEXT §4.4.
- Xếp hạng W/D/L + **Elo** (1200, K=32) cho 4 bot và hồ sơ chung "Người chơi". Có nút reset. Không tính ván dừng, ván bot tự đấu, ván có bot debug.
- Lịch sử: 20 ván đơn lẻ gần nhất, có xem lại (play/pause/tốc độ/từng nước) và xuất PGN.
- Panel 6 mục, thu gọn được. Thanh đánh giá dùng chênh lệch quân (trung lập).
- Âm thanh mặc định tắt; bật/tắt trong Cài đặt và icon trong ván.
- Giao diện song ngữ vi/en, chọn trong Cài đặt.
- Bộ quân **rhosgfx** (CC0 1.0).
- Cấu hình bằng **TOML**: `backend/config/default.toml` (commit) + `backend/config/local.toml` (cá nhân, gitignored).

### Decided — Option 4
- Dùng PyTorch, huấn luyện trên Kaggle. Trọng số phát hành qua GitHub Release và được bot tự tải kèm kiểm tra sha256. Checkpoint trung gian ở lại Kaggle.
- Elo chỉ là thước đo đánh giá, không phải reward.

### Decided — Quy trình
- Repo public `august0362/BTL_AI`; admin `@august0362`.
- Cấm push thẳng vào `main`. Làm trên branch, merge qua PR với CI xanh và branch cập nhật với `main`.
- PR của thành viên cần 1 approve của `@august0362`. PR của admin tự merge khi CI xanh (Ruleset bypass chỉ áp dụng cho phần review).
- `CODEOWNERS` là nơi duy nhất ghi username để phân quyền duyệt.
- CI: ruff, import-linter, pytest, coverage ≥80% cho backend/core/tournament, test hợp đồng bot, i18n, config, hygiene, cài đặt sạch, GUI smoke.
- Thành viên Option 1–3 tự quản thuật toán; chỉ bắt buộc qua test hợp đồng.

### Deferred
- OI-1 giới hạn thời gian · OI-2 dừng cứng bot · OI-3 giải round-robin cá nhân (local, không push) · OI-4 username thành viên Option 3 · OI-5 tinh chỉnh max_plies/khai cuộc · OI-6 thanh đánh giá theo bot.
