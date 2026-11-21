"""Chuyển đổi Word ↔ LaTeX (ex_test) bằng pandoc.

* LaTeX → Word (.docx): công thức $...$ thành công thức Word gốc (OMML – sửa được bằng Equation của Word).
* Word → LaTeX: đọc .docx (công thức Word / MathType đã chuyển sang Equation), nhận dạng
  «Câu 1.», phương án «A. … D.», ý «a) … d)», đáp án đánh dấu bằng gạch chân / in đậm chữ cái,
  «Lời giải/Hướng dẫn giải», «Đáp án: …» (trả lời ngắn) ⇒ khối \\begin{ex}…\\end{ex}.

Cần cài pandoc (https://pandoc.org – bản cài Windows .msi). Nhận dạng đáp án là heuristic:
sau khi nhập nên chạy «Rà soát» để tìm câu chưa xác định được đáp án.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from .generator import SECTION_ORDER
from .parser import Question

PREAMBLE = r"""\documentclass{article}
\usepackage{amsmath,amssymb}
\newcommand{\heva}[1]{\left\{\begin{aligned}#1\end{aligned}\right.}
\newcommand{\hoac}[1]{\left[\begin{aligned}#1\end{aligned}\right.}
\begin{document}
"""
PART = {"TN": "PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn", "DS": "PHẦN II. Câu trắc nghiệm đúng sai",
        "KQ": "PHẦN III. Câu trắc nghiệm trả lời ngắn", "TL": "PHẦN IV. Tự luận"}


class PandocMissing(RuntimeError):
    pass


def pandoc_path() -> str:
    p = shutil.which("pandoc")
    if not p:
        for c in (r"C:\Program Files\Pandoc\pandoc.exe",
                  os.path.expandvars(r"%LOCALAPPDATA%\Pandoc\pandoc.exe")):
            if os.path.exists(c):
                return c
        raise PandocMissing("Chưa cài pandoc – tải tại https://pandoc.org/installing.html (bản Windows .msi)")
    return p


def _run(args: list[str]) -> str:
    extra = {"creationflags": 0x08000000} if os.name == "nt" else {}      # chạy ẩn trên Windows
    r = subprocess.run([pandoc_path()] + args, capture_output=True, text=True, encoding="utf-8", **extra)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:500])
    return r.stdout


# ---------------------------------------------------------------- LaTeX → Word
FIG_RE = re.compile(r"\\begin\{(tikzpicture|pspicture)\}.*?\\end\{\1\}", re.S)


def _clean(s: str) -> str:
    s = FIG_RE.sub(r"\\textit{[Hình vẽ]}", s)
    s = re.sub(r"\\begin\{itemchoice\}", r"\\begin{enumerate}", s)
    s = re.sub(r"\\end\{itemchoice\}", r"\\end{enumerate}", s)
    s = re.sub(r"\\itemch(?![A-Za-z])", r"\\item", s)
    s = re.sub(r"\\(immini|hfill|allowdisplaybreaks)(?![A-Za-z])", "", s)
    return s


def question_latex(q: Question, i: int, mark_answers: bool = False, with_solution: bool = False) -> str:
    out = [f"\\textbf{{Câu {i}.}} {_clean(q.stem)}\n"]
    if q.qtype == "TN":
        for k, (c, ok) in enumerate(zip(q.choices, q.correct)):
            lab = "ABCD"[k] if k < 4 else str(k + 1)
            lab = f"\\underline{{\\textbf{{{lab}.}}}}" if (mark_answers and ok) else f"\\textbf{{{lab}.}}"
            out.append(f"{lab} {_clean(c)}\n")
    elif q.qtype == "DS":
        for k, (c, ok) in enumerate(zip(q.choices, q.correct)):
            lab = ("abcd"[k] if k < 4 else str(k + 1)) + ")"
            lab = f"\\underline{{{lab}}}" if (mark_answers and ok) else lab
            out.append(f"{lab} {_clean(c)}\n")
    elif q.qtype == "KQ" and mark_answers:
        out.append(f"Đáp án: {q.short_answer}\n")
    if with_solution and q.solution.strip():
        out.append(f"\\textit{{Lời giải.}} {_clean(q.solution)}\n")
    return "\n".join(out)


def to_latex_doc(sections: dict, title: str = "", subtitle: str = "", mark_answers=False,
                 with_solution=False) -> str:
    body = [PREAMBLE]
    if title:
        body.append(f"\\begin{{center}}\\textbf{{{title}}}\\\\ {subtitle}\\end{{center}}\n")
    for s in SECTION_ORDER:
        qs = sections.get(s) or []
        if not qs:
            continue
        body.append(f"\\textbf{{{PART[s]}}}\n")
        for i, q in enumerate(qs, 1):
            body.append(question_latex(q, i, mark_answers, with_solution))
    body.append("\\end{document}\n")
    return "\n".join(body)


def export_docx(version_or_sections, path: str, *, ten_de="ĐỀ KIỂM TRA", thoi_gian=90, header=None,
                truong="", mark_answers=False, with_solution=False) -> str:
    """Xuất 1 mã đề (ExamVersion) hoặc dict phần → .docx (công thức Word gốc)."""
    sections = getattr(version_or_sections, "sections", version_or_sections)
    code = getattr(version_or_sections, "code", "")
    header = header or {}
    title = " – ".join(x for x in (header.get("KY_THI", ""), ten_de) if x)
    sub = " · ".join(x for x in (truong, f"Môn {header['MON_THI']}" if header.get("MON_THI") else "",
                                  f"Thời gian {thoi_gian} phút", f"Mã đề {code}" if code else "") if x)
    tex = to_latex_doc(sections, title, sub, mark_answers, with_solution)
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "de.tex")
        with open(src, "w", encoding="utf-8") as f:
            f.write(tex)
        _run(["-f", "latex", "-t", "docx", src, "-o", os.path.abspath(path)])
    return path


def export_questions_docx(questions, path: str, mark_answers=True, with_solution=True) -> str:
    secs = {s: [q for q in questions if q.qtype == s] for s in SECTION_ORDER}
    return export_docx(secs, path, ten_de="NGÂN HÀNG CÂU HỎI", mark_answers=mark_answers,
                       with_solution=with_solution)


# ---------------------------------------------------------------- Word → LaTeX
Q_START = re.compile(r"^\s*(?:\\textbf\{)?\s*Câu\s*(\d+)\s*[.:)]?\s*\}?\s*[.:]?\s*", re.I)
OPT_RE = re.compile(r"(?:\\underline\{\s*)?(?:\\textbf\{\s*)?(?:\\underline\{\s*)?([A-D])\s*[.)]\s*\}?\}?\}?")
DS_RE = re.compile(r"^\s*(?:\\underline\{\s*)?(?:\\textbf\{\s*)?([a-d])\s*\)\s*\}?\}?")
SOL_RE = re.compile(r"^\s*(?:\\textbf\{|\\emph\{|\\textit\{)?\s*(Lời giải|Hướng dẫn giải|Giải)\s*[.:]?\s*\}?\s*[.:]?\s*", re.I)
ANS_RE = re.compile(r"^\s*(?:\\textbf\{)?\s*(Đáp án|Trả lời|Đáp số)\s*[.:]?\s*\}?\s*[.:]?\s*(.+)$", re.I)
PART_RE = re.compile(r"PHẦN\s+(I{1,3}|IV)\b", re.I)


def _split_options(line: str, first: int = 0):
    """Tách 1 dòng chứa nhiều phương án «A. … B. … C. … D. …» → [(chữ, đánh_dấu, nội dung)]."""
    out = []
    ms = [m for m in OPT_RE.finditer(line) if m.start() == 0 or line[m.start() - 1] in " \t}~"]
    letters = [m.group(1) for m in ms]
    if not ms or ms[0].start() != 0 or letters != list("ABCD")[first:first + len(letters)]:
        return None
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else len(line)
        label = line[m.start():m.end()]
        marked = "\\underline" in label or "\\uline" in label      # đáp án gạch chân
        out.append((m.group(1), marked, line[m.end():end].strip().rstrip("\\").strip()))
    return out


def _finish(cur, blocks, tag):
    if not cur:
        return
    stem = "\n".join(cur["stem"]).strip()
    sol = "\n".join(cur["sol"]).strip()
    head = "\\begin{ex}" + (f"%[{tag}]" if tag else "")
    body = [head, "\t" + stem]
    if cur["opts"]:
        body.append("\t\\choice")
        for _, marked, txt in cur["opts"]:
            body.append("\t{" + ("\\True " if marked else "") + txt + "}")
    elif cur["ds"]:
        body.append("\t\\choiceTF[t]")
        for _, marked, txt in cur["ds"]:
            body.append("\t{" + ("\\True " if marked else "") + txt + "}")
    elif cur["ans"] is not None:
        body.append("\t\\shortans[oly]{" + cur["ans"] + "}")
    if sol:
        body.append("\t\\loigiai{\n\t\t" + sol + "\n\t}")
    body.append("\\end{ex}")
    blocks.append("\n".join(body))


def latex_text_to_ex(text: str, tag: str = "") -> list[str]:
    """Nhận dạng câu hỏi từ văn bản LaTeX (đầu ra của pandoc) → danh sách khối ex."""
    lines = [ln.rstrip() for ln in text.replace("\r", "").split("\n")]
    blocks, cur, mode = [], None, "stem"
    for ln in lines:
        s = ln.strip()
        if not s or s in ("\\begin{document}", "\\end{document}"):
            continue
        if PART_RE.search(s) and not Q_START.match(s):
            continue
        m = Q_START.match(s)
        if m:
            _finish(cur, blocks, tag)
            cur = {"stem": [s[m.end():]], "opts": [], "ds": [], "ans": None, "sol": []}
            mode = "stem"
            continue
        if cur is None:
            continue
        if SOL_RE.match(s):
            mode = "sol"
            rest = SOL_RE.sub("", s, count=1)
            if rest:
                cur["sol"].append(rest)
            continue
        if mode != "sol":
            opts = _split_options(s, len(cur["opts"]))
            if opts:
                cur["opts"] += opts
                mode = "opts"
                continue
            md = DS_RE.match(s)
            if md:
                label = s[:md.end()]
                cur["ds"].append((md.group(1), "\\underline" in label or "\\uline" in label, s[md.end():].strip()))
                mode = "ds"
                continue
            ma = ANS_RE.match(s)
            if ma and cur["opts"] and re.fullmatch(r"\s*\(?([A-Da-d])\)?\.?\s*", ma.group(2)):
                letter = re.sub(r"[^A-Da-d]", "", ma.group(2)).upper()      # «Đáp án: B» sau các phương án
                cur["opts"] = [(L, L.upper() == letter, t) for L, _mk, t in cur["opts"]]
                continue
            if ma and not cur["opts"] and not cur["ds"]:
                a = ma.group(2).strip()
                a = re.sub(r"\s+", "", a)                       # «- 4» → «-4»
                a = re.sub(r"(\d),(\d)", r"\1{,}\2", a)          # 0,99 → 0{,}99
                cur["ans"] = a
                continue
            if mode == "opts" and cur["opts"]:          # dòng nối tiếp phương án cuối
                L, mk, txt = cur["opts"][-1]
                cur["opts"][-1] = (L, mk, (txt + " " + s).strip())
                continue
            if mode == "ds" and cur["ds"]:
                L, mk, txt = cur["ds"][-1]
                cur["ds"][-1] = (L, mk, (txt + " " + s).strip())
                continue
            cur["stem"].append(s)
        else:
            cur["sol"].append(s)
    _finish(cur, blocks, tag)
    return blocks


ENUM_RE = re.compile(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", re.S)


def _flatten_lists(latex: str) -> str:
    """Danh sách đánh số tự động của Word (a) b) …, A. B. …, 1. 2. …) → dòng chữ «b) …» để nhận dạng."""
    def conv(m):
        body = m.group(1)
        style = re.search(r"\\labelenumi\{\\(alph|Alph|arabic|roman)\{enumi\}([.)])?\}", body)
        kind, sep = (style.group(1), style.group(2) or ".") if style else ("arabic", ".")
        start = re.search(r"\\setcounter\{enumi\}\{(\d+)\}", body)
        n = int(start.group(1)) if start else 0
        body = re.sub(r"\\def\\labelenumi\{.*?\}\n|\\setcounter\{enumi\}\{\d+\}|\\tightlist", "", body)
        out = []
        for item in re.split(r"\\item\b", body)[1:]:
            n += 1
            lab = {"alph": "abcdefghij"[(n - 1) % 10], "Alph": "ABCDEFGHIJ"[(n - 1) % 10]}.get(kind, str(n))
            out.append(f"{lab}{sep} " + " ".join(item.split()))
        return "\n\n".join(out)
    return ENUM_RE.sub(conv, latex)


def import_docx(path: str, tag: str = "", opts=None) -> str:
    """Đọc file Word → nội dung .tex gồm các khối \\begin{ex}…\\end{ex}.
    Có pandoc thì dùng pandoc; máy chưa cài pandoc (hoặc có `opts` – tuỳ chọn riêng) thì đọc bằng Python thuần
    (docxnative: công thức Word, bảng, hình, đáp án gạch chân/tô màu)."""
    if opts is not None:
        from .docxnative import docx_to_ex
        return docx_to_ex(path, opts, tag)[0]
    try:
        pandoc_path()
    except PandocMissing:
        from .docxnative import docx_to_ex
        return docx_to_ex(path, None, tag)[0]
    latex = _run(["-f", "docx", "-t", "latex", "--wrap=none", os.path.abspath(path)])
    latex = latex.replace("\\(", "$").replace("\\)", "$").replace("\\[", "$$").replace("\\]", "$$")
    latex = re.sub(r"\\ul\{", r"\\underline{", latex)
    latex = _flatten_lists(latex)
    return "\n".join(latex_text_to_ex(latex, tag)) + "\n"
