"""Bộ sinh câu hỏi trắc nghiệm đổi số tự động (Hàm số & Mẫu tự tạo) chuẩn ex_test."""
from __future__ import annotations
import math
import random
import re


def _fmt_poly_cubic(a: int, b: int, c: int, d: int) -> str:
    parts: list[str] = []
    for coef, var in [(a, "x^3"), (b, "x^2"), (c, "x"), (d, "")]:
        if coef == 0:
            continue
        sign = "+" if coef > 0 else "-"
        abs_c = abs(coef)
        term = f"{abs_c}{var}" if (abs_c != 1 or not var) else var
        if not parts:
            parts.append(f"-{term}" if coef < 0 else term)
        else:
            parts.append(f" {sign} {term}")
    return "".join(parts) or "0"


def generate_cubic_monotonicity(count: int = 5) -> str:
    """Sinh câu hỏi: Xét tính đơn điệu hàm bậc ba có 2 điểm cực trị nguyên."""
    out: list[str] = []
    for _ in range(count):
        x1 = random.randint(-3, 0)
        x2 = x1 + random.randint(2, 4)
        # y' = 3(x-x1)(x-x2) = 3x^2 - 3(x1+x2)x + 3x1x2
        # => y = x^3 - 3/2(x1+x2)x^2 + 3x1x2 x + d  (chọn x1+x2 chẵn để hệ số nguyên)
        if (x1 + x2) % 2 != 0:
            x2 += 1
        a = 1
        b = -3 * (x1 + x2) // 2
        c = 3 * x1 * x2
        d = random.randint(-5, 5)
        fx = _fmt_poly_cubic(a, b, c, d)
        ans_true = f"$({x1};{x2})$"
        distractors = [
            f"$(-\\infty;{x1})$",
            f"$({x2};+\\infty)$",
            f"$({x1 - 1};{x2 + 1})$",
        ]
        choices = [f"\\True {ans_true}"] + distractors
        random.shuffle(choices)
        blk = (
            "\\begin{ex}%[2D1N1-1]\n"
            f"Hàm số $y = {fx}$ nghịch biến trên khoảng nào dưới đây?\n"
            "\\choice\n"
            + "\n".join(f"{{{ch}}}" for ch in choices)
            + "\n\\loigiai{\n"
            f"Ta có $y' = 3x^2 {'+' if 2*b>=0 else ''}{2*b}x {'+' if c>=0 else ''}{c} = 0 \\Leftrightarrow \\left[\\begin{{array}}{{l}} x = {x1} \\\\ x = {x2} \\end{{array}}\\right.$.\\\\\n"
            f"Vì hệ số $a = 1 > 0$ nên $y' < 0 \\Leftrightarrow x \\in ({x1};{x2})$.\\\\\n"
            f"Vậy hàm số nghịch biến trên khoảng $({x1};{x2})$.\n"
            "}\n\\end{ex}"
        )
        out.append(blk)
    return "\n\n".join(out)


def generate_asymptote_rational(count: int = 5) -> str:
    """Sinh câu hỏi: Tìm tiệm cận đứng và tiệm cận ngang hàm bậc nhất trên bậc nhất."""
    out: list[str] = []
    for _ in range(count):
        a = random.choice([-4, -3, -2, 2, 3, 4])
        b = random.randint(-5, 5)
        c = 1
        d = random.choice([-4, -3, -2, -1, 1, 2, 3, 4])
        if a * d == b * c:
            b += 1
        tcd = -d
        tcn = a
        num = f"{a}x {'+' if b>=0 else '-'} {abs(b)}" if b != 0 else f"{a}x"
        den = f"x {'+' if d>=0 else '-'} {abs(d)}"
        ans_true = f"$x = {tcd}$ và $y = {tcn}$"
        choices = [
            f"\\True {ans_true}",
            f"$x = {d}$ và $y = {tcn}$",
            f"$x = {tcd}$ và $y = {-tcn}$",
            f"$x = {tcn}$ và $y = {tcd}$",
        ]
        random.shuffle(choices)
        blk = (
            "\\begin{ex}%[2D1N4-1]\n"
            f"Tiệm cận đứng và tiệm cận ngang của đồ thị hàm số $y = \\dfrac{{{num}}}{{{den}}}$ lần lượt là\n"
            "\\choice\n"
            + "\n".join(f"{{{ch}}}" for ch in choices)
            + "\n\\loigiai{\n"
            f"Ta có $\\lim\\limits_{{x \\to ({tcd})^+}} y = \\infty$ nên tiệm cận đứng là $x = {tcd}$.\\\\\n"
            f"Và $\\lim\\limits_{{x \\to \\pm\\infty}} y = {tcn}$ nên tiệm cận ngang là $y = {tcn}$.\n"
            "}\n\\end{ex}"
        )
        out.append(blk)
    return "\n\n".join(out)


def generate_custom_parametric(template: str, var_ranges: dict[str, tuple[int, int]], count: int = 5) -> str:
    """
    Tạo hàng loạt câu hỏi đổi số tự tạo từ mẫu bất kỳ.
    Cú pháp trong mẫu:
      - Biến ngẫu nhiên: [a], [b], [c]
      - Biểu thức tính toán: {{a + b}}, {{2*a - b}}
    """
    results: list[str] = []
    safe_globals = {"__builtins__": {}, "abs": abs, "min": min, "max": max, "math": math}
    for _ in range(count):
        env = {k: random.randint(lo, hi) for k, (lo, hi) in var_ranges.items()}
        text = template
        for k, v in env.items():
            text = text.replace(f"[{k}]", str(v))
        def _eval_expr(m: re.Match) -> str:
            expr = m.group(1).strip()
            try:
                val = eval(expr, safe_globals, env)
                return str(val)
            except Exception:
                return m.group(0)
        text = re.sub(r"\{\{([^}]+)\}\}", _eval_expr, text)
        results.append(text)
    return "\n\n".join(results)
