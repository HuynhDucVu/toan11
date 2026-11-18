"""Tiện ích thao tác chuỗi LaTeX: đọc nhóm {...}, [...] cân bằng."""
from __future__ import annotations


def skip_ws(s: str, i: int) -> int:
    """Bỏ qua khoảng trắng (kể cả xuống dòng) và comment % ... cuối dòng."""
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c == "%" and (i == 0 or s[i - 1] != "\\"):
            j = s.find("\n", i)
            i = n if j < 0 else j + 1
        else:
            break
    return i


def read_group(s: str, i: int, open_ch: str = "{", close_ch: str = "}"):
    """Đọc một nhóm cân bằng bắt đầu tại s[i] == open_ch.

    Trả về (nội_dung_bên_trong, vị_trí_sau_dấu_đóng).
    Bỏ qua \\{ \\} và nội dung comment.
    """
    if i >= len(s) or s[i] != open_ch:
        raise ValueError(f"Mong đợi '{open_ch}' tại vị trí {i}")
    depth = 0
    j = i
    n = len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2  # bỏ qua kí tự được escape: \{ \} \% \\
            continue
        if c == "%":
            k = s.find("\n", j)
            j = n if k < 0 else k + 1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    raise ValueError(f"Thiếu '{close_ch}' cho nhóm mở tại vị trí {i}")


def read_command_args(s: str, start: int, n_args: int | None = None, optional: bool = True):
    """Đọc các tham số sau một lệnh: [opt]{a1}{a2}...

    n_args=None: đọc liên tiếp mọi nhóm {...} có thể.
    Trả về (opt hoặc None, [args], vị_trí_kết_thúc).
    """
    i = start
    opt = None
    if optional:
        k = skip_ws(s, i)
        if k < len(s) and s[k] == "[":
            opt, i = read_group(s, k, "[", "]")
    args = []
    while n_args is None or len(args) < n_args:
        k = skip_ws(s, i)
        if k < len(s) and s[k] == "{":
            a, i = read_group(s, k)
            args.append(a)
        else:
            break
    return opt, args, i


def find_command(s: str, name: str, start: int = 0) -> int:
    """Tìm vị trí lệnh \\name (không khớp \\nameXYZ), bỏ qua trong comment."""
    pat = "\\" + name
    i = start
    while True:
        i = s.find(pat, i)
        if i < 0:
            return -1
        end = i + len(pat)
        nxt = s[end] if end < len(s) else ""
        line_start = s.rfind("\n", 0, i) + 1
        in_comment = _has_unescaped_percent(s[line_start:i])
        if not (nxt.isalpha() or nxt == "@") and not in_comment:
            return i
        i = end


def _has_unescaped_percent(text: str) -> bool:
    j = 0
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "%":
            return True
        j += 1
    return False


def strip_true(text: str) -> tuple[str, bool]:
    """Bỏ \\True khỏi phương án; trả về (nội_dung, là_đáp_án_đúng)."""
    t = text.strip()
    if t.startswith("\\True"):
        return t[len("\\True"):].strip(), True
    return t, False
