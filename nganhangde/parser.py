"""Tách file .tex (khung ex_test) thành danh sách câu hỏi.

Hỗ trợ 4 loại câu (theo cấu trúc đề 2025):
    TN – trắc nghiệm 4 phương án   \\choice{..}{..}{..}{..}
    DS – đúng/sai 4 ý              \\choiceTF[t]{..}{..}{..}{..}
    KQ – trả lời ngắn             \\shortans[oly]{..}
    TL – tự luận                  \\begin{bt}...\\end{bt} hoặc ex không có phương án
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .idcode import parse_id
from .texutil import find_command, read_command_args, strip_true

ENV_RE = re.compile(r"\\begin\{(ex|bt)\}(.*?)\\end\{\1\}", re.S)
TAG_RE = re.compile(r"%\[([^\]]*)\]")
LETTERS = "ABCDEFGH"
DS_LETTERS = "abcdefgh"


@dataclass
class Question:
    qtype: str                      # TN / DS / KQ / TL
    stem: str                       # đề bài (phần trước \choice ...)
    choices: list[str] = field(default_factory=list)   # phương án / các ý (đã bỏ \True)
    correct: list[bool] = field(default_factory=list)  # TN: đúng 1 ý; DS: mảng Đ/S
    short_answer: str = ""          # KQ
    choice_opt: str = ""            # tham số tuỳ chọn của \choice[..] / \choiceTF[..]
    solution: str = ""              # nội dung \loigiai{...}
    id_code: str = ""
    tags: list[str] = field(default_factory=list)       # các %[...] khác: nguồn, tác giả
    env: str = "ex"
    raw: str = ""                   # khối LaTeX gốc
    db_id: int | None = None

    # ---- tiện ích ----
    @property
    def answer_text(self) -> str:
        if self.qtype == "TN":
            return "".join(LETTERS[i] for i, c in enumerate(self.correct) if c) or "?"
        if self.qtype == "DS":
            return "".join("Đ" if c else "S" for c in self.correct)
        if self.qtype == "KQ":
            return self.short_answer
        return ""

    @property
    def fingerprint(self) -> str:
        """Mã băm nội dung đã chuẩn hoá – dùng phát hiện câu trùng."""
        # sắp xếp phương án ⇒ câu chỉ đảo thứ tự phương án vẫn bị coi là trùng
        body = self.stem + "||" + "||".join(sorted(self.choices))
        body = re.sub(r"\\(left|right|displaystyle|dfrac|tfrac)", lambda m: "frac" if "frac" in m.group(1) else "", body)
        body = re.sub(r"[\s{}$]", "", body).lower()
        return hashlib.sha1(body.encode("utf-8")).hexdigest()

    def set_id(self, new_id: str):
        """Đổi/gán ID, cập nhật cả khối LaTeX gốc (raw) để xuất file giữ nguyên phần còn lại."""
        new_id = new_id.strip().upper()
        old = self.id_code
        self.id_code = new_id
        if not self.raw:
            return
        first, sep, rest = self.raw.partition("\n")
        if old and f"%[{old}]" in first:
            first = first.replace(f"%[{old}]", f"%[{new_id}]", 1)
        elif old:
            first = re.sub(r"%\[" + re.escape(old) + r"\]", f"%[{new_id}]", first, count=1, flags=re.I)
        else:
            first = first + f"%[{new_id}]"
        self.raw = first + sep + rest

    def to_latex(self, with_solution: bool = True) -> str:
        """Dựng lại khối LaTeX từ các trường (sau khi đã trộn phương án)."""
        head = "\\begin{%s}" % self.env
        meta = "".join(f"%[{t}]" for t in self.tags)
        if self.id_code:
            meta += f"%[{self.id_code}]"
        lines = [head + meta, "\t" + self.stem.strip()]
        opt = f"[{self.choice_opt}]" if self.choice_opt else ""
        if self.qtype in ("TN", "DS"):
            cmd = "\\choice" if self.qtype == "TN" else "\\choiceTF"
            lines.append(f"\t{cmd}{opt}")
            for txt, ok in zip(self.choices, self.correct):
                lines.append("\t{" + ("\\True " if ok else "") + txt + "}")
        elif self.qtype == "KQ":
            lines.append(f"\t\\shortans{opt}{{{self.short_answer}}}")
        if with_solution and self.solution.strip():
            lines.append("\t\\loigiai{\n" + self.solution.strip("\n").rstrip() + "\n\t}")
        lines.append("\\end{%s}" % self.env)
        return "\n".join(lines)


def parse_block(env: str, body: str) -> Question:
    first_line, _, rest = body.partition("\n")
    tags = TAG_RE.findall(first_line)
    id_code = ""
    other_tags = []
    for t in tags:
        if not id_code and parse_id(t):
            id_code = t.strip().upper()
        else:
            other_tags.append(t.strip())
    content = rest if TAG_RE.search(first_line) else body

    # tách lời giải
    solution = ""
    p = find_command(content, "loigiai")
    if p >= 0:
        _, args, end = read_command_args(content, p + len("\\loigiai"), 1, optional=False)
        if args:
            solution = args[0].strip("\n")
            content = content[:p] + content[end:]

    q = Question(qtype="TL", stem=content.strip(), id_code=id_code, tags=other_tags, env=env)

    for cmd, qtype in (("choiceTF", "DS"), ("choice", "TN")):
        p = find_command(content, cmd)
        if p >= 0:
            opt, args, end = read_command_args(content, p + len(cmd) + 1, None)
            q.qtype = qtype
            q.choice_opt = opt or ""
            for a in args:
                txt, ok = strip_true(a)
                q.choices.append(txt)
                q.correct.append(ok)
            q.stem = (content[:p] + content[end:]).strip()
            break
    else:
        p = find_command(content, "shortans")
        if p >= 0:
            opt, args, end = read_command_args(content, p + len("\\shortans"), 1)
            q.qtype = "KQ"
            q.choice_opt = opt or ""
            q.short_answer = args[0].strip() if args else ""
            q.stem = (content[:p] + content[end:]).strip()

    q.solution = solution
    return q


def parse_tex(text: str) -> list[Question]:
    out = []
    for m in ENV_RE.finditer(text):
        q = parse_block(m.group(1), m.group(2))
        q.raw = m.group(0)
        out.append(q)
    return out


def parse_file(path: str) -> list[Question]:
    with open(path, encoding="utf-8") as f:
        return parse_tex(f.read())


def validate(q: Question) -> list[str]:
    """Kiểm tra lỗi soạn thảo thường gặp; trả về danh sách cảnh báo."""
    warn = []
    if not q.id_code:
        warn.append("Thiếu ID dạng [0D2N1-2]")
    if q.qtype == "TN":
        if len(q.choices) != 4:
            warn.append(f"TN có {len(q.choices)} phương án (cần 4)")
        if sum(q.correct) != 1:
            warn.append(f"TN có {sum(q.correct)} đáp án \\True (cần đúng 1)")
    if q.qtype == "DS" and len(q.choices) != 4:
        warn.append(f"Đúng/Sai có {len(q.choices)} ý (cần 4)")
    if q.qtype == "KQ" and not q.short_answer:
        warn.append("Trả lời ngắn chưa có đáp án")
    if not q.solution:
        warn.append("Chưa có lời giải")
    if q.stem.count("$") % 2:
        warn.append("Số dấu $ lẻ trong đề bài")
    return warn
