import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Sequence
from ..core.parser import Question
from .mtef_bridge import convert_omml_docx_to_mathtype_ole

INLINE_MATH_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$)", re.DOTALL)


@dataclass
class ConversionPathReport:
    total_equations: int = 0
    direct_omml: int = 0
    raw_fallback: int = 0
    mathtype_ole_applied: bool = False
    details: list[dict] = field(default_factory=list)


def _simple_omml(expr: str) -> str | None:
    body = expr.strip().strip("$").strip()
    if not body or any(t in body for t in (r"\begin{", r"\matrix", r"\cases")):
        return None
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    mf = re.fullmatch(r"\\d?frac\{([^{}]+)\}\{([^{}]+)\}", body)
    if mf:
        return (
            '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            f"<m:f><m:num><m:r><m:t>{esc(mf.group(1))}</m:t></m:r></m:num>"
            f"<m:den><m:r><m:t>{esc(mf.group(2))}</m:t></m:r></m:den></m:f></m:oMath>"
        )
    if "\\" not in body:
        return f'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>{esc(body)}</m:t></m:r></m:oMath>'
    return None


def _add_math_runs(p, text: str, rep: ConversionPathReport) -> None:
    from docx.oxml import parse_xml
    pos = 0
    for m in INLINE_MATH_RE.finditer(text):
        if m.start() > pos:
            p.add_run(text[pos : m.start()])
        expr = m.group(0)
        rep.total_equations += 1
        omml = _simple_omml(expr)
        if omml:
            p._p.append(parse_xml(omml))
            rep.direct_omml += 1
            rep.details.append({"expr": expr, "path": "direct_omml"})
        else:
            p.add_run(expr)
            rep.raw_fallback += 1
            rep.details.append({"expr": expr, "path": "raw_fallback"})
        pos = m.end()
    if pos < len(text):
        p.add_run(text[pos:])


def recover_roundtrip_ir(docx_path: str) -> list[Question] | None:
    with zipfile.ZipFile(docx_path, "r") as zf:
        if "customXml/toan11_ir.json" not in zf.namelist():
            return None
        data = json.loads(zf.read("customXml/toan11_ir.json").decode("utf-8"))
    out = []
    for it in data.get("questions", []):
        q = Question(it["qtype"], it["stem"], it.get("choices", []), it.get("correct", []), it.get("short_ans", ""), it.get("solution", ""), it.get("ids", []), it.get("tags", []), cmd_name=it.get("cmd_name", ""), cmd_opt=it.get("cmd_opt", ""))
        q.raw = q.to_latex(True)
        out.append(q)
    return out


def export_questions_to_docx(
    questions: Sequence[Question], out_docx: str, title: str = "ĐỀ KIỂM TRA TOÁN",
    include_solution: bool = True, convert_to_mathtype_ole: bool = False, report_json_path: str | None = None,
) -> ConversionPathReport:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Thiếu python-docx. Chạy: pip install python-docx") from exc

    doc = Document()
    doc.add_heading(title, level=1)
    rep = ConversionPathReport()
    for idx, q in enumerate(questions, 1):
        p = doc.add_paragraph()
        p.add_run(f"Câu {idx}. ").bold = True
        _add_math_runs(p, q.stem, rep)
        if q.qtype in ("TN", "DS"):
            labels = "ABCDE" if q.qtype == "TN" else "abcd"
            sep = ". " if q.qtype == "TN" else ") "
            for oi, (ch, ok) in enumerate(zip(q.choices, q.correct)):
                op = doc.add_paragraph()
                r = op.add_run(f"{labels[oi]}{sep}")
                r.bold, r.underline = True, ok
                _add_math_runs(op, ch, rep)
        elif q.qtype == "KQ":
            ap = doc.add_paragraph()
            ap.add_run("Đáp số: ").bold = True
            _add_math_runs(ap, q.short_ans, rep)
        if include_solution and q.solution.strip():
            sp = doc.add_paragraph()
            sp.add_run("Lời giải: ").italic = True
            _add_math_runs(sp, q.solution, rep)
    doc.save(out_docx)

    ir = {"schema": "toan11-ir-v1", "questions": [{"qtype": q.qtype, "ids": q.ids, "tags": q.tags, "stem": q.stem, "choices": q.choices, "correct": q.correct, "short_ans": q.short_ans, "solution": q.solution, "cmd_name": q.cmd_name, "cmd_opt": q.cmd_opt} for q in questions]}
    with zipfile.ZipFile(out_docx, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("customXml/toan11_ir.json", json.dumps(ir, ensure_ascii=False, indent=2))

    if convert_to_mathtype_ole:
        tmp = f"{out_docx}.mt.docx"
        if convert_omml_docx_to_mathtype_ole(out_docx, tmp) and os.path.exists(tmp):
            os.replace(tmp, out_docx)
            rep.mathtype_ole_applied = True

    if report_json_path:
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(rep.__dict__, f, ensure_ascii=False, indent=2)
    return rep
