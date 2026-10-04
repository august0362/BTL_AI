# Chess AI Tournament

## Chạy nhanh

Trên Windows, double-click `run.bat` để tạo môi trường, cài dependencies khi cần và mở game. Lần cài đầu có thể mất vài phút, nhất là PyTorch.

- `run.bat --test`: cài công cụ phát triển nếu cần rồi chạy toàn bộ pytest.
- `run.bat --reinstall`: cài lại dependencies.

## Giới thiệu

Dự án là game cờ vua cho bốn AI độc lập và người chơi: 
- Alpha-Beta + Linear Regression (Option 1)
- Alpha-Beta + Genetic Algorithm (Option 2)
- Pure MCTS (Option 3)
- Deep Reinforcement Learning/DQN (Option 4). Dự án dùng Python 3.13; luật cờ do `python-chess` đảm nhiệm.

## Cài đặt thủ công

Cài Python 3.13, mở terminal tại thư mục dự án rồi chạy:

```bat
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r environments\requirements-dev.txt
.venv\Scripts\python main.py
```

Để mở game thủ công sau đó: `.venv\Scripts\python main.py`.

## Cấu trúc thư mục

```text
BTL_AI/
├── backend/       AI, trạng thái ván, giải đấu và cấu hình
├── frontend/      GUI Pygame và tài nguyên hình ảnh/âm thanh
├── database/      Lịch sử và xếp hạng được tạo khi chơi
├── documents/     Kiến trúc, hướng dẫn, kế hoạch và nhật ký
├── environments/  Phiên bản Python và danh sách dependencies
├── another/       Test, script và công cụ phụ trợ
└── .github/       Workflow CI, CODEOWNERS và mẫu Pull Request
```

## Phát triển

- Kiến trúc và hợp đồng bot: [CONTEXT](documents/CONTEXT.md).
- Phân công, vùng được sửa, bàn cờ đầu vào và Git/PR: [CONTRIBUTING](documents/CONTRIBUTING.md).
- Chạy toàn bộ kiểm tra cục bộ: `another\scripts\test.bat`.

## Tài liệu

| File | Nội dung |
|---|---|
| [documents/CONTEXT.md](documents/CONTEXT.md) | Kiến trúc, hợp đồng giao diện, quy tắc — **đọc trước khi code** |
| [documents/TASKS.md](documents/TASKS.md) | Lộ trình và checklist công việc |
| [documents/CHANGELOG.md](documents/CHANGELOG.md) | Nhật ký quyết định và thay đổi |
| [documents/USER_GUIDE.md](documents/USER_GUIDE.md) | Hướng dẫn sử dụng game |
| [documents/CONTRIBUTING.md](documents/CONTRIBUTING.md) | Phân công, hợp đồng bot và quy trình đóng góp |
| [documents/DEEP_RL_DESIGN.md](documents/DEEP_RL_DESIGN.md) | Option 4: ranh giới bạn tự viết / hạ tầng có sẵn |
| [documents/RL_LEARNING_GUIDE.md](documents/RL_LEARNING_GUIDE.md) | Lộ trình học RL cho Option 4 |

## Credits

Xem [frontend/gui/assets/CREDITS.md](frontend/gui/assets/CREDITS.md).
