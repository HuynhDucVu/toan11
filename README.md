# toan11 – Ngân hàng đề thi LaTeX

Phần mềm quản lý ngân hàng câu hỏi Toán định dạng `ex_test`. Các chức năng:

* nhập file `.tex`;
* phân loại theo ID `[0D2N1-2]`;
* lọc câu và chống câu trùng;
* trộn đề theo ma trận;
* xuất mã đề, lời giải và đáp án.

```bash
python -m nganhangde import 0-1-De-chuan-hoa-1.tex
python -m nganhangde make ma_tran_mau.json -n 4 -o de_xuat
python -m nganhangde gui
```

Xem hướng dẫn lập trình chi tiết trong [HUONG-DAN-LAP-TRINH.md](HUONG-DAN-LAP-TRINH.md).
