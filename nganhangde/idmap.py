"""Đọc/ghi file giải nghĩa ID (MapID).

Định dạng file .txt, mỗi dòng một mục (dòng bắt đầu bằng # là chú thích):

    0D2      = Chương 2. Bất phương trình bậc hai một ẩn
    0D21     = Bài 1. Dấu của tam thức bậc hai
    0D21-2   = Dạng 2. Giải bất phương trình bậc hai

Khoá là các phần của ID bỏ kí tự mức độ: lớp, lớp+môn, +chương, +bài, +"-dạng".
Chấp nhận cả dấu phân cách '=', ':', tab, hoặc dạng '[0D2] Tên'.
"""
from __future__ import annotations

import re

LINE_RE = re.compile(r"^\s*\[?([0-9][0-9A-Za-z]{0,3}(?:-[0-9A-Za-z]+)?)\]?\s*(?:=|:|\t|\s)\s*(.+?)\s*$")


def parse_map_text(text: str) -> dict[str, str]:
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


def save_map(mapping: dict[str, str], path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Giải nghĩa ID – mỗi dòng: khoá = tên\n")
        for k in sorted(mapping):
            f.write(f"{k:<10}= {mapping[k]}\n")
