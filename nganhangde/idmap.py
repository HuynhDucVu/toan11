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

import os
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


# ---------------------------------------------------------------- danh mục đi kèm phần mềm
BUILTIN_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "map_id_toan_6_12.tex")


def builtin_map() -> dict[str, str]:
    """Danh mục ID6 Toán 6–12 (GDPT 2018) đi kèm phần mềm – lấy từ file Map ID do giáo viên cung cấp."""
    return load_map(BUILTIN_MAP) if os.path.exists(BUILTIN_MAP) else {}


def to_html(mapping: dict[str, str], title: str = "Tra cứu mã ID") -> str:
    """Trang HTML tự chứa để tra cứu mã ID: gõ không dấu vẫn tìm được, bấm vào mã để chép."""
    import html as _h
    import json as _j
    from .textnorm import search_text
    rows = []
    for k in sorted((k for k in mapping if not k.startswith("#")), key=split_key):
        parts = split_key(k)
        path = " › ".join(x for x in (mapping.get("".join(parts[:n]), "") for n in range(1, len(parts) + 1)
                                      if n <= 4) if x)
        if "-" in k:
            path += " › " + mapping[k]
        level = len(parts) - 1
        rows.append([k, path, level, search_text(k + " " + path)])
    data = _j.dumps(rows, ensure_ascii=False)
    lv = " · ".join(f"<b>{k[1:]}</b> = {_h.escape(v)}" for k, v in mapping.items() if k.startswith("#"))
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_h.escape(title)}</title>
<style>body{{font:15px system-ui,sans-serif;margin:0;background:#f5f7fa}}header{{background:#1f4e79;color:#fff;padding:12px 16px;position:sticky;top:0}}
input{{font-size:16px;padding:8px;width:min(560px,100%);border-radius:6px;border:0}}main{{padding:8px 16px}}
.r{{padding:6px 8px;border-bottom:1px solid #e3e8ef;background:#fff;cursor:pointer}}.r:hover{{background:#eef3f8}}
.k{{font-family:Consolas,monospace;font-weight:700;color:#1f4e79;display:inline-block;min-width:90px}}.l0{{font-weight:700}}
#n{{color:#555;margin:6px 0}}</style></head><body><header><div style="font-weight:700;margin-bottom:6px">{_h.escape(title)}</div>
<input id="q" placeholder="Gõ mã hoặc tên (không dấu cũng được), vd: duong tron, 0H94" autofocus>
<div style="font-size:13px;margin-top:6px">Mức độ: {lv or "N/H/V/C"} – chèn vào vị trí thứ 4 của ID, vd 0H9<b>N</b>4-1. Bấm một dòng để chép mã.</div></header>
<main><div id="n"></div><div id="list"></div></main>
<script>const D={data};
function bo(s){{return s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').replace(/đ/g,'d').replace(/Đ/g,'D').toLowerCase()}}
function show(){{const t=bo(document.getElementById('q').value).split(/\\s+/).filter(Boolean);
const r=D.filter(x=>t.every(w=>x[3].includes(w))).slice(0,400);
document.getElementById('n').textContent=r.length+' kết quả'+(r.length==400?' (hiện 400 dòng đầu)':'');
document.getElementById('list').innerHTML=r.map(x=>`<div class="r l${{x[2]}}" style="padding-left:${{8+x[2]*16}}px" onclick="navigator.clipboard&&navigator.clipboard.writeText('${{x[0]}}')"><span class="k">${{x[0]}}</span> ${{x[1].replace(/</g,'&lt;')}}</div>`).join('')}}
document.getElementById('q').addEventListener('input',show);show();</script></body></html>"""


def map_files() -> list[str]:
    """Các file Map ID dạng .tex: trong thư mục «Map ID (DPS)» (cũ → mới theo ngày sửa, file mới đè file cũ)."""
    import glob
    from .appdirs import folder
    fs = glob.glob(os.path.join(folder("map_id"), "*.tex"))
    return sorted(fs, key=lambda p: os.path.getmtime(p))


def bundled_map() -> dict[str, str]:
    """Map ID đi kèm phần mềm (Map_ID_Moi.tex) – dùng khi chưa nạp Map ID nào."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "Map_ID_Moi.tex")
    try:
        return load_map(p)
    except OSError:
        return {}


def load_folder_maps() -> tuple[dict[str, str], list[str]]:
    """Gộp mọi file Map ID trong thư mục (file mới đè file cũ). Trả về (bảng, danh sách file đã đọc)."""
    out, used = {}, []
    for p in map_files():
        try:
            m = load_map(p)
        except (OSError, UnicodeError):
            continue
        if m:
            out.update(m)
            used.append(os.path.basename(p))
    return out, used
