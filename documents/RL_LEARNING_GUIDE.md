# Lộ trình học Reinforcement Learning cho Option 4

> Viết cho @august0362: đã biết Python, học máy cơ bản, PyTorch ở mức làm theo được; **chưa học RL**.
> Mục tiêu: tự viết `backend/ai/deep_rl/user/` (mạng, agent, replay, train) đạt mốc RL-1 → RL-3 trong `DEEP_RL_DESIGN.md`.
> Nguyên tắc: **học khái niệm nào thì làm bài tập nhỏ ngay**, không đọc lý thuyết dồn cục.

---

## Chặng 0 — Bức tranh lớn (1 buổi)

RL là học bằng **thử – sai – nhận thưởng**:

```
          hành động a
  Agent ───────────────► Môi trường (bàn cờ + đối thủ)
    ▲                         │
    └──── trạng thái s', thưởng r ◄──┘
```

| Thuật ngữ | Trong dự án này |
|---|---|
| Trạng thái `s` | Thế cờ → `encode_board(board)` (18×8×8) |
| Hành động `a` | Một nước đi hợp lệ |
| Thưởng `r` | +1 thắng / −1 thua / 0 hòa ở cuối ván (+ thưởng quân nếu bật) |
| Episode | Một ván cờ (`env.reset()` … `terminated`) |
| Policy π | Cách chọn nước: `Policy.select_move(board)` |
| Hàm giá trị V(s) / Q(s,a) | Mạng của bạn: "thế cờ này tốt đến đâu" |

**Đọc:** Sutton & Barto, *Reinforcement Learning: An Introduction* (bản miễn phí: http://incompleteideas.net/book/the-book-2nd.html), Chương 1 và mục 3.1–3.3.

## Chặng 1 — Q-learning dạng bảng (2–3 buổi)

**Khái niệm:** return và hệ số chiết khấu γ, phương trình Bellman, **TD learning**, Q-learning, ε-greedy (khám phá và khai thác).

Công thức cốt lõi, cần hiểu từng ký hiệu:

```
Q(s,a) ← Q(s,a) + α · [ r + γ · max_a' Q(s',a') − Q(s,a) ]
                          └──── "mục tiêu TD" ────┘
```

**Đọc:** Sutton & Barto Chương 6 (6.1, 6.2, 6.5). **Xem:** David Silver, *RL Course*, bài 1, 2, 4, 5 (https://www.davidsilver.uk/teaching/).

**Bài tập:** viết Q-learning dạng bảng cho **cờ caro 3×3 (tic-tac-toe)** đánh với bot ngẫu nhiên. Đây là bản thu nhỏ của bài cờ vua: có lượt đi, thắng/thua/hòa, nước hợp lệ.
- Đạt yêu cầu khi: sau khoảng 50k ván, gần như không thua bot ngẫu nhiên.
- Làm trong `notebooks/` cá nhân. Không đưa vào repo.

## Chặng 2 — Deep Q-Network (3–4 buổi)

Bảng Q không chứa nổi mọi thế cờ, nên thay bảng bằng **mạng neural** Q(s,a; θ). Bốn mẹo làm DQN ổn định:

| Mẹo | Vì sao | Bạn viết ở |
|---|---|---|
| **Experience replay** | Các nước liên tiếp quá giống nhau; lấy mẫu ngẫu nhiên từ bộ nhớ giúp học ổn định | `user/replay.py` |
| **Target network** | Mục tiêu TD không "chạy theo" chính mạng đang học | `user/agent.py` |
| **Huber loss + gradient clipping** | Tránh cập nhật quá lớn | `user/agent.py` |
| **Double DQN** | Giảm ước lượng Q quá lạc quan | `user/agent.py` |

**Đọc:**
- Bài báo DQN: Mnih et al. 2015, *Human-level control through deep reinforcement learning* (Nature). Đọc phần Methods.
- OpenAI Spinning Up, phần "Key Concepts" (https://spinningup.openai.com).

**Làm theo:** PyTorch tutorial *Reinforcement Learning (DQN)* với CartPole (https://pytorch.org/tutorials/intermediate/reinforcement_q_learning.html). Chạy trên Kaggle, đọc hiểu từng dòng, rồi **tự gõ lại không nhìn**.

**Tham khảo thêm:** Hugging Face Deep RL Course, Unit 1–3 (https://huggingface.co/learn/deep-rl-course).

## Chặng 3 — Áp dụng vào cờ vua (bắt đầu viết `backend/ai/deep_rl/user/`)

Đi theo các mốc trong `DEEP_RL_DESIGN.md`:

1. **RL-1 — cắm được vào game:**
   - `model.py`: CNN nhận `(N, 18, 8, 8)`, trả `(N, 1)` qua `tanh`.
   - `policy.py`: `load_policy()` nạp mạng (ngẫu nhiên nếu chưa có trọng số). `select_move` dùng `encode_afterstates` rồi chọn nước có điểm cao nhất.
   - Kiểm tra: `pytest another/tests/ai/test_bot_contract.py`, sau đó thấy bot "Deep RL" chọn được trên GUI.
2. **RL-2 — huấn luyện:**
   - `replay.py` + `agent.py` (ε-greedy, cập nhật, target net).
   - `train.py`: vòng lặp với `ChessEnv(opponent=RandomOpponent())`, log qua `MetricsLogger`.
   - Chạy thử 5 phút trên máy, rồi chạy trên Kaggle bằng `backend/ai/deep_rl/kaggle/train_notebook.ipynb`.
3. **RL-3 — đạt chỉ tiêu:** `python -m ai.deep_rl.evaluate --opponent random --games 50` cho kết quả ≥ 90% thắng. Sau đó phát hành trọng số lên GitHub Release.

**Hướng afterstate (gợi ý):** mạng học V(s'), với s' là thế cờ sau nước của mình. Mục tiêu TD cho V(s'_t) là:
- `r` nếu ván kết thúc, hoặc
- `r + γ · V(s'_{t+1})`, trong đó s'_{t+1} là afterstate tốt nhất ở lượt sau của mình (dùng target net).

## Chặng 4 — Khi bot không học (đọc khi gặp)

| Triệu chứng | Kiểm tra |
|---|---|
| Loss = NaN | Learning rate quá lớn? Thiếu `tanh` ở đầu ra? Có clip gradient chưa? |
| Tỷ lệ thắng mãi ~50% với random | ε có giảm không? Reward có đúng **phía** người đi không? (lỗi phổ biến nhất: quên đổi dấu reward khi đổi bên) |
| Thắng random nhưng thua tham lam | Thêm đối thủ tham lam vào `MixedOpponent`; bật thưởng quân nhỏ |
| Học rất chậm | Batch lớn hơn, cập nhật nhiều lần mỗi ván, khai cuộc ngẫu nhiên để đa dạng thế cờ |
| Bot tốt khi train nhưng tệ trong game | `select_move` trong game có đang để ε > 0 không? Có gọi `model.eval()` không? |

## Cách học cùng Claude

- Hỏi khái niệm bất cứ lúc nào, ví dụ: "giải thích target network bằng ví dụ cờ caro".
- Viết xong một file, nhờ Claude **review**. Claude sẽ chỉ ra lỗi và giải thích vì sao, nhưng không viết hộ phần lõi RL (theo yêu cầu của bạn).
- Gửi biểu đồ `metrics` để Claude chẩn đoán vì sao bot chưa học được.
