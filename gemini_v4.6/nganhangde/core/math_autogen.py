"""Tạo tự động các câu hỏi trắc nghiệm đổi số (đủ ID6, đáp án, lời giải) như tab Soạn thảo MyLT."""
import random
from .parser import Question


def gen_asymptote_linear_rational(count: int = 5, seed: int = 2026) -> list[Question]:
    """Sinh hàng loạt câu tìm tiệm cận đứng / ngang của hàm bậc nhất trên bậc nhất (ID: 2D1N4-1)."""
    rng = random.Random(seed)
    out: list[Question] = []
    for _ in range(count):
        a = rng.choice([i for i in range(-5, 6) if i != 0])
        b = rng.randint(-6, 6)
        c = rng.choice([i for i in range(-4, 5) if i != 0])
        d = rng.choice([i for i in range(-5, 6) if i != 0])
        if a * d - b * c == 0:
            d += 1
        # Đảm bảo tỉ số nguyên cho gọn
        a = c * rng.choice([-3, -2, -1, 1, 2, 3])
        tc_ngang = a // c
        num_str = f"{a}x {'+' if b >= 0 else '-'} {abs(b)}" if b != 0 else f"{a}x"
        den_str = f"{c}x {'+' if d >= 0 else '-'} {abs(d)}"
        distractors = list({tc_ngang + 1, tc_ngang - 1, -tc_ngang if tc_ngang != 0 else 2, tc_ngang + 2})[:3]
        choices = [f"$y = {tc_ngang}$"] + [f"$y = {v}$" for v in distractors]
        q = Question(
            qtype="TN",
            stem=f"Tiệm cận ngang của đồ thị hàm số $y = \\dfrac{{{num_str}}}{{{den_str}}}$ là đường thẳng có phương trình",
            choices=choices,
            correct=[True, False, False, False],
            solution=(
                f"Ta có $\\lim\\limits_{{x \\to \\pm\\infty}} \\dfrac{{{num_str}}}{{{den_str}}} = \\dfrac{{{a}}}{{{c}}} = {tc_ngang}$.\n"
                f"Vậy tiệm cận ngang là $y = {tc_ngang}$. \\textbf{{Chọn A}}."
            ),
            ids=["2D1N4-1"],
            cmd_name="choice",
            cmd_opt="4",
        )
        q.raw = q.to_latex(True)
        out.append(q)
    return out


def gen_cubic_extrema_count(count: int = 5, seed: int = 2026) -> list[Question]:
    """Sinh hàng loạt câu tìm điểm cực đại / cực tiểu của hàm bậc ba có nghiệm nguyên đẹp (ID: 2D1H2-1)."""
    rng = random.Random(seed)
    out: list[Question] = []
    for _ in range(count):
        x1 = rng.randint(-3, 1)
        x2 = x1 + rng.choice([2, 4])
        # y' = 3(x - x1)(x - x2) = 3x^2 - 3(x1+x2)x + 3x1x2
        b_coef = -3 * (x1 + x2) // 2 if (x1 + x2) % 2 == 0 else -3 * (x1 + x2)
        scale = 1 if (x1 + x2) % 2 == 0 else 2
        a3 = scale
        b2 = -3 * (x1 + x2) * scale // 2
        c1 = 3 * x1 * x2 * scale
        d0 = rng.randint(-4, 4)
        terms = [f"{'' if a3 == 1 else a3}x^3"]
        if b2 != 0:
            terms.append(f"{'+' if b2 > 0 else '-'} {'' if abs(b2) == 1 else abs(b2)}x^2")
        if c1 != 0:
            terms.append(f"{'+' if c1 > 0 else '-'} {'' if abs(c1) == 1 else abs(c1)}x")
        if d0 != 0:
            terms.append(f"{'+' if d0 > 0 else '-'} {abs(d0)}")
        poly = " ".join(terms)
        distractors = [x2, -x1 if x1 != 0 else x2 + 1, x1 + x2 if x1 + x2 not in (x1, x2) else x2 + 2]
        choices = [f"$x = {x1}$"] + [f"$x = {v}$" for v in distractors]
        q = Question(
            qtype="TN",
            stem=f"Hàm số $y = {poly}$ đạt cực đại tại điểm",
            choices=choices,
            correct=[True, False, False, False],
            solution=(
                f"Ta có $y' = {3*a3}x^2 {'+' if 2*b2 >= 0 else '-'} {abs(2*b2)}x {'+' if c1 >= 0 else '-'} {abs(c1)} = 0 \\Leftrightarrow x = {x1}$ hoặc $x = {x2}$.\n"
                f"Vì hệ số bậc ba dương và ${x1} < {x2}$ nên hàm số đạt cực đại tại $x = {x1}$. \\textbf{{Chọn A}}."
            ),
            ids=["2D1H2-1"],
            cmd_name="choice",
            cmd_opt="4",
        )
        q.raw = q.to_latex(True)
        out.append(q)
    return out
