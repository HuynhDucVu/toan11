"""Sinh mã TikZ cho hình hay dùng trong đề Toán: bảng biến thiên (tkz-tab), đồ thị hàm số,
biểu đồ cột, biểu đồ quạt.

Hàm số nhập theo cú pháp Python/thông dụng: x^3 - 3*x + 1, (2*x+1)/(x-1), sqrt(x), sin(x), exp(x)…
(dấu ^ được hiểu là luỹ thừa; nhân ngầm như 3x được tự thêm dấu *).
"""
from __future__ import annotations

import math
import re
from fractions import Fraction

FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
         "ln": math.log, "log": math.log10, "abs": abs, "pi": math.pi, "e": math.e}


class FuncError(ValueError):
    pass


def to_python(expr: str) -> str:
    s = expr.strip().replace("^", "**").replace("−", "-").replace("·", "*").replace(",", ".")
    s = re.sub(r"(\d)\s*([a-zA-Z(])", r"\1*\2", s)            # 3x → 3*x, 2(x+1) → 2*(x+1)
    s = re.sub(r"\)\s*([a-zA-Z(\d])", r")*\1", s)              # (x+1)(x-1) → (x+1)*(x-1)
    s = re.sub(r"\bx\s*\(", "x*(", s)
    return s


def make_func(expr: str):
    code = to_python(expr)
    if "__" in code or "import" in code or "lambda" in code:
        raise FuncError("Biểu thức không hợp lệ")
    try:
        c = compile(code, "<hàm số>", "eval")
    except SyntaxError as e:
        raise FuncError(f"Biểu thức sai cú pháp: {expr}") from e
    names = set(c.co_names) - set(FUNCS) - {"x"}
    if names:
        raise FuncError(f"Không biết: {', '.join(sorted(names))}")

    def f(x):
        try:
            v = eval(c, {"__builtins__": {}}, {**FUNCS, "x": x})  # noqa: S307
            return float(v) if not isinstance(v, complex) else math.nan
        except (ZeroDivisionError, ValueError, OverflowError):
            return math.nan
    return f


def nice(v: float, max_den: int = 12) -> str:
    """Số đẹp cho LaTeX: số nguyên, phân số \\dfrac, hoặc thập phân dấu phẩy."""
    if math.isnan(v):
        return ""
    if abs(v) > 1e6:
        return "+\\infty" if v > 0 else "-\\infty"
    fr = Fraction(v).limit_denominator(max_den)
    if abs(float(fr) - v) < 1e-7:
        if fr.denominator == 1:
            return str(fr.numerator)
        sg = "-" if fr < 0 else ""
        return f"{sg}\\dfrac{{{abs(fr.numerator)}}}{{{fr.denominator}}}"
    r = math.sqrt(abs(v))                                     # ±a√b đơn giản
    for b in (2, 3, 5, 6, 7):
        a = v / math.sqrt(b)
        if abs(a - round(a)) < 1e-7 and round(a) != 0:
            a = int(round(a))
            return ("-" if a < 0 else "") + ("" if abs(a) == 1 else str(abs(a))) + f"\\sqrt{{{b}}}"
    del r
    return f"{v:.2f}".replace(".", "{,}")


# ---------------------------------------------------------------- bảng biến thiên
def _deriv(f, x, h=1e-6):
    return (f(x + h) - f(x - h)) / (2 * h)


def _roots(g, lo=-30.0, hi=30.0, n=6000):
    xs = [lo + (hi - lo) * i / n for i in range(n + 1)]
    out = []
    prev_x, prev = xs[0], g(xs[0])
    for x in xs[1:]:
        v = g(x)
        if math.isnan(v) or math.isnan(prev):
            prev_x, prev = x, v
            continue
        if v == 0 or prev * v < 0:
            a, b = prev_x, x
            for _ in range(80):
                m = (a + b) / 2
                if g(a) * g(m) <= 0:
                    b = m
                else:
                    a = m
            r = _snap((a + b) / 2)
            if not out or abs(out[-1] - r) > 1e-5:
                out.append(r)
        prev_x, prev = x, v
    return out


def _snap(r: float) -> float:
    fr = Fraction(r).limit_denominator(24)
    return float(fr) if abs(float(fr) - r) < 1e-5 else r


def _poles(f, lo=-30.0, hi=30.0, n=6000):
    """Điểm hàm không xác định mà hai bên tiến ra vô cực (tiệm cận đứng)."""
    out = []
    xs = [lo + (hi - lo) * i / n for i in range(n + 1)]
    vals = [f(x) for x in xs]
    for i in range(1, n):
        a, v, b = vals[i - 1], vals[i], vals[i + 1]
        cand = None
        if math.isnan(v) and not math.isnan(a) and not math.isnan(b) and max(abs(a), abs(b)) > 50:
            cand = xs[i]                                        # mẫu = 0 đúng tại mắt lưới
        elif not math.isnan(a) and not math.isnan(v) and a * v < 0 and max(abs(a), abs(v)) > 1e3:
            lo_, hi_ = xs[i - 1], xs[i]                         # đổi dấu kèm bùng nổ giữa 2 mắt lưới
            for _ in range(80):
                m = (lo_ + hi_) / 2
                fm = f(m)
                if math.isnan(fm) or a * fm < 0:
                    hi_ = m
                else:
                    lo_ = m
            cand = (lo_ + hi_) / 2
        if cand is not None:
            cand = _snap(cand)
            if abs(f(cand + 1e-6)) > 1e3 and (not out or abs(out[-1] - cand) > 1e-5):
                out.append(cand)
    return out


def variation_table(expr: str, name: str = "y"):
    """Tự lập bảng biến thiên cho hàm số trên ℝ (đa thức, phân thức đơn giản).

    Trả về dict: xs (nhãn LaTeX), sign (dòng dấu y'), var (dòng biến thiên kiểu tkz-tab).
    """
    f = make_func(expr)
    poles = _poles(f)
    crit = [r for r in _roots(lambda x: _deriv(f, x)) if all(abs(r - p) > 1e-3 for p in poles)]
    keys = sorted(set([*crit, *poles]))
    xs = ["-\\infty"] + [nice(k) for k in keys] + ["+\\infty"]
    big = 1e7
    pts = [-big] + keys + [big]
    sign, var = [""], []
    # giá trị/giới hạn ở từng mốc
    for i, p in enumerate(pts):
        is_pole = any(abs(p - q) < 1e-9 for q in poles)
        if i == 0 or i == len(pts) - 1:
            v = f(p)
            lab = "+\\infty" if v > 1e3 else "-\\infty" if v < -1e3 else nice(round(v, 4))
        elif is_pole:
            lab = None
        else:
            lab = nice(f(p))
        # chiều trên khoảng bên phải
        if i < len(pts) - 1:
            a, b = pts[i], pts[i + 1]
            m = (a + b) / 2 if abs(a) < big and abs(b) < big else (b - 1 if abs(a) >= big else a + 1)
            d = _deriv(f, m)
            sign.append("+" if d > 0 else "-")
        if i < len(pts) - 1:
            sign.append("d" if (i + 1 < len(pts) - 1 and any(abs(pts[i + 1] - q) < 1e-9 for q in poles))
                        else ("0" if i + 1 < len(pts) - 1 else ""))
        var.append((p, lab, is_pole))
    sign = sign[:2 * len(pts) - 1]
    # vị trí cao/thấp cho dòng biến thiên
    cells = []
    for i, (p, lab, is_pole) in enumerate(var):
        left = sign[2 * i - 1] if i > 0 else None
        right = sign[2 * i + 1] if 2 * i + 1 < len(sign) else None
        if is_pole:
            lim_l = f(p - 1e-7)
            lim_r = f(p + 1e-7)
            tl = "+\\infty" if lim_l > 0 else "-\\infty"
            tr = "+\\infty" if lim_r > 0 else "-\\infty"
            pl = "+" if lim_l > 0 else "-"
            pr = "+" if lim_r > 0 else "-"
            cells.append(f"{pl}D{pr}/${tl}$/${tr}$")
            continue
        if left is None:
            pos = "-" if right == "+" else "+"
        elif right is None:
            pos = "+" if left == "+" else "-"
        else:
            pos = "+" if left == "+" else "-"
        cells.append(f"{pos}/${lab}$")
    return {"xs": xs, "sign": sign, "var": cells, "name": name, "crit": crit, "poles": poles}


def variation_tikz(xs, sign, var, name="y", deriv_name=None, lgt=1.2, espcl=2.4) -> str:
    if not deriv_name:
        deriv_name = name[:-3] + "'(x)" if name.endswith("(x)") else f"{name}'"
    xs_s = ",".join(f"${x}$" for x in xs)
    line = ",".join(sign) + ("," if len(sign) == 2 * len(xs) - 2 else "")
    return ("\\begin{tikzpicture}\n"
            f"\t\\tkzTabInit[nocadre=false,lgt={lgt},espcl={espcl},deltacl=0.6]"
            f"{{$x$/0.7,${deriv_name}$/0.7,${name}$/2}}{{{xs_s}}}\n"
            f"\t\\tkzTabLine{{{line}}}\n"
            f"\t\\tkzTabVar{{{','.join(var)}}}\n"
            "\\end{tikzpicture}")


def variation_from_expr(expr: str, name: str = "y") -> str:
    t = variation_table(expr, name)
    return variation_tikz(t["xs"], t["sign"], t["var"], name)


# ---------------------------------------------------------------- đồ thị
def sample(f, a: float, b: float, n: int = 300, ymin=-1e9, ymax=1e9):
    """Các đoạn liên tục [(x, y), ...] – tách đoạn ở chỗ hàm không xác định hoặc vượt khung."""
    segs, cur = [], []
    for i in range(n + 1):
        x = a + (b - a) * i / n
        y = f(x)
        if math.isnan(y) or y < ymin or y > ymax:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
            continue
        if cur and abs(y - cur[-1][1]) > (ymax - ymin) * 0.8:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
        cur.append((x, y))
    if len(cur) > 1:
        segs.append(cur)
    return segs


def graph_tikz(expr: str, xmin=-4, xmax=4, ymin=-4, ymax=4, grid=True, label="", points=(), scale=0.8) -> str:
    f = make_func(expr)
    segs = sample(f, xmin, xmax, 400, ymin - 0.5, ymax + 0.5)
    lines = [f"\\begin{{tikzpicture}}[scale={scale},>=stealth]"]
    if grid:
        lines.append(f"\t\\draw[gray!30,very thin] ({xmin},{ymin}) grid ({xmax},{ymax});")
    lines.append(f"\t\\draw[->] ({xmin - 0.3},0)--({xmax + 0.4},0) node[below left]{{$x$}};")
    lines.append(f"\t\\draw[->] (0,{ymin - 0.3})--(0,{ymax + 0.4}) node[below left]{{$y$}};")
    lines.append("\t\\node[below left] at (0,0){$O$};")
    ticks_x = [i for i in range(math.ceil(xmin), math.floor(xmax) + 1) if i != 0]
    ticks_y = [i for i in range(math.ceil(ymin), math.floor(ymax) + 1) if i != 0]
    lines.append("\t\\foreach \\i in {" + ",".join(map(str, ticks_x)) +
                 "}{\\draw (\\i,0.06)--(\\i,-0.06) node[below,font=\\scriptsize]{$\\i$};}")
    lines.append("\t\\foreach \\i in {" + ",".join(map(str, ticks_y)) +
                 "}{\\draw (0.06,\\i)--(-0.06,\\i) node[left,font=\\scriptsize]{$\\i$};}")
    lines.append("\t\\clip (%s,%s) rectangle (%s,%s);" % (xmin - 0.3, ymin - 0.3, xmax + 0.4, ymax + 0.4))
    for seg in segs:
        pts = " ".join(f"({x:.3f},{y:.3f})" for x, y in seg)
        lines.append(f"\t\\draw[thick,blue,smooth] plot coordinates {{{pts}}};")
    for x0 in points:
        y0 = f(x0)
        if not math.isnan(y0):
            lines.append(f"\t\\draw[dashed] ({x0},0)--({x0},{y0:.3f})--(0,{y0:.3f});")
            lines.append(f"\t\\fill ({x0},{y0:.3f}) circle (1.5pt);")
    if label:
        lines.append(f"\t\\node[blue,above right] at ({xmax - 1.5},{ymax - 0.8}){{${label}$}};")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)


# ---------------------------------------------------------------- biểu đồ
def bar_tikz(labels, values, xlabel="", ylabel="", width=0.6, color="blue!50") -> str:
    vmax = max(values) if values else 1
    step = 10 ** math.floor(math.log10(vmax)) if vmax > 0 else 1
    top = math.ceil(vmax / step) * step
    h = 4.0 / top
    dx = max(1.0, 0.16 * max((len(str(lb)) for lb in labels), default=1))   # nhãn dài ⇒ cột thưa hơn
    xend = len(values) * dx + 0.6 * dx
    out = ["\\begin{tikzpicture}[>=stealth]",
           f"\t\\draw[->] (0,0)--({xend:.2f},0) node[below right]{{{xlabel}}};",
           f"\t\\draw[->] (0,0)--(0,{top * h + 0.6}) node[above]{{{ylabel}}};"]
    k = 0
    while k <= top + 1e-9:
        out.append(f"\t\\draw[gray!30] (0,{k * h:.3f})--({xend - 0.3:.2f},{k * h:.3f}); "
                   f"\\node[left,font=\\scriptsize] at (0,{k * h:.3f}){{{nice(k)}}};")
        k += step
    for i, (lb, v) in enumerate(zip(labels, values), 1):
        x = i * dx
        out.append(f"\t\\fill[{color},draw=black] ({x - width / 2:.2f},0) rectangle ({x + width / 2:.2f},{v * h:.3f});")
        out.append(f"\t\\node[above,font=\\scriptsize] at ({x:.2f},{v * h:.3f}){{{nice(v)}}};")
        out.append(f"\t\\node[below,font=\\scriptsize] at ({x:.2f},0){{{lb}}};")
    out.append("\\end{tikzpicture}")
    return "\n".join(out)


PIE_COLORS = ["red!40", "blue!40", "green!40", "orange!50", "violet!40", "cyan!40", "yellow!60", "gray!40"]


def pie_tikz(labels, values, radius=2.0, percent=True) -> str:
    total = sum(values) or 1
    out = ["\\begin{tikzpicture}"]
    a = 90.0
    for i, (lb, v) in enumerate(zip(labels, values)):
        b = a - 360.0 * v / total
        mid = math.radians((a + b) / 2)
        col = PIE_COLORS[i % len(PIE_COLORS)]
        out.append(f"\t\\fill[{col},draw=black] (0,0) -- ({a:.2f}:{radius}) arc ({a:.2f}:{b:.2f}:{radius}) -- cycle;")
        txt = f"{nice(round(100 * v / total, 1))}\\%" if percent else nice(v)
        out.append(f"\t\\node[font=\\scriptsize,align=center] at ({0.62 * radius * math.cos(mid):.3f},"
                   f"{0.62 * radius * math.sin(mid):.3f}){{{lb}\\\\{txt}}};")
        a = b
    out.append("\\end{tikzpicture}")
    return "\n".join(out)


def parse_data(text: str):
    """Đọc bảng số liệu: mỗi dòng «nhãn: giá trị» hoặc «nhãn, giá trị» hoặc «nhãn<tab>giá trị»."""
    labels, values = [], []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^\s*(.+?)\s*[:;\t,]\s*(-?[\d.,]+)\s*$", line)
        if not m:
            raise FuncError(f"Không đọc được dòng: «{line}» (cần «nhãn: số»)")
        labels.append(m.group(1))
        values.append(float(m.group(2).replace(",", ".")))
    return labels, values
