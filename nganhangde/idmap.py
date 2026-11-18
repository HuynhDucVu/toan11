"""Đọc/ghi bảng giải nghĩa ID (Map ID).

Hỗ trợ 2 định dạng:

1. Định dạng phân cấp bằng gạch ngang (file Map_ID.tex dùng chung trong cộng đồng LaTeX):

        -[0] Lớp 10
        ----[D] Đại số/Thống kê 10
        -------[1] Mệnh đề. Tập hợp
        ----------[1] Mệnh đề
        -------------[1] Xác định mệnh đề, mệnh đề chứa biến

   1 gạch = lớp, 4 = môn, 7 = chương, 10 = bài, 13 = dạng. Dòng bắt đầu bằng % là chú thích;
   dòng không có gạch như «[N] Nhận biết» là tên mức độ.

2. Định dạng phẳng «khoá = tên»:

        0D2      = Chương 2. Bất phương trình bậc hai
        0D21     = Bài 1. Dấu của tam thức bậc hai
        0D21-2   = Dạng 2. Giải bất phương trình bậc hai

Khoá nội bộ (bỏ kí tự mức độ): lớp | lớp+môn | +chương | +bài | +bài-dạng, vd '0', '0D', '0D1', '0D11', '0D11-1'.
Tên mức độ lưu với khoá '#N', '#H', ...
"""
from __future__ import annotations

import re

LINE_RE = re.compile(r"^\s*\[?([0-9][0-9A-Za-z]{0,3}(?:-[0-9A-Za-z]+)?)\]?\s*(?:=|:|\t|\s)\s*(.+?)\s*$")
DASH_RE = re.compile(r"^(-*)\[([^\]]+)\]\s*(.*?)\s*$")
DASH_LEVEL = {1: 0, 4: 1, 7: 2, 10: 3, 13: 4}     # số gạch → cấp (lớp, môn, chương, bài, dạng)


def _key(parts: list[str]) -> str:
    k = "".join(parts[:4])
    return k + ("-" + parts[4] if len(parts) > 4 else "")


def parse_dash_text(text: str) -> dict[str, str]:
    out, cur = {}, []
    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith("%"):
            continue
        m = DASH_RE.match(line)
        if not m:
            continue
        dashes, code, name = len(m.group(1)), m.group(2).strip().upper(), m.group(3)
        if dashes == 0:                       # [N] Nhận biết – tên mức độ
            out["#" + code] = name
            continue
        level = DASH_LEVEL.get(dashes)
        if level is None or level > len(cur):
            continue                          # sai cấu trúc ⇒ bỏ qua dòng
        cur = cur[:level] + [code]
        out.setdefault(_key(cur), name)      # mã trùng: giữ mục xuất hiện trước
    return out


def dash_duplicates(text: str) -> list[tuple[str, str, str]]:
    """Các khoá bị khai báo trùng trong file Map ID: [(khoá, tên_trước, tên_sau)]."""
    seen, dups, cur = {}, [], []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("%"):
            continue
        m = DASH_RE.match(line.rstrip())
        if not m or not m.group(1):
            continue
        level = DASH_LEVEL.get(len(m.group(1)))
        if level is None or level > len(cur):
            continue
        cur = cur[:level] + [m.group(2).strip().upper()]
        k = _key(cur)
        if k in seen:
            dups.append((k, seen[k], m.group(3)))
        else:
            seen[k] = m.group(3)
    return dups


def is_dash_format(text: str) -> bool:
    return bool(re.search(r"^-{1,13}\[[^\]]+\]", text, re.M))


def parse_map_text(text: str) -> dict[str, str]:
    if is_dash_format(text):
        return parse_dash_text(text)
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "%")):
            continue
        m = LINE_RE.match(line)
        if m:
            out[m.group(1).upper()] = m.group(2)
    return out


def load_map(path: str) -> dict[str, str]:
    with open(path, encoding="utf-8-sig") as f:
        return parse_map_text(f.read())


def split_key(k: str) -> list[str]:
    """'0D11-3' → ['0','D','1','1','3']"""
    base, _, dang = k.partition("-")
    return list(base) + ([dang] if dang else [])


def to_dash_text(mapping: dict[str, str]) -> str:
    lines = ["%", "%Map ID – xuất từ phần mềm Ngân hàng đề thi", "%",
             "Tên tham số 1: Lớp", "Tên tham số 2: Môn", "Tên tham số 3: Chương",
             "Tên tham số 4: Mức độ", "Tên tham số 5: Bài", "Tên tham số 6: Dạng", "%"]
    for k in ("#N", "#H", "#V", "#C"):
        if k in mapping:
            lines.append(f"[{k[1:]}] {mapping[k]}")
    lines.append("%")
    keys = [k for k in mapping if not k.startswith("#")]
    for k in sorted(keys, key=lambda k: split_key(k)):
        parts = split_key(k)
        dashes = {v: d for d, v in DASH_LEVEL.items()}[len(parts) - 1]
        lines.append("-" * dashes + f"[{parts[-1]}] {mapping[k]}")
    return "\n".join(lines) + "\n"


def save_map(mapping: dict[str, str], path: str):
    with open(path, "w", encoding="utf-8") as f:
        if path.lower().endswith(".tex"):
            f.write(to_dash_text(mapping))
            return
        f.write("# Giải nghĩa ID – mỗi dòng: khoá = tên\n")
        for k in sorted(mapping):
            f.write(f"{k:<10}= {mapping[k]}\n")


class IdTree:
    """Cây chọn ID cho giao diện: children(prefix_parts) → [(mã, tên)]."""

    def __init__(self, mapping: dict[str, str]):
        self.m = mapping
        self.kids: dict[tuple, list[tuple[str, str]]] = {}
        for k, name in mapping.items():
            if k.startswith("#"):
                continue
            parts = split_key(k)
            self.kids.setdefault(tuple(parts[:-1]), []).append((parts[-1], name))
        for v in self.kids.values():
            v.sort(key=lambda x: (len(x[0]), x[0]))

    def children(self, parts) -> list[tuple[str, str]]:
        return self.kids.get(tuple(parts), [])

    def name(self, parts) -> str:
        return self.m.get(_key(list(parts)), "")
