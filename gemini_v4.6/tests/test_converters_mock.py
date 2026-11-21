import json
from pathlib import Path
from xml.etree import ElementTree as ET

from nganhangde.ai.pdf_ocr import ocr_pdf_to_extest
from nganhangde.ai.providers import AIConfig, AIResult, AIUsage
from nganhangde.converters.moodle_xml import escape_cloze_answer_text, export_moodle_xml
from nganhangde.converters.tex_to_word import export_questions_to_docx, recover_roundtrip_ir
from nganhangde.converters.word_to_tex import convert_docx_to_questions
from nganhangde.core.generator import shuffle_variant
from nganhangde.core.parser import parse_tex_questions
from nganhangde.exporters.online_gas import export_online_exam_bundle
from nganhangde.exporters.topic_book import export_topic_book_tex

SAMPLE = r"""
%[1D1N1-1]
\begin{ex}
Tính $f(2)$ với $f(x)=\dfrac{1}{2}$ và hình \includegraphics{hinh.png}.
\choice{\True $2$}{$1$}{$4$}{$-2$}
\loigiai{Kết quả $2$.}
\end{ex}
%[1D2H2-1]
\begin{ex}
Xét mệnh đề:
\choiceTF{\True $2+2=4$}{$1>2$}{\True $3^2=9$}{$0=1$}
\end{ex}
%[1H4V1-2]
\begin{ex}
Đáp số: \shortans{$-1{,}5$}
\end{ex}
"""


def test_word_moodle_gas_and_topic_book(tmp_path):
    (tmp_path / "hinh.png").write_bytes(b"\x89PNG\r\n\x1a\nFAKE")
    qs = parse_tex_questions(SAMPLE)

    # Word 2 chiều + round-trip IR
    docx_p = tmp_path / "de.docx"
    rep = export_questions_to_docx(qs, str(docx_p))
    assert rep.direct_omml >= 2
    assert len(recover_roundtrip_ir(str(docx_p)) or []) == 3
    back, _ = convert_docx_to_questions(str(docx_p))
    assert len(back) == 3

    # Moodle XML chuẩn MathJax + Base64 + Cloze
    xml_s = export_moodle_xml(qs, str(tmp_path / "moodle.xml"), asset_dir=str(tmp_path))
    assert xml_s.splitlines()[0] == '<?xml version="1.0" encoding="UTF-8"?>'
    assert [q.attrib["type"] for q in ET.fromstring(xml_s).findall("question")] == ["category", "multichoice", "cloze", "shortanswer"]
    assert "@@PLUGINFILE@@/hinh.png" in xml_s
    assert escape_cloze_answer_text(r'a}b~c#d/e"f\g') == r'a\}b\~c\#d\/e&quot;f\\g'

    # GAS server-only key + LockService
    v = shuffle_variant(qs, "2026", seed=5, shuffle_q=False, shuffle_opt=False)
    b = export_online_exam_bundle(v, str(tmp_path / "gas"), server_only_key=True)
    assert "LockService.getScriptLock()" in Path(b["gas_script"]).read_text(encoding="utf-8")
    assert "offline_key" not in Path(b["exam_html"]).read_text(encoding="utf-8")

    # Topic Book (Chuyên đề)
    book_p = tmp_path / "chuyen_de.tex"
    export_topic_book_tex(qs, str(book_p), book_title="CHUYÊN ĐỀ TOÁN 11")
    txt = book_p.read_text(encoding="utf-8")
    assert r"\tableofcontents" in txt and "Dạng 1." in txt
