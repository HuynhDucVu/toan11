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
O = "{urn:schemas-microsoft-com:office:office}"


@dataclass
class DocxOptions:
    tables: bool = True              # chuyển bảng thành tabular
    images: bool = True              # xuất hình ra thư mục và chèn \includegraphics
    image_dir: str = ""              # thư mục lưu hình (mặc định: <tên file>_hinh cạnh file Word)
    chem: bool = False               # môn Hoá: chỉ số dưới/trên trong chữ thường (H₂O → H_{2}O)
    replacements: list[tuple[str, str]] = field(default_factory=list)   # «thay thế cá nhân»
    theory: bool = False             # chuyên đề/lý thuyết: giữ nguyên văn bản, không nhận dạng câu hỏi
    ds: bool = True                  # nhận dạng câu Đúng/Sai (a) b) c) d)); tắt thì các ý a) b)… nằm trong đề bài


@dataclass
class DocxReport:
    omml: int = 0
    mathtype_ole: int = 0
    images: int = 0
    tables: int = 0
    mathtype_ok: int = 0             # công thức MathType đã đọc trực tiếp (MTEF → LaTeX)
    mathtype_fail: int = 0
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


_STRUCT = re.compile(r"^\s*(?:\\textbf\{)?\s*(?:Câu|Bài)\s*\d+|^\s*(?:Lời giải|Hướng dẫn|Trả lời|Đáp án|Đáp số|PHẦN|Phần)|^\s*\[\[",
                     re.I)


def _underlined(r) -> bool:
    rpr = r.find(f"{W}rPr")
    u = rpr.find(f"{W}u") if rpr is not None else None
    return u is not None and u.attrib.get(f"{W}val", "single") != "none"


def _style(r):
    rpr = r.find(f"{W}rPr")
    if rpr is None:
        return None
    va = rpr.find(f"{W}vertAlign")
    return va.attrib.get(f"{W}val") if va is not None else None


def _wval(el, tag, default=""):
    """Giá trị w:val của phần tử con <w:tag> (không gian tên WordprocessingML)."""
    x = el.find(f"{W}{tag}") if el is not None else None
    return x.attrib.get(f"{W}val", default) if x is not None else default


def _roman(n: int, upper=True) -> str:
    out = ""
    for v, r in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                 (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += r
            n -= v
    return out if upper else out.lower()


def _fmt_number(n: int, fmt: str) -> str:
    if fmt == "upperLetter":
        return chr(ord("A") + (n - 1) % 26) * (1 + (n - 1) // 26)
    if fmt == "lowerLetter":
        return chr(ord("a") + (n - 1) % 26) * (1 + (n - 1) // 26)
    if fmt == "upperRoman":
        return _roman(n, True)
    if fmt == "lowerRoman":
        return _roman(n, False)
    if fmt == "decimalZero":
        return f"{n:02d}"
    return str(n)


class Numbering:
    """Nhãn danh sách đánh số TỰ ĐỘNG của Word («Câu 1.», «A.», «a)»…) – chữ này không nằm trong văn bản đoạn nên
    phải tính lại từ numbering.xml (kiểu số, mẫu «Câu %1.», số bắt đầu, đặt lại khi sang mục cha)."""

    def __init__(self, zf):
        self.abstract: dict[str, dict[int, dict]] = {}
        self.nums: dict[str, tuple[str, dict[int, int]]] = {}
        self.style_num: dict[str, tuple[str, int]] = {}
        self.counters: dict[tuple[str, int], int] = {}
        names = zf.namelist()
        if "word/numbering.xml" in names:
            root = ET.fromstring(zf.read("word/numbering.xml"))
            for an in root.findall(f"{W}abstractNum"):
                lv = {}
                for l in an.findall(f"{W}lvl"):
                    il = int(l.attrib.get(f"{W}ilvl", "0"))
                    lv[il] = {"fmt": _wval(l, "numFmt", "decimal"), "text": _wval(l, "lvlText", f"%{il + 1}."),
                              "start": int(_wval(l, "start", "1") or 1), "marked": _marked(l)}
                self.abstract[an.attrib.get(f"{W}abstractNumId", "")] = lv
            for n in root.findall(f"{W}num"):
                aid = _wval(n, "abstractNumId", "")
                ov = {}
                for o in n.findall(f"{W}lvlOverride"):
                    so = o.find(f"{W}startOverride")
                    if so is not None:
                        ov[int(o.attrib.get(f"{W}ilvl", "0"))] = int(so.attrib.get(f"{W}val", "1"))
                self.nums[n.attrib.get(f"{W}numId", "")] = (aid, ov)
        if "word/styles.xml" in names:
            for st in ET.fromstring(zf.read("word/styles.xml")).findall(f"{W}style"):
                np_ = st.find(f"{W}pPr/{W}numPr")
                if np_ is not None:
                    nid = _wval(np_, "numId", "")
                    if nid:
                        self.style_num[st.attrib.get(f"{W}styleId", "")] = (nid, int(_wval(np_, "ilvl", "0") or 0))

    def label(self, p) -> tuple[str, bool] | None:
        """(chữ nhãn, nhãn có gạch chân/tô màu) cho đoạn p; None nếu đoạn không đánh số tự động."""
        ppr = p.find(f"{W}pPr")
        if ppr is None:
            return None
        np_ = ppr.find(f"{W}numPr")
        nid, il = ("", 0)
        if np_ is not None:
            nid, il = _wval(np_, "numId", ""), int(_wval(np_, "ilvl", "0") or 0)
        sid = _wval(ppr, "pStyle", "")
        if (not nid) and sid in self.style_num:
            nid, il = self.style_num[sid]
        if not nid or nid == "0" or nid not in self.nums:
            return None
        aid, ov = self.nums[nid]
        lv = self.abstract.get(aid, {})
        cur = lv.get(il)
        if cur is None:
            return None
        key = (nid, il)
        self.counters[key] = self.counters.get(key, ov.get(il, cur["start"]) - 1) + 1
        for k in [k for k in self.counters if k[0] == nid and k[1] > il]:
            del self.counters[k]                              # sang mục mới ⇒ các cấp con đếm lại từ đầu
        if cur["fmt"] in ("bullet", "none"):
            return None
        text = cur["text"]
        for j in range(il + 1):
            c = self.counters.get((nid, j))
            if c is None:
                c = lv.get(j, {"start": 1})["start"]
            text = text.replace(f"%{j + 1}", _fmt_number(c, lv.get(j, cur)["fmt"]))
        if re.search(r"%\d", text):
            text = re.sub(r"%\d", "", text)
        ppr_r = ppr.find(f"{W}rPr")
        marked = cur["marked"] or (ppr_r is not None and _marked(ppr))
        return text.strip(), marked


class _Ctx:
    def __init__(self, zf, rels, opts, rep, base):
        self.zf, self.rels, self.opts, self.rep, self.base = zf, rels, opts, rep, base
        self.n_img = 0
        self.num = Numbering(zf)


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


def _mathtype_object(ctx: _Ctx, run) -> str | None:
    """Công thức MathType (đối tượng OLE trong w:object) → «$…$»; None nếu run không chứa công thức MathType."""
    ole = None
    for o in run.iter(f"{O}OLEObject"):
        ole = o
        break
    if ole is None or not (ole.attrib.get("ProgID", "") or "").startswith("Equation"):
        return None
    target = ctx.rels.get(ole.attrib.get(f"{R}id", ""), "")
    name = "word/" + target.lstrip("/").replace("word/", "", 1) if target else ""
    try:
        from .mtef import ole_to_latex
        res = ole_to_latex(ctx.zf.read(name))
        ctx.rep.mathtype_ok += 1
        return "$" + res.latex + "$" if res.latex else ""
    except Exception as e:  # noqa: BLE001 – olefile thiếu, MTEF lạ, file hỏng…
        ctx.rep.mathtype_fail += 1
        if ctx.rep.mathtype_fail == 1:
            ctx.rep.warnings.append(f"Có công thức MathType không đọc được ({type(e).__name__}: {str(e)[:80]}).")
        return "$\\text{[công thức]}$"


def _parts(ctx: _Ctx, elem, out: list[str]):
    for c in elem:
        t = c.tag
        if t == f"{W}r":
            mt = _mathtype_object(ctx, c)
            if mt is not None:
                out.append(mt)
                continue
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
            if _marked(c) and txt.strip() and not getattr(ctx, "skip_mark", False):
                m = re.match(r"^(\s*[A-Da-d]\s*[.)])(.*)$", txt, re.S) if not "".join(out).strip() else None
                if m:                                        # nhãn phương án gạch chân/tô màu = đáp án đúng
                    txt = f"\\underline{{{m.group(1).strip()}}}{m.group(2)}"
                elif _underlined(c) and not _STRUCT.match(txt):
                    txt = f"\\underline{{{txt}}}"          # gạch chân thật (không phải chỉ tô màu); «Câu N», «Lời giải»… giữ nguyên
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


def _first_run_marked(p) -> bool:
    for r in p.iter(f"{W}r"):
        if any((t.text or "").strip() for t in r.iter(f"{W}t")):
            return _marked(r)
    return False


def _para(ctx, p) -> str:
    out: list[str] = []
    lab = ctx.num.label(p)                       # «Câu 1.», «A.», «a)» do Word tự đánh số
    opt_marked = bool(lab and re.fullmatch(r"[A-Da-d][.)]", lab[0]) and (lab[1] or _first_run_marked(p)))
    ctx.skip_mark = opt_marked                   # đáp án gạch chân: chỉ đánh dấu nhãn, không gạch chân lẫn vào nội dung
    try:
        _parts(ctx, p, out)
    finally:
        ctx.skip_mark = False
    s = "".join(out)
    if lab and lab[0] and s.strip():
        text = f"\\underline{{{lab[0]}}}" if opt_marked else lab[0]
        s = text + " " + s
    s = re.sub(r"\\underline\{([^{}]*)\}\\underline\{([^{}]*)\}", r"\\underline{\1\2}", s)   # gộp các đoạn liền nhau
    s = s.replace("\u00a0", " ").strip()
    s = re.sub(r"\\\[(.+?)\\\]", lambda m: "$$" + m.group(1).strip() + "$$", s, flags=re.S)      # \[ … \] (Toggle TeX)
    s = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", s, flags=re.S)       # \( … \)
    return s.replace("\\frac{", "\\dfrac{").replace("\\ddfrac{", "\\dfrac{")


def _table(ctx, tbl, keep_table: bool = True) -> str:
    rows = []
    raw = []
    for tr in tbl.findall(f"{W}tr"):
        cells = []
        for tc in tr.findall(f"{W}tc"):
            txt = " ".join(x for x in (_para(ctx, p) for p in tc.findall(f".//{W}p")) if x).strip()
            raw.append(txt)
            cells.append(txt.replace("&", r"\&"))
        rows.append(cells)
    if not rows:
        return ""
    # bảng chỉ để dàn 4 phương án / 4 ý (mỗi ô một mục: A. B. C. D. hoặc a) b) c) d); 1×4 hay 2×2) ⇒ trả về dòng chữ thường
    flat = [c for c in raw if c]
    marks = [re.match(r"^\s*(?:\\underline\{)?\s*([A-Da-d])\s*[.)]", c) for c in flat]
    if len(flat) == 4 and all(marks):
        seq = "".join(m.group(1) for m in marks)
        if seq == "ABCD":
            return " ".join(flat)
        if seq == "abcd":
            return "\n".join(flat)
    if not keep_table:
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
            elif el.tag == f"{W}tbl":
                t = _table(ctx, el, opts.tables)
                if t:
                    lines.append(t)
    return "\n".join(lines) + "\n", rep


def docx_to_ex(path: str, opts: DocxOptions | None = None, tag: str = "") -> tuple[str, DocxReport]:
    """Word → các khối ex_test (hoặc văn bản thường nếu tuỳ chọn «chuyên đề»)."""
    from .wordconv import latex_text_to_ex
    text, rep = docx_to_latex(path, opts)
    if opts and opts.theory:
        return text, rep
    return "\n".join(latex_text_to_ex(text, tag, ds=getattr(opts, "ds", True))) + "\n", rep


def copy_images(src_dir: str, dst_dir: str):
    if os.path.isdir(src_dir):
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)


def diagnose_docx(path: str, opts: DocxOptions | None = None, n_lines: int = 40) -> str:
    """Báo cáo chẩn đoán khi chuyển Word ra ít/không có câu hỏi: phần mềm «nhìn thấy» gì trong file.
    Có thể gửi báo cáo này cho người hỗ trợ (chỉ gồm đầu các dòng chữ, không gồm hình)."""
    import collections
    L = [f"File: {os.path.basename(path)}"]
    try:
        rep = triage(path)
        L.append(f"Công thức Word (OMML): {rep.omml} · MathType dạng đối tượng (OLE): {rep.mathtype_ole} · "
                 f"hình: {rep.images} · bảng: {rep.tables}")
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            L.append("Thành phần: " + ", ".join(n for n in names if n.startswith("word/") and n.count("/") == 1)[:300])
            root = ET.fromstring(zf.read("word/document.xml"))
            ps = root.findall(f".//{W}p")
            numbered = sum(1 for p in ps if p.find(f"{W}pPr/{W}numPr") is not None)
            L.append(f"Số đoạn: {len(ps)} · đoạn đánh số tự động: {numbered} · khung chữ (textbox): "
                     f"{len(root.findall(f'.//{W}txbxContent'))} · thay đổi theo dõi (ins/del): "
                     f"{len(root.findall(f'.//{W}ins')) + len(root.findall(f'.//{W}del'))}")
        text, _ = docx_to_latex(path, opts)
        lines = [ln for ln in text.split("\n") if ln.strip()]
        from .wordconv import ANS_RE, DS_RE, OPT_RE, Q_START
        c = collections.Counter()
        for ln in lines:
            c["Câu N"] += bool(Q_START.match(ln))
            c["A./B./C./D."] += bool(OPT_RE.match(ln.strip()))
            c["a)/b)/c)/d)"] += bool(DS_RE.match(ln))
            c["Đáp án:"] += bool(ANS_RE.match(ln))
            c["có \\underline"] += "\\underline" in ln
        L.append("Dòng chữ app đọc được: %d · nhận dạng: " % len(lines) + ", ".join(f"{k}={v}" for k, v in c.items()))
        L.append("--- %d dòng đầu (cắt 110 ký tự) ---" % n_lines)
        L += [ln[:110] for ln in lines[:n_lines]]
    except Exception as e:  # noqa: BLE001
        L.append(f"Không đọc được file: {type(e).__name__}: {e}")
    return "\n".join(L) + "\n"
