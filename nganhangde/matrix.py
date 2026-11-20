"""Ma trận đề kiểm tra theo Công văn 7991/BGDĐT-GDTrH (2024): Excel/Word ↔ ma trận của phần mềm.

Ma trận CV 7991 có hàng là chủ đề/nội dung, cột là dạng câu (nhiều lựa chọn · Đúng/Sai · trả lời ngắn · tự luận)
× cấp độ tư duy (Biết · Hiểu · Vận dụng). Mức «Vận dụng cao» (C) của ID được tính vào cột Vận dụng.

File Excel xuất ra có 2 sheet:
* «Ma trận CV7991»: bảng trình bày để in/nộp;
* «Dòng ma trận»: bảng phẳng (Loại, Mẫu ID, Mức độ, Từ khoá, Số câu) – sửa ở đây rồi «Nạp ma trận từ Excel».
"""
from __future__ import annotations

import re

from .generator import Rule

PARTS = [("TN", "Nhiều lựa chọn"), ("DS", "Đúng – Sai"), ("KQ", "Trả lời ngắn"), ("TL", "Tự luận")]
LEVELS = [("N", "Biết"), ("H", "Hiểu"), ("V", "Vận dụng")]
LEVEL_OF = {"N": "N", "Y": "N", "H": "H", "B": "H", "V": "V", "K": "V", "C": "V", "G": "V"}
LEVEL_NAME = {"N": "Nhận biết", "H": "Thông hiểu", "V": "Vận dụng", "C": "Vận dụng cao"}
TYPE_ALIASES = {"TN": "TN", "I": "TN", "NHIỀU LỰA CHỌN": "TN", "TRẮC NGHIỆM": "TN",
                "DS": "DS", "ĐS": "DS", "II": "DS", "ĐÚNG SAI": "DS", "ĐÚNG – SAI": "DS", "ĐÚNG/SAI": "DS",
                "KQ": "KQ", "III": "KQ", "TRẢ LỜI NGẮN": "KQ", "TLN": "KQ",
                "TL": "TL", "IV": "TL", "TỰ LUẬN": "TL"}


def rule_level(r: Rule) -> str:
    """Cấp độ của dòng ma trận: theo cột Mức độ, nếu trống thì theo kí tự thứ 4 của mẫu ID."""
    if r.muc_do:
        return LEVEL_OF.get(r.muc_do.upper(), "?")
    return LEVEL_OF.get(r.id[3:4].upper(), "?") if len(r.id) >= 4 else "?"


def topic_of(r: Rule, names: dict) -> tuple[str, str]:
    """(khoá chương, tên) từ mẫu ID: '0D2*' → ('0D2', 'Chương …')."""
    k = r.id.upper()[:3]
    if len(k) < 3 or any(ch in k for ch in "*?["):
        return "*", "Chung (mẫu ID không chỉ rõ chương)"
    return k, names.get(k, k)


def build_table(rules: list[Rule], names: dict | None = None, scoring=None):
    """Trả về (các hàng [tên chủ đề, {(phần, mức): số câu}], tổng theo cột, điểm theo phần)."""
    from .scoring import DEFAULT
    sc = scoring or DEFAULT
    names = names or {}
    topics: dict[str, list] = {}
    for r in rules:
        key, name = topic_of(r, names)
        row = topics.setdefault(key, [name, {}])
        cell = (r.qtype, rule_level(r))
        row[1][cell] = row[1].get(cell, 0) + r.count
    rows = [topics[k] for k in sorted(topics)]
    total: dict = {}
    for _, cells in rows:
        for c, n in cells.items():
            total[c] = total.get(c, 0) + n
    n_type = {p: sum(n for (q, _), n in total.items() if q == p) for p, _ in PARTS}
    points = {"TN": n_type["TN"] * sc.tn, "DS": n_type["DS"] * sc.ds[3], "KQ": n_type["KQ"] * sc.kq,
              "TL": sum(sc.tl_points(n_type["TL"]))}
    return rows, total, points


def export_xlsx(rules: list[Rule], path: str, names: dict | None = None, scoring=None, title: str = "") -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    rows, total, points = build_table(rules, names, scoring)
    has_unknown = any(lv == "?" for (_, lv) in total)
    levels = LEVELS + ([("?", "Chưa rõ")] if has_unknown else [])
    wb = Workbook()
    ws = wb.active
    ws.title = "Ma trận CV7991"
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    mid = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ncol = 2 + len(PARTS) * len(levels) + 1
    ws.cell(1, 1, title or "MA TRẬN ĐỀ KIỂM TRA (theo Công văn 7991/BGDĐT-GDTrH)").font = Font(bold=True, size=13)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws.cell(3, 1, "TT")
    ws.cell(3, 2, "Chủ đề / Nội dung")
    ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    ws.merge_cells(start_row=3, start_column=2, end_row=4, end_column=2)
    col = 3
    for p, pname in PARTS:
        ws.cell(3, col, pname)
        ws.merge_cells(start_row=3, start_column=col, end_row=3, end_column=col + len(levels) - 1)
        for j, (_, lname) in enumerate(levels):
            ws.cell(4, col + j, lname)
        col += len(levels)
    ws.cell(3, col, "Tổng số câu")
    ws.merge_cells(start_row=3, start_column=col, end_row=4, end_column=col)
    r0 = 5
    for i, (name, cells) in enumerate(rows, 1):
        ws.cell(r0, 1, i)
        ws.cell(r0, 2, name)
        c = 3
        for p, _ in PARTS:
            for lv, _ in levels:
                n = cells.get((p, lv))
                ws.cell(r0, c, n or None)
                c += 1
        ws.cell(r0, c, sum(cells.values()))
        r0 += 1
    ws.cell(r0, 2, "Tổng số câu").font = Font(bold=True)
    c = 3
    for p, _ in PARTS:
        for lv, _ in levels:
            ws.cell(r0, c, total.get((p, lv)) or None)
            c += 1
    grand = sum(total.values())
    ws.cell(r0, c, grand)
    r0 += 1
    ws.cell(r0, 2, "Tổng điểm").font = Font(bold=True)
    c = 3
    all_pts = sum(points.values()) or 1
    for p, _ in PARTS:
        ws.cell(r0, c, round(points[p], 2))
        ws.merge_cells(start_row=r0, start_column=c, end_row=r0, end_column=c + len(levels) - 1)
        ws.cell(r0 + 1, c, f"{points[p] / all_pts:.0%}")
        ws.merge_cells(start_row=r0 + 1, start_column=c, end_row=r0 + 1, end_column=c + len(levels) - 1)
        c += len(levels)
    ws.cell(r0, c, round(sum(points.values()), 2))
    ws.cell(r0 + 1, 2, "Tỉ lệ").font = Font(bold=True)
    ws.cell(r0 + 1, c, "100%")
    # tỉ lệ theo cấp độ tư duy
    r1 = r0 + 3
    ws.cell(r1, 2, "Tỉ lệ số câu theo cấp độ tư duy").font = Font(bold=True)
    for j, (lv, lname) in enumerate(levels):
        n = sum(x for (_, l_), x in total.items() if l_ == lv)
        ws.cell(r1 + 1 + j, 2, lname)
        ws.cell(r1 + 1 + j, 3, n)
        ws.cell(r1 + 1 + j, 4, f"{n / max(grand, 1):.0%}")
    for row in ws.iter_rows(min_row=3, max_row=r0 + 1, max_col=ncol):
        for cell in row:
            cell.border = box
            cell.alignment = mid
    for cell in ws[3] + ws[4]:
        cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 42
    from openpyxl.utils import get_column_letter
    for j in range(3, ncol + 1):
        ws.column_dimensions[get_column_letter(j)].width = 9
    # bảng phẳng để sửa và nạp lại
    w2 = wb.create_sheet("Dòng ma trận")
    w2.append(["Loại", "Mẫu ID", "Mức độ", "Từ khoá", "Số câu"])
    for cell in w2[1]:
        cell.font = Font(bold=True)
    for r in rules:
        w2.append([r.qtype, r.id, r.muc_do or "", r.text or "", r.count])
    for col_, wd in zip("ABCDE", (8, 16, 9, 24, 8)):
        w2.column_dimensions[col_].width = wd
    w2.append([])
    w2.append(["Loại: TN, DS, KQ, TL · Mức độ: N, H, V, C hoặc để trống · Mẫu ID: 0D2N*, 2H3?1-*, *"])
    wb.save(path)
    return path


def _norm(x) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip()


def import_xlsx(path: str) -> list[Rule]:
    """Đọc sheet «Dòng ma trận» (hoặc sheet đầu tiên có cột Loại/Mẫu ID/Số câu)."""
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    sheets = ([wb["Dòng ma trận"]] if "Dòng ma trận" in wb.sheetnames else []) + list(wb.worksheets)
    for ws in sheets:
        for r in range(1, min(ws.max_row, 20) + 1):
            head = {_norm(c.value).lower(): c.column for c in ws[r] if c.value is not None}
            col = {}
            for key, names in (("qtype", ("loại", "loai", "dạng câu", "phần")), ("id", ("mẫu id", "id", "ma id")),
                               ("muc_do", ("mức độ", "muc do", "mức")), ("text", ("từ khoá", "từ khóa", "tu khoa")),
                               ("count", ("số câu", "so cau", "sl"))):
                col[key] = next((head[n] for n in names if n in head), None)
            if not (col["qtype"] and col["count"]):
                continue
            rules = []
            for rr in range(r + 1, ws.max_row + 1):
                t = TYPE_ALIASES.get(_norm(ws.cell(rr, col["qtype"]).value).upper())
                n = ws.cell(rr, col["count"]).value
                try:
                    n = int(float(str(n).replace(",", ".")))
                except (TypeError, ValueError):
                    continue
                if not t or n <= 0:
                    continue
                get = (lambda k: _norm(ws.cell(rr, col[k]).value) if col[k] else "")
                rules.append(Rule(t, n, get("id") or "*", (get("muc_do") or "").upper()[:1] or None,
                                  get("text") or None))
            if rules:
                return rules
    raise ValueError("Không tìm thấy bảng ma trận: cần các cột «Loại» và «Số câu» (thêm «Mẫu ID», «Mức độ» nếu có).")


def to_html(rules: list[Rule], names: dict | None = None, scoring=None, title: str = "") -> str:
    """Bảng HTML (dùng để chuyển sang Word bằng pandoc)."""
    import html
    rows, total, points = build_table(rules, names, scoring)
    th = "".join(f"<th colspan='3'>{n}</th>" for _, n in PARTS)
    th2 = "".join(f"<th>{n}</th>" for _ in PARTS for _, n in LEVELS)
    body = []
    for i, (name, cells) in enumerate(rows, 1):
        tds = "".join(f"<td>{cells.get((p, lv), '')}</td>" for p, _ in PARTS for lv, _ in LEVELS)
        body.append(f"<tr><td>{i}</td><td>{html.escape(name)}</td>{tds}<td>{sum(cells.values())}</td></tr>")
    tds = "".join(f"<td>{total.get((p, lv), '')}</td>" for p, _ in PARTS for lv, _ in LEVELS)
    body.append(f"<tr><td></td><td><b>Tổng số câu</b></td>{tds}<td>{sum(total.values())}</td></tr>")
    pts = "".join(f"<td colspan='3'>{points[p]:g}</td>" for p, _ in PARTS)
    body.append(f"<tr><td></td><td><b>Tổng điểm</b></td>{pts}<td>{sum(points.values()):g}</td></tr>")
    return (f"<html><body><h2>{html.escape(title or 'MA TRẬN ĐỀ KIỂM TRA (CV 7991)')}</h2><table border='1'>"
            f"<tr><th rowspan='2'>TT</th><th rowspan='2'>Chủ đề / Nội dung</th>{th}<th rowspan='2'>Tổng</th></tr>"
            f"<tr>{th2}</tr>" + "".join(body) + "</table></body></html>")


def export_docx(rules: list[Rule], path: str, names: dict | None = None, scoring=None, title: str = "") -> str:
    """Word qua pandoc (báo PandocMissing nếu máy chưa cài)."""
    import os
    import tempfile
    from .wordconv import _run
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "mt.html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(to_html(rules, names, scoring, title))
        _run([src, "-o", path])
    return path
