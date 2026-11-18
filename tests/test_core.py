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
    assert len(files) == 8
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
