"""Giải mã ID câu hỏi kiểu [0D2N1-2] (ID6 phổ biến trong cộng đồng LaTeX Toán).

    vị trí 1: lớp      0 → 10, 1 → 11, 2 → 12 (6..9 → lớp 6..9)
    vị trí 2: phân môn  D = Đại số/Giải tích, H = Hình học
    vị trí 3: chương   0-9 hoặc A-Z
    vị trí 4: mức độ   N/Y = Nhận biết, H/B = Thông hiểu, V/K = Vận dụng, C/G = Vận dụng cao
    vị trí 5: bài
    sau '-' : dạng toán
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

ID_RE = re.compile(r"^([0-9])([A-Z])([0-9A-Z])([A-Z])([0-9A-Z])(?:-([0-9A-Z]+))?$")

LOP = {"0": "10", "1": "11", "2": "12", "6": "6", "7": "7", "8": "8", "9": "9"}
MON = {"D": "Đại số - Giải tích", "H": "Hình học"}
MUC_DO = {
    "N": "Nhận biết", "Y": "Nhận biết",
    "H": "Thông hiểu", "B": "Thông hiểu",
    "V": "Vận dụng", "K": "Vận dụng",
    "C": "Vận dụng cao", "G": "Vận dụng cao",
}
# Chuẩn hoá về 1 kí hiệu để lọc/thống kê
MUC_DO_CHUAN = {"N": "N", "Y": "N", "H": "H", "B": "H", "V": "V", "K": "V", "C": "C", "G": "C"}


@dataclass
class IDCode:
    raw: str
    lop: str
    mon: str
    chuong: str
    muc_do: str  # đã chuẩn hoá N/H/V/C
    bai: str
    dang: str

    def describe(self) -> str:
        return (f"Lớp {LOP.get(self.lop, self.lop)} – {MON.get(self.mon, self.mon)} – "
                f"Chương {self.chuong} – Bài {self.bai} – Dạng {self.dang or '?'} – "
                f"{MUC_DO.get(self.muc_do, self.muc_do)}")

    def to_dict(self):
        return asdict(self)


def parse_id(code: str) -> IDCode | None:
    code = code.strip().strip("[]").upper()
    m = ID_RE.match(code)
    if not m:
        return None
    lop, mon, chuong, md, bai, dang = m.groups()
    return IDCode(code, lop, mon, chuong, MUC_DO_CHUAN.get(md, md), bai, dang or "")
