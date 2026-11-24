"""Đọc ID, tách câu, cơ sở dữ liệu."""
from nganhangde.db import Bank
from nganhangde.idcode import parse_id
from nganhangde.parser import parse_file, parse_tex, validate
from conftest import SAMPLE


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
