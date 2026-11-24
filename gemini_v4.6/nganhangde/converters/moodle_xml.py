import base64
import html
import os
import re
from typing import Sequence
from ..core.parser import Question
from ..core.texutil import normalize_short_ans

INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
DISPLAY_MATH_RE = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
INLINE_MATH_RE = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$", re.DOTALL)


def _cdata(text: str) -> str:
    return f"<![CDATA[{text.replace(']]>', ']]]]><![CDATA[>')}]]>"


def escape_cloze_answer_text(text: str) -> str:
    out = text.replace("\\", "\\\\")
    for ch in ("}", "#", "~", "/"):
        out = out.replace(ch, f"\\{ch}")
    return out.replace('"', "&quot;")


def _latex_to_moodle_html(text: str, asset_dir: str | None = None) -> tuple[str, list[tuple[str, str]]]:
    embedded, placeholders = [], []

    def _img_ph(m: re.Match) -> str:
        rel = m.group(1).strip()
        fn = os.path.basename(rel)
        if asset_dir:
            src = rel if os.path.isabs(rel) else os.path.join(asset_dir, rel)
            if os.path.exists(src):
                embedded.append((fn, base64.b64encode(open(src, "rb").read()).decode("ascii")))
        tok = f"__IMG_{len(placeholders)}__"
        placeholders.append((tok, f'<img src="@@PLUGINFILE@@/{html.escape(fn)}" alt="{html.escape(fn)}" style="max-width:100%;" />'))
        return tok

    work = INCLUDEGRAPHICS_RE.sub(_img_ph, text)
    work = DISPLAY_MATH_RE.sub(lambda m: f"\\[{m.group(1)}\\]", work)
    work = INLINE_MATH_RE.sub(lambda m: f"\\({m.group(1)}\\)", work)
    work = html.escape(work).replace("\n", "<br/>")
    for tok, tag in placeholders:
        work = work.replace(tok, tag)
    return work, embedded


def _file_tags(files: list[tuple[str, str]]) -> str:
    seen, out = set(), []
    for fn, b64 in files:
        if fn not in seen:
            seen.add(fn)
            out.append(f'    <file name="{html.escape(fn)}" path="/" encoding="base64">{b64}</file>')
    return "\n".join(out)


def export_moodle_xml(questions: Sequence[Question], out_xml: str, category_name: str = "Toan11_2026", asset_dir: str | None = None, ds_mode: str = "cloze") -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>", '  <question type="category">', f"    <category><text>$course$/top/{html.escape(category_name)}</text></category>", "  </question>"]
    for idx, q in enumerate(questions, 1):
        qname = q.primary_id or f"Cau_{idx:03d}"
        sh, files = _latex_to_moodle_html(q.stem, asset_dir)
        lh, lfiles = _latex_to_moodle_html(q.solution, asset_dir)
        fxml, lfxml = _file_tags(files), _file_tags(lfiles)
        if q.qtype == "TN":
            lines.extend([
                '  <question type="multichoice">', f"    <name><text>{html.escape(qname)}</text></name>",
                '    <questiontext format="html">', f"      <text>{_cdata(f'<p>{sh}</p>')}</text>", *([fxml] if fxml else []), "    </questiontext>",
                '    <generalfeedback format="html">', f"      <text>{_cdata(f'<p>{lh}</p>')}</text>", *([lfxml] if lfxml else []), "    </generalfeedback>",
                f"    <defaultgrade>0.25</defaultgrade><single>true</single><shuffleanswers>{'0' if q.lock_shuffle else '1'}</shuffleanswers><answernumbering>ABCD</answernumbering>",
            ])
            for ch, ok in zip(q.choices, q.correct):
                ch_h, _ = _latex_to_moodle_html(ch, asset_dir)
                lines.append(f'    <answer fraction="{"100" if ok else "0"}" format="html"><text>{_cdata(ch_h)}</text></answer>')
            lines.append("  </question>")
        elif q.qtype == "DS":
            sub_rows = []
            for si, (ch, ok) in enumerate(zip(q.choices, q.correct)):
                ch_h, _ = _latex_to_moodle_html(ch, asset_dir)
                box = "{1:MULTICHOICE_H:=Đúng~Sai}" if ok else "{1:MULTICHOICE_H:=Sai~Đúng}"
                sub_rows.append(f"<p><b>{'abcd'[si]})</b> {ch_h} &nbsp; {box}</p>")
            lines.extend([
                '  <question type="cloze">', f"    <name><text>{html.escape(qname)}</text></name>",
                '    <questiontext format="html">', f"      <text>{_cdata(f'<p>{sh}</p>' + ''.join(sub_rows))}</text>", *([fxml] if fxml else []), "    </questiontext>",
                '    <generalfeedback format="html">', f"      <text>{_cdata(f'<p>{lh}</p>')}</text>", *([lfxml] if lfxml else []), "    </generalfeedback>",
                "  </question>",
            ])
        elif q.qtype == "KQ":
            nc = normalize_short_ans(q.short_ans)
            nd = nc.replace(",", ".")
            lines.extend([
                '  <question type="shortanswer">', f"    <name><text>{html.escape(qname)}</text></name>",
                '    <questiontext format="html">', f"      <text>{_cdata(f'<p>{sh}</p>')}</text>", *([fxml] if fxml else []), "    </questiontext>",
                '    <generalfeedback format="html">', f"      <text>{_cdata(f'<p>{lh}</p>')}</text>", *([lfxml] if lfxml else []), "    </generalfeedback>",
                "    <defaultgrade>0.5</defaultgrade><usecase>0</usecase>",
            ])
            for a in ([nc] if nc == nd else [nc, nd]):
                lines.append(f'    <answer fraction="100" format="moodle_auto_format"><text>{html.escape(a)}</text></answer>')
            lines.append("  </question>")
        else:
            lines.extend([
                '  <question type="essay">', f"    <name><text>{html.escape(qname)}</text></name>",
                '    <questiontext format="html">', f"      <text>{_cdata(f'<p>{sh}</p>')}</text>", *([fxml] if fxml else []), "    </questiontext>",
                '    <graderinfo format="html">', f"      <text>{_cdata(f'<p>{lh}</p>')}</text>", "    </graderinfo>",
                "    <defaultgrade>1.0</defaultgrade><responseformat>editor</responseformat><attachments>-1</attachments>",
                "  </question>",
            ])
    lines.append("</quiz>")
    xml_out = "\n".join(lines) + "\n"
    open(out_xml, "w", encoding="utf-8").write(xml_out)
    return xml_out
