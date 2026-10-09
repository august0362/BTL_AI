# Hướng dẫn đóng góp

Lối vào nhanh cho thành viên và quy trình Git. Nguồn chuẩn về kiến trúc, hợp đồng bot và luật chung là [CONTEXT.md](CONTEXT.md) — đọc trước khi code.

## Ai sửa ở đâu

| Thành viên | Phần phụ trách | Vùng phát triển |
|---|---|---|
| `@cieldontcry` | Option 1 — Alpha-Beta + Linear Regression | `backend/ai/alphabeta_regression/` |
| `@khanhtaduy2k5` | Option 2 — Alpha-Beta + Genetic Algorithm | `backend/ai/genetic_alphabeta/` |
| `@quanganh167` | Option 3 — MCTS | `backend/ai/mcts/` |
| `@august0362` | Option 4 — Deep RL; tích hợp, phần dùng chung | `backend/ai/deep_rl/` |

- Chỉ sửa package bot của mình và thêm test trong `another/tests/ai/<bot_id>/`. **Không xóa/sửa test hiện có**; thấy hợp đồng/test sai thì trao đổi với người tích hợp.
- Được thêm module riêng trong package (vd `backend/ai/mcts/search.py`); class entry point ở `bot.py`; tuân thủ ranh giới import (CONTEXT §3.1): không import bot khác, `tournament`, `gui`.
- Sửa `backend/core/`, `ai/base_bot.py`, `ai/registry.py`, `backend/tournament/`, `frontend/gui/`, cấu hình hoặc CI cần phối hợp với `@august0362`.

## Luồng gọi bot và dữ liệu bàn cờ

`backend/ai/registry.py` ánh xạ ID → module:class (vd `"mcts": "ai.mcts.bot:MctsBot"`). Hệ thống tạo bot qua registry; `MatchRunner` gọi `select_move(board)` với bàn cờ hiện tại, bot trả `chess.Move` hợp lệ, runner xác nhận rồi mới cập nhật ván.

```mermaid
flowchart LR
    G[GUI hoặc trận đấu] --> R[MatchRunner]
    R -->|select_move(board)| B[Bot]
    B -->|chess.Move hợp lệ| R
    R -->|push nước đi| S[GameState]
    S -->|bàn cờ hiện tại| R
```

- Thử bot: `chess.Board()` tạo thế bắt đầu, `chess.Board(fen)` tạo từ FEN, rồi `move = bot.select_move(board)`. Khi chơi thật, hệ thống truyền `board: chess.Board` hiện tại (quân, bên tới lượt, nhập thành, bắt tốt qua đường…); luật cờ do `python-chess` xử lý.
- Trả nước trong `board.legal_moves`, **không sửa** `board` được truyền (thử nước trên `board.copy()`). Hai instance cùng loại độc lập. Kế thừa `BaseBot`, khai báo `bot_id`, `display_name`, cài `select_move`; `last_search_info` tùy chọn.
- Deep RL: `encode_board(board)` (`backend/ai/deep_rl/encoding.py`) → `numpy.float32` `(18, 8, 8)`; `legal_action_mask(board)` → mặt nạ 4096 hành động. `DeepRLBot` nối giải đấu với `deep_rl/user/policy.py`; phần tự triển khai của Option 4 ở `deep_rl/user/` (`model.py`, `agent.py`, `replay.py`, `train.py`, `policy.py`).
- Thêm bot mới hoặc đổi ID/module/class thì cập nhật `BOT_REGISTRY` (sửa thuật toán thì không). Giữ import nhẹ; không khởi tạo được thì raise `BotUnavailableError`.

## Từ clone đến Pull Request

1. Cài Git và Python 3.13, clone rồi chạy `run.bat` (hoặc thủ công):

   ```bat
   git clone https://github.com/august0362/BTL_AI.git
   cd BTL_AI
   py -3.13 -m venv .venv
   .venv\Scripts\python -m pip install -r environments\requirements-dev.txt
   ```

2. `git status` sạch → `another\scripts\pull.bat` để cập nhật `main` → tạo branch `feat/`, `fix/` hoặc `documents/` + mô tả (chữ, số, gạch ngang):

   ```bat
   git switch main
   git switch -c feat/mcts-uct-selection
   ```

3. Sửa trong phạm vi của mình. Bot được kiểm với `{"fast_mode": true, "allow_random_init": true, "seed": 0}`: tìm kiếm nhanh cho CI, cho phép khởi tạo ngẫu nhiên khi phù hợp, RNG riêng để lặp lại được.

4. Chạy test hợp đồng (đổi `mcts` thành bot của bạn) và toàn bộ kiểm tra (pytest, Ruff, ranh giới import):

   ```bat
   .venv\Scripts\python -m pytest another\tests\ai\test_bot_contract.py -k mcts --basetemp=.pytest-tmp
   another\scripts\test.bat
   ```

5. Stage đúng file (thêm test trong `another/tests/ai/<bot_id>/` nếu có), commit, push:

   ```bat
   git status
   git add backend/ai/mcts
   git commit -m "feat(mcts): add UCT selection"
   git push -u origin feat/mcts-uct-selection
   ```

   Hoặc dùng `another\scripts\push.bat`: đang ở `main` thì tạo branch `feat/<mô-tả>`, chạy pytest nếu có `.venv`, stage **mọi thay đổi** (`git add -A`), commit và push — kiểm `git status` trước để không gửi nhầm.

6. Mở PR vào `main`, mô tả thay đổi và kết quả kiểm tra. Không push thẳng `main`. Merge cần CI xanh, một approval và review của CODEOWNER (`.github/CODEOWNERS`).

Không commit `database/data/`, `another/local_tools/`, `backend/config/local.toml`, `backend/ai/*/weights/`, `android/`, bí mật hoặc file > 5 MB.

## Khi push hoặc merge bị từ chối

| Lỗi | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Push lên `main` bị từ chối | `main` được bảo vệ | Push branch riêng rồi mở PR |
| HTTP 403, permission denied, repo not found | Sai tài khoản, chưa được mời, remote sai | Kiểm tra tài khoản, quyền collaborator, `origin` |
| `src refspec ... does not match any` | Branch chưa có hoặc chưa có commit | `git branch --show-current`, tạo branch và commit |
| `non-fast-forward` / `fetch first` | Remote có commit mới hơn | Tree sạch → `another\scripts\pull.bat`, xử lý xung đột, push lại |
| Chưa có `user.name` / `user.email` | Git chưa cấu hình danh tính | Cấu hình Git (lỗi commit, chưa phải lỗi push) |
| Push được nhưng CI đỏ | Test, lint, format, ranh giới import | Đọc log CI, sửa trên cùng branch, push tiếp |
| CI xanh nhưng chưa merge được | Thiếu approval/CODEOWNER hoặc branch chưa cập nhật | Làm theo yêu cầu trên PR (chặn merge, không phải push) |
| `pull.bat` báo thay đổi chưa commit | Working tree không sạch | Commit hoặc stash rồi chạy lại |

`pull.bat` cần working tree sạch: trên `main` thì fast-forward từ `origin/main`; trên branch công việc thì cập nhật branch rồi merge `origin/main`. Hủy merge đang xung đột: `git merge --abort`.

## Tài liệu khác

[CONTEXT.md](CONTEXT.md) (kiến trúc, hợp đồng) · [TASKS.md](TASKS.md) (tiến độ) · [USER_GUIDE.md](USER_GUIDE.md) (cách chơi) · [DEEP_RL_DESIGN.md](DEEP_RL_DESIGN.md), [RL_LEARNING_GUIDE.md](RL_LEARNING_GUIDE.md) (Option 4).
