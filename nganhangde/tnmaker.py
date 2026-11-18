"""Xuất đáp án ra Excel để nhập vào phần mềm chấm phiếu (TNMaker, …).

Mỗi phần mềm chấm có mẫu file đáp án riêng, nên bố cục được cấu hình qua ExportOptions:

  tnmaker_layout = 'doc'   (mặc định)            tnmaker_layout = 'ngang'
      Câu   | 0101 | 0102 | …                      Mã đề | I.1 | I.2 | … | II.1 | … | III.1 | …
      I.1   |  A   |  C   |                        0101  |  A  |  C  |   | ĐSĐS |   | 0,92  |
      …
      II.1  | ĐSĐS | SSĐĐ |    (ds_style='gop')
      II.1a |  Đ   |  S   |    (ds_style='tach')
      III.1 | 0,92 | 541  |

Có thêm sheet «Thông tin» ghi cấu trúc đề và thang điểm, sheet «Mã đề – câu gốc» để đối chiếu câu.
"""
from __future__ import annotations

from .generator import SECTION_ORDER, ExamVersion

PART = {"TN": "I", "DS": "II", "KQ": "III"}
SYMBOLS = {"ĐS": ("Đ", "S"), "TF": ("T", "F"), "10": ("1", "0")}


def _plain_kq(a: str, dec: str) -> str:
    from .exporter import plain_answer
    a = plain_answer(a)
    return a.replace(",", dec) if dec != "," else a.replace(".", ",")


def answer_columns(versions: list[ExamVersion], opt) -> list[tuple[str, str, int, int | None]]:
    """Danh sách cột/dòng đáp án: (nhãn, phần, số câu, ý) – ý = None nếu gộp."""
    cols = []
    for s in SECTION_ORDER:
        if s == "TL":
            continue
        n = max((len(v.sections.get(s) or []) for v in versions), default=0)
        for i in range(1, n + 1):
            if s == "DS" and opt.ds_style == "tach":
                for k, y in enumerate("abcd"):
                    cols.append((f"{PART[s]}.{i}{y}", s, i, k))
            else:
                cols.append((f"{PART[s]}.{i}", s, i, None))
    return cols


def cell_value(v: ExamVersion, s: str, i: int, k: int | None, opt) -> str:
    qs = v.sections.get(s) or []
    if i > len(qs):
        return ""
    q = qs[i - 1]
    if s == "TN":
        return q.answer_text
    if s == "DS":
        t, f = SYMBOLS.get(opt.ds_symbols, SYMBOLS["ĐS"])
        marks = [t if c else f for c in q.correct]
        return marks[k] if k is not None else "".join(marks)
    return _plain_kq(q.answer_text, opt.kq_decimal)


def write_answer_xlsx(versions: list[ExamVersion], path: str, opt) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Đáp án"
    cols = answer_columns(versions, opt)
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F4E79")
    center = Alignment(horizontal="center", vertical="center")

    if opt.tnmaker_layout == "ngang":
        ws.append(["Mã đề"] + [c[0] for c in cols])
        for v in versions:
            ws.append([v.code] + [cell_value(v, s, i, k, opt) for _, s, i, k in cols])
        header_cells = ws[1]
    else:
        ws.append(["Câu"] + [v.code for v in versions])
        for label, s, i, k in cols:
            ws.append([label] + [cell_value(v, s, i, k, opt) for v in versions])
        header_cells = ws[1]
    for c in header_cells:
        c.font, c.fill, c.alignment = head_font, head_fill, center
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = center
            c.number_format = "@"          # lưu dạng chữ: giữ '0101', '0,92', '-4'
    for j in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(j)].width = 9
    ws.freeze_panes = "B2"

    # Sheet thông tin cấu trúc + thang điểm
    from .exporter import SCORING
    info = wb.create_sheet("Thông tin")
    v0 = versions[0] if versions else None
    n = {s: len(v0.sections.get(s) or []) if v0 else 0 for s in SECTION_ORDER}
    info.append(["Số mã đề", len(versions)])
    info.append(["Phần I – trắc nghiệm 4 phương án", n["TN"], f"{SCORING['TN']:g} điểm/câu"])
    info.append(["Phần II – Đúng/Sai (4 ý)", n["DS"], "1 ý 0,1 · 2 ý 0,25 · 3 ý 0,5 · 4 ý 1 điểm"])
    info.append(["Phần III – trả lời ngắn", n["KQ"], f"{SCORING['KQ']:g} điểm/câu"])
    info.append(["Kí hiệu Đúng/Sai", "/".join(SYMBOLS.get(opt.ds_symbols, SYMBOLS["ĐS"]))])
    info.append(["Dấu thập phân phần III", opt.kq_decimal])
    info.column_dimensions["A"].width = 36
    info.column_dimensions["C"].width = 40

    # Sheet đối chiếu: câu trong mã đề ↔ ID câu gốc
    m = wb.create_sheet("Mã đề – câu gốc")
    m.append(["Mã đề", "Phần", "Câu", "ID", "Mã câu trong kho"])
    for v in versions:
        for s in SECTION_ORDER:
            for i, q in enumerate(v.sections.get(s) or [], 1):
                m.append([v.code, PART.get(s, "IV"), i, q.id_code, q.db_id if q.db_id is not None else ""])
    wb.save(path)
    return path
