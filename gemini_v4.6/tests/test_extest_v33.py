from nganhangde.core.idcode import parse_id
from nganhangde.core.idmap_builtin import describe_id6
from nganhangde.core.parser import parse_tex_questions

TEX_V33 = r"""
%[1D1N1-1]
\begin{ex}
Tính giá trị $\frac{1}{2}$ với \vec{AB} và \vec{a}.
\choice[2] % comment xen ke
{\True $1$}
{$2$}
{$3$}
{$4$}
\loigiai{Dùng công thức cơ bản. \textbf{Chọn A}}
\end{ex}

%[1D2H2-1]
\begin{ex}
Xét các mệnh đề:
\choiceTF[1t]
{\True $2+2=4$}
{$1>2$}
{\True $3^2=9$}
{$0=1$}
\loigiai{\begin{itemchoice}\itemch Đúng.\itemch Sai.\itemch Đúng.\itemch Sai.\end{itemchoice}}
\end{ex}

%[1H4V1-2]
\begin{ex}
Tính gần đúng. \shortans[oly]{$2{,}8$}
\loigiai{Kết quả $2{,}8$.}
\end{ex}

%[6D1N1-1]
\begin{ex}
Ghép nối hai cột:
\match{A}{1}{B}{2}
\end{ex}

%[2D4V2-1]
\begin{bt}
Giải các ý sau:
\begin{listEX}
\item Ý thứ nhất.
\item Ý thứ hai.
\end{listEX}
\dapso{$5$}
\end{bt}
"""


def test_parse_and_roundtrip_extest_v33():
    qs = parse_tex_questions(TEX_V33, auto_normalize=True)
    assert [q.qtype for q in qs] == ["TN", "DS", "KQ", "GN", "KQ"]
    assert r"\dfrac{1}{2}" in qs[0].stem and r"\overrightarrow{AB}" in qs[0].stem and r"\mathbf{a}" in qs[0].stem
    assert qs[0].cmd_opt == "2"
    assert qs[1].cmd_name == "choiceTF" and qs[1].cmd_opt == "1t"
    assert qs[2].cmd_opt == "oly" and qs[2].short_ans == "$2{,}8$"
    assert qs[3].cmd_name == "match" and len(qs[3].choices) == 4
    assert r"\begin{listEX}" in qs[4].stem and qs[4].cmd_name == "dapso"

    # Kiểm thử khứ hồi (round-trip)
    rebuilt = "\n\n".join(q.to_latex(include_solution=True) for q in qs)
    qs2 = parse_tex_questions(rebuilt)
    assert len(qs2) == len(qs)
    assert [q.qtype for q in qs2] == [q.qtype for q in qs]


def test_id6_grades_6_to_12_and_physics_mode():
    assert "Lớp 6" in describe_id6("6D1N1-1")
    assert "Lớp 9" in describe_id6("9H4H1-1")
    assert "Lớp 11" in describe_id6("1D2H2-1")
    assert "Lớp 12" in describe_id6("2D4V2-1")
    phys = parse_id("2M1T1-1", math_mode=False)
    assert phys is not None and phys.muc_do == "V" and phys.muc_do_cv7991 == "VD"
