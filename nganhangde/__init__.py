"""Phần mềm quản lý ngân hàng đề thi LaTeX (định dạng ex_test).

Các mô-đun:
    texutil    – đọc ngoặc nhọn cân bằng, xử lí comment LaTeX
    idcode     – giải mã ID câu hỏi dạng [0D2N1-2]
    parser     – tách file .tex thành danh sách câu hỏi
    db         – lưu trữ câu hỏi trong SQLite
    generator  – chọn câu theo ma trận, trộn câu/trộn phương án, sinh mã đề
    exporter   – xuất đề, lời giải, bảng đáp án ra .tex/.csv
"""
__version__ = "0.17.4"
