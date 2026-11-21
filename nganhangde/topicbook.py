"""Xuất «quyển chuyên đề»: gom câu hỏi theo chương – bài – dạng (tên lấy từ Map ID), có trang bìa, mục lục,
đề bài + lời giải ngay dưới từng câu (hoặc chỉ đề, để lời giải riêng)."""
from __future__ import annotations

from collections import OrderedDict

from .idcode import parse_id


def _key_title(q, names: dict) -> tuple[str, str, str]:
    """(khoá sắp xếp, tên chương, tên dạng)."""
    idc = parse_id(q.id_code) if q.id_code else None
    if not idc:
        return ("~", "Chưa phân loại", "Các câu chưa có ID")
    kc = idc.lop + idc.mon + idc.chuong
    kb = kc + idc.bai
    chuong = names.get(kc) or f"Chương {idc.chuong}"
    bai = names.get(kb)
    dang = names.get(f"{kb}-{idc.dang}") if idc.dang else None
    title = " – ".join(x for x in (f"Bài {idc.bai}. {bai}" if bai else f"Bài {idc.bai}", dang or (f"Dạng {idc.dang}" if idc.dang else "")) if x)
    return (f"{kc}{idc.bai}{idc.dang or ''}", chuong, title)


def topic_book_tex(questions, names: dict | None = None, *, title="CHUYÊN ĐỀ TOÁN THPT", author="Tổ Toán",
                   school="TRƯỜNG THPT", toc=True, solutions=True) -> str:
    names = names or {}
    groups: "OrderedDict[tuple[str, str], OrderedDict[str, list]]" = OrderedDict()
    for q in sorted(questions, key=lambda x: (_key_title(x, names)[0], x.qtype)):
        k, ch, dang = _key_title(q, names)
        groups.setdefault((k[:3], ch), OrderedDict()).setdefault(dang, []).append(q)
    L = [r"\documentclass[12pt,a4paper]{article}", r"\usepackage[utf8]{vietnam}", r"\usepackage{amsmath,amssymb,tikz,tkz-tab}",
         r"\usetikzlibrary{calc,patterns}", r"\usepackage[top=2cm,bottom=2cm,left=2cm,right=1.8cm]{geometry}",
         f"\\usepackage[{'loigiai' if solutions else 'dethi'}]{{ex_test}}",
         r"\providecommand{\heva}[1]{\left\{\begin{aligned}#1\end{aligned}\right.}",
         r"\providecommand{\hoac}[1]{\left[\begin{aligned}#1\end{aligned}\right.}",
         r"\begin{document}", r"\begin{titlepage}\centering", f"\\textbf{{\\Large {school}}}\\\\[1.5cm]",
         r"\rule{\linewidth}{0.6mm}\\[0.5cm]", f"{{\\Huge\\bfseries {title}}}\\\\[0.4cm]", r"\rule{\linewidth}{0.6mm}\\[1.5cm]",
         f"\\textbf{{\\large Biên soạn: {author}}}\\\\[0.5cm]",
         f"\\textit{{{len(questions)} câu hỏi, {sum(len(d) for d in groups.values())} dạng toán}}", r"\vfill\today",
         r"\end{titlepage}"]
    if toc:
        L += [r"\tableofcontents", r"\newpage"]
    for (_k, ch), dangs in groups.items():
        L.append(f"\\section{{{ch}}}")
        for dang, qs in dangs.items():
            L.append(f"\\subsection{{{dang}}}")
            for q in qs:
                L.append(q.to_latex(solutions))
    L.append(r"\end{document}")
    return "\n".join(L) + "\n"


def export_topic_book(questions, names, path: str, **kw) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(topic_book_tex(questions, names, **kw))
    return path
