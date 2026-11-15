# Giải thích phần cải tiến heuristic

Mục tiêu là MCTS chọn nước an toàn hơn trước đối thủ tìm kiếm. Không chỉ tăng điểm
ăn quân, vì nước ăn được một tốt có thể khiến mất một xe ở lượt sau.

## 1. Chấm bàn cờ — evaluation.py

Có thể đọc điểm theo dạng:

`H = vật chất + vị trí theo giai đoạn + hỗ trợ chiếu hết ở tàn cuộc`

- Tốt 100, mã 320, tượng 330, xe 500, hậu 900.
- Điểm ô thưởng quân nhẹ ở trung tâm và phát triển tốt.
- Khi còn nhiều quân, vua ở hàng sau có điểm tốt hơn. Khi ít quân, vua tham gia
  trung tâm và hỗ trợ kết thúc ván.
- Điểm vị trí của tốt tăng theo hàng tiến lên, cao hơn trong giai đoạn tàn cuộc.

Các bảng điểm ô được tính trước thành tuple bất biến. Mỗi lần đánh giá chỉ tra bảng,
không phải tính lại khoảng cách tới trung tâm cho từng quân.

Điểm được chuyển sang khoảng (0, 1) trước khi đưa vào MCTS:

```python
reward = 0.5 + 0.45 * score / (400 + abs(score))
```

0,5 là cân bằng. Đây là ước lượng, không phải xác suất thắng đã được hiệu chuẩn.
0 và 1 dành cho thua/thắng thực sự; hòa nhận 0,5 theo luật ván cờ.

## 2. Tránh ăn quân lỗ — leaf.py

Sau khi MCTS mở một nhánh, bộ đánh giá thử hai ply đáp trả rồi tiếp tục xét chuỗi
ăn quân tối đa bốn ply. Khi đang bị chiếu phải xét mọi cách thoát chiếu hợp lệ,
kể cả nước không ăn quân.

Ví dụ xe 500 ăn tốt 100 nhưng bị xe đối phương bắt lại: nếu dừng ngay sau khi ăn tốt,
heuristic báo +100; kiểm tra trao đổi sẽ thấy nguy cơ mất xe và đánh giá khác.

Đây là minimax/negamax ngắn có cắt Alpha-Beta, cộng quiescence (ổn định trao đổi).
Nó chỉ cung cấp **giá trị lá**; cây MCTS vẫn quyết định nước cuối bằng số lượt thăm.

Mọi push đều được pop trong `finally`, kể cả khi hết thời gian. Luật cờ, nước hợp lệ,
nhập thành, bắt tốt qua đường và phong cấp do python-chess xử lý.

## 3. Không giả định đối thủ chọn nước yếu — node.py

Ví dụ một nhánh có điểm mẫu trung bình 0,9 nhưng một đáp trả mạnh làm giá trị còn 0,1;
nhánh khác có trung bình 0,6 và giá trị đáp trả 0,6. Chỉ dùng trung bình dễ chọn nhánh đầu.

Bản hỗ trợ dùng:

```python
estimate = 0.2 * mean_reward + 0.8 * reply_reward
```

Sau đó cộng phần khám phá UCT. `reply_reward` được truyền ngược với giả định bên tới
lượt chọn đáp trả tốt nhất cho họ. Đây là implicit minimax hỗ trợ MCTS.

Khi chưa thử hết các đáp trả, giữ đánh giá ban đầu như một nhánh ảo. Một nước đối phương
chơi yếu được lấy mẫu không được làm mất cảnh báo về một nước phản công mạnh.

## 4. Lõi MCTS vẫn quyết định — search.py

Mỗi vòng vẫn chọn một nhánh, mở một nước chưa thử, đánh giá và hồi truyền.
Mở nhánh ngẫu nhiên bằng RNG riêng; không giữ một bảng nước thắng viết sẵn.
Nước cuối cùng là nút con có nhiều lượt thăm nhất, không lấy trực tiếp nước
do một engine hoặc bộ tìm kiếm ngoài chọn hộ.

Chỉ copy board một lần rồi push/pop qua các lượt thử; sau tìm kiếm ngắt liên kết
cha/con để không tích lũy cây chờ cyclic GC.

## 5. Pure MCTS và bản đang thi đấu

- `use_heuristics=false`: UCT, mở nhánh và rollout ngẫu nhiên; không chạy bộ đánh giá lá mới.
- `use_heuristics=true`: MCTS heuristic với các thành phần trên.

Màn hình vẫn hiển thị MCTS vì bot_id và registry không đổi. Tên trên GUI không cho
biết một cấu hình là Pure hay heuristic; xem cấu hình và last_search_info.

## 6. Những điều cần trình bày trung thực

- Giảm hệ số khám phá và dùng heuristic là các lựa chọn thực nghiệm, không là định lý
  rằng chúng luôn tốt hơn trong mọi bàn cờ.
- Một loạt 20/20 thắng không chứng minh mọi khai cuộc đều thắng. Các lượt xác nhận
  khác có thể xuất hiện hòa hoặc thua; xem đầy đủ RESULTS-HEURISTIC-B2.md.
- Không tính hòa thành thắng và không dùng tỷ lệ điểm thay cho tỷ lệ thắng.
- Bộ nhớ, thời gian và giới hạn 150 ply của giải ảnh hưởng kết quả. Một thế đang hơn
  quân vẫn được tính hòa nếu chưa kết thúc trước giới hạn ván.
