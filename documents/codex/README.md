# Prompt giao việc cho Codex

Đây là kho prompt triển khai và sửa lỗi đã dùng trong quá trình xây dựng dự án;
đa số chỉ để tra cứu lịch sử. Thành viên làm việc hằng ngày chỉ cần bắt đầu từ
[CONTEXT](../CONTEXT.md), [CONTRIBUTING](../CONTRIBUTING.md) và [TASKS](../TASKS.md).

Mỗi file là **một agent Codex → một branch → một PR**. Dán toàn bộ phần dưới dòng `---` của file vào Codex.
Các prompt trong **cùng một đợt** sửa những file khác nhau → chạy **song song** nhiều agent được.
Đợt sau chỉ bắt đầu khi PR của đợt trước (mà nó phụ thuộc) đã **merge vào `main`**.

| Đợt | Prompt | Branch | Phụ thuộc | Thư mục được sửa |
|---|---|---|---|---|
| 1 | [M1-A_core.md](M1-A_core.md) | `feat/core-game-state` | — | `backend/core/` |
| 1 | [M1-B_ai_base.md](M1-B_ai_base.md) | `feat/ai-base-registry` | — | `backend/ai/` |
| 1 | [M3-A_gui_logic.md](M3-A_gui_logic.md) | `feat/gui-logic` | — | `frontend/gui/*.py` (5 module logic) |
| 2 | [M2-1_players_records.md](M2-1_players_records.md) | `feat/tournament-records` | M1-A | `backend/tournament/players.py`, `backend/tournament/records.py` |
| 3 | [M2-2_match_series.md](M2-2_match_series.md) | `feat/tournament-match` | M2-1 | `backend/tournament/match_runner.py`, `backend/tournament/series.py` |
| 3 | [M2-3_ranking_history.md](M2-3_ranking_history.md) | `feat/tournament-ranking` | M2-1 | `backend/tournament/ranking.py`, `backend/tournament/history.py` |
| 4 | [M3-B_controller.md](M3-B_controller.md) | `feat/gui-controller` | M2 | `frontend/gui/controller.py` |
| 5 | [M3-C_pygame_app.md](M3-C_pygame_app.md) | `feat/gui-app-mvp` | M3-B | `frontend/gui/app.py`, `frontend/gui/assets_loader.py`, `frontend/gui/widgets/`, `frontend/gui/screens/`, `main.py`, locales |

Quy tắc chung (đã ghi trong từng prompt):
- **Không sửa `another/tests/`.** Test là đặc tả do Claude viết. Nếu Codex cho rằng test sai → dừng và báo lại, không tự sửa.
- Chỉ sửa đúng các file trong cột cuối.
- Trước khi mở PR: `pytest`, `ruff check .`, `ruff format --check .`, `lint-imports` đều phải xanh.
- Có thể nói thêm với Codex: "Mở PR vào `main` với mô tả theo `.github/pull_request_template.md`".
