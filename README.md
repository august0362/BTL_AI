# Chess AI Tournament

Game cờ vua trên Windows: đánh với máy, xem các AI đấu nhau hoặc mở giải vòng tròn để xếp hạng.

## Yêu cầu

- Windows 10/11 64-bit, không cần quyền Administrator.
- Lần đầu chạy cần Internet và khoảng 2 GB ổ trống (chủ yếu cho PyTorch).
- Không cần cài Python trước: `run.bat` tự tải bản portable nếu máy chưa có Python 3.13.

## Cài đặt và chạy

1. Vào https://github.com/august0362/BTL_AI → **Code** → **Download ZIP**.
2. Giải nén vào một thư mục bất kỳ, ví dụ `D:\BTL_AI`.
3. Double-click **`run.bat`**.

Lần đầu mất khoảng 3–10 phút: `run.bat` tải Python (nếu cần), cài thư viện vào `.venv\`, tải model AI
từ GitHub Release (có kiểm SHA-256) rồi mở game. Những lần sau game mở trong vài giây; model mới
(nếu có) được tải tự động, không có mạng thì dùng model đã có trên máy.

Thoát: đóng cửa sổ game, mọi tiến trình của game dừng theo.

## Gặp lỗi?

| Hiện tượng | Cách xử lý |
|---|---|
| "Khong tai duoc Python" / "Cai thu vien that bai" | Kiểm tra Internet (tắt VPN/proxy chặn GitHub, PyPI) rồi chạy lại `run.bat`. |
| "Chua co model AI va khong tai duoc" | Lần đầu bắt buộc có mạng để tải model. |
| SmartScreen chặn `run.bat` | Bấm **More info** → **Run anyway**. |
| Antivirus xóa hoặc chặn file | Cho phép thư mục dự án rồi chạy lại. |
| Lỗi lạ sau khi chép thư mục sang chỗ khác | Xóa thư mục `.venv` rồi chạy lại `run.bat`. |
| Muốn cài lại thư viện | Chạy `run.bat --reinstall` từ Command Prompt. |

## Tài liệu

- Cách chơi: [documents/USER_GUIDE.md](documents/USER_GUIDE.md)
- Dành cho người phát triển: [documents/CONTRIBUTING.md](documents/CONTRIBUTING.md)
