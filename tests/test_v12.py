"""Giai đoạn 2: thang điểm, câu chùm, giới hạn đáp án liền nhau, phiếu chấm, ma trận CV 7991."""
import os
import random
from collections import Counter

import pytest

from nganhangde.generator import ExamVersion, MixOptions, Rule, _letters, _longest_run, _mix_section, group_key
from nganhangde.parser import Question

ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE = os.path.join(ROOT, "0-1-De-chuan-hoa-1.tex")


def _tn(i, tags=()):
    return Question("TN", f"Câu {i}", ["a", "b", "c", "d"], [True, False, False, False], tags=list(tags))


def test_groups_and_max_run():
    qs = [_tn(i) for i in range(24)]
    for i in (3, 10, 11):
        qs[i].tags = ["chum:G1"]
    for seed in range(200):
        out = _mix_section(qs, random.Random(seed), MixOptions(), False)
        assert _longest_run(_letters(out))[0] <= 3
        c = Counter(_letters(out))
        assert max(c.values()) - min(c.values()) <= 1
        pos = [i for i, q in enumerate(out) if group_key(q) == "G1"]
        assert pos == list(range(pos[0], pos[0] + 3))
        assert [out[i].stem for i in pos] == ["Câu 3", "Câu 10", "Câu 11"]


def test_scoring_custom():
    from nganhangde.scoring import Scoring
    sc = Scoring.from_dict({"tn": "0,2", "ds": "0,1; 0,2; 0,4; 0,8", "kq": "0,3", "tl": "1; 0,5"})
    assert sc.ds_score(3) == 0.4 and sc.tl_points(3) == [1.0, 0.5, 1.0]
    assert abs(sc.max_points({"TN": 10, "DS": 2, "KQ": 4, "TL": 2}) - (2 + 1.6 + 1.2 + 1.5)) < 1e-9
    with pytest.raises(ValueError):
        Scoring.from_dict({"ds": "0,1; 0,2"})
    from nganhangde.exporter import scoring_tex
    v = ExamVersion("101")
    v.sections = {"TN": [_tn(1)], "DS": [], "KQ": [], "TL": []}
    assert "0,2 điểm" in scoring_tex(v, sc)


def _version(code="0101", n_tn=4, kq="$0{,}5$"):
    v = ExamVersion(code)
    v.sections = {"TN": [_tn(i) for i in range(n_tn)],
                  "DS": [Question("DS", "x", list("abcd"), [True, False, True, False])],
                  "KQ": [Question("KQ", "y", short_answer=kq)], "TL": []}
    return v


def test_capacity_and_qr():
    from nganhangde.omr import check_capacity, qr_payload
    assert check_capacity([_version()]) == []
    w = check_capacity([_version(n_tn=41, kq="$12{,}345$")])
    assert any("Phần I" in x for x in w) and any("không tô được" in x for x in w)
    assert qr_payload(_version()) == "0101|I:AAAA|II:1010|III:0,5"


def test_fill_template_horizontal_and_vertical(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from nganhangde.exporter import ExportOptions
    from nganhangde.omr import fill_template, parse_label
    assert parse_label("II.1b") == ("DS", 1, 1)
    assert parse_label("Câu 5") == (None, 5, None)
    assert parse_label(3) == (None, 3, None)
    vs = [_version("0101"), _version("0102")]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mã đề", "1", "2", "3", "4", "5", "6"])
    p = tmp_path / "ngang.xlsx"
    wb.save(p)
    out = fill_template(vs, str(p), str(tmp_path / "o1.xlsx"), ExportOptions())
    ws = openpyxl.load_workbook(out).active
    assert [c.value for c in ws[2]] == ["0101", "A", "A", "A", "A", "ĐSĐS", "0,5"]
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in (["Câu"], ["I.1"], ["II.1a"], ["II.1b"], ["III.1"]):
        ws.append(row)
    p = tmp_path / "doc.xlsx"
    wb.save(p)
    ws = openpyxl.load_workbook(fill_template(vs, str(p), str(tmp_path / "o2.xlsx"), ExportOptions())).active
    assert [ws.cell(r, 2).value for r in range(1, 6)] == ["0101", "A", "Đ", "S", "0,5"]
    wb = openpyxl.Workbook()
    wb.active.append(["Họ tên", "SBD"])
    p = tmp_path / "x.xlsx"
    wb.save(p)
    with pytest.raises(ValueError):
        fill_template(vs, str(p), str(tmp_path / "o3.xlsx"), ExportOptions())


def test_matrix_cv7991_roundtrip(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from nganhangde import matrix
    rules = [Rule("TN", 6, "0D2N*"), Rule("TN", 4, "0D2H*"), Rule("DS", 2, "0D3*", "V"),
             Rule("KQ", 3, "0D3C*"), Rule("TL", 1, "*")]
    rows, total, points = matrix.build_table(rules, {"0D2": "Chương 2", "0D3": "Chương 3"})
    assert total[("TN", "N")] == 6 and total[("KQ", "V")] == 3 and total[("TL", "?")] == 1
    assert points["TN"] == 2.5 and points["DS"] == 2.0
    p = matrix.export_xlsx(rules, str(tmp_path / "mt.xlsx"), {"0D2": "Chương 2"})
    wb = openpyxl.load_workbook(p)
    assert wb.sheetnames == ["Ma trận CV7991", "Dòng ma trận"]
    back = matrix.import_xlsx(p)
    assert [(r.qtype, r.count, r.id, r.muc_do) for r in back] == [(r.qtype, r.count, r.id, r.muc_do) for r in rules]


def test_export_with_scoring_qr_and_template(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from nganhangde.exporter import ExportOptions, export_versions
    wb = openpyxl.Workbook()
    wb.active.append(["Mã đề", "I.1", "I.2", "II.1", "III.1"])
    tpl = tmp_path / "mau.xlsx"
    wb.save(tpl)
    opt = ExportOptions(scoring=True, qr_answers=True, diem={"kq": "0,25"}, omr_profile="mau",
                        omr_template=str(tpl), online_html=True)
    files = export_versions([_version()], str(tmp_path / "out"), options=opt)
    lg = open(tmp_path / "out" / "loigiai_0101.tex", encoding="utf-8").read()
    assert "\\qrcode" in lg and "\\usepackage{qrcode}" in lg and "0,25 điểm" in lg
    assert any(f.endswith("dap_an_phieu_cham.xlsx") for f in files)
    html = open(tmp_path / "out" / "online_0101.html", encoding="utf-8").read()
    assert '"KQ": 0.25' in html
