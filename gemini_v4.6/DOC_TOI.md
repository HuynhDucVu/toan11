# Bản Gemini v4.6 (lưu để đối chiếu)

Đây là bản do Gemini viết riêng (gói `nganhangde` với `core/`, `exporters/`, `converters/`…), **không phải** phần mềm
đang phát hành ở thư mục gốc. Không được đóng gói và không chạy kiểm thử trong CI (xem `pytest.ini`).

Đã bỏ khỏi bản lưu: `config.ini` (cài đặt cá nhân/khoá API), 2 file PDF phiếu 2025 (26 MB) và các file Map ID/ConvID
gốc của MyLT (`templates/map_id`) – chép từ bản gốc khi cần.

Lỗi đã thấy khi rà soát (cần sửa trước khi dùng): `ui/mylt2026_exact_widgets.py` gọi tên chưa định nghĩa
`resource_path` (dòng 578, 593, 616), `convert_extest_old_to_new` (914), `convert_dethi_to_extest` (917).

Đã chuyển sang phần mềm chính: cách đọc `Bank.mylt` bằng Microsoft Jet OLEDB qua PowerShell 32-bit kèm giải mật khẩu
file Access (`nganhangde/mylt_import.py`).
Còn có thể chuyển: công thức MathType trong Word qua Word COM, thử mở lại file Word đang bị khoá (WinError 32),
phiếu TLTN 2025 dạng PDF, đối soát câu hỏi bằng AI (`ai/question_verifier.py`).
