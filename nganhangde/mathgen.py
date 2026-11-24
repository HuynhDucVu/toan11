"""Sinh câu hỏi số từ câu mẫu có tham số (tương tự «Sinh số / MakeSo»).

Câu mẫu là một khối \\begin{ex}…\\end{ex} bình thường, thêm các dòng khai báo bắt đầu bằng «%@»:

    %@ a = 1..9            số nguyên ngẫu nhiên trong [1; 9]
    %@ b = -5..5 khac 0    số nguyên trong [-5; 5], khác 0 (khac: liệt kê giá trị loại trừ, cách nhau dấu phẩy)
    %@ c = [2, 3, 5, 7]    chọn ngẫu nhiên trong danh sách
    %@ d = 0.5..3 buoc 0.5 số thực theo bước
    %@ D = b*b - 4*a*c     biểu thức tính từ biến đã có
    %@ dk: D > 0 and a != c   điều kiện (sai thì sinh lại)

Trong nội dung câu (đề, phương án, đáp án, lời giải) viết  @{biểu thức}  để chèn giá trị.
Hàm định dạng hay dùng:
    frac(p, q)   phân số tối giản dạng LaTeX: \\dfrac{p}{q} (tự rút gọn, mẫu 1 ⇒ số nguyên)
    dec(x, n=2)  số thập phân dấu phẩy: 0{,}25   (bỏ số 0 thừa)
    sgn(x)       số có dấu: «+ 3», «- 3»
    term(x, 'x') hạng tử có dấu: «+ 3x», «- x», (0 ⇒ bỏ hẳn)
    coef(x, 'x') hệ số trước biến: 1→«x», -1→«-x», 3→«3x»
    sq(x)        căn rút gọn: sq(12) → «2\\sqrt{3}»
    C(n,k) A(n,k) fact(n) gcd lcm abs round sqrt pi

Mỗi biến thể được kiểm tra lại bằng phần «Rà soát» (đáp án/lời giải/LaTeX) và loại bỏ trùng.
"""
from __future__ import annotations

import math
import random
import re
from fractions import Fraction

from .parser import parse_tex
from .review import LOI, review_question, worst
from .texutil import read_group

DECL_RE = re.compile(r"^[ \t]*%@[ \t]*(.+?)[ \t]*$", re.M)
RANGE_RE = re.compile(r"^(-?[\d.]+)\s*\.\.\s*(-?[\d.]+)(?:\s+buoc\s+([\d.]+))?(?:\s+khac\s+(.+))?$")


class TemplateError(ValueError):
    pass


# ---------------------------------------------------------------- hàm định dạng
def frac(p, q=1) -> str:
    f = Fraction(p).limit_denominator(10 ** 6) / Fraction(q).limit_denominator(10 ** 6)
    if f.denominator == 1:
        return str(f.numerator)
    sign = "-" if f < 0 else ""
    return f"{sign}\\dfrac{{{abs(f.numerator)}}}{{{f.denominator}}}"


def dec(x, n: int = 2) -> str:
    s = f"{round(float(x), n):.{n}f}".rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s.replace(".", "{,}")


def sgn(x) -> str:
    x = _num(x)
    return f"+ {x}" if x >= 0 else f"- {abs(x)}"


def term(x, var: str = "") -> str:
    """Hạng tử có dấu đứng sau hạng tử khác: term(3,'x')→«+ 3x», term(-1,'x')→«- x», term(0,'x')→«», term(-5)→«- 5»."""
    x = _num(x)
    if x == 0:
        return ""
    s = "+ " if x > 0 else "- "
    a = abs(x)
    if var:
        return s + (var if a == 1 else f"{a}{var}")
    return s + str(a)


def coef(x, var: str = "x") -> str:
    x = _num(x)
    if x == 1:
        return var
    if x == -1:
        return "-" + var
    return f"{x}{var}"


def sq(n) -> str:
    """√n rút gọn: 12 → 2\\sqrt{3}; 16 → 4."""
    n = int(n)
    if n < 0:
        raise TemplateError("sq() cần số không âm")
    a, b = 1, n
    k = 2
    while k * k <= b:
        while b % (k * k) == 0:
            a *= k
            b //= k * k
        k += 1
    if b == 1:
        return str(a)
    return (f"{a}" if a != 1 else "") + f"\\sqrt{{{b}}}"


def _num(x):
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, Fraction) and x.denominator == 1:
        return x.numerator
    return x


SAFE = {"frac": frac, "dec": dec, "sgn": sgn, "term": term, "coef": coef, "sq": sq, "abs": abs, "round": round,
        "min": min, "max": max, "int": int, "float": float, "sqrt": math.sqrt, "pi": math.pi,
        "gcd": math.gcd, "lcm": math.lcm, "C": math.comb, "A": math.perm, "fact": math.factorial,
        "Fraction": Fraction, "floor": math.floor, "ceil": math.ceil, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "exp": math.exp, "e": math.e, "True": True, "False": False}


def _eval(expr: str, env: dict):
    if "__" in expr or "import" in expr or "lambda" in expr:
        raise TemplateError(f"Biểu thức không hợp lệ: {expr}")
    try:
        return eval(expr, {"__builtins__": {}}, {**SAFE, **env})  # noqa: S307 – câu mẫu do giáo viên soạn
    except ZeroDivisionError:
        raise
    except Exception as e:  # noqa: BLE001
        raise TemplateError(f"Lỗi ở biểu thức «{expr}»: {e}") from None


def _fmt(v) -> str:
    v = _num(v)
    if isinstance(v, float):
        return dec(v, 4)
    if isinstance(v, Fraction):
        return frac(v)
    return str(v)


# ---------------------------------------------------------------- đọc câu mẫu
def parse_template(text: str):
    """Tách phần khai báo %@ và phần thân. Trả về (danh sách khai báo, điều kiện, thân)."""
    decls, conds = [], []
    for m in DECL_RE.finditer(text):
        line = m.group(1)
        if re.match(r"^(dk|đk|dieukien)\s*:", line, re.I):
            conds.append(line.split(":", 1)[1].strip())
        elif "=" in line:
            name, rhs = line.split("=", 1)
            name = name.strip()
            if not re.match(r"^[A-Za-z_]\w*$", name):
                raise TemplateError(f"Tên biến không hợp lệ: «{name}»")
            decls.append((name, rhs.strip()))
        else:
            raise TemplateError(f"Không hiểu dòng khai báo: «%@ {line}»")
    body = DECL_RE.sub("", text)
    body = re.sub(r"\n[ \t]*\n(?=[ \t]*\\(choice|shortans|loigiai|end))", "\n", body)
    return decls, conds, body


def _draw(rhs: str, env: dict, rng: random.Random):
    m = RANGE_RE.match(rhs)
    if m:
        lo, hi, step, excl = m.groups()
        ex = {_num(float(x)) for x in excl.split(",")} if excl else set()
        if step or "." in lo or "." in hi:
            st = float(step or 1)
            n = int(round((float(hi) - float(lo)) / st))
            vals = [_num(round(float(lo) + i * st, 10)) for i in range(n + 1)]
        else:
            vals = list(range(int(lo), int(hi) + 1))
        vals = [v for v in vals if v not in ex]
        if not vals:
            raise TemplateError(f"Miền giá trị rỗng: {rhs}")
        return rng.choice(vals)
    if rhs.startswith("[") and rhs.endswith("]"):
        vals = _eval(rhs, env)
        return rng.choice(list(vals))
    return _eval(rhs, env)


def substitute(body: str, env: dict) -> str:
    out, i = [], 0
    while True:
        j = body.find("@{", i)
        if j < 0:
            out.append(body[i:])
            break
        out.append(body[i:j])
        expr, k = read_group(body, j + 1)
        out.append(_fmt(_eval(expr, env)))
        i = k
    return "".join(out)


def instantiate(text: str, rng: random.Random, max_tries: int = 500) -> tuple[str, dict]:
    decls, conds, body = parse_template(text)
    last_err = None
    for _ in range(max_tries):
        env = {}
        try:
            for name, rhs in decls:
                env[name] = _draw(rhs, env, rng)
            if not all(_eval(c, env) for c in conds):
                continue
            return substitute(body, env), env
        except ZeroDivisionError as e:
            last_err = e
            continue
    raise TemplateError("Không tìm được bộ số thoả điều kiện sau nhiều lần thử"
                        + (f" ({last_err})" if last_err else "") + " – kiểm tra lại «%@ dk:».")


def generate(text: str, n: int = 10, seed: int | None = None, check: bool = True):
    """Sinh tối đa n biến thể khác nhau. Trả về (danh_sách_câu, danh_sách_cảnh_báo)."""
    rng = random.Random(seed)
    out, seen, warns = [], set(), []
    tries = 0
    while len(out) < n and tries < n * 30:
        tries += 1
        tex, env = instantiate(text, rng)
        qs = parse_tex(tex)
        if len(qs) != 1:
            raise TemplateError("Câu mẫu phải là đúng 1 khối \\begin{ex}…\\end{ex}")
        q = qs[0]
        if q.qtype == "TN" and len(set(q.choices)) < len(q.choices):
            continue                                   # phương án bị trùng ⇒ sinh lại
        if q.fingerprint in seen:
            continue
        if check and worst(review_question(q)) == LOI:
            warns.append(f"Bỏ 1 biến thể lỗi ({', '.join(i.msg for i in review_question(q) if i.level == LOI)}) "
                         f"với {env}")
            continue
        seen.add(q.fingerprint)
        out.append(q)
    if len(out) < n:
        warns.append(f"Chỉ sinh được {len(out)}/{n} biến thể khác nhau – miền giá trị của biến quá hẹp.")
    return out, warns


SAMPLE = r"""\begin{ex}%[0D7N2-1]%[Sinh số]
%@ a = 1..3
%@ x1 = -6..6
%@ x2 = -6..6
%@ dk: x1 < x2 and x1 + x2 != 0 and x1*x2 != 0
%@ b = -a*(x1 + x2)
%@ c = a*x1*x2
	Tập nghiệm của bất phương trình $@{coef(a,'x^2')} @{term(b,'x')} @{term(c)} < 0$ là
	\choice
	{\True $(@{x1};@{x2})$}
	{$(-\infty;@{x1})\cup(@{x2};+\infty)$}
	{$[@{x1};@{x2}]$}
	{$(@{x1 - 1};@{x2 + 1})$}
	\loigiai{
		Tam thức $f(x)=@{coef(a,'x^2')} @{term(b,'x')} @{term(c)}$ có hai nghiệm $x_1=@{x1}$, $x_2=@{x2}$ và hệ số $a=@{a}>0$.\\
		Do đó $f(x)<0 \Leftrightarrow @{x1}<x<@{x2}$. Chọn đáp án A.
	}
\end{ex}
"""


SAMPLE_KQ = r"""\begin{ex}%[0D0V2-4]%[Sinh số]
%@ n = 8..15
%@ k = 2..4
%@ m = 3..7
%@ dk: m < n
%@ p = Fraction(C(m, k), C(n, k))
	Một hộp có @{n} viên bi, trong đó có @{m} viên bi đỏ. Lấy ngẫu nhiên @{k} viên bi.
	Xác suất để lấy được @{k} viên bi đỏ là (làm tròn đến hàng phần trăm)
	\shortans[oly]{$@{dec(float(p), 2)}$}
	\loigiai{
		Số phần tử không gian mẫu: $n(\Omega)=\mathrm{C}_{@{n}}^{@{k}}=@{C(n,k)}$.\\
		Số kết quả thuận lợi: $n(A)=\mathrm{C}_{@{m}}^{@{k}}=@{C(m,k)}$.\\
		Vậy $P(A)=@{frac(C(m,k), C(n,k))}\approx @{dec(float(p), 2)}$.
	}
\end{ex}
"""


def generate_file(text: str, n_each: int = 5, seed: int | None = None):
    """Sinh biến thể cho mọi câu mẫu trong một file (mỗi khối ex có dòng %@ là một câu mẫu)."""
    from .parser import ENV_RE
    rng = random.Random(seed)
    out, warns = [], []
    for m in ENV_RE.finditer(text):
        block = m.group(0)
        if "%@" not in block:
            continue
        qs, w = generate(block, n_each, rng.randrange(10 ** 9))
        out += qs
        warns += w
    return out, warns
