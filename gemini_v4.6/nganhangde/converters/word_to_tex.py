import time
import os
from pathlib import Path
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET
from ..core.parser import Question
from .mtef_bridge import convert_mathtype_via_word_com, inspect_docx_mtef_objects

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
Q_START_RE = re.compile(r"^\s*(?:Câu|Bài)\s+\d+\s*[.:]\s*(.*)", re.IGNORECASE)
TF_RE = re.compile(r"^\s*([a-d])\)\s*(.*)")
SA_RE = re.compile(r"^\s*(?:Đáp\s*số|Trả\s*lời(?:\s*ngắn)?|KQ)\s*[:.]\s*(.*)", re.IGNORECASE)
SOL_RE = re.compile(r"^\s*(?:Lời\s*giải|Hướng\s*dẫn\s*giải)\s*[:.]?\s*(.*)", re.IGNORECASE)


@dataclass
class DocxTriageReport:
    omml_count: int = 0
    mathtype_ole_count: int = 0
    media_image_count: int = 0
    ole_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mathtype_converted: bool = False


def triage_docx_equations(docx_path: str) -> DocxTriageReport:
    rep = DocxTriageReport()
    mtef_list = inspect_docx_mtef_objects(docx_path)
    rep.ole_files = [m.entry_name for m in mtef_list]
    rep.mathtype_ole_count = len(mtef_list)
    with zipfile.ZipFile(docx_path, "r") as zf:
        names = zf.namelist()
        rep.media_image_count = sum(1 for n in names if n.startswith("word/media/"))
        if "word/document.xml" in names:
            rep.omml_count = len(ET.fromstring(zf.read("word/document.xml")).findall(f".//{M_NS}oMath"))
    if rep.mathtype_ole_count:
        rep.warnings.append(
            f"Phát hiện {rep.mathtype_ole_count} công thức MathType OLE (oleObject*.bin)."
        )
    return rep


def _omml(node: ET.Element | None) -> str:
    if node is None:
        return ""
    tag = node.tag.replace(M_NS, "")
    ch = lambda n: "".join(_omml(c) for c in n) if n is not None else ""
    if tag == "t":
        return node.text or ""
    if tag == "f":
        return f"\\dfrac{{{ch(node.find(f'{M_NS}num'))}}}{{{ch(node.find(f'{M_NS}den'))}}}"
    if tag == "sSup":
        return f"{{{ch(node.find(f'{M_NS}e'))}}}^{{{ch(node.find(f'{M_NS}sup'))}}}"
    if tag == "sSub":
        return f"{{{ch(node.find(f'{M_NS}e'))}}}_{{{ch(node.find(f'{M_NS}sub'))}}}"
    if tag == "sSubSup":
        return f"{{{ch(node.find(f'{M_NS}e'))}}}_{{{ch(node.find(f'{M_NS}sub'))}}}^{{{ch(node.find(f'{M_NS}sup'))}}}"
    if tag == "rad":
        deg = ch(node.find(f"{M_NS}deg")).strip()
        expr = ch(node.find(f"{M_NS}e"))
        return f"\\sqrt[{deg}]{{{expr}}}" if deg else f"\\sqrt{{{expr}}}"
    if tag == "d":
        dpr = node.find(f"{M_NS}dPr")
        beg = "("
        end = ")"
        if dpr is not None:
            bc = dpr.find(f"{M_NS}begChr")
            ec = dpr.find(f"{M_NS}endChr")
            if bc is not None:
                beg = bc.attrib.get(f"{M_NS}val", "(")
            if ec is not None:
                end = ec.attrib.get(f"{M_NS}val", ")")
        b_tex = r"\{" if beg == "{" else (beg or ".")
        e_tex = r"\}" if end == "}" else (end or ".")
        inner = ", ".join(_omml(e) for e in node.findall(f"{M_NS}e"))
        return f"\\left{b_tex}{inner}\\right{e_tex}"
    if tag == "nary":
        npr = node.find(f"{M_NS}naryPr")
        sym = r"\displaystyle\int\limits"
        if npr is not None:
            chr_el = npr.find(f"{M_NS}chr")
            val = chr_el.attrib.get(f"{M_NS}val", "∫") if chr_el is not None else "∫"
            if val == "∑":
                sym = r"\displaystyle\sum\limits"
            elif val == "∏":
                sym = r"\displaystyle\prod\limits"
        sub = ch(node.find(f"{M_NS}sub")).strip()
        sup = ch(node.find(f"{M_NS}sup")).strip()
        body = ch(node.find(f"{M_NS}e"))
        s_part = f"_{{{sub}}}" if sub else ""
        p_part = f"^{{{sup}}}" if sup else ""
        return f"{sym}{s_part}{p_part}{body}"
    if tag == "limLow":
        base = ch(node.find(f"{M_NS}e")).strip()
        lim = ch(node.find(f"{M_NS}lim")).strip()
        if base == "lim":
            return f"\\lim\\limits_{{{lim}}}"
        return f"\\operatorname{{{base}}}_{{{lim}}}"
    if tag == "acc":
        apr = node.find(f"{M_NS}accPr")
        val = ""
        if apr is not None:
            cel = apr.find(f"{M_NS}chr")
            if cel is not None:
                val = cel.attrib.get(f"{M_NS}val", "")
        inner = ch(node.find(f"{M_NS}e"))
        if val in ("\u20d7", "→"):
            return f"\\overrightarrow{{{inner}}}"
        if val in ("\u0304", "\u0305", "¯"):
            return f"\\overline{{{inner}}}"
        return f"\\widehat{{{inner}}}"
    if tag == "bar":
        return f"\\overline{{{ch(node.find(f'{M_NS}e'))}}}"
    if tag == "func":
        fn = ch(node.find(f"{M_NS}fName")).strip()
        arg = ch(node.find(f"{M_NS}e"))
        return f"\\{fn} {arg}" if fn in ("sin", "cos", "tan", "cot", "log", "ln", "lim") else f"{fn}({arg})"
    if tag == "m":
        rows = []
        for mr in node.findall(f"{M_NS}mr"):
            cells = [_omml(e) for e in mr.findall(f"{M_NS}e")]
            rows.append(" & ".join(cells))
        return r"\begin{aligned}" + r" \\ ".join(rows) + r"\end{aligned}"
    return ch(node)


def _is_marked(r_el: ET.Element) -> bool:
    rpr = r_el.find(f"{W_NS}rPr")
    if rpr is None:
        return False
    u = rpr.find(f"{W_NS}u")
    if u is not None and u.attrib.get(f"{W_NS}val", "single") != "none":
        return True
    col = rpr.find(f"{W_NS}color")
    return bool(col is not None and (col.attrib.get(f"{W_NS}val") or "").upper() not in ("", "000000", "AUTO"))


def _extract_paragraph_parts(elem: ET.Element, parts: list[str], marked_flag: list[bool]) -> None:
    """Duyệt đệ quy để không bỏ sót công thức OMML nằm trong mc:AlternateContent / w:ins / w:sdt."""
    for c in elem:
        if c.tag == f"{W_NS}r":
            txt = "".join(t.text or "" for t in c.findall(f".//{W_NS}t"))
            if txt:
                if _is_marked(c):
                    marked_flag[0] = True
                parts.append(txt)
        elif c.tag == f"{M_NS}oMath":
            lx = _omml(c).strip()
            if lx:
                parts.append(f"${lx}$")
        elif c.tag == f"{M_NS}oMathPara":
            for om in c.findall(f".//{M_NS}oMath"):
                lx = _omml(om).strip()
                if lx:
                    parts.append(f"$${lx}$$")
        elif c.tag.endswith("Fallback"):
            continue
        else:
            _extract_paragraph_parts(c, parts, marked_flag)


def _normalize_mathtype_tex(text: str) -> str:
    """Chuẩn hoá cú pháp LaTeX sinh ra từ MathType Toggle TeX sang chuẩn Việt Nam."""
    text = re.sub(r"\\\[(.+?)\\\]", lambda m: f"$${m.group(1).strip()}$$", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", text, flags=re.DOTALL)
    text = text.replace(r"\frac{", r"\dfrac{")
    return text


def convert_docx_to_questions(
    docx_path: str,
    use_word_com: bool = True,
    show_word: bool = False,
    mode: str = "toggle_tex",
) -> tuple[list[Question], DocxTriageReport]:
    triage = triage_docx_equations(docx_path)
    actual_docx = docx_path
    tmp_dir_obj = None

    if triage.mathtype_ole_count > 0 and use_word_com and os.name == "nt":
        tmp_dir_obj = tempfile.TemporaryDirectory(prefix="w2t_mt_")
        tmp_out = Path(tmp_dir_obj.name) / "converted_mt.docx"
        ok, msg = convert_mathtype_via_word_com(docx_path, tmp_out, show_word=show_word, mode=mode)
        if ok and tmp_out.exists():
            actual_docx = str(tmp_out)
            triage.mathtype_converted = True
        else:
            triage.warnings.append(f"Chưa chuyển được MathType tự động qua Word COM: {msg}")

    try:
        lines: list[tuple[str, bool]] = []
        xml_bytes = None
        last_open_err = None
        for _attempt in range(12):
            try:
                with zipfile.ZipFile(actual_docx, "r") as zf:
                    xml_bytes = zf.read("word/document.xml")
                break
            except PermissionError as exc:
                last_open_err = exc
                time.sleep(0.35)
        if xml_bytes is None:
            raise last_open_err or PermissionError(f"Không thể đọc tệp đang bị khóa: {actual_docx}")
        root = ET.fromstring(xml_bytes)
        for p in root.findall(f".//{W_NS}p"):
            parts: list[str] = []
            marked_flag = [False]
            _extract_paragraph_parts(p, parts, marked_flag)
            s = _normalize_mathtype_tex("".join(parts)).strip()
            if s:
                lines.append((s, marked_flag[0]))
    finally:
        if tmp_dir_obj is not None:
            for _ in range(5):
                try:
                    tmp_dir_obj.cleanup()
                    break
                except OSError:
                    time.sleep(0.25)

    qs: list[Question] = []
    stem, chs, oks, tfs, sa, sol, in_sol = [], [], [], [], "", [], False

    def flush():
        nonlocal stem, chs, oks, tfs, sa, sol, in_sol
        if not stem:
            return
        st, sl = "\n".join(stem).strip(), "\n".join(sol).strip()
        if tfs:
            q = Question("DS", st, [x[0] for x in tfs], [x[1] for x in tfs], "", sl, cmd_name="choiceTF")
        elif chs:
            q = Question("TN", st, list(chs), list(oks), "", sl, cmd_name="choice")
        elif sa:
            q = Question("KQ", st, [], [], sa, sl, cmd_name="shortans")
        else:
            q = Question("TL", st, [], [], "", sl)
        q.raw = q.to_latex(True)
        qs.append(q)
        stem, chs, oks, tfs, sa, sol, in_sol = [], [], [], [], "", [], False

    for text, marked in lines:
        mq = Q_START_RE.match(text)
        if mq:
            flush()
            stem.append(mq.group(1).strip())
            continue
        msol = SOL_RE.match(text)
        if msol and stem:
            in_sol = True
            if msol.group(1).strip():
                sol.append(msol.group(1).strip())
            continue
        msa = SA_RE.match(text)
        if msa and stem and not sa:
            sa = msa.group(1).strip()
            if in_sol:
                sol.append(text)
            continue
        if in_sol:
            sol.append(text)
            continue
        mtf = TF_RE.match(text)
        if mtf and stem:
            tfs.append((mtf.group(2).strip(), marked))
            continue
        if stem and re.match(r"^[A-D]\.\s+", text):
            chunks = re.split(r"(?=(?:^|\s)[A-D]\.\s+)", text)
            for ck in chunks:
                ck = ck.strip()
                if re.match(r"^[A-D]\.\s+", ck):
                    body = re.sub(r"^[A-D]\.\s+", "", ck).strip()
                    ok = marked and len(chunks) == 1
                    if body.startswith("*"):
                        ok, body = True, body[1:].strip()
                    chs.append(body)
                    oks.append(ok)
            continue
        if stem:
            stem.append(text)
    flush()
    return qs, triage
