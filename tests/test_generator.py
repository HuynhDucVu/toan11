"""Chọn câu, trộn đề, xuất đề, chuẩn 2026."""
import random

import pytest

from nganhangde.exporter import export_versions
from nganhangde.generator import NotEnoughQuestions, Rule, make_versions, shuffle_choices
from nganhangde.parser import parse_file, parse_tex
from conftest import SAMPLE


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
    assert len(files) == 13 and any(f.endswith("dap_an_TNMaker.xlsx") for f in files)      # + phiếu TLTN 2025 (trắng + 3 phiếu khoá)
    de = open(files[0], encoding="utf-8").read()
    assert "\\loigiai" not in de and "Mã đề 101" in de


def test_not_enough(bank):
    with pytest.raises(NotEnoughQuestions):
        make_versions(bank, [Rule("TN", 50)], 1)


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


def test_shuffle_updates_chon_letter():
    import random
    from nganhangde.generator import shuffle_choices
    from nganhangde import review as rv
    q = parse_tex(r"\begin{ex}%[0D1N1-1]" "\nX\n\\choice{1}{\\True 2}{3}{4}\n\\loigiai{Vậy chọn. Chọn đáp án B.}\n\\end{ex}")[0]
    for s in range(10):
        m = shuffle_choices(q, random.Random(s))
        assert not [i for i in rv.review_question(m) if i.code == "chon_lech"]
        assert f"Chọn đáp án {m.answer_text}" in m.solution


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
    opt = ExportOptions(renumber=True, official_titles=True, scoring=True, ds_style="tach", ds_symbols="TF", tnmaker_layout="doc")
    files = export_versions(vs, str(tmp_path / "o"), options=opt)
    de = open(files[0], encoding="utf-8").read()
    assert de.count("\\setcounter{ex}{0}") == 3
    assert "Thí sinh trả lời từ câu 1 đến câu 12" in de and "từ câu 1 đến câu 4" in de and "đến câu 6" in de
    lg = open(files[1], encoding="utf-8").read()
    assert "Thang điểm" in lg and "Tổng điểm toàn bài: 10 điểm" in lg
    wb = load_workbook([f for f in files if f.endswith("dap_an_TNMaker.xlsx")][0])
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
    rows = list(load_workbook([f for f in files if f.endswith("dap_an_TNMaker.xlsx")][0])["Đáp án"].values)
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
