"""Bổ sung theo nhóm chức năng MyLT 2026: trộn đề (vùng, tỉ lệ, đề tương tự), phiếu, xuất thêm, vẽ hình."""
import random
import shutil
import subprocess
from collections import Counter

import pytest

from nganhangde.generator import (ExamVersion, MixOptions, make_codes, mix_versions, sections_from_questions,
                                  similar_exam, _mix_section)
from nganhangde.parser import Question, parse_file, parse_tex

from conftest import SAMPLE


def _tn(i):
    return Question("TN", f"Câu {i}", ["a", "b", "c", "d"], [True, False, False, False])


def test_regions_ratio_codes_and_fix_last():
    text = "\n".join([r"\begin{ex}c1\choice{\True a}{b}{c}{d}\end{ex}"] * 0)
    blocks = []
    for i in range(6):
        if i in (0, 3):
            blocks.append("%VUNG")
        blocks.append(f"\\begin{{ex}}%[0D1N1-1]\nCâu {i}\n\\choice\n{{\\True a}}\n{{b}}\n{{c}}\n{{d}}\n\\end{{ex}}")
    qs = parse_tex(text + "\n".join(blocks))
    assert [q.region for q in qs] == [1, 1, 1, 2, 2, 2]
    for seed in range(30):
        out = _mix_section(qs, random.Random(seed), MixOptions(), False)
        assert {q.stem.strip() for q in out[:3]} == {"Câu 0", "Câu 1", "Câu 2"}
    many = [_tn(i) for i in range(24)]
    out = _mix_section(many, random.Random(1), MixOptions(tn_ratio="2,4,3,3", max_run=0), False)
    c = Counter(q.answer_text for q in out)
    assert (c["A"], c["B"], c["C"], c["D"]) == (4, 8, 6, 6)
    assert make_codes(3, 101, 3, step=5) == ["101", "106", "111"]
    ds = Question("DS", "x", ["p", "q", "r", "s"], [True, False, True, False])
    for seed in range(20):
        v = mix_versions({"DS": [ds]}, ["1"], random.Random(seed), MixOptions(fix_ds_last=True))[0]
        assert v.sections["DS"][0].choices[-1] == "s"


def test_similar_exam(bank):
    sample = bank.search()[:6]
    qs, notes = similar_exam(bank, sample, random.Random(0))
    assert len(qs) == len(sample)
    for a, b in zip(sample, qs):
        assert a.qtype == b.qtype
        if b.db_id != a.db_id:
            assert a.id_code.split("-")[0][:3] == b.id_code[:3]
    assert all("Câu" in n for n in notes)


def test_exports_extra(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from nganhangde import exportx
    qs = parse_file(SAMPLE)
    text, skip = exportx.aiken(qs)
    assert text.count("ANSWER:") == 12 and skip == len(qs) - 12
    p, _ = exportx.quizizz_xlsx(qs, str(tmp_path / "q.xlsx"))
    ws = openpyxl.load_workbook(p).active
    assert ws.cell(1, 1).value == "Question Text" and ws.max_row == 1 + 12 + 16 + 6
    assert "1. " in exportx.msforms_markdown(qs[:2])
    v = ExamVersion("101")
    v.sections = sections_from_questions(qs)
    b = exportx.blogger_html(v)
    assert "<html" not in b and "function submit" in b
    ex = exportx.plain_to_ex("Câu 1. Tính $1+1$.\nA. $1$\nB. $2$\nC. $3$\nD. $4$\nĐáp án: B\n")
    q = parse_tex(ex)[0]
    assert q.qtype == "TN" and q.answer_text == "B"


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="cần pdflatex")
def test_tikz_png_and_sheet(tmp_path):
    pytest.importorskip("pypdfium2")
    from nganhangde import exportx, geom
    from nganhangde.omr import sheet_document
    out, res = exportx.tikz_to_png([geom.build(geom.TEMPLATES["Tam giác vuông tại A"]).tikz()], str(tmp_path), dpi=60)
    assert res.ok and len(out) == 1 and open(out[0], "rb").read(8) == b"\x89PNG\r\n\x1a\n"
    v = mix_versions(sections_from_questions(parse_file(SAMPLE)), ["0101"], random.Random(1), MixOptions())
    tex = tmp_path / "s.tex"
    tex.write_text(sheet_document(v), encoding="utf-8")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "s.tex"], cwd=tmp_path,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-800:]


def test_export_options_extra(tmp_path):
    from nganhangde.exporter import ExportOptions, export_versions
    v = mix_versions(sections_from_questions(parse_file(SAMPLE)), ["101"], random.Random(1), MixOptions())
    files = export_versions(v, str(tmp_path), options=ExportOptions(answers_end=True, even_pages=True,
                                                                     answer_sheet=True, answers_xlsx=False))
    de = (tmp_path / "de_101.tex").read_text(encoding="utf-8")
    assert "Đáp án" in de and "\\ifodd\\value{page}" in de
    assert any(f.endswith("phieu_dap_an_to_san.tex") for f in files)


def test_drawmore_and_geom():
    from nganhangde import drawmore as dm, geom
    xs, line = dm.sign_table("(x-1)(x+2)/(x-3)")
    assert xs == ["-\\infty", "-2", "1", "3", "+\\infty"] and line == ["", "-", "0", "+", "0", "-", "d", "+", ""]
    assert [dm.angle_latex(t) for t in dm.trig_points(["pi/3+kpi"])] == ["\\dfrac{\\pi}{3}", "\\dfrac{4\\pi}{3}"]
    with pytest.raises(dm.FuncError):
        dm.trig_points(["1 + k"])
    assert dm.cubic_from_extrema(1, 1, 3, 5) == "-x^3 + 6x^2 - 9x + 5"
    assert dm.quartic_from_extrema(1, 1, 0) == "x^4 - 2x^2 + 1"
    sc = geom.build(geom.TEMPLATES["Hình vuông ABCD, tâm O"])
    assert tuple(round(c, 6) for c in sc.pts["O"]) == (1.5, 1.5)
    sc = geom.build([geom.S("diem", ten="A", x=0, y=0), geom.S("diem", ten="B", x=4, y=0),
                     geom.S("diem", ten="C", x=0, y=3), geom.S("tam_noi", ten="I", A="A", B="B", C="C")])
    assert tuple(round(c, 6) for c in sc.pts["I"]) == (1.0, 1.0)
    with pytest.raises(geom.FuncError):
        geom.build([geom.S("doan", A="X", B="Y")])
