"""Đọc file Word (.docx) bằng Python thuần – KHÔNG cần pandoc.

* Đọc từng đoạn văn, công thức Word (OMML) → LaTeX, bảng → tabular, hình → file trong thư mục `hinh/`.
* Chữ **gạch chân hoặc tô màu** (cách MyLT đánh dấu đáp án đúng) được bọc \\underline{…} để bộ nhận dạng câu hỏi
  (wordconv.latex_text_to_ex) đặt \\True đúng chỗ.
* Công thức MathType (đối tượng OLE) không đọc trực tiếp được: báo số lượng, dùng `wordcom` để Word + MathType đổi
  sang công thức Word rồi đọc lại.
Hàm chính: `docx_to_latex(path, opts) -> (latex, DocxReport)`.
"""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
V = "{urn:schemas-microsoft-com:vml}"


@dataclass
class DocxOptions:
    tables: bool = True              # chuyển bảng thành tabular
    images: bool = True              # xuất hình ra thư mục và chèn \includegraphics
    image_dir: str = ""              # thư mục lưu hình (mặc định: <tên file>_hinh cạnh file Word)
    chem: bool = False               # môn Hoá: chỉ số dưới/trên trong chữ thường (H₂O → H_{2}O)
    replacements: list[tuple[str, str]] = field(default_factory=list)   # «thay thế cá nhân»
    theory: bool = False             # chuyên đề/lý thuyết: giữ nguyên văn bản, không nhận dạng câu hỏi


@dataclass
class DocxReport:
    omml: int = 0
    mathtype_ole: int = 0
    images: int = 0
    tables: int = 0
    warnings: list[str] = field(default_factory=list)


def triage(path: str) -> DocxReport:
    rep = DocxReport()
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        rep.mathtype_ole = sum(1 for n in names if n.startswith("word/embeddings/oleObject") and n.endswith(".bin"))
        rep.images = sum(1 for n in names if n.startswith("word/media/"))
        if "word/document.xml" in names:
            root = ET.fromstring(zf.read("word/document.xml"))
            rep.omml = len(root.findall(f".//{M}oMath"))
            rep.tables = len(root.findall(f".//{W}tbl"))
    if rep.mathtype_ole:
        rep.warnings.append(f"Có {rep.mathtype_ole} công thức MathType (đối tượng OLE) – cần Word + MathType để đổi sang công "
                            "thức Word trước (tuỳ chọn «Dùng Word»), nếu không các công thức này bị bỏ qua.")
    return rep


# ---------------------------------------------------------------- OMML → LaTeX
def _ch(n) -> str:
    return "".join(omml(c) for c in n) if n is not None else ""


def _val(el, tag, default=""):
    x = el.find(f"{M}{tag}") if el is not None else None
    return x.attrib.get(f"{M}val", default) if x is not None else default


def omml(node) -> str:
    if node is None:
        return ""
    tag = node.tag.replace(M, "")
    g = lambda t: node.find(f"{M}{t}")   # noqa: E731
    if tag == "t":
        return (node.text or "").replace("−", "-").replace("≤", r"\le ").replace("≥", r"\ge ").replace("≠", r"\ne ") \
            .replace("∞", r"\infty ").replace("∈", r"\in ").replace("π", r"\pi ").replace("→", r"\to ") \
            .replace("×", r"\times ").replace("·", r"\cdot ").replace("°", r"^\circ ").replace("∪", r"\cup ") \
            .replace("∩", r"\cap ").replace("⇔", r"\Leftrightarrow ").replace("⇒", r"\Rightarrow ") \
            .replace("α", r"\alpha ").replace("β", r"\beta ").replace("Δ", r"\Delta ").replace("∠", r"\widehat ")
    if tag == "f":
        return f"\\dfrac{{{_ch(g('num'))}}}{{{_ch(g('den'))}}}"
    if tag == "sSup":
        return f"{{{_ch(g('e'))}}}^{{{_ch(g('sup'))}}}"
    if tag == "sSub":
        return f"{{{_ch(g('e'))}}}_{{{_ch(g('sub'))}}}"
    if tag == "sSubSup":
        return f"{{{_ch(g('e'))}}}_{{{_ch(g('sub'))}}}^{{{_ch(g('sup'))}}}"
    if tag == "rad":
        deg, e = _ch(g("deg")).strip(), _ch(g("e"))
        return f"\\sqrt[{deg}]{{{e}}}" if deg else f"\\sqrt{{{e}}}"
    if tag == "d":
        dpr = g("dPr")
        beg, end = _val(dpr, "begChr", "("), _val(dpr, "endChr", ")")
        sep = _val(dpr, "sepChr", ",")
        fix = lambda c, left: (r"\{" if c == "{" else r"\}" if c == "}" else "." if c == "" else   # noqa: E731
                               r"\|" if c == "‖" else c)
        inner = (sep + " ").join(_ch(e) for e in node.findall(f"{M}e"))
        return f"\\left{fix(beg, True)}{inner}\\right{fix(end, False)}"
    if tag == "nary":
        npr = g("naryPr")
        ch_ = _val(npr, "chr", "∫")
        sym = {"∑": r"\displaystyle\sum\limits", "∏": r"\displaystyle\prod\limits", "∬": r"\displaystyle\iint\limits",
               "∮": r"\displaystyle\oint\limits"}.get(ch_, r"\displaystyle\int\limits")
        sub, sup = _ch(g("sub")).strip(), _ch(g("sup")).strip()
        return sym + (f"_{{{sub}}}" if sub else "") + (f"^{{{sup}}}" if sup else "") + _ch(g("e"))
    if tag == "limLow":
        base, lim = _ch(g("e")).strip(), _ch(g("lim")).strip()
        return f"\\lim\\limits_{{{lim}}}" if base == "lim" else f"{base}_{{{lim}}}"
    if tag == "limUpp":
        return f"{{{_ch(g('e'))}}}^{{{_ch(g('lim'))}}}"
    if tag == "acc":
        c = _val(g("accPr"), "chr", "")
        inner = _ch(g("e"))
        if c in ("\u20d7", "→"):
            return f"\\overrightarrow{{{inner}}}"
        if c in ("\u0304", "\u0305", "¯"):
            return f"\\overline{{{inner}}}"
        if c in ("\u0302", "^"):
            return f"\\widehat{{{inner}}}"
        return f"\\widehat{{{inner}}}"
    if tag == "bar":
        return f"\\overline{{{_ch(g('e'))}}}"
    if tag == "func":
        fn = _ch(g("fName")).strip()
        arg = _ch(g("e"))
        return (f"\\{fn} " if fn in ("sin", "cos", "tan", "cot", "log", "ln", "lim", "max", "min") else fn) + arg
    if tag == "eqArr":
        return r"\begin{cases}" + r" \\ ".join(_ch(e) for e in node.findall(f"{M}e")) + r"\end{cases}"
    if tag == "m":
        rows = [" & ".join(_ch(e) for e in mr.findall(f"{M}e")) for mr in node.findall(f"{M}mr")]
        return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"
    if tag in ("rPr", "ctrlPr", "dPr", "naryPr", "accPr", "fPr", "radPr", "sSupPr", "sSubPr", "eqArrPr", "mPr"):
        return ""
    return _ch(node)


# ---------------------------------------------------------------- đoạn văn
def _marked(r) -> bool:
    rpr = r.find(f"{W}rPr")
    if rpr is None:
        return False
    u = rpr.find(f"{W}u")
    if u is not None and u.attrib.get(f"{W}val", "single") != "none":
        return True
    col = rpr.find(f"{W}color")
    return bool(col is not None and (col.attrib.get(f"{W}val") or "").upper() not in ("", "000000", "AUTO"))


def _style(r):
    rpr = r.find(f"{W}rPr")
    if rpr is None:
        return None
    va = rpr.find(f"{W}vertAlign")
    return va.attrib.get(f"{W}val") if va is not None else None


class _Ctx:
    def __init__(self, zf, rels, opts, rep, base):
        self.zf, self.rels, self.opts, self.rep, self.base = zf, rels, opts, rep, base
        self.n_img = 0


def _image(ctx: _Ctx, elem) -> str:
    rid = None
    for b in elem.iter(f"{A}blip"):
        rid = b.attrib.get(f"{R}embed")
    for b in elem.iter(f"{V}imagedata"):
        rid = rid or b.attrib.get(f"{R}id")
    target = ctx.rels.get(rid or "")
    if not target or not ctx.opts.images:
        return ""
    name = "word/" + target.lstrip("/").replace("word/", "", 1)
    if name not in ctx.zf.namelist():
        return ""
    ctx.n_img += 1
    d = ctx.opts.image_dir or ctx.base + "_hinh"
    os.makedirs(d, exist_ok=True)
    ext = os.path.splitext(name)[1].lower() or ".png"
    fn = f"hinh{ctx.n_img:03d}{ext}"
    with open(os.path.join(d, fn), "wb") as f:
        f.write(ctx.zf.read(name))
    rel = os.path.join(os.path.basename(d), fn).replace("\\", "/")
    return f"\\includegraphics[width=5cm]{{{os.path.splitext(rel)[0] if ext in ('.png', '.jpg', '.jpeg') else rel}}}"


def _parts(ctx: _Ctx, elem, out: list[str]):
    for c in elem:
        t = c.tag
        if t == f"{W}r":
            txt = "".join((x.text or "") if x.tag == f"{W}t" else "\t" if x.tag == f"{W}tab" else
                          " " if x.tag in (f"{W}br", f"{W}cr") else "" for x in c.iter()
                          if x.tag in (f"{W}t", f"{W}tab", f"{W}br", f"{W}cr"))
            if c.find(f".//{W}drawing") is not None or c.find(f".//{W}pict") is not None:
                im = _image(ctx, c)
                if im:
                    out.append(im)
            if not txt:
                continue
            for a, b in ctx.opts.replacements:
                txt = txt.replace(a, b)
            if ctx.opts.chem:
                va = _style(c)
                if va == "subscript":
                    txt = "$_{" + txt + "}$"
                elif va == "superscript":
                    txt = "$^{" + txt + "}$"
            if _marked(c) and txt.strip():
                m = re.match(r"^(\s*[A-Da-d]\s*[.)])(.*)$", txt, re.S) if not "".join(out).strip() else None
                txt = (f"\\underline{{{m.group(1).strip()}}}{m.group(2)}" if m else f"\\underline{{{txt}}}")
            out.append(txt)
        elif t == f"{M}oMath":
            x = omml(c).strip()
            if x:
                out.append(f"${x}$")
        elif t == f"{M}oMathPara":
            for om in c.findall(f".//{M}oMath"):
                x = omml(om).strip()
                if x:
                    out.append(f"$${x}$$")
        elif t.endswith("Fallback") or t == f"{W}pPr":
            continue
        else:
            _parts(ctx, c, out)


def _para(ctx, p) -> str:
    out: list[str] = []
    _parts(ctx, p, out)
    s = "".join(out)
    s = re.sub(r"\\underline\{([^{}]*)\}\\underline\{([^{}]*)\}", r"\\underline{\1\2}", s)   # gộp các đoạn liền nhau
    return s.replace("\u00a0", " ").strip()


def _table(ctx, tbl) -> str:
    rows = []
    for tr in tbl.findall(f"{W}tr"):
        cells = []
        for tc in tr.findall(f"{W}tc"):
            cells.append(" ".join(_para(ctx, p) for p in tc.findall(f".//{W}p")).replace("&", r"\&").strip())
        rows.append(cells)
    if not rows:
        return ""
    n = max(len(r) for r in rows)
    body = "\\\\\\hline\n".join(" & ".join(r + [""] * (n - len(r))) for r in rows)
    return "\\begin{center}\\begin{tabular}{|" + "c|" * n + "}\\hline\n" + body + "\\\\\\hline\\end{tabular}\\end{center}"


def docx_to_latex(path: str, opts: DocxOptions | None = None) -> tuple[str, DocxReport]:
    """Văn bản LaTeX từng đoạn (mỗi đoạn một dòng) – dùng làm đầu vào cho wordconv.latex_text_to_ex."""
    opts = opts or DocxOptions()
    rep = triage(path)
    with zipfile.ZipFile(path) as zf:
        rels = {}
        if "word/_rels/document.xml.rels" in zf.namelist():
            for r in ET.fromstring(zf.read("word/_rels/document.xml.rels")).findall(f"{REL}Relationship"):
                rels[r.attrib.get("Id", "")] = r.attrib.get("Target", "")
        root = ET.fromstring(zf.read("word/document.xml"))
        ctx = _Ctx(zf, rels, opts, rep, os.path.splitext(path)[0])
        body = root.find(f"{W}body")
        lines = []
        for el in (body if body is not None else []):
            if el.tag == f"{W}p":
                s = _para(ctx, el)
                if s:
                    lines.append(s)
            elif el.tag == f"{W}tbl" and opts.tables:
                lines.append(_table(ctx, el))
    return "\n".join(lines) + "\n", rep


def docx_to_ex(path: str, opts: DocxOptions | None = None, tag: str = "") -> tuple[str, DocxReport]:
    """Word → các khối ex_test (hoặc văn bản thường nếu tuỳ chọn «chuyên đề»)."""
    from .wordconv import latex_text_to_ex
    text, rep = docx_to_latex(path, opts)
    if opts and opts.theory:
        return text, rep
    return "\n".join(latex_text_to_ex(text, tag)) + "\n", rep


def copy_images(src_dir: str, dst_dir: str):
    if os.path.isdir(src_dir):
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
