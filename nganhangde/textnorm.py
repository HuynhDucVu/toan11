"""Chuẩn hoá văn bản để tìm kiếm: bỏ dấu tiếng Việt, chữ thường, chuẩn hoá vài lệnh LaTeX.

«Bất phương trình $\\dfrac{1}{x}$» → «bat phuong trinh frac 1 x»
"""
from __future__ import annotations

import re
import unicodedata


_BASE: dict[int, str] = {}          # mã ký tự → chữ gốc không dấu (đệm: mỗi ký tự chỉ tính một lần)


def unaccent(s: str) -> str:
    if s.isascii():                 # phần lớn đề toán là ASCII: không cần làm gì
        return s
    s = s.replace("đ", "d").replace("Đ", "D")
    for c in set(s):
        if ord(c) > 127 and ord(c) not in _BASE:
            _BASE[ord(c)] = "".join(x for x in unicodedata.normalize("NFD", c) if unicodedata.category(x) != "Mn")
    return s.translate(_BASE)


def search_text(*parts: str) -> str:
    s = " ".join(p for p in parts if p)
    s = re.sub(r"\\[dt]frac", "frac", s)
    s = re.sub(r"\\(left|right|displaystyle|mathrm|text|textbf|textit)\b", " ", s)
    s = unaccent(s).lower()
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return " ".join(s.split())


def fts_query(text: str) -> str:
    """Câu truy vấn FTS5: mỗi từ (đã bỏ dấu) là một tiền tố bắt buộc, vd «tap nghiem» → "tap"* "nghiem"*."""
    toks = search_text(text).split()
    return " ".join(f'"{t}"*' for t in toks)
