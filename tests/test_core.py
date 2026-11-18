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
    assert len(files) == 7
    de = open(files[0], encoding="utf-8").read()
    assert "\\loigiai" not in de and "Mã đề 101" in de


def test_not_enough(bank):
    with pytest.raises(NotEnoughQuestions):
        make_versions(bank, [Rule("TN", 50)], 1)
