"""Bộ công cụ xử lý tệp .tex hàng loạt cho Tab Tiện ích 2 (chuẩn MyLT 2026)."""
from __future__ import annotations
from pathlib import Path
import random
import re


EX_BLOCK_RE = re.compile(r"\\begin\{ex\}.*?\\end\{ex\}", re.DOTALL)
ID_RE = re.compile(r"%\[([0-9A-Za-z\-]+)\]")


def extract_ex_blocks(tex: str) -> list[str]:
    return EX_BLOCK_RE.findall(tex)


def check_tex_questions(tex: str) -> list[str]:
    """Kiểm tra lỗi phổ biến trong tệp .tex (ngoặc, thiếu \\True, thiếu ID, thiếu \\end{ex})."""
    issues: list[str] = []
    n_begin = len(re.findall(r"\\begin\{ex\}", tex))
    n_end = len(re.findall(r"\\end\{ex\}", tex))
    if n_begin != n_end:
        issues.append(f"Lệch số cặp môi trường ex: {n_begin} \\begin{{ex}} nhưng có {n_end} \\end{{ex}}.")

    blocks = extract_ex_blocks(tex)
    for idx, blk in enumerate(blocks, start=1):
        if not ID_RE.search(blk):
            issues.append(f"Câu {idx}: Thiếu mã ID dạng %[...].")
        if r"\choice" in blk and r"\choiceTF" not in blk and r"\True" not in blk:
            issues.append(f"Câu {idx}: Trắc nghiệm \\choice nhưng chưa đánh dấu \\True.")
        if blk.count("{") != blk.count("}"):
            issues.append(f"Câu {idx}: Lệch dấu ngoặc nhọn {{ }} ({blk.count('{')} mở / {blk.count('}')} đóng).")
    if not issues:
        issues.append(f"Hợp lệ: Đã kiểm tra {len(blocks)} câu hỏi, không phát hiện lỗi cú pháp cơ bản.")
    return issues


def load_convid_map(convid_path: Path) -> dict[str, str]:
    """Đọc bảng ánh xạ chuyển ID từ tệp ConvID_*.tex."""
    mapping: dict[str, str] = {}
    text = Path(convid_path).read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        # Hỗ trợ cả định dạng old->new, old=new, old\tnew, hoặc [old] [new]
        m = re.match(r"^\[?([0-9A-Za-z\-]+)\]?\s*(?:->|=>|=|\s+)\s*\[?([0-9A-Za-z\-]+)\]?", line)
        if m:
            mapping[m.group(1)] = m.group(2)
    return mapping


def convert_ids_in_tex(tex: str, convid_path: Path) -> tuple[str, int]:
    """Chuyển hàng loạt mã ID trong tệp .tex dựa theo tệp ConvID_*.tex."""
    mapping = load_convid_map(convid_path)
    count = 0

    def _repl(m: re.Match) -> str:
        nonlocal count
        old_id = m.group(1)
        if old_id in mapping:
            count += 1
            return f"%[{mapping[old_id]}]"
        # Thử khớp tiền tố 5 ký tự (bỏ mức độ / dạng nếu bảng ConvID map theo bài)
        for prefix_len in (6, 5, 4, 3):
            if len(old_id) >= prefix_len and old_id[:prefix_len] in mapping:
                count += 1
                return f"%[{mapping[old_id[:prefix_len]]}{old_id[prefix_len:]}]"
        return m.group(0)

    new_tex = ID_RE.sub(_repl, tex)
    return new_tex, count


def _replace_blocks(tex: str, new_blocks: list[str]) -> str:
    it = iter(new_blocks)
    return EX_BLOCK_RE.sub(lambda _: next(it), tex)


def shuffle_questions_in_tex(tex: str, seed: int | None = None) -> str:
    """Trộn thứ tự toàn bộ câu hỏi \\begin{ex}...\\end{ex} trong tệp."""
    blocks = extract_ex_blocks(tex)
    rng = random.Random(seed)
    rng.shuffle(blocks)
    return _replace_blocks(tex, blocks)


def sort_questions_by_id(tex: str) -> str:
    """Sắp xếp câu hỏi theo mã ID tăng dần."""
    blocks = extract_ex_blocks(tex)
    blocks.sort(key=lambda b: (ID_RE.search(b).group(1) if ID_RE.search(b) else "ZZZZ"))
    return _replace_blocks(tex, blocks)


def _extract_braced_args(text: str, start_idx: int, count: int = 4) -> list[tuple[int, int, str]]:
    """Tách đúng `count` đối số {...} liên tiếp bắt đầu từ start_idx."""
    args: list[tuple[int, int, str]] = []
    i = start_idx
    n = len(text)
    while len(args) < count and i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n or text[i] != "{":
            break
        arg_start = i
        depth = 0
        while i < n:
            if text[i] == "{" and (i == 0 or text[i - 1] != "\\"):
                depth += 1
            elif text[i] == "}" and (i == 0 or text[i - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    args.append((arg_start, i + 1, text[arg_start + 1 : i]))
                    i += 1
                    break
            i += 1
    return args


def _transform_choice_in_block(blk: str, mode: str = "shuffle") -> str:
    m = re.search(r"\\choice(?!TF)\b", blk)
    if not m:
        return blk
    args = _extract_braced_args(blk, m.end(), 4)
    if len(args) != 4:
        return blk
    contents = [a[2] for a in args]
    if mode == "shuffle":
        random.shuffle(contents)
    elif mode == "move_true_a":
        true_idx = next((i for i, c in enumerate(contents) if r"\True" in c), -1)
        if true_idx > 0:
            contents[0], contents[true_idx] = contents[true_idx], contents[0]
    rebuilt = "\n".join(f"{{{c}}}" for c in contents)
    return blk[: args[0][0]] + rebuilt + blk[args[-1][1] :]


def shuffle_choices_in_tex(tex: str) -> str:
    blocks = [_transform_choice_in_block(b, "shuffle") for b in extract_ex_blocks(tex)]
    return _replace_blocks(tex, blocks)


def move_true_to_a(tex: str) -> str:
    blocks = [_transform_choice_in_block(b, "move_true_a") for b in extract_ex_blocks(tex)]
    return _replace_blocks(tex, blocks)


def add_dapso_in_tex(tex: str) -> str:
    """Tự động chèn \\dapso{A/B/C/D} vào cuối mỗi câu \\choice nếu chưa có."""
    new_blocks: list[str] = []
    for blk in extract_ex_blocks(tex):
        if r"\dapso{" in blk:
            new_blocks.append(blk)
            continue
        m = re.search(r"\\choice(?!TF)\b", blk)
        if m:
            args = _extract_braced_args(blk, m.end(), 4)
            if len(args) == 4:
                true_idx = next((i for i, a in enumerate(args) if r"\True" in a[2]), -1)
                if true_idx >= 0:
                    letter = "ABCD"[true_idx]
                    blk = blk.replace(r"\end{ex}", f"\\dapso{{{letter}}}\n\\end{{ex}}", 1)
        new_blocks.append(blk)
    return _replace_blocks(tex, new_blocks)


def make_input_master_tex(tex_paths: list[Path]) -> str:
    """Tạo mã nguồn chèn nhiều tệp .tex bằng lệnh \\input{...}."""
    lines = [
        r"\documentclass[12pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[vietnamese]{babel}",
        r"\usepackage{amsmath,amssymb,ex_test}",
        r"\begin{document}",
    ]
    for p in tex_paths:
        lines.append(f"\\input{{{Path(p).as_posix()}}}")
    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"


def assign_single_id(tex: str, new_id: str) -> str:
    """Gán tất cả các câu hỏi trong tệp theo cùng 1 mã ID."""
    new_id = new_id.strip().strip("%[]")
    if not new_id:
        return tex
    out: list[str] = []
    for blk in extract_ex_blocks(tex):
        if ID_RE.search(blk):
            blk = ID_RE.sub(f"%[{new_id}]", blk, count=1)
        else:
            blk = blk.replace(r"\begin{ex}", f"\\begin{{ex}}%[{new_id}]", 1)
        out.append(blk)
    return _replace_blocks(tex, out)


def process_ids(tex: str, action: str = "remove") -> str:
    """Xử lý ID: 'remove' (Xoá ID), 'hide' (Ẩn ID dạng comment), 'show' (Hiện ID)."""
    if action == "remove":
        return ID_RE.sub("", tex)
    if action == "hide":
        return re.sub(r"\\textbf\{\[([0-9A-Za-z\-]+)\]\}", r"%[\1]", tex)
    if action == "show":
        return ID_RE.sub(lambda m: f"%[{m.group(1)}] \\textbf{{[{m.group(1)}]}}", tex)
    return tex


def extract_answer_string(tex: str) -> str:
    """Lấy chuỗi đáp án trắc nghiệm (VD: ABCDAC...) từ tệp TeX."""
    ans: list[str] = []
    for blk in extract_ex_blocks(tex):
        m = re.search(r"\\choice(?!TF)\b", blk)
        if not m:
            continue
        args = _extract_braced_args(blk, m.end(), 4)
        if len(args) == 4:
            idx = next((i for i, a in enumerate(args) if r"\True" in a[2]), -1)
            ans.append("ABCD"[idx] if idx >= 0 else "-")
    return "".join(ans)


def apply_answer_string(tex: str, answer_str: str) -> str:
    """Đặt đáp án \\True cho các câu \\choice theo chuỗi đáp án (VD: ABCD...)."""
    letters = [c.upper() for c in answer_str if c.upper() in "ABCD"]
    it = iter(letters)
    new_blocks: list[str] = []
    for blk in extract_ex_blocks(tex):
        m = re.search(r"\\choice(?!TF)\b", blk)
        if not m:
            new_blocks.append(blk)
            continue
        args = _extract_braced_args(blk, m.end(), 4)
        target = next(it, None)
        if len(args) == 4 and target is not None:
            t_idx = "ABCD".index(target)
            cleaned = [re.sub(r"\\True\s*", "", a[2]).strip() for a in args]
            cleaned[t_idx] = f"\\True {cleaned[t_idx]}"
            rebuilt = "\n".join(f"{{{c}}}" for c in cleaned)
            blk = blk[: args[0][0]] + rebuilt + blk[args[-1][1] :]
        new_blocks.append(blk)
    return _replace_blocks(tex, new_blocks)


def remove_blank_lines(tex: str) -> str:
    return "\n".join(ln for ln in tex.splitlines() if ln.strip()) + "\n"


def generate_sample_code(
    count: int = 5,
    kind: str = "tn",
    include_sol: bool = True,
    true_at_a: bool = True,
    start_num: int | None = None,
    info_header: str = "",
) -> str:
    """Sinh nhanh khung code mẫu ex_test (Trắc nghiệm / Đúng sai / Tự luận)."""
    blocks: list[str] = []
    for i in range(count):
        prefix = f"% Câu {start_num + i}\n" if start_num is not None else ""
        hdr = f"% {info_header}\n" if info_header.strip() else ""
        if kind == "tn":
            a_mark = "\\True " if true_at_a else ""
            body = (
                "\\begin{ex}%[2D1N1-1]\nNội dung câu hỏi...\n\\choice\n"
                f"{{{a_mark}Phương án A}}\n{{Phương án B}}\n{{Phương án C}}\n{{Phương án D}}\n"
            )
        elif kind == "ds":
            body = (
                "\\begin{ex}%[2D1H1-1]\nNội dung câu hỏi đúng sai...\n\\choiceTF\n"
                "{\\True Mệnh đề a}\n{Mệnh đề b}\n{\\True Mệnh đề c}\n{Mệnh đề d}\n"
            )
        else:
            body = "\\begin{ex}%[2D1V1-1]\nNội dung câu hỏi tự luận...\n"
        sol = "\\loigiai{\nLời giải chi tiết...\n}\n" if include_sol else ""
        blocks.append(f"{prefix}{hdr}{body}{sol}\\end{{ex}}")
    return "\n\n".join(blocks) + "\n"


def assign_ids_from_reference_tex(tex: str, ref_tex: str) -> tuple[str, int]:
    """Gán mã ID cho các câu trong `tex` theo thứ tự ID tương ứng của tệp `ref_tex`."""
    ref_ids: list[str] = []
    for blk in extract_ex_blocks(ref_tex):
        m = ID_RE.search(blk)
        ref_ids.append(m.group(1) if m else "")
    out: list[str] = []
    changed = 0
    for idx, blk in enumerate(extract_ex_blocks(tex)):
        if idx < len(ref_ids) and ref_ids[idx]:
            nid = ref_ids[idx]
            if ID_RE.search(blk):
                blk = ID_RE.sub(f"%[{nid}]", blk, count=1)
            else:
                blk = blk.replace(r"\begin{ex}", f"\\begin{{ex}}%[{nid}]", 1)
            changed += 1
        out.append(blk)
    return _replace_blocks(tex, out), changed


def process_exam_info(tex: str, action: str = "add", info: str = "", env: str = "ex") -> str:
    """Thêm hoặc xoá thông tin đề dạng %[Thông tin đề] ngay trước/sau \\begin{env}."""
    info = info.strip().strip("%[]")
    if action == "remove":
        return re.sub(r"%\[[^\]]*?(?:Đề|SGD|THPT|HK|GK|Thi|Năm)[^\]]*\]", "", tex, flags=re.IGNORECASE)
    if action == "add" and info:
        pat = re.compile(rf"(\\begin\{{{re.escape(env)}\}})")
        return pat.sub(rf"\1%[{info}]", tex)
    return tex


def number_questions_in_tex(
    tex: str,
    action: str = "add",
    start: int = 1,
    before_begin: bool = True,
    env: str = "ex",
) -> str:
    """Thêm hoặc xoá comment đánh số câu hỏi (% Câu 1, % Câu 2...)."""
    if action == "remove":
        return re.sub(r"(?m)^[ \t]*%\s*Câu\s+\d+\s*\.?\s*\r?\n?", "", tex)
    counter = [start]
    pat = re.compile(rf"\\begin\{{{re.escape(env)}\}}")

    def _repl(m: re.Match) -> str:
        n = counter[0]
        counter[0] += 1
        if before_begin:
            return f"% Câu {n}\n{m.group(0)}"
        return f"{m.group(0)} % Câu {n}"

    return pat.sub(_repl, tex)


def format_code_indent(tex: str) -> str:
    """Căn lề gọn mã nguồn câu hỏi ex_test."""
    lines: list[str] = []
    indent = 0
    for raw in tex.splitlines():
        s = raw.strip()
        if s.startswith((r"\end{ex}", r"\end{bt}", r"\end{vd}", r"\end{tikzpicture}", "}")):
            indent = max(0, indent - 1)
        lines.append(("  " * indent) + s if s else "")
        if s.startswith((r"\begin{ex}", r"\begin{bt}", r"\begin{vd}", r"\begin{tikzpicture}", r"\loigiai{")):
            indent += 1
    return "\n".join(lines) + "\n"


def split_tex_by_id(tex: str, out_dir: Path) -> int:
    """Tách các câu hỏi ra từng tệp .tex riêng theo mã 3 ký tự đầu (VD: 2D1.tex, 2H2.tex)."""
    groups: dict[str, list[str]] = {}
    for blk in extract_ex_blocks(tex):
        m = ID_RE.search(blk)
        key = m.group(1)[:3].upper() if m else "CHUA_CO_ID"
        groups.setdefault(key, []).append(blk)
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, blks in groups.items():
        (out_dir / f"{key}.tex").write_text("\n\n".join(blks) + "\n", encoding="utf-8")
    return len(groups)


def split_tex_by_chunk(tex: str, out_dir: Path, stem: str = "tach", chunk_size: int = 100) -> int:
    """Tách tệp chứa hàng trăm/hàng ngàn câu hỏi thành nhiều tệp, mỗi tệp tối đa `chunk_size` câu (mặc định 100)."""
    blocks = extract_ex_blocks(tex)
    if not blocks:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    files_written = 0
    for start in range(0, len(blocks), chunk_size):
        part = blocks[start : start + chunk_size]
        idx = files_written + 1
        (out_dir / f"{stem}_phan_{idx:02d}.tex").write_text("\n\n".join(part) + "\n", encoding="utf-8")
        files_written += 1
    return files_written
