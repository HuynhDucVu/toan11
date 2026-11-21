"""Tiện ích 2 (theo nhóm chức năng của MyLT): dọn mã, đặt đáp án theo chuỗi, đưa đáp án về A, chuyển mức độ trong ID,
tách/nối file theo ID, tạo mã \\input, xuất toàn bộ kho ra các file theo ID."""
from __future__ import annotations

import copy
import os
import re

from .parser import Question, parse_tex
from .review import _replace_chon_letters, replace_questions_text

ID_RE = re.compile(r"%\[([0-9][A-Z][0-9A-Z])([A-Z])([0-9A-Z])((?:-[0-9A-Z]+)?)\]")
OLD_TO_NEW_LEVEL = {"Y": "N", "B": "H", "K": "V", "G": "C", "T": "C"}


def clean_code(text: str) -> tuple[str, int]:
    """Xoá khoảng trắng cuối dòng, gộp nhiều dòng trống liền nhau, bỏ dòng trống bên trong khối câu hỏi."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    out, inside, removed, blank = [], 0, 0, 0
    for ln in lines:
        if re.match(r"\s*\\begin\{(ex|bt)\}", ln):
            inside += 1
        if not ln.strip():
            if inside or blank:
                removed += 1
                continue
            blank = 1
        else:
            blank = 0
        out.append(ln)
        if re.match(r"\s*\\end\{(ex|bt)\}", ln):
            inside = max(0, inside - 1)
    return "\n".join(out).strip() + "\n", removed


def _permute_tn(q: Question, perm: list[int]) -> Question:
    """perm[i] = chỉ số phương án cũ đặt vào vị trí i; đổi cả «Chọn X» trong lời giải."""
    nq = copy.deepcopy(q)
    L = "ABCD"
    n = len(q.choices)
    nq.choices = [q.choices[i] for i in perm]
    nq.correct = [q.correct[i] for i in perm]
    if n <= 4:
        nq.solution = _replace_chon_letters(q.solution, lambda old: L[perm.index(L.index(old))]
                                            if L.index(old) < n else old)
    return nq


def answers_to_A(text: str) -> tuple[str, int]:
    """Đưa phương án đúng của mọi câu trắc nghiệm về vị trí A (các phương án khác giữ thứ tự)."""
    pairs = []
    for q in parse_tex(text):
        if q.qtype == "TN" and sum(q.correct) == 1 and q.correct[0] is not True:
            k = q.correct.index(True)
            perm = [k] + [i for i in range(len(q.choices)) if i != k]
            pairs.append((q.raw, _permute_tn(q, perm).to_latex(True)))
    return replace_questions_text(text, pairs)


def set_answers(text: str, key: str) -> tuple[str, int, list[str]]:
    """Đặt đáp án theo chuỗi (vd «ABCDA…» cho các câu TN theo thứ tự; dấu cách/phẩy bỏ qua).
    Trả về (văn bản mới, số câu đã đặt, cảnh báo)."""
    letters = [c for c in key.upper() if c in "ABCD"]
    pairs, warn, k = [], [], 0
    for i, q in enumerate(parse_tex(text), 1):
        if q.qtype != "TN":
            continue
        if k >= len(letters):
            warn.append(f"Chuỗi đáp án ngắn hơn số câu trắc nghiệm (dừng ở câu {i}).")
            break
        idx = "ABCD".index(letters[k])
        k += 1
        if idx >= len(q.choices):
            warn.append(f"Câu {i}: không có phương án {letters[k - 1]}.")
            continue
        nq = copy.deepcopy(q)
        nq.correct = [j == idx for j in range(len(q.choices))]
        if nq.correct != q.correct:
            pairs.append((q.raw, nq.to_latex(True)))
    if k < len(letters):
        warn.append(f"Chuỗi đáp án dài hơn số câu trắc nghiệm ({len(letters)} > {k}).")
    new, n = replace_questions_text(text, pairs)
    return new, n, warn


def convert_levels(text: str, mapping: dict | None = None) -> tuple[str, int]:
    """Chuyển mức độ trong ID (kí tự thứ 4), mặc định 5 mức cũ Y/B/K/G/T → 4 mức N/H/V/C."""
    mapping = mapping or OLD_TO_NEW_LEVEL
    n = 0

    def sub(m):
        nonlocal n
        lv = mapping.get(m.group(2), m.group(2))
        if lv != m.group(2):
            n += 1
        return f"%[{m.group(1)}{lv}{m.group(3)}{m.group(4)}]"
    return ID_RE.sub(sub, text), n


def _key(id_code: str, level: str) -> str:
    """Khoá gom nhóm: 'chuong' → 0D2, 'bai' → 0D2-1 (bài), 'dang' → 0D21-2."""
    if not id_code or len(id_code) < 5:
        return "khong_ID"
    base = id_code[:3]
    if level == "chuong":
        return base
    if level == "bai":
        return base + id_code[4]
    return base + id_code[4] + ("-" + id_code.split("-", 1)[1] if "-" in id_code else "")


def split_by_id(paths: list[str], out_dir: str, level: str = "bai") -> list[str]:
    """Tách các file .tex thành từng file theo chương / bài / dạng (tên file = khoá ID)."""
    groups: dict[str, list[str]] = {}
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f:
            for q in parse_tex(f.read()):
                groups.setdefault(_key(q.id_code, level), []).append(q.raw)
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for k, blocks in sorted(groups.items()):
        fp = os.path.join(out_dir, f"{k}.tex")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n\n".join(blocks) + "\n")
        out.append(fp)
    return out


def join_files(paths: list[str], out_path: str) -> int:
    """Nối các câu hỏi của nhiều file thành một file (theo thứ tự file)."""
    blocks = []
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f:
            qs = parse_tex(f.read())
        if qs:
            blocks.append(f"%% ===== {os.path.basename(p)} =====")
            blocks += [q.raw for q in qs]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks) + "\n")
    return sum(1 for b in blocks if not b.startswith("%%"))


def input_code(paths: list[str], base_dir: str | None = None) -> str:
    """Mã \\input{…} để chèn nhiều file .tex vào một file chính (đường dẫn tương đối, dấu /)."""
    out = []
    for p in paths:
        rel = os.path.relpath(p, base_dir) if base_dir else p
        out.append("\\input{" + os.path.splitext(rel)[0].replace("\\", "/") + "}")
    return "\n".join(out) + "\n"


def export_bank_by_id(bank, out_dir: str, level: str = "bai") -> list[str]:
    """Xuất toàn bộ kho câu hỏi ra các file .tex theo chương / bài / dạng."""
    groups: dict[str, list[str]] = {}
    for q in bank.search():
        groups.setdefault(_key(q.id_code, level), []).append(q.to_latex(True))
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for k, blocks in sorted(groups.items()):
        fp = os.path.join(out_dir, f"{k}.tex")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n\n".join(blocks) + "\n")
        out.append(fp)
    return out


# ---------------------------------------------------------------- bổ sung (theo MyLT 1.0.2.58+)
def add_dapso(text: str) -> tuple[str, int]:
    """Chèn \\dapso{A/B/C/D} cuối mỗi câu trắc nghiệm một đáp án (chưa có)."""
    pairs = []
    for q in parse_tex(text):
        if q.qtype == "TN" and sum(q.correct) == 1 and "\\dapso" not in q.raw:
            raw = q.raw
            pairs.append((raw, raw.replace("\\end{ex}", f"\\dapso{{{'ABCD'[q.correct.index(True)]}}}\n\\end{{ex}}", 1)))
    return replace_questions_text(text, pairs)


def shuffle_questions(text: str, seed=None) -> tuple[str, int]:
    """Xáo thứ tự các câu hỏi trong file (giữ phần còn lại của file)."""
    import random
    qs = parse_tex(text)
    order = list(range(len(qs)))
    random.Random(seed).shuffle(order)
    pairs = [(qs[i].raw, f"\x00{k}\x00") for k, i in enumerate(order)]
    marker, _ = replace_questions_text(text, pairs)
    for k, i in enumerate(order):
        marker = marker.replace(f"\x00{k}\x00", qs[i].raw, 1)
    return marker, len(qs)


def shuffle_choices_in_file(text: str, seed=None) -> tuple[str, int]:
    """Trộn phương án A–D từng câu trắc nghiệm (đổi cả «Chọn X» trong lời giải)."""
    import random
    from .generator import shuffle_choices
    rng = random.Random(seed)
    pairs = []
    for q in parse_tex(text):
        if q.qtype == "TN":
            nq = shuffle_choices(q, rng)
            if nq.choices != q.choices:
                pairs.append((q.raw, nq.to_latex(True)))
    return replace_questions_text(text, pairs)


def sort_by_id_text(text: str) -> tuple[str, int]:
    """Sắp xếp các câu hỏi trong file theo ID (câu chưa có ID đứng cuối)."""
    qs = parse_tex(text)
    order = sorted(range(len(qs)), key=lambda i: (qs[i].id_code or "~", i))
    marker, _ = replace_questions_text(text, [(qs[k].raw, f"\x00{k}\x00") for k in range(len(qs))])
    for k, i in enumerate(order):
        marker = marker.replace(f"\x00{k}\x00", qs[i].raw, 1)
    return marker, len(qs)


def assign_group_id(text: str, new_id: str, only_missing: bool = False) -> tuple[str, int]:
    """Gán cùng một ID cho mọi câu trong file (hoặc chỉ câu chưa có ID)."""
    new_id = new_id.strip().strip("%[]").upper()
    pairs = []
    for q in parse_tex(text):
        if only_missing and q.id_code:
            continue
        nq = copy.deepcopy(q)
        nq.set_id(new_id)
        pairs.append((q.raw, nq.raw))
    return replace_questions_text(text, pairs)


def hide_show_ids(text: str, action: str) -> tuple[str, int]:
    """'remove' xoá ID; 'show' in ID nhỏ sau câu; 'hide' bỏ phần in ID (giữ %[ID])."""
    n = 0

    def rm(m):
        nonlocal n
        n += 1
        return ""
    if action == "remove":
        return ID_RE.sub(rm, text), n
    if action == "show":
        def sh(m):
            nonlocal n
            n += 1
            return f"{m.group(0)}\\textbf{{[{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}]}}"
        return ID_RE.sub(sh, text), n
    return re.sub(r"\\textbf\{\[[0-9A-Z]{3}[A-Z][0-9A-Z](?:-[0-9A-Z]+)?\]\}", rm, text), n
