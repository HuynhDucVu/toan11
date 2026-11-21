import re
import unicodedata


def strip_accents_vi(text: str) -> str:
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def read_group(s: str, i: int) -> tuple[str | None, int]:
    n = len(s)
    if i >= n or s[i] != "{":
        return None, i
    depth, j = 0, i
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "%":
            nl = s.find("\n", j)
            j = n if nl == -1 else nl + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    return None, i


def read_opt_and_args(s: str, i: int, max_args: int = 4) -> tuple[str, list[str], int]:
    n, opt = len(s), ""

    def skip_ws_comments(pos: int) -> int:
        while pos < n:
            if s[pos].isspace():
                pos += 1
            elif s[pos] == "%":
                nl = s.find("\n", pos)
                pos = n if nl == -1 else nl + 1
            else:
                break
        return pos

    i = skip_ws_comments(i)
    if i < n and s[i] == "[":
        end_opt = s.find("]", i)
        if end_opt != -1:
            opt = s[i + 1 : end_opt].strip()
            i = end_opt + 1

    args: list[str] = []
    for _ in range(max_args):
        i = skip_ws_comments(i)
        if i < n and s[i] == "{":
            grp, next_i = read_group(s, i)
            if grp is None:
                break
            args.append(grp)
            i = next_i
        else:
            break
    return opt, args, i


def normalize_math_symbols(tex: str) -> str:
    tex = re.sub(r"(?<![dt])\\frac\{", r"\\dfrac{", tex)
    tex = re.sub(r"\\iff\b", r"\\Leftrightarrow", tex)
    tex = re.sub(r"\\vec\{([A-Za-z0-9]{2,})\}", r"\\overrightarrow{\1}", tex)
    tex = re.sub(r"\\vec\{([a-zA-Z])\}", r"\\mathbf{\1}", tex)
    tex = re.sub(r"(?<!\\displaystyle)\\int(?![a-zA-Z]|\\limits)", r"\\displaystyle\\int\\limits", tex)
    tex = re.sub(r"\\displaystyle\\int(?!\\limits)", r"\\displaystyle\\int\\limits", tex)
    tex = re.sub(r"\\lim(?![a-zA-Z]|\\limits)", r"\\lim\\limits", tex)
    tex = re.sub(r"(?<!\\displaystyle)\\sum(?![a-zA-Z]|\\limits)", r"\\displaystyle\\sum\\limits", tex)
    return tex


def normalize_short_ans(raw: str) -> str:
    s = raw.strip()
    if s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    return s.replace("{,}", ",").replace("\\,", "").replace(" ", "")
