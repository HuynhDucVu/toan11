import os
import random

import pytest

from nganhangde.db import Bank
from nganhangde.exporter import export_versions
from nganhangde.generator import NotEnoughQuestions, Rule, make_versions, shuffle_choices
from nganhangde.idcode import parse_id
from nganhangde.parser import parse_file, parse_tex, validate

ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE = os.path.join(ROOT, "0-1-De-chuan-hoa-1.tex")


@pytest.fixture
def bank(tmp_path):
    b = Bank(str(tmp_path / "t.db"))
    for q in parse_file(SAMPLE):
        b.add(q)
    yield b
    b.close()


def test_idcode():
    c = parse_id("[0D2N1-2]")
    assert (c.lop, c.mon, c.chuong, c.muc_do, c.bai, c.dang) == ("0", "D", "2", "N", "1", "2")
    assert parse_id("2H3Y4-5").muc_do == "N"       # Y = nhận biết (kiểu ID cũ)
    assert parse_id("De-chuan-hoa") is None


def test_parse_sample():
    qs = parse_file(SAMPLE)
    assert [q.qtype for q in qs].count("TN") == 12
    assert [q.qtype for q in qs].count("DS") == 4
    assert [q.qtype for q in qs].count("KQ") == 6
    assert qs[0].answer_text == "D" and qs[0].id_code == "0D2N1-2"
    assert qs[12].answer_text == "ĐSĐS"
    assert qs[16].short_answer == "$12$"
    assert all(not validate(q) for q in qs)


def test_nested_braces_and_escapes():
    tex = r"""\begin{ex}%[0D1N1-1]
    Tính $\{1;2\}$ và 50\% {nhóm {lồng}}
    \choice{$\frac{1}{2}$}{\True $\left\{x\right\}$}{c}{d}
    \loigiai{Lời giải {có ngoặc}}
\end{ex}"""
    q = parse_tex(tex)[0]
    assert q.choices[0] == r"$\frac{1}{2}$"
    assert q.correct == [False, True, False, False]
    assert q.solution == "Lời giải {có ngoặc}"
    # dựng lại rồi đọc lại phải ra cùng câu
    q2 = parse_tex(q.to_latex())[0]
    assert (q2.choices, q2.correct, q2.solution.strip()) == (q.choices, q.correct, q.solution)


def test_duplicate_detection(bank):
    q = parse_file(SAMPLE)[0]
    assert bank.add(q) is None
    assert bank.count() == 22


def test_search(bank):
    assert len(bank.search(id_like="0H9*")) == 9
    assert all(q.qtype == "KQ" for q in bank.search(qtype="KQ"))
    assert len(bank.search(muc_do="V")) == 5


def test_shuffle_keeps_answer():
    rng = random.Random(0)
    for q in parse_file(SAMPLE):
        if q.qtype not in ("TN", "DS"):
            continue
        right = {c for c, ok in zip(q.choices, q.correct) if ok}
        for _ in range(5):
            s = shuffle_choices(q, rng)
            assert {c for c, ok in zip(s.choices, s.correct) if ok} == right
            if q.qtype == "DS":  # lời giải từng ý phải đi theo ý
                items = s.solution.split("\\itemch")[1:]
                assert [it.strip().startswith("Đúng") for it in items] == s.correct


def test_make_versions_and_export(bank, tmp_path):
    rules = [Rule("TN", 6, "0H9*"), Rule("DS", 2), Rule("KQ", 3, muc_do="V")]
    vs = make_versions(bank, rules, 3, seed=1)
    assert [v.code for v in vs] == ["101", "102", "103"]
    ids = [sorted(q.db_id for q in v.all_questions()) for v in vs]
    assert ids[0] == ids[1] == ids[2] and len(ids[0]) == 11
    files = export_versions(vs, str(tmp_path / "out"))
    assert len(files) == 9 and files[-1].endswith("dap_an_TNMaker.xlsx")
    de = open(files[0], encoding="utf-8").read()
    assert "\\loigiai" not in de and "Mã đề 101" in de


def test_not_enough(bank):
    with pytest.raises(NotEnoughQuestions):
        make_versions(bank, [Rule("TN", 50)], 1)


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


def test_balance_and_options(bank):
    from nganhangde.generator import MixOptions, answer_distribution, overlap_report
    rules = [Rule("TN", 12), Rule("DS", 4)]
    vs = make_versions(bank, rules, 4, seed=3, options=MixOptions(balance=True))
    for v in vs:
        d = answer_distribution(v)
        assert max(d.values()) - min(d.values()) <= 1          # 12 câu ⇒ mỗi chữ 3 câu
    assert all(r == 1.0 for _, _, r in overlap_report(vs))       # cùng bộ câu
    # không trộn ý Đúng/Sai ⇒ đáp án DS giữ nguyên như gốc
    orig = {q.fingerprint: q.answer_text for q in bank.search(qtype="DS")}
    vs = make_versions(bank, rules, 2, seed=1, options=MixOptions(shuffle_ds=False))
    assert all(orig[q.fingerprint] == q.answer_text for v in vs for q in v.sections["DS"])
    # đề gốc giữ nguyên thứ tự phương án
    vs = make_versions(bank, rules, 2, seed=1, options=MixOptions(first_original=True))
    assert all(q.answer_text == bank.get(q.db_id).answer_text for q in vs[0].all_questions())


def test_matrix_from_exam(bank):
    from nganhangde.generator import matrix_from_questions
    rules = matrix_from_questions(parse_file(SAMPLE), "bai")
    assert sum(r.count for r in rules) == 22
    vs = make_versions(bank, rules, 1, seed=0)                    # kho đủ câu để dựng lại
    assert len(list(vs[0].all_questions())) == 22


def test_bank_extras(bank, tmp_path):
    from nganhangde.idmap import parse_map_text
    bank.set_idmap(parse_map_text("0D2 = Chương 2\n[0D21] Bài 1\n0D21-2: Dạng 2\n# chú thích"))
    assert bank.id_names("0D2N1-2") == ["Chương 2", "Bài 1", "Dạng 2"]
    q = bank.search(id_like="0D2N1-2")[0]
    assert len(bank.similar(q)) == 1
    bank.backup(str(tmp_path / "bk.db"))
    other = Bank(str(tmp_path / "khac.db"))
    assert other.merge_from(str(tmp_path / "bk.db")) == (22, 0)
    assert other.idmap()["0D2"] == "Chương 2"
    other.close()
    assert bank.export_subset([1, 2, 3], str(tmp_path / "tach.db")) == 3


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


BAD = r"""\begin{ex}%[0D1N1-1]
    Câu TN ghi chọn lệch.
    \choice{$1$}{\True $2$}{$3$}{$4$}
    \loigiai{Tính được kết quả. Chọn đáp án C.}
\end{ex}
\begin{ex}%[0D1N1-2]
    Câu TN có hai phương án giống nhau và hai True.
    \choice{\True $\dfrac{1}{2}$}{$\frac12$}{\True $3$}{$4$}
    \loigiai{x}
\end{ex}
\begin{ex}%[0D1H1-1]
    Câu đúng sai lệch lời giải.
    \choiceTF[t]{\True a}{b}{\True c}{d}
    \loigiai{\begin{itemchoice}
        \itemch Đúng. x
        \itemch Đúng. y
        \itemch Đúng. z
        \itemch Sai. t
    \end{itemchoice}}
\end{ex}
\begin{ex}%[0D1V1-1]
    Trả lời ngắn không phải số $x+1$.
    \shortans[oly]{$x+1$}
    \loigiai{Ta có \begin{itemize} \item a \end{enumerate}}
\end{ex}
\begin{ex}
    Thiếu ngoặc { và lẻ dấu $ đô la.
    \shortans[oly]{$12345$}
    \loigiai{Kết quả $12345$.}
\end{ex}
"""


def test_review():
    from nganhangde.review import LOI, review_question, worst, remove_questions_text
    qs = parse_tex(BAD)
    codes = [{i.code for i in review_question(q)} for q in qs]
    assert "chon_lech" in codes[0]
    assert {"so_true", "pa_trung"} <= codes[1]
    assert "ds_lech" in codes[2]
    msg = [i.msg for i in review_question(qs[2]) if i.code == "ds_lech"][0]
    assert "Ý b" in msg
    assert {"kq_so", "env"} <= codes[3]
    assert {"id", "ngoac", "dola", "kq_dai"} <= codes[4]
    assert all(worst(review_question(q)) == LOI for q in qs)
    text, n = remove_questions_text(BAD, [qs[0].raw, qs[2].raw])
    assert n == 2 and len(parse_tex(text)) == 3
    # đề mẫu: không có lỗi nặng
    assert all(worst(review_question(q)) != LOI for q in parse_file(SAMPLE))


def test_fix_and_conclusion():
    from nganhangde import review as rv
    qs = parse_tex(BAD)
    f, done = rv.fix_question(qs[0], rv.THEO_LOI_GIAI)
    assert f.answer_text == "C" and done and rv.worst(rv.review_question(f)) != rv.LOI
    f, done = rv.fix_question(qs[0], rv.THEO_DAP_AN)
    assert f.answer_text == "B" and "Chọn đáp án B" in f.solution
    f, _ = rv.fix_question(qs[2], rv.THEO_LOI_GIAI)
    assert f.answer_text == "ĐĐĐS"
    f, _ = rv.fix_question(qs[2], rv.THEO_DAP_AN)
    assert f.answer_text == "ĐSĐS" and "\\itemch Sai. y" in f.solution
    f, done = rv.fix_question(qs[1])          # 2 \True, không có «Chọn» ⇒ không tự sửa được
    assert not done
    kq = parse_tex(r"\begin{ex}%[0D1V1-1]" "\nTính.\n\\shortans[oly]{$0.5$}\n\\loigiai{Ta có $0{,}5$.}\n\\end{ex}")[0]
    f, done = rv.fix_question(kq)
    assert f.short_answer == "$0{,}5$" and not rv.review_question(f)
    q = parse_file(SAMPLE)[17]
    f, ok = rv.add_conclusion(q)
    assert ok and not rv.review_question(f)
    text, n = rv.replace_questions_text(BAD, [(qs[0].raw, rv.fix_question(qs[0])[0].to_latex())])
    assert n == 1 and parse_tex(text)[0].answer_text == "C"


def test_shuffle_updates_chon_letter():
    import random
    from nganhangde.generator import shuffle_choices
    from nganhangde import review as rv
    q = parse_tex(r"\begin{ex}%[0D1N1-1]" "\nX\n\\choice{1}{\\True 2}{3}{4}\n\\loigiai{Vậy chọn. Chọn đáp án B.}\n\\end{ex}")[0]
    for s in range(10):
        m = shuffle_choices(q, random.Random(s))
        assert not [i for i in rv.review_question(m) if i.code == "chon_lech"]
        assert f"Chọn đáp án {m.answer_text}" in m.solution


DASH_MAP = """%
% Map ID mẫu
[N] Nhận biết
[V] Vận dụng
-[0] Lớp 10
----[D] Đại số 10
-------[8] Đại số tổ hợp
----------[3] Nhị thức Newton
-------------[2] Khai triển một nhị thức
-------------[4] Tìm hệ số, số hạng trong khai triển
----[H] Hình học 10
-------[9] Phương pháp toạ độ trong mặt phẳng
----------[4] Đường tròn trong mặt phẳng toạ độ
-------------[1] Xác định tâm và bán kính của đường tròn
-------------[1] Dòng trùng mã
----------[5] Ba đường conic
-------------[3] Elip: tiêu cự, trục lớn, trục bé
"""


def test_idmap_dash_format():
    from nganhangde.idmap import parse_map_text, to_dash_text, dash_duplicates, IdTree
    m = parse_map_text(DASH_MAP)
    assert m["0D8"] == "Đại số tổ hợp" and m["0H94-1"] == "Xác định tâm và bán kính của đường tròn"
    assert m["#V"] == "Vận dụng"
    assert dash_duplicates(DASH_MAP) == [("0H94-1", "Xác định tâm và bán kính của đường tròn", "Dòng trùng mã")]
    assert parse_map_text(to_dash_text(m)) == m
    t = IdTree(m)
    assert [c for c, _ in t.children(["0"])] == ["D", "H"]
    assert t.children(["0", "H", "9", "4"]) == [("1", "Xác định tâm và bán kính của đường tròn")]


def test_set_id_and_suggest():
    from nganhangde.idmap import parse_map_text
    from nganhangde.idsuggest import MapSuggester, Suggester
    qs = parse_file(SAMPLE)
    q = qs[0]
    q.set_id("0D7N2-1")
    assert q.raw.splitlines()[0].endswith("%[0D7N2-1]") and "0D2N1-2" not in q.raw.splitlines()[0]
    assert parse_tex(q.raw)[0].id_code == "0D7N2-1"
    blank = parse_tex(r"\begin{ex}%[Nguồn]" "\nCâu không ID\n\\choice{\\True a}{b}{c}{d}\n\\end{ex}")[0]
    blank.set_id("0D1N1-1")
    assert parse_tex(blank.raw)[0].id_code == "0D1N1-1" and "Nguồn" in parse_tex(blank.raw)[0].tags
    # gợi ý theo Map ID
    ms = MapSuggester(parse_map_text(DASH_MAP), "0")
    circle = parse_file(SAMPLE)[2]                       # «Cho đường tròn … có tâm I và bán kính»
    assert ms.suggest(circle, "N")[0].id_code == "0H9N4-1"
    newton = parse_file(SAMPLE)[11]                      # «Viết khai triển … nhị thức Niu-tơn»
    assert ms.suggest(newton, "H")[0].id_code.startswith("0D8H3")
    # gợi ý theo câu giống trong kho
    qs = parse_file(SAMPLE)
    for i, x in enumerate(qs):
        x.db_id = i
    s = Suggester(qs[1:]).suggest(qs[0])
    assert s[0].id_code == "0D2N1-2" and s[0].score > 0.5


def test_thpt2026_options_and_tnmaker(bank, tmp_path):
    from openpyxl import load_workbook
    from nganhangde.exporter import ExportOptions
    from nganhangde.generator import (MixOptions, THPT_2026, check_structure, make_codes)
    codes = make_codes(24, 101, 4)
    assert codes[0] == "0101" and codes[-1] == "0124" and len(set(make_codes(24, digits=3, randomize=True))) == 24
    rules = [Rule("TN", 12), Rule("DS", 4), Rule("KQ", 6)]
    assert check_structure(rules) == [] and check_structure([Rule("TN", 10)])
    assert THPT_2026["so_ma"] == 24
    vs = make_versions(bank, rules, codes=codes[:3], seed=4, options=MixOptions(shuffle_ds=False))
    opt = ExportOptions(renumber=True, official_titles=True, scoring=True, ds_style="tach", ds_symbols="TF")
    files = export_versions(vs, str(tmp_path / "o"), options=opt)
    de = open(files[0], encoding="utf-8").read()
    assert de.count("\\setcounter{ex}{0}") == 3
    assert "Thí sinh trả lời từ câu 1 đến câu 12" in de and "từ câu 1 đến câu 4" in de and "đến câu 6" in de
    lg = open(files[1], encoding="utf-8").read()
    assert "Thang điểm" in lg and "Tổng điểm phần trắc nghiệm: 10 điểm" in lg
    wb = load_workbook(files[-1])
    ws = wb["Đáp án"]
    rows = list(ws.values)
    assert rows[0] == ("Câu", "0101", "0102", "0103")
    labels = [r[0] for r in rows[1:]]
    assert labels[:2] == ["I.1", "I.2"] and "II.1a" in labels and labels[-1] == "III.6"
    assert len(labels) == 12 + 16 + 6
    v = vs[0]
    i = labels.index("II.2c") + 1
    assert rows[i][1] == ("T" if v.sections["DS"][1].correct[2] else "F")
    assert rows[labels.index("I.1") + 1][1] == v.sections["TN"][0].answer_text
    assert "$" not in "".join(str(r[1]) for r in rows[1:])
    # bố cục ngang
    files = export_versions(vs, str(tmp_path / "n"), options=ExportOptions(tnmaker_layout="ngang"))
    rows = list(load_workbook(files[-1])["Đáp án"].values)
    assert rows[0][0] == "Mã đề" and rows[1][0] == "0101" and len(rows[0]) == 1 + 12 + 4 + 6


def test_batch1_features(bank, tmp_path):
    from nganhangde import tools
    from nganhangde.exporter import ExportOptions, matrix_spec
    from nganhangde.generator import MixOptions, replacement_pool, level_rank, pick_questions
    import random
    # xếp câu dễ → khó
    vs = make_versions(bank, [Rule("TN", 12)], 2, seed=1, options=MixOptions(sort_by_level=True))
    for v in vs:
        ranks = [level_rank(q) for q in v.sections["TN"]]
        assert ranks == sorted(ranks)
    # giới hạn tỉ lệ trùng khi mỗi mã một bộ câu
    vs = make_versions(bank, [Rule("TN", 3, "0H9*")], 2, seed=2, same_questions=False, max_overlap=0.34)
    a, b = ({q.db_id for q in v.all_questions()} for v in vs)
    assert len(a & b) <= 1
    with pytest.raises(NotEnoughQuestions):
        make_versions(bank, [Rule("TN", 6, "0H9*")], 2, seed=2, same_questions=False, max_overlap=0.0)
    # đổi câu: kho thay thế cùng dòng ma trận, không trùng câu đã chọn
    rules = [Rule("TN", 2, "0H9*"), Rule("KQ", 2)]
    picked = pick_questions(bank, rules, random.Random(0))
    used = {q.db_id for qs in picked.values() for q in qs}
    q = picked["TN"][0]
    pool = replacement_pool(bank, rules, q, used)
    assert pool and all(x.id_code.startswith("0H9") and x.qtype == "TN" and x.db_id not in used for x in pool)
    sec = {k: list(v) for k, v in picked.items()}
    sec["TN"][0] = pool[0]
    vs = make_versions(bank, rules, codes=["1", "2"], sections=sec)
    assert pool[0].db_id in {x.db_id for x in vs[0].all_questions()}
    # thông tin đầu đề, in ID, zip, ma trận đặc tả
    opt = ExportOptions(show_id=True, make_zip=True, header={"KY_THI": "KIỂM TRA CUỐI KÌ II", "MON_THI": "TOÁN 10"})
    files = export_versions(vs, str(tmp_path / "o"), options=opt, truong="THPT ABC")
    de, lg = (open(f, encoding="utf-8").read() for f in files[:2])
    assert "KIỂM TRA CUỐI KÌ II" in de and "TOÁN 10" in de and "<<" not in de
    assert "\\scriptsize[" in lg and "\\scriptsize[" not in de
    assert files[-1].endswith(".zip")
    p = matrix_spec(bank, rules, str(tmp_path / "mt.xlsx"))
    from openpyxl import load_workbook
    rows = list(load_workbook(p).active.values)
    assert rows[1][1] == "0H9*" and rows[-1][4] == 4
    assert "MA TRẬN" in open(matrix_spec(bank, rules, str(tmp_path / "mt.tex")), encoding="utf-8").read()
    # lịch sử sửa + khôi phục, thay thế hàng loạt, lọc theo nguồn
    q = bank.get(1)
    n = bank.replace_text("tập nghiệm", "TẬP NGHIỆM")
    assert n == 2 and "TẬP NGHIỆM" in bank.get(1).stem
    h = bank.history(1)
    assert h and h[0]["action"] == "thay thế"
    bank.restore(h[0]["hid"])
    assert bank.get(1).stem == q.stem
    bank.delete([2])
    assert bank.get(2) is None
    bank.restore(bank.history(2)[0]["hid"])
    assert bank.search(text="Xét vị trí tương đối")
    assert len(bank.search(tag="Hoài Nam")) == 22
    # công cụ file
    text = open(SAMPLE, encoding="utf-8").read()
    t2, k = tools.remove_ids_text(text)
    assert k == 22 and all(not x.id_code for x in parse_tex(t2))
    t3, k = tools.remove_tag_text(text, "De-chuan-hoa-so-3")
    assert k == 22 and all("De-chuan-hoa-so-3" not in x.tags for x in parse_tex(t3))
    t4, k = tools.replace_text(text, "\\dfrac", "\\frac")
    assert k > 0 and "\\dfrac" not in "".join(x.raw for x in parse_tex(t4))
    assert tools.filter_by_tag([SAMPLE], "hoài nam", str(tmp_path / "tag.tex")) == 22
    assert tools.near_duplicates(parse_file(SAMPLE), 0.7)[0][:2] == (0, 4)
    tz = tmp_path / "tz.tex"
    tz.write_text("\\begin{ex}%[0H1N1-1]\nHình\n\\begin{tikzpicture}\\draw (0,0)--(1,1);\\end{tikzpicture}\n"
                  "\\choice{\\True a}{b}{c}{d}\n\\end{ex}\n", encoding="utf-8")
    fs = tools.extract_tikz([str(tz)], str(tmp_path / "hinh"))
    assert len(fs) == 1 and "standalone" in open(fs[0], encoding="utf-8").read()


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


def test_pdfbuild(bank, tmp_path):
    from nganhangde import pdfbuild as pb
    try:
        eng = pb.find_engine("pdflatex")
    except pb.EngineMissing:
        pytest.skip("máy chưa có LaTeX")
    from nganhangde.exporter import ExportOptions
    vs = make_versions(bank, [Rule("TN", 12), Rule("DS", 4), Rule("KQ", 6)], codes=["101"], seed=1)
    files = export_versions(vs, str(tmp_path / "o"), options=ExportOptions(renumber=True, official_titles=True,
                            scoring=True), truong="THPT ABC")
    for f in files[:2]:
        r = pb.compile_tex(f, eng)
        assert r.ok and r.pdf and os.path.getsize(r.pdf) > 10000, r.errors
        assert not os.path.exists(f.replace(".tex", ".aux"))          # đã dọn file phụ
    assert not os.path.exists(str(tmp_path / "o" / "ex_test.sty"))   # gói rút gọn chỉ chép tạm
    # lỗi được đọc thành câu dễ hiểu, có số dòng
    bad = tmp_path / "loi.tex"
    bad.write_text("\\documentclass{article}\n\\begin{document}\nA\n\\lenhsai{x}\n$x^2\n\\end{document}\n",
                   encoding="utf-8")
    r = pb.compile_tex(str(bad), eng)
    assert not r.ok and r.errors[0].startswith("Dòng 4:") and "lệnh không tồn tại" in r.errors[0]
    assert os.path.exists(str(tmp_path / "loi.log"))                    # lỗi ⇒ giữ .log để xem
    # xem trước 1 câu
    r = pb.preview_questions([bank.get(13)], engine=eng, out_dir=str(tmp_path / "xt"))
    assert r.ok and r.pdf
    errs, _ = pb.parse_log("! Undefined control sequence.\nl.12 \\foo\n! Missing $ inserted.\nl.20 x^2\n")
    assert errs == ["Dòng 12: Undefined control sequence. – lệnh không tồn tại (gõ sai tên lệnh hoặc thiếu gói)",
                    "Dòng 20: Missing $ inserted. – thiếu dấu $ (công thức chưa đóng/mở đúng)"]
