# Nhật ký tiến hóa bot Deep RL

Ghi lại từng phiên bản của bot `deep_rl`: đã đổi gì, vì sao đổi, và kết quả đo được. Bản mới
nhất ở cuối. Cách dùng code xem [README.md](README.md).

**Quy ước đo:** mỗi ván đấu thử tối đa 150 nửa nước; muốn thắng phải chiếu hết, quá 150 nửa nước
là hòa. Đối thủ: `random` (đi ngẫu nhiên), `greedy` (luôn ăn quân to nhất nếu được), `AB3`
(benchmark `bench_alphabeta_material`, alpha-beta thuần độ sâu 3). Kết quả ghi theo
**thắng / hòa / thua** của bot Deep RL.

| Phiên bản | Ngày | Ý chính | Trạng thái |
|---|---|---|---|
| v0 | 2026-10-04 | Hạ tầng + bot đi ngẫu nhiên | Thay thế |
| v1 | 2026-10-09 | DQN tự chơi từ đầu | Đã phát hành `deeprl-v1.0` |
| v2 | 2026-10-10 | Pretrain từ ván kỳ thủ (Cross-Entropy) | Đã train |
| v2.1 | 2026-10-10 | Khi đấu: alpha-beta độ sâu 3, điểm lá = max Q | Đang dùng trong game |
| v3 | 2026-10-10 | Self-play tiếp từ trọng số pretrain | Đang train |
| v4 | 2026-10-10 | DQfD: trộn ván kỳ thủ vào self-play | Đã thử: Q vẫn sụp về ~0 |
| v5 | 2026-10-10 | Curriculum ngược: tàn cuộc → trung cuộc → cả ván | Đã thử: tốt ở ván 500, rồi Q sụp |
| v6 | 2026-10-10 | Giữ tín hiệu cuối ván (Q chuẩn hóa, n-step, buffer chiếu hết…) | Đã thử: "cú sốc Bellman" |
| v7 | 2026-10-10 | Pretrain có giá trị, khinh hòa, PBRS (quân + PST), Double DQN, lr khởi động | Code xong, chưa train |
| v8 | 2026-10-11 | Bài tập chiếu hết sau 1 → 4 nước (puzzle Lichess), lên cấp khi đạt chuẩn, ôn lại cấp cũ; λ = 0 | Đã train: `deeprl-v8-best.pt` |
| v9 | 2026-10-11 | Trộn pha cũ vào pha mới + puzzle ôn 5 %, đo thêm B1.5, ảnh chụp mỗi 5.000 ván | Đã dừng: bài tập vẫn làm quên |
| v10 | 2026-10-12 | Lộ trình đan xen: bỏ khối bài tập, mọi loại ván / kho mẫu trộn từ đầu, tỉ lệ đổi dần; thêm puzzle chiến thuật | Code xong, chưa train |

---

## v0: hạ tầng (2026-10-04)

- Có sẵn `encoding.py` (18 plane, 4096 nước), `env.py`, `opponents.py`, `evaluate.py`,
  `metrics.py`, `weights.py` (tải trọng số từ GitHub Release, kiểm SHA-256).
- Thư mục `user/` chỉ là khung; chưa có trọng số thì bot đi nước ngẫu nhiên hợp lệ.

## v1: DQN tự chơi từ đầu (2026-10-09)

**Thiết kế**
- Đầu vào `(18, 8, 8)`, luôn lật về phía bên sắp đi: 6 plane quân mình, 6 quân đối thủ, 2 plane
  lặp thế cờ, 4 plane quyền nhập thành.
- Hành động: 4672 = 64 ô × 73 kiểu (kiểu AlphaZero). Mask nước không hợp lệ bằng `-1e9`.
- Mạng: CNN 6 khối residual × 64 kênh, GroupNorm, đầu ra qua `tanh` để Q ∈ [-1, 1].
- Học: mạng đóng băng soft update τ = 0.005; `y = r − γ·max Q_target(s')` (dấu trừ vì s' là
  lượt đối thủ); loss Huber ngưỡng 1; γ = 0.99, Adam lr 1e-4, batch 256, buffer 500.000.
- Phần thưởng: +1 chiếu hết, 0 hòa, 0 trong ván.
- 1.000 ván đầu đi ngẫu nhiên (ε = 1) để đổ đầy buffer; sau đó softmax(Q/τ), τ giảm 1.0 → 0.1;
  tổng 15.000 ván, chạy 64 ván song song.

**Kết quả** (Kaggle T4, 3 giờ 35 phút)
- `score` khi train: 0,49 → khoảng 0,59.
- Đấu thử 100 ván với `final.pt`: `random` 24 / 76 / 0, `greedy` 7 / 91 / 2. So với bot đi ngẫu
  nhiên (4,5 / 93 / 2,5 và 0,5 / 89 / 10,5): thắng `random` nhiều hơn khoảng 5 lần, gần như
  không thua `greedy`.
- Phát hành: GitHub Release `deeprl-v1.0`, file `deeprl-v1.0.pt` (1,76 MB),
  SHA-256 `a523ce21…1b39`.

**Bài học**
- Khoảng 92% ván tự chơi bị cắt ở 150 nửa nước, phần thưởng gần như luôn bằng 0. Tín hiệu quá
  thưa nên bot học rất chậm.
- Thêm cách tính thời gian còn lại khi train: làm mượt số giây mỗi ván
  `E = 0.3·x + 0.7·E`, `eta = E × số ván còn lại` (ở ván 1.500 dự kiến 202 phút, thực tế 207).

## v2: pretrain từ ván kỳ thủ (2026-10-10)

**Thay đổi**
- Dữ liệu: `Kasparov.pgn` (2.128 ván) + `Carlsen.pgn` (7.818 ván) = 9.946 ván. Chỉ lấy ván có
  người thắng (6.732 ván, bỏ 3.213 ván hòa) và chỉ nước của **bên thắng**, cả Trắng lẫn Đen:
  296.366 thế cờ. File PGN không có Elo nên không lọc theo Elo.
- Học có giám sát: logit trước `tanh` + mask → Cross-Entropy, Adam lr 1e-3, batch 256, tách 10%
  số ván làm tập kiểm tra, lưu bản có Top-1 accuracy kiểm tra cao nhất (`sl_pretrained.pt`).
- Thêm `Model.logits()`; `forward = tanh(logits)` nên trọng số cũ vẫn dùng được.

**Kết quả** (Kaggle, 15 epoch)
- Top-1 accuracy kiểm tra cao nhất 35,1% ở epoch 10. Từ khoảng epoch 8, loss kiểm tra tăng trong
  khi loss học vẫn giảm (học thuộc dữ liệu): khoảng 10 epoch là đủ.
- Bản mạng nhỏ thử trên máy (32 kênh × 2 khối, 2 epoch, 40 ván): `random` 15 / 25 / 0,
  `greedy` 12 / 26 / 2, đã hơn hẳn v1 về khả năng không thua.
- Gặp `AB3` (10 ván, bản Kaggle): 0 / 3 / 7. Chơi theo "trực giác" mà không tính trước nước
  nào nên dễ để mất quân.

**Bài học**
- Cross-Entropy chỉ dạy nước nào **cao hơn** nước nào trong cùng một thế cờ (softmax không đổi
  khi cộng cùng một hằng số). Vì vậy `max tanh(logit)` của bản SL là "độ tự tin về nước đi",
  không phải giá trị thế cờ.

## v2.1: alpha-beta khi đấu (2026-10-10)

**Thay đổi** (`user/search.py`, chỉ dùng lúc đấu, không ảnh hưởng train)
- Alpha-beta (negamax) độ sâu `depth = 3`; giá trị một thế cờ = `max Q(s, a)` trên nước hợp lệ;
  chiếu hết / hòa tính chính xác theo luật.
- Tầng cuối dùng luôn Q(s, a), nên độ sâu 3 chỉ cần chạy mạng ở tầng 2, theo batch.
- Iterative deepening trong `max_think_time_s = 1.0` giây; hết giờ dùng độ sâu đã xong.
- Cấu hình ở `[bots.deep_rl]`: `depth = 3` (1 = chỉ dùng mạng), `max_think_time_s = 1.0`.

**Kết quả gặp `AB3`** (trên CPU)

| Trọng số | Cách chơi | Thắng / hòa / thua | Tốc độ |
|---|---|---|---|
| v2 (SL) | chỉ mạng | 0 / 3 / 7 (10 ván) | — |
| v2 (SL) | alpha-beta độ sâu 3 | 0 / 4 / 6 (10 ván) | ~0,4 giây/nước |
| v1 (DQN) | alpha-beta độ sâu 3 | 2 / 4 / 2 (8 ván) | ~0,75 giây/nước |

**Bài học**
- Alpha-beta chỉ giúp khi Q là **giá trị** thế cờ (trọng số sau RL). Với bản chỉ pretrain, hãy
  đặt `depth = 1`.

## v3: self-play tiếp từ trọng số pretrain (2026-10-10, đang train)

**Thay đổi**
- `train.py --init-weights sl_pretrained.pt`: nạp vào cả mạng chính lẫn mạng đóng băng.
- Không có ván ngẫu nhiên khởi động (`--warmup-games 0`), lr 5e-5, 15.000 ván.
- Nhiệt độ softmax τ cố định (`--temperature`, mặc định 0.3) thay cho τ giảm dần.
- Tách 2 notebook trong `kaggle/pre-train/`: `pretrain_notebook.ipynb` và
  `selfplay_notebook.ipynb`.

**Quan sát ban đầu** (log Kaggle, 20 ván mỗi lần)
- Ván 500: `random` 2 / 18 / 0, ván 1.000: `random` 10 / 10 / 0. Bot yếu đi ở đầu giai đoạn RL
  rồi học lại: Bellman kéo các "độ tự tin" của SL về thang giá trị (gần 0 vì phần thưởng gần
  như luôn 0), làm nhòe thứ tự nước học từ kỳ thủ.

**Sự cố đã sửa**
- Kaggle (torch 2.11, Python 3.13) đã nạp `torch._utils` nhưng không gắn vào `torch`, nên
  `torch.load(weights_only=True)` báo `no attribute '_utils'`. Sửa: `load_file()` tự gắn
  `torch._utils` trước khi nạp. Lỗi `no attribute 'dtype'` sau đó là do phiên notebook bị hỏng
  vì chạy lại cell nhiều lần; khởi động lại phiên / Save & Run All là hết.

## v4: DQfD, trộn ván kỳ thủ vào self-play (2026-10-10, code xong, chưa train)

**Thay đổi** (theo Hester et al. 2018, *Deep Q-learning from Demonstrations*)
- Mỗi nước của bên thắng trong PGN thành một mẫu (s, a, r, s'); nước cuối của bên thắng được
  thưởng +1 và tính là hết ván, kể cả khi đối thủ xin thua.
- Mỗi batch học: 75% mẫu self-play + 25% mẫu kỳ thủ (`--expert-fraction 0.25`).
- Loss = TD (Huber, Bellman như cũ) trên cả batch + λ·margin trên phần kỳ thủ, với
  `margin = mean[ max_a (Q(s,a) + 0.05·[a ≠ a_E]) − Q(s, a_E) ]`, λ = 1 (`--margin 0.05`,
  `--margin-weight 1.0`). Phần margin giữ nước kỳ thủ cao hơn mọi nước khác mà không phá thang
  giá trị như Cross-Entropy.
- Code do Codex viết (prompt `documents/codex/RL-1_dqfd.md`).

**Chạy thử trên máy** (mạng nhỏ, 64 ván, chỉ để kiểm tra code): nạp 296.366 mẫu kỳ thủ; loss
margin giảm 0,58 → 0,27.

**Cần so sánh khi có kết quả:** v3 với v4, theo các dòng `SL vs …` / `RL vs …` cuối notebook và
đấu `AB3` với `depth = 3`.

**Kết quả trên Kaggle** (20 ván mỗi lần đấu thử): ván 500 `random` 4 / 15 / 1, ván 1.000
`random` 1 / 18 / 1, `q ≈ 0`, `td ≈ 0,004`, `margin ≈ 0,05` (= đúng khoảng margin): Q của mọi
nước gần như bằng nhau, tức **Q sụp về ~0**. DQfD làm chậm nhưng không chặn được. Nguyên nhân
chính: phần thưởng quá thưa (~92% ván bị cắt ở 150 nửa nước, mục tiêu Bellman gần như luôn 0).

## v5: curriculum ngược (2026-10-10)

**Thay đổi** ("Backplay", Resnick và cộng sự 2018; `user/curriculum.py`)
- 30.000 ván, 4 giai đoạn theo thứ tự ván: 30% bắt đầu từ thế cách cuối một ván có người thắng
  trong PGN 2–20 nửa nước (tàn cuộc), 30% cách cuối 20–80 nửa nước (trung cuộc), 10% từ đầu ván
  không cố định độ dài (trần 400), 30% cuối từ đầu ván tối đa 150 nửa nước như trong giải.
- Giữ: khởi đầu từ `sl_pretrained.pt`, DQfD, lr 5e-5, τ = 0,3, phần thưởng ±1 (chưa thưởng
  theo quân). `--max-hours 11.5` dừng an toàn trước giới hạn 12 giờ của Kaggle (notebook không
  tự chạy tiếp từ checkpoint). Log thêm `phase` và `decisive` (tỉ lệ ván tự chơi kết thúc bằng chiếu hết).
- Code do Codex viết (prompt `documents/codex/RL-3_curriculum.md`).

**Chạy thử trên máy** (trọng số pretrain, 120 ván, CPU): ván bắt đầu từ tàn cuộc / trung cuộc
kết thúc bằng chiếu hết **35–40%** (trước đây gần như 0), Q giữ ở khoảng −0,2 … −0,37 thay vì
sụp về 0; khi chuyển sang ván từ đầu 150 nửa nước, tỉ lệ chiếu hết giảm còn ~7%.

**Kết quả trên Kaggle** (20 ván mỗi lần đấu thử): ván 500 `q = −0,357`, `decisive = 29%`,
`random` 9 / 11 / 0, `greedy` 6 / 14 / 0, score 0,688 (lần chạy khác: 0,713) — tốt nhất từ trước
tới giờ. Từ ván 1.000: `q ≈ 0`, `margin → 0,05`, `decisive` 5–9% ngay trong giai đoạn tàn cuộc,
score ~0,6; buffer đầy 500.000 mẫu ở ván ~3.500. Dừng ở ván ~6.500; `best.pt` (ván 500) lưu thành
`deeprl-v5.pt`, dùng thử trong Xếp hạng AI.

**Chẩn đoán**: Q phẳng + `softmax(Q/0,3)` trên Q thô → tự chơi gần như ngẫu nhiên → ván tàn cuộc
không dứt điểm, kéo dài tới 400 nửa nước, buffer ngập mẫu thưởng 0 → Q càng phẳng (vòng luẩn quẩn).

## v6: giữ tín hiệu cuối ván (2026-10-10)

**Thay đổi** (prompt `documents/codex/RL-4_keep_terminal_signal.md`): softmax trên Q chuẩn hóa
`(Q − mean)/std`, τ tăng 0 → 0,3 trong 30% số ván đầu; tàn cuộc bắt đầu cách cuối 2–10 nửa nước,
trần 60 (trung cuộc trần 120); buffer riêng ván chiếu hết (25% mỗi batch); n-step TD n = 5 (negamax
`G = r₀ − γr₁ + …`, bootstrap `(−γ)ᵏ·max Q`); DQfD 50%, λ = 2; đấu thử 10 ván.

**Kết quả trên Kaggle** (10 ván mỗi lần đấu thử):

| Ván | τ | q | td | margin | decisive | score |
|---|---|---|---|---|---|---|
| 501 | 0,02 | 0,805 | 1,147 | 0,083 | 19,8% | 0,575 |
| 1.000 | 0,03 | 0,652 | 0,964 | 0,073 | 6,0% | 0,575 |
| 2.000 | 0,07 | −0,028 | 0,456 | 0,057 | 4,4% | 0,575 |
| 3.000 | 0,10 | −0,057 | 0,467 | 0,054 | 2,6% | 0,600 |
| 6.000 | 0,20 | −0,003 | 0,433 | 0,057 | 3,6% | 0,550 |

**Chẩn đoán: "cú sốc Bellman"**. `decisive` rơi khi τ mới 0,02–0,08 (gần argmax), nên không phải do
τ. Trọng số SL (Cross-Entropy) cho `max tanh(logit) ≈ +1` ở mọi thế ("bên nào cũng tin mình
thắng", `q = 0,8`), Bellman đòi `y ≈ −γ·1 ≈ −1` → sai số ~1,5–2 trên hầu hết mẫu (`td = 1,15`),
mạng bị ghi đè diện rộng và mất thứ tự nước học từ kỳ thủ (`margin → 0,05`). Argmax trên Q nhiễu
nên không dứt điểm được. Ngay cả ở đầu (τ ≈ 0), bản SL chỉ dứt điểm ~20% thế cách cuối 2–10 nửa
nước.

**Hướng v7**: pretrain thêm giá trị (hồi quy Q của nước đã đi về `+γᵏ` cho bên thắng, `−γᵏ` cho
bên thua) để Q xuất phát khớp Bellman; Double DQN; lr thấp ở ~1.000 ván đầu.

## v7: sửa "cú sốc Bellman" và xu hướng hòa (2026-10-10, code xong, chưa train)

**Thay đổi** (prompt `documents/codex/RL-6_v7.md`):
- **Pretrain có giá trị**: ngoài Cross-Entropy (nước bên thắng), hồi quy Q(s, nước đã đi) của
  **mọi nước của cả hai bên** về `±γᵏ − Φ(s)` (+ bên về sau thắng, − bên thua, k = số nửa nước còn
  lại); `--value-weight 1`, 10 epoch. Q xuất phát đúng thang ±1, khớp nhãn Bellman.
- **Khinh hòa**: nước kết thúc ván hòa theo luật nhận −0,1 (`--draw-penalty 0.1`).
- **PBRS**: `r' = r − γΦ(s') − Φ(s)`, Φ = `0,5·tanh(điểm quân + PST Michniewski / 400)` theo góc nhìn
  bên sắp đi (kiểu Benchmark 2), Φ = 0 ở thế kết thúc; tổng cả ván triệt tiêu về `−Φ(s₀)` nên không
  đổi chiến lược tối ưu. Áp cho cả mẫu tự chơi và mẫu kỳ thủ. Khi đấu, điểm lá = `max Q + Φ(s)`;
  file trọng số ghi `meta.potential_scale`.
- **Double DQN** (mạng chính chọn nước ở s', mạng đóng băng chấm) và **lr khởi động** 10 % → 100 %
  trong 1.000 ván đầu.

**Chạy thử trên máy** (mạng nhỏ, pretrain 2 epoch + 200 ván tự chơi, CPU): `td` ở đầu RL = 0,40
(v6: 1,15), `decisive` 15–31 %.

**Pretrain v7 trên Kaggle** (mạng 64 × 6, 10 epoch, lưu epoch 6): Top-1 accuracy 34 %; đấu thử
50 ván, chỉ mạng (argmax): `random` 28 / 22 / 0, `greedy` 22 / 28 / 0 — bản chọn nước mạnh nhất từ
trước tới giờ. `val_value_loss` ≈ 0,35, cao hơn mức đoán 0 (0,207).

**Thí nghiệm v7.1** (mạng 32 × 2, 1.500 bước, cùng dữ liệu; "gần cuối" = |nhãn| ≥ 0,6):

| Cách pretrain | Top-1 | Huber giá trị (đoán 0: 0,202) | Đúng dấu ở thế gần cuối | Q trung bình |
|---|---|---|---|---|
| Chỉ CE | 28,6 % | 0,414 | 56,6 % | **+0,416** |
| CE + giá trị (v7) | 27,7 % | 0,350 | 56,8 % | **+0,049** |
| Margin + giá trị (v7.1) | 12,8 % | 0,202 | 55,4 % | +0,031 |
| CE chỉ đẩy nước khác xuống + giá trị | 6,8 % | 0,626 | 44,8 % | −1,000 (sụp) |

Kết luận: từ ~6.700 ván, mạng **gần như không học được giá trị** (đúng dấu chỉ ~56 %, kể cả gần cuối
ván) — dữ liệu quá ít để đoán thắng thua. Nhưng phần giá trị vẫn có ích: kéo **Q trung bình từ
+0,42 về ~0**, bỏ được độ lệch gây "cú sốc Bellman", mà giữ nguyên khả năng chọn nước. Margin
(v7.1) làm chọn nước kém hẳn nên **giữ v7** (CE + giá trị); code v7.1 còn (`--ce-weight`,
`--margin-weight`) nhưng notebook dùng cấu hình v7.

## v8: bài tập chiếu hết trước curriculum (2026-10-11, code xong, chưa train)

**Vì sao**: log self-play v7 — `decisive` 22,6 % → 4,6 % trong 2.500 ván đầu dù τ ≈ 0; bot không
biết dứt điểm nên không thấy +1. Trong 6.732 ván PGN có người thắng, chỉ **309 ván** kết thúc bằng
chiếu hết (còn lại đối thủ xin thua) → không đủ dạy chiếu hết.

**Thay đổi** (prompt `documents/codex/RL-8_mate_drills.md`, `RL-9_mate_review.md`):
- Dữ liệu: bộ puzzle **Lichess** (CC0, ~5 triệu puzzle, 307 MB nén) → lọc **2.000 thế mỗi cấp**
  `mateIn1…4` (độ phổ biến ≥ 80, ≥ 100 lượt giải; sau tăng lên 10.000, xem dưới), kiểm tra lại từng lời giải bằng python-chess (đủ
  2N − 1 nửa nước, nước cuối chiếu hết) → `kaggle/pre-train/mate_puzzles.csv` (650 KB).
- Self-play bắt đầu bằng **cấp 1**: mỗi ván từ một puzzle ngẫu nhiên, trần `2N − 1` nửa nước; **lên
  cấp** khi tỉ lệ chiếu hết ≥ 80 % trong 500 ván gần nhất (≥ 500 ván, tối đa 4.000 ván/cấp); xong
  cấp 4 mới tới tàn cuộc → trung cuộc → cả ván (`--games` chỉ đếm phần này).
- **Ôn lại**: cấp 2 có 25 % ván cấp 1; cấp 3 có 10 % cấp 1 + 15 % cấp 2; cấp 4 có 5 % / 8 % / 12 %
  cấp 1 / 2 / 3; ván ôn không tính vào điều kiện lên cấp. `--learning-starts 1000` (ván cấp 1 chỉ 1
  nửa nước).
- `--mate-expert 1` (**bật**): nước của bên chiếu hết trong lời giải vào phần mẫu chuẩn (DQfD),
  nguồn +1 chắc chắn kể cả khi bot chưa tự tìm ra nước chiếu hết.

**Chạy thử trên máy** (mạng nhỏ 32 × 2, pretrain 2 epoch, 900 ván/cấp, không bật `--mate-expert`):
tỉ lệ chiếu hết đúng hạn cấp 1 → 4: **19,7 % / 15,3 % / 10,3 % / 5,3 %** — cơ chế chạy đúng, nhưng
chưa đạt chuẩn 80 % sau 900 ván.

**Kaggle lần 1–2**: lần 1 lr kẹt 5e-6 (khởi động lr tính theo ván thường) → `--lr-warmup-games 0`.
Lần 2: `q` tăng 0,53 → **1,000**, `td ≈ 1,0`, `margin = 0,0500`; chiếu hết cấp 1 chỉ 5,8 % sau 4.000
ván, cấp 2 0,6 %. **Thủ phạm: loss margin DQfD (λ = 2)**: kéo Q mọi nước trôi lên tới khi tanh bão
hòa (mọi Q ≈ 1, đạo hàm ≈ 0, softmax gần như chọn bừa). Thử trên máy (trọng số v7, cấp 1, 3.000 ván):

| Cấu hình | Chiếu hết khi luyện | Argmax (puzzle đã gặp) | q cuối |
|---|---|---|---|
| Như notebook (mẫu tuyển thủ 50 %, λ = 2) | 4,0 % | 12,5 % (v7 gốc: 13,3 %) | 0,994 |
| Không mẫu tuyển thủ | 28,2 % | — | 0,38 |
| Mẫu tuyển thủ 50 %, **λ = 0** | **35,6 %** | **40,2 %** | 0,27 |

Bản λ = 0 trên puzzle **chưa gặp**: cấp 1 → 4 = 39 / 21,5 / 12 / 7,5 % (v7 gốc: 12 / 5,5 / 1,5 / 2 %).
→ Notebook: `--margin-weight 0`; mỗi cấp **10.000 puzzle** luyện + 500 puzzle kiểm tra riêng
(`mate_puzzles_test.csv`, cell cuối notebook đo argmax), `--mate-max-games 20000` (3.000 ván cấp 1
chỉ có ~750 bước học).

**Bài học về margin**: dấu hiệu `margin ≈ 0,050` (mọi nước bằng nhau) đã có từ v4 (λ = 1) và v6
(λ = 2), khi đó bị đọc thành "phần thưởng thưa" / "cú sốc Bellman" mà chưa thử tắt riêng margin.
DQfD gốc dùng Q tuyến tính; với đầu ra `tanh` (Q ∈ [−1, 1]) margin đẩy Q tới bão hòa và mạng kẹt.
Từ v8 self-play dùng λ = 0; `margin` trong log chỉ còn là chỉ số theo dõi (≈ 0,05 là báo động).

**Kaggle lần 3** (λ = 0, 10.000 puzzle/cấp): chiếu hết cấp 1 tăng 11 % → 56 % sau 8.500 ván,
`q ≈ 0,35`, `margin ≈ 0,53`; nhưng `score` đấu thử giảm 0,825 → ~0,55 (cần theo dõi).

**Đấu nội bộ** (20 ván, luật Xếp hạng AI): v7 pretrain chỉ dùng mạng (`depth = 1`) vs v1
(`depth = 3`): **0 / 6 / 14**; v7 pretrain `depth = 3` vs v1 `depth = 3`: **1 / 7 / 12**. Trọng số
chỉ pretrain yếu hơn v1 cả khi có lẫn không có cây: pretrain chưa thay được RL.

## v9: trộn dữ liệu để không quên (2026-10-11, code xong, chưa train)

**Vì sao**: v8 trượt ở pha `full150` (mục "Kaggle lần 3") vì curriculum nối tiếp thuần.

**Thay đổi** (Claude viết trực tiếp, không qua Codex):
- Mỗi ván thường bốc kiểu bắt đầu theo pha (`--phase-mix`, `--puzzle-review 0.05`):

  | Pha (độ dài) | Tàn cuộc | Trung cuộc | Từ đầu | Puzzle |
  |---|---|---|---|---|
  | Tàn cuộc (30 %) | 95 % | – | – | 5 % |
  | Trung cuộc (30 %) | 25 % | 70 % | – | 5 % |
  | Full, trần 400 (20 %) | 15 % | 20 % | 60 % | 5 % |
  | Full150 (20 %) | 15 % | 20 % | 60 % | 5 % |

- Cấp 3–4 tối đa 10.000 ván (`--mate-level-max-games`), cấp 1–2 vẫn 20.000.
- Đấu thử 20 ván mỗi đối thủ `random` / `greedy` (mỗi 500 ván); thêm 20 ván với **B1.5** ở cuối mỗi
  cấp / pha (`MaterialAlphaBetaOpponent` trong `opponents.py`, 2 nửa nước khai cuộc ngẫu nhiên; kiểm
  tra: giá trị nước chọn trùng Benchmark 1.5 gốc 48/48, ~0,04 giây/nước). `best.pt` vẫn chọn theo
  random + greedy.
- Ảnh chụp `snap_5k.pt` … `snap_30k.pt` (`--snapshot-every 5000`).
- **Mẫu kỳ thủ (PGN) 50 % → 3 %** mỗi batch: pretrain đã học xong nước kỳ thủ; v8 dành nửa thời gian
  học cho thế cờ kỳ thủ (gần như không có quân treo) nên Q không biết ăn quân. Lời giải puzzle tách
  kho riêng: **30 %** batch khi làm bài tập, **5 %** ở ván thường (`--puzzle-expert-fraction`,
  `--regular-puzzle-expert-fraction`).

- Cột log **`gm%`**: 500 thế của các ván kiểm tra pretrain (bỏ khỏi kho kỳ thủ), tỉ lệ nước Q cao
  nhất trùng nước kỳ thủ. Mốc: pretrain **35 %** (khớp accuracy 34 %), v8 **14 %**, v1 16 % → v8 quên
  gần hết kiến thức kỳ thủ dù 37 % batch là PGN (λ = 0: mẫu PGN chỉ học bằng TD, không giữ thứ tự nước).
- Mẫu kỳ thủ **10 % giảm tuyến tính về 3 %** theo ván thường (`--expert-fraction-end 0.03`).
- Log đổi thành 2 dòng có nhãn + 1 dòng trống.
- Cột log **`tac%`** (`user/tactics.py`): trên 300 thế cố định có quân đối thủ ≥ 3 điểm bị treo, tỉ lệ
  nước Q cao nhất ăn đúng quân đó. Mốc: v1 **69 %**, pretrain v7 **69 %**, v8 **47 %** → pretrain
  không hỏng, chính self-play v8 làm mất kỹ năng ăn quân.

**v8 khi đấu thật** (`deeprl-v8-best.pt`, alpha-beta độ sâu 3, 20 ván): gặp v1 **1 / 4 / 15**; Xếp hạng
AI 7 / 1 / 10 (v1: 8 / 3 / 7). Nguyên nhân: Q xếp nước ăn không Hậu thứ 3 sau nước Tốt (v1 xếp nhất),
nên thứ tự nước kém → chỉ 21 % nước đạt độ sâu 3 (v1: 73 %) → ở độ sâu 2 không thấy mất quân → treo
quân liên tục. Chỉ số train (argmax vs random/greedy) không đo được chiến thuật.

## v10: lộ trình đan xen (2026-10-12, code xong, chưa train)

**Vì sao**: v9 trên Kaggle (có `tac%` / `gm%`) cho thấy chính **khối bài tập chiếu hết** làm quên:
trong cấp 1, `tac` 69 % → 51 % sau 3.000 ván → 38 % sau 14.000 ván; `gm` 35 % → 22 % → 15 %, dù
mẫu kỳ thủ là 10 %. Bài tập chỉ đổi lấy chiếu hết sau 1 nước — thứ alpha-beta khi đấu đã tự tìm được.

**Thay đổi** (`user/schedule.py`, `--game-schedule`, `--batch-schedule`, `--tactic-puzzles`):
- Không còn khối bài tập: mỗi ván bốc kiểu bắt đầu theo lộ trình, tỉ lệ nội suy tuyến tính theo tiến độ:

  | Tiến độ | Chiếu hết | Chiến thuật | Tàn cuộc | Trung cuộc | Từ đầu 400 | Từ đầu 150 |
  |---|---|---|---|---|---|---|
  | 0 % | 30 % | 20 % | 40 % | 10 % | – | – |
  | 25 % | 25 % | 15 % | 40 % | 15 % | 5 % | – |
  | 50 % | 20 % | 10 % | 30 % | 20 % | 10 % | 10 % |
  | 75 % | 15 % | 10 % | 20 % | 15 % | 15 % | 25 % |
  | 100 % | 10 % | 10 % | 15 % | 10 % | 20 % | 35 % |

  Cấp chiếu hết bốc theo lộ trình riêng (`--mate-level-schedule`): 0 % L1 70 / L2 30; 25 % 30 / 40 / 30;
  50 % 15 / 25 / 35 / 25; ≥ 75 % 10 / 20 / 35 / 35 (≈ cấp 3 900 ván, cấp 4 580 ván / 30.000), không còn
  ngưỡng 80 %.
- Batch (5 mốc như bảng ván): tự chơi 45 / 50 / 57 / 64 / 70 %, ván chiếu hết tự chơi 10 / 10 / 12 / 12 / 12 %,
  kỳ thủ 10 / 8 / 6 / 5 / 5 %, lời giải chiếu hết 10 / 10 / 8 / 6 / 5 %, lời giải chiến thuật 25 / 22 / 17 /
  13 / 8 %. Lý do: ván puzzle rất ngắn nên chỉ chiếm vài % mẫu tự chơi — phần học chiếu hết / chiến
  thuật thật sự đến từ kho lời giải; giảm chiếu hết (tránh dồn như v9), tăng chiến thuật (điểm yếu
  `tac`), kỳ thủ có sàn 5 % (neo `gm`).
- **Puzzle chiến thuật** Lichess (không chiếu hết): 10.000 luyện + 500 kiểm tra (`tactic_puzzles.csv`),
  chủ đề hangingPiece 3.150, fork 2.100, pin 1.575, skewer / discoveredAttack 1.050, trappedPiece /
  capturingDefender 788; 23.546 mẫu lời giải. Ván chiến thuật trần = độ dài lời giải.
- B1.5 đo mỗi 20 % tiến độ.
- **Tăng dữ liệu** (2026-10-12): puzzle chiếu hết **20.000/cấp** (cấp 4 gần hết 24.843 bài có sẵn;
  200.000 mẫu lời giải), puzzle chiến thuật **30.000** (70.785 mẫu lời giải), tổng **40.000 ván**
  (≈ cấp 3 1.250 ván, cấp 4 750 ván). Bộ kiểm tra giữ nguyên (cùng seed). Nạp dữ liệu ≈ 2 phút, ≈ 400 MB.

## Hướng tiếp theo (chưa làm)

- **Sau khi thắng được v1** — đối thủ ngoài: ~10–20 % ván thường cho B1.5 (độ sâu 1 → 2 → 3 theo pha)
  cầm một bên. Self-play có "điểm mù chung" (hai bên cùng không ăn quân treo nên lỗi không bị phạt);
  DQN học off-policy nên nước của đối thủ vẫn là dữ liệu hợp lệ. Rủi ro: đối thủ quá mạnh (luôn −1),
  bắt bài riêng một đối thủ, và chậm (B1.5 độ sâu 3 ~0,05–0,1 giây/nước trên CPU).

- **Ưu tiên tiếp theo — curriculum có ôn lại**: v8 Kaggle lần 3 trượt ở pha `full150` (thắng `random`
  ~6,1/10 so với ~7,1–7,3 ở trung cuộc / full) vì curriculum nối tiếp thuần, kho 500k mẫu bị ván từ đầu
  thay hết → quên kỹ năng dứt điểm. Sửa: mỗi pha sau trộn % ván bắt đầu từ pha trước (vd full150 =
  60 % mới + 20 % tàn cuộc + 20 % trung cuộc), hoặc kho riêng không bị ghi đè; lưu ảnh chụp mỗi 5.000
  ván; `--eval-games 30`.

- **Sau khi RL xong** (chỉ khi `final.pt` thắng được v1): tăng sức tìm kiếm trong `user/search.py`,
  không cần train lại — sắp xếp nước theo Q, chỉ xét top-k nước (giữ nước chiếu / ăn quân) để lên độ
  sâu 4–5, quiescence search ở lá, bảng chuyển vị.
- Bài tập "dồn Vua" (Hậu/Xe + Vua vs Vua đơn) nếu bot vẫn hay hòa vì hết nước khi hơn quân.
- Giảm `--mate-max-games` cho cấp 3–4 (chững sớm) để tiết kiệm thời gian Kaggle.
- Thêm PGN của kỳ thủ khác để có nhiều dữ liệu hơn.
