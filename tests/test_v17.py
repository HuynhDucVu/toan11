"""Bản 0.17: header kiểu MyLT, câu đổi số tự động, Tiện ích 2, mỗi đề một thư mục."""
import random
import shutil

import pytest

from nganhangde.generator import MixOptions, mix_versions, sections_from_questions
from nganhangde.parser import parse_file, parse_tex

from conftest import SAMPLE

HEADER = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{vietnam}
\usepackage{amsmath,amssymb,tikz,tkz-tab,fancyhdr}
\usepackage[book]{ex_test}
\newcommand{\tentruong}{Trường THPT A}
\newcommand{\tenkythi}{Kiểm tra định kỳ}
\newcommand{\thoigian}{45}
\newcommand{\tieude}[3]{\noindent\tentruong\ -- \tenkythi\ (#1 trang, #2 câu) \fbox{Mã đề #3}\par}
\newcommand{\chantrang}[2]{\pagestyle{fancy}\fancyhf{}\rfoot{Trang \thepage/#1 -- Mã đề #2}}
\newcommand{\tieudea}[2]{\noindent\textbf{PHẦN #1.} Thí sinh trả lời từ câu 1 đến câu #2.}
\newcommand{\hetde}{\centerline{HẾT}}
\begin{document}
"""


def _v():
    return mix_versions(sections_from_questions(parse_file(SAMPLE)), ["101"], random.Random(1), MixOptions())


def test_mylt_header(tmp_path):
    from nganhangde.exporter import ExportOptions, export_versions, is_header
    assert is_header(HEADER)
    h = tmp_path / "Header.tex"
    h.write_text(HEADER, encoding="utf-8")
    files = export_versions(_v(), str(tmp_path / "o"), template_path=str(h), truong="THPT Phạm Văn Đồng",
                            options=ExportOptions(header={"KY_THI": "Giữa kì I"}, answers_xlsx=False, per_folder=True))
    de = (tmp_path / "o" / "101" / "de_101.tex").read_text(encoding="utf-8")
    lg = (tmp_path / "o" / "101" / "loigiai_101.tex").read_text(encoding="utf-8")
    assert "\\usepackage[book,dethi]{ex_test}" in de and "\\usepackage[book,loigiai]{ex_test}" in lg
    assert "\\newcommand{\\tentruong}{THPT Phạm Văn Đồng}" in de and "{Giữa kì I}" in de
    assert "\\tieude{\\pageref{LastPage}}{22}{101}" in de and "\\tieudea{I}{12}" in de and "\\hetde" in de
    assert "Bảng đáp án" in lg and any(f.replace("\\", "/").endswith("101/de_101.tex") for f in files)
    if shutil.which("pdflatex"):
        from nganhangde.pdfbuild import compile_tex
        assert compile_tex(str(tmp_path / "o" / "101" / "de_101.tex")).ok


def test_autogen_all_types():
    from nganhangde import autogen
    from nganhangde.review import LOI, review_question
    for k in autogen.PROBLEMS:
        blocks = autogen.generate(k, 6, seed=3)
        assert len(blocks) == 6, k
        for b in blocks:
            q = parse_tex(b)[0]
            assert q.qtype == "TN" and len(set(q.choices)) == 4 and sum(q.correct) == 1, k
            assert q.id_code.startswith("2D1") and not [i for i in review_question(q) if i.level == LOI], (k, b)


def test_autogen_math_is_right():
    from nganhangde import autogen
    rng = random.Random(5)
    for _ in range(30):
        a, x1, x2, co, f = autogen._cubic(rng)
        h = 1e-5
        for x in (x1, x2):                                    # f'(x1) = f'(x2) = 0
            assert abs((f(x + h) - f(x - h)) / (2 * h)) < 1e-4
        assert ((f(x1 + 0.5) - f(x1)) < 0) == (a > 0)        # a > 0: giảm ngay sau x1


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="cần pdflatex")
def test_autogen_compiles(tmp_path, monkeypatch):
    from nganhangde import autogen
    from nganhangde.exporter import fill, load_template
    monkeypatch.setenv("NHD_USE_APP_TEMPLATE", "0")
    body = "\n".join(b for k in autogen.PROBLEMS for b in autogen.generate(k, 1, seed=11))
    t = tmp_path / "t.tex"
    t.write_text(fill(load_template(None), MODE="loigiai", NOI_DUNG=body, TEN_DE="T", MA_DE="1"), encoding="utf-8")
    from nganhangde.pdfbuild import compile_tex
    r = compile_tex(str(t))
    assert r.ok, r.errors


def test_tools2(tmp_path, bank):
    from nganhangde import tools2
    text = open(SAMPLE, encoding="utf-8").read()
    a, n = tools2.answers_to_A(text)
    qs = parse_tex(a)
    assert n > 0 and {q.answer_text for q in qs if q.qtype == "TN"} == {"A"}
    b, n, w = tools2.set_answers(text, "ABCD" * 3)
    assert [q.answer_text for q in parse_tex(b) if q.qtype == "TN"] == list("ABCD" * 3) and not w
    assert tools2.convert_levels("%[0D1Y2-1] %[0D1T3]") == ("%[0D1N2-1] %[0D1C3]", 2)
    assert tools2.clean_code("\\begin{ex}\n\nx\n\\end{ex}\n\n\n\ny")[1] == 3
    fs = tools2.split_by_id([SAMPLE], str(tmp_path / "s"), "chuong")
    assert len(fs) == 4 and tools2.join_files(fs, str(tmp_path / "j.tex")) == 22
    assert tools2.input_code([str(tmp_path / "s" / "0D8.tex")], str(tmp_path)) == "\\input{s/0D8}\n"
    assert len(tools2.export_bank_by_id(bank, str(tmp_path / "b"), "chuong")) == 4


def test_import_mylt_rows(bank):
    from nganhangde.mylt_import import import_rows
    n0 = bank.count()
    rows = [
        {"id": 1, "NoiDung": "\\begin{ex}%[0D1N1-1]\nCâu A mới hoàn toàn $x=1$\n\\choice\n{\\True a}\n{b}\n{c}\n{d}\n"
                             "\\loigiai{Chọn A.}\n%<MyLT>\n\\end{ex}", "IDCauHoi": "0D1N1-1", "TuLuan": 0, "SoLan": 3},
        {"id": 2, "NoiDung": "Chứng minh bất đẳng thức mới $a^2\\ge0$.\n\\loigiai{Hiển nhiên.}", "IDCauHoi": "0D1V1-2",
         "TuLuan": 1, "SoLan": 0},
        {"id": 3, "NoiDung": "", "IDCauHoi": "", "TuLuan": 0, "SoLan": 0},
    ]
    r = import_rows(bank, rows)
    assert (r["them"], r["trung"], len(r["loi"])) == (2, 0, 1) and bank.count() == n0 + 2
    q = bank.search(text="Câu A mới")[0]
    assert q.id_code == "0D1N1-1" and "%<MyLT>" not in q.raw
    assert bank.con.execute("SELECT used_count FROM questions WHERE id=?", (q.db_id,)).fetchone()[0] == 3
    tl = bank.search(text="Chứng minh bất đẳng thức mới")[0]
    assert tl.qtype == "TL" and tl.id_code == "0D1V1-2"
    assert import_rows(bank, rows[:1])["trung"] == 1
