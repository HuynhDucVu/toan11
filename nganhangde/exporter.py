"""Xuất đề thi, lời giải, bảng đáp án."""
from __future__ import annotations

import csv
import os

from .generator import SECTION_ORDER, SECTION_TITLE, ExamVersion
from .parser import Question

DEFAULT_TEMPLATE = "de_thi.tex"


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


def questions_to_tex(qs: list[Question], with_solution: bool = True) -> str:
    return "\n".join(q.to_latex(with_solution) for q in qs) + "\n"


def version_body(v: ExamVersion, with_solution: bool) -> str:
    parts = []
    for s in SECTION_ORDER:
        qs = v.sections.get(s) or []
        if not qs:
            continue
        parts.append(f"\\section*{{{SECTION_TITLE[s]}}}")
        parts.append(questions_to_tex(qs, with_solution))
    return "\n".join(parts)


def fill(template: str, **kw) -> str:
    for k, val in kw.items():
        template = template.replace(f"<<{k}>>", str(val))
    return template


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
                    ten_de: str = "ĐỀ KIỂM TRA", truong: str = "", thoi_gian: int = 90) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    tpl = load_template(template_path)
    files = []
    for v in versions:
        common = dict(TEN_DE=ten_de, TRUONG=truong, THOI_GIAN=thoi_gian, MA_DE=v.code)
        for mode, prefix, sol in (("dethi", "de", False), ("loigiai", "loigiai", True)):
            body = version_body(v, sol)
            if sol:
                body += "\n\\section*{Bảng đáp án}\n" + answer_table_tex(v)
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
    return files


def export_questions(qs: list[Question], path: str, with_solution: bool = True):
    """Xuất các câu đã chọn ra 1 file .tex (giữ nguyên định dạng ex)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(questions_to_tex(qs, with_solution))
