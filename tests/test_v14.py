"""Giai đoạn 4: phòng thi LAN, Google Forms (Apps Script), Moodle (ảnh, graderinfo), trình chiếu, cây dữ liệu."""
import json
import random
import urllib.request

from nganhangde.generator import MixOptions, mix_versions, sections_from_questions
from nganhangde.parser import parse_file, parse_tex

from conftest import SAMPLE


def _versions(codes=("101", "102")):
    return mix_versions(sections_from_questions(parse_file(SAMPLE)), list(codes), random.Random(3), MixOptions())


def test_grade_answers_matches_rules():
    from nganhangde.online import answer_key, grade_answers
    v = _versions(["101"])[0]
    key = answer_key(v)
    perfect = {k: (list(x) if isinstance(x, list) else x) for k, x in key.items()}
    total, mx, _ = grade_answers(v, perfect)
    assert total == mx == 10.0
    ds = next(k for k in key if k.startswith("DS"))
    half = dict(perfect)
    half[ds] = [x if i < 2 else (not x) for i, x in enumerate(key[ds])]       # đúng 2/4 ý
    t2, _, per = grade_answers(v, half)
    assert per[ds] == 0.25 and abs(t2 - (10 - 0.75)) < 1e-9
    kq = next(k for k in key if k.startswith("KQ"))
    assert grade_answers(v, {kq: " " + key[kq].replace(",", ".") + " "})[2][kq] == 0.5


def test_arena_http_roundtrip(tmp_path):
    from nganhangde.arena import Arena
    a = Arena(_versions(), ten_de="KT", thoi_gian=10, host="127.0.0.1", port=0)
    url = a.start()
    try:
        assert "Vào làm bài" in urllib.request.urlopen(url).read().decode()
        r = urllib.request.urlopen(url + "vao?ten=An")
        assert "/de/101/" in r.geturl()
        page = r.read().decode()
        assert 'DATA=""' in page and "ARENA=true" in page and "/mathjax.js" in page
        assert len(urllib.request.urlopen(url + "mathjax.js").read()) > 1_000_000
        req = urllib.request.Request(url + "de/101/nop", data=json.dumps(
            {"ma": "101", "ten": "An", "tra_loi": {"TN1": 0}}).encode(), headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(req).read().decode())
        assert "key" in res and res["toi_da"] == 10.0
        assert "An" in urllib.request.urlopen(url + "bang").read().decode()
        bad = urllib.request.Request(url + "nop", data=b"{khong", headers={"Content-Type": "application/json"})
        assert "loi" in json.loads(urllib.request.urlopen(bad).read().decode())
        a.export_csv(str(tmp_path / "d.csv"))
        assert "An" in (tmp_path / "d.csv").read_text(encoding="utf-8-sig")
    finally:
        a.stop()


def test_gas_script():
    from nganhangde.gas import apps_script, latex_to_text
    assert latex_to_text(r"$\dfrac{x^2+1}{x-1}\le\sqrt{3}$") == "(x²+1)/(x-1)≤√3"
    code = apps_script(_versions(["101"])[0], ten_de="KT")
    assert "function taoDe()" in code and "setIsQuiz(true)" in code
    data = json.loads(code[code.index("var DATA = ") + 11:code.index(";\n\nfunction taoDe")])
    assert sum(1 for x in data if x["t"] == "mc") == 12 + 4 * 4
    assert "Phần III câu 1:" in code


def test_moodle_images_and_graderinfo(tmp_path):
    from nganhangde.online import moodle_xml
    (tmp_path / "hinh.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    qs = parse_tex(r"""\begin{ex}%[0D1N1-1]
Xem hình \includegraphics[width=3cm]{hinh}
\choice
{\True a}{b}{c}{d}
\loigiai{Chọn A.}
\end{ex}
\begin{bt}%[0D1V1-1]
Chứng minh.
\loigiai{Lời giải tự luận.}
\end{bt}""")
    x = moodle_xml(qs, scoring=None, base_dir=str(tmp_path))
    assert "@@PLUGINFILE@@/hinh.png" in x and "encoding='base64'" in x
    assert "<graderinfo" in x and "Lời giải tự luận" in x and "<defaultgrade>1.0</defaultgrade>" in x


def test_slides_and_tree(tmp_path, bank):
    from nganhangde.slides import export_slides
    p = export_slides(parse_file(SAMPLE)[:3], str(tmp_path / "s.html"))
    html = open(p, encoding="utf-8").read()
    assert html.count("class='slide'") == 3 and "mathjax/tex-svg.js" in html
    assert (tmp_path / "mathjax" / "tex-svg.js").exists()
    rows = bank.tree_stats()
    assert sum(r["n"] for r in rows) == bank.count() and any(r["dang"] for r in rows)
