"""Draw Studio – các hình hay gặp trong đề Toán THPT, sinh mã TikZ thuần (biên dịch được ở mọi máy):

* number_line_tikz   – biểu diễn tập nghiệm trên trục số: (-∞;-2] ∪ (1;3) ∪ {5}, gạch bỏ phần không thuộc;
* region_tikz        – miền nghiệm hệ bất phương trình bậc nhất hai ẩn (gạch bỏ phần không thuộc miền nghiệm),
                       kèm toạ độ các đỉnh và giá trị F = ax + by tại đỉnh (bài toán tối ưu);
* graph_plus_tikz    – đồ thị có tiệm cận đứng/ngang/xiên tự động và tô miền tích phân;
* solid_tikz         – thư viện hình khối: hình chóp, lăng trụ, hình hộp, lập phương, tứ diện, nón, trụ, cầu.
"""
from __future__ import annotations

import math
import re

from .drawgen import FuncError, _poles, _snap, graph_tikz, make_func, nice, to_python, FUNCS

INF = re.compile(r"^[+]?(inf|∞|\+∞|vc|\\infty|\+\\infty)$", re.I)
NINF = re.compile(r"^-(inf|∞|vc|\\infty)$", re.I)


def f2(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) > 1e-9 else "0"


# ================================================================ trục số
def _num(t: str) -> float:
    t = t.strip().replace("\\infty", "inf").replace("$", "")
    if INF.match(t):
        return math.inf
    if NINF.match(t):
        return -math.inf
    f = make_func(t)                                    # cho phép 1/2, sqrt(2), -3/4
    v = f(0)
    if math.isnan(v):
        raise FuncError(f"Không hiểu số «{t}»")
    return v


def parse_set(text: str):
    """'(-inf;-2] U (1;3) U {5}' → ([(a, b, a_closed, b_closed)], [điểm lẻ]). Hỗ trợ ∪, U, hợp; dấu ; hoặc ,"""
    s = text.replace("∪", "U").replace("\\cup", "U").replace("ℝ", "(-inf;inf)").replace("\\mathbb{R}", "(-inf;inf)")
    s = s.replace("$", "").replace("\\left", "").replace("\\right", "").replace("\\{", "{").replace("\\}", "}")
    ivs, pts = [], []
    for m in re.finditer(r"([\[(])\s*([^;,\])]+)\s*[;,]\s*([^\])]+?)\s*([\])])|\{([^}]*)\}", s):
        if m.group(5) is not None:
            pts += [_num(x) for x in re.split(r"[;,]", m.group(5)) if x.strip()]
        else:
            a, b = _num(m.group(2)), _num(m.group(3))
            if a >= b:
                raise FuncError(f"Khoảng {m.group(0)} không hợp lệ")
            ivs.append((a, b, m.group(1) == "[" and a > -math.inf, m.group(4) == "]" and b < math.inf))
    if not ivs and not pts:
        raise FuncError("Không đọc được tập hợp – ví dụ: (-inf;-2] U (1;3) U {5}")
    return ivs, pts


def number_line_tikz(text: str, hatch_excluded: bool = True, unit: float = 1.6) -> str:
    """Trục số. Các mốc được đặt cách đều theo thứ tự (không theo tỉ lệ) cho dễ đọc."""
    ivs, pts = parse_set(text)
    marks = sorted({v for a, b, _, _ in ivs for v in (a, b) if math.isfinite(v)} | set(pts))
    pos = {v: (i + 1) * unit for i, v in enumerate(marks)}
    left, right = 0.0, (len(marks) + 1) * unit

    def X(v):
        return left if v == -math.inf else right if v == math.inf else pos[v]

    lines = ["\\begin{tikzpicture}[>=stealth]", f"\t\\draw[->] ({left - 0.2},0)--({right + 0.3},0);"]
    # phần không thuộc tập nghiệm: các khoảng còn lại
    keep = sorted((X(a), X(b)) for a, b, _, _ in ivs)
    gaps, cur = [], left
    for a, b in keep:
        if a > cur:
            gaps.append((cur, a))
        cur = max(cur, b)
    if cur < right:
        gaps.append((cur, right))
    for a, b in gaps:
        if hatch_excluded:
            n = max(1, int((b - a) / 0.15))
            for k in range(n):
                x = a + (b - a) * (k + 0.5) / n
                lines.append(f"\t\\draw[gray] ({f2(x - 0.06)},-0.12)--({f2(x + 0.06)},0.12);")
    if not hatch_excluded:
        for a, b in keep:
            lines.append(f"\t\\draw[very thick,blue] ({f2(a)},0)--({f2(b)},0);")
    for a, b, ca, cb in ivs:
        for v, closed, side in ((a, ca, "left"), (b, cb, "right")):
            if math.isfinite(v):
                br = ("[" if closed else "(") if side == "left" else ("]" if closed else ")")
                lines.append(f"\t\\node[blue] at ({f2(X(v))},0){{\\Large ${br}$}};")
    for v in pts:
        lines.append(f"\t\\fill[blue] ({f2(X(v))},0) circle (2pt);")
    for v in marks:
        lines.append(f"\t\\node[below=3pt] at ({f2(X(v))},0){{${nice(v)}$}};")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)


# ================================================================ miền nghiệm
INEQ_RE = re.compile(r"^(.*?)(<=|>=|≤|≥|<|>)(.*)$")


def _lin(expr: str):
    """Hệ số (a, b, c) của biểu thức tuyến tính ax + by + c."""
    code = to_python(expr)
    code = re.sub(r"\by\s*\(", "y*(", code)
    if "__" in code or "import" in code or "lambda" in code:
        raise FuncError("Biểu thức không hợp lệ")
    try:
        c = compile(code, "<bpt>", "eval")
    except SyntaxError as e:
        raise FuncError(f"Sai cú pháp: {expr}") from e
    if set(c.co_names) - set(FUNCS) - {"x", "y"}:
        raise FuncError(f"Chỉ dùng biến x, y: {expr}")

    def g(x, y):
        return float(eval(c, {"__builtins__": {}}, {**FUNCS, "x": x, "y": y}))  # noqa: S307
    c0 = g(0, 0)
    a, b = g(1, 0) - c0, g(0, 1) - c0
    if abs(g(2, 3) - (2 * a + 3 * b + c0)) > 1e-9 or abs(g(-1.5, 7) - (-1.5 * a + 7 * b + c0)) > 1e-9:
        raise FuncError(f"Không phải bậc nhất: {expr}")
    return a, b, c0


def parse_ineq(text: str):
    """'x + 2y <= 4' → (a, b, c, strict) với nghĩa a x + b y + c ≤ 0 (strict: <)."""
    m = INEQ_RE.match(text.strip().replace("≤", "<=").replace("≥", ">="))
    if not m:
        raise FuncError(f"Không phải bất phương trình: {text}")
    l_, op, r_ = m.groups()
    a1, b1, c1 = _lin(l_)
    a2, b2, c2 = _lin(r_)
    a, b, c = a1 - a2, b1 - b2, c1 - c2
    if op in (">", ">="):
        a, b, c = -a, -b, -c
    if abs(a) < 1e-12 and abs(b) < 1e-12:
        raise FuncError(f"Bất phương trình không chứa x, y: {text}")
    return a, b, c, op in ("<", ">")


def _clip(poly, a, b, c):
    """Phần đa giác thoả a x + b y + c ≤ 0 (Sutherland–Hodgman)."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        fp, fq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
        if fp <= 1e-12:
            out.append(p)
        if (fp < -1e-12 and fq > 1e-12) or (fp > 1e-12 and fq < -1e-12):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _line_label(a, b, c) -> str:
    def term(k, v, first):
        if abs(k) < 1e-12:
            return ""
        s = "-" if k < 0 else ("" if first else "+")
        k = abs(k)
        return s + ("" if abs(k - 1) < 1e-12 else nice(k)) + v
    s = term(a, "x", True) + term(b, "y", not term(a, "x", True))
    cc = -c
    return f"{s}={nice(cc)}"


def region(ineqs: list[str], box=(-1, 6, -1, 6)):
    """(các bpt đã phân tích, đa giác miền nghiệm trong khung)."""
    xmin, xmax, ymin, ymax = box
    parsed = [parse_ineq(t) for t in ineqs if t.strip()]
    poly = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    for a, b, c, _ in parsed:
        poly = _clip(poly, a, b, c)
        if not poly:
            break
    return parsed, poly


def vertices(ineqs: list[str]):
    """Các đỉnh của miền nghiệm (khi miền bị chặn) – giao của từng cặp đường thẳng thoả mọi bpt."""
    parsed = [parse_ineq(t) for t in ineqs if t.strip()]
    pts = []
    for i in range(len(parsed)):
        for j in range(i + 1, len(parsed)):
            a1, b1, c1, _ = parsed[i]
            a2, b2, c2, _ = parsed[j]
            d = a1 * b2 - a2 * b1
            if abs(d) < 1e-12:
                continue
            x, y = (b1 * c2 - b2 * c1) / d, (a2 * c1 - a1 * c2) / d
            if all(a * x + b * y + c <= 1e-9 for a, b, c, _ in parsed):
                if not any(abs(x - p[0]) < 1e-9 and abs(y - p[1]) < 1e-9 for p in pts):
                    pts.append((x, y))
    cx = sum(p[0] for p in pts) / len(pts) if pts else 0
    cy = sum(p[1] for p in pts) / len(pts) if pts else 0
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def optimize(ineqs: list[str], objective: str):
    """Giá trị F tại các đỉnh: [(x, y, F)], cùng (min, max). Chỉ đúng khi miền nghiệm bị chặn."""
    a, b, c = _lin(objective)
    rows = [(x, y, a * x + b * y + c) for x, y in vertices(ineqs)]
    if not rows:
        return [], None, None
    return rows, min(r[2] for r in rows), max(r[2] for r in rows)


def region_tikz(ineqs: list[str], xmin=-1, xmax=6, ymin=-1, ymax=6, label_vertices=True, scale=0.8) -> str:
    """Gạch bỏ (tô xám) phần mặt phẳng KHÔNG thoả từng bất phương trình – miền để trắng là miền nghiệm."""
    parsed, _ = region(ineqs, (xmin, xmax, ymin, ymax))
    box = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    lines = [f"\\begin{{tikzpicture}}[scale={scale},>=stealth]"]
    for a, b, c, _ in parsed:
        bad = _clip(box, -a, -b, -c)                 # phần a x + b y + c ≥ 0 (không thoả)
        if len(bad) >= 3:
            lines.append("\t\\fill[gray!35] " + "--".join(f"({f2(x)},{f2(y)})" for x, y in bad) + "--cycle;")
    lines.append(f"\t\\draw[->] ({xmin - 0.3},0)--({xmax + 0.4},0) node[below left]{{$x$}};")
    lines.append(f"\t\\draw[->] (0,{ymin - 0.3})--(0,{ymax + 0.4}) node[below left]{{$y$}};")
    lines.append("\t\\node[below left] at (0,0){$O$};")
    for a, b, c, strict in parsed:
        seg = _clip(_clip(box, a, b, c), -a, -b, -c)   # đoạn thẳng a x + b y + c = 0 trong khung
        pts = sorted({(round(x, 9), round(y, 9)) for x, y in seg})
        if len(pts) >= 2:
            p, q = pts[0], pts[-1]
            lab = _line_label(a, b, c)
            if abs(b) < 1e-12 and abs(a + 1) < 1e-12 or abs(a) < 1e-12 and abs(b + 1) < 1e-12:
                lab = _line_label(-a, -b, -c)
            lines.append(f"\t\\draw[thick{',dashed' if strict else ''}] ({f2(p[0])},{f2(p[1])})--"
                         f"({f2(q[0])},{f2(q[1])}) node[pos=0.92,above,sloped,font=\\scriptsize]{{${lab}$}};")
    if label_vertices:
        for x, y in vertices(ineqs):
            if xmin <= x <= xmax and ymin <= y <= ymax:
                lines.append(f"\t\\fill ({f2(x)},{f2(y)}) circle (1.5pt) node[above right,font=\\scriptsize]"
                             f"{{$({nice(x)};{nice(y)})$}};")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)


# ================================================================ đồ thị có tiệm cận, tô miền
def asymptotes(expr: str):
    """(tiệm cận đứng [x0], tiệm cận ngang/xiên [(a, b)] với y = a x + b)."""
    f = make_func(expr)
    vert = _poles(f)
    slant = []
    for sgn in (1, -1):
        X1, X2 = sgn * 1e6, sgn * 2e6
        y1, y2 = f(X1), f(X2)
        if math.isnan(y1) or math.isnan(y2):
            continue
        a = (y2 - y1) / (X2 - X1)
        b = y2 - a * X2
        if abs(f(sgn * 4e6) - (a * sgn * 4e6 + b)) > 1e-3 or abs(a) > 1e3:
            continue                                     # không có tiệm cận (vd đa thức bậc ≥ 2)
        a, b = _snap(round(a, 6)) + 0.0, _snap(round(b, 4)) + 0.0
        if not any(abs(a - p) < 1e-4 and abs(b - q) < 1e-4 for p, q in slant):
            slant.append((a, b))
    return vert, slant


def graph_plus_tikz(expr: str, xmin=-4, xmax=4, ymin=-4, ymax=4, *, grid=True, label="", points=(),
                    show_asymptotes=True, shade=None, expr2: str = "", scale=0.8) -> str:
    """Đồ thị + tiệm cận (nét đứt) + tô miền tích phân trên [a; b] (giữa đồ thị và Ox, hoặc giữa 2 đồ thị)."""
    code = graph_tikz(expr, xmin, xmax, ymin, ymax, grid, label, points, scale)
    extra = []
    f = make_func(expr)
    if shade:
        a, b = shade
        g = make_func(expr2) if expr2.strip() else (lambda x: 0.0)
        n = 120
        top = [(a + (b - a) * i / n, f(a + (b - a) * i / n)) for i in range(n + 1)]
        bot = [(a + (b - a) * i / n, g(a + (b - a) * i / n)) for i in range(n, -1, -1)]
        if any(math.isnan(y) for _, y in top + bot):
            raise FuncError("Hàm không xác định trên đoạn cần tô")
        pts = "--".join(f"({x:.3f},{y:.3f})" for x, y in top + bot)
        extra.append(f"\t\\fill[blue!20] {pts}--cycle;")
        extra.append(f"\t\\draw[dashed] ({a},{f(a):.3f})--({a},{g(a):.3f}) ({b},{f(b):.3f})--({b},{g(b):.3f});")
    if expr2.strip():
        from .drawgen import sample
        for seg in sample(make_func(expr2), xmin, xmax, 400, ymin - 0.5, ymax + 0.5):
            extra.append("\t\\draw[thick,red,smooth] plot coordinates {" +
                         " ".join(f"({x:.3f},{y:.3f})" for x, y in seg) + "};")
    if show_asymptotes:
        vert, slant = asymptotes(expr)
        for x0 in vert:
            if xmin <= x0 <= xmax:
                extra.append(f"\t\\draw[dashed,red!70] ({f2(x0)},{ymin - 0.3})--({f2(x0)},{ymax + 0.4})"
                             f" node[below right,font=\\scriptsize]{{$x={nice(x0)}$}};")
        for a, b in slant:
            x1, x2 = xmin - 0.3, xmax + 0.4
            lab = f"y={nice(b)}" if abs(a) < 1e-9 else \
                f"y={'' if abs(a - 1) < 1e-9 else '-' if abs(a + 1) < 1e-9 else nice(a)}x" + \
                (f"{'+' if b > 0 else '-'}{nice(abs(b))}" if abs(b) > 1e-9 else "")
            extra.append(f"\t\\draw[dashed,red!70] ({f2(x1)},{f2(a * x1 + b)})--({f2(x2)},{f2(a * x2 + b)})"
                         f" node[pos=0.95,above,sloped,font=\\scriptsize]{{${lab}$}};")
    head, sep, tail = code.partition("\t\\clip")
    clip_line, nl, rest = tail.partition("\n")
    return head + sep + clip_line + nl + "\n".join(extra) + ("\n" if extra else "") + rest


# ================================================================ hình khối
K, ANG = 0.5, math.radians(40)


def _proj(p):
    x, y, z = p
    return x + K * y * math.cos(ANG), z + K * y * math.sin(ANG)


SOLIDS = {
    "chop_tu_giac_deu": "Hình chóp tứ giác đều S.ABCD",
    "chop_sa_vuong_vuong": "Hình chóp S.ABCD, đáy hình vuông, SA ⊥ (ABCD)",
    "chop_tam_giac_sa": "Hình chóp S.ABC, SA ⊥ (ABC)",
    "chop_tam_giac_deu": "Hình chóp tam giác đều S.ABC",
    "tu_dien": "Tứ diện ABCD",
    "lang_tru_tam_giac": "Lăng trụ tam giác ABC.A'B'C'",
    "hinh_hop": "Hình hộp chữ nhật ABCD.A'B'C'D'",
    "lap_phuong": "Hình lập phương ABCD.A'B'C'D'",
    "hinh_non": "Hình nón",
    "hinh_tru": "Hình trụ",
    "hinh_cau": "Mặt cầu",
}


def _poly_tikz(P: dict, edges_vis, edges_hid, label_pos: dict, extra=()):
    lines = ["\\begin{tikzpicture}[scale=1,line join=round]"]
    for n, p in P.items():
        x, y = _proj(p)
        lines.append(f"\t\\coordinate ({n.replace(chr(39), 'p')}) at ({f2(x)},{f2(y)});")
    nm = (lambda s: s.replace("'", "p"))
    for a, b in edges_hid:
        lines.append(f"\t\\draw[dashed] ({nm(a)})--({nm(b)});")
    for a, b in edges_vis:
        lines.append(f"\t\\draw ({nm(a)})--({nm(b)});")
    lines += list(extra)
    for n in P:
        lines.append(f"\t\\fill ({nm(n)}) circle (1pt) node[{label_pos.get(n, 'below')}]{{${n}$}};")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)


def solid_tikz(kind: str, a: float = 3.0, h: float = 3.5) -> str:
    """a: cạnh đáy (hoặc bán kính), h: chiều cao."""
    if kind not in SOLIDS:
        raise FuncError(f"Không có hình «{kind}»")
    if kind in ("chop_tu_giac_deu", "chop_sa_vuong_vuong"):
        P = {"A": (0, 0, 0), "B": (a, 0, 0), "C": (a, a, 0), "D": (0, a, 0)}
        P["S"] = (a / 2, a / 2, h) if kind == "chop_tu_giac_deu" else (0, 0, h)
        vis = [("A", "B"), ("B", "C"), ("S", "A"), ("S", "B"), ("S", "C")]
        hid = [("A", "D"), ("D", "C"), ("S", "D")]
        extra = []
        if kind == "chop_tu_giac_deu":
            P["O"] = (a / 2, a / 2, 0)
            hid += [("A", "C"), ("B", "D"), ("S", "O")]
        lp = {"S": "above", "A": "left", "B": "below right", "C": "right", "D": "above left", "O": "below"}
        return _poly_tikz(P, vis, hid, lp, extra)
    if kind in ("chop_tam_giac_sa", "chop_tam_giac_deu", "tu_dien"):
        P = {"A": (0, 0, 0), "B": (a * 0.45, -0.6 * a, 0), "C": (a, 0.5 * a, 0)}
        if kind == "chop_tam_giac_sa":
            P["S"] = (0, 0, h)
        else:
            G = tuple(sum(P[k][i] for k in "ABC") / 3 for i in range(3))
            P["S" if kind != "tu_dien" else "D"] = (G[0], G[1], h)
        top = "S" if kind != "tu_dien" else "D"
        vis = [("A", "B"), ("B", "C"), (top, "A"), (top, "B"), (top, "C")]
        hid = [("A", "C")]
        lp = {top: "above", "A": "left", "B": "below", "C": "right"}
        return _poly_tikz(P, vis, hid, lp)
    if kind == "lang_tru_tam_giac":
        base = {"A": (0, 0, 0), "B": (a * 0.45, -0.6 * a, 0), "C": (a, 0.5 * a, 0)}
        P = dict(base)
        for k, (x, y, z) in base.items():
            P[k + "'"] = (x, y, h)
        vis = [("A", "B"), ("B", "C"), ("A'", "B'"), ("B'", "C'"), ("C'", "A'"), ("A", "A'"), ("B", "B'"),
               ("C", "C'")]
        hid = [("A", "C")]
        lp = {"A": "left", "B": "below", "C": "right", "A'": "left", "B'": "below left", "C'": "right"}
        return _poly_tikz(P, vis, hid, lp)
    if kind in ("hinh_hop", "lap_phuong"):
        b, c = (a, a) if kind == "lap_phuong" else (a * 1.4, a * 0.9)
        hh = a if kind == "lap_phuong" else h
        base = {"A": (0, 0, 0), "B": (b, 0, 0), "C": (b, c, 0), "D": (0, c, 0)}
        P = dict(base)
        for k, (x, y, z) in base.items():
            P[k + "'"] = (x, y, hh)
        vis = [("A", "B"), ("B", "C"), ("A'", "B'"), ("B'", "C'"), ("C'", "D'"), ("D'", "A'"), ("A", "A'"),
               ("B", "B'"), ("C", "C'")]
        hid = [("A", "D"), ("D", "C"), ("D", "D'")]
        lp = {"A": "below left", "B": "below right", "C": "right", "D": "above left", "A'": "left",
              "B'": "right", "C'": "above right", "D'": "above left"}
        return _poly_tikz(P, vis, hid, lp)
    r = a / 2
    ry = r * K * math.sin(ANG) * 1.2                       # bán trục elip của đáy
    if kind == "hinh_cau":
        return "\n".join([
            "\\begin{tikzpicture}",
            f"\t\\draw (0,0) circle ({f2(r)});",
            f"\t\\draw (-{f2(r)},0) arc (180:360:{f2(r)} and {f2(ry)});",
            f"\t\\draw[dashed] ({f2(r)},0) arc (0:180:{f2(r)} and {f2(ry)});",
            "\t\\fill (0,0) circle (1pt) node[above]{$I$};",
            f"\t\\draw[dashed] (0,0)--({f2(r)},0) node[midway,above]{{$R$}};",
            "\\end{tikzpicture}"])
    if kind == "hinh_non":
        return "\n".join([
            "\\begin{tikzpicture}",
            f"\t\\draw (-{f2(r)},0) arc (180:360:{f2(r)} and {f2(ry)});",
            f"\t\\draw[dashed] ({f2(r)},0) arc (0:180:{f2(r)} and {f2(ry)});",
            f"\t\\draw (-{f2(r)},0)--(0,{f2(h)})--({f2(r)},0);",
            f"\t\\draw[dashed] (0,{f2(h)})--(0,0)--({f2(r)},0);",
            "\t\\fill (0,0) circle (1pt) node[below]{$O$};",
            f"\t\\node[above] at (0,{f2(h)}){{$S$}};",
            f"\t\\node[right] at (0,{f2(h / 2)}){{$h$}};",
            f"\t\\node[above] at ({f2(r / 2)},0){{$r$}};",
            "\\end{tikzpicture}"])
    return "\n".join([                                      # hình trụ
        "\\begin{tikzpicture}",
        f"\t\\draw (0,{f2(h)}) ellipse ({f2(r)} and {f2(ry)});",
        f"\t\\draw (-{f2(r)},0) arc (180:360:{f2(r)} and {f2(ry)});",
        f"\t\\draw[dashed] ({f2(r)},0) arc (0:180:{f2(r)} and {f2(ry)});",
        f"\t\\draw (-{f2(r)},0)--(-{f2(r)},{f2(h)}) ({f2(r)},0)--({f2(r)},{f2(h)});",
        f"\t\\draw[dashed] (0,0)--(0,{f2(h)}) (0,0)--({f2(r)},0);",
        f"\t\\fill (0,0) circle (1pt) node[below]{{$O$}} (0,{f2(h)}) circle (1pt) node[above]{{$O'$}};",
        "\\end{tikzpicture}"])
