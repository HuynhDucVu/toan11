"""Phiếu chấm trắc nghiệm (OMR): kiểm tra sức chứa phiếu, file đáp án theo mẫu bất kì, mã QR đáp án.

Mỗi phần mềm chấm (TNMaker, QM, Azota, SmartTest, …) có mẫu file đáp án riêng và có thể đổi theo phiên bản.
Thay vì đoán, `fill_template` đọc **file mẫu do chính phần mềm đó xuất ra** và điền đáp án vào đúng cột/dòng:

* Mẫu ngang: một dòng tiêu đề có ô «Mã đề» (Ma de / Code …) và các ô câu: «1», «Câu 1», «I.1», «II.3b», «III.2»…
  → mỗi mã đề ghi một dòng.
* Mẫu dọc: cột đầu có ô «Câu» rồi bên dưới là nhãn câu → mã đề ghi vào dòng tiêu đề, mỗi mã một cột.

Nhãn có số La Mã (I, II, III) đánh số theo phần; nhãn chỉ có số đánh số liên tục qua các phần (TN → ĐS → TLN).
Chữ a–d sau số là ý của câu Đúng/Sai.
"""
from __future__ import annotations

import re

from .generator import ExamVersion

# Phiếu trả lời trắc nghiệm theo mẫu thi tốt nghiệp THPT từ 2025
PHIEU_2025 = {"TN": 40, "DS": 8, "KQ": 6}
PART_NAME = {"TN": "Phần I", "DS": "Phần II", "KQ": "Phần III"}
KQ_OK = re.compile(r"^-?[0-9]*,?[0-9]*$")

CODE_HEAD = re.compile(r"^(m[aã]\s*đ[eề]|ma\s*de|made|m[aã]\s*đề\s*thi|code|test\s*code|key|đề)$", re.I)
ROW_HEAD = re.compile(r"^(c[aâ]u|cau|stt|question|q)$", re.I)
LABEL = re.compile(r"^(?:(IV|III|II|I)\s*[.\-_ ]\s*)?(?:c[aâ]u|cau|q|question|c)?\s*\.?\s*(\d+)\s*[.\-_ ]?\s*([a-dA-D])?$",
                   re.I)
ROMAN = {"I": "TN", "II": "DS", "III": "KQ"}


def check_capacity(versions: list[ExamVersion], cap: dict | None = None) -> list[str]:
    """Cảnh báo khi đề không vừa phiếu: quá số câu mỗi phần, đáp án trả lời ngắn không tô được."""
    from .exporter import plain_answer
    cap = cap or PHIEU_2025
    out = []
    for v in versions[:1] or []:
        for s, m in cap.items():
            n = len(v.sections.get(s) or [])
            if n > m:
                out.append(f"{PART_NAME[s]} có {n} câu, phiếu chỉ có {m} ô – học sinh không tô hết được.")
    seen = set()
    for v in versions:
        for i, q in enumerate(v.sections.get("KQ") or [], 1):
            a = plain_answer(q.answer_text)
            if (len(a) > 4 or not KQ_OK.match(a) or not a) and q.db_id not in seen:
                seen.add(q.db_id)
                out.append(f"Mã {v.code} Phần III câu {i}: đáp án «{a}» không tô được trên phiếu "
                           "(tối đa 4 kí tự gồm chữ số, dấu - và dấu phẩy).")
    return out


# ---------------------------------------------------------------- mã QR đáp án
def qr_payload(v: ExamVersion) -> str:
    """Chuỗi ASCII gọn: 0101|I:ABCD…|II:1010,0011|III:0,92;-4 (Đ=1, S=0)."""
    from .exporter import plain_answer
    parts = [v.code]
    tn = "".join(q.answer_text or "?" for q in v.sections.get("TN") or [])
    if tn:
        parts.append("I:" + tn)
    ds = ",".join("".join("1" if c else "0" for c in q.correct) for q in v.sections.get("DS") or [])
    if ds:
        parts.append("II:" + ds)
    kq = ";".join(plain_answer(q.answer_text) for q in v.sections.get("KQ") or [])
    if kq:
        parts.append("III:" + kq)
    return "|".join(parts)


def qr_tex(v: ExamVersion) -> str:
    data = qr_payload(v).replace("%", "\\%").replace("#", "\\#")
    return ("\\begin{center}\\qrcode[height=3cm]{" + data + "}\\\\\n"
            "{\\footnotesize Mã QR đáp án mã đề " + v.code + " (Đ = 1, S = 0)}\\end{center}")


# ---------------------------------------------------------------- điền file mẫu
def parse_label(text) -> tuple[str | None, int, int | None] | None:
    """'I.3' → ('TN', 3, None); 'II.2b' → ('DS', 2, 1); 'Câu 15' → (None, 15, None)."""
    if text is None:
        return None
    t = str(text).strip()
    if isinstance(text, (int, float)) and float(text).is_integer():
        return None, int(text), None
    m = LABEL.match(t)
    if not m:
        return None
    part = ROMAN.get((m.group(1) or "").upper())
    sub = "abcd".index(m.group(3).lower()) if m.group(3) else None
    return part, int(m.group(2)), sub


def _flat(v: ExamVersion) -> list[tuple[str, int]]:
    return [(s, i) for s in ("TN", "DS", "KQ") for i in range(1, len(v.sections.get(s) or []) + 1)]


def _value(v: ExamVersion, lab, opt) -> str:
    from .tnmaker import cell_value
    part, n, sub = lab
    if part is None:
        flat = _flat(v)
        if not 1 <= n <= len(flat):
            return ""
        part, n = flat[n - 1]
    if part == "TN" and sub is not None:
        return ""
    if part != "DS":
        sub = None
    return cell_value(v, part, n, sub, opt)


def fill_template(versions: list[ExamVersion], template: str, out_path: str, opt) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(template)
    ws = wb.active
    # mẫu ngang: tìm dòng có ô «Mã đề»
    for r in range(1, min(ws.max_row, 15) + 1):
        cells = [(c.column, c.value) for c in ws[r] if c.value is not None]
        code_col = next((col for col, val in cells if CODE_HEAD.match(str(val).strip())), None)
        if code_col is None:
            continue
        labels = {col: parse_label(val) for col, val in cells if col != code_col}
        labels = {k: x for k, x in labels.items() if x}
        if not labels:
            continue
        for k, v in enumerate(versions, 1):
            ws.cell(r + k, code_col, v.code).number_format = "@"
            for col, lab in labels.items():
                c = ws.cell(r + k, col, _value(v, lab, opt))
                c.number_format = "@"
        wb.save(out_path)
        return out_path
    # mẫu dọc: tìm ô «Câu» ở một cột, nhãn câu nằm bên dưới
    for r in range(1, min(ws.max_row, 15) + 1):
        for c in ws[r]:
            if c.value is not None and ROW_HEAD.match(str(c.value).strip()):
                col0 = c.column
                rows = {}
                for rr in range(r + 1, ws.max_row + 1):
                    lab = parse_label(ws.cell(rr, col0).value)
                    if lab:
                        rows[rr] = lab
                if not rows:
                    continue
                for k, v in enumerate(versions, 1):
                    ws.cell(r, col0 + k, v.code).number_format = "@"
                    for rr, lab in rows.items():
                        ws.cell(rr, col0 + k, _value(v, lab, opt)).number_format = "@"
                wb.save(out_path)
                return out_path
    raise ValueError("Không nhận ra file mẫu: cần một ô tiêu đề «Mã đề» (mẫu ngang) hoặc «Câu» (mẫu dọc) "
                     "trong 15 dòng đầu, kèm các nhãn câu như 1, 2, … hoặc I.1, II.1a, III.1.")
