"""Biên dịch PDF, Gemini (giả lập), cập nhật, TeXstudio."""
import os

import pytest

from nganhangde.exporter import export_versions
from nganhangde.generator import Rule, make_versions
from nganhangde.parser import parse_file
from conftest import SAMPLE
from test_review_idmap import DASH_MAP


def test_pdfbuild(bank, tmp_path):
    from nganhangde import pdfbuild as pb
    try:
        eng = pb.find_engine("pdflatex")
    except pb.EngineMissing:
        pytest.skip("máy chưa có LaTeX")
    from nganhangde.exporter import ExportOptions
    vs = make_versions(bank, [Rule("TN", 12), Rule("DS", 4), Rule("KQ", 6)], codes=["101"], seed=1)
    files = export_versions(vs, str(tmp_path / "o"), options=ExportOptions(renumber=True, official_titles=True,
                            scoring=True), truong="THPT ABC")
    for f in files[:2]:
        r = pb.compile_tex(f, eng)
        assert r.ok and r.pdf and os.path.getsize(r.pdf) > 10000, r.errors
        assert not os.path.exists(f.replace(".tex", ".aux"))          # đã dọn file phụ
    assert os.path.exists(str(tmp_path / "o" / "ex_test.sty"))       # ex_test.sty đầy đủ được chép cạnh đề
    # lỗi được đọc thành câu dễ hiểu, có số dòng
    bad = tmp_path / "loi.tex"
    bad.write_text("\\documentclass{article}\n\\begin{document}\nA\n\\lenhsai{x}\n$x^2\n\\end{document}\n",
                   encoding="utf-8")
    r = pb.compile_tex(str(bad), eng)
    assert not r.ok and r.errors[0].startswith("Dòng 4:") and "lệnh không tồn tại" in r.errors[0]
    assert os.path.exists(str(tmp_path / "loi.log"))                    # lỗi ⇒ giữ .log để xem
    # xem trước 1 câu
    r = pb.preview_questions([bank.get(13)], engine=eng, out_dir=str(tmp_path / "xt"))
    assert r.ok and r.pdf
    errs, _ = pb.parse_log("! Undefined control sequence.\nl.12 \\foo\n! Missing $ inserted.\nl.20 x^2\n")
    assert errs == ["Dòng 12: Undefined control sequence. – lệnh không tồn tại (gõ sai tên lệnh hoặc thiếu gói)",
                    "Dòng 20: Missing $ inserted. – thiếu dấu $ (công thức chưa đóng/mở đúng)"]


def test_gemini_id():
    import json as _json
    from nganhangde import aiid
    from nganhangde.idmap import parse_map_text
    m = parse_map_text(DASH_MAP)
    qs = parse_file(SAMPLE)
    circle, newton, ellipse = qs[2], qs[11], qs[10]
    calls = []

    def fake(url, data, key, timeout=90):
        calls.append((url, data, key))
        if data is None:                                          # list_models
            return {"models": [{"name": "models/gemini-x", "supportedGenerationMethods": ["generateContent"]},
                               {"name": "models/embed", "supportedGenerationMethods": ["embedContent"]}]}
        prompt = data["contents"][0]["parts"][0]["text"]
        assert "0H94-1 | Lớp 10 › Hình học 10" in prompt and "### Câu 3" in prompt
        assert data["generationConfig"]["responseMimeType"] == "application/json"
        out = {"ket_qua": [
            {"cau": 1, "ma": "0H94-1", "muc_do": "N", "tin_cay": 0.92, "ly_do": "tâm và bán kính đường tròn"},
            {"cau": 2, "ma": "0D83-2", "muc_do": "H", "tin_cay": 0.85, "ly_do": "khai triển nhị thức"},
            {"cau": 3, "ma": "0H77-7", "muc_do": "N", "tin_cay": 0.9, "ly_do": "mã bịa"}]}
        return {"candidates": [{"content": {"parts": [{"text": "```json\n" + _json.dumps(out) + "\n```"}]}}]}

    c = aiid.GeminiClient("KHOA-THU", "gemini-x", transport=fake)
    assert c.list_models() == ["gemini-x"]
    res = c and aiid.classify(c, [circle, newton, ellipse], m, scope="0")
    assert [r.id_code for r in res] == ["0H9N4-1", "0D8H3-2", None]
    assert res[0].score == 0.92 and res[2].score == 0 and "không có trong Map ID" in res[2].reason
    assert calls[-1][2] == "KHOA-THU" and calls[-1][0].endswith("/models/gemini-x:generateContent")
    with pytest.raises(aiid.AIError):
        aiid.GeminiClient("")
    with pytest.raises(aiid.AIError):                             # phạm vi không có dạng nào
        aiid.classify(c, [circle], m, scope="2")


def test_updater_and_editor(tmp_path):
    import hashlib
    from nganhangde import updater as up
    from nganhangde.editor import find_texstudio, first_error_line
    assert up.is_newer("0.10.0", "0.9.0") and not up.is_newer("0.9.0", "0.9.0") and up.is_newer("v1.0", "0.9.9")
    blob = b"MZ" + b"x" * 5000
    src = tmp_path / "NganHangDe.exe"
    src.write_bytes(blob)
    good = "sha256:" + hashlib.sha256(blob).hexdigest()

    def fake(url):
        return {"tag_name": "v9.9.9", "body": "## Có gì mới\n- abc", "html_url": "https://x/rel",
                "assets": [{"name": "NganHangDe.exe", "browser_download_url": src.as_uri(),
                            "size": len(blob), "digest": good}]}
    rel = up.latest_release(fake)
    assert rel.version == "9.9.9" and rel.sha256 == good.split(":")[1] and rel.size == len(blob)
    seen = []
    p = up.download(rel, str(tmp_path / "dl"), progress=lambda d, t: seen.append((d, t)))
    assert open(p, "rb").read() == blob and seen[-1] == (len(blob), len(blob))
    rel.sha256 = "0" * 64                                        # mã kiểm tra sai ⇒ xoá file, báo lỗi
    with pytest.raises(up.UpdateError):
        up.download(rel, str(tmp_path / "dl2"))
    assert not os.listdir(tmp_path / "dl2")
    bat = up.update_script(1234, r"C:\T\new.exe", r"D:\NHD\NganHangDe.exe")
    assert 'PYINSTALLER_RESET_ENVIRONMENT=1' in bat and 'tasklist' not in bat and 'find' not in bat and r'copy /Y "C:\T\new.exe" "D:\NHD\NganHangDe.exe"' in bat
    assert r'"D:\NHD\NganHangDe_cu.exe"' in bat and 'start "" "D:\\NHD\\NganHangDe.exe"' in bat
    with pytest.raises(up.UpdateError):                          # chạy từ mã nguồn ⇒ không tự thay exe
        up.apply_update(p)
    assert first_error_line(["==> x", "Dòng 17: lệnh không tồn tại"]) == 17 and first_error_line([]) is None
    assert find_texstudio(str(src)) == str(src)


def test_find_engine_from_texstudio_and_texlive2019(tmp_path, monkeypatch):
    from nganhangde import pdfbuild
    tl = tmp_path / "texlive" / "2019" / "bin" / "win32"
    tl.mkdir(parents=True)
    (tl / "pdflatex.exe").write_text("")
    (tl / "xelatex.exe").write_text("")
    ini = tmp_path / "texstudio.ini"
    exe = str(tl / "pdflatex.exe").replace("\\", "/")
    ini.write_text("[texmaker]\nTools\\Commands\\pdflatex=\"\\\"" + exe + "\\\" -synctex=1 -interaction=nonstopmode %.tex\"\n"
                   "Tools\\Commands\\xelatex=xelatex -synctex=1 %.tex\n"
                   f"Tools\\SearchPaths={tl}\n", encoding="utf-8")
    found = pdfbuild.texstudio_engines([str(ini)])
    assert found["pdflatex"] == str(tl / "pdflatex.exe") and found["xelatex"] == str(tl / "xelatex.exe")
    monkeypatch.setattr(pdfbuild, "texstudio_ini_paths", lambda: [str(ini)])
    assert pdfbuild.find_engine() == str(tl / "pdflatex.exe")
    assert pdfbuild.find_engine("xelatex") == str(tl / "xelatex.exe")
