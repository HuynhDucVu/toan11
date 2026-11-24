"""Bộ đọc/nạp động tệp Map ID chuẩn định dạng MyLT (4 mức N/H/V/C và 5 mức Y/B/K/G/T, 3 bộ sách C/T/K)."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from .idcode import parse_id


@dataclass
class MapIDTree:
    name: str
    levels: dict[str, str] = field(default_factory=dict)
    grades: dict[str, str] = field(default_factory=dict)
    subjects: dict[tuple[str, str], str] = field(default_factory=dict)
    chapters: dict[tuple[str, str, str], str] = field(default_factory=dict)
    lessons: dict[tuple[str, str, str, str], str] = field(default_factory=dict)
    forms: dict[tuple[str, str, str, str, str], str] = field(default_factory=dict)

    def describe(self, code: str) -> str:
        info = parse_id(code, math_mode=False)
        if not info:
            return f"Mã không chuẩn: {code}"
        parts: list[str] = []
        g_name = self.grades.get(info.lop, f"Lớp {info.lop}")
        parts.append(g_name)
        s_name = self.subjects.get((info.lop, info.mon))
        if s_name:
            parts.append(s_name)
        c_name = self.chapters.get((info.lop, info.mon, info.chuong))
        if c_name:
            parts.append(c_name)
        if info.bai:
            l_name = self.lessons.get((info.lop, info.mon, info.chuong, info.bai))
            if l_name:
                parts.append(l_name)
        if info.dang:
            f_name = self.forms.get((info.lop, info.mon, info.chuong, info.bai, info.dang))
            if f_name:
                parts.append(f_name)
        lv_name = self.levels.get(info.raw[3], info.muc_do) if len(info.raw) >= 4 else info.muc_do
        parts.append(f"Mức: {lv_name}")
        return " · ".join(parts)


_LV_RE = re.compile(r"^\[([A-Za-z0-9])\]\s*(.+)$")
_NODE_RE = re.compile(r"^(-+)\[([A-Za-z0-9])\]\s*(.+)$")


def load_map_id_file(path: str | Path) -> MapIDTree:
    p = Path(path)
    tree = MapIDTree(name=p.stem)
    cur_g = cur_s = cur_c = cur_l = ""
    for raw_line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%") or line.startswith("Tên tham số"):
            continue
        m_lv = _LV_RE.match(line)
        if m_lv:
            tree.levels[m_lv.group(1)] = m_lv.group(2).strip()
            continue
        m_nd = _NODE_RE.match(line)
        if not m_nd:
            continue
        dashes, key, label = len(m_nd.group(1)), m_nd.group(2), m_nd.group(3).strip()
        if dashes == 1:
            cur_g = key
            tree.grades[cur_g] = label
            cur_s = cur_c = cur_l = ""
        elif dashes == 4:
            cur_s = key
            tree.subjects[(cur_g, cur_s)] = label
            cur_c = cur_l = ""
        elif dashes == 7:
            cur_c = key
            tree.chapters[(cur_g, cur_s, cur_c)] = label
            cur_l = ""
        elif dashes == 10:
            cur_l = key
            tree.lessons[(cur_g, cur_s, cur_c, cur_l)] = label
        elif dashes >= 13:
            tree.forms[(cur_g, cur_s, cur_c, cur_l, key)] = label
    return tree
