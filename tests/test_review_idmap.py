"""Rà soát đáp án – lời giải, Map ID, gán ID."""
from nganhangde.parser import parse_file, parse_tex
from conftest import SAMPLE


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
