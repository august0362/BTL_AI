# MCTS heuristic hướng tới Benchmark 2

Bản này giữ cây MCTS/UCT và bổ sung đánh giá chiến thuật ngắn ở lá. ID vẫn là
`mcts`, entry point `ai.mcts.bot:MctsBot`. Không cần thư viện, trọng số hay engine mới.

**Đây là MCTS heuristic có kiểm tra minimax/Alpha-Beta ở lá, không phải Pure MCTS.**
Pure MCTS vẫn chọn bằng `use_heuristics=false` và không gọi đánh giá lá mới.

Đọc `HUONG_DAN_HEURISTIC.md` để hiểu từng phần. Kết quả thực đo, cả các cấu hình
không thắng hết, nằm trong `RESULTS-HEURISTIC-B2.md` và `results/heuristic_b2/`.
`RESULTS.md` là kết quả lịch sử v1, không phải số liệu của bản mới.

## Ý tưởng

1. Chấm vật chất và vị trí theo giai đoạn: phát triển quân, giữ vua ở hàng sau
   khi còn nhiều quân và đưa vua tham gia ở tàn cuộc.
2. Trước khi chấm lá, thử ngắn các đáp trả và chuỗi ăn quân để tránh tưởng rằng
   ăn được tốt là lời trong khi nước tiếp theo mất xe/hậu.
3. Dùng đáp trả tốt nhất đã biết của đối phương để hỗ trợ lựa chọn trong MCTS.
   Nước trả cuối cùng vẫn là nút con có nhiều lượt thăm nhất.

Công thức hỗ trợ chọn nhánh:

`0.2 * mean_reward + 0.8 * reply_reward + c * sqrt(log(parent_visits) / visits)`

Giữ riêng giá trị ước lượng ban đầu khi chưa thử hết các đáp trả. Không để một
nước đáp trả yếu được lấy mẫu xóa mất cảnh báo chiến thuật đã biết.

## Đường gọi và file

| File | Vai trò |
|---|---|
| bot.py | BaseBot, cấu hình, RNG riêng và entry point |
| search.py | Selection → Expansion → đánh giá lá → Backpropagation |
| node.py | Thống kê, UCT, hỗ trợ đáp trả, chọn robust child, giải phóng cây |
| evaluation.py | Vật chất, điểm ô và vai trò vua theo giai đoạn |
| leaf.py | Kiểm tra ngắn ở lá, quiescence và phục hồi board khi timeout |

Mỗi search chỉ copy board một lần, giữ lịch sử lặp nước, sau đó push/pop và
phục hồi stack. Tối đa 1024 nút cây; ngắt liên kết cha/con sau mỗi nước.
Không có bảng nhớ trạng thái tìm kiếm dùng chung giữa bot hoặc giữa các ván.

## Cấu hình mặc định

| Khóa | Giá trị | Ý nghĩa |
|---|---:|---|
| use_heuristics | true | false để chọn Pure MCTS |
| max_think_time_s | 1.0 | Trần hợp tác, không bảo đảm hard real-time của OS |
| leaf_depth | 2 | Hai ply kiểm tra ở lá; sau đó thử trao đổi tối đa 4 ply |
| exploration_constant | 0.015 | Hỗ trợ tập trung hơn trong ngân sách một giây |
| max_tree_nodes | 1024 | Trần nút cây, tính cả gốc |
| simulations | 100000 | Trần vòng lặp, thường bị chặn trước bởi thời gian/nút |
| seed | không đặt | RNG độc lập cho từng instance |

`leaf_depth=0` là phương án nhẹ chỉ kiểm tra trao đổi. Số liệu thử nghiệm cho thấy
nó không thắng hết các ván đã kiểm tra; không lấy kết quả đó thay cho cấu hình cuối.
`fast_mode=true` giới hạn 32 vòng/0,05 giây và dùng rollout ngắn cho CI.

Cùng seed và thời gian vẫn có thể khác nước trên máy khác nhau. Khi thời gian là 0,
số mô phỏng cố định cho phép kiểm tra tái lập trong cùng môi trường.

## Kiểm tra đúng bản trên Windows

Đóng Chess, giải nén gói cập nhật vào thư mục có main.py, backend và another.
Trong PowerShell tại gốc dự án:

```powershell
$env:PYTHONPATH = "$PWD\backend;$PWD\frontend;$PWD\another"
.\.venv\Scripts\python.exe -c "from ai.mcts.bot import MctsBot; b=MctsBot(); print(b.implementation_id, b.search_config.leaf_depth, b.search_config.exploration_constant)"
```

Phải in `mcts-heuristic-b2-1 2 0.015`.
Cấu hình cá nhân truyền vào bot được ưu tiên hơn mặc định; muốn đối chiếu đúng
thí nghiệm thì dùng ngân sách 1 s và cấu hình bảng trên.

```powershell
.\.venv\Scripts\python.exe -m pytest another\tests\ai\mcts another\tests\ai\test_bot_contract.py -k mcts --basetemp=.pytest-tmp
.\another\scripts\test.bat
```

Sau khi kiểm tra đạt, chạy run.bat và bắt đầu giải mới. Registry và GUI giữ nguyên.

## Benchmark có thể chạy lại

```powershell
$env:PYTHONPATH = "$PWD\backend;$PWD\frontend;$PWD\another"
.\.venv\Scripts\python.exe -m tests.ai.mcts.benchmark_heuristic --games 40 --workers 1 --seconds 1 --seed 20261401 --output mcts-vs-b2
```

Đối thủ mặc định là `bench_alphabeta3`, độ sâu mặc định 3, không fast_mode.
Thêm `--memory` để đo OS peak trừ baseline bằng ProcessPlayer như GUI.
Có PGN, JSON từng ván, thống kê thời gian, độ sâu đối thủ và SHA-256 mã hai bên.
Không giảm độ sâu, đổi trọng số hay sửa mã Benchmark 2 để tạo thành tích.

Tỷ lệ thắng = thắng / số ván. Hòa không tính là thắng. Kết quả trên một tập thử
không chứng minh thắng 100% mọi khai cuộc hoặc mọi thế cờ.
