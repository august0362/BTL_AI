# Deep RL (Option 4) — DQN self-play

Bot học bằng **DQN tự chơi với chính nó** (một mạng chơi cả hai bên). Chưa có trọng số thì
bot đi nước ngẫu nhiên hợp lệ. Các phiên bản và kết quả đo: [EVOLUTION.md](EVOLUTION.md).

## Các file

| File | Vai trò |
|---|---|
| `user/features.py` | Mã hóa bàn cờ 18 plane (lật về phía bên sắp đi) và 4672 nước đi |
| `user/model.py` | CNN residual → Q-value cho 4672 nước |
| `user/replay.py` | Replay buffer dạng vòng, nén bit |
| `user/agent.py` | Mạng chính + mạng đóng băng, action masking, softmax/argmax, Bellman, Huber, soft update |
| `user/train.py` | Vòng self-play + huấn luyện, đánh giá, lưu checkpoint |
| `user/pretrain.py` | Pretrain từ PGN kỳ thủ: nước của bên thắng, Cross-Entropy → `sl_pretrained.pt` |
| `user/policy.py` | Nạp trọng số cho bot: `depth = 1` argmax Q, `depth >= 2` alpha-beta |
| `user/search.py` | Alpha-beta (negamax) độ sâu `depth`, điểm lá = max Q của mạng, iterative deepening theo `max_think_time_s` |
| `bot.py`, `weights.py` | Nối với game: tải trọng số từ GitHub Release, kiểm SHA-256 |
| `evaluate.py`, `opponents.py`, `metrics.py` | Đấu thử với đối thủ ngẫu nhiên / tham ăn, ghi và vẽ `metrics.csv` |
| `encoding.py`, `env.py`, `policy_api.py` | Hạ tầng dựng sẵn từ đầu dự án (mã hóa 18 plane/4096 nước cũ, môi trường đấu với đối thủ cố định). DQN self-play không dùng `encoding.py`/`env.py`, nhưng còn test nên giữ lại |

## Thiết kế

- **Đầu vào** `(B, 18, 8, 8)`: 6 plane quân mình, 6 plane quân đối thủ, 2 plane lặp thế cờ
  (đã xuất hiện ≥ 1 / ≥ 2 lần trước), 4 plane quyền nhập thành (mình K/Q, đối thủ K/Q).
  Khi Đen đi, bàn cờ được lật dọc để bên sắp đi luôn ở dưới.
- **Hành động** 4672 = 64 ô đi × 73 kiểu (56 kiểu Hậu, 8 kiểu Mã, 9 phong cấp thấp).
- **Chọn nước**: CNN → Q → mask nước không hợp lệ bằng `-1e9` → softmax(Q/τ) khi train
  (τ cố định `--temperature`, mặc định 0.3), argmax khi đấu. 1.000 ván đầu đi ngẫu nhiên (ε = 1) để đổ đầy buffer.
- **Học**: `y = r − γ·max Q_target(s', a')` (dấu trừ vì s' là lượt đối thủ; có mask ở s'),
  `y = r` khi hết ván; loss Huber (ngưỡng 1); soft update mạng đóng băng τ = 0.005.
- **Phần thưởng** của nước vừa đi: +1 chiếu hết, 0 hòa, 0 trong ván. Bên thua nhận −1
  gián tiếp qua `−γ·max Q`.
- Mặc định: 15.000 ván, γ = 0.99, Adam lr 1e-4, batch 256, buffer 500.000, 1 bước
  gradient mỗi 4 nửa nước, tối đa 150 nửa nước mỗi ván, CNN 6 khối × 64 kênh,
  64 ván chạy song song. Xem `python -m ai.deep_rl.user.train --help`.

## Khi đấu trong game: alpha-beta + mạng Q

`[bots.deep_rl]`: `depth = 3` (mặc định), `max_think_time_s = 1.0`.
- Điểm một thế cờ (theo bên sắp đi) = `max Q(s, a)` trên nước hợp lệ; chiếu hết / hòa tính
  chính xác. Tầng cuối dùng luôn Q(s, a) nên độ sâu 3 chỉ chạy mạng ở tầng 2 (theo batch).
- Iterative deepening 1 → `depth`; hết giờ thì dùng độ sâu đã xong. `depth = 1` = chỉ argmax Q.
- Điểm lá chỉ có nghĩa khi Q là **giá trị** (trọng số sau self-play RL). Trọng số chỉ pretrain
  (Cross-Entropy) cho "độ tự tin về nước đi", nên khi thử bản SL hãy đặt `depth = 1`.

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

## Pretrain từ ván kỳ thủ (rồi mới self-play)

Thư mục `kaggle/pre-train/` (chỉ trên máy, không push) chứa PGN (`.pgn` hoặc `.zip`) và
2 notebook: `pretrain_notebook.ipynb` (ra `sl_pretrained.pt`) và `selfplay_notebook.ipynb` (self-play từ `sl_pretrained.pt`).

- Chỉ lấy ván có người thắng; học nước của **bên thắng** (Trắng hoặc Đen). Mỗi thế cờ:
  `X = encode(board)` (18 × 8 × 8), `y = move_to_action(nước)` trong `[0, 4672)`.
- Thế cờ được lưu sẵn vào `positions.npz`; tách 10 % số ván làm tập kiểm tra, xáo trộn,
  batch 256, logit trước `tanh` + mask → Cross-Entropy, Adam lr 1e-3, 15 epoch. Bản có Top-1
  accuracy kiểm tra cao nhất lưu thành `sl_pretrained.pt`.
- Self-play sau đó: `train.py --init-weights sl_pretrained.pt --warmup-games 0
  --temperature 0.3 --lr 5e-5`.

Khi tự chơi, có thể bật DQfD bằng `--expert-pgn <file.pgn/.zip hoặc thư mục>` để mỗi batch lấy
25 % chuyển tiếp từ ván kỳ thủ (`--expert-fraction 0.25`); loss margin (`--margin 0.05`,
`--margin-weight 1.0`) giữ Q của nước kỳ thủ cao hơn các nước hợp lệ khác ít nhất 0,05.

Có thể bật bài tập chiếu hết trước curriculum bằng `--mate-puzzles <mate_puzzles.csv>`. CSV gồm
`level,puzzle_id,fen,solution`, dùng puzzle Lichess đã kiểm chứng; bot luyện chiếu hết sau 1–4 nước
rồi mới chuyển sang tàn cuộc, trung cuộc và cả ván. Các cờ `--mate-max-level`,
`--mate-pass-rate`, `--mate-window`, `--mate-min-games`, `--mate-max-games`,
`--mate-temperature` điều khiển cấp, tỷ lệ lên cấp, cửa sổ đánh giá, giới hạn số ván và nhiệt độ.
`--mate-expert 1` thêm nước tấn công trong lời giải vào buffer DQfD. `--mate-review "2:1=0.25;3:1=0.10,2=0.15;4:1=0.05,2=0.08,3=0.12"` cho một phần ván ôn lại cấp cũ (ví dụ cấp 2 có 25 % ván cấp 1); ván ôn lại không tính vào điều kiện lên cấp.

### Curriculum (Backplay)

Dùng `--curriculum-pgn <file.pgn/.zip hoặc thư mục>` để bắt đầu các ván gần cuối PGN quyết định,
rồi lùi dần về khai cuộc: `--endgame-fraction` 30 % endgame (lùi 2–20 nửa nước,
`--endgame-back-min/max`), `--middlegame-fraction` 30 % middlegame (20–80,
`--middlegame-back-min/max`), 10 % (`--free-fraction`) từ
đầu ván với giới hạn dài, phần còn lại từ đầu ván với `--max-plies` (mặc định 150). Các pha dài
dùng `--long-max-plies` (mặc định 400); `--max-hours` giới hạn thời gian và vẫn lưu checkpoint.
Để tắt curriculum, bỏ `--curriculum-pgn`.

### v6: giữ tín hiệu chiếu hết

v6 chuẩn hóa Q hợp lệ trước softmax, tăng nhiệt độ tuyến tính bằng `--temp-start` và
`--temp-ramp-fraction`, giới hạn tàn cuộc/trung cuộc bằng `--endgame-max-plies` và
`--middlegame-max-plies`. Có thể trộn ván chiếu hết qua `--decisive-fraction` và
`--decisive-buffer-size`, đồng thời dùng trả thưởng nhiều bước với `--n-step`.

Chạy trên máy: `python -m ai.deep_rl.user.pretrain --pgn backend\ai\deep_rl\kaggle\pre-train --out runs\pre`.
Trên Kaggle: upload `kaggle/deep_rl.zip` (đã gồm `kaggle/pre-train/*.zip`) làm New Version của dataset,
import notebook 1 (`pretrain_notebook.ipynb`), GPU + Internet On, **Save & Run All**. Notebook 2
(`selfplay_notebook.ipynb`) thêm Input là output của notebook 1 để lấy `sl_pretrained.pt`.

## Công bố trọng số

Đính kèm `best.pt` vào GitHub Release với tag dạng `deeprl-vX.Y`. Tính SHA-256
(`certutil -hashfile best.pt SHA256`) rồi điền URL tải asset và checksum vào
`bots.deep_rl.weights_url` và `bots.deep_rl.weights_sha256`. Bot sẽ tải asset vào
`backend/ai/deep_rl/weights/` và kiểm checksum trước khi nạp.

### v7

v7 th?m value pretrain (`--value-weight`, `--potential-scale`, `--gamma`), potential shaping, ph?t h?a (`--draw-penalty`), Double DQN (`--double-dqn`) v? lr warm-up (`--lr-warmup-games`, `--lr-warmup-factor`). Pretrain v? self-play ph?i d?ng c?ng `potential_scale`.

### v7

v7 th?m value pretrain (`--value-weight`, `--potential-scale`, `--gamma`), potential shaping, ph?t h?a (`--draw-penalty`), Double DQN (`--double-dqn`) v? lr warm-up (`--lr-warmup-games`, `--lr-warmup-factor`). Pretrain v? self-play ph?i d?ng c?ng `potential_scale`.

v7.1 pretrain dùng `--ce-weight 0 --margin-weight 1 --margin 0.05 --value-weight 1` để học thứ tự nước mà không xung đột với giá trị.

### v9: trộn pha để không quên

`--phase-mix "middlegame:endgame=0.25;full:endgame=0.15,middlegame=0.2;full150:endgame=0.15,middlegame=0.2"`
cho mỗi pha thường một phần ván bắt đầu kiểu pha trước; `--puzzle-review 0.05` thêm 5 % ván từ puzzle
chiếu hết ở mọi pha. `--mate-level-max-games "3=10000,4=10000"` đặt số ván tối đa riêng từng cấp.
`--bench-eval-games 20` đấu 20 ván với Benchmark 1.5 (alpha-beta đếm quân độ sâu 3, viết lại trong
`opponents.py`) ở cuối mỗi pha / cấp; `--snapshot-every 5000` lưu `snap_5k.pt`, `snap_10k.pt`…
`--puzzle-expert-fraction` / `--regular-puzzle-expert-fraction` đưa lời giải puzzle vào kho riêng với tỉ lệ
batch riêng (bài tập / ván thường); khi cả hai bằng 0, lời giải gộp vào kho chuyên gia như trước.

### v10: lộ trình đan xen

`--game-schedule "0:mate=0.3,tactic=0.2,endgame=0.4,middlegame=0.1;…;1:…"` chọn kiểu bắt đầu mỗi ván
(`mate`, `tactic`, `endgame`, `middlegame`, `full`, `full150`) theo tiến độ, nội suy tuyến tính giữa
các mốc; khi có cờ này không còn khối bài tập chiếu hết. `--batch-schedule` làm tương tự cho phần batch
lấy từ các kho cố định (`pgn`, `decisive`, `mate`, `tactic`). `--tactic-puzzles` là CSV puzzle chiến thuật
Lichess (`puzzle_id,theme,fen,solution`).
