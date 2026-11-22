"""Chuyển Word → LaTeX (docxnative): chỉ số trên/dưới, ký hiệu Insert→Symbol, escape % & #, đáp án gạch chân."""
import pytest

docx = pytest.importorskip("docx")

from nganhangde.docxnative import _tex_plain, docx_to_ex, docx_to_latex  # noqa: E402
from nganhangde.parser import parse_tex  # noqa: E402


def _make(tmp_path, paras):
    from docx.enum.text import WD_UNDERLINE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    d = docx.Document()
    for parts in paras:
        p = d.add_paragraph()
        for item in parts:
            if isinstance(item, tuple) and item[0] == "__SYM__":
                r = p.add_run()
                sym = OxmlElement("w:sym")
                sym.set(qn("w:font"), "Symbol")
                sym.set(qn("w:char"), item[1])
                r._r.append(sym)
                continue
            text, kw = item
            r = p.add_run(text)
            if kw.get("u"):
                r.underline = WD_UNDERLINE.SINGLE
            if kw.get("sup"):
                r.font.superscript = True
            if kw.get("sub"):
                r.font.subscript = True
    path = tmp_path / "de.docx"
    d.save(str(path))
    return str(path)


def test_plain_text_escapes():
    assert _tex_plain("50% đúng") == r"50\% đúng"
    assert _tex_plain("3 & 4 # 5") == r"3 \& 4 \# 5"
    assert _tex_plain("%[0D2N1-2]") == "%[0D2N1-2]"          # chú thích ID giữ nguyên
    assert _tex_plain("x ≤ 2") == r"x $\le$ 2"
    assert _tex_plain("π") == r"$\pi$"


def test_superscript_subscript_and_symbol(tmp_path):
    p = _make(tmp_path, [[("Câu 1. ", {}), ("y = x", {}), ("2", {"sup": True}), (" và m", {}), ("3", {"sub": True})],
                         [("A. 1", {}), ("__SYM__", "F0A3"), (" 2", {})]])
    text, _ = docx_to_latex(p)
    assert "x$^{2}$" in text and "m$_{3}$" in text
    assert "$\\le$" in text                                     # Insert → Symbol (≤) không bị mất


def test_percent_does_not_swallow_line(tmp_path):
    p = _make(tmp_path, [[("Câu 1. ", {}), ("Tỉ lệ 50% đúng là bao nhiêu?", {})],
                         [("A. 1", {})], [("B. 2", {"u": True})], [("C. 3", {})], [("D. 4", {})]])
    t, _ = docx_to_ex(p, tag="T")
    qs = parse_tex(t)
    assert len(qs) == 1 and "đúng là bao nhiêu" in qs[0].stem        # phần sau dấu % không bị mất
    assert qs[0].correct == [False, True, False, False]


def test_two_questions_with_answers(tmp_path):
    p = _make(tmp_path, [
        [("Câu 1. ", {}), ("Cho hàm số y = x", {}), ("2", {"sup": True}), (".", {})],
        [("A. 1", {})], [("B. 2", {"u": True})], [("C. 3 & 4", {})], [("D. 5", {})],
        [("Câu 2. ", {}), ("Tính 10", {}), ("3", {"sup": True}), (".", {})],
        [("A. 1000", {})], [("B. 100", {})], [("C. 10", {"u": True})], [("D. 1", {})],
    ])
    t, _ = docx_to_ex(p, tag="T")
    qs = parse_tex(t)
    assert [q.qtype for q in qs] == ["TN", "TN"]
    assert qs[0].correct == [False, True, False, False] and qs[1].correct == [False, False, True, False]
    assert "3 \\& 4" in t
