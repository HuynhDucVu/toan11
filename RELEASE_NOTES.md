## Tải về và chạy
1. Tải file **NganHangDe.exe** ở mục *Assets* bên dưới.
2. Chép vào một thư mục riêng (ví dụ `D:\NganHangDe`) rồi nhấp đúp để chạy, không cần cài đặt.
3. Nếu Windows SmartScreen cảnh báo (vì file chưa ký số): bấm **More info → Run anyway**.

Kho câu hỏi `nganhang.db` nằm cạnh file exe. Cập nhật từ bản cũ: chỉ cần thay file exe, kho giữ nguyên.

## Có gì mới ở bản 0.4.0 – Tuỳ chọn trộn đề và đáp án cho TNMaker
- Mục **«Tuỳ chọn trộn đề»** (tab Tạo đề) gồm 4 thẻ:
  - **Mã đề:** đánh mã liên tiếp hoặc ngẫu nhiên, chọn mã bắt đầu, 3 hoặc 4 chữ số (0101…).
  - **Trộn:** trộn câu, trộn phương án, trộn ý Đúng/Sai, cân bằng đáp án A/B/C/D, giữ đề gốc.
  - **Trình bày:** đánh số lại từ Câu 1 ở mỗi phần, tiêu đề và lời dẫn theo mẫu đề thi tốt nghiệp, in thang điểm trong file lời giải.
  - **Phiếu chấm TNMaker:** xuất `dap_an_TNMaker.xlsx`. Chọn được bố cục (mỗi dòng 1 câu hoặc mỗi dòng 1 mã đề), phần Đúng/Sai gộp hay tách 4 ô, kí hiệu Đ/S, T/F hoặc 1/0, dấu thập phân. File có thêm sheet «Thông tin» (cấu trúc, thang điểm) và sheet «Mã đề – câu gốc».
- **Nút ⭐ Áp dụng chuẩn đề thi tốt nghiệp THPT 2026:**
  - 12 câu trắc nghiệm, 4 câu Đúng/Sai, 6 câu trả lời ngắn; 90 phút; 24 mã đề 0101…0124;
  - giữ thứ tự ý Đúng/Sai, đánh số lại từng phần, lời dẫn chính thức, thang điểm, đáp án Excel;
  - báo khi ma trận lệch cấu trúc 12 – 4 – 6.
- Trộn đề trực tiếp từ file (tab Công cụ) dùng chung các tuỳ chọn này. Dòng lệnh có thêm `--chuan-2026`.
- Sửa lỗi ngầm khi thêm dòng vào ma trận đề.

## Bản 0.3.0 – Map ID và gán ID
- **Nạp thẳng file Map ID dạng gạch ngang** (`Map_ID.tex` dùng chung với các phần mềm khác) vào menu **Công cụ → Giải nghĩa ID**. Phần mềm báo các mã bị khai báo trùng và xuất lại được đúng định dạng đó.
- **Gán ID cho nhiều câu** (nút 🏷 Gán ID, phím F3; với file thì vào tab Công cụ → Gán ID cho file):
  - **Gợi ý ID tự động** theo câu giống nhất trong kho và theo tên chương/bài/dạng trong Map ID, có hiện độ giống;
  - **Nhận gợi ý tốt nhất** cho các câu có độ giống từ ngưỡng chọn trở lên;
  - **Chọn ID theo Map ID** (Lớp → Môn → Chương → Bài → Dạng → Mức độ) rồi áp cho các câu đã chọn; chỉ đổi Mức độ cũng được;
  - Lưu vào kho, hoặc lưu thành file `.tex` mới (file gốc giữ nguyên).
- Gợi ý chỉ để tham khảo: hãy xem lại cột «ID mới» trước khi lưu.

## Bản 0.2.0 – Rà soát và tự sửa
- **Tự sửa đáp án lệch lời giải.** Chọn tin vào lời giải (sửa đánh dấu `\True`) hoặc tin vào đáp án (sửa chữ «Chọn X», «Đúng/Sai» trong lời giải).
- **Thêm câu kết luận còn thiếu:** «Chọn đáp án X» cho trắc nghiệm, «Vậy đáp án là …» cho trả lời ngắn.
- **Đổi dấu chấm thập phân** trong đáp án trả lời ngắn thành dấu phẩy.
- **Nút ⚡ SỬA TỰ ĐỘNG + BỎ CÂU SAI.** Một bước sửa mọi câu sửa được, rồi bỏ những câu vẫn còn lỗi. Với file `.tex`, kết quả lưu thành file mới; file gốc giữ nguyên.
- Cột **«Tự sửa được»** cho biết trước phần mềm sẽ sửa gì ở từng câu.
- **Sửa lỗi khi trộn đề:** chữ «Chọn X» trong lời giải nay tự đổi theo vị trí mới của phương án.

## Chức năng chính
- Ngân hàng câu hỏi LaTeX (`ex_test`): trắc nghiệm, Đúng/Sai, trả lời ngắn, tự luận; phân loại theo ID `[0D2N1-2]`, giải nghĩa ID, câu tương tự.
- Tạo đề theo ma trận, nhiều mã đề, cân bằng đáp án A/B/C/D, ma trận từ đề có sẵn.
- Rà soát đáp án, lời giải và lỗi LaTeX; tự sửa và bỏ câu sai.
- Công cụ trên file `.tex`: trộn đề trực tiếp, lọc/đổi ID, lấy bảng đáp án, tìm câu trùng.
- Sao lưu, gộp và tách kho.
