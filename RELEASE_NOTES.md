## Tải về và chạy
1. Tải file **NganHangDe.exe** ở mục *Assets* bên dưới.
2. Chép vào một thư mục riêng (ví dụ `D:\NganHangDe`) rồi nhấp đúp để chạy, không cần cài đặt.
3. Nếu Windows SmartScreen cảnh báo (vì file chưa ký số): bấm **More info → Run anyway**.

Kho câu hỏi `nganhang.db` nằm cạnh file exe. Cập nhật từ bản cũ: chỉ cần thay file exe, kho giữ nguyên.

## Có gì mới ở bản 0.7.0 – Sinh câu hỏi số và vẽ hình (đợt 3, 4)
**🔢 Sinh câu (tab mới)**
- Từ **một câu mẫu có tham số**, sinh hàng loạt biến thể với số liệu khác nhau. Đáp án và lời giải tự tính theo số mới.
- Khai báo biến bằng dòng `%@`:
  - `%@ a = 1..9` (số nguyên), `%@ b = -5..5 khac 0` (loại trừ giá trị), `%@ c = [2,3,5]` (chọn trong danh sách);
  - `%@ D = b*b-4*a*c` (biểu thức), `%@ dk: D > 0` (điều kiện).
- Trong câu viết `@{biểu thức}` để chèn giá trị. Có sẵn hàm `frac`, `dec`, `term`, `coef`, `sq`, `C`, `A`…
- Mỗi biến thể được rà soát (đáp án, lời giải, LaTeX) và loại câu trùng. Có 2 câu mẫu để bắt đầu (trắc nghiệm, trả lời ngắn).

**🎨 Vẽ hình (tab mới)** – sinh mã TikZ, xem trước ngay trong phần mềm
- **Bảng biến thiên** (`tkz-tab`): nhập hàm số là tự tính đạo hàm, cực trị, giới hạn, tiệm cận đứng (đa thức, phân thức…). Sửa tay được.
- **Đồ thị hàm số:** chọn khung x, y, lưới, đánh dấu điểm; tự tách nhánh ở chỗ hàm không xác định.
- **Biểu đồ cột và biểu đồ quạt** từ bảng số liệu.

## Bản 0.6.0 – Đề online, Moodle, Word ↔ LaTeX (đợt 2)
- **Bài làm online:** mỗi mã đề một file HTML, mở bằng trình duyệt trên máy tính, iPhone hoặc Android.
  - Học sinh nhập tên, làm bài có đồng hồ đếm ngược, bấm *Nộp bài* là được chấm ngay theo thang điểm thi tốt nghiệp.
  - Sau khi nộp: hiện đáp án đúng/sai từng câu và (tuỳ chọn) lời giải. Gửi qua Zalo hoặc email được.
  - Cần mạng khi mở để hiện công thức. Dùng để ôn tập, không dùng cho kì thi chính thức.
- **Moodle XML:** trắc nghiệm → multichoice; Đúng/Sai → cloze 4 ý; trả lời ngắn → shortanswer (nhận cả 0,5 và 0.5).
- **LaTeX → Word (.docx):** công thức thành công thức Word gốc, sửa được bằng Equation.
- **Word → LaTeX:**
  - nhận dạng «Câu 1.», phương án A–D (cùng dòng hay mỗi dòng một phương án đều được), ý a)–d) kể cả danh sách đánh số tự động;
  - đáp án lấy từ chữ cái **gạch chân**; nhận cả «Đáp án: …» và «Lời giải: …»;
  - nhập thẳng vào kho (menu Tệp → Nhập file Word).
- Thẻ **«Online / Word»** trong Tuỳ chọn trộn đề; menu **Tệp → Xuất câu ra Word / Moodle / bài làm online**; tab Công cụ có Word → LaTeX, LaTeX → Word, Bài làm online từ file.
- **Chức năng Word cần cài pandoc** (miễn phí): https://pandoc.org/installing.html (bản Windows .msi).

## Bản 0.5.0 – Bổ sung theo MyLT (đợt 1)
**Tạo đề**
- **Đổi câu trước khi trộn:** tick «Xem trước bộ câu…». Bấm *🎲 Đổi ngẫu nhiên* hoặc *Chọn câu thay…*; câu thay luôn cùng dòng ma trận.
- **Xếp câu dễ → khó** trong mỗi phần (Nhận biết → Vận dụng cao), ở thẻ «Trộn».
- **Giới hạn tỉ lệ câu trùng** giữa 2 mã đề, khi mỗi mã dùng một bộ câu khác.
- **Thông tin đầu đề:** Sở/Phòng GD, kì thi, môn, năm học, giáo viên. Mẫu đề mới có ô Họ tên, Số báo danh và dòng «HẾT».
- **In ma trận đặc tả** (Excel hoặc LaTeX), kèm tên chương/bài/dạng lấy từ Map ID.
- Thẻ «Trình bày» có thêm: in ID nhỏ sau mỗi câu trong file lời giải (bản giáo viên), nén cả kết quả thành `.zip`.

**Ngân hàng câu hỏi**
- **Lịch sử sửa từng câu**, khôi phục được bản cũ; **khôi phục câu đã xoá** (menu Câu hỏi).
- **Tìm và thay thế** hàng loạt (Ctrl+H) trong đề bài, phương án, lời giải; có hỗ trợ regex.
- **Lọc theo nguồn**, **tìm câu gần trùng** theo tỉ lệ %, xoá câu thừa.
- **Kiểm tra bản cập nhật** (menu Trợ giúp).

**Công cụ trên file .tex**
- Tìm và thay thế, xoá ID, xoá một nguồn, lọc câu theo nguồn, trích hình TikZ ra file riêng, tìm câu gần trùng.

## Bản 0.4.0 – Tuỳ chọn trộn đề và đáp án cho TNMaker
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
