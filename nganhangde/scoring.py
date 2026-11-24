"""Thang điểm tuỳ chỉnh.

Mặc định theo quy chế thi tốt nghiệp THPT từ 2025 (môn Toán):
Phần I 0,25 điểm/câu; Phần II đúng 1/2/3/4 ý được 0,1/0,25/0,5/1 điểm; Phần III 0,5 điểm/câu.
Giáo viên đổi được cho bài kiểm tra ở trường (vd Phần III 0,25; tự luận 1 – 1 – 0,5 điểm).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def num(s) -> float:
    """'0,25' / '0.25' / 0.25 → 0.25."""
    if isinstance(s, (int, float)):
        return float(s)
    return float(str(s).strip().replace(",", "."))


def nums(s) -> list[float]:
    """'0,1; 0,25; 0,5; 1' → [0.1, 0.25, 0.5, 1.0]. Phân cách bằng ; hoặc khoảng trắng hoặc '/'."""
    if isinstance(s, (list, tuple)):
        return [num(x) for x in s]
    return [num(x) for x in re.split(r"[;/\s]+", str(s).strip()) if x]


def vn(x: float) -> str:
    return f"{x:g}".replace(".", ",")


@dataclass
class Scoring:
    tn: float = 0.25
    kq: float = 0.5
    ds: list[float] = field(default_factory=lambda: [0.1, 0.25, 0.5, 1.0])   # đúng 1, 2, 3, 4 ý
    tl: list[float] = field(default_factory=list)                            # điểm từng câu tự luận
    tl_default: float = 1.0

    @classmethod
    def from_dict(cls, d: dict | None) -> "Scoring":
        d = d or {}
        sc = cls()
        if "tn" in d:
            sc.tn = num(d["tn"])
        if "kq" in d:
            sc.kq = num(d["kq"])
        if d.get("ds") not in (None, ""):
            v = nums(d["ds"])
            if len(v) != 4:
                raise ValueError("Thang Phần II cần đúng 4 số (đúng 1, 2, 3, 4 ý)")
            sc.ds = v
        if d.get("tl") not in (None, ""):
            sc.tl = nums(d["tl"])
        if "tl_default" in d:
            sc.tl_default = num(d["tl_default"])
        return sc

    def to_dict(self) -> dict:
        return {"tn": self.tn, "kq": self.kq, "ds": list(self.ds), "tl": list(self.tl), "tl_default": self.tl_default}

    def ds_score(self, n_correct: int) -> float:
        return self.ds[n_correct - 1] if 1 <= n_correct <= 4 else 0.0

    def tl_points(self, n: int) -> list[float]:
        return [self.tl[i] if i < len(self.tl) else self.tl_default for i in range(n)]

    def max_points(self, n: dict) -> float:
        return (n.get("TN", 0) * self.tn + n.get("DS", 0) * self.ds[3] + n.get("KQ", 0) * self.kq
                + sum(self.tl_points(n.get("TL", 0))))

    def ds_text(self) -> str:
        return "/".join(vn(x) for x in self.ds)

    def lines(self, n: dict) -> list[str]:
        rows = []
        if n.get("TN"):
            rows.append(f"Phần I: mỗi câu đúng {vn(self.tn)} điểm ({n['TN']} câu, tối đa {vn(n['TN'] * self.tn)} điểm).")
        if n.get("DS"):
            d = self.ds
            rows.append(f"Phần II: mỗi câu đúng 1 ý được {vn(d[0])}; 2 ý được {vn(d[1])}; 3 ý được {vn(d[2])}; "
                        f"cả 4 ý được {vn(d[3])} điểm ({n['DS']} câu, tối đa {vn(n['DS'] * d[3])} điểm).")
        if n.get("KQ"):
            rows.append(f"Phần III: mỗi câu đúng {vn(self.kq)} điểm ({n['KQ']} câu, tối đa {vn(n['KQ'] * self.kq)} điểm).")
        if n.get("TL"):
            p = self.tl_points(n["TL"])
            rows.append("Phần IV (tự luận): " + "; ".join(f"câu {i} – {vn(x)} điểm" for i, x in enumerate(p, 1))
                        + f" (tối đa {vn(sum(p))} điểm).")
        rows.append(f"Tổng điểm toàn bài: {vn(self.max_points(n))} điểm.")
        return rows

    def js(self) -> str:
        """Đối tượng S cho bài làm online."""
        import json
        return json.dumps({"TN": self.tn, "KQ": self.kq,
                           "DS": {0: 0, 1: self.ds[0], 2: self.ds[1], 3: self.ds[2], 4: self.ds[3]}})


DEFAULT = Scoring()
