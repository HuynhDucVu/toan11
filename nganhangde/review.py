"""Rà soát đáp án và lời giải.

Mỗi câu được kiểm tra theo 3 nhóm, kết quả là danh sách `Issue(level, code, msg)`:

  LOI (lỗi – nên sửa hoặc xoá câu)
    * cấu trúc: TN không đủ 4 phương án / không đúng 1 \\True / phương án trùng hoặc rỗng;
      Đúng/Sai không đủ 4 ý; trả lời ngắn thiếu đáp án hoặc đáp án không phải số
    * đáp án mâu thuẫn lời giải: lời giải Đúng/Sai ghi «Đúng/Sai» ngược với \\True;
      lời giải TN ghi «Chọn B» nhưng \\True ở phương án khác
    * LaTeX hỏng: ngoặc { } lệch, số dấu $ lẻ, \\begin/\\end không khớp, \\left/\\right lệch

  CANH_BAO (cần xem lại)
    * thiếu ID, thiếu lời giải
    * lời giải không chứa đáp án trả lời ngắn; lời giải dẫn tới một phương án sai
    * đáp án trả lời ngắn dài quá 4 kí tự (không tô được trên phiếu thi 2025)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import Question

LOI, CANH_BAO = "Lỗi", "Cảnh báo"
LETTERS = "ABCD"

CHON_RE = re.compile(r"Chọn\s*(?:đáp\s*án|phương\s*án|câu)?\s*(?:\\textbf\{|\\True\s*)?\s*\(?\s*([A-D])\s*\)?(?![A-Za-zÀ-ỹ])")
ITEMCH_RE = re.compile(r"\\itemch(?![A-Za-z])")
BEGIN_END_RE = re.compile(r"\\(begin|end)\{([^}]*)\}")
NUMBER_RE = re.compile(r"^-?\d+(,\d+)?$")


@dataclass
class Issue:
    level: str
    code: str
    msg: str


def strip_comments(s: str) -> str:
    out = []
    for line in s.split("\n"):
        j, cut = 0, len(line)
        while j < len(line):
            if line[j] == "\\":
                j += 2
                continue
            if line[j] == "%":
                cut = j
                break
            j += 1
        out.append(line[:cut])
    return "\n".join(out)


def norm_math(s: str) -> str:
    """Chuẩn hoá biểu thức để so khớp: bỏ khoảng trắng, $, \\left \\right, ngoặc nhọn…"""
    s = re.sub(r"\\(left|right|displaystyle|,|;|!|quad)", "", s)
    s = re.sub(r"\\[dt]frac", r"\\frac", s)
    s = s.replace("{,}", ",")
    return re.sub(r"[\s${}]", "", s).lower()


def has_token(hay: str, needle: str) -> bool:
    """needle xuất hiện trong hay như một cụm trọn vẹn (vd '-1' không khớp trong '-12')."""
    if not needle:
        return False
    return re.search(r"(?<![0-9a-z\\])" + re.escape(needle) + r"(?![0-9a-z])", hay) is not None


def plain_number(a: str) -> str:
    a = a.replace("{,}", ",").replace(".", ",")
    return re.sub(r"[\s${}]", "", a)


# ---------------------------------------------------------------- LaTeX
def latex_issues(text: str, where: str) -> list[Issue]:
    t = strip_comments(text)
    out = []
    depth, j = 0, 0
    while j < len(t):
        c = t[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                break
        j += 1
    if depth != 0:
        out.append(Issue(LOI, "ngoac", f"{where}: ngoặc {{ }} không cân bằng"))
    no_dd = t.replace("\\$", "")
    if no_dd.count("$") % 2:
        out.append(Issue(LOI, "dola", f"{where}: số dấu $ lẻ"))
    stack = []
    for kind, env in BEGIN_END_RE.findall(t):
        if kind == "begin":
            stack.append(env)
        elif not stack or stack.pop() != env:
            out.append(Issue(LOI, "env", f"{where}: \\end{{{env}}} không khớp \\begin"))
            break
    else:
        if stack:
            out.append(Issue(LOI, "env", f"{where}: thiếu \\end{{{stack[-1]}}}"))
    nl = len(re.findall(r"\\left(?![a-zA-Z])", t))
    nr = len(re.findall(r"\\right(?![a-zA-Z])", t))
    if nl != nr:
        out.append(Issue(LOI, "leftright", f"{where}: {nl} \\left nhưng {nr} \\right"))
    return out


# ---------------------------------------------------------------- từng loại câu
def _ds_solution_marks(solution: str) -> list[bool | None]:
    """Đọc lời giải itemchoice: mỗi \\itemch bắt đầu bằng «Đúng»/«Sai» → True/False/None."""
    b, e = solution.find("\\begin{itemchoice}"), solution.rfind("\\end{itemchoice}")
    body = solution[b + len("\\begin{itemchoice}"):e] if b >= 0 and e > b else solution
    parts = ITEMCH_RE.split(body)[1:]
    marks = []
    for p in parts:
        head = re.sub(r"\\[a-zA-Z]+\s*", "", p.strip())[:20].lstrip("{( ").lower()
        if head.startswith("đúng"):
            marks.append(True)
        elif head.startswith("sai"):
            marks.append(False)
        else:
            marks.append(None)
    return marks


def check_tn(q: Question) -> list[Issue]:
    out = []
    if len(q.choices) != 4:
        out.append(Issue(LOI, "so_pa", f"Có {len(q.choices)} phương án (cần 4)"))
    n_true = sum(q.correct)
    if n_true != 1:
        out.append(Issue(LOI, "so_true", f"Có {n_true} đáp án \\True (cần đúng 1)"))
    normed = [norm_math(c) for c in q.choices]
    if any(not c for c in normed):
        out.append(Issue(LOI, "pa_rong", "Có phương án rỗng"))
    dups = {c for c in normed if c and normed.count(c) > 1}
    if dups:
        letters = [LETTERS[i] for i, c in enumerate(normed) if c in dups and i < 4]
        out.append(Issue(LOI, "pa_trung", f"Phương án {', '.join(letters)} giống nhau"))
    if n_true == 1 and q.solution:
        right = q.correct.index(True)
        m = CHON_RE.findall(strip_comments(q.solution))
        if m and m[-1] != LETTERS[right]:
            out.append(Issue(LOI, "chon_lech", f"Lời giải ghi «Chọn {m[-1]}» nhưng đáp án \\True là {LETTERS[right]}"))
        elif not m:
            sol = norm_math(q.solution)
            tail = norm_math(q.solution[-300:])
            ok = has_token(sol, normed[right])
            wrong = [LETTERS[i] for i, c in enumerate(normed)
                     if i != right and i < 4 and len(c) >= 2 and has_token(tail, c) and c not in normed[right]]
            if wrong and not ok:
                out.append(Issue(CANH_BAO, "lg_lech",
                                 f"Cuối lời giải xuất hiện phương án {', '.join(wrong)} nhưng không thấy đáp án "
                                 f"{LETTERS[right]} – kiểm tra lại đáp án"))
    return out


def check_ds(q: Question) -> list[Issue]:
    out = []
    if len(q.choices) != 4:
        out.append(Issue(LOI, "so_y", f"Có {len(q.choices)} ý (cần 4)"))
    if q.solution:
        marks = _ds_solution_marks(q.solution)
        if marks and len(marks) == len(q.choices):
            bad = [("abcd"[i] if i < 4 else str(i + 1))
                   for i, (m, ok) in enumerate(zip(marks, q.correct)) if m is not None and m != ok]
            if bad:
                out.append(Issue(LOI, "ds_lech",
                                 f"Ý {', '.join(bad)}: lời giải kết luận ngược với đánh dấu \\True"))
            if any(m is None for m in marks):
                out.append(Issue(CANH_BAO, "ds_khong_ro", "Có ý trong lời giải không mở đầu bằng «Đúng»/«Sai»"))
        elif marks:
            out.append(Issue(CANH_BAO, "ds_so_muc", f"Lời giải có {len(marks)} mục \\itemch, câu có {len(q.choices)} ý"))
    return out


def check_kq(q: Question) -> list[Issue]:
    out = []
    a = plain_number(q.short_answer)
    if not a:
        return [Issue(LOI, "kq_rong", "Chưa có đáp án trả lời ngắn")]
    if re.search(r"\d\.\d", q.short_answer):
        out.append(Issue(CANH_BAO, "kq_cham", f"Đáp án «{q.short_answer}» dùng dấu chấm thập phân (phiếu thi dùng dấu phẩy)"))
    if not NUMBER_RE.match(a):
        out.append(Issue(LOI, "kq_so", f"Đáp án «{q.short_answer}» không phải một số (phiếu thi chỉ tô được số)"))
    elif len(a) > 4:
        out.append(Issue(CANH_BAO, "kq_dai", f"Đáp án «{a}» dài {len(a)} kí tự, phiếu thi chỉ có 4 ô"))
    if q.solution and NUMBER_RE.match(a):
        sol = plain_number(strip_comments(q.solution))
        if not re.search(r"(?<![\d,])" + re.escape(a) + r"(?![\d])", sol):
            out.append(Issue(CANH_BAO, "kq_khong_co",
                             f"Lời giải không ghi giá trị {a} – thiếu bước kết luận hoặc đáp án sai"))
    return out


def review_question(q: Question) -> list[Issue]:
    out = []
    if not q.id_code:
        out.append(Issue(CANH_BAO, "id", "Thiếu ID"))
    if not q.solution.strip():
        out.append(Issue(CANH_BAO, "lg", "Chưa có lời giải"))
    out += {"TN": check_tn, "DS": check_ds, "KQ": check_kq}.get(q.qtype, lambda _q: [])(q)
    out += latex_issues(q.stem, "Đề bài")
    for i, c in enumerate(q.choices):
        out += latex_issues(c, f"Phương án {LETTERS[i] if q.qtype == 'TN' and i < 4 else 'abcd'[i] if i < 4 else i + 1}")
    if q.solution:
        out += latex_issues(q.solution, "Lời giải")
    return out


def worst(issues: list[Issue]) -> str:
    if any(i.level == LOI for i in issues):
        return LOI
    return CANH_BAO if issues else ""


# ---------------------------------------------------------------- file
def remove_questions_text(text: str, raws_to_remove: list[str]) -> tuple[str, int]:
    """Xoá các khối câu (theo nội dung gốc) khỏi file, giữ nguyên phần còn lại."""
    n = 0
    for raw in raws_to_remove:
        i = text.find(raw)
        if i < 0:
            continue
        j = i + len(raw)
        if j < len(text) and text[j] == "\n":
            j += 1
        text = text[:i] + text[j:]
        n += 1
    return text, n


# ================================================================ TỰ SỬA
THEO_LOI_GIAI, THEO_DAP_AN = "theo_loi_giai", "theo_dap_an"
WORD_RE = re.compile(r"(Đúng|Sai|đúng|sai|ĐÚNG|SAI)")


def _replace_chon_letters(solution: str, mapping) -> str:
    """Đổi chữ cái trong mọi cụm «Chọn X» của lời giải; mapping: hàm chữ_cũ → chữ_mới."""
    def sub(m):
        a, b = m.span(1)
        rel_a, rel_b = a - m.start(), b - m.start()
        g = m.group(0)
        return g[:rel_a] + mapping(m.group(1)) + g[rel_b:]
    return CHON_RE.sub(sub, solution)


def _rewrite_ds_words(solution: str, marks: list[bool]) -> str:
    """Viết lại chữ Đúng/Sai đầu mỗi mục \\itemch cho khớp marks."""
    pos = [m.end() for m in ITEMCH_RE.finditer(solution)]
    if len(pos) != len(marks):
        return solution
    out, last = [], 0
    for p, ok in zip(pos, marks):
        m = WORD_RE.search(solution, p, min(len(solution), p + 40))
        if not m:
            continue
        word = "Đúng" if ok else "Sai"
        if m.group(0).isupper():
            word = word.upper()
        out.append(solution[last:m.start()] + word)
        last = m.end()
    out.append(solution[last:])
    return "".join(out)


def fix_question(q: Question, policy: str = THEO_LOI_GIAI) -> tuple[Question, list[str]]:
    """Tự sửa những lỗi sửa được một cách chắc chắn. Trả về (câu đã sửa, danh sách việc đã làm).

    policy khi đáp án mâu thuẫn lời giải:
        THEO_LOI_GIAI – giữ lời giải, sửa đánh dấu \\True cho khớp lời giải
        THEO_DAP_AN   – giữ \\True, sửa chữ trong lời giải («Chọn X», «Đúng/Sai») cho khớp đáp án
    """
    import copy
    q = copy.deepcopy(q)
    done = []
    sol_nc = strip_comments(q.solution)

    if q.qtype == "TN" and len(q.choices) == 4:
        m = CHON_RE.findall(sol_nc)
        n_true = sum(q.correct)
        if m:
            said = LETTERS.index(m[-1])
            right = q.correct.index(True) if n_true == 1 else None
            if right != said:
                if policy == THEO_LOI_GIAI or n_true != 1:
                    q.correct = [i == said for i in range(4)]
                    done.append(f"Đặt \\True vào phương án {m[-1]} theo lời giải")
                else:
                    q.solution = _replace_chon_letters(q.solution, lambda _L: LETTERS[right])
                    done.append(f"Sửa lời giải thành «Chọn {LETTERS[right]}» theo đáp án")

    elif q.qtype == "DS" and q.solution:
        marks = _ds_solution_marks(q.solution)
        if len(marks) == len(q.choices) and all(x is not None for x in marks) and marks != q.correct:
            bad = ", ".join("abcd"[i] for i, (a, b) in enumerate(zip(marks, q.correct)) if a != b and i < 4)
            if policy == THEO_LOI_GIAI:
                q.correct = list(marks)
                done.append(f"Sửa đánh dấu \\True ý {bad} theo lời giải")
            else:
                new = _rewrite_ds_words(q.solution, q.correct)
                if new != q.solution:
                    q.solution = new
                    done.append(f"Sửa chữ Đúng/Sai trong lời giải ý {bad} theo đáp án")

    elif q.qtype == "KQ" and re.search(r"\d\.\d", q.short_answer):
        q.short_answer = re.sub(r"(\d)\.(\d)", r"\1{,}\2", q.short_answer)
        done.append("Đổi dấu chấm thập phân thành dấu phẩy")
    return q, done


def add_conclusion(q: Question) -> tuple[Question, bool]:
    """Thêm câu kết luận cuối lời giải (TN: «Chọn đáp án X»; trả lời ngắn: «Vậy đáp án là …»)."""
    import copy
    if not q.solution.strip():
        return q, False
    sol = strip_comments(q.solution)
    q2 = copy.deepcopy(q)
    if q.qtype == "TN" and sum(q.correct) == 1 and not CHON_RE.search(sol):
        q2.solution = q.solution.rstrip() + "\n\t\tChọn đáp án \\textbf{" + LETTERS[q.correct.index(True)] + "}."
        return q2, True
    if q.qtype == "KQ" and q.short_answer:
        a = plain_number(q.short_answer)
        if NUMBER_RE.match(a) and not re.search(r"(?<![\d,])" + re.escape(a) + r"(?![\d])", plain_number(sol)):
            ans = q.short_answer if "$" in q.short_answer else f"${q.short_answer}$"
            q2.solution = q.solution.rstrip() + f"\\\\\n\t\tVậy đáp án là {ans}."
            return q2, True
    return q, False


def replace_questions_text(text: str, pairs: list[tuple[str, str]]) -> tuple[str, int]:
    """Thay khối câu cũ (raw) bằng khối mới trong file, giữ nguyên phần còn lại."""
    n = 0
    for old, new in pairs:
        i = text.find(old)
        if i >= 0:
            text = text[:i] + new + text[i + len(old):]
            n += 1
    return text, n
