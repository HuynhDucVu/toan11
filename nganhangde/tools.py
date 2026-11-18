"""Các công cụ xử lí file .tex không cần kho dữ liệu.

    find_duplicates  – tìm câu trùng trong một hoặc nhiều file
    filter_by_id     – lọc các câu có ID khớp mẫu ra file mới
    erase_solutions  – xoá lời giải \\loigiai{...} (giữ nguyên phần còn lại)
    convert_ids      – đổi tiền tố ID theo bảng ánh xạ (vd 0D2 → 0D3)
    count_by_id      – đếm số câu theo loại/mức độ (bảng thống kê nhanh)
"""
from __future__ import annotations

import fnmatch
import re
from collections import Counter, defaultdict

from .parser import ENV_RE, TAG_RE, parse_file
from .idcode import parse_id
from .texutil import find_command, read_command_args


def find_duplicates(paths: list[str]):
    """Trả về danh sách nhóm câu trùng: [[(file, số_thứ_tự, ID), ...], ...]."""
    groups = defaultdict(list)
    for p in paths:
        for i, q in enumerate(parse_file(p), 1):
            groups[q.fingerprint].append((p, i, q.id_code))
    return [g for g in groups.values() if len(g) > 1]


def filter_by_id(paths: list[str], pattern: str, out_path: str, qtype: str | None = None) -> int:
    """Chép nguyên văn các khối ex/bt có ID khớp mẫu (* ?) sang file mới."""
    pattern = pattern.strip().upper() or "*"
    blocks = []
    for p in paths:
        for q in parse_file(p):
            if qtype and q.qtype != qtype:
                continue
            if fnmatch.fnmatchcase(q.id_code or "", pattern):
                blocks.append(q.raw)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocks) + "\n")
    return len(blocks)


def erase_solutions_text(text: str) -> tuple[str, int]:
    out, n, i = [], 0, 0
    while True:
        p = find_command(text, "loigiai", i)
        if p < 0:
            out.append(text[i:])
            break
        _, args, end = read_command_args(text, p + len("\\loigiai"), 1, optional=False)
        if not args:
            out.append(text[i:p + 1])
            i = p + 1
            continue
        # bỏ luôn khoảng trắng đầu dòng trước \loigiai nếu dòng chỉ còn trống
        head = text[i:p]
        ls = head.rfind("\n")
        if ls >= 0 and not head[ls + 1:].strip():
            head = head[:ls]
        out.append(head)
        i = end
        n += 1
    return "".join(out), n


def erase_solutions(path: str, out_path: str) -> int:
    with open(path, encoding="utf-8") as f:
        text, n = erase_solutions_text(f.read())
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return n


def convert_ids_text(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    """Đổi tiền tố ID trong các nhãn %[...] ở dòng \\begin{ex}. mapping: {'0D2': '0D3', ...}."""
    items = sorted(mapping.items(), key=lambda kv: -len(kv[0]))
    count = 0

    def fix_tag(m):
        nonlocal count
        tag = m.group(1)
        if not parse_id(tag):
            return m.group(0)
        for old, new in items:
            if tag.upper().startswith(old.upper()):
                count += 1
                return f"%[{new.upper()}{tag[len(old):]}]"
        return m.group(0)

    def fix_block(m):
        first, sep, rest = m.group(0).partition("\n")
        return TAG_RE.sub(fix_tag, first) + sep + rest

    return ENV_RE.sub(fix_block, text), count


def convert_ids(path: str, out_path: str, mapping: dict[str, str]) -> int:
    with open(path, encoding="utf-8") as f:
        text, n = convert_ids_text(f.read(), mapping)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return n


def count_by_id(paths: list[str]):
    """Đếm theo (loại, mức độ) và theo tiền tố lớp-môn-chương."""
    by_type, by_chapter = Counter(), Counter()
    for p in paths:
        for q in parse_file(p):
            idc = parse_id(q.id_code) if q.id_code else None
            by_type[(q.qtype, idc.muc_do if idc else "?")] += 1
            by_chapter[(idc.lop + idc.mon + idc.chuong) if idc else "?"] += 1
    return by_type, by_chapter


def parse_mapping(text: str) -> dict[str, str]:
    """Đọc bảng ánh xạ dạng nhiều dòng 'cũ = mới' hoặc 'cũ -> mới'."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*([0-9A-Za-z?]+)\s*(?:=|->|→|,|\s)\s*([0-9A-Za-z]+)\s*$", line)
        if m:
            out[m.group(1).upper()] = m.group(2).upper()
    return out


# ---------------------------------------------------------------- công cụ bổ sung
def get_answers(paths: list[str]):
    """Lấy bảng đáp án từ file đề: [(file, phần, số câu trong phần, ID, đáp án)]."""
    out = []
    for p in paths:
        counters = Counter()
        for q in parse_file(p):
            counters[q.qtype] += 1
            out.append((p, q.qtype, counters[q.qtype], q.id_code, q.answer_text))
    return out


def add_tag_text(text: str, tag: str) -> tuple[str, int]:
    """Chèn nhãn %[tag] (vd nguồn đề) vào dòng \\begin{ex} của mọi câu chưa có nhãn đó."""
    n = 0

    def fix(m):
        nonlocal n
        first, sep, rest = m.group(0).partition("\n")
        if f"%[{tag}]" in first:
            return m.group(0)
        n += 1
        env_end = first.index("}") + 1           # sau \begin{ex}
        return first[:env_end] + f"%[{tag}]" + first[env_end:] + sep + rest

    return ENV_RE.sub(fix, text), n


def add_tag(path: str, out_path: str, tag: str) -> int:
    with open(path, encoding="utf-8") as f:
        text, n = add_tag_text(f.read(), tag)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return n


def sort_by_id(paths: list[str], out_path: str) -> int:
    """Gộp các file và sắp xếp câu theo loại câu rồi theo ID."""
    order = {"TN": 0, "DS": 1, "KQ": 2, "TL": 3}
    qs = [q for p in paths for q in parse_file(p)]
    qs.sort(key=lambda q: (order[q.qtype], q.id_code or "~"))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(q.raw for q in qs) + "\n")
    return len(qs)


def shuffle_file(path: str, codes: list[str], out_dir: str, *, seed=None, options=None,
                 template_path=None, ten_de="ĐỀ KIỂM TRA", truong="", thoi_gian=90):
    """Trộn trực tiếp một file đề .tex thành nhiều mã đề (không cần nạp vào kho)."""
    import random

    from .exporter import export_versions
    from .generator import mix_versions, sections_from_questions
    versions = mix_versions(sections_from_questions(parse_file(path)), codes, random.Random(seed), options)
    files = export_versions(versions, out_dir, template_path=template_path, ten_de=ten_de,
                            truong=truong, thoi_gian=thoi_gian)
    return versions, files
