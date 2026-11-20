"""Google Forms qua Apps Script: sinh đoạn mã .gs tạo một Google Form dạng bài kiểm tra (quiz) từ một mã đề.

Cách dùng (giáo viên): mở script.google.com → Dự án mới → xoá mã mẫu, dán toàn bộ file .gs → bấm Chạy (hàm taoDe)
→ cấp quyền → xem nhật ký thực thi: có đường dẫn sửa Form và đường dẫn gửi học sinh.

Giới hạn của Google Forms (không do phần mềm):
* Form không hiển thị công thức LaTeX → công thức được đổi sang chữ thường/Unicode (x², √, ≤, π…); công thức phức tạp
  nên kiểm tra lại trong Form. Hình vẽ không chuyển được.
* Phần II (Đúng/Sai) tách thành 4 câu nhỏ, mỗi ý một số điểm bằng nhau – Form không chấm theo thang 0,1/0,25/0,5/1.
* Phần III (trả lời ngắn), tự luận: Apps Script không đặt được đáp án tự chấm cho ô trả lời ngắn → để giáo viên chấm
  (đáp án ghi trong phần phản hồi dành cho giáo viên ở cuối file .gs).
"""
from __future__ import annotations

import json
import re

from .generator import ExamVersion

SUP = str.maketrans("0123456789+-n()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ⁽⁾")
SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
SYMS = {r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥", r"\ne": "≠", r"\neq": "≠", r"\pi": "π",
        r"\infty": "∞", r"\cdot": "·", r"\times": "×", r"\in": "∈", r"\notin": "∉", r"\cup": "∪", r"\cap": "∩",
        r"\alpha": "α", r"\beta": "β", r"\Delta": "Δ", r"\varphi": "φ", r"\pm": "±", r"\to": "→",
        r"\Rightarrow": "⇒", r"\Leftrightarrow": "⇔", r"\perp": "⊥", r"\parallel": "∥", r"\circ": "°",
        r"\mathbb{R}": "ℝ", r"\mathbb{N}": "ℕ", r"\mathbb{Z}": "ℤ", r"\mathbb{Q}": "ℚ", r"\varnothing": "∅",
        r"\emptyset": "∅", r"\sim": "∼", r"\approx": "≈", r"\angle": "∠", r"\triangle": "△", r"\{": "{", r"\}": "}",
        r"\left": "", r"\right": "", r"\displaystyle": "", r"\,": " ", r"\;": " ", r"\!": "", r"\quad": "  "}


def _group(s: str, i: int):
    """Đọc nhóm {...} bắt đầu tại s[i] == '{' → (nội dung, vị trí sau nhóm)."""
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def math_to_text(m: str) -> str:
    out, i = [], 0
    while i < len(m):
        for cmd in ("\\dfrac", "\\frac", "\\tfrac"):
            if m.startswith(cmd, i) and m[i + len(cmd):i + len(cmd) + 1] == "{":
                a, j = _group(m, i + len(cmd))
                b, j = _group(m, j) if j < len(m) and m[j] == "{" else ("", j)
                A, B = math_to_text(a), math_to_text(b)
                wrap = (lambda t: t if re.fullmatch(r"[\w²³√π.,]+", t) else f"({t})")
                out.append(f"{wrap(A)}/{wrap(B)}")
                i = j
                break
        else:
            if m.startswith("\\sqrt", i):
                j = i + 5
                n = ""
                if j < len(m) and m[j] == "[":
                    k = m.index("]", j)
                    n, j = m[j + 1:k], k + 1
                a, j = _group(m, j) if j < len(m) and m[j] == "{" else (m[j:j + 1], j + 1)
                A = math_to_text(a)
                root = {"3": "∛", "4": "∜"}.get(n, (n.translate(SUP) if n else "") + "√")
                out.append(root + (A if len(A) == 1 else f"({A})"))
                i = j
                continue
            if m[i] in "^_" and i + 1 < len(m):
                a, j = _group(m, i + 1) if m[i + 1] == "{" else (m[i + 1], i + 2)
                A = math_to_text(a)
                tab = SUP if m[i] == "^" else SUB
                conv = A.translate(tab)
                ok = all(ch in "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ⁽⁾₀₁₂₃₄₅₆₇₈₉" for ch in conv)
                out.append(conv if ok else ("^" if m[i] == "^" else "_") + f"({A})")
                i = j
                continue
            if m[i] == "\\":
                k = re.match(r"\\(mathbb\{\w\}|[A-Za-z]+|.)", m[i:], re.S)
                if not k:                                   # dấu \ cuối chuỗi
                    i += 1
                    continue
                tok = k.group(0)
                if tok in SYMS:
                    out.append(SYMS[tok])
                elif tok in ("\\text", "\\mathrm", "\\textbf", "\\mathbf", "\\overline", "\\vec", "\\overrightarrow"):
                    j = i + len(tok)
                    a, j = _group(m, j) if j < len(m) and m[j] == "{" else ("", j)
                    pre = "→" if tok in ("\\vec", "\\overrightarrow") else ""
                    out.append(math_to_text(a) + pre)
                    i = j
                    continue
                elif tok in ("\\sin", "\\cos", "\\tan", "\\cot", "\\log", "\\ln", "\\lim", "\\max", "\\min"):
                    out.append(tok[1:] + " ")
                else:
                    out.append("")
                i += len(tok)
                continue
            if m[i] in "{}":
                i += 1
                continue
            out.append(m[i])
            i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def latex_to_text(s: str) -> str:
    s = re.sub(r"(?<!\\)%.*", "", s)
    s = re.sub(r"\\begin\{(tikzpicture|figure|center)\}.*?\\end\{\1\}", " [Hình vẽ – xem đề in] ", s, flags=re.S)
    s = re.sub(r"\\includegraphics(\[[^\]]*\])?\{[^}]*\}", " [Hình] ", s)
    s = re.sub(r"\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)",
               lambda m: math_to_text(m.group(1) or m.group(2) or m.group(3)), s, flags=re.S)
    s = re.sub(r"\\(textbf|textit|emph|underline|text)\{([^{}]*)\}", r"\2", s)
    s = re.sub(r"\\(begin|end)\{[^}]*\}|\\item(ch)?|\\\\|\\(hfill|vspace\{[^}]*\}|medskip|noindent)", " ", s)
    return re.sub(r"[ \t]+", " ", s).replace(" \n", "\n").strip()


def apps_script(v: ExamVersion, *, ten_de: str = "BÀI KIỂM TRA", scoring=None) -> str:
    from .exporter import plain_answer
    from .scoring import DEFAULT
    sc = scoring or DEFAULT
    items, key_note = [], []
    for s, label in (("TN", "PHẦN I"), ("DS", "PHẦN II"), ("KQ", "PHẦN III"), ("TL", "PHẦN IV")):
        qs = v.sections.get(s) or []
        if not qs:
            continue
        items.append({"t": "head", "title": label})
        for i, q in enumerate(qs, 1):
            stem = f"Câu {i}. " + latex_to_text(q.stem)
            if s == "TN":
                items.append({"t": "mc", "title": stem, "choices": [latex_to_text(c) for c in q.choices],
                              "ok": [bool(x) for x in q.correct], "pts": sc.tn})
            elif s == "DS":
                items.append({"t": "head", "title": stem})
                for k, (c, ok) in enumerate(zip(q.choices, q.correct)):
                    items.append({"t": "mc", "title": f"{'abcd'[k] if k < 4 else k + 1}) " + latex_to_text(c),
                                  "choices": ["Đúng", "Sai"], "ok": [ok, not ok], "pts": round(sc.ds[3] / 4, 4)})
            elif s == "KQ":
                items.append({"t": "text", "title": stem, "pts": sc.kq})
                key_note.append(f"Phần III câu {i}: {plain_answer(q.answer_text)}")
            else:
                items.append({"t": "para", "title": stem, "pts": sc.tl_points(len(qs))[i - 1]})
    data = json.dumps(items, ensure_ascii=False, indent=1)
    title = json.dumps(f"{ten_de} – Mã đề {v.code}", ensure_ascii=False)
    note = "\n".join("// " + x for x in key_note) or "// (không có)"
    return f"""/**
 * Tạo Google Form (bài kiểm tra) – {ten_de}, mã đề {v.code}. Sinh bởi phần mềm Ngân hàng đề thi.
 * Cách dùng: script.google.com → Dự án mới → dán toàn bộ mã này → chọn hàm taoDe → Chạy → cấp quyền.
 * Xem Nhật ký thực thi để lấy đường dẫn. Công thức đã đổi sang chữ thường – kiểm tra lại trong Form.
 * Phần III và tự luận: giáo viên chấm trong Form (Apps Script không đặt được đáp án cho ô trả lời ngắn).
 * Đáp án Phần III dành cho giáo viên:
{note}
 */
var DATA = {data};

function taoDe() {{
  var form = FormApp.create({title});
  form.setIsQuiz(true);
  form.setCollectEmail(false);
  form.addTextItem().setTitle('Họ và tên, lớp').setRequired(true);
  DATA.forEach(function (it) {{
    if (it.t === 'head') {{
      form.addSectionHeaderItem().setTitle(it.title);
    }} else if (it.t === 'mc') {{
      var item = form.addMultipleChoiceItem();
      item.setTitle(it.title)
          .setChoices(it.choices.map(function (c, i) {{ return item.createChoice(c, it.ok[i]); }}))
          .setPoints(Math.round(it.pts * 100) / 100 || 0);
    }} else if (it.t === 'text') {{
      form.addTextItem().setTitle(it.title).setPoints(Math.round(it.pts * 100) / 100 || 0);
    }} else {{
      form.addParagraphTextItem().setTitle(it.title).setPoints(Math.round(it.pts * 100) / 100 || 0);
    }}
  }});
  Logger.log('Sửa Form: ' + form.getEditUrl());
  Logger.log('Gửi học sinh: ' + form.getPublishedUrl());
}}
"""


def export_gas(versions, out_dir: str, **kw) -> list[str]:
    import os
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for v in versions:
        p = os.path.join(out_dir, f"google_form_{v.code}.gs")
        with open(p, "w", encoding="utf-8") as f:
            f.write(apps_script(v, **kw))
        out.append(p)
    return out
