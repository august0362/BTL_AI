# Kết quả triển khai MCTS — mốc vượt Random

Mã nguồn đầu vào: `BTL_AI-github(1).zip`. MCTS đầu vào là baseline ngẫu nhiên.
Phiên bản bàn giao thay baseline bằng cây UCT thật và có hai chế độ riêng.

## Kết quả thực nghiệm

| Chế độ | Ngân sách/nước | Số ván | Thắng | Hòa | Thua | Tỷ lệ thắng | Điểm có tính hòa |
|---|---:|---:|---:|---:|---:|---:|---:|
| MCTS có heuristic (mặc định) | 1 giây | 100 | 100 | 0 | 0 | 100% | 100% |
| Pure MCTS / UCT (thăm dò riêng) | 1 giây | 10 | 10 | 0 | 0 | 100% | 100% |

**Mục tiêu thắng ít nhất 70/100 ván được đối chiếu bằng loạt 100 ván của bản có
heuristic.** Loạt Pure chỉ có 10 ván, dùng seed khác; không coi đây là bằng chứng
đủ để khẳng định tỷ lệ thắng dài hạn của Pure hoặc tác động riêng của heuristic.

- Đối thủ: `bench_random` gốc, tạo qua registry, không sửa mã đối thủ.
- Loạt chính: seed bắt đầu 20261101, 50 khai cuộc ngẫu nhiên × 2 ván đổi màu;
  50 ván trắng và 50 ván đen. Pure: seed bắt đầu 20261201, 5 cặp đổi màu.
- Mỗi khai cuộc dài 2 nửa nước. Giới hạn 150 nửa nước/ván, bật luật hòa của dự án.
- Dùng `MatchRunner` chung; chỉ kết quả thật theo luật ván mới được tính thắng.
- Đã phát lại toàn bộ PGN: 110
  ván hợp lệ, kiểm tra kết quả, cặp khai cuộc, màu quân và SHA-256 mã bot.
- MCTS hỗ trợ: thời gian trung bình **0.932 giây/nước**;
  p95 **0.976 giây**; cao nhất
  **1.350 giây**; 95 nước vượt 1 giây.
- Pure: trung bình 0.968 giây/nước,
  cao nhất 0.976 giây.
- Thời gian hợp tác, không phải giới hạn cứng của hệ điều hành. Kết quả này đo
  trên Linux, Python 3.13.16, python-chess 1.11.2;
  loạt chính chạy 6 worker, Pure chạy 1 worker.
- Tỷ lệ rollout bị cắt của bản hỗ trợ: 99.42%;
  của Pure: 90.57%. Cutoff không phải hòa thật;
  ở bản hỗ trợ phần lớn giá trị lá là ước lượng, ở Pure là giá trị trung lập.
- Khoảng Wilson 95% mô tả cho tỷ lệ thắng loạt chính:
  [96.30%, 100.00%].
  Các ván ghép cặp không độc lập hoàn toàn; không dùng khoảng này để cam kết
  sức mạnh trên mọi máy hoặc mọi tập seed.

Loạt sàng lọc trước đó: 20/20 thắng ở 0,05 giây/nước, seed 20261015. Không gộp
loạt sàng lọc vào 100 ván đánh giá chính. Chưa đánh giá vượt Benchmark 2.

## Kiểm thử mã nguồn

- Kiểm tra MCTS và hợp đồng lọc theo MCTS: **49 passed**.
- Toàn bộ test ngoài `another/tests/ai/deep_rl/`: **560 passed, 5 skipped**.
- Coverage của `core` và `tournament`: **89,35%**, vượt ngưỡng 80% của dự án.
- Ruff toàn dự án: đạt. Định dạng: đạt. Import-linter: 3/3 hợp đồng đạt.
- Trong 5 skip: 2 test baseline bỏ qua bot thật; 3 test vệ sinh repo cần Git,
  trong khi ZIP không có lịch sử `.git` trong bản làm việc.
- Full pytest không loại Deep RL bị dừng lúc collection do thiếu PyTorch.
  Yêu cầu cài PyTorch đã bị cơ chế duyệt tự động từ chối. Không thay dependency
  của dự án và không tuyên bố đã kiểm thử phần Deep RL.
- Test GUI chạy headless trên Linux; chưa xác nhận hiển thị trực tiếp trên Windows.

Kiểm tra bao gồm công thức UCT, chọn nhánh cho đen, backup đúng góc nhìn,
robust child, expansion một nút, thắng/hòa thật, chiếu hết ưu tiên hơn luật hòa,
lặp ba lần thực tế, đồng hồ 50 nước, Pure không gọi heuristic, cutoff, deadline,
seed tất định với số simulation cố định, RNG độc lập, giữ nguyên FEN và lịch sử,
reset, mate một nước cho hai màu, cấu hình sai và hợp đồng nước hợp lệ.

## Phạm vi thay đổi và cách áp dụng

Chỉ một file cũ bị thay: `backend/ai/mcts/bot.py`. Các file khác được thêm trong
`backend/ai/mcts/` và `another/tests/ai/mcts/`. Không sửa/xóa test cũ; không thay
backend dùng chung, registry, GUI, cấu hình hoặc dependency. Không commit/push Git.

Gói `MCTS-update.zip` là **bản cập nhật phần MCTS**, không phải toàn bộ repo.
Giải nén vào thư mục gốc dự án đang có, nơi chứa `backend`, `another`, `main.py`;
cho phép thay `backend/ai/mcts/bot.py`. Đọc `backend/ai/mcts/README.md` để chạy
test, chọn chế độ Pure hoặc chạy lại benchmark. Giữ bản dự án gốc nếu cần đối chiếu.

`results/random_100/` và `results/pure_10/` chứa JSON từng ván, PGN và tổng hợp.
`results/audit.json` ghi kết quả phát lại độc lập. `results/pytest.txt` là log test.
