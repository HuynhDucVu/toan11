# toan11 – Ngân hàng đề thi LaTeX

Phần mềm quản lý ngân hàng câu hỏi Toán định dạng `ex_test`. Các chức năng:

* nhập file `.tex`, giải nghĩa ID theo chương/bài/dạng, tìm câu tương tự;
* phân loại theo ID `[0D2N1-2]`;
* lọc câu và chống câu trùng;
* trộn đề theo ma trận hoặc trộn trực tiếp từ file, cân bằng đáp án A/B/C/D;
* sao lưu, gộp và tách kho;
* xuất mã đề, lời giải và đáp án.

**Dùng file exe trên Windows:** nhấp đúp `build_exe.bat` (cần Python 3.10+) để tạo `dist\NganHangDe.exe`.
Hoặc chạy GitHub Actions **Build exe**.

**Chạy từ mã nguồn:**

```bash
pip install -r requirements.txt
python -m nganhangde import 0-1-De-chuan-hoa-1.tex
python -m nganhangde make ma_tran_mau.json -n 4 -o de_xuat
python -m nganhangde gui
```

Xem hướng dẫn lập trình chi tiết trong [HUONG-DAN-LAP-TRINH.md](HUONG-DAN-LAP-TRINH.md).
