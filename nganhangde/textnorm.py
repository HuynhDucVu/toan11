"""Chuẩn hoá văn bản để tìm kiếm: bỏ dấu tiếng Việt, chữ thường, chuẩn hoá vài lệnh LaTeX.

«Bất phương trình $\\dfrac{1}{x}$» → «bat phuong trinh frac 1 x»
"""
from __future__ import annotations

import re
import unicodedata


def unaccent(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


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
