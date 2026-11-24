"""Giai đoạn 3 – Draw Studio."""
import shutil
import subprocess

import pytest

from nganhangde import drawstudio as ds


def test_parse_set_and_numline():
    ivs, pts = ds.parse_set("(-inf;-2] ∪ [1/2;3) U {5}")
    assert ivs[0][1] == -2 and ivs[0][3] is True and ivs[1][0] == 0.5 and ivs[1][2] is True and pts == [5]
    code = ds.number_line_tikz("(-inf;-2] U (1;3)")
    assert "$]$" in code and "$($" in code and "$)$" in code
    with pytest.raises(ds.FuncError):
        ds.parse_set("(3;1)")


def test_region_vertices_optimize():
    sys_ = ["x>=0", "y>=0", "x+y<=4", "x+2y<=6"]
    v = {(round(x, 6) + 0.0, round(y, 6) + 0.0) for x, y in ds.vertices(sys_)}
    assert v == {(0, 0), (4, 0), (2, 2), (0, 3)}
    rows, lo, hi = ds.optimize(sys_, "3x + 2y")
    assert (lo, hi) == (0, 12)
    assert ds.parse_ineq("2x - y > -1") == (-2.0, 1.0, -1.0, True)
    with pytest.raises(ds.FuncError):
        ds.parse_ineq("x^2 + y <= 1")
    code = ds.region_tikz(sys_)
    assert "gray!35" in code and "x+y=4" in code


def test_asymptotes_and_shading():
    assert ds.asymptotes("(x^2+1)/(x-1)") == ([1.0], [(1.0, 1.0)])
    assert ds.asymptotes("(2x+1)/(x-1)") == ([1.0], [(0.0, 2.0)])
    assert ds.asymptotes("x^3 - 3x") == ([], [])
    code = ds.graph_plus_tikz("x^2", -1, 3, -1, 5, shade=(0, 2), expr2="2x")
    assert "blue!20" in code and "red,smooth" in code
    assert code.index("\\clip") < code.index("blue!20")


@pytest.mark.parametrize("kind", list(ds.SOLIDS))
def test_solids(kind):
    code = ds.solid_tikz(kind)
    assert code.startswith("\\begin{tikzpicture}") and code.endswith("\\end{tikzpicture}")


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="cần pdflatex")
def test_all_compile(tmp_path):
    parts = [ds.number_line_tikz("(-inf;-2] U (1;3) U {5}"), ds.region_tikz(["x>=0", "y>=0", "x+y<=4"]),
             ds.graph_plus_tikz("(x^2+1)/(x-1)", -4, 5, -5, 8), ds.graph_plus_tikz("x^2", -1, 3, -1, 5, shade=(0, 2))]
    parts += [ds.solid_tikz(k) for k in ds.SOLIDS]
    tex = tmp_path / "t.tex"
    tex.write_text("\\documentclass{article}\\usepackage{tikz}\\begin{document}" + "\n\n".join(parts) +
                   "\\end{document}", encoding="utf-8")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name], cwd=tmp_path,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:]
