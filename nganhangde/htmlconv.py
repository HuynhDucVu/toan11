"""Chuyển nội dung LaTeX (khung ex_test) sang HTML để hiển thị trên trình duyệt / Moodle.

Công thức ($...$, $$...$$, \\(...\\), \\[...\\], môi trường toán) giữ nguyên để MathJax vẽ.
Phần chữ: \\textbf, \\textit, \\underline, \\\\, itemize/enumerate/itemchoice, center → thẻ HTML.
Hình TikZ, bảng tabular… không vẽ được trên web ⇒ thay bằng ô «[Hình vẽ – xem bản in]».
"""
from __future__ import annotations

import html
import re

from .texutil import read_group

MATH_RE = re.compile(
    r"(\$\$.*?\$\$|\$[^$]*?\$|\\\(.*?\\\)|\\\[.*?\\\]|"
    r"\\begin\{(equation\*?|align\*?|aligned|gather\*?|eqnarray\*?|cases|array)\}.*?\\end\{\2\})", re.S)
FIGURE_ENVS = ("tikzpicture", "tabular", "tikz", "figure", "minipage", "tabularx", "longtable", "pspicture")
LIST_ENVS = {"itemize": "ul", "enumerate": "ol", "itemchoice": "ol type='a'", "enumEX": "ol"}
DROP_CMDS = ("hfill", "vspace", "hspace", "medskip", "smallskip", "bigskip", "noindent", "centering",
             "newline", "par", "quad", "qquad", "displaystyle", "immini", "allowdisplaybreaks", "vfill",
             "Opensolutionfile", "Closesolutionfile", "label", "indapan")
STYLE_CMDS = {"textbf": "b", "textit": "i", "emph": "i", "underline": "u", "textup": "span", "text": "span",
              "textrm": "span", "mbox": "span", "textsf": "span", "texttt": "code"}

# Macro của cộng đồng ex_test đưa vào MathJax
MATHJAX_MACROS = {
    "heva": [r"\left\{\begin{aligned}#1\end{aligned}\right.", 1],
    "hoac": [r"\left[\begin{aligned}#1\end{aligned}\right.", 1],
    "vec": [r"\overrightarrow{#1}", 1],
    "R": r"\mathbb{R}", "N": r"\mathbb{N}", "Z": r"\mathbb{Z}", "Q": r"\mathbb{Q}",
    "dfrac": [r"\frac{#1}{#2}", 2], "tfrac": [r"\frac{#1}{#2}", 2], "colon": r"\mathpunct{:}",
}


IMAGE_HOOK = None          # hàm(tên file) → địa chỉ ảnh (vd Moodle @@PLUGINFILE@@), đặt tạm khi xuất

BE_RE = re.compile(r"\\(begin|end)\{([^}]*)\}")


def _env_end(t: str, env: str, start: int) -> int:
    """Vị trí của \\end{env} khớp (có tính lồng nhau) kể từ start; -1 nếu không có."""
    depth = 1
    for m in BE_RE.finditer(t, start):
        if m.group(2) != env:
            continue
        depth += 1 if m.group(1) == "begin" else -1
        if depth == 0:
            return m.start()
    return -1


def _split_items(inner: str) -> list[str]:
    """Tách \\item / \\itemch ở cấp ngoài cùng (bỏ qua các môi trường lồng bên trong)."""
    items, depth, last, started = [], 0, 0, False
    tok = re.compile(r"\\(begin|end)\{[^}]*\}|\\item(?:ch)?(?![A-Za-z])")
    for m in tok.finditer(inner):
        if m.group(1) == "begin":
            depth += 1
        elif m.group(1) == "end":
            depth -= 1
        elif depth == 0:
            if started:
                items.append(inner[last:m.start()])
            started, last = True, m.end()
    if started:
        items.append(inner[last:])
    return items


def _text_to_html(t: str) -> str:
    """Chuyển đoạn chữ (không có công thức) sang HTML."""
    t = t.replace("\\lq\\lq", "“").replace("\\rq\\rq", "”").replace("``", "“").replace("''", "”")
    t = re.sub(r"(?<!\\)%[^\n]*", "", t)                     # bỏ comment
    out, i = [], 0
    while i < len(t):
        c = t[i]
        if c == "\\":
            if t.startswith("\\\\", i):
                out.append("<br>")
                i += 2
                j = i
                if j < len(t) and t[j] == "[":            # \\[2pt]
                    k = t.find("]", j)
                    i = k + 1 if k > 0 else i
                continue
            m = re.match(r"\\([A-Za-z@]+)\*?", t[i:])
            if not m:                                     # \{ \} \% \& \_ \,
                nxt = t[i + 1:i + 2]
                out.append({"{": "{", "}": "}", "%": "%", "&": "&amp;", "_": "_", ",": " ", "#": "#",
                            "$": "$", " ": " "}.get(nxt, ""))
                i += 2
                continue
            name, j = m.group(1), i + m.end()
            if name == "begin":
                env, j2 = read_group(t, j) if j < len(t) and t[j] == "{" else ("", j)
                end_tag = "\\end{" + env + "}"
                k = _env_end(t, env, j2)
                inner = t[j2:k] if k >= 0 else t[j2:]
                i = (k + len(end_tag)) if k >= 0 else len(t)
                if env in FIGURE_ENVS:
                    out.append("<div class='fig'>[Hình vẽ / bảng – xem bản in]</div>")
                elif env in LIST_ENVS:
                    tag = LIST_ENVS[env]
                    items = _split_items(inner)
                    out.append(f"<{tag}>" + "".join(f"<li>{_text_to_html(x.strip())}</li>" for x in items)
                               + f"</{tag.split()[0]}>")
                elif env == "center":
                    out.append(f"<div style='text-align:center'>{_text_to_html(inner)}</div>")
                else:
                    out.append(_text_to_html(inner))
                continue
            if name in STYLE_CMDS and j < len(t) and t[j] == "{":
                arg, j2 = read_group(t, j)
                tag = STYLE_CMDS[name]
                out.append(f"<{tag}>{_text_to_html(arg)}</{tag}>")
                i = j2
                continue
            if name in ("includegraphics",):
                fname = ""
                while j < len(t) and t[j] in "[{":
                    br = t[j]
                    g, j = read_group(t, j, br, "]" if br == "[" else "}")
                    if br == "{":
                        fname = g.strip()
                src = IMAGE_HOOK(fname) if IMAGE_HOOK and fname else None
                out.append(f"<div class='fig'><img src='{src}' style='max-width:100%'></div>" if src else
                           "<div class='fig'>[Hình ảnh – xem bản in]</div>")
                i = j
                continue
            if name in DROP_CMDS:
                while j < len(t) and t[j] in "[{":         # bỏ luôn tham số
                    _, j = read_group(t, j, t[j], "]" if t[j] == "[" else "}")
                i = j
                continue
            if j < len(t) and t[j] == "{":                # lệnh lạ: giữ nội dung tham số
                arg, j2 = read_group(t, j)
                out.append(_text_to_html(arg))
                i = j2
                continue
            i = j
            continue
        if c in "{}":
            i += 1
            continue
        if c == "~":
            out.append("&nbsp;")
            i += 1
            continue
        if c == "\n" and t.startswith("\n\n", i):
            out.append("<br>")
            i += 2
            continue
        out.append(html.escape(c))
        i += 1
    return "".join(out)


def latex_to_html(s: str) -> str:
    """LaTeX → HTML; công thức giữ nguyên (đã escape <, >, &) cho MathJax."""
    math = []

    def keep(m):
        math.append(html.escape(m.group(0), quote=False))
        return f"\x00{len(math) - 1}\x00"
    s = MATH_RE.sub(keep, s)
    try:
        out = _text_to_html(s)
    except ValueError:                       # ngoặc lệch: hiển thị thô thay vì lỗi
        out = html.escape(s)
    out = re.sub(r"\x00(\d+)\x00", lambda m: math[int(m.group(1))], out)
    return re.sub(r"(<br>\s*){3,}", "<br><br>", out).strip()


def dollar_to_paren(s: str) -> str:
    """$..$ → \\(..\\), $$..$$ → \\[..\\] (định dạng Moodle/MathJax mặc định ưa dùng)."""
    s = re.sub(r"\$\$(.+?)\$\$", r"\\[\1\\]", s, flags=re.S)
    return re.sub(r"(?<!\\)\$(.+?)(?<!\\)\$", r"\\(\1\\)", s, flags=re.S)
