from collections import OrderedDict
from pathlib import Path
from typing import Sequence
from ..core.idmap_builtin import describe_id6
from ..core.parser import Question


def _group_key(q: Question) -> tuple[str, str]:
    info = q.id_info()
    if not info:
        return ("000-0", "Các bài toán chưa phân loại mã ID")
    prefix = f"{info.lop}{info.mon}{info.chuong}"
    dang_key = f"{prefix}-{info.bai or '0'}-{info.dang or '0'}"
    title = describe_id6(q.primary_id).rsplit(" · Mức:", 1)[0]
    return (dang_key, title)


def export_topic_book_tex(
    questions: Sequence[Question], out_tex: str, book_title: str = "CHUYÊN ĐỀ TOÁN THPT",
    author: str = "Tổ Toán", school: str = "TRƯỜNG THPT",
    include_toc: bool = True, solution_mode: str = "inline",
) -> str:
    groups: OrderedDict[tuple[str, str], list[Question]] = OrderedDict()
    for q in sorted(questions, key=lambda x: (x.primary_id or "ZZZ", x.qtype)):
        groups.setdefault(_group_key(q), []).append(q)

    ex_opt = "loigiai" if solution_mode == "inline" else "dethi"
    lines = [
        r"\documentclass[12pt,a4paper]{article}",
        r"\usepackage{amsmath,amssymb,fontawesome5}",
        r"\usepackage{tikz,tkz-tab}",
        r"\usetikzlibrary{calc,patterns}",
        r"\usepackage[top=2cm,bottom=2cm,left=2cm,right=1.8cm]{geometry}",
        f"\\usepackage[{ex_opt}]{{ex_test}}",
        r"\begin{document}",
        r"\begin{titlepage}\centering",
        f"  \\textbf{{\\Large {school}}}\\\\[1.5cm]",
        r"  \rule{\linewidth}{0.6mm}\\[0.5cm]",
        f"  {{\\Huge\\bfseries {book_title}}}\\\\[0.4cm]",
        r"  \rule{\linewidth}{0.6mm}\\[1.5cm]",
        f"  \\textbf{{\\large Biên soạn: {author}}}\\\\[0.5cm]",
        f"  \\textit{{Tổng số câu hỏi: {len(questions)} câu — Phân loại thành {len(groups)} dạng toán}}",
        r"  \vfill\today",
        r"\end{titlepage}",
    ]
    if include_toc:
        lines.extend([r"\tableofcontents", r"\newpage"])
    for idx, ((_k, title), qs) in enumerate(groups.items(), 1):
        lines.append(f"\\section{{Dạng {idx}. {title}}}")
        for q in qs:
            lines.append(q.to_latex(include_solution=(solution_mode == "inline")))
            lines.append("")
    lines.append(r"\end{document}")
    Path(out_tex).write_text("\n".join(lines), encoding="utf-8")
    return out_tex
