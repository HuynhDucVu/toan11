"""Nhập câu hỏi 3 bước: ① Rà soát → ② AI giải lại (tuỳ chọn) → ③ Nhập vào kho (theo bản Gemini v4.6)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import review as rv
from .parser import Question, parse_file


@dataclass
class ImportOptions:
    need_solution: bool = False      # bắt buộc có lời giải và đáp án
    skip_dups: bool = True           # bỏ qua câu đã có trong kho
    deep_dups: bool = False          # kiểm tra trùng sâu (gần giống ≥ 85%) với kho và trong lô
    no_id5: bool = False             # không nhập câu có ID 5 ký tự (chưa phân dạng)
    skip_errors: bool = False        # bỏ qua câu có lỗi nặng khi rà soát
    ratio: float = 0.85              # ngưỡng «gần giống» khi kiểm tra trùng sâu


@dataclass
class Entry:
    q: Question
    source: str = ""
    issues: list = field(default_factory=list)
    skip: str = ""                   # lý do bỏ qua ("" = sẽ nhập)
    ai_changed: bool = False


def load(paths: list[str]) -> list[Entry]:
    out = []
    for p in paths:
        for q in parse_file(p):
            out.append(Entry(q, p))
    return out


def review(entries: list[Entry], bank, opt: ImportOptions) -> None:
    """Rà soát từng câu và gán lý do bỏ qua theo tuỳ chọn."""
    seen: dict = {}
    for e in entries:
        e.issues = rv.review_question(e.q, os.path.dirname(e.source) or None)
        e.skip = ""
        q = e.q
        if opt.need_solution and (not q.solution.strip() or (q.qtype != "TL" and not q.answer_text)):
            e.skip = "thiếu lời giải hoặc đáp án"
        elif opt.no_id5 and len((q.id_code or "").strip()) == 5 and "-" not in q.id_code:
            e.skip = "ID 5 ký tự"
        elif opt.skip_errors and any(i.level == rv.LOI for i in e.issues):
            e.skip = "có lỗi khi rà soát"
        elif opt.skip_dups and (q.fingerprint in seen or bank.find_duplicate(q)):
            e.skip = "trùng trong kho/lô"
        seen.setdefault(q.fingerprint, 1)
    if opt.deep_dups:
        from .tools import near_duplicates
        live = [e for e in entries if not e.skip]
        for i, j, _ in near_duplicates([e.q for e in live], opt.ratio):
            if not live[j].skip:
                live[j].skip = f"gần giống câu #{entries.index(live[i]) + 1}"
        stored = bank.search()
        if stored:
            allq = stored + [e.q for e in live if not e.skip]
            n0 = len(stored)
            todo = [e for e in live if not e.skip]
            for i, j, _ in near_duplicates(allq, opt.ratio):
                if i < n0 <= j and not todo[j - n0].skip:
                    todo[j - n0].skip = "gần giống câu trong kho"


def ai_resolve(client, entries: list[Entry], only_flagged: bool = True, *, progress=None, should_stop=None) -> int:
    """Bước 2: AI giải lại các câu có vấn đề (hoặc thiếu lời giải); chỉ cập nhật lời giải, không tự đổi đáp án."""
    from . import aitasks
    todo = [e for e in entries if not e.skip and (not only_flagged or e.issues or not e.q.solution.strip())]
    n = 0
    for k, e in enumerate(todo):
        if should_stop and should_stop():
            break
        if progress:
            progress(k, len(todo))
        p = aitasks.make_solution(client, e.q, overwrite=bool(e.issues) or not e.q.solution.strip())
        e.q, e.issues, e.ai_changed = p.question, p.issues, True
        n += 1
    return n


def commit(entries: list[Entry], bank) -> dict:
    from collections import Counter
    added = skipped = dup = 0
    by_type = Counter()
    for e in entries:
        if e.skip:
            skipped += 1
        elif bank.add(e.q, e.source):
            added += 1
            by_type[e.q.qtype] += 1
        else:
            dup += 1
    return {"added": added, "skipped": skipped, "dup": dup, "by_type": by_type}


def export_fixed(entries: list[Entry], path: str) -> int:
    """Xuất các câu sẽ nhập (đã qua AI/sửa) ra một file .tex."""
    qs = [e.q for e in entries if not e.skip]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(q.to_latex(True) for q in qs) + "\n")
    return len(qs)
