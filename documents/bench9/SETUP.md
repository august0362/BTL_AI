# Benchmark 9 — Cài đặt

B9 cần binary Stockfish 19. Binary (~100 MB) **không** được commit (`.gitignore`: `backend/ai/benchmarks_extension/bench9/engine/`); mỗi máy cài một lần.

## Cài (Windows / Linux)

```bat
:: Windows, từ gốc repo
set PYTHONPATH=backend
.venv\Scripts\python -m ai.benchmarks_extension.bench9.install
```

```bash
# Linux
PYTHONPATH=backend .venv/bin/python -m ai.benchmarks_extension.bench9.install
```

Trình cài đặt:

1. Nhận diện hệ điều hành và kiến trúc CPU (`windows`/`linux` × `x86_64`/`arm64`).
2. Chọn bản **universal** chính thức của Stockfish 19 — binary tự chọn AVX2/AVX-512/BMI2… lúc chạy, nên không thể chọn nhầm tập lệnh làm crash CPU cũ.
3. Tải archive từ GitHub Release `sf_19` (URL ghim trong `provenance.py`).
4. Kiểm SHA-256 archive (khớp digest GitHub công bố) và SHA-256 binary (x86-64; arm64 chỉ kiểm archive).
5. Giải nén **chỉ** binary + `Copying.txt`, `AUTHORS`, `README.md` vào `bench9/engine/`, ghi `INSTALLED.json`.
6. Smoke test: khởi động UCI, kiểm tên engine, xác nhận mạng NNUE nạp đúng `nn-1a298aa575a0.nnue`, tìm 0,2 s từ thế cờ đầu và in nước/độ sâu/nps.

Tùy chọn: `--check` (chỉ kiểm bản đã cài), `--force` (tải lại), `--dest <thư mục>`.

Không có gì được tải trong lúc chơi: bot chỉ tìm file đã cài; thiếu file → `BotUnavailableError` kèm lệnh cài.

## Nền tảng khác / engine riêng

Nền tảng chưa ghim (macOS, x86 32-bit…) → trình cài đặt báo rõ. Khi đó tự build Stockfish `sf_19` từ mã nguồn (`https://github.com/official-stockfish/Stockfish`, `make -j profile-build`) và trỏ tới nó trong `backend/config/local.toml`:

```toml
[bots.bench_super_alphabeta_nnue]
engine_path = "/đường/dẫn/stockfish"
```

(hoặc biến môi trường `BENCH9_ENGINE_PATH`). Đường dẫn phụ thuộc máy thuộc về `local.toml`, không phải `default.toml`.

## Hiện B9 trong giao diện

`[benchmarks] max_level = 9` (trong `local.toml`, hoặc chọn ở màn Cài đặt). B9 đã có trong `tournament.bots` của `default.toml`; nếu `local.toml` có danh sách `tournament.bots` riêng thì thêm `"bench_super_alphabeta_nnue"` vào đó.

## CI

`.github/workflows/ci.yml` cache thư mục `bench9/engine` (khóa = hash `provenance.py`) và chạy trình cài đặt trước pytest. Bản Linux ~81 MB, không cần GPU, không train. Các test cần engine được đánh dấu `needs_engine` và tự bỏ qua trên máy chưa cài; riêng `test_benchmarks.py`/`test_bot_contract.py` (test có sẵn) gọi mọi benchmark, nên CI phải cài engine.

## Kiểm tra nhanh

```bat
.venv\Scripts\python -m pytest -q --basetemp=.pytest-tmp another\tests\ai\test_benchmark9.py
```
