from collections import OrderedDict
from dataclasses import dataclass, field
from ..core.matrix_cv7991 import ExamMatrix

QTYPES = ("TN", "DS", "KQ", "TL")
QTYPE_LABELS = {"TN": "Nhiều lựa chọn", "DS": "Đúng – Sai", "KQ": "Trả lời ngắn", "TL": "Tự luận"}
LEVELS = ("NB", "TH", "VD")
LEVEL_LABELS = {"NB": "Biết", "TH": "Hiểu", "VD": "Vận dụng"}


def _map_lv(md: str) -> str:
    x = (md or "").strip().upper()
    return "NB" if x in ("N", "Y", "NB") else ("TH" if x in ("H", "B", "TH") else ("VD" if x in ("V", "K", "C", "G", "VD") else "NB"))


@dataclass
class SpecRow:
    chapter: str
    content_unit: str
    outcomes: str = ""
    counts: dict[str, dict[str, int]] = field(default_factory=lambda: {qt: {lv: 0 for lv in LEVELS} for qt in QTYPES})

    def level_total(self, lv: str) -> int:
        return sum(self.counts[qt][lv] for qt in QTYPES)

    def row_points(self, unit_points: dict[str, float]) -> float:
        return sum(sum(self.counts[qt].values()) * unit_points.get(qt, 0.0) for qt in QTYPES)


def build_cv7991_rows(matrix: ExamMatrix, outcomes_map: dict[str, str] | None = None):
    outcomes_map = outcomes_map or {}
    grouped: OrderedDict[tuple[str, str], SpecRow] = OrderedDict()
    for r in matrix.rules:
        if r.qtype not in QTYPES or r.count <= 0:
            continue
        chap, unit = [p.strip() for p in r.topic.split("|", 1)] if "|" in r.topic else (r.id_glob[:3] if len(r.id_glob) >= 3 and r.id_glob != "*" else "Chủ đề chung", r.topic.strip() or r.id_glob)
        if (chap, unit) not in grouped:
            grouped[(chap, unit)] = SpecRow(chap, unit, outcomes_map.get(unit) or r.competency or "")
        grouped[(chap, unit)].counts[r.qtype][_map_lv(r.muc_do)] += r.count
    totals = matrix.total_by_type()
    unit_pts = {qt: (matrix.part_points.get(qt, 0.0) / totals[qt] if totals[qt] > 0 else 0.0) for qt in QTYPES}
    total_pts = sum(matrix.part_points.get(qt, 0.0) for qt in QTYPES if totals[qt] > 0) or 10.0
    return list(grouped.values()), unit_pts, total_pts


def export_cv7991_excel(matrix: ExamMatrix, out_xlsx: str, outcomes_map: dict[str, str] | None = None) -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    rows, unit_pts, total_pts = build_cv7991_rows(matrix, outcomes_map)
    wb = openpyxl.Workbook()
    thin = Side(style="thin", color="888888")
    bdr = Border(left=thin, right=thin, top=thin, bottom=thin)
    hf, sf = PatternFill("solid", fgColor="1F4E78"), PatternFill("solid", fgColor="D9E1F2")
    hfont, bfont = Font(color="FFFFFF", bold=True), Font(bold=True)
    ctr = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws1 = wb.active
    ws1.title = "PhuLuc1_MaTran"
    ws1.merge_cells("A1:S1")
    ws1["A1"] = f"MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ — {matrix.name.upper()}"
    for col_i, t in [(1, "TT"), (2, "Chủ đề/Chương"), (3, "Nội dung/đơn vị kiến thức"), (19, "Tỉ lệ % điểm")]:
        ws1.merge_cells(start_row=3, start_column=col_i, end_row=4, end_column=col_i)
        c = ws1.cell(3, col_i, t)
        c.fill, c.font, c.alignment = hf, hfont, ctr
    for sc, title in [(4, "Nhiều lựa chọn"), (7, "Đúng – Sai"), (10, "Trả lời ngắn"), (13, "Tự luận"), (16, "Tổng số câu theo mức")]:
        ws1.merge_cells(start_row=3, start_column=sc, end_row=3, end_column=sc + 2)
        c = ws1.cell(3, sc, title)
        c.fill, c.font, c.alignment = hf, hfont, ctr
        for off, lv in enumerate(LEVELS):
            sub = ws1.cell(4, sc + off, LEVEL_LABELS[lv])
            sub.fill, sub.font, sub.alignment = sf, bfont, ctr

    r_i, csums, lpts = 5, {c: 0 for c in range(4, 19)}, {lv: 0.0 for lv in LEVELS}
    for tt, row in enumerate(rows, 1):
        ws1.cell(r_i, 1, tt).alignment = ctr
        ws1.cell(r_i, 2, row.chapter)
        ws1.cell(r_i, 3, row.content_unit)
        col = 4
        for qt in QTYPES:
            for lv in LEVELS:
                v = row.counts[qt][lv]
                ws1.cell(r_i, col, v if v else "").alignment = ctr
                csums[col] += v
                lpts[lv] += v * unit_pts[qt]
                col += 1
        for off, lv in enumerate(LEVELS):
            cnt = row.level_total(lv)
            ws1.cell(r_i, 16 + off, cnt if cnt else "").alignment = ctr
            csums[16 + off] += cnt
        ws1.cell(r_i, 19, round(row.row_points(unit_pts) / total_pts * 100.0, 1)).alignment = ctr
        r_i += 1

    totals = matrix.total_by_type()
    ws1.merge_cells(start_row=r_i, start_column=1, end_row=r_i, end_column=3)
    ws1.cell(r_i, 1, "Tổng số câu").font = bfont
    for c in range(4, 19):
        ws1.cell(r_i, c, csums[c]).font = bfont
    ws1.cell(r_i, 19, sum(csums[c] for c in range(16, 19))).font = bfont
    r_i += 1
    ws1.merge_cells(start_row=r_i, start_column=1, end_row=r_i, end_column=3)
    ws1.cell(r_i, 1, "Tổng số điểm").font = bfont
    for qi, qt in enumerate(QTYPES):
        sc = 4 + qi * 3
        ws1.merge_cells(start_row=r_i, start_column=sc, end_row=r_i, end_column=sc + 2)
        ws1.cell(r_i, sc, round(matrix.part_points.get(qt, 0.0), 2) if totals[qt] > 0 else 0.0).font = bfont
    for off, lv in enumerate(LEVELS):
        ws1.cell(r_i, 16 + off, round(lpts[lv], 2)).font = bfont
    ws1.cell(r_i, 19, round(total_pts, 2)).font = bfont
    r_i += 1
    ws1.merge_cells(start_row=r_i, start_column=1, end_row=r_i, end_column=3)
    ws1.cell(r_i, 1, "Tỉ lệ % điểm").font = bfont
    for qi, qt in enumerate(QTYPES):
        sc = 4 + qi * 3
        ws1.merge_cells(start_row=r_i, start_column=sc, end_row=r_i, end_column=sc + 2)
        pts = matrix.part_points.get(qt, 0.0) if totals[qt] > 0 else 0.0
        ws1.cell(r_i, sc, round(pts / total_pts * 100.0, 1)).font = bfont
    for off, lv in enumerate(LEVELS):
        ws1.cell(r_i, 16 + off, round(lpts[lv] / total_pts * 100.0, 1)).font = bfont
    ws1.cell(r_i, 19, 100.0).font = bfont
    for rr in range(3, r_i + 1):
        for cc in range(1, 20):
            ws1.cell(rr, cc).border = bdr

    ws2 = wb.create_sheet("PhuLuc2_BanDacTa")
    ws2.merge_cells("A1:P1")
    ws2["A1"] = f"BẢN ĐẶC TẢ ĐỀ KIỂM TRA ĐỊNH KÌ — {matrix.name.upper()}"
    for col_i, t in [(1, "TT"), (2, "Chủ đề/Chương"), (3, "Nội dung/đơn vị kiến thức"), (4, "Yêu cầu cần đạt")]:
        ws2.merge_cells(start_row=3, start_column=col_i, end_row=4, end_column=col_i)
        c = ws2.cell(3, col_i, t)
        c.fill, c.font, c.alignment = hf, hfont, ctr
    for qi, qt in enumerate(QTYPES):
        sc = 5 + qi * 3
        ws2.merge_cells(start_row=3, start_column=sc, end_row=3, end_column=sc + 2)
        c = ws2.cell(3, sc, QTYPE_LABELS[qt])
        c.fill, c.font, c.alignment = hf, hfont, ctr
        for off, lv in enumerate(LEVELS):
            sub = ws2.cell(4, sc + off, LEVEL_LABELS[lv])
            sub.fill, sub.font, sub.alignment = sf, bfont, ctr
    for tt, row in enumerate(rows, 1):
        rr = 4 + tt
        ws2.cell(rr, 1, tt).alignment = ctr
        ws2.cell(rr, 2, row.chapter)
        ws2.cell(rr, 3, row.content_unit)
        ws2.cell(rr, 4, row.outcomes or "- Đạt YCCĐ chương trình GDPT 2018.")
        col = 5
        for qt in QTYPES:
            for lv in LEVELS:
                v = row.counts[qt][lv]
                ws2.cell(rr, col, v if v else "").alignment = ctr
                col += 1
    for rr in range(3, 5 + len(rows)):
        for cc in range(1, 17):
            ws2.cell(rr, cc).border = bdr
    wb.save(out_xlsx)


def export_cv7991_docx(matrix: ExamMatrix, out_docx: str, outcomes_map: dict[str, str] | None = None) -> None:
    try:
        from docx import Document
        from docx.enum.section import WD_ORIENT
        from docx.shared import Pt
    except ImportError as exc:
        raise RuntimeError("Thiếu python-docx. Chạy: pip install python-docx") from exc

    rows, unit_pts, total_pts = build_cv7991_rows(matrix, outcomes_map)
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width

    doc.add_heading(f"PHỤ LỤC 1. MA TRẬN — {matrix.name}", level=1)
    t1 = doc.add_table(rows=2 + len(rows) + 3, cols=19)
    t1.style = "Table Grid"
    for ci, txt in [(0, "TT"), (1, "Chủ đề/Chương"), (2, "Nội dung"), (18, "Tỉ lệ %")]:
        t1.cell(0, ci).merge(t1.cell(1, ci)).text = txt
    for gi, title in enumerate(["Nhiều lựa chọn", "Đúng – Sai", "Trả lời ngắn", "Tự luận", "Tổng câu"]):
        sc = 3 + gi * 3
        t1.cell(0, sc).merge(t1.cell(0, sc + 2)).text = title
        for off, lv in enumerate(LEVELS):
            t1.cell(1, sc + off).text = LEVEL_LABELS[lv]
    csums, lpts = [0] * 19, {lv: 0.0 for lv in LEVELS}
    for i, row in enumerate(rows):
        rr = 2 + i
        t1.cell(rr, 0).text, t1.cell(rr, 1).text, t1.cell(rr, 2).text = str(i + 1), row.chapter, row.content_unit
        c = 3
        for qt in QTYPES:
            for lv in LEVELS:
                v = row.counts[qt][lv]
                t1.cell(rr, c).text = str(v) if v else ""
                csums[c] += v
                lpts[lv] += v * unit_pts[qt]
                c += 1
        for off, lv in enumerate(LEVELS):
            cnt = row.level_total(lv)
            t1.cell(rr, 15 + off).text = str(cnt) if cnt else ""
            csums[15 + off] += cnt
        t1.cell(rr, 18).text = f"{round(row.row_points(unit_pts) / total_pts * 100.0, 1)}%"
    br, totals = 2 + len(rows), matrix.total_by_type()
    t1.cell(br, 0).merge(t1.cell(br, 2)).text = "Tổng số câu"
    for c in range(3, 18):
        t1.cell(br, c).text = str(csums[c])
    t1.cell(br, 18).text = str(sum(csums[15:18]))
    t1.cell(br + 1, 0).merge(t1.cell(br + 1, 2)).text = "Tổng số điểm"
    for qi, qt in enumerate(QTYPES):
        sc = 3 + qi * 3
        t1.cell(br + 1, sc).merge(t1.cell(br + 1, sc + 2)).text = str(round(matrix.part_points.get(qt, 0.0), 2) if totals[qt] > 0 else 0.0)
    for off, lv in enumerate(LEVELS):
        t1.cell(br + 1, 15 + off).text = str(round(lpts[lv], 2))
    t1.cell(br + 1, 18).text = str(round(total_pts, 2))
    t1.cell(br + 2, 0).merge(t1.cell(br + 2, 2)).text = "Tỉ lệ % điểm"
    for qi, qt in enumerate(QTYPES):
        sc = 3 + qi * 3
        pts = matrix.part_points.get(qt, 0.0) if totals[qt] > 0 else 0.0
        t1.cell(br + 2, sc).merge(t1.cell(br + 2, sc + 2)).text = f"{round(pts / total_pts * 100.0, 1)}%"
    for off, lv in enumerate(LEVELS):
        t1.cell(br + 2, 15 + off).text = f"{round(lpts[lv] / total_pts * 100.0, 1)}%"
    t1.cell(br + 2, 18).text = "100%"

    doc.add_page_break()
    doc.add_heading(f"PHỤ LỤC 2. BẢN ĐẶC TẢ — {matrix.name}", level=1)
    t2 = doc.add_table(rows=2 + len(rows), cols=16)
    t2.style = "Table Grid"
    for ci, txt in [(0, "TT"), (1, "Chủ đề/Chương"), (2, "Nội dung"), (3, "Yêu cầu cần đạt")]:
        t2.cell(0, ci).merge(t2.cell(1, ci)).text = txt
    for qi, qt in enumerate(QTYPES):
        sc = 4 + qi * 3
        t2.cell(0, sc).merge(t2.cell(0, sc + 2)).text = QTYPE_LABELS[qt]
        for off, lv in enumerate(LEVELS):
            t2.cell(1, sc + off).text = LEVEL_LABELS[lv]
    for i, row in enumerate(rows):
        rr = 2 + i
        t2.cell(rr, 0).text, t2.cell(rr, 1).text, t2.cell(rr, 2).text, t2.cell(rr, 3).text = str(i + 1), row.chapter, row.content_unit, row.outcomes or "- Đạt YCCĐ GDPT 2018."
        c = 4
        for qt in QTYPES:
            for lv in LEVELS:
                v = row.counts[qt][lv]
                t2.cell(rr, c).text = str(v) if v else ""
                c += 1
    for tbl in (t1, t2):
        for r in tbl.rows:
            for cell in r.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(8.5)
    doc.save(out_docx)
