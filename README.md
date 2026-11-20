# toan11 – Ngân hàng đề thi LaTeX

Phần mềm quản lý ngân hàng câu hỏi Toán định dạng `ex_test`. Các chức năng:

* nhập file `.tex`, giải nghĩa ID theo chương/bài/dạng, tìm câu tương tự;
* phân loại theo ID `[0D2N1-2]`, nạp file Map ID dạng gạch ngang, **gán ID** cho nhiều câu, **gợi ý ID tự động** và **gán ID bằng AI** (Gemini, Claude, OpenAI, DeepSeek, Grok);
* **Trợ lý AI**: sinh câu tương tự, bù câu thiếu ma trận, PDF → LaTeX, chấm tự luận, hỏi cách sửa lỗi biên dịch;
* lọc câu, **tìm kiếm không dấu** (FTS5), chống câu trùng; **danh mục ID Toán 6–12 có sẵn**; hỗ trợ ex_test 3.3;
* **lịch sử ra đề**, tránh lặp câu giữa các bài kiểm tra gần nhau;
* **rà soát đáp án và lời giải** (đáp án lệch lời giải, Đúng/Sai ngược, đáp án trả lời ngắn sai dạng theo CV 1239, ảnh thiếu, lỗi LaTeX), **tự sửa** và bỏ câu sai;
* trộn đề theo ma trận hoặc trộn trực tiếp từ file, cân bằng đáp án A/B/C/D, **chuẩn đề tốt nghiệp THPT 2026** (24 mã 0101…0124), **đáp án Excel cho TNMaker** hoặc theo file mẫu của phần mềm chấm bất kì, mã QR đáp án; **ma trận CV 7991** (Excel/Word), thang điểm tuỳ chỉnh, câu chùm;
* sao lưu, gộp và tách kho;
* **sinh câu hỏi số** từ câu mẫu có tham số; **vẽ hình**: bảng biến thiên tự động, đồ thị (tiệm cận, tô miền tích phân), biểu đồ, trục số, miền nghiệm, hình khối → mã TikZ;
* xuất mã đề, lời giải và đáp án; **biên dịch PDF** (pdflatex/xelatex, báo lỗi kèm số dòng, gói ex_test rút gọn đi kèm); **bài làm online** (HTML tự chấm, mở được trên điện thoại), **phòng thi LAN** (học sinh làm bài qua Wi-Fi, bảng điểm trực tiếp), **trình chiếu chữa đề**, **Google Forms** (Apps Script), **Moodle XML** (kèm ảnh), **Word ↔ LaTeX** (cần pandoc).

**Tải bản dựng sẵn cho Windows:** trang [Releases](https://github.com/HuynhDucVu/toan11/releases/latest), tải `NganHangDe.exe`.
Từ bản 0.10.0 phần mềm **tự cập nhật** (Trợ giúp → Cập nhật phần mềm).

**Tự đóng gói exe:** nhấp đúp `build_exe.bat` (cần Python 3.10+) để tạo `dist\NganHangDe.exe`.
Hoặc chạy GitHub Actions **Build exe**.

**Chạy từ mã nguồn:**

```bash
pip install -r requirements.txt
python -m nganhangde import 0-1-De-chuan-hoa-1.tex
python -m nganhangde make ma_tran_mau.json -n 4 -o de_xuat
python -m nganhangde gui
```

Xem hướng dẫn lập trình chi tiết trong [HUONG-DAN-LAP-TRINH.md](HUONG-DAN-LAP-TRINH.md).
