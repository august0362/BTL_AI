# Benchmark 9 — Huấn luyện NNUE trên Kaggle: đánh giá khả thi

## Kết luận

**Không huấn luyện mạng riêng. B9 dùng mạng chính thức `nn-1a298aa575a0.nnue` làm mạng sản xuất.** Vì không có đường cải thiện đáng tin, notebook Kaggle **không** được tạo. Đây là kết luận có chủ đích, không phải việc bỏ dở.

## Lý do

1. **Quy mô dữ liệu và tính toán chênh nhau nhiều bậc.** Theo release notes của Stockfish 19, mạng SFNNv16 được huấn luyện trên *hàng trăm tỉ* thế cờ được chấm điểm lại bằng mạng Leela mạnh, có Quantization-Aware Training và nhiều vòng tinh chỉnh tham số trên hạ tầng phân tán (fishtest). Một phiên Kaggle miễn phí bị giới hạn GPU theo tuần, thời gian mỗi phiên và dung lượng đĩa (kiểm tra quota hiện tại tại kaggle.com/docs). Với mức đó, chỉ chạy nổi vài giờ fine-tune trên một tập nhỏ hơn hàng nghìn lần — gần như chắc chắn **yếu hơn** mạng gốc (quên kiến thức, lệch phân bố).
2. **Không có dữ liệu phù hợp trong tầm tay.** Tập binpack chính thức của `nnue-pytorch` lớn hàng trăm GB đến TB, vượt giới hạn dataset/đĩa Kaggle. PGN Kasparov/Carlsen của dự án Deep RL quá nhỏ và không có nhãn engine.
3. **Không thể qua cổng chấp nhận bằng đối thủ trong dự án.** B9 với mạng gốc đã thắng **100 %** trước B7, B8, B5, B6, AB3, B4 và Deep RL (`BENCHMARK_RESULTS.md`). Một mạng tùy chỉnh không thể cho thấy "cải thiện đáng tin cậy" trước các đối thủ này; phép so sánh có ý nghĩa duy nhất là mạng mới vs mạng gốc trong Stockfish–Stockfish, cần hàng chục nghìn ván để thấy vài Elo — mà kết quả dự kiến là âm (mục 1).
4. **Rủi ro tương thích kiến trúc.** Mạng phải đúng kiến trúc SFNNv16 của binary 19; `nnue-pytorch` ở commit tương ứng phải build data loader C++ và xuất `.nnue` đúng định dạng — nhiều công sức cho một kết quả dự kiến yếu hơn.

Vì vậy, theo quy tắc "không thay mạng mạnh đã kiểm chứng bằng mạng thử nghiệm yếu hơn chỉ để chứng minh là đã huấn luyện", giữ mạng chính thức.

## Nếu sau này vẫn muốn thử một mạng `.nnue` khác

B9 đã hỗ trợ sẵn, không cần sửa code, và **không thể vô tình thay mạng mặc định**:

1. Đặt file mạng (đúng kiến trúc của Stockfish 19) ở đâu đó trên máy.
2. Khai báo một bot thứ hai trong `backend/config/local.toml`, giữ nguyên B9 gốc:

   ```toml
   [bots.bench9_custom]
   class = "ai.benchmarks_extension.bench9.bot:SuperAlphaBetaNNUEBot"
   display_name = "B9 · mạng thử nghiệm"
   nnue_path = "D:/nets/nn-custom.nnue"
   ```

   Mạng sai định dạng/kiến trúc → `BotUnavailableError` ngay khi tạo bot (adapter kiểm dòng `NNUE evaluation using …`).
3. **Cổng chấp nhận** — đấu trực tiếp với mạng gốc, cùng điều kiện, khai cuộc ghép cặp đổi màu:

   ```bat
   set PYTHONPATH=backend;frontend;another
   .venv\Scripts\python another\tools\bench9_strength.py --candidate bench9_custom ^
       --opponents bench_super_alphabeta_nnue --pairs 500 --opening-plies 8 --workers 4
   ```

   Chỉ đổi mạng mặc định khi cận dưới khoảng tin cậy 95 % > 0 Elo **và** tốc độ (nps) không giảm đáng kể. Ngược lại giữ mạng chính thức.
