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


# ---------------------------------------------------------------- phiếu trả lời (in / tô sẵn đáp án)
def _bub(x, y, txt, filled=False, r=0.17):
    fill = "black" if filled else "white"
    color = "white" if filled else "black"
    return (f"\\draw[fill={fill}] ({x:.2f},{y:.2f}) circle ({r});"
            f"\\node[font=\\tiny,text={color}] at ({x:.2f},{y:.2f}){{{txt}}};")


def sheet_tikz(n_tn=40, n_ds=8, n_kq=6, code="", key=None, title="PHIẾU TRẢ LỜI TRẮC NGHIỆM",
               code_digits=3, sbd_digits=6) -> str:
    """Phiếu trả lời 3 phần (TN · Đúng/Sai · Trả lời ngắn). key = None (phiếu trắng) hoặc đáp án một mã đề
    {'TN': ['A', …], 'DS': [[True, False, …], …], 'KQ': ['0,5', …]} để tô sẵn (phiếu khoá cho phần mềm chấm)."""
    key = key or {}
    L = ["\\begin{tikzpicture}[x=1cm,y=1cm]",
         "\\draw[thick] (0,0) rectangle (19,-26.5);",
         f"\\node[font=\\bfseries\\large] at (9.5,-0.6){{{title}}};",
         "\\node[anchor=west] at (0.4,-1.4){Họ và tên: \\makebox[7cm]{\\dotfill}};",
         "\\node[anchor=west] at (0.4,-2.1){Lớp: \\makebox[2.5cm]{\\dotfill}\\quad Phòng: \\makebox[2cm]{\\dotfill}};"]
    # số báo danh + mã đề
    def digit_block(x0, label, n, value=""):
        out = [f"\\node[font=\\small\\bfseries] at ({x0 + (n - 1) * 0.225:.2f},-1.3){{{label}}};"]
        for j in range(n):
            ch = value[j] if j < len(value) else ""
            out.append(f"\\draw ({x0 + j * 0.45 - 0.2:.2f},-1.55) rectangle ({x0 + j * 0.45 + 0.2:.2f},-1.95);")
            if ch:
                out.append(f"\\node[font=\\small] at ({x0 + j * 0.45:.2f},-1.75){{{ch}}};")
            for d in range(10):
                out.append(_bub(x0 + j * 0.45, -2.3 - d * 0.42, str(d), ch == str(d)))
        return out
    L += digit_block(11.0, "Số báo danh", sbd_digits)
    L += digit_block(14.6 + (6 - sbd_digits) * 0.3, "Mã đề", code_digits, str(code)[-code_digits:] if code else "")
    # Phần I
    y0 = -6.9
    L.append(f"\\node[anchor=west,font=\\bfseries] at (0.3,{y0}){{PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn}};")
    tn = key.get("TN") or []
    cols = max(1, -(-n_tn // 10))
    for c in range(cols):
        x0 = 0.9 + c * (18 / max(cols, 4))
        for j, letter in enumerate("ABCD"):
            L.append(f"\\node[font=\\scriptsize\\bfseries] at ({x0 + 0.6 + j * 0.45:.2f},{y0 - 0.45}){{{letter}}};")
        for r in range(10):
            i = c * 10 + r
            if i >= n_tn:
                break
            y = y0 - 0.9 - r * 0.42
            L.append(f"\\node[font=\\scriptsize] at ({x0:.2f},{y:.2f}){{{i + 1}}};")
            for j, letter in enumerate("ABCD"):
                L.append(_bub(x0 + 0.6 + j * 0.45, y, letter, i < len(tn) and tn[i] == letter))
    # Phần II
    y0 = -12.2
    L.append(f"\\node[anchor=west,font=\\bfseries] at (0.3,{y0}){{PHẦN II. Câu trắc nghiệm đúng sai}};")
    ds = key.get("DS") or []
    per_row = 4
    for i in range(n_ds):
        bx = 0.9 + (i % per_row) * 4.5
        by = y0 - 0.6 - (i // per_row) * 2.6
        L.append(f"\\node[font=\\scriptsize\\bfseries] at ({bx + 0.9:.2f},{by:.2f}){{Câu {i + 1}}};")
        L.append(f"\\node[font=\\tiny] at ({bx + 0.7:.2f},{by - 0.35:.2f}){{Đúng}};"
                 f"\\node[font=\\tiny] at ({bx + 1.3:.2f},{by - 0.35:.2f}){{Sai}};")
        for k, y_ in enumerate("abcd"):
            yy = by - 0.75 - k * 0.42
            L.append(f"\\node[font=\\scriptsize] at ({bx:.2f},{yy:.2f}){{{y_})}};")
            val = ds[i][k] if i < len(ds) and k < len(ds[i]) else None
            L.append(_bub(bx + 0.7, yy, "", val is True))
            L.append(_bub(bx + 1.3, yy, "", val is False))
    # Phần III
    y0 = -18.0
    L.append(f"\\node[anchor=west,font=\\bfseries] at (0.3,{y0}){{PHẦN III. Câu trắc nghiệm trả lời ngắn}};")
    kq = key.get("KQ") or []
    for i in range(n_kq):
        bx = 0.9 + i * 3.0
        ans = (kq[i] if i < len(kq) else "").replace(".", ",")
        ans = ans if len(ans) <= 4 else ""
        L.append(f"\\node[font=\\scriptsize\\bfseries] at ({bx + 0.7:.2f},{y0 - 0.5:.2f}){{Câu {i + 1}}};")
        for j in range(4):
            ch = ans[j] if j < len(ans) else ""
            x = bx + j * 0.45
            L.append(f"\\draw ({x - 0.2:.2f},{y0 - 0.8:.2f}) rectangle ({x + 0.2:.2f},{y0 - 1.2:.2f});")
            if ch:
                L.append(f"\\node[font=\\small] at ({x:.2f},{y0 - 1.0:.2f}){{{ch}}};")
            rows = (["-"] if j == 0 else []) + ([","] if j in (1, 2) else []) + [str(d) for d in range(10)]
            yy = y0 - 1.5
            for sym in ["-", ","] + [str(d) for d in range(10)]:
                if sym in rows:
                    L.append(_bub(x, yy, sym if sym != "," else "{,}", ch == sym))
                yy -= 0.42
    L.append("\\end{tikzpicture}")
    return "\n".join(L)


def sheet_document(versions=None, blank_counts=None, title="PHIẾU TRẢ LỜI TRẮC NGHIỆM") -> str:
    """Tài liệu LaTeX: mỗi trang một phiếu. versions → phiếu tô sẵn đáp án từng mã; không có → 1 phiếu trắng."""
    from .exporter import plain_answer
    pages = []
    if versions:
        for v in versions:
            key = {"TN": [q.answer_text for q in v.sections.get("TN") or []],
                   "DS": [list(q.correct) for q in v.sections.get("DS") or []],
                   "KQ": [plain_answer(q.answer_text) for q in v.sections.get("KQ") or []]}
            n = {s: max(len(v.sections.get(s) or []), 1) for s in ("TN", "DS", "KQ")}
            pages.append(sheet_tikz(max(n["TN"], 12), n["DS"], n["KQ"], v.code, key, title,
                                    code_digits=max(3, len(v.code))))
    else:
        c = blank_counts or PHIEU_2025
        pages.append(sheet_tikz(c.get("TN", 40), c.get("DS", 8), c.get("KQ", 6), title=title))
    return ("\\documentclass{article}\n\\usepackage[utf8]{vietnam}\n\\usepackage{tikz}\n"
            "\\usepackage[a4paper,margin=1cm]{geometry}\n\\pagestyle{empty}\n\\begin{document}\n"
            + "\n\\newpage\n".join("\\noindent\\centering\n" + p for p in pages) + "\n\\end{document}\n")
