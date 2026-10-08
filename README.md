# Chess AI Tournament

Game cờ vua cho bốn AI độc lập và người chơi — Alpha-Beta + Linear Regression (Option 1), Alpha-Beta + Genetic Algorithm (Option 2), Pure MCTS (Option 3), Deep Reinforcement Learning/DQN (Option 4) — cùng thang bot benchmark B1–B8. Python 3.13; luật cờ do `python-chess` đảm nhiệm.

## Chạy nhanh (Windows)

1. Cài Python 3.13: `winget install -e --id Python.Python.3.13`
2. Double-click `run.bat` (bắt buộc): tạo môi trường, cài dependencies khi cần và mở game. Lần đầu có thể mất vài phút (PyTorch).
   - `run.bat --test`: cài công cụ phát triển nếu cần rồi chạy toàn bộ pytest (bắt buộc trước khi gửi PR).
   - `run.bat --reinstall`: cài lại dependencies.

Cài thủ công:

```bat
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r environments\requirements-dev.txt
.venv\Scripts\python main.py
```

## Cấu trúc thư mục

```text
BTL_AI/
├── backend/       AI, trạng thái ván, giải đấu và cấu hình
├── frontend/      GUI Pygame và tài nguyên hình ảnh/âm thanh
├── database/      Lịch sử và xếp hạng được tạo khi chơi
├── documents/     Kiến trúc, hướng dẫn, kế hoạch và nhật ký
├── environments/  Phiên bản Python và dependencies
├── another/       Test, script và công cụ phụ trợ
└── .github/       CI, CODEOWNERS và mẫu Pull Request
```

## Phát triển

- Kiến trúc và hợp đồng bot: [CONTEXT](documents/CONTEXT.md).
- Phân công, vùng được sửa, bàn cờ đầu vào, Git/PR: [CONTRIBUTING](documents/CONTRIBUTING.md).
- Cách chơi: [USER_GUIDE](documents/USER_GUIDE.md).
- Chạy toàn bộ kiểm tra cục bộ: `another\scripts\test.bat`.

## Credits

Xem [frontend/gui/assets/CREDITS.md](frontend/gui/assets/CREDITS.md).
