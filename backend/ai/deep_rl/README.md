# Deep RL (Option 4)

Bot `deep_rl` trong ứng dụng là **RL Hybrid**. Lịch sử v1 → V22X: [DEEP_RL_EVOLUTION.md](DEEP_RL_EVOLUTION.md).

## RL Hybrid

File `deeprl-v22x-filtered-hybrid.pt` (29 MB) có định dạng `v20-phase-experts-1` với 3 ô `start` / `mid` /
`end`, nhưng thực chất chỉ chứa 2 mạng PolicyValueNet 12×128:
- `start` = `mid` = V22X FILTERED u38000: học từ nhãn Stockfish 19 trên Lichess eval DB.
- `end` = END u13000: tàn cuộc, học từ Tablebase + Mate.

Cách chơi (`search = "ramp"`):
- MCTS PUCT 200 lượt, tối đa 1 s mỗi nước.
- Từ nước đầu tiên của mình có `G = 4·Hậu + 2·Xe + Tượng + Mã ≤ 4`, bot chuyển hẳn sang mạng END.

`run.bat` tải file này từ GitHub Release `models-*` và kiểm SHA-256. Cấu hình của bot nằm trong
`models.json` của release, được gộp vào config.

## Định dạng trọng số

| `format` | Bản | Cách chơi | Mã |
|---|---|---|---|
| `deep_rl_dqn_v1` | v1–v10 | `depth = 1`: argmax Q; `depth >= 2`: alpha-beta, lá = max Q | `user/` |
| `v11-policy-value-mcts-2` | V11.2 | MCTS `simulations` lượt | `v11/` |
| `v20-phase-experts-1` | V20, V22, V22X | Các `search`: `mcts` (theo pha), `alphabeta`, `hybrid`, `ramp` | `v20/` |

Dùng file khác trên máy mình thì khai báo trong `backend/config/local.toml`:

```toml
[bots.deep_rl]
weights_url = "file:///<đường dẫn>/backend/ai/deep_rl/weights/<file>.pt"
weights_sha256 = "<SHA-256>"
```

Gộp các checkpoint thành một file: `python -m ai.deep_rl.v20.pack --start S.pt --mid M.pt --end E.pt --out X.pt`
(chạy với `PYTHONPATH=backend`; lệnh in ra SHA-256).

## Các file

| File | Vai trò |
|---|---|
| `bot.py`, `weights.py` | Nối với game: tải trọng số, kiểm SHA-256, gọi policy |
| `v20/` | Mạng 12×128, MCTS / alpha-beta / ramp, chọn pha, đóng gói |
| `v11/` | Suy luận V11.2 |
| `user/` | DQN v1–v10: mạng Q, train, pretrain, alpha-beta |
| `encoding.py`, `env.py`, `evaluate.py`, `opponents.py`, `metrics.py`, `policy_api.py` | Hạ tầng ban đầu, vẫn còn test |
| `weights/` (gitignore) | Trọng số đã tải |
| `kaggle/` (gitignore) | Notebook + data ZIP của V22 / V22X; ZIP kết quả trong `kaggle/output/` |

## Huấn luyện

Từ V11, mọi lần train chạy trên Kaggle. Các bước:
1. Upload data ZIP làm Dataset.
2. Chạy notebook với `RUN_MODE = "smoke"`, sau đó `"full"`. Phiên bị ngắt thì chạy `"resume"` kèm ZIP
   resume của phiên trước.
3. Tải ZIP kết quả về `kaggle/output/`.

Chi tiết từng đợt nằm trong [DEEP_RL_EVOLUTION.md](DEEP_RL_EVOLUTION.md).
