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


def test_verify_conversion_reports_missing_answer_and_count(tmp_path):
    """Kiểm tra sau chuyển: đếm mốc «Câu» khớp số câu; câu thiếu lời giải được báo."""
    from nganhangde.docxnative import verify_docx_conversion, docx_to_ex
    p = _make(tmp_path, [
        [("Câu 1. ", {}), ("Tính 1+1.", {})],
        [("A. 2", {})], [("B. 3", {"u": True})], [("C. 4", {})], [("D. 5", {})],
        [("Câu 2. ", {}), ("Tính 2+2.", {})],
        [("A. 3", {})], [("B. 4", {"u": True})], [("C. 5", {})], [("D. 6", {})],
        [("Lời giải. ", {}), ("Chọn B.", {})],
    ])
    tex, _ = docx_to_ex(p, tag="T")
    warns = verify_docx_conversion(p, tex)
    assert any("chưa có lời giải" in w and "câu 1" in w for w in warns)
    assert not any("mốc «Câu»" in w for w in warns)                      # 2 mốc, 2 câu: khớp


def test_word_dialog_wires_verify_and_ai(monkeypatch):
    """Hộp thoại chuyển Word: có tuỳ chọn AI; ai_polish_tex viết lời giải, báo đáp án AI khác, xuất LaTeX chuẩn."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import nganhangde.ui.dialogs.ai_settings as ais
    from nganhangde.ui.dialogs import word2tex as w2t
    from nganhangde.parser import parse_tex
    assert any(k == "ai_review" for k, _t, _d in w2t.CHECKS)

    class FakeClient:
        def generate_json(self, prompt, schema=None):
            return {"dap_an": "B", "loi_giai": "Lời giải do AI viết.", "ghi_chu": ""}
    monkeypatch.setattr(ais, "ensure_client", lambda win: FakeClient())
    tex = ("\\begin{ex}%[0D2N1-1]\n\tTính 1+1.\n\t\\choice\n\t{\\True 2}\n\t{3}\n\t{4}\n\t{5}\n"
           "\t\\loigiai{\n\t\tCũ.\n\t}\n\\end{ex}\n")
    out, notes = w2t.ai_polish_tex(None, tex)
    qs = parse_tex(out)
    assert len(qs) == 1 and "Lời giải do AI viết." in qs[0].solution
    assert any("viết lại lời giải 1/1" in n for n in notes)
    assert any("đáp án khác" in n for n in notes)                      # AI ra B, đáp án đánh dấu là A


def test_manim_lecture_code_main_and_size(tmp_path):
    """Bài giảng Manim: sinh code hợp lệ, main.py, đo dung lượng; biên dịch thật chỉ khi máy có manim."""
    import ast
    import shutil
    from nganhangde import manim_lecture as ml

    class FakeClient:
        def generate_json(self, prompt, schema=None):
            return {"title": "Hàm số", "scenes": [{"title": "Định nghĩa", "blocks": [
                {"kind": "text", "content": "Hàm số bậc hai"}, {"kind": "math", "content": r"y=ax^2+bx+c"},
                {"kind": "step", "content": "Với a khác 0"}]}]}
    design = ml.design_lecture(FakeClient(), "nội dung")
    assert design["scenes"][0]["title"] == "Định nghĩa"
    p = ml.write_project(design, str(tmp_path / "bg"), "-ql")
    ast.parse(open(p["code"], encoding="utf-8").read())                    # mã Python hợp lệ
    assert "class Canh01_Dinh_nghia(Scene)" in open(p["code"], encoding="utf-8").read()
    assert "SCENES = ['Canh01_Dinh_nghia']" in open(p["main"], encoding="utf-8").read()
    assert ml.size_report([])["total"] == 0
    if shutil.which("manim") is None and ml.manim_command() is None:
        ok, vids, msg = ml.render(str(tmp_path / "bg"), p["scenes"], "-ql")
        assert not ok and "pip install manim" in msg                       # không có manim: báo cách cài
