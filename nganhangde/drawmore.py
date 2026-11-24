"""Bổ sung vẽ hình: bảng xét dấu, đường tròn lượng giác (biểu diễn nghiệm), đồ thị theo cực trị,
mẫu hàm số thường gặp, đồ thị có vạch chia tuỳ chọn và điểm gióng."""
from __future__ import annotations

import math
import re
from fractions import Fraction

from .drawgen import FuncError, _poles, _roots, make_func, nice

# ---------------------------------------------------------------- bảng xét dấu
def sign_table(expr: str, name: str = "f(x)"):
    """(nhãn x, dòng dấu tkz-tab) của biểu thức trên ℝ: 0 tại nghiệm, d (gạch kép) tại điểm không xác định."""
    f = make_func(expr)
    poles = _poles(f)
    zeros = [r for r in _roots(f) if all(abs(r - p) > 1e-6 for p in poles)]
    keys = sorted(set(round(k, 9) for k in zeros + poles))
    if len(keys) > 12:
        raise FuncError("Quá nhiều nghiệm – hàm có thể tuần hoàn, hãy nhập biểu thức khác")
    xs = ["-\\infty"] + [nice(k) for k in keys] + ["+\\infty"]
    pts = [-1e6] + keys + [1e6]
    line = [""]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        m = (a + b) / 2 if i not in (0, len(pts) - 2) else (b - 1 if i == 0 else a + 1)
        if len(pts) == 2:
            m = 0.123
        v = f(m)
        if math.isnan(v):
            raise FuncError(f"Hàm không xác định trên khoảng ({nice(a)}; {nice(b)}) – bảng xét dấu chỉ cho hàm xác "
                            "định trên ℝ trừ hữu hạn điểm")
        line.append("+" if v > 0 else "-")
        if i < len(pts) - 2:
            k = pts[i + 1]
            line.append("d" if any(abs(k - p) < 1e-6 for p in poles) else "0")
    line.append("")
    return xs, line


def sign_table_tikz(expr: str, name: str = "f(x)", lgt: float = 1.6, espcl: float = 2.0) -> str:
    xs, line = sign_table(expr, name)
    return ("\\begin{tikzpicture}\n"
            f"\t\\tkzTabInit[nocadre=false,lgt={lgt},espcl={espcl}]{{$x$/0.8,${name}$/0.8}}"
            f"{{{','.join(f'${x}$' for x in xs)}}}\n"
            f"\t\\tkzTabLine{{{','.join(line)}}}\n\\end{{tikzpicture}}")


def sign_table_manual(xs: list[str], signs: list[str], name: str = "f(x)") -> str:
    """Bảng xét dấu nhập tay: xs = mốc (LaTeX), signs = dòng tkz-tab, vd [',', '+', '0', '-', ...]."""
    return ("\\begin{tikzpicture}\n"
            f"\t\\tkzTabInit[nocadre=false,lgt=1.6,espcl=2]{{$x$/0.8,${name}$/0.8}}"
            f"{{{','.join(f'${x}$' for x in xs)}}}\n\t\\tkzTabLine{{{','.join(signs)}}}\n\\end{{tikzpicture}}")


# ---------------------------------------------------------------- đường tròn lượng giác
def _eval_k(expr: str, k: int) -> float:
    s = expr.replace("π", "pi").replace("\\pi", "pi").replace(" ", "")
    s = re.sub(r"(\d)\s*(pi|k|\()", r"\1*\2", s)
    s = re.sub(r"(pi|k)\s*(pi|k|\d|\()", r"\1*\2", s)
    s = re.sub(r"\)\s*(\(|\w)", r")*\1", s)
    if re.search(r"[^0-9pik+\-*/().]", s.replace("pi", "")):
        raise FuncError(f"Không hiểu họ nghiệm «{expr}» – ví dụ: pi/6 + k2pi, -pi/3 + kpi/2")
    try:
        return float(eval(s, {"__builtins__": {}}, {"pi": math.pi, "k": k}))  # noqa: S307
    except (SyntaxError, ZeroDivisionError, NameError) as e:
        raise FuncError(f"Không hiểu họ nghiệm «{expr}»") from e


def angle_latex(t: float) -> str:
    """Góc (rad) → LaTeX theo π: 0, \\dfrac{\\pi}{6}, -\\dfrac{2\\pi}{3}, \\pi…"""
    fr = Fraction(t / math.pi).limit_denominator(48)
    if abs(float(fr) * math.pi - t) > 1e-6:
        return nice(t)
    if fr == 0:
        return "0"
    sgn = "-" if fr < 0 else ""
    p, q = abs(fr.numerator), fr.denominator
    num = "\\pi" if p == 1 else f"{p}\\pi"
    return f"{sgn}{num}" if q == 1 else f"{sgn}\\dfrac{{{num}}}{{{q}}}"


def trig_points(families: list[str]) -> list[float]:
    """Các điểm (góc trong [0; 2π)) biểu diễn hợp các họ nghiệm a + k·b."""
    pts: list[float] = []
    for fam in families:
        if not fam.strip():
            continue
        a, b = _eval_k(fam, 0), _eval_k(fam, 1) - _eval_k(fam, 0)
        if abs(b) < 1e-12:
            raise FuncError(f"«{fam}» thiếu chu kì k")
        n = 2 * math.pi / abs(b)
        if abs(n - round(n)) > 1e-6 or round(n) > 48:
            raise FuncError(f"Chu kì của «{fam}» không chia hết 2π – không biểu diễn hữu hạn điểm được")
        for j in range(int(round(n))):
            t = (a + j * b) % (2 * math.pi)
            if not any(abs(t - p) < 1e-7 or abs(abs(t - p) - 2 * math.pi) < 1e-7 for p in pts):
                pts.append(t)
    return sorted(pts)


def trig_circle_tikz(families: list[str], polygon: bool = True, labels: bool = True, r: float = 2.2) -> str:
    pts = trig_points(families)
    L = ["\\begin{tikzpicture}[>=stealth]",
         f"\t\\draw[->] ({-r - 0.5},0)--({r + 0.6},0) node[below]{{$\\cos$}};",
         f"\t\\draw[->] (0,{-r - 0.5})--(0,{r + 0.6}) node[left]{{$\\sin$}};",
         f"\t\\draw (0,0) circle ({r});",
         "\t\\node[below left] at (0,0){$O$};",
         f"\t\\node[below right] at ({r},0){{$A$}};"]
    if polygon and len(pts) >= 3:
        L.append("\t\\draw[blue] " + "--".join(f"({math.degrees(t):.4g}:{r})" for t in pts) + "--cycle;")
    elif polygon and len(pts) == 2:
        L.append(f"\t\\draw[blue] ({math.degrees(pts[0]):.4g}:{r})--({math.degrees(pts[1]):.4g}:{r});")
    for t in pts:
        d = math.degrees(t)
        L.append(f"\t\\fill[red] ({d:.4g}:{r}) circle (2pt);")
        if labels:
            L.append(f"\t\\node[font=\\scriptsize] at ({d:.4g}:{r + 0.5}){{${angle_latex(t if t <= math.pi + 1e-9 else t - 2 * math.pi)}$}};")
    L.append("\\end{tikzpicture}")
    return "\n".join(L)


# ---------------------------------------------------------------- đồ thị theo cực trị / mẫu hàm số
def _num(v: float) -> str:
    fr = Fraction(v).limit_denominator(1000)
    return str(fr) if abs(float(fr) - v) < 1e-9 else f"{v:.6g}"


def poly_text(coefs: list[float]) -> str:
    """[a_n, …, a_0] → 'x^3 - 3x + 1' (bỏ hệ số 0, gọn hệ số 1)."""
    n = len(coefs) - 1
    out = ""
    for i, c in enumerate(coefs):
        if abs(c) < 1e-12:
            continue
        p = n - i
        mag = _num(abs(c))
        if "/" in mag:
            mag = f"({mag})"
        body = ("" if mag == "1" and p > 0 else mag + ("*" if p > 0 and "(" in mag else "")) + \
               ("x" if p == 1 else f"x^{p}" if p > 1 else "")
        out += (" - " if c < 0 else " + " if out else "") + body if out or c >= 0 else "-" + body
    return out or "0"


def cubic_from_extrema(x1: float, y1: float, x2: float, y2: float) -> str:
    """Hàm bậc ba có cực trị tại (x1; y1) và (x2; y2)."""
    if abs(x1 - x2) < 1e-12:
        raise FuncError("Hai điểm cực trị phải có hoành độ khác nhau")
    g = (lambda x: x ** 3 / 3 - (x1 + x2) * x ** 2 / 2 + x1 * x2 * x)
    if abs(g(x1) - g(x2)) < 1e-12:
        raise FuncError("Không có hàm bậc ba thoả mãn")
    a = (y1 - y2) / (g(x1) - g(x2))
    d = y1 - a * g(x1)
    A, B, C = a / 3, -a * (x1 + x2) / 2, a * x1 * x2
    return poly_text([A, B, C, d])


def quartic_from_extrema(y0: float, x1: float, y1: float) -> str:
    """Hàm trùng phương y = ax⁴ + bx² + c, cực trị tại (0; y0) và (±x1; y1)."""
    if abs(x1) < 1e-12 or abs(y0 - y1) < 1e-12:
        raise FuncError("Cần x1 ≠ 0 và y1 ≠ y0")
    a = (y0 - y1) / x1 ** 4
    b = -2 * a * x1 ** 2
    return poly_text([a, 0, b, 0, y0])


TEMPLATES = [
    ("Bậc ba: y = x³ − 3x + 1", "x^3 - 3x + 1"),
    ("Bậc ba nghịch biến: y = −x³ + 3x² − 2", "-x^3 + 3x^2 - 2"),
    ("Trùng phương: y = x⁴ − 2x² − 1", "x^4 - 2x^2 - 1"),
    ("Trùng phương: y = −x⁴ + 2x² + 1", "-x^4 + 2x^2 + 1"),
    ("Bậc nhất/bậc nhất: y = (2x + 1)/(x − 1)", "(2x+1)/(x-1)"),
    ("Bậc hai/bậc nhất: y = (x² + x + 1)/(x + 1)", "(x^2+x+1)/(x+1)"),
    ("Parabol: y = x² − 2x − 3", "x^2 - 2x - 3"),
    ("Mũ: y = 2^x", "2^x"),
    ("Mũ: y = (1/2)^x", "(1/2)^x"),
    ("Lôgarit: y = log₂ x", "ln(x)/ln(2)"),
    ("Lôgarit: y = ln x", "ln(x)"),
    ("Lượng giác: y = sin x", "sin(x)"),
    ("Lượng giác: y = cos x", "cos(x)"),
    ("Căn: y = √x", "sqrt(x)"),
    ("Trị tuyệt đối: y = |x² − 4|", "abs(x^2 - 4)"),
]


def parse_ticks(text: str) -> list[tuple[float, str]]:
    """'-1, 1, 2' hoặc '3.1416:\\pi, 1.5708:\\dfrac{\\pi}{2}' → [(giá trị, nhãn LaTeX)]."""
    out = []
    for part in re.split(r"[;,]\s*(?![^{]*\})", text):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            v, lab = part.split(":", 1)
            out.append((make_func(v)(0), lab.strip()))
        else:
            v = make_func(part.replace("π", "pi"))(0)
            out.append((v, angle_latex(v) if "pi" in part or "π" in part else nice(v)))
    return out


def customize_graph(code: str, xticks=None, yticks=None, guides=()) -> str:
    """Thay vạch chia mặc định bằng vạch tuỳ chọn; thêm điểm gióng (đường đứt nét chiếu xuống hai trục)."""
    lines = code.split("\n")
    out = []
    for ln in lines:
        if xticks is not None and "\\foreach" in ln and "node[below" in ln:
            continue
        if yticks is not None and "\\foreach" in ln and "node[left" in ln:
            continue
        out.append(ln)
    extra = []
    for v, lab in xticks or []:
        extra.append(f"\t\\draw ({v:.4g},0.06)--({v:.4g},-0.06) node[below,font=\\scriptsize]{{${lab}$}};")
    for v, lab in yticks or []:
        extra.append(f"\t\\draw (0.06,{v:.4g})--(-0.06,{v:.4g}) node[left,font=\\scriptsize]{{${lab}$}};")
    for x, y in guides:
        extra.append(f"\t\\draw[dashed] ({x:.4g},0)--({x:.4g},{y:.4g})--(0,{y:.4g});")
        extra.append(f"\t\\fill ({x:.4g},{y:.4g}) circle (1.5pt);")
    i = next((k for k, ln in enumerate(out) if ln.lstrip().startswith("\\clip")), len(out) - 1)
    return "\n".join(out[:i] + extra + out[i:])
