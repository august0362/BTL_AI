# Codex prompt — DOC-1: complete README + user guide

> Branch: `documents/readme-guide`. Runs in parallel with UI-3 and LOCAL-1. Documentation only.

---

Write documentation for the team (Vietnamese, with real diacritics, UTF-8 + LF). Read `documents/CONTEXT.md`, `documents/TASKS.md`, `backend/ai/deep_rl/README.md`, `run.bat`, `another/scripts/*.bat` and the GUI code to get every fact right. **Do not invent features.**

## 1. `README.md` (repo root): rewrite it to be complete but short
- Keep the "Chạy nhanh" section at the top and list only the current, useful guides in the document table.
- Sections:
  - Giới thiệu (4 AI + người chơi, Python 3.13);
  - Chạy nhanh;
  - Cài đặt thủ công;
  - Cấu trúc thư mục (short tree with a one-line purpose each);
  - Viết bot mới (contract `BaseBot.select_move`, where to put the code, registry, contract test, `lint-imports` rules);
  - Quy trình Git (push.bat / pull.bat, branch naming, PR, no direct push to main);
  - Kiểm thử (`another\scripts\test.bat`, `run.bat --test`);
  - Credits (link `frontend/gui/assets/CREDITS.md`).

## 2. `documents/USER_GUIDE.md`: how to use the game
- Go through every screen in order: Menu, Người vs Bot, Bot vs Bot, Ván đấu (panel sections, eval bar, speaker, stop), Lịch sử, Xem lại, Xếp hạng (Elo explained in 3 sentences), Cài đặt (language, sound, 24 themes, replay speed).
- Explain the end-of-game rules briefly, linking `CONTEXT.md` §4.4.
- Cover where data is stored (`database/data/`, `backend/config/local.toml`) and how to reset.
- Include a "Lỗi thường gặp" section: torch install slow, a bot is greyed out (why), blurry window (DPI), Python not found.
- Embed 4 screenshots. Generate them with `another/tools/render_previews.py` into `documents/images/` (menu, setup_bots, game, settings, theme `dark_winter`, vi, 1440×960) and reference them with relative paths. Keep each PNG < 400 KB.

## 3. `documents/CONTRIBUTING.md`
For the other members (Option 1–3 owners): a step-by-step guide from cloning to merged PR for their bot. It must cover:
- the contract and the `fast_mode`/`seed` config;
- running the contract test only for their bot (`pytest another/tests/ai/test_bot_contract.py -k <bot_id>`);
- what CI checks;
- the CODEOWNERS approval.

Add a link to `documents/USER_GUIDE.md` and `documents/CONTRIBUTING.md` in the README table. Follow `AGENTS.md`. Touch only `README.md`, `documents/USER_GUIDE.md`, `documents/CONTRIBUTING.md` and `documents/images/`.
