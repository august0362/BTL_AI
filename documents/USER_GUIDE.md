# Hướng dẫn sử dụng

## Menu

**Người vs Bot**, **Bot vs Bot**, **Xếp hạng AI**, **Lịch sử**, **Xếp hạng**, **Cài đặt**, **Thoát**.

Danh sách bot gồm 4 bot thành viên và các bot benchmark (B1–B7 mặc định, 19 bot; B8 hiện khi đặt `[benchmarks] max_level = 8` trong `backend/config/default.toml`). Bot màu xám chưa khởi tạo được; dòng bên dưới nêu lý do (chưa triển khai, thiếu trọng số…).

## Người vs Bot

Chọn bot, chọn quân Trắng, Đen hoặc Ngẫu nhiên rồi bấm **Bắt đầu**. Chọn quân rồi chọn ô đến để đi; Tốt tới hàng cuối thì chọn quân phong cấp trong hộp thoại.

## Bot vs Bot

Chọn bot Trắng và bot Đen độc lập (được trùng nhau), có nút hoán đổi, chọn **1 ván** hoặc **Best of 3**. Khai cuộc ngẫu nhiên mặc định chỉ áp dụng cho chế độ này.

## Ván đấu

Bàn cờ bên trái; panel bên phải có lượt đi, nước gần nhất, kết quả/trạng thái, thời gian suy nghĩ, danh sách nước đi (đánh dấu nước mới nhất) và thanh đánh giá — biểu diễn **chênh lệch quân** (trắng dương, đen âm), không phải đánh giá riêng của bot.

- Nút loa bật/tắt âm thanh (đi quân, ăn quân, chiếu, kết thúc); mặc định tắt.
- Bot vs Bot: tỷ số loạt, số ván, **Tạm dừng/Tiếp tục**, nút xoay vòng độ trễ giữa các nước.
- **Dừng ván** hủy ván, không ghi xếp hạng; bot đang nghĩ dừng sau nước hiện tại.
- Ván kết thúc khi chiếu hết, hết nước (hòa), không đủ quân, lặp 3 lần, luật 50 nước hoặc chạm 300 nửa nước — chi tiết ở [CONTEXT §4.4](CONTEXT.md#44-luật-kết-thúc-ván).

## Xếp hạng AI

Giải vòng tròn giữa các bot (không có người chơi, không ảnh hưởng Elo). Bấm **Bắt đầu đấu** (thành **Dừng đấu** khi chạy).

- **Lượt thách đấu:** lần lượt từng bot thách đấu mọi bot khác và cầm Trắng, nên mỗi cặp có đủ ván Trắng–Đen và Đen–Trắng. "Đang chạy: A vs B" = ván đang đấu, A thách đấu (Trắng), B bị thách đấu (Đen).
- **Cột:** Số ván, Thắng, Hòa, Thua, Điểm (thắng 1, hòa 0,5, thua 0), Thời gian nghĩ, Bộ nhớ (MB/ván, đo khi bot nghĩ), **Tổng** (điểm ván + phần thời gian và bộ nhớ so với trung bình + thưởng thắng ngược). Bấm tiêu đề cột để sắp xếp; sau 5 giây tự về xếp theo Tổng.
- Trong lúc chạy, Tổng là **tạm tính**; kết thúc giải mới chốt. Luật đầy đủ: [CONTEXT §4.9.4](CONTEXT.md).
- Góc phải trên: thời gian đã chạy và **thời gian còn lại ước tính** (chính xác dần sau khi mỗi bot đã đấu vài ván).
- **Lịch sử** giải lưu các "Trận Chiến Lần n" kèm tỉ số đối đầu từng cặp.

## Lịch sử & Xem lại

Lịch sử có tối đa 20 ván gần nhất (hai bên, kết quả, lý do, ngày); chọn một dòng để xem lại. Xem lại có về đầu, lùi/tiến một nửa nước, phát/tạm dừng, tới cuối, nút tốc độ; thanh đánh giá và danh sách nước cập nhật theo vị trí. **Xuất PGN** ghi vào `database/data/exports/`.

## Xếp hạng

Thứ hạng, số ván, thắng, hòa, thua, điểm và Elo của người chơi và các bot. Elo chỉ tính từ ván Người vs Bot và Bot vs Bot, bắt đầu 1200; thắng đối thủ mạnh tăng nhiều hơn, thua thì giảm, hòa chỉ điều chỉnh nhẹ. **Đặt lại** cần xác nhận.

## Cài đặt

- **Ngôn ngữ:** Tiếng Việt / English, áp dụng ngay.
- **Âm thanh:** đồng bộ với nút loa trong ván.
- **Chủ đề:** 24 theme tối và sáng; cuộn, rê chuột để xem trước, bấm để áp dụng.
- **Tốc độ xem lại:** mỗi lần bấm tăng 500 ms, sau 1000 ms quay về 500 ms; lưu làm mặc định.

## Dữ liệu và đặt lại

`database/data/`: xếp hạng `ranking.json`, lịch sử `history/`, giải đấu `tournaments/`, PGN `exports/`. Cài đặt cá nhân ở `backend/config/local.toml` (chỉ ghi giá trị ghi đè, không commit). Đặt lại: đóng game rồi xóa tệp/thư mục tương ứng; xóa `local.toml` để về cài đặt mặc định.

## Lỗi thường gặp

- **Cài PyTorch chậm:** lần đầu mất vài phút; để `run.bat` chạy xong, kiểm tra mạng.
- **Bot bị làm mờ:** bot không khởi tạo được — đọc lý do dưới tên bot (chưa triển khai, thiếu trọng số).
- **Cửa sổ mờ (Windows):** cập nhật Python/Pygame, khởi động lại game (app đã bật DPI awareness); vẫn mờ thì kiểm tra tùy chọn tương thích DPI của Windows cho Python.
- **Không tìm thấy Python:** cài Python 3.13 kèm Python Launcher (`py`), chạy lại `run.bat` từ thư mục dự án.

## Ảnh minh họa

1440×960, tiếng Việt, theme `dark_winter`:

![Menu chính](images/menu.png)

![Thiết lập Bot vs Bot](images/setup_bots.png)

![Màn hình ván đấu](images/game.png)

![Cài đặt](images/settings.png)
