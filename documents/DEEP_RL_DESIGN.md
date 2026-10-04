# Thiết kế Option 4 — Deep Reinforcement Learning

> Quyết định 2026-10-03: **@august0362 tự viết lõi RL** (mạng, thuật toán học, vòng lặp huấn luyện).
> Codex viết **toàn bộ hạ tầng / adapter** để code của bạn cắm vào là chạy được trong game và trên Kaggle.
> Hướng dẫn học: [RL_LEARNING_GUIDE.md](RL_LEARNING_GUIDE.md). Hợp đồng chung: `documents/CONTEXT.md` §4.1, §7.

---

## 1. Ranh giới: ai viết gì

```
backend/ai/deep_rl/
├── encoding.py        [Codex]  bàn cờ -> mảng numpy 18×8×8; nước đi <-> chỉ số hành động
├── env.py             [Codex]  môi trường kiểu Gym: reset / step / reward / đối thủ
├── opponents.py       [Codex]  đối thủ để luyện: random, tham lam (ăn quân), policy từ checkpoint
├── evaluate.py        [Codex]  cho policy đấu N ván, ghi CSV tỷ lệ thắng
├── metrics.py         [Codex]  ghi log CSV khi train + vẽ biểu đồ cho báo cáo
├── weights.py         [Codex]  tải trọng số từ GitHub Release + kiểm sha256
├── bot.py             [Codex]  DeepRLBot (BaseBot) — gọi policy CỦA BẠN
├── policy_api.py      [Codex]  "ổ cắm": giao diện Policy mà code của bạn phải thỏa
├── kaggle/            [Codex]  notebook mẫu: clone repo, cài thư viện, gọi train của bạn
└── user/              [BẠN]    lõi RL — Codex chỉ tạo khung có TODO, KHÔNG viết thuật toán
    ├── model.py         mạng neural (PyTorch)
    ├── agent.py         chọn nước (ε-greedy), cập nhật Q / V, target network...
    ├── replay.py        replay buffer
    ├── train.py         vòng lặp huấn luyện
    └── policy.py        load_policy(): nạp trọng số -> đối tượng Policy dùng trong game
```

## 2. "Ổ cắm" — hợp đồng giữa code của bạn và phần còn lại

```python
# backend/ai/deep_rl/policy_api.py  (Codex viết)
class Policy(Protocol):
    def select_move(self, board: chess.Board) -> chess.Move: ...   # nước hợp lệ cho board.turn

# backend/ai/deep_rl/user/policy.py  (BẠN viết — Codex tạo khung raise NotImplementedError)
def load_policy(weights_path: Path | None, device: str = "cpu") -> Policy: ...
    # weights_path None -> khởi tạo ngẫu nhiên (dùng cho test hợp đồng / chưa train)
```

`DeepRLBot` (Codex viết):
1. Lấy đường dẫn trọng số qua `weights.py` (tải từ Release nếu có `weights_url`).
2. Gọi `user.policy.load_policy(...)`.
3. Mỗi nước: `policy.select_move(board)`, kiểm tra nước hợp lệ, ghi `last_search_info`.
4. Khi `load_policy` còn `NotImplementedError`: raise `BotUnavailableError("deep_rl: chưa cài policy")`. Khi đó GUI hiện mờ bot, test hợp đồng skip, và **không có gì bị hỏng** trong lúc bạn đang học và viết dần.

## 3. Công cụ Codex cung cấp cho bạn

**`encoding.py`** — không phụ thuộc torch, trả `numpy.float32`:
- `encode_board(board) -> (18, 8, 8)`, luôn nhìn từ phía **bên sắp đi** (lật bàn khi đen đi):

  | Mặt phẳng | Nội dung |
  |---|---|
  | 0–5 | Quân của mình: Tốt, Mã, Tượng, Xe, Hậu, Vua |
  | 6–11 | Quân đối thủ, cùng thứ tự |
  | 12–15 | Quyền nhập thành: mình K/Q, đối thủ K/Q |
  | 16 | Ô bắt tốt qua đường |
  | 17 | `halfmove_clock / 100` |

- `encode_afterstates(board, moves) -> (N, 18, 8, 8)`: thế cờ sau từng nước, nhìn từ phía bên **vừa đi**. Dùng cho hướng B (afterstate).
- `move_to_action(move, turn) / action_to_move(index, board)`: ánh xạ 4.096 hành động (ô đi × ô đến, lật theo bên đi; phong cấp mặc định Hậu, phong cấp dưới chọn ngẫu nhiên nhỏ). Dùng cho hướng A.
- `legal_action_mask(board) -> (4096,) bool`.

**`env.py`** — môi trường kiểu Gymnasium (không cần cài gymnasium):

```python
env = ChessEnv(opponent=RandomOpponent(), agent_color=chess.WHITE | "random",
               reward=RewardConfig(win=1, draw=0, loss=-1, material_coef=0.0),
               max_plies=200, random_opening_plies=(0, 4), seed=0)
obs, info = env.reset()          # info["board"], info["legal_moves"]
obs, reward, terminated, truncated, info = env.step(move)   # đối thủ tự đi luôn trong step
```

- `material_coef > 0` thì cộng thưởng nhỏ theo chênh lệch quân sau mỗi lượt (bật/tắt tùy bạn).

**`opponents.py`:** `RandomOpponent`, `GreedyCaptureOpponent` (ưu tiên ăn quân giá trị cao, nếu không có thì ngẫu nhiên), `PolicyOpponent(policy)` (đấu với bản cũ của chính bạn), `MixedOpponent([(opp, weight), ...])`.

**`evaluate.py`:** `evaluate(policy, opponent, n_games, seed) -> EvalResult(wins, draws, losses, avg_plies)`; tự đổi màu quân luân phiên. Có CLI: `python -m ai.deep_rl.evaluate --weights path --opponent random --games 50`.

**`metrics.py`:** `MetricsLogger(csv_path).log(step=..., **values)`; `plot(csv_path, out_png)` vẽ loss, tỷ lệ thắng, epsilon theo step.

**`kaggle/train_notebook.ipynb`:**
1. Clone repo public, `pip install chess`.
2. Kiểm tra GPU.
3. `python -m ai.deep_rl.user.train --out /kaggle/working/run1`.
4. Đánh giá, vẽ biểu đồ, nén thư mục kết quả để tải về.

## 4. Mục tiêu và mốc

| Mốc | Tiêu chí |
|---|---|
| RL-0 (Codex) | Hạ tầng xong, có test; `DeepRLBot` báo "chưa cài policy" |
| RL-1 (bạn) | `load_policy` với mạng khởi tạo ngẫu nhiên → bot xuất hiện trên GUI, qua test hợp đồng |
| RL-2 (bạn) | Huấn luyện chạy được trên Kaggle, có biểu đồ loss / tỷ lệ thắng |
| RL-3 (bạn) | ≥ 90% thắng `RandomOpponent` trên 50 ván → phát hành `deeprl-v1.0` (CONTEXT §7) |
| RL-4 (bạn) | Thắng `GreedyCaptureOpponent` đa số ván (điểm cộng) |

## 5. Gợi ý thiết kế (để bạn tham khảo, không bắt buộc)

- **Hướng B (afterstate)** dễ thành công hơn hướng A: mạng chỉ trả 1 số cho mỗi thế cờ.
- Trộn đối thủ: random → tham lam → bản cũ của chính mình.
- Thưởng phụ theo quân: bật nhỏ (0,05–0,1) lúc đầu, giảm dần về 0.
- Mạng: CNN 3×3, 64 kênh, 4–6 khối residual, đầu ra `tanh`.
