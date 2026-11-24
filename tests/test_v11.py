"""Kiểm thử giai đoạn 1 (theo tài liệu nâng cấp): ex_test v3.3, di trú CSDL, FTS5 không dấu, lịch sử ra đề."""
import json
import os
import sqlite3

from nganhangde.db import SCHEMA, Bank
from nganhangde.parser import parse_tex

V33 = r"""\begin{ex}%[0D1H1-1]
    Xét tính đúng sai (bảng): \begin{listEX}\item ý phụ\end{listEX}
    \choiceTFt[2t]
    {\True Mệnh đề a}{Mệnh đề b}{\True Mệnh đề $c$}{Mệnh đề d}
    \loigiai{\begin{itemchoice}\itemch Đúng. x\itemch Sai. y\itemch Đúng. z\itemch Sai. t\end{itemchoice}}
\end{ex}
\begin{ex}%[0D1V1-2]
    Tính $x$. % chú thích {lệch ngoặc} không ảnh hưởng
    \dapso{$2{,}8$}
\end{ex}
\begin{ex}%[0D1V1-3]
    Tính $y$.
    \shortans[0]{$-4$}
\end{ex}
\begin{ex}%[0D1N1-4]
    Chọn đáp án đúng
    \choice[2]
    {$\dfrac{1}{2}$}{\True $\left\{x\right\}$}{c}{d}
\end{ex}
"""


def test_extest_v33_roundtrip():
    qs = parse_tex(V33)
    assert [q.qtype for q in qs] == ["DS", "KQ", "KQ", "TN"]
    assert qs[0].choice_cmd == "choiceTFt" and qs[0].choice_opt == "2t" and qs[0].answer_text == "ĐSĐS"
    assert qs[1].choice_cmd == "dapso" and qs[1].short_answer == "$2{,}8$"
    assert qs[2].choice_opt == "0" and qs[2].short_answer == "$-4$"
    assert qs[3].choice_opt == "2" and qs[3].answer_text == "B"
    for q in qs:                                   # dựng lại rồi đọc lại phải y hệt
        r = parse_tex(q.to_latex())[0]
        assert (r.qtype, r.choices, r.correct, r.short_answer, r.choice_opt, r.choice_cmd, r.solution.strip()) == \
               (q.qtype, q.choices, q.correct, q.short_answer, q.choice_opt, q.choice_cmd, q.solution.strip())
    assert "\\choiceTFt[2t]" in qs[0].to_latex() and "\\dapso{$2{,}8$}" in qs[1].to_latex()
    assert "listEX" in qs[0].stem


def _old_v1_db(path):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA.split("CREATE TABLE IF NOT EXISTS history")[0])   # lược đồ bản ≤ 0.10
    con.execute("INSERT INTO questions(qtype, id_code, stem, choices, correct, tags, fingerprint, raw) "
                "VALUES ('TN','0D2N1-2','Bất phương trình $x^2<1$ có tập nghiệm là',?,?,?, 'fp1', '')",
                (json.dumps(["a", "b", "c", "d"]), json.dumps([True, False, False, False]), json.dumps(["Đề A"])))
    con.commit()
    con.close()


def test_migration_fts_and_batches(tmp_path):
    p = str(tmp_path / "cu.db")
    _old_v1_db(p)
    b = Bank(p)
    assert b.migrated_from == 1 and os.path.exists(p + ".bak")
    assert b.con.execute("PRAGMA user_version").fetchone()[0] == 2
    assert b.count() == 1
    assert b.search(text="bat phuong trinh") and b.search(text="Bất PHƯƠNG") and b.search(text="tap nghiem")
    assert not b.search(text="hình chóp")
    q = b.get(1)
    q.stem = "Cho hình chóp S.ABCD"
    b.update(1, q)
    assert b.search(text="hinh chop") and not b.search(text="bat phuong")       # chỉ mục đồng bộ khi sửa
    b.delete([1])
    assert not b.search(text="hinh chop")                                         # và khi xoá
    b.close()
    b2 = Bank(p)                                                                  # mở lại: không di trú lần nữa
    assert b2.migrated_from is None
    from nganhangde.parser import parse_file
    sample = os.path.join(os.path.dirname(__file__), "..", "0-1-De-chuan-hoa-1.tex")
    for x in parse_file(sample):
        b2.add(x)
    from nganhangde.generator import Rule, make_versions
    vs = make_versions(b2, [Rule("TN", 4)], codes=["101", "102"], seed=1)
    bid = b2.log_batch(vs, ten_de="Thử", seed=1, matrix=[{"qtype": "TN", "count": 4}], out_dir="x")
    assert b2.batches()[0]["id"] == bid and b2.batches()[0]["n"] == 4
    assert b2.recent_question_ids() == {q.db_id for q in vs[0].all_questions()}


def test_cv1239_rules_and_lock(tmp_path):
    from nganhangde import review as rv
    from nganhangde.generator import LOCK_RE
    def codes(tex, base=None):
        return {i.code for i in rv.review_question(parse_tex(tex)[0], base)}
    kq = "\\begin{{ex}}%[0D1V1-1]\nTính.\n\\shortans{{{a}}}\n\\loigiai{{x {a}}}\n\\end{{ex}}"
    assert "kq_phanso" in codes(kq.format(a="$\\dfrac{1}{2}$")) and "kq_phanso" in codes(kq.format(a="1/2"))
    assert "kq_dai" in codes(kq.format(a="$-12{,}5$"))                          # 5 kí tự > 4 ô
    assert rv.worst(rv.review_question(parse_tex(kq.format(a="$-12{,}5$"))[0])) == rv.LOI
    assert "kq_so" in codes(kq.format(a="12 cm"))
    assert not ({"kq_dai", "kq_so", "kq_phanso"} & codes(kq.format(a="$-1{,}5$")))
    ds = "\\begin{ex}%[0D1H1-1]\nX\n\\choiceTF{\\True a}{\\True b}{\\True c}{\\True d}\n\\end{ex}"
    assert "ds_dong_nhat" in codes(ds)
    img = "\\begin{ex}%[0D1N1-1]\nHình \\includegraphics[width=3cm]{hinh1}\n\\choice{\\True a}{b}{c}{d}\n\\end{ex}"
    assert "anh" in codes(img, str(tmp_path))
    (tmp_path / "hinh1.png").write_bytes(b"x")
    assert "anh" not in codes(img, str(tmp_path))
    for t in ("Cả A và B đều đúng", "Đáp án khác", "Các phương án trên đều sai", "A, B đúng", "Tất cả đều sai"):
        assert LOCK_RE.search(t), t
    for t in ("$x=2$", "Hàm số đồng biến", "Bảng A"):
        assert not LOCK_RE.search(t), t


def test_builtin_idmap_and_html():
    from nganhangde.idmap import builtin_map, to_html
    m = builtin_map()
    assert len(m) > 1000 and m["0"] == "Lớp 10" and "0H94" in m
    h = to_html({"0": "Lớp 10", "0H": "Hình học", "0H9": "Toạ độ", "0H94": "Đường tròn", "0H94-1": "Tâm, bán kính",
                 "#N": "Nhận biết"})
    assert "0H94-1" in h and "duong tron" in h and "<input" in h
