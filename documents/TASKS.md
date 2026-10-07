# TASKS — Chess AI Tournament

> **Cách dùng:** đổi `[ ]` thành `[x]` khi task đã merge vào `main`. Ghi số PR sau task nếu có, ví dụ `(#12)`.
> **Owner:** `U` = @august0362 · `C` = Claude · `X` = Codex (Claude soạn prompt, U dán vào Codex và tạo PR) · `M1/M2/M3` = thành viên Option 1/2/3
> **Phụ thuộc:** `← S0-01` nghĩa là phải xong S0-01 trước.
> **Thứ tự chạy Codex (nhiều agent song song):** xem `documents/codex/README.md`.

Các mốc được theo dõi ngay trong checklist bên dưới; một mốc hoàn tất khi các
việc cần thiết đã được đánh dấu xong và merge vào `main`. M0 → M1 → M2 → M3 → M4
→ M6 → M7; M5 (Deep RL) và các bot thành viên chạy song song với M2–M4 sau M1.

---

## M0 — Repo & quản trị

- [x] **S0-01** `C` Viết tài liệu kiến trúc, kế hoạch, checklist và changelog (đã gom vào `documents/`)
- [x] **S0-02** `U` Đọc và duyệt 4 file tài liệu
- [x] **S0-03** `C` Chốt Python **3.13** (đổi từ 3.14 ngày 2026-10-03: máy có sẵn, đủ wheel)
- [x] **S0-04** `C` Scaffold: thư mục, `__init__.py`, `.gitignore`, `.gitattributes`, `environments/.python-version`, `pyproject.toml`, `environments/requirements*.txt`, `backend/config/default.toml`, `README.md`, `main.py`
- [x] **S0-05** `C` `.github/CODEOWNERS`, `.github/pull_request_template.md`, `.github/workflows/ci.yml`
- [x] **S0-11** `C` `.venv` Python 3.13 + thư viện (cài qua `run.bat`); test xanh
- [x] **OPS-1** `X` `another/scripts/push.bat`, `another/scripts/pull.bat` (Codex viết; Claude test với remote cục bộ: lần đầu, tạo nhánh, pull gộp main, xung đột, thay đổi chưa commit)
- [x] **OPS-2** `X` `run.bat` (bấm đúp: tạo venv, cài thư viện khi cần, chạy game; `--test`, `--reinstall`) + `another/scripts/test.bat` (giống CI). Claude test: lần đầu cài torch 255 s, lần 2 bỏ qua cài đặt 2 s, cả hai PASS
- [ ] **S0-06** `U` Chạy `another/scripts/push.bat` lần đầu → tạo repo + push `main` lên `august0362/BTL_AI` ← S0-11
- [ ] **S0-07** `U` Bật Ruleset `main-protect` + `main-review` theo CONTEXT §8.2 (sau khi CI đã chạy ít nhất 1 lần để chọn được check `ci`) ← S0-06
- [ ] **S0-08** `U` Mời `@cieldontcry`, `@khanhtaduy2k5`, `@quanganh167` làm collaborator ← S0-06
- [ ] **S0-09** `U` Thử push thẳng vào `main` → xác nhận bị từ chối ← S0-07
- [x] **S0-10** `U` Gửi username GitHub của thành viên Option 3; cập nhật CODEOWNERS + CONTEXT §2: `@quanganh167`

## M1 — Core, hợp đồng bot, CI

### Đặc tả & test (Claude) — đã kiểm chứng bằng bản cài đặt tham chiếu (92 test xanh)
- [x] **C1-01** `C` Test đặc tả `backend/core/`: `another/tests/core/test_types.py`, `test_game_state.py`, `test_material.py`, `test_config.py`
- [x] **C1-02** `C` Test hợp đồng bot + base/registry: `another/tests/ai/test_bot_contract.py`, `test_base_bot.py`, `test_registry.py`
- [x] **C1-03** `C` import-linter (3 contract) trong `pyproject.toml`; đã thử vi phạm → bắt được
- [x] **C1-04** `C` Prompt Codex: `documents/codex/M1-A_core.md`, `documents/codex/M1-B_ai_base.md`
- [x] **X1-08** `C` (gộp vào C1-02) test hợp đồng bot
- [x] **X1-09** `C` `another/tests/architecture/`: hygiene (file lớn, file cấm, marker xung đột), config schema, i18n
- [x] **X1-10** `C` `.github/workflows/ci.yml`

### Code (Codex) — 2 PR, làm song song được
- [x] **X1-A** `X` Prompt `documents/codex/M1-A_core.md` → branch `feat/core-game-state` (gồm X1-01..X1-04) — đợt 1
- [x] **X1-B** `X` Prompt `documents/codex/M1-B_ai_base.md` → branch `feat/ai-base-registry` (gồm X1-05..X1-07) — đợt 1

### Tích hợp
- [x] **U1-01** `C` Claude điều khiển Codex CLI (bản sao ngoài Desktop), review, gộp; 219 test xanh
- [ ] **U1-02** `U` Mở PR thử vi phạm ranh giới import (vd `backend/ai/mcts/x.py` chứa `import ai.deep_rl`) → xác nhận CI đỏ → đóng PR
- [ ] **U1-03** `U` Thông báo cho nhóm: "M1 xong, bắt đầu code bot theo documents/CONTEXT.md §4.1"

## M2 — Tournament harness

- [x] **C2-01** `C` Đặc tả API chi tiết (CONTEXT §4.6–4.8) + test: `another/tests/tournament/` (players, match_runner, series, ranking, history) — đã kiểm chứng bằng bản tham chiếu (151 test xanh)
- [x] **X2-1** `X` Prompt `documents/codex/M2-1_players_records.md` → `feat/tournament-records` ← M1-A merged
- [x] **X2-2** `X` Prompt `documents/codex/M2-2_match_series.md` → `feat/tournament-match` ← X2-1 merged
- [x] **X2-3** `X` Prompt `documents/codex/M2-3_ranking_history.md` → `feat/tournament-ranking` ← X2-1 merged (song song X2-2)

## M3 — GUI MVP

### Tài nguyên
- [x] **U3-01** `C` Tải 12 SVG bộ rhosgfx (commit `5b44d719ec59` của lichess) → `frontend/gui/assets/pieces/rhosgfx/svg/`
- [x] **U3-02** `C` Chuyển sang PNG 256×256 → `frontend/gui/assets/pieces/rhosgfx/`
- [x] **U3-03** `C` `frontend/gui/assets/CREDITS.md`
- [x] **X3-01** `C` `another/tools/svg_to_png.py` (dùng pygame-ce, không thêm thư viện)
- [x] **C3-02** `C` Chuỗi giao diện `frontend/gui/locales/vi.toml`, `en.toml` (đủ màn hình theo §5.2)

### Logic GUI (không cần màn hình)
- [x] **C3-03** `C` Đặc tả §5.8 + test `another/tests/gui/` (scaling, board_geometry, move_input, game_info, i18n)
- [x] **X3-A** `X` Prompt `documents/codex/M3-A_gui_logic.md` → `feat/gui-logic` (đợt 1, song song M1)

### Phần vẽ Pygame
- [x] **C3-04** `C` Đặc tả §5.9–5.10 + test `another/tests/gui/test_controller.py`, `test_app_smoke.py` + prompt M3-B, M3-C
- [x] **X3-B** `X` Prompt `documents/codex/M3-B_controller.md` (GameController)
- [x] **X3-C** `X` Prompt `documents/codex/M3-C_pygame_app.md` (App, widgets, Menu / Chuẩn bị / Ván đấu) ← X3-B
- [ ] **U3-04** `U` Tích hợp, chạy thử theo kịch bản QA (C3-01), chỉnh UI/UX
- [ ] **C3-01** `C` Kịch bản QA thủ công cho GUI MVP

## M4 — GUI đầy đủ

- [x] **C4-02** `C` Đặc tả §5.11 + prompt M4-A, M4-B
- [x] **M4-A** `X` Logic: ReplayModel, SoundManager/sound_for_move, leaderboard_rows, set_bot_move_delay, WAV tự sinh — kèm test (Codex)
- [x] **M4-B** `X` Màn Bot vs Bot, Lịch sử, Xem lại, Xếp hạng, Cài đặt, âm thanh — kèm smoke test (Codex)
- [x] **M4-B-fix1/2** `X` QA: lịch sử chỉ hiện 7 ván → cuộn được; icon loa ô vuông → vẽ hình; nút Tạm dừng bị đè → xếp lại + test chống đè
- [ ] **U4-02** `U` Chơi thử toàn bộ game, báo lỗi / góp ý UI

## UI v2 — nét, theme, thiết kế (yêu cầu 2026-10-03)

- [x] **UI-1** `X` Hết mờ (DPI awareness + vẽ ở độ phân giải thật), tên "Chess", 6 theme, chuẩn thiết kế (+ fix1: vẽ thật sự ở độ phân giải thật, trạng thái chọn)
- [x] **UI-2** `X` 18 theme Color Hunt tự sinh từ tên file, thuật toán tạo màu đạt WCAG, bộ chọn theme cuộn được (tổng 24 theme)
- [x] **UI-3** `X` Làm dịu màu ô cờ mọi theme (giới hạn độ bão hòa / độ sáng)
- [x] **DOC-1** `X` README đầy đủ, `documents/USER_GUIDE.md` (kèm ảnh), `documents/CONTRIBUTING.md`

## M5 — Deep RL v1 (Option 4) — lõi RL do @august0362 tự viết

- [x] **C5-01** `C` Thiết kế + ranh giới `documents/DEEP_RL_DESIGN.md`; lộ trình học `documents/RL_LEARNING_GUIDE.md`
- [x] **RL-0** `X` Hạ tầng: encoding, env, opponents, evaluate, metrics, weights, bot adapter, khung `user/`, notebook Kaggle, test (`documents/codex/RL-0_infra.md`)
- [ ] **U5-L** `U` Học theo `documents/RL_LEARNING_GUIDE.md` chặng 0–2 (cờ caro Q-learning, DQN CartPole)
- [ ] **RL-1** `U` `user/model.py` + `user/policy.py` → bot hiện trên GUI, qua test hợp đồng
- [ ] **RL-2** `U` `user/replay.py`, `user/agent.py`, `user/train.py` → train chạy trên Kaggle, có biểu đồ
- [ ] **RL-3** `U` ≥ 90% thắng RandomOpponent / 50 ván → upload trọng số lên Release `deeprl-v1.0`, điền URL + sha256 vào config
- [ ] **RL-4** `U` Thắng GreedyCaptureOpponent đa số ván (điểm cộng)

## Track thành viên (tự quản — chỉ theo dõi mốc)

- [x] **BOT-0** `X` Bot chưa có code chạy baseline ngẫu nhiên (`backend/ai/baseline.py`), GUI ghi "(baseline)" — thành viên thay lớp trong `backend/ai/<bot>/bot.py` khi viết bot thật, rồi Đặt lại bảng xếp hạng

- [ ] **M1-01** `M1` Option 1 qua test hợp đồng, PR được merge
- [ ] **M2-01** `M2` Option 2 qua test hợp đồng, PR được merge
- [ ] **M3-01** `M3` Option 3 qua test hợp đồng, PR được merge

## M6 — Tích hợp

- [ ] **U6-01** `U` Chơi thử đủ 6 cặp bot + người vs từng bot trên GUI; bot lỗi/thiếu trọng số không làm crash và hiện lý do
- [x] **C6-01** `C` Đặc tả giải round-robin cá nhân (OI-3) — `documents/codex/LOCAL-1_arena.md`
- [x] **LOCAL-1** `X` `another/local_tools/arena.py` (chỉ trên máy, gitignored): đấu vòng tròn, CSV/PGN, Elo riêng

## M7 — Hoàn thiện

- [ ] **C7-01** `C` Rà soát Open Issues, cập nhật CONTEXT/CHANGELOG
- [x] **X7-01** `X` README hoàn chỉnh (DOC-1)
- [ ] **U7-01** `U` Tag `v1.0.0` + Release

## M8 — Bảng xếp hạng AI (yêu cầu 2026-10-07)

> Đã code xong trên nhánh `server-vie`; các mục `[x]` chờ PR/merge để tính là hoàn tất.

- [x] **BENCH-1** `X` Bốn bot benchmark trong `backend/ai/benchmarks/` (Random · Alpha-Beta 3 · Alpha-Beta TT · Alpha-Beta Custom) + đăng ký opt-in `BENCHMARK_BOTS`
- [x] **TOUR-1** `X` `tournament_config.py` + bảng `[tournament]` trong `backend/config/default.toml` (20 ván/cặp, 10 lịch sử, `max_plies`, `depth`)
- [x] **TOUR-1b** `X` Trần thời gian suy nghĩ mỗi nước `max_think_time_s` (mặc định 1.0s) + bot benchmark sâu dần tự dừng đúng hạn; `depth = 0` = không ép độ sâu (giữ cấu hình riêng của bot)
- [x] **TOUR-2** `X` `round_robin.py`: vòng tròn mọi cặp, chia đều Trắng/Đen, điểm 1/0.5/0, hạng "1224", phá hòa bằng thời gian, bot mới mỗi ván, dừng giữa chừng
- [x] **TOUR-3** `X` `tournament_history.py`: lưu "Trận Chiến Lần n" (`battle_NNNN.json`), giữ 10 bản gần nhất, tách khỏi Elo
- [x] **GUI-T1** `X` Mục **Xếp hạng AI** trong Board Menu (dưới "Bot vs Bot", trên "Lịch sử") + màn lịch sử riêng, chạy nền, thanh tiến trình, nút Dừng đấu
- [x] **T8-01** `X` Test: `test_benchmarks.py`, `test_round_robin.py`, `test_tournament_history.py`, `test_tournament_view.py`, `test_tournament_smoke.py`
- [ ] **U8-01** `U` Chạy thử giải đầy đủ trên GUI, duyệt bố cục bảng/nút, báo lỗi
