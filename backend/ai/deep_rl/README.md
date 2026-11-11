# Deep RL (Option 4)

Bot `deep_rl` nạp một file trọng số rồi chơi theo định dạng của file đó; chưa có trọng số thì đi nước
ngẫu nhiên hợp lệ. Lịch sử v1 → V22: [DEEP_RL_EVOLUTION.md](DEEP_RL_EVOLUTION.md).

## Định dạng trọng số

| `format` | Bản | Cách chơi | Mã |
|---|---|---|---|
| `deep_rl_dqn_v1` | v1–v10 | `depth = 1`: argmax Q; `depth >= 2`: alpha-beta, lá = max Q | `user/` |
| `v11-policy-value-mcts-2` | V11.2 | MCTS `simulations` lượt | `v11/` |
| `v20-phase-experts-1` | V20 | 3 mạng START/MID/END chọn theo pha + MCTS `simulations` lượt | `v20/` |

## V20: ghép ba mạng

Trước mỗi nước, bot xét lại các thế đến lượt nó trong lịch sử ván:
- **END** nếu đã từng có `G ≤ 8`, với `G = 4·Hậu + 2·Xe + Tượng + Mã` (cả hai bên, thế đầu 24);
- **MID** nếu đã từng có `r ≥ 0,5`, với `r = clip((ply − 16)/20 + 0,2·(24 − G)/16, 0, 1)`;
- còn lại **START**.

Sau đó chạy MCTS bằng mạng của pha đó: cây mới, không nhiễu, chọn nước nhiều lượt thăm nhất.
Đặt `search = "alphabeta"` thì thay MCTS bằng alpha-beta độ sâu `depth` (`v20/alphabeta.py`), điểm
lá = Value của mạng, thứ tự nước theo Policy; cùng thuật toán với alpha-beta của DQN v1.0 nên dùng để so
hai mạng. Ví dụ: `search = "alphabeta"`, `depth = 3`, `max_think_time_s = 0`,
`device = "cuda"`: khoảng 1,6 s mỗi nước trên RTX 3050 (CUDA Graph), 5–10 s trên CPU. Dùng GPU cần
torch bản CUDA trong `.venv`:
`.venv\Scripts\python -m pip install "torch==2.14.1+cu126" --index-url https://download.pytorch.org/whl/cu126`.

## Đóng gói và cấu hình

Gộp ba checkpoint Kaggle thành một file (lệnh in SHA-256):

```bat
set PYTHONPATH=backend
.venv\Scripts\python -m ai.deep_rl.v20.pack --start START.pt --mid MID.pt --end END.pt --out backend\ai\deep_rl\weights\deeprl-v20.pt
```

Khai báo trong `backend/config/local.toml`:

```toml
[bots.deep_rl]
weights_url = "file:///<đường dẫn tới>/backend/ai/deep_rl/weights/deeprl-v20.pt"
weights_sha256 = "<SHA-256 lệnh pack in ra>"
simulations = 96
```

- V20 bản mới (đội top 1: START A u6000 + MID u6000 + END u6000) đã đóng gói thành
  `deeprl-v20-latest.pt` (`simulations = 196`). Hiện ứng dụng không gắn bản V20 nào: `[bots.deep_rl]`
  dùng DQN v1.0.
- V21 và V22 (một mạng START–MID + END u13000, chuyển sang END khi G ≤ 4) chưa có định dạng bot; sẽ thêm
  khi V22 có kết quả Kaggle.
- Khóa khác: `device` (mặc định `cpu`); `depth`, `max_think_time_s` chỉ dùng cho DQN và V11.
- Bot kiểm SHA-256 trước khi nạp (`weights.py`); file nằm trong `weights/` (gitignore).
- Phát hành cho cả nhóm: đính kèm file vào GitHub Release tag `deeprl-vX.Y`, rồi điền URL và SHA-256
  vào `default.toml`.

## Các file

| File | Vai trò |
|---|---|
| `bot.py`, `weights.py` | Nối với game: tải trọng số, kiểm SHA-256, gọi policy |
| `v20/` | Suy luận V20: mạng 12×128, MCTS hoặc alpha-beta, chọn pha, đóng gói |
| `v11/` | Suy luận V11.2 (mã hóa bàn cờ, nước đi và luật kết thúc dùng chung với `v20/`) |
| `user/` | DQN v1–v10: mạng Q, train, pretrain, alpha-beta (`python -m ai.deep_rl.user.train --help`) |
| `encoding.py`, `env.py`, `evaluate.py`, `opponents.py`, `metrics.py`, `policy_api.py` | Hạ tầng ban đầu, vẫn còn test |
| `weights/` (gitignore) | `deeprl-v1.0.pt` (bot hiện tại), `deeprl-v11.2-curriculum.pt`, `deeprl-v20.pt`, `deeprl-v20-latest.pt` |
| `kaggle/` (gitignore) | Chỉ gói đang dùng: `V22_Unified_START_MID/` (notebook + data ZIP) |

## Huấn luyện

Từ V11, mọi lần train chạy trên Kaggle: upload data ZIP làm Dataset, mở notebook, chạy
`RUN_MODE = "smoke"` rồi `"full"` (phiên bị ngắt thì `"resume"` kèm ZIP resume của phiên trước), tải ZIP
kết quả về thư mục của gói trong `kaggle/`. Notebook và kết quả các đợt trước V22 đã xóa; số liệu nằm trong
EVOLUTION. V22: [§10](DEEP_RL_EVOLUTION.md#10-giai-đoạn-vii--v22-một-mạng-startmid-chưng-cất-stockfish-19-811);
dựng V20 từ đầu: [§12](DEEP_RL_EVOLUTION.md#12-quy-trình-dựng-bot-v20-từ-đầu).
