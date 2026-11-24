"""Câu đổi số tự động (không cần AI) – mỗi lần gọi sinh một câu trắc nghiệm mới với số liệu ngẫu nhiên, có đủ
ID (theo Map ID Toán 12: 2D1…), 4 phương án, hình (bảng biến thiên tkz-tab / đồ thị TikZ) và lời giải.

Hàm bậc ba được dựng từ hai điểm tới hạn nguyên x1 < x2 (cùng tính chẵn lẻ để hệ số nguyên):
    f'(x) = 3a(x − x1)(x − x2)  ⇒  f(x) = a·x³ − (3a(x1+x2)/2)·x² + 3a·x1·x2·x + d.
"""
from __future__ import annotations

import random
from fractions import Fraction

from .drawgen import graph_tikz, variation_from_expr


# ---------------------------------------------------------------- tiện ích
def frac(v) -> str:
    """Số → LaTeX: 3, -2, \\dfrac{1}{3}, -\\dfrac{5}{2}."""
    f = Fraction(v).limit_denominator(1000)
    if f.denominator == 1:
        return str(f.numerator)
    return ("-" if f < 0 else "") + f"\\dfrac{{{abs(f.numerator)}}}{{{f.denominator}}}"


def tex_poly(coefs, var="x") -> str:
    """[a_n, …, a_0] → 'x^3-3x^2+2' (LaTeX)."""
    n, out = len(coefs) - 1, ""
    for i, c in enumerate(coefs):
        c = Fraction(c).limit_denominator(1000)
        if c == 0:
            continue
        p = n - i
        mag = abs(c)
        m = "" if (mag == 1 and p > 0) else frac(mag)
        term = m + (var if p == 1 else f"{var}^{{{p}}}" if p > 1 else "")
        out += ("-" if c < 0 else ("+" if out else "")) + term
    return out or "0"


def py_poly(coefs) -> str:
    n = len(coefs) - 1
    return "+".join(f"({Fraction(c).limit_denominator(1000)})*x**{n - i}" for i, c in enumerate(coefs)).replace("**", "^")


def interval(a, b) -> str:
    A = "-\\infty" if a is None else frac(a)
    B = "+\\infty" if b is None else frac(b)
    return f"$\\left({A};{B}\\right)$"


def _block(id_code: str, stem: str, options: list[str], correct: int, solution: str, rng: random.Random) -> str:
    """Khối ex_test; xáo vị trí đáp án đúng."""
    order = list(range(4))
    rng.shuffle(order)
    opts = [options[i] for i in order]
    pos = order.index(correct)
    lines = [f"\\begin{{ex}}%[{id_code}]%[Câu đổi số]", stem, "\\choice"]
    lines += [("{\\True " if k == pos else "{") + o + "}" for k, o in enumerate(opts)]
    lines.append("\\loigiai{" + solution + f"\\\\ Chọn đáp án {'ABCD'[pos]}.}}")
    lines.append("\\end{ex}")
    return "\n".join(lines)


def _distinct(correct: str, cands: list[str]) -> list[str] | None:
    out = [correct]
    for c in cands:
        if c not in out:
            out.append(c)
        if len(out) == 4:
            return out
    return None


def _cubic(rng):
    while True:
        x1 = rng.randint(-3, 2)
        x2 = x1 + rng.choice([2, 4])
        a = rng.choice([1, -1])
        d = rng.randint(-3, 3)
        co = [a, Fraction(-3 * a * (x1 + x2), 2), 3 * a * x1 * x2, d]
        f = (lambda x, co=co: sum(float(c) * x ** (3 - i) for i, c in enumerate(co)))
        if all(Fraction(c).denominator == 1 for c in co) and max(abs(f(x1)), abs(f(x2))) <= 12:
            return a, x1, x2, co, f


def _cd_ct(a, x1, x2, f):
    """(x_CĐ, y_CĐ, x_CT, y_CT)."""
    return (x1, f(x1), x2, f(x2)) if a > 0 else (x2, f(x2), x1, f(x1))


def _graph(co, x1, x2, f, extra_x=()):
    ys = [f(x1), f(x2)]
    ymin, ymax = int(min(ys) - 2), int(max(ys) + 2)
    return graph_tikz(py_poly(co), min(x1, x2) - 2, max(x1, x2) + 2, ymin, ymax, grid=False,
                      points=(x1, x2, *extra_x), scale=0.6)


# ---------------------------------------------------------------- các bài toán
def dondieu_congthuc(rng):
    a, x1, x2, co, f = _cubic(rng)
    want = rng.choice(["đồng biến", "nghịch biến"])
    inc = [interval(None, x1), interval(x2, None)] if a > 0 else [interval(x1, x2)]
    dec = [interval(x1, x2)] if a > 0 else [interval(None, x1), interval(x2, None)]
    good = rng.choice(inc if want == "đồng biến" else dec)
    bad = (dec if want == "đồng biến" else inc) + [interval(x1 - 1, x2 + 1), interval(None, None),
                                                    interval(x1, None), interval(None, x2)]
    opts = _distinct(good, bad)
    stem = f"Hàm số $y={tex_poly(co)}$ {want} trên khoảng nào dưới đây?"
    sol = (f"Ta có $y'={tex_poly([3 * a, 2 * co[1], co[2]])}$; $y'=0\\Leftrightarrow x={x1}$ hoặc $x={x2}$. "
           f"Vì hệ số của $x^3$ {'dương' if a > 0 else 'âm'} nên hàm số đồng biến trên "
           + " và ".join(inc).replace("$$", "$ và $") + ", nghịch biến trên " + " và ".join(dec) + ".")
    return _block("2D1N1-1", stem, opts, 0, sol, rng)


def dondieu_bbt(rng):
    a, x1, x2, co, f = _cubic(rng)
    want = rng.choice(["đồng biến", "nghịch biến"])
    inc = [interval(None, x1), interval(x2, None)] if a > 0 else [interval(x1, x2)]
    dec = [interval(x1, x2)] if a > 0 else [interval(None, x1), interval(x2, None)]
    good = rng.choice(inc if want == "đồng biến" else dec)
    ycd, yct = sorted([f(x1), f(x2)], reverse=True)
    bad = (dec if want == "đồng biến" else inc) + [interval(yct, ycd), interval(x1 - 1, x2 + 1), interval(None, None)]
    opts = _distinct(good, bad)
    stem = ("Cho hàm số $y=f(x)$ có bảng biến thiên như sau\n\\begin{center}\n" + variation_from_expr(py_poly(co), "f(x)")
            + "\n\\end{center}\nHàm số đã cho " + want + " trên khoảng nào dưới đây?")
    sol = ("Dựa vào bảng biến thiên, $f'(x)>0$ trên " + " và ".join(inc) + ", $f'(x)<0$ trên " + " và ".join(dec)
           + f". Vậy hàm số {want} trên {good}.")
    return _block("2D1H1-2", stem, opts, 0, sol, rng)


def dondieu_dothi(rng):
    a, x1, x2, co, f = _cubic(rng)
    want = rng.choice(["đồng biến", "nghịch biến"])
    inc = [interval(None, x1), interval(x2, None)] if a > 0 else [interval(x1, x2)]
    dec = [interval(x1, x2)] if a > 0 else [interval(None, x1), interval(x2, None)]
    good = rng.choice(inc if want == "đồng biến" else dec)
    ys = sorted([f(x1), f(x2)])
    bad = (dec if want == "đồng biến" else inc) + [interval(ys[0], ys[1]), interval(x1 - 1, x2 + 1), interval(None, None)]
    opts = _distinct(good, bad)
    stem = ("Cho hàm số $y=f(x)$ có đồ thị như hình vẽ.\n\\begin{center}\n" + _graph(co, x1, x2, f)
            + "\n\\end{center}\nHàm số đã cho " + want + " trên khoảng nào dưới đây?")
    sol = (f"Dựa vào đồ thị, trên {good} đồ thị đi {'lên' if want == 'đồng biến' else 'xuống'} "
           f"(từ trái sang phải) nên hàm số {want} trên khoảng đó.")
    return _block("2D1H1-2", stem, opts, 0, sol, rng)


def cuctri_congthuc(rng):
    a, x1, x2, co, f = _cubic(rng)
    xcd, ycd, xct, yct = _cd_ct(a, x1, x2, f)
    want = rng.choice(["cực đại", "cực tiểu"])
    good = f"$x={xcd if want == 'cực đại' else xct}$"
    bad = [f"$x={xct if want == 'cực đại' else xcd}$", f"$x={-(xcd if want == 'cực đại' else xct)}$",
           f"$x={frac(ycd if want == 'cực đại' else yct)}$", f"$x={xcd + xct}$", f"$x={xcd - 1}$"]
    opts = _distinct(good, bad)
    stem = f"Điểm {want} của hàm số $y={tex_poly(co)}$ là"
    sol = (f"$y'={tex_poly([3 * a, 2 * co[1], co[2]])}=0\\Leftrightarrow x={x1}$ hoặc $x={x2}$. "
           f"Lập bảng xét dấu $y'$ ta được hàm số đạt cực đại tại $x={xcd}$, cực tiểu tại $x={xct}$.")
    return _block("2D1N2-1", stem, opts, 0, sol, rng)


def cuctri_bbt(rng):
    a, x1, x2, co, f = _cubic(rng)
    xcd, ycd, xct, yct = _cd_ct(a, x1, x2, f)
    want = rng.choice(["giá trị cực đại", "giá trị cực tiểu", "điểm cực đại", "điểm cực tiểu"])
    vals = {"giá trị cực đại": ycd, "giá trị cực tiểu": yct, "điểm cực đại": xcd, "điểm cực tiểu": xct}
    good = f"${frac(vals[want])}$"
    bad = [f"${frac(v)}$" for k, v in vals.items() if k != want] + [f"${frac(-vals[want])}$", f"${frac(vals[want] + 1)}$"]
    opts = _distinct(good, bad)
    stem = ("Cho hàm số $y=f(x)$ có bảng biến thiên như sau\n\\begin{center}\n" + variation_from_expr(py_poly(co), "f(x)")
            + f"\n\\end{{center}}\n{want[0].upper() + want[1:]} của hàm số đã cho bằng")
    sol = (f"Từ bảng biến thiên: hàm số đạt cực đại tại $x={xcd}$, giá trị cực đại $y_{{CĐ}}={frac(ycd)}$; "
           f"đạt cực tiểu tại $x={xct}$, giá trị cực tiểu $y_{{CT}}={frac(yct)}$.")
    return _block("2D1N2-2", stem, opts, 0, sol, rng)


def gtln_doan(rng):
    a, x1, x2, co, f = _cubic(rng)
    p, q = x1 - rng.choice([1, 2]), x2 + rng.choice([0, 1])
    pts = sorted({p, q, *[x for x in (x1, x2) if p <= x <= q]})
    vals = {x: f(x) for x in pts}
    want = rng.choice(["lớn nhất", "nhỏ nhất"])
    best = max(vals.values()) if want == "lớn nhất" else min(vals.values())
    good = f"${frac(best)}$"
    bad = [f"${frac(v)}$" for v in vals.values()] + [f"${frac(best + 2)}$", f"${frac(-best)}$", f"${frac(best - 3)}$"]
    opts = _distinct(good, bad)
    stem = f"Giá trị {want} của hàm số $f(x)={tex_poly(co)}$ trên đoạn $[{p};{q}]$ bằng"
    sol = (f"$f'(x)={tex_poly([3 * a, 2 * co[1], co[2]])}=0\\Leftrightarrow x={x1}$ hoặc $x={x2}$. Ta có "
           + ", ".join(f"$f({x})={frac(v)}$" for x, v in vals.items())
           + f". Vậy giá trị {want} bằng ${frac(best)}$.")
    return _block("2D1N3-1", stem, opts, 0, sol, rng)


def tiemcan_b1b1(rng):
    while True:
        a, b, d = rng.randint(-4, 4), rng.randint(-5, 5), rng.randint(-4, 4)
        if a != 0 and d != 0 and a * (-d) + b != 0 and a != -d and a != d:
            break
    want = rng.choice(["đứng", "ngang"])
    num = tex_poly([a, b])
    den = tex_poly([1, d])
    if want == "đứng":
        good, bad = f"$x={-d}$", [f"$x={d}$", f"$y={a}$", f"$x={a}$", f"$y={-d}$"]
    else:
        good, bad = f"$y={a}$", [f"$y={-a}$", f"$x={-d}$", f"$y={frac(Fraction(b, d))}$", f"$x={a}$"]
    opts = _distinct(good, bad)
    stem = f"Tiệm cận {want} của đồ thị hàm số $y=\\dfrac{{{num}}}{{{den}}}$ là đường thẳng"
    sol = (f"Ta có $\\lim\\limits_{{x\\to\\pm\\infty}}y={a}$ nên tiệm cận ngang là $y={a}$; "
           f"$\\lim\\limits_{{x\\to {-d}^{{+}}}}y=\\pm\\infty$ nên tiệm cận đứng là $x={-d}$.")
    return _block("2D1N4-1", stem, opts, 0, sol, rng)


def tim_m_cucdai(rng):
    x0 = rng.randint(-3, 3)
    m = x0 + 2
    stem = (f"Tìm giá trị thực của tham số $m$ để hàm số $y=\\dfrac{{1}}{{3}}x^3-mx^2+\\left(m^2-4\\right)x+3$ "
            f"đạt cực đại tại $x={x0}$.")
    good = f"$m={m}$"
    bad = [f"$m={x0 - 2}$", f"$m={x0}$", f"$m={-m}$", f"$m={m + 1}$"]
    opts = _distinct(good, bad)
    sol = (f"$y'=x^2-2mx+m^2-4=(x-m)^2-4$, $y'=0\\Leftrightarrow x=m-2$ hoặc $x=m+2$. Hệ số của $x^3$ dương nên hàm số "
           f"đạt cực đại tại $x=m-2$. Do đó $m-2={x0}\\Leftrightarrow m={m}$.")
    return _block("2D1H2-3", stem, opts, 0, sol, rng)


def nhandang_b3(rng):
    a, x1, x2, co, f = _cubic(rng)
    neg = [-c for c in co]
    other = None
    for k in range(10):
        a2, y1, y2, co2, _f2 = _cubic(rng)
        if co2 != co and co2 != neg and a2 == a:
            other = co2
            break
    quart = [a, 0, -2 * a, 0, co[3]]
    cands = [f"$y={tex_poly(co)}$", f"$y={tex_poly(neg)}$", f"$y={tex_poly(other or [a, 0, 3 * a, co[3]])}$",
             f"$y={tex_poly(quart)}$"]
    opts = _distinct(cands[0], cands[1:])
    stem = ("Đường cong trong hình vẽ dưới đây là đồ thị của hàm số nào?\n\\begin{center}\n" + _graph(co, x1, x2, f)
            + "\n\\end{center}")
    sol = (f"Đồ thị có dạng của hàm bậc ba với hệ số của $x^3$ {'dương' if a > 0 else 'âm'}, có hai điểm cực trị "
           f"$({x1};{frac(f(x1))})$ và $({x2};{frac(f(x2))})$. Kiểm tra chỉ có hàm số $y={tex_poly(co)}$ thoả mãn.")
    return _block("2D1H5-1", stem, opts, 0, sol, rng)


def sodiem_cuctri_tp(rng):
    a = rng.choice([1, -1, 2, -2])
    b = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4])
    c = rng.randint(-3, 3)
    n = 3 if a * b < 0 else 1
    stem = f"Số điểm cực trị của hàm số $y={tex_poly([a, 0, b, 0, c])}$ là"
    opts = ["$" + str(n) + "$"] + [f"${k}$" for k in (0, 1, 2, 3) if k != n][:3]
    sol = (f"$y'={tex_poly([4 * a, 0, 2 * b, 0])}=2x\\left({tex_poly([2 * a, 0, b])}\\right)$. "
           + ("Phương trình $y'=0$ có ba nghiệm phân biệt và $y'$ đổi dấu qua mỗi nghiệm nên hàm số có $3$ điểm cực trị."
              if n == 3 else "Phương trình $y'=0$ chỉ có nghiệm $x=0$ và $y'$ đổi dấu qua đó nên hàm số có $1$ điểm cực trị."))
    return _block("2D1N2-1", stem, opts, 0, sol, rng)


PROBLEMS = {
    "dondieu_congthuc": ("Đơn điệu hàm bậc ba – cho công thức", dondieu_congthuc),
    "dondieu_bbt": ("Đơn điệu – dựa vào bảng biến thiên", dondieu_bbt),
    "dondieu_dothi": ("Đơn điệu – dựa vào đồ thị", dondieu_dothi),
    "cuctri_congthuc": ("Điểm cực trị hàm bậc ba – cho công thức", cuctri_congthuc),
    "cuctri_bbt": ("Cực trị – dựa vào bảng biến thiên", cuctri_bbt),
    "sodiem_cuctri_tp": ("Số điểm cực trị hàm trùng phương", sodiem_cuctri_tp),
    "tim_m_cucdai": ("Tìm m để hàm bậc ba đạt cực đại tại x₀", tim_m_cucdai),
    "gtln_doan": ("GTLN, GTNN hàm bậc ba trên đoạn", gtln_doan),
    "tiemcan_b1b1": ("Tiệm cận của hàm bậc nhất / bậc nhất", tiemcan_b1b1),
    "nhandang_b3": ("Nhận dạng hàm bậc ba từ đồ thị", nhandang_b3),
}


def generate(kind: str, n: int, seed=None, max_tries: int = 50) -> list[str]:
    """n câu khác nhau của một dạng."""
    rng = random.Random(seed)
    fn = PROBLEMS[kind][1]
    out, seen = [], set()
    tries = 0
    while len(out) < n and tries < n * max_tries:
        tries += 1
        try:
            blk = fn(rng)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if blk is None or "\\choice\n{" not in blk:
            continue
        key = blk.split("\\choice")[0]
        if key not in seen:
            seen.add(key)
            out.append(blk)
    return out
