# Benchmark 9 — Nguồn gốc engine và giấy phép

## Engine đã chọn

| Mục | Giá trị |
|---|---|
| Engine | Stockfish 19 (bản ổn định) |
| Nguồn | https://github.com/official-stockfish/Stockfish |
| Release | tag `sf_19`, phát hành 2026-09-05 |
| Commit | `edb0d9db6731067ec50ce619ff372b463bc4dd5d` |
| Giấy phép | GNU GPL v3 (`Copying.txt` trong archive, được cài cùng binary) |
| Mạng NNUE | `nn-1a298aa575a0.nnue` (kiến trúc SFNNv16, nhúng trong binary — `src/evaluate.h: EvalFileDefaultName`; engine báo `NNUE evaluation using nn-1a298aa575a0.nnue (109MiB, (86896, 1024, 32, 32, 1))`) |

### Checksum (SHA-256)

| Asset | Archive | Binary bên trong |
|---|---|---|
| `stockfish-windows-x86-64-universal.zip` | `3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7` | `45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0` |
| `stockfish-linux-x86-64-universal.tar.gz` | `9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f` | `0f83d24cc46d2c66c60f16001af5444873bc112b7d028594513426894c12da19` |
| `stockfish-windows-arm64-universal.zip` | `8372ad3f0d7276deb2c70f801f541ec7db463219fc6d9c7592864e542aa4f401` | (chưa ghi) |
| `stockfish-linux-arm64-universal.tar.gz` | `fe26cfd1d9db4c8af3d21e24d9ff34cacb31c1f940085a7583da11796f2bac01` | (chưa ghi) |

Checksum archive khớp trường `digest` mà GitHub API công bố cho từng asset; checksum binary x86-64 được tính trên máy sau khi giải nén. Nguồn sự thật trong code: `backend/ai/benchmarks_extension/bench9/provenance.py`.

## Vì sao chọn bản này

- Stockfish 19 là bản ổn định mới nhất (bản dev mới nhất lúc làm: `stockfish-dev-20261010-dcf1cd5a`). Release notes: +44 Elo so với Stockfish 18.
- **Không** chọn bản dev: không có số đo nào cho thấy bản dev mạnh hơn trong điều kiện giải này, và B9 đã thắng 100 % mọi đối thủ hiện có (`BENCHMARK_RESULTS.md`) — đối thủ trong dự án không thể phân biệt hai bản. Theo quy tắc "ưu tiên stable trừ khi có số đo", giữ `sf_19`.
- Không so engine NNUE khác (Berserk, Obsidian, PlentyChess…): không có lý do thực tế để kỳ vọng mạnh hơn Stockfish ở 1 s/nước, 1 luồng, và cũng không thể đo được sự khác biệt bằng các bot trong dự án.
- Bản universal tránh rủi ro chọn sai tập lệnh SIMD (binary tự phát hiện CPU).

## Nghĩa vụ GPLv3

- Dự án **không phân phối** binary trong repo; trình cài đặt tải bản chính thức từ upstream. Mỗi lần cài đều đặt kèm `Copying.txt` (GPLv3), `AUTHORS`, `README.md` cạnh binary.
- Không sửa mã nguồn Stockfish. Mã nguồn tương ứng: tag `sf_19` ở repo upstream (archive Windows chính thức cũng chứa thư mục `src/`).
- Adapter Python giao tiếp qua UCI (tiến trình riêng). Nếu sau này phát hành lại binary hoặc bản Stockfish đã sửa, phải kèm mã nguồn tương ứng và giữ nguyên thông báo giấy phép.
- B9 luôn được ghi là *engine-derived* (docstring package, `default.toml`, tài liệu này). Thuật toán và mạng là của dự án Stockfish và cộng đồng huấn luyện (dữ liệu chấm điểm lại bằng mạng Leela theo release notes), không phải sáng tạo của dự án này.

## Thư viện phía Python

`python-chess` (`chess.engine`, đã có trong `environments/requirements.txt`, GPLv3). Không thêm phụ thuộc mới.
