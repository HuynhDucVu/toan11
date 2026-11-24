"""Bản 0.16: câu đổi số / lời giải AI (xem test_v13_ai), bảng chọn theo ID, sắp xếp câu, Google Form nhận kết quả,
Google Forms dạng ảnh."""
import os
import json
import random
import shutil

import pytest

from nganhangde.generator import MixOptions, Rule, make_versions, mix_versions, sections_from_questions
from nganhangde.parser import parse_file

from conftest import SAMPLE


def test_order_by_matrix(bank):
    rules = [Rule("TN", 3, "0H9*"), Rule("TN", 2, "0D8*")]
    for seed in range(10):
        v = make_versions(bank, rules, 1, seed=seed, options=MixOptions(order="matrix"))[0]
        ids = [q.id_code[:3] for q in v.sections["TN"]]
        assert ids == ["0H9", "0H9", "0H9", "0D8", "0D8"]
    v = make_versions(bank, rules, 1, seed=1, options=MixOptions(order="id"))[0]
    assert [q.id_code for q in v.sections["TN"]] == sorted(q.id_code for q in v.sections["TN"])


def test_gform_link_and_html():
    from nganhangde.online import parse_prefill_link, version_html
    g = parse_prefill_link("https://docs.google.com/forms/d/e/1FAIpQLSabc-XYZ/viewform?usp=pp_url"
                           "&entry.111=TEN&entry.222=lop&entry.333=DIEM&entry.444=khac")
    assert g == {"id": "1FAIpQLSabc-XYZ", "entries": {"ten": "111", "lop": "222", "diem": "333"}}
    with pytest.raises(ValueError):
        parse_prefill_link("https://example.com/x")
    v = mix_versions(sections_from_questions(parse_file(SAMPLE)), ["101"], random.Random(1), MixOptions())[0]
    h = version_html(v, gform=g, style={"khung": "#FF8000", "chu_loigiai": "#0000FF", "nen": "red;}<script>"})
    assert "formResponse" in h and '"1FAIpQLSabc-XYZ"' in h and 'id="sbd"' in h
    assert "--c:#FF8000" in h and ".sol{color:#0000FF}" in h and "red;}" not in h
    assert 'id="sbd"' not in version_html(v)


def test_gas_images_script():
    from nganhangde.gas import apps_script_images
    v = mix_versions(sections_from_questions(parse_file(SAMPLE)), ["101"], random.Random(1), MixOptions())[0]
    code = apps_script_images(v, [f"cau_{i:02d}.png" for i in range(1, 23)])
    data = json.loads(code[code.index("var DATA = ") + 11:code.index(";\n\nfunction taoDe")])
    assert sum(x["t"] == "img" for x in data) == 22 and "FOLDER_ID" in code and "addImageItem" in code
    assert sum(x["t"] == "mc" for x in data) == 12 + 16


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="cần pdflatex")
def test_question_pngs(tmp_path):
    pytest.importorskip("pypdfium2")
    from nganhangde.exportx import question_pngs
    v = mix_versions(sections_from_questions(parse_file(SAMPLE)), ["101"], random.Random(1), MixOptions())[0]
    out, res = question_pngs(v, str(tmp_path), dpi=50)
    assert res.ok and len(out) == 22 and out[0][:2] == ("TN", 1)


def test_app_folder_layout(tmp_path, monkeypatch):
    from nganhangde import appdirs
    from nganhangde.exporter import load_template
    monkeypatch.setenv("NHD_HOME", str(tmp_path))
    root = appdirs.ensure_layout()
    for k in appdirs.SUBDIRS:
        assert os.path.isdir(appdirs.folder(k))
    assert (tmp_path / "TEMPLATE" / "de_thi.tex").exists() and (tmp_path / "DOC_TOI.txt").exists()
    assert appdirs.default_db() == str(tmp_path / "DATA" / "BANK" / "nganhang.db")
    (tmp_path / "TEMPLATE" / "de_thi.tex").write_text("MAU RIENG <<NOI_DUNG>>", encoding="utf-8")
    assert load_template().startswith("MAU RIENG")              # giáo viên sửa mẫu trong mau_de là có hiệu lực
    (tmp_path / "nganhang.db").write_text("")
    (tmp_path / "DATA" / "BANK" / "nganhang.db").unlink(missing_ok=True)
    assert appdirs.default_db() == str(tmp_path / "nganhang.db")  # máy dùng bố cục cũ: giữ kho cũ
    assert appdirs.settings_file() == str(tmp_path / "config.ini") and root == str(tmp_path)
