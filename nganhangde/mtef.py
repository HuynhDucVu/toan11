"""Đọc công thức MathType (đối tượng OLE «Equation Native», định dạng MTEF v3–v5) → LaTeX, không cần cài MathType/Word.

Công thức MathType trong file .docx là đối tượng nhúng word/embeddings/oleObjectN.bin (tệp OLE «Compound File») có luồng
«Equation Native» = 28 byte đầu + dòng byte MTEF. Mô-đun này đọc luồng đó (qua thư viện olefile), duyệt các bản ghi MTEF
(LINE, CHAR, TMPL, PILE, MATRIX, EMBELL…) và dựng mã LaTeX: phân số, căn, mũ/chỉ số, ngoặc, hệ ngoặc nhọn (\\heva, \\hoac),
tổng/tích/tích phân, giới hạn, vectơ, gạch ngang/ngã/mũ, ma trận…

Giới hạn: ký tự lạ ngoài bảng ánh xạ được giữ nguyên dạng Unicode; ghi chú số ký tự/khuôn mẫu chưa hỗ trợ ở `Result.warnings`.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field


class MtefError(ValueError):
    pass


# ---------------------------------------------------------------- Unicode → LaTeX
GREEK = {"α": "\\alpha", "β": "\\beta", "γ": "\\gamma", "δ": "\\delta", "ε": "\\varepsilon", "ϵ": "\\epsilon", "ζ": "\\zeta",
         "η": "\\eta", "θ": "\\theta", "ϑ": "\\vartheta", "ι": "\\iota", "κ": "\\kappa", "λ": "\\lambda", "μ": "\\mu",
         "ν": "\\nu", "ξ": "\\xi", "ο": "o", "π": "\\pi", "ϖ": "\\varpi", "ρ": "\\rho", "ϱ": "\\varrho", "σ": "\\sigma",
         "ς": "\\varsigma", "τ": "\\tau", "υ": "\\upsilon", "φ": "\\varphi", "ϕ": "\\phi", "χ": "\\chi", "ψ": "\\psi",
         "ω": "\\omega", "Γ": "\\Gamma", "Δ": "\\Delta", "Θ": "\\Theta", "Λ": "\\Lambda", "Ξ": "\\Xi", "Π": "\\Pi",
         "Σ": "\\Sigma", "Υ": "\\Upsilon", "Φ": "\\Phi", "Ψ": "\\Psi", "Ω": "\\Omega", "Α": "A", "Β": "B", "Ε": "E",
         "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Χ": "X"}
SYMBOLS = {"−": "-", "−": "-", "–": "-", "±": "\\pm", "∓": "\\mp", "×": "\\times", "÷": "\\div", "·": "\\cdot",
           "⋅": "\\cdot", "∙": "\\cdot", "∗": "*", "∘": "\\circ", "≤": "\\leq", "≥": "\\geq", "⩽": "\\leqslant", "⩾": "\\geqslant",
           "≠": "\\neq", "≈": "\\approx", "≡": "\\equiv", "∼": "\\sim", "≅": "\\cong", "≪": "\\ll", "≫": "\\gg", "∝": "\\propto",
           "∞": "\\infty", "∈": "\\in", "∉": "\\notin", "∋": "\\ni", "⊂": "\\subset", "⊃": "\\supset", "⊆": "\\subseteq",
           "⊇": "\\supseteq", "⊄": "\\not\\subset", "∪": "\\cup", "∩": "\\cap", "∅": "\\emptyset", "∖": "\\setminus",
           "→": "\\to", "←": "\\leftarrow", "↔": "\\leftrightarrow", "⇒": "\\Rightarrow", "⇐": "\\Leftarrow",
           "⇔": "\\Leftrightarrow", "↦": "\\mapsto", "↑": "\\uparrow", "↓": "\\downarrow", "∀": "\\forall",
           "∃": "\\exists", "∄": "\\nexists", "∂": "\\partial", "∇": "\\nabla", "∠": "\\angle", "⊥": "\\perp", "∥": "\\parallel",
           "∦": "\\nparallel", "∧": "\\wedge", "∨": "\\vee", "¬": "\\neg", "′": "'", "″": "''", "‴": "'''", "°": "^{\\circ}",
           "∑": "\\sum", "∏": "\\prod", "∫": "\\int", "∬": "\\iint", "∭": "\\iiint", "∮": "\\oint", "√": "\\sqrt{}", "…": "\\ldots",
           "⋯": "\\cdots", "⋮": "\\vdots", "⋱": "\\ddots", "△": "\\triangle", "□": "\\square", "⊕": "\\oplus", "⊗": "\\otimes",
           "∴": "\\therefore", "∵": "\\because", "ℓ": "\\ell", "ℏ": "\\hbar", "ℝ": "\\mathbb{R}", "ℕ": "\\mathbb{N}",
           "ℤ": "\\mathbb{Z}", "ℚ": "\\mathbb{Q}", "ℂ": "\\mathbb{C}", "⟨": "\\langle", "⟩": "\\rangle", "⌊": "\\lfloor",
           "⌋": "\\rfloor", "⌈": "\\lceil", "⌉": "\\rceil", "{": "\\{", "}": "\\}", "%": "\\%", "&": "\\&", "#": "\\#",
           "_": "\\_", "$": "\\$", "~": "\\sim", "^": "\\hat{}", "\\": "\\backslash", "|": "|", "‖": "\\|", " ": "\\ ",
           " ": "\\,", " ": "\\ ", " ": "\\quad", " ": "\\ ", " ": "\\ ", " ": "\\,",
           " ": "\\,", "⁡": "", "⁢": "", "⁣": "", "​": ""}
# Phông Symbol (8-bit, dùng khi bản ghi không có MTCode)
SYMBOL_FONT = {0x61: "α", 0x62: "β", 0x63: "χ", 0x64: "δ", 0x65: "ε", 0x66: "φ", 0x67: "γ", 0x68: "η", 0x69: "ι", 0x6A: "ϕ",
               0x6B: "κ", 0x6C: "λ", 0x6D: "μ", 0x6E: "ν", 0x6F: "ο", 0x70: "π", 0x71: "θ", 0x72: "ρ", 0x73: "σ", 0x74: "τ",
               0x75: "υ", 0x77: "ω", 0x78: "ξ", 0x79: "ψ", 0x7A: "ζ", 0x44: "Δ", 0x46: "Φ", 0x47: "Γ", 0x51: "Θ", 0x4C: "Λ",
               0x50: "Π", 0x53: "Σ", 0x57: "Ω", 0x59: "Ψ", 0x58: "Ξ", 0x2D: "−", 0xB1: "±", 0xA3: "≤", 0xB3: "≥", 0xB9: "≠",
               0xBB: "≈", 0xAE: "→", 0xAC: "←", 0xAB: "↔", 0xDE: "⇒", 0xDC: "⇐", 0xDB: "⇔", 0xA5: "∞", 0xB4: "×", 0xB8: "÷",
               0xD7: "⋅", 0xCE: "∈", 0xCF: "∉", 0xC8: "∪", 0xC7: "∩", 0xCC: "⊂", 0xCA: "⊆", 0xC9: "⊃", 0xC6: "∅", 0xB6: "∂",
               0xD1: "∇", 0xE5: "∑", 0xD5: "∏", 0xF2: "∫", 0xD6: "√", 0x22: "∀", 0x24: "∃", 0xB0: "°", 0xBC: "…", 0x5E: "⊥",
               0xBA: "≡", 0x40: "≅", 0x7E: "∼", 0xB5: "∝", 0xD9: "∧", 0xDA: "∨", 0xD8: "¬", 0xD0: "∠", 0x27: "∋"}
FUNCS = {"sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "coth", "log",
         "ln", "lg", "exp", "lim", "max", "min", "sup", "inf", "det", "dim", "ker", "gcd", "arg", "deg", "Pr", "hom", "mod"}
FACE = {1: "text", 2: "func", 3: "var", 4: "greek", 5: "greek", 6: "sym", 7: "vec", 8: "num", 9: "user", 10: "user",
        11: "sym", 12: "text"}

FENCES = {0: ("\\langle", "\\rangle"), 1: ("(", ")"), 2: ("\\{", "\\}"), 3: ("[", "]"), 4: ("|", "|"), 5: ("\\|", "\\|"),
          6: ("\\lfloor", "\\rfloor"), 7: ("\\lceil", "\\rceil"), 8: ("[", "]")}
INTERVAL = {0: ("(", ")"), 1: (")", "("), 2: ("[", "]"), 3: ("]", "[")}
BIGOPS = {15: "\\int", 16: "\\sum", 17: "\\prod", 18: "\\coprod", 19: "\\bigcup", 20: "\\bigcap", 21: "\\int", 22: "\\sum"}
EMBELL = {2: "\\dot{%s}", 3: "\\ddot{%s}", 4: "\\dddot{%s}", 8: "\\tilde{%s}", 9: "\\hat{%s}", 11: "\\vec{%s}",
          12: "\\overleftarrow{%s}", 13: "\\overleftrightarrow{%s}", 14: "\\vec{%s}", 15: "\\overleftarrow{%s}", 16: "\\bar{%s}",
          17: "\\bar{%s}", 19: "\\widehat{%s}", 24: "\\ddddot{%s}"}


@dataclass
class Result:
    latex: str = ""
    inline: bool = True
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------- bộ đọc nhị phân
class _R:
    def __init__(self, data: bytes, pos: int = 0):
        self.d, self.p = data, pos

    def eof(self):
        return self.p >= len(self.d)

    def u8(self):
        if self.p >= len(self.d):
            raise MtefError("hết dữ liệu")
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        return self.u8() | (self.u8() << 8)

    def uint(self):                       # số nguyên không dấu độ dài biến đổi (1 hoặc 3 byte)
        v = self.u8()
        return self.u16() if v == 255 else v

    def cstr(self):
        start = self.p
        while self.p < len(self.d) and self.d[self.p] != 0:
            self.p += 1
        s = self.d[start:self.p].decode("latin-1", "replace")
        self.p += 1
        return s


@dataclass
class Node:
    kind: str                              # line | char | tmpl | pile | matrix | embell
    opts: int = 0
    kids: list = field(default_factory=list)
    a: int = 0                             # char: typeface · tmpl: selector · pile: halign · matrix: rows
    b: int = 0                             # char: mtcode · tmpl: variation · pile: valign · matrix: cols
    c: int = 0                             # char: font position · tmpl: option
    mt: bool = True                        # char: có MTCode
    emb: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)


def _nudge(r: _R, opts: int):
    if opts & 0x08:
        a, b = r.u8(), r.u8()
        if a == 128 and b == 128:
            r.u16()
            r.u16()


def _dimension_array(r: _R):
    """Mảng kích thước: 1 byte số lượng, rồi dòng nibble (cao trước): mỗi kích thước = nibble đơn vị + các nibble giá trị
    + nibble kết thúc 0xF; số nibble lẻ thì thêm nibble 0 cho tròn byte."""
    n = r.u8()
    pending = []

    def nib():
        if not pending:
            b = r.u8()
            pending.extend((b >> 4, b & 15))
        return pending.pop(0)
    for _ in range(n):
        nib()                                          # đơn vị
        while nib() != 0xF:
            pass


def _read_records(r: _R, end_on_end: bool, ctx: dict) -> list[Node]:
    out = []
    while not r.eof():
        t = r.u8()
        if t == 0:                                    # END
            if end_on_end:
                return out
            continue
        if t == 1:                                    # LINE
            o = r.u8()
            _nudge(r, o)
            if o & 0x04:
                r.u16()
            if o & 0x02:
                _skip_ruler(r)
            n = Node("line", o)
            if not o & 0x01:
                n.kids = _read_records(r, True, ctx)
            out.append(n)
        elif t == 2:                                  # CHAR
            o = r.u8()
            _nudge(r, o)
            face = r.u8() - 128
            n = Node("char", o, a=face)
            n.mt = not o & 0x20
            if n.mt:
                n.b = r.u16()
            if o & 0x04:
                n.c = r.u8()
            elif o & 0x10:
                n.c = r.u16()
            if o & 0x01:
                n.emb = [x.a for x in _read_records(r, True, ctx) if x.kind == "embell"]
            out.append(n)
        elif t == 3:                                  # TMPL
            o = r.u8()
            _nudge(r, o)
            sel = r.u8()
            var = r.u8()
            if var & 0x80:
                var = (var & 0x7F) | (r.u8() << 8)
            topt = r.u8()
            n = Node("tmpl", o, a=sel, b=var, c=topt)
            n.kids = _read_records(r, True, ctx)
            out.append(n)
        elif t == 4:                                  # PILE
            o = r.u8()
            _nudge(r, o)
            ha, va = r.u8(), r.u8()
            if o & 0x02:
                _skip_ruler(r)
            n = Node("pile", o, a=ha, b=va)
            n.kids = _read_records(r, True, ctx)
            out.append(n)
        elif t == 5:                                  # MATRIX
            o = r.u8()
            _nudge(r, o)
            r.u8(), r.u8(), r.u8()                       # valign, h_just, v_just
            rows, cols = r.u8(), r.u8()
            r.p += (rows + 1 + 3) // 4 + (cols + 1 + 3) // 4
            n = Node("matrix", o, a=rows, b=cols)
            n.kids = _read_records(r, True, ctx)
            out.append(n)
        elif t == 6:                                  # EMBELL
            o = r.u8()
            _nudge(r, o)
            out.append(Node("embell", o, a=r.u8()))
        elif t == 7:                                  # RULER
            _skip_ruler(r, typed=False)
        elif t == 8:                                  # FONT_STYLE_DEF
            r.uint()
            r.u8()
        elif t == 9:                                  # SIZE
            b = r.u8()
            if b == 101:
                r.u16()
            elif b == 100:
                r.u8()
                r.u16()
            else:
                r.u8()
        elif 10 <= t <= 14:                           # FULL, SUB, SUB2, SYM, SUBSYM
            pass
        elif t == 15:                                 # COLOR
            r.uint()
        elif t == 16:                                 # COLOR_DEF
            o = r.u8()
            for _ in range(4 if o & 1 else 3):
                r.u16()
            if o & 4:
                r.cstr()
        elif t == 17:                                 # FONT_DEF
            r.uint()
            r.cstr()
        elif t == 18:                                 # EQN_PREFS
            r.u8()
            _dimension_array(r)
            _dimension_array(r)
            n = r.u8()
            for _ in range(n):
                if r.uint():
                    r.u8()
        elif t == 19:                                 # ENCODING_DEF
            r.cstr()
        elif t >= 100:                                # FUTURE
            r.p += r.uint()
        else:
            ctx["warn"].append(f"bản ghi MTEF lạ (loại {t})")
            raise MtefError(f"bản ghi MTEF lạ (loại {t})")
    return out


def _skip_ruler(r: _R, typed: bool = True):
    if typed:
        if r.u8() != 7:
            raise MtefError("thiếu RULER")
    n = r.u8()
    r.p += 3 * n


def parse(mtef: bytes) -> tuple[list[Node], dict]:
    """Chuỗi byte MTEF (không gồm 28 byte đầu OLE) → (cây bản ghi, thông tin tiêu đề)."""
    r = _R(mtef)
    ver = r.u8()
    if ver not in (3, 4, 5):
        raise MtefError(f"phiên bản MTEF {ver} chưa hỗ trợ")
    if ver != 5:
        raise MtefError("chỉ hỗ trợ MTEF 5 (MathType 4 trở lên)")
    r.u8()
    r.u8()
    r.u8()
    r.u8()                                            # platform, product, version, subversion
    key = r.cstr()
    opt = r.u8()
    ctx = {"warn": [], "key": key, "inline": bool(opt & 1)}
    return _read_records(r, False, ctx), ctx


# ---------------------------------------------------------------- dựng LaTeX
class _Render:
    def __init__(self):
        self.warn = []

    # ---- ký tự
    def char_code(self, n: Node) -> str:
        if n.mt:
            code = n.b
        else:
            code = n.c
            face = FACE.get(n.a, "")
            if n.a in (6, 11) or face == "greek":
                return SYMBOL_FONT.get(code, chr(code) if code else "")
        try:
            return chr(code)
        except (ValueError, OverflowError):
            return ""

    def render_char(self, n: Node) -> tuple[str, str]:
        """(loại, mã LaTeX) của một ký tự."""
        ch = self.char_code(n)
        kind = FACE.get(n.a, "var")
        if n.a == 24 or n.a == 22 or n.a == 23:        # SPACE / EXPAND / MARKER
            return "space", "\\," if ch not in (" ",) else "\\ "
        if kind in ("text", "func"):
            return kind, ch
        if ch in GREEK:
            tex = GREEK[ch]
        elif ch in SYMBOLS:
            tex = SYMBOLS[ch]
        elif ch == "−":
            tex = "-"
        elif ord(ch or "\0") < 128 or not ch:
            tex = ch
        else:
            tex = ch                                   # ký tự lạ: giữ nguyên Unicode
            self.warn.append(f"ký tự chưa ánh xạ U+{ord(ch):04X}")
        if kind == "vec" and tex.isalpha():
            tex = "\\mathbf{%s}" % tex
        for e in n.emb:
            if e in EMBELL:
                tex = EMBELL[e] % tex
            elif e in (5, 6, 18):
                tex = tex + {5: "'", 6: "''", 18: "'''"}[e]
        return kind, tex

    # ---- danh sách đối tượng trong một dòng
    def line(self, node: Node) -> str:
        toks: list[tuple[str, str]] = []
        for k in node.kids:
            if k.kind == "char":
                toks.append(self.render_char(k))
            elif k.kind == "tmpl":
                toks.append(("tmpl", self.tmpl(k)))
            elif k.kind == "pile":
                toks.append(("pile", self.pile(k)))
            elif k.kind == "matrix":
                toks.append(("matrix", self.matrix(k)))
            elif k.kind == "line":
                toks.append(("tmpl", self.line(k)))
        return self.join(toks)

    def join(self, toks) -> str:
        out: list[str] = []
        i = 0
        while i < len(toks):
            kind, tex = toks[i]
            if kind == "text":                          # gom các chữ trong phông Text thành \text{…}
                s = tex
                while i + 1 < len(toks) and toks[i + 1][0] == "text":
                    i += 1
                    s += toks[i][1]
                out.append("\\text{%s}" % _esc_text(s))
            elif kind == "func":                        # tên hàm: sin, lim… → \sin, \lim
                w = tex
                while i + 1 < len(toks) and toks[i + 1][0] == "func":
                    i += 1
                    w += toks[i][1]
                out.append("\\" + w if w in FUNCS else "\\mathrm{%s}" % w)
            elif kind == "num" and tex == "," and out and i + 1 < len(toks) and toks[i + 1][0] == "num" \
                    and re.search(r"\d$", out[-1]) and re.match(r"\d", toks[i + 1][1]):
                out.append("{,}")                       # dấu phẩy thập phân kiểu Việt Nam: 0{,}5
            else:
                out.append(tex)
            i += 1
        s = ""
        for part in out:                                # \alpha x → thêm dấu cách sau lệnh khi chữ cái theo sau
            if s and re.search(r"\\[A-Za-z]+$", s) and re.match(r"[A-Za-z]", part):
                s += " "
            s += part
        return s

    def slot(self, node) -> str:
        if node is None:
            return ""
        if node.kind == "line":
            return self.line(node)
        if node.kind == "pile":
            return self.pile(node)
        return ""

    def pile(self, n: Node) -> str:
        lines = [self.slot(k) for k in n.kids if k.kind == "line"]
        if len(lines) == 1:
            return lines[0]
        col = {1: "l", 2: "c", 3: "r"}.get(n.a, "c")
        return "\\begin{array}{%s} %s \\end{array}" % (col, " \\\\ ".join(lines))

    def matrix(self, n: Node) -> str:
        rows, cols = max(n.a, 1), max(n.b, 1)
        cells = [self.slot(k) for k in n.kids if k.kind == "line"]
        body = " \\\\ ".join(" & ".join(cells[r * cols:(r + 1) * cols]) for r in range(rows))
        return "\\begin{array}{%s} %s \\end{array}" % ("c" * cols, body)

    # ---- khuôn mẫu (phân số, căn, mũ…)
    def tmpl(self, n: Node) -> str:
        sel, var = n.a, n.b
        slots = [k for k in n.kids if k.kind in ("line", "pile")]
        s = [self.slot(x) for x in slots]

        def g(i):
            return s[i] if i < len(s) else ""
        if sel in FENCES or sel == 9:
            if sel == 9:
                lf, rf = INTERVAL.get(var & 0x0F, ("(", ")"))[0], INTERVAL.get((var >> 4) & 0x0F, ("(", ")"))[1]
                left_on, right_on = True, True
            else:
                lf, rf = FENCES[sel]
                left_on, right_on = bool(var & 1), bool(var & 2)
            body = g(0)
            main = slots[0] if slots else None
            # hệ phương trình (ngoặc nhọn/vuông bên trái, không ngoặc phải) → \heva / \hoac theo ex_test
            if left_on and not right_on and sel in (2, 3) and main is not None and any(k.kind == "pile" for k in main.kids):
                pile = next(k for k in main.kids if k.kind == "pile")
                rows = " \\\\ ".join(self.slot(k) for k in pile.kids if k.kind == "line")
                return ("\\heva{%s}" if sel == 2 else "\\hoac{%s}") % rows
            return f"\\left{lf if left_on else '.'} {body} \\right{rf if right_on else '.'}"
        if sel == 10:                                     # căn
            rad, idx = g(0), g(1)
            return "\\sqrt[%s]{%s}" % (idx, rad) if idx else "\\sqrt{%s}" % rad
        if sel == 11:                                     # phân số
            if var & 2:
                return "{%s}/{%s}" % (g(0), g(1))
            return "\\dfrac{%s}{%s}" % (g(0), g(1))
        if sel in (12, 13):                               # gạch dưới / gạch trên
            cmd = "\\underline" if sel == 12 else "\\overline"
            return (cmd + "{%s}") % g(0) if not var & 1 else (cmd + "{" + cmd + "{%s}}") % g(0)
        if sel == 14:                                     # mũi tên có chữ
            top, bottom = g(0), g(1)
            arrow = "\\xrightarrow" if not var & 0x10 else "\\xleftarrow"
            return arrow + ("[%s]" % bottom if bottom else "") + "{%s}" % top
        if sel in BIGOPS:                                 # tổng, tích, tích phân
            up, low = (g(1), g(2)) if len(s) >= 3 else ("", "")
            op = BIGOPS[sel]
            if sel == 15:                                 # tích phân: 1 đơn, 2 kép, 3 ba, 4/8/12 đường cong kín
                k = var & 0x0F
                op = {1: "\\int", 2: "\\iint", 3: "\\iiint", 4: "\\oint", 8: "\\oint", 12: "\\oint"}.get(k, "\\int")
            sub = ("_{%s}" % low) if low else ""
            sup = ("^{%s}" % up) if up else ""
            return f"{op}{sub}{sup} {g(0)}".rstrip()
        if sel == 23:                                     # lim
            main, low = g(0), g(1)
            main = "\\lim" if main in ("lim", "\\lim") else main
            return (main if main.startswith("\\") else "\\mathop{%s}" % main) + ("\\limits_{%s}" % low if low else "")
        if sel in (24, 25):                               # ngoặc ngang
            cmd = {24: "\\overbrace", 25: "\\overbracket"}[sel] if var & 1 else {24: "\\underbrace", 25: "\\underbracket"}[sel]
            note = g(1)
            return cmd + "{%s}" % g(0) + (("^{%s}" if var & 1 else "_{%s}") % note if note else "")
        if sel == 26:                                     # chia dài
            return "%s\\overline{\\smash{)}%s}" % (g(1), g(0)) if False else g(1) or g(0)
        if sel in (27, 28, 29):                           # chỉ số dưới / mũ
            sub, sup = g(0), g(1)
            if sel == 27:
                return "_{%s}" % sub
            if sel == 28:
                return "^{%s}" % (sup or sub)
            return "_{%s}^{%s}" % (sub, sup)
        if sel == 31:                                     # vectơ
            arrow = "\\overleftarrow" if (var & 1 and not var & 2) else "\\overrightarrow"
            if var & 4:
                arrow = arrow.replace("over", "under")
            return arrow + "{%s}" % g(0)
        if sel == 32:
            return "\\widetilde{%s}" % g(0)
        if sel == 33:
            return "\\widehat{%s}" % g(0)
        if sel == 34:
            return "\\overset{\\frown}{%s}" % g(0)
        if sel in (35, 36, 30):
            return g(0)
        if sel == 37:
            return "\\boxed{%s}" % g(0)
        self.warn.append(f"khuôn mẫu MathType số {sel} chưa hỗ trợ")
        return " ".join(x for x in s if x)


def _esc_text(s: str) -> str:
    return re.sub(r"([%&#_$])", r"\\\1", s.replace("\\", "\\textbackslash{}")).replace("{", "\\{").replace("}", "\\}") \
        .replace("\\textbackslash\\{\\}", "\\textbackslash{}")


def mtef_to_latex(mtef: bytes) -> Result:
    nodes, ctx = parse(mtef)
    rd = _Render()
    parts = []
    for n in nodes:
        if n.kind == "line":
            parts.append(rd.line(n))
        elif n.kind == "pile":
            parts.append(rd.pile(n))
    tex = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    res = Result(tex, ctx.get("inline", True), sorted(set(rd.warn)))
    return res


def native_to_latex(stream: bytes) -> Result:
    """Luồng «Equation Native» (28 byte đầu + MTEF) → LaTeX."""
    if len(stream) < 30:
        raise MtefError("luồng quá ngắn")
    hdr = stream[0] | (stream[1] << 8)
    if not 20 <= hdr <= 64:
        hdr = 28
    return mtef_to_latex(stream[hdr:])


def ole_to_latex(ole_bytes: bytes) -> Result:
    """Nội dung file word/embeddings/oleObjectN.bin → LaTeX (cần thư viện olefile)."""
    import olefile
    ole = olefile.OleFileIO(io.BytesIO(ole_bytes))
    try:
        if not ole.exists("Equation Native"):
            raise MtefError("không phải công thức MathType (thiếu «Equation Native»)")
        return native_to_latex(ole.openstream("Equation Native").read())
    finally:
        ole.close()
