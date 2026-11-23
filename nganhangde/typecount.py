"""Thống kê số câu theo loại (TN, ĐS, TLN, TL) sau mỗi lần nhập – dùng chung cho mọi lệnh nhập."""
from __future__ import annotations

from collections import Counter

ORDER = (("TN", "TN"), ("DS", "ĐS"), ("KQ", "TLN"), ("TL", "TL"))   # mã trong kho → nhãn hiển thị


def count_types(qs) -> Counter:
    """Đếm theo loại cho danh sách câu (Question) hoặc bộ lặp các loại."""
    c = Counter()
    for q in qs:
        c[getattr(q, "qtype", q)] += 1
    return c


def fmt(counts) -> str:
    """«TN: 12 · ĐS: 3 · TLN: 6 · TL: 1 · tổng 22» (luôn đủ 4 loại để thấy loại nào bằng 0)."""
    parts = [f"{label}: {counts.get(code, 0):,}" for code, label in ORDER]
    total = sum(counts.get(code, 0) for code, _ in ORDER) + sum(
        v for k, v in counts.items() if k not in dict(ORDER))
    return " · ".join(parts) + f" · tổng {total:,}"


def bank_counts(bank) -> Counter:
    """Số câu hiện có trong kho theo loại."""
    return Counter({r[0]: r[1] for r in bank.con.execute("SELECT qtype, COUNT(*) FROM questions GROUP BY qtype")})
