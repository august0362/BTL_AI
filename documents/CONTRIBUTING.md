# Hướng dẫn đóng góp

Đọc [CONTEXT.md](CONTEXT.md) trước khi code; đó là nguồn chuẩn cho kiến trúc,
hợp đồng bot và các luật chung. File này là lối vào nhanh cho thành viên và
quy trình Git.

## Ai sửa ở đâu

| Thành viên | Phần phụ trách | Vùng phát triển |
|---|---|---|
| `@cieldontcry` | Option 1 — Alpha-Beta + Linear Regression | `backend/ai/alphabeta_regression/` |
| `@khanhtaduy2k5` | Option 2 — Alpha-Beta + Genetic Algorithm | `backend/ai/genetic_alphabeta/` |
| `@quanganh167` | Option 3 — MCTS | `backend/ai/mcts/` |
| `@august0362` | Option 4 — Deep RL; tích hợp và phần dùng chung | `backend/ai/deep_rl/` |

Chỉ thay đổi package bot của mình và thêm test liên quan trong
`another/tests/ai/<bot_id>/`. Không xóa hoặc sửa test hiện có; nếu cho rằng hợp
đồng/test sai, trao đổi với người tích hợp trước. Có thể thêm module riêng trong
package bot, ví dụ `backend/ai/mcts/search.py`; giữ class entry point trong
`bot.py` và tuân thủ ranh giới import ở CONTEXT §3.1. Thay đổi
`backend/core/`, `backend/ai/base_bot.py`, `backend/ai/registry.py`,
`backend/tournament/`, `frontend/gui/`, cấu hình hoặc CI cần phối hợp với
`@august0362`.

## Luồng gọi bot và dữ liệu bàn cờ

`backend/ai/registry.py` ánh xạ ID sang module và class, ví dụ
`"mcts": "ai.mcts.bot:MctsBot"`. Hệ thống tạo bot qua registry, rồi
`MatchRunner` gọi `select_move(board)` với bàn cờ hiện tại. Bot trả về một
`chess.Move` hợp lệ; runner xác nhận rồi mới cập nhật ván.

```mermaid
flowchart LR
    G[GUI hoặc trận đấu] --> R[MatchRunner]
    R -->|select_move(board)| B[Bot]
    B -->|chess.Move hợp lệ| R
    R -->|push nước đi| S[GameState]
    S -->|bàn cờ hiện tại| R
```

`chess.Board()` (B hoa) tạo bàn cờ mới ở thế bắt đầu; `chess.Board(fen)` tạo thế
cờ từ FEN. Ví dụ, lời gọi dưới đây tạo một bàn cờ mới để thử bot:

```python
import chess

board = chess.Board()
move = bot.select_move(board)
```

Khi chơi thật, không tự tạo bàn mới để lấy input: hệ thống truyền
`board: chess.Board` hiện tại vào `select_move`. Dữ liệu này có quân cờ, bên tới
lượt, quyền nhập thành, nước bắt tốt qua đường và các trạng thái cần cho luật cờ.
Luật cờ do `python-chess` xử lý.

Bot phải trả một nước trong `board.legal_moves` và không sửa đối tượng `board`
được truyền vào. Nếu cần thử các nước, dùng `board.copy()` rồi thao tác trên bản
sao. Hai instance cùng loại phải độc lập. Bot kế thừa `BaseBot`, khai báo
`bot_id` và `display_name`, cài `select_move`; `last_search_info` là thống kê tùy
chọn. Không import bot khác, `tournament` hay `gui` từ package bot.

Deep RL dùng cùng bàn cờ đầu vào, sau đó mã hóa cho mô hình bằng
`encode_board(board)` trong `backend/ai/deep_rl/encoding.py`; kết quả là mảng
`numpy.float32` kích thước `(18, 8, 8)`. `legal_action_mask(board)` cho mặt nạ
4096 hành động. Class `DeepRLBot` đã nối giải đấu với
`backend/ai/deep_rl/user/policy.py`; phần tự triển khai của Option 4 nằm trong
`backend/ai/deep_rl/user/` (`model.py`, `agent.py`, `replay.py`, `train.py`,
`policy.py`).

Khi thêm một bot mới hoặc đổi ID/module/class, cập nhật `BOT_REGISTRY`. Khi sửa
thuật toán của một bot đã đăng ký, không cần đăng ký lại. Giữ package import
nhẹ; nếu bot không thể khởi tạo, báo `BotUnavailableError`.

## Từ clone đến Pull Request

1. Cài Git và Python 3.13. Clone repo rồi chạy `run.bat`, hoặc cài thủ công:

   ```bat
   git clone https://github.com/august0362/BTL_AI.git
   cd BTL_AI
   py -3.13 -m venv .venv
   .venv\Scripts\python -m pip install -r environments\requirements-dev.txt
   ```

2. Đảm bảo `git status` sạch rồi chạy `another\scripts\pull.bat` để cập nhật
   `main`. Tạo branch riêng; dùng tiền tố `feat/`, `fix/` hoặc `documents/`, sau
   đó là mô tả chỉ gồm chữ, số và dấu gạch ngang:

   ```bat
   git switch main
   git switch -c feat/mcts-uct-selection
   ```

3. Sửa trong phạm vi của mình. Bot được kiểm tra với cấu hình
   `{"fast_mode": true, "allow_random_init": true, "seed": 0}`: hỗ trợ tìm kiếm
   nhanh cho CI, cho phép khởi tạo ngẫu nhiên khi phù hợp và dùng RNG riêng để
   kết quả có thể lặp lại.

4. Trước khi gửi, chạy test hợp đồng cho bot và các kiểm tra phù hợp:

   ```bat
   .venv\Scripts\python -m pytest another\tests\ai\test_bot_contract.py -k mcts --basetemp=.pytest-tmp
   another\scripts\test.bat
   ```

   Ví dụ trên lọc bot `mcts`; thay tên theo bot của bạn. `test.bat` chạy toàn bộ
   pytest, Ruff và kiểm tra ranh giới import.

5. Xem lại thay đổi, stage đúng file, commit và push branch:

   ```bat
   git status
   git add backend/ai/mcts
   git commit -m "feat(mcts): add UCT selection"
   git push -u origin feat/mcts-uct-selection
   ```

   Đổi bot, test, branch và nội dung commit theo phần việc thực tế. Nếu thêm
   test, stage thêm đúng file trong `another/tests/ai/<bot_id>/`. Có thể dùng
   `another\scripts\push.bat`: nếu đang ở `main`, script tạo branch
   `feat/<mô-tả>`, chạy pytest nếu có `.venv`, stage **mọi thay đổi** bằng
   `git add -A`, commit và push. Hãy kiểm tra `git status` trước để không gửi
   nhầm file.

6. Mở Pull Request từ branch vào `main`, mô tả thay đổi và kết quả kiểm tra.
   Không push trực tiếp lên `main`. PR cần CI xanh, một approval và review của
   CODEOWNER theo `.github/CODEOWNERS` trước khi merge.

Không commit `database/data/`, `another/local_tools/`,
`backend/config/local.toml`, `backend/ai/*/weights/`, bí mật hoặc file lớn hơn
5 MB.

## Khi push hoặc merge bị từ chối

| Lỗi | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Push lên `main` bị từ chối | `main` được bảo vệ | Push branch riêng rồi mở PR. |
| HTTP 403, permission denied hoặc repo not found | Đăng nhập sai tài khoản, chưa được mời vào repo hoặc remote sai | Kiểm tra tài khoản, quyền collaborator và `origin`. |
| `src refspec ... does not match any` | Branch chưa tồn tại hoặc chưa có commit | Kiểm tra `git branch --show-current`, tạo branch và commit. |
| `non-fast-forward` / `fetch first` | Remote có commit mới hơn | Working tree sạch rồi chạy `another\scripts\pull.bat`, xử lý xung đột và push lại. |
| Chưa có `user.name` / `user.email` | Git chưa được cấu hình danh tính | Cấu hình Git; đây là lỗi commit, chưa phải lỗi push. |
| Push thành công nhưng CI đỏ | Test, lint, format hoặc ranh giới import chưa đạt | Đọc log CI, sửa trên cùng branch, commit và push tiếp. |
| CI xanh nhưng PR chưa merge được | Thiếu approval/CODEOWNER review hoặc branch chưa cập nhật | Làm theo yêu cầu còn thiếu trên PR. Đây là chặn merge, không phải push. |
| `pull.bat` báo thay đổi chưa commit | Working tree không sạch | Commit hoặc stash thay đổi rồi chạy lại. |

`pull.bat` yêu cầu working tree sạch. Trên `main`, script fast-forward từ
`origin/main`; trên branch công việc, nó cập nhật branch đó rồi merge
`origin/main`. Nếu muốn hủy lần merge đang xung đột, chạy `git merge --abort`.

## Các tài liệu còn lại

- [CONTEXT.md](CONTEXT.md): kiến trúc và hợp đồng kỹ thuật chi tiết.
- [TASKS.md](TASKS.md): checklist tiến độ; các mốc và việc cần làm.
- [USER_GUIDE.md](USER_GUIDE.md): cách chơi game.
- [DEEP_RL_DESIGN.md](DEEP_RL_DESIGN.md) và
  [RL_LEARNING_GUIDE.md](RL_LEARNING_GUIDE.md): thiết kế và lộ trình học riêng
  cho Option 4.
