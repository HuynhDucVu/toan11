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


def is_locked(q: Question) -> bool:
    return any(LOCK_RE.search(c) for c in q.choices)


def shuffle_choices(q: Question, rng: random.Random, target: int | None = None) -> Question:
    """Trộn phương án/ý. `target`: (chỉ TN) vị trí muốn đặt đáp án đúng – dùng để cân bằng A/B/C/D."""
    q = copy.deepcopy(q)
    if q.qtype not in ("TN", "DS") or len(q.choices) < 2 or is_locked(q):
        return q
    n = len(q.choices)
    perm = list(range(n))
    rng.shuffle(perm)
    if q.qtype == "TN" and target is not None and sum(q.correct) == 1 and target < n:
        right = q.correct.index(True)
        k = perm.index(right)
        perm[k], perm[target] = perm[target], perm[k]   # đưa đáp án đúng về vị trí target
    if q.qtype == "DS":
        parts = _split_itemch(q.solution)
        if parts is None or len(parts[1]) != n:
            return q  # không trộn được lời giải tương ứng ⇒ giữ nguyên thứ tự ý
        head, items, tail = parts
        items = [items[i].strip() for i in perm]
        ind = "\n\t\t\t"
        q.solution = head.rstrip() + ind + ind.join(items) + "\n\t\t" + tail.lstrip()
    if q.qtype == "TN" and n <= 4:
        # lời giải ghi «Chọn C» phải đổi theo vị trí mới của phương án
        from .review import _replace_chon_letters
        L = "ABCD"
        q.solution = _replace_chon_letters(q.solution, lambda old: L[perm.index(L.index(old))]
                                           if L.index(old) < n else old)
    q.choices = [q.choices[i] for i in perm]
    q.correct = [q.correct[i] for i in perm]
    return q


@dataclass
class MixOptions:
    """Tuỳ chọn trộn đề."""
    shuffle_q: bool = True          # trộn thứ tự câu trong từng phần
    shuffle_tn: bool = True         # trộn phương án câu trắc nghiệm
    shuffle_ds: bool = True         # trộn thứ tự ý câu đúng/sai
    balance: bool = True            # cân bằng số đáp án A/B/C/D trong mỗi đề
    first_original: bool = False    # mã đề đầu tiên giữ nguyên thứ tự gốc (đề gốc)


def _mix_section(qs: list[Question], rng: random.Random, opt: MixOptions, keep_order: bool) -> list[Question]:
    qs = list(qs)
    if opt.shuffle_q and not keep_order:
        rng.shuffle(qs)
    if keep_order:
        return [copy.deepcopy(q) for q in qs]
    # vị trí đích cho đáp án TN: lặp A,B,C,D rồi xáo ⇒ các chữ cái gần như đều nhau
    free = [q for q in qs if q.qtype == "TN" and len(q.choices) == 4 and not is_locked(q)]
    targets = []
    if opt.balance and opt.shuffle_tn:
        targets = [i % 4 for i in range(len(free))]
        rng.shuffle(targets)
    out, k = [], 0
    for q in qs:
        if q.qtype == "TN":
            if not opt.shuffle_tn:
                out.append(copy.deepcopy(q))
                continue
            t = None
            if targets and q in free:
                t = targets[k]
                k += 1
            out.append(shuffle_choices(q, rng, t))
        elif q.qtype == "DS" and opt.shuffle_ds:
            out.append(shuffle_choices(q, rng))
        else:
            out.append(copy.deepcopy(q))
    return out


def mix_versions(sections: dict[str, list[Question]], codes: list[str], rng: random.Random,
                 opt: MixOptions | None = None) -> list[ExamVersion]:
    """Trộn một bộ câu đã chọn thành nhiều mã đề."""
    opt = opt or MixOptions()
    out = []
    for i, code in enumerate(codes):
        v = ExamVersion(code)
        keep = opt.first_original and i == 0
        for s in SECTION_ORDER:
            v.sections[s] = _mix_section(sections.get(s, []), rng, opt, keep)
        out.append(v)
    return out


def make_versions(bank: Bank, rules: list[Rule], n_versions: int = 4, *,
                  codes: list[str] | None = None, seed: int | None = None,
                  same_questions: bool = True, shuffle_q: bool = True,
                  shuffle_opts: bool = True, prefer_unused: bool = False,
                  options: MixOptions | None = None) -> list[ExamVersion]:
    rng = random.Random(seed)
    if not codes:
        codes = [str(101 + i) for i in range(n_versions)]
    opt = options or MixOptions(shuffle_q=shuffle_q, shuffle_tn=shuffle_opts, shuffle_ds=shuffle_opts)
    if same_questions:
        return mix_versions(pick_questions(bank, rules, rng, prefer_unused), codes, rng, opt)
    out = []
    for code in codes:
        out += mix_versions(pick_questions(bank, rules, rng, prefer_unused), [code], rng, opt)
    return out


def sections_from_questions(qs: list[Question]) -> dict[str, list[Question]]:
    """Gom các câu (vd đọc từ 1 file đề) theo phần TN/DS/KQ/TL, giữ thứ tự trong file."""
    out = {s: [] for s in SECTION_ORDER}
    for q in qs:
        out[q.qtype].append(q)
    return out


# ---------------------------------------------------------------- báo cáo
def answer_distribution(v: ExamVersion) -> dict[str, int]:
    """Số câu TN có đáp án A/B/C/D trong một mã đề."""
    d = {c: 0 for c in "ABCD"}
    for q in v.sections.get("TN", []):
        a = q.answer_text
        if a in d:
            d[a] += 1
    return d


def overlap_report(versions: list[ExamVersion]):
    """Tỉ lệ câu trùng giữa từng cặp mã đề (theo nội dung câu)."""
    sets = [{q.fingerprint for q in v.all_questions()} for v in versions]
    out = []
    for i in range(len(versions)):
        for j in range(i + 1, len(versions)):
            n = max(len(sets[i]), 1)
            out.append((versions[i].code, versions[j].code, len(sets[i] & sets[j]) / n))
    return out


def matrix_from_questions(qs: list[Question], level: str = "bai") -> list[Rule]:
    """Lập ma trận từ một đề có sẵn: đếm số câu theo (loại, ID ở mức `level`, mức độ).

    level: 'dang' (đúng dạng), 'bai' (cùng bài), 'chuong' (cùng chương).
    """
    from collections import OrderedDict
    from .idcode import parse_id
    cnt: OrderedDict = OrderedDict()
    for q in qs:
        idc = parse_id(q.id_code) if q.id_code else None
        if not idc:
            key = (q.qtype, "*", None)
        else:
            base = idc.lop + idc.mon + idc.chuong
            if level == "chuong":
                pat = base + "*"
            elif level == "bai":
                pat = base + "?" + idc.bai + "*"
            else:
                pat = base + "?" + idc.bai + ("-" + idc.dang if idc.dang else "*")
            key = (q.qtype, pat, idc.muc_do)
        cnt[key] = cnt.get(key, 0) + 1
    rules = [Rule(t, n, pat, md) for (t, pat, md), n in cnt.items()]
    order = {s: i for i, s in enumerate(SECTION_ORDER)}
    return sorted(rules, key=lambda r: order[r.qtype])
