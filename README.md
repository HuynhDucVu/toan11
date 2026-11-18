# toan11 – Ngân hàng đề thi LaTeX

Phần mềm quản lý ngân hàng câu hỏi Toán định dạng `ex_test`. Các chức năng:

* nhập file `.tex`, giải nghĩa ID theo chương/bài/dạng, tìm câu tương tự;
* phân loại theo ID `[0D2N1-2]`, nạp file Map ID dạng gạch ngang, **gán ID** cho nhiều câu và **gợi ý ID tự động**;
* lọc câu và chống câu trùng;
* **rà soát đáp án và lời giải** (đáp án lệch lời giải, Đúng/Sai ngược, đáp án trả lời ngắn sai dạng, lỗi LaTeX), **tự sửa** và bỏ câu sai;
* trộn đề theo ma trận hoặc trộn trực tiếp từ file, cân bằng đáp án A/B/C/D, **chuẩn đề tốt nghiệp THPT 2026** (24 mã 0101…0124), **đáp án Excel cho TNMaker**;
* sao lưu, gộp và tách kho;
* **sinh câu hỏi số** từ câu mẫu có tham số; **vẽ hình**: bảng biến thiên tự động, đồ thị hàm số, biểu đồ → mã TikZ;
* xuất mã đề, lời giải và đáp án; **bài làm online** (HTML tự chấm, mở được trên điện thoại), **Moodle XML**, **Word ↔ LaTeX** (cần pandoc).

**Tải bản dựng sẵn cho Windows:** trang [Releases](https://github.com/HuynhDucVu/toan11/releases/latest), tải `NganHangDe.exe`.

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
