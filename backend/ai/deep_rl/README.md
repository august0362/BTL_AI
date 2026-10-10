# Deep RL (Option 4) — DQN self-play

Bot học bằng **DQN tự chơi với chính nó** (một mạng chơi cả hai bên). Chưa có trọng số thì
bot đi nước ngẫu nhiên hợp lệ.

## Các file

| File | Vai trò |
|---|---|
| `user/features.py` | Mã hóa bàn cờ 18 plane (lật về phía bên sắp đi) và 4672 nước đi |
| `user/model.py` | CNN residual → Q-value cho 4672 nước |
| `user/replay.py` | Replay buffer dạng vòng, nén bit |
| `user/agent.py` | Mạng chính + mạng đóng băng, action masking, softmax/argmax, Bellman, Huber, soft update |
| `user/train.py` | Vòng self-play + huấn luyện, đánh giá, lưu checkpoint |
| `user/policy.py` | Nạp `best.pt` cho bot (chọn nước argmax) |
| `bot.py`, `weights.py` | Nối với game: tải trọng số từ GitHub Release, kiểm SHA-256 |
| `evaluate.py`, `opponents.py`, `metrics.py` | Đấu thử với đối thủ ngẫu nhiên / tham ăn, ghi và vẽ `metrics.csv` |
| `encoding.py`, `env.py`, `policy_api.py` | Hạ tầng dựng sẵn từ đầu dự án (mã hóa 18 plane/4096 nước cũ, môi trường đấu với đối thủ cố định). DQN self-play không dùng `encoding.py`/`env.py`, nhưng còn test nên giữ lại |

## Thiết kế

- **Đầu vào** `(B, 18, 8, 8)`: 6 plane quân mình, 6 plane quân đối thủ, 2 plane lặp thế cờ
  (đã xuất hiện ≥ 1 / ≥ 2 lần trước), 4 plane quyền nhập thành (mình K/Q, đối thủ K/Q).
  Khi Đen đi, bàn cờ được lật dọc để bên sắp đi luôn ở dưới.
- **Hành động** 4672 = 64 ô đi × 73 kiểu (56 kiểu Hậu, 8 kiểu Mã, 9 phong cấp thấp).
- **Chọn nước**: CNN → Q → mask nước không hợp lệ bằng `-1e9` → softmax(Q/τ) khi train
  (τ 1.0 → 0.1), argmax khi đấu. 1.000 ván đầu đi ngẫu nhiên (ε = 1) để đổ đầy buffer.
- **Học**: `y = r − γ·max Q_target(s', a')` (dấu trừ vì s' là lượt đối thủ; có mask ở s'),
  `y = r` khi hết ván; loss Huber (ngưỡng 1); soft update mạng đóng băng τ = 0.005.
- **Phần thưởng** của nước vừa đi: +1 chiếu hết, 0 hòa, 0 trong ván. Bên thua nhận −1
  gián tiếp qua `−γ·max Q`.
- Mặc định: 15.000 ván, γ = 0.99, Adam lr 1e-4, batch 256, buffer 500.000, 1 bước
  gradient mỗi 4 nửa nước, tối đa 150 nửa nước mỗi ván, CNN 6 khối × 64 kênh,
  64 ván chạy song song. Xem `python -m ai.deep_rl.user.train --help`.

## Chạy thử trên máy

```shell
set PYTHONPATH=backend
.venv\Scripts\python -m ai.deep_rl.user.train --out runs\try --games 300 --warmup-games 100 --channels 32 --blocks 2
.venv\Scripts\python -m ai.deep_rl.evaluate --weights runs\try\best.pt --games 20
```

## Huấn luyện trên Kaggle

1. Dùng `kaggle/deep_rl.zip` (thư mục `deep_rl/`, không có `__pycache__`, `weights`, file zip).
   Sửa code thì tạo lại file zip này rồi upload bản mới (New Version) lên Dataset.
2. Kaggle → **Datasets → New Dataset**, upload `kaggle/deep_rl.zip`.
3. Kaggle → **Code → New Notebook → File → Import Notebook**, chọn
   `kaggle/train_notebook.ipynb`. **Add Input** dataset vừa tạo; **Settings**: GPU, Internet On.
4. **Save Version → Save & Run All** để chạy nền; xong thì tải `run1.zip` ở tab Output.

Kết quả: `best.pt` (trọng số cho bot, điểm đánh giá cao nhất), `final.pt`, `checkpoint.pt`
(chạy tiếp bằng `--resume`), `metrics.csv`, `metrics.png`.

## Công bố trọng số

Đính kèm `best.pt` vào GitHub Release với tag dạng `deeprl-vX.Y`. Tính SHA-256
(`certutil -hashfile best.pt SHA256`) rồi điền URL tải asset và checksum vào
`bots.deep_rl.weights_url` và `bots.deep_rl.weights_sha256`. Bot sẽ tải asset vào
`backend/ai/deep_rl/weights/` và kiểm checksum trước khi nạp.
