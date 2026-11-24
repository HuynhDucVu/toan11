import json
from pathlib import Path
from .idcode import parse_id
from .texutil import strip_accents_vi

GDPT2018_MATH_CATALOG: list[dict] = [
    {"prefix": "6D1", "grade": "6", "chapter": "Chương I. Tập hợp các số tự nhiên", "lessons": {"1": "Tập hợp", "2": "Các phép tính số tự nhiên", "3": "Lũy thừa với số mũ tự nhiên"}},
    {"prefix": "6D2", "grade": "6", "chapter": "Chương II. Tính chia hết trong tập số tự nhiên", "lessons": {"1": "Quan hệ chia hết và dấu hiệu", "2": "Số nguyên tố", "3": "ƯCLN và BCNN"}},
    {"prefix": "6D3", "grade": "6", "chapter": "Chương III. Số nguyên", "lessons": {"1": "Tập hợp số nguyên", "2": "Phép cộng trừ nhân chia số nguyên"}},
    {"prefix": "6H4", "grade": "6", "chapter": "Chương IV. Một số hình phẳng trong thực tiễn", "lessons": {"1": "Tam giác đều, hình vuông, lục giác đều", "2": "Chu vi và diện tích tứ giác"}},
    {"prefix": "6D6", "grade": "6", "chapter": "Chương VI. Phân số và Số thập phân", "lessons": {"1": "Phân số và phép tính", "2": "Số thập phân và tỉ số phần trăm"}},
    {"prefix": "6H8", "grade": "6", "chapter": "Chương VIII. Những hình học cơ bản", "lessons": {"1": "Điểm, đường thẳng, tia, đoạn thẳng", "2": "Góc và số đo góc"}},
    {"prefix": "7D1", "grade": "7", "chapter": "Chương I. Số hữu tỉ", "lessons": {"1": "Tập hợp số hữu tỉ", "2": "Cộng trừ nhân chia số hữu tỉ", "3": "Lũy thừa số hữu tỉ"}},
    {"prefix": "7D2", "grade": "7", "chapter": "Chương II. Số thực", "lessons": {"1": "Căn bậc hai số học", "2": "Số vô tỉ và số thực"}},
    {"prefix": "7H3", "grade": "7", "chapter": "Chương III. Góc và đường thẳng song song", "lessons": {"1": "Góc ở vị trí đặc biệt", "2": "Hai đường thẳng song song"}},
    {"prefix": "7H4", "grade": "7", "chapter": "Chương IV. Tam giác bằng nhau", "lessons": {"1": "Tổng ba góc tam giác", "2": "Các trường hợp bằng nhau của tam giác", "3": "Tam giác cân"}},
    {"prefix": "7D6", "grade": "7", "chapter": "Chương VI. Tỉ lệ thức và đại lượng tỉ lệ", "lessons": {"1": "Tỉ lệ thức và dãy tỉ số bằng nhau", "2": "Đại lượng tỉ lệ thuận, nghịch"}},
    {"prefix": "7D7", "grade": "7", "chapter": "Chương VII. Biểu thức đại số và đa thức một biến", "lessons": {"1": "Đa thức một biến", "2": "Phép tính đa thức một biến"}},
    {"prefix": "8D1", "grade": "8", "chapter": "Chương I. Đa thức nhiều biến", "lessons": {"1": "Đơn thức, đa thức nhiều biến", "2": "Hằng đẳng thức đáng nhớ", "3": "Phân tích đa thức thành nhân tử"}},
    {"prefix": "8H3", "grade": "8", "chapter": "Chương III. Tứ giác", "lessons": {"1": "Hình thang, hình bình hành", "2": "Hình chữ nhật, hình thoi, hình vuông"}},
    {"prefix": "8H4", "grade": "8", "chapter": "Chương IV. Định lí Thalès", "lessons": {"1": "Định lí Thalès trong tam giác", "2": "Đường trung bình và tính chất đường phân giác"}},
    {"prefix": "8D6", "grade": "8", "chapter": "Chương VI. Phân thức đại số", "lessons": {"1": "Phân thức đại số", "2": "Các phép toán trên phân thức"}},
    {"prefix": "8D7", "grade": "8", "chapter": "Chương VII. Phương trình bậc nhất và hàm số bậc nhất", "lessons": {"1": "Phương trình bậc nhất một ẩn", "2": "Hàm số bậc nhất và đồ thị"}},
    {"prefix": "8H9", "grade": "8", "chapter": "Chương IX. Tam giác đồng dạng", "lessons": {"1": "Các trường hợp đồng dạng", "2": "Định lí Pythagore"}},
    {"prefix": "9D1", "grade": "9", "chapter": "Chương I. Phương trình và hệ phương trình bậc nhất hai ẩn", "lessons": {"1": "Hệ hai phương trình bậc nhất hai ẩn", "2": "Giải bài toán bằng cách lập hệ"}},
    {"prefix": "9D2", "grade": "9", "chapter": "Chương II. Phương trình và bất phương trình bậc nhất một ẩn", "lessons": {"1": "Phương trình quy về bậc nhất", "2": "Bất đẳng thức và bất phương trình bậc nhất"}},
    {"prefix": "9D3", "grade": "9", "chapter": "Chương III. Căn bậc hai và căn bậc ba", "lessons": {"1": "Căn bậc hai và căn thức bậc hai", "2": "Biến đổi đơn giản biểu thức chứa căn"}},
    {"prefix": "9H4", "grade": "9", "chapter": "Chương IV. Hệ thức lượng trong tam giác vuông", "lessons": {"1": "Tỉ số lượng giác góc nhọn", "2": "Ứng dụng giải tam giác vuông"}},
    {"prefix": "9H5", "grade": "9", "chapter": "Chương V. Đường tròn", "lessons": {"1": "Đường tròn và dây cung", "2": "Vị trí tương đối đường thẳng và đường tròn", "3": "Góc với đường tròn và tứ giác nội tiếp"}},
    {"prefix": "9D6", "grade": "9", "chapter": "Chương VI. Hàm số y = ax^2 và phương trình bậc hai", "lessons": {"1": "Hàm số y = ax^2", "2": "Phương trình bậc hai và định lí Viète"}},
    {"prefix": "0D1", "grade": "10", "chapter": "Chương I. Mệnh đề và tập hợp", "lessons": {"1": "Mệnh đề", "2": "Tập hợp và các phép toán"}},
    {"prefix": "0D2", "grade": "10", "chapter": "Chương II. BPT và hệ BPT bậc nhất hai ẩn", "lessons": {"1": "Bất phương trình bậc nhất hai ẩn", "2": "Hệ bất phương trình bậc nhất hai ẩn"}},
    {"prefix": "0H3", "grade": "10", "chapter": "Chương III. Hệ thức lượng trong tam giác", "lessons": {"1": "Giá trị lượng giác góc 0° đến 180°", "2": "Hệ thức lượng trong tam giác"}},
    {"prefix": "0H4", "grade": "10", "chapter": "Chương IV. Vectơ", "lessons": {"1": "Khái niệm mở đầu", "2": "Tổng hiệu hai vectơ", "3": "Tích vectơ với một số", "4": "Vectơ trong mặt phẳng tọa độ", "5": "Tích vô hướng"}},
    {"prefix": "0D5", "grade": "10", "chapter": "Chương V. Mẫu số liệu không ghép nhóm", "lessons": {"1": "Số gần đúng và sai số", "2": "Xu thế trung tâm", "3": "Độ phân tán"}},
    {"prefix": "0D6", "grade": "10", "chapter": "Chương VI. Hàm số, đồ thị và ứng dụng", "lessons": {"1": "Hàm số", "2": "Hàm số bậc hai", "3": "Dấu tam thức bậc hai", "4": "PT quy về PT bậc hai"}},
    {"prefix": "0H7", "grade": "10", "chapter": "Chương VII. Phương pháp tọa độ Oxy", "lessons": {"1": "PT đường thẳng", "2": "Đường thẳng trong Oxy", "3": "Đường tròn trong Oxy", "4": "Ba đường conic"}},
    {"prefix": "0D8", "grade": "10", "chapter": "Chương VIII. Đại số tổ hợp", "lessons": {"1": "Quy tắc đếm", "2": "Hoán vị, chỉnh hợp, tổ hợp", "3": "Nhị thức Newton"}},
    {"prefix": "0D9", "grade": "10", "chapter": "Chương IX. Xác suất cổ điển", "lessons": {"1": "Biến cố và định nghĩa cổ điển", "2": "Thực hành tính xác suất"}},
    {"prefix": "1D1", "grade": "11", "chapter": "Chương I. Hàm số và PT lượng giác", "lessons": {"1": "Giá trị lượng giác", "2": "Công thức lượng giác", "3": "Hàm số lượng giác", "4": "PT lượng giác cơ bản"}},
    {"prefix": "1D2", "grade": "11", "chapter": "Chương II. Dãy số, CSC, CSN", "lessons": {"1": "Dãy số", "2": "Cấp số cộng", "3": "Cấp số nhân"}},
    {"prefix": "1D3", "grade": "11", "chapter": "Chương III. Mẫu số liệu ghép nhóm", "lessons": {"1": "Mẫu số liệu ghép nhóm", "2": "Các số đặc trưng đo xu thế trung tâm"}},
    {"prefix": "1H4", "grade": "11", "chapter": "Chương IV. Quan hệ song song không gian", "lessons": {"1": "Đường thẳng và mặt phẳng", "2": "Hai đường thẳng song song", "3": "Đường thẳng song song mặt phẳng", "4": "Hai mặt phẳng song song", "5": "Phép chiếu song song"}},
    {"prefix": "1D5", "grade": "11", "chapter": "Chương V. Giới hạn. Hàm số liên tục", "lessons": {"1": "Giới hạn dãy số", "2": "Giới hạn hàm số", "3": "Hàm số liên tục"}},
    {"prefix": "1D6", "grade": "11", "chapter": "Chương VI. Hàm số mũ và lôgarit", "lessons": {"1": "Lũy thừa số mũ thực", "2": "Lôgarit", "3": "Hàm số mũ và lôgarit", "4": "PT, BPT mũ và lôgarit"}},
    {"prefix": "1H7", "grade": "11", "chapter": "Chương VII. Quan hệ vuông góc không gian", "lessons": {"1": "Hai đường thẳng vuông góc", "2": "Đường thẳng vuông góc mặt phẳng", "3": "Phép chiếu vuông góc và góc", "4": "Hai mặt phẳng vuông góc", "5": "Khoảng cách", "6": "Thể tích"}},
    {"prefix": "1D8", "grade": "11", "chapter": "Chương VIII. Quy tắc tính xác suất", "lessons": {"1": "Biến cố hợp, giao, độc lập", "2": "Công thức cộng, công thức nhân"}},
    {"prefix": "1D9", "grade": "11", "chapter": "Chương IX. Đạo hàm", "lessons": {"1": "Định nghĩa và ý nghĩa đạo hàm", "2": "Các quy tắc tính đạo hàm", "3": "Đạo hàm cấp hai"}},
    {"prefix": "2D1", "grade": "12", "chapter": "Chương I. Ứng dụng đạo hàm khảo sát HS", "lessons": {"1": "Đơn điệu và cực trị", "2": "GTLN và GTNN", "3": "Đường tiệm cận", "4": "Khảo sát và vẽ đồ thị", "5": "Ứng dụng thực tiễn"}},
    {"prefix": "2H2", "grade": "12", "chapter": "Chương II. Vectơ và tọa độ Oxyz", "lessons": {"1": "Vectơ trong không gian", "2": "Hệ trục tọa độ Oxyz", "3": "Biểu thức tọa độ phép toán vectơ"}},
    {"prefix": "2D3", "grade": "12", "chapter": "Chương III. Độ phân tán mẫu ghép nhóm", "lessons": {"1": "Khoảng biến thiên và tứ phân vị", "2": "Phương sai và độ lệch chuẩn"}},
    {"prefix": "2D4", "grade": "12", "chapter": "Chương IV. Nguyên hàm và tích phân", "lessons": {"1": "Nguyên hàm", "2": "Tích phân", "3": "Ứng dụng hình học tích phân"}},
    {"prefix": "2H5", "grade": "12", "chapter": "Chương V. Phương pháp tọa độ Oxyz", "lessons": {"1": "PT mặt phẳng", "2": "PT đường thẳng không gian", "3": "PT mặt cầu"}},
    {"prefix": "2D6", "grade": "12", "chapter": "Chương VI. Xác suất có điều kiện", "lessons": {"1": "Xác suất có điều kiện", "2": "Xác suất toàn phần và Bayes"}},
]
LEVEL_LABELS_VI = {"N": "Nhận biết", "H": "Thông hiểu", "V": "Vận dụng", "C": "Vận dụng cao"}


def describe_id6(code: str) -> str:
    info = parse_id(code)
    if not info:
        return f"Mã không chuẩn: {code}"
    prefix = f"{info.lop}{info.mon}{info.chuong}"
    for item in GDPT2018_MATH_CATALOG:
        if item["prefix"] == prefix:
            lesson = item["lessons"].get(info.bai, f"Bài {info.bai}" if info.bai else "")
            parts = [f"Lớp {item['grade']}", item["chapter"]]
            if lesson:
                parts.append(lesson)
            if info.dang:
                parts.append(f"Dạng {info.dang}")
            parts.append(f"Mức: {LEVEL_LABELS_VI.get(info.muc_do, info.muc_do)}")
            return " · ".join(parts)
    return f"Lớp {info.lop} · Môn {info.mon} · Chương {info.chuong}"


def export_id6_lookup_html(out_html: str) -> str:
    rows = []
    for ch in GDPT2018_MATH_CATALOG:
        for b_key, b_name in ch["lessons"].items():
            for lv_code, lv_name in LEVEL_LABELS_VI.items():
                sid = f"{ch['prefix']}{lv_code}{b_key}-1"
                rows.append({
                    "id": sid, "grade": ch["grade"], "chapter": ch["chapter"], "lesson": b_name, "level": lv_name,
                    "q": strip_accents_vi(f"{sid} lop {ch['grade']} {ch['chapter']} {b_name} {lv_name}").lower(),
                })
    html_doc = (
        "<!DOCTYPE html><html lang='vi'><head><meta charset='utf-8'><title>Tra cứu ID6 Toán 6-12 GDPT 2018</title>"
        "<style>body{font-family:system-ui;max-width:1060px;margin:auto;padding:16px}input{width:100%;padding:10px;margin-bottom:12px}"
        "table{width:100%;border-collapse:collapse}th,td{border:1px solid #ddd;padding:8px}th{background:#1f4e78;color:#fff}"
        "code{background:#eef3f8;padding:2px 6px;border-radius:4px;cursor:pointer}</style></head><body>"
        "<h2>Tra cứu nhanh Mã ID6 Toán 6–12 (GDPT 2018)</h2><input id='q' placeholder='Gõ không dấu để lọc (VD: lop 11 cap so cong, tich phan, thales)...'>"
        "<table><thead><tr><th>Mã mẫu (bấm chép)</th><th>Lớp</th><th>Chương</th><th>Bài</th><th>Mức độ</th></tr></thead><tbody id='tb'></tbody></table>"
        f"<script>const ROWS={json.dumps(rows, ensure_ascii=False)};"
        "const norm=s=>s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').replace(/[đĐ]/g,'d').toLowerCase();"
        "const render=k=>{const q=norm(k||'').trim();const rs=q?ROWS.filter(r=>r.q.includes(q)):ROWS.slice(0,150);"
        "tb.innerHTML=rs.map(r=>`<tr><td><code onclick=\"navigator.clipboard?.writeText('${r.id}')\">${r.id}</code></td><td>${r.grade}</td><td>${r.chapter}</td><td>${r.lesson}</td><td>${r.level}</td></tr>`).join('');};"
        "q.addEventListener('input',e=>render(e.target.value));render('');</script></body></html>"
    )
    Path(out_html).write_text(html_doc, encoding="utf-8")
    return out_html
