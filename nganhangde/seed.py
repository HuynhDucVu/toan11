"""Nạp ngân hàng mẫu để dùng thử khi chưa có dữ liệu: đề mẫu Toán 10 (22 câu có ID, đáp án, lời giải) và các câu
đổi số tự động hàm số Toán 12 (autogen). Câu trùng tự bỏ qua nên nạp nhiều lần cũng không bị nhân đôi."""
from __future__ import annotations

import os

from . import autogen
from .parser import parse_file, parse_tex

PKG = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(PKG, "data", "de_mau_toan10.tex")


def seed_bank(bank, per_type: int = 8) -> dict:
    """Trả về {'de_mau': số câu thêm từ đề mẫu, 'doi_so': số câu đổi số thêm, 'trung': số câu trùng bỏ qua}."""
    res = {"de_mau": 0, "doi_so": 0, "trung": 0}
    if os.path.isfile(SAMPLE):
        for q in parse_file(SAMPLE):
            if bank.add(q, "de_mau_toan10.tex") is None:
                res["trung"] += 1
            else:
                res["de_mau"] += 1
    for kind in autogen.PROBLEMS:
        for blk in autogen.generate(kind, per_type, seed=2026):
            for q in parse_tex(blk):
                if bank.add(q, "cau_doi_so_tu_dong") is None:
                    res["trung"] += 1
                else:
                    res["doi_so"] += 1
    return res
