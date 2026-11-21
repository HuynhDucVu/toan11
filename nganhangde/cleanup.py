"""Dọn kho: lọc câu trùng (giống hệt sau chuẩn hoá và gần giống) và câu sai (lỗi khi rà soát).
Kho lớn (hàng trăm nghìn câu) vẫn chạy được: chỉ so gần giống trong từng nhóm cùng ID5 (vd 0D2N1)."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from . import review as rv
from .parser import Question


@dataclass
class ScanResult:
    total: int = 0
    wrong: dict = field(default_factory=dict)         # id → [lí do]
    dup_exact: dict = field(default_factory=dict)     # id bị xoá → id được giữ
    dup_near: dict = field(default_factory=dict)      # id bị xoá → (id được giữ, độ giống)

    def delete_ids(self, wrong=True, exact=True, near=False) -> list[int]:
        ids = set()
        if wrong:
            ids |= set(self.wrong)
        if exact:
            ids |= set(self.dup_exact)
        if near:
            ids |= set(self.dup_near)
        return sorted(ids)


def _body_key(q: Question) -> str:
    """Khoá nội dung: bỏ lệnh định dạng, khoảng trắng, dấu $ {} – giống hệt sau chuẩn hoá thì coi là một câu."""
    body = q.stem + "||" + "||".join(sorted(q.choices)) + "||" + (q.short_answer or "")
    body = re.sub(r"\\(left|right|displaystyle|dfrac|tfrac|textbf|textit|mathrm)(?![A-Za-z])", "", body)
    body = re.sub(r"%.*", "", body)
    return re.sub(r"[\s{}$.,;:]", "", body).lower()


def quality(q: Question) -> tuple:
    """Điểm giữ lại khi trùng: có lời giải, có ID đầy đủ (6 ký tự có gạch), nhiều nội dung hơn, id nhỏ hơn."""
    idc = q.id_code or ""
    return (bool(q.solution.strip()), "-" in idc, len(idc) >= 5, len(q.solution), -(q.db_id or 0))


def is_wrong(q: Question) -> list[str]:
    """Lí do câu bị coi là sai (rỗng = ổn): lỗi mức «Lỗi» khi rà soát, hoặc đề trống."""
    if not q.stem.strip() and not q.choices:
        return ["Câu trống"]
    return [i.msg for i in rv.review_question(q) if i.level == rv.LOI]


def scan(bank, *, find_wrong=True, find_exact=True, find_near=False, threshold=0.9,
         progress=None, should_stop=None) -> ScanResult:
    res = ScanResult()
    qs = bank.search()
    res.total = len(qs)
    stop = should_stop or (lambda: False)
    if find_wrong:
        for k, q in enumerate(qs):
            if k % 2000 == 0:
                if progress:
                    progress(k, len(qs))
                if stop():
                    return res
            why = is_wrong(q)
            if why:
                res.wrong[q.db_id] = why[:3]
    bad = set(res.wrong)
    if find_exact:
        groups = defaultdict(list)
        for q in qs:
            if q.db_id not in bad:
                groups[_body_key(q)].append(q)
        for g in groups.values():
            if len(g) > 1:
                g.sort(key=quality, reverse=True)
                for q in g[1:]:
                    res.dup_exact[q.db_id] = g[0].db_id
    if find_near:
        from .tools import near_duplicates
        gone = bad | set(res.dup_exact)
        blocks = defaultdict(list)
        for q in qs:
            if q.db_id not in gone:
                blocks[(q.qtype, (q.id_code or "")[:5])].append(q)
        todo = [b for b in blocks.values() if len(b) > 1]
        for k, b in enumerate(todo):
            if progress:
                progress(k, len(todo))
            if stop():
                break
            for i, j, sc in near_duplicates(b, threshold):
                a, c = b[i], b[j]
                keep, drop = (a, c) if quality(a) >= quality(c) else (c, a)
                if drop.db_id not in res.dup_near and keep.db_id not in res.dup_near:
                    res.dup_near[drop.db_id] = (keep.db_id, sc)
    return res


def apply(bank, ids: list[int]) -> int:
    """Xoá (có ghi lịch sử – khôi phục được ở Câu hỏi → Khôi phục câu đã xoá)."""
    for k in range(0, len(ids), 5000):
        bank.delete(ids[k:k + 5000])
    return len(ids)
