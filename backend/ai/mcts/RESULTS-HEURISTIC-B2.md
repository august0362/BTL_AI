# Kết quả cải tiến MCTS heuristic trước Benchmark 2

## Kết luận thực nghiệm

**Chưa đạt mục tiêu thắng 100%.** Bản gọn được bàn giao đạt
**37 thắng, 2 hòa, 1 thua / 40 ván**,
tức **92.5% tỷ lệ thắng** trong loạt xác nhận.
Không dùng tỷ lệ điểm hoặc tỷ lệ không thua để gọi là tỷ lệ thắng.

Bản thêm che chắn vua, tốt thông và ưu tiên đáp trả đạt
35 / 4 / 1 trên nhóm 40 khai cuộc đổi màu khác. Hai loạt không cùng seed,
nên không kết luận thống kê rằng bản này chắc chắn mạnh hơn bản kia.
Chọn bàn giao bản gọn vì yêu cầu ít quy tắc, dễ giải thích; nguồn thử nghiệm
phức tạp hơn và mọi ván không thắng vẫn được giữ để đối chiếu.

Đây là MCTS heuristic có minimax/Alpha-Beta ngắn ở lá, không gọi là Pure MCTS.
Pure MCTS vẫn có thể chọn với use_heuristics=false và không gọi heuristic mới.

## Đối thủ và điều kiện

- Repo thực đọc: august0362/BTL_AI, commit **f16f85b374abf8a2ff20beebadaff93632c97ad3**.
- Đối thủ: bench_alphabeta3 / BenchmarkAlphaBetaBot gốc, Alpha-Beta độ sâu 3,
  đánh giá material + PST; không fast_mode. Ngân sách mỗi bot 1 s/nước.
- SHA-256 các file benchmark được kiểm tra trùng Git HEAD; không sửa đối thủ,
  trọng số, luật, registry hoặc công thức xếp hạng.
- Mỗi cặp dùng cùng seed, 2 ply khai cuộc, hai màu; giới hạn 150 ply/ván,
  claim_draw=true. Độ sâu đối thủ ghi theo từng ván là 3, trừ lượt chỉ một nước hợp lệ (0).
- Máy Linux / Python 3.13.18 / chess 1.11.2, nproc=9; một số loạt chạy đồng thời.
  Thời gian là số đo trong điều kiện đó, không phải cam kết trên laptop Windows.

## Phát triển, lựa chọn và xác nhận

Trên cùng 20 ván ở seed 20261201–20261210:

| Bản | Thắng / hòa / thua |
|---|---:|
| MCTS cũ | 0 / 5 / 15 |
| Bản kiểm tra hai ply, c=0,015 | 20 / 0 / 0 |

20/20 là loạt dùng để lựa chọn cấu hình. Sau đó giữ nguyên mã và chạy 40 ván
seed 20261401–20261420: kết quả 37 / 2 / 1, không còn là 100% thắng.
Điều này cho thấy vì sao không nên bảo đảm 100% từ một loạt thử thuận lợi.

Một vòng cải tiến chiến lược khác được kiểm tra trên seed 20261801–20261820,
kết quả 35 / 4 / 1; không chọn riêng ván thắng để tính tỷ lệ.

## Kết quả đầy đủ

Các tên thư mục là ID thí nghiệm, không phải tên bot mới trong GUI.

| Loạt | Thắng / hòa / thua | Trung bình/nước |
|---|---:|---:|
| screen_depth2_006 | 11 / 0 / 1 | 0.946 s |
| screen_depth2_0015 | 11 / 1 / 0 | 0.937 s |
| screen_captures_only | 8 / 0 / 0 | 0.555 s |
| screen2_q | 19 / 0 / 1 | 0.540 s |
| screen2_d2 | 20 / 0 / 0 | 0.942 s |
| before_holdout | 0 / 5 / 15 | 0.948 s |
| confirmation_b2 | 37 / 2 / 1 | 0.947 s |
| memory_b2 | 2 / 0 / 0 | 0.948 s |
| regression_candidate2 | 8 / 0 / 0 | 0.941 s |
| confirmation_v2_b2 | 35 / 4 / 1 | 0.946 s |
| memory_v2_b2 | 2 / 0 / 0 | 0.946 s |
| final_random | 20 / 0 / 0 | 0.913 s |
| selected_random | 20 / 0 / 0 | 0.904 s |
| selected_memory | 2 / 0 / 0 | 0.947 s |

Bản được bàn giao: **mcts-heuristic-b2-1**, leaf_depth=2,
exploration_constant=0.015, max_tree_nodes=1024, trần 1 s.
Thời gian trung bình trước B2 0.947 s/nước;
cao nhất 0.981 s; số nước vượt 1 s: 0.
Nguồn của nó được đối chiếu cả với candidate1_source.zip và SHA-256 của loạt xác nhận.
Chọn bản gọn sau khi xem hai thử nghiệm không làm số liệu trở thành một bảo đảm tổng quát.

Kiểm tra Random riêng của bản bàn giao: **20 / 0 / 0 / 20 ván**,
seed 20262201–20262210. Không lấy thành tích này để khẳng định chắc thắng B2.

## Nội dung mã

1. Giữ cây MCTS, RNG riêng, mở nhánh ngẫu nhiên và robust child nhiều lượt thăm nhất.
2. Vật chất + điểm ô theo giai đoạn; ưu tiên vua an toàn đầu ván và tham gia tàn cuộc.
3. Hai ply kiểm tra ngắn, sau đó ổn định chuỗi ăn quân tối đa 4 ply; xét mọi thoát chiếu.
4. Kết hợp 0,2 điểm mẫu trung bình với 0,8 giá trị đáp trả tốt nhất đã biết của đối phương,
   giữ prior khi chưa thử hết nước. Pure dùng UCT/rollout cũ.
5. Chỉ copy một board mỗi nước, phục hồi toàn bộ stack, tối đa 1024 nút và giải phóng cây ngay.
6. Không dùng engine ngoài, trọng số học sẵn, sách khai cuộc, tra FEN hoặc nhận diện seed đối thủ.

Đọc HUONG_DAN_HEURISTIC.md để giải thích từng phần bằng ví dụ.

## Kiểm thử và giới hạn còn tồn tại

- **65 passed**: test MCTS và hợp đồng lọc MCTS; toàn bộ test MCTS cũ giữ nguyên.
- Ruff toàn dự án, format và 3 hợp đồng import: đạt.
- Full suite ngoài thư mục Deep RL: **582 passed, 3 skipped, 1 failed**;
  coverage core/tournament **89,42%**.
- Test còn lỗi: another/tests/tournament/test_process_player.py::test_memory_usage_reports_current_and_peak.
  Reader Linux của phần dùng chung trả current > peak một lượng nhỏ trong môi trường này.
  Lỗi cũng xuất hiện khi chạy riêng test đó, không gọi bot MCTS. File reader và test
  không bị sửa. Chưa xác nhận toàn bộ CI xanh; cần chạy test.bat trên Windows.
- Số MB trong raw memory trials là OS peak trừ baseline của reader trên; do lỗi kiểm tra
  reader còn tồn tại, chỉ lưu làm dữ liệu tham khảo, không dùng làm cam kết RAM chính xác.
- Deep RL chưa được chạy do môi trường không có PyTorch; không cài dependency mới cho MCTS.
- Đã phát lại độc lập **226 PGN**, kiểm tra
  mọi nước hợp lệ, kết quả, luật kết thúc, màu, khai cuộc, source hash và benchmark không đổi.
- Không sửa/xóa test có sẵn, không thay module dùng chung, không commit/push hoặc tạo branch.

## Cài đặt

Giải nén MCTS-heuristic-B2-update.zip vào gốc dự án có main.py, sau khi đóng Chess.
Kiểm tra MctsBot.implementation_id in mcts-heuristic-b2-1. Chạy test MCTS và test.bat,
rồi mở giải mới. Giữ lịch sử giải cũ để so sánh; không thay bảng điểm cũ bằng kết quả khác.
Các file được thay chỉ thuộc backend/ai/mcts và thêm file trong another/tests/ai/mcts.
