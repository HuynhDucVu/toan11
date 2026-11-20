"""Công cụ file, Word, online/Moodle, sinh câu, vẽ hình."""
import pytest

from nganhangde.exporter import export_versions
from nganhangde.generator import Rule, make_versions
from nganhangde.parser import parse_file, parse_tex
from conftest import SAMPLE


def test_tools(tmp_path):
    from nganhangde import tools
    groups = tools.find_duplicates([SAMPLE, SAMPLE])
    assert len(groups) == 22
    out = tmp_path / "loc.tex"
    assert tools.filter_by_id([SAMPLE], "0H9*", str(out)) == 9
    assert len(parse_file(str(out))) == 9
    out2 = tmp_path / "khong_lg.tex"
    assert tools.erase_solutions(SAMPLE, str(out2)) == 22
    qs = parse_file(str(out2))
    assert len(qs) == 22 and all(not q.solution for q in qs)
    assert qs[0].answer_text == "D"
    out3 = tmp_path / "doi_id.tex"
    assert tools.convert_ids(SAMPLE, str(out3), tools.parse_mapping("0H9 = 0H4\n0D2->0D5")) == 11
    ids = [q.id_code for q in parse_file(str(out3))]
    assert "0H4H3-3" in ids and "0D5N1-2" in ids and not any(i.startswith("0H9") for i in ids)


def test_file_tools(tmp_path):
    from nganhangde import tools
    ans = tools.get_answers([SAMPLE])
    assert ans[0][1:] == ("TN", 1, "0D2N1-2", "D") and ans[12][1:3] == ("DS", 1)
    out = tmp_path / "nguon.tex"
    assert tools.add_tag(SAMPLE, str(out), "THPT ABC") == 22
    assert all("THPT ABC" in q.tags for q in parse_file(str(out)))
    assert tools.add_tag(str(out), str(tmp_path / "x.tex"), "THPT ABC") == 0
    assert tools.sort_by_id([SAMPLE], str(tmp_path / "sx.tex")) == 22
    vs, files = tools.shuffle_file(SAMPLE, ["001", "002"], str(tmp_path / "tron"), seed=5)
    assert [v.code for v in vs] == ["001", "002"] and len(list(vs[0].all_questions())) == 22


WORD_MD = """**Câu 1:** Tập nghiệm của phương trình $x^2-1=0$ là

A. $\\{1\\}$ B. $\\{-1\\}$ [C.]{.underline} $\\{-1;1\\}$ D. $\\varnothing$

Lời giải: Ta có $x^2=1$ nên $x=\\pm1$. Chọn C.

**Câu 2.** Cho hàm số $y=x^2$. Xét tính đúng sai:

[a)]{.underline} Hàm số đồng biến trên $(0;+\\infty)$.

b) Đồ thị đi qua điểm $(1;2)$.

[c)]{.underline} Hàm số có giá trị nhỏ nhất bằng $0$.

d) Hàm số là hàm số lẻ.

Câu 3: Tính $\\dfrac{1}{2}+0{,}25$.

Đáp án: 0,75

Lời giải: $0{,}5+0{,}25=0{,}75$.
"""


def test_word_import(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("pandoc"):
        pytest.skip("chưa cài pandoc")
    from nganhangde.wordconv import import_docx
    md = tmp_path / "de.md"
    md.write_text(WORD_MD, encoding="utf-8")
    docx = tmp_path / "de.docx"
    subprocess.run(["pandoc", str(md), "-o", str(docx)], check=True)
    qs = parse_tex(import_docx(str(docx), tag="Word"))
    assert [q.qtype for q in qs] == ["TN", "DS", "KQ"]
    assert qs[0].answer_text == "C" and "Chọn C" in qs[0].solution
    assert qs[1].answer_text == "ĐSĐS"
    assert qs[2].short_answer == "0{,}75" and qs[2].solution
    assert all("Word" in q.tags for q in qs)


def test_online_moodle_export(bank, tmp_path):
    import xml.dom.minidom
    from nganhangde.exporter import ExportOptions
    from nganhangde.htmlconv import latex_to_html
    vs = make_versions(bank, [Rule("TN", 12), Rule("DS", 4), Rule("KQ", 6)], codes=["101"], seed=1)
    files = export_versions(vs, str(tmp_path / "o"), options=ExportOptions(online_html=True, moodle=True))
    html_file = [f for f in files if f.endswith("online_101.html")][0]
    h = open(html_file, encoding="utf-8").read()
    assert h.count("class='card q'") == 22 and "atob(DATA)" in h and "\\begin{ex}" not in h
    xml_file = [f for f in files if f.endswith("moodle.xml")][0]
    doc = xml.dom.minidom.parse(xml_file)
    types = [q.getAttribute("type") for q in doc.getElementsByTagName("question")]
    assert types.count("multichoice") == 12 and types.count("cloze") == 4 and types.count("shortanswer") == 6
    assert "{1:MULTICHOICE:" in open(xml_file, encoding="utf-8").read()
    t = latex_to_html(r"\textbf{Công đoạn $1$:} chọn \begin{itemize}\item a \begin{itemize}\item b\end{itemize}\item c\end{itemize}"
                      r"\begin{tikzpicture}\draw(0,0);\end{tikzpicture} x<y")
    assert "<b>Công đoạn $1$:</b>" in t and t.count("<li>") == 3 and "[Hình vẽ" in t and "x&lt;y" in t


def test_mathgen():
    from nganhangde import mathgen as mg
    assert mg.frac(6, 4) == "\\dfrac{3}{2}" and mg.frac(8, 4) == "2" and mg.frac(-1, 3) == "-\\dfrac{1}{3}"
    assert mg.dec(0.25) == "0{,}25" and mg.dec(2.0) == "2" and mg.sgn(-3) == "- 3" and mg.sq(12) == "2\\sqrt{3}"
    qs, warns = mg.generate(mg.SAMPLE, 6, seed=3)
    assert len(qs) == 6 and not warns and len({q.fingerprint for q in qs}) == 6
    assert mg.term(1, "x") == "+ x" and mg.term(-3, "x") == "- 3x" and mg.term(0, "x") == "" and mg.term(-5) == "- 5"
    assert not any(_r2.search(r"[+-] 1x", q.stem) for q in qs for _r2 in [__import__("re")])
    from nganhangde.review import review_question
    assert all(not review_question(q) for q in qs)
    import re as _re
    for q in qs:                                         # đáp án (x1;x2) thật sự là nghiệm của tam thức
        x1, x2 = map(int, _re.findall(r"-?\d+", q.choices[0]))
        m = _re.search(r"\$(-?\d*)x\^2 ([+-]) (\d*)x ([+-]) (\d+) < 0\$", q.stem)
        a = int(m.group(1)) if m.group(1) not in ("", "-") else (-1 if m.group(1) == "-" else 1)
        b = int(m.group(3) or 1) * (1 if m.group(2) == "+" else -1)
        c = int(m.group(5)) * (1 if m.group(4) == "+" else -1)
        f = lambda x: a * x * x + b * x + c  # noqa: E731
        assert f(x1) == 0 and f(x2) == 0 and f((x1 + x2) / 2) < 0
    kq, w = mg.generate(mg.SAMPLE_KQ, 4, seed=1)
    assert len(kq) == 4 and all(q.qtype == "KQ" for q in kq) and not w
    out, w = mg.generate_file(mg.SAMPLE + "\n" + mg.SAMPLE_KQ, 3, seed=2)
    assert len(out) == 6
    with pytest.raises(mg.TemplateError):
        mg.generate("\\begin{ex}\n%@ a = 1..3\n%@ dk: a > 5\nx @{a}\n\\shortans{1}\n\\end{ex}", 1)
    with pytest.raises(mg.TemplateError):
        mg.generate("\\begin{ex}\n%@ a = __import__('os')\nx\n\\end{ex}", 1)


def test_drawgen():
    from nganhangde import drawgen as dg
    t = dg.variation_table("x^3-3x+1")
    assert t["xs"] == ["-\\infty", "-1", "1", "+\\infty"]
    assert t["sign"] == ["", "+", "0", "-", "0", "+", ""]
    assert t["var"] == ["-/$-\\infty$", "+/$3$", "-/$-1$", "+/$+\\infty$"]
    t = dg.variation_table("(x-2)/(x+3)")
    assert t["xs"] == ["-\\infty", "-3", "+\\infty"] and "d" in t["sign"]
    assert t["var"] == ["-/$1$", "+D-/$+\\infty$/$-\\infty$", "+/$1$"]
    t = dg.variation_table("x+1/x")
    assert t["xs"] == ["-\\infty", "-1", "0", "1", "+\\infty"] and t["var"][1] == "+/$-2$" and t["var"][3] == "-/$2$"
    code = dg.variation_from_expr("x^4-2x^2")
    assert "\\tkzTabInit" in code and "\\tkzTabLine{,-,0,+,0,-,0,+,}" in code
    g = dg.graph_tikz("1/x", -4, 4, -4, 4)
    assert g.count("plot coordinates") == 2                     # 2 nhánh hypebol, tách ở x = 0
    assert dg.nice(0.5) == "\\dfrac{1}{2}" and dg.nice(-2 * 3 ** 0.5) == "-2\\sqrt{3}"
    labels, values = dg.parse_data("Giỏi: 12\nKhá: 20\nTrung bình, 8")
    assert labels == ["Giỏi", "Khá", "Trung bình"] and values == [12, 20, 8]
    assert dg.bar_tikz(labels, values).count("rectangle") == 3
    assert dg.pie_tikz(labels, values).count("arc") == 3 and "30\\%" in dg.pie_tikz(labels, values)
    with pytest.raises(dg.FuncError):
        dg.make_func("__import__('os')")
