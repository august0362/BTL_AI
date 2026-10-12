# Benchmark 9 — Kết quả đo

Mọi số dưới đây là trận thật, chạy ngày 2026-10-11 trên máy phát triển (Intel i5-12500H, 12 nhân / 16 luồng, Windows 11, Python 3.13), bằng `another/tools/bench9_strength.py`. Dữ liệu thô: `database/data/bench9_strength/` (gitignore).

## Điều kiện

- Luật giải thật: `GameState(max_plies=150, claim_draw=True)`, `max_think_time_s = 1.0` cho **cả hai** bot.
- Mỗi bot chạy trong tiến trình riêng (`ProcessPlayer`, như Xếp hạng AI); thời gian nghĩ đo bên trong tiến trình bot; RAM = đỉnh RAM mỗi ván (B9 gồm cả tiến trình Stockfish).
- Khai cuộc ngẫu nhiên 2 nửa nước (như giải), **ghép cặp đổi màu**: mỗi khai cuộc chơi 2 ván, B9 cầm Trắng một ván, Đen một ván. Seed ghi lại.
- B9: Stockfish 19, 1 luồng, hash 16 MB. Đối thủ: cấu hình `default.toml` + `local.toml` của máy.
- Nhiều ván chạy song song (8 hoặc 6 ván) để rút ngắn thời gian → tốc độ của mọi bot thấp hơn khi chơi một ván (B9: 340–760 knps thay vì ~650 knps khi máy rảnh). Điều này làm yếu cả hai bên, không thiên vị B9.
- Elo: logistic; khoảng tin cậy 95 %. Khi thắng 100 % chỉ có **cận dưới** một phía (pⁿ ≥ 0,05) — Elo thật không ước lượng được bằng các đối thủ này.

## Kết quả sức mạnh

| Đối thủ | Ván | Thắng/Hòa/Thua | Điểm | Elo (cận dưới 95 %) | Kết thúc | Nửa nước TB |
|---|---|---|---|---|---|---|
| B7 · Dragon (`bench7`) | 200 | 200/0/0 | 100 % | > +729 | 200 chiếu hết | 63,2 |
| B8 · Luna (`bench8_luna`) | 200 | 200/0/0 | 100 % | > +729 | 200 chiếu hết | 64,7 |
| B6 · GPT | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 68,3 |
| B6 · Gemini | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 67,1 |
| B6 · DeepSeek | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 66,7 |
| B5 · Hybrid | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 63,6 |
| B5 · GPT | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 62,4 |
| B5 · DeepSeek | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 55,6 |
| B4 · Alpha-Beta Custom | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 60,1 |
| B2 · Alpha-Beta 3 (AB3) | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 46,2 |
| Deep RL (`deep_rl`, v1.0) | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 38,3 |
| Deep RL bản mới (`deep_rl_next`, chỉ có trên máy này) | 50 | 50/0/0 | 100 % | > +484 | 50 chiếu hết | 32,4 |
| **Tổng** | **900** | **900/0/0** | | | **900 chiếu hết** | |

Seed: 9 (B7/B8, 100 khai cuộc), 19 (các đối thủ còn lại, 25 khai cuộc). 0 ván bị hủy, 0 lỗi, 0 lần phải khởi động lại engine (`fallback`).

**Mục tiêu "vượt B7/B8" đã được chứng minh** với độ tin cậy cao (400 ván, 0 ván không thắng). Mục tiêu "+50 Elo so với B7" bị vượt xa — cận dưới 95 % là +729. Elo chính xác của B9 so với các bot này **không đo được** (mọi ván thắng), chỉ biết cận dưới.

### Mốc 150 nửa nước

Không ván nào chạm mốc: ván dài nhất kết thúc bằng chiếu hết trước 150 nửa nước, trung bình 32–68 nửa nước tùy đối thủ. Vì vậy không cần (và đã không thêm) heuristic nào theo mốc của giải.

## Thời gian và tài nguyên của B9

| Đối thủ | Nghĩ TB (s) | Nghĩ tối đa (s) | Nước > 1,0 s | Độ sâu TB | knps TB | RAM TB / tối đa (MB) | RAM đối thủ TB (MB) |
|---|---|---|---|---|---|---|---|
| B7 | 0,883 | 1,134 | 23 | 43,1 | 339 | 232 / 327 | 30 |
| B8 | 0,883 | 0,994 | 0 | 45,5 | 659 | 237 / 251 | 61 |
| B6 · GPT / Gemini / DeepSeek | 0,876–0,878 | 0,975 | 0 | 44,6–46,5 | 695–756 | 237–239 / 252 | 26–44 |
| B5 · Hybrid | 0,858 | 1,530 | 5 | 47,9 | 632 | 235 / 252 | 15 |
| B5 · GPT / DeepSeek | 0,864–0,868 | 1,051 | 2 | 46,3–48,1 | 629–750 | 233–235 / 247 | 13–19 |
| B4, AB3 | 0,850–0,864 | 0,987 | 0 | 47,6–49,8 | 617–684 | 232–234 / 327 | 0–3 |
| Deep RL (2 bản) | 0,823–0,865 | 0,981 | 0 | 43,1–52,8 | 426–435 | 223–226 / 235 | 196–199 |

"Độ sâu TB" là trung bình độ sâu Stockfish báo cáo; cao vì thế cờ gần chiếu hết được tìm rất sâu. Độ sâu điển hình ở trung cuộc là 20–25.

**Về các nước vượt trần (30/≈27 000 nước):** chúng dồn thành hai cụm — ván 25–176 của trận B7 (đúng lúc chạy pytest + render GUI song song với 8 ván, knps tụt xuống ~75k) và ván 197–219 của trận thứ hai (cùng lúc chạy `ruff`/`lint-imports`). Ngoài hai cụm đó, nước chậm nhất là 0,994 s. Nguyên nhân: tiến trình bị hệ điều hành giành CPU *giữa* lúc tìm, chính sách độ trễ thích nghi (đo độ trễ thật mỗi nước) không thể đoán trước một đợt quá tải bất ngờ. Sau trận đầu, `time_safety_s` mặc định được tăng 0,02 → 0,03 s. Giải Xếp hạng AI chạy từng ván một nên không có mức tải này. Kiểm chứng trên máy rảnh: xem mục dưới.

### Trận kiểm chứng trên máy rảnh

1 ván một lúc, không chạy gì khác, seed 29, 5 khai cuộc ghép cặp × 2 đối thủ:

| Đối thủ | Ván | Thắng/Hòa/Thua | Nghĩ TB / tối đa (s) | Nước > 1,0 s | Độ sâu TB | RAM TB (MB) |
|---|---|---|---|---|---|---|
| B5 · Hybrid | 10 | 10/0/0 | 0,878 / 0,973 | 0 | 44,4 | 327 |
| B7 · Dragon | 10 | 10/0/0 | 0,867 / 0,973 | 0 | 44,3 | 327 |

Không nước nào vượt trần khi máy không bị quá tải; biên an toàn thực tế ≈ 27 ms. RAM của tiến trình Stockfish khi chạy một mình là ~327 MB (khi nhiều tiến trình Stockfish chạy song song, mạng NNUE được chia sẻ giữa các tiến trình nên mỗi tiến trình báo thấp hơn, ~230 MB) — con số đúng cho giải (từng ván một) là **~330 MB**.

## Bức tranh trong bảng Xếp hạng AI

Bảng Xếp hạng AI không chỉ tính sức cờ: **Tổng = điểm ván + (thời gian TB − của bot)/100 + (RAM TB − của bot)/100 MB + thưởng**. Dự kiến cho B9:

- **Điểm ván:** cao nhất (thắng gần như mọi ván).
- **Thời gian:** dùng gần hết trần (~0,85–0,96 s/nước), dài hơn các bot cố định độ sâu (B1–B4) → mất một ít điểm thời gian.
- **RAM:** ~330 MB/ván khi chạy từng ván (tiến trình Stockfish, chủ yếu mạng NNUE 109 MiB + binary), cao hơn hẳn các bot Python (0–60 MB; Deep RL ~200 MB) → mất ~2,5 điểm so với trung bình.

Nghĩa là B9 mạnh nhất về sức cờ một cách áp đảo, nhưng **vị trí chính xác trên bảng Tổng phụ thuộc trọng số thời gian/RAM** và chưa được đo bằng một lượt giải đầy đủ — không khẳng định "hạng nhất" ở bảng Tổng.

## Tái lập

```bat
set PYTHONPATH=backend;frontend;another
.venv\Scripts\python another\tools\bench9_strength.py --opponents bench7,bench8_luna --pairs 100 --workers 8 --seed 9
.venv\Scripts\python another\tools\bench9_strength.py --opponents bench_alphabeta3,bench_alphabeta_custom,bench5_gpt,bench5_deepseek,bench5_hybrid,bench6_gpt,bench6_gemini,bench6_deepseek,deep_rl,deep_rl_next --pairs 25 --workers 6 --seed 19
```

Lưu ý: trận B7/B8 chạy với `time_safety_s = 0,02`, trận thứ hai với 0,03 (mặc định hiện tại). `bench5_grok`, `bench6_grok`, `bench5_gemini` không tham gia đo và đã bị bỏ khỏi repo theo yêu cầu.
