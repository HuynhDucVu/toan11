"""Xuất đề thi, lời giải, bảng đáp án."""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass

from .generator import SECTION_ORDER, SECTION_TITLE, ExamVersion
from .parser import Question

DEFAULT_TEMPLATE = "de_thi.tex"

# Lời dẫn theo mẫu đề thi tốt nghiệp THPT (số câu điền tự động)
OFFICIAL_TITLE = {
    "TN": ("PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn.",
           "Thí sinh trả lời từ câu 1 đến câu {n}. Mỗi câu hỏi thí sinh chỉ chọn một phương án."),
    "DS": ("PHẦN II. Câu trắc nghiệm đúng sai.",
           "Thí sinh trả lời từ câu 1 đến câu {n}. Trong mỗi ý a), b), c), d) ở mỗi câu, thí sinh chọn đúng hoặc sai."),
    "KQ": ("PHẦN III. Câu trắc nghiệm trả lời ngắn.", "Thí sinh trả lời từ câu 1 đến câu {n}."),
    "TL": ("PHẦN IV. Tự luận.", ""),
}
# Thang điểm theo quy chế thi tốt nghiệp THPT từ 2025 (môn Toán)
SCORING = {"TN": 0.25, "KQ": 0.5, "DS": {1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}}


@dataclass
class ExportOptions:
    """Tuỳ chọn khi xuất đề."""
    renumber: bool = False            # đánh số lại từ Câu 1 ở mỗi phần (\setcounter{ex}{0})
    official_titles: bool = False     # tiêu đề + lời dẫn theo mẫu đề thi tốt nghiệp
    scoring: bool = False             # in thang điểm trong file lời giải
    answers_xlsx: bool = True         # đáp án Excel (dùng cho TNMaker / phần mềm chấm)
    tnmaker_layout: str = "doc"       # 'doc': mỗi dòng một câu, mỗi cột một mã đề; 'ngang': mỗi dòng một mã đề
    ds_style: str = "gop"             # 'gop': 1 ô «ĐSĐS» / câu; 'tach': 4 ô a,b,c,d
    ds_symbols: str = "ĐS"            # 'ĐS' | 'TF' | '10'
    kq_decimal: str = ","             # dấu thập phân phần trả lời ngắn
    show_id: bool = False             # in ID nhỏ sau mỗi câu trong file lời giải (bản cho giáo viên)
    make_zip: bool = False            # nén cả thư mục kết quả thành .zip
    header: dict | None = None        # thông tin đầu đề: SO_GD, KY_THI, MON_THI, GIAO_VIEN, NAM_HOC
    online_html: bool = False         # mỗi mã đề một file HTML làm bài online (chấm điểm ngay)
    online_solution: bool = True      # bài online: hiện lời giải sau khi nộp
    moodle: bool = False              # file Moodle XML (bộ câu của đề)
    word: bool = False                # file Word .docx mỗi mã đề (cần pandoc)


def plain_answer(a: str) -> str:
    """Bỏ kí hiệu LaTeX khỏi đáp án trả lời ngắn: '$0{,}92$' → '0,92', '$-4$' → '-4'."""
    a = a.replace("{,}", ",").replace("\\dfrac", "").replace("\\frac", "")
    return a.replace("$", "").replace("{", "").replace("}", "").strip()


def load_template(path: str | None = None) -> str:
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read()
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", DEFAULT_TEMPLATE)
    with open(default, encoding="utf-8") as f:
        return f.read()


def questions_to_tex(qs: list[Question], with_solution: bool = True, show_id: bool = False) -> str:
    out = []
    for q in qs:
        t = q.to_latex(with_solution)
        if show_id and q.id_code:
            t = t.replace("\\end{" + q.env + "}", "\\hfill{\\scriptsize[" + q.id_code + "]}\n\\end{" + q.env + "}", 1)
        out.append(t)
    return "\n".join(out) + "\n"


def section_heading(s: str, n: int, opt: "ExportOptions | None") -> str:
    if opt and opt.official_titles:
        head, lead = OFFICIAL_TITLE[s]
        lead = lead.format(n=n)
        return f"\\noindent\\textbf{{{head}}} {lead}\\par\\smallskip"
    return f"\\section*{{{SECTION_TITLE[s]}}}"


def version_body(v: ExamVersion, with_solution: bool, opt: "ExportOptions | None" = None) -> str:
    parts = []
    for s in SECTION_ORDER:
        qs = v.sections.get(s) or []
        if not qs:
            continue
        parts.append(section_heading(s, len(qs), opt))
        if opt and opt.renumber:
            parts.append("\\setcounter{ex}{0}")
        parts.append(questions_to_tex(qs, with_solution, bool(opt and opt.show_id and with_solution)))
    return "\n".join(parts)


def scoring_tex(v: ExamVersion) -> str:
    n = {s: len(v.sections.get(s) or []) for s in SECTION_ORDER}
    rows = []
    if n["TN"]:
        rows.append(f"Phần I: mỗi câu đúng {SCORING['TN']:g} điểm ({n['TN']} câu, tối đa {n['TN'] * SCORING['TN']:g} điểm).")
    if n["DS"]:
        d = SCORING["DS"]
        rows.append(f"Phần II: mỗi câu đúng 1 ý được {d[1]:g}; 2 ý được {d[2]:g}; 3 ý được {d[3]:g}; "
                    f"cả 4 ý được {d[4]:g} điểm ({n['DS']} câu, tối đa {n['DS'] * d[4]:g} điểm).")
    if n["KQ"]:
        rows.append(f"Phần III: mỗi câu đúng {SCORING['KQ']:g} điểm ({n['KQ']} câu, tối đa {n['KQ'] * SCORING['KQ']:g} điểm).")
    total = n["TN"] * SCORING["TN"] + n["DS"] * SCORING["DS"][4] + n["KQ"] * SCORING["KQ"]
    rows.append(f"Tổng điểm phần trắc nghiệm: {total:g} điểm.")
    return "\\section*{Thang điểm}\n" + "\\\\\n".join(rows) + "\n"


def score_ds(n_correct: int) -> float:
    return SCORING["DS"].get(n_correct, 0.0)


def fill(template: str, **kw) -> str:
    import re as _re
    for k, val in kw.items():
        template = template.replace(f"<<{k}>>", str(val))
    return _re.sub(r"<<[A-Z_]+>>", "", template)       # chỗ trống không có thông tin ⇒ để trống


def answer_table_tex(v: ExamVersion) -> str:
    rows = []
    for s in SECTION_ORDER:
        key = [(i, q.answer_text) for i, q in enumerate(v.sections.get(s) or [], 1)]
        if not key or s == "TL":
            continue
        rows.append(f"\\noindent\\textbf{{{SECTION_TITLE[s]}}}\\\\")
        rows.append("\\begin{tabular}{|" + "c|" * len(key) + "}\\hline")
        rows.append(" & ".join(str(i) for i, _ in key) + "\\\\\\hline")
        rows.append(" & ".join(a for _, a in key) + "\\\\\\hline")
        rows.append("\\end{tabular}\\par\\medskip")
    return "\n".join(rows)


def export_versions(versions: list[ExamVersion], out_dir: str, *, template_path: str | None = None,
                    ten_de: str = "ĐỀ KIỂM TRA", truong: str = "", thoi_gian: int = 90,
                    options: ExportOptions | None = None) -> list[str]:
    opt = options or ExportOptions()
    os.makedirs(out_dir, exist_ok=True)
    tpl = load_template(template_path)
    files = []
    for v in versions:
        common = dict(TEN_DE=ten_de, TRUONG=truong, THOI_GIAN=thoi_gian, MA_DE=v.code, **(opt.header or {}))
        for mode, prefix, sol in (("dethi", "de", False), ("loigiai", "loigiai", True)):
            body = version_body(v, sol, opt)
            if sol:
                body += "\n\\section*{Bảng đáp án}\n" + answer_table_tex(v)
                if opt.scoring:
                    body += "\n" + scoring_tex(v)
            path = os.path.join(out_dir, f"{prefix}_{v.code}.tex")
            with open(path, "w", encoding="utf-8") as f:
                f.write(fill(tpl, MODE=mode, NOI_DUNG=body, **common))
            files.append(path)
    csv_path = os.path.join(out_dir, "dap_an.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Mã đề", "Phần", "Câu", "Đáp án", "ID gốc"])
        for v in versions:
            for s in SECTION_ORDER:
                for i, q in enumerate(v.sections.get(s) or [], 1):
                    w.writerow([v.code, s, i, plain_answer(q.answer_text), q.id_code])
    files.append(csv_path)
    # bảng đáp án dạng ngang (mỗi mã đề một dòng) – tiện dán vào phần mềm chấm thi/Excel
    wide_path = os.path.join(out_dir, "dap_an_bang.csv")
    with open(wide_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        cols = [(s, i) for s in SECTION_ORDER if s != "TL"
                for i in range(1, max((len(v.sections.get(s) or []) for v in versions), default=0) + 1)]
        w.writerow(["Mã đề"] + [f"{s}{i}" for s, i in cols])
        for v in versions:
            row = [v.code]
            for s, i in cols:
                qs = v.sections.get(s) or []
                row.append(plain_answer(qs[i - 1].answer_text) if i <= len(qs) else "")
            w.writerow(row)
    files.append(wide_path)
    if opt.answers_xlsx:
        from .tnmaker import write_answer_xlsx
        try:
            files.append(write_answer_xlsx(versions, os.path.join(out_dir, "dap_an_TNMaker.xlsx"), opt))
        except ImportError:
            pass        # thiếu openpyxl: vẫn có 2 file CSV
    if opt.online_html:
        from .online import export_html
        files += export_html(versions, out_dir, ten_de=ten_de, thoi_gian=int(thoi_gian),
                             show_solution=opt.online_solution)
    if opt.moodle and versions:
        from .online import export_moodle
        files.append(export_moodle(list(versions[0].all_questions()), os.path.join(out_dir, "moodle.xml"),
                                   category=ten_de))
    if opt.word:
        from .wordconv import export_docx, PandocMissing
        for v in versions:
            try:
                files.append(export_docx(v, os.path.join(out_dir, f"de_{v.code}.docx"), ten_de=ten_de,
                                         thoi_gian=thoi_gian, header=opt.header or {}, truong=truong))
            except PandocMissing:
                break
    if opt.make_zip:
        from .tools import zip_dir
        files.append(zip_dir(out_dir))
    return files


def matrix_spec(bank, rules, path: str) -> str:
    """In ma trận đặc tả: mỗi dòng ma trận kèm tên chương/bài/dạng, mức độ, số câu, số câu kho có.

    Đuôi .xlsx ⇒ Excel; còn lại ⇒ bảng LaTeX.
    """
    from .idmap import split_key
    names = bank.idmap()
    level = {"N": "Nhận biết", "H": "Thông hiểu", "V": "Vận dụng", "C": "Vận dụng cao", None: "Mọi mức"}
    part = {"TN": "I. Trắc nghiệm", "DS": "II. Đúng/Sai", "KQ": "III. Trả lời ngắn", "TL": "IV. Tự luận"}
    rows = []
    for r in rules:
        pat = r.id.upper()
        base = pat.split("*")[0].split("?")[0].split("[")[0]
        key = base[:3] + (base[4:] if len(base) > 4 else "")
        label = " › ".join(names[k] for k in ("".join(split_key(key)[:n]) for n in (3, 4))
                           if k in names) if len(base) >= 3 else ""
        if "-" in key and key in names:
            label += " › " + names[key]
        have = len(bank.search(qtype=r.qtype, id_like=r.id, muc_do=r.muc_do, text=r.text))
        rows.append([part[r.qtype], r.id, label or "—", level.get(r.muc_do, r.muc_do), r.count, have])
    total = sum(x[4] for x in rows)
    if path.lower().endswith(".xlsx"):
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = "Ma trận đặc tả"
        ws.append(["Phần", "Mẫu ID", "Nội dung (chương › bài › dạng)", "Mức độ", "Số câu", "Kho có"])
        for c in ws[1]:
            c.font = Font(bold=True)
        for x in rows:
            ws.append(x)
        ws.append(["Tổng", "", "", "", total, ""])
        for col, wd in zip("ABCDEF", (18, 14, 70, 14, 8, 8)):
            ws.column_dimensions[col].width = wd
        wb.save(path)
    else:
        body = "\n".join(" & ".join(str(c).replace("&", "\\&").replace("_", "\\_") for c in x) + "\\\\ \\hline"
                         for x in rows)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\\begin{center}\\textbf{MA TRẬN ĐẶC TẢ}\\end{center}\n"
                    "\\begin{tabular}{|l|l|p{7cm}|l|c|c|}\\hline\n"
                    "Phần & Mẫu ID & Nội dung & Mức độ & Số câu & Kho có\\\\ \\hline\n" + body +
                    f"\n\\multicolumn{{4}}{{|r|}}{{Tổng}} & {total} & \\\\ \\hline\n\\end{{tabular}}\n")
    return path


def export_questions(qs: list[Question], path: str, with_solution: bool = True):
    """Xuất các câu đã chọn ra 1 file .tex (giữ nguyên định dạng ex)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(questions_to_tex(qs, with_solution))
