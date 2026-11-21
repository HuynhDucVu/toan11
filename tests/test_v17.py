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


def test_mylt_columns_and_find(tmp_path, bank):
    from nganhangde import mylt_import as m
    assert m.pick_columns(["id", "NoiDung", "IDCauHoi", "TuLuan", "SoLan"]) == {
        "text": "NoiDung", "id": "IDCauHoi", "tuluan": "TuLuan", "solan": "SoLan"}
    cm = m.pick_columns(["ID", "Nội dung", "ID Câu hỏi", "Tự luận", "Số lần"])
    assert cm["text"] == "Nội dung" and cm["id"] == "ID Câu hỏi" and m.pick_columns(["a", "b"]) == {}
    rows = m._normalize([{"Nội dung": b"\xe1\xbb\x91", "ID Câu hỏi": "0d1n1-1", "Số lần": 2.0}], {**cm})
    assert rows[0]["NoiDung"] == "ố" and rows[0]["SoLan"] == 2.0
    d = tmp_path / "MyLT" / "DATA" / "BANK"
    d.mkdir(parents=True)
    (d / "Bank.mylt").write_bytes(b"x" * 50)
    assert [p for p in m.find_banks([str(tmp_path)]) if p.endswith("Bank.mylt")]
    with pytest.raises(m.MyltError):
        m.read_rows(str(tmp_path / "khong_co.mylt"))
    with pytest.raises(m.MyltError):                       # file không phải Access
        m.read_rows(str(d / "Bank.mylt"))


def test_mylt_archive(tmp_path, monkeypatch):
    from nganhangde import mylt_import as m
    monkeypatch.setattr(m, "_tools", lambda: [])
    with pytest.raises(m.MyltError) as e:
        m.extract_archive(str(tmp_path / "Bank.rar"))
    assert "WinRAR" in str(e.value)
    exe = shutil.which("7z") or shutil.which("7za")
    if not exe:
        pytest.skip("không có 7z")
    import subprocess
    src = tmp_path / "Bank.mylt"
    src.write_bytes(b"du lieu gia")
    z = tmp_path / "Bank.7z"
    subprocess.run([exe, "a", "-pMyLT123", str(z), str(src)], check=True, capture_output=True)
    monkeypatch.setattr(m, "_tools", lambda: [("7z", exe)])
    out = m.extract_archive(str(z), "MyLT123", str(tmp_path / "o"))
    assert open(out, "rb").read() == b"du lieu gia"
    with pytest.raises(m.MyltError):
        m.extract_archive(str(z), "sai", str(tmp_path / "o2"))


def test_jet4_password_roundtrip(tmp_path):
    import struct
    from nganhangde import mylt_import as m
    mask = 0xAA7F
    raw = bytearray(40)
    for i in range(20):
        v = ord("MyLT@2018"[i]) if i < 9 else 0
        struct.pack_into("<H", raw, i * 2, v ^ mask if i % 2 == 0 else v)
    plain = bytearray(0x80)
    plain[0x2A:0x52] = raw
    head = bytearray(0x98)
    head[0x14] = 1
    head[0x18:0x98] = m._rc4(bytes([0xC7, 0xDA, 0x39, 0x6B]), bytes(plain))
    p = tmp_path / "Bank.mylt"
    p.write_bytes(bytes(head))
    assert m.jet4_password(str(p)) == "MyLT@2018"
    p.write_bytes(b"\x00" * 200)
    assert m.jet4_password(str(p)) == ""
    assert "SELECT * FROM" in m.PS_SCRIPT and "Jet OLEDB:Database Password" in m.PS_SCRIPT


def test_mylt_sync_and_diagnose(tmp_path, bank, monkeypatch):
    from nganhangde import mylt_import as m
    f = tmp_path / "Bank.mylt"
    f.write_bytes(b"x")
    rows = [{"NoiDung": "\\begin{ex}%[0D1N1-1]\nCâu đồng bộ mới $x$\n\\choice\n{\\True a}\n{b}\n{c}\n{d}\n\\loigiai{Chọn A.}\n\\end{ex}",
             "IDCauHoi": "0D1N1-1", "TuLuan": 0, "SoLan": 0}]
    monkeypatch.setattr(m, "iter_rows", lambda p: iter(rows))
    st = {}
    S = type("S", (), {"value": lambda self, k, d=None: st.get(k, d), "setValue": lambda self, k, v: st.__setitem__(k, v)})()
    assert m.sync_if_linked(bank, S) is None                 # chưa liên kết
    st["mylt/link"] = str(f)
    n0 = bank.count()
    assert m.sync_if_linked(bank, S)["them"] == 1 and bank.count() == n0 + 1
    assert m.sync_if_linked(bank, S) is None                 # file không đổi ⇒ không nhập lại
    assert "Dung lượng" in m.diagnose(str(f))


def _make_docx(path, body_xml, media=None):
    import zipfile
    W = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
         'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"')
    doc = f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body>{body_xml}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", doc)
        for k, v in (media or {}).items():
            z.writestr(k, v)


def _p(text="", underline=False, math=None):
    r = (f'<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>' if underline else
         f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>') if text else ""
    m = (f'<m:oMath><m:f><m:num><m:r><m:t>{math[0]}</m:t></m:r></m:num><m:den><m:r><m:t>{math[1]}</m:t></m:r></m:den>'
         '</m:f></m:oMath>') if math else ""
    return f"<w:p>{r}{m}</w:p>"


def test_docx_native_reader(tmp_path, monkeypatch):
    from nganhangde import wordconv
    from nganhangde.docxnative import DocxOptions, docx_to_latex
    body = (_p("Câu 1. Giá trị của ") + _p(math=("1", "2")) + _p("A. 1") + _p("B. 2", underline=True) + _p("C. 3") + _p("D. 4")
            + _p("Lời giải. Chọn B.") + _p("Câu 2. Cho hàm số.") + _p("a) Mệnh đề 1", underline=True) + _p("b) Mệnh đề 2")
            + _p("c) Mệnh đề 3") + _p("d) Mệnh đề 4", underline=True))
    f = tmp_path / "de.docx"
    _make_docx(str(f), body)
    tex, rep = docx_to_latex(str(f))
    assert "$\\dfrac{1}{2}$" in tex and "\\underline{B.} 2" in tex and rep.omml == 1 and rep.mathtype_ole == 0
    monkeypatch.setattr(wordconv, "pandoc_path", lambda: (_ for _ in ()).throw(wordconv.PandocMissing("x")))
    qs = parse_tex(wordconv.import_docx(str(f)))                      # không có pandoc ⇒ đọc bằng Python thuần
    assert [q.qtype for q in qs] == ["TN", "DS"] and qs[0].answer_text == "B" and qs[1].correct == [True, False, False, True]
    # tuỳ chọn thay thế cá nhân + chuyên đề (giữ văn bản)
    out = wordconv.import_docx(str(f), "", DocxOptions(replacements=[("Mệnh đề", "Khẳng định")], theory=True))
    assert "Khẳng định 1" in out and "\\begin{ex}" not in out


def test_docx_mathtype_warning_and_table(tmp_path):
    from nganhangde.docxnative import docx_to_latex
    tbl = ('<w:tbl><w:tr><w:tc><w:p><w:r><w:t>x</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>y</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    f = tmp_path / "t.docx"
    _make_docx(str(f), _p("Bảng:") + tbl, {"word/embeddings/oleObject1.bin": b"MathType"})
    tex, rep = docx_to_latex(str(f))
    assert "\\begin{tabular}{|c|c|}" in tex and rep.mathtype_ole == 1 and rep.warnings


def test_tools2_extras():
    from nganhangde import tools2
    t = open(SAMPLE, encoding="utf-8").read()
    a, n = tools2.add_dapso(t)
    assert n == 12 and a.count("\\dapso{") == 12 and tools2.add_dapso(a)[1] == 0
    b, n = tools2.shuffle_questions(t, 1)
    assert n == 22 and sorted(q.fingerprint for q in parse_tex(b)) == sorted(q.fingerprint for q in parse_tex(t))
    c, _ = tools2.sort_by_id_text(t)
    ids = [q.id_code for q in parse_tex(c)]
    assert ids == sorted(ids)
    d, n = tools2.shuffle_choices_in_file(t, 2)
    assert n > 0 and len(parse_tex(d)) == 22
    e, n = tools2.assign_group_id(t, "0D2N1-2")
    assert n == 22 and {q.id_code for q in parse_tex(e)} == {"0D2N1-2"}
    f, n = tools2.hide_show_ids(t, "show")
    assert n == 22 and tools2.hide_show_ids(f, "hide")[0] == t
    assert {q.id_code for q in parse_tex(tools2.hide_show_ids(t, "remove")[0])} == {""}


def test_topic_book(bank, tmp_path):
    from nganhangde.topicbook import export_topic_book
    p = export_topic_book(bank.search(), bank.idmap(), str(tmp_path / "cd.tex"), title="CHUYÊN ĐỀ", school="THPT A")
    tex = open(p, encoding="utf-8").read()
    assert tex.count("\\begin{ex}") == 22 and "\\section{" in tex and "\\subsection{" in tex and "\\tableofcontents" in tex
    if shutil.which("pdflatex"):
        from nganhangde.pdfbuild import compile_tex
        assert compile_tex(p).ok


def test_omr_profiles_and_qr_formats():
    from nganhangde import omr
    from nganhangde.generator import ExamVersion
    from nganhangde.parser import Question
    v = ExamVersion("0101")
    v.sections = {"TN": [Question("TN", "x", list("abcd"), [True, False, False, False])],
                  "DS": [Question("DS", "y", list("abcd"), [True, False, True, False])],
                  "KQ": [Question("KQ", "z", short_answer="$5$")], "TL": []}
    md = omr.qr_payload(v, "md")
    assert md.startswith("MD:0101;P1:A;P2:ĐSĐS;P3:")
    assert '"code":"0101"' in omr.qr_payload(v, "json")
    assert omr.check_capacity([v], profile="bgd2025") == []
    big = ExamVersion("0101")
    big.sections = {"TN": [v.sections["TN"][0]] * 15, "DS": [], "KQ": [], "TL": []}
    assert omr.check_capacity([big], profile="toan_12_4_6")
    assert not omr.check_capacity([big], profile="bgd2025")


def test_mathpix_request_and_theme(tmp_path):
    import base64
    import pytest
    from nganhangde import mathpix
    from nganhangde.ui.common import STYLE
    from nganhangde.ui.dialogs.appearance import themed_style
    f = tmp_path / "a.png"
    f.write_bytes(b"\x89PNGxx")
    req = mathpix.build_request(str(f))
    assert req["src"].startswith("data:image/png;base64,") and base64.b64decode(req["src"].split(",")[1]) == b"\x89PNGxx"
    with pytest.raises(mathpix.MathpixError):
        mathpix.image_to_latex(str(f), "", "")
    s = themed_style(STYLE, "#112233", "#445566")
    assert "#112233" in s and "#1f4e79" not in s and "#445566" in s


def test_cleanup_dups_and_wrong(tmp_path):
    from nganhangde import cleanup
    from nganhangde.db import Bank
    from nganhangde.parser import parse_tex
    b = Bank(str(tmp_path / "c.db"))
    t1 = ("\\begin{ex}%[0D1N1-1]\nTính $1+1$.\n\\choice\n{$1$}\n{\\True $2$}\n{$3$}\n{$4$}\n\\loigiai{Chọn B.}\n\\end{ex}")
    t2 = t1.replace("\\loigiai{Chọn B.}\n", "").replace("[0D1N1-1]", "[0D1N1]")          # cùng nội dung, thiếu lời giải/ID
    t2 = t2.replace("Tính $1+1$.", "Tính  $1 + 1$")                                      # khác khoảng trắng
    bad = "\\begin{ex}%[0D1N1-2]\nTính $x.\n\\choice\n{$1$}\n{\\True $2$}\n{$3$}\n{$4$}\n\\end{ex}"   # $ lẻ
    for t in (t1, t2, bad):
        for q in parse_tex(t):
            b.add(q, "t")
    assert b.count() == 3
    r = cleanup.scan(b)
    assert len(r.dup_exact) == 1 and len(r.wrong) == 1
    keep = list(r.dup_exact.values())[0]
    assert "Chọn B" in b.get(keep).solution            # giữ câu có lời giải
    ids = r.delete_ids(wrong=False, exact=True, near=True)
    assert cleanup.apply(b, ids) == 1 and b.count() == 2


def _ex(idc, stem, sol=True, ans="B"):
    ch = "".join(("{\\True " if L == ans else "{") + f"p{L}" + "}\n" for L in "ABCD")
    return (f"\\begin{{ex}}%[{idc}]\n{stem}\n\\choice\n{ch}" + ("\\loigiai{Chọn B.}\n" if sol else "") + "\\end{ex}\n")


def test_mix_region_solution_filter_toggle(tmp_path):
    import random
    from nganhangde import generator as g
    from nganhangde.db import Bank
    from nganhangde.exporter import ExportOptions, export_versions
    from nganhangde.parser import parse_tex
    b = Bank(str(tmp_path / "m.db"))
    for k in range(6):
        for q in parse_tex(_ex(f"0D1N1-{k % 3 + 1}", f"Câu chương một số {k} $x_{k}$", sol=k % 2 == 0)):
            b.add(q, "t")
    for k in range(6):
        for q in parse_tex(_ex(f"0D2N1-{k % 3 + 1}", f"Câu chương hai số {k} $y_{k}$", sol=True)):
            b.add(q, "t")
    rules = [g.Rule("TN", 12, "*")]
    # lọc lời giải
    with_sol = g.pick_questions(b, [g.Rule("TN", 9, "*")], random.Random(1), solution_filter="co")
    assert all(q.solution.strip() for q in with_sol["TN"])
    no_sol = g.pick_questions(b, [g.Rule("TN", 3, "*")], random.Random(1), solution_filter="khong")
    assert not any(q.solution.strip() for q in no_sol["TN"])
    # trộn riêng từng chương: chương 1 luôn đứng trước chương 2
    sec = g.pick_questions(b, rules, random.Random(2))
    sec["TN"].sort(key=lambda q: q.id_code)
    vs = g.mix_versions(sec, ["101", "102", "103"], random.Random(3), g.MixOptions(region_by="chuong"))
    for v in vs:
        ch = [q.id_code[2] for q in v.sections["TN"]]
        assert ch == sorted(ch)
    # ẩn/hiện đáp án bằng 1 lệnh
    files = export_versions(vs[:1], str(tmp_path / "out"), options=ExportOptions(ans_toggle=True))
    lg = open([f for f in files if "loigiai" in f][0], encoding="utf-8").read()
    assert "\\newif\\ifshowans" in lg and "\\ifshowans" in lg and lg.count("\\fi") >= 1


def test_similar_widen_and_content(tmp_path):
    import random
    from nganhangde import generator as g
    from nganhangde.db import Bank
    from nganhangde.parser import parse_tex
    b = Bank(str(tmp_path / "s.db"))
    stems = {"0D1N1-1": "Tính đạo hàm của hàm số $y=x^2$", "0D1N2-1": "Tính đạo hàm hàm số $y=x^3$ tại điểm",
             "0D1N2-2": "Tìm tập xác định của phân thức", "0D1H3-1": "Giải phương trình lượng giác sinx=1"}
    for idc, s in stems.items():
        for q in parse_tex(_ex(idc, s)):
            b.add(q, "t")
    sample = parse_tex(_ex("0D1N1-1", "Tính đạo hàm của hàm số $y=x^4$"))
    out, notes = g.similar_exam(b, sample, random.Random(0), widen=0, keep_missing=False)
    assert out and "0D1N1" in out[0].id_code
    far = parse_tex(_ex("0D1N5-1", "Tính đạo hàm hàm số $y=x^5$"))             # không có câu cùng ID/ID5
    out, notes = g.similar_exam(b, far, random.Random(0), widen=0, keep_missing=False)
    assert not out
    out, notes = g.similar_exam(b, far, random.Random(0), widen=2, by_content=True, keep_missing=False)
    assert out and out[0].id_code.startswith("0D1N") and "đạo hàm" in out[0].stem and any("ID4" in n for n in notes)


def test_mylt_xlsx_layout(tmp_path):
    import openpyxl
    from nganhangde.exporter import ExportOptions
    from nganhangde.generator import ExamVersion
    from nganhangde.parser import Question
    from nganhangde.tnmaker import write_answer_xlsx
    vs = []
    for code, ans in (("813", [True, False, False, False]), ("784", [False, True, False, False])):
        v = ExamVersion(code)
        v.sections = {"TN": [Question("TN", "x", list("abcd"), ans)],
                      "DS": [Question("DS", "y", list("abcd"), [True, False, True, False])],
                      "KQ": [Question("KQ", "z", short_answer="$0{,}11$"), Question("KQ", "z", short_answer="$38$")], "TL": []}
        vs.append(v)
    p = write_answer_xlsx(vs, str(tmp_path / "a.xlsx"), ExportOptions())
    ws = openpyxl.load_workbook(p).active
    assert ws.title == "MyLT" and ws["A1"].value == "Câu\\Đề" and ws["B1"].value == 813
    assert [ws.cell(r, 1).value for r in range(2, 6)] == [1, 2, 3, 4]       # số câu liên tục
    assert ws["B2"].value == "A" and ws["C2"].value == "B" and ws["B4"].value == "0,11" and ws["B5"].value == 38


def test_layout_like_mylt(tmp_path, monkeypatch):
    from nganhangde import appdirs
    root = str(tmp_path / "app")
    appdirs.ensure_layout(root)
    for sub in ("DATA/BANK", "DATA/DE", "DATA/AUTO", "DATA/MA TRAN DE", "DATA/WORD2EXTEST", "DATA/EXTEST2WORD", "DATA/PDF2TEX",
                "DATA/MOODLE XML", "DATA/MFORMS", "DATA/TUONG TU", "DATA/LOC ID", "DATA/LOC TIKZ", "DATA/IMG",
                "TEMPLATE", "Map ID (DPS)", "TEMP", "LOG"):
        assert (tmp_path / "app").joinpath(*sub.split("/")).is_dir(), sub
    assert (tmp_path / "app" / "TEMPLATE" / "de_thi.tex").exists()
    assert appdirs.folder("de_xuat", root).endswith("DE")
    # bản cũ: thư mục cũ còn thì dùng tiếp
    old = tmp_path / "cu"
    (old / "de_xuat").mkdir(parents=True)
    assert appdirs.folder("de_xuat", str(old)).endswith("de_xuat")


def test_phieu_tltn_2025(tmp_path):
    import pytest
    pytest.importorskip("pypdf")
    pdfium = pytest.importorskip("pypdfium2")
    from nganhangde import phieutltn as P
    from nganhangde.generator import ExamVersion
    from nganhangde.parser import Question
    v = ExamVersion("813")
    v.sections = {"TN": [Question("TN", "x", list("abcd"), [i % 4 == k for k in range(4)]) for i in range(40)],
                  "DS": [Question("DS", "y", list("abcd"), [True, False, True, False]) for _ in range(8)],
                  "KQ": [Question("KQ", "z", short_answer="$-0{,}9$"), Question("KQ", "z", short_answer="$12345$")], "TL": []}
    pts, warn = P.marks_for(v)
    assert len(pts) == 40 + 32 + 4 + 3 and any("dài hơn 4" in w for w in warn)   # 5 chữ số không tô được
    files, w2 = P.export_sheets([v], str(tmp_path / "ph"))
    assert len(files) == 2 and all(f.endswith(".pdf") for f in files)
    img = pdfium.PdfDocument(files[1])[0].render(scale=1).to_pil().convert("L")
    x, y = P.P1_X[0][0], P.P1_Y[0]                     # câu 1 đáp án A phải được tô đen
    assert img.getpixel((int(x), int(y))) < 60
    assert pdfium.PdfDocument(files[0])[0].render(scale=1).to_pil().convert("L").getpixel((int(x), int(y))) > 200


def test_default_export_has_sheet_and_tnmaker_excel(tmp_path):
    import os
    import pytest
    pytest.importorskip("pypdf")
    from nganhangde.exporter import ExportOptions, export_versions
    from nganhangde.generator import ExamVersion
    from nganhangde.parser import Question
    v = ExamVersion("813")
    v.sections = {"TN": [Question("TN", "x", list("abcd"), [True, False, False, False])], "DS": [], "KQ": [], "TL": []}
    files = export_versions([v], str(tmp_path / "o"), options=ExportOptions())
    names = [os.path.basename(f) for f in files]
    assert "dap_an_TNMaker.xlsx" in names and "phieu_khoa_813.pdf" in names and "phieu_trang_TLTN2025.pdf" in names


def test_pdf_to_tex_text_layer(tmp_path):
    import shutil
    import subprocess
    import pytest
    pytest.importorskip("pypdfium2")
    if not shutil.which("pdflatex"):
        pytest.skip("không có pdflatex")
    from nganhangde import pdf2tex
    t = tmp_path / "de.tex"
    t.write_text("\\documentclass{article}\\usepackage[utf8]{inputenc}\\begin{document}"
                 "PHAN I\\\\ Cau 1. Tinh $1+1$.\\\\ A. 1 B. 2 C. 3 D. 4\\\\ "
                 "Cau 2. Tong $2+2$.\\\\ A. 3 B. 4 C. 5 D. 6\\\\ DAP AN\\\\ 1. B 2. B 3. C\\end{document}", encoding="utf-8")
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "de.tex"], cwd=tmp_path, capture_output=True, timeout=60)
    text = pdf2tex.extract_text(str(tmp_path / "de.pdf"))
    assert "Cau 1" in text
    tex, notes = pdf2tex.text_to_ex(text.replace("Cau", "Câu").replace("DAP AN", "ĐÁP ÁN").replace("PHAN", "PHẦN"))
    qs = __import__("nganhangde.parser", fromlist=["parse_tex"]).parse_tex(tex)
    assert len(qs) == 2 and all(q.qtype == "TN" and q.answer_text == "B" for q in qs)
    out, n2 = pdf2tex.pdf_to_tex(str(tmp_path / "de.pdf"), "text")
    assert isinstance(out, str)
