## Tải về và chạy
1. Tải file **NganHangDe.exe** ở mục *Assets* bên dưới.
2. Chép vào một thư mục riêng (ví dụ `D:\NganHangDe`) rồi nhấp đúp để chạy, không cần cài đặt.
3. Nếu Windows SmartScreen cảnh báo (vì file chưa ký số): bấm **More info → Run anyway**.

Kho câu hỏi `nganhang.db` nằm cạnh file exe. Cập nhật từ bản cũ: chỉ cần thay file exe, kho giữ nguyên.

## Có gì mới ở bản 0.3.0 – Map ID và gán ID
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
