# TASKS — Chess AI Tournament

> Đổi `[ ]` thành `[x]` khi task đã merge vào `main` (ghi số PR nếu có, vd `(#12)`). Mốc hoàn tất khi các việc cần thiết đã merge.
> **Owner:** `U` = @august0362 · `C` = Claude · `X` = Codex (Claude soạn prompt, U dán vào Codex và tạo PR) · `M1/M2/M3` = thành viên Option 1/2/3. **Phụ thuộc:** `← S0-01` = phải xong S0-01 trước. Thứ tự chạy Codex song song: `documents/codex/README.md`.
> Thứ tự mốc: M0 → M1 → M2 → M3 → M4 → M6 → M7; M5 (Deep RL) và bot thành viên chạy song song M2–M4 sau M1.

## M0 — Repo & quản trị

- [x] **S0-01** `C` Tài liệu kiến trúc, kế hoạch, checklist, changelog (gom vào `documents/`)
- [x] **S0-02** `U` Đọc và duyệt 4 file tài liệu
- [x] **S0-03** `C` Chốt Python **3.13** (đổi từ 3.14 ngày 2026-10-03: máy có sẵn, đủ wheel)
- [x] **S0-04** `C` Scaffold: thư mục, `__init__.py`, `.gitignore`, `.gitattributes`, `.python-version`, `pyproject.toml`, requirements, `default.toml`, `README.md`, `main.py`
- [x] **S0-05** `C` `.github/CODEOWNERS`, PR template, `workflows/ci.yml`
- [x] **S0-11** `C` `.venv` Python 3.13 + thư viện (qua `run.bat`); test xanh
- [x] **OPS-1** `X` `another/scripts/push.bat`, `pull.bat` (Claude test với remote cục bộ: lần đầu, tạo nhánh, pull gộp main, xung đột, thay đổi chưa commit)
- [x] **OPS-2** `X` `run.bat` (tạo venv, cài khi cần, chạy game; `--test`, `--reinstall`) + `another/scripts/test.bat` (giống CI). Lần đầu cài torch 255 s, lần 2 bỏ qua cài 2 s, cả hai PASS
- [ ] **S0-06** `U` `push.bat` lần đầu → tạo repo + push `main` lên `august0362/BTL_AI` ← S0-11
- [ ] **S0-07** `U` Bật Ruleset `main-protect` + `main-review` (CONTEXT §8; sau khi CI chạy ≥ 1 lần để chọn check `ci`) ← S0-06
- [ ] **S0-08** `U` Mời `@cieldontcry`, `@khanhtaduy2k5`, `@quanganh167` làm collaborator ← S0-06
- [ ] **S0-09** `U` Thử push thẳng `main` → xác nhận bị từ chối ← S0-07
- [x] **S0-10** `U` Username thành viên Option 3: `@quanganh167` (CODEOWNERS + CONTEXT §2)

## M1 — Core, hợp đồng bot, CI

- [x] **C1-01** `C` Test đặc tả `backend/core/` (`test_types.py`, `test_game_state.py`, `test_material.py`, `test_config.py`) — kiểm bằng bản tham chiếu, 92 test xanh
- [x] **C1-02** `C` Test hợp đồng bot + base/registry (`test_bot_contract.py`, `test_base_bot.py`, `test_registry.py`; gồm X1-08)
- [x] **C1-03** `C` import-linter (3 contract) trong `pyproject.toml`, đã thử vi phạm → bắt được
- [x] **C1-04** `C` Prompt Codex `M1-A_core.md`, `M1-B_ai_base.md`
- [x] **X1-09** `C` `another/tests/architecture/`: hygiene (file lớn, file cấm, marker xung đột), config schema, i18n
- [x] **X1-10** `C` `.github/workflows/ci.yml`
- [x] **X1-A** `X` `M1-A_core.md` → `feat/core-game-state` (X1-01..04), **X1-B** `X` `M1-B_ai_base.md` → `feat/ai-base-registry` (X1-05..07) — đợt 1, song song
- [x] **U1-01** `C` Claude điều khiển Codex CLI (bản sao ngoài Desktop), review, gộp; 219 test xanh
- [ ] **U1-02** `U` PR thử vi phạm ranh giới import (vd `backend/ai/mcts/x.py` chứa `import ai.deep_rl`) → CI đỏ → đóng PR
- [ ] **U1-03** `U` Báo nhóm: "M1 xong, code bot theo CONTEXT §4.1"

## M2 — Tournament harness

- [x] **C2-01** `C` Đặc tả CONTEXT §4.6–4.8 + test `another/tests/tournament/` (players, match_runner, series, ranking, history) — kiểm bằng bản tham chiếu, 151 test xanh
- [x] **X2-1** `X` `M2-1_players_records.md` → `feat/tournament-records` ← M1-A
- [x] **X2-2** `X` `M2-2_match_series.md` → `feat/tournament-match` ← X2-1
- [x] **X2-3** `X` `M2-3_ranking_history.md` → `feat/tournament-ranking` ← X2-1 (song song X2-2)

## M3 — GUI MVP

- [x] **U3-01..03, X3-01** `C` 12 SVG rhosgfx (commit lichess `5b44d719ec59`) → `assets/pieces/rhosgfx/svg/`, PNG 256×256 bằng `another/tools/svg_to_png.py` (pygame-ce), `CREDITS.md`
- [x] **C3-02** `C` Chuỗi giao diện `locales/vi.toml`, `en.toml` (đủ màn hình)
- [x] **C3-03** `C` Đặc tả module GUI thuần logic + test `another/tests/gui/` (scaling, board_geometry, move_input, game_info, i18n); **X3-A** `X` `M3-A_gui_logic.md` → `feat/gui-logic` (đợt 1)
- [x] **C3-04** `C` Đặc tả controller/app + test `test_controller.py`, `test_app_smoke.py` + prompt; **X3-B** `X` `M3-B_controller.md`; **X3-C** `X` `M3-C_pygame_app.md` (App, widgets, Menu / Chuẩn bị / Ván đấu) ← X3-B
- [ ] **C3-01** `C` Kịch bản QA thủ công cho GUI MVP
- [ ] **U3-04** `U` Tích hợp, chạy theo kịch bản QA, chỉnh UI/UX

## M4 — GUI đầy đủ

- [x] **C4-02** `C` Đặc tả + prompt M4-A, M4-B
- [x] **M4-A** `X` ReplayModel, SoundManager/sound_for_move, leaderboard_rows, set_bot_move_delay, WAV tự sinh + test
- [x] **M4-B** `X` Màn Bot vs Bot, Lịch sử, Xem lại, Xếp hạng, Cài đặt, âm thanh + smoke test; **fix1/2**: lịch sử 7 ván → cuộn được; icon loa ô vuông → vẽ hình; nút Tạm dừng bị đè → xếp lại + test chống đè
- [ ] **U4-02** `U` Chơi thử toàn bộ game, báo lỗi / góp ý UI

## UI v2 — nét, theme, thiết kế (2026-10-03)

- [x] **UI-1** `X` Hết mờ (DPI awareness + vẽ ở độ phân giải thật), tên "Chess", 6 theme, chuẩn thiết kế (+ fix1)
- [x] **UI-2** `X` 18 theme Color Hunt tự sinh từ tên file, thuật toán màu đạt WCAG, bộ chọn theme cuộn được (24 theme)
- [x] **UI-3** `X` Làm dịu màu ô cờ mọi theme
- [x] **DOC-1** `X` README, `USER_GUIDE.md` (kèm ảnh), `CONTRIBUTING.md` (gồm X7-01)

## M5 — Deep RL v1 (Option 4, lõi RL do @august0362 tự viết)

- [x] **C5-01** `C` `documents/DEEP_RL_DESIGN.md`, `documents/RL_LEARNING_GUIDE.md`
- [x] **RL-0** `X` Hạ tầng: encoding, env, opponents, evaluate, metrics, weights, bot adapter, khung `user/`, notebook Kaggle, test (`RL-0_infra.md`)
- [ ] **U5-L** `U` Học chặng 0–2 (cờ caro Q-learning, DQN CartPole)
- [ ] **RL-1** `U` `user/model.py` + `user/policy.py` → bot hiện trên GUI, qua test hợp đồng
- [ ] **RL-2** `U` `user/replay.py`, `agent.py`, `train.py` → train trên Kaggle, có biểu đồ
- [ ] **RL-3** `U` ≥ 90 % thắng RandomOpponent / 50 ván → trọng số lên Release `deeprl-v1.0`, URL + sha256 vào config
- [ ] **RL-4** `U` Thắng GreedyCaptureOpponent đa số ván (điểm cộng)

## Track thành viên (tự quản)

- [x] **BOT-0** `X` Bot chưa có code chạy baseline ngẫu nhiên, GUI ghi "(baseline)" — viết bot thật thì thay lớp trong `bot.py`, rồi Đặt lại xếp hạng
- [ ] **M1-01** `M1` Option 1 qua test hợp đồng, PR được merge
- [ ] **M2-01** `M2` Option 2 qua test hợp đồng, PR được merge
- [ ] **M3-01** `M3` Option 3 qua test hợp đồng, PR được merge

## M6 — Tích hợp

- [ ] **U6-01** `U` Chơi đủ 6 cặp bot + người vs từng bot; bot lỗi/thiếu trọng số không crash, hiện lý do
- [x] **C6-01** `C` Đặc tả giải round-robin cá nhân (OI-3) — `LOCAL-1_arena.md`; **LOCAL-1** `X` `another/local_tools/arena.py` (gitignored): vòng tròn, CSV/PGN, Elo riêng

## M7 — Hoàn thiện

- [ ] **C7-01** `C` Rà soát Open Issues, cập nhật CONTEXT/CHANGELOG
- [ ] **U7-01** `U` Tag `v1.0.0` + Release

## M8 — Bot benchmark & Xếp hạng AI (2026-10-07 → 10-08)

> Code xong trên nhánh làm việc; `[x]` chờ PR/merge để tính hoàn tất.

- [x] **BENCH-1** `X` B1–B4 trong `backend/ai/benchmarks/` + đăng ký opt-in `BENCHMARK_BOTS`
- [x] **BENCH-5..8** `C` B5 (5 bot), B6 (4 bot), B7 Dragon, B8 Luna — mỗi thế hệ một package `ai.bench5` … `ai.bench8`, `[benchmarks] max_level`, tên bot trong config
- [x] **TOUR-1** `X` `tournament_config.py` + `[tournament]` (`max_plies`, `depth`, `max_history`); **TOUR-1b** trần `max_think_time_s` (1,0 s), benchmark tự dừng đúng hạn; `depth = 0` = không ép độ sâu
- [x] **TOUR-2** `X` `round_robin.py`: điểm 1/0,5/0, hạng "1224", bot mới mỗi ván, dừng giữa chừng; sau đổi sang **lượt thách đấu** (mỗi bot thách mọi bot khác, cầm Trắng)
- [x] **TOUR-3** `X` `tournament_history.py`: "Trận Chiến Lần n" (`battle_NNNN.json`), tách khỏi Elo
- [x] **TOUR-4** `C` Tổng = điểm + thời gian + bộ nhớ (so với trung bình) + thưởng thắng ngược theo cặp; tạm tính khi chạy, chốt khi kết thúc
- [x] **TOUR-5** `C` Cột Bộ nhớ: mỗi bot một tiến trình mỗi ván (`process_player.py`), hệ điều hành đo đỉnh RAM
- [x] **GUI-T1** `X` Mục **Xếp hạng AI** (dưới Bot vs Bot, trên Lịch sử) + màn lịch sử riêng, chạy nền, thanh tiến trình, Dừng đấu; nhãn ván đang đấu, sắp xếp theo cột
- [x] **T8-01** `X` Test: `test_benchmarks.py`, `test_benchmark5/6/8.py`, `test_round_robin.py`, `test_process_player.py`, `test_tournament_history.py`, `test_tournament_view.py`, `test_tournament_smoke.py`
- [x] **ELO-1** `X` Elo cho `human` + mọi bot hiện trên GUI (bỏ `baseline`); Người vs Bot / Bot vs Bot chọn được mọi bot (`ELO-1_all_bots.md`)
- [ ] **U8-01** `U` Chạy thử giải đầy đủ trên GUI, duyệt bố cục bảng/nút, báo lỗi
