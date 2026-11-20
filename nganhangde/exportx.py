"""Xuất thêm: Aiken (Moodle/LMS), Quizizz (Excel), Microsoft Forms (Word, nhập nhanh), Blogger (HTML);
hoá ảnh hình TikZ (PNG); chuyển đề LaTeX dạng thường («Câu 1. … A. … B. …») sang ex_test."""
from __future__ import annotations

import os
import re

from .gas import latex_to_text


# ---------------------------------------------------------------- Aiken
def aiken(questions) -> tuple[str, int]:
    """Định dạng Aiken: chỉ câu trắc nghiệm 1 đáp án; công thức đổi sang chữ thường. Trả về (văn bản, số câu bỏ qua)."""
    out, skip = [], 0
    for q in questions:
        if q.qtype != "TN" or sum(q.correct) != 1 or len(q.choices) > 26:
            skip += 1
            continue
        stem = " ".join(latex_to_text(q.stem).split())
        opts = [f"{chr(65 + i)}. {' '.join(latex_to_text(c).split())}" for i, c in enumerate(q.choices)]
        out.append("\n".join([stem, *opts, f"ANSWER: {chr(65 + q.correct.index(True))}"]))
    return "\n\n".join(out) + "\n", skip


# ---------------------------------------------------------------- Quizizz
QUIZIZZ_HEAD = ["Question Text", "Question Type", "Option 1", "Option 2", "Option 3", "Option 4", "Option 5",
                "Correct Answer", "Time in seconds", "Image Link"]


def quizizz_xlsx(questions, path: str, seconds: int = 60) -> tuple[str, int]:
    """Bảng theo mẫu nhập Excel của Quizizz (Multiple Choice, Fill-in-the-Blank, Open-Ended).
    Mẫu của Quizizz có thể đổi theo thời gian – nếu nhập lỗi, so cột với mẫu tải từ Quizizz."""
    from openpyxl import Workbook
    from .exporter import plain_answer
    wb = Workbook()
    ws = wb.active
    ws.title = "Quizizz"
    ws.append(QUIZIZZ_HEAD)
    skip = 0
    for q in questions:
        stem = " ".join(latex_to_text(q.stem).split())
        if q.qtype == "TN" and sum(q.correct) == 1 and len(q.choices) <= 5:
            opts = [" ".join(latex_to_text(c).split()) for c in q.choices] + [""] * (5 - len(q.choices))
            ws.append([stem, "Multiple Choice", *opts, q.correct.index(True) + 1, seconds, ""])
        elif q.qtype == "DS":
            for k, (c, ok) in enumerate(zip(q.choices, q.correct)):
                ws.append([f"{stem} – Ý {'abcd'[k] if k < 4 else k + 1}) {' '.join(latex_to_text(c).split())}",
                           "Multiple Choice", "Đúng", "Sai", "", "", "", 1 if ok else 2, seconds, ""])
        elif q.qtype == "KQ":
            ws.append([stem, "Fill-in-the-Blank", plain_answer(q.answer_text), "", "", "", "", "", seconds, ""])
        elif q.qtype == "TL":
            ws.append([stem, "Open-Ended", "", "", "", "", "", "", seconds * 3, ""])
        else:
            skip += 1
    for col in "ABCDEFGHIJ":
        ws.column_dimensions[col].width = 18
    ws.column_dimensions["A"].width = 60
    wb.save(path)
    return path, skip


# ---------------------------------------------------------------- Microsoft Forms
def msforms_markdown(questions) -> str:
    """Văn bản đánh số «1. … / A. … » – Microsoft Forms → Nhập nhanh (Quick import) nhận diện được."""
    out = []
    for i, q in enumerate(questions, 1):
        out.append(f"{i}. {' '.join(latex_to_text(q.stem).split())}\n")
        if q.qtype == "TN":
            out += [f"{chr(65 + k)}. {' '.join(latex_to_text(c).split())}" for k, c in enumerate(q.choices)]
        elif q.qtype == "DS":
            out += [f"{'abcd'[k] if k < 4 else k + 1}) {' '.join(latex_to_text(c).split())} (Đúng/Sai)"
                    for k, c in enumerate(q.choices)]
        out.append("")
    return "\n\n".join(out)


def msforms_docx(questions, path: str) -> str:
    """Word cho Microsoft Forms (cần pandoc). Đáp án đúng đặt lại trong Forms sau khi nhập."""
    import tempfile
    from .wordconv import _run
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "f.md")
        with open(src, "w", encoding="utf-8") as f:
            f.write(msforms_markdown(questions))
        _run([src, "-f", "markdown", "-o", path])
    return path


# ---------------------------------------------------------------- Blogger
def blogger_html(version, **kw) -> str:
    """Đoạn HTML dán vào bài viết Blogger (chế độ HTML): bài làm online tự chấm của một mã đề."""
    from .online import version_html
    h = version_html(version, **kw)
    h = re.sub(r"<!doctype html>|</?html[^>]*>|</?head>|</?body>|<meta[^>]*>|<title>.*?</title>", "", h, flags=re.S | re.I)
    return "<!-- Bài làm online – dán vào Blogger ở chế độ «Xem HTML» -->\n<div class='nhd-de'>" + h.strip() + "</div>\n"


# ---------------------------------------------------------------- hoá ảnh TikZ
TIKZ_PREAMBLE = ("\\documentclass[tikz,border=3pt]{standalone}\n\\usepackage[utf8]{vietnam}\n"
                 "\\usepackage{amsmath,amssymb,tkz-tab}\n"
                 "\\usetikzlibrary{calc,angles,quotes,intersections,patterns,arrows.meta}\n\\begin{document}\n")


def _write_png(path: str, buf: bytes, w: int, h: int, stride: int, ch: int):
    """Ghi PNG không cần Pillow (buffer RGB/RGBA từ pdfium với rev_byteorder=True)."""
    import struct
    import zlib
    rows = b"".join(b"\x00" + buf[y * stride:y * stride + w * ch] for y in range(h))
    ctype = {3: 2, 4: 6, 1: 0}[ch]

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def tikz_to_png(pictures: list[str], out_dir: str, dpi: int = 200, prefix: str = "hinh", engine: str = ""):
    """Biên dịch các khối tikzpicture (mỗi hình một trang) rồi xuất PNG. Trả về (ds file png, BuildResult)."""
    from .pdfbuild import compile_tex, find_engine
    os.makedirs(out_dir, exist_ok=True)
    tex = os.path.join(out_dir, f"{prefix}_tat_ca.tex")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(TIKZ_PREAMBLE + "\n".join(pictures) + "\n\\end{document}\n")
    res = compile_tex(tex, engine or find_engine(), runs=1)
    if not res.ok:
        return [], res
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return [], res
    pdf = pdfium.PdfDocument(res.pdf)
    out = []
    for i in range(len(pdf)):
        bm = pdf[i].render(scale=dpi / 72, rev_byteorder=True)
        p = os.path.join(out_dir, f"{prefix}_{i + 1:03d}.png")
        _write_png(p, bytes(bm.buffer), bm.width, bm.height, bm.stride, bm.n_channels)
        out.append(p)
    pdf.close()
    return out, res


def tikz_from_files(paths: list[str]) -> list[str]:
    from .tools import TIKZ_RE
    out = []
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f:
            out += TIKZ_RE.findall(f.read())
    return out


# ---------------------------------------------------------------- đề thường → ex_test
def plain_to_ex(text: str, tag: str = "") -> str:
    """Đề LaTeX gõ thường («Câu 1.», «A.», «B.», … đáp án gạch chân hoặc dòng «Đáp án») → khối ex_test."""
    from .wordconv import latex_text_to_ex
    body = text
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.S)
    if m:
        body = m.group(1)
    body = re.sub(r"\\textbf\{(Câu\s*\d+[.:])\}", r"\1", body)
    return "\n\n".join(latex_text_to_ex(body, tag)) + "\n"


# ---------------------------------------------------------------- câu hỏi thành ảnh (Google Forms dạng ảnh)
QIMG_PREAMBLE = ("\\documentclass[border=6pt,multi=qpage]{standalone}\n\\usepackage[utf8]{vietnam}\n"
                 "\\usepackage{amsmath,amssymb,xcolor,tikz,tkz-tab}\n"
                 "\\usetikzlibrary{calc,angles,quotes,intersections,patterns,arrows.meta}\n"
                 "\\newenvironment{qpage}{\\begin{minipage}{16cm}\\setlength{\\parskip}{3pt}}{\\end{minipage}}\n"
                 "\\providecommand{\\heva}[1]{\\left\\{\\begin{aligned}#1\\end{aligned}\\right.}\n"
                 "\\providecommand{\\hoac}[1]{\\left[\\begin{aligned}#1\\end{aligned}\\right.}\n"
                 "\\providecommand{\\True}{}\n\\providecommand{\\immini}[2]{#1\\par #2}\n\\begin{document}\n")


def question_page(q, num: int, show_options: bool = True) -> str:
    body = [f"\\textbf{{Câu {num}.}} {q.stem.strip()}"]
    if show_options and q.qtype in ("TN", "DS"):
        lab = "ABCD" if q.qtype == "TN" else "abcd"
        for k, c in enumerate(q.choices):
            body.append(f"\\par\\noindent\\textbf{{{lab[k] if k < 4 else k + 1}{'.' if q.qtype == 'TN' else ')'}}} "
                        + c.replace("\\True", "").strip())
    return "\\begin{qpage}\n" + "\n".join(body) + "\n\\end{qpage}\n"


def question_pngs(version, out_dir: str, dpi: int = 110, prefix: str = "cau"):
    """Mỗi câu của mã đề thành một ảnh PNG (đề + phương án) – dùng cho Google Forms (Forms không hiện công thức).
    Trả về ([(phần, số câu, đường dẫn png)], BuildResult)."""
    from .generator import SECTION_ORDER
    from .pdfbuild import compile_tex, find_engine
    os.makedirs(out_dir, exist_ok=True)
    order, pages, n = [], [], 0
    for s in SECTION_ORDER:
        for i, q in enumerate(version.sections.get(s) or [], 1):
            n += 1
            order.append((s, i))
            pages.append(question_page(q, i))
    tex = os.path.join(out_dir, f"{prefix}_tat_ca.tex")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(QIMG_PREAMBLE + "\n".join(pages) + "\\end{document}\n")
    res = compile_tex(tex, find_engine(), runs=1)
    if not res.ok:
        return [], res
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(res.pdf)
    out = []
    for k, (s, i) in enumerate(order):
        if k >= len(pdf):
            break
        bm = pdf[k].render(scale=dpi / 72, rev_byteorder=True)
        p = os.path.join(out_dir, f"{prefix}_{k + 1:02d}.png")
        _write_png(p, bytes(bm.buffer), bm.width, bm.height, bm.stride, bm.n_channels)
        out.append((s, i, p))
    pdf.close()
    return out, res
