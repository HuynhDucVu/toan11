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
    assert "\\begin{tabular}{|c|c|}" in tex and rep.mathtype_ole == 1 and rep.mathtype_ok == 0


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
    pytest.importorskip("pypdfium2")
    from nganhangde import phieutltn as P
    from nganhangde.pdfrender import render_file
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
    x, y = P.P1_X[0][0], P.P1_Y[0]                     # câu 1 đáp án A phải được tô đen
    assert render_file(files[1], 0, 1).pixelColor(int(x), int(y)).red() < 60
    assert render_file(files[0], 0, 1).pixelColor(int(x), int(y)).red() > 200


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


def test_run_cancelable(tmp_path):
    import sys
    import threading
    import time
    import pytest
    from nganhangde import mylt_import as m
    out = str(tmp_path / "o.txt")
    assert m._run_cancelable([sys.executable, "-c", "print('xin chao')"], out, stdout_to_out=True) == ""
    assert "xin chao" in open(out).read()
    err = m._run_cancelable([sys.executable, "-c", "import sys;sys.stderr.write('loi nang');sys.exit(3)"], out)
    assert "loi nang" in err
    stop = {"v": False}
    threading.Timer(0.8, lambda: stop.__setitem__("v", True)).start()
    t = time.time()
    with pytest.raises(m.MyltError):
        m._run_cancelable([sys.executable, "-c", "import time;time.sleep(30)"], out, should_stop=lambda: stop["v"])
    assert time.time() - t < 10


def test_pandoc_download_from_local_zip(tmp_path, monkeypatch):
    import pathlib
    import zipfile
    from nganhangde import pandoc_dl, wordconv
    z = tmp_path / "pandoc-9.9-windows-x86_64.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("pandoc-9.9/pandoc.exe", b"MZ-gia")
        f.writestr("pandoc-9.9/readme.txt", "x")
    seen = []
    out = pandoc_dl.download_pandoc(str(tmp_path / "pd"), pathlib.Path(z).as_uri(), progress=lambda a, b: seen.append((a, b)))
    assert out.endswith("pandoc.exe") and open(out, "rb").read() == b"MZ-gia"
    monkeypatch.setattr(wordconv.shutil, "which", lambda n: None)
    monkeypatch.setattr(pandoc_dl, "target_dir", lambda: str(tmp_path / "pd"))
    from nganhangde import appdirs
    monkeypatch.setattr(appdirs, "folder", lambda key, root=None: str(tmp_path / "pd") if key == "pandoc" else str(tmp_path / key))
    assert wordconv.pandoc_path() == out                      # tìm thấy pandoc trong thư mục phần mềm
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as f:
        f.writestr("a.txt", "x")
    import pytest
    with pytest.raises(pandoc_dl.PandocDownloadError):
        pandoc_dl.download_pandoc(str(tmp_path / "pd2"), pathlib.Path(bad).as_uri())


def test_inline_double_dollar_and_clean_code():
    from nganhangde.texutil import inline_double_dollar
    from nganhangde.tools2 import clean_code
    assert inline_double_dollar("Tính $$x$$ biết $$y=2$$.") == "Tính $x$ biết $y=2$."
    assert inline_double_dollar("$$\\dfrac{1}{2}$$") == "$$\\dfrac{1}{2}$$"            # công thức trình bày riêng: giữ
    assert inline_double_dollar("\t{$$x^2$$}") == "\t{$x^2$}"                          # trong phương án: về $…$
    assert inline_double_dollar("Giá $5$ và $6$") == "Giá $5$ và $6$"
    text = "\\begin{ex}\nChu vi $$C=2.(5+9)=28$$.\n\\end{ex}\n"
    out, _ = clean_code(text)
    assert "$C=2.(5+9)=28$" in out and "$$" not in out


def test_word_to_ex_inline_double_dollar(tmp_path):
    import sys
    sys.path.insert(0, __import__("os").path.dirname(__file__))
    from nganhangde.wordconv import latex_text_to_ex
    blocks = latex_text_to_ex("Câu 1. Cho $$x$$ thoả $$x>0$$.\nA. $$1$$\nB. $$2$$\nC. $$3$$\nD. $$4$$\n")
    assert blocks and "$$" not in blocks[0] and "$x$" in blocks[0]


def test_package_folder_copied_next_to_exports(tmp_path):
    import os
    from nganhangde import packages
    from nganhangde.exporter import ExportOptions, export_versions
    from nganhangde.generator import ExamVersion
    from nganhangde.parser import Question
    v = ExamVersion("101")
    v.sections = {"TN": [Question("TN", "x", list("abcd"), [True, False, False, False])], "DS": [], "KQ": [], "TL": []}
    out1 = tmp_path / "o1"
    export_versions([v], str(out1), options=ExportOptions(answers_xlsx=False, tltn2025=False))
    assert not (out1 / "ex_test.sty").exists()              # thư mục gói lệnh trống: không chép gì (không chép gói rút gọn)
    fake = tmp_path / "ex_test.sty"
    fake.write_text("% ex_test moi nhat\n\\ProvidesPackage{ex_test}\n", encoding="utf-8")
    packages.install_package(str(fake))
    assert packages.has_extest() and "ex_test.sty" in packages.list_packages()
    out2 = tmp_path / "o2"
    try:
        export_versions([v], str(out2), options=ExportOptions(answers_xlsx=False, tltn2025=False, per_folder=True))
        assert (out2 / "101" / "ex_test.sty").exists()       # cạnh từng file đề
    finally:
        os.remove(os.path.join(packages.package_dir(), "ex_test.sty"))      # thư mục phần mềm dùng chung cả phiên kiểm thử
    import pytest
    with pytest.raises(ValueError):
        packages.install_package(str(tmp_path / "a.txt"))


def test_docx_auto_numbering(tmp_path):
    """Đề Word đánh số tự động: «Câu 1.», A–D, a)–d) không có trong văn bản đoạn."""
    from nganhangde import wordconv
    from nganhangde.docxnative import DocxOptions, docx_to_latex
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    numbering = f"""<?xml version="1.0" encoding="UTF-8"?><w:numbering {W}>
<w:abstractNum w:abstractNumId="0">
 <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="Câu %1."/></w:lvl>
 <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="upperLetter"/><w:lvlText w:val="%2."/></w:lvl>
 <w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%3)"/></w:lvl>
</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>"""

    def para(text, lvl, underline=False):
        r = (f'<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>{text}</w:t></w:r>' if underline else f"<w:r><w:t>{text}</w:t></w:r>")
        return f'<w:p><w:pPr><w:numPr><w:ilvl w:val="{lvl}"/><w:numId w:val="1"/></w:numPr></w:pPr>{r}</w:p>'
    body = (para("Tính $1+1$.", 0) + para("1", 1) + para("2", 1, underline=True) + para("3", 1) + para("4", 1)
            + para("Cho hàm số.", 0) + para("ý một", 2, underline=True) + para("ý hai", 2) + para("ý ba", 2) + para("ý bốn", 2, underline=True))
    f = tmp_path / "de.docx"
    _make_docx(str(f), body, media={"word/numbering.xml": numbering})
    tex, _ = docx_to_latex(str(f))
    assert "Câu 1. Tính" in tex and "Câu 2. Cho hàm số." in tex       # nhãn «Câu N.» được tính lại
    assert "\\underline{B.} 2" in tex and "A. 1" in tex and "D. 4" in tex          # chữ phương án tự đánh số
    assert "\\underline{a)} ý một" in tex and "d) ý bốn" in tex or "\\underline{d)} ý bốn" in tex
    qs = parse_tex(wordconv.import_docx(str(f), "", DocxOptions()))
    assert [q.qtype for q in qs] == ["TN", "DS"] and qs[0].answer_text == "B"
    assert qs[1].correct == [True, False, False, True]


def test_docx_options_in_table(tmp_path):
    from nganhangde import wordconv
    from nganhangde.docxnative import DocxOptions
    def cell(t, u=False):
        r = (f'<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>{t}</w:t></w:r>' if u else f"<w:r><w:t>{t}</w:t></w:r>")
        return f"<w:tc><w:p>{r}</w:p></w:tc>"
    tbl = "<w:tbl><w:tr>" + cell("A. 1") + cell("B. 2", True) + cell("C. 3") + cell("D. 4") + "</w:tr></w:tbl>"
    body = _p("Câu 1. Tính $1+1$.") + tbl + _p("Câu 2. Thêm.") + tbl.replace("B. 2", "B. 22")
    f = tmp_path / "de.docx"
    _make_docx(str(f), body)
    for tables in (True, False):                          # bảng phương án luôn được dàn lại, kể cả khi tắt «Chuyển bảng»
        qs = parse_tex(wordconv.import_docx(str(f), "", DocxOptions(tables=tables)))
        assert len(qs) == 2 and qs[0].qtype == "TN" and qs[0].choices[1] == "2"
        assert qs[0].answer_text == "B"


def test_docx_diagnosis_report(tmp_path):
    from nganhangde.docxnative import diagnose_docx
    f = tmp_path / "x.docx"
    _make_docx(str(f), _p("Tiêu đề đề thi") + _p("Câu 1. Tính $1+1$.") + _p("A. 1") + _p("B. 2", underline=True))
    rp = diagnose_docx(str(f))
    assert "Số đoạn: 4" in rp and "Câu N=1" in rp and "A./B./C./D.=2" in rp and "có \\underline=1" in rp


def _mtef_char(face, code, opt=0, fontpos=None):
    b = bytearray([2, opt | (0x04 if fontpos is not None else 0), 128 + face, code & 255, code >> 8])
    if fontpos is not None:
        b.append(fontpos)
    return bytes(b)


def _mtef_header():
    return bytes([5, 1, 0, 4, 0]) + b"DSMT4\x00" + b"\x00"


def test_mtef_quadratic_formula_and_templates():
    """Công thức nghiệm –b ± √(b²–4ac) / 2a theo đúng ví dụ trong đặc tả MTEF v5."""
    from nganhangde import mtef
    END, LINE = b"\x00", b"\x01\x00"
    minus = _mtef_char(6, 0x2212, fontpos=0x2D)
    pm = _mtef_char(6, 0x00B1, fontpos=0xB1)
    var = lambda c: _mtef_char(3, ord(c))
    num = lambda c: _mtef_char(8, ord(c))
    # TMPL mũ: ô chỉ số dưới rỗng (LINE NULL) rồi ô mũ
    sup_tmpl = bytes([3, 0, 28, 0, 0]) + bytes([1, 1]) + bytes([1, 0]) + num("2") + END + END
    radicand = bytes([1, 0]) + var("b") + sup_tmpl + minus + num("4") + var("a") + var("c") + END
    root = bytes([3, 0, 10, 0, 0]) + radicand + bytes([1, 1]) + END
    numer = bytes([1, 0]) + minus + var("b") + pm + root + END
    denom = bytes([1, 0]) + num("2") + var("a") + END
    frac = bytes([3, 0, 11, 0, 0]) + numer + denom + END
    stream = _mtef_header() + bytes([9, 0, 128]) + bytes([1, 0]) + frac + END + END
    res = mtef.mtef_to_latex(stream)
    assert res.latex.replace(" ", "") == "\\dfrac{-b\\pm\\sqrt{b^{2}-4ac}}{2a}"
    # tiêu đề OLE 28 byte đứng trước MTEF
    ole = (bytes([28, 0]) + bytes(26)) + stream
    assert mtef.native_to_latex(ole).latex == res.latex
    # hệ phương trình: ngoặc nhọn trái + PILE → \heva{…}
    eq1 = bytes([1, 0]) + var("x") + _mtef_char(6, 0x2B, fontpos=0x2B) + var("y") + _mtef_char(6, 0x3D, fontpos=0x3D) + num("1") + END
    eq2 = bytes([1, 0]) + var("x") + minus + var("y") + _mtef_char(6, 0x3D, fontpos=0x3D) + num("3") + END
    pile = bytes([4, 0, 1, 0]) + eq1 + eq2 + END
    brace = bytes([3, 0, 2, 1, 0]) + bytes([1, 0]) + pile + END + END           # chỉ có ngoặc trái (variation 1)
    sys_ = _mtef_header() + bytes([1, 0]) + brace + END + END
    assert mtef.mtef_to_latex(sys_).latex == "\\heva{x+y=1 \\\\ x-y=3}"
    # tích phân có cận, lim, chữ Hy Lạp
    sub = bytes([1, 0]) + num("0") + END
    sup = bytes([1, 0]) + num("1") + END
    body = bytes([1, 0]) + var("f") + _mtef_char(6, 0x28, fontpos=0x28) + var("x") + _mtef_char(6, 0x29, fontpos=0x29) + END
    integ = bytes([3, 0, 15, 1, 0]) + body + sup + sub + _mtef_char(6, 0x222B) + END
    s2 = _mtef_header() + bytes([1, 0]) + integ + _mtef_char(4, 0x03B1) + var("x") + END + END
    assert mtef.mtef_to_latex(s2).latex.replace(" ", "") == "\\int_{0}^{1}f(x)\\alphax"


def _build_ole(stream_name: str, payload: bytes) -> bytes:
    """Tệp OLE (Compound File v3) tối thiểu chứa một luồng ≥ 4096 byte (dùng thử đọc «Equation Native»)."""
    import struct
    data = payload + bytes(max(0, 4096 - len(payload)))
    nsec = (len(data) + 511) // 512
    data += bytes(nsec * 512 - len(data))
    fat = [0xFFFFFFFD, 0xFFFFFFFE] + [i + 1 for i in range(3, 2 + nsec)] + [0xFFFFFFFE]
    fat += [0xFFFFFFFF] * (128 - len(fat))

    def dirent(name, typ, child, start, size):
        nm = name.encode("utf-16-le") + b"\0\0" if name else b""
        return (nm + bytes(64 - len(nm)) + struct.pack("<H", len(nm)) + bytes([typ, 1]) +
                struct.pack("<III", 0xFFFFFFFF, 0xFFFFFFFF, child) + bytes(16) + bytes(4) + bytes(16) +
                struct.pack("<I", start) + struct.pack("<Q", size))
    entries = dirent("Root Entry", 5, 1, 0xFFFFFFFE, 0) + dirent(stream_name, 2, 0xFFFFFFFF, 2, len(data)) + \
        dirent("", 0, 0xFFFFFFFF, 0, 0) * 2
    hdr = (bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]) + bytes(16) + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) +
           bytes(6) + struct.pack("<IIIIIIIII", 0, 1, 1, 0, 4096, 0xFFFFFFFE, 0, 0xFFFFFFFE, 0) +
           struct.pack("<I", 0) + struct.pack("<108I", *([0xFFFFFFFF] * 108)))
    return hdr + struct.pack("<128I", *fat) + entries + data


def test_docx_with_mathtype_ole_equation(tmp_path):
    """File Word có công thức MathType (đối tượng OLE) được đọc thẳng sang LaTeX, không cần Word/MathType."""
    import zipfile
    from nganhangde import wordconv
    from nganhangde.docxnative import DocxOptions, docx_to_latex
    END = b"\x00"
    var = lambda c: _mtef_char(3, ord(c))
    num = lambda c: _mtef_char(8, ord(c))
    frac = bytes([3, 0, 11, 0, 0]) + bytes([1, 0]) + num("1") + END + bytes([1, 0]) + num("2") + END + END
    mtef = _mtef_header() + bytes([1, 0]) + var("x") + _mtef_char(6, 0x3D, fontpos=0x3D) + frac + END + END
    ole = _build_ole("Equation Native", bytes([28, 0]) + bytes(26) + mtef)
    ns = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
          'xmlns:o="urn:schemas-microsoft-com:office:office" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:v="urn:schemas-microsoft-com:vml"')

    def obj():
        return ('<w:r><w:object><v:shape><v:imagedata r:id="rId9"/></v:shape>'
                '<o:OLEObject Type="Embed" ProgID="Equation.DSMT4" ShapeID="s" DrawAspect="Content" r:id="rId7"/></w:object></w:r>')
    body = (f'<w:p><w:r><w:t xml:space="preserve">Câu 1. Giá trị của </w:t></w:r>{obj()}<w:r><w:t xml:space="preserve"> bằng</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>A. 1</w:t></w:r></w:p><w:p><w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>B. 2</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>C. 3</w:t></w:r></w:p><w:p><w:r><w:t>D. 4</w:t></w:r></w:p>')
    f = tmp_path / "mt.docx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {ns}><w:body>{body}</w:body></w:document>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId7" Type="x" Target="embeddings/oleObject1.bin"/></Relationships>')
        z.writestr("word/embeddings/oleObject1.bin", ole)
    tex, rep = docx_to_latex(str(f))
    assert rep.mathtype_ole == 1 and rep.mathtype_ok == 1 and rep.mathtype_fail == 0
    assert "Giá trị của $x=\\dfrac{1}{2}$ bằng" in tex.replace("$x = \\dfrac", "$x=\\dfrac")
    qs = parse_tex(wordconv.import_docx(str(f), "", DocxOptions()))
    assert len(qs) == 1 and qs[0].answer_text == "B" and "\\dfrac{1}{2}" in qs[0].stem


def test_header_mylt_template_exports(tmp_path):
    from nganhangde import appdirs
    from nganhangde.exporter import ExportOptions, export_versions
    from nganhangde.generator import ExamVersion
    from nganhangde.parser import Question
    root = str(tmp_path / "app")
    appdirs.ensure_layout(root)
    tpl = tmp_path / "app" / "TEMPLATE" / "Header_MyLT.tex"
    assert tpl.exists()
    v = ExamVersion("101")
    v.sections = {"TN": [Question("TN", "Tính $1+1$.", list("abcd"), [False, True, False, False])], "DS": [], "KQ": [], "TL": []}
    fs = export_versions([v], str(tmp_path / "o"), template_path=str(tpl),
                         options=ExportOptions(answers_xlsx=False, tltn2025=False))
    t = open([f for f in fs if f.endswith("de_101.tex")][0], encoding="utf-8").read()
    assert "{ex_test}" in t and "\\tieude{" in t and "\\begin{ex}" in t and "\\hetde" in t


def test_parse_choicetf_environment_form():
    t = ("\\begin{ex}%[0H9V1-6]\n\tXác định đúng sai\n\t\\begin{choiceTF}\n\t\t{\\True $a=1$}\n\t\t{$b=2$}\n\t\t{$c=3$}\n"
         "\t\t{\\True $d=4$}\n\t\\end{choiceTF}\n\t\\loigiai{Do đó.}\n\\end{ex}")
    q = parse_tex(t)[0]
    assert q.qtype == "DS" and q.correct == [True, False, False, True] and q.stem == "Xác định đúng sai"
    assert "\\choiceTF" in q.to_latex(True)


def test_cleanup_temp_for_update(tmp_path, monkeypatch):
    import os
    import tempfile
    from nganhangde import updater
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp))
    (tmp / "nhd_update_abc").mkdir()
    (tmp / "nhd_update_abc" / "NganHangDe_0.exe").write_bytes(b"x" * 1000)
    (tmp / "capnhat_nganhangde.bat").write_text("@echo off")
    (tmp / "_MEI123").mkdir()
    (tmp / "_MEI123" / "python312.dll").write_bytes(b"d")
    (tmp / "_MEI123" / "lib.pyd").write_bytes(b"p")
    (tmp / "khac.txt").write_text("giu")
    from nganhangde import appdirs
    tam = appdirs.folder("tam")
    os.makedirs(tam, exist_ok=True)
    open(os.path.join(tam, "rac.tex"), "w").write("x")
    res = updater.cleanup_temp()
    assert res["files"] >= 4 and res["bytes"] >= 1000
    assert (tmp / "khac.txt").exists() and not (tmp / "nhd_update_abc").exists() and not (tmp / "_MEI123").exists()
    assert not (tmp / "capnhat_nganhangde.bat").exists() and not os.path.exists(os.path.join(tam, "rac.tex"))


def test_legacy_tf_choice_and_reclassify(tmp_path):
    from nganhangde.db import Bank
    from nganhangde.parser import Question
    base = ("\\begin{ex}%[0H9V1-6]\n\tXét tính đúng sai\n\tPRE\\choice\n\t{\\True $a$}\n\t{$b$}\n\t{$c$}\n\t{\\True $d$}\n"
            "\t\\loigiai{x}\n\\end{ex}")
    for pre, cmd in (("\\TF", ""), ("\\MYLT[t]\\TF", "choiceTFt"), ("\\MyLTt\\TF", "choiceTFt"), ("\\TF\\MYLT[2]", ""),
                     ("\\MYLT[1]\\TF", "")):
        q = parse_tex(base.replace("PRE", pre))[0]
        assert q.qtype == "DS" and q.correct == [True, False, False, True] and q.choice_cmd == cmd and q.stem == "Xét tính đúng sai"
    assert parse_tex(base.replace("PRE", ""))[0].qtype == "TN"
    # kho cũ: câu đã lưu là TN (bộ nhận dạng cũ) ⇒ reclassify đổi thành DS, giữ ID/nguồn
    b = Bank(str(tmp_path / "k.db"))
    q = parse_tex(base.replace("PRE", ""))[0]
    q.raw = base.replace("PRE", "\\TF")                    # raw là khối gốc có «\TF»
    q.stem = "Xét tính đúng sai\n\\TF"
    q.id_code = "0H9V1-6"
    nid = b.add(q, "nguon.tex")
    assert b.get(nid).qtype == "TN"
    r = b.reclassify()
    assert r["doi"] == 1 and r["theo_loai"] == {"TN→DS": 1}
    g = b.get(nid)
    assert g.qtype == "DS" and g.correct == [True, False, False, True] and g.id_code == "0H9V1-6" and g.stem == "Xét tính đúng sai"
