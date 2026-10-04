# Deep RL (Option 4)

Thư mục `user/` là phần chủ sở hữu tự hoàn thiện: mô hình, tác nhân, replay
buffer, vòng lặp huấn luyện và `load_policy`. Policy cần có
`select_move(board: chess.Board) -> chess.Move`. Phần hạ tầng đã có sẵn trong
`encoding`, `env`, `opponents`, `evaluate` và `metrics`; hiện các tệp lõi trong
`user/` chỉ là khung và chủ động báo `NotImplementedError`.
Bot hiện chơi nước ngẫu nhiên hợp lệ cho đến khi `load_policy` được triển khai.

## Chạy môi trường

```python
from ai.deep_rl.env import ChessEnv
from ai.deep_rl.opponents import RandomOpponent

env = ChessEnv(opponent=RandomOpponent(), agent_color="random", seed=0)
observation, info = env.reset()
observation, reward, terminated, truncated, info = env.step(info["legal_moves"][0])
```

Quan sát có dạng `float32 (18, 8, 8)`. `info` có bản sao bàn cờ và danh sách
nước hợp lệ. Mỗi `step` chạy nước của agent rồi nước trả lời của đối thủ nếu ván
còn tiếp diễn.

## Đánh giá

Sau khi viết `user.policy.load_policy`, chạy:

```shell
python -m ai.deep_rl.evaluate --weights path/to/model.pt --opponent random --games 50
```

`evaluate` luân phiên màu giữa các ván. `MetricsLogger(path).log(step=..., loss=...,
win_rate=..., epsilon=...)` ghi CSV; `plot(csv_path, out_png)` tạo biểu đồ PNG
(cần cài matplotlib).

## Huấn luyện trên Kaggle

Mở `kaggle/train_notebook.ipynb`, đặt URL repo công khai, bật GPU nếu muốn và
chạy các cell. Notebook cài `chess`, gọi module huấn luyện của bạn, đánh giá,
vẽ biểu đồ và nén thư mục kết quả để tải về. Phần huấn luyện chưa được triển
khai trong skeleton.

## Công bố trọng số

Tải checkpoint từ Kaggle, sau đó đính kèm vào GitHub Release với tag dạng
`deeprl-vX.Y`. Tính SHA-256 của asset và điền URL cùng checksum vào
`bots.deep_rl.weights_url` và `bots.deep_rl.weights_sha256`. Bot sẽ tải asset
vào `backend/ai/deep_rl/weights/` và xác minh checksum trước khi nạp policy.
