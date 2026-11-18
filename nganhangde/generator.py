"""Sinh đề theo ma trận: chọn câu, trộn thứ tự câu, trộn phương án, tạo nhiều mã đề."""
from __future__ import annotations

import copy
import random
import re
from dataclasses import dataclass, field

from .db import Bank
from .parser import Question

SECTION_ORDER = ["TN", "DS", "KQ", "TL"]
SECTION_TITLE = {
    "TN": "PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn",
    "DS": "PHẦN II. Câu trắc nghiệm đúng sai",
    "KQ": "PHẦN III. Câu trắc nghiệm trả lời ngắn",
    "TL": "PHẦN IV. Tự luận",
}
# Phương án có nội dung kiểu này thì không trộn (vị trí phương án có ý nghĩa)
LOCK_RE = re.compile(r"(cả\s+(ba|hai|3|2)|đều\s+(đúng|sai)|tất cả|không có .*nào|A\s*,\s*B)", re.I)
ITEMCH_RE = re.compile(r"\\itemch(?![A-Za-z])")


@dataclass
class Rule:
    """Một dòng ma trận: lấy `count` câu loại `qtype` có ID khớp mẫu `id` (GLOB)."""
    qtype: str
    count: int
    id: str = "*"
    muc_do: str | None = None
    text: str | None = None

    @classmethod
    def from_dict(cls, d):
        return cls(qtype=d["qtype"], count=int(d["count"]), id=d.get("id", "*") or "*",
                   muc_do=d.get("muc_do") or None, text=d.get("text") or None)


@dataclass
class ExamVersion:
    code: str                                   # mã đề
    sections: dict[str, list[Question]] = field(default_factory=dict)

    def all_questions(self):
        for s in SECTION_ORDER:
            yield from self.sections.get(s, [])

    def answer_key(self):
        """[(phần, số câu, đáp án)]"""
        out = []
        for s in SECTION_ORDER:
            for i, q in enumerate(self.sections.get(s, []), 1):
                out.append((s, i, q.answer_text))
        return out


class NotEnoughQuestions(Exception):
    pass


def pick_questions(bank: Bank, rules: list[Rule], rng: random.Random,
                   prefer_unused: bool = False) -> dict[str, list[Question]]:
    chosen: dict[str, list[Question]] = {s: [] for s in SECTION_ORDER}
    used_ids: set[int] = set()
    errors = []
    for r in rules:
        pool = [q for q in bank.search(qtype=r.qtype, id_like=r.id, muc_do=r.muc_do, text=r.text)
                if q.db_id not in used_ids]
        if len(pool) < r.count:
            errors.append(f"{r.qtype} ID '{r.id}' mức '{r.muc_do or '*'}': cần {r.count}, kho chỉ có {len(pool)}")
            continue
        rng.shuffle(pool)
        if prefer_unused:
            counts = dict(bank.con.execute("SELECT id, used_count FROM questions").fetchall())
            pool.sort(key=lambda q: counts.get(q.db_id, 0))  # sort ổn định ⇒ vẫn ngẫu nhiên trong nhóm
        sel = pool[: r.count]
        used_ids.update(q.db_id for q in sel)
        chosen[r.qtype].extend(sel)
    if errors:
        raise NotEnoughQuestions("\n".join(errors))
    return chosen


def _split_itemch(solution: str):
    """Tách lời giải dạng itemchoice thành (đầu, [mục], cuối) để trộn theo ý."""
    b = solution.find("\\begin{itemchoice}")
    e = solution.rfind("\\end{itemchoice}")
    if b < 0 or e < 0:
        return None
    inner_start = b + len("\\begin{itemchoice}")
    inner = solution[inner_start:e]
    pos = [m.start() for m in ITEMCH_RE.finditer(inner)]
    if not pos:
        return None
    items = [inner[p: (pos[k + 1] if k + 1 < len(pos) else len(inner))] for k, p in enumerate(pos)]
    return solution[:inner_start] + inner[:pos[0]], items, solution[e:]


def shuffle_choices(q: Question, rng: random.Random) -> Question:
    q = copy.deepcopy(q)
    if q.qtype not in ("TN", "DS") or len(q.choices) < 2:
        return q
    if any(LOCK_RE.search(c) for c in q.choices):
        return q
    perm = list(range(len(q.choices)))
    rng.shuffle(perm)
    if q.qtype == "DS":
        parts = _split_itemch(q.solution)
        if parts is None or len(parts[1]) != len(q.choices):
            return q  # không trộn được lời giải tương ứng ⇒ giữ nguyên thứ tự ý
        head, items, tail = parts
        items = [items[i].strip() for i in perm]
        ind = "\n\t\t\t"
        q.solution = head.rstrip() + ind + ind.join(items) + "\n\t\t" + tail.lstrip()
    q.choices = [q.choices[i] for i in perm]
    q.correct = [q.correct[i] for i in perm]
    return q


def make_versions(bank: Bank, rules: list[Rule], n_versions: int = 4, *,
                  codes: list[str] | None = None, seed: int | None = None,
                  same_questions: bool = True, shuffle_q: bool = True,
                  shuffle_opts: bool = True, prefer_unused: bool = False) -> list[ExamVersion]:
    rng = random.Random(seed)
    if not codes:
        codes = [str(101 + i) for i in range(n_versions)]
    base = pick_questions(bank, rules, rng, prefer_unused) if same_questions else None
    versions = []
    for code in codes:
        picked = base if same_questions else pick_questions(bank, rules, rng, prefer_unused)
        v = ExamVersion(code)
        for s in SECTION_ORDER:
            qs = list(picked.get(s, []))
            if shuffle_q:
                rng.shuffle(qs)
            if shuffle_opts:
                qs = [shuffle_choices(q, rng) for q in qs]
            v.sections[s] = qs
        versions.append(v)
    return versions
