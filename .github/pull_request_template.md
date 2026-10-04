## Mô tả
<!-- PR này làm gì? Liên quan task nào trong documents/TASKS.md (vd X1-02)? -->

## Module bị ảnh hưởng
- [ ] `backend/core/`  - [ ] `backend/ai/base_bot.py` / `backend/ai/registry.py`  - [ ] `backend/ai/<bot của tôi>/`
- [ ] `backend/tournament/`  - [ ] `frontend/gui/`  - [ ] `backend/config/`  - [ ] CI / docs

<!-- Nếu sửa backend/core/, backend/ai/base_bot.py, backend/ai/registry.py hoặc backend/tournament/: giải thích lý do. -->

## Thư viện mới (nếu có)
<!-- tên, phiên bản, lý do -->

## Kiểm tra trước khi gửi
- [] `pytest` xanh trên máy
- [ ] `ruff check .` và `ruff format --check .` không lỗi
- [ ] `lint-imports` không lỗi
- [ ] Branch đã cập nhật với `main` mới nhất
- [ ] Không commit `database/data/`, `another/local_tools/`, `backend/config/local.toml`, file trọng số
